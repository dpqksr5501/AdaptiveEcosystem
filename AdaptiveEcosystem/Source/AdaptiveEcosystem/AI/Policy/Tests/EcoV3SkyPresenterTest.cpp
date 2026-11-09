// 하늘 연출 (10-27 사용자 결정 B '하늘 연동' — 해·달이 팀 시계를 따라 돈다) — 순수 함수와 레벨 빛 손잡이.
//
// 보는 것:
//   Sky.Angles          해 pitch: 낮 180+180p·밤 360+180p, 지평선 = 0·60·120 초, 낮 30 초 머리 위·밤 30 초 발밑, 낮밤 경계에서 끊기지 않음,
//                       해는 +X 쪽에서 떠서 −X 쪽으로 진다(yaw 0), 달 = 해 + 180°(빛 방향 정반대·높이 = −해 높이, 팀 BP 처럼 정규화된 해 회전에서 만들어도 같다),
//                       팀 기본 해 315° = 낮 45 초 자리
//   Sky.DarknessParity  하늘 어둠 = v3 어둠 (EcoObservationV3::DayNightPhase, 주기 900·어스름 45 스텝·시작 0) — 두 바퀴 1800 스텝 모두 1e-9 안
//   Sky.Brightness      밤 정도·해 세기·달빛(팀 값 → 밤 달빛, 어스름 6 초 동안 오르고 팀보다 어둡게 안 함)·달 색 섞기·하늘빛 배수, 콘솔 값이 이상해도 자름
//   Sky.ClientClock     표시 시계: 표본 전에는 없음, 첫 표본에 맞춤, 1 초마다 정확한 표본이면 그대로 따라감, 늦고 흔들리는 표본에도 뒤로 가지 않고 0.3 초 안,
//                       2 초 넘게 어긋나거나 판이 바뀌면 곧바로 맞춤, 멈춤(dt 0)이면 그대로, 위상 밖은 낮·밤을 번갈아 이어 감(본 길이를 씀)
//   Sky.Rig             시험 월드 방향광 셋(대기 빛 색인 0·1·대기 빛 아님): 해·달 찾기(팀 하늘 BP 없음 — 색인으로)·해 길 방위 = 놓인 방위,
//                       한밤·한낮 그리기(해·달 방향과 세기, 대기 빛 아닌 방향광은 그대로)·달 색 섞기·되돌리기(회전·세기·색 처음 값), Static 해는 손대지 않음
// 문서: AdaptiveEcosystem/Docs/RL_Policy/SKY_DAYNIGHT.md

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoObservationV3.h"
#include "../EcoV3SkyPresenter.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "EcoTestWorld.h"

