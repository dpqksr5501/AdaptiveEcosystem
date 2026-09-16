// Copyright Epic Games, Inc. All Rights Reserved.

#include "Creature/CreatureCharacter.h"
#include "Creature/CreatureTraitComponent.h"
#include "Ecology/EcologyServerSubsystem.h"
#include "Engine/World.h"
#include "AdaptiveEcosystem.h"

ACreatureCharacter::ACreatureCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	TraitComponent = CreateDefaultSubobject<UCreatureTraitComponent>(TEXT("TraitComponent"));

	// Set default identification for vertical slice testing
	SpawnData.RegionId = FName(TEXT("Forest_A"));
	SpawnData.SpeciesId = FName(TEXT("Wolf"));
	SpawnData.Generation = 1;
	SpawnData.ProfileRevision = 1;
	SpawnData.StableAgentId = 1001;
}

void ACreatureCharacter::BeginPlay()
{
	Super::BeginPlay();

	// Automatically query and apply species profile from authoritative server subsystem on start
	if (UWorld* World = GetWorld())
	{
		if (UEcologyServerSubsystem* ServerSubsystem = World->GetSubsystem<UEcologyServerSubsystem>())
		{
			FSpeciesEvolutionProfile Profile;
			if (ServerSubsystem->GetSpeciesEvolutionProfile(SpawnData.RegionId, SpawnData.SpeciesId, Profile))
			{
				ApplyProfile(Profile);
			}
			else
			{
				UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("CreatureCharacter [%s]: Failed to query profile for [%s x %s] on BeginPlay."),
					*GetName(), *SpawnData.RegionId.ToString(), *SpawnData.SpeciesId.ToString());
			}
		}
	}
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

void ACreatureCharacter::ApplyDummyVerticalSlice()
{
	if (UWorld* World = GetWorld())
	{
		if (UEcologyServerSubsystem* ServerSubsystem = World->GetSubsystem<UEcologyServerSubsystem>())
		{
			FSpeciesEvolutionProfile DummyProfile;
			if (ServerSubsystem->GetSpeciesEvolutionProfile(FName(TEXT("Forest_A")), FName(TEXT("Wolf")), DummyProfile))
			{
				ApplyProfile(DummyProfile);
				UE_LOG(LogAdaptiveEcosystem, Log, TEXT("CreatureCharacter [%s] successfully applied dummy vertical slice via command: %s"),
					*GetName(), *TraitComponent->GetDebugDescription());
				return;
			}
		}
	}

	// Fallback direct dummy profile apply
	FSpeciesEvolutionProfile DirectDummy = UEcologyServerSubsystem::CreateDummyWolfProfile();
	ApplyProfile(DirectDummy);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("CreatureCharacter [%s] applied fallback dummy vertical slice: %s"),
		*GetName(), *TraitComponent->GetDebugDescription());
}
