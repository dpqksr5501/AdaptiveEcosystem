#pragma once

#include "EcoRepertoire.h"
#include <algorithm>
#include <array>
#include <span>

namespace EcoPredictiveAvoidanceV3
{
	using EcoRepertoireV3::FVec2;
	inline constexpr std::size_t MaxCandidates = 8;
	inline constexpr double HorizonSteps = 8.;
	inline constexpr double GapMargin = .10;

	struct FAgent
	{
		std::int64_t Id;
		FVec2 Position, DesiredDelta;
		double Radius;
		bool bStill;
	};

	struct FApproach
	{
		double Gap;
		double AtStep;
	};

	/** Disc edge gap under constant relative motion, in native units. Negative means overlap. */
	inline FApproach ClosestApproach(const FAgent& Self, FVec2 Delta, const FAgent& Other, double Horizon)
	{
		namespace R = EcoRepertoireV3;
		const auto Offset = R::Sub(Other.Position, Self.Position);
		const auto Relative = R::Sub(Other.DesiredDelta, Delta);
		const double SpeedSquared = R::SizeSquared(Relative);
		const double Dot = Offset.X * Relative.X + Offset.Y * Relative.Y;
		const double At = SpeedSquared > 1.e-12 ? std::clamp(-Dot / SpeedSquared, 0., Horizon) : 0.;
		const auto Closest = R::Add(Offset, R::Scale(Relative, At));
		return {std::hypot(Closest.X, Closest.Y) - Self.Radius - Other.Radius, At};
	}

	struct FProposal
	{
		FVec2 Delta;
		std::int64_t RiskId = 0;
		double BaseGap = 0., ProposedGap = 0., ClosestAtStep = 0.;
		std::size_t Retained = 0, Dropped = 0, PairChecks = 0;
		bool bChanged = false;
	};

	/** Returns a direction proposal at the original speed. All inputs describe one pre-move instant. */
	inline FProposal Evaluate(std::span<const FAgent> Agents, std::size_t SelfIndex)
	{
		namespace R = EcoRepertoireV3;
		const auto& Self = Agents[SelfIndex];
		FProposal Result{Self.DesiredDelta};
		const double Speed = std::hypot(Self.DesiredDelta.X, Self.DesiredDelta.Y);
		struct FCandidate
		{
			std::size_t Index;
			FApproach Approach;
		};
		std::array<FCandidate, MaxCandidates> Candidates{};
		std::size_t Nearby = 0;
		for (std::size_t Index = 0; Index < Agents.size(); ++Index)
		{
			if (Index == SelfIndex) continue;
			const auto& Other = Agents[Index];
			const auto Offset = R::Sub(Other.Position, Self.Position);
			const double Reach = HorizonSteps * (Speed + std::hypot(Other.DesiredDelta.X, Other.DesiredDelta.Y))
				+ Self.Radius + Other.Radius + GapMargin;
			if (R::SizeSquared(Offset) > Reach * Reach) continue;
			++Nearby;
			++Result.PairChecks;
			const FCandidate Entry{Index, ClosestApproach(Self, Self.DesiredDelta, Other, HorizonSteps)};
			auto Before = [&](const FCandidate& Existing)
			{
				if (Entry.Approach.Gap != Existing.Approach.Gap) return Entry.Approach.Gap < Existing.Approach.Gap;
				if (Entry.Approach.AtStep != Existing.Approach.AtStep) return Entry.Approach.AtStep < Existing.Approach.AtStep;
				return Other.Id < Agents[Existing.Index].Id;
			};
			std::size_t Slot = 0;
			while (Slot < Result.Retained && !Before(Candidates[Slot])) ++Slot;
			if (Slot == MaxCandidates) continue;
			Result.Retained = std::min(Result.Retained + 1, MaxCandidates);
			for (std::size_t Move = Result.Retained - 1; Move > Slot; --Move) Candidates[Move] = Candidates[Move - 1];
			Candidates[Slot] = Entry;
		}

		Result.Dropped = Nearby - Result.Retained;
		if (Result.Retained == 0) return Result;
		const auto& Risk = Candidates.front();
		Result.RiskId = Agents[Risk.Index].Id;
		Result.BaseGap = Result.ProposedGap = Risk.Approach.Gap;
		Result.ClosestAtStep = Risk.Approach.AtStep;
		if (Self.bStill || Speed < 1.e-9 || Result.BaseGap >= GapMargin) return Result;

		// Try smaller turns first, with a consistent left preference at equal angle.
		// Evaluate against the same retained neighbors for every trial, including newly intersected ones.
		constexpr std::array Angles{20., -20., 40., -40., 65., -65.};
		for (double Degrees : Angles)
		{
			const double Angle = Degrees * 0.017453292519943295;
			const double C = std::cos(Angle);
			const double S = std::sin(Angle);
			const FVec2 Trial{Self.DesiredDelta.X * C - Self.DesiredDelta.Y * S,
				Self.DesiredDelta.X * S + Self.DesiredDelta.Y * C};
			double Gap = ClosestApproach(Self, Trial, Agents[Risk.Index], HorizonSteps).Gap;
			for (std::size_t Row = 1; Row < Result.Retained; ++Row)
				Gap = std::min(Gap, ClosestApproach(Self, Trial, Agents[Candidates[Row].Index], HorizonSteps).Gap);
			Result.PairChecks += Result.Retained;
			if (Gap <= Result.ProposedGap + 1.e-9) continue;
			Result.Delta = Trial;
			Result.ProposedGap = Gap;
			Result.bChanged = true;
			if (Gap >= GapMargin) break;
		}
		return Result;
	}
}
