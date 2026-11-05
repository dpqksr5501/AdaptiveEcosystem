#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineBaseTypes.h"
#include "Subsystems/WorldSubsystem.h"

#include "EcoV3SkyPresenter.generated.h"

class AActor;
class FStructProperty;
class UDirectionalLightComponent;
class USkyLightComponent;
class UEcoV3SkyPresenterSubsystem;

// 통합 v3 모드의 하늘 연출 — 해·달이 팀 시계(낮 60 초·밤 60 초)를 따라 돈다 (10-27 사용자 결정 B '하늘 연동').
//
// 그리기만 한다 — 규칙·관측·개체·난수·팀 시계·레벨·애셋에 쓰지 않는다. 사슴·늑대의 낮밤(v3 어둠 d)은 전처럼 팀 시계에 맞춘 전역 스텝이 정하고,
// 이 연출은 같은 팀 시계를 읽어 하늘을 그 시각에 맞춰 보일 뿐이다 (어느 v3 규칙도 빛·하늘 BP 를 읽지 않는다).
//   1. 시간: 서버·단독은 팀 시계 UEcoWorldClockSubsystem(권위, 낮/밤·위상 시작·끝), 클라이언트는 GameState 요약 Time(서버가 보낸 같은 값, 약 1 초마다).
//      표시 시계(EcoV3Sky::StepClock)가 프레임마다 앞으로 가고, 새 값이 오면 오차를 kBlendSeconds 동안 나눠 메운다(뒤로 가지 않는다).
//      kSnapSeconds 넘게 어긋나거나 세계 판(WorldEpoch)이 바뀌면 곧바로 맞춘다. 서버·단독은 매 프레임 새 값이 와서 팀 시계와 같다.
//   2. 각도: 낮 진행 p → 해 pitch 180 + 180p, 밤 진행 p → 360 + 180p (= 180p). 지평선 = 0·60·120 초, 낮 30 초 = 머리 위, 밤 30 초 = 발밑.
//      해 높이 e = asin(−sin pitch) 라 v3 어둠 d = clamp(0.5 − e/36°, 0, 1) 와 같다 (스텝 단위로 같은 값 — 시험 Sky.DarknessParity).
//      yaw 는 팀 하늘 BP 와 같은 0 (+X 쪽에서 떠서 머리 위를 지나 −X 쪽으로 진다 — BP 가 없는 맵은 해 방향광이 놓인 방위). 달 = 해 + 180° pitch (팀 BP 의 달 식, 늘 정반대).
//   3. 밝기: 해·달은 팀 SkyAtmosphere 의 대기 빛(색인 0·1)이라 지평선 아래면 대기 투과가 0 이 되어 저절로 꺼진다 (엔진 FAtmosphereSetup::GetTransmittanceAtGroundLevel).
//      - 해 세기 = 팀 값 × SunIntensityScale(e): 지평선 위 1, 아래 kSunSetFadeDeg(항해 박명 12°)까지 부드럽게 0 — 대기 없는 맵에서 땅 밑 해가 비추지 않게 하는 안전장치.
//      - 달 세기 = 팀 값(0.01 lux) → 밤 달빛(eco.Sky.NightBrightness, 기본 1 lux = 팀 해 8 lux 의 1/8) 로 NightFactor(d) 만큼 (d 0.5 → 0, d 1 → 1).
//        팀 달빛 0.01 lux 는 거의 깜깜해 늑대·사슴이 안 보인다 (사용자 '밤에도 보이게'). 팀 값보다 어둡게 하지는 않는다.
//      - 달 색 = 팀 색(노랑 255,242,77) → 차가운 달빛 CoolMoonColor() 로 eco.Sky.MoonTint × NightFactor (기본 1 — 10-27 창 모드 확인: 자동 노출이 한밤을
//        낮 밝기로 맞춰 팀 노랑 달빛이면 노란 낮처럼 보였다. 0 = 팀 색 그대로).
//      - 하늘빛(SkyLight) 세기 = 팀 값 × Lerp(1, eco.Sky.NightSkyLight, NightFactor) (기본 1 = 팀 값 그대로 — 그늘이 너무 검으면 올린다).
//      안개는 건드리지 않는다 — 팀 높이 안개의 산란 색이 0 이고 대기 기여(×1)만 쓰므로 밤이면 같이 어두워진다.
//   4. 팀 하늘 BP(/Game/SHC/Blueprints/Sky/BP_SkyManager — 4 맵 모두 SunSpeed 0, 해 315° 고정)는 그대로 둔다 (SunSpeed 를 바꾸지 않는다).
//      BP Tick 은 DynamicSun 이면 매 프레임 SunCurrentRotation 칸(pitch += SunSpeed·dt, yaw·roll 0)을 해 액터 회전에 넣고, 달 = 해 + 180° pitch 로 돌린다
//      (BeginPlay 에서 해가 없거나 DynamicSun 이 꺼져 있으면 Tick 을 끈다). 그래서 실행 중 그 칸에 우리 pitch 를 써 두어 BP 가 같은 값으로 돌리게 하고,
//      카메라 갱신 뒤(TG_PostUpdateWork — BP Tick(TG_PrePhysics) 뒤) 해·달 방향광을 직접 돌려 이번 프레임 값을 정확히 맞춘다. 끄면 그 칸·회전·세기·색을 처음 값으로 되돌린다.
//      (조사 때 콘솔 'set BP_SkyManager_C SunCurrentRotation ...' 가 안 먹은 까닭 — 엔진 소스로 본 것, 실행 확인 전: 편집기 빌드의 set 은 값을 넣은 뒤
//       PostEditChangeProperty 를 부르고, PIE 가 아닌 -game 월드의 액터는 거기서 생성 스크립트를 다시 돌린다(AActor::ReregisterComponentsWhenModified).
//       이 BP 의 생성 스크립트가 SunCurrentRotation = SunDefaultRotaion(315°) 이라 곧바로 덮였다. SunSpeed 는 생성 스크립트가 안 건드려 남았다.
//       우리는 반사로 인스턴스 칸만 쓰므로 생성 스크립트가 다시 돌지 않는다.)
//   5. 켜는 조건 (eco.Sky.Link): 0 = 끔, 1 = 통합 v3 모드 월드에서 켬(기본 — 서버·단독은 통합 서브시스템이 켜졌을 때, 클라이언트는 eco.IntegratedPolicyVersion 3 이거나
//      조정자 bUseV3Policy), 2 = 팀 시계가 도는 모든 게임 월드(팀 기본 v1 확인용 — 고른 사람만). 팀 기본(v1) 월드는 1 에서 아무것도 바꾸지 않는다.
//      시간 출처(팀 시계·요약)가 아직 없으면 기다린다. 데디케이티드 서버에는 만들지 않는다(보이는 화면이 없다). NullRHI 헤드리스 실행에서도 돈다 — 빛만 돌리고
//      시뮬레이션에 쓰지 않으므로 헤드리스 확인(-EcoV3FilmWatch=SkyManager 로 해·달 회전과 SunCurrentRotation)을 할 수 있다.
// 콘솔: eco.Sky.Link (0·1·2), eco.Sky.NightBrightness (밤 달빛 lux), eco.Sky.MoonTint (0~1), eco.Sky.NightSkyLight (배수), eco.Sky.LogSeconds (기록 간격).
// 문서: AdaptiveEcosystem/Docs/RL_Policy/SKY_DAYNIGHT.md

