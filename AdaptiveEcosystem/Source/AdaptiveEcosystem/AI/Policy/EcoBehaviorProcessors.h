// §9.4 PolicyProcessor + §9.5 SteeringProcessor.
//
// 실행 순서 (§9.5 "Policy → Steering → 이동", MASS_PROCESSOR_ORDER.md "… → Interaction → Lifecycle"):
//
//   1. UEcoNeighborhoodGatherProcessor   산 초식 + 포식자를 색인에 넣는다 (매 틱)
//   2. UEcoPerceptionProcessor           산 초식의 §3.3 기하 입력         (매 틱)
//   3. UEcoPolicyProcessor               산 초식 관측 7개 → 행동 4개      (StepSeconds 마다)
//   4. UEcoSteeringProcessor             산 초식 조향 → 속도·위치·yaw     (매 틱)
//   5. UEcoPredationProcessor            포획 판정. 잡히면 HP=0(즉시) + Alive→PendingDeath(지연)
//   6. (페이즈 끝) 지연 명령 반영. 시체는 다음 틱부터 1~5 어디에도 걸리지 않는다
//
// 1과 2가 나뉘어 있는 이유: 색인이 **모든** 개체를 담은 뒤에야 조회가 맞다.
// 2와 3이 나뉜 이유: 조향은 매 틱 기하가 필요한데 정책은 StepSeconds(0.133초)마다만 돈다.
// 주기는 프레임 수가 아니라 시간으로 센다 (EcoPolicyClock.h) — FPS 가 바뀌어도 같다.
// 초식 쿼리는 전부 FEcoAliveTag 를 요구한다. 포식자 쿼리는 요구하지 않는다.
//
// 스레드: 이 첫 판은 전부 게임 스레드에서 돈다. 서브시스템 색인을 공유하기 때문이다.
// 병렬화는 색인을 읽기 전용으로 굳힌 뒤의 최적화 과제다.

#pragma once

#include "CoreMinimal.h"
#include "MassEntityQuery.h"
#include "MassProcessor.h"

#include "EcoPolicyClock.h"

#include "EcoBehaviorProcessors.generated.h"

/** §9.4 — 색인 채우기. 초식과 포식자를 모두 넣는다. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoNeighborhoodGatherProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoNeighborhoodGatherProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery HerbivoreQuery;
	FMassEntityQuery PredatorQuery;
};

/** §3.3 기하 입력 계산. 조향과 관측이 같은 값을 보게 한다. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPerceptionProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoPerceptionProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery EntityQuery;
};

/**
 * §9.4 — 관측 7개를 만들고 정책을 돌려 행동 4개를 낸다.
 *
 * `ExecutionFlags = Server`: 논리 상태는 서버/스탠드얼론에만 존재한다 (AGENTS.md §2.2).
 * 콘솔 변수 `eco.UseLearnedPolicy` 로 학습 정책과 §5.1 Utility 비교군을 갈아끼운다.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPolicyProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoPolicyProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery EntityQuery;

	/** §9.4 프레임 dt → 논리 틱. 결정 주기를 FPS 와 분리한다. */
	EcoPolicy::FStepClock StepClock;
};

/**
 * §9.6/§9.8-5 — 포식 판정, 피식 보고, 피식 EMA 스텝.
 *
 * 이게 없으면 `recent_predation` 이 영원히 0이고, 그러면 §5.1 Utility 비교군의
 * `cohesion = k_coh × rp` 와 `flee_dist` 의 rp 항이 통째로 죽는다. 실제로 테스트 레벨에서
 * Utility 의 cohesion 이 0.00 으로 찍혔다. 폐루프를 닫는 조각이다.
 *
 * 포식자 포획만 센다 — 아사는 §3.1 EMA 의 분자가 아니다 (파이썬도 그렇다).
 * 플레이어 사냥은 `UEcoRegionPredationSubsystem::ReportPredation()` 을 직접 부르면 된다 (§9.6).
 * 분모는 틱마다 센 포획 전 생존 초식 수(스텝 안 최대값)이고, StepSeconds 마다 포획 직후에
 * EMA 를 한 번 스텝한다 — 파이썬과 같은 전역 값이다 (UEcoRegionPredationSubsystem 참고).
 *
 * 포획 규칙은 파이썬 §4.2 와 같다 — `Tests/EcoPredationTest.cpp` 가 고정한다:
 *   - **포식자 쪽에서** 판정한다. 초식이 포식자를 봤는지와 무관하다
 *   - 체감 거리 = 거리 × (초식이 은신처 안이면 CoverHideMult)
 *   - 포식자당 한 틱 한 마리, 잡으면 PredEatCooldownS 동안 사냥하지 않는다
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPredationProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoPredationProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	/** 생존 수 보고용. 잡힌 개체의 Vitals 를 쓴다는 선언도 여기서 한다. */
	FMassEntityQuery HerbivoreQuery;
	/** 포획 판정은 파이썬 §4.2 처럼 포식자 쪽에서 한다. */
	FMassEntityQuery PredatorQuery;

	/** §9.6 — StepSeconds 마다 피식 EMA 를 한 번 스텝한다. 포획 판정 직후다. 시간 기준이다. */
	EcoPolicy::FStepClock StepClock;
	/** EMA 스텝 경계까지의 위상 [0, PolicyInterval). */
	int32 EmaPhase = 0;
};

/**
 * §9.5 — §3.3 조향 수식. 파이썬 `env/steering.py` 와 한 줄씩 대응한다.
 * 움직일 때 Transform yaw = 속도 방향(즉시), 멈추면 유지한다 (world.py head 규약, EcoHeading.h).
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoSteeringProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoSteeringProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery EntityQuery;
};
