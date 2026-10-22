// 레벨 나무 놓기 명령 — 설명은 EcoV3PlaceTreesCommandlet.h 머리 주석.
#include "EcoV3PlaceTreesCommandlet.h"

#include "EcoPolicyV3IntegratedSubsystem.h"
#include "TreeLayoutV3.h"

#if WITH_EDITOR
#include "ActorFolder.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Components/StaticMeshComponent.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "EditorWorldUtils.h"
#include "Engine/CollisionProfile.h"
#include "Engine/Level.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "Modules/ModuleManager.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "PhysicsEngine/BodySetup.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UObjectGlobals.h"
#include "World/EcologyRegion.h"
#include "WorldPartition/LoaderAdapter/LoaderAdapterShape.h"
#include "WorldPartition/WorldPartition.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogEcoV3PlaceTrees, Log, All);

UEcoV3PlaceTreesCommandlet::UEcoV3PlaceTreesCommandlet()
{
	IsClient = false;
	IsServer = false;
	IsEditor = true;
	LogToConsole = true;
}

#if WITH_EDITOR
namespace EcoV3PlaceTreesImpl
{
	using FSub = UEcoPolicyV3IntegratedSubsystem;

	const TCHAR* const kIdTagPrefix = TEXT("EcoV3TreeId_");

	FString TreeId(FName Region, int32 Index)
	{
		return FString::Printf(TEXT("%s_%02d"), *Region.ToString(), Index);
	}

	/** 짝 꼬리표 EcoV3TreeId_<지역>_<번호> 의 <지역>_<번호> (없으면 빈 문자열). */
	FString IdOf(const AActor& A)
	{
		for (const FName& Tag : A.Tags)
		{
			const FString S = Tag.ToString();
			if (S.StartsWith(kIdTagPrefix))
			{
				return S.RightChop(FCString::Strlen(kIdTagPrefix));
			}
		}
		return FString();
	}

	bool IsOurs(const AActor& A)
	{
		return A.ActorHasTag(FSub::LevelTreeTag()) || A.ActorHasTag(FSub::LevelTrunkTag());
	}

	/** 바라는 액터 상태 (나무 또는 줄기 막이). */
	struct FWant
	{
		FString Label;
		TArray<FName> Tags;
		UStaticMesh* Mesh = nullptr;
		FTransform Xf;
		FName Profile;
		bool bHiddenInGame = false;
		bool bCastShadow = true;
		AActor* AttachTo = nullptr;
	};

	/** 액터가 이미 바라는 상태인가 (변환은 1e-4 cm·1e-6 크기·사원수 1e-6 안). */
	bool Matches(const AStaticMeshActor& A, const FWant& W, const FName Folder)
	{
		const UStaticMeshComponent* C = A.GetStaticMeshComponent();
		if (!C || C->GetStaticMesh() != W.Mesh || A.GetActorLabel() != W.Label || A.Tags != W.Tags || A.GetFolderPath() != Folder
			|| A.GetIsSpatiallyLoaded() || C->GetCollisionProfileName() != W.Profile || C->CastShadow != W.bCastShadow
			|| A.IsHidden() != W.bHiddenInGame || C->bHiddenInGame != W.bHiddenInGame || C->Mobility != EComponentMobility::Static
			|| C->CanEverAffectNavigation() || A.GetAttachParentActor() != W.AttachTo)
		{
			return false;
		}
		const FTransform& X = C->GetComponentTransform();
		return X.GetLocation().Equals(W.Xf.GetLocation(), 1e-4) && X.GetScale3D().Equals(W.Xf.GetScale3D(), 1e-6)
			   && X.GetRotation().Equals(W.Xf.GetRotation(), 1e-6);
	}

