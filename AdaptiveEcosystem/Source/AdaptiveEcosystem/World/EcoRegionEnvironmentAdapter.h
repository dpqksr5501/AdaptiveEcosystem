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
};
