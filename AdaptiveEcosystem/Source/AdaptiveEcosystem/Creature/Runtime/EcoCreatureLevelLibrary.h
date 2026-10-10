#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EcoCreatureLevelLibrary.generated.h"

USTRUCT(BlueprintType)
struct FEcoCreatureGroundProbe
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) bool bValid = false;
    UPROPERTY(BlueprintReadOnly) FVector Position = FVector::ZeroVector;
};

/** Uses the same geometry checks as authority spawning, also callable from Editor Python. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoCreatureLevelLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Creature|Level", meta=(WorldContext="WorldContext"))
    static FEcoCreatureGroundProbe ProbeGround(UObject* WorldContext, FVector Hint);
};
