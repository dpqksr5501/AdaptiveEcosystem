#include "Debug/EcoMoveTestSubsystem.h"

#include "Engine/World.h"

#if !UE_BUILD_SHIPPING
#include "AdaptiveEcosystem.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "Creature/Debug/EcoCreatureInspection.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Debug/EcoMoveAvoidance.h"
#include "Debug/EcoMoveBaseline.h"
#include "Dom/JsonObject.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassEntityQuery.h"
#include "MassEntitySubsystem.h"
#include "MassExecutionContext.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace
{
constexpr int32 DefaultSteps = 90;
constexpr int32 MaxSteps = 900;
constexpr int32 DefaultStaticFrames = 600, MaxStaticFrames = 18000;
constexpr double LostTargetSeconds = 3.;
constexpr double VisualInterval = 1. / 30.;
constexpr TCHAR ObserveMap[] = TEXT("/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed");

FAutoConsoleCommandWithWorldAndArgs MoveTest(
	TEXT("eco.MoveTest"), TEXT("Native v3 movement diagnostics. Use eco.MoveTest Help."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (auto* Recorder = World ? World->GetSubsystem<UEcoMoveTestSubsystem>() : nullptr)
			Recorder->Execute(Args);
		else
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] Start Play and enter the command in its game console."));
	}), ECVF_Cheat);

constexpr TCHAR StaticMeshModeCVar[] = TEXT("eco.IntegratedV3.StaticMeshContact");
int32 StaticMeshContactMode()
{
	const auto* CVar = IConsoleManager::Get().FindConsoleVariable(StaticMeshModeCVar);
	return CVar && CVar->GetInt() == 1 ? 1 : 0;
}

bool HasLiveNativeDeer(UWorld& World, int64 Id)
{
	const auto* V3 = World.GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	auto* Mass = World.GetSubsystem<UMassEntitySubsystem>();
	if (!V3 || !V3->IsActive() || V3->NumContexts() == 0 || !Mass) return false;
	auto& Manager = Mass->GetMutableEntityManager();
	if (Manager.IsProcessing()) return false;

	FMassEntityQuery Query(Manager.AsShared());
	Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoIntegratedPolicyV3Tag>(EMassFragmentPresence::All);
	Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
	auto Context = Manager.CreateExecutionContext(0);
	bool bFound = false;
	Query.ForEachEntityChunk(Context, [&](FMassExecutionContext& Chunk)
	{
		const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>();
		const auto Links = Chunk.GetFragmentView<FEcoIntegratedV3Fragment>();
		const auto Vitals = Chunk.GetFragmentView<FEcoVitalsFragment>();
		for (int32 Index = 0; !bFound && Index < Chunk.GetNumEntities(); ++Index)
			bFound = Ids[Index].StableAgentId == Id && !Links[Index].bDead && Vitals[Index].HP > 0;
	});
	return bFound;
}

const TCHAR* NetModeName(ENetMode Mode)
{
	switch (Mode)
	{
	case NM_Standalone: return TEXT("Standalone");
	case NM_ListenServer: return TEXT("ListenServer");
	case NM_DedicatedServer: return TEXT("DedicatedServer");
	case NM_Client: return TEXT("Client");
	default: return TEXT("Unknown");
	}
}

struct FCsv
{
	FString Data;

	void Field(const FString& Value)
	{
		Data.AppendChar(TEXT('"'));
		Data += Value.Replace(TEXT("\""), TEXT("\"\""));
		Data.AppendChar(TEXT('"'));
	}
	void Field(FName Value) { Field(Value.ToString()); }
	void Field(bool Value) { Data.AppendChar(Value ? TEXT('1') : TEXT('0')); }
	void Field(double Value) { Data.Appendf(TEXT("%.17g"), Value); }
	template<typename T> void Field(T Value) { Data += LexToString(Value); }

	template<typename... T> void Row(const T&... Fields)
	{
		const int32 Start = Data.Len();
		([&]
		{
			if (Data.Len() > Start) Data.AppendChar(TEXT(','));
			Field(Fields);
		}(), ...);
		Data.AppendChar(TEXT('\n'));
	}
};

bool Reversed(const FVector2D& A, const FVector2D& B)
{
	return A.SizeSquared() >= 1. && B.SizeSquared() >= 1. && FVector2D::DotProduct(A, B) < 0.;
}

bool SameGoal(const FEcoMoveTestSample& A, const FEcoMoveTestSample& B)
{
	return A.GoalKind == B.GoalKind && A.GoalId == B.GoalId
		&& (A.GoalKind.IsNone() || FVector2D::DistSquared(A.GoalXYCm, B.GoalXYCm) <= FMath::Square(25.));
}
}

void FEcoMoveTestSample::SetGoal(FName Kind, int64 Id, double WorldX, double WorldY)
{
	GoalKind = Kind;
	GoalId = Id;
	GoalXYCm = FVector2D(WorldX, WorldY);
}
#endif

bool UEcoMoveTestSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return !UE_BUILD_SHIPPING && Super::ShouldCreateSubsystem(Outer) && World && World->IsGameWorld();
}

void UEcoMoveTestSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
#if !UE_BUILD_SHIPPING
	PostTickHandle = FWorldDelegates::OnWorldPostActorTick.AddUObject(this, &UEcoMoveTestSubsystem::PostActorTick);
	StartTickHandle = FWorldDelegates::OnWorldTickStart.AddUObject(this, &UEcoMoveTestSubsystem::StartWorldTick);
#endif
}

void UEcoMoveTestSubsystem::OnWorldEndPlay(UWorld& InWorld)
{
#if !UE_BUILD_SHIPPING
	if (bActive) Finish(TEXT("Incomplete"), TEXT("WorldEnded"));
#endif
	Super::OnWorldEndPlay(InWorld);
}

void UEcoMoveTestSubsystem::Deinitialize()
{
#if !UE_BUILD_SHIPPING
	FWorldDelegates::OnWorldPostActorTick.Remove(PostTickHandle);
	FWorldDelegates::OnWorldTickStart.Remove(StartTickHandle);
	if (bActive) Finish(TEXT("Incomplete"), TEXT("WorldEnded"));
#endif
	Super::Deinitialize();
}