#include <limits>

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoV3SkyPresenterTestImpl
{
	/** 해가 있는 쪽 (빛이 나아가는 방향의 반대). */
	FVector SunPosition(const FRotator& LightRotation)
	{
		return -LightRotation.Vector();
	}

	ADirectionalLight* SpawnLight(UWorld& World, float Intensity, int32 AtmosphereIndex, const FRotator& Rotation, const FColor& Color)
	{
		ADirectionalLight* L = World.SpawnActor<ADirectionalLight>(FVector::ZeroVector, Rotation);
		if (!L || !L->GetComponent())
		{
			return nullptr;
		}
		UDirectionalLightComponent* C = L->GetComponent();
		C->SetMobility(EComponentMobility::Movable);
		C->SetIntensity(Intensity);
		C->SetLightFColor(Color);
		C->SetAtmosphereSunLight(AtmosphereIndex >= 0);
		if (AtmosphereIndex >= 0)
		{
			C->SetAtmosphereSunLightIndex(AtmosphereIndex);
		}
		return L;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3SkyAnglesTest,
	"AdaptiveEcosystem.Policy.V3.Sky.Angles",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3SkyAnglesTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3Sky;
	using EcoV3SkyPresenterTestImpl::SunPosition;
	constexpr double Tol = 1e-9;
	// 지평선·머리 위·발밑 (낮 60 초 + 밤 60 초: 0 초 = 낮 p 0, 30 초 = 낮 p 0.5, 60 초 = 밤 p 0, 90 초 = 밤 p 0.5, 120 초 = 다음 낮 p 0)
	TestTrue(TEXT("0 초 (낮 시작): 해 pitch 180°, 높이 0"), FMath::Abs(SunPitchDeg(true, 0.0) - 180.0) < Tol && FMath::Abs(SunElevationDeg(SunPitchDeg(true, 0.0))) < 1e-6);
	TestTrue(TEXT("30 초 (낮 한가운데): 해 pitch 270°, 높이 90°"), FMath::Abs(SunPitchDeg(true, 0.5) - 270.0) < Tol && FMath::Abs(SunElevationDeg(270.0) - 90.0) < 1e-6);
	TestTrue(TEXT("60 초 (낮 끝 = 밤 시작): 둘 다 pitch 0°, 높이 0"),
			 FMath::Abs(SunPitchDeg(true, 1.0)) < Tol && FMath::Abs(SunPitchDeg(false, 0.0)) < Tol && FMath::Abs(SunElevationDeg(0.0)) < 1e-6);
	TestTrue(TEXT("90 초 (밤 한가운데): 해 pitch 90°, 높이 −90°"), FMath::Abs(SunPitchDeg(false, 0.5) - 90.0) < Tol && FMath::Abs(SunElevationDeg(90.0) + 90.0) < 1e-6);
	TestTrue(TEXT("120 초 (밤 끝 = 낮 시작): pitch 180° 로 이어진다"), FMath::Abs(SunPitchDeg(false, 1.0) - 180.0) < Tol);
	TestTrue(TEXT("낮 15 초: 해 높이 45°"), FMath::Abs(SunElevationDeg(SunPitchDeg(true, 0.25)) - 45.0) < 1e-6);
	TestTrue(TEXT("팀 기본 해 315° (45° 높이) = 우리 길의 낮 45 초 자리"), FMath::Abs(SunPitchDeg(true, 0.75) - 315.0) < Tol);
	TestTrue(TEXT("진행이 범위 밖·NaN 이면 자른다"), SunPitchDeg(true, -1.0) == SunPitchDeg(true, 0.0) && SunPitchDeg(false, 2.0) == SunPitchDeg(false, 1.0)
		&& SunPitchDeg(true, std::numeric_limits<double>::quiet_NaN()) == SunPitchDeg(true, 0.0));

	// 120 초를 0.25 초씩: 높이가 연속(한 걸음 0.75° 이하)이고 낮에는 0 이상·밤에는 0 이하, 방향광 회전의 해 자리 높이와 같다
	bool bContinuous = true, bSign = true, bVector = true;
	double Prev = 0.0;
	for (int32 i = 0; i <= 480; ++i)
	{
		const double T = 0.25 * i;
		const bool bDay = FMath::Fmod(T, 120.0) < 60.0;
		const double P = FMath::Fmod(T, 60.0) / 60.0;
		const double Pitch = SunPitchDeg(bDay, P);
		const double E = SunElevationDeg(Pitch);
		if (i > 0 && FMath::Abs(E - Prev) > 0.75 + 1e-6)
		{
			bContinuous = false;
		}
		if ((bDay && E < -1e-9) || (!bDay && E > 1e-9))
		{
			bSign = false;
		}
		if (FMath::Abs(SunPosition(SunRotation(Pitch, 0.0)).Z - FMath::Sin(FMath::DegreesToRadians(E))) > 1e-9)
		{
			bVector = false;
		}
		Prev = E;
	}
	TestTrue(TEXT("0~120 초: 해 높이가 끊기지 않는다 (0.25 초에 0.75° = 3°/s)"), bContinuous);
	TestTrue(TEXT("낮에는 지평선 위, 밤에는 아래"), bSign);
	TestTrue(TEXT("해 높이 = 방향광 회전의 해 자리 높이 (asin(−sin pitch))"), bVector);

	// 해 길: yaw 0 이면 +X 쪽에서 떠서 −X 쪽으로 진다 (팀 BP 와 같은 평면)
	const FVector Rise = SunPosition(SunRotation(SunPitchDeg(true, 0.01), 0.0));
	const FVector SetPos = SunPosition(SunRotation(SunPitchDeg(true, 0.99), 0.0));
	TestTrue(*FString::Printf(TEXT("해 뜸 자리 (%.3f, %.3f, %.3f) 는 +X, 해 짐 자리 (%.3f, %.3f, %.3f) 는 −X"), Rise.X, Rise.Y, Rise.Z, SetPos.X, SetPos.Y, SetPos.Z),
			 Rise.X > 0.99 && Rise.Z > 0.0 && SetPos.X < -0.99 && SetPos.Z > 0.0 && FMath::Abs(Rise.Y) < 1e-9);
	const FVector Rise90 = SunPosition(SunRotation(SunPitchDeg(true, 0.01), 90.0));
	TestTrue(TEXT("yaw 90 이면 +Y 쪽에서 뜬다"), Rise90.Y > 0.99);

	// 달 = 해 + 180°: 빛 방향 정반대, 높이 = −해 높이. 팀 BP 는 정규화된 해 액터 회전(GetActorRotation)에서 만드는데 그래도 같다
	bool bMoon = true;
	for (const double Pitch : {0.0, 30.0, 90.0, 150.0, 180.0, 225.0, 270.0, 315.0, 359.0})
	{
		const FRotator S = SunRotation(Pitch, 0.0);
		const FRotator M = MoonRotation(S);
		const FRotator MFromNormalized = MoonRotation(S.Quaternion().Rotator());
		if (FVector::DotProduct(M.Vector(), S.Vector()) > -1.0 + 1e-9 || !MFromNormalized.Vector().Equals(M.Vector(), 1e-6)
			|| FMath::Abs(SunPosition(M).Z + SunPosition(S).Z) > 1e-9)
		{
			bMoon = false;
			AddInfo(FString::Printf(TEXT("달이 해의 반대가 아니다: 해 pitch %.0f"), Pitch));
		}
	}
	TestTrue(TEXT("달 = 해의 정반대 (팀 BP 식 MakeRotator(Roll, Pitch + 180, Yaw) 와 같은 방향)"), bMoon);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3SkyDarknessParityTest,
	"AdaptiveEcosystem.Policy.V3.Sky.DarknessParity",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3SkyDarknessParityTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3Sky;
	// 통합 v3 지역 세계: 주기 900 스텝 (60 + 60 초, 스텝 2/15 초), 시작 0, 어스름 45 스텝 (MakeRegionWorldConfig). 팀 시계 낮 시작 = 스텝 0.
	constexpr int32 Period = 900;
	constexpr int32 Half = Period / 2;
	double MaxDiff = 0.0;
	int32 WorstT = -1;
	int32 Dark0 = 0, Dark1 = 0, Twilight = 0;
	for (int32 T = 0; T < 2 * Period; ++T)
	{
		const int32 S = T % Period;
		const bool bDay = S < Half;
		const double P = static_cast<double>(S % Half) / static_cast<double>(Half);
		const double Sky = Darkness(SunElevationDeg(SunPitchDeg(bDay, P)));
		const double V3 = EcoObservationV3::DayNightPhase(T, Period, 0, 45).Dark;
		const double Diff = FMath::Abs(Sky - V3);
		if (Diff > MaxDiff)
		{
			MaxDiff = Diff;
			WorstT = T;
		}
		Dark0 += V3 == 0.0 ? 1 : 0;
		Dark1 += V3 == 1.0 ? 1 : 0;
		Twilight += V3 > 0.0 && V3 < 1.0 ? 1 : 0;
	}
	AddInfo(FString::Printf(TEXT("1800 스텝: 가장 큰 차이 %.3g (스텝 %d), v3 d = 0 %d · 1 %d · 어스름 %d 스텝"), MaxDiff, WorstT, Dark0, Dark1, Twilight));
	TestTrue(TEXT("하늘 어둠 = v3 어둠 (모든 스텝 1e-9 안)"), MaxDiff < 1e-9);
	TestTrue(TEXT("어스름이 실제로 있다 (경계마다 ±45 스텝 → 두 바퀴 4 경계 × 89 스텝 남짓)"), Twilight >= 4 * 88);
	TestTrue(TEXT("지평선 = d 0.5, 18° 위 = 0, 18° 아래 = 1"), Darkness(0.0) == 0.5 && Darkness(18.0) == 0.0 && Darkness(-18.0) == 1.0 && Darkness(60.0) == 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3SkyBrightnessTest,
	"AdaptiveEcosystem.Policy.V3.Sky.Brightness",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3SkyBrightnessTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3Sky;
	TestTrue(TEXT("밤 정도: d 0 → 0, 0.5 → 0, 0.75 → 0.5, 1 → 1"),
			 NightFactor(0.0) == 0.0 && NightFactor(0.5) == 0.0 && FMath::Abs(NightFactor(0.75) - 0.5) < 1e-12 && NightFactor(1.0) == 1.0);
	bool bMonotone = true;
	for (int32 i = 1; i <= 100; ++i)
	{
		bMonotone = bMonotone && NightFactor(i / 100.0) >= NightFactor((i - 1) / 100.0) && SunIntensityScale(-0.2 * i) <= SunIntensityScale(-0.2 * (i - 1));
	}
	TestTrue(TEXT("밤 정도는 d 를 따라 늘고, 해 세기 배수는 해가 내려갈수록 준다"), bMonotone);
	TestTrue(TEXT("해 세기 배수: 지평선 위 1, −6° 0.5, −12° 아래 0"),
			 SunIntensityScale(30.0) == 1.0 && SunIntensityScale(0.0) == 1.0 && FMath::Abs(SunIntensityScale(-6.0) - 0.5) < 1e-12
				 && SunIntensityScale(-12.0) == 0.0 && SunIntensityScale(-40.0) == 0.0);

	// 팀 값 (LV_Ecosystem_IntegrationTest·LV_EcoV3_JYUEcosystem 등: 해 8 lux, 달 0.01 lux 노랑 255,242,77, 하늘빛 1)
	FLook Team;
	Team.TeamSunIntensity = 8.0f;
	Team.TeamMoonIntensity = 0.01f;
	Team.TeamMoonColor = FLinearColor(FColor(255, 242, 77));
	Team.TeamSkyIntensity = 1.0f;
	Team.NightLux = 1.0;
	const FPose Noon = ComputePose(true, 0.5, Team);
	TestTrue(*FString::Printf(TEXT("한낮: 해 %.2f (팀 8), 달 %.3f (팀 0.01 그대로), 하늘빛 %.2f, 달 색 팀 그대로"), Noon.SunIntensity, Noon.MoonIntensity, Noon.SkyIntensity),
			 Noon.SunIntensity == 8.0f && Noon.MoonIntensity == 0.01f && Noon.SkyIntensity == 1.0f && Noon.MoonTintWeight == 0.0f && Noon.MoonColor == Team.TeamMoonColor
				 && Noon.Dark == 0.0 && Noon.Night == 0.0);
	const FPose Midnight = ComputePose(false, 0.5, Team);
	TestTrue(*FString::Printf(TEXT("한밤: 해 %.2f, 달 %.3f (밤 달빛 1), d %.2f"), Midnight.SunIntensity, Midnight.MoonIntensity, Midnight.Dark),
			 Midnight.SunIntensity == 0.0f && Midnight.MoonIntensity == 1.0f && Midnight.Dark == 1.0 && Midnight.Night == 1.0 && Midnight.SkyIntensity == 1.0f);
	// 어스름: 해 진 순간(밤 p 0) d 0.5 → 달 팀 값, 3 초 뒤(p 0.05) d 0.75 → 반쯤, 6 초 뒤(p 0.1) d 1 → 밤 달빛
	const FPose Dusk0 = ComputePose(false, 0.0, Team);
	const FPose Dusk3 = ComputePose(false, 0.05, Team);
	const FPose Dusk6 = ComputePose(false, 0.1, Team);
	TestTrue(*FString::Printf(TEXT("어스름 달빛: 0 초 %.3f · 3 초 %.3f · 6 초 %.3f"), Dusk0.MoonIntensity, Dusk3.MoonIntensity, Dusk6.MoonIntensity),
			 Dusk0.MoonIntensity == 0.01f && FMath::Abs(Dusk3.MoonIntensity - 0.505f) < 1e-4f && FMath::Abs(Dusk6.MoonIntensity - 1.0f) < 1e-5f
				 && FMath::Abs(Dusk0.Dark - 0.5) < 1e-9 && FMath::Abs(Dusk3.Dark - 0.75) < 1e-9);
	TestTrue(TEXT("해 진 순간 해 세기는 팀 값 (대기가 줄인다), 3 초 뒤(−9°) 줄고, 6 초 뒤(−18°) 0"),
			 Dusk0.SunIntensity == 8.0f && Dusk3.SunIntensity > 0.0f && Dusk3.SunIntensity < 8.0f && Dusk6.SunIntensity == 0.0f);
	bool bRising = true;
	for (int32 i = 1; i <= 50; ++i)
	{
		bRising = bRising && ComputePose(false, i / 100.0, Team).MoonIntensity >= ComputePose(false, (i - 1) / 100.0, Team).MoonIntensity;
	}
	TestTrue(TEXT("해 진 뒤 한밤까지 달빛이 줄지 않는다"), bRising);

	FLook Dim = Team;
	Dim.NightLux = 0.001;
	TestTrue(TEXT("밤 달빛을 팀 값보다 낮게 줘도 팀 값보다 어둡게 하지 않는다"), ComputePose(false, 0.5, Dim).MoonIntensity == 0.01f);
	FLook Bad = Team;
	Bad.NightLux = std::numeric_limits<double>::quiet_NaN();
	Bad.MoonTint = 7.0;
	Bad.NightSkyLight = -3.0;
	const FPose BadPose = ComputePose(false, 0.5, Bad);
	TestTrue(*FString::Printf(TEXT("이상한 콘솔 값: 달빛 NaN → 기본 %.2f, 색 섞기 7 → 1, 하늘빛 배수 −3 → 0 (달 %.3f, 섞기 %.2f, 하늘빛 %.2f)"), kDefaultNightLux,
							  BadPose.MoonIntensity, BadPose.MoonTintWeight, BadPose.SkyIntensity),
			 BadPose.MoonIntensity == static_cast<float>(kDefaultNightLux) && BadPose.MoonTintWeight == 1.0f && BadPose.SkyIntensity == 0.0f);
	FLook Huge = Team;
	Huge.NightLux = 1e9;
	TestTrue(TEXT("밤 달빛은 1000 lux 로 자른다"), ComputePose(false, 0.5, Huge).MoonIntensity == 1000.0f);

	FLook Tinted = Team;
	Tinted.MoonTint = 1.0;
	Tinted.NightSkyLight = 3.0;
	const FPose TintNight = ComputePose(false, 0.5, Tinted);
	const FPose TintDay = ComputePose(true, 0.5, Tinted);
	TestTrue(TEXT("달 색 섞기 1: 한밤은 차가운 달빛, 한낮은 팀 색 그대로"),
			 TintNight.MoonColor.Equals(CoolMoonColor(), 1e-6f) && TintNight.MoonTintWeight == 1.0f && TintDay.MoonTintWeight == 0.0f
				 && TintDay.MoonColor == Tinted.TeamMoonColor);
	TestTrue(TEXT("밤 하늘빛 ×3: 한밤 3, 한낮 1 (팀 값)"), TintNight.SkyIntensity == 3.0f && TintDay.SkyIntensity == 1.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3SkyClientClockTest,
	"AdaptiveEcosystem.Policy.V3.Sky.ClientClock",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3SkyClientClockTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3Sky;
	auto Sample = [](int32 Epoch, double T, bool bDay, double Start, double End)
	{
		FClockSample S;
		S.Epoch = Epoch;
		S.ServerSeconds = T;
		S.bDay = bDay;
		S.PhaseStart = Start;
		S.PhaseEnd = End;
		return S;
	};
	// 팀 고정 주기 (낮 60·밤 60) 의 표본
	auto Fixed = [&Sample](int32 Epoch, double T)
	{
		const double Cycle = FMath::FloorToDouble(T / 120.0) * 120.0;
		const bool bDay = T - Cycle < 60.0;
		return Sample(Epoch, T, bDay, bDay ? Cycle : Cycle + 60.0, bDay ? Cycle + 60.0 : Cycle + 120.0);
	};
	constexpr double Dt = 1.0 / 60.0;

	{
		FDisplayClock C;
		bool bDay = true;
		double P = 0.0;
		StepClock(C, Dt, nullptr);
		TestFalse(TEXT("표본 전: 보이는 시각 없음 (하늘은 팀 그대로)"), ClockPhase(C, bDay, P));
		const FClockSample First = Fixed(1, 10.0);
		StepClock(C, Dt, &First);
		TestTrue(TEXT("첫 표본에 곧바로 맞춘다"), C.bHas && C.Shown == 10.0 && C.Snaps == 1 && ClockPhase(C, bDay, P) && bDay && FMath::Abs(P - 10.0 / 60.0) < 1e-12);
	}
	{
		// 서버 시각을 1 초마다 정확히 받는다 (60 fps) → 그대로 따라간다
		FDisplayClock C;
		double Now = 5.0;
		const FClockSample First = Fixed(1, Now);
		StepClock(C, 0.0, &First);
		double MaxErr = 0.0;
		for (int32 F = 1; F <= 60 * 130; ++F)
		{
			Now += Dt;
			const FClockSample S = Fixed(1, Now);
			StepClock(C, Dt, F % 60 == 0 ? &S : nullptr);
			MaxErr = FMath::Max(MaxErr, FMath::Abs(C.Shown - Now));
		}
		TestTrue(*FString::Printf(TEXT("정확한 1 초 표본 130 초: 가장 큰 어긋남 %.3g 초 (1e-6 안), 맞춤 %d 번"), MaxErr, C.Snaps), MaxErr < 1e-6 && C.Snaps == 1);
	}
	{
		// 늦고(0.1 초) 흔들리는(±0.15 초) 표본 → 뒤로 가지 않고, 늦은 서버 시각에서 0.3 초 안
		FDisplayClock C;
		double Now = 0.0;
		const FClockSample First = Fixed(1, Now);
		StepClock(C, 0.0, &First);
		const double Noise[] = {0.15, -0.15, 0.05, -0.1, 0.12, -0.02, 0.0, -0.15, 0.15, 0.08};
		bool bForward = true;
		double MaxErr = 0.0;
		int32 Received = 0;
		for (int32 F = 1; F <= 60 * 60; ++F)
		{
			Now += Dt;
			const double Before = C.Shown;
			const bool bArrive = F % 60 == 0;
			const FClockSample S = Fixed(1, Now - 0.1 + Noise[Received % 10]);
			StepClock(C, Dt, bArrive ? &S : nullptr);
			Received += bArrive ? 1 : 0;
			bForward = bForward && C.Shown >= Before;
			if (Now > 5.0)
			{
				MaxErr = FMath::Max(MaxErr, FMath::Abs(C.Shown - (Now - 0.1)));
			}
		}
		TestTrue(*FString::Printf(TEXT("흔들리는 표본 60 초: 뒤로 가지 않음 %d, 늦은 서버 시각과 가장 큰 어긋남 %.3f 초 (0.3 안), 맞춤 %d 번"), bForward ? 1 : 0, MaxErr,
								  C.Snaps),
				 bForward && MaxErr <= 0.3 && C.Snaps == 1);
		// 5 초 건너뜀 → 곧바로 맞춤
		const FClockSample Jump = Fixed(1, C.Shown + 5.0);
		StepClock(C, Dt, &Jump);
		TestTrue(TEXT("2 초 넘게 어긋나면 곧바로 맞춘다"), C.Shown == Jump.ServerSeconds && C.Snaps == 2 && C.Pending == 0.0);
		// 판이 바뀌면 가까워도 맞춤
		const FClockSample Reset = Fixed(2, C.Shown + 0.5);
		StepClock(C, Dt, &Reset);
		TestTrue(TEXT("세계 판이 바뀌면 곧바로 맞춘다"), C.Shown == Reset.ServerSeconds && C.Snaps == 3);
		// 멈춤: dt 0 이면 새 표본이 와도 움직이지 않는다 (메울 몫만 남는다)
		const double Frozen = C.Shown;
		const FClockSample Near = Fixed(2, C.Shown + 0.5);
		StepClock(C, 0.0, &Near);
		TestTrue(TEXT("멈춤(dt 0): 그대로"), C.Shown == Frozen && FMath::Abs(C.Pending - 0.5) < 1e-12);
	}
	{
		// 위상 밖: 낮 표본(0~60, 59.5 초) 뒤 1 초 동안 표본이 없으면 밤 0.5 초로 이어 간다 (밤 길이를 아직 못 봤으면 낮 길이)
		FDisplayClock C;
		const FClockSample S = Sample(1, 59.5, true, 0.0, 60.0);
		StepClock(C, 0.0, &S);
		for (int32 F = 0; F < 60; ++F)
		{
			StepClock(C, Dt, nullptr);
		}
		bool bDay = true;
		double P = 0.0;
		const bool bPhase = ClockPhase(C, bDay, P);
		TestTrue(*FString::Printf(TEXT("낮 끝을 넘으면 밤으로 이어 간다 (밤 p %.4f)"), P), bPhase && !bDay && FMath::Abs(P - 0.5 / 60.0) < 1e-6);
		// 본 길이를 쓴다: 밤 40 초(60~100)를 본 뒤 낮(100~160) 150 초 표본에서 20 초 표본 없이 → 170 초 = 밤 10/40
		const FClockSample Night = Sample(1, 70.0, false, 60.0, 100.0);
		StepClock(C, 0.0, &Night);
		const FClockSample Day = Sample(1, 150.0, true, 100.0, 160.0);
		StepClock(C, 0.0, &Day);
		for (int32 F = 0; F < 20 * 60; ++F)
		{
			StepClock(C, Dt, nullptr);
		}
		const bool bPhase2 = ClockPhase(C, bDay, P);
		TestTrue(*FString::Printf(TEXT("본 밤 길이 40 초를 쓴다 (낮 %.0f · 밤 %.0f 초, 밤 p %.4f)"), C.DaySeconds, C.NightSeconds, P),
				 bPhase2 && !bDay && FMath::Abs(P - 0.25) < 1e-6 && C.DaySeconds == 60.0 && C.NightSeconds == 40.0);
	}
	{
		bool bDay = true;
		double P = 0.0;
		TestTrue(TEXT("위상 시작 전 시각은 앞 위상의 끝 (밤 60~120 표본, 50 초 = 낮 p 0.833)"),
				 PhaseAt(Sample(1, 70.0, false, 60.0, 120.0), 50.0, 0.0, bDay, P) && bDay && FMath::Abs(P - 50.0 / 60.0) < 1e-12);
		TestTrue(TEXT("위상 끝 = 다음 위상 시작 (p 0)"), PhaseAt(Sample(1, 30.0, true, 0.0, 60.0), 60.0, 60.0, bDay, P) && !bDay && P == 0.0);
		TestTrue(TEXT("두 바퀴 뒤에도 이어 간다 (250 초 = 낮 p 10/60)"), PhaseAt(Sample(1, 30.0, true, 0.0, 60.0), 250.0, 60.0, bDay, P) && bDay
			&& FMath::Abs(P - 10.0 / 60.0) < 1e-12);
		TestFalse(TEXT("위상 길이 0 이하면 거짓"), PhaseAt(Sample(1, 30.0, true, 60.0, 60.0), 30.0, 60.0, bDay, P));
		FDisplayClock C;
		const FClockSample Broken = Sample(1, 30.0, true, 60.0, 0.0);
		StepClock(C, Dt, &Broken);
		TestFalse(TEXT("깨진 표본(끝 < 시작)은 받지 않는다"), C.bHas);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3SkyRigTest,
	"AdaptiveEcosystem.Policy.V3.Sky.Rig",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3SkyRigTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3Sky;
	using EcoV3SkyPresenterTestImpl::SpawnLight;
	{
		EcoTest::FScopedTestWorld W;
		if (!TestNotNull(TEXT("시험 월드"), W.World))
		{
			return false;
		}
		// 팀 맵과 같은 놓임: 해 (p−30, y105, r−180) 8 lux 색인 0, 달 (p−30, y105, r180) 0.01 lux 노랑 색인 1, 그리고 대기 빛 아닌 채움 빛 2 lux
		const FColor MoonYellow(255, 242, 77);
		ADirectionalLight* SunA = SpawnLight(*W.World, 8.0f, 0, FRotator(-30.0, 105.0, -180.0), FColor::White);
		ADirectionalLight* MoonA = SpawnLight(*W.World, 0.01f, 1, FRotator(-30.0, 105.0, 180.0), MoonYellow);
		ADirectionalLight* FillA = SpawnLight(*W.World, 2.0f, -1, FRotator(-60.0, 10.0, 0.0), FColor::White);
		if (!TestTrue(TEXT("방향광 셋을 띄웠다"), SunA && MoonA && FillA))
		{
			return false;
		}
		UDirectionalLightComponent* SunC = SunA->GetComponent();
		UDirectionalLightComponent* MoonC = MoonA->GetComponent();
		UDirectionalLightComponent* FillC = FillA->GetComponent();
		const FQuat SunQ0 = SunC->GetComponentQuat();
		const FQuat MoonQ0 = MoonC->GetComponentQuat();
		const FQuat FillQ0 = FillC->GetComponentQuat();

		FSkyRig Rig;
		TestTrue(TEXT("찾기: 해 방향광이 있다"), Rig.Capture(*W.World));
		TestTrue(TEXT("해 = 대기 빛 색인 0, 달 = 색인 1, 팀 하늘 BP 없음, 하늘빛 없음"),
				 Rig.Sun.Get() == SunC && Rig.Moon.Get() == MoonC && !Rig.SkyManager.IsValid() && !Rig.Sky.IsValid() && Rig.IsAlive());
		TestTrue(*FString::Printf(TEXT("해 길 방위 = 놓인 해의 방위 105° (roll 180 이어도 앞 방향으로, 잰 값 %.3f)"), Rig.SunYawDeg), FMath::Abs(Rig.SunYawDeg - 105.0) < 1e-3);
		TestTrue(TEXT("처음 값을 적었다 (세기·색)"), Rig.OriginalSunIntensity == 8.0f && Rig.OriginalMoonIntensity == 0.01f && Rig.OriginalMoonColor == MoonYellow);

		FLook Look = Rig.BaseLook();
		TestTrue(TEXT("연출 입력 기본값 = 콘솔 기본값 (밤 달빛 1 lux, 달 색 섞기 1)"), Look.NightLux == kDefaultNightLux && Look.MoonTint == kDefaultMoonTint && Look.MoonTint == 1.0);
		Look.NightLux = 1.0;
		Look.MoonTint = 0.0;                          // 팀 색 그대로 (섞기 0) 부터 본다
		Rig.Apply(ComputePose(false, 0.5, Look));   // 한밤
		const FVector SunF = SunC->GetComponentRotation().Vector();
		const FVector MoonF = MoonC->GetComponentRotation().Vector();
		TestTrue(*FString::Printf(TEXT("한밤: 해 빛은 위로 (해 발밑, 앞 z %.3f), 달 빛은 아래로 (달 머리 위, 앞 z %.3f)"), SunF.Z, MoonF.Z), SunF.Z > 0.999 && MoonF.Z < -0.999);
		TestTrue(*FString::Printf(TEXT("한밤: 해 세기 %.2f (0), 달 세기 %.3f (1), 달 색 팀 그대로"), SunC->Intensity, MoonC->Intensity),
				 SunC->Intensity == 0.0f && MoonC->Intensity == 1.0f && MoonC->LightColor == MoonYellow);
		TestTrue(TEXT("대기 빛 아닌 방향광은 손대지 않는다"), FillC->Intensity == 2.0f && FillC->GetComponentQuat().Equals(FillQ0, 1e-6));

		Rig.Apply(ComputePose(true, 0.5, Look));    // 한낮
		TestTrue(TEXT("한낮: 해 빛은 아래로 (머리 위), 해 8 lux, 달 0.01 lux"),
				 SunC->GetComponentRotation().Vector().Z < -0.999 && MoonC->GetComponentRotation().Vector().Z > 0.999 && SunC->Intensity == 8.0f
					 && MoonC->Intensity == 0.01f);
		Rig.Apply(ComputePose(true, 0.25, Look));   // 낮 15 초: 해 높이 45°, 방위 105° 쪽에서 떠오르는 길
		const FVector SunPos = -SunC->GetComponentRotation().Vector();
		TestTrue(*FString::Printf(TEXT("낮 15 초: 해 자리 높이 45° (z %.3f), 방위 105° 쪽 (%.1f°)"), SunPos.Z, FMath::RadiansToDegrees(FMath::Atan2(SunPos.Y, SunPos.X))),
				 FMath::Abs(SunPos.Z - FMath::Sin(FMath::DegreesToRadians(45.0))) < 1e-4
					 && FMath::Abs(FMath::RadiansToDegrees(FMath::Atan2(SunPos.Y, SunPos.X)) - 105.0) < 1e-3);

		Look.MoonTint = 1.0;
		Rig.Apply(ComputePose(false, 0.5, Look));
		TestTrue(TEXT("달 색 섞기 1: 한밤 달 색이 바뀐다"), MoonC->LightColor != MoonYellow);

		Rig.Restore();
		TestTrue(TEXT("되돌리기: 회전·세기·색이 처음 값"),
				 SunC->GetComponentQuat().Equals(SunQ0, 1e-4) && MoonC->GetComponentQuat().Equals(MoonQ0, 1e-4) && SunC->Intensity == 8.0f
					 && MoonC->Intensity == 0.01f && MoonC->LightColor == MoonYellow);
		TestTrue(TEXT("되돌린 뒤 손잡이를 놓는다"), !Rig.bCaptured && !Rig.Sun.IsValid() && !Rig.IsAlive());
	}
	{
		// Static 해는 돌릴 수 없다 → 찾기 실패, 아무것도 바꾸지 않는다
		EcoTest::FScopedTestWorld W;
		if (!TestNotNull(TEXT("시험 월드 2"), W.World))
		{
			return false;
		}
		ADirectionalLight* SunA = SpawnLight(*W.World, 8.0f, 0, FRotator(-45.0, 0.0, 0.0), FColor::White);
		if (!TestNotNull(TEXT("방향광"), SunA))
		{
			return false;
		}
		SunA->GetComponent()->SetMobility(EComponentMobility::Static);
		const FQuat Q0 = SunA->GetComponent()->GetComponentQuat();
		FSkyRig Rig;
		TestFalse(TEXT("Static 해: 찾기 실패"), Rig.Capture(*W.World));
		Rig.Apply(ComputePose(false, 0.5, FLook()));
		TestTrue(TEXT("Static 해: 그대로"), SunA->GetComponent()->GetComponentQuat().Equals(Q0, 1e-6) && SunA->GetComponent()->Intensity == 8.0f);
	}
	{
		// 방향광이 없는 월드 → 찾기 실패
		EcoTest::FScopedTestWorld W;
		FSkyRig Rig;
		TestFalse(TEXT("방향광 없는 월드: 찾기 실패"), W.World && Rig.Capture(*W.World));
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
