#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
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
    UPROPERTY() uint8 Food = 0;
    UPROPERTY() uint8 Moisture = 0;
    UPROPERTY() uint8 Stress = 0;
    UPROPERTY() uint8 Plant = 0;
};

USTRUCT()
struct FEcoMovementTraceVisual
{
    GENERATED_BODY()
    UPROPERTY() FVector Position=FVector::ZeroVector;
    UPROPERTY() uint8 Age=0;
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
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    static bool IsRequested();
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
    UPROPERTY(ReplicatedUsing=OnRep_Cells) TArray<FEcoVegetationVisualCell> Cells;
    UPROPERTY(ReplicatedUsing=OnRep_Cells) TArray<FEcoMovementTraceVisual> MovementMarks;
    int32 ContextIndex = INDEX_NONE;
private:
    UFUNCTION() void OnRep_Cells();
    void GatherGround();
    int32 NextGroundCell = 0;
    double NextPublish = 0;
    double NextGroundRefresh = 0;
    TMap<int32, FVector> Ground;
};