#if !UE_BUILD_SHIPPING
void UEcoMoveTestSubsystem::Execute(const TArray<FString>& Args)
{
	const FString Command = Args.IsEmpty() ? TEXT("Help") : Args[0];
	if (Command.Equals(TEXT("Help"), ESearchCase::IgnoreCase))
	{
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("[Eco MoveTest] Observe [StableAgentId [Steps]] | Status | Stop. Default: %d steps; max: %d. ")
			TEXT("Authority requires a live integrated v3 deer (map %s, one Standalone player is sufficient). ")
			TEXT("Clients can record a visible deer for the equivalent time, using presentation only."),
			DefaultSteps, MaxSteps, ObserveMap);
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("[Eco MoveTest] Run <Baseline|HeadOn|Graze|Flight|ShadowHeadOn|Crossing> [Steps [Seed]]. ")
			TEXT("HeadOn/Graze/Flight compare Off and Enabled in isolated Native v3 fixtures. Use Standalone or server Play. Default seed: %lld."),
			EcoMoveBaseline::DefaultSeed);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco MoveTest] Run StaticMeshAvoidance [Frames] records actual authority Native deer. Set eco.IntegratedV3.StaticMeshContact before Play."));
		return;
	}
	if (Args.Num() == 1 && Command.Equals(TEXT("Status"), ESearchCase::IgnoreCase))
	{
		PrintStatus();
		return;
	}
	if (Args.Num() == 1 && Command.Equals(TEXT("Stop"), ESearchCase::IgnoreCase))
	{
		if (bActive) Finish(TEXT("Incomplete"), TEXT("UserStopped"));
		else PrintStatus();
		return;
	}
	if (Command.Equals(TEXT("Run"), ESearchCase::IgnoreCase))
	{
		const FString Scenario = Args.Num() >= 2 ? Args[1] : FString();
		const bool bBaseline = Scenario.Equals(TEXT("Baseline"), ESearchCase::IgnoreCase);
		const bool bHeadOn = Scenario.Equals(TEXT("HeadOn"), ESearchCase::IgnoreCase);
		const bool bShadowHeadOn = Scenario.Equals(TEXT("ShadowHeadOn"), ESearchCase::IgnoreCase);
		const bool bCrossing = Scenario.Equals(TEXT("Crossing"), ESearchCase::IgnoreCase);
		const bool bGraze = Scenario.Equals(TEXT("Graze"), ESearchCase::IgnoreCase);
		const bool bFlight = Scenario.Equals(TEXT("Flight"), ESearchCase::IgnoreCase);
		if (bActive)
		{
			PrintStatus();
			return;
		}
		if (Scenario.Equals(TEXT("StaticMeshAvoidance"), ESearchCase::IgnoreCase))
		{
			int32 Frames = DefaultStaticFrames;
			if (Args.Num() > 3 || (Args.Num() == 3 && (!LexTryParseString(Frames, *Args[2]) || Frames < 1 || Frames > MaxStaticFrames)))
			{
				UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] Usage: Run StaticMeshAvoidance [Frames], 1-%d. Set the seed before Play."), MaxStaticFrames);
			}
			else StartStaticMesh(Frames);
			return;
		}
		int32 Steps = DefaultSteps;
		int64 Seed = EcoMoveBaseline::DefaultSeed;
		if ((!bBaseline && !bHeadOn && !bShadowHeadOn && !bCrossing && !bGraze && !bFlight) || Args.Num() > 4
			|| (Args.Num() >= 3 && (!LexTryParseString(Steps, *Args[2]) || Steps < 1 || Steps > MaxSteps))
			|| (Args.Num() == 4 && (!LexTryParseString(Seed, *Args[3]) || Seed < 0)))
		{
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] Usage: Run <Baseline|HeadOn|Graze|Flight|ShadowHeadOn|Crossing> [Steps [Seed]], Steps 1-%d, Seed >= 0."), MaxSteps);
			return;
		}
		if (bBaseline) StartBaseline(Steps, Seed);
		else
		{
			using EcoMoveAvoidance::EScenario;
			EScenario Fixture = EScenario::HeadOn;
			if (bCrossing) Fixture = EScenario::Crossing;
			if (bGraze) Fixture = EScenario::Graze;
			if (bFlight) Fixture = EScenario::Flight;
			StartAvoidance(Fixture, Steps, Seed, bHeadOn || bGraze || bFlight);
		}
		return;
	}
	if (!Command.Equals(TEXT("Observe"), ESearchCase::IgnoreCase))
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] Use eco.MoveTest Help for commands and scenarios."));
		return;
	}
	if (bActive)
	{
		PrintStatus();
		return;
	}

	int64 Id = 0;
	int32 Steps = DefaultSteps;
	if (Args.Num() > 3 || (Args.Num() >= 2 && (!LexTryParseString(Id, *Args[1]) || Id <= 0))
		|| (Args.Num() == 3 && (!LexTryParseString(Steps, *Args[2]) || Steps < 1 || Steps > MaxSteps)))
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] Usage: Observe [StableAgentId [Steps]], Steps 1-%d."), MaxSteps);
		return;
	}
	StartObserve(Id, Steps);
}

void UEcoMoveTestSubsystem::StartObserve(int64 Id, int32 Steps)
{
	UWorld& World = *GetWorld();
	const bool bUseVisual = World.GetNetMode() == NM_Client;
	if (!bUseVisual)
	{
		const auto* V3 = World.GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
		if (!V3 || !V3->IsActive() || V3->NumContexts() == 0)
		{
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] Integrated v3 is not ready. Open %s in the Content Browser, start Play Standalone and wait for deer to spawn."), ObserveMap);
			return;
		}
	}
	if (Id == 0)
	{
		for (auto It = World.GetPlayerControllerIterator(); It; ++It)
		{
			const APlayerController* Controller = It->Get();
			const auto* Hud = Controller && Controller->IsLocalController() ? Cast<AEcoCreatureInspectorHUD>(Controller->GetHUD()) : nullptr;
			if (Hud && Hud->GetSelectedAgentId() > 0)
			{
				Id = Hud->GetSelectedAgentId();
				break;
			}
		}
		if (Id == 0)
		{
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] Select an Herbivore in ECO INSPECTOR (middle mouse or Tab) or use eco.MoveTest Observe <StableAgentId>."));
			return;
		}
	}
	auto* Actor = FindVisual(Id);
	if (bUseVisual ? (!Actor || !Actor->VisualState.bAlive) : !HasLiveNativeDeer(World, Id))
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] Agent %lld is not a live %s deer in this world."), Id,
			bUseVisual ? TEXT("visible") : TEXT("integrated v3"));
		return;
	}

	if (!PrepareRun(Steps)) return;
	Baseline.Reset();
	Avoidance.Reset();
	AgentId = Id;
	bClient = bUseVisual;
	LastNativeAt = NextVisualAt = StartedAt;
	Samples.Reset(bClient ? 0 : Steps);
	VisualSamples.Reset(Steps * 4 + 1);
	Visual = Actor;
	PrintStatus();
}

bool UEcoMoveTestSubsystem::PrepareRun(int32 Steps)
{
	RunId = FDateTime::UtcNow().ToString(TEXT("%Y%m%dT%H%M%SZ")) + TEXT("_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
	Directory = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("Profiling/EcoMovement") / RunId);
	if (!IFileManager::Get().MakeDirectory(*Directory, true))
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("[Eco MoveTest] Could not create %s"), *Directory);
		RunId.Reset();
		Directory.Reset();
		LastResult.Reset();
		LastReason.Reset();
		return false;
	}
	RequestedSteps = Steps;
	StartedAt = GetWorld()->GetTimeSeconds();
	LastResult.Reset();
	LastReason.Reset();
	bStaticMesh = false;
	StaticMeshFrames.Reset();
	StaticMeshSetup.Reset();
	bActive = true;
	return true;
}

bool UEcoMoveTestSubsystem::PrepareFixture(int32 Steps)
{
	if (GetWorld()->GetNetMode() == NM_Client)
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] Run fixtures from a Standalone or server Play console."));
		return false;
	}
	if (!PrepareRun(Steps)) return false;
	AgentId = 0;
	bClient = false;
	Visual.Reset();
	Samples.Reset();
	VisualSamples.Reset();
	Baseline.Reset();
	Avoidance.Reset();
	return true;
}

void UEcoMoveTestSubsystem::StartBaseline(int32 Steps, int64 Seed)
{
	if (!PrepareFixture(Steps)) return;
	Baseline = MakeShared<EcoMoveBaseline::FRun>();
	Baseline->Init(Seed, Steps);
	PrintStatus();
}

void UEcoMoveTestSubsystem::StartStaticMesh(int32 Frames)
{
	const auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	if (GetWorld()->GetNetMode() == NM_Client || !Native || !Native->IsActive() || !Native->UsesTerrain() || Native->NumContexts() == 0)
	{
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco MoveTest] StaticMeshAvoidance requires an active authority Native v3 world with terrain."));
		return;
	}
	if (!PrepareFixture(Frames)) return;
	bStaticMesh = true;
	StaticMeshMode = StaticMeshContactMode();
	StaticMeshFrames.Reserve(Frames);
	StaticMeshSetup = MakeShared<FJsonObject>();
	TArray<TSharedPtr<FJsonValue>> Regions;
	for (int32 Index = 0; Index < Native->NumContexts(); ++Index)
	{
		const auto& Ctx = *Native->GetContext(Index);
		auto Entry = MakeShared<FJsonObject>();
		Entry->SetStringField(TEXT("region"), Ctx.RegionId.ToString());
		Entry->SetStringField(TEXT("seed"), LexToString(Ctx.Sim.Config.Seed));
		Entry->SetBoolField(TEXT("contact"), Native->UsesStaticMeshContact(Ctx));
		Entry->SetBoolField(TEXT("imported_discs"), Ctx.bObstaclesImported);
		Entry->SetBoolField(TEXT("synthetic_stage_discs"), !Ctx.Trees.Discs.empty());
		Entry->SetNumberField(TEXT("live_deer_at_start"), Ctx.AliveDeer);
		Entry->SetNumberField(TEXT("wolves_at_start"), Ctx.Wolves);
		Entry->SetNumberField(TEXT("discs_at_start"), Ctx.Sim.Config.Obstacles.Num());
		Regions.Add(MakeShared<FJsonValueObject>(Entry));
	}
	StaticMeshSetup->SetArrayField(TEXT("regions"), Regions);
	StaticMeshSetup->SetStringField(TEXT("brain"), Native->GetActiveBrain().Id);
	StaticMeshSetup->SetNumberField(TEXT("native_steps_per_game_second"), 1. / EcoRepertoireV3::kStepSeconds);
	StaticMeshSetup->SetNumberField(TEXT("world_seconds_at_start"), StartedAt);
	StaticMeshSetup->SetBoolField(TEXT("fixed_frame_rate"), FApp::UseFixedTimeStep());
	StaticMeshSetup->SetNumberField(TEXT("fixed_delta_seconds"), FApp::GetFixedDeltaTime());
	TMap<FString, int32> Instances;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		const TInlineComponentArray<UInstancedStaticMeshComponent*> Components(*It);
		for (const auto* Component : Components)
		{
			const UStaticMesh* Mesh = Component->GetStaticMesh();
			if (Mesh && Component->IsQueryCollisionEnabled() && Component->GetCollisionResponseToChannel(ECC_WorldStatic) == ECR_Block)
				Instances.FindOrAdd(Mesh->GetPathName()) += Component->GetInstanceCount();
		}
	}
	Instances.KeySort([](const FString& A, const FString& B) { return A < B; });
	auto Meshes = MakeShared<FJsonObject>();
	for (const auto& Pair : Instances) Meshes->SetNumberField(Pair.Key, Pair.Value);
	StaticMeshSetup->SetObjectField(TEXT("loaded_blocking_instanced_mesh_assets"), Meshes);
	auto Settings = MakeShared<FJsonObject>();
	for (const TCHAR* Name : {TEXT("eco.IntegratedV3.StaticMeshContact.Candidates"), TEXT("eco.IntegratedV3.StaticMeshContact.Sweeps"),
		TEXT("eco.IntegratedV3.StaticMeshContact.NearCm"), TEXT("eco.IntegratedV3.StaticMeshContact.MiddleCm"),
		TEXT("t.MaxFPS"), TEXT("net.MaxSimulatedTickRate"), TEXT("eco.IntegratedV3.SocialControl")})
		if (const auto* CVar = IConsoleManager::Get().FindConsoleVariable(Name)) Settings->SetStringField(Name, CVar->GetString());
	StaticMeshSetup->SetObjectField(TEXT("settings"), Settings);
	PrintStatus();
}

