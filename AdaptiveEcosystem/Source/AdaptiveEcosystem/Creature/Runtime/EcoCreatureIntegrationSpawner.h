#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AdaptiveEcosystemGameMode.h"
#include "AI/Policy/EcoWorldProviders.h"
#include "Core/EcoMigrationTypes.h"
#include "Core/EcoSurvivalTypes.h"
#include "Core/EcoCombatTypes.h"
#include "AI/Behavior/EcoSpeciesAIProfile.h"
#include "Core/EcoBehaviorReasonHistory.h"
#include "Ecology/EcoSpawnSchedule.h"
#include "Mass/EntityHandle.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Runtime/EcoFauna.h"
#include "EcoCreatureIntegrationSpawner.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FEcoRuntimeSample, float, DeltaSeconds);

class UMassEntityConfigAsset;
struct FMassEntityManager;
class AEcologyRegion;
class UWorldPartitionStreamingSourceComponent;
class UEcoFootstepAudioSet;
class AEcoVegetationField;
class AEcoForagePatchVisual;
class UEcoNaturalHabitatProfile;
class APawn;
class AController;
class AEcoCreatureHitProxy;
class UEcoMeleeHitComponent;
class UEcoPolicyV3IntegratedStepProcessor;
class UEcoPolicyV3IntegratedVisualProcessor;
namespace EcoThreatV3 { struct FThreatStepInput; }
struct FEcoV3RegionContext;
struct FEcoDeathOutcome;

enum class EEcoAdaptiveRoutine : uint16
{
    DeerMeal = 1 << 0,
    WolfMeal = 1 << 1,
    FaunaMeal = 1 << 2,
    ThreatVision = 1 << 3,
    ShelterApproach = 1 << 4,
    Roam = 1 << 5,
    RoutineSprint = 1 << 6,
    PreyValue = 1 << 7,
    PursuitLimit = 1 << 8,
    All = (1 << 9) - 1
};

