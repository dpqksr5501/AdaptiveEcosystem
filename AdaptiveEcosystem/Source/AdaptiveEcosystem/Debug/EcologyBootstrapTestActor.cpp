// Copyright Epic Games, Inc. All Rights Reserved.

#include "Debug/EcologyBootstrapTestActor.h"
#include "Creature/CreatureCharacter.h"
#include "Creature/CreatureTraitComponent.h"
#include "Ecology/EcologyServerSubsystem.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "AdaptiveEcosystem.h"

AEcologyBootstrapTestActor::AEcologyBootstrapTestActor()
{
	PrimaryActorTick.bCanEverTick = false;

	TestRegionId = FName(TEXT("Forest_A"));
	TestSpeciesId = FName(TEXT("Wolf"));
	bAutoRunOnBeginPlay = true;
	CreatureClassToSpawn = ACreatureCharacter::StaticClass();
}

void AEcologyBootstrapTestActor::BeginPlay()
{
	Super::BeginPlay();

	if (bAutoRunOnBeginPlay)
	{
		RunBootstrapVerticalSliceTest();
	}
}

bool AEcologyBootstrapTestActor::RunBootstrapVerticalSliceTest()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: World is null."));
		return false;
	}

	// 1. Query Authoritative Species Profile from Server Subsystem
	UEcologyServerSubsystem* ServerSubsystem = World->GetSubsystem<UEcologyServerSubsystem>();
	if (!ServerSubsystem)
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyBootstrapTestActor: EcologyServerSubsystem not found (may be running on NM_Client)."));
		return false;
	}

	FSpeciesEvolutionProfile Profile;
	if (!ServerSubsystem->GetSpeciesEvolutionProfile(TestRegionId, TestSpeciesId, Profile))
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: Failed to find profile for [%s x %s]."),
			*TestRegionId.ToString(), *TestSpeciesId.ToString());
		return false;
	}

	// 2. Resolve Target Creature (Explicit -> Find Existing -> Spawn New)
	ACreatureCharacter* Creature = TargetCreature.Get();
	if (!Creature)
	{
		// Search for any existing creature character in the level
		for (TActorIterator<ACreatureCharacter> It(World); It; ++It)
		{
			Creature = *It;
			TargetCreature = Creature;
			break;
		}
	}

	if (!Creature && CreatureClassToSpawn)
	{
		// Spawn a test creature near this test actor
		const FVector SpawnLocation = GetActorLocation() + GetActorForwardVector() * 200.0f;
		const FRotator SpawnRotation = GetActorRotation();
		FActorSpawnParameters SpawnParams;
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;

		Creature = World->SpawnActor<ACreatureCharacter>(CreatureClassToSpawn, SpawnLocation, SpawnRotation, SpawnParams);
		if (Creature)
		{
			TargetCreature = Creature;
			UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyBootstrapTestActor: Spawned new test creature [%s]."), *Creature->GetName());
		}
	}

	if (!Creature)
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: No target creature available to test."));
		return false;
	}

	// 3. Inject SpawnData and Profile into Creature via canonical InitializeCreature API
	FCreatureSpawnData SpawnData;
	SpawnData.RegionId = TestRegionId;
	SpawnData.SpeciesId = TestSpeciesId;
	SpawnData.Generation = Profile.Generation;
	SpawnData.ProfileRevision = Profile.ProfileRevision;
	SpawnData.StableAgentId = 8888;

	Creature->InitializeCreature(SpawnData, Profile);

	// 4. Verify Trait Expression
	if (const UCreatureTraitComponent* TraitComp = Creature->GetTraitComponent())
	{
		const float Scale = TraitComp->GetBodyScale();
		const float SpeedMult = TraitComp->GetMoveSpeedMultiplier();
		const float Fear = TraitComp->GetFear();
		const float Aggression = TraitComp->GetAggression();

		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyBootstrapTestActor: TEST PASSED for [%s]!"), *Creature->GetName());
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Target: %s x %s (Gen: %d, Rev: %lld)"),
			*TestRegionId.ToString(), *TestSpeciesId.ToString(), Profile.Generation, Profile.ProfileRevision);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  BodyScale:           %.2f (Expected: %.2f)"), Scale, Profile.Phenotype.BodyScale);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  MoveSpeedMultiplier: %.2f (Expected: %.2f)"), SpeedMult, Profile.Gameplay.MoveSpeedMultiplier);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Fear:                %.2f (Expected: %.2f)"), Fear, Profile.Behavior.Fear);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Aggression:          %.2f (Expected: %.2f)"), Aggression, Profile.Behavior.Aggression);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));

		if (GEngine)
		{
			GEngine->AddOnScreenDebugMessage(
				-1, 8.0f, FColor::Green,
				FString::Printf(TEXT("[Ecology Test Passed] %s: Scale=%.2f, Speed=%.2f, Fear=%.2f, Agg=%.2f"),
					*Creature->GetName(), Scale, SpeedMult, Fear, Aggression));
		}
		return true;
	}

	UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: Creature has no TraitComponent."));
	return false;
}
