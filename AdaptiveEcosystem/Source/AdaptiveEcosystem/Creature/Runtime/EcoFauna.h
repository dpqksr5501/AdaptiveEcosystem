#pragma once

#include "CoreMinimal.h"
#include "AI/Policy/EcoLifeHistoryV3.h"
#include "Mass/EcoMassNetworkTrait.h"
#include "MassEntityTypes.h"
#include "EcoFauna.generated.h"

class AEcoCreatureRepresentationActor;

namespace EcoFaunaNutrition
{
    constexpr float MaintenancePerSecond = .35f;
    // Native v3 zeros the legacy coordinator's EnergyPerFood setting.
    constexpr float PlantEnergyPerUnit = 5.f;
    constexpr float MinimumMeal = MaintenancePerSecond / PlantEnergyPerUnit;
}

UENUM(BlueprintType)
enum class EEcoFaunaDiet : uint8 { Herbivore, Omnivore, Carnivore };

UENUM(BlueprintType)
enum class EEcoFaunaLocomotion : uint8 { Ground, Flight };

enum class EEcoFaunaFlightPhase : uint8 { Grounded, Takeoff, Cruise, Landing };

USTRUCT(BlueprintType)
struct FEcoFaunaPersistenceSettings
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere) bool bEnabled = false;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="s")) float ActivityMemorySeconds = 4.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="s")) float ForageMemorySeconds = 90.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", ClampMax="1")) float ScarcePreyValue = .35f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1")) float PreyHalfSaturation = 3.f;

    bool IsValid() const
    {
        return FMath::IsFinite(ActivityMemorySeconds) && ActivityMemorySeconds >= 1.f
            && FMath::IsFinite(ForageMemorySeconds) && ForageMemorySeconds >= 1.f
            && FMath::IsFinite(ScarcePreyValue) && ScarcePreyValue >= 0.f && ScarcePreyValue <= 1.f
            && FMath::IsFinite(PreyHalfSaturation) && PreyHalfSaturation >= 1.f;
    }
};

USTRUCT(BlueprintType)
struct FEcoFaunaPreyRule
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere) FName SpeciesId;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.01")) float Preference = 1.f;
    /** Zero uses the hunter's ordinary sight range. */
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="cm")) float MaxPursuitStart = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.01")) float MaxPreyMassRatio = 1.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", ClampMax="1")) float MaxHealthyMaturity = 1.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", ClampMax="1")) float MaxInjuredMaturity = 1.f;
    /** A healthy mature conspecific this close protects an immature target. Zero disables the check. */
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="cm")) float GuardRadius = 0.f;
};

USTRUCT(BlueprintType)
struct FEcoFaunaSpecies
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere) FName SpeciesId;
    UPROPERTY(EditAnywhere) TSubclassOf<AEcoCreatureRepresentationActor> VisualClass;
    UPROPERTY(EditAnywhere) EEcoFaunaDiet Diet = EEcoFaunaDiet::Herbivore;
    UPROPERTY(EditAnywhere) EEcoFaunaLocomotion Locomotion = EEcoFaunaLocomotion::Ground;
    /** Explicit relation. Only fauna residents can be selected by this backend. */
    UPROPERTY(EditAnywhere) TArray<FEcoFaunaPreyRule> PreyRules;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.01", Units="kg")) float AdultMass = 40.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm")) float AttackReach = 100.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm")) float SightRange = 1500.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", ClampMax="180", Units="deg")) float SightHalfAngle = 99.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1")) float WalkSpeed = 150.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1")) float RunSpeed = 330.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm/s^2")) float GroundAcceleration = 750.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="cm")) float StalkRange = 0.f;
    UPROPERTY(EditAnywhere) bool bFlankDefendedPrey = false;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="cm")) float HabitatCarrionRange = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="cm")) float CaregiverFollowRange = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="s")) float RootingSeconds = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1")) float BodyRadius = 25.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm")) float EyeHeight = 35.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm")) float SweepHeight = 65.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="cm")) float WadeDepth = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="cm")) float StepHeight = 20.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0")) float SprintDrain = .10f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0")) float FatigueRecovery = .13f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0")) float Maintenance = EcoFaunaNutrition::MaintenancePerSecond;
    /** Fraction of full-activity maintenance while resting. Only used by adaptive persistence. */
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.1", ClampMax="1")) float RestingMaintenanceFraction = .35f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", ClampMax="1200")) float ScentRange = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", ClampMax="100")) float DefenseDamage = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="cm")) float OffspringGuardRange = 0.f;
    UPROPERTY(EditAnywhere) bool bAllowSecondParentGuard = false;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", ClampMax="1")) float DayActivity = 1.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", ClampMax="1")) float NightActivity = 1.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.1", ClampMax="1")) float NightVision = 1.f;
    float RoutineActivity(float Darkness) const { return FMath::Lerp(DayActivity, NightActivity, FMath::Clamp(Darkness, 0.f, 1.f)); }
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.05", Units="s")) float AttackWindup = .35f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="s")) float AttackRecovery = 6.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1")) float MaturitySeconds = 180.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="s")) float Gestation = 30.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="s")) float BirthRecovery = 300.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.01")) float FoodPerMeal = .2f;
    /** Zero disables use of shared carrion. */
    UPROPERTY(EditAnywhere, meta=(ClampMin="0")) float CarrionEnergyPerMeal = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", ClampMax="0.9")) float CarrionHungerFraction = .82f;
    /** Zero uses the diet's default meal start. */
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", ClampMax="0.95")) float MealStartFraction = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.3", ClampMax="1")) float MealStopFraction = .9f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="s")) float PostMealRestSeconds = 4.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.1", Units="s")) float PursuitLimitSeconds = 12.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm")) float ThreatSenseRange = 650.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", ClampMax="180", Units="deg")) float ThreatSightHalfAngle = 90.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0", Units="cm")) float ThreatNearAwarenessRange = 280.f;
    /** Soft radius for routine wandering. Threats, family and resources can lead beyond it. */
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm")) float RoutineHomeRadius = 520.f;
    float MealStart() const
    { return MealStartFraction > 0.f ? MealStartFraction : UsesPlantFood() ? .72f : FMath::Max(.8f, CarrionHungerFraction); }
    UPROPERTY(EditAnywhere) bool bAllowConspecificCarrion = false;
    /** Zero estimates edible energy from body mass. */
    UPROPERTY(EditAnywhere, meta=(ClampMin="0")) float AdultCarrionEnergy = 0.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="0.05", Units="s")) float DeathSettleSeconds = .9f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="s")) float CarrionLifetime = 20.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", ClampMax="8")) int32 FeedingPlaces = 2;
    UPROPERTY(EditAnywhere, meta=(ClampMin="2")) int32 RegionalLimit = 12;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm")) float FlightCruiseHeight = 1200.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm")) float FlightCeiling = 3000.f;
    UPROPERTY(EditAnywhere, meta=(ClampMin="1", Units="cm/s")) float FlightSpeed = 650.f;

    bool UsesPlantFood() const { return Diet != EEcoFaunaDiet::Carnivore; }
    float CarrionReach() const { return FMath::Clamp(AttackReach, 24.f, 100.f); }
};

