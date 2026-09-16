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

	/** Spawn data that identifies this creature representation */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Creature")
	FCreatureSpawnData SpawnData;

	/** Manually requests and applies the dummy vertical slice (Forest_A x Wolf) profile */
	UFUNCTION(BlueprintCallable, Exec, Category = "Ecology|Creature|Debug")
	void ApplyDummyVerticalSlice();

	/** Applies a specific species evolution profile */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Creature")
	void ApplyProfile(const FSpeciesEvolutionProfile& InProfile);

	/** Getter for trait component */
	UFUNCTION(BlueprintPure, Category = "Ecology|Creature")
	UCreatureTraitComponent* GetTraitComponent() const { return TraitComponent; }
};
