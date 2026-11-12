// R9 데모 플레이어 — 보이는 것 (몸·멧돼지 몸·풀·판 자리·은신처·가장자리·물기 표시·먼 표식). 그리기만 한다 — 위치·먹이·죽음은 프레임 값 그대로.
//
// 사슴·늑대: 표현 액터(AEcoCreatureRepresentationActor — '받은 값만 그리는' 수동 액터)를 Mass 없이 띄우고 BindIdentity → 매 프레임 ConsumeVisualState.
//   자세는 애님 BP 가 표현 상태(속도·Activity·먹는 중·살아 있음)로 고른다 (EcoCreatureAnimInstance.cpp:49-67).
// 멧돼지 (2026-11-13): 실행 중 에셋 레지스트리에서 돼지·멧돼지 표현 BP → 스켈레탈 메시 차례로 찾는다 (/Game/AnimalVarietyPack/Pig → /Game/JYU/Fauna → /Game,
//   이름 Pig·Boar·Hog·Swine·villsvin — EcoR9DemoWhole.h BoarNameScore). 메시면 같은 스켈레톤 애니를 이름(Idle·Walk·Trot·Run·Eat/Graze/Root/Sniff·Death)으로 골라
//   상태별 한 마디 재생. 없으면 엔진 기본 도형 자리표시 (낮고 긴 몸·짧은 다리·주둥이·귀·어두운 털).
// 풀: 조연우 AEcoVegetationField 와 같은 메시(SM_MWAM_GrassA)·재질(MI_JYU_EcosystemGrass)·custom data 4 칸(양·수분·스트레스·새순 색)·칸마다 5 덩이 꼴
//   (EcoVegetationField.cpp:532-551, setup_jyu_ecosystem.py:88-90). 조연우 코드·에셋은 읽기만 한다. 값은 R9 먹이 격자 그대로 — 먹으면 줄고 eat_min(0.06) 밑이면 숨고 다시 자란다.
//   큰 세계(맵 전체 땅)는 카메라 둘레 창만 그린다 (인스턴스 재사용 — 바뀐 칸만 다시 씀).
// 큰 세계 몸: 카메라에서 eco.R9Demo.BodyNear(220 m) 안 가까운 eco.R9Demo.BodyBudget(90) 마리만 몸 액터, 나머지는 작은 공 표식 (섬 무대 먼 표식 꼴,
//   EcoV3IslandStage.cpp IslandTickMarkers — 크기는 카메라 거리 × 0.012, 최소 1.5 m).

#include "EcoR9DemoSubsystem.h"

#include "EcoR9DemoState.h"

#include "Animation/AnimSequence.h"
#include "Animation/Skeleton.h"
#include "Camera/CameraActor.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Core/EcoActivityTypes.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/PackageName.h"
#include "ReferenceSkeleton.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"

#include <limits>
#if WITH_EDITOR
// 에셋 레지스트리 모듈은 에디터 빌드에서만 이 모듈의 의존성이다 (AdaptiveEcosystem.Build.cs — Build.cs 는 바꾸지 않음). PIE·창 없는 -game 실행은 에디터 바이너리라 된다
#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Blueprint/BlueprintSupport.h"
#include "Engine/Blueprint.h"
#endif

namespace EcoR9DemoVisualsImpl
{
	using namespace EcoR9Demo;

	constexpr float kEatMin = 0.06f;            // 격자 먹이 eat_min (SPEC_PORT 2 절) — 이 밑이면 먹을 수 없으니 숨긴다
	constexpr double kTuftWidthCm = 280.0;      // BP_JYU_VegetationField 의 PatchWidthCm
	constexpr double kTuftHeightCm = 60.0;      // PatchHeightCm
	constexpr double kTuftOffset = 0.22;        // 칸 크기 × 0.22 만큼 네 쪽 (EcoVegetationField.cpp:539)
	constexpr double kDugSeconds = 10.0;        // 멧돼지가 판 자국이 남는 시간 [어림]
	constexpr double kCorpseSettle = 2.5;       // 쓰러지는 클립 뒤 누운 몸으로
	constexpr double kCorpseNoFoodSeconds = 40.0;   // 사체 정보가 없는 재생에서 누운 몸을 두는 시간 [어림]
	constexpr double kPursueUnits = 10.0;       // 뛰는 늑대가 이 거리(20 m) 안 먹잇감이면 '쫓음' 표시 [해석]
	constexpr int32 kGrassQuant = 64;           // 풀 양 눈금 (이만큼 바뀌어야 인스턴스를 다시 씀 — 다시 자람은 매 스텝 아주 조금씩이라)
	constexpr int32 kWindowSnap = 8;            // 풀 창 모서리 맞춤 (칸 — 32 m)
	constexpr int32 kSpawnPerTick = 8;          // 큰 세계: 한 틱에 새로 띄우는 몸 상한 (끊김 없게)
	constexpr double kBodyKeep = 1.25;          // 몸이 있는 개체는 BodyNear × 1.25 까지 지킨다 (깜빡이지 않게)
	constexpr double kBoarLengthCm = 150.0;     // 멧돼지 메시 몸 길이 맞춤 (어른 약 1.5 m) [어림]
	constexpr double kBoarWalkCmS = 120.0;      // 걷기·뛰기 애니 재생 빠르기 기준 [어림]
	constexpr double kBoarRunCmS = 420.0;
	// 표현 액터 신원 = 이 수 + R9 uid. 팀 맵에서 팀 개체(StableAgentId 는 작은 양수)와 같은 번호가 되지 않게 따로 둔다
	// (팀 살피기 HUD·관찰 카메라가 신원 번호로 표현 액터를 찾음 — EcoCreatureInspection.cpp:41, EcoV3ObserverCamera.cpp:529). 그리기만 바뀐다
	constexpr int64 kStableIdBase = 9000000000000LL;
	const FName kDemoRegionId(TEXT("R9Demo"));

	const TCHAR* const kDeerJyu = TEXT("/Game/JYU/Creatures/BP_JYU_Deer.BP_JYU_Deer_C");
	const TCHAR* const kWolfJyu = TEXT("/Game/JYU/Creatures/BP_JYU_Wolf.BP_JYU_Wolf_C");
	const TCHAR* const kDeerTeam = TEXT("/Game/Creatures/Integrated/BP_EcoDeer.BP_EcoDeer_C");
	const TCHAR* const kWolfTeam = TEXT("/Game/Creatures/Integrated/BP_EcoWolf.BP_EcoWolf_C");
	// 멧돼지 몸 찾는 차례 (사용자 11-13: 팀 돼지 = 라이선스 AnimalVarietyPack Pig — 이 PC 에 없을 수 있음)
	const TCHAR* const kBoarRoots[] = {TEXT("/Game/AnimalVarietyPack/Pig"), TEXT("/Game/JYU/Fauna"), TEXT("/Game")};

	UClass* LoadRepClass(const TCHAR* Path)
	{
		UClass* C = LoadClass<AEcoCreatureRepresentationActor>(nullptr, Path);
		return C && !C->HasAnyClassFlags(CLASS_Abstract) ? C : nullptr;
	}

	/** 정수 해시 → [0, 1) (보이는 덩어리 돌림·흔들림용 — 규칙과 무관). */
	double Hash01(uint32 V)
	{
		V ^= V >> 16;
		V *= 0x7feb352dU;
		V ^= V >> 15;
		V *= 0x846ca68bU;
		V ^= V >> 16;
		return static_cast<double>(V) / 4294967296.0;
	}

	/** 메시 바닥을 땅에 맞춰, 목표 높이·폭(cm)이 되게 하는 배율과 자리. */
	FTransform FitOnGround(const UStaticMesh* Mesh, const FVector& Ground, double YawDeg, double WidthCm, double HeightCm)
	{
		const FBox Box = Mesh->GetBoundingBox();
		const FVector Size = Box.GetSize();
		const double Sxy = WidthCm / FMath::Max(1.0, FMath::Max(Size.X, Size.Y));
		const double Sz = HeightCm / FMath::Max(1.0, Size.Z);
		return FTransform(FRotator(0.0, YawDeg, 0.0), Ground - FVector(0.0, 0.0, Box.Min.Z * Sz), FVector(Sxy, Sxy, Sz));
	}

	FTransform Hidden(const FVector& Where)
	{
		return FTransform(FRotator::ZeroRotator, Where - FVector(0.0, 0.0, 2000.0), FVector(0.001));
	}

	bool IsPrey(uint8 Species) { return Species == kDeer || Species == kBoar; }

	/** 기준 자세에서 뼈 하나의 컴포넌트 공간 자리 (부모 사슬을 곱함). 없으면 거짓. */
	bool RefBonePos(const FReferenceSkeleton& Ref, int32 Bone, FVector& Out)
	{
		if (Bone == INDEX_NONE)
		{
			return false;
		}
		const TArray<FTransform>& Pose = Ref.GetRefBonePose();
		FTransform T = FTransform::Identity;
		for (int32 b = Bone; b != INDEX_NONE && Pose.IsValidIndex(b); b = Ref.GetParentIndex(b))
		{
			T = T * Pose[b];
		}
		Out = T.GetLocation();
		return true;
	}

	/** 이름에 이 조각이 든 첫 뼈. */
	int32 FindBoneLike(const FReferenceSkeleton& Ref, std::initializer_list<const TCHAR*> Words)
	{
		for (const TCHAR* W : Words)
		{
			for (int32 b = 0; b < Ref.GetNum(); ++b)
			{
				if (Ref.GetBoneName(b).ToString().Contains(W))
				{
					return b;
				}
			}
		}
		return INDEX_NONE;
	}
}

