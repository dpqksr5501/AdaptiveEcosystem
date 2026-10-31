#include "World/EcoRegionEnvironmentAdapter.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "World/EcoWorldClockSubsystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Engine/World.h"
#include "Network/EcoGameState.h"

AEcoRegionEnvironmentAdapter::AEcoRegionEnvironmentAdapter()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = .2f;
}

bool AEcoRegionEnvironmentAdapter::EvaluateCycleRainfall(double SimulationSeconds, float& OutRainfall) const
{
	OutRainfall = 0;
	if (!bCycleRainfall || bApplyAuthoredWeather || !FMath::IsFinite(SimulationSeconds) || SimulationSeconds < 0
		|| !FMath::IsFinite(RainCycleSeconds) || RainCycleSeconds < 20 || RainCycleSeconds > 86400
		|| !FMath::IsFinite(RainPhaseOffsetSeconds) || !FMath::IsFinite(DryRainfall) || DryRainfall < 0 || DryRainfall > 1
		|| !FMath::IsFinite(WetRainfall) || WetRainfall < 0 || WetRainfall > 1
		|| !FMath::IsFinite(RainTransitionFraction) || RainTransitionFraction < .01f || RainTransitionFraction > .25f) return false;
	const double Phase = FMath::Fmod(FMath::Fmod(SimulationSeconds + RainPhaseOffsetSeconds, RainCycleSeconds) + RainCycleSeconds, RainCycleSeconds) / RainCycleSeconds;
	const double Blend = RainTransitionFraction;
	double Alpha = Phase < .5 - Blend ? 0 : (Phase < .5 ? (Phase - (.5 - Blend)) / Blend : (Phase < 1 - Blend ? 1 : (1 - Phase) / Blend));
	Alpha = Alpha * Alpha * (3 - 2 * Alpha);
	OutRainfall = FMath::Lerp(DryRainfall, WetRainfall, float(Alpha));
	return true;
}

bool AEcoRegionEnvironmentAdapter::ResolveAuthorityRegions(TArray<AEcologyRegion*>& Targets) const
{
	Targets.Reset();
	if (!GetWorld() || !GetWorld()->IsGameWorld() || GetNetMode() == NM_Client) return false;
	const auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	const auto* WorldInputs = GetWorld()->GetSubsystem<UEcologyWorldSubsystem>();
	if (!Ecology || !WorldInputs) return false;
	TArray<FName> Ids = RegionIds;
	if (Ids.IsEmpty()) Ecology->GetRegionIds(Ids);
	// Validate the whole batch before changing any Region actor.
	for (const FName Id : Ids)
	{
		auto* Region = WorldInputs->GetRegion(Id); if (!Region) return false;
		Targets.AddUnique(Region);
	}
	return !Targets.IsEmpty();
}

bool AEcoRegionEnvironmentAdapter::ApplyWeather(const FRegionEnvironmentState& Weather)
{
	if (!FMath::IsFinite(Weather.Temperature) || !FMath::IsFinite(Weather.Humidity)
		|| !FMath::IsFinite(Weather.Rainfall) || Weather.Humidity < 0 || Weather.Humidity > 1
		|| Weather.Rainfall < 0 || Weather.Rainfall > 1
		|| uint8(Weather.WeatherState) > uint8(EEcoWeatherState::Drought)) return false;
	TArray<AEcologyRegion*> Targets;
	if (!ResolveAuthorityRegions(Targets)) return false;
	for (auto* Region : Targets) Region->SetEnvironmentState(Weather);
	return true;
}

bool AEcoRegionEnvironmentAdapter::ApplyRainfall(float Rainfall, EEcoWeatherState WeatherState)
{
	if (!FMath::IsFinite(Rainfall) || Rainfall < 0 || Rainfall > 1 || uint8(WeatherState) > uint8(EEcoWeatherState::Drought)) return false;
	TArray<AEcologyRegion*> Targets;
	if (!ResolveAuthorityRegions(Targets)) return false;
	for (auto* Region : Targets)
	{
		auto Weather = Region->GetEnvironmentState();
		Weather.Rainfall = Rainfall; Weather.WeatherState = WeatherState;
		Region->SetEnvironmentState(Weather);
	}
	return true;
}

void AEcoRegionEnvironmentAdapter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!GetWorld() || !GetWorld()->IsGameWorld()) return;
	// Placed, nonreplicated actors may have ROLE_Authority even in NM_Client.
	// World NetMode determines simulation ownership; client events only consume DTOs.
	const bool bAuthorityWorld = GetNetMode() != NM_Client;
	FEcoServerTimeSnapshot Time;
	if (bAuthorityWorld)
	{
		if (bApplyAuthoredWeather && !bCycleRainfall) ApplyWeather(AuthoredWeather);
		const auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
		if (!Clock || !Clock->IsClockRunning()) return;
		Time = Clock->GetServerTime();
		if (bCycleRainfall)
		{
			float Rain = 0;
			const bool bValid = EvaluateCycleRainfall(Time.ServerTimeSeconds, Rain);
			if (bValid) { ApplyRainfall(Rain, Rain > 0 ? EEcoWeatherState::Rain : EEcoWeatherState::Clear); bCycleRejected = false; }
			else if (!bCycleRejected) { UE_LOG(LogTemp, Error, TEXT("[Eco Environment] Rejected climate cycle on %s"), *GetPathName()); bCycleRejected = true; }
		}
	}
	const auto* GameState = GetWorld()->GetGameState<AEcoGameState>();
	if (GameState)
	{
		const auto Summary = GameState->GetEcologySummary();
		if (!bAuthorityWorld) Time = Summary.Time;
		if (Summary.Time.WorldEpoch != LastSummaryEpoch || Summary.Revision != LastSummaryRevision)
		{
			LastSummaryEpoch = Summary.Time.WorldEpoch;
			LastSummaryRevision = Summary.Revision;
			for (const auto& Region : Summary.Regions)
				if (RegionIds.IsEmpty() || RegionIds.Contains(Region.RegionId))
					OnEnvironmentUpdated(Region.RegionId, Region.Environment);
		}
	}
	if (Time.WorldEpoch <= 0) return;
	const double Duration = Time.DayCycle.PhaseEndSeconds - Time.DayCycle.PhaseStartSeconds;
	OnClockUpdated(Time.DayCycle.Phase, Duration > 0 ? FMath::Clamp(float((Time.ServerTimeSeconds - Time.DayCycle.PhaseStartSeconds) / Duration), 0.f, 1.f) : 0.f);
}
