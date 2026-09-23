// Copyright Epic Games, Inc. All Rights Reserved.

#include "Mass/EcoMassNetworkBootstrap.h"

#include "AdaptiveEcosystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoMassFragments.h"
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
		InitializeMassNetwork();
	}
	else
	{
		RegisterTemplate();
	}
}

bool AEcoMassNetworkBootstrap::InitializeMassNetwork()
{
	if (bInitialized)
	{
		return true;
	}

	if (!RegisterTemplate())
	{
		return false;
	}

	if (GetNetMode() == NM_Client)
	{
		return false;
	}

	UWorld* World = GetWorld();
	UMassSpawnerSubsystem* SpawnerSubsystem = World ? World->GetSubsystem<UMassSpawnerSubsystem>() : nullptr;
	UEcologySimulationSubsystem* EcologySubsystem = World ? World->GetSubsystem<UEcologySimulationSubsystem>() : nullptr;
	if (!SpawnerSubsystem || !EcologySubsystem)
	{
		UE_LOG(LogAdaptiveEcosystem, Error,
			TEXT("%s cannot initialize: Mass spawner or authoritative ecology subsystem is unavailable."), *GetName());
		return false;
	}

	if (InitialAgentCount <= 0)
	{
		bInitialized = true;
		return true;
	}

	const FMassEntityTemplate& EntityTemplate = EntityConfig->GetOrCreateEntityTemplate(*World);
	TArray<FMassEntityHandle> SpawnedEntities;
	auto CreationContext = SpawnerSubsystem->SpawnEntities(EntityTemplate, InitialAgentCount, SpawnedEntities);
	if (SpawnedEntities.Num() != InitialAgentCount)
	{
		UE_LOG(LogAdaptiveEcosystem, Error,
			TEXT("%s requested %d Mass agents but spawned %d."), *GetName(), InitialAgentCount, SpawnedEntities.Num());
		return false;
	}

	FMassEntityManager& EntityManager = SpawnerSubsystem->GetEntityManagerChecked();
	const int32 ColumnCount = FMath::Max(1, FMath::CeilToInt(FMath::Sqrt(static_cast<float>(InitialAgentCount))));
	const FVector Origin = GetActorLocation();

	for (int32 EntityIndex = 0; EntityIndex < SpawnedEntities.Num(); ++EntityIndex)
	{
		FMassEntityView EntityView(EntityManager, SpawnedEntities[EntityIndex]);
		if (!ensure(EntityView.HasFragment<FTransformFragment>()
			&& EntityView.HasFragment<FEcoIdentityFragment>()
			&& EntityView.HasFragment<FEcoRegionFragment>()
			&& EntityView.HasTag<FEcoAuthorityTag>()))
		{
			UE_LOG(LogAdaptiveEcosystem, Error,
				TEXT("%s entity config must contain UEcoMassNetworkTrait."), *GetName());
			return false;
		}

		const int32 Row = EntityIndex / ColumnCount;
		const int32 Column = EntityIndex % ColumnCount;
		const FVector Offset(
			(static_cast<float>(Column) - static_cast<float>(ColumnCount - 1) * 0.5f) * SpawnSpacing,
			static_cast<float>(Row) * SpawnSpacing,
			0.0f);

		EntityView.GetFragmentData<FTransformFragment>().GetMutableTransform().SetLocation(Origin + Offset);

		FEcoIdentityFragment& Identity = EntityView.GetFragmentData<FEcoIdentityFragment>();
		Identity.StableAgentId = EcologySubsystem->AllocateStableAgentId();
		Identity.SpeciesId = SpeciesId;

		FEcoRegionFragment& Region = EntityView.GetFragmentData<FEcoRegionFragment>();
		Region.CurrentRegionId = RegionId;
	}

	// Releasing the creation context dispatches Mass add-observers, including
	// the server-side FMassNetworkID assignment required by MassReplication.
	CreationContext.Reset();
	bInitialized = true;

	UE_LOG(LogAdaptiveEcosystem, Log,
		TEXT("%s initialized %d authoritative Mass agents using template %s."),
		*GetName(), SpawnedEntities.Num(), *EntityTemplate.GetTemplateID().ToString());
	return true;
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
