// v3 R1b 세계 서비스 — 우리 정책 시험 경로(AEcoPolicyTestSpawner 평면 시험 맵) 전용.
//
// 맡는 것 (서버·단독 월드만. Client 에서는 세션을 열지 않는다 — AGENTS.md 2절 2항):
//   - 세계 상태 하나 (EcoWorldV3::FWorldState: 설정·먹이 격자·은신처·전역 스텝 t·어둠·피식 EMA·세계 난수·기록)
//   - 결정 시계 (EcoPolicy::FStepClock, StepSeconds = 8/60 s = 7.5 Hz. v1 과 같은 시간 기준. 계약 10-1)
//   - Mass 개체 만들기 (조각 구성·슬롯 배정·첫 관측과 첫 요청)
//   - 파이썬 단위 ↔ cm 대응 (계약 12-1. 맵 [0, size]² 의 원점 = 스포너 중심 − size/2)
//   - 서버 기록 줄 [EcoV3] (행동별 사용·진입, 포획, 아사, 마스크 위반) — 시뮬레이션 시간 기준 N초마다
// 이 서브시스템은 복제 통로가 아니다 (AGENTS.md 2절 6항). 프로퍼티 복제·RPC 가 없다.
//
// 판 고르기: 콘솔 변수 eco.PolicyVersion (1 = v1, 3 = v3, 기본 1). 스포너가 시작과 매 틱 시작(안전 지점)에 읽는다.

#pragma once

#include "CoreMinimal.h"
#include "Mass/EntityHandle.h"
#include "MassEntityTypes.h"
#include "Subsystems/WorldSubsystem.h"

#include "EcoPolicyClock.h"
#include "EcoWorldV3.h"

#include "EcoPolicyV3Subsystem.generated.h"

struct FMassEntityManager;

DECLARE_LOG_CATEGORY_EXTERN(LogEcoPolicyV3, Log, All);

/**
 * 평면 시험 맵의 v3 세계 설정 (cm·초). 기본값은 R1b 학습 세계(configs/v3_r1_on.yaml) 범위 안의 한 세계다 — 계약 7-7
 * '언리얼 ⊆ 학습'. 범위 밖 값을 넣으면 세션 시작 때 경고를 남긴다(막지는 않는다).
 */
USTRUCT(BlueprintType)
struct ADAPTIVEECOSYSTEM_API FEcoPolicyV3Settings
{
	GENERATED_BODY()

	/** 세계 시드. 사건 결정 지연 해시의 Seed(계약 5-5)이자 세계 난수(먹이 패치·배치·늑대 선회·원거리 굴림·리스폰)의 시드다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3")
	int32 Seed = 20000;

	/** 사슴 수. 학습은 128 이고 피식 EMA 분모도 이 값이다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3", meta = (ClampMin = "1", ClampMax = "1024"))
	int32 HerbivoreCount = 128;

	/** 정사각 맵 한 변. cm. 학습 60~110단위 = 12000~22000 cm. 스포너 위치가 맵 중심이다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3", meta = (ClampMin = "400"))
	float WorldSizeCm = 20000.0f;

	/** 은신처 원 반경. cm. 학습 4~9단위 = 800~1800 cm. 맵 1/4·3/4 지점 네 곳에 둔다. 0 이면 은신처가 없다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3", meta = (ClampMin = "0"))
	float CoverRadiusCm = 1600.0f;

	/** 잠행-돌진형 늑대 수 (학습 비율 30~70%). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3|Threats", meta = (ClampMin = "0"))
	int32 NumStalkers = 3;

	/** 근접 추격형 늑대 수. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3|Threats", meta = (ClampMin = "0"))
	int32 NumChasers = 2;

	/** 원거리형 수 (추격형의 한 갈래, 학습 0~50%). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3|Threats", meta = (ClampMin = "0"))
	int32 NumRanged = 1;

	/** 야행성 수 (밤에 자지 않고 박명 감속이 없다, 학습 0~25%). 보통 위협 슬롯 끝에서부터 고른다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3|Threats", meta = (ClampMin = "0"))
	int32 NumNocturnal = 1;

	/** 플레이어형 대역 (맵 전체를 보는 모드 기계, 계약 7-5). 사람 플레이어가 아니다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3|Threats")
	bool bPlayerProxy = false;

	/** 근접형 늑대 속력 = 900 cm/s × 이 값. 학습 0.6~0.95 (0.8 = 720 cm/s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3|Threats", meta = (ClampMin = "0"))
	float PredSpeedMult = 0.8f;

	/** 낮밤 한 주기. 결정 스텝 (900 = 60 s 낮 + 60 s 밤, 학습 {600, 900, 1800}). 0 이하면 낮 고정. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3")
	int32 DayPeriodSteps = 900;

	/** 낮밤 시작 위상. 결정 스텝 (0 = 새벽 전환에서 시작). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3", meta = (ClampMin = "0"))
	int32 DayOffsetSteps = 0;

	/** 먹이 재생률 배수 (학습 0.5~2). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3", meta = (ClampMin = "0"))
	float FoodRegenMult = 1.0f;

	/** [EcoV3] 서버 기록 줄 주기. 시뮬레이션 초. 0 이면 끈다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|PolicyV3", meta = (ClampMin = "0"))
	float LogIntervalSeconds = 5.0f;
};

/** 최근 포획 자리 (디버그 표시). */
struct FEcoPolicyV3CatchMark
{
	FVector Location = FVector::ZeroVector;
	double Time = 0.0;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPolicyV3Subsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Deinitialize() override;

