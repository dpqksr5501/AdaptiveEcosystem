#include "AdaptiveEcosystem.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "MassCommonFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EcoMassPresentationFragments.h"
#include "Network/Mass/EcoMassClientBubble.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Network/EcoGameState.h"

#if !UE_BUILD_SHIPPING
namespace
{
	// Manual-only edits, outside Mass processing; no client RPC or simulation authority.
	void EditAuthorityAgent(UWorld* World, const FString& IdText, TFunctionRef<void(FMassEntityView&)> Edit)
	{
		int64 Id = 0;
		if (!IsInGameThread() || !World || !World->IsGameWorld() || World->GetNetMode() == NM_Client
			|| !LexTryParseString(Id, *IdText) || Id <= 0)
		{
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[M4 Edit] Requires a positive StableAgentId in the authority game world."));
			return;
		}
		auto* Spawner = World->GetSubsystem<UMassSpawnerSubsystem>();
		if (!Spawner) return;
		FMassEntityManager& Manager = Spawner->GetEntityManagerChecked();
		if (Manager.IsProcessing())
		{
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[M4 Edit] Mass is processing; retry next frame."));
			return;
		}
		TArray<FMassEntityHandle> Matches;
		FMassEntityQuery Query(Manager.AsShared());
		Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
		Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
		Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
		Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
		FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
		Query.ForEachEntityChunk(Context, [&](FMassExecutionContext& Chunk)
		{
			const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>();
			for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
				if (Ids[I].StableAgentId == Id) Matches.Add(Chunk.GetEntity(I));
		});
		if (Matches.Num() != 1)
		{
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[M4 Edit] World=%s ID=%lld expected one alive authority agent; found %d."),
				*World->GetName(), Id, Matches.Num());
			return;
		}
		FMassEntityView View(Manager, Matches[0]);
		Edit(View);
	}

	FAutoConsoleCommandWithWorldAndArgs SetVitals(
		TEXT("eco.M4.SetVitals"), TEXT("Manual authority edit: eco.M4.SetVitals <StableAgentId> <health ratio 0..1> <energy ratio 0..1>. HP=0 is committed by existing survival logic."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			float Health = 0.0f, Energy = 0.0f;
			if (Args.Num() != 3 || !LexTryParseString(Health, *Args[1]) || !LexTryParseString(Energy, *Args[2])
				|| !FMath::IsFinite(Health) || !FMath::IsFinite(Energy) || Health < 0 || Health > 1 || Energy < 0 || Energy > 1)
			{
				UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[M4 Edit] Usage: eco.M4.SetVitals <ID> <health 0..1> <energy 0..1>"));
				return;
			}
			EditAuthorityAgent(World, Args[0], [&](FMassEntityView& View)
			{
				auto* Vitals = View.GetFragmentDataPtr<FEcoVitalsFragment>();
				if (!Vitals) return;
				Vitals->HP = Health * Vitals->MaxHP;
				Vitals->Energy = Energy * Vitals->MaxEnergy;
				UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[M4 Edit] World=%s ID=%s Health=%.3f Energy=%.3f"),
					*World->GetName(), *Args[0], Health, Energy);
			});
		}));

	FAutoConsoleCommandWithWorldAndArgs Teleport(
		TEXT("eco.M4.Teleport"), TEXT("Manual authority edit: eco.M4.Teleport <StableAgentId> <X cm> <Y cm> <Z cm>. Increments reset revision."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			FVector Position;
			if (Args.Num() != 4 || !LexTryParseString(Position.X, *Args[1]) || !LexTryParseString(Position.Y, *Args[2])
				|| !LexTryParseString(Position.Z, *Args[3]) || !FMath::IsFinite(Position.X)
				|| !FMath::IsFinite(Position.Y) || !FMath::IsFinite(Position.Z))
			{
				UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[M4 Edit] Usage: eco.M4.Teleport <ID> <X cm> <Y cm> <Z cm>"));
				return;
			}
			EditAuthorityAgent(World, Args[0], [&](FMassEntityView& View)
			{
				auto* Transform = View.GetFragmentDataPtr<FTransformFragment>();
				auto* Reset = View.GetFragmentDataPtr<FEcoMovementDiscontinuityFragment>();
				if (!Transform || !Reset) return;
				Transform->GetMutableTransform().SetLocation(Position);
				++Reset->Revision;
				UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[M4 Edit] World=%s ID=%s Position=%s ResetRev=%u"),
					*World->GetName(), *Args[0], *Position.ToString(), Reset->Revision);
			});
		}));

	FAutoConsoleCommandWithWorldAndArgs NetworkDump(
		TEXT("eco.M4.Dump"), TEXT("Read-only M4 baseline counts/IDs in the selected PIE world. Use eco.M4.Dump details for rows."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (!IsInGameThread() || !World || !World->IsGameWorld()) return;
			UMassSpawnerSubsystem* Spawner = World->GetSubsystem<UMassSpawnerSubsystem>();
			if (!Spawner) return;
			FMassEntityManager& Manager = Spawner->GetEntityManagerChecked();
			if (Manager.IsProcessing())
			{
				UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[M4] Mass is processing; retry dump next frame."));
				return;
			}
			const bool bClient = World->GetNetMode() == NM_Client;
			const bool bDetails = Args.Contains(TEXT("details"));
			int32 Count = 0, Alive = 0, Duplicates = 0, InvalidIds = 0;
			TSet<int64> Seen;
			TArray<FString> Rows;
			FMassEntityQuery Query(Manager.AsShared());
			Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
			Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
			Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
			Query.AddTagRequirement<FEcoClientProxyTag>(bClient ? EMassFragmentPresence::All : EMassFragmentPresence::None);
			Query.AddTagRequirement<FEcoAuthorityTag>(bClient ? EMassFragmentPresence::None : EMassFragmentPresence::All);
			if (bClient) Query.AddRequirement<FEcoClientPresentationFragment>(EMassFragmentAccess::ReadOnly);
			else
			{
				Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
				Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
				Query.AddRequirement<FEcoVitalsRuntimeFragment>(EMassFragmentAccess::ReadOnly);
				Query.AddRequirement<FEcoDeathFragment>(EMassFragmentAccess::ReadOnly);
			}
			FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
			Query.ForEachEntityChunk(Context, [&](FMassExecutionContext& Chunk)
			{
				const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>();
				const auto Regions = Chunk.GetFragmentView<FEcoRegionFragment>();
				for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
				{
					++Count;
					InvalidIds += Ids[I].StableAgentId <= 0;
					Duplicates += Seen.Contains(Ids[I].StableAgentId);
					Seen.Add(Ids[I].StableAgentId);
					uint32 Sequence = 0;
					float Health = 0, Energy = 0;
					int32 Reason = 0, State = 0, Cause = 0;
					double ZeroSeconds = 0;
					FName Target = NAME_None;
					bool bAlive = Chunk.DoesArchetypeHaveTag<FEcoAliveTag>();
					if (bClient)
					{
						const auto& Presentation = Chunk.GetFragmentView<FEcoClientPresentationFragment>()[I];
						Sequence = Presentation.Current.SampleSequence;
						bAlive = Presentation.bHasSample && Presentation.Current.LifeState == EEcoVisualLifeState::Alive;
						Health = Presentation.Current.NormalizedHealth;
						Energy = Presentation.Current.NormalizedEnergy;
					}
					else
					{
						const auto& V = Chunk.GetFragmentView<FEcoVitalsFragment>()[I];
						const auto& T = Chunk.GetFragmentView<FEcoTravelFragment>()[I];
						Health = V.MaxHP > 0 ? V.HP / V.MaxHP : 0;
						Energy = V.MaxEnergy > 0 ? V.Energy / V.MaxEnergy : 0;
						Reason = static_cast<int32>(T.Reason);
						State = static_cast<int32>(T.State);
						Target = T.TargetRegionId;
						ZeroSeconds = Chunk.GetFragmentView<FEcoVitalsRuntimeFragment>()[I].ZeroEnergySeconds;
						Cause = static_cast<int32>(Chunk.GetFragmentView<FEcoDeathFragment>()[I].Cause);
					}
					Alive += bAlive;
					if (bDetails) Rows.Add(FString::Printf(TEXT("ID=%lld Species=%s Region=%s Alive=%d Sequence=%u Health=%.3f Energy=%.3f ZeroSeconds=%.3f State=%d Target=%s Reason=%d DeathCause=%d Position=%s"),
						Ids[I].StableAgentId, *Ids[I].SpeciesId.ToString(), *Regions[I].CurrentRegionId.ToString(), bAlive, Sequence,
						Health, Energy, ZeroSeconds, State, *Target.ToString(), Reason, Cause,
						*Chunk.GetFragmentView<FTransformFragment>()[I].GetTransform().GetLocation().ToString()));
				}
			});
			UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[M4] World=%s NetMode=%d Role=%s Entities=%d Alive=%d DuplicateIDs=%d InvalidIDs=%d"),
				*World->GetName(), static_cast<int32>(World->GetNetMode()), bClient ? TEXT("ClientProxy") : TEXT("Authority"), Count, Alive, Duplicates, InvalidIds);
			for (const FString& Row : Rows) UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[M4] %s"), *Row);
			if (const AEcoGameState* State = World->GetGameState<AEcoGameState>())
			{
				const auto& Summary = State->GetEcologySummary();
				for (const auto& R : Summary.Regions)
					UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Pressure] World=%s Epoch=%d Step=%lld Region=%s Pop=%d Resident=%d Out=%d In=%d Projected=%d Comfort=%d Crowding=%.3f Satisfaction=%.3f Pressure=%d StarvationDeaths=%lld ExternalDeaths=%lld"),
						*World->GetName(), Summary.Time.WorldEpoch, Summary.StepId, *R.RegionId.ToString(), R.Population, R.ResidentCount,
						R.OutboundCount, R.IncomingCount, R.ProjectedPopulation, R.EcologicalComfortPopulation, R.CrowdingRatio,
						R.FoodSatisfaction, R.bPressureActive, R.StarvationDeaths, R.ExternalDeaths);
			}
			for (TActorIterator<AEcoMassClientBubbleInfo> It(World); It; ++It)
			{
				const auto& Serializer = It->GetSerializer();
				UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[M4] Bubble=%s Entries=%d PendingAdds=%d"),
					*It->GetName(), Serializer.GetAgentItems().Num(), Serializer.Bubble.GetPendingAddCount());