namespace EcoV3Sky
{
	inline constexpr double kTwilightDeg = 18.0;          // v3 어스름 반폭: τ = 0.05 × 주기 = 반주기의 10 % = 180° × 0.1 (낮 60 초면 ±6 초 × 3°/s)
	inline constexpr double kSunSetFadeDeg = 12.0;        // 해가 지평선 아래 이만큼 내려가면 세기 0 (항해 박명 — 대기 투과가 이미 0 이라 대기 있는 맵에서는 차이 없음)
	inline constexpr double kDefaultNightLux = 1.0;       // eco.Sky.NightBrightness 기본 (팀 해 8 lux 의 1/8 — 10-27 창 모드 확인: 자동 노출이 한밤을 낮 밝기로 맞추고 어스름 어두운 틈이 가장 짧다)
	inline constexpr double kDefaultMoonTint = 1.0;       // eco.Sky.MoonTint 기본 (10-27 창 모드 확인: 팀 노랑 달빛은 자동 노출 뒤 한밤이 노란 낮처럼 보여 차가운 달빛으로)
	inline constexpr double kBlendSeconds = 2.0;          // 클라이언트 표시 시계: 새 값의 오차를 메우는 시간 상수
	inline constexpr double kSnapSeconds = 2.0;           // 이보다 크게 어긋나면 곧바로 맞춘다 (≤ kBlendSeconds 라 메우는 동안 뒤로 가지 않는다)
	inline constexpr double kLogEverySecondsDefault = 10.0;

