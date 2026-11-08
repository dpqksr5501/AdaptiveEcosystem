#pragma once

#include "CoreMinimal.h"
#include "Components/WidgetComponent.h"
#include "EcoHealthBarComponent.generated.h"

/** Local screen-space presentation only. Feed authoritative/replicated values; never applies damage. */
UCLASS(ClassGroup=(UI), meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoHealthBarComponent : public UWidgetComponent
{
	GENERATED_BODY()
public:
	UEcoHealthBarComponent();
	UFUNCTION(BlueprintCallable, Category="Health|Presentation")
	void SetHealthNormalized(float Fraction, bool bAlive = true, bool bHasHealth = true);
	UFUNCTION(BlueprintCallable, Category="Health|Presentation")
	void SetHealth(float CurrentHealth, float MaxHealth, bool bAlive = true);
	/** Call when a visual leaves relevance or is returned to a pool. */
	UFUNCTION(BlueprintCallable, Category="Health|Presentation")
	void ClearHealth();
	UFUNCTION(BlueprintPure, Category="Health|Presentation")
	float GetHealthFraction() const { return HealthFraction; }
	UFUNCTION(BlueprintPure, Category="Health|Presentation")
	bool HasHealthSample() const { return bHasHealthSample; }
	virtual void InitWidget() override;
protected:
	virtual void BeginPlay() override;
private:
	float HealthFraction = 0.f;
	bool bHasHealthSample = false;
};
