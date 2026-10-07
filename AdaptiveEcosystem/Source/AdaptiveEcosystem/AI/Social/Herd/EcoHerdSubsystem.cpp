// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/Alarm/EcoThreatSourceComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

UEcoHerdSubsystem::UEcoHerdSubsystem()
{
}

bool UEcoHerdSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	if (!Super::ShouldCreateSubsystem(Outer))
	{
		return false;
	}

	const UWorld* World = Cast<UWorld>(Outer);
	if (!World)
	{
		return false;
	}

	// Active only on Server or Standalone worlds
	return World->GetNetMode() != NM_Client;
}

void UEcoHerdSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	ActiveHerds.Reset();
	InjectedAlarms.Reset();
	ObservedAlarms.Reset();
	ThreatSources.Reset();
	HerdSpeciesIndices.Reset();
	FreeSlots.Reset();
	NextPersistentHerdId = 1;
}

void UEcoHerdSubsystem::Deinitialize()
{
	ActiveHerds.Reset();
	InjectedAlarms.Reset();
	ObservedAlarms.Reset();
	ThreatSources.Reset();
	HerdSpeciesIndices.Reset();
	FreeSlots.Reset();
	Super::Deinitialize();
}

int32 UEcoHerdSubsystem::AllocateHerd(int32 SpeciesRuntimeIndex, const FVector& InitialCenter)
{
	int32 SlotIndex = INDEX_NONE_ECO;
	if (FreeSlots.Num() > 0)
	{
		SlotIndex = FreeSlots.Pop(EAllowShrinking::No);
	}
	else
	{
		SlotIndex = ActiveHerds.AddDefaulted();
		HerdSpeciesIndices.AddDefaulted();
		InjectedAlarms.AddDefaulted();
		ObservedAlarms.AddDefaulted();
	}

	FEcoHerdRuntimeData& NewHerd = ActiveHerds[SlotIndex];
	InjectedAlarms[SlotIndex] = {};
	ObservedAlarms[SlotIndex] = {};
	NewHerd.RuntimeIndex = SlotIndex;
	NewHerd.PersistentHerdId = NextPersistentHerdId++;
	NewHerd.Center = InitialCenter;
	NewHerd.AverageVelocity = FVector::ZeroVector;
	NewHerd.MemberCount = 1;
	NewHerd.Representative.Reset();
	NewHerd.AlarmStrength = 0.0f;
	NewHerd.LastThreatPosition = FVector::ZeroVector;
	NewHerd.LastThreatEvidenceTime = -1.0;
	NewHerd.LastAggregateTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	NewHerd.LastTopologyUpdateTime = NewHerd.LastAggregateTime;

	HerdSpeciesIndices[SlotIndex] = SpeciesRuntimeIndex;

	return SlotIndex;
}

void UEcoHerdSubsystem::ReleaseHerd(int32 RuntimeIndex)
{
	if (ActiveHerds.IsValidIndex(RuntimeIndex) && ActiveHerds[RuntimeIndex].PersistentHerdId != 0)
	{
		ActiveHerds[RuntimeIndex].PersistentHerdId = 0;
		ActiveHerds[RuntimeIndex].MemberCount = 0;
		ActiveHerds[RuntimeIndex].Representative.Reset();
		InjectedAlarms[RuntimeIndex] = {};
		ObservedAlarms[RuntimeIndex] = {};
		ActiveHerds[RuntimeIndex].AlarmStrength = 0.0f;
		ActiveHerds[RuntimeIndex].LastThreatPosition = FVector::ZeroVector;
		ActiveHerds[RuntimeIndex].LastThreatEvidenceTime = -1.0;
		HerdSpeciesIndices[RuntimeIndex] = INDEX_NONE_ECO;
		FreeSlots.Add(RuntimeIndex);
	}
}

bool UEcoHerdSubsystem::IsValidHerdIndex(int32 RuntimeIndex) const
{
	return ActiveHerds.IsValidIndex(RuntimeIndex) && ActiveHerds[RuntimeIndex].PersistentHerdId != 0;
}

bool UEcoHerdSubsystem::GetHerdData(int32 RuntimeIndex, FEcoHerdRuntimeData& OutData) const
{
	if (IsValidHerdIndex(RuntimeIndex))
	{
		OutData = ActiveHerds[RuntimeIndex];
		return true;
	}
	return false;
}

