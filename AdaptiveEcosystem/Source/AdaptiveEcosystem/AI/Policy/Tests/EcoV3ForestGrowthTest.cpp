// 숲 자람 모드 자동화 시험 (10-27, EcoV3ForestGrowth.{h,cpp}·EcoV3ForestTree.{h,cpp} — 설계 Docs/RL_Policy/FOREST_GROWTH_MODE.md 1절).
//
// 묶음:
//   ForestGrowth.Plan      순수 계획: 기본 시간표(묘목 225·525·825·1125, 다 자람 375·675·975·1275 스텝), 단계 수·마지막 단계 그루, 값 자르기, 같은 씨 = 같은 자리
//                          (다른 씨 = 다른 자리), 자리 규칙(벽 4 m·은신처 원 + 2 m·다른 원판 + 3 m 밖, 크기 1.8~2.2, MakeLevelTree 와 같은 나무), 피할 원판·땅 없음·
//                          자리 없음, 묘목 크기 몫
//   ForestGrowth.Schedule  서브시스템 (시험 바닥 위 메마른 땅 무대): 묘목은 줄기로 세지 않음(충돌 끔·꼬리표 없음·세계 원판 0), 다 자람 스텝에서 세계에 들어감
//                          ('나무 0→3 (+3 −0)' 출처 forest_growth), 단계마다 환경 판 하나, 세계 원판 = 숲 자리 줄기 원판, 같은 씨 두 판 = 비트 단위로 같은 원판,
//                          Test.RemoveTrees 는 숲 나무를 지우지 않음, Test.AddTrees 는 숲 자리를 피함, 스냅숏 env.forest
//   ForestGrowth.Off       끔(기본): 액터·자리·강제 읽기·스냅숏 칸 없음 — 경계·프레임 함수가 아무것도 하지 않는다
//   ForestGrowth.Refuse    거부: 무대 없는 지역·환경 감시 끔·장애물 끔 → 아무것도 놓지 않음

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoV3ForestGrowth.h"
#include "../EcoV3ForestTree.h"
#include "../EcoWorldV3.h"
#include "../TreeLayoutV3.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "EcoTestWorld.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoV3ForestTestImpl
{
	using FSub = UEcoPolicyV3IntegratedSubsystem;
	using EcoObservationV3::FCoverInput;
	using EcoTreeLayoutV3::FTree;

	constexpr double kSize = EcoTreeLayoutV3::kStageSizeUnits;   // 60 단위 (120 m)
	constexpr double kTopZ = 250.0;
	const FVector kOrigin(0.0, 0.0, kTopZ);

	AStaticMeshActor* Floor(UWorld& World, double SideCm, double TopZ)
	{
		AStaticMeshActor* A = World.SpawnActor<AStaticMeshActor>(FVector(0.5 * SideCm, 0.5 * SideCm, TopZ - 50.0), FRotator::ZeroRotator);
		if (!A)
		{
			return nullptr;
		}
		A->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
		A->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
		A->SetActorScale3D(FVector(SideCm / 100.0 + 20.0, SideCm / 100.0 + 20.0, 1.0));
		A->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
		return A;
	}

	void SetCVar(const TCHAR* Name, const TCHAR* Value)
	{
		if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name))
		{
			V->Set(Value, ECVF_SetByCode);
		}
	}

	FString GetCVar(const TCHAR* Name)
	{
		const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name);
		return V ? V->GetString() : FString();
	}

	/** 작은 시험 시간표: 단계 3 그루, 첫 단계 1 초, 간격 4 초, 자람 2 초, 목표 7 (묘목 8·38·68, 다 자람 23·53·83 스텝). */
	EcoV3Forest::FSettings SmallSettings(int64 Seed)
	{
		EcoV3Forest::FSettings S;
		S.bOn = true;
		S.Region = TEXT("Barren");
		S.PerStage = 3;
		S.StartSeconds = 1.0;
		S.StageSeconds = 4.0;
		S.GrowSeconds = 2.0;
		S.Target = 7;
		S.Seed = Seed;
		return S;
	}

	/** 메마른 땅 무대 하나 (시험 바닥 위). */
	FEcoV3RegionContext* BarrenContext(FAutomationTestBase& Test, UWorld& World, int64 Seed, UEcoPolicyV3IntegratedSubsystem*& OutSub, bool bObstacles = true)
	{
		OutSub = World.GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
		if (!Test.TestNotNull(TEXT("통합 서브시스템"), OutSub))
		{
			return nullptr;
		}
		FEcoV3IntegratedSettings S;
		S.Seed = Seed;
		S.StageSizeUnits = kSize;
		S.bObstacles = bObstacles;
		S.WeatherBarren = GetCVar(TEXT("eco.IntegratedV3.WeatherBarren"));
		OutSub->ActivateForTest(S, /*bTerrain*/ false);
		const EcoWorldV3::FWorldConfig C = FSub::MakeRegionWorldConfig(S, 0, 16, 2, EcoWorldV3::QuadCovers(kSize, 6.0), FName(TEXT("Barren")));
		return OutSub->AddContext(FName(TEXT("Barren")), 0, kOrigin, C, 16, 2);
	}

	int32 CountForestActors(UWorld& World)
	{
		int32 N = 0;
		for (TActorIterator<AEcoV3ForestTree> It(&World); It; ++It)
		{
			++N;
		}
		return N;
	}

	/** 결정 스텝 하나 (처리기 순서 그대로 — 프레임 앞 묘목, 경계의 다 자람, 환경 넣기, 스텝 끝). */
	void Step(UEcoPolicyV3IntegratedSubsystem& Sub)
	{
		Sub.ForestPreActorTick();
		Sub.ForestStepBoundary();
		if (Sub.HasPendingEnvChange())
		{
			Sub.ApplyEnvChange({}, {});
		}
		Sub.FinishGlobalStep();
	}

	/** 자리 규칙 위반 수 (벽 4 m·은신처 원 + 2 m·자리끼리 + 3 m, 크기 범위). */
	int32 BadSpots(const TArray<EcoV3Forest::FSlot>& Slots, const std::vector<FCoverInput>& Covers)
	{
		const double Wall = EcoTreeLayoutV3::kWallClearM * 100.0 / EcoRepertoireV3::kUnitCm;
		const double Clear = EcoTreeLayoutV3::kCoverClearM * 100.0 / EcoRepertoireV3::kUnitCm;
		const double Gap = EcoV3Forest::kGapM * 100.0 / EcoRepertoireV3::kUnitCm;
		int32 Bad = 0;
		for (int32 k = 0; k < Slots.Num(); ++k)
		{
			const FTree& T = Slots[k].Tree;
			Bad += (T.X >= Wall + T.R - 1e-9 && T.Y >= Wall + T.R - 1e-9 && T.X <= kSize - Wall - T.R + 1e-9 && T.Y <= kSize - Wall - T.R + 1e-9) ? 0 : 1;
			for (const FCoverInput& Cv : Covers)
			{
				Bad += FMath::Sqrt(FMath::Square(T.X - Cv.X) + FMath::Square(T.Y - Cv.Y)) >= Cv.Radius + Clear + T.R - 1e-9 ? 0 : 1;
			}
			for (int32 j = k + 1; j < Slots.Num(); ++j)
			{
				const FTree& U = Slots[j].Tree;
				Bad += FMath::Sqrt(FMath::Square(T.X - U.X) + FMath::Square(T.Y - U.Y)) >= T.R + U.R + Gap - 1e-9 ? 0 : 1;
			}
			Bad += (T.Scale >= EcoTreeLayoutV3::kScaleLo && T.Scale < EcoTreeLayoutV3::kScaleHi) ? 0 : 1;
			const FTree M = FSub::MakeLevelTree(T.X, T.Y, T.Scale, T.YawDeg);
			Bad += (M.R == T.R && M.PivotX == T.PivotX && M.PivotY == T.PivotY) ? 0 : 1;
		}
		return Bad;
	}

	bool SameSlots(const TArray<EcoV3Forest::FSlot>& A, const TArray<EcoV3Forest::FSlot>& B)
	{
		if (A.Num() != B.Num())
		{
			return false;
		}
		for (int32 i = 0; i < A.Num(); ++i)
		{
			const FTree& T = A[i].Tree;
			const FTree& U = B[i].Tree;
			if (T.X != U.X || T.Y != U.Y || T.R != U.R || T.YawDeg != U.YawDeg || T.Scale != U.Scale || A[i].GroundMinZ != B[i].GroundMinZ)
			{
				return false;
			}
		}
		return true;
	}
}