USTRUCT(BlueprintType)
struct FEcoCreatureSpawnGroup
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere) FName RegionId = TEXT("Forest_A");
	UPROPERTY(EditAnywhere, meta=(ClampMin="0")) int32 Herbivores = 8;
	UPROPERTY(EditAnywhere, meta=(ClampMin="0")) int32 Wolves = 1;
	/** Keep authored rule-driven fauna without creating a Native v3 stage for this group. */
	UPROPERTY(EditAnywhere, Category="Creature|V3") bool bRulesOnly = false;
	/** World-space authored candidates. Empty arrays retain the original demo arrangement. */
	UPROPERTY(EditAnywhere) TArray<FVector> HerbivoreSpawnPoints;
	UPROPERTY(EditAnywhere) TArray<FVector> WolfSpawnPoints;
    UPROPERTY(EditAnywhere) TArray<FEcoFaunaPlacement> Fauna;
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
    /** Passive diagnostics at completed runtime boundaries, including headless servers. */
    UPROPERTY(BlueprintAssignable, Category="Creature|Inspection") FEcoRuntimeSample OnRuntimeSample;
    void RecordGameplayReason(int64 Agent, FName Region, double At, FName Reason, int64 RelatedAgent=0, double Amount=0);
    const FEcoBehaviorReasonHistory* FindGameplayReasons(int64 Agent) const { return GameplayReasons.Find(Agent); }
    /** Authority-only food stock for inspection and controlled map verification. */
    UFUNCTION(BlueprintPure, Category="Creature|Inspection")
    bool InspectFaunaHabitatStock(FName PatchId, float& Stock) const;
    /** Short-lived preference among candidates that pass the authority's ordinary food checks. */
    UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category="Creature|Fauna")
    bool SubmitFaunaFoodIntent(int64 AgentId, EEcoFaunaFoodIntent Kind, int64 TargetAgentId, FName PatchId);
	UPROPERTY(EditAnywhere, Category="Creature|Config") EEcoEnabledSpecies EnabledSpecies = EEcoEnabledSpecies::Both;
	UPROPERTY(EditAnywhere, Category="Creature|Config") bool bEnableSpeciesAIFixtures = false;
	UPROPERTY(EditAnywhere, Category="Creature|V3") bool bUseV3Policy = false;
	UPROPERTY(EditAnywhere, Category="Creature|V3", meta=(ClampMin="1",ClampMax="128")) int32 V3DeerPerRegion = 48;
	/** Copy-level opt-in: consume only authored shelter anchors. */
	UPROPERTY(EditAnywhere, Category="Creature|V3") bool bV3UseAuthoredShelters = false;
	/** 11-05 island stage (Docs/RL_Policy/ISLAND_STAGE.md): integrated v3 turns the single group region into one island-wide square world with a land/water mask.
	 *  Default false; only the owned copy map /Game/EcoTest/Maps/LV_EcoV3_Island sets it. Console eco.IntegratedV3.Island 0/1 overrides. */
	UPROPERTY(EditAnywhere, Category="Creature|V3") bool bV3IslandStage = false;
	/** Owned-map opt-in; does not change other maps or policy schemas. */
	UPROPERTY(EditAnywhere, Category="Creature|Vegetation") bool bEnableVegetation = false;
    /** Owned scene opt-in: deterministic diversity, observed encounters and conditional offspring. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Creature|Life") bool bEnableEcosystemLife = false;
    UPROPERTY(EditAnywhere, Category="Creature|Life") bool bEnableAdaptiveRoutines = false;
    uint16 GetAdaptiveRoutineMask() const
    {
        return bEnableEcosystemLife
            ? AdaptiveRoutineOverride.Get(bEnableAdaptiveRoutines ? uint16(EEcoAdaptiveRoutine::All) : 0) : 0;
    }
    bool UsesAdaptiveRoutine(EEcoAdaptiveRoutine Rule) const { return (GetAdaptiveRoutineMask() & uint16(Rule)) != 0; }
    /** Explicit level opt-in; null preserves all legacy/life-v2 habitat and safety rules. */
    UPROPERTY(EditAnywhere, Category="Creature|Habitat") TObjectPtr<UEcoNaturalHabitatProfile> NaturalHabitatProfile;
    UPROPERTY(EditAnywhere, Category="Creature|Habitat") TMap<FName,TObjectPtr<UEcoNaturalHabitatProfile>> RegionHabitatProfiles;
	UPROPERTY(EditAnywhere, Category="Creature|Vegetation") TSubclassOf<AEcoVegetationField> VegetationFieldClass;
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
    /** Empty in legacy maps. Grounded residents share the spatial food ledger and Mass presentation. */
    UPROPERTY(EditAnywhere, Category="Creature|Population") TArray<FEcoFaunaSpecies> FaunaSpecies;
    UPROPERTY(EditAnywhere, Category="Creature|Population", meta=(ClampMin="0", ClampMax="3")) int32 FaunaHabitatStage = 0;
    UPROPERTY(EditAnywhere, Category="Creature|Population") TArray<FEcoFaunaHabitatPatch> FaunaHabitatPatches;
    UPROPERTY(EditAnywhere, Category="Creature|Movement") TArray<FEcoFaunaPerch> FaunaPerches;
    UPROPERTY(EditAnywhere, Category="Creature|Population") TArray<FEcoFaunaCoolingSite> FaunaCoolingSites;
    UPROPERTY(EditAnywhere, Category="Creature|Population") FEcoFaunaPersistenceSettings FaunaPersistence;
	UPROPERTY(EditAnywhere, Category="Creature|Population", meta=(ClampMin="1",ClampMax="512")) int32 GlobalPopulationLimit = 128;
	UPROPERTY(EditAnywhere, Category="Creature|Time", meta=(ClampMin="1")) double DaySeconds = 60;
	UPROPERTY(EditAnywhere, Category="Creature|Time", meta=(ClampMin="1")) double NightSeconds = 60;
	UPROPERTY(EditAnywhere, Category="Creature|Migration") FEcoMigrationSettings Migration;
    /** Separate opt-in for shared native-v3 herd journeys; legacy per-agent migration remains guarded. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Creature|Migration") bool bEnableHerdJourneys=false;
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
	/** Client camera-to-creature 3D distance. 0 disables this local limit; Bubble relevance and Actor budgets still apply.
	 *  Hiding a visual never removes its server logical agent or changes the authority debug map. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Creature|Visual", meta=(ClampMin="0",ClampMax="200000",Units="cm")) float ClientVisualDistance = 1000.0f;
	/** Experimental policy scheduling only. Off by default until the scale fixture is measured. */
	UPROPERTY(EditAnywhere, Category="Creature|Simulation LOD") bool bEnableSimulationLOD = false;
	UPROPERTY(EditAnywhere, Category="Creature|Simulation LOD", meta=(ClampMin="4000",Units="cm")) float FarSimulationDistance = 20000.0f;
	UPROPERTY(EditAnywhere, Category="Creature|Simulation LOD", meta=(ClampMin="1",ClampMax="8")) float FarPolicyIntervalMultiplier = 4.0f;
	UFUNCTION(BlueprintPure, Category="Creature") int32 GetVisualCount() const { return Visuals.Num(); }
	UFUNCTION(BlueprintPure, Category="Creature") bool IsRuntimeReady() const { return bReady; }
	UFUNCTION(BlueprintCallable, Category="Creature|Diagnostics") void DumpRuntime(bool bDetails = false) const;
    /** Explicit authority checkpoint. Slots are local Saved/Ecosystem names, not arbitrary paths. */
    UFUNCTION(BlueprintCallable, Category="Creature|Persistence") bool SaveEcosystem(const FString& Slot);
    UFUNCTION(BlueprintCallable, Category="Creature|Persistence") bool LoadEcosystem(const FString& Slot);
    /** Server-owned melee request; no client position, damage, target or outcome is accepted. */
    bool QueuePlayerStrike(APawn& Player);
    /** Called exclusively by authoritative socket sweeps; the server reads damage from their data asset. */
    bool QueueComboContact(UEcoMeleeHitComponent& Source, AEcoCreatureHitProxy& Target, const FHitResult& Hit);
    bool QueueWeaponContact(class UEcoWeaponFireComponent& Source, AEcoCreatureHitProxy& Target, const FHitResult& Hit);
    void GetCombatCandidates(APawn& Player,int32& Epoch,TArray<int64>& Out) const;
    UFUNCTION(BlueprintPure, Category="Creature|Combat") FEcoCombatDiagnostics GetCombatDiagnostics() const;
    UPROPERTY(EditAnywhere, Category="Creature|Combat") bool bEnablePlayerCombat = false;
    UPROPERTY(EditAnywhere, Category="Creature|Combat", meta=(ClampMin="500", ClampMax="5000")) float HitProxyDistance = 1800.f;
    UPROPERTY(EditAnywhere, Category="Creature|Combat", meta=(ClampMin="1", ClampMax="512")) int32 MaxHitProxies = 256;
    UPROPERTY(EditAnywhere, Category="Creature|Combat", meta=(ClampMin="0", ClampMax="200")) float WolfPlayerDamage = 20.f;
    /** Native threat hook supplies movement intent only; damage is consumed outside Mass processing. */
    bool GuideWolfPlayerCombat(int64 Id, FEcoV3RegionContext& Context, const FVector& Position,
        const FVector& Heading, double Now, bool bAvailable, bool bProvoked, EcoThreatV3::FThreatStepInput& Input);
    /** Native movement keeps ownership. This query only selects a bounded, visible food destination. */
    bool SelectWolfCarrion(int64 WolfId, FName Region, const FVector& Position, bool bCanScavenge,
        double ApproachSpeedCmPerSecond, FVector& Out, double AuthoritySeconds = -1.);
    /** Explicit authority operation only; two founders in an empty population, never a natural birth. */
    UFUNCTION(BlueprintCallable,BlueprintAuthorityOnly,Category="Creature|Life") bool QueuePopulationRecovery(FName RegionId,bool bPredator);
	/** Read-only authoring report. Never creates Entities, edits actors, or saves the level. */
	UFUNCTION(CallInEditor, BlueprintCallable, Category="Creature|Setup") void ValidateEditorSetup() const;
    /** Bounded, read-only test/production level survey; no resource or actor writes. */
    UFUNCTION(BlueprintPure,Category="Creature|Setup") FString CaptureHabitatAuthoringReport() const;
	virtual float GetFoodDensity(const FVector& Location, float Radius) const override;
	virtual FVector GetFoodGradient(const FVector& Location, float Radius) const override;
	virtual float ConsumeFood(const FVector& Location, float Amount) override;
	virtual float GetRecentPredation(const FVector& Location) const override;
	virtual float GetCoverDistance(const FVector& Location) const override;
	virtual FVector GetCoverDirection(const FVector& Location) const override;
	virtual bool IsInCover(const FVector& Location) const override;
