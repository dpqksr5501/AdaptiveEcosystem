// v3 R1b 세계 개체 논리 파리티 자동화 시험 — 엔진 **안에서** 파이썬 세계(env_v2/repertoire.py·world.py)와 대조한다.
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Repertoire"
//                        -unattended -nopause -nosplash -NullRHI
//                        -testexit="Automation Test Queue Empty"
//   (관측 쪽은 AdaptiveEcosystem.Policy.V3.Observation)
//
// 골든은 `RepertoireGoldenVectorsV3.h` 에 배열로 박혀 있다 (herbivore_rl/export_golden_v3_world.py 가 R1b 세계
// configs/v3_r1_on.yaml 의 보정 시드 20000~20002 롤아웃과 경계 열에서 생성). 파일 I/O·레벨·월드가 없는 순수 수치 시험이다.
// 검사 본문은 `RepertoireGoldenCheckV3.h` 이고, 같은 검사를 herbivore_rl/tests/test_repertoire_golden_v3.py 가 g++ 로도 돌린다.
//
// 묶음:
//   Repertoire.Contract          번호·관측 배치·경보 꺼짐·단위 환산 (컴파일 시점 확인 포함)
//   Repertoire.Constants         세계 상수 표 = C++ FRepertoireConfig·FObservationConfig
//   Repertoire.JitterHash        H(505, 시드, 개체 키)·지연, 파리티 키(슬롯·세대)·통합 모드 키(StableAgentId)
//   Repertoire.ArbiterSequences  Arbitrate 한 번으로 롤아웃 창·경계 열 (결정 뒤 상태 19칸·결정·전환·사건·지연)
//   Repertoire.PrepareCommit     Prepare → Commit 이 Arbitrate 와 같고 Prepare 의 reads 가 파이썬 rep_peek 과 같다
//   Repertoire.ClosedLoop        Prepare → 마스크 → 망(EcoPolicyV3) → Commit 이 파이썬 R1b 롤아웃 요청·상태를 그대로 낸다
//   Repertoire.InitRespawn       처음 나는 개체·리스폰 상태
//   Repertoire.Control           행동별 제어기 (속도·보행·섭식·대사·탐지·정지·웅크림·heading 덮기·은신 배수)
//   Repertoire.MoveEnergy        이동(벽 자르기·heading)·섭식·대사·번식
//   Repertoire.Perceive          threat_recency·away 갱신
//   Observation.Build            관측 18 만들기 (float, 세계가 낸 관측)
//   Observation.Perception       스텝 끝 기하 (위협·동족·은신처 지각, 사건 비교 시야)
//   Observation.DayNight         어둠 d·전환까지 스텝
//   Observation.PredationEma     전역 피식 EMA

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "RepertoireGoldenCheckV3.h"

// 계약 확인 (컴파일 시점): 행동 번호·관측 배치는 정책 추론 헤더와 같고, R1b 세계에는 경보 사건이 없다
static_assert(EcoRepertoireV3::kGraze == EcoPolicyV3::kGraze && EcoRepertoireV3::kFlee == EcoPolicyV3::kFlee
				  && EcoRepertoireV3::kHide == EcoPolicyV3::kHide && EcoRepertoireV3::kFreeze == EcoPolicyV3::kFreeze
				  && EcoRepertoireV3::kSleep == EcoPolicyV3::kSleep,
			  "행동 번호가 EcoPolicyV3 와 다르다");
static_assert(EcoRepertoireV3::kNumBehaviors == EcoPolicyV3::kNumBehaviors, "행동 수가 다르다");
static_assert(EcoObservationV3::kObsDim == EcoPolicyV3::kObsDim, "관측 칸 수가 정책 모델과 다르다 (R1b 는 18)");
static_assert(EcoObservationV3::kObsPredCount == EcoPolicyV3::kObsPredCount
				  && EcoObservationV3::kObsCoverDist == EcoPolicyV3::kObsCoverDist
				  && EcoObservationV3::kObsThreatRecency == EcoPolicyV3::kObsThreatRecency,
			  "마스크가 읽는 관측 칸 번호가 다르다");
