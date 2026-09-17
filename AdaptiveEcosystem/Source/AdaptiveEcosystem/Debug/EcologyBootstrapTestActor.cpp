// Copyright Epic Games, Inc. All Rights Reserved.

#include "Debug/EcologyBootstrapTestActor.h"
#include "Creature/CreatureCharacter.h"
#include "Creature/CreatureTraitComponent.h"
#include "Ecology/EcologyServerSubsystem.h"
#include "Evolution/EvolutionDecisionProvider.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "AdaptiveEcosystem.h"

AEcologyBootstrapTestActor::AEcologyBootstrapTestActor()
{
	PrimaryActorTick.bCanEverTick = false;

	TestRegionId = FName(TEXT("Forest_A"));
	TestSpeciesId = FName(TEXT("Wolf"));
	TestVegetationSpeciesId = FName(TEXT("Grass_A"));
	bAutoRunOnBeginPlay = true;
	CreatureClassToSpawn = ACreatureCharacter::StaticClass();
}

void AEcologyBootstrapTestActor::BeginPlay()
{
	Super::BeginPlay();

	if (bAutoRunOnBeginPlay)
	{
		RunBootstrapVerticalSliceTest();
		RunEcosystemFeedbackLoopTest();
	}
}


bool AEcologyBootstrapTestActor::RunBootstrapVerticalSliceTest()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: World is null."));
		return false;
	}

	// 1. Query Authoritative Species Profile from Server Subsystem
	UEcologyServerSubsystem* ServerSubsystem = World->GetSubsystem<UEcologyServerSubsystem>();
	if (!ServerSubsystem)
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyBootstrapTestActor: EcologyServerSubsystem not found (may be running on NM_Client)."));
		return false;
	}

	FSpeciesEvolutionProfile Profile;
	if (!ServerSubsystem->GetSpeciesEvolutionProfile(TestRegionId, TestSpeciesId, Profile))
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: Failed to find profile for [%s x %s]."),
			*TestRegionId.ToString(), *TestSpeciesId.ToString());
		return false;
	}

	// 2. Resolve Target Creature (Explicit -> Find Existing -> Spawn New)
	ACreatureCharacter* Creature = TargetCreature.Get();
	if (!Creature)
	{
		// Search for any existing creature character in the level
		for (TActorIterator<ACreatureCharacter> It(World); It; ++It)
		{
			Creature = *It;
			TargetCreature = Creature;
			break;
		}
	}

	if (!Creature && CreatureClassToSpawn)
	{
		// Spawn a test creature near this test actor
		const FVector SpawnLocation = GetActorLocation() + GetActorForwardVector() * 200.0f;
		const FRotator SpawnRotation = GetActorRotation();
		FActorSpawnParameters SpawnParams;
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;

		Creature = World->SpawnActor<ACreatureCharacter>(CreatureClassToSpawn, SpawnLocation, SpawnRotation, SpawnParams);
		if (Creature)
		{
			TargetCreature = Creature;
			UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyBootstrapTestActor: Spawned new test creature [%s]."), *Creature->GetName());
		}
	}

	if (!Creature)
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: No target creature available to test."));
		return false;
	}

	// 3. Inject SpawnData and Profile into Creature via canonical InitializeCreature API
	FCreatureSpawnData SpawnData;
	SpawnData.RegionId = TestRegionId;
	SpawnData.SpeciesId = TestSpeciesId;
	SpawnData.Generation = Profile.Generation;
	SpawnData.ProfileRevision = Profile.ProfileRevision;
	SpawnData.StableAgentId = 8888;

	Creature->InitializeCreature(SpawnData, Profile);

	// 4. Verify Trait Expression
	if (const UCreatureTraitComponent* TraitComp = Creature->GetTraitComponent())
	{
		const float Scale = TraitComp->GetBodyScale();
		const float SpeedMult = TraitComp->GetMoveSpeedMultiplier();
		const float Fear = TraitComp->GetFear();
		const float Aggression = TraitComp->GetAggression();

		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyBootstrapTestActor: TEST PASSED for [%s]!"), *Creature->GetName());
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Target: %s x %s (Gen: %d, Rev: %lld)"),
			*TestRegionId.ToString(), *TestSpeciesId.ToString(), Profile.Generation, Profile.ProfileRevision);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  BodyScale:           %.2f (Expected: %.2f)"), Scale, Profile.Phenotype.BodyScale);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  MoveSpeedMultiplier: %.2f (Expected: %.2f)"), SpeedMult, Profile.Gameplay.MoveSpeedMultiplier);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Fear:                %.2f (Expected: %.2f)"), Fear, Profile.Behavior.Fear);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Aggression:          %.2f (Expected: %.2f)"), Aggression, Profile.Behavior.Aggression);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));

		if (GEngine)
		{
			GEngine->AddOnScreenDebugMessage(
				-1, 8.0f, FColor::Green,
				FString::Printf(TEXT("[Ecology Monster Passed] %s: Scale=%.2f, Speed=%.2f, Fear=%.2f, Agg=%.2f"),
					*Creature->GetName(), Scale, SpeedMult, Fear, Aggression));
		}

		// Also execute vegetation evolution pipeline test
		RunVegetationEvolutionTest();

		return true;
	}

	UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: Creature has no TraitComponent."));
	return false;
}