	void Apply(AStaticMeshActor& A, const FWant& W, const FName Folder)
	{
		A.Modify();
		UStaticMeshComponent* C = A.GetStaticMeshComponent();
		C->Modify();
		if (A.GetAttachParentActor() != W.AttachTo)
		{
			A.DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
		}
		C->SetMobility(EComponentMobility::Static);
		C->SetStaticMesh(W.Mesh);
		C->SetCollisionProfileName(W.Profile);
		C->SetCastShadow(W.bCastShadow);
		C->SetHiddenInGame(W.bHiddenInGame);
		C->SetCanEverAffectNavigation(false);   // 팀 내비 메시를 더럽히지 않는다 (팀 이동은 길 찾기를 쓰지 않는다)
		if (W.bHiddenInGame)
		{
			// 보이지 않는 막이: 그림자·거리장·반사·광선 추적에도 넣지 않는다
			C->bAffectDistanceFieldLighting = false;
			C->bAffectDynamicIndirectLighting = false;
			C->bVisibleInReflectionCaptures = false;
			C->bVisibleInRealTimeSkyCaptures = false;
			C->bVisibleInRayTracing = false;
		}
		A.SetActorHiddenInGame(W.bHiddenInGame);
		A.SetActorTransform(W.Xf, false, nullptr, ETeleportType::TeleportPhysics);
		if (W.AttachTo && A.GetAttachParentActor() != W.AttachTo)
		{
			A.AttachToActor(W.AttachTo, FAttachmentTransformRules::KeepWorldTransform);
		}
		A.SetIsSpatiallyLoaded(false);   // 늘 불림 — 무대를 만들 때(스트리밍 전 시작 자리 계획 포함) 언제나 있다
		A.SetActorLabel(W.Label);
		A.SetFolderPath(Folder);
		A.Tags = W.Tags;
		C->MarkRenderStateDirty();
		A.PostEditChange();
		A.MarkPackageDirty();
	}