void UEcoMoveTestSubsystem::StartWorldTick(UWorld* InWorld, ELevelTick TickType, float DeltaSeconds)
{
	if (!IsRecordingStaticMesh() || GetWorld() != InWorld || TickType == LEVELTICK_ViewportsOnly) return;
	if (StaticMeshFrames.Num() == RequestedSteps)
	{
		int32 NativeSteps = 0;
		int32 Intent = 0;
		int32 StaticHits = 0;
		int32 ContactRegions = 0;
		for (const auto& Frame : StaticMeshFrames)
		{
			NativeSteps += Frame.Steps;
			Intent += Frame.Metrics.Intent;
			StaticHits += Frame.Metrics.StaticHits;
			ContactRegions += Frame.Metrics.ContactRegions;
		}
		const bool bCovered = NativeSteps > 0 && Intent > 0 && (StaticMeshMode == 0 || (ContactRegions > 0 && StaticHits > 0));
		Finish(bCovered ? TEXT("Recorded") : TEXT("Incomplete"), bCovered ? TEXT("AcceptanceRequiresComparison") : TEXT("MotionOrContactNotObserved"));
		return;
	}
	if (StaticMeshMode != StaticMeshContactMode())
	{
		Finish(TEXT("Incomplete"), TEXT("ModeChanged"));
		return;
	}
	StaticMeshFrames.Add({GFrameCounter, 0, InWorld->GetTimeSeconds(), DeltaSeconds, 0., {}});
	WorldTickStarted = FPlatformTime::Seconds();
}

void UEcoMoveTestSubsystem::RecordStaticMesh(int32 Steps, FEcoV3StaticMeshMetrics&& Metrics)
{
	if (!IsRecordingStaticMesh() || StaticMeshFrames.IsEmpty() || StaticMeshFrames.Last().Frame != GFrameCounter) return;
	auto& Frame = StaticMeshFrames.Last();
	Frame.Steps += Steps;
	Frame.Metrics.Accumulate(Metrics);
}

void UEcoMoveTestSubsystem::StartAvoidance(EcoMoveAvoidance::EScenario Scenario, int32 Steps, int64 Seed, bool bCompareApplied)
{
	if (!PrepareFixture(Steps)) return;
	Avoidance = MakeShared<EcoMoveAvoidance::FRun>();
	Avoidance->Init(Scenario, Seed, Steps, bCompareApplied);
	PrintStatus();
}

int64 UEcoMoveTestSubsystem::NativeTarget() const
{
	return bActive && !bStaticMesh && !Baseline && !Avoidance && !bClient && Samples.Num() < RequestedSteps
		&& (Samples.IsEmpty() || Samples.Last().DeathCause == EcoWorldV3::kDeathNone) ? AgentId : 0;
}

void UEcoMoveTestSubsystem::RecordNative(FEcoMoveTestSample&& Sample)
{
	LastNativeAt = Sample.WorldSeconds;
	Samples.Add(MoveTemp(Sample));
}

AEcoCreatureRepresentationActor* UEcoMoveTestSubsystem::FindVisual(int64 Id) const
{
	for (TActorIterator<AEcoCreatureRepresentationActor> It(GetWorld()); It; ++It)
	{
		if (It->bBound && !It->IsHidden() && It->VisualState.StableAgentId == Id
			&& It->VisualState.SpeciesId == TEXT("Herbivore")) return *It;
	}
	return nullptr;
}

void UEcoMoveTestSubsystem::RecordVisual(double Now)
{
	if (Now + UE_DOUBLE_SMALL_NUMBER < NextVisualAt) return;
	NextVisualAt = Now + VisualInterval;
	auto* Actor = Visual.Get();
	if (!Actor || !Actor->bBound || Actor->IsHidden() || Actor->VisualState.StableAgentId != AgentId)
	{
		Actor = FindVisual(AgentId);
		Visual = Actor;
	}
	if (!Actor || VisualSamples.Num() >= RequestedSteps * 4 + 1) return;
	const auto& State = Actor->VisualState;
	VisualSamples.Add({Now, State.WorldTime, Samples.Num(), State.Sequence, State.RegionId, Actor->GetActorLocation(),
		State.Position, State.Velocity, Actor->GetActorRotation().Yaw, State.FocusYawDegrees, State.bAlive, State.bDiscontinuity});
}

void UEcoMoveTestSubsystem::PostActorTick(UWorld* InWorld, ELevelTick TickType, float DeltaSeconds)
{
	if (!bActive || GetWorld() != InWorld) return;
	if (bStaticMesh)
	{
		if (!StaticMeshFrames.IsEmpty() && StaticMeshFrames.Last().Frame == GFrameCounter)
			StaticMeshFrames.Last().WorldTickSeconds = FPlatformTime::Seconds() - WorldTickStarted;
		return;
	}
	if (Avoidance)
	{
		Avoidance->Step();
		if (Avoidance->bAppliedComparison)
		{
			if (Avoidance->bTargetDied) Finish(TEXT("Incomplete"), TEXT("TargetDied"));
			else if (Avoidance->CompletedSteps >= RequestedSteps)
			{
				if (const TCHAR* Failure = Avoidance->Regression()) Finish(TEXT("Failed"), Failure);
				else if (const TCHAR* Missing = Avoidance->MissingCoverage()) Finish(TEXT("Incomplete"), Missing);
				else Finish(TEXT("Passed"), TEXT("AppliedComparisonChecks"));
			}
			return;
		}
		if (Avoidance->Mismatch)
			Finish(TEXT("Failed"), TEXT("ShadowParityMismatch"));
		else if (Avoidance->bTargetDied)
			Finish(TEXT("Incomplete"), TEXT("TargetDied"));
		else if (Avoidance->Samples.Num() >= RequestedSteps)
		{
			if (Avoidance->RiskRows == 0 || Avoidance->ChangedRows == 0)
				Finish(TEXT("Incomplete"), TEXT("EncounterNotCovered"));
			else
				Finish(TEXT("Passed"), TEXT("ShadowParityAndCoverage"));
		}
		return;
	}
	if (Baseline)
	{
		Baseline->Step();
		if (Baseline->Completed >= RequestedSteps)
		{
			const auto& Sparse = Baseline->Sparse;
			const auto& Small = Baseline->Small;
			if (Sparse.Mismatch || Small.Mismatch || Small.SpatialCandidates != Small.FullCandidates)
				Finish(TEXT("Failed"), TEXT("ParityMismatch"));
			else if (Sparse.SpatialCandidates >= Sparse.FullCandidates || Small.Queries == 0)
				Finish(TEXT("Incomplete"), TEXT("RequiredSearchPathNotCovered"));
			else
				Finish(TEXT("Passed"), TEXT("ExactNativeParity"));
		}
		return;
	}
	const double Now = InWorld->GetTimeSeconds();
	RecordVisual(Now);
	if (bClient)
	{
		if (!VisualSamples.IsEmpty() && !VisualSamples.Last().bAlive)
			Finish(TEXT("Incomplete"), TEXT("TargetDied"));
		else if (!VisualSamples.IsEmpty() && !Visual.IsValid())
			Finish(TEXT("Incomplete"), TEXT("RepresentationLost"));
		else if (Now - StartedAt + UE_DOUBLE_SMALL_NUMBER >= RequestedSteps * EcoRepertoireV3::kStepSeconds)
			Finish(VisualSamples.IsEmpty() ? TEXT("Incomplete") : TEXT("Recorded"),
				VisualSamples.IsEmpty() ? TEXT("NoRepresentationSamples") : TEXT("Completed"));
		return;
	}
	if (!Samples.IsEmpty() && Samples.Last().DeathCause != EcoWorldV3::kDeathNone)
		Finish(TEXT("Incomplete"), TEXT("TargetDied"));
	else if (Samples.Num() >= RequestedSteps)
		Finish(TEXT("Recorded"), TEXT("Completed"));
	else if (Now - LastNativeAt > LostTargetSeconds)
		Finish(TEXT("Incomplete"), HasLiveNativeDeer(*InWorld, AgentId) ? TEXT("NativeSamplesStalled") : TEXT("TargetLostOrBackendStopped"));
}

