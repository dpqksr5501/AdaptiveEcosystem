#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/NetSerialization.h"
#include "EcoVegetationField.generated.h"

class UInstancedStaticMeshComponent;
class UBoxComponent;
class UStaticMesh;
class UMaterialInterface;
class UStaticMeshComponent;
class UEcoNaturalHabitatProfile;
class UDecalComponent;
class AEcoVegetationSiteChunk;

/** Authored ground-connected water/soil input. Does not own food or perform simulation. */
UCLASS()
class ADAPTIVEECOSYSTEM_API AEcoVegetationHabitat : public AActor
{
    GENERATED_BODY()
public:
    AEcoVegetationHabitat();
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    UFUNCTION(BlueprintPure,Category="Habitat") bool IsValidHabitat() const;
    bool ContainsGround(const FVector& Point) const;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UBoxComponent> Bounds;
    /** Local presentation of the authored shallow freshwater source. No food or navigation ownership. */
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> WaterSurface;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UDecalComponent> SoilTransition;
    UPROPERTY(EditAnywhere, Category="Habitat|Water") TSoftObjectPtr<UStaticMesh> WaterMesh;
    UPROPERTY(EditAnywhere, Category="Habitat|Water") FVector2D WaterSurfaceSizeCm=FVector2D(800,800);
    UPROPERTY(EditAnywhere, Category="Habitat|Water") TSoftObjectPtr<UMaterialInterface> WaterMaterial;
    UPROPERTY(EditAnywhere, Category="Habitat") FName RegionId;
    UPROPERTY(EditAnywhere, Category="Habitat|Natural") FName HabitatId;
    UPROPERTY(EditAnywhere, Category="Habitat|Natural") int32 Priority=0;
    UPROPERTY(EditAnywhere, Category="Habitat|Natural",meta=(ClampMin="0",ClampMax="3000",Units="cm")) float BlendDistanceCm=400;
    /** Optional local climate/guild variant; e.g. dryland or alpine. */
    UPROPERTY(EditAnywhere, Category="Habitat|Natural") TObjectPtr<UEcoNaturalHabitatProfile> GrowthProfile;
    double BlendWeight(const FVector& Point) const;
    uint32 Fingerprint() const;
    /** 0=grass, 1=riparian, 2=shrub. Other values are rejected. */
    UPROPERTY(EditAnywhere, Category="Habitat", meta=(ClampMin="0",ClampMax="2")) int32 Plant = 0;
    UPROPERTY(EditAnywhere, Category="Habitat", meta=(ClampMin="0",ClampMax="1")) float Drainage = 0.5f;
    UPROPERTY(EditAnywhere, Category="Habitat", meta=(ClampMin="0",ClampMax="1")) float Shade = 0;
    /** Explicitly authored hydraulic connectivity; proximity alone supplies no water. */
    UPROPERTY(EditAnywhere, Category="Habitat") bool bConnectedFreshWater = false;
    UPROPERTY(EditAnywhere, Category="Habitat") float WaterSurfaceZ = 0;
    UPROPERTY(EditAnywhere, Category="Habitat", meta=(ClampMin="0",ClampMax="200")) float MaxSupplyRiseCm = 100;
    /** Opt-in water column for rule-fauna. The bottom is read from world collision. */
    UPROPERTY(EditAnywhere, Category="Habitat|Water") bool bSupportsFaunaSwimming = false;
    /** Disable on local water inputs that share an already rendered water surface. */
    UPROPERTY(EditAnywhere, Category="Habitat|Water") bool bDrawWaterSurface = true;
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(Units="cm/s")) FVector FaunaWaterCurrent = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(ClampMin="0", ClampMax="40")) float FaunaWaterTemperatureC = 20.f;
    /** Underwater visual cover at the bottom of a vegetated water column. */
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(ClampMin="0", ClampMax="1")) float FaunaWaterCoverDensity = 0.f;
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(ClampMin="0", Units="cm")) float FaunaWaterCoverHeightCm = 0.f;
    /** Optional rise above the authored low-water surface. Zero keeps a static source. */
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(ClampMin="0", Units="cm")) float WaterLevelRise = 0.f;
    /** Authored runoff response at full normalized regional rainfall. */
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(ClampMin="0", ClampMax="100", Units="cm"))
    float WaterRainRiseCm = 0.f;
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(ClampMin="1", Units="s")) float WaterRiseSeconds = 30.f;
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(ClampMin="0", Units="s")) float WaterHighSeconds = 20.f;
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(ClampMin="1", Units="s")) float WaterFallSeconds = 45.f;
    UPROPERTY(EditAnywhere, Category="Habitat|Water", meta=(ClampMin="0", Units="s")) float WaterLowSeconds = 40.f;
    double GetWaterLevelZ() const;
    double EvaluateWaterLevelZ(double SimulationSeconds, float Rainfall = 0.f) const;
private:
    void RefreshWaterVisual();
};

/** A sampled cell's visual DTO; never a second resource balance. Stable ID = RegionId + Cell. */
USTRUCT()
struct FEcoVegetationVisualCell
{
    GENERATED_BODY()
    UPROPERTY() int32 Cell = 0;
    UPROPERTY() FVector Position = FVector::ZeroVector;
    UPROPERTY() FVector_NetQuantizeNormal Normal=FVector::UpVector;
    UPROPERTY() uint8 Development=255;
    UPROPERTY() uint8 Food = 0;
    UPROPERTY() uint8 Moisture = 0;
    UPROPERTY() uint8 Stress = 0;
    UPROPERTY() uint8 FreshTint = 128; // neutral when the habitat rules are off
    UPROPERTY() uint8 PooledWater = 0;
    UPROPERTY() uint8 Disturbance = 0;
    UPROPERTY() uint8 Plant = 0;
    UPROPERTY() uint8 WidthCm=0;
    UPROPERTY() uint8 HeightCm=0;
    UPROPERTY() uint8 SiteFood[9]={};
};