USTRUCT(BlueprintType)
struct FEcoFaunaPlacement
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere) FName SpeciesId;
    UPROPERTY(EditAnywhere) TArray<FVector> SpawnPoints;
    UPROPERTY(EditAnywhere) TArray<FVector> HabitatSpawnPoints;
    UPROPERTY(EditAnywhere) int32 HabitatSpawnStage = 1;
};

/** Finite, spatial food reserve with optional body-size shelter at its center. */
USTRUCT(BlueprintType)
struct FEcoFaunaHabitatPatch
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere) FName Id;
    UPROPERTY(EditAnywhere) FName RegionId;
    UPROPERTY(EditAnywhere) FVector Center = FVector::ZeroVector;
    UPROPERTY(EditAnywhere) int32 Stage = 1;
    UPROPERTY(EditAnywhere) FName ShelteredSpecies;
    UPROPERTY(EditAnywhere) float ShelterRadius = 0.f;
    UPROPERTY(EditAnywhere) float EntranceRadius = 0.f;
    UPROPERTY(EditAnywhere) TArray<FName> Consumers;
    UPROPERTY(EditAnywhere) float Capacity = 0.f;
    UPROPERTY(EditAnywhere) float RegrowthPerSecond = 0.f;
    UPROPERTY(EditAnywhere) float EnergyPerMeal = 3.f;

    bool Shelters(FName Species, const FVector& Position) const
    {
        return ShelterRadius > 0.f && Species == ShelteredSpecies
            && FVector::DistSquared(Position, Center) <= FMath::Square(ShelterRadius);
    }

    float TakeMeal(float& Stock, float EnergyDeficit) const
    {
        const float Meal = FMath::Min3(Stock, EnergyPerMeal, EnergyDeficit);
        if (Meal < .2f) return 0.f;
        Stock -= Meal;
        return Meal;
    }
};

/** Authority-only life and movement state for the opt-in rule backend. */
USTRUCT()
struct FEcoFaunaFragment : public FMassFragment
{
    GENERATED_BODY()

