// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Core/EcoDataContracts.h"
#include "EcologyRegion.generated.h"

class UBoxComponent;

/**
 * Defines a geographical region in the world with distinct environmental properties.
 * Owned by World / Level layer.
 */
UCLASS(BlueprintType, Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcologyRegion : public AActor
{
	GENERATED_BODY()

public:
	AEcologyRegion();

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

public:
	/** Unique identifier of the region (e.g. "Forest_A") */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Region")
	FName RegionId;

	/** Current environmental parameters within this region */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Region")
	FRegionEnvironmentState EnvironmentState;

	/** Box component representing the bounding volume of this region */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Region")
	TObjectPtr<UBoxComponent> RegionBounds;

	/** Queries current environment state */
	UFUNCTION(BlueprintPure, Category = "Ecology|Region")
	const FRegionEnvironmentState& GetEnvironmentState() const { return EnvironmentState; }

	/** Updates current environment state */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Region")
	void SetEnvironmentState(const FRegionEnvironmentState& InState) { EnvironmentState = InState; }

	/**
	 * Consumes vegetation in this region due to grazing or harvesting.
	 * Effective vegetation density loss is mitigated by GrazingResistance.
	 * Food availability is reduced by ConsumedAmount.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Region")
	void ApplyVegetationConsumption(float ConsumedAmount, float GrazingResistance);

	/**
	 * Regrows vegetation and recovers food availability based on species traits.
	 * FoodAvailability is capped by current VegetationDensity.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Region")
	void ApplyVegetationRegrowth(float DeltaTime, float GrowthRate, float RegenerationRate);

};
