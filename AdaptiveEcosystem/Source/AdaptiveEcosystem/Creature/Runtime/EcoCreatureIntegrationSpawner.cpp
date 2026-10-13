#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Creature/Audio/EcoFootstepAudioComponent.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Creature/Runtime/EcoCreatureNetworkTrait.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EcoMassMigration.h"
#include "Mass/EcoMassNetworkBootstrap.h"
#include "Mass/EcoMassNetworkSubsystem.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityTemplate.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "MassCommandBuffer.h"
#include "MassMovementFragments.h"
#include "Network/EcoGameState.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcoWorldClockSubsystem.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "HAL/PlatformMisc.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Components/WorldPartitionStreamingSourceComponent.h"

AEcoCreatureIntegrationGameMode::AEcoCreatureIntegrationGameMode() { GameStateClass = AEcoGameState::StaticClass(); }
void AEcoCreatureIntegrationGameMode::InitGameState()
{
	Super::InitGameState();
	if (auto* State = GetGameState<AEcoGameState>()) State->InitializeAuthorityState(FMath::Max(1, int32(GetTypeHash(FGuid::NewGuid()) & MAX_int32)), 8);
}

AEcoCreatureIntegrationSpawner::AEcoCreatureIntegrationSpawner()
{
	// Mass phases share actor tick groups and may hold observers locked while their
	// parallel work finishes. Reconcile at OnWorldPostActorTick, after all phases.
	PrimaryActorTick.bCanEverTick = false;
	Groups.AddDefaulted();
	HerbivoreActorClass = AEcoHerbivoreRepresentation::StaticClass();
	WolfActorClass = AEcoWolfRepresentation::StaticClass();
	HabitatStreamingSource = CreateDefaultSubobject<UWorldPartitionStreamingSourceComponent>(TEXT("HabitatStreamingSource"));
	HabitatStreamingSource->DisableStreamingSource();
}

void AEcoCreatureIntegrationSpawner::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	if (GetWorld() && GetWorld()->IsGameWorld()) RegisterTemplates();
}

bool AEcoCreatureIntegrationSpawner::RegisterTemplates()
{
	const auto* Network = GetWorld()->GetSubsystem<UEcoMassNetworkSubsystem>();
	if (!Network || !Network->IsBubbleInfoClassRegistered()) return false;
	for (UMassEntityConfigAsset* Config : {HerbivoreConfig.Get(), WolfConfig.Get()})
	{
		if (!Config || !Config->FindTrait(UEcoCreatureNetworkTrait::StaticClass())) return false;
		const auto& Template = Config->GetOrCreateEntityTemplate(*GetWorld());
		if (!Template.IsValid()) return false;
		UE_LOG(LogTemp, Log, TEXT("[Eco Integration] Template=%s Config=%s NetMode=%d"),
			*Template.GetTemplateID().ToString(), *Config->GetPathName(), int32(GetNetMode()));
	}
	return true;
}

void AEcoCreatureIntegrationSpawner::BeginPlay()
{
	Super::BeginPlay();
	PostTickHandle = FWorldDelegates::OnWorldPostActorTick.AddUObject(this, &AEcoCreatureIntegrationSpawner::OnWorldPostActorTick);
	StartedAt = GetWorld()->GetTimeSeconds();
#if WITH_DEV_AUTOMATION_TESTS
	FParse::Value(FCommandLine::Get(), TEXT("EcoIntegrationExitAfter="), TestExitAfter);
	FParse::Value(FCommandLine::Get(), TEXT("EcoIntegrationCaptureAt="), TestCaptureAt);
	bTestObserverCycle = TestExitAfter > 0 && FParse::Param(FCommandLine::Get(), TEXT("EcoIntegrationObserverCycle"));
#endif
	for (TActorIterator<AEcologyRegion> It(GetWorld()); It; ++It) Regions.Add(*It);
	Regions.Sort([](const AEcologyRegion& A, const AEcologyRegion& B) { return A.RegionId.LexicalLess(B.RegionId); });
	if (!RegisterTemplates()) { UE_LOG(LogTemp, Error, TEXT("[Eco Integration] Missing creature configs/bubble registration.")); return; }
	if (GetNetMode() == NM_Client) { HabitatStreamingSource->DisableStreamingSource(); bReady = true; return; }
	if (bUseHabitatStreaming)
	{
		if (!FMath::IsFinite(HabitatStreamingRadius) || HabitatStreamingRadius < 3000.0f)
		{ FailRuntime(TEXT("Invalid habitat streaming radius")); return; }
		UpdateHabitatStreaming();
		HabitatStreamingSource->EnableStreamingSource();
		bWaitingForHabitat = true;
		UE_LOG(LogTemp, Log, TEXT("[Eco Integration] Waiting for authored habitat collision streaming."));
	}
	else if (!(bReady = StartAuthority())) FailRuntime(TEXT("Authority initialization"));
}

