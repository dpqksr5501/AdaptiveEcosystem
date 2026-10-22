// Integrated native v3 tags and movement-owned binding state.
// Deer now carry the existing Social fragments plus FEcoV3SocialBridgeFragment.
// Social supplies Request/Feedback through the native control hook; no second movement writer.
// V1 HerbivoreTag/legacy steering and flat-test tags remain absent. Client remains presentation-only.

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
    /** Region handoff refreshes local observation caches without reinitializing the body or reserve. */
    bool bRefreshObservation=false;
    /** Immutable last observed native prey, copied for representation only; never used by policy. */
    FVector LastSeenPreyPosition=FVector::ZeroVector;
    int64 LastSeenPreyKey=0;
    double LastSeenPreyTime=-1;

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
