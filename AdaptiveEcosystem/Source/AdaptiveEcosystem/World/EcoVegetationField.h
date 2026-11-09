#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InstanceDataTypes.h"
#include "Net/Serialization/FastArraySerializer.h"
#include "Core/EcoFoodPatchLayout.h"
#include "EcoVegetationField.generated.h"

class UInstancedStaticMeshComponent;
class UBoxComponent;
class UStaticMesh;
class UMaterialInterface;
class UStaticMeshComponent;

/** Authored ground-connected water/soil input. Does not own food or perform simulation. */
UCLASS()
class ADAPTIVEECOSYSTEM_API AEcoVegetationHabitat : public AActor
{
    GENERATED_BODY()
public:
    AEcoVegetationHabitat();
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    UFUNCTION(BlueprintPure,Category="Habitat") bool IsValidHabitat() const;
    bool ContainsGround(const FVector& Point) const;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UBoxComponent> Bounds;
    /** Local presentation of the authored shallow freshwater source. No food or navigation ownership. */
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> WaterSurface;
    UPROPERTY(EditAnywhere, Category="Habitat|Water") FVector2D WaterSurfaceSizeCm=FVector2D(800,800);
    UPROPERTY(EditAnywhere, Category="Habitat|Water") TSoftObjectPtr<UMaterialInterface> WaterMaterial;
    UPROPERTY(EditAnywhere, Category="Habitat") FName RegionId;
    /** 0=grass, 1=riparian, 2=shrub. Other values are rejected. */
    UPROPERTY(EditAnywhere, Category="Habitat", meta=(ClampMin="0",ClampMax="2")) int32 Plant = 0;
    UPROPERTY(EditAnywhere, Category="Habitat", meta=(ClampMin="0",ClampMax="1")) float Drainage = 0.5f;
    UPROPERTY(EditAnywhere, Category="Habitat", meta=(ClampMin="0",ClampMax="1")) float Shade = 0;
    /** Explicitly authored hydraulic connectivity; proximity alone supplies no water. */
    UPROPERTY(EditAnywhere, Category="Habitat") bool bConnectedFreshWater = false;
    UPROPERTY(EditAnywhere, Category="Habitat") float WaterSurfaceZ = 0;
    UPROPERTY(EditAnywhere, Category="Habitat", meta=(ClampMin="0",ClampMax="200")) float MaxSupplyRiseCm = 100;
    bool HasWaterSupply() const;
#if !UE_BUILD_SHIPPING
    TOptional<bool> DebugWaterConnection;
#endif
private:
    void RefreshWaterVisual();
};

/** Visual copy of a committed food cell. The region Field owns its grid lifetime. */
USTRUCT()
struct FEcoVegetationVisualCell : public FFastArraySerializerItem
{
    GENERATED_BODY()
    /** Visual encoding for native patch amounts in [0,1]. Positive sub-quantum values retain a nonzero code. */
    static uint16 EncodeAmount(double Amount);
    bool HasRenderableFood() const { return Food > 0 && Capacity > 0; }
    UPROPERTY() int32 Cell = 0;
    UPROPERTY() FVector_NetQuantize10 Position;
    UPROPERTY() uint16 Food = 0;
    UPROPERTY() uint16 Capacity = 0;
    UPROPERTY() uint8 Moisture = 0;
    UPROPERTY() uint8 Stress = 0;
    UPROPERTY() uint8 Plant = 0;
};

USTRUCT()
struct FEcoVegetationVisualGrid : public FFastArraySerializer
{
    GENERATED_BODY()
    UPROPERTY() TArray<FEcoVegetationVisualCell> Cells;

    bool NetDeltaSerialize(FNetDeltaSerializeInfo& Params);
};

template<> struct TStructOpsTypeTraits<FEcoVegetationVisualGrid> : TStructOpsTypeTraitsBase2<FEcoVegetationVisualGrid>
{
    enum { WithNetDeltaSerializer = true };
};

/** One complete cell of authority ground. No food is reconstructed from this S1 DTO. */
USTRUCT()
struct FEcoFoodPatchGroundCell : public FFastArraySerializerItem
{
    GENERATED_BODY()
    UPROPERTY() int32 Cell = 0;
    UPROPERTY() uint32 Epoch = 0;
    UPROPERTY() uint32 SettingsHash = 0;
    UPROPERTY() uint32 Revision = 0;
    UPROPERTY() uint32 ValidMask = 0;
    UPROPERTY() TArray<FVector_NetQuantize10> RelativePositions;
    UPROPERTY() TArray<FVector_NetQuantizeNormal> Normals;
    // XY comes from LayoutVersion1, Z uses 1cm wire codes. Normals remain authority-only in S1.
    bool bHeightOnlyFromWire = false;
    bool NetSerialize(FArchive& Ar, UPackageMap* Map, bool& bOutSuccess);
    bool Matches(const FEcoFoodPatchLayout& Layout) const;
    /** Hot loop variant; caller must validate the descriptor once before entering the loop. */
    bool MatchesValidatedLayout(const FEcoFoodPatchLayout& Layout) const;
};
template<> struct TStructOpsTypeTraits<FEcoFoodPatchGroundCell> : TStructOpsTypeTraitsBase2<FEcoFoodPatchGroundCell>
{ enum { WithNetSerializer = true }; };

USTRUCT()
struct FEcoFoodPatchGroundGrid : public FFastArraySerializer
{
    GENERATED_BODY()
    UPROPERTY() TArray<FEcoFoodPatchGroundCell> Cells;
    bool NetDeltaSerialize(FNetDeltaSerializeInfo& Params);
};
template<> struct TStructOpsTypeTraits<FEcoFoodPatchGroundGrid> : TStructOpsTypeTraitsBase2<FEcoFoodPatchGroundGrid>
{ enum { WithNetDeltaSerializer = true }; };

