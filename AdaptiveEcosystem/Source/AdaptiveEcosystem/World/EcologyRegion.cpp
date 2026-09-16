// Copyright Epic Games, Inc. All Rights Reserved.

#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "Components/BoxComponent.h"
#include "Engine/World.h"

AEcologyRegion::AEcologyRegion()
{
	PrimaryActorTick.bCanEverTick = false;

	RegionId = FName(TEXT("Forest_A"));

	RegionBounds = CreateDefaultSubobject<UBoxComponent>(TEXT("RegionBounds"));
	RootComponent = RegionBounds;
	RegionBounds->SetBoxExtent(FVector(5000.0f, 5000.0f, 1000.0f));
	RegionBounds->SetCollisionProfileName(TEXT("NoCollision"));
	RegionBounds->SetGenerateOverlapEvents(false);
}

void AEcologyRegion::BeginPlay()
{
	Super::BeginPlay();

	if (UWorld* World = GetWorld())
	{
		if (UEcologyWorldSubsystem* WorldSubsystem = World->GetSubsystem<UEcologyWorldSubsystem>())
		{
			WorldSubsystem->RegisterRegion(this);
		}
	}
}

void AEcologyRegion::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UWorld* World = GetWorld())
	{
		if (UEcologyWorldSubsystem* WorldSubsystem = World->GetSubsystem<UEcologyWorldSubsystem>())
		{
			WorldSubsystem->UnregisterRegion(this);
		}
	}

	Super::EndPlay(EndPlayReason);
}