// -----------------------------------------------------------------------------
// 순수 계획
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3ForestPlanTest,
	"AdaptiveEcosystem.Policy.V3.ForestGrowth.Plan",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ForestPlanTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3ForestTestImpl;
	// 1. 기본 시간표
	const EcoV3Forest::FSettings D;
	TestTrue(TEXT("기본: 끔 · 메마른 땅 · 6 그루 × 40 초 · 자람 20 초 · 목표 24 · 첫 단계 30 초 · 씨 -1 · 묘목 0.15"),
			 !D.bOn && D.Region == FName(TEXT("Barren")) && D.PerStage == 6 && D.StageSeconds == 40.0 && D.GrowSeconds == 20.0 && D.Target == 24
				 && D.StartSeconds == 30.0 && D.Seed == -1 && D.SaplingFrac == 0.15);
	const int64 Sprout[4] = {225, 525, 825, 1125};
	const int64 Mature[4] = {375, 675, 975, 1275};
	bool bSchedule = EcoV3Forest::NumStages(D, 24) == 4;
	for (int32 k = 0; k < 4; ++k)
	{
		bSchedule = bSchedule && EcoV3Forest::SproutStep(D, k) == Sprout[k] && EcoV3Forest::MatureStep(D, k) == Mature[k];
	}
	TestTrue(TEXT("묘목 30·70·110·150 초 = 스텝 225·525·825·1125, 다 자람 50·90·130·170 초 = 375·675·975·1275, 단계 4"), bSchedule);
	TestTrue(TEXT("단계 수 ⌈놓은 수 ÷ 6⌉: 22 → 4 · 6 → 1 · 0 → 0, 자리 23 → 단계 3"),
			 EcoV3Forest::NumStages(D, 22) == 4 && EcoV3Forest::NumStages(D, 6) == 1 && EcoV3Forest::NumStages(D, 0) == 0 && EcoV3Forest::StageOfSlot(D, 23) == 3);
	TestTrue(TEXT("초 → 스텝 반올림 (1 초 = 7.5 → 8, 0.5 초 = 3.75 → 4)"), EcoV3Forest::SecondsToSteps(1.0) == 8 && EcoV3Forest::SecondsToSteps(0.5) == 4);
	{
		EcoV3Forest::FSettings Bad;
		Bad.PerStage = 0;
		Bad.Target = 500;
		Bad.GrowSeconds = 0.1;
		Bad.StageSeconds = -3.0;
		Bad.SaplingFrac = 7.0;
		Bad.Region = NAME_None;
		const EcoV3Forest::FSettings S = EcoV3Forest::Sanitize(Bad);
		TestTrue(TEXT("값 자르기: 단계 그루 1 · 목표 64 · 자람 1 초 · 간격 1 초 · 묘목 몫 1 · 지역 Barren"),
				 S.PerStage == 1 && S.Target == 64 && S.GrowSeconds == 1.0 && S.StageSeconds == 1.0 && S.SaplingFrac == 1.0 && S.Region == FName(TEXT("Barren")));
	}

	// 2. 자리: 같은 씨 = 같은 자리, 규칙 지킴, 목표 수
	const std::vector<FCoverInput> Covers = EcoWorldV3::QuadCovers(kSize, 6.0);
	auto Make = [](double X, double Y, double Scale, double Yaw) { return FSub::MakeLevelTree(X, Y, Scale, Yaw); };
	auto Flat = [](const FTree&, double& OutMinZ) { OutMinZ = 123.0; return true; };
	TArray<EcoV3Forest::FSlot> A, B, C;
	int32 MissA = -1, MissB = -1, MissC = -1;
	EcoV3Forest::PlanSlots(24, kSize, Covers, {}, EcoV3Forest::RngState(20010, 0), Make, Flat, A, MissA);
	EcoV3Forest::PlanSlots(24, kSize, Covers, {}, EcoV3Forest::RngState(20010, 0), Make, Flat, B, MissB);
	EcoV3Forest::PlanSlots(24, kSize, Covers, {}, EcoV3Forest::RngState(20011, 0), Make, Flat, C, MissC);
	TestTrue(TEXT("목표 24 그루 모두 (못 찾음 0)"), A.Num() == 24 && MissA == 0);
	TestTrue(TEXT("같은 씨 = 비트 단위로 같은 자리"), SameSlots(A, B));
	TestFalse(TEXT("다른 씨 = 다른 자리"), SameSlots(A, C));
	TestEqual(TEXT("자리 규칙 (벽 4 m·은신처 + 2 m·자리끼리 + 3 m·크기 1.8~2.2·MakeLevelTree) 위반 0"), BadSpots(A, Covers), 0);
	TestTrue(TEXT("순번 0..23 · 땅 높이"), A[0].Index == 0 && A.Last().Index == 23 && A[5].GroundMinZ == 123.0);
	{
		// 다른 지역 색인 = 다른 자리
		TArray<EcoV3Forest::FSlot> R2;
		int32 M2 = 0;
		EcoV3Forest::PlanSlots(24, kSize, Covers, {}, EcoV3Forest::RngState(20010, 1), Make, Flat, R2, M2);
		TestFalse(TEXT("다른 지역 색인 = 다른 자리"), SameSlots(A, R2));
	}

	// 3. 피할 원판: 무대 가운데 큰 원판 (반지름 10) 둘레 + 3 m 밖
	{
		TArray<EcoV3Forest::FSlot> P;
		int32 M = 0;
		EcoV3Forest::PlanSlots(12, kSize, Covers, {30.0, 30.0, 10.0}, EcoV3Forest::RngState(7, 0), Make, Flat, P, M);
		int32 Inside = 0;
		for (const EcoV3Forest::FSlot& S : P)
		{
			Inside += FMath::Sqrt(FMath::Square(S.Tree.X - 30.0) + FMath::Square(S.Tree.Y - 30.0)) < 10.0 + S.Tree.R + 1.5 - 1e-9 ? 1 : 0;
		}
		TestTrue(TEXT("피할 원판 둘레 + 3 m 안 자리 0 (12 그루 모두)"), Inside == 0 && P.Num() == 12);
	}
	// 4. 땅이 없는 자리 (X < 30) 는 고르지 않는다
	{
		TArray<EcoV3Forest::FSlot> P;
		int32 M = 0;
		EcoV3Forest::PlanSlots(8, kSize, Covers, {}, EcoV3Forest::RngState(9, 0), Make,
							   [](const FTree& T, double& OutMinZ) { OutMinZ = 0.0; return T.X >= 30.0; }, P, M);
		bool bAll = P.Num() == 8;
		for (const EcoV3Forest::FSlot& S : P)
		{
			bAll = bAll && S.Tree.X >= 30.0;
		}
		TestTrue(TEXT("땅 검사를 통과한 자리만 (8 그루 모두 X ≥ 30)"), bAll);
	}
	// 5. 자리가 없으면 빼고 기록 (무대를 다 덮는 은신처)
	{
		TArray<EcoV3Forest::FSlot> P;
		int32 M = 0;
		EcoV3Forest::PlanSlots(5, kSize, {{30.0, 30.0, 60.0}}, {}, EcoV3Forest::RngState(1, 0), Make, Flat, P, M);
		TestTrue(TEXT("자리 없음 → 0 그루 · 못 찾음 5"), P.Num() == 0 && M == 5);
	}
	// 6. 묘목 크기 몫 (그리기만)
	TestTrue(TEXT("묘목 몫: 처음 0.15 · 끝 1 · 가운데 0.575 · 넘으면 1"),
			 FMath::IsNearlyEqual(EcoV3Forest::GrowFraction(0.0, 20.0, 0.15), 0.15) && FMath::IsNearlyEqual(EcoV3Forest::GrowFraction(20.0, 20.0, 0.15), 1.0)
				 && FMath::IsNearlyEqual(EcoV3Forest::GrowFraction(10.0, 20.0, 0.15), 0.575) && FMath::IsNearlyEqual(EcoV3Forest::GrowFraction(99.0, 20.0, 0.15), 1.0));
	return true;
}