void AEcoCreatureIntegrationSpawner::UpdateHabitatStreaming()
{
	if (GetNetMode() == NM_Client || !bUseHabitatStreaming) return;
	HabitatStreamingSource->Shapes.Reset();
	auto AddPoint = [&](const FVector& Point)
	{
		if (Point.ContainsNaN()) return;
		FStreamingSourceShape& Shape = HabitatStreamingSource->Shapes.AddDefaulted_GetRef();
		Shape.bUseGridLoadingRange = false;
		Shape.Radius = HabitatStreamingRadius;
		Shape.Location = GetActorTransform().InverseTransformPosition(Point);
	};
	// Keep authored arrivals available for migration, plus current logical positions.
	for (const AEcologyRegion* Region : Regions) AddPoint(Region->GetActorTransform().TransformPosition(Region->ArrivalOffset));
	if (Owned.IsEmpty())
	{
		for (const auto& Group : Groups)
		{
			for (const FVector& Point : Group.HerbivoreSpawnPoints) AddPoint(Point);
			for (const FVector& Point : Group.WolfSpawnPoints) AddPoint(Point);
		}
	}
	else if (auto* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>())
	{
		const auto& EM = Spawner->GetEntityManagerChecked();
		for (const auto E : Owned) if (EM.IsEntityValid(E)) AddPoint(EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation());
	}
}

bool AEcoCreatureIntegrationSpawner::BuildSpawnPositions(const FEcoCreatureSpawnGroup& Group, int32 Count, bool bPredator, TArray<FVector>& Out) const
{
	Out.Reset();
	const auto Found = Regions.FindByPredicate([&](const AEcologyRegion* R) { return R->RegionId == Group.RegionId; });
	if (!Found || Count < 0) return false;
	const auto& Authored = bPredator ? Group.WolfSpawnPoints : Group.HerbivoreSpawnPoints;
	if (!Authored.IsEmpty() && Authored.Num() < Count) return false;
	for (int32 I = 0; I < Count; ++I)
	{
		const double Angle = (I + (bPredator ? 2 : 0)) * 2.399963;
		const FVector Hint = Authored.IsEmpty() ? (*Found)->GetActorLocation()
			+ FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0) * (bPredator ? 1600 : 600) : Authored[I];
		FVector Ground;
		if (!EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Hint, Ground) || !(*Found)->ContainsPosition(Ground))
		{
			UE_LOG(LogTemp, Error, TEXT("[Eco Integration] Invalid spawn ground Region=%s Predator=%d Candidate=%d Hint=%s"),
				*Group.RegionId.ToString(), bPredator, I, *Hint.ToCompactString());
			return false;
		}
		Out.Add(Ground);
	}
	return true;
}

bool AEcoCreatureIntegrationSpawner::StartAuthority()
{
	auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
	auto* Registry = GetWorld()->GetSubsystem<UEcoWorldProviderRegistry>();
	if (!Ecology || !Clock || !Registry || Clock->IsClockRunning() || Regions.IsEmpty()
		|| Groups.IsEmpty() || GlobalPopulationLimit < 1 || GlobalPopulationLimit > 512
		|| !FMath::IsFinite(EnergyDrainPerSecond) || EnergyDrainPerSecond < 0
		|| !FMath::IsFinite(EnergyPerFood) || EnergyPerFood < 0 || !Migration.IsValid()) return false;
	for (TActorIterator<AEcoMassNetworkBootstrap> It(GetWorld()); It; ++It)
	{ UE_LOG(LogTemp, Error, TEXT("[Eco Integration] Use a separate level; M3 Bootstrap cannot share this coordinator.")); return false; }
	for (TActorIterator<AEcoCreatureIntegrationSpawner> It(GetWorld()); It; ++It)
	{ if (*It != this) { UE_LOG(LogTemp, Error, TEXT("[Eco Integration] Only one coordinator is allowed.")); return false; } }
	int64 Total = 0; TSet<FName> GroupIds;
	for (const auto& Group : Groups)
	{
		if (Group.RegionId.IsNone() || GroupIds.Contains(Group.RegionId) || Group.Herbivores < 0 || Group.Wolves < 0 || !Group.Schedule.IsValid()) return false;
		GroupIds.Add(Group.RegionId); Total += int64(Group.Herbivores) + Group.Wolves;
		if (!Regions.ContainsByPredicate([&](const AEcologyRegion* R) { return R->RegionId == Group.RegionId; })) return false;
		if (Group.bUseFoodPatchPosition && (Group.FoodPatchPosition.ContainsNaN()
			|| !(*Regions.FindByPredicate([&](const AEcologyRegion* R) { return R->RegionId == Group.RegionId; }))->ContainsPosition(Group.FoodPatchPosition))) return false;
	}
	if (Total > GlobalPopulationLimit || !HerbivoreActorClass || !WolfActorClass) return false;
	// Validate every habitat before starting clock/resources or creating any Entity.
	for (const auto& Group : Groups)
	{
		TArray<FVector> Positions;
		if (!BuildSpawnPositions(Group, Group.Herbivores, false, Positions)
			|| !BuildSpawnPositions(Group, Group.Wolves, true, Positions)) return false;
	}
	if (!Ecology->ConfigurePopulationLimit(GlobalPopulationLimit)) return false;
	for (AEcologyRegion* Region : Regions)
	{
		FRegionEcologyState State;
		if (!Region->MakeInitialEcologyState(State) || !Ecology->RegisterRegionState(State)) return false;
		GetWorld()->GetSubsystem<UEcologyWorldSubsystem>()->RegisterRegion(Region);
	}
	for (const auto& Group : Groups) if (!Ecology->RegisterSpawnSchedule(Group.RegionId, Group.Schedule)) return false;
	auto* GameState = GetWorld()->GetGameState<AEcoGameState>();
	if (!GameState) return false;
	FEcoFoodEventSettings Day, Night; Day.bEnabled = Night.bEnabled = false;
	if (!Clock->StartClock(GameState->GetWorldEpoch(), DaySeconds, NightSeconds)
		|| !Ecology->StartResourceSimulation(GameState->GetWorldEpoch(), Day, Night, true)) return false;
	Registry->SetFoodProvider(this); Registry->SetCoverProvider(this);
	for (const auto& Group : Groups)
	{
		FEcoSpawnRequest Request;
		if (!Ecology->RequestInitialSpawn(Group.RegionId, Group.Herbivores + Group.Wolves, Clock->GetServerTime(), Request)) return false;
		const int32 Actual = Spawn(Group.RegionId, Group.Herbivores, false) + Spawn(Group.RegionId, Group.Wolves, true);
		PublishSummary(); // Commit population before releasing this group's spawn reservation.
		if (!Ecology->CompleteSpawnRequest(Request.RequestId, Actual) || Actual != Request.Count) return false;
	}
	GameState->SetMassReplicationReady(true); GameState->SetWorldPhase(EEcoWorldPhase::Running);
	UE_LOG(LogTemp, Log, TEXT("[Eco Integration] Authority ready: Agents=%d Regions=%d PPO+Social+MassBubble"), Owned.Num(), Regions.Num());
	return true;
}

