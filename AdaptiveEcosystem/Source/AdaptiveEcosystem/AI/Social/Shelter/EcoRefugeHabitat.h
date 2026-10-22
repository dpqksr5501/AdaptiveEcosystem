#pragma once

#include "AI/Social/Shelter/EcoShelterAnchor.h"
#include "EcoRefugeHabitat.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class UStaticMesh;

/** An authored refuge: visible brush/boulders share the registered refuge footprint.
 * Components are cosmetic; native simulation owns predator exclusion and prey protection.
 * Authored actors load from the map on clients; generated refuges replicate their static layout. */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoRefugeHabitat : public AEcoShelterAnchor
{
    GENERATED_BODY()
public:
    AEcoRefugeHabitat();
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    UFUNCTION(CallInEditor,BlueprintCallable,Category="Ecology|Refuge") void RebuildHabitat();
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Ecology|Refuge") TObjectPtr<UStaticMesh> BrushMesh;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Ecology|Refuge") TObjectPtr<UStaticMesh> BoulderMesh;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Ecology|Refuge",meta=(ClampMin="80",ClampMax="250")) float BrushSpacing=145;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Ecology|Refuge",meta=(ClampMin="60",ClampMax="200")) float BrushHeight=130;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Ecology|Refuge") int32 LayoutSeed=1701;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Ecology|Refuge") TObjectPtr<UHierarchicalInstancedStaticMeshComponent> Brush;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Ecology|Refuge") TObjectPtr<UHierarchicalInstancedStaticMeshComponent> Boulders;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,ReplicatedUsing=OnRep_Ready,Category="Ecology|Refuge") bool bRegistrationReady=false;
protected:
    virtual void BeginPlay() override;
private:
    UPROPERTY(ReplicatedUsing=OnRep_Layout) float LayoutRadius=1200;
    UPROPERTY(ReplicatedUsing=OnRep_Layout) int32 ReplicatedSeed=1701;
    UFUNCTION() void OnRep_Layout();
    UFUNCTION() void OnRep_Ready();
    void TryRegisterGrounded();
    FTimerHandle RegistrationTimer;
    int32 RegistrationAttempts=0;
};
