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
#include "Mass/EcoHerdMigration.h"
#include "HAL/IConsoleManager.h"

static TAutoConsoleVariable<int32> EcoIntegrationLogDetails(TEXT("eco.Integration.LogDetails"), 0,
	TEXT("Read-only agent/region/receive audit at the existing five-second integration log interval. Disable for profiling."));

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
    if(bEnableHerdJourneys)for(TActorIterator<AEcoHerdMigrationRoute> It(GetWorld());It;++It)if(It->bEnabled){
        for(int32 I=0;I<It->Points.Num();++I){
            AddPoint(It->Points[I]);if(I==0)continue;
            const double Distance=FVector::Dist2D(It->Points[I-1],It->Points[I]);
            const int32 Count=FMath::Clamp(FMath::CeilToInt(Distance/FMath::Max(1000.f,HabitatStreamingRadius*.75f)),1,256);
            for(int32 K=1;K<Count;++K)AddPoint(FMath::Lerp(It->Points[I-1],It->Points[I],double(K)/Count));
        }
    }
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
    if (OnRuntimeSample.IsBound() && GetWorld()->GetTimeSeconds() >= NextAuditSample)
    {
        NextAuditSample = GetWorld()->GetTimeSeconds() + 2.0;
        OnRuntimeSample.Broadcast(Delta);
    }
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
		if (EcoIntegrationLogDetails.GetValueOnGameThread()) DumpRuntime(true);
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
	for (AEcoCreatureRepresentationActor* Actor : VisualPool) if (Actor) Actor->Destroy();
	VisualPool.Reset();
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
	Owned.Reset(); SpeciesTotals.Reset(); Super::EndPlay(Reason);
}
