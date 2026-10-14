#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/GameModeBase.h"
#include "AI/Policy/EcoWorldProviders.h"
#include "Core/EcoMigrationTypes.h"
#include "Core/EcoSurvivalTypes.h"
#include "AI/Behavior/EcoSpeciesAIProfile.h"
#include "Ecology/EcoSpawnSchedule.h"
#include "Mass/EntityHandle.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "EcoCreatureIntegrationSpawner.generated.h"

class UMassEntityConfigAsset;
class AEcologyRegion;
class UWorldPartitionStreamingSourceComponent;
class UEcoFootstepAudioSet;

USTRUCT(BlueprintType)
struct FEcoCreatureSpawnGroup
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere) FName RegionId = TEXT("Forest_A");
	UPROPERTY(EditAnywhere, meta=(ClampMin="0")) int32 Herbivores = 8;
	UPROPERTY(EditAnywhere, meta=(ClampMin="0")) int32 Wolves = 1;
	/** World-space authored candidates. Empty arrays retain the original demo arrangement. */
	UPROPERTY(EditAnywhere) TArray<FVector> HerbivoreSpawnPoints;
	UPROPERTY(EditAnywhere) TArray<FVector> WolfSpawnPoints;
	/** Spatial distribution hint only; regional FoodAmount remains the authority. */
	UPROPERTY(EditAnywhere) bool bUseFoodPatchPosition = false;
	UPROPERTY(EditAnywhere) FVector FoodPatchPosition = FVector::ZeroVector;
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
	UPROPERTY(EditAnywhere, Category="Creature|Config") EEcoEnabledSpecies EnabledSpecies = EEcoEnabledSpecies::Both;
	UPROPERTY(EditAnywhere, Category="Creature|Config") bool bEnableSpeciesAIFixtures = false;
	bool IsSpeciesEnabled(bool bPredator) const
	{ return EnabledSpecies == EEcoEnabledSpecies::Both || (bPredator ? EnabledSpecies == EEcoEnabledSpecies::WolfOnly : EnabledSpecies == EEcoEnabledSpecies::DeerOnly); }
	virtual void PostInitializeComponents() override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	UPROPERTY(EditAnywhere, Category="Creature|Config") TObjectPtr<UMassEntityConfigAsset> HerbivoreConfig;
	UPROPERTY(EditAnywhere, Category="Creature|Config") TObjectPtr<UMassEntityConfigAsset> WolfConfig;
	UPROPERTY(EditAnywhere, Category="Creature|Visual") TSubclassOf<AEcoCreatureRepresentationActor> HerbivoreActorClass;
	UPROPERTY(EditAnywhere, Category="Creature|Visual") TSubclassOf<AEcoCreatureRepresentationActor> WolfActorClass;
	/** Shared presentation/noise tuning; cadence remains per logical agent and per local visual. */
	UPROPERTY(EditAnywhere, Category="Creature|Audio") TObjectPtr<UEcoFootstepAudioSet> FootstepAudioSet;
	UPROPERTY(EditAnywhere, Category="Creature|Population") TArray<FEcoCreatureSpawnGroup> Groups;
	UPROPERTY(EditAnywhere, Category="Creature|Population", meta=(ClampMin="1",ClampMax="512")) int32 GlobalPopulationLimit = 128;
	UPROPERTY(EditAnywhere, Category="Creature|Time", meta=(ClampMin="1")) double DaySeconds = 60;
	UPROPERTY(EditAnywhere, Category="Creature|Time", meta=(ClampMin="1")) double NightSeconds = 60;
	UPROPERTY(EditAnywhere, Category="Creature|Migration") FEcoMigrationSettings Migration;
	UPROPERTY(EditAnywhere, Category="Creature|Population") bool bEnableWaves = false;
	UPROPERTY(EditAnywhere, Category="Creature|Streaming") bool bUseHabitatStreaming = false;
	UPROPERTY(EditAnywhere, Category="Creature|Streaming", meta=(ClampMin="3000", Units="cm")) float HabitatStreamingRadius = 10000.0f;
	UPROPERTY(VisibleAnywhere, Category="Creature|Streaming") TObjectPtr<UWorldPartitionStreamingSourceComponent> HabitatStreamingSource;
	UPROPERTY(EditAnywhere, Category="Creature|Vitals", meta=(ClampMin="0")) float EnergyDrainPerSecond = 1.0f;
	UPROPERTY(EditAnywhere, Category="Creature|Vitals", meta=(ClampMin="0")) float EnergyPerFood = 5.0f;
	/** Preserve the former Creature defaults; Box has its own baseline settings. */
	UPROPERTY(EditAnywhere, Category="Creature|Vitals", meta=(ClampMin="0")) double StarvationGraceSeconds = 0.0;
	UPROPERTY(EditAnywhere, Category="Creature|Vitals", meta=(ClampMin="0.01")) float StarvationDamagePerSecond = 5.0f;
	/** Opt-in predator metabolism. Disabled by default to preserve the existing demonstration. */
	UPROPERTY(EditAnywhere, Category="Creature|Predator") bool bEnablePredatorSurvival = false;
	UPROPERTY(EditAnywhere, Category="Creature|Predator", meta=(ClampMin="0")) float PredatorEnergyDrainPerSecond = 1.0f;
	UPROPERTY(EditAnywhere, Category="Creature|Predator", meta=(ClampMin="0")) float PredatorEnergyPerCapture = 25.0f;
	UPROPERTY(EditAnywhere, Category="Creature|Pressure") bool bEnablePopulationPressure = true;
	UPROPERTY(EditAnywhere, Category="Creature|Pressure") FEcoOvercrowdingSettings PopulationPressure;
	UPROPERTY(EditAnywhere, Category="Creature|Scheduling", meta=(ClampMin="1",ClampMax="32")) int32 MaxCatchUpSteps = 8;
	UPROPERTY(EditAnywhere, Category="Creature|Visual", meta=(ClampMin="0",ClampMax="1")) float InterpolationDelaySeconds = 0.1f;
	UPROPERTY(EditAnywhere, Category="Creature|Visual", meta=(ClampMin="0",ClampMax="200000",Units="cm")) float HostVisualDistance = 20000.0f;
	/** Experimental policy scheduling only. Off by default until the scale fixture is measured. */
	UPROPERTY(EditAnywhere, Category="Creature|Simulation LOD") bool bEnableSimulationLOD = false;
	UPROPERTY(EditAnywhere, Category="Creature|Simulation LOD", meta=(ClampMin="4000",Units="cm")) float FarSimulationDistance = 20000.0f;
	UPROPERTY(EditAnywhere, Category="Creature|Simulation LOD", meta=(ClampMin="1",ClampMax="8")) float FarPolicyIntervalMultiplier = 4.0f;
	UFUNCTION(BlueprintPure, Category="Creature") int32 GetVisualCount() const { return Visuals.Num(); }
	UFUNCTION(BlueprintPure, Category="Creature") bool IsRuntimeReady() const { return bReady; }
	UFUNCTION(BlueprintCallable, Category="Creature|Diagnostics") void DumpRuntime(bool bDetails = false) const;
	/** Read-only authoring report. Never creates Entities, edits actors, or saves the level. */
	UFUNCTION(CallInEditor, BlueprintCallable, Category="Creature|Setup") void ValidateEditorSetup() const;
	virtual float GetFoodDensity(const FVector& Location, float Radius) const override;
	virtual FVector GetFoodGradient(const FVector& Location, float Radius) const override;
	virtual float ConsumeFood(const FVector& Location, float Amount) override;
	virtual float GetRecentPredation(const FVector& Location) const override;
	virtual float GetCoverDistance(const FVector& Location) const override;
	virtual FVector GetCoverDirection(const FVector& Location) const override;
	virtual bool IsInCover(const FVector& Location) const override;
