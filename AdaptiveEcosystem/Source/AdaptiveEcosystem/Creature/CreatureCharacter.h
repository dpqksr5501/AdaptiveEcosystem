// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Core/EcoDataContracts.h"
#include "CreatureCharacter.generated.h"

class UCreatureTraitComponent;

/**
 * Base creature character representing active actor representation in the world.
 * Owned by Creature Runtime / Gameplay layer.
 * 
 * Rules:
 * - Does NOT directly depend on or query EcologyServerSubsystem or Evolution providers.
 * - Pure representation layer: initialized via InitializeCreature(...) by Server / Spawner / Test Harness.
 */
UCLASS(BlueprintType, Blueprintable)
class ADAPTIVEECOSYSTEM_API ACreatureCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ACreatureCharacter();

protected:
	virtual void BeginPlay() override;

public:
	/** Trait component responsible for physical and behavioral trait expressions */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Creature", meta = (AllowPrivateAccess = "true"))
	TObjectPtr<UCreatureTraitComponent> TraitComponent;

	/** Spawn data identifying this creature representation */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Creature")
	FCreatureSpawnData SpawnData;

	/**
	 * Canonical initialization API called by Server / Spawner / Representation Manager.
	 * Decouples Creature from how or where the profile was created.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Creature")
	void InitializeCreature(const FCreatureSpawnData& InSpawnData, const FSpeciesEvolutionProfile& InProfile);

	/** Applies a specific species evolution profile to this creature */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Creature")
	void ApplyProfile(const FSpeciesEvolutionProfile& InProfile);

	/** Getter for trait component */
	UFUNCTION(BlueprintPure, Category = "Ecology|Creature")
	UCreatureTraitComponent* GetTraitComponent() const { return TraitComponent; }
};
