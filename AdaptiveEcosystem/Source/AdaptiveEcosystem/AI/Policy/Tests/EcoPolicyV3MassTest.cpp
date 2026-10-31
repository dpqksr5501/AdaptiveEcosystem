// v3 R1b 사슴·늑대의 Mass 경로 자동화 시험 (계획서 RL_V3_UNREAL_TRAINING_PLAN.md 4-5 e3, 우리 시험 경로).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Mass"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 코드로 월드를 만들고(EcoTestWorld.h) UEcoPolicyV3Subsystem 으로 v3 세계·개체군을 연 뒤, v3 프로세서를 직접 돌린다.
//
// 묶음:
//   Mass.ReferenceParity     Mass 경로와 엔진 무관 기준 루프(EcoWorldV3::FReferenceWorld)를 같은 시작에서 나란히 돌려
//                            스텝마다 논리 상태(행동·위상·경과·seq·잠금·놀람·사건 대기·HIDE 목표·도착·세대·에너지·위치·
//                            위협 상태·전역 t·EMA·먹이)를 비트 단위로 비교한다. 두 경로는 같은 단계 함수(EcoWorldV3::Step)를
//                            쓰므로 이 시험이 지키는 것은 Mass 연결(조각 저장·슬롯 순서 모으기·결정 시계·스폰)이다.
//                            단계 함수 자체의 파이썬 대조는 Repertoire.*·Observation.*·Threat.*·Inference 골든 시험의 몫이다.
//   Mass.Determinism         같은 시드 → 같은 행동 열·상태 해시, 다른 시드 → 다른 열
//   Mass.StateValid          수백 스텝 동안 행동 상태·위협 상태·관측이 늘 유효하다 (SLEEP 없음, 위상 = PhaseOf, 범위)
//   Mass.MaskRespected       읽은 개체는 마스크가 허용한 행동만, 읽지 않은 개체는 행동이 그대로. 저장한 마스크 = 관측으로 다시 낸 값
//   Mass.AllFourBehaviors    늑대·은신처가 있는 장면에서 GRAZE·FLEE·HIDE·FREEZE 가 모두 나온다 (계획서 e3 끝난 기준의 시험판)
//   Mass.V1Untouched         v1 개체와 v3 개체를 한 월드에 두고: v3 프로세서는 v1 조각을, v1 프로세서는 v3 조각을 바꾸지 않는다
//   Mass.DecisionClock       60·30 FPS 에서 같은 결정 스텝 수 (7.5 Hz), 스텝 사이 화면 위치 보간
//   Mass.VersionSelect       eco.PolicyVersion 기본 1, 판 고르기 규칙, 기본 설정이 학습 범위 안, cm ↔ 단위 대응

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoBehaviorConfig.h"
#include "../EcoBehaviorFragments.h"
#include "../EcoBehaviorProcessors.h"
#include "../EcoNeighborhoodSubsystem.h"
#include "../EcoPolicyV3Fragments.h"
#include "../EcoPolicyV3Processors.h"
#include "../EcoPolicyV3Subsystem.h"
#include "Debug/EcoPolicyTestSpawner.h"
#include "EcoTestWorld.h"
#include "HAL/IConsoleManager.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "MassMovementFragments.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일과 이름이 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoPolicyV3MassTestImpl
{
	using EcoWorldV3::FHerbView;
	using EcoWorldV3::FThreatAgent;
	using EcoWorldV3::FWorldConfig;

	/** 늑대·은신처가 있는 작은 장면 (학습 범위 안: 맵 60단위, 은신처 넓이 약 17%, 보통 위협 5 + 플레이어 대역). */
	FWorldConfig V3ScenarioConfig(int64 Seed = 20001)
	{
		FWorldConfig C;
		C.Seed = Seed;
		C.WorldSize = 60.0;
		C.NumHerbivores = 48;
		C.NumStalkers = 2;
		C.NumChasers = 2;
		C.NumRanged = 1;
		C.NumNocturnal = 1;
		C.bPlayerProxy = true;
		C.PredSpeedMult = 0.8;
		C.DayPeriod = 900;
		C.DayOffset = 0;
		C.TwilightSteps = 45;
		C.Covers = EcoWorldV3::QuadCovers(C.WorldSize, 7.0);
		return C;
	}

	/** 한 시험 월드의 v3 Mass 개체군과 프로세서. */
	struct FV3MassHarness
	{
		EcoTest::FScopedTestWorld Scoped;
		FMassEntityManager* EM = nullptr;
		UEcoPolicyV3Subsystem* Sub = nullptr;
		UEcoPolicyV3StepProcessor* StepProc = nullptr;
		UEcoPolicyV3VisualProcessor* VisualProc = nullptr;
		TArray<FMassEntityHandle> Herbs;
		TArray<FMassEntityHandle> Threats;

		bool Setup(FAutomationTestBase& Test, const FWorldConfig& C, const FVector& Center = FVector::ZeroVector)
		{
			UWorld* World = Scoped.World;
			if (!Test.TestNotNull(TEXT("테스트 월드"), World))
			{
				return false;
			}
			UMassEntitySubsystem* Mass = World->GetSubsystem<UMassEntitySubsystem>();
			Sub = World->GetSubsystem<UEcoPolicyV3Subsystem>();
			if (!Test.TestNotNull(TEXT("UMassEntitySubsystem"), Mass) || !Test.TestNotNull(TEXT("UEcoPolicyV3Subsystem"), Sub))
			{
				return false;
			}
			EM = &Mass->GetMutableEntityManager();
			if (!Test.TestTrue(TEXT("v3 세션이 열린다"), Sub->BeginSession(C, Center, 0.0f)))
			{
				return false;
			}
			if (!Test.TestTrue(TEXT("v3 개체군을 만든다"), Sub->SpawnPopulation(*EM, Herbs, Threats)))
			{
				return false;
			}
			const TSharedRef<FMassEntityManager> Shared = EM->AsShared();
			StepProc = NewObject<UEcoPolicyV3StepProcessor>(World);
			VisualProc = NewObject<UEcoPolicyV3VisualProcessor>(World);
			StepProc->CallInitialize(World, Shared);
			VisualProc->CallInitialize(World, Shared);
			return true;
		}

		void Frame(float Dt)
		{
			EcoTest::RunProcessor(*StepProc, *EM, Dt);
			EcoTest::RunProcessor(*VisualProc, *EM, Dt);
			EcoTest::FlushPhase(*EM);
		}

		/** dt = StepSeconds 한 프레임 = 결정 스텝 하나 (논리 틱 8). */
		void DecisionStep() { Frame(EcoBehaviorConfig::StepSeconds); }

		FHerbView View(int32 i) const { return UEcoPolicyV3Subsystem::MakeHerbView(*EM, Herbs[i]); }
		const FThreatAgent& Threat(int32 m) const { return EM->GetFragmentDataChecked<FEcoThreatStateFragment>(Threats[m]).Agent; }
		const EcoWorldV3::FWorldState& Sim() const { return Sub->GetSim(); }
	};

	// ---- 논리 상태 스냅숏 (정수 칸 + 실수 칸, 비트 단위 비교) ----

	struct FV3Snapshot
	{
		TArray<int64> Ints;
		TArray<double> Reals;
		TArray<FString> IntNames;
		TArray<FString> RealNames;
		bool bNames = false;

		void I(const TCHAR* Name, int32 Who, int64 V)
		{
			Ints.Add(V);
			if (bNames)
			{
				IntNames.Add(FString::Printf(TEXT("%s[%d]"), Name, Who));
			}
		}
		void R(const TCHAR* Name, int32 Who, double V)
		{
			Reals.Add(V);
			if (bNames)
			{
				RealNames.Add(FString::Printf(TEXT("%s[%d]"), Name, Who));
			}
		}
	};

	void V3AppendHerb(FV3Snapshot& S, const FHerbView& V, int32 i)
	{
		const EcoRepertoireV3::FRepState& Rp = *V.Rep;
		const EcoWorldV3::FHerbBody& B = *V.Body;
		S.I(TEXT("behavior"), i, Rp.Behavior);
		S.I(TEXT("phase"), i, Rp.Phase);
		S.I(TEXT("steps_in"), i, Rp.StepsIn);
		S.I(TEXT("seq"), i, Rp.Seq);
		S.I(TEXT("lock_left"), i, Rp.LockLeft);
		S.I(TEXT("startle_left"), i, Rp.StartleLeft);
		S.I(TEXT("ev_wait"), i, Rp.EvWait);
		S.I(TEXT("hide_target"), i, Rp.HideTarget);
		S.I(TEXT("arrived"), i, Rp.bArrived ? 1 : 0);
		S.I(TEXT("prev_pc"), i, Rp.PrevPc);
		S.I(TEXT("prev_flags"), i, (Rp.bPrevNear ? 1 : 0) | (Rp.bPrevFast ? 2 : 0) | (Rp.bPrevLow ? 4 : 0) | (Rp.bPrevDark ? 8 : 0));
		S.I(TEXT("jitter"), i, Rp.Jitter);
		S.I(TEXT("generation"), i, B.Generation);
		S.I(TEXT("repro_cd"), i, B.ReproCd);
		S.I(TEXT("death"), i, B.DeathCause);
		S.I(TEXT("request"), i, V.Decision->Request);
		S.I(TEXT("reads"), i, V.Decision->Prep.bReads ? 1 : 0);
		S.I(TEXT("gait"), i, V.Control->Gait);
		S.R(TEXT("pos_x"), i, B.Pos.X);
		S.R(TEXT("pos_y"), i, B.Pos.Y);
		S.R(TEXT("head_x"), i, B.Head.X);
		S.R(TEXT("head_y"), i, B.Head.Y);
		S.R(TEXT("energy"), i, B.Energy);
		S.R(TEXT("recency"), i, Rp.Recency);
		S.R(TEXT("see_mult"), i, Rp.SeeMult);
		for (int32 k = 0; k < EcoObservationV3::kObsDim; ++k)
		{
			S.R(TEXT("obs"), i * 100 + k, V.Perception->Obs[k]);
		}
	}

	void V3AppendThreat(FV3Snapshot& S, const FThreatAgent& A, int32 m)
	{
		const EcoThreatV3::FThreatState& T = A.State;
		S.I(TEXT("w_cooldown"), m, T.Cooldown);
		S.I(TEXT("w_stalk_state"), m, static_cast<int64>(T.StalkState));
		S.I(TEXT("w_stalk_left"), m, T.StalkLeft);
		S.I(TEXT("w_player_mode"), m, static_cast<int64>(T.PlayerMode));
		S.I(TEXT("w_player_left"), m, T.PlayerLeft);
		S.I(TEXT("w_target"), m, T.Target);
		S.I(TEXT("w_caught"), m, A.Last.Caught);
		S.R(TEXT("w_pos_x"), m, T.PosX);
		S.R(TEXT("w_pos_y"), m, T.PosY);
		S.R(TEXT("w_head_x"), m, T.HeadX);
		S.R(TEXT("w_head_y"), m, T.HeadY);
		S.R(TEXT("w_vel_x"), m, T.VelX);
		S.R(TEXT("w_vel_y"), m, T.VelY);
	}

	void V3AppendWorld(FV3Snapshot& S, const EcoWorldV3::FWorldState& W)
	{
		S.I(TEXT("t"), 0, W.T);
		S.I(TEXT("rng"), 0, static_cast<int64>(W.Rng.State));
		S.I(TEXT("caught_total"), 0, W.Stats.Caught);
		S.I(TEXT("starved_total"), 0, W.Stats.Starved);
		S.R(TEXT("dark"), 0, W.Dark);
		S.R(TEXT("pred_ema"), 0, W.PredEma);
		S.R(TEXT("food_total"), 0, W.Food.Total());
	}

	FV3Snapshot V3SnapshotHarness(const FV3MassHarness& H, bool bNames = false)
	{
		FV3Snapshot S;
		S.bNames = bNames;
		V3AppendWorld(S, H.Sim());
		for (int32 i = 0; i < H.Herbs.Num(); ++i)
		{
			V3AppendHerb(S, H.View(i), i);
		}
		for (int32 m = 0; m < H.Threats.Num(); ++m)
		{
			V3AppendThreat(S, H.Threat(m), m);
		}
		return S;
	}

	FV3Snapshot V3SnapshotReference(EcoWorldV3::FReferenceWorld& Ref, bool bNames = false)
	{
		FV3Snapshot S;
		S.bNames = bNames;
		V3AppendWorld(S, Ref.World);
		for (int32 i = 0; i < Ref.NumHerbivores(); ++i)
		{
			V3AppendHerb(S, Ref.Views[i], i);
		}
		for (int32 m = 0; m < Ref.NumThreats(); ++m)
		{
			V3AppendThreat(S, Ref.Threats[m], m);
		}
		return S;
	}

	/** 같으면 빈 문자열, 다르면 처음 다른 칸 (이름은 B 의 이름표에서). */
	FString V3FirstDifference(const FV3Snapshot& A, const FV3Snapshot& B)
	{
		if (A.Ints.Num() != B.Ints.Num() || A.Reals.Num() != B.Reals.Num())
		{
			return FString::Printf(TEXT("칸 수가 다르다 (%d/%d, %d/%d)"), A.Ints.Num(), B.Ints.Num(), A.Reals.Num(), B.Reals.Num());
		}
		for (int32 k = 0; k < A.Ints.Num(); ++k)
		{
			if (A.Ints[k] != B.Ints[k])
			{
				return FString::Printf(TEXT("%s: %lld vs %lld"), B.IntNames.IsValidIndex(k) ? *B.IntNames[k] : TEXT("?"),
									   static_cast<long long>(A.Ints[k]), static_cast<long long>(B.Ints[k]));
			}
		}
		for (int32 k = 0; k < A.Reals.Num(); ++k)
		{
			if (FMemory::Memcmp(&A.Reals[k], &B.Reals[k], sizeof(double)) != 0)
			{
				return FString::Printf(TEXT("%s: %.17g vs %.17g"), B.RealNames.IsValidIndex(k) ? *B.RealNames[k] : TEXT("?"),
									   A.Reals[k], B.Reals[k]);
			}
		}
		return FString();
	}

	/** FNV-1a 64 (정수 칸 + 실수 칸의 비트). */
	uint64 V3HashSnapshot(const FV3Snapshot& S)
	{
		uint64 H = 0xcbf29ce484222325ULL;
		auto Mix = [&H](const void* Data, int32 Bytes)
		{
			const uint8* P = static_cast<const uint8*>(Data);
			for (int32 k = 0; k < Bytes; ++k)
			{
				H ^= P[k];
				H *= 0x100000001b3ULL;
			}
		};
		Mix(S.Ints.GetData(), S.Ints.Num() * static_cast<int32>(sizeof(int64)));
		Mix(S.Reals.GetData(), S.Reals.Num() * static_cast<int32>(sizeof(double)));
		return H;
	}

	const TCHAR* V3TestBehaviorName(int32 B)
	{
		static const TCHAR* Names[5] = {TEXT("GRAZE"), TEXT("FLEE"), TEXT("HIDE"), TEXT("FREEZE"), TEXT("SLEEP")};
		return (B >= 0 && B < 5) ? Names[B] : TEXT("?");
	}
}

