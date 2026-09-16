// Copyright Epic Games, Inc. All Rights Reserved.

#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "AdaptiveEcosystem.h"

void UEcologyWorldSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	RegisteredRegions.Empty();
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyWorldSubsystem initialized."));
}

void UEcologyWorldSubsystem::Deinitialize()
{
	RegisteredRegions.Empty();
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyWorldSubsystem deinitialized."));
	Super::Deinitialize();
}

void UEcologyWorldSubsystem::RegisterRegion(AEcologyRegion* InRegion)
{
	if (!InRegion)
	{
		return;
	}

	if (InRegion->RegionId.IsNone())
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("Attempted to register EcologyRegion with None RegionId."));
		return;
	}

	RegisteredRegions.Add(InRegion->RegionId, InRegion);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("Registered EcologyRegion: %s"), *InRegion->RegionId.ToString());
}

void UEcologyWorldSubsystem::UnregisterRegion(AEcologyRegion* InRegion)
{
	if (!InRegion)
	{
		return;
	}

	if (RegisteredRegions.Contains(InRegion->RegionId))
	{
		RegisteredRegions.Remove(InRegion->RegionId);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("Unregistered EcologyRegion: %s"), *InRegion->RegionId.ToString());
	}
}

AEcologyRegion* UEcologyWorldSubsystem::GetRegion(FName InRegionId) const
{
	if (const TWeakObjectPtr<AEcologyRegion>* FoundPtr = RegisteredRegions.Find(InRegionId))
	{
		return FoundPtr->Get();
	}
	return nullptr;
}

bool UEcologyWorldSubsystem::GetEnvironmentState(FName InRegionId, FRegionEnvironmentState& OutState) const
{
	if (AEcologyRegion* Region = GetRegion(InRegionId))
	{
		OutState = Region->GetEnvironmentState();
		return true;
	}
	return false;
}
