#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EcoJWJMultiplayerAuthoring.generated.h"

/** Editor-only terrain loading for the user-authorized JWJ multiplayer map. */
UCLASS()
class UEcoJWJMultiplayerAuthoring : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Ecology|Editor")
    static bool LoadStartTerrain(UWorld* World, FVector Center);
};