int32 AEcoCreatureIntegrationSpawner::Spawn(FName RegionId, int32 Count, bool bPredator)
{
	if (GetNetMode() == NM_Client || Count <= 0) return 0;
	auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	auto* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>();
	const auto Found = Regions.FindByPredicate([&](const AEcologyRegion* R) { return R->RegionId == RegionId; });
	if (!Ecology || !Spawner || !Found) return 0;
	TArray<FVector> Positions;
	const auto* Group = Groups.FindByPredicate([&](const FEcoCreatureSpawnGroup& G) { return G.RegionId == RegionId; });
	if (!Group || !BuildSpawnPositions(*Group, Count, bPredator, Positions)) return 0;
	auto& EM = Spawner->GetEntityManagerChecked();
	TArray<FMassEntityHandle> Entities;
	const auto& Template = (bPredator ? WolfConfig : HerbivoreConfig)->GetOrCreateEntityTemplate(*GetWorld());
	auto Creation = Spawner->SpawnEntities(Template, Count, Entities);
	const FName Species = bPredator ? FName(TEXT("Wolf")) : FName(TEXT("Herbivore"));
	const int32 SpeciesIndex = Ecology->RegisterSpecies(Species);
	for (int32 I = 0; I < Entities.Num(); ++I)
	{
		auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entities[I]);
		Id.StableAgentId = Ecology->AllocateStableAgentId(); Id.SpeciesId = Species; Id.SpeciesRuntimeIndex = SpeciesIndex;
		auto& Membership = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entities[I]);
		Membership.CurrentRegionId = RegionId; Membership.CurrentRegionIndex = Ecology->GetRegionRuntimeIndex(RegionId);
		const double A = (I + (bPredator ? 2 : 0)) * 2.399963;
		const FVector Position = Positions[I];
		EM.GetFragmentDataChecked<FTransformFragment>(Entities[I]).GetMutableTransform() = FTransform(FRotator(0, FMath::RadiansToDegrees(A), 0), Position);
		Owned.Add(Entities[I]);
		UE_LOG(LogTemp, Log, TEXT("[Eco Integration][Spawn] Id=%lld Region=%s Species=%s Ground=%s"),
			Id.StableAgentId, *RegionId.ToString(), *Species.ToString(), *Position.ToCompactString());
	}
	Creation.Reset();
	return Entities.Num();
}

AEcologyRegion* AEcoCreatureIntegrationSpawner::FindRegion(const FVector& Position) const
{
	for (AEcologyRegion* Region : Regions) if (Region && Region->ContainsPosition(Position)) return Region;
	return nullptr;
}