	/** 콘솔 변수 eco.PolicyVersion. 3 이면 3, 그 밖은 모두 1 (v1 이 기본이다). */
	static int32 GetRequestedPolicyVersion();

	/** cm·초 설정 → 파이썬 단위 세계 설정. */
	static EcoWorldV3::FWorldConfig MakeWorldConfig(const FEcoPolicyV3Settings& Settings);

	/** 학습 세계(v3_r1_on.yaml) 범위 밖인 값의 설명 목록. 비었으면 모두 범위 안이다. */
	static TArray<FString> CheckTrainingRange(const EcoWorldV3::FWorldConfig& Config);

	/**
	 * 세계를 만든다 (먹이 격자·은신처·t = 0). 개체는 SpawnPopulation 이 만든다.
	 * CenterCm = 맵 중심 (Z 는 개체 높이). 서버·단독 월드에서만 열린다. 이미 열려 있으면 false.
	 */
	bool BeginSession(const EcoWorldV3::FWorldConfig& Config, const FVector& CenterCm, float LogIntervalSeconds);
	void EndSession();
	bool IsSessionActive() const { return bSessionActive; }

	/** v3 사슴 조각 구성 (프로세서 쿼리와 같아야 한다). */
	static TArray<const UScriptStruct*> HerbivoreComposition();
	/** v3 늑대 조각 구성. */
	static TArray<const UScriptStruct*> ThreatComposition();

	/**
	 * 세션 설정대로 사슴 N·위협 M 개체를 만들고(슬롯 = 배열 색인) 첫 관측·첫 요청을 만든다 (파이썬 reset).
	 * Mass 처리 밖(BeginPlay·월드 틱 시작)에서만 부른다. 실패하면 false 이고 만든 개체는 지운다.
	 */
	bool SpawnPopulation(FMassEntityManager& EntityManager, TArray<FMassEntityHandle>& OutHerbivores,
						 TArray<FMassEntityHandle>& OutThreats);

	/** 개체를 지운다 (Mass 처리 밖에서). 세션은 그대로 둔다. */
	static void DestroyPopulation(FMassEntityManager& EntityManager, TArray<FMassEntityHandle>& Herbivores,
								  TArray<FMassEntityHandle>& Threats);

	/** 사슴 하나의 조각들을 가리키는 보기 (조각이 없으면 IsValid() == false). */
	static EcoWorldV3::FHerbView MakeHerbView(const FMassEntityManager& EntityManager, FMassEntityHandle Entity);

	/** 프레임 dt → 이번 프레임에 돌 결정 스텝 수 (최대 64). 세션이 없으면 0. */
	int32 AdvanceClock(float DeltaSeconds);

	/** 다음 결정 스텝까지의 진행 [0, 1) — 화면 보간 전용. */
	float GetVisualAlpha() const;

	/** 프로세서가 결정 스텝 하나를 마칠 때마다 부른다 (기록·포획 표시). */
	void NotifyStepCompleted(const EcoWorldV3::FStepReport& Report);

	/** [EcoV3] 기록 줄을 지금 남긴다 (지난 줄 뒤 구간 + 누적). */
	void LogSummary();

	EcoWorldV3::FWorldState& GetSim() { return Sim; }
	const EcoWorldV3::FWorldState& GetSim() const { return Sim; }

	/** 파이썬 단위 → 월드 cm (Z = 맵 중심 높이). */
	FVector UnitsToCm(double X, double Y) const;
	FVector UnitsToCm(const EcoWorldV3::FVec2& P) const { return UnitsToCm(P.X, P.Y); }
	/** 월드 cm → 파이썬 단위 (Z 무시). */
	EcoWorldV3::FVec2 CmToUnits(const FVector& P) const;
	/** 파이썬 (0, 0) 의 월드 cm. */
	const FVector& GetOriginCm() const { return OriginCm; }
	double GetWorldSizeCm() const { return Sim.Config.WorldSize * EcoRepertoireV3::kUnitCm; }

	/** 사슴 화면 값: PrevPos→Pos 를 Alpha 로 보간한 위치, heading 의 yaw, 이번 스텝 변위 속도 (cm/s). */
	void ComputeHerbVisual(const EcoWorldV3::FHerbBody& Body, float Alpha, FTransform& OutTransform, FVector& OutVelocity) const;
	/** 늑대 화면 값. */
	void ComputeThreatVisual(const EcoWorldV3::FThreatAgent& Agent, float Alpha, FTransform& OutTransform,
							 FVector& OutVelocity) const;

	/** 1.5 초 안의 포획 자리. */
	const TArray<FEcoPolicyV3CatchMark>& GetRecentCatches() const { return RecentCatches; }

private:
	EcoWorldV3::FWorldState Sim;
	bool bSessionActive = false;
	FVector OriginCm = FVector::ZeroVector;

	EcoPolicy::FStepClock Clock;
	int32 ClockPhase = 0;

	int32 LogEverySteps = 0;
	int64 LastLogStep = 0;
	EcoWorldV3::FWorldStats LastLogStats;

	TArray<FEcoPolicyV3CatchMark> RecentCatches;
};
