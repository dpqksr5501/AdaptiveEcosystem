// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "EcoMassNetworkBootstrap.generated.h"

class UMassEntityConfigAsset;

/**
 * Registers a deterministic Mass template in every world and spawns the
 * authoritative logical population only on server/standalone worlds.
 */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoMassNetworkBootstrap : public AActor
{
	GENERATED_BODY()

public:
	AEcoMassNetworkBootstrap();

	/** Idempotently registers the template and creates the initial authority population. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Mass")
	bool InitializeMassNetwork();

	UFUNCTION(BlueprintPure, Category = "Ecology|Mass")
	bool IsMassNetworkInitialized() const { return bInitialized; }

protected:
	virtual void PostInitializeComponents() override;
	virtual void BeginPlay() override;

	/** Shared asset containing UEcoMassNetworkTrait; it must load on server and clients. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Mass")
	TObjectPtr<UMassEntityConfigAsset> EntityConfig;

	UPROPERTY(EditAnywhere, Category = "Ecology|Mass", meta = (ClampMin = "0"))
	int32 InitialAgentCount = 64;

	UPROPERTY(EditAnywhere, Category = "Ecology|Mass", meta = (ClampMin = "0.0"))
	float SpawnSpacing = 250.0f;

	UPROPERTY(EditAnywhere, Category = "Ecology|Mass")
	FName SpeciesId = TEXT("Species.Default");

	UPROPERTY(EditAnywhere, Category = "Ecology|Mass")
	FName RegionId = TEXT("Region.Default");

	/** Allows the actor to initialize itself without a GameMode callback. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Mass")
	bool bAutoInitialize = true;

private:
	bool RegisterTemplate() const;

	UPROPERTY(Transient)
	bool bInitialized = false;
};