float AEcoCreatureIntegrationSpawner::GetFoodDensity(const FVector& Position, float Radius) const
{
	const auto* Region = FindRegion(Position);
	const auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	FRegionEcologyState State;
	if (!Region || !Ecology || !Ecology->GetRegionState(Region->RegionId, State) || State.FoodCapacity <= 0) return 0;
	const auto* Group = Groups.FindByPredicate([&](const FEcoCreatureSpawnGroup& G) { return G.RegionId == Region->RegionId; });
	const FVector Patch = Group && Group->bUseFoodPatchPosition ? Group->FoodPatchPosition : Region->GetActorLocation() + FVector(1000, 1000, 0);
	return FMath::Clamp(State.FoodAmount / State.FoodCapacity, 0.f, 1.f)
		* (0.3f + 0.7f * FMath::Exp(-FVector::DistSquared2D(Position, Patch) / FMath::Square(2500.f)));
}
FVector AEcoCreatureIntegrationSpawner::GetFoodGradient(const FVector& P, float Radius) const
{
	const float H = FMath::Max(100.f, Radius * 0.2f);
	return FVector(GetFoodDensity(P + FVector(H,0,0), H) - GetFoodDensity(P - FVector(H,0,0), H),
		GetFoodDensity(P + FVector(0,H,0), H) - GetFoodDensity(P - FVector(0,H,0), H), 0).GetSafeNormal();
}
float AEcoCreatureIntegrationSpawner::ConsumeFood(const FVector&, float)
{
	// Mutation is exclusively the sorted, batched resource transaction in Reconcile.
	return 0;
}
float AEcoCreatureIntegrationSpawner::GetRecentPredation(const FVector& P) const
{
	const auto* Region = FindRegion(P); const auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	return Region && Ecology ? Ecology->GetPredationHistory(Region->RegionId) : 0;
}
float AEcoCreatureIntegrationSpawner::GetCoverDistance(const FVector& P) const
{
	float Best = MAX_flt;
	if (auto* Shelters = GetWorld()->GetSubsystem<UEcoShelterSubsystem>())
		for (const auto& S : Shelters->GetShelters()) if (Shelters->IsValidShelterIndex(S.RuntimeIndex)) Best = FMath::Min(Best, float(FVector::Dist2D(P, S.Position) - S.Radius));
	return FMath::Max(0.f, Best);
}
FVector AEcoCreatureIntegrationSpawner::GetCoverDirection(const FVector& P) const
{
	float Best = MAX_flt; FVector Dir = FVector::ZeroVector;
	if (auto* Shelters = GetWorld()->GetSubsystem<UEcoShelterSubsystem>())
		for (const auto& S : Shelters->GetShelters()) if (Shelters->IsValidShelterIndex(S.RuntimeIndex))
		{ const float D = FVector::Dist2D(P, S.Position) - S.Radius; if (D < Best) { Best = D; Dir = S.Position - P; } }
	return Best <= 0 ? FVector::ZeroVector : Dir.GetSafeNormal2D();
}
bool AEcoCreatureIntegrationSpawner::IsInCover(const FVector& P) const { return GetCoverDistance(P) <= 0; }

