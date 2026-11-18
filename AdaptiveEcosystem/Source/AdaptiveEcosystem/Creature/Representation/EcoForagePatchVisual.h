#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "EcoForagePatchVisual.generated.h"

class UHierarchicalInstancedStaticMeshComponent;

/** Passive level presentation of an authored, authority-owned forage patch. */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoForagePatchVisual : public AActor
{
    GENERATED_BODY()

public:
    AEcoForagePatchVisual();
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category="Forage") FName PatchId;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Forage") TObjectPtr<UHierarchicalInstancedStaticMeshComponent> Plants;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Forage") TObjectPtr<UHierarchicalInstancedStaticMeshComponent> WoodyStems;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Forage") TArray<FTransform> FullPlantTransforms;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Forage", meta=(ClampMin="0.05", ClampMax="1")) float ResidualHeightFraction = .2f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Forage") bool bKeepWoodyStems = false;
    UFUNCTION(BlueprintPure, Category="Forage") float GetForageFraction() const { return ForageAmount / 255.f; }
    UFUNCTION(CallInEditor, BlueprintCallable, Category="Forage") void RebuildForagePreview();

    void PublishStockFraction(float Fraction);

protected:
    virtual void BeginPlay() override;
    UFUNCTION(BlueprintImplementableEvent, Category="Forage") void OnForageAppearanceChanged(float Fraction);

private:
    UPROPERTY(ReplicatedUsing=OnRep_ForageAmount) uint8 ForageAmount = 255;
    UFUNCTION() void OnRep_ForageAmount();
    void ApplyForageAppearance();
};