	AStaticMeshActor* Spawn(UWorld& World)
	{
		FActorSpawnParameters P;
		P.OverrideLevel = World.PersistentLevel;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		P.ObjectFlags |= RF_Transactional;
		return World.SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), FTransform::Identity, P);
	}

	/** 우리 액터 하나를 지운다 (외부 액터 파일 이름을 돌려준다). */
	FString Destroy(UWorld& World, AActor& A)
	{
		const UPackage* Pkg = A.GetExternalPackage();
		const FString Name = Pkg ? Pkg->GetName() : FString();
		UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("지움: %s (%s)"), *A.GetActorLabel(), *Name);
		World.EditorDestroyActor(&A, true);
		return Name;
	}

	struct FStage
	{
		FName Region;
		FVector OriginCm = FVector::ZeroVector;
		const EcoTreeLayoutV3::FStageTrees* Table = nullptr;
	};

	int32 Run(const FString& Params)
	{
		FString Map = TEXT("/Game/Map/LV_Ecosystem_IntegrationTest");
		FParse::Value(*Params, TEXT("Map="), Map);
		const bool bRemove = FParse::Param(*Params, TEXT("Remove"));
		const bool bDryRun = FParse::Param(*Params, TEXT("DryRun"));
		const bool bForce = FParse::Param(*Params, TEXT("Force"));
		UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("레벨 나무 놓기: 맵 %s | %s%s | 배치 표 %s (지문 %s)"), *Map,
			   bRemove ? TEXT("지우기") : TEXT("놓기·고치기"), bDryRun ? TEXT(" (저장 안 함)") : TEXT(""), UTF8_TO_TCHAR(EcoTreeLayoutV3::kVersion),
			   UTF8_TO_TCHAR(EcoTreeLayoutV3::kDigest));

		IAssetRegistry& AssetRegistry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
		AssetRegistry.WaitForCompletion();

		UWorld::InitializationValues IVS;
		IVS.RequiresHitProxies(false);
		IVS.ShouldSimulatePhysics(false);
		IVS.EnableTraceCollision(true);
		IVS.CreateNavigation(false);
		IVS.CreateAISystem(false);
		IVS.AllowAudioPlayback(false);
		IVS.CreatePhysicsScene(true);
		FScopedEditorWorld Scoped(Map, IVS);
		UWorld* World = Scoped.GetWorld();
		if (!World || !World->PersistentLevel)
		{
			UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("맵을 열지 못했다: %s"), *Map);
			return 1;
		}
		// 월드 파티션: 모든 액터를 불러 온다 (지형·지역·조정자·우리 액터). 이 레벨은 액터 161 개라 한 번에 불러도 된다
		TUniquePtr<FLoaderAdapterShape> Loader;
		if (World->GetWorldPartition())
		{
			Loader = MakeUnique<FLoaderAdapterShape>(World, FBox(FVector(-HALF_WORLD_MAX), FVector(HALF_WORLD_MAX)), TEXT("EcoV3PlaceTrees"));
			Loader->Load();
		}
		int32 NumActors = 0;
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			++NumActors;
		}
		UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("불러온 액터 %d (월드 파티션 %s)"), NumActors, World->GetWorldPartition() ? TEXT("예") : TEXT("아니오"));

		// 우리 액터 (꼬리표). 짝 꼬리표가 없거나 겹치면 버릴 것으로 둔다
		TMap<FString, AStaticMeshActor*> OldTrees;
		TMap<FString, AStaticMeshActor*> OldTrunks;
		TArray<AActor*> Strays;
		TArray<AActor*> Ours;
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			AActor* A = *It;
			if (!A || !IsOurs(*A))
			{
				continue;
			}
			Ours.Add(A);
			AStaticMeshActor* Sm = Cast<AStaticMeshActor>(A);
			const FString Id = IdOf(*A);
			TMap<FString, AStaticMeshActor*>& Into = A->ActorHasTag(FSub::LevelTrunkTag()) ? OldTrunks : OldTrees;
			if (!Sm || Id.IsEmpty() || Into.Contains(Id))
			{
				Strays.Add(A);
				continue;
			}
			Into.Add(Id, Sm);
		}
		UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("이미 있는 우리 액터 %d (나무 %d · 줄기 막이 %d · 짝 없음 %d)"), Ours.Num(), OldTrees.Num(), OldTrunks.Num(), Strays.Num());

		TArray<FString> ToDelete;
		TArray<UPackage*> ToSave;
		const FName Folder(FSub::LevelTreeFolder());

		if (bRemove)
		{
			for (AActor* A : Ours)
			{
				const FString Name = Destroy(*World, *A);
				if (!Name.IsEmpty())
				{
					ToDelete.Add(Name);
				}
			}
			// 빈 폴더 EcoV3_Trees (외부 개체 파일) 도 지운다 — 우리 폴더라 다른 액터가 없다
			if (UActorFolder* F = World->PersistentLevel->GetActorFolder(Folder))
			{
				if (const UPackage* Pkg = F->GetExternalPackage())
				{
					ToDelete.Add(Pkg->GetName());
				}
			}
		}
		else
		{
			// 무대 자리: 통합 모드와 같은 규칙 (조정자 그룹 → 지역, 바라는 중심 = 먹이 자리 또는 지역 중심, 지역 상자 안으로 옮김, 높이 = 중심 지면)
			TArray<AEcoCreatureIntegrationSpawner*> Spawners;
			for (TActorIterator<AEcoCreatureIntegrationSpawner> It(World); It; ++It)
			{
				Spawners.Add(*It);
			}
			if (Spawners.Num() != 1)
			{
				UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("조정자(AEcoCreatureIntegrationSpawner)가 %d 개다 — 하나여야 무대 자리를 정할 수 있다"), Spawners.Num());
				return 1;
			}
			const double SizeUnits = EcoTreeLayoutV3::kStageSizeUnits;
			const double Half = 0.5 * SizeUnits * EcoRepertoireV3::kUnitCm;
			TArray<FStage> Stages;
			for (const FEcoCreatureSpawnGroup& G : Spawners[0]->Groups)
			{
				AEcologyRegion* Region = nullptr;
				for (TActorIterator<AEcologyRegion> It(World); It; ++It)
				{
					Region = It->RegionId == G.RegionId ? *It : Region;
				}
				const EcoTreeLayoutV3::FStageTrees* Table = FSub::FindStageTrees(G.RegionId, SizeUnits);
				if (!Region)
				{
					UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("지역 %s 를 찾지 못했다"), *G.RegionId.ToString());
					return 1;
				}
				const FVector Desired = G.bUseFoodPatchPosition ? G.FoodPatchPosition : Region->GetActorLocation();
				bool bInside = false;
				const FVector Center = FSub::StageCenterCm(Desired, Region->GetActorLocation(), SizeUnits,
														   [Region](const FVector& P) { return Region->ContainsPosition(P); }, bInside);
				FVector CenterGround = Center;
				EcoCreatureMovement::ProjectSpawnPoint(*World, Center, CenterGround);
				FStage St;
				St.Region = G.RegionId;
				St.OriginCm = FVector(Center.X - Half, Center.Y - Half, CenterGround.Z);
				St.Table = Table;
				UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("무대 %s: 중심 (%.0f, %.0f), 원점 (%.0f, %.0f, %.0f), 한 변 %.0f m, 지역 상자 안 %s | 배치 표 %d 그루"),
					   *G.RegionId.ToString(), Center.X, Center.Y, St.OriginCm.X, St.OriginCm.Y, St.OriginCm.Z, 2.0 * Half / 100.0,
					   bInside ? TEXT("예") : TEXT("아니오"), Table ? Table->Num : 0);
				if (Table && Table->Num > 0)
				{
					Stages.Add(St);
				}
			}

			UStaticMesh* TreeMesh = LoadObject<UStaticMesh>(nullptr, UTF8_TO_TCHAR(EcoTreeLayoutV3::kMeshPath));
			UStaticMesh* TrunkMesh = LoadObject<UStaticMesh>(nullptr, FSub::LevelTrunkMeshPath());
			if (!TreeMesh || !TrunkMesh)
			{
				UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("메시를 읽지 못했다: 나무 %s · 줄기 막이 %s"), TreeMesh ? TEXT("있음") : TEXT("없음"),
					   TrunkMesh ? TEXT("있음") : TEXT("없음"));
				return 1;
			}
			{
				const FKAggregateGeom* Agg = TrunkMesh->GetBodySetup() ? &TrunkMesh->GetBodySetup()->AggGeom : nullptr;
				const FBox Box = TrunkMesh->GetBodySetup() && Agg->GetElementCount() > 0 ? Agg->CalcAABB(FTransform::Identity) : TrunkMesh->GetBounds().GetBox();
				UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("줄기 막이 메시 %s: 충돌 요소 %d (볼록 %d), 충돌 상자 %s ~ %s"), FSub::LevelTrunkMeshPath(),
					   Agg ? Agg->GetElementCount() : 0, Agg ? Agg->ConvexElems.Num() : 0, *Box.Min.ToString(), *Box.Max.ToString());
			}

			// 지면 검사에서 뺄 액터 = 이미 있는 우리 액터 (다시 놓을 때 줄기 막이 윗면을 땅으로 읽지 않게)
			TArray<AActor*> Ignore = Ours;
			TSet<FString> Wanted;
			int32 New = 0, Changed = 0, Same = 0, NoGround = 0;
			for (const FStage& St : Stages)
			{
				double MaxRelief = 0.0;
				for (int32 k = 0; k < St.Table->Num; ++k)
				{
					const EcoTreeLayoutV3::FTree& T = St.Table->Trees[k];
					const FString Id = TreeId(St.Region, k);
					double MinZ = 0.0, MaxZ = 0.0;
					if (!FSub::GroundStageTree(*World, St.OriginCm, T, MinZ, MaxZ, &Ignore))
					{
						UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("%s: 줄기 아래 지면을 못 찾았다 — 놓지 않는다"), *Id);
						++NoGround;
						continue;
					}
					MaxRelief = FMath::Max(MaxRelief, MaxZ - MinZ);
					Wanted.Add(Id);
					FWant Tree;
					Tree.Label = FString::Printf(TEXT("EcoV3Tree_%s"), *Id);
					Tree.Tags = {FSub::LevelTreeTag(), FName(*(FString(kIdTagPrefix) + Id))};
					Tree.Mesh = TreeMesh;
					Tree.Xf = FSub::LevelTreeTransform(T, St.OriginCm, MinZ);
					Tree.Profile = UCollisionProfile::NoCollision_ProfileName;
					Tree.bCastShadow = true;
					FWant Trunk;
					Trunk.Label = FString::Printf(TEXT("EcoV3Trunk_%s"), *Id);
					Trunk.Tags = {FSub::LevelTrunkTag(), FName(*(FString(kIdTagPrefix) + Id))};
					Trunk.Mesh = TrunkMesh;
					Trunk.Profile = UCollisionProfile::BlockAll_ProfileName;
					Trunk.bHiddenInGame = true;
					Trunk.bCastShadow = false;
					if (!FSub::LevelTrunkTransform(T, St.OriginCm, MinZ, *TrunkMesh, Trunk.Xf))
					{
						UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("줄기 막이 메시 충돌 상자가 비었다"));
						return 1;
					}
					AStaticMeshActor* const* OldTree = OldTrees.Find(Id);
					AStaticMeshActor* const* OldTrunk = OldTrunks.Find(Id);
					AStaticMeshActor* TreeActor = OldTree ? *OldTree : Spawn(*World);
					AStaticMeshActor* TrunkActor = OldTrunk ? *OldTrunk : Spawn(*World);
					if (!TreeActor || !TrunkActor)
					{
						UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("%s: 액터를 놓지 못했다"), *Id);
						return 1;
					}
					Trunk.AttachTo = TreeActor;
					const bool bTreeSame = OldTree && Matches(*TreeActor, Tree, Folder);
					if (!bTreeSame || bForce)
					{
						Apply(*TreeActor, Tree, Folder);   // 붙은 줄기 막이도 함께 움직인다 — 줄기 막이는 그 뒤에 본다
					}
					const bool bTrunkSame = OldTrunk && Matches(*TrunkActor, Trunk, Folder);
					if (!bTrunkSame || bForce)
					{
						Apply(*TrunkActor, Trunk, Folder);
					}
					for (AStaticMeshActor* A : {TreeActor, TrunkActor})
					{
						const bool bWasNew = A == TreeActor ? !OldTree : !OldTrunk;
						const bool bWasSame = A == TreeActor ? bTreeSame : bTrunkSame;
						New += bWasNew ? 1 : 0;
						Changed += !bWasNew && !bWasSame ? 1 : 0;
						Same += bWasSame ? 1 : 0;
						if ((!bWasSame || bForce) && A->GetExternalPackage())
						{
							ToSave.AddUnique(A->GetExternalPackage());
						}
					}
					const FVector L = Tree.Xf.GetLocation();
					UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("%s: 나무 기준점 (%.1f, %.1f, %.1f) 방위 %.1f° 크기 %.3f | 줄기 (%.1f, %.1f) 반지름 %.2f cm | 땅 %.1f~%.1f cm | %s"),
						   *Id, L.X, L.Y, L.Z, T.YawDeg, T.Scale, St.OriginCm.X + T.X * EcoRepertoireV3::kUnitCm, St.OriginCm.Y + T.Y * EcoRepertoireV3::kUnitCm,
						   T.R * EcoRepertoireV3::kUnitCm, MinZ, MaxZ,
						   !OldTree ? TEXT("새로") : (bTreeSame && bTrunkSame ? TEXT("그대로") : TEXT("고침")));
				}
				UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("무대 %s: %d 그루, 밑동 아래 땅 높낮이 최대 %.1f cm, 나무 밑동은 가장 낮은 땅보다 %.0f cm 묻음, 줄기 막이 = 땅 − %.0f ~ + %.0f cm"),
					   *St.Region.ToString(), St.Table->Num, MaxRelief, EcoTreeLayoutV3::kSinkCm, FSub::kLevelTrunkSinkCm, FSub::kLevelTrunkTopCm);
			}
			// 표에 없는 우리 액터 (짝 꼬리표가 없거나 겹친 것 포함) 는 지운다
			for (AActor* A : Strays)
			{
				ToDelete.Add(Destroy(*World, *A));
			}
			for (const TPair<FString, AStaticMeshActor*>& P : OldTrees)
			{
				if (!Wanted.Contains(P.Key))
				{
					ToDelete.Add(Destroy(*World, *P.Value));
				}
			}
			for (const TPair<FString, AStaticMeshActor*>& P : OldTrunks)
			{
				if (!Wanted.Contains(P.Key))
				{
					ToDelete.Add(Destroy(*World, *P.Value));
				}
			}
			ToDelete.RemoveAll([](const FString& S) { return S.IsEmpty(); });
			// 폴더 (외부 개체 파일): 새로 생겼거나 바뀌었으면 함께 저장
			if (UActorFolder* F = World->PersistentLevel->GetActorFolder(Folder))
			{
				if (F->GetExternalPackage() && (F->GetExternalPackage()->IsDirty() || bForce))
				{
					ToSave.AddUnique(F->GetExternalPackage());
				}
			}
			UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("액터: 새로 %d · 고침 %d · 그대로 %d · 지움 %d · 지면 없음 %d | 저장할 파일 %d"), New, Changed, Same, ToDelete.Num(),
				   NoGround, ToSave.Num());

			// 확인: 통합 모드의 레벨 읽기가 이 무대에서 읽는 원판 = 배치 표 (은신처 원 = 통합 모드의 우리 은신처 넷, 무대 1/4·3/4 · 반경 12 m)
			bool bAllSame = NoGround == 0;
			for (const FStage& St : Stages)
			{
				FEcoV3ObstacleScan Scan;
				const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(SizeUnits, 6.0);
				FSub::ScanStageObstacles(*World, St.OriginCm, SizeUnits, Covers, TSet<const AActor*>(), false, Scan, St.Region);
				const std::vector<double> Table = FSub::StageTreeDiscs(St.Region, SizeUnits);
				TArray<FVector> Trunks;
				FSub::GatherLevelTrunks(*World, Trunks);
				int32 PlanSnapped = 0;
				const std::vector<double> PlanDiscs = FSub::LevelTrunkDiscs(Trunks, St.Region, St.OriginCm, SizeUnits, &PlanSnapped);
				const bool bSame = Scan.Discs == Table && PlanDiscs == Table && Scan.LevelTreesSnapped == St.Table->Num && Scan.LevelTreesUnmatched == 0;
				bAllSame = bAllSame && bSame;
				UE_LOG(LogEcoV3PlaceTrees, Display,
					   TEXT("확인 %s: 레벨 읽기 원판 %d (줄기 막이 %d, 표와 맞춤 %d, 다름 %d, 읽은 값 ↔ 표 차이 최대 %.3g cm) · 무대 안 메시 %d · 충돌 없음 %d | ")
						   TEXT("원판 = 표 (비트 단위) %s · 시작 자리 계획 원판 = 표 %s (맞춤 %d)"),
					   *St.Region.ToString(), Scan.Num(), Scan.LevelTrees, Scan.LevelTreesSnapped, Scan.LevelTreesUnmatched, Scan.LevelTreeMaxSnapCm,
					   Scan.SeenMeshes, Scan.NoCollision, Scan.Discs == Table ? TEXT("예") : TEXT("아니오"), PlanDiscs == Table ? TEXT("예") : TEXT("아니오"),
					   PlanSnapped);
			}
			if (!bAllSame)
			{
				UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("확인 실패: 레벨 읽기 원판이 배치 표와 다르다 — 저장하지 않는다"));
				return 1;
			}
		}

		if (bDryRun)
		{
			UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("저장 안 함 (-DryRun): 저장할 파일 %d · 지울 파일 %d"), ToSave.Num(), ToDelete.Num());
			return 0;
		}
		// 저장 (외부 액터·외부 개체 파일 — 월드 파티션 빌더와 같은 저장 인자. 원본 관리는 쓰지 않는다: 커밋은 사람이 git 으로)
		for (UPackage* Pkg : ToSave)
		{
			FString File;
			if (!FPackageName::TryConvertLongPackageNameToFilename(Pkg->GetName(), File, FPackageName::GetAssetPackageExtension()))
			{
				UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("파일 이름을 못 만들었다: %s"), *Pkg->GetName());
				return 1;
			}
			IFileManager::Get().MakeDirectory(*FPaths::GetPath(File), true);
			IPlatformFile::GetPlatformPhysical().SetReadOnly(*File, false);
			Pkg->MarkAsFullyLoaded();
			FSavePackageArgs Args;
			Args.TopLevelFlags = RF_Standalone;
			Args.SaveFlags = SAVE_None;
			if (!UPackage::SavePackage(Pkg, nullptr, *File, Args))
			{
				UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("저장 실패: %s"), *Pkg->GetName());
				return 1;
			}
			UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("저장: %s"), *FPaths::ConvertRelativePathToFull(File));
		}
		UPackage::WaitForAsyncFileWrites();
		for (const FString& Name : ToDelete)
		{
			if (UPackage* Pkg = FindPackage(nullptr, *Name))
			{
				ResetLoaders(Pkg);
			}
			FString File;
			if (FPackageName::TryConvertLongPackageNameToFilename(Name, File, FPackageName::GetAssetPackageExtension()) && IFileManager::Get().FileExists(*File))
			{
				IPlatformFile::GetPlatformPhysical().SetReadOnly(*File, false);
				if (!IPlatformFile::GetPlatformPhysical().DeleteFile(*File))
				{
					UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("지우기 실패: %s"), *File);
					return 1;
				}
				UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("지움: %s"), *FPaths::ConvertRelativePathToFull(File));
			}
		}
		UE_LOG(LogEcoV3PlaceTrees, Display, TEXT("끝: 저장 %d · 지움 %d"), ToSave.Num(), ToDelete.Num());
		return 0;
	}
}
#endif

int32 UEcoV3PlaceTreesCommandlet::Main(const FString& Params)
{
#if WITH_EDITOR
	return EcoV3PlaceTreesImpl::Run(Params);
#else
	UE_LOG(LogEcoV3PlaceTrees, Error, TEXT("EcoV3PlaceTrees 는 편집기 빌드에서만 돈다"));
	return 1;
#endif
}