// -----------------------------------------------------------------------------
// 서브시스템: 묘목 → 다 자람 → 세계
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3ForestScheduleTest,
	"AdaptiveEcosystem.Policy.V3.ForestGrowth.Schedule",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ForestScheduleTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3ForestTestImpl;
	// 시험 목표 7 < eco.IntegratedV3.BigTrees 10 — 계획 때 경고 한 줄 (두 판)
	AddExpectedMessagePlain(TEXT("숲 자람만으로는"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 2);
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World) || !TestNotNull(TEXT("바닥"), Floor(*W.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ)))
	{
		return false;
	}
	UWorld& World = *W.World;
	UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
	FEcoV3RegionContext* Ctx = BarrenContext(*this, World, 39100, Sub);
	if (!Ctx)
	{
		return false;
	}
	FString Why;
	if (!TestTrue(TEXT("숲 켬 (메마른 땅)"), Sub->StartForestForTest(SmallSettings(4242), Why)))
	{
		AddError(Why);
		return false;
	}
	TestEqual(TEXT("자리 7 (목표)"), Sub->GetForestSlots().Num(), 7);
	TestEqual(TEXT("자리 규칙 위반 0 (은신처·벽·틈·땅)"), BadSpots(Sub->GetForestSlots(), Ctx->Sim.Config.Covers), 0);
	TestTrue(TEXT("Play 시작: 액터 없음 · 세계 원판 0"), CountForestActors(World) == 0 && Ctx->Sim.Config.Obstacles.Num() == 0);

	struct FSeen
	{
		int64 Step;
		FString Detail;
		FString Source;
	};
	TArray<FSeen> Seen;
	bool bSaplingBlocks = false;
	bool bSaplingChecked = false;
	int32 Revisions = 0;
	for (int64 t = 0; t <= 100; ++t)
	{
		const int32 Before = Sub->GetEnvChanges().Num();
		Step(*Sub);
		for (int32 i = Before; i < Sub->GetEnvChanges().Num(); ++i)
		{
			Seen.Add({Sub->GetEnvChanges()[i].Step, Sub->GetEnvChanges()[i].Detail, Sub->GetEnvChanges()[i].Source});
		}
		if (t == 10)
		{
			// 첫 단계 묘목 (8 스텝에 돋음, 23 스텝에 다 자람): 줄기로 세지 않는다 — 아무것도 막지 않는다
			TArray<FVector> Trunks;
			FSub::GatherLevelTrunks(World, Trunks);
			int32 Collide = 0;
			int32 TrunkTag = 0;
			for (TActorIterator<AEcoV3ForestTree> It(&World); It; ++It)
			{
				Collide += It->TrunkCollisionOn() ? 1 : 0;
				TrunkTag += It->ActorHasTag(FSub::LevelTrunkTag()) ? 1 : 0;
			}
			bSaplingChecked = true;
			bSaplingBlocks = !Trunks.IsEmpty() || Collide > 0 || TrunkTag > 0;
			TestTrue(TEXT("묘목 3 · 세계 원판 0 · 대기 변화 없음 · 숲 줄 묘목 3"), CountForestActors(World) == 3 && Ctx->Sim.Config.Obstacles.Num() == 0
																	   && !Sub->HasPendingEnvChange() && Sub->ForestSaplingCount() == 3);
			TestTrue(TEXT("자라는 중 · 다음 다 자람 23"), Sub->IsForestGrowing() && Sub->ForestNextMatureStep() == 23);
		}
		if (t == 23)
		{
			TestEqual(TEXT("23 스텝 경계에서 세계 원판 3"), Ctx->Sim.Config.Obstacles.Num(), 3);
		}
		if (t == 22)
		{
			TestEqual(TEXT("22 스텝까지 세계 원판 0"), Ctx->Sim.Config.Obstacles.Num(), 0);
		}
	}
	Revisions = Sub->GetEnvRevision();
	TestTrue(TEXT("묘목은 줄기가 아니다 (충돌 끔·꼬리표 없음·GatherLevelTrunks 0)"), bSaplingChecked && !bSaplingBlocks);
	if (TestEqual(TEXT("단계마다 환경 판 하나 (3)"), Seen.Num(), 3))
	{
		TestTrue(TEXT("23·53·83 스텝 · '나무 0→3 (+3 −0)'·'3→6'·'6→7' · 출처 forest_growth"),
				 Seen[0].Step == 23 && Seen[1].Step == 53 && Seen[2].Step == 83 && Seen[0].Detail == TEXT("나무 0→3 (+3 −0)") && Seen[1].Detail == TEXT("나무 3→6 (+3 −0)")
					 && Seen[2].Detail == TEXT("나무 6→7 (+1 −0)") && Seen[0].Source == TEXT("forest_growth") && Seen[2].Source == TEXT("forest_growth"));
	}
	TestEqual(TEXT("환경 판 3"), Revisions, 3);
	TestTrue(TEXT("다 자람 7 · 묘목 0 · 다 자랐다"), Sub->ForestMatureCount() == 7 && Sub->ForestSaplingCount() == 0 && !Sub->IsForestGrowing() && Sub->ForestNextMatureStep() == -1);
	// 세계 원판 = 숲 자리 줄기 원판 ((x, y, r) 순 — 액터 충돌 상자에서 읽은 값이 계획 값과 1e-6 안)
	{
		const std::vector<double>& Discs = Ctx->Sim.Config.Obstacles.Discs;
		int32 Matched = 0;
		for (const EcoV3Forest::FSlot& S : Sub->GetForestSlots())
		{
			for (size_t k = 0; k + 2 < Discs.size(); k += 3)
			{
				Matched += (FMath::Abs(Discs[k] - S.Tree.X) < 1e-6 && FMath::Abs(Discs[k + 1] - S.Tree.Y) < 1e-6 && FMath::Abs(Discs[k + 2] - S.Tree.R) < 1e-6) ? 1 : 0;
			}
		}
		TestEqual(TEXT("세계 원판 7 = 숲 자리 7 (액터 줄기 막이 충돌 상자 → 원판)"), Matched, 7);
		int32 Mature = 0;
		for (TActorIterator<AEcoV3ForestTree> It(&World); It; ++It)
		{
			Mature += (It->IsMature() && It->TrunkCollisionOn() && It->ActorHasTag(FSub::LevelTrunkTag()) && It->TrunkHash() != 0) ? 1 : 0;
		}
		TestEqual(TEXT("다 자란 액터 7 (줄기 충돌 켬·꼬리표 EcoV3Trunk·변환 지문)"), Mature, 7);
	}
	// 같은 씨 두 판 = 비트 단위로 같은 세계 원판
	{
		EcoTest::FScopedTestWorld W2;
		UEcoPolicyV3IntegratedSubsystem* Sub2 = nullptr;
		FEcoV3RegionContext* Ctx2 = W2.World && Floor(*W2.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ) ? BarrenContext(*this, *W2.World, 39100, Sub2) : nullptr;
		FString Why2;
		if (TestNotNull(TEXT("시험 월드 2"), Ctx2) && TestTrue(TEXT("숲 켬 2"), Sub2->StartForestForTest(SmallSettings(4242), Why2)))
		{
			for (int64 t = 0; t <= 100; ++t)
			{
				Step(*Sub2);
			}
			TestTrue(TEXT("같은 씨 = 같은 자리·같은 세계 원판 (비트 단위)"),
					 SameSlots(Sub->GetForestSlots(), Sub2->GetForestSlots()) && Ctx2->Sim.Config.Obstacles.Discs == Ctx->Sim.Config.Obstacles.Discs);
		}
	}
	// Test.RemoveTrees 는 숲 나무를 지우지 않는다 · Test.AddTrees 는 숲 자리를 피한다
	{
		FString Message;
		TestEqual(TEXT("Test.RemoveTrees — 숲 나무는 지우지 않음 (0 짝)"), Sub->TestRemoveTrees(TEXT("Barren"), 3, Message), 0);
		TestEqual(TEXT("숲 나무 7 그대로"), CountForestActors(World), 7);
		TestEqual(TEXT("Test.AddTrees 2"), Sub->TestAddTrees(TEXT("Barren"), 2, TOptional<int32>(5), Message), 2);
		Sub->PollEnvironment(true);
		Sub->ApplyEnvChange({}, {});
		const std::vector<double>& Discs = Ctx->Sim.Config.Obstacles.Discs;
		int32 Close = 0;
		for (size_t k = 0; k + 2 < Discs.size(); k += 3)
		{
			for (size_t j = k + 3; j + 2 < Discs.size(); j += 3)
			{
				Close += FMath::Sqrt(FMath::Square(Discs[k] - Discs[j]) + FMath::Square(Discs[k + 1] - Discs[j + 1])) < Discs[k + 2] + Discs[j + 2] + 1.5 - 1e-9 ? 1 : 0;
			}
		}
		TestTrue(TEXT("세계 원판 9 · 줄기끼리 3 m 안 0 (시험용 나무가 숲 자리를 피함)"), Discs.size() == 27 && Close == 0);
	}
	// 스냅숏 env.forest
	{
		const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"), TEXT("EcoV3ForestSnapshot.json")));
		ON_SCOPE_EXIT
		{
			IFileManager::Get().Delete(*Path, false, true, true);
		};
		if (TestTrue(TEXT("스냅숏 씀"), Sub->ExportSnapshot(Path, TEXT("시험"), TEXT("console"))))
		{
			FString Text;
			TSharedPtr<FJsonObject> Root;
			const TSharedPtr<FJsonObject>* Env = nullptr;
			const TSharedPtr<FJsonObject>* Forest = nullptr;
			const bool bOk = FFileHelper::LoadFileToString(Text, *Path) && FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) && Root.IsValid()
							 && Root->TryGetObjectField(TEXT("env"), Env) && (*Env)->TryGetObjectField(TEXT("forest"), Forest);
			TestTrue(TEXT("env.forest: on · Barren · 목표 7 · 놓음 7 · 다 자람 7 · done · 다음 -1"),
					 bOk && (*Forest)->GetBoolField(TEXT("on")) && (*Forest)->GetStringField(TEXT("region")) == TEXT("Barren")
						 && static_cast<int32>((*Forest)->GetNumberField(TEXT("target"))) == 7 && static_cast<int32>((*Forest)->GetNumberField(TEXT("planned"))) == 7
						 && static_cast<int32>((*Forest)->GetNumberField(TEXT("mature"))) == 7 && (*Forest)->GetBoolField(TEXT("done"))
						 && static_cast<int64>((*Forest)->GetNumberField(TEXT("next_mature_step"))) == -1);
			TestTrue(TEXT("env.changes 출처 forest_growth"), bOk && (*Env)->GetArrayField(TEXT("changes"))[0]->AsObject()->GetStringField(TEXT("source")) == TEXT("forest_growth"));
		}
	}
	TestEqual(TEXT("ForestInfo 줄 = 1 + 자리 수"), Sub->ForestInfoLines().Num(), 1 + 7);
	return true;
}

