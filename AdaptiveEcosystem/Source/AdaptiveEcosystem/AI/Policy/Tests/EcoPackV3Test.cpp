// v3 야생 2단계 2 자동화 시험 — C++ 늑대 무리 협동 사냥(EcoThreatModel.h FPackHuntConfig·PackPeek·PackGoals·Step 6b′, EcoWorldV3.h C2)을
// 파이썬(env_v2/world.py wild_pack·pack_goals·_step_predators_v3, configs/v3_wild2_pack_mirror.yaml)과 대조한다 (명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md '골든 시험').
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Pack"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `PackGoldenVectorsV3.h` (herbivore_rl/export_golden_v3_pack.py)이고, 검사 본문은 `PackGoldenCheckV3.h` 다. 같은 검사를
// herbivore_rl/tests/test_wild2_pack.py 가 g++ 로도 돌린다(tests/cpp/pack_v3_main.cpp).
//
// 묶음:
//   Pack.Golden             설정(기본 끔·계수 = 거울 설정), 목표 장면(PackGoals = pack_goals 비트 단위), 한 스텝 장면(PackPeek → PackGoals → Step
//                           = _step_predators_v3 비트 단위), 끄면 그대로(무리 칸을 읽지 않는다)
//   Pack.Run                기준 루프 1800 스텝 (무대 60, 사슴 64, 늑대 잠행 2·추격 2, 포만·제자리 식사·은신처 안전·몸 여유 0.5): 켜면 앞장·돕기가 있고
//                           기다림·문 ≤ 돕기, 협동 포획 ≤ 늑대 포획 = 사냥 성공 + 사냥 밖, 늑대 중심은 늘 은신처 원(반지름 + 몸 여유) 밖. 끄면 무리 기록이 0
//   Pack.IntegratedDefaults 통합 기본값: 지역마다 늑대 4 (잠행 2·추격 2)·협동 사냥 켬·은신처 먹이 부족 끔 (사용자 결정 10-17 '추천대로 끄고'),
//                           MakeRegionWorldConfig·InitWorld 가 무리 칸을 넘긴다

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "PackGoldenCheckV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoPackV3Test
{
	using EcoThreatV3::PackCheck::FReport;

	void Report(FAutomationTestBase& Test, const TCHAR* What, const FReport& R)
	{
		Test.AddInfo(FString::Printf(TEXT("%s: 사례 %d, 어긋남 %d (처음 사례 %d 칸 %d), 돕기 %d 기다림 %d 문 %d 포획 %d"), What, R.Cases, R.Failures,
									 R.FirstCase, R.FirstField, R.Help, R.Wait, R.Door, R.Catches));
		Test.TestTrue(*FString::Printf(TEXT("%s: 파이썬과 비트 단위로 같다"), What), R.Passed());
	}

	/** 기준 루프 세계: 무대 60, 사슴 64, 늑대 잠행 2·추격 2 (주행성), 포만·제자리 식사 38, 은신처 4 (반경 6) 안전·몸 여유 0.5, 무리 bPack. */
	EcoWorldV3::FWorldConfig RunConfig(bool bPack)
	{
		EcoWorldV3::FWorldConfig C;
		C.WorldSize = 60.0;
		C.Seed = 20002;
		C.NumHerbivores = 64;
		C.NumStalkers = 2;
		C.NumChasers = 2;
		C.NumRanged = 0;
		C.NumNocturnal = 0;
		C.Covers = EcoWorldV3::QuadCovers(C.WorldSize, 6.0);
		C.bShelterSafe = true;
		C.ShelterWolfMargin = 0.5;
		C.WildSatiation.bEnabled = true;
		C.PredEatCdOverride = 38;
		C.bEatInPlace = true;
		C.PackHunt.bEnabled = bPack;
		return C;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPackV3GoldenTest,
	"AdaptiveEcosystem.Policy.V3.Pack.Golden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPackV3GoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoPackV3Test;
	namespace PC = EcoThreatV3::PackCheck;
	namespace G = EcoThreatV3::GoldenPack;
	Report(*this, TEXT("설정"), PC::CheckConfig());
	const FReport Goals = PC::CheckGoals();
	Report(*this, TEXT("목표 장면"), Goals);
	TestTrue(TEXT("목표 장면: 돕기·기다림·문 수 = 골든"), Goals.Help == G::kGoalHelp && Goals.Wait == G::kGoalWait && Goals.Door == G::kGoalDoor
														 && Goals.Help > 0 && Goals.Wait > 0 && Goals.Door > 0);
	const FReport Steps = PC::CheckSteps();
	Report(*this, TEXT("한 스텝 장면"), Steps);
	TestTrue(TEXT("한 스텝 장면: 돕기·기다림·문·포획 수 = 골든"), Steps.Help == G::kStepHelp && Steps.Wait == G::kStepWait && Steps.Door == G::kStepDoor
															  && Steps.Catches == G::kStepCatches && Steps.Help > 0 && Steps.Wait > 0);
	Report(*this, TEXT("끄면 그대로"), PC::CheckOffIgnores());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPackV3RunTest,
	"AdaptiveEcosystem.Policy.V3.Pack.Run",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPackV3RunTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	using namespace EcoPackV3Test;
	for (const bool bPack : {true, false})
	{
		FReferenceWorld Ref;
		Ref.Init(RunConfig(bPack));
		FWorldState& W = Ref.World;
		TestEqual(TEXT("세계 설정 → 위협 설정 무리 칸"), W.ThreatCfg.Pack.bEnabled, bPack);
		int64 WolfCatches = 0;
		int64 InsideSteps = 0;
		int64 HelpMoves = 0;
		for (int32 t = 0; t < 1800; ++t)
		{
			Step(W, Ref.Views.data(), Ref.NumHerbivores(), Ref.ThreatPtrs.data(), Ref.NumThreats());
			for (int32 m = 0; m < Ref.NumThreats(); ++m)
			{
				const FThreatAgent& A = *Ref.ThreatPtrs[m];
				WolfCatches += A.Last.Caught >= 0 ? 1 : 0;
				for (const EcoObservationV3::FCoverInput& Cv : W.Config.Covers)
				{
					const double Dx = A.State.PosX - Cv.X;
					const double Dy = A.State.PosY - Cv.Y;
					InsideSteps += std::sqrt(Dx * Dx + Dy * Dy) < Cv.Radius + W.Config.ShelterWolfMargin ? 1 : 0;
				}
				if (bPack && W.PackGoalBuf[static_cast<size_t>(m)].bHelp && !W.PackGoalBuf[static_cast<size_t>(m)].bWait)
				{
					HelpMoves += 1;
				}
			}
		}
		const FWorldStats& S = W.Stats;
		int64 Success = 0, Outside = 0;
		for (int32 k = 0; k < kNumHuntKinds; ++k)
		{
			Success += S.HuntSuccess[k];
			Outside += S.HuntOutside[k];
		}
		const TCHAR* Tag = bPack ? TEXT("켬") : TEXT("끔");
		TestEqual(*FString::Printf(TEXT("%s: 늑대 중심은 늘 은신처 원(반지름 + 몸 여유) 밖"), Tag), InsideSteps, int64(0));
		TestEqual(*FString::Printf(TEXT("%s: 사냥 성공 + 사냥 밖 = 늑대 포획"), Tag), Success + Outside, WolfCatches);
		if (bPack)
		{
			TestEqual(TEXT("켬: 늑대·스텝 = 1800 × 4"), S.PackWolfSteps, int64(1800) * 4);
			TestTrue(TEXT("켬: 앞장·돕기가 있다"), S.PackLeadSteps > 0 && S.PackHelpSteps > 0 && HelpMoves > 0);
			TestTrue(TEXT("켬: 기다림·문 ≤ 돕기"), S.PackWaitSteps <= S.PackHelpSteps && S.PackDoorSteps <= S.PackHelpSteps);
			TestEqual(TEXT("켬: 무리 기록 늑대 포획 = 늑대 포획"), S.PackCatches, WolfCatches);
			TestTrue(TEXT("켬: 협동 포획 ≤ 늑대 포획"), S.PackCoopCatches <= S.PackCatches);
		}
		else
		{
			TestTrue(TEXT("끔: 무리 기록이 모두 0"), S.PackWolfSteps == 0 && S.PackLeadSteps == 0 && S.PackHelpSteps == 0 && S.PackCatches == 0
													  && W.PackWolves.empty());
		}
		AddInfo(FString::Printf(TEXT("%s: 잡힘 %lld · 사냥 성공 %lld · 늑대·스텝 %lld 중 앞장 %lld 돕기 %lld 기다림 %lld 문 %lld · 협동 포획 %lld/%lld"), Tag,
								static_cast<long long>(S.Caught), static_cast<long long>(Success), static_cast<long long>(S.PackWolfSteps),
								static_cast<long long>(S.PackLeadSteps), static_cast<long long>(S.PackHelpSteps), static_cast<long long>(S.PackWaitSteps),
								static_cast<long long>(S.PackDoorSteps), static_cast<long long>(S.PackCoopCatches), static_cast<long long>(S.PackCatches)));
	}
	// 같은 시드 = 같은 비트 (무리 미리 보기가 세계 난수를 뽑지 않는다 — 두 번 돌려 같다)
	{
		FReferenceWorld A, B;
		A.Init(RunConfig(true));
		B.Init(RunConfig(true));
		bool bSame = true;
		for (int32 t = 0; t < 300 && bSame; ++t)
		{
			Step(A.World, A.Views.data(), A.NumHerbivores(), A.ThreatPtrs.data(), A.NumThreats());
			Step(B.World, B.Views.data(), B.NumHerbivores(), B.ThreatPtrs.data(), B.NumThreats());
			for (int32 m = 0; m < A.NumThreats(); ++m)
			{
				bSame = bSame && A.ThreatPtrs[m]->State.PosX == B.ThreatPtrs[m]->State.PosX && A.ThreatPtrs[m]->State.PosY == B.ThreatPtrs[m]->State.PosY;
			}
			bSame = bSame && A.World.Rng.State == B.World.Rng.State;
		}
		TestTrue(TEXT("같은 시드 = 같은 비트, 세계 난수 자리도 같다"), bSame);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPackV3IntegratedDefaultsTest,
	"AdaptiveEcosystem.Policy.V3.Pack.IntegratedDefaults",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPackV3IntegratedDefaultsTest::RunTest(const FString& Parameters)
{
	const FEcoV3IntegratedSettings Def;
	TestEqual(TEXT("통합 기본: 지역마다 늑대 4"), Def.WolvesPerRegion, 4);
	TestTrue(TEXT("통합 기본: 협동 사냥 켬"), Def.bPackHunt);
	TestFalse(TEXT("통합 기본: 은신처 먹이 부족 끔 (사용자 결정 10-17 '추천대로 끄고')"), Def.bShelterFood);
	TestFalse(TEXT("세계 설정 기본은 무리 끔 (평면 맵·기준 루프·골든 그대로)"), EcoWorldV3::FWorldConfig().PackHunt.bEnabled);
	const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(Def.StageSizeUnits, 6.0);
	const EcoWorldV3::FWorldConfig C = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Def, 0, 128, Def.WolvesPerRegion, Covers);
	TestTrue(TEXT("늑대 4 = 잠행 2·추격 2, 원거리·야행성 없음"), C.NumStalkers == 2 && C.NumChasers == 2 && C.NumRanged == 0 && C.NumNocturnal == 0);
	TestTrue(TEXT("세계 설정: 무리 켬, 먹이 부족 끔, 몸 여유 0.5"), C.PackHunt.bEnabled && !C.ShelterFood.bEnabled && C.ShelterWolfMargin == 0.5);
	const EcoThreatV3::FPackHuntConfig Pk;
	TestTrue(TEXT("세계 설정 무리 계수 = 거울 설정"), C.PackHunt.JoinR == Pk.JoinR && C.PackHunt.Lead == Pk.Lead && C.PackHunt.DoorR == Pk.DoorR
															 && C.PackHunt.DoorCos == Pk.DoorCos && C.PackHunt.WaitR == Pk.WaitR);
	EcoWorldV3::FWorldState W;
	EcoWorldV3::InitWorld(W, C);
	TestTrue(TEXT("InitWorld → 위협 설정 무리 켬"), W.ThreatCfg.Pack.bEnabled);
	FEcoV3IntegratedSettings Off = Def;
	Off.bPackHunt = false;
	TestFalse(TEXT("PackHunt 0 → 세계 무리 끔"), UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Off, 0, 128, 4, Covers).PackHunt.bEnabled);
	// 학습 범위: 보통 위협 2~12, 잠행 비율 30~70%
	const EcoThreatV3::FThreatConfig Tc;
	TestTrue(TEXT("늑대 4 는 두뇌 학습 범위 안"), Def.WolvesPerRegion >= Tc.PredatorCountLo && Def.WolvesPerRegion <= Tc.PredatorCountHi
													 && 0.5 >= Tc.StalkFracLo && 0.5 <= Tc.StalkFracHi);
	return true;
}

#endif
