#pragma once
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EcoComboAuthoringLibrary.generated.h"
class UAnimMontage;
class UAnimSequence;
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoComboAuthoringLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Editor-only authoring, never invoked by gameplay. Replaces the supplied owned montage tracks. */
    UFUNCTION(BlueprintCallable, Category="Eco|Editor")
    static bool ConfigureComboMontage(UAnimMontage* Montage, const TArray<UAnimSequence*>& Sequences);
};
