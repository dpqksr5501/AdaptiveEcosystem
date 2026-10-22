#pragma once

#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoWorldV3.h"
#include "EcoPolicyV3SocialBridge.generated.h"

struct FEcoV3RegionContext;

/** Read-only versioned signal, available after AlarmPropagation and before native Step.
 * Shared reports never become direct observations. Source timestamps survive repeated receptions. */
struct FEcoSocialSignalSnapshot
{
    static constexpr int32 Version=1;
    bool bValid=false,bDirect=false;
    EEcoSenseSource PersonalSource=EEcoSenseSource::None;
    FVector ReportedPosition=FVector::ZeroVector;
    float Strength=0;
    double EvidenceTime=-1,ReceivedTime=-1;
    int64 PersistentHerdId=0;
    uint64 SourceKey=0;
};
struct FEcoBehaviorReasonEvent { double Time=0;FName Reason;FName Region;int64 NativeStep=0; };
struct FEcoBehaviorReasonHistory {
    FEcoBehaviorReasonEvent Events[16];int32 Count=0;
    bool IsEmpty() const { return Count==0; }
    int32 Num() const { return Count; }
    const FEcoBehaviorReasonEvent& Last() const { return Events[Count-1]; }
    const FEcoBehaviorReasonEvent* begin() const { return Events; }
    const FEcoBehaviorReasonEvent* end() const { return Events+Count; }
    void Append(const FEcoBehaviorReasonEvent& Event){
        if(Count==16){for(int32 I=1;I<16;++I)Events[I-1]=Events[I];--Count;}
        Events[Count++]=Event;
    }
};

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
    FEcoBehaviorReasonHistory History;
    void RecordReason(double Now,FName Reason,FName Region,int64 NativeStep){
        if(!History.IsEmpty()&&History.Last().Reason==Reason&&History.Last().Region==Region)return;
        History.Append({Now,Reason,Region,NativeStep});
    }
};

namespace EcoV3Social
{
    ADAPTIVEECOSYSTEM_API FEcoSocialSignalSnapshot ReadSignal(const FEcoSensoryStateFragment& Sense,
        const FEcoAlarmStateFragment& Alarm,int64 CurrentHerdId,double Now,const FEcoSensorySettings& Settings);
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
