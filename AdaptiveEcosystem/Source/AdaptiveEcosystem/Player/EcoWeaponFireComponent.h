#pragma once
#include "Components/ActorComponent.h"
#include "Core/EcoCombatTypes.h"
#include "EcoWeaponFireComponent.generated.h"
class AEcoWeaponActor;
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FEcoWeaponDamageOutcome,const FEcoCombatDamageOutcome&,Outcome);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FEcoWeaponShot,int64,Execution,FVector,Muzzle,FVector,End);
UCLASS(ClassGroup=(Combat),meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoWeaponFireComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UEcoWeaponFireComponent();
    /** Authority-owned ammo contribution; zero until an ammo definition is equipped. */
    UPROPERTY(EditAnywhere,BlueprintReadOnly,Category="Weapon",meta=(ClampMin="0")) float AmmoDamage=0;
    /** Configure a custom channel if required; existing maps can use Visibility. */
    UPROPERTY(EditAnywhere,Category="Weapon") TEnumAsByte<ECollisionChannel> TraceChannel=ECC_Visibility;
    UPROPERTY(BlueprintAssignable,Category="Weapon") FEcoWeaponDamageOutcome OnDamageOutcome;
    UPROPERTY(BlueprintAssignable,Category="Weapon") FEcoWeaponShot OnShot;
    void RequestFire();
    void PublishDamageOutcome(const FEcoCombatDamageOutcome& Outcome);
    bool HasAuthoritativeShot() const { return bInShot; }
    float GetShotDamage() const { return ShotDamage; }
    int64 GetExecution() const { return Execution; }
    UFUNCTION(Server,Reliable) void ServerFire(FVector_NetQuantize ViewOrigin,FVector_NetQuantizeNormal Direction,AEcoWeaponActor* ExpectedWeapon);
    UFUNCTION(Client,Reliable) void ClientDamageOutcome(const FEcoCombatDamageOutcome& Outcome);
    UFUNCTION(NetMulticast,Unreliable) void MulticastShot(int64 Id,FVector_NetQuantize Muzzle,FVector_NetQuantize End);
private:
    bool Trace(const FVector& Start,const FVector& End,FHitResult& Hit) const;
    bool bInShot=false;
    float ShotDamage=0;
    int64 Execution=0;
    double NextAllowedFire=0;
};