FString UEcoMoveTestSubsystem::ScreenStatus() const
{
	if (bStaticMesh) return FString();
	if (bActive)
	{
		if (Avoidance)
			return FString::Printf(TEXT("MoveTest %s | %s | %d / %d steps"), EcoMoveAvoidance::Name(Avoidance->Scenario),
				Avoidance->bAppliedComparison ? TEXT("Off vs Enabled") : TEXT("shadow avoidance"),
				Avoidance->bAppliedComparison ? Avoidance->CompletedSteps : Avoidance->Samples.Num(), RequestedSteps);
		if (Baseline)
			return FString::Printf(TEXT("MoveTest Baseline | full scan vs spatial | %d / %d steps per layout"), Baseline->Completed, RequestedSteps);
		const FString Progress = bClient
			? FString::Printf(TEXT("%.1f / %.1f s | visual %d"), GetWorld()->GetTimeSeconds() - StartedAt,
				RequestedSteps * EcoRepertoireV3::kStepSeconds, VisualSamples.Num())
			: FString::Printf(TEXT("%d / %d native steps"), Samples.Num(), RequestedSteps);
		return FString::Printf(TEXT("MoveTest Observe | Deer #%lld | %s"), AgentId, *Progress);
	}
	if (!LastResult.IsEmpty() && GetWorld()->GetTimeSeconds() <= ShowResultUntil)
		return FString::Printf(TEXT("MoveTest %s (%s) | see Output Log"), *LastResult, *LastReason);
	return FString();
}

void UEcoMoveTestSubsystem::PrintStatus() const
{
	if (RunId.IsEmpty())
	{
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco MoveTest] No run. Use eco.MoveTest Help."));
		return;
	}
	if (bStaticMesh)
	{
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("[Eco MoveTest] %s RunId=%s Scenario=StaticMeshAvoidance Mode=%s Frames=%d/%d Reason=%s Path=%s"),
			bActive ? TEXT("Running") : *LastResult, *RunId, StaticMeshMode == 1 ? TEXT("B") : TEXT("A"),
			StaticMeshFrames.Num(), RequestedSteps, *LastReason, *Directory);
		return;
	}
	if (Avoidance)
	{
		if (Avoidance->bAppliedComparison)
		{
			UE_LOG(LogAdaptiveEcosystem, Log,
				TEXT("[Eco MoveTest] %s RunId=%s Scenario=%s Mode=OffVsEnabled Steps=%d/%d Seed=%lld AppliedRows=%d Reason=%s Path=%s"),
				bActive ? TEXT("Running") : *LastResult, *RunId, EcoMoveAvoidance::Name(Avoidance->Scenario),
				Avoidance->CompletedSteps, RequestedSteps, Avoidance->Seed, Avoidance->Enabled.AppliedRows, *LastReason, *Directory);
			return;
		}
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("[Eco MoveTest] %s RunId=%s Scenario=%s Mode=Shadow Steps=%d/%d Seed=%lld MismatchMask=%u RiskRows=%d ProposedRows=%d Reason=%s Path=%s"),
			bActive ? TEXT("Running") : *LastResult, *RunId, EcoMoveAvoidance::Name(Avoidance->Scenario), Avoidance->Samples.Num(),
			RequestedSteps, Avoidance->Seed, Avoidance->Mismatch, Avoidance->RiskRows, Avoidance->ChangedRows, *LastReason, *Directory);
		return;
	}
	if (Baseline)
	{
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("[Eco MoveTest] %s RunId=%s Scenario=Baseline StepsPerLayout=%d/%d Seed=%lld MismatchMask=%u Reason=%s Path=%s"),
			bActive ? TEXT("Running") : *LastResult, *RunId, Baseline->Completed, RequestedSteps, Baseline->Seed,
			Baseline->Sparse.Mismatch | Baseline->Small.Mismatch, *LastReason, *Directory);
		return;
	}
	UE_LOG(LogAdaptiveEcosystem, Log,
		TEXT("[Eco MoveTest] %s RunId=%s Agent=%lld Mode=%s Native=%d/%d Visual=%d Reason=%s Path=%s"),
		bActive ? TEXT("Running") : *LastResult, *RunId, AgentId, bClient ? TEXT("Presentation") : TEXT("Authority"),
		Samples.Num(), bClient ? 0 : RequestedSteps, VisualSamples.Num(), *LastReason, *Directory);
}

void UEcoMoveTestSubsystem::Finish(const TCHAR* Result, const TCHAR* Reason)
{
	bActive = false;
	LastResult = Result;
	LastReason = Reason;
	ShowResultUntil = GetWorld()->GetTimeSeconds() + 8.;
	const bool bSaved = bStaticMesh ? WriteStaticMesh(Result, Reason) : Avoidance ? WriteAvoidance(Result, Reason)
		: Baseline ? WriteBaseline(Result, Reason) : WriteReport(Result, Reason);
	if (!bSaved)
	{
		LastResult = TEXT("WriteFailed");
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("[Eco MoveTest] Could not save complete report for RunId=%s to %s"), *RunId, *Directory);
	}
	PrintStatus();
}

