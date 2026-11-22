#pragma once

#include "CoreMinimal.h"

enum class EEcoExperienceActivity : uint8
{
	Patch, Carrion, Hunt, Passage, Perch, Refuge, Plants, Birth, Hatch, Provision, Rest, Shore, Cooling, Count
};

enum class EEcoExperienceOutcome : uint8
{
	Completed, RouteBlocked, TimedOut, ThreatInterrupted, HabitatUnavailable, Count
};

inline const TCHAR* LexToString(EEcoExperienceOutcome Outcome)
{
	switch (Outcome)
	{
	case EEcoExperienceOutcome::Completed: return TEXT("Completed");
	case EEcoExperienceOutcome::RouteBlocked: return TEXT("RouteBlocked");
	case EEcoExperienceOutcome::TimedOut: return TEXT("TimedOut");
	case EEcoExperienceOutcome::ThreatInterrupted: return TEXT("ThreatInterrupted");
	case EEcoExperienceOutcome::HabitatUnavailable: return TEXT("HabitatUnavailable");
	default: return TEXT("Unknown");
	}
}

struct FEcoExperienceKey
{
	EEcoExperienceActivity Activity;
	FName Region;
	FName Site;
	FIntVector Cell = FIntVector::ZeroValue;

	bool operator==(const FEcoExperienceKey& Other) const = default;

	static FIntVector SiteCell(const FVector& Position)
	{
		return FIntVector(FMath::FloorToInt32(Position.X / 100.), FMath::FloorToInt32(Position.Y / 100.),
			FMath::FloorToInt32(Position.Z / 100.));
	}

	static FIntVector PlantCell(const FVector& Position)
	{
		return FIntVector(FMath::FloorToInt32(Position.X / 400.), FMath::FloorToInt32(Position.Y / 400.), 0);
	}

	static FIntVector SpatialResourceCell(const FVector& Center)
	{
		return FIntVector(FMath::RoundToInt(Center.X), FMath::RoundToInt(Center.Y), 0);
	}
};

struct FEcoExperienceEstimate
{
	FEcoExperienceKey Key{};
	double UpdatedAt = 0.;
	EEcoExperienceOutcome LastOutcome = EEcoExperienceOutcome::Completed;
	double AccessAt = -1.;
	double Success = 0.;
	double Failure = 0.;
	double DangerAt = -1.;
	double Danger = 0.;
	double AvailabilityAt = -1.;
	double Unavailable = 0.;

	static constexpr double HalfLife = 120.;
	static constexpr double DangerHalfLife = 45.;
	static constexpr double AvailabilityHalfLife = 30.;
	static constexpr double MaxEvidence = 16.;
	static constexpr double SampleSpacing = 2.;
	static constexpr double MinPreference = .75;
	static constexpr double MaxPreference = 1.25;

	static double Decay(double Now, double At, double DecayHalfLife)
	{
		return At < 0. ? 0. : FMath::Pow(.5, FMath::Max(0., Now - At) / DecayHalfLife);
	}

	double Preference(double Now) const
	{
		const double Weight = Decay(Now, AccessAt, HalfLife);
		const double Reliability = (1. + Weight * Success) / (2. + Weight * (Success + Failure));
		const double RecentDanger = Danger * Decay(Now, DangerAt, DangerHalfLife);
		const double RecentUnavailability = Unavailable * Decay(Now, AvailabilityAt, AvailabilityHalfLife);
		return FMath::Clamp(1. + .5 * (Reliability - .5) - .20 * RecentDanger - .10 * RecentUnavailability,
			MinPreference, MaxPreference);
	}

