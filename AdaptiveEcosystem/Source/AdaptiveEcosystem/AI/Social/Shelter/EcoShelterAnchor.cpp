// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Shelter/EcoShelterAnchor.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Components/ArrowComponent.h"
#include "Engine/World.h"

AEcoShelterAnchor::AEcoShelterAnchor()
{
	PrimaryActorTick.bCanEverTick = false;

#if WITH_EDITORONLY_DATA
	FacingArrow = CreateDefaultSubobject<UArrowComponent>(TEXT("FacingArrow"));
	if (FacingArrow)
	{
		FacingArrow->ArrowColor = FColor(0, 180, 255);
		FacingArrow->ArrowSize = 1.5f;
		FacingArrow->bTreatAsASprite = true;
		RootComponent = FacingArrow;
	}
#endif
}

void AEcoShelterAnchor::BeginPlay()
{
	Super::BeginPlay();

	if (UWorld* World = GetWorld())
	{
		if (UEcoShelterSubsystem* ShelterSubsystem = World->GetSubsystem<UEcoShelterSubsystem>())
		{
			ShelterRuntimeIndex = ShelterSubsystem->RegisterShelter(
				GetActorLocation(),
				GetActorForwardVector(),
				Quality,
				Capacity
			);
		}
	}
}

void AEcoShelterAnchor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (ShelterRuntimeIndex != -1)
	{
		if (UWorld* World = GetWorld())
		{
			if (UEcoShelterSubsystem* ShelterSubsystem = World->GetSubsystem<UEcoShelterSubsystem>())
			{
				ShelterSubsystem->UnregisterShelter(ShelterRuntimeIndex);
			}
		}
		ShelterRuntimeIndex = -1;
	}

	Super::EndPlay(EndPlayReason);
}
