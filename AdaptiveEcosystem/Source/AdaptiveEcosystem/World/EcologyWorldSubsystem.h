// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Core/EcoDataContracts.h"
#include "EcologyWorldSubsystem.generated.h"

class AEcologyRegion;

/**
 * World subsystem that tracks and provides queries for ecology regions and environment state.
 * Owned by World / Level layer.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcologyWorldSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/** Registers an active ecology region in the world */
	UFUNCTION(BlueprintCallable, Category = "Ecology|World")
	void RegisterRegion(AEcologyRegion* InRegion);

	/** Unregisters an ecology region */
	UFUNCTION(BlueprintCallable, Category = "Ecology|World")
	void UnregisterRegion(AEcologyRegion* InRegion);

	/** Finds an ecology region actor by RegionId */
	UFUNCTION(BlueprintPure, Category = "Ecology|World")
	AEcologyRegion* GetRegion(FName InRegionId) const;

	/** Queries environment state by RegionId. Returns true if region was found. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|World")
	bool GetEnvironmentState(FName InRegionId, FRegionEnvironmentState& OutState) const;

private:
	/** Map of registered regions keyed by RegionId */
	UPROPERTY(Transient)
	TMap<FName, TWeakObjectPtr<AEcologyRegion>> RegisteredRegions;
};