void UEcoR9DemoSubsystem::LoadVisualAssets()
{
	using namespace EcoR9DemoVisualsImpl;
	const bool bTeam = EcoR9DemoCVars::Bodies().Equals(TEXT("team"), ESearchCase::IgnoreCase);
	DeerClass = bTeam ? LoadRepClass(kDeerTeam) : LoadRepClass(kDeerJyu);
	if (!DeerClass)
	{
		DeerClass = LoadRepClass(bTeam ? kDeerJyu : kDeerTeam);
	}
	if (!DeerClass)
	{
		DeerClass = AEcoHerbivoreRepresentation::StaticClass();
	}
	WolfClass = bTeam ? LoadRepClass(kWolfTeam) : LoadRepClass(kWolfJyu);
	if (!WolfClass)
	{
		WolfClass = LoadRepClass(bTeam ? kWolfJyu : kWolfTeam);
	}
	if (!WolfClass)
	{
		WolfClass = AEcoWolfRepresentation::StaticClass();
	}
	GrassMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassA.SM_MWAM_GrassA"));
	if (!GrassMesh)
	{
		GrassMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassA.SM_MWAM_GrassA"));
	}
	GrassMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/JYU/Ecosystem/MI_JYU_EcosystemGrass.MI_JYU_EcosystemGrass"));
	ShrubMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassB.SM_MWAM_GrassB"));
	StoneMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Cover/SM_MWAM_StoneA.SM_MWAM_StoneA"));
	SphereMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	CylinderMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	BasicMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	LoadBoarAssets();
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 몸: 사슴 %s · 늑대 %s · 멧돼지 %s | 풀 %s + %s | 수풀 %s · 돌 %s"), *GetNameSafe(DeerClass), *GetNameSafe(WolfClass),
		   *State->BoarLine, *GetNameSafe(GrassMesh), *GetNameSafe(GrassMaterial), *GetNameSafe(ShrubMesh), *GetNameSafe(StoneMesh));
}

void UEcoR9DemoSubsystem::LoadBoarAssets()
{
	using namespace EcoR9DemoVisualsImpl;
	FEcoR9DemoState& S = *State;
	BoarClass = nullptr;
	BoarMesh = nullptr;
	BoarAnims.Reset();
	BoarAnims.SetNum(static_cast<int32>(ER9AnimRole::Num));
	FString From;
	// 1. 덮어쓰기 (eco.R9Demo.BoarMesh): 표현 BP 클래스 또는 스켈레탈 메시
	const FString Override = EcoR9DemoCVars::BoarMesh();
	if (!Override.IsEmpty())
	{
		if (Override.EndsWith(TEXT("_C")))
		{
			BoarClass = LoadRepClass(*Override);
		}
		if (!BoarClass)
		{
			BoarMesh = LoadObject<USkeletalMesh>(nullptr, *Override);
		}
		From = BoarClass || BoarMesh ? FString::Printf(TEXT("eco.R9Demo.BoarMesh %s"), *Override) : FString();
		if (!BoarClass && !BoarMesh)
		{
			UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] eco.R9Demo.BoarMesh '%s' 를 표현 BP·스켈레탈 메시로 못 읽음 — 스스로 찾는다"), *Override);
		}
	}
	int32 Anims = 0;
#if WITH_EDITOR
	// 2. 에셋 레지스트리 (로드하지 않고 이름·클래스 꼬리표만 봄): 표현 BP (부모가 EcoCreatureRepresentationActor 꼴) 를 모든 뿌리에서 먼저, 그다음 스켈레탈 메시
	if (IAssetRegistry* AR = IAssetRegistry::Get())
	{
		// 팩 폴더는 먼저 동기로 훑어 둔다 (창 없는 -game 실행은 레지스트리가 아직 다 안 읽혔을 수 있다). 디스크에 있는 폴더만
		TArray<FString> ScanPaths;
		for (const TCHAR* Sub : {TEXT("AnimalVarietyPack"), TEXT("JYU/Fauna")})
		{
			if (IFileManager::Get().DirectoryExists(*FPaths::Combine(FPaths::ProjectContentDir(), Sub)))
			{
				ScanPaths.Add(FString(TEXT("/Game/")) + Sub);
			}
		}
		if (!ScanPaths.IsEmpty())
		{
			AR->ScanPathsSynchronous(ScanPaths, /*bForceRescan*/ false);
		}
		auto Best = [AR](const TCHAR* Root, const FTopLevelAssetPath& Class, TFunctionRef<bool(const FAssetData&)> Extra) -> FAssetData
		{
			FARFilter F;
			F.PackagePaths.Add(FName(Root));
			F.bRecursivePaths = true;
			F.ClassPaths.Add(Class);
			TArray<FAssetData> Assets;
			AR->GetAssets(F, Assets);
			FAssetData Pick;
			int32 PickScore = 0;
			for (const FAssetData& A : Assets)
			{
				const std::string Lower = EcoR9Demo::ToLowerAscii(std::string(TCHAR_TO_UTF8(*A.AssetName.ToString())));
				int32 Score = EcoR9Demo::BoarNameScore(Lower);
				if (Score <= 0 || !Extra(A))
				{
					continue;
				}
				Score = Score * 1000 - FMath::Min(999, static_cast<int32>(A.AssetName.GetStringLength()));   // 같은 점수면 짧은 이름 (SK_Pig > SK_Pig_LOD_Test)
				if (Score > PickScore || (Score == PickScore && A.GetObjectPathString() < Pick.GetObjectPathString()))
				{
					Pick = A;
					PickScore = Score;
				}
			}
			return Pick;
		};
		if (!BoarClass && !BoarMesh)
		{
			for (const TCHAR* Root : kBoarRoots)
			{
				const FAssetData Bp = Best(Root, UBlueprint::StaticClass()->GetClassPathName(),
										   [](const FAssetData& A)
										   {
											   FString Parent;
											   return A.GetTagValue(FBlueprintTags::NativeParentClassPath, Parent) && Parent.Contains(TEXT("Representation"));
										   });
				if (Bp.IsValid())
				{
					const FString ClassPath = Bp.PackageName.ToString() + TEXT(".") + Bp.AssetName.ToString() + TEXT("_C");
					BoarClass = LoadRepClass(*ClassPath);
					if (BoarClass)
					{
						From = FString::Printf(TEXT("표현 BP %s (%s 아래)"), *ClassPath, Root);
						break;
					}
				}
			}
		}
		if (!BoarClass && !BoarMesh)
		{
			for (const TCHAR* Root : kBoarRoots)
			{
				const FAssetData Mesh = Best(Root, USkeletalMesh::StaticClass()->GetClassPathName(), [](const FAssetData&) { return true; });
				if (Mesh.IsValid())
				{
					BoarMesh = LoadObject<USkeletalMesh>(nullptr, *Mesh.GetObjectPathString());
					if (BoarMesh)
					{
						From = FString::Printf(TEXT("스켈레탈 메시 %s (%s 아래)"), *Mesh.GetObjectPathString(), Root);
						break;
					}
				}
			}
		}
		// 3. 메시면 같은 스켈레톤 애니: 메시 팩 폴더(…/Pig) → /Game 차례, 이름으로 쓰임을 고른다 (뿌리 움직임·돌기·맞음 변형은 낮게)
		if (BoarMesh && BoarMesh->GetSkeleton())
		{
			const FString SkelPath = BoarMesh->GetSkeleton()->GetPathName();
			const FString MeshDir = FPackageName::GetLongPackagePath(BoarMesh->GetPackage()->GetName());
			const FString PackRoot = FPackageName::GetLongPackagePath(MeshDir);
			TArray<int32> BestScore;
			BestScore.Init(0, static_cast<int32>(ER9AnimRole::Num));
			TArray<FString> BestPath;
			BestPath.SetNum(static_cast<int32>(ER9AnimRole::Num));
			for (const FString& Root : {PackRoot.IsEmpty() ? MeshDir : PackRoot, FString(TEXT("/Game"))})
			{
				FARFilter F;
				F.PackagePaths.Add(FName(*Root));
				F.bRecursivePaths = true;
				F.ClassPaths.Add(UAnimSequence::StaticClass()->GetClassPathName());
				TArray<FAssetData> Assets;
				AR->GetAssets(F, Assets);
				for (const FAssetData& A : Assets)
				{
					FString Skel;
					if (!A.GetTagValue(FName(TEXT("Skeleton")), Skel) || FPackageName::ExportTextPathToObjectPath(Skel) != SkelPath)
					{
						continue;
					}
					int32 Score = 0;
					const ER9AnimRole Role = AnimRoleOf(ToLowerAscii(std::string(TCHAR_TO_UTF8(*A.AssetName.ToString()))), Score);
					const int32 R = static_cast<int32>(Role);
					if (Role != ER9AnimRole::None && Score > BestScore[R])
					{
						BestScore[R] = Score;
						BestPath[R] = A.GetObjectPathString();
					}
				}
				bool bAny = false;
				for (const FString& P : BestPath)
				{
					bAny = bAny || !P.IsEmpty();
				}
				if (bAny)
				{
					break;   // 팩 폴더에서 찾았으면 /Game 전체는 보지 않는다
				}
			}
			for (int32 R = 1; R < static_cast<int32>(ER9AnimRole::Num); ++R)
			{
				if (!BestPath[R].IsEmpty())
				{
					BoarAnims[R] = LoadObject<UAnimSequence>(nullptr, *BestPath[R]);
				}
			}
		}
	}