void AEcoCreatureIntegrationSpawner::Reconcile(float Delta)
{
	auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	if (EM.IsProcessing() || !Clock->AdvanceClock(Delta)) return;
	const auto Time = Clock->GetServerTime();
	const double Now = Time.ServerTimeSeconds;
	TArray<FMassEntityHandle> Remove;
	for (const auto E : Owned)
	{
		if (!EM.IsEntityValid(E)) { Remove.Add(E); continue; }
		auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		auto& Life = EM.GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(E);
		if (V.HP <= 0 && Life.DeathTime < 0)
		{
			Life.DeathTime = Now;
			const bool bPredated = Life.bPredated;
			const int64 StableId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId;
			if (auto* Shelter = GetWorld()->GetSubsystem<UEcoShelterSubsystem>()) Shelter->ReleaseAgentReservations(StableId);
			EM.RemoveTagFromEntity(E, FEcoAliveTag::StaticStruct());
			if (bPredated)
			{
				FEcoPredationEvent Event; Event.RegionId = EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId;
				Event.PreyStableAgentId = StableId; Ecology->ApplyPredationEvent(Event);
			}
		}
		// Removing Alive moves the entity to another archetype: reacquire fragment references.
		const double DeathTime = EM.GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(E).DeathTime;
		if (DeathTime >= 0 && Now - DeathTime >= 2.0) Remove.Add(E);
	}
	// All Mass phase completion events have finished at this world boundary. Notify
	// replication destruction observers while the original storage is still available.
	TArray<FMassEntityHandle> ValidRemove;
	for (const auto E : Remove) { if (EM.IsEntityValid(E)) ValidRemove.Add(E); Owned.Remove(E); }
	if (!ValidRemove.IsEmpty()) EM.BatchDestroyEntities(ValidRemove);
	if (Now - LastResourceTime >= 1.0)
	{
		const double Elapsed = Now - LastResourceTime; LastResourceTime = Now;
		Ecology->TickSimulation(float(Elapsed)); // Authoritative resource regeneration/history decay.
		TArray<FEcoFeedRequest> Requests;
		if (!Ecology->BeginResourceStep(Time, ++Step)) { FailRuntime(TEXT("BeginResourceStep")); return; }
		for (const auto E : Owned)
		{
			auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
			const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
			if (V.HP <= 0 || Id.SpeciesId != TEXT("Herbivore")) continue;
			V.Energy = FMath::Max(0.f, V.Energy - float(Elapsed) * EnergyDrainPerSecond);
			if (V.Energy <= 0) V.HP = FMath::Max(0.f, V.HP - float(Elapsed) * 5.f);
			const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(E);
			const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(E);
			if (V.HP <= 0 || Travel.State != EEcoResidenceState::Resident) continue;
			const float Density = GetFoodDensity(EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation(), 200);
			const auto& SocialRequest = EM.GetFragmentDataChecked<FEcoSocialMovementRequestFragment>(E);
			const float Forage = SocialRequest.bValid ? SocialRequest.EffectiveAction.Forage : EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action.Forage;
			const float Amount = Forage * Density * float(Elapsed);
			if (Amount <= 0) continue;
			auto& Req = Requests.AddDefaulted_GetRef(); Req.WorldEpoch = Time.WorldEpoch; Req.StepId = Step; Req.DueTime = Now;
			Req.RegionIndex = Region.CurrentRegionIndex; Req.Food.RegionId = Region.CurrentRegionId;
			Req.Food.StableAgentId = Id.StableAgentId; Req.Food.RequestedAmount = Amount;
		}
		TArray<FEcoFeedResult> Results;
		if (!Ecology->ResolveFeeding(Requests, Results)) { FailRuntime(TEXT("ResolveFeeding")); return; }
		if (!Ecology->CompleteResourceStep()) { FailRuntime(TEXT("CompleteResourceStep")); return; }
		for (const auto& Result : Results) for (const auto E : Owned)
			if (EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId == Result.Request.Food.StableAgentId)
			{ auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E); V.Energy = FMath::Min(V.MaxEnergy, V.Energy + float(Result.GrantedAmount) * EnergyPerFood); break; }
		TArray<FName> RegionIds; Ecology->GetRegionIds(RegionIds);
		TArray<FEcoResourceSnapshot> Resources; Ecology->GetResourceSnapshots(Resources);
		TArray<FEcoRegionSpatialSnapshot> Spaces;
		if (!GetWorld()->GetSubsystem<UEcologyWorldSubsystem>()->BuildSpatialSnapshots(RegionIds, Spaces)) { FailRuntime(TEXT("BuildSpatialSnapshots")); return; }
		if (!EcoMassMigration::Reconcile(EM, Time, Now, Step, Resources, Spaces, Migration, true, 1.0, false)) { FailRuntime(TEXT("MigrationReconcile")); return; }
		PublishSummary();
		if (bEnableWaves) for (const auto& G : Groups)
		{
			FEcoSpawnRequest Request;
			while (Ecology->PollSpawnWave(G.RegionId, Time, Request))
			{ const int32 Actual = Spawn(G.RegionId, Request.Count, false); PublishSummary(); Ecology->CompleteSpawnRequest(Request.RequestId, Actual); }
		}
	}
	for (const auto E : Owned)
	{
		const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		const auto& Life = EM.GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(E);
		auto& Present = EM.GetFragmentDataChecked<FEcoCreaturePresentationFragment>(E);
		Present.Velocity = V.HP > 0 ? EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value : FVector::ZeroVector;
		const auto* Predator = EM.GetFragmentDataPtr<FEcoPredatorStateFragment>(E);
		Present.Flags = (V.HP > 0 ? 1 : 0) | (Predator && Predator->EatCooldown > 0 ? 2 : 0) | (Life.bPursuing ? 4 : 0) | 8;
		Present.Health = uint8(FMath::Clamp(V.HP / FMath::Max(V.MaxHP, 1.f), 0.f, 1.f) * 255);
		Present.Energy = uint8(FMath::Clamp(V.Energy / FMath::Max(V.MaxEnergy, 1.f), 0.f, 1.f) * 255);
		// Observe the single movement writer's completed result. Never move the agent here.
		auto& Cadence = EM.GetFragmentDataChecked<FEcoCreatureFootstepFragment>(E).Cadence;
		if (FootstepAudioSet && FootstepAudioSet->IsValidConfiguration())
		{
			const FVector Position = EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
			const float Speed = Present.Velocity.Size2D();
			if (Cadence.Advance(Position, Speed, V.HP > 0, Delta, FootstepAudioSet->GetStride(Speed), FootstepAudioSet->MinimumSpeed))
				if (auto* Noise = GetWorld()->GetSubsystem<UEcoNoiseSubsystem>())
				{
					const auto& Identity = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
					const float Loudness = FMath::Lerp(0.45f, 1.f, FMath::Clamp((Speed - 250.f) / 650.f, 0.f, 1.f));
					Noise->ReportCreatureFootstep(Position, Loudness, FootstepAudioSet->NoiseRange,
						Identity.SpeciesId == TEXT("Wolf") ? FootstepAudioSet->PredatorThreat : 0.f,
						Identity.StableAgentId, Identity.SpeciesId);
				}
		}
		else Cadence.Reset();
	}
}

