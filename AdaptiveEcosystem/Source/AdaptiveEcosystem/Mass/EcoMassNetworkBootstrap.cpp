// Copyright Epic Games, Inc. All Rights Reserved.

#include "Mass/EcoMassNetworkBootstrap.h"

#include "AdaptiveEcosystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassLifecycleSubsystem.h"
#include "World/EcologyRegion.h"
#include "Components/SceneComponent.h"
#include "Mass/EcoMassNetworkSubsystem.h"
#include "Mass/EcoMassNetworkTrait.h"
#include "Mass/EcoMassTags.h"
#include "MassCommonFragments.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityManager.h"
#include "MassEntityTemplate.h"
#include "MassEntityView.h"
#include "MassSpawnerSubsystem.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(EcoMassNetworkBootstrap)

AEcoMassNetworkBootstrap::AEcoMassNetworkBootstrap()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void AEcoMassNetworkBootstrap::PostInitializeComponents()
{
	Super::PostInitializeComponents();

	// Incoming actor channels can deliver a bubble before the client GameState
	// dispatches BeginPlay. Register the local template during level initialization.
	if (GetWorld() && GetWorld()->IsGameWorld())
	{
		RegisterTemplate();
	}
}

void AEcoMassNetworkBootstrap::BeginPlay()
{
	Super::BeginPlay();

	if (GetNetMode() == NM_Client)
	{
		// Idempotent fallback, including configs assigned by Blueprint BeginPlay.
		// Normal client registration already happened in PostInitializeComponents.
		RegisterTemplate();
	}
	else if (bAutoInitialize)
	{
		// Defer until all level actors have finished BeginPlay.
		RegisterTemplate();
		if (UEcoMassLifecycleSubsystem* Lifecycle = GetWorld()->GetSubsystem<UEcoMassLifecycleSubsystem>())
		{
			Lifecycle->RequestInitialization();
		}
	}
	else
	{
		RegisterTemplate();
	}
}

bool AEcoMassNetworkBootstrap::InitializeMassNetwork()
{
	if (GetNetMode() == NM_Client || !GetWorld()) return false;
	UEcoMassLifecycleSubsystem* Lifecycle = GetWorld()->GetSubsystem<UEcoMassLifecycleSubsystem>();
	return Lifecycle && Lifecycle->InitializePopulation() && bInitialized;
}

FName AEcoMassNetworkBootstrap::GetConfiguredRegionId() const
{
	return RegionActor ? RegionActor->RegionId : RegionId;
}

FVector AEcoMassNetworkBootstrap::GetSpawnPosition(int64 Slot) const
{
	const int32 Capacity = FMath::Max(1, SpawnSchedule.RegionPopulationLimit);
	const int32 Side = FMath::CeilToInt(FMath::Sqrt(static_cast<float>(Capacity)));
	const int32 Index = static_cast<int32>(Slot % Capacity);
	return GetActorLocation() + FVector(
		(static_cast<float>(Index % Side) - (Side - 1) * 0.5f) * SpawnSpacing,
		(static_cast<float>(Index / Side) - (Side - 1) * 0.5f) * SpawnSpacing, 0.0f);
}

