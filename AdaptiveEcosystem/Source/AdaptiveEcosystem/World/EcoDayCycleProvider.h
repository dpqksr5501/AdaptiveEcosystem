#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "Core/EcoTimeTypes.h"
#include "EcoDayCycleProvider.generated.h"

UINTERFACE(BlueprintType, meta=(CannotImplementInterfaceInBlueprint))
class ADAPTIVEECOSYSTEM_API UEcoDayCycleProvider : public UInterface
{
	GENERATED_BODY()
};

/** Implement on the future server day/night/weather subsystem.
 * Evaluation must support historical times for bounded scheduler catch-up.
 * Register before the population starts; weather/resource mutation is not part of this interface.
 */
class ADAPTIVEECOSYSTEM_API IEcoDayCycleProvider
{
	GENERATED_BODY()
public:
	virtual bool EvaluateDayCycle(double ServerTimeSeconds, FEcoDayCycleState& OutState) const = 0;
};
