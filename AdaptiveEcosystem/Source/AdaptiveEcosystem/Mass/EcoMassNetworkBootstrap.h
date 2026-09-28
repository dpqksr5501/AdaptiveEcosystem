// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Core/EcoSpawnTypes.h"
#include "EcoMassNetworkBootstrap.generated.h"

class UMassEntityConfigAsset;
class AEcologyRegion;

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
	FName GetConfiguredRegionId() const;
	bool ValidateConfiguration(const AEcologyRegion& Region, FString& OutError) const;
	void PrepareRuntime(AEcologyRegion& Region, int32 RegionIndex, int32 SpeciesIndex);
	int32 ExecuteSpawnRequest(const FEcoSpawnRequest& Request, double ActualSpawnTime);

protected:
	virtual void PostInitializeComponents() override;
	virtual void BeginPlay() override;

public:

	/** Shared asset containing UEcoMassNetworkTrait; it must load on server and clients. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Mass")
	TObjectPtr<UMassEntityConfigAsset> EntityConfig;

	UPROPERTY(EditAnywhere, Category = "Ecology|Mass", meta = (ClampMin = "0"))
	int32 InitialAgentCount = 8;

	UPROPERTY(EditAnywhere, Category = "Ecology|Mass", meta = (ClampMin = "0.0"))
	float SpawnSpacing = 250.0f;

	UPROPERTY(EditAnywhere, Category = "Ecology|Mass")
	FName SpeciesId = TEXT("Species.Default");

	UPROPERTY(EditAnywhere, Category = "Ecology|Mass")
	FName RegionId = TEXT("Forest_A");

	/** Preferred binding. When set, this actor's RegionId is used instead of the fallback name above. */
	UPROPERTY(EditAnywhere, Category="Ecology|Mass")
	TObjectPtr<AEcologyRegion> RegionActor;
	UPROPERTY(EditAnywhere, Category="Ecology|Mass")
	FEcoSpawnScheduleSettings SpawnSchedule;

	/** Allows the actor to initialize itself without a GameMode callback. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Mass")
	bool bAutoInitialize = true;

private:
	bool RegisterTemplate() const;

	UPROPERTY(Transient)
	bool bInitialized = false;
	TWeakObjectPtr<AEcologyRegion> RuntimeRegion;
	int32 RuntimeRegionIndex = INDEX_NONE;
	int32 RuntimeSpeciesIndex = INDEX_NONE;
	int64 SpawnedSlotCount = 0;
	int64 LastExecutedRequestId = 0;
	FVector GetSpawnPosition(int64 Slot) const;
};
