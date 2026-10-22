#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "GameFramework/Actor.h"
#include "MassEntityTypes.h"
#include "Core/EcoMigrationTypes.h"
#include "EcoHerdMigration.generated.h"

struct FMassEntityManager;
struct FEcoServerTimeSnapshot;

UENUM(BlueprintType)
enum class EEcoHerdJourneyState : uint8 { Preparing, Traveling, Resting, Regrouping, Settled, Failed };

/** Intent/diagnostics only. The native Step remains the sole movement/metabolism writer. */
USTRUCT()
struct FEcoHerdTravelFragment : public FMassFragment
{
    GENERATED_BODY()
    int64 PlanId=0, PersistentHerdId=0;
    bool bActive=false, bPause=false;
    FVector Goal=FVector::ZeroVector;
    float SpeedScale=1;
    int32 Waypoint=0;
    double LastProgressTime=0, BestDistance=MAX_dbl, MembershipUntil=0;
    FName Reason=NAME_None;
};

/** Authored traversable knowledge. Points are world coordinates; both ends must lie inside their native stages. */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoHerdMigrationRoute : public AActor
{
    GENERATED_BODY()
public:
    AEcoHerdMigrationRoute();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Migration") FName FromRegion;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Migration") FName ToRegion;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Migration") TArray<FVector> Points;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Migration") bool bBidirectional=true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Migration") bool bEnabled=true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Migration") float CorridorWidth=600;
};

struct FEcoHerdJourney
{
    int64 Id=0, HerdId=0;
    FName Origin, Destination, Reason;
    EEcoHerdJourneyState State=EEcoHerdJourneyState::Preparing;
    TArray<int64> Members;
    TArray<FVector> Points;
    double Started=0, Changed=0, CooldownUntil=0;
    float CorridorWidth=600;
    int32 Arrived=0, Dead=0, Failed=0;
    bool bReturning=false;
};

/** Game-thread coordination at completed M4 resource boundaries; no replication or position integration. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoHerdMigrationSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    bool Reconcile(FMassEntityManager& Manager, const FEcoServerTimeSnapshot& Time, int64 Step,
        TArray<FEcoMigrationOutcome>& Arrivals);
    bool IsEnabled() const;
    /** Explicit copy-map test fixture; records food removal in the existing authority ledger. */
    UFUNCTION(BlueprintCallable,Category="Migration|Audit") bool ApplyFoodFractionForAudit(FName Region,float Fraction,bool bSuspendRegeneration=false);
    const TMap<int64,FEcoHerdJourney>& GetPlans() const { return Plans; }
    static const TCHAR* StateName(EEcoHerdJourneyState State);
private:
    TMap<int64,FEcoHerdJourney> Plans;
    TMap<int64,double> ShortageSince;
    TMap<int64,double> NextPlanAttempt;
    int64 NextPlan=1;
};
