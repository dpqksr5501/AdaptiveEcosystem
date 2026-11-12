// R9 데모 플레이어 — 보이는 것 (몸·멧돼지 자리표시·풀·판 자리·은신처·가장자리·물기 표시). 그리기만 한다 — 위치·먹이·죽음은 프레임 값 그대로.
//
// 사슴·늑대: 표현 액터(AEcoCreatureRepresentationActor — '받은 값만 그리는' 수동 액터)를 Mass 없이 띄우고 BindIdentity → 매 프레임 ConsumeVisualState.
//   자세는 애님 BP 가 표현 상태(속도·Activity·먹는 중·살아 있음)로 고른다 (EcoCreatureAnimInstance.cpp:49-67).
// 풀: 조연우 AEcoVegetationField 와 같은 메시(SM_MWAM_GrassA)·재질(MI_JYU_EcosystemGrass)·custom data 4 칸(양·수분·스트레스·새순 색)·칸마다 5 덩이 꼴
//   (EcoVegetationField.cpp:532-551, setup_jyu_ecosystem.py:88-90). 조연우 코드·에셋은 읽기만 한다. 값은 R9 먹이 격자 그대로 — 먹으면 줄고 eat_min(0.06) 밑이면 숨고 다시 자란다.

#include "EcoR9DemoSubsystem.h"

