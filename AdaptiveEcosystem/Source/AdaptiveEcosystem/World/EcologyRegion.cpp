// Copyright Epic Games, Inc. All Rights Reserved.

#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "Components/BoxComponent.h"
#include "Engine/World.h"

AEcologyRegion::AEcologyRegion()
{
	PrimaryActorTick.bCanEverTick = false;

	RegionId = FName(TEXT("Forest_A"));

	RegionBounds = CreateDefaultSubobject<UBoxComponent>(TEXT("RegionBounds"));
	RootComponent = RegionBounds;
	RegionBounds->SetBoxExtent(FVector(5000.0f, 5000.0f, 1000.0f));
	RegionBounds->SetCollisionProfileName(TEXT("NoCollision"));
	RegionBounds->SetGenerateOverlapEvents(false);
}

void AEcologyRegion::BeginPlay()
{
	Super::BeginPlay();

	if (UWorld* World = GetWorld())
	{
		if (UEcologyWorldSubsystem* WorldSubsystem = World->GetSubsystem<UEcologyWorldSubsystem>())
		{
			WorldSubsystem->RegisterRegion(this);
		}
	}
}

bool AEcologyRegion::ContainsPosition(const FVector& Position) const
{
	if (!RegionBounds || Position.ContainsNaN()) return false;
	const FVector Local = RegionBounds->GetComponentTransform().InverseTransformPosition(Position);
	const FVector Extent = RegionBounds->GetUnscaledBoxExtent();
	return FMath::Abs(Local.X) <= Extent.X && FMath::Abs(Local.Y) <= Extent.Y && FMath::Abs(Local.Z) <= Extent.Z;
}

bool AEcologyRegion::MakeInitialEcologyState(FRegionEcologyState& OutState) const
{
	if (RegionId.IsNone() || !RegionBounds || !FMath::IsFinite(InitialFoodAmount)
		|| !FMath::IsFinite(FoodCapacity) || FoodCapacity < 0.0f || InitialFoodAmount < 0.0f
		|| InitialFoodAmount > FoodCapacity) return false;
	OutState = FRegionEcologyState();
	OutState.RegionId = RegionId;
	OutState.FoodAmount = InitialFoodAmount;
	OutState.FoodCapacity = FoodCapacity;
	OutState.FoodRegenerationRate = 0.0f;
	OutState.Population = 0;
	OutState.AverageEnergy = 0.0f;
	return true;
}

void AEcologyRegion::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UWorld* World = GetWorld())
	{
		if (UEcologyWorldSubsystem* WorldSubsystem = World->GetSubsystem<UEcologyWorldSubsystem>())
		{
			WorldSubsystem->UnregisterRegion(this);
		}
	}

	Super::EndPlay(EndPlayReason);
}

void AEcologyRegion::ApplyVegetationConsumption(float ConsumedAmount, float GrazingResistance)
{
	// LEGACY ONLY: active resource ownership is UEcologySimulationSubsystem::FRegionEcologyState.
	if (ConsumedAmount <= 0.0f)
	{
		return;
	}

	// Grazing resistance softens the loss of actual plant biomass/density (clamped up to 90% resistance)
	const float ClampedResistance = FMath::Clamp(GrazingResistance, 0.0f, 0.90f);
	const float DensityLoss = ConsumedAmount * (1.0f - ClampedResistance);

	EnvironmentState.VegetationDensity = FMath::Clamp(EnvironmentState.VegetationDensity - DensityLoss, 0.0f, 1.0f);
	EnvironmentState.FoodAvailability = FMath::Clamp(EnvironmentState.FoodAvailability - ConsumedAmount, 0.0f, EnvironmentState.VegetationDensity);
}

void AEcologyRegion::ApplyVegetationRegrowth(float DeltaTime, float GrowthRate, float RegenerationRate)
{
	// LEGACY ONLY: active resource ownership is UEcologySimulationSubsystem::FRegionEcologyState.
	if (DeltaTime <= 0.0f)
	{
		return;
	}

	// Base regrowth speeds per second
	constexpr float BaseGrowthSpeed = 0.02f;
	constexpr float BaseRegenSpeed = 0.04f;

	// Rainfall positively impacts plant biomass growth (Rainfall 0..1 maps to 0.5x..1.5x)
	const float RainFactor = FMath::Clamp(0.5f + EnvironmentState.Rainfall, 0.5f, 1.5f);

	const float GrowthDelta = BaseGrowthSpeed * FMath::Max(0.1f, GrowthRate) * RainFactor * DeltaTime;
	EnvironmentState.VegetationDensity = FMath::Clamp(EnvironmentState.VegetationDensity + GrowthDelta, 0.0f, 1.0f);

	// Food availability regenerates up to current vegetation density
	const float FoodDelta = BaseRegenSpeed * FMath::Max(0.1f, RegenerationRate) * DeltaTime;
	EnvironmentState.FoodAvailability = FMath::Clamp(EnvironmentState.FoodAvailability + FoodDelta, 0.0f, EnvironmentState.VegetationDensity);
}