	/** 차가운 달빛 색 (eco.Sky.MoonTint 1 의 색, 선형). */
	ADAPTIVEECOSYSTEM_API FLinearColor CoolMoonColor();

	/** 팀 시계 위상과 진행 p(0~1, 밖이면 자름) → 해 pitch (도, [0, 360)). 낮 180 + 180p, 밤 360 + 180p. 낮 끝 = 밤 시작(0°), 밤 끝 = 낮 시작(180°). */
	ADAPTIVEECOSYSTEM_API double SunPitchDeg(bool bDay, double Progress);

	/** 해 pitch → 해 높이 (도, −90~90) = asin(−sin pitch). 방향광은 pitch 쪽으로 빛을 보내므로 해는 그 반대쪽에 있다. */
	ADAPTIVEECOSYSTEM_API double SunElevationDeg(double PitchDeg);

	/** 해 높이 → v3 어둠 d = clamp(0.5 − 높이 / (2 × 18°), 0, 1) (EcoObservationV3::DayNightPhase 와 같은 값 — 지평선 0.5, 18° 위 0, 18° 아래 1). */
	ADAPTIVEECOSYSTEM_API double Darkness(double ElevationDeg);

	/** 밤 정도 (0~1) = smoothstep(d: 0.5 → 1). 지평선 전까지 0, 해가 18° 내려가면(어스름 끝) 1. */
	ADAPTIVEECOSYSTEM_API double NightFactor(double Dark);

	/** 해 세기 배수 (0~1): 지평선 위 1, 아래 kSunSetFadeDeg 까지 smoothstep 으로 0. */
	ADAPTIVEECOSYSTEM_API double SunIntensityScale(double ElevationDeg);

	/** 해 방향광 회전 (pitch, yaw, roll 0). yaw = 해가 뜨는 방위. */
	ADAPTIVEECOSYSTEM_API FRotator SunRotation(double PitchDeg, double YawDeg);

	/** 달 방향광 회전 = 해 + 180° pitch (팀 BP: MakeRotator(Roll, Pitch + 180, Yaw) of 해 액터 회전 — 빛 방향이 정반대). */
	ADAPTIVEECOSYSTEM_API FRotator MoonRotation(const FRotator& Sun);

	/** 팀 원래 값 + 콘솔 설정 (한 프레임 연출의 입력). */
	struct FLook
	{
		float TeamSunIntensity = 8.0f;
		float TeamMoonIntensity = 0.01f;
		FLinearColor TeamMoonColor = FLinearColor::White;
		float TeamSkyIntensity = 1.0f;
		double SunYawDeg = 0.0;
		double NightLux = kDefaultNightLux;   // eco.Sky.NightBrightness
		double MoonTint = kDefaultMoonTint;   // eco.Sky.MoonTint (0~1)
		double NightSkyLight = 1.0;           // eco.Sky.NightSkyLight
	};

	/** 한 시각의 하늘 (그릴 값). */
	struct FPose
	{
		double SunPitchDeg = 0.0;      // [0, 360) — 팀 BP SunCurrentRotation 칸에 쓰는 값
		double SunElevationDeg = 0.0;
		double Dark = 0.0;             // 하늘 어둠 (v3 d 와 같은 식)
		double Night = 0.0;            // NightFactor(Dark)
		FRotator Sun = FRotator::ZeroRotator;
		FRotator Moon = FRotator::ZeroRotator;
		float SunIntensity = 0.0f;
		float MoonIntensity = 0.0f;
		FLinearColor MoonColor = FLinearColor::White;
		float MoonTintWeight = 0.0f;   // 0 이면 팀 달 색을 바이트 그대로 둔다
		float SkyIntensity = 0.0f;
	};