	bool IsValid(double Now) const
	{
		const auto ValidTime = [&](double Time)
		{
			return FMath::IsFinite(Time) && (Time == -1. || (Time >= 0. && Time <= UpdatedAt));
		};
		return Key.Activity < EEcoExperienceActivity::Count && !Key.Region.IsNone()
			&& LastOutcome < EEcoExperienceOutcome::Count
			&& FMath::IsFinite(UpdatedAt) && UpdatedAt >= 0. && UpdatedAt <= Now + UE_SMALL_NUMBER
			&& ValidTime(AccessAt) && ValidTime(DangerAt) && ValidTime(AvailabilityAt)
			&& FMath::IsFinite(Danger) && Danger >= 0. && Danger <= 1.
			&& FMath::IsFinite(Unavailable) && Unavailable >= 0. && Unavailable <= 1.
			&& FMath::IsFinite(Success) && FMath::IsFinite(Failure) && Success >= 0. && Failure >= 0.
			&& Success + Failure <= MaxEvidence + UE_SMALL_NUMBER
			&& (AccessAt >= 0. || Success + Failure == 0.) && (DangerAt >= 0. || Danger == 0.)
			&& (AvailabilityAt >= 0. || Unavailable == 0.)
			&& (LastOutcome == EEcoExperienceOutcome::ThreatInterrupted ? DangerAt
				: LastOutcome == EEcoExperienceOutcome::HabitatUnavailable ? AvailabilityAt : AccessAt) == UpdatedAt;
	}

	bool Observe(double Now, EEcoExperienceOutcome Outcome)
	{
		if (Now < UpdatedAt) return false;
		if (Outcome == EEcoExperienceOutcome::ThreatInterrupted)
		{
			if (DangerAt >= 0. && Now < DangerAt + SampleSpacing) return false;
			Danger = FMath::Min(1., Danger * Decay(Now, DangerAt, DangerHalfLife) + .5);
			DangerAt = Now;
		}
		else if (Outcome == EEcoExperienceOutcome::HabitatUnavailable)
		{
			if (AvailabilityAt >= 0. && Now < AvailabilityAt + SampleSpacing) return false;
			Unavailable = FMath::Min(1., Unavailable * Decay(Now, AvailabilityAt, AvailabilityHalfLife) + .5);
			AvailabilityAt = Now;
		}
		else
		{
			if (AccessAt >= 0. && Now < AccessAt + SampleSpacing) return false;
			const double Weight = Decay(Now, AccessAt, HalfLife);
			Success = Weight * Success + (Outcome == EEcoExperienceOutcome::Completed ? 1. : 0.);
			Failure = Weight * Failure + (Outcome == EEcoExperienceOutcome::RouteBlocked ? 1.
				: Outcome == EEcoExperienceOutcome::TimedOut ? .5 : 0.);
			const double Scale = FMath::Min(1., MaxEvidence / (Success + Failure));
			Success *= Scale;
			Failure *= Scale;
			AccessAt = Now;
		}
		UpdatedAt = Now;
		LastOutcome = Outcome;
		return true;
	}
};

struct FEcoFaunaLongTermExperience
{
	struct FPartner
	{
		int64 AgentId = 0;
		double At = -1.;
		double Familiarity = 0.;
	};

	static constexpr int32 MaxPartners = 6;
	static constexpr double ConditionInterval = 10.;
	static constexpr double TemperamentHalfLife = 300.;
	static constexpr double FamiliarityHalfLife = 420.;

	double ConditionAt = -1.;
	double Condition = 0.;
	double ExplorationAt = -1.;
	double Exploration = 0.;
	double AssociationAt = -1.;
	double Association = 0.;
	double LastSocialAt = -1.;
	TArray<FPartner> Partners;

	void SampleCondition(double Now, double EnergyFraction)
	{
		if (!FMath::IsFinite(EnergyFraction) || !FMath::IsFinite(Now) || Now < 0.) return;
		if (ConditionAt < 0.)
		{
			ConditionAt = Now;
			return;
		}
		if (Now < ConditionAt + ConditionInterval) return;
		const double Signal = FMath::Clamp((EnergyFraction - .55) * 2., -1., 1.);
		// Count one observation after a gap. Unknown intervals are not evidence.
		const double Retained = FEcoExperienceEstimate::Decay(ConditionAt + ConditionInterval, ConditionAt, 120.);
		Condition = FMath::Lerp(Signal, Condition, Retained);
		ConditionAt = Now;
	}