bool AEcoMassNetworkBootstrap::ValidateConfiguration(const AEcologyRegion& Region, FString& OutError) const
{
	if (GetNetMode() == NM_Client || !SpawnSchedule.IsValid() || SpeciesId.IsNone()
		|| InitialAgentCount < 0 || InitialAgentCount > SpawnSchedule.RegionPopulationLimit
		|| !FMath::IsFinite(SpawnSpacing) || SpawnSpacing < 0.0f
		|| GetConfiguredRegionId() != Region.RegionId || Region.GetWorld() != GetWorld())
	{
		OutError = TEXT("Invalid species, count, interval, spacing or region binding.");
		return false;
	}
	// Validate every reusable spawn slot before any entity is created.
	for (int32 Slot = 0; Slot < SpawnSchedule.RegionPopulationLimit; ++Slot)
	{
		if (!Region.ContainsPosition(GetSpawnPosition(Slot)))
		{
			OutError = FString::Printf(TEXT("Spawn slot %d is outside region %s. Move the Bootstrap or reduce SpawnSpacing."),
				Slot, *Region.RegionId.ToString());
			return false;
		}
	}
	if (!RegisterTemplate())
	{
		OutError = TEXT("Mass template registration failed.");
		return false;
	}
	const auto& Composition = EntityConfig->GetOrCreateEntityTemplate(*GetWorld()).GetCompositionDescriptor();
	// UE 5.8 stores template composition in ElementsBitSet. The deprecated
	// Fragments/Tags fields are not kept in sync by Add(), so never validate those.
	TArray<FString> MissingElements;
	const auto RequireElement = [&Composition, &MissingElements]<typename T>()
	{
		if (!Composition.Contains<T>()) MissingElements.Add(T::StaticStruct()->GetName());
	};
	RequireElement.operator()<FEcoIdentityFragment>();
	RequireElement.operator()<FEcoRegionFragment>();
	RequireElement.operator()<FEcoVitalsFragment>();
	RequireElement.operator()<FEcoTravelFragment>();
	RequireElement.operator()<FEcoLifetimeFragment>();
	RequireElement.operator()<FTransformFragment>();
	RequireElement.operator()<FEcoAuthorityTag>();
	RequireElement.operator()<FEcoAliveTag>();
	const bool bHasClientProxy = Composition.Contains<FEcoClientProxyTag>();
	if (!MissingElements.IsEmpty() || bHasClientProxy)
	{
		OutError = FString::Printf(TEXT("Invalid authority template: Config=%s NetMode=%d Missing=[%s] ForbiddenClientProxy=%s"),
			*GetPathNameSafe(EntityConfig.Get()), static_cast<int32>(GetNetMode()),
			*FString::Join(MissingElements, TEXT(", ")), bHasClientProxy ? TEXT("true") : TEXT("false"));
		return false;
	}
	return true;
}

void AEcoMassNetworkBootstrap::PrepareRuntime(AEcologyRegion& Region, int32 RegionIndex, int32 SpeciesIndex)
{
	RuntimeRegion = &Region;
	RuntimeRegionIndex = RegionIndex;
	RuntimeSpeciesIndex = SpeciesIndex;
}

int32 AEcoMassNetworkBootstrap::ExecuteSpawnRequest(const FEcoSpawnRequest& Request, double ActualSpawnTime)
{
	if (!IsInGameThread() || GetNetMode() == NM_Client || !RuntimeRegion.IsValid()
		|| RuntimeRegionIndex == INDEX_NONE || RuntimeSpeciesIndex == INDEX_NONE || !EntityConfig
		|| Request.RegionId != RuntimeRegion->RegionId || Request.RequestId <= LastExecutedRequestId
		|| Request.Count < 0 || !FMath::IsFinite(ActualSpawnTime) || ActualSpawnTime < 0.0)
	{
		return 0;
	}
	LastExecutedRequestId = Request.RequestId;
	if (Request.Count == 0)
	{
		if (Request.bInitial) bInitialized = true;
		return 0;
	}
	UMassSpawnerSubsystem* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>();
	UEcologySimulationSubsystem* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	if (!Spawner || !Ecology) return 0;
	FMassEntityManager& Manager = Spawner->GetEntityManagerChecked();
	if (Manager.IsProcessing()) return 0;

	// Allocate outside the entity initialization loop. Never call a UObject from a Mass query loop.
	TArray<int64> StableIds;
	StableIds.Reserve(Request.Count);
	for (int32 Index = 0; Index < Request.Count; ++Index)
	{
		const int64 Id = Ecology->AllocateStableAgentId();
		if (Id == EcoIds::InvalidAgentId) return 0;
		StableIds.Add(Id);
	}
	TArray<FMassEntityHandle> Entities;
	const FMassEntityTemplate& Template = EntityConfig->GetOrCreateEntityTemplate(*GetWorld());
	auto CreationContext = Spawner->SpawnEntities(Template, Request.Count, Entities);
	for (int32 Index = 0; Index < Entities.Num(); ++Index)
	{
		FMassEntityView View(Manager, Entities[Index]);
		View.GetFragmentData<FTransformFragment>().GetMutableTransform().SetLocation(GetSpawnPosition(SpawnedSlotCount++));
		FEcoIdentityFragment& Identity = View.GetFragmentData<FEcoIdentityFragment>();
		Identity.StableAgentId = StableIds[Index];
		Identity.SpeciesId = SpeciesId;
		Identity.SpeciesRuntimeIndex = RuntimeSpeciesIndex;
		FEcoRegionFragment& Region = View.GetFragmentData<FEcoRegionFragment>();
		Region.CurrentRegionId = Request.RegionId;
		Region.CurrentRegionIndex = RuntimeRegionIndex;
		View.GetFragmentData<FEcoTravelFragment>() = FEcoTravelFragment();
		FEcoLifetimeFragment& Lifetime = View.GetFragmentData<FEcoLifetimeFragment>();
		Lifetime.SpawnTimeSeconds = ActualSpawnTime;
		Lifetime.NextFeedTimeSeconds = ActualSpawnTime + 20.0;
	}
	// Publish fully initialized agents to MassReplication add observers.
	CreationContext.Reset();
	if (Request.bInitial) bInitialized = Entities.Num() == Request.Count;
	UE_LOG(LogAdaptiveEcosystem, Log,
		TEXT("[Eco Spawn] Region=%s Request=%lld Epoch=%d Cycle=%lld Phase=%d Wave=%lld Initial=%d Count=%d/%d Due=%.2f Born=%.2f"),
		*Request.RegionId.ToString(), Request.RequestId, Request.WorldEpoch, Request.CycleId,
		static_cast<int32>(Request.Phase), Request.WaveIndex, Request.bInitial, Entities.Num(), Request.Count,
		Request.ScheduledTime, ActualSpawnTime);
	return Entities.Num();
}