#endif
	// 4. 에디터 바이너리가 아닌 빌드: AnimalVarietyPack 이름 꼴로 짐작 (있는 패키지만 읽는다 — 없는 경로로 경고를 내지 않게)
	if (!BoarClass && !BoarMesh)
	{
		const TCHAR* const Guess[] = {TEXT("/Game/AnimalVarietyPack/Pig/Meshes/SK_Pig"), TEXT("/Game/AnimalVarietyPack/Boar/Meshes/SK_Boar")};
		for (const TCHAR* Pkg : Guess)
		{
			if (FPackageName::DoesPackageExist(Pkg))
			{
				BoarMesh = LoadObject<USkeletalMesh>(nullptr, *(FString(Pkg) + TEXT(".") + FPackageName::GetShortName(Pkg)));
				if (BoarMesh)
				{
					From = FString::Printf(TEXT("스켈레탈 메시 %s (이름 짐작)"), Pkg);
					break;
				}
			}
		}
	}
	if (BoarMesh && BoarMesh->GetSkeleton())
	{
		bool bAnyAnim = false;
		for (const TObjectPtr<UAnimSequence>& A : BoarAnims)
		{
			bAnyAnim = bAnyAnim || A != nullptr;
		}
		if (!bAnyAnim)
		{
			const FString Dir = FPackageName::GetLongPackagePath(FPackageName::GetLongPackagePath(BoarMesh->GetPackage()->GetName())) + TEXT("/Animations/");
			const FString Base = FPackageName::GetShortName(BoarMesh->GetPackage()->GetName()).Replace(TEXT("SK_"), TEXT(""));
			const TCHAR* const Names[] = {TEXT("IdleBreathe"), TEXT("Idle"), TEXT("Walk"), TEXT("Trot"), TEXT("Run"), TEXT("Eat"), TEXT("Graze"), TEXT("Death"),
										  TEXT("IdleLookAround"), TEXT("Attack")};
			for (const TCHAR* N : Names)
			{
				const FString Pkg = Dir + TEXT("ANIM_") + Base + TEXT("_") + N;
				if (!FPackageName::DoesPackageExist(Pkg))
				{
					continue;
				}
				UAnimSequence* Seq = LoadObject<UAnimSequence>(nullptr, *(Pkg + TEXT(".") + FPackageName::GetShortName(Pkg)));
				int32 Score = 0;
				const int32 R = Seq && Seq->GetSkeleton() == BoarMesh->GetSkeleton()
									? static_cast<int32>(AnimRoleOf(ToLowerAscii(std::string(TCHAR_TO_UTF8(*Seq->GetName()))), Score))
									: 0;
				if (R > 0 && !BoarAnims[R])
				{
					BoarAnims[R] = Seq;
				}
			}
		}
	}
	for (const TObjectPtr<UAnimSequence>& A : BoarAnims)
	{
		Anims += A ? 1 : 0;
	}
	// 5. 메시 맞춤: 앞 방향 (기준 자세 골반 → 머리, 없으면 긴 축 — AnimalVarietyPack 은 +Y 라 −90°), 몸 길이 1.5 m, 발바닥을 땅에
	if (BoarMesh)
	{
		const FReferenceSkeleton& Ref = BoarMesh->GetRefSkeleton();
		FVector Pelvis, Head;
		const bool bBones = RefBonePos(Ref, FindBoneLike(Ref, {TEXT("Pelvis"), TEXT("pelvis"), TEXT("Hips"), TEXT("hips"), TEXT("Spine"), TEXT("spine")}), Pelvis) &&
							RefBonePos(Ref, FindBoneLike(Ref, {TEXT("Head"), TEXT("head"), TEXT("Neck"), TEXT("neck")}), Head);
		const FBoxSphereBounds Bounds = BoarMesh->GetImportedBounds();
		const FVector Fwd = bBones ? (Head - Pelvis) : FVector::ZeroVector;
		if (bBones && Fwd.Size2D() > 1.0)
		{
			BoarYawOffset = static_cast<float>(-FMath::RadiansToDegrees(FMath::Atan2(Fwd.Y, Fwd.X)));
		}
		else
		{
			BoarYawOffset = Bounds.BoxExtent.Y > Bounds.BoxExtent.X ? -90.0f : 0.0f;
		}
		const double Length = 2.0 * FMath::Max(Bounds.BoxExtent.X, Bounds.BoxExtent.Y);
		BoarMeshScale = static_cast<float>(FMath::Clamp(kBoarLengthCm / FMath::Max(1.0, Length), 0.05, 20.0));
		BoarMeshLiftCm = -(Bounds.Origin.Z - Bounds.BoxExtent.Z) * BoarMeshScale;
	}
	if (BoarClass)
	{
		S.BoarLine = FString::Printf(TEXT("%s (%s)"), *GetNameSafe(BoarClass), *From);
	}
	else if (BoarMesh)
	{
		S.BoarLine = FString::Printf(TEXT("%s · 애니 %d/%d · 앞 %.0f° · 배율 %.2f (%s)"), *GetNameSafe(BoarMesh), Anims, static_cast<int32>(ER9AnimRole::Num) - 1, BoarYawOffset,
									 BoarMeshScale, *From);
	}
	else
	{
		S.BoarLine = TEXT("자리표시 (돼지 에셋 없음)");
		UE_LOG(LogEcoR9Demo, Log,
			   TEXT("[EcoR9Demo] 멧돼지 몸: /Game/AnimalVarietyPack/Pig · /Game/JYU/Fauna · /Game 에서 Pig·Boar·Hog·Swine·villsvin 이름의 표현 BP·스켈레탈 메시를 못 찾아 ")
				   TEXT("자리표시로 그린다 — 돼지 에셋을 넣으면 다음 Play 부터 스스로 쓴다 (eco.R9Demo.BoarMesh <경로> 로 직접 줄 수도 있다)"));
	}
}

UInstancedStaticMeshComponent* UEcoR9DemoSubsystem::MakeIsm(AActor* Owner, const TCHAR* Name, UStaticMesh* Mesh, UMaterialInterface* Material, int32 NumCustom,
															bool bShadow)
{
	if (!Owner || !Mesh)
	{
		return nullptr;
	}
	UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(Owner, Name);
	C->SetMobility(EComponentMobility::Movable);
	C->SetStaticMesh(Mesh);
	if (Material)
	{
		C->SetMaterial(0, Material);
	}
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetCanEverAffectNavigation(false);
	C->SetGenerateOverlapEvents(false);
	C->SetCastShadow(bShadow);
	if (NumCustom > 0)
	{
		C->SetNumCustomDataFloats(NumCustom);
	}
	C->SetupAttachment(Owner->GetRootComponent());
	C->RegisterComponent();
	Owner->AddInstanceComponent(C);
	return C;
}

void UEcoR9DemoSubsystem::SpawnStaticDecor()
{
	using namespace EcoR9DemoVisualsImpl;
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	FActorSpawnParameters P;
	P.Name = MakeUniqueObjectName(World->PersistentLevel, AActor::StaticClass(), TEXT("EcoR9Demo_Decor"));
	P.ObjectFlags |= RF_Transient;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AActor* Decor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, P);
	if (!Decor)
	{
		return;
	}
	Decor->SetReplicates(false);
	USceneComponent* Root = NewObject<USceneComponent>(Decor, TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	Decor->SetRootComponent(Root);
	Root->RegisterComponent();
	SpawnedActors.Add(Decor);
	S.Decor = Decor;
	const bool bWhole = S.Info.bWhole;
	// 1·2. 풀 덩어리·판 자리: 풀 창(작은 세계 = 격자 전체, 큰 세계 = 카메라 둘레)에 맞춰 UpdateFood 가 만든다
	S.TuftBase.Reset();
	S.GrassIsm.Reset();
	S.DugIsm.Reset();
	S.FoodWin = EcoR9Demo::FR9FoodWindow();
	if (GrassMesh)
	{
		UInstancedStaticMeshComponent* Grass = MakeIsm(Decor, TEXT("R9Grass"), GrassMesh, GrassMaterial, 4, true);
		S.GrassIsm = Grass;
		S.bGrassHidden = true;
		if (SphereMesh && BasicMaterial)
		{
			UMaterialInstanceDynamic* Soil = UMaterialInstanceDynamic::Create(BasicMaterial, Decor);
			Soil->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.10f, 0.065f, 0.04f));
			S.DugIsm = MakeIsm(Decor, TEXT("R9Dug"), SphereMesh, Soil, 0, false);
		}
	}
	// 3. 은신처: 원 둘레에 수풀, 안쪽에 성긴 수풀, 바위 둘 (보이는 표시 — 논리는 원 그대로). 큰 세계는 수백 개라 계층 인스턴스 + 먼 것은 그리지 않음 (250 ~ 320 m)
	if (ShrubMesh)
	{
		UInstancedStaticMeshComponent* Shrubs = nullptr;
		UInstancedStaticMeshComponent* Stones = nullptr;
		if (bWhole)
		{
			auto MakeHism = [&](const TCHAR* Name, UStaticMesh* Mesh) -> UInstancedStaticMeshComponent*
			{
				if (!Mesh)
				{
					return nullptr;
				}
				UHierarchicalInstancedStaticMeshComponent* C = NewObject<UHierarchicalInstancedStaticMeshComponent>(Decor, Name);
				C->SetMobility(EComponentMobility::Movable);
				C->SetStaticMesh(Mesh);
				C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				C->SetCanEverAffectNavigation(false);
				C->SetGenerateOverlapEvents(false);
				C->SetCastShadow(true);
				C->SetCullDistances(25000, 32000);
				C->SetupAttachment(Decor->GetRootComponent());
				C->RegisterComponent();
				Decor->AddInstanceComponent(C);
				return C;
			};
			Shrubs = MakeHism(TEXT("R9ShelterShrubs"), ShrubMesh);
			Stones = MakeHism(TEXT("R9ShelterStones"), StoneMesh);
		}
		else
		{
			Shrubs = MakeIsm(Decor, TEXT("R9ShelterShrubs"), ShrubMesh, nullptr, 0, true);
			Stones = StoneMesh ? MakeIsm(Decor, TEXT("R9ShelterStones"), StoneMesh, nullptr, 0, true) : nullptr;
		}
		TArray<FTransform> ShrubTs, StoneTs;
		uint32 Seed = 1;
		for (const FR9Shelter& Sh : S.Info.Shelters)
		{
			const double RingCm = Sh.R * S.Info.UnitCm;
			const int32 N = bWhole ? FMath::Clamp(FMath::RoundToInt32(2.0 * PI * RingCm / 500.0), 6, 24) : FMath::Clamp(FMath::RoundToInt32(2.0 * PI * RingCm / 350.0), 8, 48);
			for (int32 j = 0; j < N; ++j)
			{
				for (int32 Ring = 0; Ring < 2; ++Ring)
				{
					if (Ring == 1 && ((j % 2) == 1 || bWhole))
					{
						continue;
					}
					const double Frac = Ring == 0 ? 1.0 : 0.55;
					const double A = 2.0 * PI * (j + 0.35 * Hash01(Seed++)) / N;
					double X = 0.0, Y = 0.0;
					S.Map.ToWorld(Sh.X + Sh.R * Frac * FMath::Cos(A), Sh.Y + Sh.R * Frac * FMath::Sin(A), X, Y);
					const double Hgt = (Ring == 0 ? 110.0 : 85.0) * (0.8 + 0.4 * Hash01(Seed++));
					ShrubTs.Add(FitOnGround(ShrubMesh, FVector(X, Y, GroundZ(X, Y)), 360.0 * Hash01(Seed++), Hgt * 1.6, Hgt));
				}
			}
			if (Stones)
			{
				for (int32 k = 0; k < (bWhole ? 1 : 2); ++k)
				{
					const double A = 2.0 * PI * (0.2 + 0.5 * k + 0.1 * Hash01(Seed++));
					double X = 0.0, Y = 0.0;
					S.Map.ToWorld(Sh.X + 0.8 * Sh.R * FMath::Cos(A), Sh.Y + 0.8 * Sh.R * FMath::Sin(A), X, Y);
					StoneTs.Add(FitOnGround(StoneMesh, FVector(X, Y, GroundZ(X, Y) - 10.0), 360.0 * Hash01(Seed++), 140.0, 80.0));
				}
			}
		}
		if (Shrubs && !ShrubTs.IsEmpty())
		{
			Shrubs->AddInstances(ShrubTs, false, true, false);
		}
		if (Stones && !StoneTs.IsEmpty())
		{
			Stones->AddInstances(StoneTs, false, true, false);
		}
	}
	// 4. 무대 가장자리 (보이지 않는 벽 자리): 낮은 돌을 6 m 마다 — 작은 세계만 (큰 세계는 벽이 땅 밖 50 m 바다·빈 곳이다)
	if (StoneMesh && !bWhole)
	{
		UInstancedStaticMeshComponent* Border = MakeIsm(Decor, TEXT("R9Border"), StoneMesh, nullptr, 0, false);
		TArray<FTransform> Ts;
		const double Every = 3.0;   // 단위
		uint32 Seed = 7;
		auto Add = [&](double U, double V)
		{
			double X = 0.0, Y = 0.0;
			S.Map.ToWorld(U, V, X, Y);
			Ts.Add(FitOnGround(StoneMesh, FVector(X, Y, GroundZ(X, Y) - 5.0), 360.0 * Hash01(Seed++), 55.0, 30.0));
		};
		for (double U = 0.0; U <= S.Info.W + 1e-6; U += Every)
		{
			Add(U, 0.0);
			Add(U, S.Info.H);
		}
		for (double V = Every; V < S.Info.H - 1e-6; V += Every)
		{
			Add(0.0, V);
			Add(S.Info.W, V);
		}
		if (Border && !Ts.IsEmpty())
		{
			Border->AddInstances(Ts, false, true, false);
		}
	}
	// 5. 물기 표시 (작은 점: 빨강 = 물림, 주황 = 받아침, 회색 = 굶음) — 번쩍임·소리 없음
	if (SphereMesh && BasicMaterial)
	{
		const FLinearColor Colors[3] = {FLinearColor(0.85f, 0.05f, 0.04f), FLinearColor(1.0f, 0.5f, 0.05f), FLinearColor(0.45f, 0.45f, 0.45f)};
		const TCHAR* Names[3] = {TEXT("R9MarkBite"), TEXT("R9MarkCounter"), TEXT("R9MarkStarve")};
		for (int32 k = 0; k < 3; ++k)
		{
			UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(BasicMaterial, Decor);
			Mid->SetVectorParameterValue(TEXT("Color"), Colors[k]);
			S.MarkIsm[k] = MakeIsm(Decor, Names[k], SphereMesh, Mid, 0, false);
		}
		// 6. 먼 개체 표식 (큰 세계 — 몸 액터가 없는 산 개체): 사슴 갈색 · 늑대 회색 · 멧돼지 검은 갈색 (섬 무대 먼 표식과 같은 꼴)
		const FLinearColor Far[3] = {FLinearColor(0.45f, 0.26f, 0.10f), FLinearColor(0.35f, 0.35f, 0.38f), FLinearColor(0.12f, 0.08f, 0.06f)};
		const TCHAR* FarNames[3] = {TEXT("R9FarDeer"), TEXT("R9FarWolf"), TEXT("R9FarBoar")};
		for (int32 k = 0; k < 3; ++k)
		{
			UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(BasicMaterial, Decor);
			Mid->SetVectorParameterValue(TEXT("Color"), Far[k]);
			S.FarIsm[k] = MakeIsm(Decor, FarNames[k], SphereMesh, Mid, 0, false);
		}
	}
}