	uint8 BodyConditionByte() const { return uint8(FMath::RoundToInt(128. + 16. * Condition)); }

	void ObserveExploration(double Now, EEcoExperienceOutcome Outcome)
	{
		if ((ExplorationAt >= 0. && Now < ExplorationAt + 20.) || Outcome >= EEcoExperienceOutcome::ThreatInterrupted) return;
		const double Signal = Outcome == EEcoExperienceOutcome::Completed ? .14
			: Outcome == EEcoExperienceOutcome::RouteBlocked ? -.14 : -.07;
		Exploration = FMath::Clamp(Exploration * FEcoExperienceEstimate::Decay(Now, ExplorationAt, TemperamentHalfLife)
			+ Signal, -1., 1.);
		ExplorationAt = Now;
	}

	double ExplorationFactor(double Now) const
	{
		return 1. + .20 * Exploration * FEcoExperienceEstimate::Decay(Now, ExplorationAt, TemperamentHalfLife);
	}

	double AssociationFactor(double Now) const
	{
		return 1. + .15 * Association * FEcoExperienceEstimate::Decay(Now, AssociationAt, TemperamentHalfLife);
	}

	double FamiliarityWith(int64 OtherId, double Now) const
	{
		const auto* Partner = Partners.FindByPredicate([&](const FPartner& Row) { return Row.AgentId == OtherId; });
		return Partner ? Partner->Familiarity * FEcoExperienceEstimate::Decay(Now, Partner->At, FamiliarityHalfLife) : 0.;
	}

	void ObservePartner(int64 OtherId, double Now, bool bCareOrBirth)
	{
		if (OtherId <= 0 || !FMath::IsFinite(Now) || Now < 0.) return;
		if (AssociationAt >= 0. && Now < AssociationAt) return;
		auto* Partner = Partners.FindByPredicate([&](const FPartner& Row) { return Row.AgentId == OtherId; });
		if (Partner && Now < Partner->At + (bCareOrBirth ? 5. : 20.)) return;
		if (!Partner)
		{
			if (Partners.Num() < MaxPartners) Partner = &Partners.AddDefaulted_GetRef();
			else
			{
				Partner = &Partners[0];
				for (auto& Row : Partners)
					if (Row.At < Partner->At) Partner = &Row;
			}
			*Partner = {OtherId};
		}
		Partner->Familiarity = FMath::Min(1., Partner->Familiarity
			* FEcoExperienceEstimate::Decay(Now, Partner->At, FamiliarityHalfLife) + (bCareOrBirth ? .35 : .10));
		Partner->At = Now;
		if (AssociationAt < 0. || Now >= AssociationAt + 20.)
		{
			Association = FMath::Min(1., Association * FEcoExperienceEstimate::Decay(Now, AssociationAt, TemperamentHalfLife) + .15);
			AssociationAt = Now;
		}
	}

	bool IsValid(int64 OwnerId, double Now) const
	{
		const auto Valid = [Now](double At, double Value, double Min) {
			return FMath::IsFinite(At) && FMath::IsFinite(Value)
				&& ((At == -1. && Value == 0.) || (At >= 0. && At <= Now + UE_SMALL_NUMBER && Value >= Min && Value <= 1.));
		};
		if (!Valid(LastSocialAt, 0., 0.) || !Valid(ConditionAt, Condition, -1.) || !Valid(ExplorationAt, Exploration, -1.)
			|| !Valid(AssociationAt, Association, 0.) || Partners.Num() > MaxPartners) return false;
		TSet<int64> Seen;
		for (const auto& Partner : Partners)
		{
			if (Partner.AgentId <= 0 || Partner.AgentId == OwnerId || Seen.Contains(Partner.AgentId)
				|| Partner.At < 0. || Partner.Familiarity <= 0. || !Valid(Partner.At, Partner.Familiarity, 0.)) return false;
			Seen.Add(Partner.AgentId);
		}
		return true;
	}
};

