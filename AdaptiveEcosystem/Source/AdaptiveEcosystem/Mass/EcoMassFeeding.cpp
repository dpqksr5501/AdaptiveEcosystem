#include "Mass/EcoMassFeeding.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassEntityManager.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"

namespace
{
	void AddMembership(FMassEntityQuery& Query)
	{
		Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
		Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
		Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
		Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
		Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
		Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	}
}

bool EcoMassFeeding::FindNextTime(FMassEntityManager& Manager, double After, double& OutTime)
{
	if (!IsInGameThread() || Manager.IsProcessing()) return false;
	OutTime = TNumericLimits<double>::Max();
	bool bValid = true;
	FMassEntityQuery Query(Manager.AsShared());
	AddMembership(Query);
	Query.AddRequirement<FEcoLifetimeFragment>(EMassFragmentAccess::ReadOnly);
	FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
	Query.ForEachEntityChunk(Context, [&OutTime, &bValid, After](FMassExecutionContext& Chunk)
	{
		const auto Lives = Chunk.GetFragmentView<FEcoLifetimeFragment>();
		const auto Travel = Chunk.GetFragmentView<FEcoTravelFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			if (!FMath::IsFinite(Lives[I].NextFeedTimeSeconds) || !FMath::IsFinite(Lives[I].SpawnTimeSeconds)
				|| Lives[I].SpawnTimeSeconds < 0.0 || Lives[I].NextFeedTimeSeconds < Lives[I].SpawnTimeSeconds)
			{
				bValid = false;
				continue;
			}
			if (!Travel[I].bIsTraveling)
				OutTime = FMath::Min(OutTime, FMath::Max(After, Lives[I].NextFeedTimeSeconds));
		}
	});
	return bValid;
}

bool EcoMassFeeding::Collect(FMassEntityManager& Manager, const FEcoServerTimeSnapshot& Time, int64 StepId,
	const FEcoFeedingSettings& Settings, TArray<FEcoFeedRequest>& Out)
{
	Out.Reset();
	if (!IsInGameThread() || Manager.IsProcessing() || !Settings.IsValid()) return false;
	if (!Settings.bEnabled) return true;
	bool bValid = true;
	FMassEntityQuery Query(Manager.AsShared());
	AddMembership(Query);
	Query.AddRequirement<FEcoLifetimeFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoFeedingFragment>(EMassFragmentAccess::ReadWrite);
	FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
	// Stage requests in each entity's fragment. The callback reads only immutable value inputs.
	Query.ForEachEntityChunk(Context, [&Time, StepId, &Settings, &bValid](FMassExecutionContext& Chunk)
	{
		const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>();
		const auto Regions = Chunk.GetFragmentView<FEcoRegionFragment>();
		const auto Lives = Chunk.GetFragmentView<FEcoLifetimeFragment>();
		const auto Travel = Chunk.GetFragmentView<FEcoTravelFragment>();
		auto Feeding = Chunk.GetMutableFragmentView<FEcoFeedingFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			if (Feeding[I].bPending) { bValid = false; continue; }
			if (Travel[I].bIsTraveling || Lives[I].NextFeedTimeSeconds > Time.ServerTimeSeconds) continue;
			if (Ids[I].StableAgentId <= 0 || Regions[I].CurrentRegionIndex < 0 || Regions[I].CurrentRegionId.IsNone()
				|| !FMath::IsFinite(Lives[I].NextFeedTimeSeconds) || !FMath::IsFinite(Lives[I].SpawnTimeSeconds)
				|| Lives[I].SpawnTimeSeconds > Time.ServerTimeSeconds || Lives[I].NextFeedTimeSeconds <= Feeding[I].LastFeedTime)
			{
				bValid = false;
				continue;
			}
			FEcoFeedRequest& Request = Feeding[I].PendingRequest;
			Request.Food.RegionId = Regions[I].CurrentRegionId;
			Request.Food.StableAgentId = Ids[I].StableAgentId;
			Request.Food.RequestedAmount = Settings.Amount;
			Request.RegionIndex = Regions[I].CurrentRegionIndex;
			Request.WorldEpoch = Time.WorldEpoch;
			Request.StepId = StepId;
			Request.DueTime = Lives[I].NextFeedTimeSeconds;
			Feeding[I].bPending = true;
		}
	});
	if (!bValid) return false;
	// Deliberately sequential gather; never switch this to ParallelForEachEntityChunk.
	Query.ForEachEntityChunk(Context, [&Out](FMassExecutionContext& Chunk)
	{
		const auto Feeding = Chunk.GetFragmentView<FEcoFeedingFragment>();
		for (const FEcoFeedingFragment& Feed : Feeding)
			if (Feed.bPending) Out.Add(Feed.PendingRequest);
	});
	Out.Sort([](const FEcoFeedRequest& A, const FEcoFeedRequest& B)
	{
		return A.Food.StableAgentId < B.Food.StableAgentId;
	});
	return true;
}