static_assert(EcoPolicyV3::kMaskVersion == 2 && EcoPolicyV3::kObsAlarmHeard < 0, "R1b 두뇌는 마스크 판 2, 경보 칸 없음");
static_assert(!EcoRepertoireV3::kR1bConfig.bKinAlarmEvent, "R1b 세계에는 E7(동족 경보)이 없다 (사람 결정 10-13 (3))");
static_assert(EcoRepertoireV3::Golden::kStateFieldCount == 19, "골든 상태 칸 수");
static_assert(EcoRepertoireV3::EntryLock(EcoRepertoireV3::kHide, EcoRepertoireV3::kR1bConfig) == 40, "HIDE 진입 잠금");

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoRepertoireV3Test
{
	using EcoRepertoireV3::Check::FReport;

	/** 검사 결과를 시험에 적는다. 어긋나면 처음 어긋난 사례·칸을 오류로 적는다. */
	void Report(FAutomationTestBase& Test, const TCHAR* What, const FReport& R, const FString& Detail = FString())
	{
		Test.AddInfo(FString::Printf(TEXT("%s: 사례 %d, 뺀 것 %d, 어긋남 %d, 실수 최대 오차 %.3e (비트 단위 같음 %d/%d)"), What,
									 R.Cases, R.Skipped, R.Failures, R.MaxError, R.FloatExact, R.FloatCount));
		if (R.Failures > 0)
		{
			Test.AddError(FString::Printf(TEXT("%s: 처음 어긋난 사례 %d, 칸 %d %s"), What, R.FirstCase, R.FirstField, *Detail));
		}
		Test.TestTrue(FString::Printf(TEXT("%s 사례가 있다"), What), R.Cases > 0);
		Test.TestEqual(FString::Printf(TEXT("%s 은 파이썬과 같다"), What), R.Failures, 0);
	}

	/** Arbiter 스텝 번호 -> "열 이름 스텝 k, 칸 이름". */
	FString SequenceDetail(const FReport& R)
	{
		using namespace EcoRepertoireV3::Golden;
		if (R.FirstCase < 0)
		{
			return FString();
		}
		for (int32 s = 0; s < kSeqCount; ++s)
		{
			if (R.FirstCase >= kSeqStart[s] && R.FirstCase < kSeqStart[s] + kSeqLength[s])
			{
				const TCHAR* const Extra[] = {TEXT("decide"), TEXT("switch"), TEXT("event"), TEXT("fire"), TEXT("e7"),
											  TEXT("사건 비트"), TEXT("reads"), TEXT("기상 결정"), TEXT("망 요청")};
				const FString Field = R.FirstField < kStateFieldCount
										  ? FString(UTF8_TO_TCHAR(kStateFieldNames[R.FirstField]))
										  : FString(Extra[FMath::Clamp(R.FirstField - kStateFieldCount, 0, 8)]);
				return FString::Printf(TEXT("(열 %s, 시드 %d 시작 %d 개체 %d, 스텝 %d, 칸 %s)"), UTF8_TO_TCHAR(kSeqName[s]),
									   kSeqSource[s * 3], kSeqSource[s * 3 + 1], kSeqSource[s * 3 + 2],
									   R.FirstCase - kSeqStart[s], *Field);
			}
		}
		return FString();
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3ContractTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.Contract",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3ContractTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;

	// 관측 이름 순서 = 정책 모델 관측 이름 (PolicyWeightsV3.h)
	for (int32 i = 0; i < EcoObservationV3::kObsDim; ++i)
	{
		TestTrue(FString::Printf(TEXT("관측 %d 이름 %s"), i, UTF8_TO_TCHAR(EcoObservationV3::kObsNames[i])),
				 EcoPolicyV3::Detail::StrEq(EcoObservationV3::kObsNames[i], EcoPolicyV3::kObsNames[i]));
	}
	for (int32 b = 0; b < kNumBehaviors; ++b)
	{
		TestTrue(FString::Printf(TEXT("행동 %d 이름"), b),
				 EcoPolicyV3::Detail::StrEq(Golden::kBehaviorNames[b], EcoPolicyV3::kBehaviorNames[b]));
	}

	// 단위 환산 (계약 12-1): 0.6단위/스텝 = 900 cm/s, 걷기 0.24 = 360 cm/s, 1단위 = 200 cm, 잠금 12스텝 = 1.6 s
	const FRepertoireConfig& C = kR1bConfig;
	TestTrue(TEXT("뛰기 900 cm/s"), FMath::IsNearlyEqual(UnitsPerStepToCmPerSec(C.HerbSpeed * C.GaitSpeed[kGaitRun]), 900.0, 1e-9));
	TestTrue(TEXT("걷기 360 cm/s"), FMath::IsNearlyEqual(UnitsPerStepToCmPerSec(C.HerbSpeed * C.GaitSpeed[kGaitWalk]), 360.0, 1e-9));
	TestTrue(TEXT("cm/s 왕복"), FMath::IsNearlyEqual(CmPerSecToUnitsPerStep(900.0), 0.6, 1e-12));
	TestTrue(TEXT("시야 4000 cm"), FMath::IsNearlyEqual(UnitsToCm(EcoObservationV3::kR1bObsConfig.SeeR), 4000.0, 1e-9));
	TestTrue(TEXT("event_near 1600 cm"), FMath::IsNearlyEqual(UnitsToCm(C.EventNear), 1600.0, 1e-9));
	TestTrue(TEXT("cm 왕복"), FMath::IsNearlyEqual(CmToUnits(1600.0), 8.0, 1e-12));
	TestTrue(TEXT("GRAZE 잠금 1.6 s"), FMath::IsNearlyEqual(StepsToSeconds(C.LockGraze), 1.6, 1e-12));
	TestTrue(TEXT("초 왕복"), FMath::IsNearlyEqual(SecondsToSteps(0.4), 3.0, 1e-9));

	// 통합 모드 개체 키: StableAgentId 를 그대로 쓴다. 새 개체 = 새 키 = 새 지연
	TestTrue(TEXT("StableAgentId 키"), MakeAgentKeyFromStableId(123456789012LL) == 123456789012ULL);
	TestTrue(TEXT("파리티 키 (슬롯 5, 세대 3)"), MakeAgentKey(5u, 3u) == (5ULL << 32) + 3ULL);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3ConstantsTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.Constants",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3ConstantsTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	const Check::FReport R = Check::CheckConstants();
	FString Detail;
	if (R.FirstCase >= 0 && R.FirstCase < Golden::kWorldConstantCount)
	{
		Detail = FString::Printf(TEXT("(%s = %.17g)"), UTF8_TO_TCHAR(Golden::kWorldConstantNames[R.FirstCase]),
								 Golden::kWorldConstantValues[R.FirstCase]);
	}
	EcoRepertoireV3Test::Report(*this, TEXT("세계 상수"), R, Detail);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3JitterHashTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.JitterHash",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3JitterHashTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	EcoRepertoireV3Test::Report(*this, TEXT("지연 해시"), Check::CheckJitterHash());
	// 컴파일 시점에도 같은 값 (constexpr)
	static_assert(DecisionJitter(20000, MakeAgentKey(0u, 0u), 3) == static_cast<std::int32_t>(JitterHash(20000, 0) % 4),
				  "constexpr 지연");
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3ArbiterSequencesTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.ArbiterSequences",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3ArbiterSequencesTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	const Check::FReport R = Check::CheckSequences(Check::ESequenceMode::Arbitrate);
	EcoRepertoireV3Test::Report(*this, TEXT("Arbiter 열 (Arbitrate)"), R, EcoRepertoireV3Test::SequenceDetail(R));
	AddInfo(FString::Printf(TEXT("열 %d (롤아웃 창과 경계 열), 스텝 %d"), Golden::kSeqCount, Golden::kStepCount));
	TestEqual(TEXT("모든 스텝을 돌았다"), R.Cases, Golden::kStepCount);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3PrepareCommitTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.PrepareCommit",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3PrepareCommitTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	const Check::FReport R = Check::CheckSequences(Check::ESequenceMode::PrepareCommit);
	EcoRepertoireV3Test::Report(*this, TEXT("Arbiter 열 (Prepare → Commit)"), R, EcoRepertoireV3Test::SequenceDetail(R));
	TestEqual(TEXT("모든 스텝을 돌았다"), R.Cases, Golden::kStepCount);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3ClosedLoopTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.ClosedLoop",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3ClosedLoopTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	const Check::FReport R = Check::CheckSequences(Check::ESequenceMode::ClosedLoop);
	EcoRepertoireV3Test::Report(*this, TEXT("닫힌 고리 (Prepare → 마스크 → 망 → Commit)"), R,
								EcoRepertoireV3Test::SequenceDetail(R));
	TestEqual(TEXT("관측을 실은 창의 스텝을 모두 돌았다"), R.Cases, Golden::kLoopRowCount);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3InitRespawnTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.InitRespawn",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3InitRespawnTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	EcoRepertoireV3Test::Report(*this, TEXT("처음 나는 개체 (InitAgent)"), Check::CheckInitAgent());
	EcoRepertoireV3Test::Report(*this, TEXT("리스폰 (RespawnAgent)"), Check::CheckRespawn());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3ControlTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.Control",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3ControlTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	EcoRepertoireV3Test::Report(*this, TEXT("제어기"), Check::CheckControl(),
								TEXT("(0·1 속도, 2 보행, 3 섭식, 4 대사, 5 탐지, 6 은신, 7 정지, 8 웅크림, 9 heading 덮기, 10·11 face, 12 먹이 판정)"));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3MoveEnergyTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.MoveEnergy",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3MoveEnergyTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	EcoRepertoireV3Test::Report(*this, TEXT("이동"), Check::CheckMove(), TEXT("(0·1 위치, 2·3 heading)"));
	EcoRepertoireV3Test::Report(*this, TEXT("섭식·대사·번식"), Check::CheckEnergy(),
								TEXT("(0 E′, 1 섭식 배수, 2 수요, 3 먹은 양, 4 E_new, 5 번식 뒤 E, 6 쿨다운, 7 번식)"));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoRepertoireV3PerceiveTest,
	"AdaptiveEcosystem.Policy.V3.Repertoire.Perceive",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRepertoireV3PerceiveTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	EcoRepertoireV3Test::Report(*this, TEXT("Perceive"), Check::CheckPerceive(), TEXT("(0 recency, 1·2 away)"));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObservationV3BuildTest,
	"AdaptiveEcosystem.Policy.V3.Observation.Build",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoObservationV3BuildTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	const Check::FReport R = Check::CheckObservationBuild();
	FString Detail;
	if (R.FirstField >= 0 && R.FirstField < EcoObservationV3::kObsDim)
	{
		Detail = FString::Printf(TEXT("(%s)"), UTF8_TO_TCHAR(EcoObservationV3::kObsNames[R.FirstField]));
	}
	EcoRepertoireV3Test::Report(*this, TEXT("관측 18 만들기"), R, Detail);
	TestEqual(TEXT("관측 칸은 같은 double 입력이면 비트 단위로 같다"), R.FloatExact, R.FloatCount);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObservationV3PerceptionTest,
	"AdaptiveEcosystem.Policy.V3.Observation.Perception",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoObservationV3PerceptionTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	EcoRepertoireV3Test::Report(
		*this, TEXT("지각 스냅샷"), Check::CheckPerception(),
		TEXT("(0 위협 수, 1 사건 비교 수, 2 동족 수, 3 은신처, 4 은신처 안, 5 거리, 6·7 위협 반대, 8 접근, 9 사건 거리, 10 사건 접근, "
			 "11·12 무리, 13·14 분리, 15 동족 경보, 16 은신 거리, 17 가장자리, 18 탐지 반경)"));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObservationV3DayNightTest,
	"AdaptiveEcosystem.Policy.V3.Observation.DayNight",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoObservationV3DayNightTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	EcoRepertoireV3Test::Report(*this, TEXT("낮밤"), Check::CheckDayNight(), TEXT("(0 어둠, 1 남은 스텝)"));
	// 전환 스텝은 정확히 0.5 (E5·밤잠 문턱이 참, 계약 11-2)
	TestEqual(TEXT("낮 첫 스텝 d = 0.5"), EcoObservationV3::DayNightPhase(0, 900, 0, 45).Dark, 0.5);
	TestEqual(TEXT("밤 첫 스텝 d = 0.5"), EcoObservationV3::DayNightPhase(450, 900, 0, 45).Dark, 0.5);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObservationV3PredationEmaTest,
	"AdaptiveEcosystem.Policy.V3.Observation.PredationEma",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoObservationV3PredationEmaTest::RunTest(const FString& Parameters)
{
	using namespace EcoRepertoireV3;
	EcoRepertoireV3Test::Report(*this, TEXT("피식 EMA"), Check::CheckPredationEma());
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
