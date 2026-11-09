#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "EcoFootstepAudioSet.generated.h"

class USoundBase;
class USoundAttenuation;
class USoundConcurrency;
class UPhysicalMaterial;
class AActor;
UENUM(BlueprintType)
enum class EEcoFootstepSurface : uint8 { Grass, Dry, Snow, Water, Wet, Stone, Wood };

USTRUCT(BlueprintType)
struct FEcoFootstepProfile
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, Category="Gait") float WalkSpeed = 150.f;
    UPROPERTY(EditAnywhere, Category="Gait") float RunSpeed = 400.f;
    UPROPERTY(EditAnywhere, Category="Gait") float WalkSpacing = 55.f;
    UPROPERTY(EditAnywhere, Category="Gait") float RunSpacing = 85.f;
    UPROPERTY(EditAnywhere, Category="Audio") float Volume = .6f;
    UPROPERTY(EditAnywhere, Category="Audio") float PlaybackRange = 1800.f;
    UPROPERTY(EditAnywhere, Category="Audio") float Pitch = 1.f;
    UPROPERTY(EditAnywhere, Category="Audio") bool bHoof = false;
    UPROPERTY(EditAnywhere, Category="Noise") float NoiseRange = 900.f;
    UPROPERTY(EditAnywhere, Category="Noise") float Threat = 0.f;
    UPROPERTY(EditAnywhere, Category="Hearing") float HearingRange = 1500.f;
    UPROPERTY(EditAnywhere, Category="Hearing") float OccludedHearing = .3f;
    UPROPERTY(EditAnywhere, Category="Hearing") float HearingThreshold = .12f;

    bool IsValid() const;
};

USTRUCT(BlueprintType)
struct FEcoFootstepSurfaceAudio
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, Category="Surface") TArray<TObjectPtr<UPhysicalMaterial>> Materials;
    UPROPERTY(EditAnywhere, Category="Surface") TArray<TObjectPtr<USoundBase>> Animal;
    UPROPERTY(EditAnywhere, Category="Surface") TArray<TObjectPtr<USoundBase>> Hoof;
    UPROPERTY(EditAnywhere, Category="Surface") TArray<TObjectPtr<USoundBase>> PlayerWalk;
    UPROPERTY(EditAnywhere, Category="Surface") TArray<TObjectPtr<USoundBase>> PlayerRun;
    UPROPERTY(EditAnywhere, Category="Surface") float NoiseMultiplier = 1.f;
    UPROPERTY(EditAnywhere, Category="Surface") float VolumeMultiplier = 1.f;
};

struct FEcoFootstepContact
{
    FVector Position = FVector::ZeroVector;
    UPhysicalMaterial* Material = nullptr;
    EEcoFootstepSurface Surface = EEcoFootstepSurface::Dry;
};

struct FEcoFootstepLevels
{
    float Spacing;
    float Volume;
    float PlaybackRange;
    float Pitch;
    float NoiseRange;
    float Loudness;
};

namespace EcoFootsteps
{
    inline const FName Player(TEXT("Player"));
    bool IsGroundActivity(uint8 Activity);
    float HearingStrength(const FEcoFootstepProfile& Listener, float Distance, float Range, float Loudness,
        float WeatherMultiplier, bool bOccluded);
}

/** Shared authored playback/range configuration. Owns no AI state or network transport. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoFootstepAudioSet : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TArray<TObjectPtr<USoundBase>> Grass;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TArray<TObjectPtr<USoundBase>> Dry;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TArray<TObjectPtr<USoundBase>> Snow;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TArray<TObjectPtr<USoundBase>> Water;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TArray<TObjectPtr<USoundBase>> Wet;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TArray<FName> GrassRegions = {TEXT("Forest"), TEXT("Forest_A"), TEXT("Forest_B")};
    /** Explicit authored materials take precedence. Unknown/streaming surfaces use RegionId. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Surface") TArray<TObjectPtr<UPhysicalMaterial>> GrassMaterials;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Surface") TArray<TObjectPtr<UPhysicalMaterial>> DryMaterials;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Surface") TArray<TObjectPtr<UPhysicalMaterial>> SnowMaterials;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Surface") TArray<TObjectPtr<UPhysicalMaterial>> WaterMaterials;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Surface") TArray<TObjectPtr<UPhysicalMaterial>> WetMaterials;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TObjectPtr<USoundAttenuation> Attenuation;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TObjectPtr<USoundConcurrency> Concurrency;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps", meta=(ClampMin="0",ClampMax="1")) float Volume = 0.7f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps", meta=(ClampMin="1",Units="cm")) float WalkStride = 140;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps", meta=(ClampMin="1",Units="cm")) float RunStride = 220;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps", meta=(ClampMin="0",Units="cm/s")) float MinimumSpeed = 40;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="AI Noise", meta=(ClampMin="1",ClampMax="10000",Units="cm")) float NoiseRange = 2000;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="AI Noise", meta=(ClampMin="0",ClampMax="1")) float PredatorThreat = 0.8f;
    /** Optional opt-in by species. Existing sets retain legacy cadence, levels and cues. */
    UPROPERTY(EditAnywhere, Category="Footsteps|Profiles") TMap<FName, FEcoFootstepProfile> Profiles;
    UPROPERTY(EditAnywhere, Category="Footsteps|Profiles") TMap<EEcoFootstepSurface, FEcoFootstepSurfaceAudio> Surfaces;
    UPROPERTY(EditAnywhere, Category="Footsteps|Profiles") float RainWetThreshold = .65f;
    const FEcoFootstepProfile* FindProfile(FName Species) const { return Profiles.Find(Species); }
    FEcoFootstepLevels Evaluate(const FEcoFootstepProfile& Profile, EEcoFootstepSurface Surface,
        float Speed, float BodyScale, float GaitGain = 1.f) const;
    bool ResolveContact(UWorld& World, const FVector& Source, FName RegionId, const AActor* Ignore,
        FEcoFootstepContact& Out) const;
    const TArray<TObjectPtr<USoundBase>>& SelectSounds(EEcoFootstepSurface S, bool bPlayer, bool bRun, bool bHoof) const;
    EEcoFootstepSurface GetSurface(const UPhysicalMaterial* M,FName RegionId) const
    {
        if (M) for (const auto& Pair : Surfaces) if (Pair.Value.Materials.Contains(M)) return Pair.Key;
        if(M&&SnowMaterials.Contains(M))return EEcoFootstepSurface::Snow;
        if(M&&WaterMaterials.Contains(M))return EEcoFootstepSurface::Water;
        if(M&&WetMaterials.Contains(M))return EEcoFootstepSurface::Wet;
        return IsGrassSurface(M,RegionId)?EEcoFootstepSurface::Grass:EEcoFootstepSurface::Dry;
    }
    const TArray<TObjectPtr<USoundBase>>& GetSounds(EEcoFootstepSurface S) const
    { return S==EEcoFootstepSurface::Snow?Snow:S==EEcoFootstepSurface::Water?Water:S==EEcoFootstepSurface::Wet?Wet:S==EEcoFootstepSurface::Grass?Grass:Dry; }
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
