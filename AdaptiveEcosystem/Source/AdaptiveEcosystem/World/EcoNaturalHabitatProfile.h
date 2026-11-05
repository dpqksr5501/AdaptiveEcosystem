#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "AI/Policy/EcoVegetationV3.h"
#include "EcoNaturalHabitatProfile.generated.h"

class UStaticMesh;
class UMaterialInterface;
class UFXSystemAsset;

/** Functional guild; numbers are tunable game defaults, not measured species constants. */
USTRUCT(BlueprintType)
struct FEcoPlantGuild
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere,Category="Growth") float MoistureMin=.30f;
    UPROPERTY(EditAnywhere,Category="Growth") float MoistureMax=.75f;
    UPROPERTY(EditAnywhere,Category="Growth") float TemperatureMin=-5;
    UPROPERTY(EditAnywhere,Category="Growth") float TemperatureOptimum=18;
    UPROPERTY(EditAnywhere,Category="Growth") float TemperatureMax=45;
    UPROPERTY(EditAnywhere,Category="Growth") float ShadeTolerance=.5f;
    UPROPERTY(EditAnywhere,Category="Growth",meta=(ClampMin="10",ClampMax="7200")) float MaturationSeconds=60;
    UPROPERTY(EditAnywhere,Category="Site",meta=(ClampMin="0",ClampMax="60")) float MaxSlopeDegrees=40;
    UPROPERTY(EditAnywhere,Category="Visual",meta=(ClampMin="10",ClampMax="200")) float WidthCm=105;
    UPROPERTY(EditAnywhere,Category="Visual",meta=(ClampMin="5",ClampMax="150")) float HeightCm=35;
    UPROPERTY(EditAnywhere,Category="Visual",meta=(ClampMin="0.1",ClampMax="1")) float Coverage=1;
    UPROPERTY(EditAnywhere,Category="Visual") TSoftObjectPtr<UStaticMesh> Mesh;
    bool IsValid() const;
    void Apply(EcoVegetationV3::FHabitat& Habitat) const;
};

/** Assign to a level coordinator; shared by test and production levels, with no map coordinates. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoNaturalHabitatProfile : public UDataAsset
{
    GENERATED_BODY()
public:
    UEcoNaturalHabitatProfile();
    UPROPERTY(EditAnywhere,Category="Identity") FName ProfileId=TEXT("TemperateMosaic");
    /** Exactly grass / riparian / shrub. New guilds need a backend/schema change. */
    UPROPERTY(EditAnywhere,Category="Growth") TArray<FEcoPlantGuild> Guilds;
    UPROPERTY(EditAnywhere,Category="Layout") int32 LayoutSeed=1907;
    /** Accelerated simulation seconds, not real deer years. Copied to each individual's saved state. */
    UPROPERTY(EditAnywhere,Category="Population",meta=(ClampMin="180",ClampMax="7200")) float MaturitySeconds=360;
    UPROPERTY(EditAnywhere,Category="Population",meta=(ClampMin="0",ClampMax="0.6")) float InitialJuvenileFraction=.25f;
    UPROPERTY(EditAnywhere,Category="Population",meta=(ClampMin="0.25",ClampMax="0.75")) float FemaleFraction=.60f;
    UPROPERTY(EditAnywhere,Category="Population",meta=(ClampMin="180",ClampMax="86400")) float MaxFounderAgeSeconds=1800;
    UPROPERTY(EditAnywhere,Category="Population",meta=(ClampMin="0",ClampMax="0.1")) float FounderBodyVariation=.08f;
    UPROPERTY(EditAnywhere,Category="Layout",meta=(ClampMin="500",ClampMax="10000",Units="cm")) float ClusterScaleCm=1800;
    /** Search relative to the region's authored ground datum, never the whole vertical world. */
    UPROPERTY(EditAnywhere,Category="Ground",meta=(ClampMin="100",ClampMax="5000",Units="cm")) float ProbeAboveCm=1200;
    UPROPERTY(EditAnywhere,Category="Ground",meta=(ClampMin="100",ClampMax="10000",Units="cm")) float ProbeBelowCm=3000;
    /** Landscape or explicit Eco.VegetationGround tag. Reject roofs/decorative boulders by default. */
    UPROPERTY(EditAnywhere,Category="Ground") bool bRequireGroundTag=true;
    /** Current Native terrestrial backend limits; not swimming/flying support. */
    UPROPERTY(EditAnywhere,Category="Ground|Movement") float WalkableSlopeDegrees=40;
    UPROPERTY(EditAnywhere,Category="Ground|Movement") float MaxStepUpCm=35;
    UPROPERTY(EditAnywhere,Category="Ground|Movement") float MaxStepDownCm=60;
    UPROPERTY(EditAnywhere,Category="Ground|Movement") float MaxWadingDepthCm=40;
    /** Hiding cover reduces detection; does not prevent entry or capture. */
    UPROPERTY(EditAnywhere,Category="Refuge") bool bWildRefuges=true;
    UPROPERTY(EditAnywhere,Category="Surface") TSoftObjectPtr<UMaterialInterface> GroundTransitionMaterial;
    UPROPERTY(EditAnywhere,Category="Surface") FLinearColor GroundTint=FLinearColor(.19f,.24f,.09f);
    UPROPERTY(EditAnywhere,Category="Surface",meta=(ClampMin="0",ClampMax="1")) float GroundTintStrength=.35f;
    UPROPERTY(EditAnywhere,Category="Weather|Visual") TSoftObjectPtr<UFXSystemAsset> RainVisual;
    UPROPERTY(EditAnywhere,Category="Weather|Visual") TSoftObjectPtr<UFXSystemAsset> SnowVisual;
    /** Opt-in lighting owner. Disable when the production sky manager already owns the clock view. */
    UPROPERTY(EditAnywhere,Category="Lighting") bool bDriveDayNightLighting=false;
    UPROPERTY(EditAnywhere,Category="Lighting") FName SunTag=TEXT("Eco.Sun");
    UPROPERTY(EditAnywhere,Category="Lighting") FName MoonTag=TEXT("Eco.Moon");
    UPROPERTY(EditAnywhere,Category="Lighting") FName ExposureTag=TEXT("Eco.Exposure");
    UPROPERTY(EditAnywhere,Category="Lighting",meta=(ClampMin="0",ClampMax="0.1")) float MoonSunFraction=.015f;
    UPROPERTY(EditAnywhere,Category="Lighting",meta=(ClampMin="-4",ClampMax="0")) float NightExposureBias=-.9f;
    bool IsValidProfile() const;
    uint32 Fingerprint() const;
};
