// v3 야생 2단계 자동화 시험 — C++ 은신처 먹이 부족(EcoWorldV3.h FShelterFoodConfig·FFoodGrid::ApplyShelterFood)과 사냥 성공률 셈(HuntUpdate)을
// 파이썬(env_v2/world.py realism_cover_food·hunt_update, configs/v3_wild2_mirror.yaml)과 대조한다 (명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md '골든 시험').
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Wild2"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `Wild2GoldenVectorsV3.h` (herbivore_rl/export_golden_v3_wild2.py)다. C++ 와 파이썬은 난수열이 달라 먹이 지도가 다르므로, 파이썬 1단계 용량을
// 그대로 넣고 같은 은신처 원으로 BuildCoverCells → ApplyShelterFood 를 불러 비트 단위로 같은지 본다(통합 모드 Build 와 같은 순서).
//
// 묶음:
//   Wild2.ShelterFoodGolden  기본값(끔·통합 켬), 거울 세계 30 × 30 의 셀 중심 은신처 셀·겹치는 셀·용량·먹이·재생률 = 파이썬, 겹침 장면 16개(셀 경계에
//                            꼭 닿는 원·모서리 중심 등 손 장면 6 + 난수 10)의 두 마스크 = 파이썬, 반경 0 원(지워진 은신처)은 건너뛰고 용량이 돌아온다
//   Wild2.HuntGolden         늑대 5 × 400 스텝 열의 스텝마다 (on, 시작, 끝, 성공, 사냥 밖)와 합 = 파이썬 hunt_update
//   Wild2.Run                기준 루프 1800 스텝 (늑대 잠행 2·추격 2, 포만 켬): 사냥 성공 + 사냥 밖 = 늑대 포획, 시작 − 끝 = 이어지는 사냥, 사슴·스텝 기록,
//                            은신처 먹이 부족을 켜면 은신처 셀 먹이가 늘 용량(1단계 × 0.15) 이하이고 끄면 지금 그대로 (먹이 격자가 같다)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "../Wild2GoldenVectorsV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoWild2V3Test
{
	namespace G2 = EcoWorldV3::GoldenWild2;

	/** 골든 격자 하나: 한 변 Gw 셀, 셀 G2::kFoodCell, 용량·먹이 = Cap0, 은신처 원 = Discs. 먹이 격자 상수는 골든 값(= FWorldConfig 기본값)이다. */
	EcoWorldV3::FWorldConfig GridConfig(const double* Discs, std::int32_t NumDiscs)
	{
		EcoWorldV3::FWorldConfig C;
		C.FoodCell = G2::kFoodCell;
		C.FoodRegenBase = G2::kFoodRegenBase;
		C.FoodRegenMult = G2::kFoodRegenMult;
		C.FoodCoverRegenMult = G2::kFoodCoverRegenMult;
		C.ShelterFood.bEnabled = true;
		for (std::int32_t k = 0; k < NumDiscs; ++k)
		{
			C.Covers.push_back({Discs[3 * k], Discs[3 * k + 1], Discs[3 * k + 2]});
		}
		return C;
	}

	void FillGrid(EcoWorldV3::FFoodGrid& F, std::int32_t Gw, const double* Cap0)
	{
		F = EcoWorldV3::FFoodGrid();
		F.Gw = Gw;
		F.Cell = G2::kFoodCell;
		F.Cap.assign(Cap0, Cap0 + static_cast<size_t>(Gw) * Gw);
		F.Food = F.Cap;
	}

	/** 기준 루프 세계: 무대 60, 사슴 64, 늑대 잠행 2·추격 2 (주행성), 포만 켬, 은신처 4 (반경 6), 먹이 부족 bShelterFood. */
	EcoWorldV3::FWorldConfig RunConfig(bool bShelterFood)
	{
		EcoWorldV3::FWorldConfig C;
		C.WorldSize = 60.0;
		C.Seed = 20001;
		C.NumHerbivores = 64;
		C.NumStalkers = 2;
		C.NumChasers = 2;
		C.NumRanged = 0;
		C.NumNocturnal = 0;
		C.Covers = EcoWorldV3::QuadCovers(C.WorldSize, 6.0);
		C.WildSatiation.bEnabled = true;
		C.PredEatCdOverride = 38;
		C.bEatInPlace = true;
		C.ShelterFood.bEnabled = bShelterFood;
		return C;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWild2V3ShelterFoodGoldenTest,
	"AdaptiveEcosystem.Policy.V3.Wild2.ShelterFoodGolden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWild2V3ShelterFoodGoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	using namespace EcoWild2V3Test;
	const FShelterFoodConfig Def;
	TestFalse(TEXT("은신처 먹이 부족 기본은 끔 (R1b 학습 세계 그대로)"), Def.bEnabled);
	TestFalse(TEXT("세계 설정 기본도 끔"), FWorldConfig().ShelterFood.bEnabled);
	TestTrue(TEXT("통합 기본값은 켬 (eco.IntegratedV3.ShelterFood 1 — 10-17 고침으로 되돌림)"), FEcoV3IntegratedSettings().bShelterFood);
	TestEqual(TEXT("cap_frac"), Def.CapFrac, G2::kCapFrac);
	TestEqual(TEXT("regen_frac"), Def.RegenFrac, G2::kRegenFrac);
	const FWorldConfig Base;
	TestEqual(TEXT("food_regen_base"), Base.FoodRegenBase, G2::kFoodRegenBase);
	TestEqual(TEXT("food_regen_mult (통합 1)"), Base.FoodRegenMult, G2::kFoodRegenMult);
	TestEqual(TEXT("food_cover_regen_mult"), Base.FoodCoverRegenMult, G2::kFoodCoverRegenMult);
	TestEqual(TEXT("food_cell"), Base.FoodCell, G2::kFoodCell);
	TestEqual(TEXT("격자 한 변 = ceil(무대 ÷ 셀)"), static_cast<int32>(std::ceil(G2::kWorldSize / G2::kFoodCell)), G2::kGw);

	// 1) 거울 세계 격자: 1단계 용량 → 셀 중심 은신처 셀 → 먹이 부족
	const FWorldConfig C = GridConfig(G2::kCover, G2::kCoverCount);
	FFoodGrid F;
	FillGrid(F, G2::kGw, G2::kCap0);
	F.BuildCoverCells(C);
	F.Cap0 = F.Cap;
	F.ApplyShelterFood(C);
	int32 Bad = 0;
	int32 Cells = 0;
	int32 Centers = 0;
	for (int32 k = 0; k < G2::kGw * G2::kGw; ++k)
	{
		const size_t i = static_cast<size_t>(k);
		Cells += F.CoverFoodCell[i];
		Centers += F.CoverCell[i];
		const bool bBad = F.CoverCell[i] != G2::kCoverCell[k] || F.CoverFoodCell[i] != G2::kCoverFoodCell[k] || F.Cap[i] != G2::kCap[k]
						  || F.Food[i] != G2::kCap[k] || F.Regen[i] != G2::kRegen[k];
		if (bBad && ++Bad <= 3)
		{
			AddError(FString::Printf(TEXT("셀 %d: 중심 %d/%d 겹침 %d/%d 용량 %.17g/%.17g 먹이 %.17g 재생 %.17g/%.17g"), k, F.CoverCell[i], G2::kCoverCell[k],
									 F.CoverFoodCell[i], G2::kCoverFoodCell[k], F.Cap[i], G2::kCap[k], F.Food[i], F.Regen[i], G2::kRegen[k]));
		}
	}
	TestEqual(TEXT("거울 세계 격자 = 파이썬 (마스크 둘·용량·먹이·재생률, 비트 단위)"), Bad, 0);
	TestEqual(TEXT("겹치는 셀 수"), Cells, G2::kCoverFoodCells);
	TestEqual(TEXT("셀 중심 은신처 셀 수"), Centers, G2::kCoverCenterCells);

	// 2) 겹침 장면: 두 마스크 = 파이썬
	int32 SceneBad = 0;
	int32 HandBad = 0;
	for (int32 s = 0; s < G2::kScenes; ++s)
	{
		const int32 Gw = G2::kSceneGw[s];
		const std::vector<double> Ones(static_cast<size_t>(Gw) * Gw, 1.0);
		const FWorldConfig Cs = GridConfig(&G2::kSceneDisc[3 * G2::kSceneDiscStart[s]], G2::kSceneDiscCount[s]);
		FFoodGrid Fs;
		FillGrid(Fs, Gw, Ones.data());
		Fs.BuildCoverCells(Cs);
		Fs.Cap0 = Fs.Cap;
		Fs.ApplyShelterFood(Cs);
		int32 Wrong = 0;
		for (int32 k = 0; k < Gw * Gw; ++k)
		{
			const int32 j = G2::kSceneMaskStart[s] + k;
			Wrong += (Fs.CoverCell[static_cast<size_t>(k)] != G2::kSceneCenter[j] || Fs.CoverFoodCell[static_cast<size_t>(k)] != G2::kSceneOverlap[j]) ? 1 : 0;
		}
		SceneBad += Wrong > 0 ? 1 : 0;
		HandBad += (Wrong > 0 && s < G2::kSceneHand) ? 1 : 0;
		if (Wrong > 0)
		{
			AddError(FString::Printf(TEXT("겹침 장면 %d: 다른 셀 %d"), s, Wrong));
		}
	}
	TestEqual(TEXT("겹침 장면: 셀 중심·겹침 마스크 = 파이썬"), SceneBad, 0);
	TestEqual(TEXT("손 장면 모두 같다"), HandBad, 0);

	// 3) 지워진 은신처 (통합 모드 RefreshRefuges — 반경 0, 번호 유지): 다시 걸면 그 원의 셀은 1단계 용량으로 돌아가고 먹이는 그대로·용량 이하
	FWorldConfig Cr = C;
	Cr.Covers[0].Radius = 0.0;
	std::vector<double> FoodBefore = F.Food;
	F.BuildCoverCells(Cr);
	F.ApplyShelterFood(Cr);
	int32 Restored = 0;
	int32 Over = 0;
	int32 FoodMoved = 0;
	for (size_t i = 0; i < F.Cap.size(); ++i)
	{
		Restored += (G2::kCoverFoodCell[i] != 0 && F.CoverFoodCell[i] == 0 && F.Cap[i] == G2::kCap0[i]) ? 1 : 0;
		Over += F.Food[i] > F.Cap[i] ? 1 : 0;
		FoodMoved += F.Food[i] != FoodBefore[i] ? 1 : 0;
	}
	TestTrue(TEXT("지운 은신처의 셀은 1단계 용량으로 돌아간다"), Restored > 0);
	TestEqual(TEXT("먹이는 용량 이하"), Over, 0);
	TestEqual(TEXT("먹이는 바뀌지 않는다 (재생으로 다시 찬다)"), FoodMoved, 0);
	AddInfo(FString::Printf(TEXT("거울 격자 %d 셀 (겹침 %d, 셀 중심 %d), 겹침 장면 %d, 지운 은신처로 돌아간 셀 %d"), G2::kGw * G2::kGw, Cells, Centers,
							G2::kScenes, Restored));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWild2V3HuntGoldenTest,
	"AdaptiveEcosystem.Policy.V3.Wild2.HuntGolden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWild2V3HuntGoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	namespace G2 = EcoWorldV3::GoldenWild2;
	bool On[G2::kHuntM] = {};
	int64 Tot[4] = {};
	int32 Bad = 0;
	for (int32 t = 0; t < G2::kHuntT; ++t)
	{
		for (int32 m = 0; m < G2::kHuntM; ++m)
		{
			const int32 j = t * G2::kHuntM + m;
			const FHuntStep Hs = HuntUpdate(On[m], G2::kHuntRun[j] != 0, G2::kHuntCaught[j] != 0);
			const int32 Bits = (On[m] ? 1 : 0) | (Hs.bStart ? 2 : 0) | (Hs.bEnd ? 4 : 0) | (Hs.bSuccess ? 8 : 0) | (Hs.bOutside ? 16 : 0);
			Tot[0] += Hs.bStart ? 1 : 0;
			Tot[1] += Hs.bEnd ? 1 : 0;
			Tot[2] += Hs.bSuccess ? 1 : 0;
			Tot[3] += Hs.bOutside ? 1 : 0;
			if (Bits != G2::kHuntBits[j] && ++Bad <= 3)
			{
				AddError(FString::Printf(TEXT("스텝 %d 늑대 %d: 비트 %d, 파이썬 %d"), t, m, Bits, G2::kHuntBits[j]));
			}
		}
	}
	TestEqual(TEXT("사냥 열 스텝마다 = 파이썬 hunt_update"), Bad, 0);
	for (int32 k = 0; k < 4; ++k)
	{
		TestEqual(*FString::Printf(TEXT("합 %d"), k), Tot[k], G2::kHuntTotals[k]);
	}
	AddInfo(FString::Printf(TEXT("사냥 열 %d × %d: 시작 %lld 끝 %lld 성공 %lld 사냥 밖 %lld"), G2::kHuntM, G2::kHuntT, static_cast<long long>(Tot[0]),
							static_cast<long long>(Tot[1]), static_cast<long long>(Tot[2]), static_cast<long long>(Tot[3])));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWild2V3RunTest,
	"AdaptiveEcosystem.Policy.V3.Wild2.Run",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWild2V3RunTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	using namespace EcoWild2V3Test;
	// 1) 끄면 지금 그대로: 먹이 격자에 2단계 칸이 비고, 같은 시드의 두 세계(끔·끔)의 격자가 같다
	FReferenceWorld Off;
	Off.Init(RunConfig(false));
	TestTrue(TEXT("끄면 겹치는 셀·Cap0 칸이 없다"), Off.World.Food.CoverFoodCell.empty() && Off.World.Food.Cap0.empty());
	FReferenceWorld On;
	On.Init(RunConfig(true));
	const FFoodGrid& Fo = Off.World.Food;
	const FFoodGrid& Fn = On.World.Food;
	int32 CapBad = 0;
	int32 Cover = 0;
	for (size_t i = 0; i < Fn.Cap.size(); ++i)
	{
		const bool bCell = Fn.CoverFoodCell[i] != 0;
		Cover += bCell ? 1 : 0;
		CapBad += (Fn.Cap0[i] != Fo.Cap[i] || Fn.Cap[i] != (bCell ? Fo.Cap[i] * G2::kCapFrac : Fo.Cap[i]) || (Fn.CoverCell[i] != 0 && !bCell)) ? 1 : 0;
	}
	TestEqual(TEXT("켜면 은신처 셀 용량 = 끈 세계 용량 × 0.15, 밖은 같다 (같은 먹이 잡음)"), CapBad, 0);
	TestTrue(TEXT("은신처 셀이 있다"), Cover > 0);

	// 2) 1800 스텝: 사냥 셈의 맞춤 (기록만이라 두 세계 모두)
	for (FReferenceWorld* Ref : {&Off, &On})
	{
		FWorldState& W = Ref->World;
		int64 WolfCatches = 0;
		int64 OverCap = 0;
		for (int32 t = 0; t < 1800; ++t)
		{
			Step(W, Ref->Views.data(), Ref->NumHerbivores(), Ref->ThreatPtrs.data(), Ref->NumThreats());
			for (const FThreatAgent* A : Ref->ThreatPtrs)
			{
				WolfCatches += A->Last.Caught >= 0 ? 1 : 0;
			}
			for (size_t i = 0; i < W.Food.Food.size(); ++i)
			{
				OverCap += W.Food.Food[i] > W.Food.Cap[i] ? 1 : 0;
			}
		}
		int64 Starts = 0, Ends = 0, Success = 0, Outside = 0;
		for (int32 k = 0; k < kNumHuntKinds; ++k)
		{
			Starts += W.Stats.HuntStarts[k];
			Ends += W.Stats.HuntEnds[k];
			Success += W.Stats.HuntSuccess[k];
			Outside += W.Stats.HuntOutside[k];
		}
		int64 Ongoing = 0;
		for (const FThreatAgent* A : Ref->ThreatPtrs)
		{
			Ongoing += A->bHuntOn ? 1 : 0;
		}
		const TCHAR* Tag = Ref == &On ? TEXT("켬") : TEXT("끔");
		TestEqual(*FString::Printf(TEXT("%s: 성공 + 사냥 밖 = 늑대 포획"), Tag), Success + Outside, WolfCatches);
		TestEqual(*FString::Printf(TEXT("%s: 시작 − 끝 = 이어지는 사냥"), Tag), Starts - Ends, Ongoing);
		TestTrue(*FString::Printf(TEXT("%s: 사냥이 있다 (잠행·추격 모두)"), Tag),
				 W.Stats.HuntStarts[static_cast<int32>(EcoThreatV3::EThreatType::Stalker)] > 0
					 && W.Stats.HuntStarts[static_cast<int32>(EcoThreatV3::EThreatType::Chaser)] > 0 && Ends >= Success);
		TestEqual(*FString::Printf(TEXT("%s: 플레이어 칸은 늘 0"), Tag), W.Stats.HuntStarts[static_cast<int32>(EcoThreatV3::EThreatType::Player)], int64(0));
		TestEqual(*FString::Printf(TEXT("%s: 사슴·스텝 = 스텝 × 사슴 (리스폰 세계)"), Tag), W.Stats.LiveDeerSteps, int64(1800) * Ref->NumHerbivores());
		TestTrue(*FString::Printf(TEXT("%s: 은신처 안 사슴·스텝 ≤ 사슴·스텝"), Tag), W.Stats.ShelterDeerSteps <= W.Stats.LiveDeerSteps && W.Stats.ShelterDeerSteps > 0);
		TestTrue(*FString::Printf(TEXT("%s: 둘레 2 m 안 잡힘 ≤ 4 m 안 ≤ 잡힘"), Tag),
				 W.Stats.CaughtNearCover[0] <= W.Stats.CaughtNearCover[1] && W.Stats.CaughtNearCover[1] <= W.Stats.Caught);
		TestEqual(*FString::Printf(TEXT("%s: 먹이는 늘 용량 이하"), Tag), OverCap, int64(0));
		AddInfo(FString::Printf(TEXT("%s: 사냥 시작 %lld 끝 %lld 성공 %lld (%.0f%%) 사냥 밖 %lld · 은신처 안 사슴·스텝 %.1f%% · 잡힘 %lld (둘레 2 m 안 %lld, 4 m 안 %lld)"),
								Tag, static_cast<long long>(Starts), static_cast<long long>(Ends), static_cast<long long>(Success),
								Ends > 0 ? 100.0 * static_cast<double>(Success) / static_cast<double>(Ends) : 0.0, static_cast<long long>(Outside),
								100.0 * static_cast<double>(W.Stats.ShelterDeerSteps) / static_cast<double>(FMath::Max<int64>(W.Stats.LiveDeerSteps, 1)),
								static_cast<long long>(W.Stats.Caught), static_cast<long long>(W.Stats.CaughtNearCover[0]),
								static_cast<long long>(W.Stats.CaughtNearCover[1])));
	}
	return true;
}

#endif
