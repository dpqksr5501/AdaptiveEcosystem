#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "EcoFootstepAudioSet.generated.h"

class USoundBase;
class USoundAttenuation;
class USoundConcurrency;
class UPhysicalMaterial;

/** Shared authored playback/range configuration. Owns no AI state or network transport. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoFootstepAudioSet : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TArray<TObjectPtr<USoundBase>> Grass;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TArray<TObjectPtr<USoundBase>> Dry;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TArray<FName> GrassRegions = {TEXT("Forest"), TEXT("Forest_A"), TEXT("Forest_B")};
    /** Explicit authored materials take precedence. Unknown/streaming surfaces use RegionId. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Surface") TArray<TObjectPtr<UPhysicalMaterial>> GrassMaterials;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Surface") TArray<TObjectPtr<UPhysicalMaterial>> DryMaterials;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TObjectPtr<USoundAttenuation> Attenuation;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TObjectPtr<USoundConcurrency> Concurrency;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps", meta=(ClampMin="0",ClampMax="1")) float Volume = 0.7f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps", meta=(ClampMin="1",Units="cm")) float WalkStride = 140;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps", meta=(ClampMin="1",Units="cm")) float RunStride = 220;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps", meta=(ClampMin="0",Units="cm/s")) float MinimumSpeed = 40;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="AI Noise", meta=(ClampMin="1",ClampMax="10000",Units="cm")) float NoiseRange = 2000;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="AI Noise", meta=(ClampMin="0",ClampMax="1")) float PredatorThreat = 0.8f;
    bool IsGrass(FName RegionId) const { return GrassRegions.Contains(RegionId); }
    bool IsGrassSurface(const UPhysicalMaterial* Material, FName RegionId) const
    {
        if (Material && GrassMaterials.Contains(Material)) return true;
        if (Material && DryMaterials.Contains(Material)) return false;
        return IsGrass(RegionId);
    }
    float GetStride(float Speed) const { return FMath::Lerp(WalkStride, RunStride, FMath::Clamp((Speed - 250) / 650, 0.f, 1.f)); }
    bool IsValidConfiguration() const;
    /** Local editor setup only. Both settings remain ordinary editable Unreal assets. */
    UFUNCTION(BlueprintCallable, Category="Footsteps|Editor")
    bool ConfigurePlayback(USoundAttenuation* SoundAttenuation, USoundConcurrency* SoundConcurrency);
};
