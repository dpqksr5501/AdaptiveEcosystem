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

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "../TreeLayoutV3.h"
#include "Components/StaticMeshComponent.h"
#include "EcoTestWorld.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"

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
	TestTrue(TEXT("기본값 무대 나무 켬"), FEcoV3IntegratedSettings().bStageTrees);
	TestTrue(TEXT("콘솔 기본값 무대 나무 켬 (eco.IntegratedV3.StageTrees 1)"), FEcoV3IntegratedSettings::FromConsole().bStageTrees);
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
		EcoTest::FScopedTestWorld W2;
		if (W2.World && TreeFloor(*W2.World, kStageSizeUnits * EcoRepertoireV3::kUnitCm, 0.0))
		{
			std::vector<EcoObservationV3::FCoverInput> Moved = Covers;
			Moved.push_back({Forest->Trees[5].X, Forest->Trees[5].Y, 1.0});   // 그 줄기 위 반지름 2 m 은신처 (다른 줄기는 9 m 넘게 떨어져 있다)
			FEcoV3StageTrees T2;
			UEcoPolicyV3IntegratedSubsystem::SpawnStageTrees(*W2.World, TEXT("Forest"), Origin, kStageSizeUnits, Moved, T2);
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

#endif
