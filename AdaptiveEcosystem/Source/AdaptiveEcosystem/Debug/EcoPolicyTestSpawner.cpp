#include "EcoPolicyTestSpawner.h"

#include "AI/Policy/EcoBehaviorConfig.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "MassMovementFragments.h"

AEcoPolicyTestSpawner::AEcoPolicyTestSpawner()
{
	PrimaryActorTick.bCanEverTick = true;
	// 조향 결과를 보려면 프로세서가 돈 뒤에 그려야 한다.
	PrimaryActorTick.TickGroup = TG_PostPhysics;
}

namespace
{
	FMassEntityManager* GetEntityManager(const UWorld* World)
	{
		if (!World)
		{
			return nullptr;
		}
		UMassEntitySubsystem* Sub = World->GetSubsystem<UMassEntitySubsystem>();
		return Sub ? &Sub->GetMutableEntityManager() : nullptr;
	}
}

void AEcoPolicyTestSpawner::BeginPlay()
{
	Super::BeginPlay();
	SpawnEntities();
}

void AEcoPolicyTestSpawner::EndPlay(const EEndPlayReason::Type Reason)
{
	if (FMassEntityManager* EM = GetEntityManager(GetWorld()))
	{
		for (const FMassEntityHandle& E : Herbivores)
		{
			if (EM->IsEntityValid(E)) { EM->DestroyEntity(E); }
		}
		for (const FMassEntityHandle& E : Predators)
		{
			if (EM->IsEntityValid(E)) { EM->DestroyEntity(E); }
		}
	}
	Herbivores.Reset();
	Predators.Reset();
	PredatorHeadings.Reset();
	Super::EndPlay(Reason);
}

void AEcoPolicyTestSpawner::SpawnEntities()
{
	FMassEntityManager* EM = GetEntityManager(GetWorld());
	if (!EM)
	{
		UE_LOG(LogTemp, Error, TEXT("EcoPolicyTestSpawner: MassEntitySubsystem 이 없다"));
		return;
	}

	// §9.4/§9.5 쿼리가 요구하는 프래그먼트·태그의 합집합.
	const TArray<const UScriptStruct*> HerbComposition = {
		FTransformFragment::StaticStruct(),
		FMassVelocityFragment::StaticStruct(),
		FEcoSteeringGeometryFragment::StaticStruct(),
		FEcoObservationFragment::StaticStruct(),
		FEcoPolicyOutputFragment::StaticStruct(),
		FEcoPolicyRuntimeFragment::StaticStruct(),
		FEcoVitalsFragment::StaticStruct(),
		FEcoHerbivoreTag::StaticStruct(),
	};
	const TArray<const UScriptStruct*> PredComposition = {
		FTransformFragment::StaticStruct(),
		FMassVelocityFragment::StaticStruct(),
		FEcoPredatorTag::StaticStruct(),
	};

	const FMassArchetypeHandle HerbArch = EM->CreateArchetype(HerbComposition);
	const FMassArchetypeHandle PredArch = EM->CreateArchetype(PredComposition);

	const FVector Origin = GetActorLocation();
	FRandomStream Rand(1337);   // 결정적으로 — 같은 배치를 다시 보고 싶을 때가 있다

	auto Spawn = [&](const FMassArchetypeHandle& Arch, int32 Count, float Radius,
					 TArray<FMassEntityHandle>& Out)
	{
		for (int32 i = 0; i < Count; ++i)
		{
			const FMassEntityHandle E = EM->CreateEntity(Arch);
			const float Angle = Rand.FRandRange(0.0f, 2.0f * PI);
			const float R = Radius * FMath::Sqrt(Rand.FRand());   // 면적 균등
			const FVector Loc = Origin + FVector(R * FMath::Cos(Angle), R * FMath::Sin(Angle), 0.0f);

			EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(Loc);
			// 정지 상태면 시야 판정이 전방 축에 고정되므로 초기 속도를 준다.
			const float A2 = Rand.FRandRange(0.0f, 2.0f * PI);
			EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value =
				FVector(FMath::Cos(A2), FMath::Sin(A2), 0.0f) * 10.0f;
			Out.Add(E);
		}
	};

	Spawn(HerbArch, HerbivoreCount, SpawnRadius, Herbivores);
	Spawn(PredArch, PredatorCount, SpawnRadius * 0.7f, Predators);

	// §9.2 "스폰 시 0~PolicyInterval 랜덤" — 정책 부하를 틱마다 고르게 흩는다.
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	for (int32 i = 0; i < Herbivores.Num(); ++i)
	{
		FEcoVitalsFragment& Vitals = EM->GetFragmentDataChecked<FEcoVitalsFragment>(Herbivores[i]);
		Vitals.MaxEnergy = 100.0f;
		Vitals.Energy = Rand.FRandRange(20.0f, 100.0f);
		EM->GetFragmentDataChecked<FEcoPolicyRuntimeFragment>(Herbivores[i]).LastPolicyStep =
			Rand.RandRange(0, Interval - 1);
	}

	PredatorHeadings.SetNum(Predators.Num());
	for (int32 i = 0; i < Predators.Num(); ++i)
	{
		const float A = Rand.FRandRange(0.0f, 2.0f * PI);
		PredatorHeadings[i] = FVector(FMath::Cos(A), FMath::Sin(A), 0.0f);
	}

	bSpawned = true;
	UE_LOG(LogTemp, Log, TEXT("EcoPolicyTestSpawner: 초식 %d, 포식자 %d 스폰. "
							  "eco.UseLearnedPolicy 로 정책을 바꾼다."),
		   Herbivores.Num(), Predators.Num());
}

