#include "Debug/EcoCameraMassDebug.h"

#include "Engine/World.h"

#if !UE_BUILD_SHIPPING
#include "AI/Policy/EcoRepertoire.h"
#include "AI/Policy/EcoV3ObserverCamera.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "DrawDebugHelpers.h"
#include "Engine/Engine.h"
#include "HAL/IConsoleManager.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassDebugger.h"
#include "MassEntityQuery.h"
#include "MassEntitySubsystem.h"
#include "MassEntityView.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"

#if WITH_EDITOR
#include "Framework/Docking/TabManager.h"
#include "Widgets/Docking/SDockTab.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SNullWidget.h"
#include "Widgets/Text/STextBlock.h"
#endif

namespace
{
#if WITH_EDITOR
	const FName MassDebuggerTabId(TEXT("MassDebugger"));
	TWeakPtr<SDockTab> ConnectedDebuggerTab;
	TWeakObjectPtr<UEcoCameraMassDebug> DebuggerTabSource;
#endif
#if WITH_MASSENTITY_DEBUG
	// The engine selection environment is world-specific, but its drawing range is process-wide.
	TWeakObjectPtr<UEcoCameraMassDebug> DebugRangeOwner;
#endif

	void RunDebugCommand(UWorld* World, TFunctionRef<void(UEcoCameraMassDebug&)> Action)
	{
		if (auto* Debug = World ? World->GetSubsystem<UEcoCameraMassDebug>() : nullptr)
		{
			Action(*Debug);
			return;
		}
		UE_LOG(LogEcoV3Cam, Display, TEXT("Start PIE with a local player to use camera Mass debug."));
	}

	FAutoConsoleCommandWithWorldAndArgs CmdCameraMassDebug(
		TEXT("eco.Cam.MassDebug"), TEXT("Show the current camera subject in ECO INSPECTOR and draw its movement. Usage: eco.Cam.MassDebug 0|1"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (Args.Num() != 1 || (Args[0] != TEXT("0") && Args[0] != TEXT("1")))
			{
				UE_LOG(LogEcoV3Cam, Display, TEXT("Usage: eco.Cam.MassDebug 0|1"));
				return;
			}
			RunDebugCommand(World, [&](UEcoCameraMassDebug& Debug) { Debug.SetEnabled(Args[0] == TEXT("1")); });
		}));

	FAutoConsoleCommandWithWorld CmdOpenCameraMassDebug(
		TEXT("eco.Cam.MassDebug.Open"), TEXT("Open the editor Mass Debugger for inspection while playing in editor."),
		FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
		{
			RunDebugCommand(World, [](UEcoCameraMassDebug& Debug) { Debug.OpenDebugger(); });
		}));
}
#endif

bool UEcoCameraMassDebug::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return !UE_BUILD_SHIPPING && Super::ShouldCreateSubsystem(Outer) && World && World->IsGameWorld();
}

void UEcoCameraMassDebug::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
#if !UE_BUILD_SHIPPING
	PostTickHandle = FWorldDelegates::OnWorldPostActorTick.AddUObject(this, &UEcoCameraMassDebug::PostActorTick);
#endif
}

void UEcoCameraMassDebug::Deinitialize()
{
#if !UE_BUILD_SHIPPING
	FWorldDelegates::OnWorldPostActorTick.Remove(PostTickHandle);
	ClearTarget();
#endif
	Super::Deinitialize();
}

void UEcoCameraMassDebug::OnWorldEndPlay(UWorld& InWorld)
{
#if !UE_BUILD_SHIPPING
	bEnabled = false;
	ClearTarget();
#endif
	Super::OnWorldEndPlay(InWorld);
}

