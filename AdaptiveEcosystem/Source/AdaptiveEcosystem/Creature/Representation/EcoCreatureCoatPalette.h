#pragma once

#include "Engine/DataAsset.h"
#include "EcoCreatureCoatPalette.generated.h"

class UMaterialInterface;

USTRUCT(BlueprintType)
struct FEcoCoatSurface
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite) float BaseLuminance = .35f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bSubtle = false;

    FLinearColor Tint(float Tone) const
    {
        const float Value = 2.f * FMath::Clamp(Tone, 0.f, 1.f) - 1.f;
        const float Light = 1.f + (bSubtle ? .08f : .32f) * Value;
        const float Warm = bSubtle ? 0.f : .09f * Value;
        return FLinearColor(Light + Warm, Light, Light - Warm, 1.f);
    }

    float Luminance(float Tone) const { return FMath::Clamp(BaseLuminance * Tint(Tone).GetLuminance(), 0.f, 1.f); }
};

/** Authored surface appearance and local background estimates for an owned ecosystem level. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoCreatureCoatPalette : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TMap<FName, FEcoCoatSurface> Species;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TMap<FName, float> RegionLuminance;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TMap<TObjectPtr<UMaterialInterface>, TObjectPtr<UMaterialInterface>> Materials;

    static uint8 PackTone(double Coat) { return uint8(FMath::RoundToInt(FMath::Clamp((Coat - .85) / .30, 0., 1.) * 255.)); }
    static double DetectionRangeScale(float Surface, float Background)
    {
        return .78 + .22 * FMath::Clamp(FMath::Abs(Surface - Background) / .5f, 0.f, 1.f);
    }
};