void AEcoCreatureIntegrationSpawner::PublishSummary()
{
	auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	FEcoCompletedWorldSummary Summary; Summary.Time = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime();
	Summary.StepId = Step; Summary.Revision = int32(Step);
	for (AEcologyRegion* Region : Regions)
	{
		FEcoRegionPopulationSnapshot Metrics; Metrics.RegionId = Region->RegionId;
		for (const auto E : Owned)
		{
			const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
			if (V.HP <= 0 || EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId != Region->RegionId) continue;
			++Metrics.Population; Metrics.AverageEnergy += V.Energy / FMath::Max(V.MaxEnergy, 1.f);
			const auto Mode = EM.GetFragmentDataChecked<FEcoTravelFragment>(E).State;
			Metrics.TravelingCount += Mode == EEcoResidenceState::Traveling; Metrics.WaitingCount += Mode == EEcoResidenceState::WaitingForFood;
		}
		Metrics.AverageEnergy /= FMath::Max(Metrics.Population, 1); Ecology->UpdatePopulationMetrics(Metrics);
		FRegionEcologyState State; Ecology->GetRegionState(Region->RegionId, State);
		auto& Row = Summary.Regions.AddDefaulted_GetRef(); Row.RegionId = Region->RegionId; Row.WorldEpoch = Summary.Time.WorldEpoch;
		Row.SummaryRevision = Summary.Revision; Row.Population = Metrics.Population; Row.AverageEnergy = Metrics.AverageEnergy;
		Row.FoodAmount = State.FoodAmount; Row.FoodCapacity = State.FoodCapacity; Row.PredationHistory = State.PredationHistory;
		Row.TravelingCount = Metrics.TravelingCount; Row.WaitingCount = Metrics.WaitingCount;
	}
	if (Step > 0) GetWorld()->GetGameState<AEcoGameState>()->PublishEcologySummary(Summary);
}

void AEcoCreatureIntegrationSpawner::SyncVisuals(float Delta)
{
	if (GetNetMode() == NM_DedicatedServer) return;
	auto* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>(); if (!Spawner) return;
	auto& EM = Spawner->GetEntityManagerChecked();
	struct FInput { int64 Id; FName Species; FName Region; FVector Position; FEcoCreaturePresentationFragment Visual; };
	TArray<FInput> Inputs;
	FMassEntityQuery Query(EM.AsShared());
	Query.AddTagRequirement<FEcoIntegratedCreatureTag>(EMassFragmentPresence::All);
	Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoCreaturePresentationFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Query.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	FMassExecutionContext Context = EM.CreateExecutionContext(Delta);
	Query.ForEachEntityChunk(Context, [this, &Inputs](FMassExecutionContext& Chunk)
	{
		if (GetNetMode() == NM_Client && (!Chunk.GetFragmentView<FEcoVitalsFragment>().IsEmpty() || !Chunk.GetFragmentView<FEcoPolicyOutputFragment>().IsEmpty()))
		{ UE_LOG(LogTemp, Error, TEXT("[Eco Integration] Client proxy contains authoritative fragments.")); bReady = false; return; }
		const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>(); const auto Positions = Chunk.GetFragmentView<FTransformFragment>();
		const auto Views = Chunk.GetFragmentView<FEcoCreaturePresentationFragment>();
		const auto Membership = Chunk.GetFragmentView<FEcoRegionFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I) if (Ids[I].StableAgentId > 0)
			Inputs.Add({Ids[I].StableAgentId, Ids[I].SpeciesId, Membership[I].CurrentRegionId, Positions[I].GetTransform().GetLocation(), Views[I]});
	});
	TSet<int64> Seen;
	for (const auto& Input : Inputs)
	{
		if (Seen.Contains(Input.Id)) continue; Seen.Add(Input.Id);
		auto& Binding = Visuals.FindOrAdd(Input.Id);
		if (!Binding.Actor.IsValid())
		{
			const auto Class = Input.Species == TEXT("Wolf") ? WolfActorClass : HerbivoreActorClass;
			FActorSpawnParameters Params; Params.Owner = this; Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			auto* Actor = GetWorld()->SpawnActor<AEcoCreatureRepresentationActor>(Class, Input.Position, FRotator::ZeroRotator, Params);
			if (!Actor || !Actor->BindIdentity(Input.Id, Input.Species)) { if (Actor) Actor->Destroy(); continue; }
			Binding.Actor = Actor; Binding.Sequence = 0;
		}
		FEcoCreatureVisualState State; State.StableAgentId = Input.Id; State.SpeciesId = Input.Species;
		State.RegionId = Input.Region;
		State.Sequence = ++Binding.Sequence; State.WorldTime = GetWorld()->GetTimeSeconds(); State.Position = Input.Position;
		if (GetNetMode() == NM_Client && Binding.Sequence > 1 && FVector::DistSquared(Binding.Actor->GetActorLocation(), State.Position) < FMath::Square(2500.f))
			State.Position = FMath::VInterpTo(Binding.Actor->GetActorLocation(), State.Position, Delta, 12.f);
		State.Velocity = Input.Visual.Velocity; State.bAlive = (Input.Visual.Flags & 1) != 0;
		State.bEating = (Input.Visual.Flags & 2) != 0; State.bPursuingPrey = (Input.Visual.Flags & 4) != 0;
		State.bHasVitals = (Input.Visual.Flags & 8) != 0; State.NormalizedHealth = Input.Visual.Health / 255.f; State.NormalizedEnergy = Input.Visual.Energy / 255.f;
		Binding.Actor->Footsteps->AudioSet = FootstepAudioSet;
		Binding.Actor->ConsumeVisualState(State, Delta);
	}
	for (auto It = Visuals.CreateIterator(); It; ++It) if (!Seen.Contains(It.Key()))
	{ if (auto* Actor = It.Value().Actor.Get()) { Actor->ClearBinding(); Actor->Destroy(); } It.RemoveCurrent(); }
}