#if !UE_BUILD_SHIPPING
void UEcoCameraMassDebug::SetEnabled(bool bEnable)
{
	if (bEnable && (!GEngine || !GEngine->GetFirstLocalPlayerController(GetWorld())
		|| !GetWorld()->GetSubsystem<UEcoV3ObserverCameraSubsystem>()))
	{
		UE_LOG(LogEcoV3Cam, Display, TEXT("Camera Mass debug requires a local observation camera."));
		return;
	}
	const bool bReselect = bEnabled && bEnable;
	bEnabled = bEnable;
	if (bEnabled)
	{
		PostActorTick(GetWorld(), LEVELTICK_All, 0.0f);
		if (bReselect && MassSelection.IsSet()) SelectMassEntity();
#if WITH_EDITOR
		ConnectDebuggerTab();
		UE_LOG(LogEcoV3Cam, Display, TEXT("%s"), *DescribeMassSelection());
#endif
	}
	else
	{
		ClearTarget();
		RequestedId = 0;
	}
	UE_LOG(LogEcoV3Cam, Display, TEXT("%s"), bEnabled ? *Describe() : TEXT("Camera Mass debug off."));
}

void UEcoCameraMassDebug::OpenDebugger()
{
#if WITH_EDITOR && WITH_MASSENTITY_DEBUG
	if (GetWorld()->WorldType == EWorldType::PIE
		&& IConsoleManager::Get().ProcessUserConsoleInput(TEXT("mass.debug"), *GLog, GetWorld()))
	{
		ConnectDebuggerTab();
		UE_LOG(LogEcoV3Cam, Display, TEXT("%s"), *DescribeMassSelection());
		return;
	}
#endif
	UE_LOG(LogEcoV3Cam, Display, TEXT("The Mass Debugger tab requires Play In Editor in the editor process."));
}

#if WITH_EDITOR
void UEcoCameraMassDebug::ConnectDebuggerTab()
{
	if (GetWorld()->WorldType != EWorldType::PIE) return;
	const auto Tab = FGlobalTabmanager::Get()->FindExistingLiveTab(MassDebuggerTabId);
	if (!Tab) return;

	DebuggerTabSource = this;
	if (ConnectedDebuggerTab.Pin() == Tab) return;
	ConnectedDebuggerTab = Tab;
	const TSharedRef<SWidget> MassDebuggerContent = Tab->GetContent();
	Tab->SetContent(SNullWidget::NullWidget);
	Tab->SetContent(
		SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight().Padding(8.f, 4.f)
		[
			SNew(STextBlock)
			.Text_Lambda([]()
			{
				const auto* Source = DebuggerTabSource.Get();
				return FText::FromString(Source ? Source->DescribeMassSelection() : TEXT("Eco Camera | No active PIE world"));
			})
		]
		+ SVerticalBox::Slot().FillHeight(1.f)
		[
			MassDebuggerContent
		]);
}

FString UEcoCameraMassDebug::DescribeMassSelection() const
{
	const FString WorldName = GetWorld()->GetDebugDisplayName();
	if (!bEnabled) return FString::Printf(TEXT("Eco Camera | %s | Run eco.Cam.MassDebug 1 in PIE"), *WorldName);
	if (GetWorld()->GetNetMode() == NM_Client)
		return FString::Printf(TEXT("Eco Camera | %s | Client presentation | Stable ID #%lld"), *WorldName, AgentId);
	if (!MassSelection.IsSet())
		return FString::Printf(TEXT("Eco Camera | %s | Waiting for a tracked Mass entity"), *WorldName);
	return FString::Printf(TEXT("Eco Camera | %s | Stable ID #%lld | Mass Entity %s"),
		*WorldName, AgentId, *MassSelection.DebugGetDescription());
}
#endif

void UEcoCameraMassDebug::ClearTarget()
{
	ClearMassSelection();
	Entity = {};
	AgentId = 0;
	Region = NAME_None;
	NativeSample.Reset();
	Trail.Reset();
	NextTrailAt = 0.0;
}

void UEcoCameraMassDebug::ResolveTarget(int64 Id)
{
	auto* Mass = GetWorld()->GetSubsystem<UMassEntitySubsystem>();
	if (!Mass) return;
	FMassEntityManager& Manager = Mass->GetMutableEntityManager();
	FMassEntityQuery Query(Manager.AsShared());
	Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	auto Exec = Manager.CreateExecutionContext(0);
	Query.ForEachEntityChunk(Exec, [&](FMassExecutionContext& Context)
	{
		if (Entity.IsSet()) return;
		const auto Ids = Context.GetFragmentView<FEcoIdentityFragment>();
		for (int32 Index = 0; Index < Ids.Num(); ++Index)
		{
			if (Ids[Index].StableAgentId == Id)
			{
				Entity = Context.GetEntity(Index);
				break;
			}
		}
	});
}

