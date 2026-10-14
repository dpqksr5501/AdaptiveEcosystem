#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SmartObjectTypes.h"
#include "SmartObjectRuntime.h"
#include "Mass/EntityHandle.h"
#include "AI/Behavior/EcoSpeciesAIProfile.h"
#include "EcoSpeciesAIInteractionSubsystem.generated.h"
class AEcoSpeciesAIActivitySite;
class AEcoSpeciesAIFixture;
struct FMassEntityManager;

/** GT reservation owner for non-Shelter slots. Existing Social retains Shelter ownership. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoSpeciesAIInteractionSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    virtual void Deinitialize() override;
    void RegisterSite(AEcoSpeciesAIActivitySite& Site);
    void UnregisterSite(AEcoSpeciesAIActivitySite& Site);
    int64 RegisterFixture(AEcoSpeciesAIFixture& Fixture);
    void UnregisterFixture(AEcoSpeciesAIFixture& Fixture);
    AEcoSpeciesAIFixture* FindFixture(int64 Id) const;
    const TArray<TWeakObjectPtr<AEcoSpeciesAIFixture>>& GetFixtures() const { return Fixtures; }
    bool FindSite(FName Region,bool Predator,EEcoActivitySlotKind Kind,const FVector& Position,FVector& Goal) const;
    int64 Claim(FMassEntityHandle Entity,int64 AgentId,FName Region,bool Predator,EEcoActivitySlotKind Kind,
        const FVector& Position,double Now,float Lease,FVector& Goal);
    bool Renew(int64 Id,int64 AgentId,double Now,float Lease,FVector& Goal);
    bool Occupy(int64 Id,int64 AgentId);
    void Release(int64 Id);
    void RejectUnreachable(int64 Id,double Now);
    void Cleanup(FMassEntityManager& EM,double Now);
    struct FFixtureReward { int64 AgentId=0; uint64 Receipt=0; float Units=0; double EligibleAt=0; };
    void QueueFixtureReward(int64 AgentId,float Units,double EligibleAt);
    void DrainFixtureRewards(double Through,TArray<FFixtureReward>& Results);
    int32 NumReservations() const { return Reservations.Num(); }
    uint64 FixtureCaptures=0, Claims=0, Releases=0;
    bool bAllowFixtures=false;
private:
    struct FReservation
    {
        int64 AgentId=0;
        FMassEntityHandle Entity;
        TWeakObjectPtr<AEcoSpeciesAIActivitySite> Site;
        FSmartObjectClaimHandle Handle;
        double Expires=0;
        bool bOccupied=false;
    };
    TArray<TWeakObjectPtr<AEcoSpeciesAIActivitySite>> Sites;
    // Static activity sites use a coarse index; moving sites must re-register.
    TMap<FIntPoint,TArray<TWeakObjectPtr<AEcoSpeciesAIActivitySite>>> SiteCells;
    void GatherSites(const FVector& Position,TArray<AEcoSpeciesAIActivitySite*>& Results) const;
    TSet<int64> InvalidatedReservations;
    struct FRejectedSite { int64 AgentId;TWeakObjectPtr<AEcoSpeciesAIActivitySite> Site;double Until; };
    TArray<FRejectedSite> RejectedSites;
    TArray<TWeakObjectPtr<AEcoSpeciesAIFixture>> Fixtures;
    TMap<int64,FReservation> Reservations;
    TArray<FFixtureReward> FixtureRewards;
    int64 NextReservation=1, NextFixture=1;
    uint64 NextReceipt=1;
};