private:
    bool UsesFaunaPersistence() const { return FaunaHabitatStage > 0 && FaunaPersistence.bEnabled; }
    TOptional<uint16> AdaptiveRoutineOverride;
    bool bFaunaPursuitFix = false;
    bool bFaunaCarrionAccess = true;
    bool bFaunaAttackAdvance = false;
    bool bFaunaFollowWounded = false;
    bool bAuditFaunaHunts = false;
    bool bAuditFaunaBirths = false;
    bool UsesFaunaPursuitFix() const { return FaunaHabitatStage >= 3 && bFaunaPursuitFix; }
    bool UsesFaunaCarrionAccess() const { return FaunaHabitatStage >= 3 && bFaunaCarrionAccess; }
    bool UsesFaunaAttackAdvance() const { return FaunaHabitatStage >= 3 && bFaunaAttackAdvance; }
    bool UsesFaunaFollowWounded() const { return FaunaHabitatStage >= 3 && bFaunaFollowWounded; }
	friend struct FEcoEcosystemCheckpoint;
    friend struct FEcoCombatTestAccess;
	friend class UEcoPolicyV3IntegratedSubsystem;
	bool RegisterTemplates();
	bool CollectSetupIssues(TArray<FString>& Errors, TArray<FString>& Notes) const;
    bool ValidateFauna(TArray<FString>& Errors) const;
    bool RegisterFaunaTemplate();
    bool BuildFaunaPositions(FName RegionId, const FEcoFaunaPlacement& Placement, TArray<FVector>& Out) const;
    bool InitializeFaunaHabitat();
    void UpdateFaunaHabitatStock(double Now);
    void PublishForageVisuals();
    const FEcoFaunaHabitatPatch* FindFaunaShelter(FName Region, FName Species, const FVector& Position, double Range,
        float ApproachEyeHeight = 0.f) const;
    TArray<float> FaunaPatchStock;
    TArray<TWeakObjectPtr<AEcoForagePatchVisual>> FaunaForageVisuals;
    double LastFaunaPatchUpdate = 0.;
    const FEcoFaunaSpecies* FindFauna(FName SpeciesId) const;
    struct FFaunaFoodIntent
    {
        EEcoFaunaFoodIntent Kind;
        FName Region, PatchId;
        int64 TargetAgentId;
        double IssuedAt;
    };
    TMap<int64, FFaunaFoodIntent> FaunaFoodIntents;
    double RankFaunaFood(double Score, int64 AgentId, FName Region, double Now,
        EEcoFaunaFoodIntent Kind, int64 TargetAgentId = 0, FName PatchId = NAME_None) const;
    int32 CountFauna(FName RegionId, FName SpeciesId = NAME_None) const;
    FIntPoint CountFaunaDiets(FName RegionId) const;
    int32 SpawnFauna(FName RegionId, const FEcoFaunaSpecies& Species, const TArray<FVector>& Positions,
        const FEcoServerTimeSnapshot& Time);
    void MoveFauna(float Delta, double Now);
    void MoveFaunaInWater(FMassEntityManager& Manager, FMassEntityHandle Entity, const FEcoFaunaSpecies& Species,
        float Delta, double Now, double PhysicalCondition, float Darkness, bool bAdaptiveMeal);
    void MoveFaunaWaterCarcass(FMassEntityManager& Manager, FMassEntityHandle Entity, const FEcoFaunaSpecies& Species,
        float Delta, double Now);
    int64 FindFaunaWaterPrey(const FMassEntityManager& Manager, FMassEntityHandle Entity, const FEcoFaunaSpecies& Species,
        const FVector& From, double Now, bool bInWater, double ApproachSeconds, double& BestScore, FVector& Goal) const;
    void ReconcileFaunaPassages(FMassEntityManager& EM, const FEcoServerTimeSnapshot& Time, double ObservedTime, int64 Step,
        TArray<FEcoMigrationOutcome>& Arrivals);
    void ProcessFaunaPredation(double Now);
    FMassEntityHandle SelectFaunaGuard(const FMassEntityManager& Manager, FMassEntityHandle Child,
        FMassEntityHandle Hunter, double Now) const;
    bool CanHuntFauna(const FMassEntityManager& Manager, FMassEntityHandle Predator, FMassEntityHandle Prey,
        const FEcoFaunaSpecies& Profile, double Now, bool bContact, bool bCheckVisibility = true, FName* Rejection = nullptr) const;
    bool MoveFaunaFlight(const FEcoFaunaSpecies& Profile, FName Region, FEcoFaunaFragment& Fauna,
        const FVector& Position, double Now, double Delta, FVector& Destination) const;
    bool ProcessFauna(const FEcoServerTimeSnapshot& Time);
    TMap<int64, FEcoFaunaCarcass> FaunaCarcasses;
    TMap<FName, EcoTracesV3::FField> FaunaScent;
    TMap<int64, int64> WolfCarrionTargets;
    void CommitFaunaCarcass(const FEcoDeathOutcome& Death, float NativeReserved);
    void FeedWolvesFromCarrion(double Now);
    struct FFaunaBirth { FName Region, Species; int64 ParentA = 0, ParentB = 0; double Due = 0.; FName NestId; };
    TArray<FFaunaBirth> FaunaBirths;
    double NextFaunaBirthScan = 0.;
    UPROPERTY(Transient) TObjectPtr<UMassEntityConfigAsset> FaunaConfig;
	bool StartAuthority();
	int32 Spawn(FName RegionId, int32 Count, bool bPredator, const FEcoServerTimeSnapshot& Time,
		const TArray<FVector>* PositionsOverride=nullptr);
    bool ProcessNaturalBirths(const FEcoServerTimeSnapshot& Time);
    struct FPendingBirth { int64 ParentA=0,ParentB=0; FName Region; double Due=0; bool bPredator=false; };
    TArray<FPendingBirth> PendingBirths;
    struct FPendingRecovery { FName Region;double Issued=0;bool bPredator=false; };
    TArray<FPendingRecovery> PendingRecoveries;
    TMap<FName,double> LastHerbRecovery,LastWolfRecovery;
    bool ProcessPopulationRecovery(const FEcoServerTimeSnapshot& Time);
    double NextBirthScan=0;
    struct FPlayerStrike { TWeakObjectPtr<APawn> Player; double Issued=0; };
    TArray<FPlayerStrike> PlayerStrikes;
    TMap<TWeakObjectPtr<APawn>,double> StrikeCooldown;
    uint64 StrikeSequence=0;
    void ProcessPlayerStrikes(const FEcoServerTimeSnapshot& Time);
    double CommitNativeCarcass(const FEcoDeathOutcome& Death);
    void UpdateHitProxies();
    void ResetCombat();
    void ProcessCombatDamage(const FEcoServerTimeSnapshot& Time);
    void ProcessComboDamage(const FEcoServerTimeSnapshot& Time, uint64 ThroughSequence=MAX_uint64);
    void ProcessWolfAttacks(const FEcoServerTimeSnapshot& Time, uint64 ThroughSequence=MAX_uint64);
    void ApplyPlayerDamage(APawn& Player, FMassEntityHandle Target, float Damage);
    struct FComboDamage
    {
        TWeakObjectPtr<APawn> Player;
        TWeakObjectPtr<AController> Controller;
        TWeakObjectPtr<UEcoMeleeHitComponent> Source;
        TWeakObjectPtr<class UEcoWeaponFireComponent> WeaponSource;
        int32 Epoch=0, Stage=0;
        uint32 Avatar=0;
        int64 Execution=0, Target=0;
        uint64 Sequence=0;
        double Issued=0, RealIssued=0;
        float Damage=0;
    };
    TArray<FComboDamage> ComboDamage;
    struct FHuntingKill { TWeakObjectPtr<UEcoMeleeHitComponent> Source; FEcoCombatDamageOutcome Outcome; TWeakObjectPtr<class UEcoWeaponFireComponent> WeaponSource; };
    TMap<int64,FHuntingKill> PendingHuntingDeaths;
    TMap<FString,double> ComboReceipts;
    UPROPERTY(Transient) TMap<int64,TObjectPtr<AEcoCreatureHitProxy>> HitProxies;
    UPROPERTY(Transient) TArray<TObjectPtr<AEcoCreatureHitProxy>> HitProxyPool;
    int32 CombatEpoch=0;
    struct FWolfCombat
    {
        TWeakObjectPtr<APawn> Target;
        uint32 Avatar=0;
        double Due=-1, Cooldown=0, LastSeen=-1;
        bool bPending=false;
        double ContactTime=0;
        uint64 Sequence=0;
    };
    TMap<int64,FWolfCombat> WolfCombat;
    FEcoCombatDiagnostics CombatDiagnostics;
    uint64 CombatContactSequence=0;
	bool BuildSpawnPositions(const FEcoCreatureSpawnGroup& Group, int32 Count, bool bPredator, TArray<FVector>& Out) const;
	void UpdateHabitatStreaming();
	void Reconcile(float DeltaSeconds);
	bool ProcessResourceStep(const FEcoServerTimeSnapshot& Time, double ObservedTime);
	bool BuildAgentLookup();
	bool ReconcilePopulation();
	void UpdatePresentationAndNoise(float DeltaSeconds);
	void UpdateSensoryPresentation();
	void UpdateSimulationLOD();
	void SyncVisuals(float DeltaSeconds);
	void PublishSummary();
	void FailRuntime(const TCHAR* Reason);
	TMap<FName,double> NextPresentationAlarm;
	void OnWorldPostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
	FDelegateHandle PostTickHandle;
	AEcologyRegion* FindRegion(const FVector& Position) const;
	UPROPERTY(Transient) TArray<TObjectPtr<AEcologyRegion>> Regions;
	UPROPERTY(Transient) TArray<TObjectPtr<UMassEntityConfigAsset>> AdditionalClientConfigs;
	TArray<FMassEntityHandle> Owned;
	struct FBinding { TWeakObjectPtr<AEcoCreatureRepresentationActor> Actor; int64 Sequence = 0; uint32 MovementRevision = 0; };
	TMap<int64, FBinding> Visuals;
	UPROPERTY(Transient) TArray<TObjectPtr<AEcoCreatureRepresentationActor>> VisualPool;
	TMap<int64, FMassEntityHandle> AgentLookup;
	bool bReady = false;
	/** Ownership is captured before travel can temporarily change the old world's NetMode. */
	bool bAuthorityWorld = false;
	bool bWaitingForHabitat = false;
	double NextStreamingUpdate = 0;
	double LastResourceTime = 0;
    double FaunaMotionTime = -1.;
    UPROPERTY(Transient) TObjectPtr<UEcoPolicyV3IntegratedStepProcessor> MixedNativeStep;
    UPROPERTY(Transient) TObjectPtr<UEcoPolicyV3IntegratedVisualProcessor> MixedNativeTransforms;
    double AuthorityClockWorldOrigin = 0.;
	double NextLog = 0;
    double NextAuditSample = 0;
	int64 Step = 0;
	int32 SummaryRevision = 0;
	double NextMigrationTime = 0.0;
	FEcoServerTimeSnapshot CompletedTime;
	int64 SuccessfulBirths = 0;
	int64 CommittedDeaths = 0;
	struct FSpeciesTotals { int64 Births = 0, Deaths = 0, Incoming = 0, Outgoing = 0; };
	TMap<FName, TMap<FName, FSpeciesTotals>> SpeciesTotals;
    TMap<int64, FEcoBehaviorReasonHistory> GameplayReasons;
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
class ADAPTIVEECOSYSTEM_API AEcoCreatureIntegrationGameMode : public AAdaptiveEcosystemGameMode
{
	GENERATED_BODY()
public:
	AEcoCreatureIntegrationGameMode();
	virtual void InitGameState() override;
	virtual void PostLogin(APlayerController* NewPlayer) override;
	virtual void Logout(AController* Exiting) override;
};
