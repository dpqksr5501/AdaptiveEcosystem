#include "Network/EcoGameState.h"
#include "World/EcoWorldClockSubsystem.h"
#include "Core/EcoRuntimeSettings.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

static TAutoConsoleVariable<int32> CVarEcoClockLog(TEXT("eco.Clock.Log"), 0, TEXT("Log synchronized day/night transitions."));

void AEcoGameState::EnablePresentationClock()
{
    if (!HasAuthority() || bPresentationClock) return;
    bPresentationClock = true;
    PresentationOrigin = GetServerWorldTimeSeconds();
}

void AEcoGameState::PublishClockSchedule()
{
    const double Now = GetServerWorldTimeSeconds();
    if (LastClockPublication >= 0 && Now - LastClockPublication < 0.2) return;
    const auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
    const bool bEcology = Clock && Clock->IsClockRunning();
    if (!bEcology && !bPresentationClock) return;
    FEcoClockSchedule Next;
    Next.ServerWorldSeconds = Now;
    if (bEcology)
    {
        Next.Sample = Clock->GetServerTime();
        Next.Rate = IsMassReplicationReady() ? 1.0 : 0.0;
    }
    else
    {
        Next.Sample.WorldEpoch = GetWorldEpoch();
        Next.Sample.ServerTimeSeconds = FMath::Max(0.0, Now - PresentationOrigin);
    }
    const auto* Settings = GetDefault<UEcoRuntimeSettings>();
    double Cursor = Next.Sample.ServerTimeSeconds;
    for (int32 Index = 0; Index < 4; ++Index)
    {
        FEcoServerTimeSnapshot Future;
        const bool bValid = bEcology ? Clock->GetSnapshotAt(Cursor, Future) :
            EcoClock::EvaluateFixedCycle(Cursor, Settings->DayDurationSeconds, Settings->NightDurationSeconds, Future.DayCycle);
        if (!bValid) break;
        Next.Phases.Add(Future.DayCycle);
        if (Index == 0) Next.Sample.DayCycle = Future.DayCycle;
        Cursor = Future.DayCycle.PhaseEndSeconds;
    }
    if (Next.Phases.IsEmpty()) return;
    ClockSchedule = MoveTemp(Next);
    LastClockPublication = Now;
    ForceNetUpdate();
}

void AEcoGameState::OnRep_ReplicatedWorldTimeSecondsDouble()
{
    Super::OnRep_ReplicatedWorldTimeSecondsDouble();
    bReceivedServerTime = true;
}

bool AEcoGameState::GetSynchronizedClock(FEcoServerTimeSnapshot& Time) const
{
    if (!HasAuthority() && !bReceivedServerTime) return false;
    return ClockSchedule.Evaluate(GetServerWorldTimeSeconds(), Time);
}

void AEcoGameState::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
#if WITH_DEV_AUTOMATION_TESTS
    float TestExitAfter = 0;
    if (FParse::Value(FCommandLine::Get(), TEXT("EcoCommonTestExitAfter="), TestExitAfter) &&
        TestExitAfter > 0 && GetWorld()->GetRealTimeSeconds() >= TestExitAfter)
        FPlatformMisc::RequestExit(false);
#endif
    if (HasAuthority()) PublishClockSchedule();
    FEcoServerTimeSnapshot Time;
    if (!GetSynchronizedClock(Time)) return;
    const bool bInitial = LastPresentedClock.WorldEpoch != Time.WorldEpoch;
    if (bInitial || Time.DayCycle.PhaseStartSeconds > LastPresentedClock.DayCycle.PhaseStartSeconds)
    {
        LastPresentedClock = Time; // Time correction cannot replay an earlier transition.
        if (CVarEcoClockLog.GetValueOnGameThread())
            UE_LOG(LogTemp, Log, TEXT("[Eco Clock] Mode=%d Epoch=%d Cycle=%lld Phase=%d Boundary=%.3f Time=%.3f ServerWorld=%.3f Initial=%d"),
                int32(GetNetMode()), Time.WorldEpoch, Time.DayCycle.CycleId, int32(Time.DayCycle.Phase),
                Time.DayCycle.PhaseStartSeconds, Time.ServerTimeSeconds, GetServerWorldTimeSeconds(), bInitial);
        OnClockPhaseChanged.Broadcast(Time, bInitial);
    }
}
