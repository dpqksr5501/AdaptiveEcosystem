#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Core/EcoTimeTypes.h"
#include "EcoDayNightListenerComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FEcoLocalDayNightEvent, EEcoDayPhase, Phase, FEcoServerTimeSnapshot, Time, bool, bInitialState);
/** Add to a light/weather/UI actor. Each listener receives initial state even when created late. */
UCLASS(ClassGroup=(Ecology), meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoDayNightListenerComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UEcoDayNightListenerComponent();
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Function) override;
    UPROPERTY(BlueprintAssignable, Category="Ecology|Time") FEcoLocalDayNightEvent OnDayNightChanged;
    UPROPERTY(BlueprintReadOnly, Category="Ecology|Time") bool bHasSynchronizedTime = false;
    UPROPERTY(BlueprintReadOnly, Category="Ecology|Time") FEcoServerTimeSnapshot CurrentTime;
    UPROPERTY(BlueprintReadOnly, Category="Ecology|Time") float PhaseProgress = 0;
private:
    int32 LastEpoch = 0;
    double LastPhaseStart = -1;
};
