#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/GameModeBase.h"
#include "AI/Policy/EcoWorldProviders.h"
#include "Core/EcoMigrationTypes.h"
#include "Ecology/EcoSpawnSchedule.h"
#include "Mass/EntityHandle.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "EcoCreatureIntegrationSpawner.generated.h"

class UMassEntityConfigAsset;
class AEcologyRegion;

USTRUCT(BlueprintType)
struct FEcoCreatureSpawnGroup
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere) FName RegionId = TEXT("Forest_A");
	UPROPERTY(EditAnywhere, meta=(ClampMin="0")) int32 Herbivores = 8;
	UPROPERTY(EditAnywhere, meta=(ClampMin="0")) int32 Wolves = 1;
	UPROPERTY(EditAnywhere) FEcoSpawnScheduleSettings Schedule;
};

/** Separate opt-in level coordinator. Existing M3 bootstrap/guards remain intact. */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoCreatureIntegrationSpawner : public AActor,
	public IEcoWorldFoodProvider, public IEcoWorldCoverProvider
{
	GENERATED_BODY()
public:
	AEcoCreatureIntegrationSpawner();
	virtual void PostInitializeComponents() override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	UPROPERTY(EditAnywhere, Category="Creature|Config") TObjectPtr<UMassEntityConfigAsset> HerbivoreConfig;
	UPROPERTY(EditAnywhere, Category="Creature|Config") TObjectPtr<UMassEntityConfigAsset> WolfConfig;
	UPROPERTY(EditAnywhere, Category="Creature|Visual") TSubclassOf<AEcoCreatureRepresentationActor> HerbivoreActorClass;
	UPROPERTY(EditAnywhere, Category="Creature|Visual") TSubclassOf<AEcoCreatureRepresentationActor> WolfActorClass;
	UPROPERTY(EditAnywhere, Category="Creature|Population") TArray<FEcoCreatureSpawnGroup> Groups;
	UPROPERTY(EditAnywhere, Category="Creature|Population", meta=(ClampMin="1",ClampMax="512")) int32 GlobalPopulationLimit = 128;
	UPROPERTY(EditAnywhere, Category="Creature|Time", meta=(ClampMin="1")) double DaySeconds = 60;
	UPROPERTY(EditAnywhere, Category="Creature|Time", meta=(ClampMin="1")) double NightSeconds = 60;
	UPROPERTY(EditAnywhere, Category="Creature|Migration") FEcoMigrationSettings Migration;
	UPROPERTY(EditAnywhere, Category="Creature|Population") bool bEnableWaves = false;
	UPROPERTY(EditAnywhere, Category="Creature|Vitals", meta=(ClampMin="0")) float EnergyDrainPerSecond = 1.0f;
	UPROPERTY(EditAnywhere, Category="Creature|Vitals", meta=(ClampMin="0")) float EnergyPerFood = 5.0f;
	UFUNCTION(BlueprintPure, Category="Creature") int32 GetVisualCount() const { return Visuals.Num(); }
	UFUNCTION(BlueprintPure, Category="Creature") bool IsRuntimeReady() const { return bReady; }
	virtual float GetFoodDensity(const FVector& Location, float Radius) const override;
	virtual FVector GetFoodGradient(const FVector& Location, float Radius) const override;
	virtual float ConsumeFood(const FVector& Location, float Amount) override;
	virtual float GetRecentPredation(const FVector& Location) const override;
	virtual float GetCoverDistance(const FVector& Location) const override;
	virtual FVector GetCoverDirection(const FVector& Location) const override;
	virtual bool IsInCover(const FVector& Location) const override;
private:
	bool RegisterTemplates();
	bool StartAuthority();
	int32 Spawn(FName RegionId, int32 Count, bool bPredator);
	void Reconcile(float DeltaSeconds);
	void SyncVisuals(float DeltaSeconds);
	void PublishSummary();
	void FailRuntime(const TCHAR* Reason);
	void OnWorldPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
	FDelegateHandle PostTickHandle;
	AEcologyRegion* FindRegion(const FVector& Position) const;
	UPROPERTY(Transient) TArray<TObjectPtr<AEcologyRegion>> Regions;
	TArray<FMassEntityHandle> Owned;
	struct FBinding { TWeakObjectPtr<AEcoCreatureRepresentationActor> Actor; int64 Sequence = 0; };
	TMap<int64, FBinding> Visuals;
	bool bReady = false;
	double LastResourceTime = 0;
	double NextLog = 0;
	int64 Step = 0;
	double TestExitAfter = 0;
	double TestCaptureAt = 0;
	double StartedAt = 0;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API AEcoCreatureIntegrationGameMode : public AGameModeBase
{
	GENERATED_BODY()
public:
	AEcoCreatureIntegrationGameMode();
	virtual void InitGameState() override;
};