bool EcoMassFeeding::Apply(FMassEntityManager& Manager, TConstArrayView<FEcoFeedResult> Results, double Interval)
{
	if (!IsInGameThread() || Manager.IsProcessing() || !FMath::IsFinite(Interval) || Interval <= 0.0) return false;
	TMap<int64, const FEcoFeedResult*> ById;
	for (const FEcoFeedResult& Result : Results)
	{
		if (ById.Contains(Result.Request.Food.StableAgentId) || !FMath::IsFinite(Result.GrantedAmount)
			|| Result.GrantedAmount < 0.0 || Result.GrantedAmount > Result.Request.Food.RequestedAmount) return false;
		ById.Add(Result.Request.Food.StableAgentId, &Result);
	}
	bool bValid = true;
	int32 Applied = 0;
	FMassEntityQuery Query(Manager.AsShared());
	AddMembership(Query);
	Query.AddRequirement<FEcoLifetimeFragment>(EMassFragmentAccess::ReadWrite);
	Query.AddRequirement<FEcoFeedingFragment>(EMassFragmentAccess::ReadWrite);
	FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
	Query.ForEachEntityChunk(Context, [&ById, &bValid, &Applied, Interval](FMassExecutionContext& Chunk)
	{
		const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>();
		const auto Regions = Chunk.GetFragmentView<FEcoRegionFragment>();
		const auto Travel = Chunk.GetFragmentView<FEcoTravelFragment>();
		auto Lives = Chunk.GetMutableFragmentView<FEcoLifetimeFragment>();
		auto Feeding = Chunk.GetMutableFragmentView<FEcoFeedingFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			const FEcoFeedResult* const* Found = ById.Find(Ids[I].StableAgentId);
			if (!Found) { if (Feeding[I].bPending) bValid = false; continue; }
			const FEcoFeedResult& Result = **Found;
			const FEcoFeedRequest& Pending = Feeding[I].PendingRequest;
			if (!Feeding[I].bPending || Travel[I].bIsTraveling || Pending.StepId != Result.Request.StepId
				|| Pending.WorldEpoch != Result.Request.WorldEpoch || Pending.DueTime != Result.Request.DueTime
				|| Lives[I].NextFeedTimeSeconds != Pending.DueTime || Pending.DueTime <= Feeding[I].LastFeedTime
				|| Regions[I].CurrentRegionId != Result.Request.Food.RegionId || Regions[I].CurrentRegionIndex != Result.Request.RegionIndex)
			{
				bValid = false;
				continue;
			}
			Feeding[I].LastFeedTime = Pending.DueTime;
			Feeding[I].LastGrantedAmount = Result.GrantedAmount;
			Feeding[I].TotalGrantedAmount += Result.GrantedAmount;
			Feeding[I].bPending = false;
			Lives[I].NextFeedTimeSeconds = Pending.DueTime + Interval;
			++Applied;
		}
	});
	return bValid && Applied == Results.Num();
}
