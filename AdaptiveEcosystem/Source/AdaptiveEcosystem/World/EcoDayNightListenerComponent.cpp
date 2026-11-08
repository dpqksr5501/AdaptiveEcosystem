#include "World/EcoDayNightListenerComponent.h"
#include "Network/EcoGameState.h"
#include "Engine/World.h"

UEcoDayNightListenerComponent::UEcoDayNightListenerComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
}
void UEcoDayNightListenerComponent::TickComponent(float Dt, ELevelTick Type, FActorComponentTickFunction* Function)
{
    Super::TickComponent(Dt, Type, Function);
    const auto* State = GetWorld()->GetGameState<AEcoGameState>();
    bHasSynchronizedTime = State && State->GetSynchronizedClock(CurrentTime);
    if (!bHasSynchronizedTime) return;
    const auto& Phase = CurrentTime.DayCycle;
    PhaseProgress = FMath::Clamp(float((CurrentTime.ServerTimeSeconds - Phase.PhaseStartSeconds) /
        (Phase.PhaseEndSeconds - Phase.PhaseStartSeconds)), 0.f, 1.f);
    const bool bInitial = LastEpoch != CurrentTime.WorldEpoch;
    if (bInitial || Phase.PhaseStartSeconds > LastPhaseStart)
    {
        LastEpoch = CurrentTime.WorldEpoch;
        LastPhaseStart = Phase.PhaseStartSeconds;
        OnDayNightChanged.Broadcast(Phase.Phase, CurrentTime, bInitial);
    }
}
