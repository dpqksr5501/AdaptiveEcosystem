// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"
#include "Core/EcoIds.h"
#include "AI/Policy/EcoPolicyContracts.h"
#include "AI/Social/EcoSocialTypes.h"
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

	/** Evaluated safety / quality score of the target */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	float CurrentScore = 0.0f;

	/** Cooldown timestamp before next candidate query */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	float NextQueryTime = 0.0f;

	/** Current progress state towards shelter */
	UPROPERTY(VisibleAnywhere, Transient, Category = "Ecology|Social")
	EEcoShelterIntentState State = EEcoShelterIntentState::None;
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
