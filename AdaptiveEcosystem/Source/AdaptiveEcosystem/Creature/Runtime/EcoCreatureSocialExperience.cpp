#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"

#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Creature/Runtime/EcoFaunaDecision.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"

namespace
{
	using namespace EcoFaunaSocial;
	struct FParticipant
	{
		int64 Id;
		FName Kind, Region;
		FVector Position;
		const FProfile* Profile;
		EMedium Medium;
		float EyeHeight;
	};

	FIntPoint SocialCell(const FVector& Position)
	{
		constexpr double CellSize = 750.; // at least the largest profile range
		return {FMath::FloorToInt32(Position.X / CellSize), FMath::FloorToInt32(Position.Y / CellSize)};
	}

	bool ShareMediumAndSpace(const FParticipant& A, const FParticipant& B)
	{
		return A.Kind == B.Kind && A.Region == B.Region && A.Medium == B.Medium
			&& FVector::DistSquared(A.Position, B.Position) <= FMath::Square(A.Profile->RangeCm)
			&& (A.Medium != EMedium::Ground || FMath::Abs(A.Position.Z - B.Position.Z) <= 120.);
	}

	bool CanSeePeer(UWorld& World, const FParticipant& A, const FParticipant& B)
	{
		if (A.Medium != EMedium::Water)
			return EcoFaunaDecision::HasClearSight(World, A.Position, B.Position, A.EyeHeight, B.EyeHeight);
		if (!EcoCreatureMovement::HasClearWaterSight(World, A.Position, B.Position)) return false;
		for (const double Fraction : {0., .25, .5, .75, 1.})
		{
			EcoCreatureMovement::FFaunaWaterColumn Water;
			const FVector Sample = FMath::Lerp(A.Position, B.Position, Fraction);
			if (!EcoCreatureMovement::SampleFaunaWater(World, A.Region, Sample, .5, Water)
				|| Sample.Z < Water.Bottom || Sample.Z > Water.Surface) return false;
		}
		return true;
	}
}

void AEcoCreatureIntegrationSpawner::RankFaunaPartners(int64 Subject, TArrayView<int64> Candidates, double Now) const
{
	if (FaunaExperienceMode != 2 || Candidates.Num() < 2) return;
	const auto* Memory = FindFaunaExperience(Subject);
	if (!Memory || Memory->LongTerm.Partners.IsEmpty()) return;
	Candidates.StableSort([&](int64 Left, int64 Right) {
		return Memory->LongTerm.FamiliarityWith(Left, Now) > Memory->LongTerm.FamiliarityWith(Right, Now);
	});
}

