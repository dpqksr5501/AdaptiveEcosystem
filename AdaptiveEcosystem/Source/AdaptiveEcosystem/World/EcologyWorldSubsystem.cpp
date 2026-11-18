// Copyright Epic Games, Inc. All Rights Reserved.

#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "AdaptiveEcosystem.h"
#include "Components/BoxComponent.h"

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

	if (const TWeakObjectPtr<AEcologyRegion>* Existing = RegisteredRegions.Find(InRegion->RegionId))
	{
		if (Existing->IsValid() && Existing->Get() != InRegion)
		{
			UE_LOG(LogAdaptiveEcosystem, Error, TEXT("Duplicate Ecology RegionId: %s"), *InRegion->RegionId.ToString());
			return;
		}
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

	if (RegisteredRegions.FindRef(InRegion->RegionId).Get() == InRegion)
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

AEcologyRegion* UEcologyWorldSubsystem::FindRegionAtPosition(const FVector& Position) const
{
	AEcologyRegion* Match = nullptr;
	for (const auto& Pair : RegisteredRegions)
		if (auto* Region = Pair.Value.Get(); Region && Region->ContainsPosition(Position)
			&& (!Match || Pair.Key.LexicalLess(Match->RegionId)))
			Match = Region;
	return Match;
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

bool UEcologyWorldSubsystem::BuildSpatialSnapshots(TConstArrayView<FName> RegionOrder,
	TArray<FEcoRegionSpatialSnapshot>& Out, bool bAllowUnavailableRegions) const
{
	check(IsInGameThread());
	Out.Reset();
	for (FName Id : RegionOrder)
	{
		const AEcologyRegion* Region = GetRegion(Id);
		FEcoRegionSpatialSnapshot& Snapshot = Out.AddDefaulted_GetRef();
		Snapshot.RegionId = Id;
		if (!Region)
		{
			if (!bAllowUnavailableRegions) return false;
			// Preserve the ledger index. Missing regions have no traversable geometry.
			Snapshot.bAvailable = false;
			continue;
		}
		if (!Region->RegionBounds) return false;
		Snapshot.BoundsTransform = Region->RegionBounds->GetComponentTransform();
		Snapshot.BoundsExtent = Region->RegionBounds->GetUnscaledBoxExtent();
		Snapshot.ArrivalPosition = Region->GetActorTransform().TransformPosition(Region->ArrivalOffset);
		const FVector Scale = Snapshot.BoundsTransform.GetScale3D().GetAbs();
		if (!Snapshot.BoundsTransform.IsValid() || Snapshot.BoundsExtent.ContainsNaN()
			|| Snapshot.BoundsExtent.GetMin() <= 0.0 || Scale.GetMin() <= UE_SMALL_NUMBER
			|| !Snapshot.Contains(Snapshot.ArrivalPosition)) return false;
		for (FName Neighbor : Region->AdjacentRegionIds)
		{
			const int32 Index = RegionOrder.IndexOfByKey(Neighbor);
			if (Index == INDEX_NONE || Neighbor == Id) return false;
			Snapshot.AdjacentIndices.AddUnique(Index);
		}
		Snapshot.AdjacentIndices.Sort();
	}
	if (bAllowUnavailableRegions)
		for (auto& Snapshot : Out)
			Snapshot.AdjacentIndices.RemoveAll([&Out](int32 Neighbor) { return !Out[Neighbor].bAvailable; });
	return true;
}
