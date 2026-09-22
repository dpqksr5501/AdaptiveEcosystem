// §9.4 PolicyProcessor + §9.5 SteeringProcessor.
//
// 실행 순서 (§9.5 "Policy → Steering → Mass 이동"):
//
//   1. UEcoNeighborhoodGatherProcessor   개체 위치를 색인에 넣는다 (매 틱)
//   2. UEcoPerceptionProcessor           §3.3 기하 입력을 만든다   (매 틱)
//   3. UEcoPolicyProcessor               관측 7개 → 행동 4개       (PolicyInterval 틱마다)
//   4. UEcoSteeringProcessor             §3.3 조향 → 속도          (매 틱)
//   5. (엔진) Mass 이동
//
// 1과 2가 나뉘어 있는 이유: 색인이 **모든** 개체를 담은 뒤에야 조회가 맞다.
// 2와 3이 나뉜 이유: 조향은 매 틱 기하가 필요한데 정책은 PolicyInterval 틱마다만 돈다.
//
// 스레드: 이 첫 판은 전부 게임 스레드에서 돈다. 서브시스템 색인을 공유하기 때문이다.
// 병렬화는 색인을 읽기 전용으로 굳힌 뒤의 최적화 과제다.

#pragma once

#include "CoreMinimal.h"
#include "MassEntityQuery.h"
#include "MassProcessor.h"

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

	/** §9.6 — PolicyInterval 틱마다 지역 EMA 를 한 번 갱신하기 위한 카운터. */
	int32 TickCounter = 0;
};

/** §9.5 — §3.3 조향 수식. 파이썬 `env/steering.py` 와 한 줄씩 대응한다. */
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
