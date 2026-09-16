// Copyright Epic Games, Inc. All Rights Reserved.

#include "Creature/CreatureTraitComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "AdaptiveEcosystem.h"

UCreatureTraitComponent::UCreatureTraitComponent()
{
	PrimaryComponentTick.bCanEverTick = false;

	BaselineMaxWalkSpeed = 600.0f;
	bBaselineSpeedCached = false;
}

void UCreatureTraitComponent::BeginPlay()
{
	Super::BeginPlay();

	if (const ACharacter* CharacterOwner = Cast<ACharacter>(GetOwner()))
	{
		if (const UCharacterMovementComponent* MovementComp = CharacterOwner->GetCharacterMovement())
		{
			BaselineMaxWalkSpeed = MovementComp->MaxWalkSpeed;
			bBaselineSpeedCached = true;
		}
	}
}

void UCreatureTraitComponent::ApplySpeciesProfile(const FSpeciesEvolutionProfile& InProfile)
{
	CurrentProfile = InProfile;

	AActor* OwnerActor = GetOwner();
	if (!OwnerActor)
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("CreatureTraitComponent: No owner actor found."));
		return;
	}

	// 1. Apply BodyScale
	const float BodyScale = FMath::Clamp(InProfile.Phenotype.BodyScale, 0.5f, 2.0f);
	OwnerActor->SetActorScale3D(FVector(BodyScale, BodyScale, BodyScale));

	// 2. Apply MoveSpeedMultiplier
	if (ACharacter* CharacterOwner = Cast<ACharacter>(OwnerActor))
	{
		if (UCharacterMovementComponent* MovementComp = CharacterOwner->GetCharacterMovement())
		{
			if (!bBaselineSpeedCached)
			{
				BaselineMaxWalkSpeed = MovementComp->MaxWalkSpeed;
				bBaselineSpeedCached = true;
			}

			const float SpeedMultiplier = FMath::Clamp(InProfile.Gameplay.MoveSpeedMultiplier, 0.5f, 2.0f);
			MovementComp->MaxWalkSpeed = BaselineMaxWalkSpeed * SpeedMultiplier;
		}
	}

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("CreatureTraitComponent on [%s] applied profile [%s x %s]: BodyScale=%.2f, MoveSpeedMult=%.2f, Fear=%.2f, Aggression=%.2f"),
		*OwnerActor->GetName(),
		*InProfile.RegionId.ToString(),
		*InProfile.SpeciesId.ToString(),
		InProfile.Phenotype.BodyScale,
		InProfile.Gameplay.MoveSpeedMultiplier,
		InProfile.Behavior.Fear,
		InProfile.Behavior.Aggression);

	OnSpeciesProfileApplied.Broadcast(CurrentProfile);
}

FString UCreatureTraitComponent::GetDebugDescription() const
{
	return FString::Printf(TEXT("Species: %s | Region: %s | Gen: %d | Scale: %.2f | SpeedMult: %.2f | Fear: %.2f | Aggression: %.2f"),
		*CurrentProfile.SpeciesId.ToString(),
		*CurrentProfile.RegionId.ToString(),
		CurrentProfile.Generation,
		CurrentProfile.Phenotype.BodyScale,
		CurrentProfile.Gameplay.MoveSpeedMultiplier,
		CurrentProfile.Behavior.Fear,
		CurrentProfile.Behavior.Aggression);
}
