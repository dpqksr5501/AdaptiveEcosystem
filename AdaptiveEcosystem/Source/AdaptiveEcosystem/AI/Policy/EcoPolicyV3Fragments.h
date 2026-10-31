// v3 R1b 사슴·늑대의 Mass 조각과 태그 (계약 POLICY_CONTRACT_V3.md 12-2, 계획서 RL_V3_UNREAL_TRAINING_PLAN.md 4-5 e3).
//
// 논리 상태는 엔진 무관 헤더의 구조체(EcoWorldV3.h·EcoRepertoire.h·EcoThreatModel.h)를 **그대로** 조각 안에 둔다.
// 프로세서는 슬롯 순서로 이 구조체들을 가리키는 보기(EcoWorldV3::FHerbView)를 모아 EcoWorldV3::Step 을 부른다 — 기준 루프
// (EcoWorldV3::FReferenceWorld)와 같은 단계 함수를 같은 순서로 부르므로 같은 시작이면 논리 상태가 같다.
// 구조체는 모두 trivially copyable 이다(Mass 조각 조건). 리플렉션 밖 칸은 저장·복제되지 않는다 — 복제는 요약 칸(UPROPERTY)의 몫이고
// 복제 설계(계획서 3-2)는 이 단계 밖이다.
//
// AGENTS.md 2절 3항: 개체별 행동 상태와 요청은 Shared Fragment 가 아니라 개체별 Entity Fragment 에 둔다.
// 논리 상태는 서버·단독 월드에만 있다(2절 2항) — 이 조각을 가진 개체는 Server|Standalone 프로세서만 돌린다.
//
// v1 과의 분리:
//   v3 사슴은 FEcoPolicyV3Tag, v3 늑대는 FEcoThreatV3Tag 를 단다. FEcoHerbivoreTag·FEcoPredatorTag·FEcoAliveTag 는 달지 않는다.
//   v1 프로세서(EcoBehaviorProcessors)의 쿼리는 모두 FEcoHerbivoreTag 나 FEcoPredatorTag 를 요구하므로 v3 개체를 보지 않고,
//   v3 프로세서의 쿼리는 위 v3 태그를 요구하므로 v1 개체를 보지 않는다. Social·Creature·Mass 공용 쿼리도 정체성·무리·지역 조각을
//   요구하므로 v3 시험 개체와 맞지 않는다 (통합 레벨에서 Social 을 끄는 일은 팀 몫 — 계획서 4-5 e3).

#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"

#include "EcoWorldV3.h"

#include "EcoPolicyV3Fragments.generated.h"

/** v3 행동 고르기 두뇌(R1b)를 쓰는 사슴. v1 정책·조향·포식 프로세서는 이 개체를 보지 않는다. */
USTRUCT()
struct FEcoPolicyV3Tag : public FMassTag
{
	GENERATED_BODY()
};

/** v3 위협 모델(EcoThreatModel.h)로 움직이는 늑대·플레이어 대역. */
USTRUCT()
struct FEcoThreatV3Tag : public FMassTag
{
	GENERATED_BODY()
};

/**
 * 행동 실행기 상태 (파이썬 RepState 한 행)와 다음 스텝 요청.
 * Rep·Decision 이 논리의 단일 진실값이고, UPROPERTY 칸은 결정 스텝마다 그 값을 옮겨 적는 요약이다(디버거·복제 후보).
 */
USTRUCT()
struct FEcoBehaviorStateFragment : public FMassFragment
{
	GENERATED_BODY()

	/** 행동·위상·경과·seq·잠금·놀람·사건 대기·지연·HIDE 목표·도착·사건 기준값·away·recency·탐지 배수 (계약 5-1). */
	EcoRepertoireV3::FRepState Rep;

	/** 결정 관측·Prepare 결과·마스크·로짓·요청, 그리고 이번 스텝 Commit 기록. */
	EcoWorldV3::FHerbDecision Decision;

	/** 지금 행동 (0 GRAZE, 1 FLEE, 2 HIDE, 3 FREEZE, 4 SLEEP). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	uint8 BehaviorId = 0;

	/** 위상 (0 진입, 1 지속, 2 이탈). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	uint8 PhaseId = 0;

	/** 이번 스텝 보행 (0 정지, 1 걷기, 2 뛰기). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	uint8 GaitId = 0;

	/** 행동이 바뀔 때마다 +1 (mod 256). 리스폰도 +1. */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	uint8 Seq = 0;

	/** 다음 스텝에 Commit 할 요청 (읽지 않는 개체는 지금 행동). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	uint8 PendingRequest = 0;

	/** 다음 스텝 요청을 만든 마스크 (비트 b = 행동 b 허용). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	uint8 PendingMaskBits = 0;

	/** 다음 스텝에 요청을 읽는가 (잠금 끝 또는 사건). */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|PolicyV3")
	bool bPendingReads = false;

	/** 논리 상태를 요약 칸에 옮겨 적는다. */
	void SyncSummary(const EcoRepertoireV3::FControlOutput& Control)
	{
		BehaviorId = static_cast<uint8>(Rep.Behavior);
		PhaseId = static_cast<uint8>(Rep.Phase);
		GaitId = static_cast<uint8>(Control.Gait);
		Seq = static_cast<uint8>(Rep.Seq);
		PendingRequest = static_cast<uint8>(Decision.Request);
		uint8 Bits = 0;
		for (int32 b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
		{
			if (Decision.Mask[b] != 0)
			{
				Bits = static_cast<uint8>(Bits | (1u << b));
			}
		}
		PendingMaskBits = Bits;
		bPendingReads = Decision.Prep.bReads;
	}
};

/** 스텝 끝 지각 (결정 관측 기하 double + 관측 18 float). 다음 스텝의 Arbiter·제어기·망 입력이다. */
USTRUCT()
struct FEcoPerceptionCacheFragment : public FMassFragment
{
	GENERATED_BODY()

	EcoWorldV3::FHerbPerception Perception;
};

/** 이번 스텝 제어기 출력 (속도 단위/스텝, 보행, 섭식·대사 배수, 탐지 배수, 정지, 웅크림, heading 덮기, 은신 배수). */
USTRUCT()
struct FEcoControlOutFragment : public FMassFragment
{
	GENERATED_BODY()

	EcoRepertoireV3::FControlOutput Control;
};

/**
 * 사슴 몸: 파이썬 단위 위치·heading(논리), 에너지, 번식 쿨다운, 슬롯·세대(개체 키), 이번 스텝 사망 기록.
 * FTransformFragment 는 이 값을 cm 로 옮긴 **화면용**이다 — 결정 스텝 사이에는 PrevPos→Pos 를 보간한다(UEcoPolicyV3VisualProcessor).
 */
USTRUCT()
struct FEcoHerbivoreBodyV3Fragment : public FMassFragment
{
	GENERATED_BODY()

	EcoWorldV3::FHerbBody Body;
};

/** 늑대·플레이어 대역 하나 (유형·원거리·야행성·기본 속력·포획 반경, 위치·heading·지난 변위·쿨다운·잠행·플레이어 모드). */
USTRUCT()
struct FEcoThreatStateFragment : public FMassFragment
{
	GENERATED_BODY()

	EcoWorldV3::FThreatAgent Agent;
};