AActor* UEcoR9DemoSubsystem::SpawnBoarPlaceholder(uint32 Id, const FVector& Location, float YawDeg)
{
	UWorld* World = GetWorld();
	if (!SphereMesh || !CylinderMesh)
	{
		return nullptr;
	}
	FActorSpawnParameters P;
	P.Name = MakeUniqueObjectName(World->PersistentLevel, AActor::StaticClass(), *FString::Printf(TEXT("EcoR9Demo_Boar_%u"), Id));
	P.ObjectFlags |= RF_Transient;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AActor* A = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform(FRotator(0.0, YawDeg, 0.0), Location), P);
	if (!A)
	{
		return nullptr;
	}
	A->SetReplicates(false);
	USceneComponent* Root = NewObject<USceneComponent>(A, TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	A->SetRootComponent(Root);
	Root->RegisterComponent();
	A->SetActorLocationAndRotation(Location, FRotator(0.0, YawDeg, 0.0));
	auto MakeMid = [this, A](const FLinearColor& Color) -> UMaterialInterface*
	{
		if (!BasicMaterial)
		{
			return nullptr;
		}
		UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(BasicMaterial, A);
		Mid->SetVectorParameterValue(TEXT("Color"), Color);
		return Mid;
	};
	// 멧돼지 털: 어두운 회갈색, 등줄기 갈기는 더 검게 (2026-11-13 — 예전 갈색 자리표시보다 멧돼지답게)
	UMaterialInterface* Hide = MakeMid(FLinearColor(0.085f, 0.065f, 0.050f));
	UMaterialInterface* Dark = MakeMid(FLinearColor(0.030f, 0.022f, 0.018f));
	UMaterialInterface* Snout = MakeMid(FLinearColor(0.30f, 0.20f, 0.17f));
	UMaterialInterface* Tusk = MakeMid(FLinearColor(0.90f, 0.88f, 0.80f));
	auto Scene = [A](const TCHAR* Name, USceneComponent* Parent, const FVector& Loc) -> USceneComponent*
	{
		USceneComponent* C = NewObject<USceneComponent>(A, Name);
		C->SetMobility(EComponentMobility::Movable);
		C->SetupAttachment(Parent);
		C->SetRelativeLocation(Loc);
		C->RegisterComponent();
		A->AddInstanceComponent(C);
		return C;
	};
	auto Part = [A](const TCHAR* Name, UStaticMesh* Mesh, USceneComponent* Parent, const FVector& Loc, const FRotator& Rot, const FVector& Scale,
					UMaterialInterface* Mat)
	{
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(A, Name);
		C->SetMobility(EComponentMobility::Movable);
		C->SetStaticMesh(Mesh);
		if (Mat)
		{
			C->SetMaterial(0, Mat);
		}
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetGenerateOverlapEvents(false);
		C->SetCanEverAffectNavigation(false);
		C->SetupAttachment(Parent);
		C->SetRelativeLocationAndRotation(Loc, Rot);
		C->SetRelativeScale3D(Scale);
		C->RegisterComponent();
		A->AddInstanceComponent(C);
	};
	// 멧돼지 꼴 (앞 = +X): 낮고 긴 몸 (앞이 높고 뒤가 처짐), 어깨 혹·등 갈기, 짧은 다리, 쐐기꼴 머리와 납작한 주둥이 끝, 세운 귀, 엄니, 짧은 꼬리 [어림 — 몸 길이 약 1.5 m]
	USceneComponent* Pivot = Scene(TEXT("Pivot"), Root, FVector::ZeroVector);
	Part(TEXT("Body"), SphereMesh, Pivot, FVector(0.0, 0.0, 50.0), FRotator(-4.0, 0.0, 0.0), FVector(1.50, 0.66, 0.60), Hide);
	Part(TEXT("Hump"), SphereMesh, Pivot, FVector(20.0, 0.0, 74.0), FRotator::ZeroRotator, FVector(0.80, 0.52, 0.34), Dark);
	Part(TEXT("Mane"), SphereMesh, Pivot, FVector(-6.0, 0.0, 80.0), FRotator(-6.0, 0.0, 0.0), FVector(1.00, 0.16, 0.12), Dark);
	for (int32 k = 0; k < 4; ++k)
	{
		const double Lx = k < 2 ? 44.0 : -44.0;
		const double Ly = (k % 2) == 0 ? 18.0 : -18.0;
		Part(*FString::Printf(TEXT("Leg%d"), k), CylinderMesh, Pivot, FVector(Lx, Ly, 13.0), FRotator::ZeroRotator, FVector(0.11, 0.11, 0.27), Dark);
	}
	Part(TEXT("Tail"), CylinderMesh, Pivot, FVector(-76.0, 0.0, 56.0), FRotator(-35.0, 0.0, 0.0), FVector(0.03, 0.03, 0.16), Dark);
	USceneComponent* Head = Scene(TEXT("Head"), Pivot, FVector(66.0, 0.0, 58.0));
	Part(TEXT("Skull"), SphereMesh, Head, FVector::ZeroVector, FRotator(-12.0, 0.0, 0.0), FVector(0.62, 0.42, 0.44), Hide);
	Part(TEXT("Snout"), CylinderMesh, Head, FVector(32.0, 0.0, -8.0), FRotator(-80.0, 0.0, 0.0), FVector(0.22, 0.20, 0.26), Hide);
	Part(TEXT("Disc"), CylinderMesh, Head, FVector(45.0, 0.0, -10.0), FRotator(-80.0, 0.0, 0.0), FVector(0.20, 0.18, 0.02), Snout);
	Part(TEXT("EarL"), SphereMesh, Head, FVector(-8.0, 13.0, 22.0), FRotator(0.0, 0.0, 20.0), FVector(0.09, 0.05, 0.18), Dark);
	Part(TEXT("EarR"), SphereMesh, Head, FVector(-8.0, -13.0, 22.0), FRotator(0.0, 0.0, -20.0), FVector(0.09, 0.05, 0.18), Dark);
	Part(TEXT("TuskL"), CylinderMesh, Head, FVector(34.0, 9.0, -14.0), FRotator(60.0, 0.0, 0.0), FVector(0.035, 0.035, 0.12), Tusk);
	Part(TEXT("TuskR"), CylinderMesh, Head, FVector(34.0, -9.0, -14.0), FRotator(60.0, 0.0, 0.0), FVector(0.035, 0.035, 0.12), Tusk);
	return A;
}

