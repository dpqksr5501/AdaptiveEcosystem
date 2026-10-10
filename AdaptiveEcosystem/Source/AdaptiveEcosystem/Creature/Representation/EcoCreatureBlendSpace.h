#pragma once
#include "CoreMinimal.h"
#include "Animation/BlendSpace1D.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EcoCreatureBlendSpace.generated.h"

class UBlueprint;

/** Ordinary editable Blend Spaces. Editor setup is never part of runtime inference. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoCreatureBlendSpaceLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Creature|Editor")
    static bool ConfigureLocomotion(UBlendSpace1D* BlendSpace, UAnimSequence* Idle, UAnimSequence* Walk, UAnimSequence* Run, float WalkSpeed = 300.f, float RunSpeed = 900.f);

    /** 2D Speed x Turn (-1 left, +1 right). Missing run turns fall back to straight Run. */
    UFUNCTION(BlueprintCallable, Category="Creature|Editor")
    static bool ConfigureTurning(UBlendSpace* BlendSpace, UAnimSequence* Idle, UAnimSequence* Walk,
        UAnimSequence* WalkLeft, UAnimSequence* WalkRight, UAnimSequence* Run,
        UAnimSequence* RunLeft, UAnimSequence* RunRight, float WalkSpeed = 300.f, float RunSpeed = 900.f);

    /** Compile-safe native CDO edit: update the Blueprint default cache before saving. */
    UFUNCTION(BlueprintCallable, Category="Creature|Editor")
    static bool ConfigureRepresentation(UBlueprint* Blueprint, UBlendSpace* BlendSpace, FRotator MeshRotation, FVector MeshForwardAxis);
    UFUNCTION(BlueprintCallable, Category="Creature|Editor")
    static bool ConfigureFootstepNotifies(UBlueprint* Blueprint, bool bEnabled);
};