enum class EEcoEncounterKind : uint8 { Hunt, Risk, Patch, Plants, Carrion, Alarm, Escape, Defense, CarrionProvision, Count };
enum class EEcoEncounterMedium : uint8 { Ground, Water, Air, Count };

struct FEcoEncounterKey
{
	EEcoEncounterKind Kind = EEcoEncounterKind::Hunt;
	EEcoEncounterMedium Medium = EEcoEncounterMedium::Ground;
	FName Region;
	FName OtherSpecies;
	FName Site;
	FIntVector Cell = FIntVector::ZeroValue;
	bool operator==(const FEcoEncounterKey&) const = default;
};

struct FEcoEncounterEstimate
{
	FEcoEncounterKey Key;
	double At = -1.;
	double Success = 0.;
	double Setback = 0.;

	static constexpr double HalfLife = 150.;
	static constexpr double EvidenceCap = 12.;
	static constexpr double Strength = .45;
	static constexpr double MinFactor = .85;
	static constexpr double MaxFactor = 1.15;

	bool IsValid(double Now) const
	{
		return Key.Kind < EEcoEncounterKind::Count && Key.Medium < EEcoEncounterMedium::Count
			&& !Key.Region.IsNone() && !Key.OtherSpecies.IsNone()
			&& FMath::IsFinite(At) && At >= 0. && At <= Now + UE_SMALL_NUMBER
			&& FMath::IsFinite(Success) && FMath::IsFinite(Setback) && Success >= 0. && Setback >= 0.
			&& Success + Setback > 0. && Success + Setback <= EvidenceCap + UE_SMALL_NUMBER;
	}

	double Factor(double Now) const
	{
		const double Weight = FEcoExperienceEstimate::Decay(Now, At, HalfLife);
		const double Estimate = (1. + Success * Weight) / (2. + (Success + Setback) * Weight);
		return FMath::Clamp(1. + Strength * (Estimate - .5), MinFactor, MaxFactor);
	}

	void Observe(double Now, double Yield)
	{
		if (Now <= At) return;
		const double Weight = FEcoExperienceEstimate::Decay(Now, At, HalfLife);
		Success = Weight * Success + Yield;
		Setback = Weight * Setback + (1. - Yield);
		const double Scale = FMath::Min(1., EvidenceCap / (Success + Setback));
		Success *= Scale;
		Setback *= Scale;
		At = Now;
	}
};

struct FEcoFoodVisitKey
{
	EEcoEncounterKind Kind = EEcoEncounterKind::Plants;
	EEcoEncounterMedium Medium = EEcoEncounterMedium::Ground;
	FName Region;
	FName Site;
	FIntVector Cell = FIntVector::ZeroValue;
	bool bNight = false;

	bool operator==(const FEcoFoodVisitKey&) const = default;
};

struct FEcoFoodVisitEstimate
{
	FEcoFoodVisitKey Key;
	double EndedAt = -1.;
	double Evidence = 0.;
	double Shortfall = 0.;
	double LastDuration = 0.;
	static constexpr double HalfLife = 150.;
	static constexpr double MaxEvidence = 12.;

	bool IsValid(double Now) const
	{
		return (Key.Kind == EEcoEncounterKind::Patch || Key.Kind == EEcoEncounterKind::Plants
			|| Key.Kind == EEcoEncounterKind::Carrion) && Key.Medium < EEcoEncounterMedium::Count
			&& !Key.Region.IsNone() && FMath::IsFinite(EndedAt) && EndedAt >= 0. && EndedAt <= Now
			&& FMath::IsFinite(LastDuration) && LastDuration >= 0. && LastDuration <= EndedAt
			&& Evidence > 0. && Evidence <= MaxEvidence && Shortfall >= 0. && Shortfall <= Evidence;
	}