int32 UEcoHerdSubsystem::GetHerdSpeciesIndex(int32 RuntimeIndex) const
{
	if (HerdSpeciesIndices.IsValidIndex(RuntimeIndex))
	{
		return HerdSpeciesIndices[RuntimeIndex];
	}
	return INDEX_NONE_ECO;
}

void UEcoHerdSubsystem::UpdateHerdAggregate(int32 RuntimeIndex, const FVector& Center, const FVector& AvgVelocity, int32 MemberCount, FMassEntityHandle Representative)
{
	if (IsValidHerdIndex(RuntimeIndex))
	{
		FEcoHerdRuntimeData& Herd = ActiveHerds[RuntimeIndex];
		Herd.Center = Center;
		Herd.AverageVelocity = AvgVelocity;
		Herd.MemberCount = MemberCount;
		Herd.Representative = Representative;
		Herd.LastAggregateTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	}
}

int32 UEcoHerdSubsystem::FindNearestHerd(int32 SpeciesRuntimeIndex, const FVector& Location, float MaxRadius) const
{
	int32 BestIndex = INDEX_NONE_ECO;
	float BestDistSq = MaxRadius * MaxRadius;

	for (int32 i = 0; i < ActiveHerds.Num(); ++i)
	{
		if (!IsValidHerdIndex(i))
		{
			continue;
		}

		if (HerdSpeciesIndices[i] != SpeciesRuntimeIndex)
		{
			continue;
		}

		const float DistSq = FVector::DistSquared(Location, ActiveHerds[i].Center);
		if (DistSq < BestDistSq)
		{
			BestDistSq = DistSq;
			BestIndex = i;
		}
	}

	return BestIndex;
}

void UEcoHerdSubsystem::EmitHerdAlarm(int32 HerdRuntimeIndex, const FVector& ThreatLocation, float Strength)
{
	check(IsInGameThread());
	if (IsValidHerdIndex(HerdRuntimeIndex) && !ThreatLocation.ContainsNaN() && FMath::IsFinite(Strength))
	{
		FEcoHerdAlarmInput& Input = InjectedAlarms[HerdRuntimeIndex];
		const float ClampedStrength = FMath::Clamp(Strength, 0.0f, 1.0f);
		if (ClampedStrength >= Input.Strength)
		{
			Input.Strength = ClampedStrength;
			Input.Position = ThreatLocation;
			Input.EvidenceWorldTime = GetWorld()->GetTimeSeconds();
		}
		ResolveAlarm(HerdRuntimeIndex);
	}
}

int32 UEcoHerdSubsystem::EmitSpatialAlarm(const FVector& ThreatLocation, float Radius, float Strength)
{
	check(IsInGameThread());
	if (ThreatLocation.ContainsNaN() || !FMath::IsFinite(Radius) || Radius < 0.0f || !FMath::IsFinite(Strength) || Strength <= 0.0f)
	{
		return 0;
	}
	int32 AffectedHerds = 0;
	const float RadiusSq = Radius * Radius;

	for (int32 i = 0; i < ActiveHerds.Num(); ++i)
	{
		if (!IsValidHerdIndex(i))
		{
			continue;
		}

		if (FVector::DistSquared(ActiveHerds[i].Center, ThreatLocation) <= RadiusSq)
		{
			EmitHerdAlarm(i, ThreatLocation, Strength);
			++AffectedHerds;
		}
	}

	return AffectedHerds;
}

void UEcoHerdSubsystem::DecayHerdAlarms(float DeltaTime, float DecayRate)
{
	check(IsInGameThread());
	if (!FMath::IsFinite(DeltaTime) || !FMath::IsFinite(DecayRate) || DeltaTime <= 0.0f || DecayRate < 0.0f)
	{
		return;
	}
	for (int32 i = 0; i < ActiveHerds.Num(); ++i)
	{
		if (!IsValidHerdIndex(i))
		{
			continue;
		}

		InjectedAlarms[i].Strength = FMath::Max(0.0f, InjectedAlarms[i].Strength - DecayRate * DeltaTime);
		ObservedAlarms[i].Strength = FMath::Max(0.0f, ObservedAlarms[i].Strength - DecayRate * DeltaTime);
		ResolveAlarm(i);
	}
}

