#pragma once
#include "Components/ActorComponent.h"
#include "EcoAimComponent.generated.h"
UCLASS(ClassGroup=(Combat), meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoAimComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UEcoAimComponent();
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Aim") bool bAiming=false;
    bool SetAiming(bool bValue);
    void TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick) override;
    void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
protected:
    void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    void Restore();
    uint8 OldBoneTick=0;
    bool bCaptured=false, bOldYaw=false, bOldOrient=false;
    FVector DefaultOffset=FVector::ZeroVector;
    FVector AimOffset=FVector::ZeroVector;
    float AimLength=200,AimFOV=65,BlendSeconds=.15f;
    float DefaultLength=0,DefaultFOV=90,Alpha=0;
};