	void Observe(double End, double Duration, double Fill)
	{
		if (End <= EndedAt) return;
		const double Fade = FEcoExperienceEstimate::Decay(End, EndedAt, HalfLife);
		const double Combined = Evidence * Fade + 1.;
		Evidence = FMath::Min(MaxEvidence, Combined);
		Shortfall = (Shortfall * Fade + 1. - Fill) * (Evidence / Combined);
		EndedAt = End;
		LastDuration = Duration;
	}

	double Factor(double Now) const
	{
		const double Fade = FEcoExperienceEstimate::Decay(Now, EndedAt, HalfLife);
		// Two neutral prior visits limit the effect of a single poor stop.
		// As evidence ages, the unobserved site's priority is restored.
		return 1. - .5 * Shortfall * Fade / (2. + Evidence * Fade);
	}
};

struct FEcoFaunaExperience
{
	static constexpr int32 MaxSites = 16;
	static constexpr int32 MaxEncounters = 24;
	static constexpr int32 MaxInteractionEncounters = 16;
	static constexpr int32 MaxFoodVisits = 16;
	TArray<FEcoExperienceEstimate> Sites;
	TArray<FEcoEncounterEstimate> Encounters;
	TArray<FEcoFoodVisitEstimate> FoodVisits;
	FEcoFaunaLongTermExperience LongTerm;

	bool HasData() const
	{
		return !Sites.IsEmpty() || !Encounters.IsEmpty() || !FoodVisits.IsEmpty()
			|| LongTerm.ConditionAt >= 0. || LongTerm.ExplorationAt >= 0. || !LongTerm.Partners.IsEmpty();
	}

	void RetainBodyCondition()
	{
		if (!Sites.IsEmpty()) Sites.Reset();
		Encounters.Reset();
		FoodVisits.Reset();
		if (LongTerm.ExplorationAt < 0. && LongTerm.AssociationAt < 0. && LongTerm.LastSocialAt < 0. && LongTerm.Partners.IsEmpty()) return;
		FEcoFaunaLongTermExperience Retained;
		Retained.ConditionAt = LongTerm.ConditionAt;
		Retained.Condition = LongTerm.Condition;
		LongTerm = MoveTemp(Retained);
	}

	void ObserveFoodVisit(const FEcoFoodVisitKey& Key, double End, double Duration, double Fill)
	{
		auto* Visit = FoodVisits.FindByPredicate([&](const auto& Row) { return Row.Key == Key; });
		if (!Visit)
		{
			if (FoodVisits.Num() < MaxFoodVisits) Visit = &FoodVisits.AddDefaulted_GetRef();
			else
			{
				Visit = &FoodVisits[0];
				for (auto& Candidate : FoodVisits)
					if (Candidate.EndedAt < Visit->EndedAt) Visit = &Candidate;
				*Visit = {};
			}
			Visit->Key = Key;
		}
		Visit->Observe(End, Duration, Fill);
	}

	const FEcoEncounterEstimate* FindEncounter(const FEcoEncounterKey& Key) const
	{
		return Encounters.FindByPredicate([&](const FEcoEncounterEstimate& Entry) { return Entry.Key == Key; });
	}

	static bool IsInteractionEncounter(EEcoEncounterKind Kind) { return Kind >= EEcoEncounterKind::Alarm; }

