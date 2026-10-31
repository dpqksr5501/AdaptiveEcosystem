#pragma once
#include "CoreMinimal.h"
#include "MassEntityTypes.h"
#include "AI/Behavior/EcoSpeciesAIProfile.h"
#include "AI/Policy/EcoPolicyContracts.h"
#include "EcoSpeciesAIFragments.generated.h"

USTRUCT() struct FEcoStateTreeBehaviorTag : public FMassTag { GENERATED_BODY() };
USTRUCT() struct FEcoGroundedNavigationTag : public FMassTag { GENERATED_BODY() };
USTRUCT() struct FEcoSpeciesAISharedFragment : public FMassConstSharedFragment
{
    GENERATED_BODY()
    UPROPERTY() TObjectPtr<UEcoSpeciesAIProfile> Profile;
};

enum class EEcoAITargetDomain : uint8 { None, Entity, Fixture };
struct FEcoAITargetRef
{
    EEcoAITargetDomain Domain = EEcoAITargetDomain::None;
    int64 Id = 0;
    bool IsValid() const { return Domain != EEcoAITargetDomain::None && Id > 0; }
    bool operator==(const FEcoAITargetRef& Other) const { return Domain==Other.Domain && Id==Other.Id; }
};

/** Gathered values only. Sensor position may be remembered; never an omniscient target pose. */
USTRUCT() struct FEcoSpeciesAIInputFragment : public FMassFragment
{
    GENERATED_BODY()
    bool bValid = false, bPredator = false, bThreat = false, bFreshSight = false;
    bool bHungry = true, bFoodAvailable = false, bHasGroup = false;
    double Now = 0, CueTime = -100, NextDecision = 0, CalmSince = -1;
    float Energy = 1, FoodDensity = 0, Threat = 0, EvidenceConfidence = 0;
    float FixtureCueConfidence = 0;
    float WanderScore = 0, ForageScore = 0, RestScore = 0, FleeScore = 0, RegroupScore = 0;
    float HuntScore = 0, SearchScore = 0, EatScore = 0, HoldScore = 1;
    FVector Position = FVector::ZeroVector, Home = FVector::ZeroVector;
    FVector FoodPosition = FVector::ZeroVector, CuePosition = FVector::ZeroVector, GroupPosition = FVector::ZeroVector;
    FTransform RegionFrame = FTransform::Identity;
    FVector RegionExtent = FVector::ZeroVector;
    FEcoAITargetRef Target;
    uint64 Snapshot = 0;
    uint8 Tier = 0;
};

/** Behavior preference. PostSocial Activity is its sole execution consumer. */
USTRUCT() struct FEcoSpeciesAIDecisionFragment : public FMassFragment
{
    GENERATED_BODY()
    EEcoSpeciesActivity Activity = EEcoSpeciesActivity::Hold;
    double EnteredAt = 0;
    uint64 Sequence = 0;
};

enum class EEcoAINavigationStatus : uint8 { None, Pending, Following, Arrived, Blocked, Failed };
USTRUCT() struct FEcoSpeciesAIMoveFragment : public FMassFragment
{
    GENERATED_BODY()
    EEcoSpeciesActivity Activity = EEcoSpeciesActivity::Hold;
    FVector Target = FVector::ZeroVector, PlannedTarget = FVector::ZeroVector;
    float Speed = 0, Radius = 100;
    uint64 Revision = 0, PlannedRevision = 0;
    double RequestedAt = 0, RetryAfter = 0, Deadline = 0, LastProgress = 0;
    double ActualTime = 0, ClampedSeconds = 0;
    float BestDistance = MAX_flt;
    EEcoAINavigationStatus Status = EEcoAINavigationStatus::None;
    uint32 Failures = 0, BlockedFrames = 0;
    void SetTarget(const FVector& Position, float InSpeed, float InRadius, double Now, const UEcoSpeciesAIProfile& P);
    void Hold(double Now);
};

/** Execution history owned by Activity, not a mirror of StateTree instance memory. */
USTRUCT() struct FEcoSpeciesAIExecutionFragment : public FMassFragment
{
    GENERATED_BODY()
    EEcoSpeciesActivity Activity = EEcoSpeciesActivity::Hold;
    FVector RetainedGoal = FVector::ZeroVector;
    FEcoAITargetRef PursuitTarget;
    double GoalUntil = 0, PursuitStarted = -1, TargetCooldownUntil = 0;
    FEcoAITargetRef RejectedTarget;
    int64 SlotReservation = 0;
    EEcoActivitySlotKind SlotKind = EEcoActivitySlotKind::Graze;
    double NextSlotAttempt = 0;
    uint64 AppliedDecision = 0;
};

/** Actual grazing exposure, bounded segments consumed once by Ecology coordinator. */
struct FEcoAIFeedSegment { double Start = 0, End = 0; FName Region; };
USTRUCT() struct FEcoSpeciesAIFeedingFragment : public FMassFragment
{
    GENERATED_BODY()
    TArray<FEcoAIFeedSegment> Segments;
    double DroppedSeconds = 0;
    void Add(double Start, double End, FName Region);
    double ConsumeThrough(double Time, FName Region);
};
template<> struct TMassFragmentTraits<FEcoSpeciesAIFeedingFragment> final
{ enum { AuthorAcceptsItsNotTriviallyCopyable = true }; };

/** Request/receipt mailbox. GT resolver owns cooldown and applies each sequence once. */
USTRUCT() struct FEcoSpeciesAIAttackFragment : public FMassFragment
{
    GENERATED_BODY()
    FEcoAITargetRef Target;
    uint64 Requested = 0, Resolved = 0;
    double RequestedAt = 0, CooldownUntil = 0, RetryAfter = 0;
    uint64 Successes = 0, Rejections = 0;
};
