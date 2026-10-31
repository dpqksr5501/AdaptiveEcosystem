// v3 R1b 사슴·늑대 Mass 프로세서 — 우리 정책 시험 경로(AEcoPolicyTestSpawner) 전용.
//
// 두 프로세서 (둘 다 Server|Standalone, PrePhysics, 게임 스레드. 세계 상태를 가진 UEcoPolicyV3Subsystem 을 함께 쓰기 때문이다):
//
//   1. UEcoPolicyV3StepProcessor   결정 시계(StepSeconds = 8/60 s, 7.5 Hz)가 넘긴 스텝 수만큼 EcoWorldV3::Step 을 돈다.
//      한 스텝 안의 순서 (계약 POLICY_CONTRACT_V3.md 10-2 — EcoWorldV3.h 머리말에 자세히):
//        Arbiter Commit(지난 틱에 정한 요청) → Control → 사슴 이동 → ThreatStep(늑대, EcoThreatModel) → 포획 정리
//        → 섭식·대사·번식·사망·피식 EMA·먹이 재생 → t+1·Tick·어둠 → 관측(지각·Perceive·관측 18) → 리스폰(그 행만 다시 관측)
//        → Prepare·마스크(판 2)·추론(EcoPolicyV3) → 다음 틱 요청 저장
//      모든 사슴·늑대가 같은 전역 스텝에서 처리된다 (계약 10-1 — v1 의 개체별 위상 분산을 쓰지 않는다).
//      개체는 조각의 슬롯 번호 순서로 모은다(쿼리 청크 순서와 무관) — 동점 규칙·결정성·기준 루프와의 파리티를 위해서다.
//
//   2. UEcoPolicyV3VisualProcessor 매 프레임 Transform·Velocity 를 쓴다 — 논리 위치(파이썬 단위)의 지난 스텝→이번 스텝을
//      시계 진행으로 보간한 **화면용** 값이다. 논리 상태는 바꾸지 않는다 (화면은 한 스텝 늦게 따라간다).
//
// v1 과 섞이지 않는다: 두 쿼리는 FEcoPolicyV3Tag / FEcoThreatV3Tag 를 요구하고, v1 프로세서는 FEcoHerbivoreTag /
// FEcoPredatorTag 를 요구한다. v3 개체에는 v1 태그가 없다.

#pragma once

#include "CoreMinimal.h"
#include "MassEntityQuery.h"
#include "MassProcessor.h"

#include "EcoWorldV3.h"

#include "EcoPolicyV3Processors.generated.h"

struct FEcoBehaviorStateFragment;

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPolicyV3StepProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoPolicyV3StepProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery HerbivoreQuery;
	FMassEntityQuery ThreatQuery;

	/** 슬롯 순서 보기 (실행마다 다시 모은다). */
	TArray<EcoWorldV3::FHerbView> HerbViews;
	TArray<FEcoBehaviorStateFragment*> HerbStates;
	TArray<EcoWorldV3::FThreatAgent*> ThreatViews;

	/** 슬롯이 비거나 겹쳤다는 오류를 한 번만 남긴다. */
	bool bReportedBadSlots = false;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPolicyV3VisualProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoPolicyV3VisualProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery HerbivoreQuery;
	FMassEntityQuery ThreatQuery;
};