using namespace EcoPolicyV3MassTestImpl;

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3MassReferenceParityTest,
	"AdaptiveEcosystem.Policy.V3.Mass.ReferenceParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3MassReferenceParityTest::RunTest(const FString& Parameters)
{
	const FWorldConfig C = V3ScenarioConfig(20002);
	FV3MassHarness H;
	if (!H.Setup(*this, C))
	{
		return false;
	}
	EcoWorldV3::FReferenceWorld Ref;
	Ref.Init(C);

	constexpr int32 Steps = 300;
	int32 Compared = 0;
	FString Diff = V3FirstDifference(V3SnapshotHarness(H), V3SnapshotReference(Ref, true));
	if (!Diff.IsEmpty())
	{
		AddError(FString::Printf(TEXT("스폰 직후(스텝 0)부터 다르다: %s"), *Diff));
		return false;
	}
	int32 MaxTransformErrCmX100 = 0;
	for (int32 s = 1; s <= Steps; ++s)
	{
		Ref.StepOnce();
		H.DecisionStep();
		++Compared;
		Diff = V3FirstDifference(V3SnapshotHarness(H), V3SnapshotReference(Ref, true));
		if (!Diff.IsEmpty())
		{
			AddError(FString::Printf(TEXT("스텝 %d 에서 Mass 경로와 기준 루프가 갈렸다: %s"), s, *Diff));
			return false;
		}
		// 결정 스텝 직후(시계 진행 0)의 화면 위치는 이번 스텝 이동 전 위치(PrevPos)다 — 한 스텝 늦게 따라가는 보간
		for (int32 i = 0; i < H.Herbs.Num(); ++i)
		{
			const FVector Got = H.EM->GetFragmentDataChecked<FTransformFragment>(H.Herbs[i]).GetTransform().GetLocation();
			const FVector Want = H.Sub->UnitsToCm(H.View(i).Body->PrevPos);
			MaxTransformErrCmX100 = FMath::Max(MaxTransformErrCmX100, FMath::RoundToInt32(FVector::Dist(Got, Want) * 100.0));
		}
	}
	const EcoWorldV3::FWorldStats& St = H.Sim().Stats;
	AddInfo(FString::Printf(TEXT("%d 스텝 비트 단위 같음 (사슴 %d, 위협 %d) | 포획 %lld 굶음 %lld | 행동 스텝 G %lld F %lld H %lld Fz %lld"),
							Compared, H.Herbs.Num(), H.Threats.Num(), static_cast<long long>(St.Caught),
							static_cast<long long>(St.Starved), static_cast<long long>(St.BehaviorSteps[0]),
							static_cast<long long>(St.BehaviorSteps[1]), static_cast<long long>(St.BehaviorSteps[2]),
							static_cast<long long>(St.BehaviorSteps[3])));
	TestEqual(TEXT("비교한 스텝"), Compared, Steps);
	TestTrue(TEXT("화면 위치 = 논리 위치(cm) 대응 (오차 0.01 cm 이하)"), MaxTransformErrCmX100 <= 1);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3MassDeterminismTest,
	"AdaptiveEcosystem.Policy.V3.Mass.Determinism",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3MassDeterminismTest::RunTest(const FString& Parameters)
{
	constexpr int32 Steps = 300;
	auto Run = [this](int64 Seed, TArray<uint64>& OutHashes, TArray<uint8>& OutBehaviors) -> bool
	{
		FV3MassHarness H;
		if (!H.Setup(*this, V3ScenarioConfig(Seed)))
		{
			return false;
		}
		OutHashes.Add(V3HashSnapshot(V3SnapshotHarness(H)));
		for (int32 s = 0; s < Steps; ++s)
		{
			H.DecisionStep();
			OutHashes.Add(V3HashSnapshot(V3SnapshotHarness(H)));
			for (int32 i = 0; i < H.Herbs.Num(); ++i)
			{
				OutBehaviors.Add(static_cast<uint8>(H.View(i).Rep->Behavior));
			}
		}
		return true;
	};

	TArray<uint64> HashA, HashB, HashC;
	TArray<uint8> BehA, BehB, BehC;
	if (!Run(20003, HashA, BehA) || !Run(20003, HashB, BehB) || !Run(20004, HashC, BehC))
	{
		return false;
	}
	int32 FirstDiff = INDEX_NONE;
	for (int32 k = 0; k < HashA.Num() && k < HashB.Num(); ++k)
	{
		if (HashA[k] != HashB[k])
		{
			FirstDiff = k;
			break;
		}
	}
	TestEqual(TEXT("같은 시드 두 번: 스텝 수"), HashA.Num(), HashB.Num());
	TestEqual(TEXT("같은 시드 두 번: 처음 다른 스텝 (-1 = 없음)"), FirstDiff, static_cast<int32>(INDEX_NONE));
	TestTrue(TEXT("같은 시드 두 번: 행동 열이 같다"), BehA == BehB);
	TestTrue(TEXT("다른 시드는 다른 행동 열·상태를 낸다"), BehA != BehC && HashA.Last() != HashC.Last());
	AddInfo(FString::Printf(TEXT("%d 스텝 × 사슴 48: 상태 해시 끝 %016llx (같은 시드 두 번), 다른 시드 %016llx"), Steps,
							static_cast<unsigned long long>(HashA.Last()), static_cast<unsigned long long>(HashC.Last())));
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3MassStateValidTest,
	"AdaptiveEcosystem.Policy.V3.Mass.StateValid",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3MassStateValidTest::RunTest(const FString& Parameters)
{
	FV3MassHarness H;
	const FWorldConfig C = V3ScenarioConfig(20005);
	if (!H.Setup(*this, C))
	{
		return false;
	}
	constexpr int32 Steps = 400;
	const int32 K = static_cast<int32>(C.Covers.size());
	int32 Errors = 0;
	auto Fail = [this, &Errors](int32 Step, const FString& What)
	{
		if (Errors < 12)
		{
			AddError(FString::Printf(TEXT("스텝 %d: %s"), Step, *What));
		}
		++Errors;
	};

	for (int32 s = 1; s <= Steps; ++s)
	{
		H.DecisionStep();
		const EcoWorldV3::FWorldState& W = H.Sim();
		if (W.T != s)
		{
			Fail(s, FString::Printf(TEXT("전역 스텝 t = %lld"), static_cast<long long>(W.T)));
		}
		for (int32 i = 0; i < H.Herbs.Num(); ++i)
		{
			const FHerbView V = H.View(i);
			const EcoRepertoireV3::FRepState& Rp = *V.Rep;
			const EcoWorldV3::FHerbBody& B = *V.Body;
			const FString Who = FString::Printf(TEXT("사슴 %d (%s)"), i, V3TestBehaviorName(Rp.Behavior));
			if (Rp.Behavior < EcoRepertoireV3::kGraze || Rp.Behavior > EcoRepertoireV3::kFreeze)
			{
				Fail(s, Who + TEXT(": R1b 허용 밖 행동 (SLEEP 은 막혀 있다)"));
			}
			// 위상은 Commit 때 정하고 Tick 은 바꾸지 않는다(계약 5-2) — 스텝 뒤(경과 +1)에서 본 위상 규칙 (SLEEP·기상 없음):
			//   리스폰(경과 0)·진입 스텝(경과 1)은 0, GRAZE·FREEZE 는 그 밖 1, FLEE 는 놀람이 남으면 0, HIDE 의 1 은 도착 뒤
			{
				const bool bFresh = Rp.StepsIn <= 1;
				bool bPhaseOk = Rp.Phase == EcoRepertoireV3::kPhaseEnter || Rp.Phase == EcoRepertoireV3::kPhaseActive;
				if (Rp.Behavior == EcoRepertoireV3::kGraze || Rp.Behavior == EcoRepertoireV3::kFreeze)
				{
					bPhaseOk = bPhaseOk && Rp.Phase == (bFresh ? EcoRepertoireV3::kPhaseEnter : EcoRepertoireV3::kPhaseActive);
				}
				if (Rp.Behavior == EcoRepertoireV3::kFlee && (bFresh || Rp.StartleLeft > 0))
				{
					bPhaseOk = bPhaseOk && Rp.Phase == EcoRepertoireV3::kPhaseEnter;
				}
				if (Rp.Behavior == EcoRepertoireV3::kHide && Rp.Phase == EcoRepertoireV3::kPhaseActive)
				{
					bPhaseOk = bPhaseOk && Rp.bArrived;
				}
				if (!bPhaseOk)
				{
					Fail(s, Who + FString::Printf(TEXT(": 위상 %d (경과 %d, 놀람 %d, 도착 %d)"), Rp.Phase, Rp.StepsIn, Rp.StartleLeft,
												  Rp.bArrived ? 1 : 0));
				}
			}
			if (Rp.StepsIn < 0 || Rp.Seq < 0 || Rp.Seq > 255 || Rp.StartleLeft < 0 || Rp.StartleLeft > 3)
			{
				Fail(s, Who + FString::Printf(TEXT(": 범위 밖 (경과 %d, seq %d, 놀람 %d)"), Rp.StepsIn, Rp.Seq, Rp.StartleLeft));
			}
			if (Rp.StartleLeft > 0 && Rp.Behavior != EcoRepertoireV3::kFlee)
			{
				Fail(s, Who + TEXT(": FLEE 가 아닌데 놀람 정지가 남았다"));
			}
			const int32 Jit = EcoRepertoireV3::DecisionJitter(C.Seed, EcoRepertoireV3::MakeAgentKey(B.Slot, B.Generation), 3);
			if (Rp.Jitter != Jit || Rp.EvWait < -1 || Rp.EvWait > Rp.Jitter)
			{
				Fail(s, Who + FString::Printf(TEXT(": 지연 %d (키로 다시 낸 값 %d), 사건 대기 %d"), Rp.Jitter, Jit, Rp.EvWait));
			}
			if ((Rp.Behavior == EcoRepertoireV3::kHide) != (Rp.HideTarget >= 0) || Rp.HideTarget >= K)
			{
				Fail(s, Who + FString::Printf(TEXT(": HIDE 목표 %d"), Rp.HideTarget));
			}
			if (Rp.bArrived && Rp.Behavior != EcoRepertoireV3::kHide)
			{
				Fail(s, Who + TEXT(": HIDE 가 아닌데 도착 표시"));
			}
			if (Rp.LockLeft > EcoRepertoireV3::kR1bConfig.HideTravelMax)
			{
				Fail(s, Who + FString::Printf(TEXT(": 잠금 %d"), Rp.LockLeft));
			}
			if (!(B.Energy > 0.0 && B.Energy <= 1.0))
			{
				Fail(s, Who + FString::Printf(TEXT(": 에너지 %f"), B.Energy));
			}
			if (B.Pos.X < 0.0 || B.Pos.X > C.WorldSize || B.Pos.Y < 0.0 || B.Pos.Y > C.WorldSize)
			{
				Fail(s, Who + TEXT(": 맵 밖"));
			}
			if (FMath::Abs(FMath::Sqrt(B.Head.X * B.Head.X + B.Head.Y * B.Head.Y) - 1.0) > 1e-9)
			{
				Fail(s, Who + TEXT(": heading 이 단위벡터가 아니다"));
			}
			if (!(Rp.Recency >= 0.0 && Rp.Recency <= 1.0) || !(Rp.SeeMult == 0.6 || Rp.SeeMult == 1.0))
			{
				Fail(s, Who + FString::Printf(TEXT(": recency %f, 탐지 배수 %f"), Rp.Recency, Rp.SeeMult));
			}
			for (int32 k = 0; k < EcoObservationV3::kObsDim; ++k)
			{
				const float O = V.Perception->Obs[k];
				if (!(O >= 0.0f && O <= 1.0f))
				{
					Fail(s, Who + FString::Printf(TEXT(": 관측 %d = %f"), k, O));
					break;
				}
			}
			if (V.Perception->Obs[EcoObservationV3::kObsBehGraze + Rp.Behavior] != 1.0f)
			{
				Fail(s, Who + TEXT(": 관측 행동 원핫이 지금 행동과 다르다"));
			}
		}
		for (int32 m = 0; m < H.Threats.Num(); ++m)
		{
			const FThreatAgent& A = H.Threat(m);
			const EcoThreatV3::FThreatState& T = A.State;
			const FString Who = FString::Printf(TEXT("위협 %d"), m);
			if (T.PosX < 0.0 || T.PosX > C.WorldSize || T.PosY < 0.0 || T.PosY > C.WorldSize)
			{
				Fail(s, Who + TEXT(": 맵 밖"));
			}
			if (T.Cooldown < 0 || T.Cooldown > 30)
			{
				Fail(s, Who + FString::Printf(TEXT(": 쿨다운 %d"), T.Cooldown));
			}
			if (A.Spec.Type != EcoThreatV3::EThreatType::Stalker && T.StalkState != EcoThreatV3::EStalkState::Roam)
			{
				Fail(s, Who + TEXT(": 잠행형이 아닌데 잠행 상태"));
			}
			if (T.StalkState == EcoThreatV3::EStalkState::Pounce && (T.StalkLeft < 0 || T.StalkLeft > 12))
			{
				Fail(s, Who + FString::Printf(TEXT(": 돌진 남은 %d"), T.StalkLeft));
			}
			if (A.Spec.Type == EcoThreatV3::EThreatType::Player && (T.PlayerLeft < 0 || T.PlayerLeft > 400))
			{
				Fail(s, Who + FString::Printf(TEXT(": 플레이어 남은 %d"), T.PlayerLeft));
			}
		}
	}
	const EcoWorldV3::FWorldStats& St = H.Sim().Stats;
	AddInfo(FString::Printf(TEXT("%d 스텝, 위반 %d | 결정 %lld 포획 %lld 굶음 %lld 번식 %lld"), Steps, Errors,
							static_cast<long long>(St.Decisions), static_cast<long long>(St.Caught),
							static_cast<long long>(St.Starved), static_cast<long long>(St.Reproduced)));
	TestEqual(TEXT("상태 위반 수"), Errors, 0);
	TestEqual(TEXT("SLEEP 사용"), St.BehaviorSteps[EcoRepertoireV3::kSleep], static_cast<int64>(0));
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3MassMaskRespectedTest,
	"AdaptiveEcosystem.Policy.V3.Mass.MaskRespected",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3MassMaskRespectedTest::RunTest(const FString& Parameters)
{
	FV3MassHarness H;
	if (!H.Setup(*this, V3ScenarioConfig(20006)))
	{
		return false;
	}
	constexpr int32 Steps = 400;
	int32 Reads = 0;
	int32 NonReads = 0;
	int32 Violations = 0;
	int32 MaskMismatch = 0;
	int32 BlockedDecisions = 0;   // 읽은 개체 중 마스크가 무언가를 막은 결정 (가능 조건이 실제로 일했다)
	int32 ThreatEntries = 0;
	int32 ThreatEntriesKnown = 0;
	for (int32 s = 1; s <= Steps; ++s)
	{
		H.DecisionStep();
		for (int32 i = 0; i < H.Herbs.Num(); ++i)
		{
			const FHerbView V = H.View(i);
			const EcoWorldV3::FHerbDecision& D = *V.Decision;
			const int32 B = D.ExecutedBehavior;   // 이 스텝에 실행한 행동 (리스폰한 개체는 지금 RepState 가 GRAZE 로 다시 시작했다)
			if (D.bCommittedReads)
			{
				++Reads;
				if (D.CommittedMask[B] == 0)
				{
					++Violations;
					if (Violations <= 8)
					{
						AddError(FString::Printf(TEXT("스텝 %d 사슴 %d: 마스크가 막은 %s 를 실행했다"), s, i, V3TestBehaviorName(B)));
					}
				}
				int32 Open = 0;
				for (int32 b = 0; b < 4; ++b)
				{
					Open += D.CommittedMask[b] != 0 ? 1 : 0;
				}
				BlockedDecisions += Open < 4 ? 1 : 0;
			}
			else
			{
				++NonReads;
				if (B != D.PrevBehavior)
				{
					++Violations;
					AddError(FString::Printf(TEXT("스텝 %d 사슴 %d: 요청을 읽지 않았는데 행동이 바뀌었다"), s, i));
				}
			}
			// FLEE·HIDE·FREEZE 진입은 '위협을 안다'(보이거나 threat_recency ≥ 0.2) 때만 열린다 — 진입 결정 관측으로 확인
			if (D.Result.bSwitch && B != EcoRepertoireV3::kGraze)
			{
				++ThreatEntries;
				ThreatEntriesKnown += D.CommittedMask[EcoRepertoireV3::kFlee] != 0 ? 1 : 0;
			}

			// 다음 스텝 마스크(저장값) = 저장한 관측과 Prepare 결과로 다시 낸 값
			uint8 Feasible[5];
			uint8 Mask[5];
			EcoPolicyV3::ComputeFeasibleMask(V.Perception->Obs, Feasible);
			EcoPolicyV3::ComposeActionMask(Feasible, D.Prep.bReads, D.Prep.bWakeDecide, V.Rep->Behavior, Mask);
			bool bSame = true;
			for (int32 b = 0; b < 5; ++b)
			{
				bSame = bSame && Mask[b] == D.Mask[b];
			}
			MaskMismatch += bSame ? 0 : 1;
			if (D.Prep.bReads ? D.Mask[D.Request] == 0 : D.Request != V.Rep->Behavior)
			{
				++Violations;
				AddError(FString::Printf(TEXT("스텝 %d 사슴 %d: 저장한 요청 %s 이 마스크 밖이다"), s, i, V3TestBehaviorName(D.Request)));
			}
		}
	}
	AddInfo(FString::Printf(TEXT("%d 스텝: 읽음 %d, 안 읽음 %d, 마스크가 막은 결정 %d, 위협 행동 진입 %d (위협 앎 %d)"), Steps, Reads,
							NonReads, BlockedDecisions, ThreatEntries, ThreatEntriesKnown));
	TestTrue(TEXT("요청을 읽은 결정이 있다"), Reads > 0);
	TestTrue(TEXT("마스크가 무언가를 막은 결정이 있다"), BlockedDecisions > 0);
	TestEqual(TEXT("마스크 위반"), Violations, 0);
	TestEqual(TEXT("저장 마스크 = 다시 낸 마스크"), MaskMismatch, 0);
	TestEqual(TEXT("FLEE·HIDE·FREEZE 진입은 위협을 알 때만"), ThreatEntriesKnown, ThreatEntries);
	TestEqual(TEXT("세계 기록의 마스크 위반"), H.Sim().Stats.MaskViolations, static_cast<int64>(0));
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3MassAllFourBehaviorsTest,
	"AdaptiveEcosystem.Policy.V3.Mass.AllFourBehaviors",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3MassAllFourBehaviorsTest::RunTest(const FString& Parameters)
{
	FV3MassHarness H;
	if (!H.Setup(*this, V3ScenarioConfig(20001)))
	{
		return false;
	}
	constexpr int32 MaxSteps = 3000;   // 400 초. 보통 훨씬 일찍 모두 나온다
	int32 FirstSeen[5] = {INDEX_NONE, INDEX_NONE, INDEX_NONE, INDEX_NONE, INDEX_NONE};
	int32 Step = 0;
	auto AllFour = [&FirstSeen]()
	{
		return FirstSeen[0] != INDEX_NONE && FirstSeen[1] != INDEX_NONE && FirstSeen[2] != INDEX_NONE && FirstSeen[3] != INDEX_NONE;
	};
	while (Step < MaxSteps && !(AllFour() && Step >= 450))
	{
		H.DecisionStep();
		++Step;
		const EcoWorldV3::FWorldStats& St = H.Sim().Stats;
		for (int32 b = 0; b < 5; ++b)
		{
			if (FirstSeen[b] == INDEX_NONE && St.BehaviorSteps[b] > 0)
			{
				FirstSeen[b] = Step;
			}
		}
	}
	const EcoWorldV3::FWorldStats& St = H.Sim().Stats;
	AddInfo(FString::Printf(TEXT("%d 스텝: 처음 나온 스텝 GRAZE %d FLEE %d HIDE %d FREEZE %d | 개체·스텝 %lld/%lld/%lld/%lld | ")
								TEXT("진입 %lld/%lld/%lld/%lld | 포획 %lld 굶음 %lld"),
							Step, FirstSeen[0], FirstSeen[1], FirstSeen[2], FirstSeen[3],
							static_cast<long long>(St.BehaviorSteps[0]), static_cast<long long>(St.BehaviorSteps[1]),
							static_cast<long long>(St.BehaviorSteps[2]), static_cast<long long>(St.BehaviorSteps[3]),
							static_cast<long long>(St.Entries[0]), static_cast<long long>(St.Entries[1]),
							static_cast<long long>(St.Entries[2]), static_cast<long long>(St.Entries[3]),
							static_cast<long long>(St.Caught), static_cast<long long>(St.Starved)));
	for (int32 b = 0; b < 4; ++b)
	{
		TestTrue(FString::Printf(TEXT("%s 가 나온다"), V3TestBehaviorName(b)), FirstSeen[b] != INDEX_NONE);
	}
	TestEqual(TEXT("SLEEP 은 나오지 않는다 (R1b 허용 마스크)"), FirstSeen[4], static_cast<int32>(INDEX_NONE));
	TestTrue(TEXT("늑대가 사슴을 잡는다 (위협이 실제로 압력을 준다)"), St.Caught > 0);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3MassV1UntouchedTest,
	"AdaptiveEcosystem.Policy.V3.Mass.V1Untouched",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3MassV1UntouchedTest::RunTest(const FString& Parameters)
{
	FV3MassHarness H;
	if (!H.Setup(*this, V3ScenarioConfig(20007), FVector(0.0, 0.0, 0.0)))
	{
		return false;
	}
	FMassEntityManager& EM = *H.EM;
	UWorld* World = H.Scoped.World;

	// v1 개체 (EcoPipelineTest 와 같은 구성) — v3 맵 안쪽에 겹치게 둔다
	const FMassArchetypeHandle V1Herb = EM.CreateArchetype(EcoTest::HerbivoreComposition());
	const FMassArchetypeHandle V1Pred = EM.CreateArchetype({FTransformFragment::StaticStruct(), FMassVelocityFragment::StaticStruct(),
															 FEcoPredatorStateFragment::StaticStruct(), FEcoPredatorTag::StaticStruct()});
	TArray<FMassEntityHandle> V1;
	for (int32 i = 0; i < 24; ++i)
	{
		const FMassEntityHandle E = EM.CreateEntity(V1Herb);
		EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(
			FVector(-3000.0 + 250.0 * (i % 6), -2000.0 + 400.0 * (i / 6), 0.0));
		EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value = FVector(10.0, 0.0, 0.0);
		FEcoVitalsFragment& Vit = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		Vit.MaxEnergy = 100.0f;
		Vit.Energy = 50.0f + i;
		V1.Add(E);
	}
	for (int32 m = 0; m < 2; ++m)
	{
		const FMassEntityHandle E = EM.CreateEntity(V1Pred);
		EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(FVector(-1500.0 + 900.0 * m, 0.0, 0.0));
		EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value = FVector(0.0, 10.0, 0.0);
		V1.Add(E);
	}

	struct FV1State
	{
		FVector Loc;
		FQuat Rot;
		FVector Vel;
		float Obs[7] = {};
		float Act[4] = {};
		float Energy = 0.0f;
		float HP = 0.0f;
	};
	auto ReadV1 = [&EM](FMassEntityHandle E)
	{
		FV1State S;
		const FTransform& T = EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform();
		S.Loc = T.GetLocation();
		S.Rot = T.GetRotation();
		S.Vel = EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value;
		if (const FEcoObservationFragment* O = EM.GetFragmentDataPtr<FEcoObservationFragment>(E))
		{
			O->Observation.ToFloatArray(S.Obs);
		}
		if (const FEcoPolicyOutputFragment* A = EM.GetFragmentDataPtr<FEcoPolicyOutputFragment>(E))
		{
			A->Action.ToFloatArray(S.Act);
		}
		if (const FEcoVitalsFragment* V = EM.GetFragmentDataPtr<FEcoVitalsFragment>(E))
		{
			S.Energy = V->Energy;
			S.HP = V->HP;
		}
		return S;
	};
	auto SameV1 = [](const FV1State& A, const FV1State& B)
	{
		bool bSame = A.Loc == B.Loc && A.Rot.Equals(B.Rot, 0.0) && A.Vel == B.Vel && A.Energy == B.Energy && A.HP == B.HP;
		for (int32 k = 0; k < 7; ++k)
		{
			bSame = bSame && A.Obs[k] == B.Obs[k];
		}
		for (int32 k = 0; k < 4; ++k)
		{
			bSame = bSame && A.Act[k] == B.Act[k];
		}
		return bSame;
	};

	// --- 1) v3 프로세서는 v1 조각을 바꾸지 않는다 ---
	TArray<FV1State> Before;
	for (const FMassEntityHandle& E : V1)
	{
		Before.Add(ReadV1(E));
	}
	for (int32 s = 0; s < 40; ++s)
	{
		H.DecisionStep();
	}
	int32 V1Changed = 0;
	for (int32 k = 0; k < V1.Num(); ++k)
	{
		V1Changed += SameV1(Before[k], ReadV1(V1[k])) ? 0 : 1;
	}
	TestEqual(TEXT("v3 프로세서 40 스텝 뒤 바뀐 v1 개체"), V1Changed, 0);
	TestEqual(TEXT("v3 세계는 40 스텝 갔다"), H.Sim().T, static_cast<int64>(40));

	// --- 2) v1 프로세서는 v3 조각·화면 위치를 바꾸지 않고, v1 이웃 색인에 v3 개체를 넣지 않는다 ---
	const FV3Snapshot V3Before = V3SnapshotHarness(H, true);
	TArray<FTransform> V3Xf;
	for (const FMassEntityHandle& E : H.Herbs)
	{
		V3Xf.Add(EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform());
	}
	for (const FMassEntityHandle& E : H.Threats)
	{
		V3Xf.Add(EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform());
	}
	const TSharedRef<FMassEntityManager> Shared = EM.AsShared();
	UEcoNeighborhoodGatherProcessor* Gather = NewObject<UEcoNeighborhoodGatherProcessor>(World);
	UEcoPerceptionProcessor* Perception = NewObject<UEcoPerceptionProcessor>(World);
	UEcoPolicyProcessor* Policy = NewObject<UEcoPolicyProcessor>(World);
	UEcoSteeringProcessor* Steering = NewObject<UEcoSteeringProcessor>(World);
	UEcoPredationProcessor* Predation = NewObject<UEcoPredationProcessor>(World);
	TArray<UMassProcessor*> V1Procs = {Gather, Perception, Policy, Steering, Predation};
	for (UMassProcessor* P : V1Procs)
	{
		P->CallInitialize(World, Shared);
	}
	const float Dt = 1.0f / 60.0f;
	for (int32 f = 0; f < 24; ++f)
	{
		for (UMassProcessor* P : V1Procs)
		{
			EcoTest::RunProcessor(*P, EM, Dt);
		}
		EcoTest::FlushPhase(EM);
	}
	const UEcoNeighborhoodSubsystem* Grid = World->GetSubsystem<UEcoNeighborhoodSubsystem>();
	int32 GridEntries = Grid ? Grid->GetEntries().Num() : -1;
	int32 V1Alive = 0;
	for (const FMassEntityHandle& E : V1)
	{
		const FEcoVitalsFragment* V = EM.GetFragmentDataPtr<FEcoVitalsFragment>(E);
		V1Alive += (!V || V->HP > 0.0f) ? 1 : 0;   // 포식자(생체 없음)와 산 초식
	}
	TestTrue(TEXT("v1 이웃 색인에는 v1 개체만 있다 (v3 사슴·늑대는 빠진다)"), GridEntries >= 0 && GridEntries <= V1.Num());
	AddInfo(FString::Printf(TEXT("v1 색인 %d칸 (v1 개체 %d, 산 개체 %d, v3 개체 %d)"), GridEntries, V1.Num(), V1Alive,
							H.Herbs.Num() + H.Threats.Num()));
	const FString Diff = V3FirstDifference(V3SnapshotHarness(H), V3Before);
	TestTrue(FString::Printf(TEXT("v1 프로세서 24 프레임 뒤 v3 논리 상태가 그대로다 %s"), *Diff), Diff.IsEmpty());
	int32 XfChanged = 0;
	int32 k = 0;
	for (const FMassEntityHandle& E : H.Herbs)
	{
		XfChanged += EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().Equals(V3Xf[k++], 0.0) ? 0 : 1;
	}
	for (const FMassEntityHandle& E : H.Threats)
	{
		XfChanged += EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().Equals(V3Xf[k++], 0.0) ? 0 : 1;
	}
	TestEqual(TEXT("v1 프로세서가 바꾼 v3 화면 위치"), XfChanged, 0);
	// v1 은 실제로 돌았다 (이 시험이 헛돌지 않는지)
	int32 V1Moved = 0;
	for (int32 j = 0; j < 24; ++j)
	{
		V1Moved += ReadV1(V1[j]).Loc != Before[j].Loc ? 1 : 0;
	}
	TestTrue(TEXT("v1 프로세서가 v1 사슴을 실제로 움직였다"), V1Moved > 0);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3MassDecisionClockTest,
	"AdaptiveEcosystem.Policy.V3.Mass.DecisionClock",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3MassDecisionClockTest::RunTest(const FString& Parameters)
{
	FWorldConfig C = V3ScenarioConfig(20008);
	C.NumHerbivores = 16;
	// 2 초를 60·30·20 FPS 로: 결정 스텝은 늘 15 (7.5 Hz)
	const float Rates[3] = {60.0f, 30.0f, 20.0f};
	for (const float Fps : Rates)
	{
		FV3MassHarness H;
		if (!H.Setup(*this, C))
		{
			return false;
		}
		const int32 Frames = FMath::RoundToInt32(2.0f * Fps);
		for (int32 f = 0; f < Frames; ++f)
		{
			H.Frame(1.0f / Fps);
		}
		TestEqual(FString::Printf(TEXT("%.0f FPS 2 초 = 결정 스텝 15"), Fps), H.Sim().T, static_cast<int64>(15));
	}

	// 스텝 사이 화면 보간: 결정 스텝 직후 60 FPS 4 프레임 = 진행 0.5 → 화면 위치 = (PrevPos + Pos)/2
	FV3MassHarness H;
	if (!H.Setup(*this, C))
	{
		return false;
	}
	for (int32 s = 0; s < 20; ++s)
	{
		H.DecisionStep();
	}
	for (int32 f = 0; f < 4; ++f)
	{
		H.Frame(1.0f / 60.0f);
	}
	TestEqual(TEXT("4 프레임 동안 결정 스텝이 없다"), H.Sim().T, static_cast<int64>(20));
	TestTrue(TEXT("시계 진행 0.5"), FMath::IsNearlyEqual(H.Sub->GetVisualAlpha(), 0.5f));
	double MaxErr = 0.0;
	int32 Moving = 0;
	for (int32 i = 0; i < H.Herbs.Num(); ++i)
	{
		const EcoWorldV3::FHerbBody& B = *H.View(i).Body;
		const FVector Want = H.Sub->UnitsToCm(0.5 * (B.PrevPos.X + B.Pos.X), 0.5 * (B.PrevPos.Y + B.Pos.Y));
		const FVector Got = H.EM->GetFragmentDataChecked<FTransformFragment>(H.Herbs[i]).GetTransform().GetLocation();
		MaxErr = FMath::Max(MaxErr, FVector::Dist(Got, Want));
		Moving += (B.Pos.X != B.PrevPos.X || B.Pos.Y != B.PrevPos.Y) ? 1 : 0;
	}
	AddInfo(FString::Printf(TEXT("보간 최대 오차 %.2e cm, 움직이는 사슴 %d/%d"), MaxErr, Moving, H.Herbs.Num()));
	TestTrue(TEXT("화면 위치 = 지난·이번 논리 위치의 보간"), MaxErr < 1e-3);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3MassVersionSelectTest,
	"AdaptiveEcosystem.Policy.V3.Mass.VersionSelect",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3MassVersionSelectTest::RunTest(const FString& Parameters)
{
	// --- 콘솔 변수: 기본 v1 ---
	IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.PolicyVersion"));
	if (!TestNotNull(TEXT("eco.PolicyVersion 콘솔 변수"), CVar))
	{
		return false;
	}
	const int32 Saved = CVar->GetInt();
	TestEqual(TEXT("eco.PolicyVersion 기본값은 1 (v1)"), Saved, 1);
	CVar->Set(3, ECVF_SetByCode);
	TestEqual(TEXT("3 이면 v3"), UEcoPolicyV3Subsystem::GetRequestedPolicyVersion(), 3);
	CVar->Set(2, ECVF_SetByCode);
	TestEqual(TEXT("모르는 값은 v1"), UEcoPolicyV3Subsystem::GetRequestedPolicyVersion(), 1);
	CVar->Set(Saved, ECVF_SetByCode);

	// --- 스포너 판 고르기: 덮어쓰기 > 콘솔 변수, 정체성 관찰자는 늘 v1 ---
	TestEqual(TEXT("(0, 1) → 1"), AEcoPolicyTestSpawner::ResolvePolicyVersion(0, 1, false), 1);
	TestEqual(TEXT("(0, 3) → 3"), AEcoPolicyTestSpawner::ResolvePolicyVersion(0, 3, false), 3);
	TestEqual(TEXT("(3, 1) → 3"), AEcoPolicyTestSpawner::ResolvePolicyVersion(3, 1, false), 3);
	TestEqual(TEXT("(1, 3) → 1"), AEcoPolicyTestSpawner::ResolvePolicyVersion(1, 3, false), 1);
	TestEqual(TEXT("(2, 2) → 1"), AEcoPolicyTestSpawner::ResolvePolicyVersion(2, 2, false), 1);
	TestEqual(TEXT("정체성 관찰자 (0, 3, 참) → 1"), AEcoPolicyTestSpawner::ResolvePolicyVersion(0, 3, true), 1);
	TestEqual(TEXT("정체성 관찰자 (3, 3, 참) → 1"), AEcoPolicyTestSpawner::ResolvePolicyVersion(3, 3, true), 1);

	// --- 기본 설정은 R1b 학습 세계 범위 안 (계약 7-7) ---
	const FEcoPolicyV3Settings Defaults;
	const FWorldConfig Cfg = UEcoPolicyV3Subsystem::MakeWorldConfig(Defaults);
	const TArray<FString> Out = UEcoPolicyV3Subsystem::CheckTrainingRange(Cfg);
	for (const FString& Why : Out)
	{
		AddError(FString::Printf(TEXT("기본 설정이 학습 범위 밖: %s"), *Why));
	}
	TestEqual(TEXT("맵 20000 cm = 100 단위"), Cfg.WorldSize, 100.0);
	TestEqual(TEXT("은신처 1600 cm = 8 단위 네 곳"), Cfg.Covers.size() == 4 ? Cfg.Covers[0].Radius : -1.0, 8.0);
	TestEqual(TEXT("늑대 6 (잠행 3, 추격 2, 원거리 1)"), Cfg.NumThreats(), 6);
	TestEqual(TEXT("사슴 128"), Cfg.NumHerbivores, 128);
	TestEqual(TEXT("낮밤 900 스텝"), Cfg.DayPeriod, 900);

	// --- 단위 대응 (계약 12-1): 맵 [0, size]² 의 원점 = 중심 − size/2, 1 단위 = 200 cm ---
	FV3MassHarness H;
	FWorldConfig Small = V3ScenarioConfig(20009);
	Small.NumHerbivores = 4;
	if (!H.Setup(*this, Small, FVector(1000.0, -2000.0, 50.0)))
	{
		return false;
	}
	const FVector Origin = H.Sub->UnitsToCm(0.0, 0.0);
	TestTrue(TEXT("원점 cm"), Origin.Equals(FVector(1000.0 - 6000.0, -2000.0 - 6000.0, 50.0), 1e-9));
	const FVector P = H.Sub->UnitsToCm(12.5, 40.25);
	TestTrue(TEXT("단위 → cm"), P.Equals(FVector(-5000.0 + 2500.0, -8000.0 + 8050.0, 50.0), 1e-9));
	const EcoWorldV3::FVec2 Back = H.Sub->CmToUnits(P);
	TestTrue(TEXT("cm → 단위 왕복"), FMath::IsNearlyEqual(Back.X, 12.5, 1e-12) && FMath::IsNearlyEqual(Back.Y, 40.25, 1e-12));
	TestTrue(TEXT("속력 0.6 단위/스텝 = 900 cm/s"),
			 FMath::IsNearlyEqual(EcoRepertoireV3::UnitsPerStepToCmPerSec(0.6), 900.0, 1e-9)
				 && FMath::IsNearlyEqual(static_cast<double>(EcoBehaviorConfig::HerbSpeedCmS), 900.0, 1e-3));
	TestTrue(TEXT("결정 스텝 = EcoBehaviorConfig::StepSeconds"),
			 FMath::IsNearlyEqual(EcoRepertoireV3::kStepSeconds, static_cast<double>(EcoBehaviorConfig::StepSeconds), 1e-7));
	// 두 번째 세션은 열리지 않는다 (한 월드에 v3 시험 개체군 하나). 그때 남기는 경고는 이 시험이 기대한 것이다
	AddExpectedMessagePlain(TEXT("이미 세션이 열려 있다"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
	TestFalse(TEXT("이미 열린 세션 위에 다시 열지 않는다"), H.Sub->BeginSession(Small, FVector::ZeroVector, 0.0f));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