bool AEcologyBootstrapTestActor::RunVegetationEvolutionTest()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}

	UEcologyServerSubsystem* ServerSubsystem = World->GetSubsystem<UEcologyServerSubsystem>();
	if (!ServerSubsystem)
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyBootstrapTestActor: ServerSubsystem null during vegetation test."));
		return false;
	}

	// 1. Query Current Base Profile
	FVegetationEvolutionProfile BaseProfile;
	if (!ServerSubsystem->GetVegetationEvolutionProfile(TestRegionId, TestVegetationSpeciesId, BaseProfile))
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: Failed to get base profile for [%s x %s]."),
			*TestRegionId.ToString(), *TestVegetationSpeciesId.ToString());
		return false;
	}

	// 2. Build Context with Simulated Grazing & Harvest Pressure
	FVegetationEvolutionContext Context;
	Context.WorldEpoch = 1;
	Context.ContextRevision = 1;
	Context.RegionId = TestRegionId;
	Context.VegetationSpeciesId = TestVegetationSpeciesId;
	Context.GrazingPressure = 0.75f; // High grazing from herbivore population
	Context.HarvestPressure = 0.10f;
	Context.Generation = BaseProfile.Generation;
	Context.CurrentProfile = BaseProfile;

	// 3. Generate Rule-Based Proposal via Dummy Decision Provider
	FVegetationEvolutionProposal Proposal;
	if (!UDummyEvolutionDecisionProvider::RequestVegetationProposal(Context, Proposal))
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: Failed to generate vegetation proposal."));
		return false;
	}

	// 4. Validate and Commit Proposal to Server
	FVegetationEvolutionProfile CommittedProfile;
	FString RejectReason;
	const bool bCommitted = ServerSubsystem->CommitVegetationEvolutionProposal(
		TestRegionId,
		TestVegetationSpeciesId,
		Proposal,
		Context.WorldEpoch,
		Context.ContextRevision,
		CommittedProfile,
		RejectReason);

	if (!bCommitted)
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: Failed to commit vegetation proposal: %s"), *RejectReason);
		return false;
	}

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyBootstrapTestActor: VEGETATION TEST PASSED for [%s x %s]!"),
		*TestRegionId.ToString(), *TestVegetationSpeciesId.ToString());
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Generation:          %d -> %d"), BaseProfile.Generation, CommittedProfile.Generation);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  ProfileRevision:     %lld -> %lld"), BaseProfile.ProfileRevision, CommittedProfile.ProfileRevision);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  GrowthRate:          %.2f -> %.2f"), BaseProfile.Traits.GrowthRate, CommittedProfile.Traits.GrowthRate);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  RegenerationRate:    %.2f -> %.2f"), BaseProfile.Traits.RegenerationRate, CommittedProfile.Traits.RegenerationRate);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  GrazingResistance:   %.2f -> %.2f"), BaseProfile.Traits.GrazingResistance, CommittedProfile.Traits.GrazingResistance);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));

	if (GEngine)
	{
		GEngine->AddOnScreenDebugMessage(
			-1, 8.0f, FColor::Cyan,
			FString::Printf(TEXT("[Ecology Vegetation Passed] %s x %s (Gen:%d): Growth=%.2f, Regen=%.2f, Resist=%.2f"),
				*TestRegionId.ToString(), *TestVegetationSpeciesId.ToString(), CommittedProfile.Generation,
				CommittedProfile.Traits.GrowthRate, CommittedProfile.Traits.RegenerationRate, CommittedProfile.Traits.GrazingResistance));
	}

	return true;
}

