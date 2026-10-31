#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Commandlets/Commandlet.h"
#include "SmartObjectDefinition.h"
#include "EcoSpeciesAIAssetBuilder.generated.h"

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoSpeciesAIAssetBuilder : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Create saved experiment assets only when absent; never overwrite a team's existing assets. */
    UFUNCTION(BlueprintCallable,Category="Species AI|Editor") static bool CreateDefaultAssets();
};
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoSpeciesAIAssetsCommandlet : public UCommandlet
{
    GENERATED_BODY()
public:
    UEcoSpeciesAIAssetsCommandlet();
    virtual int32 Main(const FString& Params) override;
};