    EcoLifeV3::FIndividual Life;
    FVector Home = FVector::ZeroVector;
    FVector Goal = FVector::ZeroVector;
    FVector LandingPoint = FVector::ZeroVector;
    FVector LastPreyPosition = FVector::ZeroVector;
    FVector LastThreatPosition = FVector::ZeroVector;
    FVector ForageMemoryPosition = FVector::ZeroVector;
    FVector HeardPreyPosition = FVector::ZeroVector;
    double NextDecision = 0.;
    double NextSense = 0.;
    double NextFoodSense = 0.;
    double NextThreatSense = 0.;
    double BlockedCarrionUntil = 0.;
    double LastMeal = -1.;
    double LastCarrionMeal = -1.;
    double LastForageIntakeAt = -1.;
    float ForageIntake = 0.f;
    float MaintenanceScale = 1.f;
    double PatchBlockedUntil = 0.;
    int32 PatchTarget = INDEX_NONE;
    int32 BlockedPatch = INDEX_NONE;
    double AttackContact = -1.;
    double AttackReady = 0.;
    double ChaseBegan = -1.;
    double LastPreySeenUntil = -1.;
    double NextScentDeposit = 0.;
    double ScentUntil = -1.;
    uint64 LastScentId = 0;
    FVector ScentPosition = FVector::ZeroVector;
    double RoutineRestUntil = -1.;
    float Stamina = 1.f;
    bool bRecovering = false;
    bool bInvestigatingNoise = false;
    int64 TargetId = 0;
    int64 GuardThreatId = 0;
    int64 CarrionTargetId = 0;
    int64 BlockedCarrionId = 0;
    double ThreatUntil = -1.;
    double HeardPreyUntil = -1.;
    int64 LastHeardFootstep = 0;
    double PhaseUntil = 0.;
    double RootingUntil = -1.;
    uint32 DecisionCount = 0;
    bool bStalking = false;
    bool bFollowingCaregiver = false;
    EEcoFaunaFlightPhase Flight = EEcoFaunaFlightPhase::Grounded;

    float RecentForageIntake(double Now, float MemorySeconds) const
    {
        return LastForageIntakeAt >= 0.
            ? ForageIntake * float(FMath::Exp(-FMath::Max(0., Now - LastForageIntakeAt) / MemorySeconds)) : 0.f;
    }

    void RecordForageIntake(const FVector& Site, double Now, float Energy, float MemorySeconds)
    {
        ForageIntake = RecentForageIntake(Now, MemorySeconds) + Energy;
        ForageMemoryPosition = Site;
        LastForageIntakeAt = Now;
    }
};

namespace EcoFaunaFeeding
{
    inline double BreedingReserve(double Energy, double MaxEnergy, double RecentIntake)
    {
        return FMath::Max(0., Energy - MaxEnergy * EcoLifeV3::FIndividual::MinimumParentEnergy) + RecentIntake;
    }

    inline double EncounterWeight(int32 Available, const FEcoFaunaPersistenceSettings& Settings)
    {
        return FMath::Lerp(double(Settings.ScarcePreyValue), 1., Available / (Available + double(Settings.PreyHalfSaturation)));
    }

    inline double Value(double Energy, double Seconds, double Risk = 0.)
    {
        return FMath::Max(0., Energy - Risk) / (1. + Seconds);
    }
}

/** Server-side stock tied to one committed death. Measured in vitality energy units. */
struct FEcoFaunaCarcass
{
    FVector Position = FVector::ZeroVector;
    FName Region;
    FName Species;
    double OpenAt = 0.;
    double ExpiresAt = 0.;
    double ExclusiveUntil = 0.;
    int64 KillerId = 0;
    double PlacesResetAt = 0.;
    int32 UsedPlaces = 0;
    int32 FeedingPlaces = 2;
    bool bGrounded = true;
    float Remaining = 0.f;

    bool IsAvailable(FName EaterRegion, const FEcoFaunaSpecies& Eater, double Now) const
    {
        return bGrounded && Region == EaterRegion && (Species != Eater.SpeciesId || Eater.bAllowConspecificCarrion)
            && Now >= OpenAt && Now < ExpiresAt && Remaining > UE_SMALL_NUMBER;
    }

    bool CanApproach(int64 AgentId, double Now) const
    {
        return bGrounded && Now >= OpenAt && Now < ExpiresAt && Remaining > UE_SMALL_NUMBER
            && (Now >= ExclusiveUntil || KillerId == AgentId);
    }

    bool RetainsKillerTarget(int64 AgentId, double Now, bool bAfterSharing) const
    {
        return KillerId == AgentId && (Now < ExclusiveUntil
            || (bAfterSharing && bGrounded && Now < ExpiresAt && Remaining > UE_SMALL_NUMBER));
    }

    float Bite(int64 AgentId, double Now, float Requested)
    {
        if (!CanApproach(AgentId, Now) || Requested <= 0.f) return 0.f;
        if (Now >= PlacesResetAt) { PlacesResetAt = Now + 1.; UsedPlaces = 0; }
        if (UsedPlaces >= FeedingPlaces) return 0.f;
        ++UsedPlaces;
        return Take(Requested);
    }

    float Take(float Requested)
    {
        const float Granted = FMath::Clamp(Requested, 0.f, Remaining);
        Remaining -= Granted;
        return Granted;
    }
};

UCLASS()
class UEcoFaunaTrait : public UEcoMassNetworkTrait
{
    GENERATED_BODY()
    virtual void BuildTemplate(FMassEntityTemplateBuildContext& Context, const UWorld& World) const override;
};