bool AEcoMassNetworkBootstrap::RegisterTemplate() const
{
	UWorld* World = GetWorld();
	if (!World || !EntityConfig)
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("%s has no Mass EntityConfig assigned."), *GetName());
		return false;
	}

	if (!EntityConfig->FindTrait(UEcoMassNetworkTrait::StaticClass()))
	{
		UE_LOG(LogAdaptiveEcosystem, Error,
			TEXT("%s EntityConfig must contain UEcoMassNetworkTrait."), *GetName());
		return false;
	}

	// UMassReplicationTrait creates its shared replication fragment while the
	// template is built. Verify the game-specific bubble registration first so
	// a lifecycle regression is reported without triggering the engine assert.
	const UEcoMassNetworkSubsystem* NetworkSubsystem = World->GetSubsystem<UEcoMassNetworkSubsystem>();
	if (!NetworkSubsystem || !NetworkSubsystem->IsBubbleInfoClassRegistered())
	{
		UE_LOG(LogAdaptiveEcosystem, Error,
			TEXT("%s cannot register its Mass template: Eco client bubble registration is not ready in world %s (NetMode: %d)."),
			*GetName(), *GetNameSafe(World), static_cast<int32>(World->GetNetMode()));
		return false;
	}

	UMassSpawnerSubsystem* SpawnerSubsystem = World->GetSubsystem<UMassSpawnerSubsystem>();
	if (!SpawnerSubsystem)
	{
		UE_LOG(LogAdaptiveEcosystem, Error,
			TEXT("%s cannot register its Mass template: Mass spawner is unavailable in world %s."),
			*GetName(), *World->GetPathName());
		return false;
	}

	const FMassEntityTemplateID TemplateID = FMassEntityTemplateIDFactory::Make(EntityConfig->GetConfig().GetGuid());
	const bool bAlreadyRegistered = SpawnerSubsystem->GetMassEntityTemplate(TemplateID) != nullptr;
	const FMassEntityTemplate& EntityTemplate = EntityConfig->GetOrCreateEntityTemplate(*World);
	if (!EntityTemplate.IsValid())
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("%s failed to register its Mass entity template."), *GetName());
		return false;
	}

	if (!bAlreadyRegistered)
	{
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("Registered Eco Mass template %s from %s in world %s (NetMode: %d)."),
			*EntityTemplate.GetTemplateID().ToString(), *EntityConfig->GetPathName(),
			*World->GetPathName(), static_cast<int32>(World->GetNetMode()));
	}

	return true;
}
