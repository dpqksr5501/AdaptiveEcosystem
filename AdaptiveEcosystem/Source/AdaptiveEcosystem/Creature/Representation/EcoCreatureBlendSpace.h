#pragma once
#include "CoreMinimal.h"
#include "Animation/BlendSpace1D.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EcoCreatureBlendSpace.generated.h"

/** Ordinary editable Blend Space 1D. Editor setup is never part of runtime inference. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoCreatureBlendSpaceLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Creature|Editor")
    static bool ConfigureLocomotion(UBlendSpace1D* BlendSpace, UAnimSequence* Idle, UAnimSequence* Walk, UAnimSequence* Run, float WalkSpeed = 300.f, float RunSpeed = 900.f);
};
