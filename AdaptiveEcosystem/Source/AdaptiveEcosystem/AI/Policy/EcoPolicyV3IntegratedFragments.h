// 팀 통합 레벨에서 v3 R1b 두뇌로 도는 사슴·늑대의 태그와 조각 ("몸은 팀 것, 머리만 우리 것").
//
// 몸(정체성·지역·생체·이동 경로·Lifecycle·발소리·표현·복제 조각)은 팀 조정자 AEcoCreatureIntegrationSpawner 가 만들고 관리한다.
// 판단과 이동은 우리 처리기(EcoPolicyV3IntegratedProcessors)가 v3 조각(EcoPolicyV3Fragments.h)으로 한다.
//
// 평면 시험 맵 경로와 섞이지 않는다:
//   평면 시험 개체 = FEcoPolicyV3Tag / FEcoThreatV3Tag (UEcoPolicyV3StepProcessor·VisualProcessor 만 본다)
//   통합 개체     = FEcoIntegratedPolicyV3Tag / FEcoIntegratedThreatV3Tag (통합 처리기만 본다)
// 팀 처리기와도 섞이지 않는다: 통합 v3 사슴에는 FEcoHerbivoreTag·Social 조각이 없고, 늑대에는 FEcoPredatorTag·FEcoPreySenseFragment 가
// 없다. 그래서 v1 정책 사슬·Social 8종·팀 늑대 감각/이동/포획 처리기의 쿼리에 걸리지 않는다 (목록은 EcoCreatureV3Trait.h 머리말).
//
// AGENTS.md 2절 3항: 개체별 상태는 개체별 Entity Fragment 에 둔다(Shared Fragment 아님). 논리 상태는 서버·단독에만 있다(2절 2항).

#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"

#include "EcoPolicyV3IntegratedFragments.generated.h"

/** 팀 통합 레벨의 v3 R1b 사슴 (팀 몸 + 우리 두뇌). */
USTRUCT()
struct FEcoIntegratedPolicyV3Tag : public FMassTag
{
	GENERATED_BODY()
};

/** 팀 통합 레벨의 v3 늑대 (팀 몸 + 학습 위협 규칙 EcoThreatV3::Step). */
USTRUCT()
struct FEcoIntegratedThreatV3Tag : public FMassTag
{
	GENERATED_BODY()
};

/**
 * 통합 개체 하나의 연결 상태 (입양 여부, 지면 높이, 막힘·사망 기록).
 * 논리 위치는 v3 조각(FEcoHerbivoreBodyV3Fragment·FEcoThreatStateFragment)의 파이썬 단위 값이 진실값이고,
 * 높이는 지형을 따라 여기에 둔다 — 화면은 PrevGroundZ → GroundZ 를 결정 스텝 사이에 보간한다.
 */
USTRUCT()
struct FEcoIntegratedV3Fragment : public FMassFragment
{
	GENERATED_BODY()

	/** 우리 처리기가 v3 상태를 만들었는가 (조정자가 막 만든 개체는 거짓). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	bool bAdopted = false;

	/** v3 가 죽음을 정했다 (잡힘·굶음). 그 뒤로 이 개체는 스텝에 들어가지 않고 화면은 죽은 자리에 멈춘다. */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	bool bDead = false;

	/** 사망 원인 (EcoWorldV3::kDeath*: 0 없음, 1 잡힘, 2 굶음). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	uint8 DeathCause = 0;

	/** 지역 무대 번호 (UEcoPolicyV3IntegratedSubsystem 의 컨텍스트 색인). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	int32 ContextIndex = INDEX_NONE;

	/** 이번 결정 스텝 위치의 지면 높이 (cm). */
	double GroundZ = 0.0;

	/** 지난 결정 스텝 위치의 지면 높이 (cm). 화면 보간 전용. */
	double PrevGroundZ = 0.0;

	/** 지형·장애물에 막혀 이동 전 자리에 남은 결정 스텝 수 (기록). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	int32 BlockedMoves = 0;

	/** 이 사슴이 마지막으로 먹은 [EcoV3I] 기록 구간 번호 (FEcoV3RegionContext::LogEpoch). '구간에 한 번이라도 먹은 사슴' 세기 전용. */
	int32 AteLogEpoch = INDEX_NONE;

	/** 이 사슴이 마지막으로 번식한 전역 스텝 (번식 = 에너지 0.9 초과 → 0.5, 학습 세계 규칙). 화면 표시 전용, 없으면 -1. */
	int64 ReproducedStep = -1;
};
