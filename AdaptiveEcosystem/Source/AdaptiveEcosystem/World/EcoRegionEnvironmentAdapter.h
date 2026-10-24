#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Core/EcoRegionTypes.h"
#include "EcoRegionEnvironmentAdapter.generated.h"

class AEcologyRegion;

/** Connect authored weather/sky Blueprints to World inputs. Owns no resources or movement. */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoRegionEnvironmentAdapter : public AActor
{
	GENERATED_BODY()
public:
	AEcoRegionEnvironmentAdapter();
	virtual void Tick(float DeltaSeconds) override;
	/** Empty list means all currently registered regions. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment") TArray<FName> RegionIds;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment") bool bApplyAuthoredWeather = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment") FRegionEnvironmentState AuthoredWeather;
	/** Deterministic authored climate cycle, driven by the authority Ecology clock. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment|Cycle") bool bCycleRainfall = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment|Cycle", meta=(ClampMin="20",ClampMax="86400")) double RainCycleSeconds = 180;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment|Cycle") double RainPhaseOffsetSeconds = 0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment|Cycle", meta=(ClampMin="0",ClampMax="1")) float DryRainfall = 0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment|Cycle", meta=(ClampMin="0",ClampMax="1")) float WetRainfall = .65f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Environment|Cycle", meta=(ClampMin="0.01",ClampMax="0.25")) float RainTransitionFraction = .1f;
	/** Pure evaluation; false for conflicting/static or unsupported settings. */
	UFUNCTION(BlueprintPure, Category="Environment|Cycle") bool EvaluateCycleRainfall(double SimulationSeconds, float& OutRainfall) const;
	UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category="Environment")
	bool ApplyWeather(const FRegionEnvironmentState& Weather);
	/** Rain-only bridge for existing weather managers. Preserves each biome's temperature/humidity. */
	UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category="Environment")
	bool ApplyRainfall(float Rainfall, EEcoWeatherState WeatherState);
	/** Normalized day/night phase time. Blueprint may drive lights and visual rain here. */
	UFUNCTION(BlueprintImplementableEvent, Category="Environment")
	void OnClockUpdated(EEcoDayPhase Phase, float PhaseProgress);
	/** Visual input only. Clients receive completed regional DTOs through GameState. */
	UFUNCTION(BlueprintImplementableEvent, Category="Environment")
	void OnEnvironmentUpdated(FName RegionId, const FRegionEnvironmentState& Environment);
private:
	bool ResolveAuthorityRegions(TArray<AEcologyRegion*>& Targets) const;
	int32 LastSummaryEpoch = 0;
	int32 LastSummaryRevision = 0;
	bool bCycleRejected = false;
};