bool UEcoMoveTestSubsystem::WriteAvoidance(const TCHAR* Result, const TCHAR* Reason) const
{
	if (Avoidance->bAppliedComparison) return WriteAppliedAvoidance(Result, Reason);
	constexpr double Cm = EcoRepertoireV3::kUnitCm;
	FCsv Csv{TEXT("step,agent_id,start_x_cm,start_y_cm,goal_x_cm,goal_y_cm,radius_cm,still,"
		"raw_dx_cm,raw_dy_cm,separation_dx_cm,separation_dy_cm,existing_dx_cm,existing_dy_cm,previous_dx_cm,previous_dy_cm,"
		"proposed_dx_cm,proposed_dy_cm,actual_dx_cm,actual_dy_cm,contact_rejected,threat_id,closest_at_step,"
		"existing_local_gap_cm,proposed_local_gap_cm,changed,retained_candidates,dropped_candidates,pair_checks,evaluation_us,"
		"existing_pair_gap_cm,combined_proposal_pair_gap_cm,actual_swept_pair_gap_cm,mismatch_mask\n")};
	int32 JointImprovements = 0;
	int32 ContactRejections = 0;
	double MinExistingGap = MAX_dbl, MinProposedGap = MAX_dbl, MinActualGap = MAX_dbl;
	for (const auto& Step : Avoidance->Samples)
	{
		JointImprovements += Step.CombinedProposalGap > Step.ExistingGap + 1.e-9 ? 1 : 0;
		MinExistingGap = FMath::Min(MinExistingGap, Step.ExistingGap);
		MinProposedGap = FMath::Min(MinProposedGap, Step.CombinedProposalGap);
		MinActualGap = FMath::Min(MinActualGap, Step.ActualGap);
		for (const auto& S : Step.Deer)
		{
			const auto& P = S.Proposal;
			ContactRejections += S.bContactRejected ? 1 : 0;
			Csv.Row(S.Step, int64(S.Agent.Id), S.Agent.Position.X * Cm, S.Agent.Position.Y * Cm,
				S.Goal.X * Cm, S.Goal.Y * Cm, S.Agent.Radius * Cm, S.Agent.bStill,
				S.Raw.X * Cm, S.Raw.Y * Cm, S.Separation.X * Cm, S.Separation.Y * Cm,
				S.Agent.DesiredDelta.X * Cm, S.Agent.DesiredDelta.Y * Cm, S.Previous.X * Cm, S.Previous.Y * Cm,
				P.Delta.X * Cm, P.Delta.Y * Cm, S.Actual.X * Cm, S.Actual.Y * Cm, S.bContactRejected,
				int64(P.RiskId), P.ClosestAtStep, P.BaseGap * Cm, P.ProposedGap * Cm,
				P.bChanged, int32(P.Retained), int32(P.Dropped), int32(P.PairChecks), S.EvaluationMicros,
				Step.ExistingGap * Cm, Step.CombinedProposalGap * Cm, Step.ActualGap * Cm, Step.Mismatch);
		}
	}

	const auto Json = MakeShared<FJsonObject>();
	const UWorld& World = *GetWorld();
	Json->SetNumberField(TEXT("schema_version"), 1);
	Json->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
	Json->SetStringField(TEXT("run_id"), RunId);
	Json->SetStringField(TEXT("scenario"), EcoMoveAvoidance::Name(Avoidance->Scenario));
	Json->SetStringField(TEXT("mode"), TEXT("Shadow"));
	Json->SetStringField(TEXT("host_map"), UWorld::RemovePIEPrefix(World.GetMapName()));
	Json->SetStringField(TEXT("world"), World.GetName());
	Json->SetStringField(TEXT("net_mode"), NetModeName(World.GetNetMode()));
	Json->SetStringField(TEXT("model"), FEcoV3BrainRegistry::Builtin()->Id);
	Json->SetStringField(TEXT("seed"), LexToString(Avoidance->Seed));
	Json->SetStringField(TEXT("result"), Result);
	Json->SetStringField(TEXT("reason"), Reason);
	Json->SetNumberField(TEXT("initial_deer"), 2);
	Json->SetNumberField(TEXT("initial_wolves"), 0);
	Json->SetNumberField(TEXT("requested_steps"), RequestedSteps);
	Json->SetNumberField(TEXT("completed_steps"), Avoidance->Samples.Num());
	Json->SetNumberField(TEXT("native_step_seconds"), EcoRepertoireV3::kStepSeconds);
	Json->SetNumberField(TEXT("prediction_horizon_steps"), EcoPredictiveAvoidanceV3::HorizonSteps);
	Json->SetNumberField(TEXT("candidate_limit"), EcoPredictiveAvoidanceV3::MaxCandidates);
	Json->SetNumberField(TEXT("gap_margin_cm"), EcoPredictiveAvoidanceV3::GapMargin * Cm);
	Json->SetNumberField(TEXT("mismatch_mask"), Avoidance->Mismatch);
	if (Avoidance->FirstMismatchStep != INDEX_NONE)
		Json->SetNumberField(TEXT("first_mismatch_step"), Avoidance->FirstMismatchStep);
	Json->SetNumberField(TEXT("risk_agent_steps"), Avoidance->RiskRows);
	Json->SetNumberField(TEXT("proposed_agent_steps"), Avoidance->ChangedRows);
	Json->SetNumberField(TEXT("dropped_candidates"), Avoidance->CandidatesDropped);
	Json->SetNumberField(TEXT("pair_checks"), Avoidance->PairChecks);
	Json->SetNumberField(TEXT("contact_rejections"), ContactRejections);
	Json->SetNumberField(TEXT("combined_gap_improved_steps"), JointImprovements);
	Json->SetNumberField(TEXT("combined_gap_regressed_steps"), Avoidance->JointRegressions);
	if (!Avoidance->Samples.IsEmpty())
	{
		Json->SetNumberField(TEXT("min_existing_pair_gap_cm"), MinExistingGap * Cm);
		Json->SetNumberField(TEXT("min_combined_proposal_pair_gap_cm"), MinProposedGap * Cm);
		Json->SetNumberField(TEXT("min_actual_swept_pair_gap_cm"), MinActualGap * Cm);
		Json->SetNumberField(TEXT("evaluation_us_mean"), Avoidance->EvaluationMicros / (2. * Avoidance->Samples.Num()));
		Json->SetNumberField(TEXT("evaluation_us_max"), Avoidance->MaxEvaluationMicros);
	}
	Json->SetArrayField(TEXT("missing_tracks"), {
		MakeShared<FJsonValueString>(TEXT("AppliedProposalTrajectory")),
		MakeShared<FJsonValueString>(TEXT("LiveLevelTerrainAndMass")),
		MakeShared<FJsonValueString>(TEXT("M4AuthorityLedger")),
		MakeShared<FJsonValueString>(TEXT("RepresentationAndReplication"))});

	FString Summary;
	const auto Writer = TJsonWriterFactory<>::Create(&Summary);
	return FJsonSerializer::Serialize(Json, Writer)
		&& FFileHelper::SaveStringToFile(Csv.Data, *(Directory / TEXT("Samples.csv")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)
		&& FFileHelper::SaveStringToFile(Summary, *(Directory / TEXT("Summary.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

bool UEcoMoveTestSubsystem::WriteAppliedAvoidance(const TCHAR* Result, const TCHAR* Reason) const
{
	const auto& Run = *Avoidance;
	constexpr double Cm = EcoRepertoireV3::kUnitCm;
	FCsv Csv{TEXT("mode,step,agent_id,start_x_cm,start_y_cm,goal_x_cm,goal_y_cm,behavior,flight_override,still,detour,"
		"raw_dx_cm,raw_dy_cm,separation_dx_cm,separation_dy_cm,"
		"before_detour_dx_cm,before_detour_dy_cm,after_terrain_dx_cm,after_terrain_dy_cm,proposed_dx_cm,proposed_dy_cm,"
		"final_dx_cm,final_dy_cm,actual_dx_cm,actual_dy_cm,proposed,applied,contact_rejected,reversal,pair_gap_cm,intake,arrival_step\n")};
	for (const auto& S : Run.AppliedSamples)
	{
		Csv.Row(FString(S.bEnabled ? TEXT("Enabled") : TEXT("Off")), S.Step, S.Agent, S.Position.X * Cm, S.Position.Y * Cm,
			S.Goal.X * Cm, S.Goal.Y * Cm, S.Behavior, S.FlightOverride, S.bStill, S.bDetour,
			S.Raw.X * Cm, S.Raw.Y * Cm, S.Separation.X * Cm, S.Separation.Y * Cm,
			S.BeforeDetour.X * Cm, S.BeforeDetour.Y * Cm, S.AfterTerrain.X * Cm, S.AfterTerrain.Y * Cm,
			S.Proposal.X * Cm, S.Proposal.Y * Cm, S.Final.X * Cm, S.Final.Y * Cm, S.Actual.X * Cm, S.Actual.Y * Cm,
			S.bProposed, S.bApplied, S.bContactRejected, S.bReversal, S.PairGap * Cm, S.Intake, S.ArrivalStep);
	}
	const int32 Targets = Run.ArrivalTargets();
	const auto Mode = [Targets](const EcoMoveAvoidance::FAppliedMetrics& M)
	{
		const auto Entry = MakeShared<FJsonObject>();
		Entry->SetNumberField(TEXT("direction_reversals"), M.Reversals);
		Entry->SetNumberField(TEXT("overlap_steps"), M.Overlaps);
		Entry->SetNumberField(TEXT("contact_rejections"), M.ContactRejections);
		Entry->SetNumberField(TEXT("detour_agent_steps"), M.DetourRows);
		Entry->SetNumberField(TEXT("risk_agent_steps"), M.RiskRows);
		Entry->SetNumberField(TEXT("applied_agent_steps"), M.AppliedRows);
		Entry->SetNumberField(TEXT("food_eaten"), M.FoodEaten);
		if (M.FirstFlightStep != INDEX_NONE) Entry->SetNumberField(TEXT("first_flight_step"), M.FirstFlightStep);
		if (M.FirstFlightMotionStep != INDEX_NONE) Entry->SetNumberField(TEXT("first_flight_motion_step"), M.FirstFlightMotionStep);
		if (Targets > 0)
		{
			TArray<TSharedPtr<FJsonValue>> Arrivals;
			int32 Arrived = 0, LastArrival = 0;
			for (int32 Index = 0; Index < Targets; ++Index)
			{
				const int32 Step = M.ArrivalSteps[Index];
				if (Step == INDEX_NONE) Arrivals.Add(MakeShared<FJsonValueNull>());
				else
				{
					Arrivals.Add(MakeShared<FJsonValueNumber>(Step));
					++Arrived;
					LastArrival = FMath::Max(LastArrival, Step);
				}
			}
			Entry->SetNumberField(TEXT("arrival_rate"), double(Arrived) / Targets);
			Entry->SetArrayField(TEXT("arrival_steps_by_agent"), Arrivals);
			// With at most two targets the nearest-rank p95 is the largest completed time.
			if (Arrived == Targets) Entry->SetNumberField(TEXT("arrival_p95_steps"), LastArrival);
		}
		if (!M.StepMicros.IsEmpty())
		{
			TArray<double> Sorted = M.StepMicros;
			Sorted.Sort();
			Entry->SetNumberField(TEXT("native_step_p95_us"), Sorted[FMath::CeilToInt(.95 * Sorted.Num()) - 1]);
		}
		return Entry;
	};
	const auto Json = MakeShared<FJsonObject>();
	const UWorld& World = *GetWorld();
	Json->SetNumberField(TEXT("schema_version"), 1);
	Json->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
	Json->SetStringField(TEXT("run_id"), RunId);
	Json->SetStringField(TEXT("scenario"), EcoMoveAvoidance::Name(Run.Scenario));
	Json->SetStringField(TEXT("mode"), TEXT("OffVsEnabled"));
	Json->SetStringField(TEXT("host_map"), UWorld::RemovePIEPrefix(World.GetMapName()));
	Json->SetStringField(TEXT("world"), World.GetName());
	Json->SetStringField(TEXT("net_mode"), NetModeName(World.GetNetMode()));
	Json->SetStringField(TEXT("model"), FEcoV3BrainRegistry::Builtin()->Id);
	Json->SetStringField(TEXT("seed"), LexToString(Run.Seed));
	Json->SetStringField(TEXT("result"), Result);
	Json->SetStringField(TEXT("reason"), Reason);
	Json->SetNumberField(TEXT("initial_deer"), 2);
	Json->SetNumberField(TEXT("initial_wolves"), 0);
	Json->SetNumberField(TEXT("requested_steps"), RequestedSteps);
	Json->SetNumberField(TEXT("completed_steps_per_mode"), Run.CompletedSteps);
	Json->SetNumberField(TEXT("native_step_seconds"), EcoRepertoireV3::kStepSeconds);
	Json->SetNumberField(TEXT("mismatch_mask"), Run.Mismatch);
	Json->SetBoolField(TEXT("first_step_policy_matched"), Run.bFirstStepPolicyMatched);
	Json->SetNumberField(TEXT("protected_velocity_changes"), Run.ProtectedChanges);
	if (Run.Off.FirstFlightMotionStep != INDEX_NONE && Run.Enabled.FirstFlightMotionStep != INDEX_NONE)
		Json->SetNumberField(TEXT("emergency_delay_steps"), Run.Enabled.FirstFlightMotionStep - Run.Off.FirstFlightMotionStep);
	Json->SetObjectField(TEXT("off"), Mode(Run.Off));
	Json->SetObjectField(TEXT("enabled"), Mode(Run.Enabled));
	Json->SetArrayField(TEXT("missing_tracks"), {
		MakeShared<FJsonValueString>(TEXT("LiveLevelTerrainAndMass")),
		MakeShared<FJsonValueString>(TEXT("M4AuthorityLedger")),
		MakeShared<FJsonValueString>(TEXT("RepresentationAndReplication"))});
	FString Summary;
	const auto Writer = TJsonWriterFactory<>::Create(&Summary);
	return FJsonSerializer::Serialize(Json, Writer)
		&& FFileHelper::SaveStringToFile(Csv.Data, *(Directory / TEXT("Samples.csv")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)
		&& FFileHelper::SaveStringToFile(Summary, *(Directory / TEXT("Summary.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

bool UEcoMoveTestSubsystem::WriteBaseline(const TCHAR* Result, const TCHAR* Reason) const
{
	FCsv Csv{TEXT("layout,step,mismatch_mask,full_candidates,spatial_candidates,queries,pre_move_rows\n")};
	TArray<TSharedPtr<FJsonValue>> Layouts;
	const auto Add = [&](const TCHAR* Name, const EcoMoveBaseline::FPair& Pair)
	{
		for (const auto& R : Pair.Rows)
			Csv.Row(FString(Name), R.Step, R.Mismatch, R.FullCandidates, R.SpatialCandidates, R.Queries, R.PreMoveRows);
		const auto Entry = MakeShared<FJsonObject>();
		const auto& Config = Pair.Full.World.Config;
		Entry->SetStringField(TEXT("name"), Name);
		Entry->SetNumberField(TEXT("initial_deer"), Pair.Full.NumHerbivores());
		Entry->SetNumberField(TEXT("initial_wolves"), Pair.Full.NumThreats());
		Entry->SetNumberField(TEXT("world_size_native_units"), Config.WorldSize);
		Entry->SetNumberField(TEXT("full_candidates"), Pair.FullCandidates);
		Entry->SetNumberField(TEXT("spatial_candidates"), Pair.SpatialCandidates);
		Entry->SetNumberField(TEXT("kin_queries"), Pair.Queries);
		Entry->SetNumberField(TEXT("mismatch_mask"), Pair.Mismatch);
		if (Pair.FirstMismatchStep >= 0) Entry->SetNumberField(TEXT("first_mismatch_step"), Pair.FirstMismatchStep);
		Entry->SetNumberField(TEXT("food_eaten_full"), Pair.Full.World.Stats.FoodEaten);
		Entry->SetNumberField(TEXT("food_eaten_spatial"), Pair.Spatial.World.Stats.FoodEaten);
		Entry->SetNumberField(TEXT("caught_full"), Pair.Full.World.Stats.Caught);
		Entry->SetNumberField(TEXT("caught_spatial"), Pair.Spatial.World.Stats.Caught);
		Layouts.Add(MakeShared<FJsonValueObject>(Entry));
	};
	Add(TEXT("Sparse"), Baseline->Sparse);
	Add(TEXT("SmallFallback"), Baseline->Small);

	const auto Json = MakeShared<FJsonObject>();
	Json->SetNumberField(TEXT("schema_version"), 1);
	Json->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
	Json->SetStringField(TEXT("run_id"), RunId);
	Json->SetStringField(TEXT("scenario"), TEXT("Baseline"));
	Json->SetStringField(TEXT("mode"), TEXT("NativeFixture"));
	Json->SetStringField(TEXT("host_map"), UWorld::RemovePIEPrefix(GetWorld()->GetMapName()));
	Json->SetStringField(TEXT("net_mode"), NetModeName(GetWorld()->GetNetMode()));
	Json->SetStringField(TEXT("model"), FEcoV3BrainRegistry::Builtin()->Id);
	Json->SetStringField(TEXT("seed"), LexToString(Baseline->Seed));
	Json->SetStringField(TEXT("result"), Result);
	Json->SetStringField(TEXT("reason"), Reason);
	Json->SetNumberField(TEXT("requested_steps_per_layout"), RequestedSteps);
	Json->SetNumberField(TEXT("completed_steps_per_layout"), Baseline->Completed);
	Json->SetNumberField(TEXT("native_step_seconds"), EcoRepertoireV3::kStepSeconds);
	Json->SetNumberField(TEXT("mismatch_mask"), Baseline->Sparse.Mismatch | Baseline->Small.Mismatch);
	Json->SetArrayField(TEXT("layouts"), Layouts);
	Json->SetArrayField(TEXT("missing_tracks"), {
		MakeShared<FJsonValueString>(TEXT("LiveLevelTerrainAndMass")),
		MakeShared<FJsonValueString>(TEXT("M4AuthorityLedger")),
		MakeShared<FJsonValueString>(TEXT("RepresentationAndReplication"))});

	FString Summary;
	const auto Writer = TJsonWriterFactory<>::Create(&Summary);
	return FJsonSerializer::Serialize(Json, Writer)
		&& FFileHelper::SaveStringToFile(Csv.Data, *(Directory / TEXT("Samples.csv")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)
		&& FFileHelper::SaveStringToFile(Summary, *(Directory / TEXT("Summary.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

bool UEcoMoveTestSubsystem::WriteStaticMesh(const TCHAR* Result, const TCHAR* Reason) const
{
	FCsv Frames{TEXT("frame,world_s,delta_s,world_tick_us,native_us,native_steps,deer_steps,intent_steps,checked_steps,"
		"moved_steps,stalled_steps,travel_intent_steps,flight_intent_steps,behavior_arrived_steps,disc_hits,static_mesh_hits,"
		"initial_overlaps,agent_blocks,body_sweeps,ground_probes,exclusion_checks,tangents,tangents_accepted,tangent_sweeps,"
		"budget_denied,contact_context_steps,legacy_context_steps,imported_context_steps,longest_static_stall_steps,"
		"disc_us,sweep_us,ground_us,exclusion_us,tangent_us\n")};
	TArray<double> TickMicros, NativeMicros;
	FEcoV3StaticMeshMetrics Total;
	int32 Steps = 0;
	for (const auto& Frame : StaticMeshFrames)
	{
		const auto& M = Frame.Metrics;
		const auto& Q = M.Queries;
		constexpr double Us = 1.e6;
		Frames.Row(Frame.Frame, Frame.WorldSeconds, Frame.DeltaSeconds, Us * Frame.WorldTickSeconds,
			Us * M.NativeSeconds, Frame.Steps, M.Deer, M.Intent, M.Checked, M.Moved, M.Stalled,
			M.Traveling, M.Flight, M.Arrived, M.DiscHits, M.StaticHits, M.InitialOverlaps, M.AgentBlocks,
			Q.Sweeps, Q.GroundProbes, Q.ExclusionChecks, M.Tangents, M.TangentsAccepted, M.TangentSweeps,
			M.BudgetDenied, M.ContactRegions, M.LegacyRegions, M.ImportedRegions, M.LongestContactStall,
			Us * M.DiscSeconds, Us * Q.SweepSeconds, Us * Q.GroundSeconds, Us * Q.ExclusionSeconds, Us * M.TangentSeconds);
		Total.Accumulate(M);
		Steps += Frame.Steps;
		if (Frame.WorldTickSeconds > 0.) TickMicros.Add(Us * Frame.WorldTickSeconds);
		if (Frame.Steps > 0) NativeMicros.Add(Us * M.NativeSeconds);
	}
	auto Json = MakeShared<FJsonObject>();
	Json->SetNumberField(TEXT("schema_version"), 1);
	Json->SetStringField(TEXT("run_id"), RunId);
	Json->SetStringField(TEXT("scenario"), TEXT("StaticMeshAvoidance"));
	Json->SetStringField(TEXT("mode"), StaticMeshMode == 1 ? TEXT("B") : TEXT("A"));
	Json->SetStringField(TEXT("result"), Result);
	Json->SetStringField(TEXT("reason"), Reason);
	Json->SetStringField(TEXT("map"), UWorld::RemovePIEPrefix(GetWorld()->GetMapName()));
	Json->SetStringField(TEXT("net_mode"), NetModeName(GetWorld()->GetNetMode()));
	Json->SetStringField(TEXT("engine_build"), FEngineVersion::Current().ToString());
	Json->SetStringField(TEXT("build_configuration"), LexToString(FApp::GetBuildConfiguration()));
	Json->SetObjectField(TEXT("setup"), StaticMeshSetup);
	Json->SetNumberField(TEXT("frames"), StaticMeshFrames.Num());
	Json->SetNumberField(TEXT("native_steps"), Steps);
	Json->SetNumberField(TEXT("move_intent_steps"), Total.Intent);
	Json->SetNumberField(TEXT("checked_steps"), Total.Checked);
	Json->SetNumberField(TEXT("moved_steps"), Total.Moved);
	Json->SetNumberField(TEXT("stalled_steps"), Total.Stalled);
	Json->SetNumberField(TEXT("legacy_disc_hits"), Total.DiscHits);
	Json->SetNumberField(TEXT("static_mesh_hits"), Total.StaticHits);
	Json->SetNumberField(TEXT("initial_overlaps"), Total.InitialOverlaps);
	Json->SetNumberField(TEXT("agent_contact_blocks"), Total.AgentBlocks);
	Json->SetNumberField(TEXT("body_sweeps"), Total.Queries.Sweeps);
	Json->SetNumberField(TEXT("tangent_sweeps"), Total.TangentSweeps);
	Json->SetNumberField(TEXT("tangent_candidates"), Total.Tangents);
	Json->SetNumberField(TEXT("tangent_candidates_advanced"), Total.TangentsAccepted);
	Json->SetNumberField(TEXT("tangent_budget_denied"), Total.BudgetDenied);
	if (Total.Deer > 0)
	{
		Json->SetNumberField(TEXT("min_body_radius_cm"), Total.MinBodyRadius);
		Json->SetNumberField(TEXT("max_body_radius_cm"), Total.MaxBodyRadius);
	}
	const auto AddPercentiles = [&](const TCHAR* Key, TArray<double>& Values)
	{
		if (Values.IsEmpty()) return;
		Values.Sort();
		const auto Quantile = [&](double P) { return Values[FMath::CeilToInt32(P * Values.Num()) - 1]; };
		auto Object = MakeShared<FJsonObject>();
		Object->SetNumberField(TEXT("p95"), Quantile(.95));
		Object->SetNumberField(TEXT("p99"), Quantile(.99));
		Object->SetNumberField(TEXT("max"), Values.Last());
		Json->SetObjectField(Key, Object);
	};
	AddPercentiles(TEXT("world_tick_to_post_actor_us"), TickMicros);
	AddPercentiles(TEXT("native_step_sum_per_active_frame_us"), NativeMicros);
	TArray<TSharedPtr<FJsonValue>> Unverified;
	for (const TCHAR* Metric : {TEXT("whole_game_thread_frame"), TEXT("gap_and_penetration_acceptance"),
		TEXT("journey_completion_rate"), TEXT("per_connection_replication"), TEXT("streaming_acceptance")})
		Unverified.Add(MakeShared<FJsonValueString>(Metric));
	Json->SetArrayField(TEXT("requires_separate_verification"), Unverified);
	FString Summary;
	return FJsonSerializer::Serialize(Json, TJsonWriterFactory<>::Create(&Summary))
		&& FFileHelper::SaveStringToFile(Frames.Data, *(Directory / TEXT("Frames.csv")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)
		&& FFileHelper::SaveStringToFile(Summary, *(Directory / TEXT("Summary.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

bool UEcoMoveTestSubsystem::WriteReport(const TCHAR* Result, const TCHAR* Reason) const
{
	FCsv Native{TEXT("step,world_s,region,seed,brain,deer,wolves,request,executed,policy_read,mask_bits,flight_override,route,gait,"
		"goal_kind,goal_id,goal_x_cm,goal_y_cm,arrived,flee_dir_x,flee_dir_y,base_dx_cm,base_dy_cm,"
		"pre_adapter_dx_cm,pre_adapter_dy_cm,pre_detour_dx_cm,pre_detour_dy_cm,final_dx_cm,final_dy_cm,"
		"start_x_cm,start_y_cm,start_z_cm,end_x_cm,end_y_cm,end_z_cm,actual_dx_cm,actual_dy_cm,actual_dz_cm,"
		"life_separation_dx_cm,life_separation_dy_cm,life_motion,social_control,boundary_steer,detour,detour_failed,obstacle_hit,"
		"island_steer,island_slide,move_rejected,alternative_accepted,ground_rejections,contact_rejections,intake,death_cause,"
		"static_mesh_hit,static_straight_block,static_final_block,static_hit_x_cm,static_hit_y_cm,static_hit_z_cm,"
		"static_hit_normal_x,static_hit_normal_y,static_hit_component,static_hit_item,body_radius_cm\n")};
	int32 GoalChanges = 0, GoalReversals = 0, BaseReversals = 0, FinalReversals = 0, ActualReversals = 0;
	int32 GroundRejectedSteps = 0, ContactRejectedSteps = 0, FlightStarts = 0, StepGaps = 0, ArrivedSteps = 0;
	int64 FirstFlightStep = -1;
	double TotalIntake = 0.;
	TSet<FString> Models, Seeds;
	for (int32 Index = 0; Index < Samples.Num(); ++Index)
	{
		const auto& S = Samples[Index];
		const FVector Delta = S.EndCm - S.StartCm;
		Native.Row(S.Step, S.WorldSeconds, S.Region, S.Seed, S.Brain, S.Deer, S.Wolves, S.Request, S.Executed,
			S.bPolicyRead, S.Mask, S.FlightOverride, S.Route, S.Gait, S.GoalKind, S.GoalId, S.GoalXYCm.X, S.GoalXYCm.Y,
			S.bArrived, S.FleeDirection.X, S.FleeDirection.Y, S.Base.X, S.Base.Y, S.BeforeAdapter.X, S.BeforeAdapter.Y,
			S.BeforeDetour.X, S.BeforeDetour.Y, S.Final.X, S.Final.Y, S.StartCm.X, S.StartCm.Y, S.StartCm.Z,
			S.EndCm.X, S.EndCm.Y, S.EndCm.Z, Delta.X, Delta.Y, Delta.Z, S.SeparationDelta.X, S.SeparationDelta.Y,
			S.LifeMotion, S.SocialControl, S.bBoundarySteer, S.bDetour, S.bDetourFailed, S.bObstacleHit,
			S.bIslandSteer, S.IslandSlide, S.bMoveRejected, S.bAlternativeAccepted, S.GroundRejections,
			S.ContactRejections, S.Intake, S.DeathCause, S.bStaticMeshHit, S.StaticMoveBlock, S.StaticFinalBlock,
			S.StaticHitPoint.X, S.StaticHitPoint.Y, S.StaticHitPoint.Z, S.StaticHitNormal.X, S.StaticHitNormal.Y,
			S.StaticHitComponent, S.StaticHitItem, double(S.BodyRadiusCm));
		Models.Add(S.Brain);
		Seeds.Add(LexToString(S.Seed));
		GroundRejectedSteps += S.GroundRejections > 0 ? 1 : 0;
		ContactRejectedSteps += S.ContactRejections > 0 ? 1 : 0;
		ArrivedSteps += S.bArrived ? 1 : 0;
		TotalIntake += S.Intake;
		const auto* Previous = Index > 0 ? &Samples[Index - 1] : nullptr;
		if (S.FlightOverride == EcoWorldV3::kKeepPanic)
		{
			if (FirstFlightStep < 0) FirstFlightStep = S.Step;
			if (Previous && Previous->Step + 1 == S.Step && Previous->Region == S.Region
				&& Previous->FlightOverride != EcoWorldV3::kKeepPanic) ++FlightStarts;
		}
		if (!Previous) continue;
		if (Previous->Step + 1 != S.Step || Previous->Region != S.Region)
		{
			++StepGaps;
			continue;
		}
		const bool bSameGoal = SameGoal(*Previous, S);
		GoalChanges += bSameGoal ? 0 : 1;
		BaseReversals += Reversed(Previous->Base, S.Base) ? 1 : 0;
		FinalReversals += Reversed(Previous->Final, S.Final) ? 1 : 0;
		const bool bReversed = Reversed(FVector2D(Previous->EndCm - Previous->StartCm), FVector2D(Delta));
		ActualReversals += bReversed ? 1 : 0;
		GoalReversals += bReversed && bSameGoal && !S.GoalKind.IsNone() && Previous->Executed == S.Executed ? 1 : 0;
	}

	FCsv Presentation{TEXT("world_s,state_s,native_samples_collected,sequence,region,actor_x_cm,actor_y_cm,actor_z_cm,"
		"state_x_cm,state_y_cm,state_z_cm,state_vx_cm_s,state_vy_cm_s,state_vz_cm_s,actor_yaw_deg,focus_yaw_deg,alive,discontinuity\n")};
	int32 YawReversals = 0;
	double PreviousTurn = 0.;
	for (int32 Index = 0; Index < VisualSamples.Num(); ++Index)
	{
		const auto& V = VisualSamples[Index];
		Presentation.Row(V.WorldSeconds, V.StateSeconds, V.NativeSamples, V.Sequence, V.Region, V.ActorCm.X, V.ActorCm.Y,
			V.ActorCm.Z, V.StateCm.X, V.StateCm.Y, V.StateCm.Z, V.StateVelocity.X, V.StateVelocity.Y, V.StateVelocity.Z,
			V.ActorYaw, V.FocusYaw, V.bAlive, V.bDiscontinuity);
		double Turn = 0.;
		if (Index > 0)
		{
			const auto& P = VisualSamples[Index - 1];
			if (!V.bDiscontinuity && V.bAlive && P.bAlive && V.Region == P.Region && V.WorldSeconds - P.WorldSeconds < .25)
				Turn = FMath::FindDeltaAngleDegrees(P.ActorYaw, V.ActorYaw);
		}
		if (Turn * PreviousTurn < 0. && FMath::Abs(Turn) >= 1. && FMath::Abs(PreviousTurn) >= 1.) ++YawReversals;
		PreviousTurn = Turn;
	}

	const auto Json = MakeShared<FJsonObject>();
	const UWorld& World = *GetWorld();
	Json->SetNumberField(TEXT("schema_version"), 1);
	Json->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
	Json->SetStringField(TEXT("run_id"), RunId);
	Json->SetStringField(TEXT("scenario"), TEXT("Observe"));
	Json->SetStringField(TEXT("mode"), bClient ? TEXT("Presentation") : TEXT("Authority"));
	Json->SetStringField(TEXT("map"), UWorld::RemovePIEPrefix(World.GetMapName()));
	Json->SetStringField(TEXT("world"), World.GetName());
	Json->SetStringField(TEXT("net_mode"), NetModeName(World.GetNetMode()));
	Json->SetStringField(TEXT("agent_id"), LexToString(AgentId));
	Json->SetStringField(TEXT("result"), Result);
	Json->SetStringField(TEXT("reason"), Reason);
	Json->SetNumberField(TEXT("elapsed_game_seconds"), World.GetTimeSeconds() - StartedAt);
	Json->SetNumberField(TEXT("native_step_seconds"), EcoRepertoireV3::kStepSeconds);
	Json->SetNumberField(TEXT("native_samples"), Samples.Num());
	Json->SetNumberField(TEXT("visual_samples"), VisualSamples.Num());
	if (bClient)
		Json->SetNumberField(TEXT("requested_game_seconds"), RequestedSteps * EcoRepertoireV3::kStepSeconds);
	else
		Json->SetNumberField(TEXT("requested_native_steps"), RequestedSteps);

	if (!Samples.IsEmpty())
	{
		TArray<TSharedPtr<FJsonValue>> ModelValues, SeedValues;
		for (const auto& Model : Models) ModelValues.Add(MakeShared<FJsonValueString>(Model));
		for (const auto& Seed : Seeds) SeedValues.Add(MakeShared<FJsonValueString>(Seed));
		Json->SetArrayField(TEXT("models"), ModelValues);
		Json->SetArrayField(TEXT("seeds"), SeedValues);
		Json->SetNumberField(TEXT("initial_region_deer"), Samples[0].Deer);
		Json->SetNumberField(TEXT("initial_region_wolves"), Samples[0].Wolves);
		const auto Metrics = MakeShared<FJsonObject>();
		Metrics->SetNumberField(TEXT("goal_changes"), GoalChanges);
		Metrics->SetNumberField(TEXT("actual_reversals_same_explicit_goal"), GoalReversals);
		Metrics->SetNumberField(TEXT("base_reversals"), BaseReversals);
		Metrics->SetNumberField(TEXT("final_reversals"), FinalReversals);
		Metrics->SetNumberField(TEXT("actual_reversals"), ActualReversals);
		Metrics->SetNumberField(TEXT("ground_rejected_steps"), GroundRejectedSteps);
		Metrics->SetNumberField(TEXT("contact_rejected_steps"), ContactRejectedSteps);
		Metrics->SetNumberField(TEXT("step_gaps_or_region_changes"), StepGaps);
		Metrics->SetNumberField(TEXT("observed_panic_onsets"), FlightStarts);
		if (FirstFlightStep >= 0) Metrics->SetStringField(TEXT("first_panic_sample_step"), LexToString(FirstFlightStep));
		Metrics->SetNumberField(TEXT("native_hide_arrived_steps"), ArrivedSteps);
		Metrics->SetNumberField(TEXT("intake"), TotalIntake);
		Json->SetObjectField(TEXT("native_metrics"), Metrics);
	}
	if (!VisualSamples.IsEmpty())
		Json->SetNumberField(TEXT("visual_yaw_direction_changes"), YawReversals);
	TArray<TSharedPtr<FJsonValue>> Missing;
	if (Samples.IsEmpty()) Missing.Add(MakeShared<FJsonValueString>(bClient ? TEXT("ClientHasPresentationOnly") : TEXT("NoNativeSamples")));
	if (VisualSamples.IsEmpty()) Missing.Add(MakeShared<FJsonValueString>(TEXT("NoLocalRepresentationSamples")));
	Json->SetArrayField(TEXT("missing_tracks"), Missing);

	FString Summary;
	const auto Writer = TJsonWriterFactory<>::Create(&Summary);
	const auto Save = [&](const FString& Value, const TCHAR* Name)
	{
		return FFileHelper::SaveStringToFile(Value, *(Directory / Name), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	};
	return FJsonSerializer::Serialize(Json, Writer)
		&& Save(Native.Data, TEXT("Samples.csv"))
		&& Save(Presentation.Data, TEXT("VisualSamples.csv"))
		&& Save(Summary, TEXT("Summary.json"));
}
#endif