void UEcoCameraMassDebug::SelectMassEntity()
{
#if WITH_MASSENTITY_DEBUG
	auto* Mass = GetWorld()->GetSubsystem<UMassEntitySubsystem>();
	if (!Mass || !Entity.IsSet()) return;
	const FMassEntityManager& Manager = Mass->GetEntityManager();
	if (FMassDebugger::FindEnvironmentForEntityManager(Manager) && Manager.IsEntityActive(Entity))
	{
		FMassDebugger::SelectEntity(Manager, Entity);
		MassSelection = Entity;
		DebugRangeOwner = this;
	}
#endif
}

void UEcoCameraMassDebug::ClearMassSelection()
{
#if WITH_MASSENTITY_DEBUG
	if (!MassSelection.IsSet()) return;
	if (auto* Mass = GetWorld()->GetSubsystem<UMassEntitySubsystem>())
	{
		const FMassEntityManager& Manager = Mass->GetEntityManager();
		if (auto* Env = FMassDebugger::FindEnvironmentForEntityManager(Manager); Env && Env->SelectedEntity == MassSelection)
		{
			Env->SelectedEntity = {};
			FMassDebugger::OnEntitySelectedDelegate.Broadcast(Manager, {});
		}
	}
	if (DebugRangeOwner.Get() == this)
	{
		int32 Begin = INDEX_NONE, End = INDEX_NONE;
		if (UE::Mass::Debug::GetDebugEntitiesRange(Begin, End) && Begin == MassSelection.Index && End == Begin)
		{
			IConsoleManager::Get().ProcessUserConsoleInput(TEXT("mass.debug.ResetDebugEntity"), *GLog, GetWorld());
		}
		DebugRangeOwner.Reset();
	}
	MassSelection = {};
#endif
}

void UEcoCameraMassDebug::PostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
	if (World != GetWorld() || !bEnabled) return;
	const auto* Camera = World->GetSubsystem<UEcoV3ObserverCameraSubsystem>();
	const int64 Id = Camera ? Camera->GetSubjectId() : 0;
	if (Id != RequestedId)
	{
		ClearTarget();
		RequestedId = Id;
		NextResolveAt = 0.0;
	}
	if (Id <= 0) return;

	const double Now = World->GetTimeSeconds();
	if (World->GetNetMode() == NM_Client)
	{
		if (const auto* Actor = EcoV3Observe::FindActor(*World, Id); Actor && !Actor->IsHidden() && Actor->VisualState.bAlive)
		{
			AgentId = Id;
			if (Region != Actor->VisualState.RegionId) Trail.Reset();
			Region = Actor->VisualState.RegionId;
			DrawMovement(Actor->GetActorLocation(), Actor->VisualState.Velocity, Now);
		}
		else
		{
			ClearTarget();
		}
		return;
	}

	auto* Mass = World->GetSubsystem<UMassEntitySubsystem>();
	if (!Mass || Mass->GetEntityManager().IsProcessing()) return;
	const FMassEntityManager& Manager = Mass->GetEntityManager();
	auto IsTarget = [Id](const FMassEntityView& View)
	{
		const auto* Identity = View.IsSet() ? View.GetFragmentDataPtr<FEcoIdentityFragment>() : nullptr;
		return Identity && Identity->StableAgentId == Id && View.HasTag<FEcoAliveTag>() && View.HasTag<FEcoAuthorityTag>();
	};
	FMassEntityView View = FMassEntityView::TryMakeView(Manager, Entity);
	if (!IsTarget(View))
	{
		if (AgentId > 0 || Entity.IsSet()) ClearTarget();
		if (Now < NextResolveAt) return;
		NextResolveAt = Now + 0.2;
		ResolveTarget(Id);
		View = FMassEntityView::TryMakeView(Manager, Entity);
		if (!IsTarget(View)) return;
	}
	AgentId = Id;
	if (const auto* Place = View.GetFragmentDataPtr<FEcoRegionFragment>(); Place && Region != Place->CurrentRegionId)
	{
		Region = Place->CurrentRegionId;
		Trail.Reset();
		if (NativeSample.IsSet() && NativeSample->Region != Region) NativeSample.Reset();
	}
	if (!MassSelection.IsSet()) SelectMassEntity();
	const auto* Velocity = View.GetFragmentDataPtr<FMassVelocityFragment>();
	DrawMovement(View.GetFragmentData<FTransformFragment>().GetTransform().GetLocation(),
		Velocity ? Velocity->Value : FVector::ZeroVector, Now);
}

