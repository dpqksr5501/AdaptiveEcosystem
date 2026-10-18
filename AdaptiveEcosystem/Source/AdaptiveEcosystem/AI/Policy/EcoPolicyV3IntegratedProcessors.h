// 팀 통합 레벨의 v3 R1b 사슴·늑대 처리기 (팀 몸 + 우리 두뇌). UEcoPolicyV3IntegratedSubsystem 이 켜져 있을 때만 돈다.
//
// 1. UEcoPolicyV3IntegratedStepProcessor (Server|Standalone, PrePhysics, 게임 스레드)
//    모으기  FEcoIntegratedPolicyV3Tag / FEcoIntegratedThreatV3Tag + FEcoAliveTag 개체를 지역(RegionId)별로, StableAgentId 순으로 모은다.
//            HP <= 0 이거나 v3 가 이미 죽음을 정한 개체는 뺀다 (조정자가 Alive 를 떼고 2 초 뒤 지운다).
//    입양    조정자가 막 만든 개체: Transform 위치·yaw 로 v3 상태를 만든다. 사슴 키 = StableAgentId (계약 12-3), 늑대 종류 = 지역 안
//            StableAgentId 순번 (짝수 잠행, 홀수 추격). 새 사슴만 첫 관측·첫 요청 (ObserveAndDecideRows).
//    스텝    전역 결정 시계가 넘긴 수만큼, 모든 지역이 같은 전역 스텝으로 EcoWorldV3::Step (계약 10-1). 지형 제약 콜백은 팀 공개 함수
//            EcoCreatureMovement::ConstrainStep 을 30 cm 이하 토막으로 부른다(한 결정 스텝 120~180 cm 를 한 번에 쓸면 완만한 비탈도 막힌다).
//            스텝마다 죽은 개체를 목록에서 뺀다 — 한 프레임에 스텝이 여러 번 돌아도 시체는 움직이거나 먹거나 잡히거나 동족으로 세어지지 않는다.
//    넘기기  잡힘 → Vitals.HP = 0 + Lifecycle.bPredated, 굶음 → HP = 0 (사망 처리·지역 피식 사건·삭제는 팀 조정자). 에너지 E × MaxEnergy 를
//            Vitals.Energy 로 거울 복사. 늑대: 포획 뒤 쿨다운 → FEcoPredatorStateFragment::EatCooldown, 표적을 쫓으면 Lifecycle.bPursuing.
//    먹기    스텝마다 먹이 칸에서 실제로 먹은 사슴을 기록 구간마다 한 번 세고(AteLogEpoch), 산 사슴 에너지 평균·굶주림 수를 컨텍스트에
//            남긴다 (기록·화면 전용. v3 먹이 격자만 — 팀 지역 FoodAmount 에는 쓰지 않는다).
//    얼기·식사 (사람 결정 10-15, 기록 전용) 스텝마다 요청을 읽은 결정의 마스크에 얼기 칸이 열렸는지 센다(FreezeMaskOpen — 얼기를 막으면
//            늘 0). 늑대마다 돌진 시작·식사 중 이동·포획을 센다(FEcoV3RegionContext::TallyWolfStep — 이어 사냥, 늑대별 포획). 식사 중
//            제자리 자체는 위협 모델(FThreatConfig::bEatInPlace)이 한다 — 처리기는 위치를 따로 고치지 않는다.
//    도주 반사 거리 (야생 w3, 경계 거리 실험을 바꿨다) 규칙 자체는 세계 스텝(EcoWorldV3::Step 의 FWildFlightConfig)이 한다. 처리기는 기록만: 스텝마다 식사 중
//            깨어 있는 늑대의 15 m 안 산 사슴 수(규칙 켬·끔 모두 — 견주기용), 프레임 끝 덮기 수(KeepNow), 사슴 글자의 덮기 이름.
// 2. UEcoPolicyV3IntegratedVisualProcessor (스텝 뒤) 매 프레임 Transform·FMassVelocityFragment 를 쓴다: 지난 스텝 → 이번 스텝 위치와
//    지면 높이를 시계 진행으로 보간하고, 속도 = 이번 스텝 변위 ÷ 스텝 시간 (팀 표현 블렌드스페이스가 서기·걷기·뛰기를 고른다).
//    죽은 개체는 죽은 자리에 멈추고 속도 0. eco.V3Debug 1 이면 개체 위에 행동·상태 글자를 그린다. 사슴 글자 = 행동 + 에너지 %,
//    이번 결정 스텝에 먹었으면 '+먹은 몫(에너지 %p)', 에너지 15% 아래면 '굶주림'(빨강), 번식 뒤 약 1.5 초 '번식'.
//    늑대 글자 = 상태 + 종류 (식사 중이면 '늑대 식사 3.2초' 처럼 남은 식사 초). 밤잠 점진화(eco.IntegratedV3.GradualNight 1)면 '눕는 중'·'깨는 중' + 걸음 %, 누울 차례인데 못 누우면
//    '사슴 곁이라 안 누움'·'사냥 중이라 안 누움', 깜깜해 새 사냥을 안 하면 '깜깜해 새 사냥 안 함' (EcoV3Integrated::WolfLabel).
//    밤잠 사건(잠듦·깸·눕기 시작·다시 일어남)은 스텝 처리기가 [EcoV3I] 한 줄씩 남긴다 (UEcoPolicyV3IntegratedSubsystem::NotifyNightStep).
//
// 위치를 쓰는 주체는 이 개체마다 하나다 (AGENTS.md): 팀 이동 처리기(UEcoSteeringProcessor·UEcoCreaturePredatorProcessor)는 v1 태그를
// 요구하므로 이 개체를 보지 않고, 엔진 ApplyMovement 는 FMassCustomMovementTag 로 막혀 있다.

