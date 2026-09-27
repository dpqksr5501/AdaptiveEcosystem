// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MassEntityQuery.h"
#include "EcoShelterTestHarnessActor.generated.h"

struct FMassEntityManager;

/**
 * Debug/Test harness actor for verifying the Shelter / Cover Runtime MVP.
 * Visualizes registered shelter points, individual reservation slots, threat-relative occlusion lines,
 * and agent shelter reservation targets.
 */
UCLASS(BlueprintType, Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoShelterTestHarnessActor : public AActor
{
	GENERATED_BODY()

public:
	AEcoShelterTestHarnessActor();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	/** High-performance 2D Canvas HUD projection callback called during viewport render */
	void DrawEntityHUD(class UCanvas* Canvas, class APlayerController* PC);

	// -------------------------------------------------------------------------
	// Configuration
	// -------------------------------------------------------------------------

	/** If true, visualizes registered shelter locations, bounding radius, and capacity HUD */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|ShelterDebug")
	bool bDrawShelters = true;

	/** If true, visualizes individual shelter slots (Green = open, Orange = reserved) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|ShelterDebug")
	bool bDrawSlots = true;

	/** If true, traces LOS from active threat to shelters (Green = occluded/defensible, Red = exposed) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|ShelterDebug")
	bool bDrawOcclusionRaycasts = true;

	/** If true, draws connection lines from agents to their reserved shelter slots */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|ShelterDebug")
	bool bDrawAgentIntentLines = true;

	/** Target Herd runtime index used to look up active threat position for occlusion testing */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|ShelterDebug", meta = (ClampMin = "0"))
	int32 ThreatHerdIndex = 0;

	/** Optional threat location override; enable the flag to use world origin explicitly. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|ShelterDebug")
	FVector ThreatLocationOverride = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|ShelterDebug")
	bool bUseThreatLocationOverride = false;

	/** Optional wall to inspect when running DiagnoseThreatOcclusion. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|ShelterDebug")
	TObjectPtr<AActor> OcclusionProbeWall = nullptr;

	/** Maximum number of agent HUD text labels to render concurrently */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|ShelterDebug", meta = (ClampMin = "1", ClampMax = "100"))
	int32 MaxAgentHudCount = 20;

	// -------------------------------------------------------------------------
	// CallInEditor Actions
	// -------------------------------------------------------------------------

	/**
	 * Resets all shelter slot reservations and clears agent shelter intent fragments.
	 */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Ecology|ShelterDebug")
	void ResetAllReservations();

	/**
	 * Prints detailed status of all registered shelters, slot allocations, and reserving agents to Log.
	 */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Ecology|ShelterDebug")
	void PrintShelterOccupancyStatus();

	/** Logs trace coordinates/results and the selected wall's runtime collision settings. */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Ecology|ShelterDebug")
	void DiagnoseThreatOcclusion();

private:
	void EnsureQueriesInitialized(FMassEntityManager& EntityManager);
	bool ResolveActiveThreatLocation(FVector& OutThreatLocation) const;

	/** Cached Mass queries */
	FMassEntityQuery DebugQuery;
	FMassEntityQuery ResetQuery;
	bool bQueriesInitialized = false;

	/** Delegate handle for UDebugDrawService Canvas drawing */
	FDelegateHandle DebugDrawDelegateHandle;
};
