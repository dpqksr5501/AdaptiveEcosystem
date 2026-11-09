// v3 10-27 고침 자동화 시험 — 먹기 걷기 고침(EcoRepertoire.h GrazeCalmDir·Control — 경계 걷기 FlightAlertControl 에는 없음)·거리 두기(쉬는 늑대 —
// EcoWorldV3.h UpdateWildFlight 의 kKeepRest·방향 관성 kRestKeepInertia, FlightRestControl·FlightRestBand)를 파이썬(env_v2/repertoire.py `graze_calm_dir`, env_v2/world.py 모듈 docstring
// '거리 두기')과 대조한다 (사용자 10-27 '평소 사슴이 제자리에서 빙빙 돈다'·'쉬는 늑대 곁에서 멈춰 있다').
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Calm"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `CalmGoldenVectorsV3.h` (herbivore_rl/export_golden_v3_calm.py, 세계 configs/v3_wild3_calm_mirror.yaml)이고, 검사 본문은 `CalmGoldenCheckV3.h` 다.
// 같은 검사를 g++ 하네스(herbivore_rl/tests/cpp/calm_v3_main.cpp)도 부른다.
//
// 묶음:
//   Calm.Golden  정의(C++ 기본 끔·InitWorld 가 옮김·거부), 방향 사례(GrazeCalmDir), 제어 사례(Control GRAZE), 덮기 장면(UpdateWildFlight — 손 장면 + 난수),
//                B 장면(FlightRestControl → FlightRestBand)
//   Calm.World   거울 세계 사슴 48 두 고침 켬 600 스텝 × 지역 둘(숲·메마른 땅) — 파이썬과 스텝마다 상태 지문·100 스텝마다 기록이 비트 단위로 같다
//   Calm.Off     같은 시작의 두 고침 끔 600 스텝 = 파이썬 끔 판(끔 = 10-26 그대로), 끈 거리 두기 칸에 엉뚱한 값을 넣어도 같다. 통합 모드 설정
//                (eco.IntegratedV3.GrazeCalm·RestKeep 기본 1 → 골든 설정 값, 0 → 끔, 도주 반사를 끄면 거리 두기도 없다)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "CalmGoldenCheckV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoCalmV3Test
{
	using EcoWorldV3::CalmCheck::FReport;

	void Report(FAutomationTestBase& Test, const TCHAR* What, const FReport& R)
	{
		Test.AddInfo(FString::Printf(TEXT("%s: 사례 %d, 어긋남 %d (처음 사례 %d 칸 %d), 셈 %lld·%lld·%lld"), What, R.Cases, R.Failures, R.FirstCase, R.FirstField,
									 static_cast<long long>(R.Count0), static_cast<long long>(R.Count1), static_cast<long long>(R.Count2)));
		Test.TestTrue(*FString::Printf(TEXT("%s: 파이썬과 비트 단위로 같다"), What), R.Passed());
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoCalmV3GoldenTest,
	"AdaptiveEcosystem.Policy.V3.Calm.Golden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoCalmV3GoldenTest::RunTest(const FString& Parameters)
{
	namespace CC = EcoWorldV3::CalmCheck;
	using namespace EcoCalmV3Test;
	Report(*this, TEXT("정의"), CC::CheckDefinitions());
	const FReport Dir = CC::CheckDirections();
	Report(*this, TEXT("먹기 걷기 방향 (GrazeCalmDir)"), Dir);
	TestTrue(TEXT("방향: 바꾼 사례·원래 방향으로 돌아간 사례가 모두 있다"), Dir.Count0 > 0 && Dir.Count1 > 0);
	Report(*this, TEXT("제어 (Control GRAZE)"), CC::CheckControl());
	const FReport Sc = CC::CheckScenes();
	Report(*this, TEXT("덮기 장면 (UpdateWildFlight)"), Sc);
	TestTrue(TEXT("덮기 장면: 거리 두기·경계·도주가 모두 나온다"), Sc.Count0 > 0 && Sc.Count1 > 0 && Sc.Count2 > 0);
	const FReport B = CC::CheckBScenes();
	Report(*this, TEXT("B 장면 (FlightRestControl → FlightRestBand)"), B);
	TestTrue(TEXT("B 장면: 띠가 바꾼·거리 두기 제어·멈춤이 모두 나온다"), B.Count0 > 0 && B.Count1 > 0 && B.Count2 > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoCalmV3WorldTest,
	"AdaptiveEcosystem.Policy.V3.Calm.World",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoCalmV3WorldTest::RunTest(const FString& Parameters)
{
	namespace CC = EcoWorldV3::CalmCheck;
	namespace G = EcoWorldV3::GoldenCalm;
	using namespace EcoCalmV3Test;
	for (int32 Li = 0; Li < G::kLoops; ++Li)
	{
		const FReport R = CC::CheckLoop(Li, true);
		Report(*this, *FString::Printf(TEXT("기준 루프 %s 두 고침 켬 (600 스텝 지문·기록)"), UTF8_TO_TCHAR(G::kLoopTable[Li].Region)), R);
		TestTrue(TEXT("기준 루프: 거리 두기·띠·잡힘이 있다"), R.Count0 > 0 && R.Count1 > 0 && R.Count2 > 0);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoCalmV3OffTest,
	"AdaptiveEcosystem.Policy.V3.Calm.Off",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoCalmV3OffTest::RunTest(const FString& Parameters)
{
	namespace CC = EcoWorldV3::CalmCheck;
	namespace G = EcoWorldV3::GoldenCalm;
	using namespace EcoCalmV3Test;
	for (int32 Li = 0; Li < G::kLoops; ++Li)
	{
		const FReport LoopOff = CC::CheckLoop(Li, false);
		Report(*this, *FString::Printf(TEXT("기준 루프 %s 두 고침 끔 (= 파이썬 끔 판)"), UTF8_TO_TCHAR(G::kLoopTable[Li].Region)), LoopOff);
		TestEqual(TEXT("끈 세계에는 거리 두기가 없다"), LoopOff.Count0, static_cast<int64>(0));
		Report(*this, TEXT("두 고침 끔 + 끈 거리 두기 칸 엉뚱한 값 (읽지 않는다)"), CC::CheckLoop(Li, false, true));
	}
	TestFalse(TEXT("세계 설정 기본은 두 고침 끔"), EcoWorldV3::FWorldConfig().WildFlight.bRestKeep || EcoRepertoireV3::GrazeCalmOn(EcoRepertoireV3::kR1bConfig));
	// 통합 모드 설정 (eco.IntegratedV3.GrazeCalm·RestKeep — 기본 1 = configs/v3_wild3_calm_mirror.yaml)
	const FEcoV3IntegratedSettings Def;
	TestTrue(TEXT("통합 기본: 두 고침 켬"), Def.bGrazeCalm && Def.bRestKeep && Def.bWildFlight);
	const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(Def.StageSizeUnits, 6.0);
	const EcoWorldV3::FWorldConfig C0 = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Def, 0, 128, Def.WolvesPerRegion, Covers);
	TestTrue(TEXT("통합 기본 세계: 먹기 걷기 고침 = 골든 설정 값"),
			 C0.GrazeCalm.EdgeR == G::kGrazeEdgeR && C0.GrazeCalm.EdgeW == G::kGrazeEdgeW && C0.GrazeCalm.Inertia == G::kGrazeInertia
				 && C0.GrazeCalm.WallMargin == G::kGrazeWallMargin);
	TestTrue(TEXT("통합 기본 세계: 거리 두기 = 골든 설정 값"),
			 C0.WildFlight.bRestKeep == G::kRestKeep && C0.WildFlight.RestKeepMargin == G::kRestKeepMargin && C0.WildFlight.RestKeepBand == G::kRestKeepBand
				 && C0.WildFlight.bRestKeepAsleep == G::kRestKeepAsleep);
	FEcoV3IntegratedSettings Both0 = Def;
	Both0.bGrazeCalm = false;
	Both0.bRestKeep = false;
	const EcoWorldV3::FWorldConfig C1 = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Both0, 0, 128, Both0.WolvesPerRegion, Covers);
	TestTrue(TEXT("GrazeCalm·RestKeep 0 → 세계 끔 (10-26 그대로)"),
			 C1.GrazeCalm.EdgeR == 0.0 && C1.GrazeCalm.EdgeW == 0.0 && C1.GrazeCalm.Inertia == 0.0 && C1.GrazeCalm.WallMargin == 0.0
				 && !C1.WildFlight.bRestKeep && C1.WildFlight.RestKeepBand == 0.0);
	FEcoV3IntegratedSettings NoFlight = Def;
	NoFlight.bWildFlight = false;
	TestFalse(TEXT("WildFlight 0 이면 거리 두기도 없다"),
			  UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(NoFlight, 0, 128, NoFlight.WolvesPerRegion, Covers).WildFlight.bRestKeep);
	TestEqual(TEXT("덮기 이름: 거리 두기"), FString(EcoV3Integrated::KeepModeNameKo(EcoWorldV3::kKeepRest)), FString(TEXT("거리 두기(쉬는 늑대)")));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
