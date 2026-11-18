#include "Ecology/EcologySimulationSubsystem.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Engine/World.h"

bool UEcologySimulationSubsystem::ConfigureRegionRegeneration(FName RegionId, float Rate, bool bRainfall,
	float DryMultiplier, float WetMultiplier)
{
	if (!CanMutateAuthoritativeState(TEXT("ConfigureRegionRegeneration")) || bResourceStepOpen
		|| !FMath::IsFinite(Rate) || Rate < 0 || !FMath::IsFinite(DryMultiplier) || DryMultiplier < 0 || DryMultiplier > 4
		|| !FMath::IsFinite(WetMultiplier) || WetMultiplier < 0 || WetMultiplier > 4) return false;
	auto* State = RegionalStates.Find(RegionId); if (!State) return false;
	const auto* Inputs = GetWorld()->GetSubsystem<UEcologyWorldSubsystem>();
	if (bRainfall && (!Inputs || !Inputs->GetRegion(RegionId))) return false;
	State->FoodRegenerationRate = Rate;
	State->bRainfallAffectsRegeneration = bRainfall;
	State->DryRegenerationMultiplier = DryMultiplier;
	State->WetRegenerationMultiplier = WetMultiplier;
	return true;
}

bool UEcologySimulationSubsystem::CaptureEnvironmentInputs(const FEcoServerTimeSnapshot& Time)
{
	const auto* Inputs = GetWorld()->GetSubsystem<UEcologyWorldSubsystem>();
	TArray<FRegionEnvironmentState> Snapshots;
	Snapshots.Reserve(RegionIds.Num());
	// A streamed-out region keeps its last completed weather until its provider returns.
	for (const FName Id : RegionIds)
	{
		const auto& State = RegionalStates.FindChecked(Id);
		const auto* Region = Inputs ? Inputs->GetRegion(Id) : nullptr;
		auto Weather = Region ? Region->GetEffectiveEnvironmentState() : State.CompletedEnvironment;
		if (!FMath::IsFinite(Weather.Rainfall) || Weather.Rainfall < 0 || Weather.Rainfall > 1
			|| !FMath::IsFinite(Weather.Humidity) || Weather.Humidity < 0 || Weather.Humidity > 1
			|| !FMath::IsFinite(Weather.Temperature)) return false;
		Weather.DayPhase = Time.DayCycle.Phase;
		Snapshots.Add(Weather);
	}
	for (int32 I = 0; I < RegionIds.Num(); ++I)
	{
		auto& State = RegionalStates.FindChecked(RegionIds[I]);
		State.CompletedEnvironment = Snapshots[I];
		State.EffectiveRegenerationMultiplier = State.bRainfallAffectsRegeneration
			? FMath::Lerp(State.DryRegenerationMultiplier, State.WetRegenerationMultiplier, Snapshots[I].Rainfall) : 1.f;
	}
	return true;
}