private:
	bool RegisterTemplates();
	bool CollectSetupIssues(TArray<FString>& Errors, TArray<FString>& Notes) const;
	bool StartAuthority();
	int32 Spawn(FName RegionId, int32 Count, bool bPredator);
	bool BuildSpawnPositions(const FEcoCreatureSpawnGroup& Group, int32 Count, bool bPredator, TArray<FVector>& Out) const;
	void UpdateHabitatStreaming();
	void Reconcile(float DeltaSeconds);
	bool ProcessResourceStep(const FEcoServerTimeSnapshot& Time, double ObservedTime);
	bool BuildAgentLookup();
	bool ReconcilePopulation();
	void UpdatePresentationAndNoise(float DeltaSeconds);
	void UpdateSimulationLOD();
	void SyncVisuals(float DeltaSeconds);
	void PublishSummary();
	void FailRuntime(const TCHAR* Reason);
	void OnWorldPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
	FDelegateHandle PostTickHandle;
	AEcologyRegion* FindRegion(const FVector& Position) const;
	UPROPERTY(Transient) TArray<TObjectPtr<AEcologyRegion>> Regions;
	TArray<FMassEntityHandle> Owned;
	struct FBinding { TWeakObjectPtr<AEcoCreatureRepresentationActor> Actor; int64 Sequence = 0; uint32 MovementRevision = 0; };
	TMap<int64, FBinding> Visuals;
	UPROPERTY(Transient) TArray<TObjectPtr<AEcoCreatureRepresentationActor>> VisualPool;
	TMap<int64, FMassEntityHandle> AgentLookup;
	bool bReady = false;
	bool bWaitingForHabitat = false;
	double NextStreamingUpdate = 0;
	double LastResourceTime = 0;
	double NextLog = 0;
	int64 Step = 0;
	int32 SummaryRevision = 0;
	double NextMigrationTime = 0.0;
	FEcoServerTimeSnapshot CompletedTime;
	int64 SuccessfulBirths = 0;
	int64 CommittedDeaths = 0;
	struct FSpeciesTotals { int64 Births = 0, Deaths = 0, Incoming = 0, Outgoing = 0; };
	TMap<FName, TMap<FName, FSpeciesTotals>> SpeciesTotals;
	double TestExitAfter = 0;
	double TestCaptureAt = 0;
	double StartedAt = 0;
#if WITH_DEV_AUTOMATION_TESTS
	void UpdateTestObserver();
	bool bTestObserverCycle = false;
	int32 LastTestObserverPhase = INDEX_NONE;
#endif
};

UCLASS()
class ADAPTIVEECOSYSTEM_API AEcoCreatureIntegrationGameMode : public AGameModeBase
{
	GENERATED_BODY()
public:
	AEcoCreatureIntegrationGameMode();
	virtual void InitGameState() override;
};