void AEcoCreatureIntegrationSpawner::ProcessFaunaSocial(FMassEntityManager& Manager, double Now)
{
	using namespace EcoFaunaSocial;
	FaunaSocialPresentation.Reset();
	if (!RecordsFaunaExperience() || GetNetMode() == NM_Client)
	{
		FaunaSocialOffers.Reset();
		return;
	}
	TArray<FParticipant> Participants;
	Participants.Reserve(Owned.Num());
	for (const auto Entity : Owned)
	{
		const auto& Identity = Manager.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
		const auto* Profile = Profiles().Find(Identity.SpeciesId);
		const auto& Vitals = Manager.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
		const auto& Present = Manager.GetFragmentDataChecked<FEcoCreaturePresentationFragment>(Entity);
		if (!Profile || Vitals.HP <= 0.f || (Present.Flags & 6) || ((Present.Flags >> 4) & 3)
			|| !IsActivityCompatible(EEcoSpeciesActivity(Present.Activity))
			|| Manager.GetFragmentDataChecked<FEcoTravelFragment>(Entity).State != EEcoResidenceState::Resident) continue;
		const FName Region = Manager.GetFragmentDataChecked<FEcoRegionFragment>(Entity).CurrentRegionId;
		const FVector Position = Manager.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform().GetLocation();
		if (Region.IsNone() || Position.ContainsNaN()) continue;
		EMedium Medium = EMedium::Ground;
		float Eye = 65.f;
		if (const auto* Fauna = Manager.GetFragmentDataPtr<FEcoFaunaFragment>(Entity))
		{
			const auto* Species = FindFauna(Identity.SpeciesId);
			if (!Species || Fauna->TargetId > 0 || Fauna->AttackContact >= 0. || Now < Fauna->ThreatUntil
				|| Fauna->ShorePhase != EEcoFaunaShorePhase::None
				|| (Fauna->Flight != EEcoFaunaFlightPhase::Grounded && Fauna->Flight != EEcoFaunaFlightPhase::Cruise)) continue;
			Medium = Species->IsAquatic() || Fauna->bSwimming ? EMedium::Water
				: Fauna->Flight == EEcoFaunaFlightPhase::Cruise ? EMedium::Air : EMedium::Ground;
			Eye = Medium == EMedium::Ground ? Species->EyeHeight : 0.f;
		}
		else
		{
			const auto* Link = Manager.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
			if (!Link || !Link->bAdopted || Link->bDead || Link->Individual.Memory.Response == EcoLifeV3::EResponse::Retreat) continue;
			const auto* Policy = Manager.GetFragmentDataPtr<FEcoBehaviorStateFragment>(Entity);
			if (Policy && (Policy->Decision.KeepActive == EcoWorldV3::kKeepPanic || Policy->Decision.KeepActive == EcoWorldV3::kKeepShelter)) continue;
		}
		Participants.Add({Identity.StableAgentId, Identity.SpeciesId, Region, Position, Profile, Medium, Eye});
	}
	Participants.Sort([](const FParticipant& A, const FParticipant& B) { return A.Id < B.Id; });
	TMap<FIntPoint, TArray<int32>> Cells;
	TMap<int64, int32> ById;
	for (int32 Index = 0; Index < Participants.Num(); ++Index)
	{
		Cells.FindOrAdd(SocialCell(Participants[Index].Position)).Add(Index);
		ById.Add(Participants[Index].Id, Index);
	}
	const auto ReadMemory = [&](int64 Id) -> const FEcoFaunaLongTermExperience* {
		const auto* Memory = FindFaunaExperience(Id);
		return Memory ? &Memory->LongTerm : nullptr;
	};
	const auto Present = [&](const FParticipant& A, const FParticipant& B, ESignal SignalKind) {
		if (FaunaExperienceMode == 2)
			FaunaSocialPresentation.Add(A.Id, Pack(SignalKind, (B.Position - A.Position).Rotation().Yaw));
	};
	TSet<int64> Busy;
	for (auto Offer = FaunaSocialOffers.CreateIterator(); Offer; ++Offer)
	{
		const auto* AIndex = ById.Find(Offer.Key());
		const auto* BIndex = ById.Find(Offer.Value().Peer);
		const double Age = Now - Offer.Value().Started;
		if (AIndex && BIndex && Age > 0. && Age <= 2.5)
		{
			const auto& A = Participants[*AIndex];
			const auto& B = Participants[*BIndex];
			if (ShareMediumAndSpace(A, B) && CanSeePeer(*GetWorld(), A, B))
			{
				for (const auto End : {TPair<int64, int64>{A.Id, B.Id}, {B.Id, A.Id}})
				{
					RecordFaunaAssociation(End.Key, End.Value, Now, false);
					FaunaExperience.FindChecked(End.Key).LongTerm.LastSocialAt = Now;
					RecordGameplayReason(End.Key, A.Region, Now, TEXT("SocialExchangeCompleted"), End.Value);
					Busy.Add(End.Key);
				}
				Present(A, B, ESignal::Offer);
				Present(B, A, ESignal::Reply);
			}
		}
		Offer.RemoveCurrent();
	}
	for (const auto& A : Participants)
	{
		const auto* Memory = ReadMemory(A.Id);
		const auto Ready = [&](const FParticipant& Row, const FEcoFaunaLongTermExperience* Record) {
			if (FaunaExperienceMode == 2) return IsReady(*Row.Profile, Record, Now);
			return !Record || Record->LastSocialAt < 0. || Now >= Record->LastSocialAt + Row.Profile->Interval;
		};
		if (Busy.Contains(A.Id) || !Ready(A, Memory)) continue;
		struct FChoice { int32 Index; double Score; };
		TArray<FChoice, TInlineAllocator<5>> Closest;
		const auto Cell = SocialCell(A.Position);
		for (int32 Y = -1; Y <= 1; ++Y)
			for (int32 X = -1; X <= 1; ++X)
			{
				const auto* Bucket = Cells.Find(Cell + FIntPoint(X, Y));
				if (!Bucket) continue;
				for (const int32 Index : *Bucket)
				{
					const auto& B = Participants[Index];
					if (A.Id == B.Id || Busy.Contains(B.Id) || !ShareMediumAndSpace(A, B)) continue;
					const auto* Peer = ReadMemory(B.Id);
					if (!Ready(B, Peer)) continue;
					const double Familiarity = FaunaExperienceMode == 2
						? .5 * ((Memory ? Memory->FamiliarityWith(B.Id, Now) : 0.) + (Peer ? Peer->FamiliarityWith(A.Id, Now) : 0.)) : 0.;
					const double Score = Cost(*A.Profile, FVector::Dist(A.Position, B.Position), Familiarity);
					if (Closest.Num() == 4 && Score > Closest.Last().Score) continue;
					Closest.Add({Index, Score});
					Closest.Sort([](const FChoice& L, const FChoice& R) {
						return L.Score != R.Score ? L.Score < R.Score : L.Index < R.Index;
					});
					if (Closest.Num() > 4) Closest.Pop(EAllowShrinking::No);
				}
			}
		for (const auto& Choice : Closest)
		{
			const auto& B = Participants[Choice.Index];
			if (!CanSeePeer(*GetWorld(), A, B)) continue;
			FaunaSocialOffers.Add(A.Id, {B.Id, Now});
			Busy.Add(A.Id);
			Busy.Add(B.Id);
			Present(A, B, ESignal::Offer);
			break;
		}
	}
}
