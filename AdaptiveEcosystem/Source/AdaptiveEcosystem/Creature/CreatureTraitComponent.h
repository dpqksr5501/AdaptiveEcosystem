// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Core/EcoDataContracts.h"
#include "CreatureTraitComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnSpeciesProfileApplied, const FSpeciesEvolutionProfile&, NewProfile);

/**
 * Manages runtime expression of species traits on a creature actor.
 * Responsible for applying BodyScale, MoveSpeedMultiplier, and providing Fear/Aggression queries.
 * Owned by Creature Runtime / Gameplay layer.
 */
UCLASS(ClassGroup=(Ecology), meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UCreatureTraitComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UCreatureTraitComponent();

protected:
	virtual void BeginPlay() override;

public:
	/** Applies a committed species evolution profile to the owning creature */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Traits")
	void ApplySpeciesProfile(const FSpeciesEvolutionProfile& InProfile);

	/** Event broadcast when a new profile is applied */
	UPROPERTY(BlueprintAssignable, Category = "Ecology|Traits")
	FOnSpeciesProfileApplied OnSpeciesProfileApplied;

	// -------------------------------------------------------------------------
	// Trait Query APIs
	// -------------------------------------------------------------------------

	UFUNCTION(BlueprintPure, Category = "Ecology|Traits")
	const FSpeciesEvolutionProfile& GetCurrentProfile() const { return CurrentProfile; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Traits")
	float GetBodyScale() const { return CurrentProfile.Phenotype.BodyScale; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Traits")
	float GetMoveSpeedMultiplier() const { return CurrentProfile.Gameplay.MoveSpeedMultiplier; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Traits")
	float GetFear() const { return CurrentProfile.Behavior.Fear; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Traits")
	float GetAggression() const { return CurrentProfile.Behavior.Aggression; }

	/** Formats current trait state as a human-readable string for debugging */
	UFUNCTION(BlueprintPure, Category = "Ecology|Traits")
	FString GetDebugDescription() const;

private:
	/** Currently applied species profile */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Traits", meta = (AllowPrivateAccess = "true"))
	FSpeciesEvolutionProfile CurrentProfile;

	/** Cached baseline walk speed from CharacterMovementComponent */
	UPROPERTY(VisibleAnywhere, Category = "Ecology|Traits", meta = (AllowPrivateAccess = "true"))
	float BaselineMaxWalkSpeed;

	/** Flag indicating whether baseline walk speed was recorded */
	bool bBaselineSpeedCached;
};
