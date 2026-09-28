#include "World/EcoWorldClockSubsystem.h"
#include "World/EcoDayCycleProvider.h"
#include "AdaptiveEcosystem.h"
#include "Engine/Engine.h"
#include "Engine/World.h"

bool EcoClock::EvaluateFixedCycle(double Time, double DaySeconds, double NightSeconds, FEcoDayCycleState& Out)
{
	const double Duration = DaySeconds + NightSeconds;
	if (!FMath::IsFinite(Time) || Time < 0.0 || !FMath::IsFinite(Duration)
		|| !FMath::IsFinite(DaySeconds) || !FMath::IsFinite(NightSeconds)
		|| DaySeconds <= 0.0 || NightSeconds <= 0.0 || Time / Duration >= static_cast<double>(MAX_int64))
	{
		return false;
	}
	Out.CycleId = static_cast<int64>(FMath::FloorToDouble(Time / Duration));
	const double CycleStart = static_cast<double>(Out.CycleId) * Duration;
	const bool bDay = Time < CycleStart + DaySeconds;
	Out.Phase = bDay ? EEcoDayPhase::Day : EEcoDayPhase::Night;
	Out.PhaseStartSeconds = bDay ? CycleStart : CycleStart + DaySeconds;
	Out.PhaseEndSeconds = bDay ? CycleStart + DaySeconds : CycleStart + Duration;
	return IsValidPhase(Time, Out);
}

bool EcoClock::IsValidPhase(double Time, const FEcoDayCycleState& Phase)
{
	return FMath::IsFinite(Time) && Time >= 0.0 && Phase.CycleId >= 0
		&& (Phase.Phase == EEcoDayPhase::Day || Phase.Phase == EEcoDayPhase::Night)
		&& FMath::IsFinite(Phase.PhaseStartSeconds) && FMath::IsFinite(Phase.PhaseEndSeconds)
		&& Phase.PhaseStartSeconds >= 0.0 && Phase.PhaseStartSeconds <= Time && Time < Phase.PhaseEndSeconds;
}

bool UEcoWorldClockSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return Super::ShouldCreateSubsystem(Outer) && World && World->IsGameWorld() && World->GetNetMode() != NM_Client;
}

bool UEcoWorldClockSubsystem::HasServerAuthority() const
{
	return IsInGameThread() && GetWorld() && GetWorld()->IsGameWorld() && GetWorld()->GetNetMode() != NM_Client;
}

bool UEcoWorldClockSubsystem::SetDayCycleProvider(UObject* Provider)
{
	if (!HasServerAuthority() || bRunning || !IsValid(Provider) || Provider->GetWorld() != GetWorld()
		|| !Cast<IEcoDayCycleProvider>(Provider))
	{
		return false;
	}
	DayCycleProvider = Provider;
	return true;
}

bool UEcoWorldClockSubsystem::StartClock(int32 WorldEpoch, double DaySeconds, double NightSeconds)
{
	if (!HasServerAuthority() || WorldEpoch <= 0) return false;
	if (bRunning) return Current.WorldEpoch == WorldEpoch;
	FEcoDayCycleState Check;
	if (!EcoClock::EvaluateFixedCycle(0.0, DaySeconds, NightSeconds, Check)) return false;
	DayDuration = DaySeconds;
	NightDuration = NightSeconds;
	Current.WorldEpoch = WorldEpoch;
	FEcoServerTimeSnapshot Initial;
	if (!GetSnapshotAt(0.0, Initial)) return false;
	Current = Initial;
	bRunning = true;
	return true;
}

bool UEcoWorldClockSubsystem::GetSnapshotAt(double TimeSeconds, FEcoServerTimeSnapshot& Out) const
{
	if (!HasServerAuthority() || !FMath::IsFinite(TimeSeconds) || TimeSeconds < 0.0) return false;
	FEcoDayCycleState Phase;
	if (DayCycleProvider)
	{
		const IEcoDayCycleProvider* Provider = Cast<IEcoDayCycleProvider>(DayCycleProvider);
		if (!Provider || !Provider->EvaluateDayCycle(TimeSeconds, Phase)) return false;
	}
	else if (!EcoClock::EvaluateFixedCycle(TimeSeconds, DayDuration, NightDuration, Phase)) return false;
	if (!EcoClock::IsValidPhase(TimeSeconds, Phase)) return false;
	Out.WorldEpoch = Current.WorldEpoch;
	Out.ServerTimeSeconds = TimeSeconds;
	Out.DayCycle = Phase;
	return true;
}

bool UEcoWorldClockSubsystem::AdvanceClock(double DeltaSeconds)
{
	if (!HasServerAuthority() || !bRunning || !FMath::IsFinite(DeltaSeconds) || DeltaSeconds < 0.0) return false;
	FEcoServerTimeSnapshot Next;
	if (!GetSnapshotAt(Current.ServerTimeSeconds + DeltaSeconds, Next)
		|| Next.DayCycle.CycleId < Current.DayCycle.CycleId
		|| (Next.DayCycle.CycleId == Current.DayCycle.CycleId
			&& Next.DayCycle.PhaseStartSeconds < Current.DayCycle.PhaseStartSeconds)) return false;
	Current = Next;
	return true;
}

void UEcoWorldClockSubsystem::PrintServerTime(bool bPrintToScreen) const
{
	if (!HasServerAuthority() || !bRunning) return;
	const FString Message = FString::Printf(TEXT("[Eco Server Time][%s] Epoch=%d Time=%.2fs Cycle=%lld %s Remaining=%.2fs"),
		*GetWorld()->GetName(), Current.WorldEpoch, Current.ServerTimeSeconds, Current.DayCycle.CycleId,
		Current.DayCycle.Phase == EEcoDayPhase::Day ? TEXT("Day") : TEXT("Night"),
		Current.DayCycle.PhaseEndSeconds - Current.ServerTimeSeconds);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("%s"), *Message);
	if (bPrintToScreen && GEngine && GetWorld()->GetNetMode() != NM_DedicatedServer)
	{
		GEngine->AddOnScreenDebugMessage(static_cast<uint64>(GetUniqueID()), 2.0f, FColor::Cyan, Message);
	}
}

void UEcoWorldClockSubsystem::Deinitialize()
{
	bRunning = false;
	DayCycleProvider = nullptr;
	Current = FEcoServerTimeSnapshot();
	Super::Deinitialize();
}
