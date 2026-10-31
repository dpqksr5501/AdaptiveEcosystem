#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineBaseTypes.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"

#include "EcoV3WeatherPresenter.generated.h"

class AEcologyRegion;
class UAudioComponent;
class UFXSystemAsset;
class UFXSystemComponent;
class USoundBase;
class UEcoV3WeatherPresenterSubsystem;

// 통합 v3 모드의 비·눈 연출 (10-18 사용자 '일단 우리 테스트 레벨에도 날씨 적용되게 해 줘').
//
// 그리기만 한다 — 규칙·관측·개체·레벨·애셋에 손대지 않는다. 날씨 규칙은 엔진 무관 세계 층(EcoWorldV3.h FWeatherConfig, 통합 모드 eco.IntegratedV3.Weather)이
// 맡고, 이 연출은 그 지역 세계가 지금 쓰는 날씨(FEcoV3RegionContext::Sim.WeatherKind·WeatherIntensity)를 읽어 보여 준다.
//   1. 프레임마다(카메라 갱신 뒤 TG_PostUpdateWork) 첫 로컬 플레이어의 카메라 자리(PlayerCameraManager — 보기 대상이 촬영 감독의 카메라든 폰이든)를 읽는다.
//   2. 그 자리를 가로(x·y)로 품는 지역(AEcologyRegion 상자, 높이는 보지 않는다 — 높은 카메라에서도 그 땅의 날씨)의 세계 날씨를 찾는다. 세계가 없는 지역은 맑음.
//   3. 비면 팀 나이아가라 /Game/SHC/ART/FX/Rain_System 과 빗소리 /Game/SHC/Audio/Environment/A_Rain_Cue 를, 눈이면 /Game/SHC/ART/FX/NiagaraSnowfall/Effects/NS_Blizzard
//      를 카메라 자리에 켠다. 들어가면 곧바로 kFadeInSeconds 동안 세지고(빗줄기 수 User.SpawnRate = kRainSpawnRateFull(팀 블루프린트 값 500) × 세기 × 페이드,
//      빗소리 음량 = 세기 × 페이드),
//      나오면 kFadeOutSeconds 동안 약해진 뒤 끄고 빗소리를 멈춘다. 눈 애셋은 세기 칸이 없어 나오는 순간 새 눈송이를 멈추고(Deactivate — 떠 있는 눈송이만 마저 내린다)
//      들어가면 곧바로 켠다. 팀 블루프린트(BP_SHC_*RegionalWeather)와 달리 7~9 초 늦게 오지 않고, 나온 뒤 5.5 초 동안 눈이 그대로 오지 않고, 음량 0 으로 소리가
//      계속 돌지 않는다(herbivore_rl/results/v3/wild2/weather_check/README.md 4절).
//   4. 기본 Native 뷰는 Weather/WeatherVisuals·통합 모드를 따른다. 새 식생 BP 맵은 Client도 기존 GameState Environment를 소비하며
//      Native 논리를 만들지 않는다. 이 뷰에서도 WeatherVisuals 0은 연출만 끄고 권위 강수는 유지한다. Dedicated/NullRHI는 그리지 않는다.
// 액터 AEcoV3WeatherFxActor (실행 중에만, 저장 안 함) 하나가 컴포넌트를 쥔다. 촬영 감독 -EcoV3FilmWatch=EcoV3WeatherFx 로 상태(켜짐·자리·음량·페이드)를 읽을 수 있다.
// 현실 근거: 비·눈은 지역 전체에 오고(팀 설계 — 지역 상자마다 날씨), 보는 사람 둘레에서 보인다(카메라 곁 연출).

namespace EcoV3WeatherFx
{
	inline constexpr double kFadeInSeconds = 1.5;    // 들어가서 다 세질 때까지 (팀 블루프린트 타임라인 5 초보다 짧게 — 경계를 넘자마자 날씨로 읽히게, 어림)
	inline constexpr double kFadeOutSeconds = 1.0;   // 나와서 꺼질 때까지
	inline const TCHAR* const kRainSystemPath = TEXT("/Game/SHC/ART/FX/Rain_System.Rain_System");
	inline const TCHAR* const kRainSoundPath = TEXT("/Game/SHC/Audio/Environment/A_Rain_Cue.A_Rain_Cue");
	inline const TCHAR* const kSnowSystemPath = TEXT("/Game/SHC/ART/FX/NiagaraSnowfall/Effects/NS_Blizzard.NS_Blizzard");
	inline const TCHAR* const kNiagaraComponentClass = TEXT("/Script/Niagara.NiagaraComponent");
	inline const TCHAR* const kSpawnRateName = TEXT("SpawnRate");   // Rain_System 의 사용자 칸 User.SpawnRate (팀 블루프린트도 이 칸을 쓴다)
	// 비 세기 1 의 User.SpawnRate (애셋 기본은 0). 팀 블루프린트 BP_SHC_RainRegionalWeather 가 타임라인 Alpha 로 Lerp(0, 500) 을 넣는다 —
	// 10-18 SHC 시험 레벨에서 실행 중 읽음(-EcoV3FilmWatch, Alpha 0.127 → 63.3, 0.527 → 263.3, 1 → 500). 같은 값이라 세기 1 의 비는 팀 화면과 같다
	inline constexpr double kRainSpawnRateFull = 500.0;

	/** 페이드 한 프레임: Alpha 를 Target 쪽으로 (올라갈 때 초당 1 ÷ FadeIn, 내려갈 때 초당 1 ÷ FadeOut, 넘지 않음). 시간이 0 이하면 곧바로 Target. */
	ADAPTIVEECOSYSTEM_API double Approach(double Alpha, double Target, double DeltaSeconds, double FadeInSeconds = kFadeInSeconds,
										  double FadeOutSeconds = kFadeOutSeconds);

