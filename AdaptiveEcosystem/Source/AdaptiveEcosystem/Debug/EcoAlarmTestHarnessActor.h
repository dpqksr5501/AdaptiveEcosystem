// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "EcoAlarmTestHarnessActor.generated.h"

/**
 * Debug/Test harness actor for injecting threat alarms and verifying the Alarm Communication MVP.
 * Provides CallInEditor injection triggers, spatial wave visualization, and per-entity state HUD.
 */
UCLASS(BlueprintType, Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoAlarmTestHarnessActor : public AActor
{
	GENERATED_BODY()

public:
	AEcoAlarmTestHarnessActor();

	virtual void Tick(float DeltaSeconds) override;

	// -------------------------------------------------------------------------
	// Configuration
	// -------------------------------------------------------------------------

	/** Target herd runtime index for directed threat injection */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|AlarmDebug", meta = (ClampMin = "0"))
	int32 TargetHerdIndex = 0;

	/** Intensity of injected threat (0.0 to 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|AlarmDebug", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float ThreatStrength = 1.0f;

	/** Spatial radius within which herds will receive threat when injecting at actor location */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|AlarmDebug", meta = (ClampMin = "100.0"))
	float SpatialThreatRadius = 2500.0f;

	/** If true, continuously emits threat each tick (simulates standing predator/danger zone) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|AlarmDebug")
	bool bContinuousThreat = false;

	/** If true, draws 3D threat location and broadcast radius */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|AlarmDebug")
	bool bDrawThreatArea = true;

	/** If true, draws colored spheres and HUD text above entities showing AlarmState, Strength, and Modulated FleeDist */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|AlarmDebug")
	bool bDrawEntityAlarmStates = true;

	// -------------------------------------------------------------------------
	// CallInEditor Injection Actions
	// -------------------------------------------------------------------------

	/** Injects threat into TargetHerdIndex at this actor's location */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Ecology|AlarmDebug")
	void TriggerThreatAtTargetHerd();

	/** Injects spatial threat to all herds within SpatialThreatRadius around this actor */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Ecology|AlarmDebug")
	void TriggerThreatAtActorLocation();

	/**
	 * Stops threat emission by clearing Herd-level threat states.
	 * Agents will naturally decay over time: Panic -> Alert -> Recovering -> Calm.
	 */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Ecology|AlarmDebug")
	void ClearAllAlarms();

	/**
	 * Hard reset for emergency test reset: forces all herds and member agents to 0 strength and Calm.
	 */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Ecology|AlarmDebug")
	void HardResetAllAlarms();

private:
	/** Timestamp of last triggered threat for visual pulsation */
	double LastThreatTriggerTime = 0.0;
};