	/** 위상·진행 → 그릴 값. 콘솔 값이 이상하면(NaN·범위 밖) 자르거나 기본값을 쓴다. */
	ADAPTIVEECOSYSTEM_API FPose ComputePose(bool bDay, double Progress, const FLook& Look);

	/** 팀 시계 표본 (서버 = UEcoWorldClockSubsystem::GetServerTime, 클라이언트 = GameState 요약 Time). */
	struct FClockSample
	{
		int32 Epoch = 0;
		double ServerSeconds = 0.0;
		bool bDay = true;
		double PhaseStart = 0.0;
		double PhaseEnd = 60.0;
	};

	/**
	 * 표본의 위상을 기준으로 시각 T 의 (낮인가, 진행 p). 위상 밖이면 낮·밤을 번갈아 이어 간다 (다른 위상 길이 = OtherPhaseSeconds, 0 이하면 이 위상 길이).
	 * 표본 위상 길이가 0 이하이거나 값이 NaN 이면 거짓.
	 */
	ADAPTIVEECOSYSTEM_API bool PhaseAt(const FClockSample& Sample, double T, double OtherPhaseSeconds, bool& bOutDay, double& OutProgress);

	/** 표시 시계 (클라이언트가 약 1 초마다 오는 요약 사이를 이어 그린다 — 서버·단독도 같은 길을 쓴다). */
	struct FDisplayClock
	{
		bool bHas = false;
		double Shown = 0.0;            // 보이는 서버 시각 (초)
		double Pending = 0.0;          // 아직 메우지 않은 오차 (초)
		FClockSample Last;             // 마지막 표본 (위상 정보)
		double DaySeconds = 0.0;       // 본 낮 길이 (0 = 아직 못 봄)
		double NightSeconds = 0.0;     // 본 밤 길이
		int32 Snaps = 0;               // 곧바로 맞춘 횟수 (처음 포함 — 기록·시험용)
	};

	/**
	 * 한 프레임: Shown += dt, 새 표본이 있으면(NewSample ≠ null) 오차 = 표본 − Shown. 처음·판이 바뀜·|오차| > Snap 이면 곧바로 맞추고, 아니면 오차를
	 * 메울 몫으로 두어 프레임마다 dt / Blend 만큼씩 메운다. dt ≤ 0(멈춤)이면 움직이지 않는다. Snap ≤ Blend 면 맞추기 전에는 뒤로 가지 않는다.
	 */
	ADAPTIVEECOSYSTEM_API void StepClock(FDisplayClock& Clock, double DeltaSeconds, const FClockSample* NewSample, double BlendSeconds = kBlendSeconds,
										 double SnapSeconds = kSnapSeconds);

	/** 지금 보이는 (낮인가, 진행 p). 표본이 아직 없으면 거짓. */
	ADAPTIVEECOSYSTEM_API bool ClockPhase(const FDisplayClock& Clock, bool& bOutDay, double& OutProgress);

