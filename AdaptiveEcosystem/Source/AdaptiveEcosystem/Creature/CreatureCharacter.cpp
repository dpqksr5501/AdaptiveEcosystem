// Copyright Epic Games, Inc. All Rights Reserved.

#include "Creature/CreatureCharacter.h"
#include "Creature/CreatureTraitComponent.h"
#include "AdaptiveEcosystem.h"

ACreatureCharacter::ACreatureCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	TraitComponent = CreateDefaultSubobject<UCreatureTraitComponent>(TEXT("TraitComponent"));

	// Default identification placeholders (to be set via InitializeCreature on spawn)
	SpawnData.RegionId = FName(TEXT("Forest_A"));
	SpawnData.SpeciesId = FName(TEXT("Wolf"));
	SpawnData.Generation = 0;
	SpawnData.ProfileRevision = 0;
	SpawnData.StableAgentId = 0;
}

void ACreatureCharacter::BeginPlay()
{
	Super::BeginPlay();

	// Pure representation: does not query server subsystems directly.
	// Expected to be initialized via InitializeCreature() by Server / Spawner / Test Harness.
	UE_LOG(LogAdaptiveEcosystem, Verbose, TEXT("CreatureCharacter [%s]: Spawned. Awaiting initialization."), *GetName());
}

void ACreatureCharacter::InitializeCreature(const FCreatureSpawnData& InSpawnData, const FSpeciesEvolutionProfile& InProfile)
{
	SpawnData = InSpawnData;
	ApplyProfile(InProfile);

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("CreatureCharacter [%s]: Initialized with AgentId=%lld, [%s x %s], Gen=%d, Rev=%lld"),
		*GetName(), SpawnData.StableAgentId, *SpawnData.RegionId.ToString(), *SpawnData.SpeciesId.ToString(),
		SpawnData.Generation, SpawnData.ProfileRevision);
}

void ACreatureCharacter::ApplyProfile(const FSpeciesEvolutionProfile& InProfile)
{
	if (TraitComponent)
	{
		TraitComponent->ApplySpeciesProfile(InProfile);

		// Synchronize generation/revision to local spawn data
		SpawnData.Generation = InProfile.Generation;
		SpawnData.ProfileRevision = InProfile.ProfileRevision;
	}
}
