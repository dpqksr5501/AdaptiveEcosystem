#pragma once
#include "Kismet/BlueprintFunctionLibrary.h"
#include "EcoWeaponAuthoringLibrary.generated.h"
class USkeletalMesh;
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoWeaponAuthoringLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Adds only a missing grip socket to the supplied mesh; never edits existing sockets. */
    UFUNCTION(BlueprintCallable,Category="Eco|Editor") static bool EnsureGunSocket(USkeletalMesh* Mesh,FName Bone=TEXT("hand_r"));
};