AActor* UEcoR9DemoSubsystem::SpawnBoarSkeletal(uint32 Id, const FVector& Location, float YawDeg, USkeletalMeshComponent*& OutMesh)
{
	OutMesh = nullptr;
	UWorld* World = GetWorld();
	if (!BoarMesh)
	{
		return nullptr;
	}
	FActorSpawnParameters P;
	P.Name = MakeUniqueObjectName(World->PersistentLevel, AActor::StaticClass(), *FString::Printf(TEXT("EcoR9Demo_Boar_%u"), Id));
	P.ObjectFlags |= RF_Transient;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AActor* A = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform(FRotator(0.0, YawDeg, 0.0), Location), P);
	if (!A)
	{
		return nullptr;
	}
	A->SetReplicates(false);
	USceneComponent* Root = NewObject<USceneComponent>(A, TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	A->SetRootComponent(Root);
	Root->RegisterComponent();
	USceneComponent* Pivot = NewObject<USceneComponent>(A, TEXT("Pivot"));
	Pivot->SetMobility(EComponentMobility::Movable);
	Pivot->SetupAttachment(Root);
	Pivot->RegisterComponent();
	A->AddInstanceComponent(Pivot);
	USkeletalMeshComponent* Sk = NewObject<USkeletalMeshComponent>(A, TEXT("BoarMesh"));
	Sk->SetMobility(EComponentMobility::Movable);
	Sk->SetSkeletalMesh(BoarMesh);
	Sk->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Sk->SetGenerateOverlapEvents(false);
	Sk->SetCanEverAffectNavigation(false);
	Sk->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	Sk->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
	Sk->SetupAttachment(Pivot);
	Sk->SetRelativeLocationAndRotation(FVector(0.0, 0.0, BoarMeshLiftCm), FRotator(0.0, BoarYawOffset, 0.0));
	Sk->SetRelativeScale3D(FVector(BoarMeshScale));
	Sk->RegisterComponent();
	A->AddInstanceComponent(Sk);
	A->SetActorLocationAndRotation(Location, FRotator(0.0, YawDeg, 0.0));
	OutMesh = Sk;
	return A;
}

void UEcoR9DemoSubsystem::ClearBodies()
{
	if (!State)
	{
		return;
	}
	for (TPair<uint32, FEcoR9DemoBody>& P : State->Bodies)
	{
		if (AEcoCreatureRepresentationActor* Rep = P.Value.Rep.Get())
		{
			Rep->ClearBinding();
			Rep->Destroy();
		}
		if (AActor* Boar = P.Value.Boar.Get())
		{
			Boar->Destroy();
		}
	}
	State->Bodies.Reset();
	State->NumBodyActors = 0;
}

void UEcoR9DemoSubsystem::OnFrameAdvanced()
{
	using namespace EcoR9DemoVisualsImpl;
	FEcoR9DemoState& S = *State;
	const double Now = GetWorld()->GetTimeSeconds();
	auto AddMarker = [&S, Now](int32 Kind, uint32 Id, const FVector& Where, double Seconds)
	{
		FEcoR9DemoMarker M;
		M.Kind = Kind;
		M.FollowId = Id;
		M.Location = Where;
		M.Until = Now + Seconds;
		S.Markers.Add(M);
	};
	// 1. 사건 (실시간 코어 또는 재생 곁 파일 .events.json): 물기 결과를 가른다
	const bool bFrameEvents = !S.Cur.Events.empty();
	for (const FR9Event& E : S.Cur.Events)
	{
		S.Recent.Add({Now, E.Kind, E.A, E.B});
		FEcoR9DemoBody* Wolf = S.Bodies.Find(E.A);
		FEcoR9DemoBody* Prey = S.Bodies.Find(E.B);
		switch (E.Kind)
		{
		case ER9Event::BiteKill:
			AddMarker(0, E.B, FVector::ZeroVector, 0.8);
			if (Wolf)
			{
				Wolf->AttackUntil = Now + 0.7;
			}
			break;
		case ER9Event::BiteWound:
			AddMarker(0, E.B, FVector::ZeroVector, 0.6);
			++S.BoarWounded;
			if (Wolf)
			{
				Wolf->AttackUntil = Now + 0.7;
			}
			break;
		case ER9Event::Counter:
			AddMarker(1, E.A, FVector::ZeroVector, 0.8);
			++S.Counters;
			if (Prey)
			{
				Prey->RearUntil = Now + 0.6;
			}
			break;
		case ER9Event::Starve:
			AddMarker(2, E.B, FVector::ZeroVector, 1.0);
			break;
		default:
			break;
		}
	}
	// 2. 깃발: 죽음·다시 남·(사건이 없을 때) 물기. 셈은 몸이 없는 먼 개체도 센다 (큰 세계는 가까운 개체만 몸이 있다)
	for (const FR9Agent& A : S.Cur.Agents)
	{
		if (A.Alive() && (A.Flags & kFlagEating) && A.Species < kNumSpecies)
		{
			++S.Eats[A.Species][A.Food >= 0 && A.Food < 3 ? A.Food + 1 : 0];   // 기록 줄 셈만 (그리기와 무관)
		}
		if (A.Alive() && (A.Flags & kFlagNew) && S.StepsShown > 0)
		{
			++S.Respawns;
		}
		FEcoR9DemoBody* B = S.Bodies.Find(A.Id);
		if (A.Dead())
		{
			if (B && B->bDead)
			{
				continue;   // 이미 센 죽음 (같은 uid 가 두 번 나오면 안 됨)
			}
			if (A.Flags & kFlagBittenDead)
			{
				if (A.Species == kDeer)
				{
					++S.DeerKilled;
				}
				else if (A.Species == kBoar)
				{
					++S.BoarKilled;
				}
				else
				{
					++S.WolvesKilled;
				}
				if (!bFrameEvents && B)
				{
					AddMarker(0, A.Id, FVector::ZeroVector, 0.8);
				}
			}
			else if (A.Species == kWolf && (A.Flags & kFlagBite))
			{
				++S.WolvesKilled;   // 반격에 죽은 늑대 (bit7 + bit4)
			}
			else
			{
				++S.Starved;
				if (!bFrameEvents && B)
				{
					AddMarker(2, A.Id, FVector::ZeroVector, 1.0);
				}
			}
			if (!B)
			{
				continue;   // 몸 없는 먼 개체 — 셈만
			}
			B->bDead = true;
			B->DeadAt = Now;
			B->CorpseUnits = FVector2D(A.X, A.Y);
			B->CorpseFrac = 1.0f;
			if (const AActor* Body = B->Rep.IsValid() ? static_cast<const AActor*>(B->Rep.Get()) : B->Boar.Get())
			{
				B->CorpseYaw = static_cast<float>(Body->GetActorRotation().Yaw);
			}
			if (!S.bFoodKnown)
			{
				B->RemoveAt = Now + kCorpseNoFoodSeconds;
			}
			continue;
		}
		if (B && (A.Flags & kFlagBite) && !bFrameEvents)
		{
			if (A.Species == kWolf)
			{
				B->AttackUntil = Now + 0.7;
				S.Recent.Add({Now, ER9Event::BiteWound, A.Id, 0});
			}
			else
			{
				AddMarker(0, A.Id, FVector::ZeroVector, 0.6);
				S.Recent.Add({Now, ER9Event::BiteWound, 0, A.Id});
			}
		}
	}
	// 3. 사체 ↔ 누운 몸: 같은 종 사체가 죽은 자리 곁에 있는 동안 둔다 (고기가 줄면 몸도 조금 작게). 사라지면 치운다
	if (S.bFoodKnown)
	{
		for (TPair<uint32, FEcoR9DemoBody>& P : S.Bodies)
		{
			FEcoR9DemoBody& B = P.Value;
			if (!B.bDead || B.RemoveAt >= 0.0)
			{
				continue;
			}
			const FR9Carcass* Found = nullptr;
			double Best = 0.6 * 0.6;
			for (const FR9Carcass& C : S.Cur.Carcasses)
			{
				const double D2 = FMath::Square(C.X - B.CorpseUnits.X) + FMath::Square(C.Y - B.CorpseUnits.Y);
				if (C.Species == B.Species && C.Meat > 0.0f && D2 <= Best)
				{
					Best = D2;
					Found = &C;
				}
			}
			if (Found)
			{
				B.CorpseFrac = Found->Meat0 > 0.0f ? FMath::Clamp(Found->Meat / Found->Meat0, 0.0f, 1.0f) : 1.0f;
			}
			else if (Now - B.DeadAt > 0.3)
			{
				B.RemoveAt = Now + 1.0;   // 다 먹혔거나 썩어 사라짐
			}
		}
	}
	// 오래된 사건 버리기
	S.Recent.RemoveAll([Now](const FEcoR9DemoRecent& R) { return Now - R.Time > 6.0; });
	UpdateFood();
}