// -----------------------------------------------------------------------------
// 끔 (기본) · 거부
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3ForestOffTest,
	"AdaptiveEcosystem.Policy.V3.ForestGrowth.Off",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ForestOffTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3ForestTestImpl;
	TestFalse(TEXT("콘솔 기본: 끔 (eco.IntegratedV3.ForestGrowth 0)"), FSub::ForestSettingsFromConsole().bOn);
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World) || !TestNotNull(TEXT("바닥"), Floor(*W.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ)))
	{
		return false;
	}
	UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
	FEcoV3RegionContext* Ctx = BarrenContext(*this, *W.World, 39200, Sub);
	if (!Ctx)
	{
		return false;
	}
	for (int64 t = 0; t <= 400; ++t)
	{
		Step(*Sub);
	}
	TestTrue(TEXT("끔: 액터 0 · 자리 0 · 대기 변화 없음 · 환경 판 0 · 세계 원판 0"), CountForestActors(*W.World) == 0 && Sub->GetForestSlots().Num() == 0
																	   && !Sub->HasPendingEnvChange() && Sub->GetEnvRevision() == 0 && Ctx->Sim.Config.Obstacles.Num() == 0);
	TestFalse(TEXT("끔: 자라지 않음 · '진행 중' 아님"), Sub->IsForestOn() || Sub->IsForestGrowing() || Sub->IsLevelChangeHeld());
	const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"), TEXT("EcoV3ForestOff.json")));
	ON_SCOPE_EXIT
	{
		IFileManager::Get().Delete(*Path, false, true, true);
	};
	FString Text;
	TSharedPtr<FJsonObject> Root;
	const TSharedPtr<FJsonObject>* Env = nullptr;
	TestTrue(TEXT("끔: 스냅숏 env.forest 없음"), Sub->ExportSnapshot(Path, TEXT("시험"), TEXT("console")) && FFileHelper::LoadFileToString(Text, *Path)
													 && FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) && Root.IsValid()
													 && Root->TryGetObjectField(TEXT("env"), Env) && !(*Env)->HasField(TEXT("forest")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3ForestRefuseTest,
	"AdaptiveEcosystem.Policy.V3.ForestGrowth.Refuse",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ForestRefuseTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3ForestTestImpl;
	AddExpectedMessagePlain(TEXT("숲 자람 | 거부"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 3);
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World) || !TestNotNull(TEXT("바닥"), Floor(*W.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ)))
	{
		return false;
	}
	UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
	if (!BarrenContext(*this, *W.World, 39300, Sub))
	{
		return false;
	}
	FString Why;
	EcoV3Forest::FSettings S = SmallSettings(1);
	S.Region = TEXT("Nowhere");
	TestFalse(TEXT("무대 없는 지역 → 거부"), Sub->StartForestForTest(S, Why));
	TestTrue(TEXT("까닭: v3 무대가 없다 · 있는 지역 Barren"), Why.Contains(TEXT("v3 무대가 없다")) && Why.Contains(TEXT("Barren")));
	{
		const FString Saved = GetCVar(TEXT("eco.IntegratedV3.EnvWatch"));
		ON_SCOPE_EXIT
		{
			SetCVar(TEXT("eco.IntegratedV3.EnvWatch"), *Saved);
		};
		SetCVar(TEXT("eco.IntegratedV3.EnvWatch"), TEXT("0"));
		TestFalse(TEXT("환경 감시 끔 → 거부"), Sub->StartForestForTest(SmallSettings(1), Why));
		TestTrue(TEXT("까닭: 환경 감시"), Why.Contains(TEXT("EnvWatch 0")));
	}
	TestTrue(TEXT("거부 뒤 액터·자리 없음"), CountForestActors(*W.World) == 0 && !Sub->IsForestOn());
	{
		EcoTest::FScopedTestWorld W2;
		UEcoPolicyV3IntegratedSubsystem* Sub2 = nullptr;
		if (W2.World && BarrenContext(*this, *W2.World, 39301, Sub2, /*bObstacles*/ false))
		{
			TestFalse(TEXT("장애물 끔 → 거부"), Sub2->StartForestForTest(SmallSettings(1), Why));
			TestTrue(TEXT("까닭: 장애물"), Why.Contains(TEXT("Obstacles 0")));
		}
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
