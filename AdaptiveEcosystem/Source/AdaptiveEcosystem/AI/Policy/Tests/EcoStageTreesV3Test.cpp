// 무대 나무 자동화 시험 (10-17 사용자 '그럼 그냥 우리 쪽 테스트 레벨에 저 사람이 만든 장애물들 적절히 배치해 봐' — herbivore_rl/results/v3/wild2/trees/README.md).
// 배치 표 TreeLayoutV3.h (파이썬 make_tree_layout.py 가 만든다)와 통합 모드의 실행 중 나무 놓기(EcoPolicyV3IntegratedSubsystem 'StageTrees')를 본다.
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.StageTrees"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 묶음:
//   StageTrees.Layout       표: 숲 24·고지 9·메마른 땅 0, 반지름 = 밑동 꼭짓점 반경 × 크기 ÷ 200 (비트 단위), 크기 범위, 벽 4 m·은신처 원 + 2 m·빈터 22 m·
//                           늑대 시작 모서리 3 m 밖, 줄기 중심 간격·틈 3 m, (x, y, r) 순, 기준점 ↔ 줄기 거리, 원판 목록 = 표, 다른 크기·모르는 지역 = 표 없음,
//                           기본값·콘솔 기본값 켬
//   StageTrees.StartPoints  시작 자리 계획(PlanStage): 숲·고지 사슴 128·늑대 4 가 줄기 원판(반지름 + 몸) 안에 하나도 없다, 늑대 자리는 나무 없을 때와 같다
//                           (표가 늑대 시작 모서리를 비워 둔다), 메마른 땅·다른 크기 무대·나무 끔은 나무 없을 때와 같은 자리
//   StageTrees.Spawn        시험 월드 바닥 위 숲 무대에 놓기: 24 그루, 메시 = 팀 Beech_Tree, 충돌 없음·그림자 켬·꼬리표, 자리 = 기준점·Z = 바닥 − 10 cm,
//                           방위·크기 = 표, 원판 = 표. 레벨 읽기는 뺄 액터로 주면 0, 안 주면 '충돌 없음' 으로만 센다(원판으로 두 번 세지 않음).
//                           은신처를 나무 위로 옮기면 그 나무만 뺀다. 레벨 원판과 합치기 = (x, y, r) 순·나무 표시
//   StageTrees.LevelActors  (10-18) 레벨 나무 놓기 명령(EcoV3PlaceTreesCommandlet)과 같은 나무 액터(충돌 없음) + 줄기 막이(엔진 원기둥, BlockAll, 나무에 붙음)를
//                           시험 바닥 위 숲 무대에 놓는다: 자리 = 실행 중 나무, 레벨 읽기 원판 = 표(비트 단위 — 맞추기 없이도 0.01 cm 안), 나무 메시는 충돌 없음,
//                           시작 자리 계획이 같은 원판을 피하고 실행 중 나무 계획과 같은 자리, 팀 이동 제약은 줄기만 막고 잎 아래는 막지 않음,
//                           나무를 옮기면 줄기 막이가 따라가고 표와 다른 줄기로 센다

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "../TreeLayoutV3.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EcoTestWorld.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "PhysicsEngine/BodySetup.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoStageTreesV3Test
{
	using EcoTreeLayoutV3::FStageTrees;
	using EcoTreeLayoutV3::FTree;

	constexpr double kTreeMPerUnit = EcoRepertoireV3::kUnitCm / 100.0;

	const FStageTrees* TreeTable(const char* Region)
	{
		for (const FStageTrees& St : EcoTreeLayoutV3::kStages)
		{
			if (FCStringAnsi::Strcmp(St.Region, Region) == 0)
			{
				return &St;
			}
		}
		return nullptr;
	}

	/** 바닥 상자 (윗면 Z = TopZ, 무대 원점 (0, 0) 의 한 변 SideCm 정사각을 덮는다). */
	AStaticMeshActor* TreeFloor(UWorld& World, double SideCm, double TopZ)
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

	/** 레벨 나무 놓기 명령과 같은 설정의 액터 (시험 월드라 움직임 가능 — 미루어 놓고 메시·충돌을 넣은 뒤 등록). bTrunk = 줄기 막이. */
	AStaticMeshActor* LevelTreeActor(UWorld& World, const FTransform& Xf, UStaticMesh& Mesh, bool bTrunk)
	{
		FActorSpawnParameters P;
		P.bDeferConstruction = true;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AStaticMeshActor* A = World.SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), Xf, P);
		if (!A)
		{
			return nullptr;
		}
		UStaticMeshComponent* C = A->GetStaticMeshComponent();
		C->SetMobility(EComponentMobility::Movable);
		C->SetStaticMesh(&Mesh);
		C->SetCollisionProfileName(bTrunk ? UCollisionProfile::BlockAll_ProfileName : UCollisionProfile::NoCollision_ProfileName);
		C->SetCastShadow(!bTrunk);
		C->SetHiddenInGame(bTrunk);
		A->FinishSpawning(Xf);
		return A;
	}

	/** 평평한 땅 (Z = 0) 지면 검사 대역. */
	bool TreeFlatGround(const FVector& Hint, FVector& Out)
	{
		Out = FVector(Hint.X, Hint.Y, 0.0);
		return true;
	}

	/** 계획 자리 가운데 줄기 원판(반지름 + 몸) 안인 수 (세계 원판 안 판정과 같은 식). */
	int32 TreeStartsInTrunks(const FEcoV3StagePlan& Plan, const std::vector<double>& Discs)
	{
		const FVector O = Plan.OriginCm();
		int32 N = 0;
		for (const TArray<FVector>* Pts : {&Plan.DeerPoints, &Plan.WolfPoints})
		{
			for (const FVector& P : *Pts)
			{
				N += EcoThreatV3::InsideAnyObstacle((P.X - O.X) / EcoRepertoireV3::kUnitCm, (P.Y - O.Y) / EcoRepertoireV3::kUnitCm, Discs.data(),
													static_cast<std::int32_t>(Discs.size() / 3), EcoWorldV3::FObstacleConfig().BodyR)
						 ? 1
						 : 0;
			}
		}
		return N;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoStageTreesV3LayoutTest,
	"AdaptiveEcosystem.Policy.V3.StageTrees.Layout",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoStageTreesV3LayoutTest::RunTest(const FString& Parameters)
{
	using namespace EcoStageTreesV3Test;
	using namespace EcoTreeLayoutV3;
	const FStageTrees* Forest = TreeTable("Forest");
	const FStageTrees* Highland = TreeTable("Highland");
	const FStageTrees* Barren = TreeTable("Barren");
	if (!TestNotNull(TEXT("숲 표"), Forest) || !TestNotNull(TEXT("고지 표"), Highland) || !TestNotNull(TEXT("메마른 땅 표"), Barren))
	{
		return false;
	}
	TestEqual(TEXT("숲 24 그루"), Forest->Num, 24);
	TestEqual(TEXT("고지 9 그루"), Highland->Num, 9);
	TestEqual(TEXT("메마른 땅 0 그루"), Barren->Num, 0);
	TestTrue(TEXT("메마른 땅 표는 비었다"), Barren->Trees == nullptr);
	TestEqual(TEXT("표 무대 한 변 = 60 단위 (120 m)"), kStageSizeUnits, 60.0);

	const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(kStageSizeUnits, 6.0);
	const double C = 0.5 * kStageSizeUnits;
	const double K = 0.4 * kStageSizeUnits;
	const double Wolves[4][2] = {{C + K, C + K}, {C - K, C - K}, {C + K, C - K}, {C - K, C + K}};
	for (const FStageTrees* St : {Forest, Highland})
	{
		const FString Name = UTF8_TO_TCHAR(St->Region);
		int32 BadR = 0, BadScale = 0, BadWall = 0, BadCover = 0, BadMeadow = 0, BadWolf = 0, BadGap = 0, BadOrder = 0, BadPivot = 0;
		double MinGapM = 1e30;
		for (int32 i = 0; i < St->Num; ++i)
		{
			const FTree& T = St->Trees[i];
			BadR += T.R == kTrunkRadiusMeshCm * T.Scale / EcoRepertoireV3::kUnitCm ? 0 : 1;   // 파이썬과 같은 식·같은 순서 (비트 단위)
			BadScale += (T.Scale >= kScaleLo && T.Scale <= kScaleHi) ? 0 : 1;
			const double E = kWallClearM / kTreeMPerUnit + T.R;
			BadWall += (T.X >= E && T.Y >= E && T.X <= kStageSizeUnits - E && T.Y <= kStageSizeUnits - E) ? 0 : 1;
			for (const EcoObservationV3::FCoverInput& Cv : Covers)
			{
				BadCover += FMath::Sqrt(FMath::Square(T.X - Cv.X) + FMath::Square(T.Y - Cv.Y)) >= Cv.Radius + kCoverClearM / kTreeMPerUnit + T.R ? 0 : 1;
			}
			BadMeadow += FMath::Sqrt(FMath::Square(T.X - C) + FMath::Square(T.Y - C)) >= kMeadowRadiusM / kTreeMPerUnit + T.R ? 0 : 1;
			for (const auto& W : Wolves)
			{
				BadWolf += FMath::Sqrt(FMath::Square(T.X - W[0]) + FMath::Square(T.Y - W[1])) >= kWolfKeepM / kTreeMPerUnit + T.R ? 0 : 1;
			}
			// 기준점 ↔ 줄기 중심 = 크기 × |메시 기준점 → 밑동 중심| (방위만 돌린다)
			const double Off = T.Scale * FMath::Sqrt(FMath::Square(kPivotOffsetMeshCmX) + FMath::Square(kPivotOffsetMeshCmY)) / EcoRepertoireV3::kUnitCm;
			BadPivot += FMath::Abs(FMath::Sqrt(FMath::Square(T.X - T.PivotX) + FMath::Square(T.Y - T.PivotY)) - Off) < 1e-5 ? 0 : 1;
			for (int32 j = i + 1; j < St->Num; ++j)
			{
				const FTree& U = St->Trees[j];
				const double D = FMath::Sqrt(FMath::Square(T.X - U.X) + FMath::Square(T.Y - U.Y));
				BadGap += (D * kTreeMPerUnit >= St->MinSpacingM && (D - T.R - U.R) * kTreeMPerUnit >= 3.0) ? 0 : 1;
				MinGapM = FMath::Min(MinGapM, (D - T.R - U.R) * kTreeMPerUnit);
			}
			if (i > 0)
			{
				const FTree& P = St->Trees[i - 1];
				BadOrder += (P.X < T.X || (P.X == T.X && (P.Y < T.Y || (P.Y == T.Y && P.R <= T.R)))) ? 0 : 1;
			}
		}
		AddInfo(FString::Printf(TEXT("%s: %d 그루, 줄기 중심 간격 %.1f m 밖, 가장 좁은 줄기 사이 틈 %.2f m"), *Name, St->Num, St->MinSpacingM, MinGapM));
		TestEqual(*(Name + TEXT(": 반지름 = 밑동 꼭짓점 반경 × 크기 ÷ 200")), BadR, 0);
		TestEqual(*(Name + TEXT(": 크기 1.8~2.2")), BadScale, 0);
		TestEqual(*(Name + TEXT(": 줄기 가장자리가 벽에서 4 m 밖")), BadWall, 0);
		TestEqual(*(Name + TEXT(": 줄기 가장자리가 은신처 원 + 2 m 밖")), BadCover, 0);
		TestEqual(*(Name + TEXT(": 무대 중심 빈터 22 m 밖")), BadMeadow, 0);
		TestEqual(*(Name + TEXT(": 늑대 시작 모서리 3 m 밖")), BadWolf, 0);
		TestEqual(*(Name + TEXT(": 줄기 중심 간격 ≥ d_min, 틈 ≥ 3 m")), BadGap, 0);
		TestEqual(*(Name + TEXT(": (x, y, r) 순")), BadOrder, 0);
		TestEqual(*(Name + TEXT(": 액터 기준점 ↔ 줄기 중심 = 크기 × 메시 어긋남")), BadPivot, 0);

		const std::vector<double> D = UEcoPolicyV3IntegratedSubsystem::StageTreeDiscs(FName(*Name), kStageSizeUnits);
		bool bSame = static_cast<int32>(D.size()) == 3 * St->Num;
		for (int32 i = 0; bSame && i < St->Num; ++i)
		{
			bSame = D[3 * i] == St->Trees[i].X && D[3 * i + 1] == St->Trees[i].Y && D[3 * i + 2] == St->Trees[i].R;
		}
		TestTrue(*(Name + TEXT(": 원판 목록 = 표 (x, y, r) 비트 단위")), bSame);
	}
	TestNotNull(TEXT("숲·한 변 60 단위 = 표"), UEcoPolicyV3IntegratedSubsystem::FindStageTrees(TEXT("Forest"), 60.0));
	TestNull(TEXT("숲·한 변 70 단위 = 표 없음 (다른 크기 무대)"), UEcoPolicyV3IntegratedSubsystem::FindStageTrees(TEXT("Forest"), 70.0));
	TestNull(TEXT("모르는 지역 = 표 없음"), UEcoPolicyV3IntegratedSubsystem::FindStageTrees(TEXT("TestA"), 60.0));
	TestTrue(TEXT("메마른 땅 원판 0"), UEcoPolicyV3IntegratedSubsystem::StageTreeDiscs(TEXT("Barren"), 60.0).empty());
	TestFalse(TEXT("기본값 실행 중 무대 나무 끔 (10-18 — 나무는 통합 레벨 액터)"), FEcoV3IntegratedSettings().bStageTrees);
	TestFalse(TEXT("콘솔 기본값 실행 중 무대 나무 끔 (eco.IntegratedV3.StageTrees 0)"), FEcoV3IntegratedSettings::FromConsole().bStageTrees);
	TestEqual(TEXT("레벨 나무 꼬리표"), UEcoPolicyV3IntegratedSubsystem::LevelTreeTag(), FName(TEXT("EcoV3Tree")));
	TestEqual(TEXT("줄기 막이 꼬리표"), UEcoPolicyV3IntegratedSubsystem::LevelTrunkTag(), FName(TEXT("EcoV3Trunk")));
	{
		// 표와 맞추기: 1 cm 안이면 표 값 (비트 단위), 밖이면 그대로. 표가 없는 지역·크기는 그대로
		const FTree& T = Forest->Trees[3];
		double X = T.X + 0.4 / EcoRepertoireV3::kUnitCm, Y = T.Y - 0.3 / EcoRepertoireV3::kUnitCm, R = T.R + 0.2 / EcoRepertoireV3::kUnitCm, Dev = 0.0;
		const bool bSnap = UEcoPolicyV3IntegratedSubsystem::SnapToLayout(TEXT("Forest"), kStageSizeUnits, X, Y, R, &Dev);
		TestTrue(TEXT("0.4 cm 어긋난 줄기 = 표 값 (비트 단위)"), bSnap && X == T.X && Y == T.Y && R == T.R && FMath::IsNearlyEqual(Dev, 0.4, 1e-9));
		double X2 = T.X + 1.5 / EcoRepertoireV3::kUnitCm, Y2 = T.Y, R2 = T.R;
		TestFalse(TEXT("1.5 cm 어긋난 줄기 = 그대로"), UEcoPolicyV3IntegratedSubsystem::SnapToLayout(TEXT("Forest"), kStageSizeUnits, X2, Y2, R2) || X2 != T.X + 1.5 / EcoRepertoireV3::kUnitCm);
		double X3 = T.X, Y3 = T.Y, R3 = T.R;
		TestFalse(TEXT("다른 크기 무대·메마른 땅 = 맞추지 않음"), UEcoPolicyV3IntegratedSubsystem::SnapToLayout(TEXT("Forest"), 65.0, X3, Y3, R3)
																  || UEcoPolicyV3IntegratedSubsystem::SnapToLayout(TEXT("Barren"), kStageSizeUnits, X3, Y3, R3));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoStageTreesV3StartPointsTest,
	"AdaptiveEcosystem.Policy.V3.StageTrees.StartPoints",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoStageTreesV3StartPointsTest::RunTest(const FString& Parameters)
{
	using namespace EcoStageTreesV3Test;
	FEcoV3IntegratedSettings S;
	S.Seed = 20000;
	S.StageSizeUnits = 60.0;
	S.bStageTrees = true;   // 10-18 부터 기본은 끔 (나무는 레벨 액터 — StageTrees.LevelActors). 여기서는 예비인 실행 중 나무 계획을 본다
	FEcoV3IntegratedSettings Off = S;
	Off.bStageTrees = false;
	auto Anywhere = [](const FVector&) { return true; };
	// 통합 레벨 무대 중심 (먹이 자리 — level_shc/scan_LV_Ecosystem_IntegrationTest.json)
	struct FCase
	{
		const TCHAR* Region;
		FVector Center;
		int32 Group;
	};
	const FCase Cases[3] = {{TEXT("Barren"), FVector(34000.0, 1000.0, 0.0), 0}, {TEXT("Forest"), FVector(34200.0, 46500.0, 0.0), 1},
							{TEXT("Highland"), FVector(34000.0, -49000.0, 0.0), 2}};
	for (const FCase& Cs : Cases)
	{
		const FName Region(Cs.Region);
		const std::vector<double> Discs = UEcoPolicyV3IntegratedSubsystem::StageTreeDiscs(Region, 60.0);
		FEcoV3StagePlan On, Bare;
		const bool bOn = UEcoPolicyV3IntegratedSubsystem::PlanStage(Region, Cs.Group, Cs.Center, Cs.Center, S, 128, 4, true, Anywhere, &TreeFlatGround, On);
		UEcoPolicyV3IntegratedSubsystem::PlanStage(Region, Cs.Group, Cs.Center, Cs.Center, Off, 128, 4, true, Anywhere, &TreeFlatGround, Bare);
		const int32 InOn = TreeStartsInTrunks(On, Discs);
		const int32 InBare = TreeStartsInTrunks(Bare, Discs);
		AddInfo(FString::Printf(TEXT("%s: 줄기 %d, 줄기 안 시작 자리 — 나무 켬 %d · 나무 끔이면 %d"), Cs.Region, static_cast<int32>(Discs.size() / 3), InOn, InBare));
		TestTrue(*FString::Printf(TEXT("%s: 사슴 128·늑대 4 를 다 놓는다"), Cs.Region), bOn && On.DeerPoints.Num() == 128 && On.WolfPoints.Num() == 4);
		TestEqual(*FString::Printf(TEXT("%s: 줄기 원판(반지름 + 몸) 안 시작 자리 0"), Cs.Region), InOn, 0);
		TestTrue(*FString::Printf(TEXT("%s: 늑대 자리는 나무 없을 때와 같다 (표가 늑대 시작 모서리를 비워 둔다)"), Cs.Region), On.WolfPoints == Bare.WolfPoints);
		if (Discs.empty())
		{
			TestTrue(*FString::Printf(TEXT("%s: 나무가 없으면 시작 자리가 나무 끔과 같다"), Cs.Region), On.DeerPoints == Bare.DeerPoints);
		}
	}
	// 다른 크기 무대(130 m)는 표를 쓰지 않는다 — 나무 끔과 같은 자리
	{
		FEcoV3IntegratedSettings Big = S;
		Big.StageSizeUnits = 65.0;
		FEcoV3IntegratedSettings BigOff = Big;
		BigOff.bStageTrees = false;
		FEcoV3StagePlan A, B;
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, Cases[1].Center, Cases[1].Center, Big, 64, 2, true, Anywhere, &TreeFlatGround, A);
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, Cases[1].Center, Cases[1].Center, BigOff, 64, 2, true, Anywhere, &TreeFlatGround, B);
		TestTrue(TEXT("다른 크기 무대: 나무 끔과 같은 시작 자리"), A.DeerPoints == B.DeerPoints && A.WolfPoints == B.WolfPoints);
	}
	// 장애물 끔(eco.IntegratedV3.Obstacles 0)이면 나무도 없다 — 시작 자리 그대로
	{
		FEcoV3IntegratedSettings NoOb = S;
		NoOb.bObstacles = false;
		FEcoV3StagePlan A, B;
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, Cases[1].Center, Cases[1].Center, NoOb, 128, 4, true, Anywhere, &TreeFlatGround, A);
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, Cases[1].Center, Cases[1].Center, Off, 128, 4, true, Anywhere, &TreeFlatGround, B);
		TestTrue(TEXT("장애물 끔: 나무 끔과 같은 시작 자리"), A.DeerPoints == B.DeerPoints && A.WolfPoints == B.WolfPoints);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoStageTreesV3SpawnTest,
	"AdaptiveEcosystem.Policy.V3.StageTrees.Spawn",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoStageTreesV3SpawnTest::RunTest(const FString& Parameters)
{
	using namespace EcoStageTreesV3Test;
	using namespace EcoTreeLayoutV3;
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World))
	{
		return false;
	}
	UWorld& World = *W.World;
	const double TopZ = 250.0;
	const FVector Origin(0.0, 0.0, 0.0);
	AStaticMeshActor* Floor = TreeFloor(World, kStageSizeUnits * EcoRepertoireV3::kUnitCm, TopZ);
	if (!TestNotNull(TEXT("바닥"), Floor))
	{
		return false;
	}
	const FStageTrees* Forest = TreeTable("Forest");
	const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(kStageSizeUnits, 6.0);
	FEcoV3StageTrees T;
	UEcoPolicyV3IntegratedSubsystem::SpawnStageTrees(World, TEXT("Forest"), Origin, kStageSizeUnits, Covers, T);
	AddInfo(FString::Printf(TEXT("놓음 %d / 표 %d (은신처 곁 %d · 지면 없음 %d · 메시 없음 %d), 땅 높낮이 최대 %.1f cm"), T.Num(), T.Layout, T.SkippedCover,
							T.SkippedNoGround, T.SkippedNoMesh, T.MaxReliefCm));
	if (!TestEqual(TEXT("숲 24 그루를 다 놓는다"), T.Num(), 24) || !TestTrue(TEXT("표대로 다 놓음"), T.Complete()) || T.Actors.Num() != 24)
	{
		return false;
	}
	TestTrue(TEXT("원판 = 표 (비트 단위)"), T.Discs == UEcoPolicyV3IntegratedSubsystem::StageTreeDiscs(TEXT("Forest"), kStageSizeUnits));
	int32 BadMesh = 0, BadCollision = 0, BadShadow = 0, BadTag = 0, BadXf = 0;
	for (int32 i = 0; i < T.Actors.Num(); ++i)
	{
		const AStaticMeshActor* A = Cast<AStaticMeshActor>(T.Actors[i].Get());
		const UStaticMeshComponent* C = A ? A->GetStaticMeshComponent() : nullptr;
		if (!C)
		{
			++BadMesh;
			continue;
		}
		const FTree& Tr = Forest->Trees[i];
		BadMesh += (C->GetStaticMesh() && C->GetStaticMesh()->GetPathName() == UTF8_TO_TCHAR(kMeshPath)) ? 0 : 1;
		BadCollision += (C->GetCollisionEnabled() == ECollisionEnabled::NoCollision && !A->GetActorEnableCollision()) ? 0 : 1;
		BadShadow += C->CastShadow ? 0 : 1;
		BadTag += A->ActorHasTag(TEXT("EcoV3StageTree")) ? 0 : 1;
		const FVector L = A->GetActorLocation();
		const FVector Want(Tr.PivotX * EcoRepertoireV3::kUnitCm, Tr.PivotY * EcoRepertoireV3::kUnitCm, TopZ - kSinkCm);
		const bool bXf = L.Equals(Want, 1e-3) && FMath::IsNearlyEqual(FRotator::NormalizeAxis(A->GetActorRotation().Yaw), FRotator::NormalizeAxis(Tr.YawDeg), 1e-3)
						 && FMath::IsNearlyZero(A->GetActorRotation().Pitch, 1e-6) && FMath::IsNearlyZero(A->GetActorRotation().Roll, 1e-6)
						 && A->GetActorScale3D().Equals(FVector(Tr.Scale), 1e-6) && FMath::IsNearlyEqual(T.GroundZ[i], TopZ, 1e-3);
		BadXf += bXf ? 0 : 1;
	}
	TestEqual(TEXT("메시 = 팀 Beech_Tree (애셋 그대로)"), BadMesh, 0);
	TestEqual(TEXT("충돌 없음"), BadCollision, 0);
	TestEqual(TEXT("그림자 켬"), BadShadow, 0);
	TestEqual(TEXT("꼬리표 EcoV3StageTree"), BadTag, 0);
	TestEqual(TEXT("자리 = 기준점·바닥 − 10 cm, 방위·크기 = 표, 곧게 섬"), BadXf, 0);

	// 레벨 읽기: 나무는 충돌이 없어 원판이 되지 않는다. 뺄 액터로 주면 아예 세지 않는다 (통합 모드가 하는 것). 바닥 상자는 두 번 다 뺀다
	{
		FEcoV3ObstacleScan Plain, Excl;
		TSet<const AActor*> FloorOnly;
		FloorOnly.Add(Floor);
		UEcoPolicyV3IntegratedSubsystem::ScanStageObstacles(World, Origin, kStageSizeUnits, Covers, FloorOnly, false, Plain);
		TSet<const AActor*> Exclude = FloorOnly;
		for (const TWeakObjectPtr<AActor>& A : T.Actors)
		{
			Exclude.Add(A.Get());
		}
		UEcoPolicyV3IntegratedSubsystem::ScanStageObstacles(World, Origin, kStageSizeUnits, Covers, Exclude, false, Excl);
		AddInfo(FString::Printf(TEXT("레벨 읽기: 뺄 액터 없이 메시 %d · 충돌 없음 %d · 원판 %d | 뺄 액터로 메시 %d · 원판 %d"), Plain.SeenMeshes, Plain.NoCollision, Plain.Num(),
								Excl.SeenMeshes, Excl.Num()));
		TestEqual(TEXT("뺄 액터 없이 읽어도 나무는 원판이 아니다 (두 번 세지 않음)"), Plain.Num(), 0);
		TestEqual(TEXT("뺄 액터 없이 읽으면 나무 24 = 충돌 없음"), Plain.NoCollision, 24);
		TestTrue(TEXT("뺄 액터로 주면 나무를 보지 않는다"), Excl.SeenMeshes == 0 && Excl.NoCollision == 0 && Excl.Num() == 0);
	}
	// 은신처를 나무 하나 위로 옮기면 그 나무만 뺀다
	{
		EcoTest::FScopedTestWorld CoverTestWorld;
		if (CoverTestWorld.World && TreeFloor(*CoverTestWorld.World, kStageSizeUnits * EcoRepertoireV3::kUnitCm, 0.0))
		{
			std::vector<EcoObservationV3::FCoverInput> Moved = Covers;
			Moved.push_back({Forest->Trees[5].X, Forest->Trees[5].Y, 1.0});   // 그 줄기 위 반지름 2 m 은신처 (다른 줄기는 9 m 넘게 떨어져 있다)
			FEcoV3StageTrees T2;
			UEcoPolicyV3IntegratedSubsystem::SpawnStageTrees(*CoverTestWorld.World, TEXT("Forest"), Origin, kStageSizeUnits, Moved, T2);
			TestTrue(TEXT("은신처 곁 나무 하나만 뺀다"), T2.Num() == 23 && T2.SkippedCover == 1 && !T2.Complete());
		}
	}
	// 바닥이 없으면 놓지 않는다 (지면 없음)
	{
		EcoTest::FScopedTestWorld W3;
		if (W3.World)
		{
			FEcoV3StageTrees T3;
			UEcoPolicyV3IntegratedSubsystem::SpawnStageTrees(*W3.World, TEXT("Highland"), Origin, kStageSizeUnits, Covers, T3);
			TestTrue(TEXT("지면이 없으면 하나도 놓지 않는다"), T3.Num() == 0 && T3.SkippedNoGround == 9 && T3.Layout == 9);
			FEcoV3StageTrees T4;
			UEcoPolicyV3IntegratedSubsystem::SpawnStageTrees(*W3.World, TEXT("Barren"), Origin, kStageSizeUnits, Covers, T4);
			TestTrue(TEXT("메마른 땅은 표가 비었다"), T4.Num() == 0 && T4.Layout == 0 && T4.Complete());
		}
	}
	// 레벨 원판과 합치기: (x, y, r) 순, 나무 표시
	{
		const std::vector<double> Level = {30.0, 30.0, 0.5, 0.0, 59.0, 0.25};
		TArray<uint8> IsTree;
		const std::vector<double> M = UEcoPolicyV3IntegratedSubsystem::MergeDiscs(Level, T.Discs, &IsTree);
		bool bSorted = M.size() == Level.size() + T.Discs.size() && IsTree.Num() == static_cast<int32>(M.size() / 3);
		int32 Trees = 0;
		for (size_t k = 3; bSorted && k + 2 < M.size(); k += 3)
		{
			bSorted = M[k - 3] < M[k] || (M[k - 3] == M[k] && (M[k - 2] < M[k + 1] || (M[k - 2] == M[k + 1] && M[k - 1] <= M[k + 2])));
		}
		for (const uint8 B : IsTree)
		{
			Trees += B;
		}
		TestTrue(TEXT("합친 원판은 (x, y, r) 순"), bSorted);
		TestEqual(TEXT("나무 표시 24"), Trees, 24);
		TestTrue(TEXT("레벨 원판 (0, 59) 이 맨 앞·레벨 표시"), M.size() >= 3 && M[0] == 0.0 && M[1] == 59.0 && IsTree.Num() > 0 && IsTree[0] == 0);
		TestTrue(TEXT("레벨 원판이 없으면 나무 원판 그대로"), UEcoPolicyV3IntegratedSubsystem::MergeDiscs({}, T.Discs) == T.Discs);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoStageTreesV3LevelActorsTest,
	"AdaptiveEcosystem.Policy.V3.StageTrees.LevelActors",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoStageTreesV3LevelActorsTest::RunTest(const FString& Parameters)
{
	using namespace EcoStageTreesV3Test;
	using namespace EcoTreeLayoutV3;
	using FSub = UEcoPolicyV3IntegratedSubsystem;
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World))
	{
		return false;
	}
	UWorld& World = *W.World;
	const double TopZ = 250.0;
	const double SideCm = kStageSizeUnits * EcoRepertoireV3::kUnitCm;
	const FVector Origin(0.0, 0.0, 0.0);
	AStaticMeshActor* Floor = TreeFloor(World, SideCm, TopZ);
	UStaticMesh* TreeMesh = LoadObject<UStaticMesh>(nullptr, UTF8_TO_TCHAR(kMeshPath));
	UStaticMesh* TrunkMesh = LoadObject<UStaticMesh>(nullptr, FSub::LevelTrunkMeshPath());
	if (!TestNotNull(TEXT("바닥"), Floor) || !TestNotNull(TEXT("팀 Beech_Tree"), TreeMesh) || !TestNotNull(TEXT("엔진 원기둥"), TrunkMesh))
	{
		return false;
	}
	const FStageTrees* Forest = TreeTable("Forest");
	// 레벨 나무 놓기 명령(EcoV3PlaceTreesCommandlet)과 같은 변환·설정으로 나무 + 줄기 막이를 놓는다 (시험 월드라 미루어 놓고 메시를 넣은 뒤 등록)
	TArray<AStaticMeshActor*> TreeActors;
	TArray<AStaticMeshActor*> TrunkActors;
	int32 NoGround = 0;
	for (int32 k = 0; k < Forest->Num; ++k)
	{
		const FTree& T = Forest->Trees[k];
		double MinZ = 0.0, MaxZ = 0.0;
		if (!FSub::GroundStageTree(World, Origin, T, MinZ, MaxZ))
		{
			++NoGround;
			continue;
		}
		FTransform TrunkXf;
		if (!TestTrue(TEXT("줄기 막이 변환"), FSub::LevelTrunkTransform(T, Origin, MinZ, *TrunkMesh, TrunkXf)))
		{
			return false;
		}
		const FTransform TreeXf = FSub::LevelTreeTransform(T, Origin, MinZ);
		AStaticMeshActor* Pair[2] = {LevelTreeActor(World, TreeXf, *TreeMesh, false), LevelTreeActor(World, TrunkXf, *TrunkMesh, true)};
		if (!TestNotNull(TEXT("나무 액터"), Pair[0]) || !TestNotNull(TEXT("줄기 막이 액터"), Pair[1]))
		{
			return false;
		}
		Pair[0]->Tags.Add(FSub::LevelTreeTag());
		Pair[1]->Tags.Add(FSub::LevelTrunkTag());
		Pair[1]->AttachToActor(Pair[0], FAttachmentTransformRules::KeepWorldTransform);
		TreeActors.Add(Pair[0]);
		TrunkActors.Add(Pair[1]);
	}
	TestEqual(TEXT("바닥 위 24 그루 모두 지면을 찾는다"), NoGround, 0);
	if (TreeActors.Num() != 24)
	{
		return false;
	}
	{
		// 나무 자리 = 실행 중 나무(SpawnStageTrees)와 같다: 기준점·바닥 − 10 cm·방위·크기. 줄기 막이 = 줄기 중심·반지름, 바닥 − 30 cm ~ + 4 m
		int32 BadTree = 0, BadTrunk = 0;
		for (int32 k = 0; k < 24; ++k)
		{
			const FTree& T = Forest->Trees[k];
			const FVector L = TreeActors[k]->GetActorLocation();
			BadTree += L.Equals(FVector(T.PivotX * EcoRepertoireV3::kUnitCm, T.PivotY * EcoRepertoireV3::kUnitCm, TopZ - kSinkCm), 1e-3)
						   && TreeActors[k]->GetActorScale3D().Equals(FVector(T.Scale), 1e-9)
						   && FMath::IsNearlyEqual(FRotator::NormalizeAxis(TreeActors[k]->GetActorRotation().Yaw), FRotator::NormalizeAxis(T.YawDeg), 1e-3)
						   ? 0 : 1;
			const FBox B = TrunkMesh->GetBodySetup()->AggGeom.CalcAABB(FTransform::Identity).TransformBy(TrunkActors[k]->GetStaticMeshComponent()->GetComponentTransform());
			const FVector C = B.GetCenter();
			BadTrunk += FMath::IsNearlyEqual(C.X, T.X * EcoRepertoireV3::kUnitCm, 1e-3) && FMath::IsNearlyEqual(C.Y, T.Y * EcoRepertoireV3::kUnitCm, 1e-3)
							&& FMath::IsNearlyEqual(B.Min.Z, TopZ - FSub::kLevelTrunkSinkCm, 0.5) && FMath::IsNearlyEqual(B.Max.Z, TopZ + FSub::kLevelTrunkTopCm, 0.5)
						? 0 : 1;
		}
		TestEqual(TEXT("나무 자리 = 실행 중 나무 (기준점·바닥 − 10 cm·방위·크기)"), BadTree, 0);
		TestEqual(TEXT("줄기 막이 = 줄기 중심, 바닥 − 30 cm ~ + 4 m"), BadTrunk, 0);
	}
	const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(kStageSizeUnits, 6.0);
	TSet<const AActor*> FloorOnly;
	FloorOnly.Add(Floor);
	const std::vector<double> Table = FSub::StageTreeDiscs(TEXT("Forest"), kStageSizeUnits);
	{
		// 레벨 읽기: 지역 이름을 주면 줄기 막이 원판 = 표 (비트 단위), 나무 메시는 충돌 없음으로만 센다
		FEcoV3ObstacleScan Scan;
		FSub::ScanStageObstacles(World, Origin, kStageSizeUnits, Covers, FloorOnly, false, Scan, TEXT("Forest"));
		AddInfo(FString::Printf(TEXT("레벨 읽기: 원판 %d · 레벨 나무 %d · 표와 맞춤 %d · 다름 %d · 차이 최대 %.3g cm · 무대 안 메시 %d · 충돌 없음 %d"), Scan.Num(), Scan.LevelTrees,
								Scan.LevelTreesSnapped, Scan.LevelTreesUnmatched, Scan.LevelTreeMaxSnapCm, Scan.SeenMeshes, Scan.NoCollision));
		TestTrue(TEXT("원판 = 표 (비트 단위)"), Scan.Discs == Table);
		TestTrue(TEXT("레벨 나무 24 · 맞춤 24 · 다름 0"), Scan.LevelTrees == 24 && Scan.LevelTreesSnapped == 24 && Scan.LevelTreesUnmatched == 0);
		TestTrue(TEXT("읽은 값 ↔ 표 차이 0.01 cm 밑 (원기둥 충돌 상자가 줄기 원판과 맞다)"), Scan.LevelTreeMaxSnapCm < 0.01);
		TestEqual(TEXT("나무 메시 24 = 충돌 없음 (잎은 원판이 아니다)"), Scan.NoCollision, 24);
		int32 Flags = 0;
		for (const uint8 B : Scan.IsLevelTree)
		{
			Flags += B;
		}
		TestEqual(TEXT("원판마다 레벨 나무 표시"), Flags, 24);
		TArray<uint8> IsTree;
		const std::vector<double> M = FSub::MergeDiscs(Scan.Discs, {}, &IsTree, &Scan.IsLevelTree);
		int32 TreeFlags = 0;
		for (const uint8 B : IsTree)
		{
			TreeFlags += B;
		}
		TestTrue(TEXT("합치기: 원판 그대로·나무 표시 24 (디버그 초록)"), M == Table && TreeFlags == 24);

		// 지역 이름 없이 읽으면 표와 맞추지 않는다 — 그래도 원기둥 상자에서 읽은 값이 표와 0.01 cm 안
		FEcoV3ObstacleScan Raw;
		FSub::ScanStageObstacles(World, Origin, kStageSizeUnits, Covers, FloorOnly, false, Raw);
		double MaxDev = Raw.Num() == 24 ? 0.0 : 1e30;
		for (int32 i = 0; Raw.Num() == 24 && i < 72; ++i)
		{
			MaxDev = FMath::Max(MaxDev, FMath::Abs(Raw.Discs[i] - Table[i]) * EcoRepertoireV3::kUnitCm);
		}
		AddInfo(FString::Printf(TEXT("맞추기 없이 읽은 원판 ↔ 표 차이 최대 %.3g cm"), MaxDev));
		TestTrue(TEXT("맞추기 없이: 원판 24, 표와 0.01 cm 안"), Raw.Num() == 24 && Raw.LevelTreesSnapped == 0 && MaxDev < 0.01);
	}
	{
		// 시작 자리 계획: 같은 줄기 원판을 피한다 (실행 중 나무 끔), 표를 쓴 계획(실행 중 나무 켬)과 같은 자리
		TArray<FVector> Trunks;
		FSub::GatherLevelTrunks(World, Trunks);
		int32 Snapped = 0;
		const std::vector<double> PlanDiscs = FSub::LevelTrunkDiscs(Trunks, TEXT("Forest"), Origin, kStageSizeUnits, &Snapped);
		TestTrue(TEXT("줄기 막이 24 → 계획 원판 = 표 (맞춤 24)"), Trunks.Num() == 24 && PlanDiscs == Table && Snapped == 24);
		FEcoV3IntegratedSettings Off;
		Off.Seed = 20000;
		Off.StageSizeUnits = kStageSizeUnits;
		Off.bStageTrees = false;
		FEcoV3IntegratedSettings On = Off;
		On.bStageTrees = true;
		const FVector Center(0.5 * SideCm, 0.5 * SideCm, 0.0);
		auto Anywhere = [](const FVector&) { return true; };
		FEcoV3StagePlan LevelPlan, TablePlan, BarePlan;
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, Center, Center, Off, 128, 4, true, Anywhere, &TreeFlatGround, LevelPlan, &Trunks);
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, Center, Center, On, 128, 4, true, Anywhere, &TreeFlatGround, TablePlan);
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, Center, Center, Off, 128, 4, true, Anywhere, &TreeFlatGround, BarePlan);
		TestTrue(TEXT("레벨 나무 계획: 레벨 줄기 원판 = 표"), LevelPlan.bLevelTrunks && LevelPlan.TrunkDiscs == Table);
		TestEqual(TEXT("레벨 나무 계획: 줄기 안 시작 자리 0"), TreeStartsInTrunks(LevelPlan, Table), 0);
		TestTrue(TEXT("레벨 나무 계획 = 실행 중 나무 계획 (같은 자리)"), LevelPlan.DeerPoints == TablePlan.DeerPoints && LevelPlan.WolfPoints == TablePlan.WolfPoints);
		TestTrue(TEXT("나무 없는 계획은 다르다 (줄기 안 자리가 있다)"), TreeStartsInTrunks(BarePlan, Table) > 0 && !BarePlan.bLevelTrunks);
		// 레벨 나무가 있는 무대는 실행 중 나무를 켜도 표를 쓰지 않는다 (두 번 놓지 않게)
		FEcoV3StagePlan Both;
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, Center, Center, On, 128, 4, true, Anywhere, &TreeFlatGround, Both, &Trunks);
		TestTrue(TEXT("레벨 나무 + 실행 중 나무 켬: 레벨 원판만"), Both.bLevelTrunks && Both.DeerPoints == LevelPlan.DeerPoints);
		// 장애물 끔이면 레벨 줄기도 피하지 않는다 (v3 세계에 원판이 없다)
		FEcoV3IntegratedSettings NoOb = Off;
		NoOb.bObstacles = false;
		FEcoV3StagePlan NoObPlan;
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, Center, Center, NoOb, 128, 4, true, Anywhere, &TreeFlatGround, NoObPlan, &Trunks);
		TestTrue(TEXT("장애물 끔: 나무 없는 계획과 같다"), !NoObPlan.bLevelTrunks && NoObPlan.DeerPoints == BarePlan.DeerPoints);
	}
	{
		// 팀 이동 제약: 줄기는 막고 잎 아래는 막지 않는다 (지역을 등록해야 ConstrainStep 이 돈다)
		AEcologyRegion* Region = World.SpawnActor<AEcologyRegion>(FVector(0.5 * SideCm, 0.5 * SideCm, 0.0), FRotator::ZeroRotator);
		UEcologyWorldSubsystem* Regions = World.GetSubsystem<UEcologyWorldSubsystem>();
		if (TestNotNull(TEXT("지역"), Region) && TestNotNull(TEXT("UEcologyWorldSubsystem"), Regions))
		{
			Region->RegionId = TEXT("Forest");
			Region->RegionBounds->SetBoxExtent(FVector(0.5 * SideCm + 2000.0, 0.5 * SideCm + 2000.0, 3000.0));
			Regions->RegisterRegion(Region);
			FEcoV3TrunkProbe Pr;
			FSub::ProbeLevelTrunks(World, TEXT("Forest"), FVector(0.0, 0.0, TopZ), kStageSizeUnits, Pr);
			AddInfo(FString::Printf(TEXT("이동 검사: 줄기 %d · 가로지르기 막힘 %d (줄기 막이 %d) · 잎 아래 둘레 %d 걸음 가운데 막힘 %d (우리 나무 %d)"), Pr.Trees, Pr.CrossBlocked,
									Pr.CrossByTrunk, Pr.RingSteps, Pr.RingBlocked, Pr.RingBlockedByTree));
			TestTrue(TEXT("줄기 24 를 가로지르면 모두 줄기 막이에 막힌다"), Pr.Trees == 24 && Pr.CrossBlocked == 24 && Pr.CrossByTrunk == 24);
			TestTrue(TEXT("잎 아래 둘레 걸음 288 은 하나도 막히지 않는다"), Pr.RingSteps == 24 * FEcoV3TrunkProbe::kRingSteps && Pr.RingBlocked == 0 && Pr.RingBlockedByTree == 0);
		}
	}
	{
		// 나무를 옮기면 붙은 줄기 막이가 따라가고, 레벨 읽기는 표와 다른 줄기로 센다 (읽은 값 그대로)
		TreeActors[5]->AddActorWorldOffset(FVector(50.0, 0.0, 0.0));
		FEcoV3ObstacleScan Moved;
		FSub::ScanStageObstacles(World, Origin, kStageSizeUnits, Covers, FloorOnly, false, Moved, TEXT("Forest"));
		bool bFound = false;
		for (int32 i = 0; i < Moved.Num(); ++i)
		{
			bFound = bFound
					 || (FMath::IsNearlyEqual(Moved.Discs[3 * i], Forest->Trees[5].X + 50.0 / EcoRepertoireV3::kUnitCm, 1e-6)
						 && FMath::IsNearlyEqual(Moved.Discs[3 * i + 1], Forest->Trees[5].Y, 1e-6));
		}
		TestTrue(TEXT("옮긴 나무: 맞춤 23 · 다름 1, 원판은 옮긴 자리"), Moved.LevelTreesSnapped == 23 && Moved.LevelTreesUnmatched == 1 && bFound);
	}
	return true;
}

#endif
