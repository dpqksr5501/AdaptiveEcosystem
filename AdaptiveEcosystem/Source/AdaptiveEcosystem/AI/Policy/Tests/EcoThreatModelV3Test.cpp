// v3 위협 모델 파리티 자동화 시험 — 엔진 **안에서** C++ 위협 스텝(EcoThreatV3::Step)을 파이썬 학습 세계(world.py)와 대조한다.
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Threat"
//                        -unattended -nopause -nosplash -NullRHI
//                        -testexit="Automation Test Queue Empty"
//
// 골든은 `ThreatGoldenVectorsV3.h` 에 배열로 박혀 있다 (herbivore_rl/export_golden_v3_threat.py 생성 — 보정 시드 20000~20002,
// 사슴은 R1b 출시 모델 argmax). 파일 I/O·레벨·월드가 없는 순수 수치 시험이다. 같은 골든을 herbivore_rl/tests/test_threat_golden_v3.py
// 가 g++ 로도 돌린다(tests/cpp/threat_v3_main.cpp).
//
// 묶음 (자세한 정의는 생성 헤더 머리 주석):
//   Config          FThreatConfig 기본값 = 파이썬 학습 세계 설정 (정확히)
//   SpecAndDayNight 세계 생성 식(MakeChaserSpec 등)과 어둠 d(t) (DayNightDark) — 사례마다 정확히
//   GoldenStep      롤아웃 한 스텝 사례와 열의 각 스텝 — 실수 |C++ - Python| <= kFloatTolerance, 정수·판정 정확
//   EdgeCases       무대 끝 사례 (문턱과 정확히 같은 거리, 동점, 행동별 은신 배수, 상태 기계 끝, 낮밤, 벽, 플레이어 모드, 거리 0)
//   Sequences       열: 첫 스텝만 골든 상태, 그 뒤는 C++ 자기 출력 상태를 이어 쓴다 (쿨다운 5 = 4스텝 쉼 등)
//   NearThreshold   문턱 근처 롤아웃 사례 — 보고만 한다
//   AliveFilter     죽은 초식은 표적·포획 후보가 아니다 (앞에 끼워도 결과가 같다, 모두 죽으면 초식 없음과 같다)
//   ResolveCatches  여러 위협이 같은 초식을 잡으면 가장 낮은 위협 색인

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoThreatModel.h"
#include "../ThreatGoldenVectorsV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoThreatV3Test
{
	using namespace EcoThreatV3;
	using namespace EcoThreatV3::Golden;

	constexpr int32 kMaxReport = 5;   // 어긋난 사례를 몇 개까지 오류로 찍나

	struct FCase
	{
		FThreatSpec Spec;
		FThreatState State;
		TArray<FPreyView> Prey;
		TArray<double> Roll;
		FThreatStepInput In;
	};

	FThreatSpec SpecOf(int32 n)
	{
		FThreatSpec S;
		S.Type = static_cast<EThreatType>(kSpecType[n]);
		S.bRanged = kSpecRanged[n] != 0;
		S.bNocturnal = kSpecNocturnal[n] != 0;
		S.BaseSpeed = kSpecBaseSpeed[n];
		S.CatchRadius = kSpecCatchR[n];
		return S;
	}

	FThreatState PreStateOf(int32 n)
	{
		FThreatState T;
		T.PosX = kPrePos[n * 2];
		T.PosY = kPrePos[n * 2 + 1];
		T.HeadX = kPreHead[n * 2];
		T.HeadY = kPreHead[n * 2 + 1];
		T.Cooldown = kPreInt[n * 5];
		T.StalkState = static_cast<EStalkState>(kPreInt[n * 5 + 1]);
		T.StalkLeft = kPreInt[n * 5 + 2];
		T.PlayerMode = static_cast<EPlayerMode>(kPreInt[n * 5 + 3]);
		T.PlayerLeft = kPreInt[n * 5 + 4];
		return T;
	}

	// 입력 포인터(In.Prey·In.RangedRoll)를 배열에 다시 건다 (배열을 고친 뒤 부른다)
	void Bind(FCase& C)
	{
		C.In.Prey = C.Prey.Num() > 0 ? C.Prey.GetData() : nullptr;
		C.In.NumPrey = C.Prey.Num();
		C.In.RangedRoll = C.Spec.bRanged ? C.Roll.GetData() : nullptr;
	}

	void Build(int32 n, FCase& C)
	{
		C.Spec = SpecOf(n);
		C.State = PreStateOf(n);
		C.Prey.Reset();
		C.Roll.Reset();
		for (int32 k = 0; k < kPreyCount[n]; ++k)
		{
			const int32 p = kPreyBegin[n] + k;
			FPreyView P;
			P.X = kPreyPos[p * 2];
			P.Y = kPreyPos[p * 2 + 1];
			P.Behavior = kPreyBehavior[p];
			P.bHideArrived = kPreyHideArrived[p] != 0;
			P.bInCover = kPreyInCover[p] != 0;
			P.bAlive = true;
			C.Prey.Add(P);
			C.Roll.Add(kPreyRoll[p]);
		}
		C.In = FThreatStepInput();
		C.In.Dark = kDark[n];
		C.In.WorldSize = kWorldSize[n];
		C.In.WanderTurn = kTurn[n];
		C.In.PlayerModeU0 = kModeU[n * 2];
		C.In.PlayerModeU1 = kModeU[n * 2 + 1];
		Bind(C);
	}

	double Track(double& MaxError, double A, double B)
	{
		const double E = FMath::Abs(A - B);
		MaxError = FMath::Max(MaxError, E);
		return E;
	}

	// 사례 n 의 기대와 비교. Shift = 결과 색인에 더할 값 (죽은 초식을 앞에 끼운 시험). 어긋나면 첫 이유를 Why 에 적고 false
	bool Compare(int32 n, const FThreatState& T, const FThreatStepResult& R, double& MaxError, int32 Shift, FString& Why)
	{
		const double Tol = kFloatTolerance;
		Why.Reset();
		auto Note = [&Why](const TCHAR* What) {
			if (Why.IsEmpty())
			{
				Why = What;
			}
		};
		if (Track(MaxError, T.PosX, kPostPos[n * 2]) > Tol || Track(MaxError, T.PosY, kPostPos[n * 2 + 1]) > Tol)
		{
			Note(TEXT("위치"));
		}
		if (Track(MaxError, T.HeadX, kPostHead[n * 2]) > Tol || Track(MaxError, T.HeadY, kPostHead[n * 2 + 1]) > Tol)
		{
			Note(TEXT("heading"));
		}
		if (Track(MaxError, T.VelX, kPostVel[n * 2]) > Tol || Track(MaxError, T.VelY, kPostVel[n * 2 + 1]) > Tol)
		{
			Note(TEXT("변위"));
		}
		if (Track(MaxError, R.Speed, kOutSpeed[n]) > Tol)
		{
			Note(TEXT("속력"));
		}
		if (Track(MaxError, R.TargetPerceived, kOutTargetPerceived[n]) > Tol)
		{
			Note(TEXT("표적 체감 거리"));
		}
		const int32 Ints[5] = {T.Cooldown, static_cast<int32>(T.StalkState), T.StalkLeft, static_cast<int32>(T.PlayerMode),
							   T.PlayerLeft};
		static const TCHAR* IntNames[5] = {TEXT("쿨다운"), TEXT("잠행 상태"), TEXT("잠행 남은"), TEXT("플레이어 모드"),
										   TEXT("플레이어 남은")};
		for (int32 k = 0; k < 5; ++k)
		{
			if (Ints[k] != kPostInt[n * 5 + k])
			{
				Note(IntNames[k]);
			}
		}
		const uint8 Bits = static_cast<uint8>((R.bAsleep ? kOutAsleep : 0) | (R.bHunting ? kOutHunting : 0) |
											  (R.bHasTarget ? kOutHasTarget : 0) | (R.bWallHit ? kOutWall : 0) |
											  (R.bPounceStart ? kOutPounceStart : 0) | (R.bChargeStart ? kOutChargeStart : 0) |
											  (R.bNewPlayerMode ? kOutNewMode : 0));
		if (Bits != kOutBits[n])
		{
			Note(TEXT("결과 비트(잠·사냥·표적·벽·돌진 시작·새 모드)"));
		}
		const int32 WantTarget = kOutTarget[n] >= 0 ? kOutTarget[n] + Shift : -1;
		const int32 WantCaught = kOutCaught[n] >= 0 ? kOutCaught[n] + Shift : -1;
		if (R.Target != WantTarget || T.Target != WantTarget)
		{
			Note(TEXT("표적"));
		}
		if (R.Caught != WantCaught)
		{
			Note(TEXT("포획"));
		}
		if (T.bAsleep != R.bAsleep)
		{
			Note(TEXT("잠 훅"));
		}
		return Why.IsEmpty();
	}

	bool SameState(const FThreatState& A, const FThreatState& B)
	{
		return A.PosX == B.PosX && A.PosY == B.PosY && A.HeadX == B.HeadX && A.HeadY == B.HeadY && A.VelX == B.VelX &&
			   A.VelY == B.VelY && A.Cooldown == B.Cooldown && A.StalkState == B.StalkState && A.StalkLeft == B.StalkLeft &&
			   A.PlayerMode == B.PlayerMode && A.PlayerLeft == B.PlayerLeft && A.bAsleep == B.bAsleep && A.Target == B.Target;
	}

	FString Where(int32 n)
	{
		FString S = FString::Printf(TEXT("사례 %d (출처 %d,%d,%d"), n, kCaseSource[n * 3], kCaseSource[n * 3 + 1],
									kCaseSource[n * 3 + 2]);
		if (kCaseEdge[n] >= 0)
		{
			S += FString::Printf(TEXT(", %s"), UTF8_TO_TCHAR(kEdgeNames[kCaseEdge[n]]));
		}
		return S + TEXT(")");
	}

	// 한 종류의 사례를 골든 입력 상태로 따로 돌린다. 반환: 불일치 수
	int32 RunKind(FAutomationTestBase& Test, uint8 Kind, const TCHAR* Group, int32& OutCount, double& OutMaxError)
	{
		const FThreatConfig Cfg;
		int32 Bad = 0;
		OutCount = 0;
		OutMaxError = 0.0;
		FString Why;
		for (int32 n = 0; n < kCaseCount; ++n)
		{
			if (kCaseKind[n] != Kind)
			{
				continue;
			}
			++OutCount;
			FCase C;
			Build(n, C);
			const FThreatStepResult R = Step(C.Spec, C.State, C.In, Cfg);
			if (!Compare(n, C.State, R, OutMaxError, 0, Why))
			{
				if (Bad < kMaxReport)
				{
					Test.AddError(FString::Printf(TEXT("[%s] %s 어긋남: %s"), Group, *Where(n), *Why));
				}
				++Bad;
			}
		}
		return Bad;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatV3ConfigTest,
	"AdaptiveEcosystem.Policy.V3.Threat.Config",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatV3ConfigTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	using namespace EcoThreatV3::Golden;

	const FThreatConfig Cfg;
	struct FD
	{
		const TCHAR* Name;
		double Cpp;
		double Py;
	};
	const FD Doubles[] = {
		{TEXT("HerbSpeed"), Cfg.HerbSpeed, kCfgHerbSpeed}, {TEXT("PredViewR"), Cfg.PredViewR, kCfgPredViewR},
		{TEXT("PredFovCos"), Cfg.PredFovCos, kCfgPredFovCos},
		{TEXT("PredMeleeCatchR"), Cfg.PredMeleeCatchR, kCfgPredMeleeCatchR},
		{TEXT("PredRangedCatchR"), Cfg.PredRangedCatchR, kCfgPredRangedCatchR},
		{TEXT("PredRangedCatchP"), Cfg.PredRangedCatchP, kCfgPredRangedCatchP},
		{TEXT("PredRangedSpeedMult"), Cfg.PredRangedSpeedMult, kCfgPredRangedSpeedMult},
		{TEXT("PredWanderTurn"), Cfg.PredWanderTurn, kCfgPredWanderTurn}, {TEXT("CStill"), Cfg.CStill, kCfgCStill},
		{TEXT("CoverMultCrouch"), Cfg.CoverMultCrouch, kCfgCoverMultCrouch},
		{TEXT("CoverMultGraze"), Cfg.CoverMultGraze, kCfgCoverMultGraze},
		{TEXT("CoverMultSleep"), Cfg.CoverMultSleep, kCfgCoverMultSleep},
		{TEXT("CoverMultOther"), Cfg.CoverMultOther, kCfgCoverMultOther}, {TEXT("SleepDark"), Cfg.SleepDark, kCfgSleepDark},
		{TEXT("StalkDist"), Cfg.StalkDist, kCfgStalkDist}, {TEXT("StalkSpeed"), Cfg.StalkSpeed, kCfgStalkSpeed},
		{TEXT("PounceSpeed"), Cfg.PounceSpeed, kCfgPounceSpeed}, {TEXT("ExhaustSpeed"), Cfg.ExhaustSpeed, kCfgExhaustSpeed},
		{TEXT("PlayerSpeeds[0]"), Cfg.PlayerSpeeds[0], kCfgPlayerSpeeds[0]},
		{TEXT("PlayerSpeeds[1]"), Cfg.PlayerSpeeds[1], kCfgPlayerSpeeds[1]},
		{TEXT("PlayerSpeeds[2]"), Cfg.PlayerSpeeds[2], kCfgPlayerSpeeds[2]},
		{TEXT("PlayerStalkP"), Cfg.PlayerStalkP, kCfgPlayerStalkP},
		{TEXT("PlayerChargeDist"), Cfg.PlayerChargeDist, kCfgPlayerChargeDist},
		{TEXT("PlayerCatchR"), Cfg.PlayerCatchR, kCfgPlayerCatchR},
		{TEXT("PredSpeedMultLo"), Cfg.PredSpeedMultLo, kCfgPredSpeedMultLo},
		{TEXT("PredSpeedMultHi"), Cfg.PredSpeedMultHi, kCfgPredSpeedMultHi},
		{TEXT("RangedFracLo"), Cfg.RangedFracLo, kCfgRangedFracLo}, {TEXT("RangedFracHi"), Cfg.RangedFracHi, kCfgRangedFracHi},
		{TEXT("StalkFracLo"), Cfg.StalkFracLo, kCfgStalkFracLo}, {TEXT("StalkFracHi"), Cfg.StalkFracHi, kCfgStalkFracHi},
		{TEXT("NocturnalFracLo"), Cfg.NocturnalFracLo, kCfgNocturnalFracLo},
		{TEXT("NocturnalFracHi"), Cfg.NocturnalFracHi, kCfgNocturnalFracHi},
		{TEXT("PlayerFrac"), Cfg.PlayerFrac, kCfgPlayerFrac}, {TEXT("WorldSizeLo"), Cfg.WorldSizeLo, kCfgWorldSizeLo},
		{TEXT("WorldSizeHi"), Cfg.WorldSizeHi, kCfgWorldSizeHi}, {TEXT("Twilight"), Cfg.Twilight, kCfgTwilight}};
	for (const FD& D : Doubles)
	{
		TestTrue(FString::Printf(TEXT("%s: C++ %.17g = 파이썬 %.17g"), D.Name, D.Cpp, D.Py), D.Cpp == D.Py);
	}
	struct FI
	{
		const TCHAR* Name;
		int32 Cpp;
		int32 Py;
	};
	const FI Ints[] = {
		{TEXT("PredEatCd"), Cfg.PredEatCd, kCfgPredEatCd}, {TEXT("PounceSteps"), Cfg.PounceSteps, kCfgPounceSteps},
		{TEXT("ExhaustSteps"), Cfg.ExhaustSteps, kCfgExhaustSteps},
		{TEXT("PlayerModeStepsLo"), Cfg.PlayerModeStepsLo, kCfgPlayerModeStepsLo},
		{TEXT("PlayerModeStepsHi"), Cfg.PlayerModeStepsHi, kCfgPlayerModeStepsHi},
		{TEXT("PlayerChargeSteps"), Cfg.PlayerChargeSteps, kCfgPlayerChargeSteps},
		{TEXT("PlayerRestSteps"), Cfg.PlayerRestSteps, kCfgPlayerRestSteps},
		{TEXT("PlayerCooldown"), Cfg.PlayerCooldown, kCfgPlayerCooldown},
		{TEXT("PredatorCountLo"), Cfg.PredatorCountLo, kCfgPredatorCountLo},
		{TEXT("PredatorCountHi"), Cfg.PredatorCountHi, kCfgPredatorCountHi},
		{TEXT("DayPeriods[0]"), Cfg.DayPeriods[0], kCfgDayPeriods[0]},
		{TEXT("DayPeriods[1]"), Cfg.DayPeriods[1], kCfgDayPeriods[1]},
		{TEXT("DayPeriods[2]"), Cfg.DayPeriods[2], kCfgDayPeriods[2]}};
	for (const FI& I : Ints)
	{
		TestEqual(FString::Printf(TEXT("%s"), I.Name), I.Cpp, I.Py);
	}
	TestEqual(TEXT("bTwilightSlow"), Cfg.bTwilightSlow, kCfgTwilightSlow);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatV3SpecAndDayNightTest,
	"AdaptiveEcosystem.Policy.V3.Threat.SpecAndDayNight",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatV3SpecAndDayNightTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	using namespace EcoThreatV3::Golden;

	const FThreatConfig Cfg;
	int32 SpecBad = 0;
	int32 DarkBad = 0;
	for (int32 n = 0; n < kCaseCount; ++n)
	{
		const EThreatType Type = static_cast<EThreatType>(kSpecType[n]);
		const FThreatSpec S = Type == EThreatType::Player
								  ? MakePlayerSpec(Cfg)
								  : (Type == EThreatType::Stalker
										 ? MakeStalkerSpec(kSpecSpeedMult[n], kSpecNocturnal[n] != 0, Cfg)
										 : MakeChaserSpec(kSpecSpeedMult[n], kSpecRanged[n] != 0, kSpecNocturnal[n] != 0, Cfg));
		if (S.BaseSpeed != kSpecBaseSpeed[n] || S.CatchRadius != kSpecCatchR[n] || S.bRanged != (kSpecRanged[n] != 0) ||
			S.bNocturnal != (kSpecNocturnal[n] != 0))
		{
			if (SpecBad < EcoThreatV3Test::kMaxReport)
			{
				AddError(FString::Printf(TEXT("%s: 위협 성질 C++ 속력 %.17g 포획 %.17g, 파이썬 %.17g %.17g"),
										 *EcoThreatV3Test::Where(n), S.BaseSpeed, S.CatchRadius, kSpecBaseSpeed[n],
										 kSpecCatchR[n]));
			}
			++SpecBad;
		}
		const double D = DayNightDark(kClock[n * 4], kClock[n * 4 + 1], kClock[n * 4 + 2], kClock[n * 4 + 3]);
		if (D != kDark[n])
		{
			if (DarkBad < EcoThreatV3Test::kMaxReport)
			{
				AddError(FString::Printf(TEXT("%s: 어둠 C++ %.17g, 파이썬 %.17g"), *EcoThreatV3Test::Where(n), D, kDark[n]));
			}
			++DarkBad;
		}
	}
	AddInfo(FString::Printf(TEXT("사례 %d: 위협 성질 불일치 %d, 어둠 불일치 %d"), kCaseCount, SpecBad, DarkBad));
	TestEqual(TEXT("세계 생성 식(MakeChaserSpec·MakeStalkerSpec·MakePlayerSpec)은 파이썬과 정확히 같아야 한다"), SpecBad, 0);
	TestEqual(TEXT("어둠 d(t) 는 파이썬과 정확히 같아야 한다 (전환 스텝 0.5 포함)"), DarkBad, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatV3GoldenStepTest,
	"AdaptiveEcosystem.Policy.V3.Threat.GoldenStep",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatV3GoldenStepTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3::Golden;

	const uint8 Kinds[3] = {kKindMain, kKindSeq, kKindStageSeq};
	const TCHAR* Names[3] = {TEXT("본"), TEXT("롤아웃 열 스텝"), TEXT("무대 열 스텝")};
	for (int32 g = 0; g < 3; ++g)
	{
		int32 Count = 0;
		double MaxError = 0.0;
		const int32 Bad = EcoThreatV3Test::RunKind(*this, Kinds[g], Names[g], Count, MaxError);
		AddInfo(FString::Printf(TEXT("%s: %d개, 최대 실수 오차 %.3e, 불일치 %d"), Names[g], Count, MaxError, Bad));
		TestTrue(FString::Printf(TEXT("%s 사례가 있어야 한다"), Names[g]), Count > 0);
		TestTrue(FString::Printf(TEXT("%s 최대 실수 오차 %.3e 가 허용치 %.0e 이내여야 한다"), Names[g], MaxError, kFloatTolerance),
				 MaxError <= kFloatTolerance);
		TestEqual(FString::Printf(TEXT("%s 정수·판정은 모두 파이썬과 같아야 한다"), Names[g]), Bad, 0);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatV3EdgeCasesTest,
	"AdaptiveEcosystem.Policy.V3.Threat.EdgeCases",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatV3EdgeCasesTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3::Golden;

	int32 Count = 0;
	double MaxError = 0.0;
	const int32 Bad = EcoThreatV3Test::RunKind(*this, kKindEdge, TEXT("끝 사례"), Count, MaxError);
	AddInfo(FString::Printf(TEXT("끝 사례 %d개 (이름 %d), 최대 실수 오차 %.3e, 불일치 %d"), Count, kEdgeCount, MaxError, Bad));
	TestEqual(TEXT("끝 사례 수 = 이름 수"), Count, kEdgeCount);
	TestTrue(TEXT("끝 사례 최대 실수 오차가 허용치 이내여야 한다"), MaxError <= kFloatTolerance);
	TestEqual(TEXT("끝 사례(문턱과 정확히 같은 거리 포함)는 모두 파이썬과 같아야 한다"), Bad, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatV3SequencesTest,
	"AdaptiveEcosystem.Policy.V3.Threat.Sequences",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatV3SequencesTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	using namespace EcoThreatV3::Golden;

	const FThreatConfig Cfg;
	double MaxError = 0.0;
	int32 Bad = 0;
	int32 Steps = 0;
	FString Why;
	for (int32 s = 0; s < kSeqCount; ++s)
	{
		FThreatState Carry;
		for (int32 k = 0; k < kSeqLength[s]; ++k)
		{
			const int32 n = kSeqBegin[s] + k;
			EcoThreatV3Test::FCase C;
			EcoThreatV3Test::Build(n, C);
			if (k > 0)
			{
				C.State = Carry;   // 자기 출력 상태를 이어 쓴다 (FThreatState 가 다음 스텝에 필요한 것을 모두 담는지 본다)
			}
			const FThreatStepResult R = Step(C.Spec, C.State, C.In, Cfg);
			++Steps;
			if (!EcoThreatV3Test::Compare(n, C.State, R, MaxError, 0, Why))
			{
				if (Bad < EcoThreatV3Test::kMaxReport)
				{
					AddError(FString::Printf(TEXT("열 %s 스텝 %d (%s) 어긋남: %s"), UTF8_TO_TCHAR(kSeqNames[s]), k,
											 *EcoThreatV3Test::Where(n), *Why));
				}
				++Bad;
			}
			Carry = C.State;
		}
	}
	AddInfo(FString::Printf(TEXT("열 %d개 %d스텝, 최대 실수 오차 %.3e, 불일치 %d"), kSeqCount, Steps, MaxError, Bad));
	TestTrue(TEXT("열이 있어야 한다"), kSeqCount > 0);
	TestTrue(TEXT("이어 붙인 열의 최대 실수 오차가 허용치 이내여야 한다"), MaxError <= kFloatTolerance);
	TestEqual(TEXT("이어 붙인 열의 정수·판정은 모두 파이썬과 같아야 한다"), Bad, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatV3NearThresholdTest,
	"AdaptiveEcosystem.Policy.V3.Threat.NearThreshold",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatV3NearThresholdTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	using namespace EcoThreatV3::Golden;

	// 문턱 근처(|d - r| < 1e-4 등) 롤아웃 사례: 계산 순서 차이로 판정이 갈릴 수 있어 실패로 치지 않고 보고만 한다
	const FThreatConfig Cfg;
	int32 Count = 0;
	int32 Exact = 0;
	double MaxError = 0.0;
	FString Why;
	for (int32 n = 0; n < kCaseCount; ++n)
	{
		if (kCaseKind[n] != kKindNear)
		{
			continue;
		}
		++Count;
		EcoThreatV3Test::FCase C;
		EcoThreatV3Test::Build(n, C);
		const FThreatStepResult R = Step(C.Spec, C.State, C.In, Cfg);
		if (EcoThreatV3Test::Compare(n, C.State, R, MaxError, 0, Why))
		{
			++Exact;
		}
		else
		{
			AddInfo(FString::Printf(TEXT("문턱 근처 %s: 파이썬과 다름 (%s) — 허용"), *EcoThreatV3Test::Where(n), *Why));
		}
	}
	AddInfo(FString::Printf(TEXT("문턱 근처 %d개 중 파이썬과 같음 %d, 최대 실수 오차 %.3e"), Count, Exact, MaxError));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatV3AliveFilterTest,
	"AdaptiveEcosystem.Policy.V3.Threat.AliveFilter",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatV3AliveFilterTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	using namespace EcoThreatV3::Golden;

	// 파이썬은 리스폰이라 늘 128마리가 살아 있다. 언리얼은 죽은 개체를 bAlive = false 로 둘 수 있으므로, 죽은 초식은 표적·포획
	// 후보에서 빠져야 한다: 위협 바로 앞(살아 있으면 표적·포획이 되는 자리)에 죽은 초식을 끼워도 결과가 같다(색인만 하나 밀린다)
	const FThreatConfig Cfg;
	int32 Count = 0;
	int32 Bad = 0;
	int32 AllDeadBad = 0;
	double MaxError = 0.0;
	FString Why;
	for (int32 n = 0; n < kCaseCount; ++n)
	{
		if (kCaseKind[n] != kKindMain && kCaseKind[n] != kKindEdge)
		{
			continue;
		}
		++Count;
		EcoThreatV3Test::FCase C;
		EcoThreatV3Test::Build(n, C);
		FPreyView Dead;
		Dead.X = C.State.PosX + 0.25 * C.State.HeadX;
		Dead.Y = C.State.PosY + 0.25 * C.State.HeadY;
		Dead.bAlive = false;
		C.Prey.Insert(Dead, 0);
		C.Roll.Insert(0.0, 0);
		EcoThreatV3Test::Bind(C);
		const FThreatStepResult R = Step(C.Spec, C.State, C.In, Cfg);
		if (!EcoThreatV3Test::Compare(n, C.State, R, MaxError, 1, Why))
		{
			if (Bad < EcoThreatV3Test::kMaxReport)
			{
				AddError(FString::Printf(TEXT("%s: 죽은 초식을 앞에 끼우니 결과가 바뀌었다 (%s)"), *EcoThreatV3Test::Where(n), *Why));
			}
			++Bad;
		}
		// 모두 죽음 = 초식 없음
		EcoThreatV3Test::FCase A;
		EcoThreatV3Test::Build(n, A);
		for (FPreyView& P : A.Prey)
		{
			P.bAlive = false;
		}
		FThreatState B = A.State;
		const FThreatStepResult RA = Step(A.Spec, A.State, A.In, Cfg);
		FThreatStepInput Empty = A.In;
		Empty.Prey = nullptr;
		Empty.NumPrey = 0;
		Empty.RangedRoll = nullptr;
		const FThreatStepResult RB = Step(A.Spec, B, Empty, Cfg);
		if (RA.bHasTarget || RA.Caught >= 0 || !EcoThreatV3Test::SameState(A.State, B) || RA.Speed != RB.Speed)
		{
			++AllDeadBad;
		}
	}
	AddInfo(FString::Printf(TEXT("사례 %d: 죽은 초식 끼우기 불일치 %d, 모두 죽음 불일치 %d"), Count, Bad, AllDeadBad));
	TestEqual(TEXT("죽은 초식은 결과를 바꾸지 않는다"), Bad, 0);
	TestEqual(TEXT("모두 죽은 초식 = 초식 없음 (표적·포획 없음)"), AllDeadBad, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoThreatV3ResolveCatchesTest,
	"AdaptiveEcosystem.Policy.V3.Threat.ResolveCatches",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoThreatV3ResolveCatchesTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;

	// 위협 0·3 이 초식 2 를, 위협 2 가 초식 0 을 잡았다. 색인 밖(7)은 무시한다. 사망은 초식마다 한 번, 주인은 가장 낮은 위협 색인
	const int32 ByThreat[5] = {2, -1, 0, 2, 7};
	int32 Catcher[4];
	ResolveCatches(ByThreat, 5, Catcher, 4);
	TestEqual(TEXT("초식 0 은 위협 2"), Catcher[0], 2);
	TestEqual(TEXT("초식 1 은 잡히지 않았다"), Catcher[1], -1);
	TestEqual(TEXT("초식 2 는 가장 낮은 위협 0"), Catcher[2], 0);
	TestEqual(TEXT("초식 3 은 잡히지 않았다"), Catcher[3], -1);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
