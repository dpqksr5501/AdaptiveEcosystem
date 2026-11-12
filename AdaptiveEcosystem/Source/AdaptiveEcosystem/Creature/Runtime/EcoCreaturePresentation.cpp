#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
#include "Creature/Audio/EcoFootstepAudioComponent.h"
#include "Mass/EcoMassPresentationFragments.h"
#include "Core/EcoRuntimeSettings.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "GameFramework/PlayerController.h"
#include "Player/EcoCombatRelevanceComponent.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

void AEcoCreatureIntegrationSpawner::SyncVisuals(float Delta)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoCreature_Visuals);
	if (GetNetMode() == NM_DedicatedServer) return;
	auto* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>(); if (!Spawner) return;
	auto& EM = Spawner->GetEntityManagerChecked();
	const auto& Budget = GetDefault<UEcoRuntimeSettings>()->ConnectionBudget;
	const double Now = GetWorld()->GetRealTimeSeconds();
	struct FInput
	{
		int64 Id; FName Species; FName Region; FVector Position; float FacingYaw; FEcoCreaturePresentationFragment Visual;
		uint32 ResetRevision = 0; double Distance = 0.0;
	};
	TArray<FVector> Viewers;
	TArray<const UEcoCombatRelevanceComponent*> CombatViewers;
	for (auto It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
		if (const auto* PC = It->Get(); PC && PC->IsLocalController())
		{
			FVector P; FRotator R; PC->GetPlayerViewPoint(P, R); Viewers.Add(P);
			if (const APawn* Pawn = PC->GetPawn())
				if (const auto* Relevance = Pawn->FindComponentByClass<UEcoCombatRelevanceComponent>())
					CombatViewers.Add(Relevance);
		}
	TArray<FInput> Inputs;
	FMassEntityQuery Query(EM.AsShared());
	Query.AddTagRequirement<FEcoIntegratedCreatureTag>(EMassFragmentPresence::All);
	Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoCreaturePresentationFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoClientPresentationFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Query.AddRequirement<FEcoMovementDiscontinuityFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Query.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	FMassExecutionContext Context = EM.CreateExecutionContext(Delta);
	Query.ForEachEntityChunk(Context, [&](FMassExecutionContext& C)
	{
		if (GetNetMode() == NM_Client && (!C.GetFragmentView<FEcoVitalsFragment>().IsEmpty() || !C.GetFragmentView<FEcoPolicyOutputFragment>().IsEmpty()))
		{ FailRuntime(TEXT("Client contains authoritative fragments")); return; }
		const auto Ids = C.GetFragmentView<FEcoIdentityFragment>(); const auto T = C.GetFragmentView<FTransformFragment>();
		const auto V = C.GetFragmentView<FEcoCreaturePresentationFragment>(); const auto RegionsView = C.GetFragmentView<FEcoRegionFragment>();
		const auto Samples = C.GetFragmentView<FEcoClientPresentationFragment>();
		const auto Resets = C.GetFragmentView<FEcoMovementDiscontinuityFragment>();
		for (int32 I = 0; I < C.GetNumEntities(); ++I)
		{
			if (Ids[I].StableAgentId <= 0 || (!Samples.IsEmpty() && !Samples[I].bHasSample)) continue;
			const FVector Position = Samples.IsEmpty() ? T[I].GetTransform().GetLocation()
				: Samples[I].GetRenderPosition(Now, InterpolationDelaySeconds);
			double Distance = Viewers.IsEmpty() ? 0.0 : TNumericLimits<double>::Max();
			for (const auto& Viewer : Viewers) Distance = FMath::Min(Distance, FVector::DistSquared(Viewer, Position));
			if (GetNetMode() != NM_Client && !Viewers.IsEmpty() && Distance > FMath::Square(HostVisualDistance)) continue;
			// Filter before retention bias/combat priority: neither may keep a distant visual alive.
			// Client proxies and the authority simulation remain independent of local Actor selection.
			if (GetNetMode() == NM_Client && ClientVisualDistance > 0.0f
				&& (Viewers.IsEmpty() || Distance > FMath::Square(ClientVisualDistance))) continue;
			const uint32 Revision = Samples.IsEmpty() ? (Resets.IsEmpty() ? 0 : Resets[I].Revision) : Samples[I].Current.MovementDiscontinuityRevision;
			// A small retention bias prevents swapping equal-distance actors at the budget boundary.
			if (Visuals.Contains(Ids[I].StableAgentId)) Distance *= .81;
			const float FacingYaw = Samples.IsEmpty() ? T[I].GetTransform().Rotator().Yaw : Samples[I].Current.Rotation.Yaw;
			Inputs.Add({Ids[I].StableAgentId, Ids[I].SpeciesId, RegionsView[I].CurrentRegionId, Position, FacingYaw, V[I], Revision, Distance});
		}
	});
	if (!bReady) return;
	for (auto& Input : Inputs)
		for (const auto* Relevance : CombatViewers)
			if (Relevance->IsOffered(Input.Id)) { Input.Distance = -1; break; }
	Inputs.Sort([](const FInput& A, const FInput& B) { return A.Distance == B.Distance ? A.Id < B.Id : A.Distance < B.Distance; });
	if (Inputs.Num() > Budget.MaxActorRepresentations) Inputs.SetNum(Budget.MaxActorRepresentations);
	TSet<int64> Selected; for (const auto& Input : Inputs) Selected.Add(Input.Id);
	for (auto It = Visuals.CreateIterator(); It; ++It) if (!Selected.Contains(It.Key()))
	{
		if (auto* Actor = It.Value().Actor.Get()) { Actor->ClearBinding(); VisualPool.Add(Actor); }
		It.RemoveCurrent();
	}
	int32 Adds = 0;
	for (const auto& Input : Inputs)
	{
		auto* Existing = Visuals.Find(Input.Id);
		if (!Existing || !Existing->Actor.IsValid())
		{
			if (Adds >= Budget.MaxAddsPerUpdate) continue;
            const auto* Fauna = FindFauna(Input.Species);
            const auto Class = Fauna ? Fauna->VisualClass : Input.Species == TEXT("Wolf") ? WolfActorClass : HerbivoreActorClass;
			AEcoCreatureRepresentationActor* Actor = nullptr;
			for (int32 I = VisualPool.Num() - 1; I >= 0; --I)
				if (IsValid(VisualPool[I]) && VisualPool[I]->GetClass() == Class.Get())
				{ Actor = VisualPool[I]; VisualPool.RemoveAtSwap(I); break; }
			if (!Actor)
			{
				// A species switch can leave a full pool of incompatible classes.
				// Evict before spawning so active + hidden actors never exceed the cap.
				while (!VisualPool.IsEmpty() && Visuals.Num() + VisualPool.Num() >= Budget.MaxActorRepresentations)
				{ AEcoCreatureRepresentationActor* Retired = VisualPool.Pop(); if (Retired) Retired->Destroy(); }
				if (Visuals.Num() >= Budget.MaxActorRepresentations) continue;
				FActorSpawnParameters Params; Params.Owner = this; Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
				Actor = GetWorld()->SpawnActor<AEcoCreatureRepresentationActor>(Class, Input.Position, FRotator::ZeroRotator, Params);
			}
			if (!Actor || !Actor->BindIdentity(Input.Id, Input.Species)) { if (Actor) Actor->Destroy(); continue; }
			auto& Binding = Visuals.FindOrAdd(Input.Id); Binding.Actor = Actor; Binding.Sequence = 0; ++Adds;
			Existing = &Binding;
		}
		auto& Binding = *Existing;
		FEcoCreatureVisualState State; State.StableAgentId = Input.Id; State.SpeciesId = Input.Species; State.RegionId = Input.Region;
		// Local render serial only. Transport acceptance occurs exclusively in FEcoClientPresentationFragment.
		State.Sequence = ++Binding.Sequence; State.WorldTime = GetWorld()->GetTimeSeconds(); State.Position = Input.Position;
		State.bDiscontinuity = Binding.Sequence == 1 || Binding.MovementRevision != Input.ResetRevision;
		Binding.MovementRevision = Input.ResetRevision;
		State.Velocity = Input.Visual.Velocity; State.bAlive = (Input.Visual.Flags & 1) != 0;
		State.bHasFacing = true;
		State.FacingYawDegrees = Input.FacingYaw;
		State.bEating = (Input.Visual.Flags & 2) != 0; State.bPursuingPrey = (Input.Visual.Flags & 4) != 0;
		State.Activity = Input.Visual.Activity <= uint8(EEcoSpeciesActivity::CorpseSettled) ? EEcoSpeciesActivity(Input.Visual.Activity) : EEcoSpeciesActivity::Hold;
		State.SenseSource = EEcoSenseSource((Input.Visual.Flags>>4)&3);
		State.FocusYawDegrees = float(Input.Visual.FocusYaw)/182.0389f;
        State.BodyScale=Input.Visual.BodyScale/128.f;State.Maturity=Input.Visual.Maturity/255.f;State.CoatTone=Input.Visual.CoatTone/255.f;
        State.Appearance=EcoPresentationFlags::Appearance(Input.Visual.Flags);
		State.bHasVitals = (Input.Visual.Flags & 8) != 0;
		State.NormalizedHealth = Input.Visual.Health / 255.f; State.NormalizedEnergy = Input.Visual.Energy / 255.f;
		Binding.Actor->Footsteps->AudioSet = FootstepAudioSet;
		Binding.Actor->ConsumeVisualState(State, Delta);
	}
    TArray<int64> PresentedIds;
    for (const auto& Pair:Visuals)
        if (const auto* Actor=Pair.Value.Actor.Get(); Actor && Actor->bBound && !Actor->IsHidden() && Actor->VisualState.bAlive) PresentedIds.Add(Pair.Key);
    PresentedIds.Sort();
    for (auto It=GetWorld()->GetPlayerControllerIterator();It;++It)
        if (auto* PC=It->Get(); PC && PC->IsLocalController() && PC->GetPawn())
            if (auto* R=PC->GetPawn()->FindComponentByClass<UEcoCombatRelevanceComponent>()) R->SetPresented(this,PresentedIds);
	// Bound hidden pool separately: changing species mix must not grow retained actors without limit.
	const int32 MaxPool = FMath::Max(0, Budget.MaxActorRepresentations - Visuals.Num());
	while (VisualPool.Num() > MaxPool) { AEcoCreatureRepresentationActor* Actor = VisualPool.Pop(); if (Actor) Actor->Destroy(); }
}
