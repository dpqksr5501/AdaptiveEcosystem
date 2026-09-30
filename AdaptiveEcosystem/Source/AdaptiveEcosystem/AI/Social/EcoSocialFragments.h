// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"
#include "Core/EcoIds.h"
#include "AI/Policy/EcoPolicyContracts.h"
#include "AI/Social/EcoSocialTypes.h"
#include "AI/Social/EcoSocialMovementTypes.h"
#include "EcoSocialFragments.generated.h"

// -----------------------------------------------------------------------------
// Per-Agent Social Fragments (Mutable individual state)
// -----------------------------------------------------------------------------

/**
 * Tracks persistent herd membership and hysteresis dwell timing.
 */
USTRUCT()
struct FEcoHerdMemberFragment : public FMassFragment
{
	GENERATED_BODY()

	/** Compact runtime index of current herd in UEcoHerdSubsystem (-1 if unassigned) */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	int32 HerdRuntimeIndex = INDEX_NONE_ECO;

	/** Membership stability score (0.0 .. 1.0) */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	float MembershipConfidence = 0.0f;

	/** Accumulated time inside join boundary candidate */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	float JoinDwellTimer = 0.0f;

	/** Accumulated time outside leave boundary */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	float LeaveDwellTimer = 0.0f;
};

/**
 * Tracks current threat perception, alarm intensity, and social alert state.
 */
USTRUCT()
struct FEcoAlarmStateFragment : public FMassFragment
{
	GENERATED_BODY()

	/** Identifier of last processed alarm signal to prevent duplicated processing */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	int64 LastSignalId = 0;

	/** World position of most recent detected threat */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	FVector LastThreatPosition = FVector::ZeroVector;

	/** Current normalized alarm intensity (0.0 = calm, 1.0 = extreme panic) */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	float AlarmStrength = 0.0f;

	/** High-level social response state */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	EEcoSocialState State = EEcoSocialState::Calm;
};

/**
 * Tracks active shelter search, reservation, and navigation intent.
 */
USTRUCT()
struct FEcoShelterIntentFragment : public FMassFragment
{
	GENERATED_BODY()

	/** Target shelter point index in UEcoShelterSubsystem */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	int32 TargetShelterIndex = INDEX_NONE_ECO;

	/** Specific slot index within the shelter (-1 if unreserved) */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	int32 TargetSlotIndex = INDEX_NONE_ECO;

	/** Exact world coordinates of designated shelter slot for downstream movement/steering */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	FVector TargetPosition = FVector::ZeroVector;

	/** Evaluated safety / quality score of the target */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	float CurrentScore = 0.0f;

	/** Cooldown timestamp before next candidate query */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	double NextQueryTime = 0.0;

	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	int64 ReservationId = 0;

	// Social-owned timing/ack state. Movement writes only its feedback fragment.
	double ReservationGrantedTime = 0.0;
	double LastMovementFeedbackTime = 0.0;
	double LastProgressTime = 0.0;
	float BestTargetDistance = MAX_flt;
	int64 LastConsumedFeedbackSequence = 0;

	/** Current progress state towards shelter */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	EEcoShelterIntentState State = EEcoShelterIntentState::None;

	/** Resets intent state and targets back to default */
	void Reset()
	{
		TargetShelterIndex = INDEX_NONE_ECO;
		TargetSlotIndex = INDEX_NONE_ECO;
		TargetPosition = FVector::ZeroVector;
		CurrentScore = 0.0f;
		ReservationId = 0;
		ReservationGrantedTime = LastMovementFeedbackTime = LastProgressTime = 0.0;
		BestTargetDistance = MAX_flt;
		LastConsumedFeedbackSequence = 0;
		State = EEcoShelterIntentState::None;
	}
};

