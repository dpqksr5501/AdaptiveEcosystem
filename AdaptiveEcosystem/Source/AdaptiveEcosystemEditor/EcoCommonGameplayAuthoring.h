#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EcoCommonGameplayAuthoring.generated.h"
class UBlueprint;
UCLASS()
class UEcoCommonGameplayAuthoring : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Ecology|Editor")
    static FString InspectBlueprint(UBlueprint* Blueprint);
};
