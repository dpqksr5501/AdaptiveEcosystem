#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AI/Behavior/EcoSpeciesAIProfile.h"
#include "EcoSpeciesAIActors.generated.h"
class USmartObjectComponent;

/** Authored interaction location; quantities remain in the Ecology resource ledger. */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoSpeciesAIActivitySite : public AActor
{
    GENERATED_BODY()
public:
    AEcoSpeciesAIActivitySite();
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<USmartObjectComponent> SmartObject;
    UPROPERTY(EditAnywhere,Category="Activity") FName RegionId=TEXT("Forest_A");
    UPROPERTY(EditAnywhere,Category="Activity") EEcoActivitySlotKind Kind=EEcoActivitySlotKind::Graze;
    UPROPERTY(EditAnywhere,Category="Activity") bool bForPredator=false;
    virtual void BeginPlay() override;
    virtual void EndPlay(EEndPlayReason::Type Reason) override;
};

/** Explicit test source, not a logical animal. Captures never enter production prey/death ledgers. */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoSpeciesAIFixture : public AActor
{
    GENERATED_BODY()
public:
    AEcoSpeciesAIFixture();
    UPROPERTY(EditAnywhere,Category="Fixture") bool bPrey=true;
    UPROPERTY(EditAnywhere,Category="Fixture") bool bVisible=true;
    UPROPERTY(EditAnywhere,Category="Fixture") bool bMakesNoise=false;
    UPROPERTY(EditAnywhere,Category="Fixture") float MotionRadius=600.f;
    UPROPERTY(EditAnywhere,Category="Fixture") float PeriodSeconds=15.f;
    UPROPERTY(EditAnywhere,Category="Fixture") float RespawnSeconds=5.f;
    UPROPERTY(EditAnywhere,Category="Fixture") float NutritionUnits=25.f;
    int64 FixtureId=0;
    bool IsAvailable(double Now) const { return Now>=CapturedUntil; }
    bool TryCapture(double Now);
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    virtual void EndPlay(EEndPlayReason::Type Reason) override;
private:
    FVector Origin=FVector::ZeroVector;
    double StartTime=0, CapturedUntil=0;
};