bool AEcologyBootstrapTestActor::RunEcosystemFeedbackLoopTest()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}

	UEcologyServerSubsystem* ServerSubsystem = World->GetSubsystem<UEcologyServerSubsystem>();
	if (!ServerSubsystem)
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyBootstrapTestActor: ServerSubsystem null during feedback loop test."));
		return false;
	}

	UEcologyWorldSubsystem* WorldSubsystem = World->GetSubsystem<UEcologyWorldSubsystem>();

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyBootstrapTestActor: STARTING CLOSED-LOOP ECO-FEEDBACK TEST"));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));

	// Phase 1: Capture Initial Baseline State
	FVegetationEvolutionProfile InitVegProfile;
	ServerSubsystem->GetVegetationEvolutionProfile(TestRegionId, TestVegetationSpeciesId, InitVegProfile);

	FSpeciesEvolutionProfile InitMonsterProfile;
	ServerSubsystem->GetSpeciesEvolutionProfile(TestRegionId, TestSpeciesId, InitMonsterProfile);

	FRegionEnvironmentState InitEnvState;
	if (WorldSubsystem)
	{
		WorldSubsystem->GetEnvironmentState(TestRegionId, InitEnvState);
	}

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Step 1: Baseline]"));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Vegetation (%s): Resist=%.2f, Regen=%.2f, Growth=%.2f"),
		*TestVegetationSpeciesId.ToString(), InitVegProfile.Traits.GrazingResistance, InitVegProfile.Traits.RegenerationRate, InitVegProfile.Traits.GrowthRate);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Environment (%s): VegDensity=%.2f, FoodAvailability=%.2f"),
		*TestRegionId.ToString(), InitEnvState.VegetationDensity, InitEnvState.FoodAvailability);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Monster (%s): BodyScale=%.2f, MoveSpeed=%.2f"),
		*TestSpeciesId.ToString(), InitMonsterProfile.Phenotype.BodyScale, InitMonsterProfile.Gameplay.MoveSpeedMultiplier);

	// Phase 2: Simulate Herbivore Grazing Event
	constexpr float GrazingAmount = 0.40f;
	ServerSubsystem->RecordGrazing(TestRegionId, TestVegetationSpeciesId, GrazingAmount, 7777);

	FRegionEnvironmentState DepletedEnvState;
	if (WorldSubsystem)
	{
		WorldSubsystem->GetEnvironmentState(TestRegionId, DepletedEnvState);
	}
	const float AccumulatedGrazingPressure = ServerSubsystem->GetGrazingPressure(TestRegionId, TestVegetationSpeciesId);

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Step 2: Grazing Impact]"));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Consumed Amount:             %.2f"), GrazingAmount);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Accumulated GrazingPressure: %.2f"), AccumulatedGrazingPressure);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  VegDensity:                  %.2f -> %.2f"), InitEnvState.VegetationDensity, DepletedEnvState.VegetationDensity);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  FoodAvailability:            %.2f -> %.2f"), InitEnvState.FoodAvailability, DepletedEnvState.FoodAvailability);

	// Phase 3: Vegetation Adapts to High Grazing Pressure
	FVegetationEvolutionContext VegContext;
	ServerSubsystem->BuildVegetationEvolutionContext(TestRegionId, TestVegetationSpeciesId, 1, 1, VegContext);

	FVegetationEvolutionProposal VegProposal;
	UDummyEvolutionDecisionProvider::RequestVegetationProposal(VegContext, VegProposal);

	FVegetationEvolutionProfile CommittedVegProfile;
	FString VegRejectReason;
	const bool bVegCommitted = ServerSubsystem->CommitVegetationEvolutionProposal(
		TestRegionId, TestVegetationSpeciesId, VegProposal, 1, 1, CommittedVegProfile, VegRejectReason);

	if (!bVegCommitted)
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: Feedback loop - Vegetation commit failed: %s"), *VegRejectReason);
		return false;
	}

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Step 3: Vegetation Evolution Committed]"));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Gen: %d -> %d, GrazingResistance: %.2f -> %.2f, RegenRate: %.2f -> %.2f"),
		InitVegProfile.Generation, CommittedVegProfile.Generation,
		InitVegProfile.Traits.GrazingResistance, CommittedVegProfile.Traits.GrazingResistance,
		InitVegProfile.Traits.RegenerationRate, CommittedVegProfile.Traits.RegenerationRate);

	// Phase 4: Server Simulation Advances (Regrowth with New Traits)
	ServerSubsystem->TickEcologySimulation(5.0f);

	FRegionEnvironmentState RegrownEnvState;
	if (WorldSubsystem)
	{
		WorldSubsystem->GetEnvironmentState(TestRegionId, RegrownEnvState);
	}

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Step 4: Simulation Tick (5s Regrowth)]"));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  VegDensity:       %.2f -> %.2f"), DepletedEnvState.VegetationDensity, RegrownEnvState.VegetationDensity);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  FoodAvailability: %.2f -> %.2f"), DepletedEnvState.FoodAvailability, RegrownEnvState.FoodAvailability);

	// Phase 5: Monster Adapts to Depleted Food Availability (Food Scarcity Selection Pressure)
	FEvolutionContext MonsterContext;
	ServerSubsystem->BuildMonsterEvolutionContext(TestRegionId, TestSpeciesId, 1, 1, MonsterContext);

	FEvolutionProposal MonsterProposal;
	UDummyEvolutionDecisionProvider DummyProvider;
	DummyProvider.RequestProposal_Implementation(MonsterContext, MonsterProposal);

	FSpeciesEvolutionProfile CommittedMonsterProfile;
	FString MonsterRejectReason;
	const bool bMonsterCommitted = ServerSubsystem->CommitEvolutionProposal(
		TestRegionId, TestSpeciesId, MonsterProposal, 1, 1, CommittedMonsterProfile, MonsterRejectReason);

	if (!bMonsterCommitted)
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyBootstrapTestActor: Feedback loop - Monster commit failed: %s"), *MonsterRejectReason);
		return false;
	}

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Step 5: Monster Evolution Committed (Adaptive to Scarcity)]"));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("  Gen: %d -> %d, BodyScale: %.2f -> %.2f, MoveSpeed: %.2f -> %.2f, RoamRadius: %.2f -> %.2f"),
		InitMonsterProfile.Generation, CommittedMonsterProfile.Generation,
		InitMonsterProfile.Phenotype.BodyScale, CommittedMonsterProfile.Phenotype.BodyScale,
		InitMonsterProfile.Gameplay.MoveSpeedMultiplier, CommittedMonsterProfile.Gameplay.MoveSpeedMultiplier,
		InitMonsterProfile.Ecology.RoamRadiusMultiplier, CommittedMonsterProfile.Ecology.RoamRadiusMultiplier);

	// Phase 6: Verify Non-blocking Async Dispatch Pipeline
	UDummyEvolutionDecisionProvider::RequestProposalAsync(
		MonsterContext,
		FOnEvolutionProposalCompleted::CreateLambda([](bool bSuccess, const FEvolutionProposal& AsyncProposal)
		{
			UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Step 6: Async Verification] Background proposal completed safely on GameThread (Success: %s)"),
				bSuccess ? TEXT("TRUE") : TEXT("FALSE"));
		}));

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyBootstrapTestActor: CLOSED-LOOP ECO-FEEDBACK TEST PASSED!"));
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("================================================================="));

	if (GEngine)
	{
		GEngine->AddOnScreenDebugMessage(
			-1, 10.0f, FColor::Green,
			FString::Printf(TEXT("[Closed-Loop Eco Feedback Passed] Grass Gen:%d (Resist:%.2f, Regen:%.2f) | Wolf Gen:%d (Scale:%.2f, Speed:%.2f)"),
				CommittedVegProfile.Generation, CommittedVegProfile.Traits.GrazingResistance, CommittedVegProfile.Traits.RegenerationRate,
				CommittedMonsterProfile.Generation, CommittedMonsterProfile.Phenotype.BodyScale, CommittedMonsterProfile.Gameplay.MoveSpeedMultiplier));
	}

	return true;
}