void AEcoPolicyTestSpawner::MovePredators(float DeltaSeconds)
{
	FMassEntityManager* EM = GetEntityManager(GetWorld());
	if (!EM || Predators.Num() == 0)
	{
		return;
	}
	const float Speed = EcoBehaviorConfig::HerbSpeedCmS * PredatorSpeedRatio;
	const FVector Origin = GetActorLocation();

	for (int32 i = 0; i < Predators.Num(); ++i)
	{
		if (!EM->IsEntityValid(Predators[i])) { continue; }
		FTransformFragment& T = EM->GetFragmentDataChecked<FTransformFragment>(Predators[i]);
		const FVector Pos = T.GetTransform().GetLocation();

		// 가장 가까운 초식을 쫓는다. 없으면 배회.
		FVector Target = FVector::ZeroVector;
		float Best = TNumericLimits<float>::Max();
		for (const FMassEntityHandle& H : Herbivores)
		{
			if (!EM->IsEntityValid(H)) { continue; }
			const FVector HP =
				EM->GetFragmentDataChecked<FTransformFragment>(H).GetTransform().GetLocation();
			const float D = FVector::DistSquared2D(Pos, HP);
			if (D < Best) { Best = D; Target = HP; }
		}

		FVector Dir = Best < TNumericLimits<float>::Max()
						  ? (Target - Pos).GetSafeNormal2D()
						  : PredatorHeadings[i];
		// 반경 밖으로 나가면 안쪽으로 돌린다.
		if (FVector::Dist2D(Pos, Origin) > SpawnRadius)
		{
			Dir = (Origin - Pos).GetSafeNormal2D();
		}
		PredatorHeadings[i] = Dir;

		T.GetMutableTransform().SetLocation(Pos + Dir * Speed * DeltaSeconds);
		EM->GetFragmentDataChecked<FMassVelocityFragment>(Predators[i]).Value = Dir * Speed;
	}
}

void AEcoPolicyTestSpawner::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bSpawned)
	{
		return;
	}
	MovePredators(DeltaSeconds);

	if (bDrawDebug)
	{
		DrawDebug();
	}
	if (LogInterval > 0.0f)
	{
		LogAccumulator += DeltaSeconds;
		if (LogAccumulator >= LogInterval)
		{
			LogAccumulator = 0.0f;
			LogSummary();
		}
	}
}