#pragma once

#include "CoreMinimal.h"
#include "MassEntityQuery.h"
#include "MassProcessor.h"

#include "EcoWorldV3.h"

#include "EcoPolicyV3IntegratedProcessors.generated.h"

struct FTransformFragment;
struct FEcoVitalsFragment;
struct FEcoDeathFragment;
struct FEcoCreatureLifecycleFragment;
struct FEcoBehaviorStateFragment;
struct FEcoIntegratedV3Fragment;
struct FEcoPredatorStateFragment;
struct FEcoSocialMovementRequestFragment;
struct FEcoShelterMovementFeedbackFragment;
struct FEcoAlarmStateFragment;
struct FEcoV3SocialBridgeFragment;

/** 통합 v3 사슴 하나 (처리기 한 번 실행 안에서만 유효한 조각 주소). */
struct FEcoV3DeerRec
{
	int64 Id = 0;
	FName Region;
	const FTransformFragment* Transform = nullptr;
	FEcoVitalsFragment* Vitals = nullptr;
	FEcoDeathFragment* Death = nullptr;
	FEcoCreatureLifecycleFragment* Life = nullptr;
	FEcoBehaviorStateFragment* State = nullptr;
	FEcoIntegratedV3Fragment* Int = nullptr;
    const FEcoSocialMovementRequestFragment* SocialRequest = nullptr;
    const FEcoAlarmStateFragment* Alarm = nullptr;
    FEcoShelterMovementFeedbackFragment* Feedback = nullptr;
    FEcoV3SocialBridgeFragment* SocialAudit = nullptr;
	EcoWorldV3::FHerbView View;
};

/** 통합 v3 늑대 하나. */
struct FEcoV3WolfRec
{
	int64 Id = 0;
	FName Region;
	const FTransformFragment* Transform = nullptr;
	FEcoCreatureLifecycleFragment* Life = nullptr;
	EcoWorldV3::FThreatAgent* Agent = nullptr;
	FEcoIntegratedV3Fragment* Int = nullptr;
	FEcoPredatorStateFragment* PredState = nullptr;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPolicyV3IntegratedStepProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoPolicyV3IntegratedStepProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery DeerQuery;
	FMassEntityQuery WolfQuery;

	TArray<FEcoV3DeerRec> Deer;
	TArray<FEcoV3WolfRec> Wolves;
	TArray<TArray<int32>> DeerByContext;    // 컨텍스트마다 산 사슴 (Deer 색인, StableAgentId 순)
	TArray<TArray<int32>> WolvesByContext;

	// 스텝마다 다시 채우는 작업 배열
	TArray<EcoWorldV3::FHerbView> Views;
	TArray<EcoWorldV3::FThreatAgent*> ThreatPtrs;
	TArray<FEcoIntegratedV3Fragment*> HerbInts;
	TArray<FEcoIntegratedV3Fragment*> WolfInts;
	TArray<int64> WolfIds;                  // 이번 Step 늑대 배열의 StableAgentId (밤잠 사건 줄)
	TArray<int32> NewRows;
	TArray<uint8> KnowsPre;                 // 이번 Step 배열의 사슴마다 스텝 앞 관측에서 늑대를 아는가 (두뇌 행동 몫 기록)

	TSet<FName> ReportedMissingRegions;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPolicyV3IntegratedVisualProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoPolicyV3IntegratedVisualProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery DeerQuery;
	FMassEntityQuery WolfQuery;
};
