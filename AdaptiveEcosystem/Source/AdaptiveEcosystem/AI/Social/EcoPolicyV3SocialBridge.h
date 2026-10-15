#pragma once

#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoWorldV3.h"
#include "EcoPolicyV3SocialBridge.generated.h"

struct FEcoV3RegionContext;

// Separate from WildFlight: policy request, native world reflex, and Social override stay inspectable.
enum class EEcoV3SocialControl : uint8 { None, Alert, Flee, ShelterTravel, ShelterHold, Regroup };
USTRUCT()
struct FEcoV3SocialBridgeFragment : public FMassFragment
{
    GENERATED_BODY()
    EEcoV3SocialControl Applied = EEcoV3SocialControl::None;
    int32 NativeBehavior = 0;
    int64 AppliedReservation = 0;
    bool bRejectedUnsafeShelter = false;
    int32 SharedStartleLeft=0; // A persistent shared alarm must not restart startle every native decision.
};

namespace EcoV3Social
{
    // Explicit discrete-action projection for the existing Social preference contract.
    // This is NOT a 7->4 PPO inference; FEcoPolicyOutputFragment remains untouched.
    ADAPTIVEECOSYSTEM_API FEcoPolicyActionV1 ProjectPolicy(int32 Request);
    ADAPTIVEECOSYSTEM_API bool IsShelterTarget(const FEcoV3RegionContext& Region,const FVector& Position);
    ADAPTIVEECOSYSTEM_API bool ApplyControl(const FEcoSocialMovementRequestFragment& Request,
        const FEcoAlarmStateFragment& Alarm, const FEcoV3RegionContext& Region,
        const FEcoIntegratedV3Fragment& Link, FEcoV3SocialBridgeFragment& Audit,
        const EcoWorldV3::FHerbView& Herb, bool bLeaseValid, double Now);
}

// Reads only direct native evidence, publishes it into an independent Herd channel.
// No Transform, Velocity, Vitals or PPO output writer.
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPolicyV3SocialSenseProcessor : public UMassProcessor
{
    GENERATED_BODY()
public:
    UEcoPolicyV3SocialSenseProcessor();
protected:
    virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& Manager) override;
    virtual void Execute(FMassEntityManager& Manager, FMassExecutionContext& Context) override;
private:
    FMassEntityQuery Query;
    double NextScan=0;
};
