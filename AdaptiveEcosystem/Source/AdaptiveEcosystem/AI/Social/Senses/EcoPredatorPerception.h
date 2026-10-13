#pragma once
#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "AI/Social/Senses/EcoSensoryTypes.h"
#include "EcoPredatorPerception.generated.h"

/** Separate from threat/herd memory: a predator's personal prey observation only. */
USTRUCT()
struct FEcoPreySenseFragment : public FMassFragment
{
    GENERATED_BODY()
    // Reuse validated personal ageing math; never publishes this cue to a Herd.
    FEcoSensoryStateFragment Cue;
    FMassEntityHandle Target;
    int64 TargetAgentId = 0;
    void Forget() { Cue.Forget(); Target = {}; TargetAgentId = 0; }
};

USTRUCT()
struct FEcoPredatorSensesSharedFragment : public FMassSharedFragment
{
    GENERATED_BODY()
    FEcoSensorySettings Settings;
};

/** Read-only pursuit handoff. No hidden transform query; ages the copied cue at read time. */
namespace EcoPredatorSenses
{
    inline bool ReadPursuit(const FEcoPreySenseFragment& Sense, const FEcoSensorySettings& Settings,
        const FEcoSensoryProfileFragment& Profile, double Now, FVector& Position)
    {
        const auto Snapshot = Sense.Cue.MakeReadSnapshot(Now, Settings, Profile, 0);
        if (Sense.TargetAgentId <= 0 || !Snapshot.bValid || !Snapshot.bHasPersonalThreat) return false;
        Position = Snapshot.LastKnownPosition; return true;
    }
}

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPredatorPerceptionProcessor : public UMassProcessor
{
    GENERATED_BODY()
public:
    UEcoPredatorPerceptionProcessor();
protected:
    virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
    virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;
private:
    FMassEntityQuery Query;
    float UntilScan = 0;
};
