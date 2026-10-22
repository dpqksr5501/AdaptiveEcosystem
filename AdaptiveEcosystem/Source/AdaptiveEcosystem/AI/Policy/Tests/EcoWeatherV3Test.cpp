// v3 야생 3단계 자동화 시험 — C++ 지역 날씨(EcoWorldV3.h FWeatherConfig·WeatherAt·WeatherMults·UpdateDayNight·SeePredNow·발소리·사슴 속도,
// EcoThreatModel.h Step 의 WeatherViewMult·WeatherSpeedMult)를 파이썬(env_v2/world.py wild_weather, configs/v3_wild3_mirror.yaml)과 대조하고,
// 통합 모드 기본값·연출 순수 함수를 본다 (명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md 11절).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Weather"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `WeatherGoldenVectorsV3.h` (herbivore_rl/export_golden_v3_weather.py)이고, 검사 본문은 `WeatherGoldenCheckV3.h` 다. 같은 검사를
// herbivore_rl/tests/test_wild3_weather.py 가 g++ 로도 돌린다(tests/cpp/weather_v3_main.cpp).
//
// 묶음:
//   Weather.Golden             설정(기본 끔·계수·지역 표 = 거울 설정), 배수·시간표·낮밤(UpdateDayNight)·지각(BuildThreatInputs 발소리 × 사슴 청각 →
//                              PerceiveThreats)·한 스텝(PackPeek → PackGoals → Step, 날씨 시야·속력) 비트 단위, 날씨를 끈 세계 = 맑음·배수 1 인 비·세기 0 눈
//                              (기준 루프 240 스텝 비트 동일), 첫 스텝 눈 이동 × 0.6·× 0.85
//   Weather.IntegratedDefaults 통합 기본값: 날씨 켬·연출 켬, 지역 날씨 = 팀 설계 (숲 비 1·고지 눈 1·메마른 땅 맑음·표에 없는 지역 맑음), 덮기 글자 읽기,
//                              MakeRegionWorldConfig 가 지역 날씨·감지 기록을 넘긴다, 끄면 날씨 끔
//   Weather.SenseStats         감지 기록: 기준 루프에서 쌍·감지·들어서만이 센다 (감지 ≤ 쌍, 들어서만 ≤ 산 사슴·스텝), 비가 오면 들어서만 몫이 준다,
//                              기록을 꺼도 논리 상태는 같다
//   Weather.Presenter          연출 순수 함수: 페이드(들어가면 1.5 초·나오면 1 초, 넘지 않음), 날씨 → 비·눈 목표, 지역 상자 가로 판정(높이 무시)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoV3WeatherPresenter.h"
#include "../EcoWorldV3.h"
#include "WeatherGoldenCheckV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoWeatherV3Test
{
	using EcoWorldV3::WeatherCheck::FReport;

	void Report(FAutomationTestBase& Test, const TCHAR* What, const FReport& R)
	{
		Test.AddInfo(FString::Printf(TEXT("%s: 사례 %d, 어긋남 %d (처음 사례 %d 칸 %d), 날씨가 바꾼 것 %d, 센 것 %d"), What, R.Cases, R.Failures, R.FirstCase,
									 R.FirstField, R.Changed, R.Count));
		Test.TestTrue(*FString::Printf(TEXT("%s: 파이썬과 비트 단위로 같다"), What), R.Passed());
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWeatherV3GoldenTest,
	"AdaptiveEcosystem.Policy.V3.Weather.Golden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWeatherV3GoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoWeatherV3Test;
	namespace WC = EcoWorldV3::WeatherCheck;
	namespace G = EcoWorldV3::GoldenWeather;
	Report(*this, TEXT("설정"), WC::CheckConfig());
	Report(*this, TEXT("배수"), WC::CheckMults());
	Report(*this, TEXT("시간표"), WC::CheckSchedule());
	Report(*this, TEXT("낮밤"), WC::CheckDayNight());
	const FReport Perc = WC::CheckPerception();
	Report(*this, TEXT("지각"), Perc);
	TestTrue(TEXT("지각: 알아챔 수 = 골든, 날씨가 바꾼 쌍이 있다"), Perc.Count == G::kPercSeen && Perc.Changed > 0);
	const FReport Steps = WC::CheckSteps();
	Report(*this, TEXT("한 스텝"), Steps);
	TestTrue(TEXT("한 스텝: 포획 수 = 골든, 날씨가 바꾼 늑대가 있다"), Steps.Count == G::kStepCatches && Steps.Changed > 0);
	Report(*this, TEXT("끄면 그대로 (맑음·배수 1 인 비·세기 0 눈 = 날씨 끔, 기준 루프 240 스텝)"), WC::CheckOffIdentical());
	const FReport Snow = WC::CheckSnowFirstStep();
	Report(*this, TEXT("첫 스텝 눈 이동"), Snow);
	TestTrue(TEXT("첫 스텝 눈 이동: 견준 개체가 있다"), Snow.Count > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWeatherV3IntegratedDefaultsTest,
	"AdaptiveEcosystem.Policy.V3.Weather.IntegratedDefaults",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWeatherV3IntegratedDefaultsTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	const FEcoV3IntegratedSettings Def;
	TestTrue(TEXT("통합 기본: 지역 날씨 켬 (eco.IntegratedV3.Weather 1)"), Def.bWeather);
	TestTrue(TEXT("통합 기본: 비·눈 연출 켬 (eco.IntegratedV3.WeatherVisuals 1)"), Def.bWeatherVisuals);
	TestTrue(TEXT("통합 기본: 지역 덮기 없음"), Def.WeatherForest.IsEmpty() && Def.WeatherHighland.IsEmpty() && Def.WeatherBarren.IsEmpty());
	TestFalse(TEXT("세계 설정 기본은 날씨 끔 (평면 맵·기준 루프·골든 그대로)"), FWorldConfig().Weather.bEnabled);
	struct FWant
	{
		const TCHAR* Region;
		int32 Kind;
		double Intensity;
	};
	for (const FWant& Wv : {FWant{TEXT("Forest"), kWeatherRain, 1.0}, FWant{TEXT("Highland"), kWeatherSnow, 1.0}, FWant{TEXT("Barren"), kWeatherClear, 0.0},
							FWant{TEXT("Elsewhere"), kWeatherClear, 0.0}})
	{
		const FWeatherConfig W = Def.WeatherFor(FName(Wv.Region));
		TestTrue(*FString::Printf(TEXT("%s: 날씨 켬 · %d · %.2f (팀 설계)"), Wv.Region, Wv.Kind, Wv.Intensity),
				 W.bEnabled && W.Kind == Wv.Kind && W.Intensity == Wv.Intensity && W.Schedule.empty());
		const FWeatherConfig D;
		TestTrue(*FString::Printf(TEXT("%s: 배수 계수 = 거울 설정 (FWeatherConfig 기본값)"), Wv.Region),
				 W.RainSight == D.RainSight && W.RainHear == D.RainHear && W.SnowSight == D.SnowSight && W.SnowHear == D.SnowHear
					 && W.SnowDeerSpeed == D.SnowDeerSpeed && W.SnowWolfSpeed == D.SnowWolfSpeed && W.bObsVisibility == D.bObsVisibility);
	}
	// 덮기 글자
	struct FParseCase
	{
		const TCHAR* Text;
		bool bOk;
		int32 Kind;
		double Intensity;
	};
	for (const FParseCase& P : {FParseCase{TEXT("rain:0.5"), true, kWeatherRain, 0.5}, FParseCase{TEXT("snow"), true, kWeatherSnow, 1.0},
							FParseCase{TEXT("Rain, 0.25"), true, kWeatherRain, 0.25}, FParseCase{TEXT("clear:0.7"), true, kWeatherClear, 0.0},
							FParseCase{TEXT("눈 0.3"), true, kWeatherSnow, 0.3}, FParseCase{TEXT("맑음"), true, kWeatherClear, 0.0},
							FParseCase{TEXT("rain:2"), true, kWeatherRain, 1.0}, FParseCase{TEXT("fog"), false, -1, -1.0}, FParseCase{TEXT("rain:x"), false, -1, -1.0},
							FParseCase{TEXT(""), false, -1, -1.0}})
	{
		int32 Kind = -1;
		double Intensity = -1.0;
		const bool bOk = FEcoV3IntegratedSettings::ParseWeather(P.Text, Kind, Intensity);
		TestTrue(*FString::Printf(TEXT("ParseWeather('%s') = %s"), P.Text, P.bOk ? TEXT("읽음") : TEXT("못 읽음")),
				 bOk == P.bOk && Kind == P.Kind && Intensity == P.Intensity);
	}
	FEcoV3IntegratedSettings Over = Def;
	Over.WeatherHighland = TEXT("snow:0.5");
	Over.WeatherForest = TEXT("fog");   // 못 읽으면 팀 설계 기본 (경고 한 줄씩 — 아래 두 번 부른다)
	AddExpectedMessagePlain(TEXT("날씨 덮기 'fog' 를 못 읽었다"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 2);
	TestTrue(TEXT("고지 덮기 snow:0.5"), Over.WeatherFor(TEXT("Highland")).Kind == kWeatherSnow && Over.WeatherFor(TEXT("Highland")).Intensity == 0.5);
	TestTrue(TEXT("못 읽은 숲 덮기 → 팀 설계 비 1"), Over.WeatherFor(TEXT("Forest")).Kind == kWeatherRain && Over.WeatherFor(TEXT("Forest")).Intensity == 1.0);
	// 세계 설정으로 넘김
	const std::vector<EcoObservationV3::FCoverInput> Covers = QuadCovers(Def.StageSizeUnits, 6.0);
	const FWorldConfig C = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Def, 0, 128, Def.WolvesPerRegion, Covers, TEXT("Highland"));
	TestTrue(TEXT("MakeRegionWorldConfig(고지): 눈 1 켬, 감지 기록 켬"), C.Weather.bEnabled && C.Weather.Kind == kWeatherSnow && C.Weather.Intensity == 1.0 && C.bSenseStats);
	FWorldState W;
	InitWorld(W, C);
	TestTrue(TEXT("InitWorld → 결정 때 날씨 눈 1, 배수 (0.7, 1, 0.6, 0.85)"), W.WeatherKind == kWeatherSnow && W.WeatherIntensity == 1.0 && W.Weather.Sight == 0.7
																	   && W.Weather.Hear == 1.0 && W.Weather.DeerSpeed == 0.6 && W.Weather.WolfSpeed == 0.85);
	TestTrue(TEXT("고지: 늑대 시야 28 m → 19.6 m (단위 14 × 0.7)"), WolfViewNow(W) == W.ThreatCfg.PredViewR * 0.7);
	FEcoV3IntegratedSettings Off = Def;
	Off.bWeather = false;
	const FWorldConfig Co = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Off, 0, 128, 4, Covers, TEXT("Forest"));
	TestFalse(TEXT("Weather 0 → 세계 날씨 끔"), Co.Weather.bEnabled);
	FWorldState Wo;
	InitWorld(Wo, Co);
	TestTrue(TEXT("Weather 0 → 맑음·배수 1, 탐지 반경 = SeePredRadius"), Wo.WeatherKind == kWeatherClear && Wo.Weather.Sight == 1.0
																		&& SeePredNow(Wo) == EcoObservationV3::SeePredRadius(Wo.Dark, Wo.ObsCfg));
	// 잘못된 날씨 설정은 InitWorld 가 끈다 (파이썬 _wild_weather_params 가 거부하는 값)
	FWorldConfig Bad = C;
	Bad.Weather.Intensity = 1.5;
	FWorldState Wb;
	InitWorld(Wb, Bad);
	TestFalse(TEXT("세기 1.5 → 날씨 끔"), Wb.Config.Weather.bEnabled);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWeatherV3SenseStatsTest,
	"AdaptiveEcosystem.Policy.V3.Weather.SenseStats",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWeatherV3SenseStatsTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	namespace WC = EcoWorldV3::WeatherCheck;
	auto Run = [](const FWeatherConfig& Wx, bool bStats, FReferenceWorld& Ref)
	{
		FWorldConfig C = WC::RefConfig(Wx, 64);
		C.bSenseStats = bStats;
		Ref.Init(C);
		for (int32 t = 0; t < 600; ++t)
		{
			Ref.StepOnce();
		}
	};
	FWeatherConfig Rain;
	Rain.bEnabled = true;
	Rain.Kind = kWeatherRain;
	Rain.Intensity = 1.0;
	FReferenceWorld Clear, Wet, NoStats;
	Run(FWeatherConfig(), true, Clear);
	Run(Rain, true, Wet);
	Run(FWeatherConfig(), false, NoStats);
	const FWorldStats& S = Clear.World.Stats;
	int64 Pairs = 0, Seen = 0;
	bool bLe = true;
	for (int32 b = 0; b < kNumSenseBands; ++b)
	{
		Pairs += S.SensePairs[b];
		Seen += S.SenseSeen[b];
		bLe = bLe && S.SenseSeen[b] <= S.SensePairs[b];
	}
	TestTrue(TEXT("감지 기록: 쌍·감지가 있고 감지 ≤ 쌍"), Pairs > 0 && Seen > 0 && bLe);
	TestTrue(TEXT("감지 기록: 산 사슴·스텝 > 0, 들어서만 ≤ 산 사슴·스텝"), S.SenseLiveSteps > 0 && S.SenseHeardOnly <= S.SenseLiveSteps);
	TestTrue(TEXT("기록을 꺼도 논리 상태는 같다 (600 스텝)"), WC::SameState(Clear, NoStats));
	TestTrue(TEXT("기록을 끈 세계는 세지 않는다"), NoStats.World.Stats.SenseLiveSteps == 0 && NoStats.World.Stats.SensePairs[0] == 0);
	const double HeardClear = static_cast<double>(S.SenseHeardOnly) / static_cast<double>(FMath::Max<int64>(1, S.SenseLiveSteps));
	const FWorldStats& R = Wet.World.Stats;
	const double HeardRain = static_cast<double>(R.SenseHeardOnly) / static_cast<double>(FMath::Max<int64>(1, R.SenseLiveSteps));
	TestTrue(TEXT("비 세계: 날씨 스텝이 모두 비"), R.WeatherSteps[kWeatherRain] == 600 && R.WeatherSteps[kWeatherClear] == 0);
	TestTrue(TEXT("비가 오면 들어서만 안 몫이 준다 (빗소리가 발소리를 덮음)"), HeardRain < HeardClear);
	AddInfo(FString::Printf(TEXT("들어서만: 맑음 %.4f · 비 %.4f, 쌍 %lld 감지 %lld"), HeardClear, HeardRain, static_cast<long long>(Pairs),
							static_cast<long long>(Seen)));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWeatherV3PresenterTest,
	"AdaptiveEcosystem.Policy.V3.Weather.Presenter",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWeatherV3PresenterTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3WeatherFx;
	// 페이드: 1/30 초 프레임으로 0 → 1 은 1.5 초(45 프레임), 1 → 0 은 1 초(30 프레임). 목표를 넘지 않는다
	double A = 0.0;
	int32 Up = 0;
	while (A < 1.0 && Up < 1000)
	{
		A = Approach(A, 1.0, 1.0 / 30.0);
		++Up;
	}
	int32 Down = 0;
	while (A > 0.0 && Down < 1000)
	{
		A = Approach(A, 0.0, 1.0 / 30.0);
		++Down;
	}
	TestTrue(*FString::Printf(TEXT("페이드: 세지는 데 %d 프레임 (45 ± 1), 약해지는 데 %d 프레임 (30 ± 1)"), Up, Down), FMath::Abs(Up - 45) <= 1 && FMath::Abs(Down - 30) <= 1);
	TestEqual(TEXT("페이드: 목표 0.5 를 넘지 않는다"), Approach(0.45, 0.5, 1.0), 0.5);
	TestEqual(TEXT("페이드: 시간 0 이면 그대로"), Approach(0.3, 1.0, 0.0), 0.3);
	double Rain = -1.0, Snow = -1.0;
	Targets(EcoWorldV3::kWeatherRain, 0.8, Rain, Snow);
	TestTrue(TEXT("비 0.8 → 비 목표 0.8, 눈 0"), Rain == 0.8 && Snow == 0.0);
	Targets(EcoWorldV3::kWeatherSnow, 1.0, Rain, Snow);
	TestTrue(TEXT("눈 1 → 비 0, 눈 1"), Rain == 0.0 && Snow == 1.0);
	Targets(EcoWorldV3::kWeatherClear, 0.0, Rain, Snow);
	TestTrue(TEXT("맑음 → 둘 다 0"), Rain == 0.0 && Snow == 0.0);
	// 지역 상자 가로 판정: 높이는 보지 않는다 (높은 카메라도 그 땅의 날씨)
	const FTransform Box(FRotator(0.0, 30.0, 0.0), FVector(1000.0, -500.0, 0.0));
	const FVector Ext(5000.0, 2000.0, 150.0);
	TestTrue(TEXT("상자 가운데"), ContainsXY(Box, Ext, FVector(1000.0, -500.0, 0.0)));
	TestTrue(TEXT("상자 위 200 m (높이 무시)"), ContainsXY(Box, Ext, FVector(1000.0, -500.0, 20000.0)));
	TestFalse(TEXT("상자 옆 밖 (회전한 짧은 축 3000 cm)"), ContainsXY(Box, Ext, Box.TransformPosition(FVector(0.0, 3000.0, 0.0))));
	TestTrue(TEXT("상자 긴 축 4900 cm"), ContainsXY(Box, Ext, Box.TransformPosition(FVector(4900.0, 0.0, 0.0))));
	return true;
}

#endif