void UEcoR9DemoSubsystem::UpdateFood()
{
	using namespace EcoR9DemoVisualsImpl;
	FEcoR9DemoState& S = *State;
	UInstancedStaticMeshComponent* Grass = S.GrassIsm.Get();
	const int32 G = S.Info.G;
	const double Now = GetWorld()->GetTimeSeconds();
	if (G <= 0 || !Grass || !GrassMesh)
	{
		return;
	}
	// 1. 창: 작은 세계 = 격자 전체 (지금 그대로), 큰 세계 = 카메라 초점 둘레 한 변 2 × GrassRadius
	FR9FoodWindow W;
	if (S.Info.bWhole)
	{
		const FVector Focus = S.bCamInit ? S.CamFocus : S.StageCenter;
		double Ux = 0.0, Uy = 0.0;
		S.Map.ToUnits(Focus.X, Focus.Y, Ux, Uy);
		const double CellCm = S.Info.CellUnits * S.Info.UnitCm;
		const int32 Side = FMath::Clamp(FMath::RoundToInt32(2.0 * 100.0 * EcoR9DemoCVars::GrassRadiusM() / FMath::Max(1.0, CellCm)), 8, G);
		W = PlaceFoodWindow(G, S.Info.CellUnits, Ux, Uy, Side, kWindowSnap);
	}
	else
	{
		W.Nx = W.Ny = G;
	}
	const int32 Cells = W.Cells();
	// 2. 창 값 읽기: 큰 세계는 코어에서 창만 (격자 전체를 베끼지 않음), 작은 세계는 프레임 격자 (실시간·재생 곁 파일)
	const bool bNewWindow = W != S.FoodWin || S.TuftBase.Num() != Cells * 5;
	if (S.Info.bWhole)
	{
		if (!S.Live || !S.Live->ReadFood(W, S.WinGrass, S.WinRoot))
		{
			S.WinGrass.clear();
		}
	}
	else if (static_cast<int32>(S.Cur.Grass.size()) == Cells)
	{
		S.WinGrass = S.Cur.Grass;
		S.WinRoot = S.Cur.Root.size() == S.Cur.Grass.size() ? S.Cur.Root : std::vector<float>();
	}
	else
	{
		S.WinGrass.clear();
	}
	const bool bShow = EcoR9DemoCVars::Grass() && S.bFoodKnown && static_cast<int32>(S.WinGrass.size()) == Cells;
	// 3. 창이 바뀌면 덩어리 자리를 다시 (칸마다 5 덩이 — 가운데 + 칸 × 0.22 네 쪽) · 인스턴스 수를 맞춤
	if (bNewWindow)
	{
		S.FoodWin = W;
		S.TuftBase.Reset();
		S.TuftBase.Reserve(Cells * 5);
		const double CellCm = S.Info.CellUnits * S.Info.UnitCm;
		for (int32 wy = 0; wy < W.Ny; ++wy)
		{
			for (int32 wx = 0; wx < W.Nx; ++wx)
			{
				const int32 Ix = W.X0 + wx;
				const int32 Iy = W.Y0 + wy;
				const int32 Cell = Iy * G + Ix;
				double Cx = 0.0, Cy = 0.0;
				S.Map.ToWorld((Ix + 0.5) * S.Info.CellUnits, (Iy + 0.5) * S.Info.CellUnits, Cx, Cy);
				for (int32 K = 0; K < 5; ++K)
				{
					const double D = CellCm * kTuftOffset;
					const double Ox = K == 1 ? -D : (K == 2 ? D : 0.0);
					const double Oy = K == 3 ? -D : (K == 4 ? D : 0.0);
					const double X = Cx + Ox;
					const double Y = Cy + Oy;
					S.TuftBase.Add(FTransform(FRotator(0.0, static_cast<double>((Cell * 137 + K * 73) % 360), 0.0), FVector(X, Y, GroundZ(X, Y))));
				}
			}
		}
		S.WinQuant.Init(-2, Cells);
		S.DugUntil.Init(-1.0, Cells);
		S.bWinPrevValid = false;
		S.bDugShown = false;
		TArray<FTransform> Ts;
		Ts.Reserve(S.TuftBase.Num());
		for (const FTransform& T : S.TuftBase)
		{
			Ts.Add(Hidden(T.GetLocation()));
		}
		if (Grass->GetInstanceCount() != Ts.Num())
		{
			Grass->ClearInstances();
			Grass->AddInstances(Ts, /*bShouldReturnIndices*/ false, /*bWorldSpace*/ true, /*bUpdateNavigation*/ false);
		}
		else
		{
			Grass->BatchUpdateInstancesTransforms(0, Ts, true, true, true);
		}
		S.bGrassHidden = true;
		if (UInstancedStaticMeshComponent* Dug = S.DugIsm.Get())
		{
			TArray<FTransform> Ds;
			Ds.Reserve(Cells);
			for (int32 k = 0; k < Cells; ++k)
			{
				Ds.Add(Hidden(S.TuftBase[k * 5].GetLocation()));
			}
			if (Dug->GetInstanceCount() != Ds.Num())
			{
				Dug->ClearInstances();
				Dug->AddInstances(Ds, false, true, false);
			}
			else
			{
				Dug->BatchUpdateInstancesTransforms(0, Ds, true, true, true);
			}
		}
	}
	// 4. 풀: 양 눈금(64)이 바뀐 칸만 다시 쓴다. 보이는 크기 = 조연우 식생 식 (폭 280 cm × √양, 높이 60 cm × (0.2 + 0.8 양))
	if (!bShow)
	{
		if (!S.bGrassHidden)
		{
			TArray<FTransform> Ts;
			for (const FTransform& T : S.TuftBase)
			{
				Ts.Add(Hidden(T.GetLocation()));
			}
			Grass->BatchUpdateInstancesTransforms(0, Ts, true, true, true);
			S.bGrassHidden = true;
			S.WinQuant.Init(-2, Cells);
		}
	}
	else
	{
		const FBox Box = GrassMesh->GetBoundingBox();
		const FVector MeshSize = Box.GetSize();
		const double Fit = FMath::Max(1.0, FMath::Max(MeshSize.X, MeshSize.Y));
		const double FitZ = FMath::Max(1.0, MeshSize.Z);
		int32 Changed = 0;
		for (int32 k = 0; k < Cells; ++k)
		{
			const float Food = S.WinGrass[static_cast<std::size_t>(k)];
			const double Amount = FMath::Clamp(static_cast<double>(Food) / S.GrassCapMax, 0.0, 1.0);
			const int16 Q = Food >= kEatMin ? static_cast<int16>(FMath::Clamp(FMath::RoundToInt32(Amount * kGrassQuant), 1, kGrassQuant)) : static_cast<int16>(-1);
			if (Q == S.WinQuant[k])
			{
				continue;
			}
			S.WinQuant[k] = Q;
			++Changed;
			const double Qa = Q > 0 ? static_cast<double>(Q) / kGrassQuant : 0.0;
			const double Width = kTuftWidthCm * FMath::Sqrt(Qa) / Fit;
			const double Height = kTuftHeightCm * (0.2 + 0.8 * Qa) / FitZ;
			const float Custom[4] = {static_cast<float>(Qa), 1.0f, 0.0f, 128.0f / 255.0f};   // 양 · 수분(초록) · 스트레스 0 · 새순 색 중립 (조연우 식생 꼴)
			for (int32 K = 0; K < 5; ++K)
			{
				const int32 I = k * 5 + K;
				const FTransform& Base = S.TuftBase[I];
				const FTransform T = Q > 0 ? FTransform(Base.GetRotation(), Base.GetLocation() - FVector(0.0, 0.0, Box.Min.Z * Height), FVector(Width, Width, Height))
										   : Hidden(Base.GetLocation());
				Grass->UpdateInstanceTransform(I, T, /*bWorldSpace*/ true, /*bMarkRenderStateDirty*/ false, /*bTeleport*/ true);
				Grass->SetCustomData(I, TArrayView<const float>(Custom, 4), false);
			}
		}
		if (Changed > 0)
		{
			Grass->MarkRenderStateDirty();
		}
		S.bGrassHidden = false;
	}
	// 5. 판 자리: 땅속 먹이가 줄어든 칸 (멧돼지만 땅속을 먹는다) — 같은 창의 앞 값과 견준다
	UInstancedStaticMeshComponent* Dug = S.DugIsm.Get();
	if (Dug && S.DugUntil.Num() == Cells && Cells > 0 && static_cast<int32>(S.WinRoot.size()) == Cells)
	{
		if (S.bWinPrevValid && S.WinPrevRoot.size() == S.WinRoot.size() && S.StepsShown > 0)
		{
			for (int32 k = 0; k < Cells; ++k)
			{
				if (S.WinRoot[static_cast<std::size_t>(k)] < S.WinPrevRoot[static_cast<std::size_t>(k)] - 1e-5f)
				{
					S.DugUntil[k] = Now + kDugSeconds;
				}
			}
		}
		S.WinPrevRoot = S.WinRoot;
		S.bWinPrevValid = true;
		bool bAnyDug = false;
		for (int32 k = 0; k < Cells; ++k)
		{
			const double Left = S.DugUntil[k] - Now;
			if (Left > 0.0)
			{
				bAnyDug = true;
				const double Fade = FMath::Clamp(Left / 3.0, 0.25, 1.0);
				const FVector At = S.TuftBase[k * 5].GetLocation();
				Dug->UpdateInstanceTransform(k, FTransform(FRotator(0.0, static_cast<double>((k * 53) % 360), 0.0), At + FVector(0.0, 0.0, 1.0), FVector(1.25 * Fade, 0.95 * Fade, 0.05)),
											 true, false, true);
			}
			else if (S.DugUntil[k] > -0.5)
			{
				Dug->UpdateInstanceTransform(k, Hidden(S.TuftBase[k * 5].GetLocation()), true, false, true);
				S.DugUntil[k] = -1.0;   // 숨김 끝 — 다음부터 다시 쓰지 않는다
				bAnyDug = true;
			}
		}
		if (bAnyDug || S.bDugShown)
		{
			Dug->MarkRenderStateDirty();
		}
		S.bDugShown = bAnyDug;
	}
}

void UEcoR9DemoSubsystem::UpdateMarkers(double Now)
{
	FEcoR9DemoState& S = *State;
	S.Markers.RemoveAll([Now](const FEcoR9DemoMarker& M) { return M.Until < Now; });
	TArray<FTransform> Ts[3];
	for (const FEcoR9DemoMarker& M : S.Markers)
	{
		FVector At = M.Location;
		if (M.FollowId != 0)
		{
			const FEcoR9DemoBody* B = S.Bodies.Find(M.FollowId);
			const AActor* Body = B ? (B->Rep.IsValid() ? static_cast<const AActor*>(B->Rep.Get()) : B->Boar.Get()) : nullptr;
			if (!Body)
			{
				continue;
			}
			At = Body->GetActorLocation() + FVector(0.0, 0.0, 175.0 * FMath::Max(0.6, static_cast<double>(B->Scale)));
		}
		if (M.Kind >= 0 && M.Kind < 3)
		{
			Ts[M.Kind].Add(FTransform(FRotator::ZeroRotator, At, FVector(0.22)));
		}
	}
	for (int32 k = 0; k < 3; ++k)
	{
		UInstancedStaticMeshComponent* Ism = S.MarkIsm[k].Get();
		if (!Ism || (Ism->GetInstanceCount() == 0 && Ts[k].IsEmpty()))
		{
			continue;
		}
		Ism->ClearInstances();
		if (!Ts[k].IsEmpty())
		{
			Ism->AddInstances(Ts[k], false, true, false);
		}
	}
}

FVector UEcoR9DemoSubsystem::CameraEye() const
{
	if (IsValid(Camera))
	{
		return Camera->GetActorLocation();
	}
	const FEcoR9DemoState& S = *State;
	return S.bCamInit ? S.CamFocus : S.StageCenter;
}

void UEcoR9DemoSubsystem::UpdateFarMarkers(const TArray<FVector>* Where)
{
	// 큰 세계: 몸 액터가 없는 산 개체를 종마다 작은 공으로 (크기 = 카메라 거리 × 0.012, 최소 1.5 m — 섬 무대 먼 표식과 같은 식)
	FEcoR9DemoState& S = *State;
	TArray<FTransform> Ts[3];
	if (Where)
	{
		const FVector Eye = CameraEye();
		for (int32 i = 0; i < Where->Num() && i < static_cast<int32>(S.Cur.Agents.size()); ++i)
		{
			const EcoR9Demo::FR9Agent& A = S.Cur.Agents[static_cast<std::size_t>(i)];
			const FVector& P = (*Where)[i];
			if (!A.Alive() || A.Species >= EcoR9Demo::kNumSpecies || P.ContainsNaN() || S.Bodies.Contains(A.Id))
			{
				continue;
			}
			const double SizeCm = FMath::Max(150.0, 0.012 * FVector::Dist(Eye, P));
			Ts[A.Species].Add(FTransform(FRotator::ZeroRotator, P + FVector(0.0, 0.0, 0.5 * SizeCm + 60.0), FVector(SizeCm / 100.0)));
		}
	}
	S.NumFar = 0;
	for (int32 k = 0; k < 3; ++k)
	{
		S.NumFar += Ts[k].Num();
		UInstancedStaticMeshComponent* Ism = S.FarIsm[k].Get();
		if (!Ism)
		{
			continue;
		}
		if (Ism->GetInstanceCount() == Ts[k].Num())
		{
			if (!Ts[k].IsEmpty())
			{
				Ism->BatchUpdateInstancesTransforms(0, Ts[k], /*bWorldSpace*/ true, /*bMarkRenderStateDirty*/ true, /*bTeleport*/ true);
			}
		}
		else
		{
			Ism->ClearInstances();
			if (!Ts[k].IsEmpty())
			{
				Ism->AddInstances(Ts[k], false, true, false);
			}
		}
	}
}

