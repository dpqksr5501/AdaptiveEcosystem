// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoIds.h"
#include "Mass/EntityHandle.h"
#include "MassEntityTypes.h"
#include "EcoSocialTypes.generated.h"

/**
 * High-level social alert state of an agent.
 * Kept as an enum inside fragments to avoid frequent MassTag churn.
 */
UENUM(BlueprintType)
enum class EEcoSocialState : uint8
{
	Calm        UMETA(DisplayName = "Calm"),
	Alert       UMETA(DisplayName = "Alert"),
	Panic       UMETA(DisplayName = "Panic"),
	Recovering  UMETA(DisplayName = "Recovering"),
	Regrouping  UMETA(DisplayName = "Regrouping")
};

/**
 * Shelter interaction state machine stages.
 */
UENUM(BlueprintType)
enum class EEcoShelterIntentState : uint8
{
	None        UMETA(DisplayName = "None"),
	Searching   UMETA(DisplayName = "Searching"),
	Reserved    UMETA(DisplayName = "Reserved"),
	Moving      UMETA(DisplayName = "Moving"),
	Occupied    UMETA(DisplayName = "Occupied")
};

/**
 * Central runtime aggregate state for a persistent herd.
 * Managed dense array inside UEcoHerdSubsystem.
 */
USTRUCT(BlueprintType)
struct FEcoHerdRuntimeData
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Herd")
	int32 RuntimeIndex = INDEX_NONE_ECO;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Herd")
	int64 PersistentHerdId = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Herd")
	FVector Center = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Herd")
	FVector AverageVelocity = FVector::ZeroVector;

	/** Living representative entity used for group-level queries and debug display */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social|Herd")
	FMassEntityHandle Representative;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Herd")
	int32 MemberCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Herd")
	float AlarmStrength = 0.0f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Herd")
	FVector LastThreatPosition = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Herd")
	double LastAggregateTime = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Herd")
	double LastTopologyUpdateTime = 0.0;
};

/**
 * Transient alarm communication signal transmitted across agents.
 */
USTRUCT(BlueprintType)
struct FEcoAlarmSignal
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Alarm")
	int64 SignalId = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Alarm")
	int64 SourceAgentId = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Alarm")
	FVector ThreatPosition = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Alarm")
	float InitialStrength = 1.0f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Alarm")
	double CreatedTime = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Alarm")
	double ExpireTime = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Alarm")
	uint8 HopCount = 0;
};

/**
 * Authored or procedural shelter refuge point.
 */
USTRUCT(BlueprintType)
struct FEcoShelterPoint
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	int32 RuntimeIndex = INDEX_NONE_ECO;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	FVector Position = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	FVector SurfaceNormal = FVector::ForwardVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	float Quality = 1.0f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	int32 Capacity = 1;
};

/**
 * Individual reservation slot within a shelter.
 */
USTRUCT(BlueprintType)
struct FEcoShelterSlot
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	int32 ShelterRuntimeIndex = INDEX_NONE_ECO;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	int32 SlotIndex = INDEX_NONE_ECO;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	FVector Position = FVector::ZeroVector;

	/** StableAgentId of the agent currently reserving this slot (0 if unreserved) */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	int64 ReservedBy = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Social|Shelter")
	double ReservationExpireTime = 0.0;
};
