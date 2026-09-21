// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Core/EcoIds.h"
#include "AI/Social/EcoSocialTypes.h"
#include "EcoHerdSubsystem.generated.h"

/**
 * Authoritative World-scoped subsystem managing persistent dynamic herds.
 * Owns central herd registry, dense runtime table, and aggregate state.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoHerdSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	UEcoHerdSubsystem();

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/**
	 * Allocates a new persistent herd for a given species.
	 * Reuses available empty slots or appends to ActiveHerds.
	 * @return Compact RuntimeIndex of the allocated herd.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Social|Herd")
	int32 AllocateHerd(int32 SpeciesRuntimeIndex, const FVector& InitialCenter);

	/**
	 * Releases an empty or dissolved herd slot.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Social|Herd")
	void ReleaseHerd(int32 RuntimeIndex);

	/** Checks if a herd runtime index is valid and actively populated */
	UFUNCTION(BlueprintPure, Category = "Ecology|Social|Herd")
	bool IsValidHerdIndex(int32 RuntimeIndex) const;

	/** Queries herd runtime snapshot by index */
	UFUNCTION(BlueprintPure, Category = "Ecology|Social|Herd")
	bool GetHerdData(int32 RuntimeIndex, FEcoHerdRuntimeData& OutData) const;

	/** Returns read-only reference to the active herd list for snapshot read patterns */
	const TArray<FEcoHerdRuntimeData>& GetActiveHerds() const { return ActiveHerds; }

	/** Retrieves the runtime species index associated with a given herd slot */
	int32 GetHerdSpeciesIndex(int32 RuntimeIndex) const;

	/**
	 * Updates the aggregate spatial and velocity state of a herd.
	 * Called during single-threaded reconciliation stage.
	 */
	void UpdateHerdAggregate(int32 RuntimeIndex, const FVector& Center, const FVector& AvgVelocity, int32 MemberCount, FMassEntityHandle Representative);

	/**
	 * Finds the closest valid herd of the matching species within search radius.
	 * @return Herd RuntimeIndex or INDEX_NONE_ECO if none within radius.
	 */
	int32 FindNearestHerd(int32 SpeciesRuntimeIndex, const FVector& Location, float MaxRadius) const;

private:
	/** Monotonically increasing unique ID for persistent herd tracking */
	int64 NextPersistentHerdId = 1;

	/** Dense array of active herd runtime records */
	UPROPERTY(Transient)
	TArray<FEcoHerdRuntimeData> ActiveHerds;

	/** Species index associated with each herd slot in ActiveHerds */
	UPROPERTY(Transient)
	TArray<int32> HerdSpeciesIndices;

	/** Free slot indices available for reuse */
	TArray<int32> FreeSlots;
};