void UEcoR9DemoSubsystem::SyncBodies(double Alpha, float DeltaTime)
{
	using namespace EcoR9DemoVisualsImpl;
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	const double Now = World->GetTimeSeconds();
	const double Step = S.Info.StepSeconds > 0.0 ? S.Info.StepSeconds : 2.0 / 15.0;
	const bool bLod = S.Info.bWhole;
	// 0. 산 개체 자리 (이어 그린 단위 → 언리얼) · 몸 배정 (큰 세계: 카메라에 가까운 개체만 — 나머지는 먼 표식)
	const int32 NA = static_cast<int32>(S.Cur.Agents.size());
	TArray<FVector> Where;
	Where.Init(FVector(std::numeric_limits<double>::quiet_NaN()), NA);
	std::vector<double> Dist(static_cast<std::size_t>(NA), -1.0);
	std::vector<std::uint8_t> Has(static_cast<std::size_t>(NA), 0);
	const FVector Eye = CameraEye();
	for (int32 i = 0; i < NA; ++i)
	{
		const FR9Agent& A = S.Cur.Agents[static_cast<std::size_t>(i)];
		if (!A.Alive() || A.Id == 0 || A.Species >= kNumSpecies)
		{
			continue;
		}
		const FR9Agent* P0 = S.FindPrev(A.Id);
		const bool bPrev = P0 && P0->Alive();
		const double Ux = FMath::Lerp(bPrev ? static_cast<double>(P0->X) : static_cast<double>(A.X), static_cast<double>(A.X), Alpha);
		const double Uy = FMath::Lerp(bPrev ? static_cast<double>(P0->Y) : static_cast<double>(A.Y), static_cast<double>(A.Y), Alpha);
		double X = 0.0, Y = 0.0;
		S.Map.ToWorld(Ux, Uy, X, Y);
		Where[i] = FVector(X, Y, GroundZ(X, Y));
		Dist[static_cast<std::size_t>(i)] = bLod ? FVector::Dist(Eye, Where[i]) : 0.0;
		const FEcoR9DemoBody* B = S.Bodies.Find(A.Id);
		Has[static_cast<std::size_t>(i)] = static_cast<std::uint8_t>(B && !B->bDead ? 1 : 0);
	}
	std::vector<std::uint8_t> Want;
	const double NearCm = bLod ? 100.0 * EcoR9DemoCVars::BodyNearM() : TNumericLimits<double>::Max();
	PickBodies(Dist, Has, NearCm, kBodyKeep, bLod ? EcoR9DemoCVars::BodyBudget() : TNumericLimits<int32>::Max(), Want);
	// 1. 몸에서 멀어진 산 개체 → 몸을 치운다 (큰 세계). 죽은 몸(사체)은 사체가 남는 동안 두되 아주 멀면 치운다
	TArray<uint32> Gone;
	if (bLod)
	{
		for (int32 i = 0; i < NA; ++i)
		{
			const FR9Agent& A = S.Cur.Agents[static_cast<std::size_t>(i)];
			if (Has[static_cast<std::size_t>(i)] && !Want[static_cast<std::size_t>(i)])
			{
				Gone.Add(A.Id);
			}
		}
		for (const TPair<uint32, FEcoR9DemoBody>& P : S.Bodies)
		{
			const AActor* Body = P.Value.Rep.IsValid() ? static_cast<const AActor*>(P.Value.Rep.Get()) : P.Value.Boar.Get();
			if (P.Value.bDead && Body && FVector::Dist(Eye, Body->GetActorLocation()) > 1.6 * NearCm)
			{
				Gone.Add(P.Key);
			}
		}
	}
	// 2. 새로 몸을 줄 개체 → 띄우기 (저장 안 됨). 큰 세계는 한 틱에 kSpawnPerTick 까지 (가까운 차례)
	int32 Spawned = 0;
	for (int32 i = 0; i < NA; ++i)
	{
		const FR9Agent& A = S.Cur.Agents[static_cast<std::size_t>(i)];
		// Id 0 은 표현 액터가 묶이지 않는다 (BindIdentity 가 거부) — 띄웠다 지우기를 프레임마다 되풀이하지 않게 건너뛴다
		if (!Want[static_cast<std::size_t>(i)] || !A.Alive() || A.Id == 0 || S.Bodies.Contains(A.Id) || A.Species >= kNumSpecies)
		{
			continue;
		}
		if (bLod && Spawned >= kSpawnPerTick)
		{
			break;
		}
		const FVector Loc = Where[i];
		const float Yaw = static_cast<float>(FR9StageMap::YawDeg(A.Hx, A.Hy));
		FEcoR9DemoBody B;
		B.Id = A.Id;
		B.Species = A.Species;
		B.Scale = A.Scale > 0.0f ? A.Scale : (A.Age ? 0.75f : 1.0f);
		B.Maturity = A.Maturity >= 0.0f ? A.Maturity : (A.Age ? 0.4f : 1.0f);
		B.BoarYaw = Yaw;
		B.LastLocation = Loc;
		if (A.Species == kBoar && !BoarClass)
		{
			// 멧돼지: 돼지 스켈레탈 메시가 있으면 그 몸, 없으면 자리표시
			USkeletalMeshComponent* Sk = nullptr;
			AActor* Boar = BoarMesh ? SpawnBoarSkeletal(A.Id, Loc, Yaw, Sk) : SpawnBoarPlaceholder(A.Id, Loc, Yaw);
			if (!Boar)
			{
				continue;
			}
			B.Boar = Boar;
			B.BoarSkel = Sk;
			TInlineComponentArray<USceneComponent*> Comps(Boar);
			for (USceneComponent* C : Comps)
			{
				if (C->GetFName() == TEXT("Pivot"))
				{
					B.BoarPivot = C;
				}
				else if (C->GetFName() == TEXT("Head"))
				{
					B.BoarHead = C;
				}
			}
		}
		else
		{
			UClass* Cls = A.Species == kWolf ? WolfClass.Get() : (A.Species == kBoar ? BoarClass.Get() : DeerClass.Get());
			if (!Cls)
			{
				continue;
			}
			static const TCHAR* const Names[3] = {TEXT("Deer"), TEXT("Wolf"), TEXT("Boar")};
			FActorSpawnParameters P;
			P.Name = MakeUniqueObjectName(World->PersistentLevel, Cls, *FString::Printf(TEXT("EcoR9Demo_%s_%u"), Names[A.Species], A.Id));
			P.ObjectFlags |= RF_Transient;
			P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			AEcoCreatureRepresentationActor* Rep =
				World->SpawnActor<AEcoCreatureRepresentationActor>(Cls, FTransform(FRotator(0.0, Yaw, 0.0), Loc), P);
			if (!Rep)
			{
				continue;
			}
			Rep->SetReplicates(false);
			if (!Rep->BindIdentity(kStableIdBase + static_cast<int64>(A.Id), Rep->VisualSpeciesId))
			{
				Rep->Destroy();
				continue;
			}
			if (Rep->IdentityLabel)
			{
				Rep->IdentityLabel->SetHiddenInGame(true);   // 'Herbivore #id' 이름표는 이 화면에서만 숨긴다
			}
			B.Rep = Rep;
			B.VisualSpecies = Rep->VisualSpeciesId;
		}
		S.Bodies.Add(A.Id, B);
		++Spawned;
	}
	// 늑대마다 가장 가까운 산 먹잇감 거리 (단위)
	auto NearestPrey = [&S](const FR9Agent& W) -> double
	{
		double Best = TNumericLimits<double>::Max();
		for (const FR9Agent& O : S.Cur.Agents)
		{
			if (O.Alive() && IsPrey(O.Species))
			{
				Best = FMath::Min(Best, FMath::Sqrt(FMath::Square(static_cast<double>(O.X - W.X)) + FMath::Square(static_cast<double>(O.Y - W.Y))));
			}
		}
		return Best;
	};
	// 3. 몸마다 이번 프레임 상태
	int32 BodyActors = 0;
	for (TPair<uint32, FEcoR9DemoBody>& Pair : S.Bodies)
	{
		FEcoR9DemoBody& B = Pair.Value;
		AActor* Body = B.Rep.IsValid() ? static_cast<AActor*>(B.Rep.Get()) : B.Boar.Get();
		if (!Body || (B.RemoveAt >= 0.0 && Now >= B.RemoveAt) || Gone.Contains(Pair.Key))
		{
			Gone.AddUnique(Pair.Key);
			continue;
		}
		const FR9Agent* Cur = S.FindCur(B.Id);
		if (!B.bDead && (!Cur || Cur->Dead()))
		{
			// 죽음 기록 없이 사라짐 (있으면 안 됨) — 치운다
			Gone.AddUnique(Pair.Key);
			continue;
		}
		++BodyActors;
		const FR9Agent* Prev = B.bDead ? nullptr : S.FindPrev(B.Id);
		double Ux = 0.0, Uy = 0.0, Vx = 0.0, Vy = 0.0;
		double YawDeg = B.CorpseYaw;
		if (B.bDead)
		{
			Ux = B.CorpseUnits.X;
			Uy = B.CorpseUnits.Y;
		}
		else
		{
			const bool bPrev = Prev && Prev->Alive();
			const double X0 = bPrev ? Prev->X : Cur->X;
			const double Y0 = bPrev ? Prev->Y : Cur->Y;
			Ux = FMath::Lerp(X0, static_cast<double>(Cur->X), Alpha);
			Uy = FMath::Lerp(Y0, static_cast<double>(Cur->Y), Alpha);
			Vx = (Cur->X - X0) / Step;
			Vy = (Cur->Y - Y0) / Step;
			const double Yaw1 = FR9StageMap::YawDeg(Cur->Hx, Cur->Hy);
			YawDeg = bPrev ? LerpYawDeg(FR9StageMap::YawDeg(Prev->Hx, Prev->Hy), Yaw1, Alpha) : Yaw1;
		}
		double Wx = 0.0, Wy = 0.0, Wvx = 0.0, Wvy = 0.0;
		S.Map.ToWorld(Ux, Uy, Wx, Wy);
		S.Map.VecToWorld(Vx, Vy, Wvx, Wvy);
		const FVector Pos(Wx, Wy, GroundZ(Wx, Wy));
		const FVector Vel(Wvx, Wvy, 0.0);
		const double Speed = Vel.Size2D();
		const bool bEat = !B.bDead && Cur->Action == kActEat;
		const bool bEating = bEat && (Cur->Flags & kFlagEating) != 0;
		const bool bInShelter = !B.bDead && (Cur->Flags & kFlagInShelter) != 0;
		const bool bRunning = !B.bDead && (Cur->Flags & kFlagRunning) != 0;
		const float Scale = B.bDead ? B.Scale * (0.7f + 0.3f * B.CorpseFrac) : B.Scale;
		if (AEcoCreatureRepresentationActor* Rep = B.Rep.Get())
		{
			const bool bWolf = B.Species == kWolf;
			const bool bPursue = bWolf && bRunning && NearestPrey(*Cur) <= kPursueUnits;
			EEcoSpeciesActivity Activity = EEcoSpeciesActivity::Hold;
			if (B.bDead)
			{
				Activity = Now - B.DeadAt >= kCorpseSettle ? EEcoSpeciesActivity::CorpseSettled : EEcoSpeciesActivity::Hold;
			}
			else if (bWolf && Now < B.AttackUntil)
			{
				Activity = EEcoSpeciesActivity::Attack;
			}
			else if (!bWolf && Now < B.RearUntil)
			{
				Activity = EEcoSpeciesActivity::Attack;   // 멧돼지 표현 BP 의 받아치기 (BP 가 있을 때)
			}
			else if (bEat)
			{
				Activity = bEating ? (bWolf ? EEcoSpeciesActivity::Eat : EEcoSpeciesActivity::Graze) : EEcoSpeciesActivity::Hold;
			}
			else if (IsWalk(Cur->Action) || IsRun(Cur->Action))
			{
				Activity = bPursue ? EEcoSpeciesActivity::Pursue : (bRunning ? EEcoSpeciesActivity::Travel : EEcoSpeciesActivity::Wander);
			}
			else if (Cur->Action == kActShelter && bInShelter && !bWolf)
			{
				Activity = EEcoSpeciesActivity::ShelterHold;   // 은신처 안 웅크림
			}
			else
			{
				Activity = EEcoSpeciesActivity::Vigilant;      // WATCH·밖에서 SHELTER = 서서 둘러봄
			}
			FEcoCreatureVisualState V;
			V.StableAgentId = kStableIdBase + static_cast<int64>(B.Id);
			V.SpeciesId = B.VisualSpecies;
			V.RegionId = kDemoRegionId;   // 팀 지역 이름과 겹치지 않는 이름 — 팀 v3 가 표현 액터를 지역별로 셀 때(TallyTeamWolfVisuals) 어느 지역에도 들지 않게
			V.Sequence = ++B.Sequence;
			V.WorldTime = Now;
			V.Position = Pos;
			V.Velocity = B.bDead ? FVector::ZeroVector : Vel;
			V.bAlive = !B.bDead;
			V.BodyScale = FMath::Clamp(Scale, 0.65f, 1.15f);
			V.Maturity = FMath::Clamp(B.Maturity, 0.0f, 1.0f);
			V.CoatTone = 0.5f;
			V.Appearance = 0;
			const bool bHpKnown = !B.bDead && Cur->Hp >= 0.0f;
			V.bHasVitals = bHpKnown && EcoR9DemoCVars::HpBars() && B.Species != kDeer && Cur->Hp < 0.999f;
			V.NormalizedHealth = bHpKnown ? FMath::Clamp(Cur->Hp, 0.0f, 1.0f) : 1.0f;
			V.NormalizedEnergy = (!B.bDead && Cur->Energy >= 0.0f) ? FMath::Clamp(Cur->Energy, 0.0f, 1.0f) : 1.0f;
			V.bEating = bEating;
			V.bPursuingPrey = bPursue;
			V.Activity = Activity;
			V.SenseSource = EEcoSenseSource::None;
			V.FocusYawDegrees = static_cast<float>(YawDeg);
			V.bDiscontinuity = B.bSnapNext;
			B.bSnapNext = false;
			Rep->ConsumeVisualState(V, DeltaTime);
		}
		else if (AActor* Boar = B.Boar.Get())
		{
			// 멧돼지 몸 (스켈레탈 또는 자리표시): 움직이는 쪽을 보고, 상태별 애니(스켈레탈) 또는 자세(자리표시)
			if (!B.bDead)
			{
				const double Target = Speed > 20.0 ? FMath::RadiansToDegrees(FMath::Atan2(Vel.Y, Vel.X)) : YawDeg;
				B.BoarYaw = FMath::FixedTurn(B.BoarYaw, static_cast<float>(Target), 360.0f * FMath::Max(DeltaTime, 0.0f));
				B.BobPhase = FMath::Fmod(B.BobPhase + static_cast<float>(Speed * DeltaTime / 80.0 * 2.0 * PI), static_cast<float>(2.0 * PI));
			}
			Boar->SetActorLocationAndRotation(Pos, FRotator(0.0, B.BoarYaw, 0.0));
			Boar->SetActorScale3D(FVector(FMath::Clamp(Scale, 0.5f, 1.2f)));
			if (USkeletalMeshComponent* Sk = B.BoarSkel.Get())
			{
				ER9AnimRole Role = ER9AnimRole::Idle;
				if (B.bDead)
				{
					Role = ER9AnimRole::Death;
				}
				else if (Now < B.RearUntil)
				{
					Role = ER9AnimRole::Attack;
				}
				else if (bEating)
				{
					Role = ER9AnimRole::Eat;
				}
				else if (bRunning || Speed > 0.5 * (kBoarWalkCmS + kBoarRunCmS))
				{
					Role = ER9AnimRole::Run;
				}
				else if (Speed > 20.0)
				{
					Role = ER9AnimRole::Walk;
				}
				else if (Cur->Action == kActWatch || (Cur->Action == kActShelter && !bInShelter))
				{
					Role = ER9AnimRole::Alert;
				}
				// 없는 애니는 가까운 것으로: 뛰기 → 걷기 → 서기, 먹기·두리번·받아치기 → 서기
				auto HasAnim = [this](ER9AnimRole R) { return BoarAnims.IsValidIndex(static_cast<int32>(R)) && BoarAnims[static_cast<int32>(R)] != nullptr; };
				if (Role == ER9AnimRole::Run && !HasAnim(Role))
				{
					Role = ER9AnimRole::Walk;
				}
				if (Role == ER9AnimRole::Attack && !HasAnim(Role))
				{
					Role = ER9AnimRole::Alert;
				}
				if (Role != ER9AnimRole::Death && !HasAnim(Role))
				{
					Role = ER9AnimRole::Idle;
				}
				if (static_cast<uint8>(Role) != B.BoarAnim)
				{
					B.BoarAnim = static_cast<uint8>(Role);
					if (UAnimSequence* Seq = HasAnim(Role) ? BoarAnims[static_cast<int32>(Role)].Get() : nullptr)
					{
						Sk->PlayAnimation(Seq, /*bLooping*/ Role != ER9AnimRole::Death && Role != ER9AnimRole::Attack);
					}
				}
				const double Rate = Role == ER9AnimRole::Walk ? Speed / kBoarWalkCmS : (Role == ER9AnimRole::Run ? Speed / kBoarRunCmS : 1.0);
				Sk->SetPlayRate(static_cast<float>(FMath::Clamp(Rate, 0.5, 2.0)));
				if (USceneComponent* Pivot = B.BoarPivot.Get())
				{
					// 죽음 애니가 없으면 옆으로 눕힌다
					const bool bLie = B.bDead && !HasAnim(ER9AnimRole::Death);
					Pivot->SetRelativeLocationAndRotation(FVector(0.0, 0.0, bLie ? 25.0 : 0.0), FRotator(0.0, 0.0, bLie ? 85.0 : 0.0));
				}
			}
			else if (USceneComponent* Pivot = B.BoarPivot.Get())
			{
				FRotator R = FRotator::ZeroRotator;
				FVector L = FVector::ZeroVector;
				if (B.bDead)
				{
					R.Roll = 85.0;
					L.Z = 30.0;
				}
				else
				{
					if (Speed > 20.0)
					{
						L.Z = 4.0 * FMath::Abs(FMath::Sin(B.BobPhase));
					}
					if (bEating)
					{
						R.Pitch = -9.0;
					}
					if (bInShelter && Cur->Action == kActShelter)
					{
						L.Z -= 14.0;
					}
					if (Now < B.RearUntil)
					{
						R.Pitch = 22.0;
						L.X = -10.0;
					}
				}
				Pivot->SetRelativeLocationAndRotation(L, R);
				if (USceneComponent* Head = B.BoarHead.Get())
				{
					FVector Hl(66.0, 0.0, 58.0);
					FRotator Hr = FRotator::ZeroRotator;
					if (!B.bDead && bEat)
					{
						Hl = FVector(70.0, 0.0, bEating ? 30.0 : 40.0);
						Hr.Pitch = bEating ? -35.0 : -20.0;
					}
					else if (!B.bDead && Cur->Action == kActWatch)
					{
						Hl = FVector(70.0, 0.0, 68.0);
						Hr.Pitch = 15.0;
					}
					Head->SetRelativeLocationAndRotation(Hl, Hr);
				}
			}
		}
		B.LastLocation = Pos;
	}
	for (const uint32 Id : Gone)
	{
		if (FEcoR9DemoBody* B = S.Bodies.Find(Id))
		{
			if (AEcoCreatureRepresentationActor* Rep = B->Rep.Get())
			{
				Rep->ClearBinding();
				Rep->Destroy();
			}
			if (AActor* Boar = B->Boar.Get())
			{
				Boar->Destroy();
			}
		}
		S.Bodies.Remove(Id);
	}
	S.NumBodyActors = BodyActors;
	// 4. 먼 개체 표식 (큰 세계 — 몸이 없는 산 개체)
	UpdateFarMarkers(bLod ? &Where : nullptr);
}