	/** 지역 날씨 → (비 목표, 눈 목표) 세기. 날씨 번호 = EcoWorldV3::kWeather*. */
	ADAPTIVEECOSYSTEM_API void Targets(int32 Kind, double Intensity, double& OutRain, double& OutSnow);

	/** 지역 상자(중심·회전·반폭)가 점 P 를 가로로 품나 (높이 무시 — AEcologyRegion::ContainsPosition 의 x·y 판정과 같다). */
	ADAPTIVEECOSYSTEM_API bool ContainsXY(const FTransform& BoxTransform, const FVector& Extent, const FVector& P);

	/**
	 * 나이아가라 컴포넌트의 사용자 실수 칸 (UNiagaraComponent::GetVariableFloat 를 반사로 — Niagara 모듈에 기대지 않는다). 칸이 없거나 나이아가라가 아니면 −1.
	 * 읽기만 한다 (촬영 감독 -EcoV3FilmWatch 도 쓴다).
	 */
	ADAPTIVEECOSYSTEM_API double NiagaraUserFloat(UObject* Component, const TCHAR* Name);
}

/** 비·눈 연출 컴포넌트를 쥐는 실행 중 액터 (저장·복제 안 함). 상태 칸은 촬영 감독 -EcoV3FilmWatch 가 읽는다 (읽기만). */
UCLASS(NotPlaceable, Transient)
class ADAPTIVEECOSYSTEM_API AEcoV3WeatherFxActor : public AActor
{
	GENERATED_BODY()

public:
	AEcoV3WeatherFxActor();

	UPROPERTY(Transient)
	TObjectPtr<USceneComponent> Root;
	UPROPERTY(Transient)
	TObjectPtr<UFXSystemComponent> Rain;
	UPROPERTY(Transient)
	TObjectPtr<UFXSystemComponent> Snow;
	UPROPERTY(Transient)
	TObjectPtr<UAudioComponent> RainSound;

	UPROPERTY(Transient)
	double RainAlpha = 0.0;           // 비 세기 × 페이드 (0~1)
	UPROPERTY(Transient)
	double SnowAlpha = 0.0;           // 눈 세기 × 페이드 (0~1, 눈 애셋은 이 값을 따르지 않고 켬·끔만 — 기록용)
	UPROPERTY(Transient)
	double RainSpawnRate = -1.0;      // 지금 넣은 User.SpawnRate (−1 = 칸 없음·안 넣음)
	UPROPERTY(Transient)
	bool bRainOn = false;
	UPROPERTY(Transient)
	bool bSnowOn = false;
	UPROPERTY(Transient)
	bool bRainSoundOn = false;
	UPROPERTY(Transient)
	int32 CameraWeather = 0;          // 카메라 지역의 날씨 번호 (0 맑음·1 비·2 눈)
	UPROPERTY(Transient)
	double CameraIntensity = 0.0;
	UPROPERTY(Transient)
	FName CameraRegion;
};

/** 카메라 갱신 뒤(TG_PostUpdateWork) 연출 틱. */
struct FEcoV3WeatherFxTickFunction : public FTickFunction
{
	TWeakObjectPtr<UEcoV3WeatherPresenterSubsystem> Owner;

	virtual void ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread,
							 const FGraphEventRef& MyCompletionGraphEvent) override;
	virtual FString DiagnosticMessage() override { return TEXT("EcoV3 비·눈 연출"); }
	virtual FName DiagnosticContext(bool bDetailed) override { return FName(TEXT("EcoV3WeatherFx")); }
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoV3WeatherPresenterSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

	/** 한 프레임 (카메라 갱신 뒤). DeltaSeconds = 월드 프레임 초. */
	void TickPresenter(float DeltaSeconds);
	const AEcoV3WeatherFxActor* GetFxActor() const { return Fx; }

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	friend struct FEcoV3WeatherFxTickFunction;

	/** 카메라 자리를 가로로 품는 지역 (이름 순 첫째). 없으면 NAME_None. */
	FName RegionAt(const FVector& P);
	/** 액터·애셋·컴포넌트 (처음 쓸 때 한 번). 못 만들면 거짓 (경고 한 줄). */
	bool EnsureFx();
	/** 모두 끈다 (연출 없음 — 꺼짐·통합 모드 아님·카메라 없음). */
	void FadeAll(double DeltaSeconds);
	void Apply(double RainTarget, double SnowTarget, double DeltaSeconds);

	double RainDensity = 1.0;         // 빗줄기 수 배수 (eco.IntegratedV3.WeatherRainDensity — 화면 전용)

	FEcoV3WeatherFxTickFunction TickFn;
	bool bTickRegistered = false;
	bool bEcologyWeatherView = false; // opt-in map: received GameState environment, including clients
	bool bTried = false;              // EnsureFx 를 한 번 해 봤다
	bool bReady = false;              // 액터·컴포넌트가 있다
	bool bRainRateParam = false;      // Rain_System 에 User.SpawnRate 칸이 있다 (없으면 켬·끔과 소리만 페이드)
	FName LastRegion;
	int32 LastKind = -1;
	double LastIntensity = -1.0;
	int64 Frames = 0;

	UPROPERTY(Transient)
	TObjectPtr<AEcoV3WeatherFxActor> Fx;
	UPROPERTY(Transient)
	TObjectPtr<UFXSystemAsset> RainAsset;
	UPROPERTY(Transient)
	TObjectPtr<UFXSystemAsset> SnowAsset;
	UPROPERTY(Transient)
	TObjectPtr<USoundBase> RainCue;

	TArray<TWeakObjectPtr<AEcologyRegion>> Regions;
	bool bRegionsGathered = false;
};