	void ObserveEncounter(const FEcoEncounterKey& Key, double Now, double Yield)
	{
		if (!FMath::IsFinite(Now) || Now < 0. || !FMath::IsFinite(Yield) || Yield < 0. || Yield > 1.
			|| Key.OtherSpecies.IsNone() || Key.Region.IsNone() || Key.Kind >= EEcoEncounterKind::Count
			|| Key.Medium >= EEcoEncounterMedium::Count) return;
		if (auto* Entry = Encounters.FindByPredicate([&](const auto& Row) { return Row.Key == Key; }))
		{
			Entry->Observe(Now, Yield);
			return;
		}
		const bool bInteraction = IsInteractionEncounter(Key.Kind);
		const int32 Limit = bInteraction ? MaxInteractionEncounters : MaxEncounters;
		int32 Count = 0;
		FEcoEncounterEstimate* Oldest = nullptr;
		for (auto& Entry : Encounters)
		{
			if (IsInteractionEncounter(Entry.Key.Kind) != bInteraction) continue;
			++Count;
			if (!Oldest || Entry.At < Oldest->At) Oldest = &Entry;
		}
		if (Count < Limit)
		{
			Encounters.Add({Key, Now, Yield, 1. - Yield});
			return;
		}
		if (Oldest && Now >= Oldest->At) *Oldest = {Key, Now, Yield, 1. - Yield};
	}

	double Preference(const FEcoExperienceKey& Key, double Now) const
	{
		const auto* Entry = Sites.FindByPredicate([&](const auto& Site) { return Site.Key == Key; });
		return Entry ? Entry->Preference(Now) : 1.;
	}

	bool Observe(const FEcoExperienceKey& Key, double Now, EEcoExperienceOutcome Outcome)
	{
		if (!FMath::IsFinite(Now) || Now < 0. || Key.Region.IsNone() || Key.Activity >= EEcoExperienceActivity::Count
			|| Outcome >= EEcoExperienceOutcome::Count)
			return false;
		auto* Entry = Sites.FindByPredicate([&](const auto& Site) { return Site.Key == Key; });
		if (!Entry)
		{
			if (Sites.Num() < MaxSites) Entry = &Sites.AddDefaulted_GetRef();
			else
			{
				int32 ActivityCounts[uint8(EEcoExperienceActivity::Count)]{};
				for (const auto& Site : Sites) ++ActivityCounts[uint8(Site.Key.Activity)];
				++ActivityCounts[uint8(Key.Activity)];
				Entry = &Sites[0];
				for (auto& Site : Sites)
				{
					const int32 SiteCount = ActivityCounts[uint8(Site.Key.Activity)];
					const int32 EntryCount = ActivityCounts[uint8(Entry->Key.Activity)];
					if (SiteCount > EntryCount || (SiteCount == EntryCount && Site.UpdatedAt < Entry->UpdatedAt))
						Entry = &Site;
				}
				if (Now < Entry->UpdatedAt) return false;
			}
			*Entry = {Key};
		}
		return Entry->Observe(Now, Outcome);
	}
};

inline const TCHAR* LexToString(EEcoExperienceActivity Activity)
{
	switch (Activity)
	{
	case EEcoExperienceActivity::Patch: return TEXT("Patch");
	case EEcoExperienceActivity::Carrion: return TEXT("Carrion");
	case EEcoExperienceActivity::Hunt: return TEXT("Hunt");
	case EEcoExperienceActivity::Passage: return TEXT("Passage");
	case EEcoExperienceActivity::Perch: return TEXT("Perch");
	case EEcoExperienceActivity::Refuge: return TEXT("Refuge");
	case EEcoExperienceActivity::Plants: return TEXT("Plants");
	case EEcoExperienceActivity::Birth: return TEXT("Birth");
	case EEcoExperienceActivity::Hatch: return TEXT("Hatch");
	case EEcoExperienceActivity::Provision: return TEXT("Provision");
	case EEcoExperienceActivity::Rest: return TEXT("Rest");
	case EEcoExperienceActivity::Shore: return TEXT("Shore");
	case EEcoExperienceActivity::Cooling: return TEXT("Cooling");
	default: return TEXT("Unknown");
	}
}