/** Social publishes a snapshot after reservation/lifecycle reconciliation. Movement reads it. */
USTRUCT()
struct FEcoSocialMovementRequestFragment : public FMassFragment
{
	GENERATED_BODY()
	bool bValid = false;
	FEcoPolicyActionV1 EffectiveAction;
	EEcoSocialMovementMode Mode = EEcoSocialMovementMode::None;
	int64 ReservationId = 0;
	int32 ShelterIndex = INDEX_NONE_ECO;
	int32 SlotIndex = INDEX_NONE_ECO;
	FVector TargetPosition = FVector::ZeroVector;
	float ArrivalRadius = 0.0f;
	double ValidUntilWorldTime = 0.0;
};

/** Movement publishes fresh sequence-numbered feedback; Social never writes this buffer. */
USTRUCT()
struct FEcoShelterMovementFeedbackFragment : public FMassFragment
{
	GENERATED_BODY()
	int64 ReservationId = 0;
	int64 Sequence = 0;
	EEcoShelterMovementStatus Status = EEcoShelterMovementStatus::None;

	void Report(int64 InReservationId, EEcoShelterMovementStatus InStatus)
	{
		check(Sequence < MAX_int64);
		ReservationId = InReservationId;
		Status = InStatus;
		++Sequence;
	}
};

/**
 * Holds modulated behavior actions and social steering multipliers.
 * Prevents compounding modification of raw PPO policy outputs.
 */
USTRUCT()
struct FEcoSocialBehaviorFragment : public FMassFragment
{
	GENERATED_BODY()

	/** Effective steering actions after social alarm and herd modulation */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	FEcoPolicyActionV1 ModulatedAction;

	/** Multiplier applied to flock cohesion (1.0 = normal, >1.0 = tight herd) */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	float SocialCohesionMultiplier = 1.0f;

	/** Flag set by membership processor when agent requires assignment or formation of a new herd */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	bool bWantsNewHerd = false;
};

// -----------------------------------------------------------------------------
// Species Shared Fragment (Immutable/slow-changing social configuration)
// -----------------------------------------------------------------------------

/**
 * Species-wide tuning parameters for social dynamics.
 * Kept separate from FEcoSpeciesSharedFragment to maintain modularity.
 */
USTRUCT()
struct FEcoSocialSpeciesSharedFragment : public FMassSharedFragment
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Shelter")
	FEcoShelterLifecycleSettings Shelter;

	/** Enable real threat sensing; manual alarm injection remains available independently. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Threat")
	bool bDetectThreats = true;

	/** Walls must block Visibility query collision. Both simple and complex lines are checked. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Threat")
	bool bThreatRequiresLineOfSight = true;

	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Threat", meta = (ClampMin = "0", ClampMax = "500"))
	float ThreatEyeHeight = 60.0f;

	/** Distance within which an unassigned agent initiates join evaluation */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Herd")
	float HerdJoinRadius = 800.0f;

	/** Distance beyond which an existing member initiates leave evaluation (Join < Leave for hysteresis) */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Herd")
	float HerdLeaveRadius = 1400.0f;

	/** Proximity threshold for merging two distinct herds of the same species */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Herd")
	float HerdMergeRadius = 1000.0f;

	/** Required continuous seconds inside join radius before membership commit */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Herd")
	float JoinDwellTime = 1.0f;

	/** Required continuous seconds outside leave radius before detachment */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Herd")
	float LeaveDwellTime = 2.0f;

	/** Maximum broadcast radius for alarm signals */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Alarm")
	float AlarmRadius = 2000.0f;

	/** Distance attenuation factor (alpha) in exponential decay */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Alarm")
	float AlarmDistanceDecay = 0.001f;

	/** Time attenuation factor (beta) per second */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Alarm")
	float AlarmTimeDecay = 0.2f;

	/** Maximum hop count for multi-agent gossip relay */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Alarm")
	uint8 MaxAlarmHop = 2;

	/** Alarm strength threshold triggering Panic state transition */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Alarm")
	float PanicThreshold = 0.6f;

	/** Alarm strength threshold triggering Alert state transition */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Alarm")
	float AlertThreshold = 0.2f;

	/** Maximum neighbor count considered during herd clustering */
	UPROPERTY(EditAnywhere, Category = "Ecology|Social|Herd")
	int32 MaxHerdNeighborCandidates = 16;
};
