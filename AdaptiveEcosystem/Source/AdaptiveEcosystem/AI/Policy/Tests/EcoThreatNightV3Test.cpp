// v3 위협 모델 밤잠 점진화 파리티 자동화 시험 — 엔진 **안에서** C++ 늑대 밤잠(EcoThreatModel.h, FThreatConfig::bRealismNight)을
// 파이썬 밤잠 세계(configs/v3_real1_night_on.yaml, world.py `_rz_night_update`·hunt_dark)와 대조한다 (사람 결정 H1 10-14).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.ThreatNight"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `ThreatNightGoldenVectorsV3.h` (herbivore_rl/export_golden_v3_threat.py --night — 보정 시드 20000~20002, 사슴은 R1b 출시
// 모델 argmax)이고, 검사 본문은 `ThreatNightGoldenCheckV3.h` 다. 같은 검사를 herbivore_rl/tests/test_threat_golden_v3.py 가 g++ 로도
// 돌린다(tests/cpp/threat_night_v3_main.cpp).
//
// 묶음:
//   ThreatNight.ConfigHashInit     FThreatConfig 밤잠 칸 = 파이썬 블록, 켜는 칸 기본 끔, 지연 해시 H(606, 시드, 슬롯), 세계 생성 때 처음 상태
//   ThreatNight.Updates            NightUpdate 한 번: 롤아웃 본·무대 끝(정확히 settle_r 8, 지연 경계, 마지막 활동도, 깸 지연)·생애 열의 업데이트
//   ThreatNight.Steps              밤잠 상태를 읽는 Step: 롤아웃 본·끝(깜깜할 때 새 사냥 막힘·쫓던 사냥 계속, 활동도·하한 속력)·열의 스텝
//   ThreatNight.Sequences          스텝 열(스텝 소유 칸을 이어 씀)과 생애 열(Step → NightUpdate 를 번갈아 C++ 자기 출력을 이어 씀)
//   ThreatNight.OffUnchanged       끄면(기본) Step 은 밤잠 칸을 읽지도 쓰지도 않는다. 끈 기준 루프는 밤잠 칸·기록을 건드리지 않는다
//   ThreatNight.ReferenceWorld     켠 기준 루프 1800 스텝(이틀): 사슴이 8 안이거나 사냥 중이면 잠들지 않는다, 깜깜하면 새 사냥 없음,
//                                  새벽에 늑대마다 지연만큼 늦게 깬다, 관측은 늑대별 잠을 읽는다, 같은 시드 = 같은 비트

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoWorldV3.h"
#include "ThreatNightGoldenCheckV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoThreatNightV3Test
{
	using EcoThreatV3::NightCheck::FReport;

	void Report(FAutomationTestBase& Test, const TCHAR* What, const FReport& R, bool bReportOnly = false)
	{
		Test.AddInfo(FString::Printf(TEXT("%s: 사례 %d, 보고만(어긋남) %d, 어긋남 %d, 실수 최대 오차 %.3e (비트 단위 같음 %d/%d)"), What,
									 R.Cases, R.Skipped, R.Failures, R.MaxError, R.FloatExact, R.FloatCount));
		if (bReportOnly)
		{
			return;
		}
		if (R.Failures > 0)
		{
			Test.AddError(FString::Printf(TEXT("%s: 처음 어긋난 사례 %d, 칸 %d (칸 번호는 ThreatNightGoldenCheckV3.h 머리 주석)"), What,
										  R.FirstCase, R.FirstField));
		}
		Test.TestTrue(FString::Printf(TEXT("%s 사례가 있다"), What), R.Cases > 0);
		Test.TestEqual(FString::Printf(TEXT("%s 은 파이썬과 같다"), What), R.Failures, 0);
	}

	/** 기준 루프 하나의 기록 (켠 판·끈 판). */
	struct FRunTally
	{
		int64 Onsets = 0;
		int64 Wakes = 0;
		int64 SettleStarts = 0;
		int64 OnsetNearDeer = 0;       // 잠든 순간 settle_r 안에 산 사슴이 있었다 (0 이어야 한다)
		int64 OnsetWhileHunting = 0;   // 잠든 업데이트의 늑대가 그 스텝에 사냥 중이었다 (0 이어야 한다)
		int64 DarkNewHuntViolations = 0; // 깜깜한데(d ≥ hunt_dark) 지난 스텝 사냥 중이 아니던 주행성이 사냥했다 (0)
		int64 DarkHuntBlocked = 0;     // 깜깜함 때문에 사냥하지 않은 깨어 있는 주행성 늑대·스텝 (> 0 이어야 규칙이 돈다)
		int64 ObsAsleepMismatch = 0;   // 관측 입력의 잠 ≠ 늑대별 잠 (0)
		int64 SleepMoved = 0;          // 잠든 늑대가 움직였다 (0)
		int64 WakeDelayMismatch = 0;   // 새벽 깸이 '밝아진 첫 업데이트 + 지연' 이 아니다 (0)
		int64 WakeChecked = 0;
		TSet<int64> FirstDawnWakeSteps; // 첫 새벽에 늑대들이 깬 스텝 (늑대마다 다르게 깬다)
		int64 MaskViolations = 0;
		uint64 Hash = 0xcbf29ce484222325ULL;
	};

	void MixHash(uint64& H, const void* Data, int32 Bytes)
	{
		const uint8* P = static_cast<const uint8*>(Data);
		for (int32 k = 0; k < Bytes; ++k)
		{
			H ^= P[k];
			H *= 0x100000001b3ULL;
		}
	}

	/** 평면 시험 맵 기본 세계 (잠행 3·추격 2·원거리 1, 야행성 1, 하루 900) 를 Steps 스텝 돈다. */
	FRunTally RunReference(bool bNight, int64 Seed, int32 Steps, EcoWorldV3::FReferenceWorld& Ref)
	{
		FRunTally T;
		EcoWorldV3::FWorldConfig C;
		C.Seed = Seed;
		C.Covers = EcoWorldV3::QuadCovers(C.WorldSize, 6.0);
		C.bRealismNight = bNight;
		Ref.Init(C);
		EcoWorldV3::FWorldState& W = Ref.World;
		const EcoThreatV3::FThreatConfig& Cfg = W.ThreatCfg;
		const int32 M = Ref.NumThreats();
		TArray<bool> PreHunt;
		TArray<bool> PreAsleep;
		TArray<int32> LightUpdates;   // 밝아진 뒤 업데이트 수 (자는 늑대만, 깨면 -1)
		LightUpdates.Init(-1, M);
		int32 DawnCount = 0;
		bool bPrevDark = W.Dark >= Cfg.SleepDark;
		for (int32 s = 0; s < Steps; ++s)
		{
			PreHunt.SetNum(M);
			PreAsleep.SetNum(M);
			for (int32 m = 0; m < M; ++m)
			{
				PreHunt[m] = Ref.Threats[m].State.bNightHunt;
				PreAsleep[m] = EcoWorldV3::ThreatAsleepNow(W, Ref.Threats[m]);
			}
			const double DarkBefore = W.Dark;
			Ref.StepOnce();
			const bool bDarkNow = W.Dark >= Cfg.SleepDark;
			if (bPrevDark && !bDarkNow)
			{
				++DawnCount;
			}
			for (int32 m = 0; m < M; ++m)
			{
				const EcoWorldV3::FThreatAgent& A = Ref.Threats[m];
				const bool bDiurnal = !A.Spec.bNocturnal;
				if (bNight && bDiurnal && DarkBefore >= Cfg.NightHuntDark)
				{
					T.DarkNewHuntViolations += (!PreHunt[m] && A.Last.bHunting) ? 1 : 0;
					T.DarkHuntBlocked += (!PreHunt[m] && !PreAsleep[m] && !A.Last.bHunting) ? 1 : 0;
				}
				if (PreAsleep[m])
				{
					T.SleepMoved += (A.State.VelX != 0.0 || A.State.VelY != 0.0) ? 1 : 0;
				}
				// 관측 입력의 잠: 켜면 늑대별 상태, 끄면 새 t 의 어둠으로 다시 판정 (지금 R1b 세계 그대로)
				const bool bObsWant = bNight ? A.State.bAsleep : EcoThreatV3::IsAsleep(A.Spec, W.Dark, Cfg);
				T.ObsAsleepMismatch += m < static_cast<int32>(W.ThreatIn.size()) && W.ThreatIn[static_cast<size_t>(m)].bAsleep != bObsWant ? 1 : 0;
				if (!bNight)
				{
					continue;
				}
				const EcoThreatV3::FNightUpdateResult& N = A.LastNight;
				T.Onsets += N.bOnset ? 1 : 0;
				T.Wakes += N.bWake ? 1 : 0;
				T.SettleStarts += N.bSettleStart ? 1 : 0;
				if (N.bOnset)
				{
					double MinD = 1e300;
					for (const EcoThreatV3::FPreyView& P : W.Prey)
					{
						MinD = FMath::Min(MinD, FMath::Sqrt(FMath::Square(P.X - A.State.PosX) + FMath::Square(P.Y - A.State.PosY)));
					}
					T.OnsetNearDeer += MinD <= Cfg.NightSettleR ? 1 : 0;
					T.OnsetWhileHunting += A.State.bNightHunt ? 1 : 0;
				}
				// 새벽 깸: 밝아진 업데이트를 세어 '밝아진 첫 업데이트 + 지연' 번째에 깨야 한다 (world.py: 기다림 = 지연)
				if (bDiurnal && PreAsleep[m] && !bDarkNow)
				{
					LightUpdates[m] = LightUpdates[m] < 0 ? 0 : LightUpdates[m] + 1;
					if (N.bWake)
					{
						++T.WakeChecked;
						T.WakeDelayMismatch += LightUpdates[m] != A.State.NightDelay ? 1 : 0;
						LightUpdates[m] = -1;
						if (DawnCount == 1)
						{
							T.FirstDawnWakeSteps.Add(W.T);
						}
					}
				}
				else if (bDarkNow)
				{
					LightUpdates[m] = -1;
				}
			}
			bPrevDark = bDarkNow;
			for (int32 m = 0; m < M; ++m)
			{
				const EcoThreatV3::FThreatState& S = Ref.Threats[m].State;
				MixHash(T.Hash, &S.PosX, sizeof(double));
				MixHash(T.Hash, &S.PosY, sizeof(double));
				const int32 Ints[6] = {S.bAsleep ? 1 : 0, S.NightAct, S.bNightSettle ? 1 : 0, S.NightDarkK, S.NightWait, S.Cooldown};
				MixHash(T.Hash, Ints, sizeof(Ints));
			}
			for (int32 i = 0; i < Ref.NumHerbivores(); ++i)
			{
				MixHash(T.Hash, &Ref.Bodies[i].Pos.X, sizeof(double));
				MixHash(T.Hash, &Ref.Bodies[i].Pos.Y, sizeof(double));
			}
		}
		T.MaskViolations = W.Stats.MaskViolations;
		return T;
	}
}


// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatNightV3ConfigHashInitTest,
	"AdaptiveEcosystem.Policy.V3.ThreatNight.ConfigHashInit",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatNightV3ConfigHashInitTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	EcoThreatNightV3Test::Report(*this, TEXT("설정"), NightCheck::CheckConfig());
	EcoThreatNightV3Test::Report(*this, TEXT("지연 해시"), NightCheck::CheckHash());
	EcoThreatNightV3Test::Report(*this, TEXT("처음 상태"), NightCheck::CheckInit());
	const FThreatConfig Cfg;
	TestFalse(TEXT("밤잠 점진화 기본은 끔 (R1b 학습 세계 그대로)"), Cfg.bRealismNight);
	TestEqual(TEXT("통합 모드 박명 45 스텝의 지연 최대 = ⌊0.5 × 45⌋"), NightMaxDelay(45, Cfg), 22);
	TestEqual(TEXT("낮 고정 세계는 지연 0"), NightMaxDelay(0, Cfg), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatNightV3UpdatesTest,
	"AdaptiveEcosystem.Policy.V3.ThreatNight.Updates",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatNightV3UpdatesTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	namespace G = EcoThreatV3::GoldenNight;
	EcoThreatNightV3Test::Report(*this, TEXT("업데이트 본"), NightCheck::CheckUpdates(G::kKindMain));
	EcoThreatNightV3Test::Report(*this, TEXT("업데이트 끝 사례"), NightCheck::CheckUpdates(G::kKindEdge));
	EcoThreatNightV3Test::Report(*this, TEXT("생애 열의 업데이트 (하나씩)"), NightCheck::CheckUpdates(G::kKindLife));
	if (G::kUpdNearBegin < G::kUpdCount)
	{
		EcoThreatNightV3Test::Report(*this, TEXT("업데이트 문턱 근처"), NightCheck::CheckUpdates(G::kKindNear), true);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatNightV3StepsTest,
	"AdaptiveEcosystem.Policy.V3.ThreatNight.Steps",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatNightV3StepsTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	namespace G = EcoThreatV3::GoldenNight;
	EcoThreatNightV3Test::Report(*this, TEXT("스텝 본"), NightCheck::CheckSteps(G::kKindMain));
	EcoThreatNightV3Test::Report(*this, TEXT("스텝 끝 사례"), NightCheck::CheckSteps(G::kKindEdge));
	EcoThreatNightV3Test::Report(*this, TEXT("롤아웃 열의 스텝 (하나씩)"), NightCheck::CheckSteps(G::kKindSeq));
	EcoThreatNightV3Test::Report(*this, TEXT("생애 열의 스텝 (하나씩)"), NightCheck::CheckSteps(G::kKindLife));
	EcoThreatNightV3Test::Report(*this, TEXT("스텝 문턱 근처"), NightCheck::CheckSteps(G::kKindNear), true);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatNightV3SequencesTest,
	"AdaptiveEcosystem.Policy.V3.ThreatNight.Sequences",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatNightV3SequencesTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	EcoThreatNightV3Test::Report(*this, TEXT("스텝 열 (스텝 소유 칸 이어 쓰기)"), NightCheck::CheckStepSequences());
	int32 Onsets = 0;
	int32 Wakes = 0;
	EcoThreatNightV3Test::Report(*this, TEXT("생애 열 (Step → NightUpdate 이어 쓰기)"), NightCheck::CheckLife(&Onsets, &Wakes));
	AddInfo(FString::Printf(TEXT("생애 열 안의 잠듦 %d, 깸 %d"), Onsets, Wakes));
	TestTrue(TEXT("생애 열에 해 질 녘 잠듦과 새벽 깸이 있다"), Onsets > 0 && Wakes > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatNightV3OffUnchangedTest,
	"AdaptiveEcosystem.Policy.V3.ThreatNight.OffUnchanged",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatNightV3OffUnchangedTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	EcoThreatNightV3Test::Report(*this, TEXT("끈 Step 은 밤잠 칸을 보지 않는다"), NightCheck::CheckOffIgnoresNightState());

	// 끈 기준 루프 (평면 시험 맵 기본값): 밤잠 칸은 기본값 그대로, 밤잠 기록 0
	EcoWorldV3::FReferenceWorld Ref;
	const EcoThreatNightV3Test::FRunTally T = EcoThreatNightV3Test::RunReference(false, 20000, 600, Ref);
	int32 Touched = 0;
	for (const EcoWorldV3::FThreatAgent& A : Ref.Threats)
	{
		const FThreatState& S = A.State;
		Touched += (S.NightAct != 0 || S.bNightSettle || S.NightDarkK != 0 || S.NightWait != -1 || S.NightDelay != 0 || S.bNightHunt) ? 1 : 0;
		Touched += A.LastNight.bOnset || A.LastNight.bWake || A.LastNight.bNearChecked ? 1 : 0;
	}
	const EcoWorldV3::FWorldStats& St = Ref.World.Stats;
	TestEqual(TEXT("끈 판은 밤잠 칸을 쓰지 않는다"), Touched, 0);
	TestTrue(TEXT("끈 판의 밤잠 기록은 0"), St.NightSettleStarts == 0 && St.NightOnsets == 0 && St.NightWakes == 0 && St.NightDarkUpdates == 0);
	TestEqual(TEXT("끈 판의 관측 잠 = 어둠의 순수 함수"), T.ObsAsleepMismatch, static_cast<int64>(0));
	TestFalse(TEXT("기준 루프 설정의 밤잠 기본은 끔"), EcoWorldV3::FWorldConfig().bRealismNight);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatNightV3ReferenceWorldTest,
	"AdaptiveEcosystem.Policy.V3.ThreatNight.ReferenceWorld",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatNightV3ReferenceWorldTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	constexpr int32 Steps = 1800;   // 하루 900 스텝 × 2 (해 질 녘 둘, 새벽 둘)
	EcoWorldV3::FReferenceWorld A;
	EcoWorldV3::FReferenceWorld B;
	EcoWorldV3::FReferenceWorld Off;
	const EcoThreatNightV3Test::FRunTally Ta = EcoThreatNightV3Test::RunReference(true, 20000, Steps, A);
	const EcoThreatNightV3Test::FRunTally Tb = EcoThreatNightV3Test::RunReference(true, 20000, Steps, B);
	const EcoThreatNightV3Test::FRunTally To = EcoThreatNightV3Test::RunReference(false, 20000, Steps, Off);
	const EcoWorldV3::FWorldStats& S = A.World.Stats;
	const double AwakeFrac = S.NightDarkUpdates > 0 ? static_cast<double>(S.NightDarkAwake) / static_cast<double>(S.NightDarkUpdates) : 0.0;
	AddInfo(FString::Printf(TEXT("켠 기준 루프 %d 스텝: 눕기 시작 %lld, 다시 일어남 %lld, 잠듦 %lld, 깸 %lld, 사슴 때문에 못 누움 %lld, ")
								TEXT("사냥 때문에 못 누움 %lld, 어둠 중 깨어 있음 %.1f%%, 깜깜해 사냥 안 함 %lld 늑대·스텝, 첫 새벽 깬 스텝 %d가지, 포획 %lld (끈 판 %lld)"),
							Steps, S.NightSettleStarts, S.NightSettleAborts, S.NightOnsets, S.NightWakes, S.NightBlockDeer,
							S.NightBlockHunt, 100.0 * AwakeFrac, Ta.DarkHuntBlocked, Ta.FirstDawnWakeSteps.Num(), S.Caught,
							Off.World.Stats.Caught));
	TestTrue(TEXT("늑대가 눕고 잠들고 깬다"), Ta.SettleStarts > 0 && Ta.Onsets > 0 && Ta.Wakes > 0);
	TestEqual(TEXT("잠드는 순간 settle_r(8 = 16 m) 안에 사슴이 없다"), Ta.OnsetNearDeer, static_cast<int64>(0));
	TestEqual(TEXT("사냥 중에는 잠들지 않는다"), Ta.OnsetWhileHunting, static_cast<int64>(0));
	TestEqual(TEXT("깜깜하면 새 사냥을 시작하지 않는다"), Ta.DarkNewHuntViolations, static_cast<int64>(0));
	TestTrue(TEXT("깜깜함 규칙이 실제로 사냥을 막는다"), Ta.DarkHuntBlocked > 0);
	TestTrue(TEXT("새벽 깸을 확인했다"), Ta.WakeChecked > 0);
	TestEqual(TEXT("새벽 깸 = 밝아진 첫 업데이트 + 늑대별 지연"), Ta.WakeDelayMismatch, static_cast<int64>(0));
	TestTrue(TEXT("첫 새벽에 늑대들이 서로 다른 스텝에 깬다"), Ta.FirstDawnWakeSteps.Num() >= 2);
	TestEqual(TEXT("관측 입력의 잠 = 늑대별 잠"), Ta.ObsAsleepMismatch, static_cast<int64>(0));
	TestEqual(TEXT("잠든 늑대는 움직이지 않는다"), Ta.SleepMoved + To.SleepMoved, static_cast<int64>(0));
	TestTrue(TEXT("어둠 중 깨어 있는 늑대가 있다 (옛 규칙은 d ≥ 0.5 에 곧바로 잤다)"), S.NightDarkAwake > 0);
	TestEqual(TEXT("마스크 위반"), Ta.MaskViolations, static_cast<int64>(0));
	TestTrue(TEXT("같은 시드 = 같은 비트 (결정적)"), Ta.Hash == Tb.Hash);
	TestTrue(TEXT("켠 판은 끈 판과 다르게 움직인다"), Ta.Hash != To.Hash);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
