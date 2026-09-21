// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Core/EcoIds.h"
#include "AI/Social/EcoSocialTypes.h"
#include "EcoShelterSubsystem.generated.h"

/**
 * Authoritative World-scoped subsystem managing physical shelter points and slot reservations.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoShelterSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	UEcoShelterSubsystem();

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/**
	 * Registers a newly spawned or placed shelter point in the world.
	 * Allocates discrete reservation slots according to Capacity distributed around Radius.
	 * @return Compact RuntimeIndex of the registered shelter.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Social|Shelter")
	int32 RegisterShelter(const FVector& Location, const FVector& Normal, float Quality, int32 Capacity, float Radius = 200.0f);

	/**
	 * Unregisters an existing shelter and vacates all its slots.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Social|Shelter")
	void UnregisterShelter(int32 ShelterIndex);

	/** Attempts to reserve a specific slot for a designated duration */
	bool ReserveSlot(int32 SlotIndex, int64 StableAgentId, double ExpireTime);

	/** Releases a reserved slot if held by the specified agent */
	void ReleaseSlot(int32 SlotIndex, int64 StableAgentId);

	/** Releases all slots currently reserved by an agent (e.g. on death) */
	void ReleaseAgentReservations(int64 StableAgentId);

	/**
	 * Checks physical world geometry line of sight between threat and target shelter location.
	 * @return True if raycast is blocked by geometry (defensively occluded/safe).
	 */
	bool CheckThreatOcclusion(const FVector& ThreatLocation, const FVector& TargetLocation) const;

	/**
	 * Queries the most suitable shelter and an unreserved slot based on distance, defensive occlusion, and quality.
	 * @param AgentLocation Current position of seeking agent.
	 * @param ThreatLocation Current position of active threat.
	 * @param SearchRadius Maximum query range.
	 * @param OutSlotIndex Index of available slot in ShelterSlots array (-1 if none).
	 * @param OutScore Computed safety/suitability score.
	 * @return Shelter RuntimeIndex or INDEX_NONE_ECO if none suitable.
	 */
	int32 FindBestAvailableShelter(const FVector& AgentLocation, const FVector& ThreatLocation, float SearchRadius, int32& OutSlotIndex, float& OutScore) const;

	/** Retrieves slot data by index */
	bool GetSlotData(int32 SlotIndex, FEcoShelterSlot& OutSlot) const;

	/** Checks and frees all slots whose reservation timestamp has lapsed */
	void CleanExpiredReservations(double CurrentTime);

	/** Resets all active reservations (debug / harness utility) */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Social|Shelter")
	void ResetAllReservations();

	/** Returns read-only reference to all registered shelter points */
	const TArray<FEcoShelterPoint>& GetShelters() const { return Shelters; }

	/** Returns read-only reference to all reservation slots */
	const TArray<FEcoShelterSlot>& GetShelterSlots() const { return ShelterSlots; }

	/** Checks if a shelter runtime index is currently valid and active */
	bool IsValidShelterIndex(int32 ShelterIndex) const;

private:
	/** Dense array of registered shelter points */
	UPROPERTY(Transient)
	TArray<FEcoShelterPoint> Shelters;

	/** Dense array of individual reservation slots mapped to shelters */
	UPROPERTY(Transient)
	TArray<FEcoShelterSlot> ShelterSlots;

	/** Available indices in Shelters array for slot recycling */
	TArray<int32> FreeShelterIndices;
};