#if UE_REPLICATION_COMPILE_SERVER_CODE
				if (!bClient)
				{
					const auto& Stats = Serializer.Bubble.GetReplicationStats();
					UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[M4 LOD] World=%s Bubble=%s Adds=%llu Removes=%llu (cumulative since creation/reset)"),
						*World->GetName(), *It->GetName(), Stats.Adds, Stats.Removes);
					int32 Counts[EMassLOD::Off] = {};
					for (const auto& Item : Serializer.GetAgentItems())
						if (Item.LastObservedLOD < EMassLOD::Off) ++Counts[Item.LastObservedLOD];
					for (int32 LOD = 0; LOD < EMassLOD::Off; ++LOD)
					{
						const auto& S = Stats.LOD[LOD];
						UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[M4 LOD] Bubble=%s LOD=%d Entries=%d Gated=%llu Checks=%llu Dirty=%llu Priority=%llu HighPromotions=%llu"),
							*It->GetName(), LOD, Counts[LOD], S.Gated, S.Checks, S.DirtySamples, S.PriorityChecks, S.HighPromotions);
					}
				}
#endif
				if (bDetails)
					for (const auto& Item : Serializer.GetAgentItems())
						UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[M4] Bubble=%s ID=%lld Template=%s Sequence=%u ServerRealTime=%.6f VisualRev=%u ResetRev=%u %s"),
							*It->GetName(), Item.Agent.GetStableAgentId(), *Item.Agent.GetTemplateID().ToString(),
							Item.Agent.MakeRepresentationSnapshot().SampleSequence, Item.Agent.MakeRepresentationSnapshot().ServerSampleRealTimeSeconds,
							Item.Agent.MakeRepresentationSnapshot().VisualRevision, Item.Agent.GetMovementDiscontinuityRevision(),
							bClient ? TEXT("ServerLOD=not replicated") : *FString::Printf(TEXT("LOD=%d Interval=%.3f LastCheck=%.6f"),
								static_cast<int32>(Item.LastObservedLOD), Item.ConfiguredUpdateInterval, Item.LastTransformCheckRealTime));
			}
		}));
}
#endif