void UEcoCameraMassDebug::RecordNative(int64 Id, const FEcoMoveTestSample& Sample)
{
	if (Id == AgentId && Id > 0) NativeSample = Sample;
}

void UEcoCameraMassDebug::DrawMovement(const FVector& Location, const FVector& Velocity, double Now)
{
	const FVector Feet = Location + FVector(0, 0, 10);
	DrawDebugSphere(GetWorld(), Feet, 32.f, 12, FColor::Cyan, false, 0.f, 0, 1.5f);
	if (!Trail.IsEmpty() && FVector::DistSquared(Trail.Last(), Feet) > FMath::Square(1000.0)) Trail.Reset();
	if (Trail.IsEmpty() || Now >= NextTrailAt)
	{
		constexpr int32 MaxTrailPoints = 41;
		if (Trail.Num() >= MaxTrailPoints) Trail.RemoveAt(0, 1, EAllowShrinking::No);
		Trail.Add(Feet);
		NextTrailAt = Now + 0.1;
	}
	for (int32 Index = 1; Index < Trail.Num(); ++Index)
	{
		DrawDebugLine(GetWorld(), Trail[Index - 1], Trail[Index], FColor::Cyan, false, 0.f, 0, 2.f);
	}
	DrawDebugLine(GetWorld(), Trail.Last(), Feet, FColor::Cyan, false, 0.f, 0, 2.f);

	constexpr double ArrowSeconds = 0.4;
	const auto Arrow = [&](const FVector& V, double Height, FColor Color)
	{
		const FVector Start = Feet + FVector(0, 0, Height);
		if (!V.IsNearlyZero(1.0))
			DrawDebugDirectionalArrow(GetWorld(), Start, Start + (V * ArrowSeconds).GetClampedToMaxSize(1500.0), 22.f, Color, false, 0.f, 0, 3.f);
	};
	Arrow(Velocity, 37., FColor::Green);
	if (!NativeSample.IsSet() || Now - NativeSample->WorldSeconds > 1.0) return;

	const auto& Sample = NativeSample.GetValue();
	Arrow(FVector(Sample.BeforeAdapter, 0.) / EcoRepertoireV3::kStepSeconds, 58., FColor::Yellow);
	Arrow(FVector(Sample.Final, 0.) / EcoRepertoireV3::kStepSeconds, 79., FColor(70, 140, 255));
	if (!Sample.GoalKind.IsNone())
	{
		const FVector Goal(Sample.GoalXYCm, Feet.Z + 15.);
		DrawDebugLine(GetWorld(), Feet, Goal, FColor::Magenta, false, 0.f, 0, 1.f);
		DrawDebugSphere(GetWorld(), Goal, 42.f, 12, FColor::Magenta, false, 0.f, 0, 2.f);
	}
}

FString UEcoCameraMassDebug::Describe() const
{
	if (!bEnabled) return {};
	if (AgentId <= 0) return TEXT("Mass debug: follow a live creature (1 / 2).");
	if (GetWorld()->GetNetMode() == NM_Client)
		return FString::Printf(TEXT("Mass debug #%lld | Client presentation\nGreen: velocity  Cyan: trail"), AgentId);

	FString Line = FString::Printf(TEXT("Mass debug #%lld | Green: velocity  Cyan: trail"), AgentId);
	if (NativeSample.IsSet() && GetWorld()->GetTimeSeconds() - NativeSample->WorldSeconds <= 1.0)
	{
		Line += TEXT("\nYellow: intent  Blue: final request");
		if (!NativeSample->GoalKind.IsNone()) Line += TEXT("\nMagenta XY: ") + NativeSample->GoalKind.ToString();
	}
	return Line;
}
#endif
