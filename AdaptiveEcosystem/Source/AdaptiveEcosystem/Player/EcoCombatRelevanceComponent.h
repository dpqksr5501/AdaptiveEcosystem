#pragma once
#include "Components/ActorComponent.h"
#include "EcoCombatRelevanceComponent.generated.h"
class AEcoCreatureIntegrationSpawner;
USTRUCT()
struct FEcoCombatOffer
{
    GENERATED_BODY()
    UPROPERTY() TObjectPtr<AEcoCreatureIntegrationSpawner> Coordinator;
    UPROPERTY() int32 Epoch=0;
    UPROPERTY() uint32 Revision=0;
    UPROPERTY() TArray<int64> Agents;
};
/** Owner-only admission and presentation acknowledgement. Never creates logical entities. */
UCLASS(ClassGroup=(Combat), meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoCombatRelevanceComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UEcoCombatRelevanceComponent();
    UPROPERTY(ReplicatedUsing=OnRep_Offer) FEcoCombatOffer Offer;
    void SetPresented(AEcoCreatureIntegrationSpawner* Coordinator,const TArray<int64>& Ids);
    bool CanAttack(const AEcoCreatureIntegrationSpawner* Coordinator,int32 Epoch,int64 Id) const;
    bool IsOffered(int64 Id) const { return Offer.Agents.Contains(Id); }
    void TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick) override;
    void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    UFUNCTION(Server,Reliable) void ServerPresented(uint32 Revision,const TArray<int64>& Ids);
    UFUNCTION() void OnRep_Offer(const FEcoCombatOffer& Previous);
    void ReportPresented();
private:
    friend class FEcoCombatPresentationAdmission;
    void UpdateOffer(FEcoCombatOffer Next);
    TArray<int64> Presented;
    TSet<int64> Ready;
    double LastReady=-10,NextRefresh=0,NextReport=0;
};