void AEcoCreatureIntegrationSpawner::Tick(float Delta)
{
	Super::Tick(Delta);
#if WITH_DEV_AUTOMATION_TESTS
	// Test watchdog must also exit after a failed runtime initialization/transaction.
	if (TestExitAfter > 0 && GetWorld()->GetTimeSeconds() - StartedAt >= TestExitAfter)
	{ UE_LOG(LogTemp, Log, TEXT("[Eco Integration] Test duration completed; Ready=%d Step=%lld."), bReady, Step); FPlatformMisc::RequestExit(false); }
	if (TestCaptureAt > 0 && GetWorld()->GetTimeSeconds() - StartedAt >= TestCaptureAt)
	{
		TestCaptureAt = 0;
		if (auto* Player = GetWorld()->GetFirstPlayerController())
		{
			FVector View; FRotator Rotation; Player->GetPlayerViewPoint(View, Rotation);
			UE_LOG(LogTemp, Log, TEXT("[Eco Integration][Capture] Pawn=%s View=%s Rotation=%s"), *GetNameSafe(Player->GetPawn()), *View.ToCompactString(), *Rotation.ToCompactString());
			Player->ConsoleCommand(TEXT("HighResShot 1280x720"));
		}
	}
#endif
	if (bWaitingForHabitat)
	{
		if (GetWorld()->GetTimeSeconds() - StartedAt > 30.0)
		{ bWaitingForHabitat = false; FailRuntime(TEXT("Habitat streaming timeout")); return; }
		if (GetWorld()->GetTimeSeconds() - StartedAt < 0.25 || !HabitatStreamingSource->IsStreamingCompleted()) return;
		bWaitingForHabitat = false;
		if (!(bReady = StartAuthority())) { FailRuntime(TEXT("Authority initialization after habitat streaming")); return; }
	}
	if (!bReady || !FMath::IsFinite(Delta) || Delta <= 0) return;
	if (bUseHabitatStreaming && GetNetMode() != NM_Client && GetWorld()->GetTimeSeconds() >= NextStreamingUpdate)
	{ NextStreamingUpdate = GetWorld()->GetTimeSeconds() + 1.0; UpdateHabitatStreaming(); }
	if (GetNetMode() != NM_Client) Reconcile(Delta);
	SyncVisuals(Delta);
#if WITH_DEV_AUTOMATION_TESTS
	if (bTestObserverCycle) UpdateTestObserver();
#endif
	if (GetWorld()->GetTimeSeconds() >= NextLog)
	{
		NextLog = GetWorld()->GetTimeSeconds() + 5;
		int32 Occupied = 0, Moving = 0;
		if (GetNetMode() != NM_Client)
		{
			auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
			for (const auto E : Owned) if (const auto* Intent = EM.GetFragmentDataPtr<FEcoShelterIntentFragment>(E))
			{ Occupied += Intent->State == EEcoShelterIntentState::Occupied; Moving += Intent->State == EEcoShelterIntentState::Moving; }
		}
		UE_LOG(LogTemp, Log, TEXT("[Eco Integration] NetMode=%d LogicalOwned=%d Visuals=%d ShelterMoving=%d Occupied=%d Step=%lld"),
			int32(GetNetMode()), Owned.Num(), Visuals.Num(), Moving, Occupied, Step);
		for (const auto& Pair : Visuals) if (const auto* Actor = Pair.Value.Actor.Get())
		{
			UE_LOG(LogTemp, Log, TEXT("[Eco Integration][Visual] NetMode=%d Id=%lld Species=%s Speed=%.1f Position=%s Alive=%d Mesh=%s"),
				int32(GetNetMode()), Pair.Key, *Actor->VisualSpeciesId.ToString(), Actor->GetVelocity().Size2D(), *Actor->GetActorLocation().ToCompactString(),
				Actor->VisualState.bAlive, *GetNameSafe(Actor->VisualMesh));
			break;
		}
	}
}

void AEcoCreatureIntegrationSpawner::OnWorldPostActorTick(UWorld* World, ELevelTick TickType, float Delta)
{
	if (World == GetWorld() && TickType != LEVELTICK_ViewportsOnly) Tick(Delta);
}

