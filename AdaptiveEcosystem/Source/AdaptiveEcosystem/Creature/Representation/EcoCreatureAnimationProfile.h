#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Animation/AnimSequence.h"
#include "Animation/BlendSpace.h"
#include "EcoCreatureAnimationProfile.generated.h"

UENUM(BlueprintType)
enum class EEcoPresentationPose : uint8 { Locomotion, Graze, Look, Hide, Freeze, Sleep, Attack, Recover, Dead };

USTRUCT(BlueprintType)
struct FEcoCreaturePoseClip
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<UAnimSequence> Clip;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bLoop = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, meta=(ClampMin="0.1",ClampMax="3")) float PlayRate = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, meta=(ClampMin="0",ClampMax="1")) float BlendSeconds = .2f;
};

/** Immutable species presentation settings. Assets are ordinary editable Unreal objects. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoCreatureAnimationProfile : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UBlendSpace> Locomotion;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<class USoundBase> AlarmSound;
    /** Index = EEcoPresentationPose, including unused locomotion index 0. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FEcoCreaturePoseClip> Poses;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="0")) float StationarySpeed = 40;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="0",ClampMax="1")) float MinimumPoseHoldSeconds = .15f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) bool bEnableGroundIK = true;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FName> FootBones;
    /** Limb end is HorseLink/Hand, while Foot/Finger0 is the separate sole contact marker. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FName> IKEndBones;
    UPROPERTY(EditAnywhere,BlueprintReadOnly) FName BodyBone;
    /** Optional neck branch used to layer head-up vigilance over moving legs. */
    UPROPERTY(EditAnywhere,BlueprintReadOnly) FName AlertHeadBone;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<float> ContactHeights;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="0",ClampMax="40")) float MaxFootCorrectionCm = 12;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="0",ClampMax="20")) float FootClearanceCm = .5f;
    bool IsValidProfile() const;
};