#include "EcoR9DemoState.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Core/EcoActivityTypes.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

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
	// 표현 액터 신원 = 이 수 + R9 uid. 팀 맵에서 팀 개체(StableAgentId 는 작은 양수)와 같은 번호가 되지 않게 따로 둔다
	// (팀 살피기 HUD·관찰 카메라가 신원 번호로 표현 액터를 찾음 — EcoCreatureInspection.cpp:41, EcoV3ObserverCamera.cpp:529). 그리기만 바뀐다
	constexpr int64 kStableIdBase = 9000000000000LL;
	const FName kDemoRegionId(TEXT("R9Demo"));

	const TCHAR* const kDeerJyu = TEXT("/Game/JYU/Creatures/BP_JYU_Deer.BP_JYU_Deer_C");
	const TCHAR* const kWolfJyu = TEXT("/Game/JYU/Creatures/BP_JYU_Wolf.BP_JYU_Wolf_C");
	const TCHAR* const kDeerTeam = TEXT("/Game/Creatures/Integrated/BP_EcoDeer.BP_EcoDeer_C");
	const TCHAR* const kWolfTeam = TEXT("/Game/Creatures/Integrated/BP_EcoWolf.BP_EcoWolf_C");

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
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 몸: 사슴 %s · 늑대 %s · 멧돼지 자리표시 | 풀 %s + %s | 수풀 %s · 돌 %s"), *GetNameSafe(DeerClass), *GetNameSafe(WolfClass),
		   *GetNameSafe(GrassMesh), *GetNameSafe(GrassMaterial), *GetNameSafe(ShrubMesh), *GetNameSafe(StoneMesh));
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
	const double CellCm = S.Info.CellUnits * S.Info.UnitCm;
	// 1. 풀 덩어리: 칸마다 5 덩이 (가운데 + 네 쪽), 크기는 매 스텝 UpdateFood 가 먹이 값으로 바꾼다
	S.TuftBase.Reset();
	const int32 G = S.Info.G;
	if (G > 0 && GrassMesh)
	{
		for (int32 iy = 0; iy < G; ++iy)
		{
			for (int32 ix = 0; ix < G; ++ix)
			{
				const int32 Cell = iy * G + ix;
				double Cx = 0.0, Cy = 0.0;
				S.Map.ToWorld((ix + 0.5) * S.Info.CellUnits, (iy + 0.5) * S.Info.CellUnits, Cx, Cy);
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
		UInstancedStaticMeshComponent* Grass = MakeIsm(Decor, TEXT("R9Grass"), GrassMesh, GrassMaterial, 4, true);
		if (Grass)
		{
			TArray<FTransform> Ts;
			Ts.Reserve(S.TuftBase.Num());
			for (const FTransform& T : S.TuftBase)
			{
				Ts.Add(Hidden(T.GetLocation()));
			}
			Grass->AddInstances(Ts, /*bShouldReturnIndices*/ false, /*bWorldSpace*/ true, /*bUpdateNavigation*/ false);
			S.GrassIsm = Grass;
			S.bGrassHidden = true;
		}
		// 2. 멧돼지가 판 자리 (칸마다 하나 — 땅속 먹이가 줄어든 칸에 몇 초)
		if (SphereMesh && BasicMaterial)
		{
			UMaterialInstanceDynamic* Soil = UMaterialInstanceDynamic::Create(BasicMaterial, Decor);
			Soil->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.10f, 0.065f, 0.04f));
			UInstancedStaticMeshComponent* Dug = MakeIsm(Decor, TEXT("R9Dug"), SphereMesh, Soil, 0, false);
			if (Dug)
			{
				TArray<FTransform> Ts;
				for (int32 k = 0; k < G * G; ++k)
				{
					Ts.Add(Hidden(S.TuftBase.IsValidIndex(k * 5) ? S.TuftBase[k * 5].GetLocation() : S.StageCenter));
				}
				Dug->AddInstances(Ts, false, true, false);
				S.DugIsm = Dug;
			}
			S.DugUntil.Init(-1.0, G * G);
		}
	}
	// 3. 은신처: 원 둘레에 수풀, 안쪽에 성긴 수풀, 바위 둘 (보이는 표시 — 논리는 원 그대로)
	if (ShrubMesh)
	{
		UInstancedStaticMeshComponent* Shrubs = MakeIsm(Decor, TEXT("R9ShelterShrubs"), ShrubMesh, nullptr, 0, true);
		UInstancedStaticMeshComponent* Stones = StoneMesh ? MakeIsm(Decor, TEXT("R9ShelterStones"), StoneMesh, nullptr, 0, true) : nullptr;
		TArray<FTransform> ShrubTs, StoneTs;
		uint32 Seed = 1;
		for (const FR9Shelter& Sh : S.Info.Shelters)
		{
			const double RingCm = Sh.R * S.Info.UnitCm;
			const int32 N = FMath::Clamp(FMath::RoundToInt32(2.0 * PI * RingCm / 350.0), 8, 48);
			for (int32 j = 0; j < N; ++j)
			{
				for (int32 Ring = 0; Ring < 2; ++Ring)
				{
					if (Ring == 1 && (j % 2) == 1)
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
				for (int32 k = 0; k < 2; ++k)
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
	// 4. 무대 가장자리 (보이지 않는 벽 자리): 낮은 돌을 6 m 마다
	if (StoneMesh)
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
	UMaterialInterface* Hide = MakeMid(FLinearColor(0.16f, 0.10f, 0.06f));
	UMaterialInterface* Dark = MakeMid(FLinearColor(0.07f, 0.045f, 0.03f));
	UMaterialInterface* Snout = MakeMid(FLinearColor(0.42f, 0.28f, 0.22f));
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
	// 멧돼지 꼴 (앞 = +X): 낮고 긴 몸, 어깨 혹, 큰 머리와 주둥이, 짧은 다리. 크기는 사슴(몸 길이 약 1.6 m)과 견줄 만하게 [어림]
	USceneComponent* Pivot = Scene(TEXT("Pivot"), Root, FVector::ZeroVector);
	Part(TEXT("Body"), SphereMesh, Pivot, FVector(0.0, 0.0, 62.0), FRotator::ZeroRotator, FVector(1.45, 0.72, 0.70), Hide);
	Part(TEXT("Hump"), SphereMesh, Pivot, FVector(14.0, 0.0, 92.0), FRotator::ZeroRotator, FVector(0.75, 0.50, 0.32), Dark);
	for (int32 k = 0; k < 4; ++k)
	{
		const double Lx = k < 2 ? 42.0 : -42.0;
		const double Ly = (k % 2) == 0 ? 20.0 : -20.0;
		Part(*FString::Printf(TEXT("Leg%d"), k), CylinderMesh, Pivot, FVector(Lx, Ly, 18.0), FRotator::ZeroRotator, FVector(0.13, 0.13, 0.36), Dark);
	}
	USceneComponent* Head = Scene(TEXT("Head"), Pivot, FVector(66.0, 0.0, 58.0));
	Part(TEXT("Skull"), SphereMesh, Head, FVector::ZeroVector, FRotator::ZeroRotator, FVector(0.58, 0.48, 0.50), Hide);
	Part(TEXT("Snout"), CylinderMesh, Head, FVector(34.0, 0.0, -6.0), FRotator(90.0, 0.0, 0.0), FVector(0.20, 0.20, 0.22), Snout);
	Part(TEXT("EarL"), SphereMesh, Head, FVector(-6.0, 15.0, 22.0), FRotator::ZeroRotator, FVector(0.10, 0.06, 0.16), Dark);
	Part(TEXT("EarR"), SphereMesh, Head, FVector(-6.0, -15.0, 22.0), FRotator::ZeroRotator, FVector(0.10, 0.06, 0.16), Dark);
	Part(TEXT("TuskL"), CylinderMesh, Head, FVector(36.0, 9.0, -13.0), FRotator(60.0, 0.0, 0.0), FVector(0.04, 0.04, 0.12), Tusk);
	Part(TEXT("TuskR"), CylinderMesh, Head, FVector(36.0, -9.0, -13.0), FRotator(60.0, 0.0, 0.0), FVector(0.04, 0.04, 0.12), Tusk);
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
	// 2. 깃발: 죽음·다시 남·(사건이 없을 때) 물기
	for (const FR9Agent& A : S.Cur.Agents)
	{
		if (A.Alive() && (A.Flags & kFlagEating) && A.Species < kNumSpecies)
		{
			++S.Eats[A.Species][A.Food >= 0 && A.Food < 3 ? A.Food + 1 : 0];   // 기록 줄 셈만 (그리기와 무관)
		}
		FEcoR9DemoBody* B = S.Bodies.Find(A.Id);
		if (A.Dead())
		{
			if (!B || B->bDead)
			{
				continue;
			}
			B->bDead = true;
			B->DeadAt = Now;
			B->CorpseUnits = FVector2D(A.X, A.Y);
			B->CorpseFrac = 1.0f;
			if (const AActor* Body = B->Rep.IsValid() ? static_cast<const AActor*>(B->Rep.Get()) : B->Boar.Get())
			{
				B->CorpseYaw = static_cast<float>(Body->GetActorRotation().Yaw);
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
				if (!bFrameEvents)
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
				if (!bFrameEvents)
				{
					AddMarker(2, A.Id, FVector::ZeroVector, 1.0);
				}
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
	const int32 Cells = G * G;
	const double Now = GetWorld()->GetTimeSeconds();
	const bool bShow = Grass && GrassMesh && EcoR9DemoCVars::Grass() && S.bFoodKnown && static_cast<int32>(S.Cur.Grass.size()) == Cells &&
					   S.TuftBase.Num() == Cells * 5;
	if (Grass && !bShow && !S.bGrassHidden)
	{
		TArray<FTransform> Ts;
		for (const FTransform& T : S.TuftBase)
		{
			Ts.Add(Hidden(T.GetLocation()));
		}
		Grass->BatchUpdateInstancesTransforms(0, Ts, true, true, true);
		S.bGrassHidden = true;
	}
	if (bShow)
	{
		const FBox Box = GrassMesh->GetBoundingBox();
		const FVector MeshSize = Box.GetSize();
		const double Fit = FMath::Max(1.0, FMath::Max(MeshSize.X, MeshSize.Y));
		const double FitZ = FMath::Max(1.0, MeshSize.Z);
		TArray<FTransform> Ts;
		Ts.SetNum(S.TuftBase.Num());
		TArray<float> Amounts;
		Amounts.SetNum(Cells);
		for (int32 k = 0; k < Cells; ++k)
		{
			const float Food = S.Cur.Grass[static_cast<std::size_t>(k)];
			const double Amount = FMath::Clamp(static_cast<double>(Food) / S.GrassCapMax, 0.0, 1.0);
			Amounts[k] = static_cast<float>(Amount);
			const bool bVisible = Food >= kEatMin;
			const double Width = kTuftWidthCm * FMath::Sqrt(Amount) / Fit;
			const double Height = kTuftHeightCm * (0.2 + 0.8 * Amount) / FitZ;
			for (int32 K = 0; K < 5; ++K)
			{
				const FTransform& Base = S.TuftBase[k * 5 + K];
				Ts[k * 5 + K] = bVisible ? FTransform(Base.GetRotation(), Base.GetLocation() - FVector(0.0, 0.0, Box.Min.Z * Height), FVector(Width, Width, Height))
										 : Hidden(Base.GetLocation());
			}
		}
		Grass->BatchUpdateInstancesTransforms(0, Ts, /*bWorldSpace*/ true, /*bMarkRenderStateDirty*/ false, /*bTeleport*/ true);
		float Custom[4] = {0.0f, 1.0f, 0.0f, 128.0f / 255.0f};   // 양 · 수분(초록) · 스트레스 0 · 새순 색 중립 (조연우 식생 꼴)
		for (int32 i = 0; i < Ts.Num(); ++i)
		{
			Custom[0] = Amounts[i / 5];
			Grass->SetCustomData(i, TArrayView<const float>(Custom, 4), false);
		}
		Grass->MarkRenderStateDirty();
		S.bGrassHidden = false;
	}
	// 판 자리: 땅속 먹이가 줄어든 칸 (멧돼지만 땅속을 먹는다)
	UInstancedStaticMeshComponent* Dug = S.DugIsm.Get();
	if (Dug && S.DugUntil.Num() == Cells && Cells > 0)
	{
		if (S.Prev.Root.size() == S.Cur.Root.size() && static_cast<int32>(S.Cur.Root.size()) == Cells && S.StepsShown > 0)
		{
			for (int32 k = 0; k < Cells; ++k)
			{
				if (S.Cur.Root[static_cast<std::size_t>(k)] < S.Prev.Root[static_cast<std::size_t>(k)] - 1e-5f)
				{
					S.DugUntil[k] = Now + kDugSeconds;
				}
			}
		}
		bool bAnyDug = false;
		for (int32 k = 0; k < Cells && !bAnyDug; ++k)
		{
			bAnyDug = S.DugUntil[k] > Now;
		}
		// 판 자국이 없고 앞에도 없었으면 900 개를 다시 쓰지 않는다 (스텝마다 렌더 상태를 새로 만들지 않게)
		if (bAnyDug || S.bDugShown)
		{
			TArray<FTransform> Ts;
			Ts.SetNum(Cells);
			for (int32 k = 0; k < Cells; ++k)
			{
				const FVector At = S.TuftBase.IsValidIndex(k * 5) ? S.TuftBase[k * 5].GetLocation() : S.StageCenter;
				const double Left = S.DugUntil[k] - Now;
				if (Left > 0.0)
				{
					const double Fade = FMath::Clamp(Left / 3.0, 0.25, 1.0);
					Ts[k] = FTransform(FRotator(0.0, static_cast<double>((k * 53) % 360), 0.0), At + FVector(0.0, 0.0, 1.0), FVector(1.25 * Fade, 0.95 * Fade, 0.05));
				}
				else
				{
					Ts[k] = Hidden(At);
				}
			}
			Dug->BatchUpdateInstancesTransforms(0, Ts, true, true, true);
			S.bDugShown = bAnyDug;
		}
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

void UEcoR9DemoSubsystem::SyncBodies(double Alpha, float DeltaTime)
{
	using namespace EcoR9DemoVisualsImpl;
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	const double Now = World->GetTimeSeconds();
	const double Step = S.Info.StepSeconds > 0.0 ? S.Info.StepSeconds : 2.0 / 15.0;
	// 1. 새 개체 → 몸 띄우기 (저장 안 됨)
	for (const FR9Agent& A : S.Cur.Agents)
	{
		// Id 0 은 표현 액터가 묶이지 않는다 (BindIdentity 가 거부) — 띄웠다 지우기를 프레임마다 되풀이하지 않게 건너뛴다
		if (!A.Alive() || A.Id == 0 || S.Bodies.Contains(A.Id) || A.Species >= kNumSpecies)
		{
			continue;
		}
		double X = 0.0, Y = 0.0;
		S.Map.ToWorld(A.X, A.Y, X, Y);
		const FVector Loc(X, Y, GroundZ(X, Y));
		const float Yaw = static_cast<float>(FR9StageMap::YawDeg(A.Hx, A.Hy));
		FEcoR9DemoBody B;
		B.Id = A.Id;
		B.Species = A.Species;
		B.Scale = A.Scale > 0.0f ? A.Scale : (A.Age ? 0.75f : 1.0f);
		B.Maturity = A.Maturity >= 0.0f ? A.Maturity : (A.Age ? 0.4f : 1.0f);
		B.BoarYaw = Yaw;
		B.LastLocation = Loc;
		if (A.Species == kBoar)
		{
			AActor* Boar = SpawnBoarPlaceholder(A.Id, Loc, Yaw);
			if (!Boar)
			{
				continue;
			}
			B.Boar = Boar;
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
			UClass* Cls = A.Species == kWolf ? WolfClass.Get() : DeerClass.Get();
			if (!Cls)
			{
				continue;
			}
			FActorSpawnParameters P;
			P.Name = MakeUniqueObjectName(World->PersistentLevel, Cls,
										  *FString::Printf(TEXT("EcoR9Demo_%s_%u"), A.Species == kWolf ? TEXT("Wolf") : TEXT("Deer"), A.Id));
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
		if ((A.Flags & kFlagNew) && S.StepsShown > 0)
		{
			++S.Respawns;
		}
		S.Bodies.Add(A.Id, B);
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
	// 2. 몸마다 이번 프레임 상태
	TArray<uint32> Gone;
	for (TPair<uint32, FEcoR9DemoBody>& Pair : S.Bodies)
	{
		FEcoR9DemoBody& B = Pair.Value;
		AActor* Body = B.Rep.IsValid() ? static_cast<AActor*>(B.Rep.Get()) : B.Boar.Get();
		if (!Body || (B.RemoveAt >= 0.0 && Now >= B.RemoveAt))
		{
			Gone.Add(Pair.Key);
			continue;
		}
		const FR9Agent* Cur = FindAgent(S.Cur, B.Id);
		if (!B.bDead && (!Cur || Cur->Dead()))
		{
			// 죽음 기록 없이 사라짐 (있으면 안 됨) — 치운다
			Gone.Add(Pair.Key);
			continue;
		}
		const FR9Agent* Prev = B.bDead ? nullptr : FindAgent(S.Prev, B.Id);
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
			// 자리표시 몸: 움직이면 흔들고, 먹으면 머리를 숙이고, 받아치면 몸을 들고, 죽으면 옆으로 눕는다
			if (!B.bDead)
			{
				const double Target = Speed > 20.0 ? FMath::RadiansToDegrees(FMath::Atan2(Vel.Y, Vel.X)) : YawDeg;
				B.BoarYaw = FMath::FixedTurn(B.BoarYaw, static_cast<float>(Target), 360.0f * FMath::Max(DeltaTime, 0.0f));
				B.BobPhase = FMath::Fmod(B.BobPhase + static_cast<float>(Speed * DeltaTime / 80.0 * 2.0 * PI), static_cast<float>(2.0 * PI));
			}
			Boar->SetActorLocationAndRotation(Pos, FRotator(0.0, B.BoarYaw, 0.0));
			Boar->SetActorScale3D(FVector(FMath::Clamp(Scale, 0.5f, 1.2f)));
			if (USceneComponent* Pivot = B.BoarPivot.Get())
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
			}
			if (USceneComponent* Head = B.BoarHead.Get())
			{
				FVector L(66.0, 0.0, 58.0);
				FRotator R = FRotator::ZeroRotator;
				if (!B.bDead && bEat)
				{
					L = FVector(70.0, 0.0, bEating ? 30.0 : 40.0);
					R.Pitch = bEating ? -35.0 : -20.0;
				}
				else if (!B.bDead && Cur->Action == kActWatch)
				{
					L = FVector(70.0, 0.0, 68.0);
					R.Pitch = 15.0;
				}
				Head->SetRelativeLocationAndRotation(L, R);
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
}