USTRUCT()
struct FEcoMovementTraceVisual
{
    GENERATED_BODY()
    UPROPERTY() FVector Position=FVector::ZeroVector;
    UPROPERTY() uint8 Age=0;
};

/** Server publishes committed cells. Existing ISM components render nearby vegetation. */
UCLASS()
class ADAPTIVEECOSYSTEM_API AEcoVegetationField : public AActor
{
    GENERATED_BODY()
public:
    AEcoVegetationField();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    virtual bool IsNetRelevantFor(const AActor* RealViewer, const AActor* ViewTarget, const FVector& SrcLocation) const override;
    static bool IsRequested();
    static bool IsVisualRequested();
    void ConfigureGrid(float InCellWidthCm, float InGridSizeCm, int32 InSeed);
    /** Explicit static-terrain revision. Moving terrain is not supported. GT authority only. */
    bool InvalidatePatchGround();
#if !UE_BUILD_SHIPPING
    FString DescribeGrassCell(const FVector& Position) const;
#endif
    UFUNCTION(BlueprintPure, Category="Ecology|Vegetation") FString CaptureDiagnostics(bool bIncludeLearningCells=false) const;
    UPROPERTY(Replicated, VisibleAnywhere, Category="Vegetation") FName RegionId;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> Plants;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> RiparianPlants;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> ShrubPlants;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UInstancedStaticMeshComponent> Tracks;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual") TSoftObjectPtr<UStaticMesh> PatchMesh;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual") TSoftObjectPtr<UMaterialInterface> PatchMaterial;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual", meta=(ClampMin="10",ClampMax="400",Units="cm")) float PatchWidthCm = 120;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual", meta=(ClampMin="5",ClampMax="100",Units="cm")) float PatchHeightCm = 45;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual") TSoftObjectPtr<UStaticMesh> RiparianMesh;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual") TSoftObjectPtr<UStaticMesh> ShrubMesh;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual", meta=(ClampMin="1", ClampMax="25"))
    int32 CandidatesPerCell = 9;
    /** S1 authority anchors only; patch consumption is implemented separately in S2/S3. Set before Play. */
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Patches") bool bEnablePatchLayout = false;
    UPROPERTY(Replicated, VisibleAnywhere, Category="Vegetation|Patches") FEcoFoodPatchLayout PatchLayout;
    UPROPERTY(Replicated) FEcoFoodPatchGroundGrid PatchGround;
    /** -1 waits for the server descriptor decision, 0 legacy, 1 S1 authority anchors. */
    UPROPERTY(Replicated) int8 PatchLayoutMode = -1;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual", meta=(ClampMin="2", ClampMax="1000"))
    int32 CandidateTracesPerUpdate = 96;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual", meta=(ClampMin="1000", Units="cm"))
    float DetailRadiusCm = 15000;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual", meta=(ClampMin="0.01"))
    float FoodAtFullDensity = 1;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual") TEnumAsByte<ECollisionChannel> GroundTraceChannel = ECC_WorldStatic;
    UPROPERTY(EditDefaultsOnly, Category="Vegetation|Visual", meta=(ClampMin="0", ClampMax="1"))
    float MinimumGroundNormalZ = .65f;
    UPROPERTY(Replicated) FEcoVegetationVisualGrid VisualGrid;
    UPROPERTY(ReplicatedUsing=OnRep_MovementMarks) TArray<FEcoMovementTraceVisual> MovementMarks;
    int32 ContextIndex = INDEX_NONE;
private:
    UFUNCTION() void OnRep_MovementMarks();
    void RefreshVisuals();
    void RefreshPlants(const FVector& Eye, double Now);
    TArray<int64> GetDueGroundCandidates(double Now, int32 Budget) const;
#if WITH_DEV_AUTOMATION_TESTS
    friend class FEcoGrassGroundRefreshFairness;
    friend class FEcoGrassVisualLifecycle;
    friend class FEcoFoodPatchAuthorityAnchors;
#endif
    void PublishCells();
    void GatherGround();
    void GatherPatchGround();
    bool EnsurePatchLayout();
    void PublishPatchGroundCell(int32 Cell);
    UPROPERTY(Replicated) float CellWidthCm = 0;
    UPROPERTY(Replicated) float GridSizeCm = 0;
    UPROPERTY(Replicated) int32 LayoutSeed = 0;
    struct FRenderedPlant
    {
        FPrimitiveInstanceId Instance;
        FVector Anchor = FVector::ZeroVector;
        FVector GroundPosition = FVector::ZeroVector;
        double NextGroundCheck = 0;
        uint16 Food = 0;
        uint16 Capacity = 0;
        float Detail = 0;
        uint8 Moisture = 0;
        uint8 Stress = 0;
        uint8 Plant = 0;
        bool bGroundReady = false;
    };
    TMap<int64, FRenderedPlant> RenderedPlants;
    double NextVisualRefresh = 0;
    int32 NextGroundCell = 0;
    double NextPublish = 0;
    // Local diagnostic provenance only; not another resource state or replicated clock.
    int64 PublishedNativeStep = -1;
    double NextGroundRefresh = 0;
    TMap<int32, FVector> Ground;
    TMap<int32, TArray<FEcoFoodPatchSample>> LocalLayoutSamples;
    uint32 CachedRegionSeed = 0;
    float CachedCellWidth = 0;
    int32 CachedPatchCount = 0;
    uint32 CachedLayoutEpoch = 0;
    TArray<int32> PublishedPatchCells;
    int32 NextPatchGround = 0;
    double NextPatchGroundSweep = 0;
};