USTRUCT()
struct FEcoMovementTraceVisual
{
    GENERATED_BODY()
    UPROPERTY() FVector Position=FVector::ZeroVector;
    UPROPERTY() uint8 Age=0;
    UPROPERTY() bool bWet=false;
};

/** Ground checked on authority, once per bounded refresh; clients never raycast food sites. */
USTRUCT()
struct FEcoVegetationSiteVisual
{
    GENERATED_BODY()
    UPROPERTY() int32 Cell=0;
    UPROPERTY() uint8 Ordinal=0;
    UPROPERTY() FVector_NetQuantize10 Position=FVector::ZeroVector;
    UPROPERTY() FVector_NetQuantizeNormal Normal=FVector::UpVector;
};

/** Server publishes bounded visual samples, clients render them. Native remains the only food writer. */
UCLASS()
class ADAPTIVEECOSYSTEM_API AEcoVegetationField : public AActor
{
    GENERATED_BODY()
public:
    AEcoVegetationField();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    static bool IsRequested();
    UFUNCTION(BlueprintPure, Category="Ecology|Vegetation") FString CaptureDiagnostics(bool bIncludeLearningCells=false) const;
    /** Authority-only ground clearing. The next Native resource step accounts for biomass loss. */
    UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category="Ecology|Vegetation")
    bool QueueGroundDisturbance(FVector WorldPosition, float Severity);
    UPROPERTY(Replicated, VisibleAnywhere, Category="Vegetation") FName RegionId;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> Plants;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> RiparianPlants;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> ShrubPlants;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> Tracks;
    /** Clearly dry, non-edible residue; never a second resource balance. */
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> DryResidue;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> Puddles;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UDecalComponent> BiomeTransition;
    UPROPERTY(ReplicatedUsing=OnRep_Profile) float SurfaceHalfExtentCm=0;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual") TSoftObjectPtr<UStaticMesh> PatchMesh;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual") TSoftObjectPtr<UMaterialInterface> PatchMaterial;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual") TSoftObjectPtr<UMaterialInterface> PuddleMaterial;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual", meta=(ClampMin="10",ClampMax="400",Units="cm")) float PatchWidthCm = 120;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual", meta=(ClampMin="5",ClampMax="100",Units="cm")) float PatchHeightCm = 45;
    UPROPERTY(Transient) TArray<FEcoVegetationVisualCell> Cells;
    /** Nonzero only in life worlds: full bounded cell coverage and ground-aligned tufts. */
    UPROPERTY(ReplicatedUsing=OnRep_Cells) float VisualCellSizeCm=0;
    UPROPERTY(ReplicatedUsing=OnRep_Profile,EditAnywhere,Category="Vegetation|Natural") TObjectPtr<UEcoNaturalHabitatProfile> NaturalProfile;
    UPROPERTY(Transient) TArray<FEcoVegetationSiteVisual> GroundSites;
    UPROPERTY(ReplicatedUsing=OnRep_Cells) TArray<FEcoMovementTraceVisual> MovementMarks;
    int32 ContextIndex = INDEX_NONE;
    static bool SampleNaturalGround(UWorld& World,const FVector& Hint,const UEcoNaturalHabitatProfile& Profile,FHitResult& Hit,const AActor* Ignore=nullptr);
    void RegisterVisualChunk(AEcoVegetationSiteChunk* Chunk);
    void RemoveVisualChunk(AEcoVegetationSiteChunk* Chunk);
private:
    void PublishVisualChunks(int32 Stride,int32 CellCount);
    TArray<TWeakObjectPtr<AEcoVegetationSiteChunk>> VisualChunks;
    bool bChunkVisualDirty=false;
    UFUNCTION() void OnRep_Cells();
    UFUNCTION() void OnRep_Profile();
    bool ProbeGround(const FVector& Hint,FHitResult& Hit) const;
    void GatherGround();
    void ExpandHabitat();
    int32 NextGroundCell = 0;
    double NextPublish = 0;
    double NextGroundRefresh = 0;
    TMap<int32, FVector> Ground;
    TMap<int32, FVector> GroundNormals;
    TMap<int32,TArray<FEcoVegetationSiteVisual>> SiteCache;
    TMap<int32,FVector2f> SiteDimensions;
    uint32 StableLayoutSeed() const;
};

/** Bounded spatial presentation transport. No logical resource or simulation ownership. */
UCLASS(NotBlueprintable,Transient)
class ADAPTIVEECOSYSTEM_API AEcoVegetationSiteChunk : public AActor
{
    GENERATED_BODY()
public:
    AEcoVegetationSiteChunk();
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    UPROPERTY(ReplicatedUsing=OnRep_Visual) TObjectPtr<AEcoVegetationField> Field;
    UPROPERTY(ReplicatedUsing=OnRep_Visual) TArray<FEcoVegetationVisualCell> Cells;
    UPROPERTY(ReplicatedUsing=OnRep_Visual) TArray<FEcoVegetationSiteVisual> Sites;
private:
    UFUNCTION() void OnRep_Visual();
};