	/**
	 * 레벨의 하늘 빛 (해·달 방향광·하늘빛·팀 하늘 BP) 손잡이와 처음 값. 실행 중에만 쓰고 되돌린다 — 레벨·애셋은 저장하지 않는다.
	 * 찾기: 팀 하늘 BP(SunCurrentRotation(FRotator)·Sun·Moon 칸을 가진 액터)가 있으면 그 Sun·Moon 액터의 방향광, 없으면 대기 빛 색인 0(해)·1(달) 방향광 중
	 * 세기가 가장 큰 것 (대기 빛이 하나도 없으면 가장 밝은 방향광을 해로, 달 없음). 하늘빛 = 첫 SkyLight.
	 */
	struct ADAPTIVEECOSYSTEM_API FSkyRig
	{
		TWeakObjectPtr<AActor> SkyManager;
		FStructProperty* SunRotationProp = nullptr;      // 팀 BP SunCurrentRotation (FRotator)
		FRotator OriginalBPRotation = FRotator::ZeroRotator;
		double BPSunSpeed = 0.0;                         // 기록용 (바꾸지 않는다)
		TWeakObjectPtr<UDirectionalLightComponent> Sun;
		TWeakObjectPtr<UDirectionalLightComponent> Moon;
		TWeakObjectPtr<USkyLightComponent> Sky;
		FRotator OriginalSunRotation = FRotator::ZeroRotator;
		FRotator OriginalMoonRotation = FRotator::ZeroRotator;
		float OriginalSunIntensity = 0.0f;
		float OriginalMoonIntensity = 0.0f;
		FColor OriginalMoonColor = FColor::White;
		float OriginalSkyIntensity = 0.0f;
		double SunYawDeg = 0.0;
		bool bCaptured = false;

		/** 찾고 처음 값을 적는다. 해 방향광이 없거나 움직일 수 없으면(Static) 거짓 (아무것도 바꾸지 않는다). */
		bool Capture(UWorld& World);
		/** 잡은 손잡이가 아직 살아 있나 (해는 꼭, 잡았던 달·하늘빛·BP 도). */
		bool IsAlive() const;
		/** 처음 값 → 연출 입력 (콘솔 칸은 기본값). */
		FLook BaseLook() const;
		/** 한 프레임 그리기: BP 칸(있으면)·해·달 회전·세기·달 색·하늘빛 세기. */
		void Apply(const FPose& Pose);
		/** 처음 값으로 되돌리고 손잡이를 놓는다. */
		void Restore();
	};
}

/** 카메라 갱신 뒤(TG_PostUpdateWork — 팀 하늘 BP Tick 뒤) 하늘 틱. */
struct FEcoV3SkyTickFunction : public FTickFunction
{
	TWeakObjectPtr<UEcoV3SkyPresenterSubsystem> Owner;

	virtual void ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread,
							 const FGraphEventRef& MyCompletionGraphEvent) override;
	virtual FString DiagnosticMessage() override { return TEXT("EcoV3 하늘 연출"); }
	virtual FName DiagnosticContext(bool bDetailed) override { return FName(TEXT("EcoV3Sky")); }
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoV3SkyPresenterSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

	/** 한 프레임. DeltaSeconds = 월드 프레임 초. */
	void TickPresenter(float DeltaSeconds);

	bool IsLinked() const { return bLinked; }
	const EcoV3Sky::FPose& GetLastPose() const { return LastPose; }
	const EcoV3Sky::FDisplayClock& GetDisplayClock() const { return Clock; }

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	/** eco.Sky.Link 와 월드 모드로 지금 연동해야 하나. */
	bool WantsLink(const UWorld& World) const;
	/** 팀 시계(권위) 또는 GameState 요약(클라이언트)의 새 표본. 새 값이 없으면 거짓. */
	bool ReadNewSample(const UWorld& World, EcoV3Sky::FClockSample& Out);
	/** 빛을 찾고 처음 값을 적는다 (못 찾으면 1 초 뒤 다시). */
	bool Link(UWorld& World);
	/** 처음 값으로 되돌린다. */
	void Unlink(const TCHAR* Why);
	void LogPose(const UWorld& World, const TCHAR* Why);

	FEcoV3SkyTickFunction TickFn;
	bool bTickRegistered = false;
	bool bSpawnerV3 = false;          // 조정자 bUseV3Policy (클라이언트 판정용 — 맵에 놓인 값)
	bool bLinked = false;
	bool bToldNoSun = false;
	double NextCaptureTry = 0.0;      // 월드 실시간 (찾기 실패 뒤 1 초마다 다시)
	double NextLogAt = 0.0;           // 표시 시계 초
	int32 LastRevision = -1;          // GameState 요약 판 (클라이언트 — 바뀔 때만 복사)
	bool bLastDay = true;
	EcoV3Sky::FDisplayClock Clock;
	EcoV3Sky::FSkyRig Rig;
	EcoV3Sky::FPose LastPose;
};
