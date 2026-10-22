// v3 숲 시야 자동화 시험 — C++ 숲 시야(EcoThreatModel.h FoliageChord·FoliageBlocked·InputSightBlocked, EcoObservationV3.h ObstacleObsValues 의
// threat_hidden, EcoWorldV3.h FObstacleConfig::Foliage·FlightPairOf·FlightUpdate 의 lost_foliage·단계 함수)를 파이썬(env_v2/world.py 모듈 docstring
// '야생 2단계' 3 의 7) — `foliage_chord`·`foliage_blocked`, 12880eb)과 대조한다 (10-22, 기본 끔).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Foliage"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `FoliageGoldenVectorsV3.h` (herbivore_rl/export_golden_v3_foliage.py)이고, 검사 본문은 `FoliageGoldenCheckV3.h` 다. 같은 검사를 g++ 하네스
// (herbivore_rl/tests/cpp/foliage_v3_main.cpp)도 부른다.
//
// 묶음:
//   Foliage.Golden  정의(기본 끔·r 3·block 2, 끈 설정·block_sight 끔·나무 표 길이 다름은 재지 않음), 눈길 길이 564 (손 사례 + 난수 — a → b 와 b → a 비트 동일,
//                   잎 구간 64 넘는 차례 고르기 길 포함), 관측 threat_hidden 192 (E·N 비트, 줄기 ∨ 잎), 쌍 장면 48 (위협 Step 의 사냥·표적, FlightPairOf 의 가림·
//                   잎만 가림), 도망 기록 장면 2 (lost_foliage·_fl_why_fol)
//   Foliage.World   거울 세계 사슴 48 숲 시야 켬 450 스텝 — 파이썬(동족 차례 합 기하)과 스텝마다 상태 지문·90 스텝마다 기록이 비트 단위로 같다 (잎 놓침이 있다)
//   Foliage.Off     같은 시작의 숲 시야 끔 450 스텝 = 파이썬 끔 판 (끔 = 지금 그대로), 끈 칸에 엉뚱한 r·block·나무 표를 넣어도 같다. 통합 모드 설정
//                   (eco.IntegratedV3.Foliage 기본 0 → 세계 끔, 켜면 6 m·4 m = 3·2 단위, 장애물을 끄면 재지 않는다)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "FoliageGoldenCheckV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoFoliageV3Test
{
	using EcoWorldV3::FoliageCheck::FReport;

	void Report(FAutomationTestBase& Test, const TCHAR* What, const FReport& R)
	{
		Test.AddInfo(FString::Printf(TEXT("%s: 사례 %d, 어긋남 %d (처음 사례 %d 칸 %d), 셈 %lld·%lld·%lld"), What, R.Cases, R.Failures, R.FirstCase, R.FirstField,
									 static_cast<long long>(R.Count0), static_cast<long long>(R.Count1), static_cast<long long>(R.Count2)));
		Test.TestTrue(*FString::Printf(TEXT("%s: 파이썬과 비트 단위로 같다"), What), R.Passed());
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoFoliageV3GoldenTest,
	"AdaptiveEcosystem.Policy.V3.Foliage.Golden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoFoliageV3GoldenTest::RunTest(const FString& Parameters)
{
	namespace FC = EcoWorldV3::FoliageCheck;
	using namespace EcoFoliageV3Test;
	Report(*this, TEXT("정의"), FC::CheckDefinitions());
	const FReport Chord = FC::CheckChord();
	Report(*this, TEXT("눈길 길이 (a → b = b → a)"), Chord);
	TestTrue(TEXT("눈길 길이: 가림·잎 구간 64 넘는 길이 모두 나온다"), Chord.Count0 > 0 && Chord.Count1 > 0);
	const FReport Obs = FC::CheckObs();
	Report(*this, TEXT("관측 threat_hidden"), Obs);
	TestTrue(TEXT("관측: 잎만 가린 사례가 있다"), Obs.Count0 > 0);
	const FReport Pairs = FC::CheckPairs();
	Report(*this, TEXT("쌍 장면 (늑대 표적·도망 쌍)"), Pairs);
	TestTrue(TEXT("쌍 장면: 잎만 가린 쌍·표적이 있다"), Pairs.Count0 > 0 && Pairs.Count1 > 0);
	const FReport Fl = FC::CheckFlightScenes();
	Report(*this, TEXT("도망 기록 장면 (lost_foliage)"), Fl);
	TestTrue(TEXT("도망 기록: 잎 놓침으로 끝난 도망이 있다"), Fl.Count0 > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoFoliageV3WorldTest,
	"AdaptiveEcosystem.Policy.V3.Foliage.World",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoFoliageV3WorldTest::RunTest(const FString& Parameters)
{
	namespace FC = EcoWorldV3::FoliageCheck;
	using namespace EcoFoliageV3Test;
	const FReport R = FC::CheckWorld(true);
	Report(*this, TEXT("기준 루프 숲 시야 켬 (450 스텝 지문·기록)"), R);
	TestTrue(TEXT("기준 루프: 잎 놓침이 있다"), R.Count0 > 0);
	AddInfo(FString::Printf(TEXT("잎 놓침 %lld · 잡힘 %lld · 시작 도망 %lld (켬·끔 첫 갈림 지문 %d)"), static_cast<long long>(R.Count0),
							static_cast<long long>(R.Count1), static_cast<long long>(R.Count2), EcoWorldV3::GoldenFoliage::kWorldFirstSplit));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoFoliageV3OffTest,
	"AdaptiveEcosystem.Policy.V3.Foliage.Off",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoFoliageV3OffTest::RunTest(const FString& Parameters)
{
	namespace FC = EcoWorldV3::FoliageCheck;
	using namespace EcoFoliageV3Test;
	const FReport Off = FC::CheckWorld(false);
	Report(*this, TEXT("숲 시야 끔 (450 스텝 = 파이썬 끔 판)"), Off);
	TestEqual(TEXT("끈 세계에는 잎 놓침이 없다"), Off.Count0, static_cast<int64>(0));
	Report(*this, TEXT("숲 시야 끔 + 끈 칸 엉뚱한 값 (읽지 않는다)"), FC::CheckWorld(false, true));
	TestFalse(TEXT("세계 설정 기본은 숲 시야 끔"), EcoWorldV3::FWorldConfig().Obstacles.Foliage.bEnabled);
	// 통합 모드 설정 (eco.IntegratedV3.Foliage·FoliageR·FoliageBlock — 개발 빌드, 기본 끔)
	const FEcoV3IntegratedSettings Def;
	TestFalse(TEXT("통합 기본: 숲 시야 끔"), Def.bFoliage);
	const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(Def.StageSizeUnits, 6.0);
	const EcoWorldV3::FWorldConfig C0 = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Def, 0, 128, Def.WolvesPerRegion, Covers);
	TestTrue(TEXT("통합 기본 세계: 숲 시야 끔 (줄기만 가림)"), !C0.Obstacles.Foliage.bEnabled && !C0.Obstacles.FoliageConfigured());
	FEcoV3IntegratedSettings On = Def;
	On.bFoliage = true;
	const EcoWorldV3::FWorldConfig C1 = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(On, 0, 128, On.WolvesPerRegion, Covers);
	TestTrue(TEXT("Foliage 1 → 세계 숲 시야 켬, 6 m·4 m = 파이썬 r 3.0·block 2.0 단위"),
			 C1.Obstacles.FoliageConfigured() && C1.Obstacles.Foliage.R == EcoWorldV3::GoldenFoliage::kDefaultR
				 && C1.Obstacles.Foliage.Block == EcoWorldV3::GoldenFoliage::kDefaultBlock);
	TestFalse(TEXT("원판이 없는 무대는 숲 시야를 재지 않는다"), C1.Obstacles.FoliageOn());
	FEcoV3IntegratedSettings NoOb = On;
	NoOb.bObstacles = false;
	TestFalse(TEXT("Obstacles 0 이면 숲 시야도 없다"),
			  UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(NoOb, 0, 128, NoOb.WolvesPerRegion, Covers).Obstacles.FoliageConfigured());
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