#if WITH_DEV_AUTOMATION_TESTS
void AEcoCreatureIntegrationSpawner::UpdateTestObserver()
{
	// Explicit timed development fixture. Moves only the observer Pawn so the
	// existing server viewer/Bubble and client landscape streaming are exercised.
	// Never changes creatures, vitals, policy, resources or replication payloads.
	const auto* GameState = GetWorld()->GetGameState();
	const double Time = GameState ? GameState->GetServerWorldTimeSeconds() : GetWorld()->GetTimeSeconds();
	const int32 Phase = int32(Time / 12.0) % 3;
	const FName Region = Phase == 0 ? TEXT("Forest") : Phase == 1 ? TEXT("Barren") : TEXT("Highland");
	FVector Point(34000, Phase == 0 ? 45000 : Phase == 1 ? 0 : -49500, Phase == 0 ? -1600 : Phase == 1 ? 1700 : 2640);
	int64 Best = MAX_int64;
	if (GetNetMode() == NM_Client)
	{
		for (const auto& Pair : Visuals) if (const auto* Actor = Pair.Value.Actor.Get())
			if (Actor->VisualState.bAlive && Actor->VisualSpeciesId == TEXT("Wolf") && Actor->VisualState.RegionId == Region && Pair.Key < Best)
			{ Best = Pair.Key; Point = Actor->GetActorLocation(); }
	}
	else if (auto* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>())
	{
		auto& EM = Spawner->GetEntityManagerChecked();
		for (const auto E : Owned) if (EM.IsEntityValid(E))
		{
			const auto* Id = EM.GetFragmentDataPtr<FEcoIdentityFragment>(E);
			const auto* Membership = EM.GetFragmentDataPtr<FEcoRegionFragment>(E);
			const auto* Vital = EM.GetFragmentDataPtr<FEcoVitalsFragment>(E);
			const auto* Transform = EM.GetFragmentDataPtr<FTransformFragment>(E);
			if (Id && Membership && Vital && Transform && Vital->HP > 0 && Id->SpeciesId == TEXT("Wolf")
				&& Membership->CurrentRegionId == Region && Id->StableAgentId < Best)
			{ Best = Id->StableAgentId; Point = Transform->GetTransform().GetLocation(); }
		}
	}
	for (auto It = GetWorld()->GetPlayerControllerIterator(); It; ++It) if (auto* Player = It->Get())
		if (APawn* Pawn = Player->GetPawn())
		{
			const FVector View = Point + FVector(400, 250, 650);
			Pawn->SetActorLocation(View, false, nullptr, ETeleportType::TeleportPhysics);
			Player->SetControlRotation((Point - View).Rotation());
		}
	if (Phase != LastTestObserverPhase)
	{
		LastTestObserverPhase = Phase;
		UE_LOG(LogTemp, Log, TEXT("[Eco Integration][Observer] Mode=%d Region=%s Target=%lld Time=%.2f"),
			int32(GetNetMode()), *Region.ToString(), Best == MAX_int64 ? 0 : Best, Time);
	}
}
#endif

void AEcoCreatureIntegrationSpawner::FailRuntime(const TCHAR* Reason)
{
	 bReady = false;
	if (GetNetMode() != NM_Client) if (auto* State = GetWorld()->GetGameState<AEcoGameState>()) State->SetMassReplicationReady(false);
	UE_LOG(LogTemp, Error, TEXT("[Eco Integration] Runtime stopped: %s Step=%lld Owned=%d WorldTime=%.3f"), Reason, Step, Owned.Num(), GetWorld()->GetTimeSeconds());
}

void AEcoCreatureIntegrationSpawner::EndPlay(const EEndPlayReason::Type Reason)
{
	FWorldDelegates::OnWorldPostActorTick.Remove(PostTickHandle);
	bReady = false;
	bWaitingForHabitat = false;
	HabitatStreamingSource->DisableStreamingSource();
	for (auto& Pair : Visuals) if (auto* Actor = Pair.Value.Actor.Get()) { Actor->ClearBinding(); Actor->Destroy(); }
	Visuals.Reset();
	if (GetWorld() && GetNetMode() != NM_Client)
	{
		if (auto* Registry = GetWorld()->GetSubsystem<UEcoWorldProviderRegistry>())
		{
			auto* Dummy = GetWorld()->GetSubsystem<UEcoDummyWorldProviderSubsystem>();
			if (Registry->GetFoodProvider() == this) Registry->SetFoodProvider(Dummy);
			if (Registry->GetCoverProvider() == this) Registry->SetCoverProvider(Dummy);
		}
		if (auto* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>())
		{
			auto& EM = Spawner->GetEntityManagerChecked();
			TArray<FMassEntityHandle> Remaining;
			for (const auto E : Owned) if (EM.IsEntityValid(E))
			{
				if (auto* Shelter = GetWorld()->GetSubsystem<UEcoShelterSubsystem>()) Shelter->ReleaseAgentReservations(EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId);
				Remaining.Add(E);
			}
			if (!Remaining.IsEmpty()) EM.BatchDestroyEntities(Remaining);
		}
	}
	Owned.Reset(); Super::EndPlay(Reason);
}