void AEcoPolicyTestSpawner::DrawDebug() const
{
	const UWorld* World = GetWorld();
	FMassEntityManager* EM = GetEntityManager(World);
	if (!EM) { return; }

	for (const FMassEntityHandle& E : Herbivores)
	{
		if (!EM->IsEntityValid(E)) { continue; }
		const FVector Pos =
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
		const FEcoPolicyActionV1& A = EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action;
		const FEcoSteeringGeometryFragment& G =
			EM->GetFragmentDataChecked<FEcoSteeringGeometryFragment>(E);

		// 색 = cohesion (파이썬 replay.py 와 같은 규약). 파랑 → 빨강.
		const FColor Color = FColor(FMath::Clamp(static_cast<int32>(A.Cohesion * 255.0f), 0, 255),
									60,
									FMath::Clamp(static_cast<int32>((1.0f - A.Cohesion) * 255.0f),
												 0, 255));
		DrawDebugSphere(World, Pos + FVector(0, 0, 50), 60.0f, 8, Color, false, -1.0f, 0, 2.0f);

		// 도주 중이면 굵은 선으로 표시 — §3.3 도주 분기가 켜졌다는 뜻이다.
		if (G.DistPredMin < A.FleeDist * EcoBehaviorConfig::SeeRadiusCm)
		{
			DrawDebugLine(World, Pos + FVector(0, 0, 50),
						  Pos + FVector(0, 0, 50) + G.AwayFromPred * 400.0f,
						  FColor::Yellow, false, -1.0f, 0, 6.0f);
		}
	}

	for (const FMassEntityHandle& E : Predators)
	{
		if (!EM->IsEntityValid(E)) { continue; }
		const FVector Pos =
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation()
			+ FVector(0, 0, 80);
		// 빨간 X (파이썬 replay.py 와 같은 표기)
		const float S = 150.0f;
		DrawDebugLine(World, Pos + FVector(-S, -S, 0), Pos + FVector(S, S, 0),
					  FColor::Red, false, -1.0f, 0, 10.0f);
		DrawDebugLine(World, Pos + FVector(-S, S, 0), Pos + FVector(S, -S, 0),
					  FColor::Red, false, -1.0f, 0, 10.0f);
		DrawDebugCircle(World, Pos, EcoBehaviorConfig::SeeRadiusCm, 32, FColor(90, 0, 0),
						false, -1.0f, 0, 3.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
	}

	DrawDebugCircle(World, GetActorLocation(), SpawnRadius, 64, FColor(60, 60, 60),
					false, -1.0f, 0, 5.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
}

void AEcoPolicyTestSpawner::LogSummary() const
{
	FMassEntityManager* EM = GetEntityManager(GetWorld());
	if (!EM) { return; }

	int32 Moving = 0, Fleeing = 0, SawPredator = 0;
	float SumCohesion = 0.0f, SumFlee = 0.0f, SumForage = 0.0f, SumCover = 0.0f;
	int32 N = 0;

	for (const FMassEntityHandle& E : Herbivores)
	{
		if (!EM->IsEntityValid(E)) { continue; }
		++N;
		const FEcoPolicyActionV1& A = EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action;
		const FEcoSteeringGeometryFragment& G =
			EM->GetFragmentDataChecked<FEcoSteeringGeometryFragment>(E);
		SumForage += A.Forage; SumCohesion += A.Cohesion; SumFlee += A.FleeDist; SumCover += A.Cover;
		if (!EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value.IsNearlyZero()) { ++Moving; }
		if (G.PredatorCount > 0) { ++SawPredator; }
		if (G.DistPredMin < A.FleeDist * EcoBehaviorConfig::SeeRadiusCm) { ++Fleeing; }
	}
	if (N == 0) { return; }

	static IConsoleVariable* CVar =
		IConsoleManager::Get().FindConsoleVariable(TEXT("eco.UseLearnedPolicy"));
	const int32 Mode = CVar ? CVar->GetInt() : -1;

	UE_LOG(LogTemp, Log,
		   TEXT("[Eco] 정책=%s | 개체 %d, 이동 %d, 포식자 본 개체 %d, 도주 %d | "
				"forage %.2f cohesion %.2f flee %.2f cover %.2f"),
		   Mode == 1 ? TEXT("학습") : (Mode == 0 ? TEXT("Utility") : TEXT("?")),
		   N, Moving, SawPredator, Fleeing,
		   SumForage / N, SumCohesion / N, SumFlee / N, SumCover / N);
}