void UEcoHerdSubsystem::ClearHerdAlarms()
{
	check(IsInGameThread());
	for (int32 i = 0; i < ActiveHerds.Num(); ++i)
	{
		if (IsValidHerdIndex(i))
		{
			InjectedAlarms[i] = {};
			ObservedAlarms[i] = {};
			ResolveAlarm(i);
		}
	}
}

void UEcoHerdSubsystem::ResolveAlarm(int32 RuntimeIndex)
{
	const FEcoHerdAlarmInput& Input = ObservedAlarms[RuntimeIndex].Strength >= InjectedAlarms[RuntimeIndex].Strength
		? ObservedAlarms[RuntimeIndex] : InjectedAlarms[RuntimeIndex];
	ActiveHerds[RuntimeIndex].AlarmStrength = Input.Strength;
	ActiveHerds[RuntimeIndex].LastThreatPosition = Input.Strength > 0.0f ? Input.Position : FVector::ZeroVector;
	ActiveHerds[RuntimeIndex].LastThreatEvidenceTime = Input.Strength > 0.0f ? Input.EvidenceWorldTime : -1.0;
}

void UEcoHerdSubsystem::ApplyObservedHerdThreats(TConstArrayView<FEcoObservedHerdThreat> Threats)
{
	check(IsInGameThread());
	for (FEcoHerdAlarmInput& Input : ObservedAlarms)
	{
		Input = {};
	}
	for (const FEcoObservedHerdThreat& Threat : Threats)
	{
		const int32 Index = Threat.HerdRuntimeIndex;
		if (IsValidHerdIndex(Index) && ActiveHerds[Index].PersistentHerdId == Threat.PersistentHerdId
			&& !Threat.Position.ContainsNaN() && FMath::IsFinite(Threat.Strength))
		{
			ObservedAlarms[Index].Position = Threat.Position;
			ObservedAlarms[Index].Strength = FMath::Clamp(Threat.Strength, 0.0f, 1.0f);
			ObservedAlarms[Index].EvidenceWorldTime = GetWorld()->GetTimeSeconds();
		}
	}
	for (int32 Index = 0; Index < ActiveHerds.Num(); ++Index)
	{
		if (IsValidHerdIndex(Index))
		{
			ResolveAlarm(Index);
		}
	}
}

void UEcoHerdSubsystem::RegisterThreatSource(UEcoThreatSourceComponent& Source)
{
	check(IsInGameThread());
	if (Source.GetWorld() == GetWorld() && Source.GetOwner() && Source.GetOwner()->HasAuthority())
	{
		ThreatSources.AddUnique(&Source);
	}
}

void UEcoHerdSubsystem::UnregisterThreatSource(UEcoThreatSourceComponent& Source)
{
	check(IsInGameThread());
	ThreatSources.Remove(&Source);
}

void UEcoHerdSubsystem::GatherActorThreats(TArray<FEcoActorThreatSnapshot>& OutThreats)
{
	check(IsInGameThread());
	OutThreats.Reset();
	ThreatSources.RemoveAll([](const TWeakObjectPtr<UEcoThreatSourceComponent>& Source) { return !Source.IsValid(); });
	for (const TWeakObjectPtr<UEcoThreatSourceComponent>& WeakSource : ThreatSources)
	{
		const UEcoThreatSourceComponent* Source = WeakSource.Get();
		AActor* Actor = Source->GetOwner();
		if (!Source->bThreatEnabled || !Source->IsActive() || !IsValid(Actor) || Actor->IsActorBeingDestroyed()
			|| !Actor->HasAuthority() || !Actor->GetRootComponent() || !FMath::IsFinite(Source->ThreatStrength))
		{
			continue;
		}
		const FVector Position = Actor->GetActorLocation();
		const float Strength = FMath::Clamp(Source->ThreatStrength, 0.0f, 1.0f);
		if (!Position.ContainsNaN() && Strength > 0.0f)
		{
			FEcoActorThreatSnapshot& Snapshot = OutThreats.AddDefaulted_GetRef();
			Snapshot.Actor = Actor;
			Snapshot.Position = Position;
			Snapshot.Strength = Strength;
			Snapshot.SourceKey = (uint64(1) << 63) | Source->GetUniqueID();
		}
	}
}
