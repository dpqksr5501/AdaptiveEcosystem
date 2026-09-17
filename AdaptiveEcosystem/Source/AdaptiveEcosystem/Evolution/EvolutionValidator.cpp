// Copyright Epic Games, Inc. All Rights Reserved.

#include "Evolution/EvolutionValidator.h"
#include "AdaptiveEcosystem.h"

bool UEvolutionValidator::IsValidFloat(float Value)
{
	return FMath::IsFinite(Value) && !FMath::IsNaN(Value);
}

FEvolutionValidationResult UEvolutionValidator::ValidateAndApplyProposal(
	const FSpeciesEvolutionProfile& CurrentProfile,
	const FEvolutionProposal& Proposal,
	int32 ExpectedWorldEpoch,
	int32 ExpectedContextRevision,
	float MutationBudget,
	float MaxDeltaPerGen)
{
	FEvolutionValidationResult Result;
	Result.bAccepted = false;
	Result.CommittedProfile = CurrentProfile;

	// 1. Check Staleness
	if (Proposal.WorldEpoch != ExpectedWorldEpoch)
	{
		Result.RejectReason = FString::Printf(TEXT("Stale WorldEpoch: Expected %d, Got %d"), ExpectedWorldEpoch, Proposal.WorldEpoch);
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EvolutionValidator: %s"), *Result.RejectReason);
		return Result;
	}

	if (Proposal.ContextRevision != ExpectedContextRevision)
	{
		Result.RejectReason = FString::Printf(TEXT("Stale ContextRevision: Expected %d, Got %d"), ExpectedContextRevision, Proposal.ContextRevision);
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EvolutionValidator: %s"), *Result.RejectReason);
		return Result;
	}

	// 2. Check Finite Values
	const float Deltas[] = {
		Proposal.BodyScaleDelta, Proposal.LegScaleDelta, Proposal.BodyBoneScaleDelta,
		Proposal.ColorBrightnessDelta, Proposal.ColorTintStrengthDelta, Proposal.MorphWeightDelta,
		Proposal.MoveSpeedDelta, Proposal.HealthDelta, Proposal.AttackDelta,
		Proposal.FearDelta, Proposal.AggressionDelta, Proposal.GroupAffinityDelta, Proposal.HidePreferenceDelta,
		Proposal.MigrationDelta, Proposal.RoamRadiusDelta, Proposal.DayActivityDelta, Proposal.NightActivityDelta
	};

	for (float Delta : Deltas)
	{
		if (!IsValidFloat(Delta))
		{
			Result.RejectReason = TEXT("Non-finite delta detected in evolution proposal.");
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EvolutionValidator: %s"), *Result.RejectReason);
			return Result;
		}
	}

	// 3. Clamp Individual Deltas to MaxDeltaPerGen
	float BodyScaleDelta = FMath::Clamp(Proposal.BodyScaleDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float LegScaleDelta = FMath::Clamp(Proposal.LegScaleDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float BodyBoneScaleDelta = FMath::Clamp(Proposal.BodyBoneScaleDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float ColorBrightnessDelta = FMath::Clamp(Proposal.ColorBrightnessDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float ColorTintStrengthDelta = FMath::Clamp(Proposal.ColorTintStrengthDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float MorphWeightDelta = FMath::Clamp(Proposal.MorphWeightDelta, -MaxDeltaPerGen, MaxDeltaPerGen);

	float MoveSpeedDelta = FMath::Clamp(Proposal.MoveSpeedDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float HealthDelta = FMath::Clamp(Proposal.HealthDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float AttackDelta = FMath::Clamp(Proposal.AttackDelta, -MaxDeltaPerGen, MaxDeltaPerGen);

	float FearDelta = FMath::Clamp(Proposal.FearDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float AggressionDelta = FMath::Clamp(Proposal.AggressionDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float GroupAffinityDelta = FMath::Clamp(Proposal.GroupAffinityDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float HidePreferenceDelta = FMath::Clamp(Proposal.HidePreferenceDelta, -MaxDeltaPerGen, MaxDeltaPerGen);

	float MigrationDelta = FMath::Clamp(Proposal.MigrationDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float RoamRadiusDelta = FMath::Clamp(Proposal.RoamRadiusDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float DayActivityDelta = FMath::Clamp(Proposal.DayActivityDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float NightActivityDelta = FMath::Clamp(Proposal.NightActivityDelta, -MaxDeltaPerGen, MaxDeltaPerGen);

	// 4. Calculate Total Delta and Enforce Mutation Budget
	float TotalDelta = FMath::Abs(BodyScaleDelta) + FMath::Abs(LegScaleDelta) + FMath::Abs(BodyBoneScaleDelta)
		+ FMath::Abs(ColorBrightnessDelta) + FMath::Abs(ColorTintStrengthDelta) + FMath::Abs(MorphWeightDelta)
		+ FMath::Abs(MoveSpeedDelta) + FMath::Abs(HealthDelta) + FMath::Abs(AttackDelta)
		+ FMath::Abs(FearDelta) + FMath::Abs(AggressionDelta) + FMath::Abs(GroupAffinityDelta) + FMath::Abs(HidePreferenceDelta)
		+ FMath::Abs(MigrationDelta) + FMath::Abs(RoamRadiusDelta) + FMath::Abs(DayActivityDelta) + FMath::Abs(NightActivityDelta);

	Result.TotalDeltaSum = TotalDelta;

	if (TotalDelta > MutationBudget && TotalDelta > KINDA_SMALL_NUMBER)
	{
		const float BudgetScale = MutationBudget / TotalDelta;
		BodyScaleDelta *= BudgetScale;
		LegScaleDelta *= BudgetScale;
		BodyBoneScaleDelta *= BudgetScale;
		ColorBrightnessDelta *= BudgetScale;
		ColorTintStrengthDelta *= BudgetScale;
		MorphWeightDelta *= BudgetScale;
		MoveSpeedDelta *= BudgetScale;
		HealthDelta *= BudgetScale;
		AttackDelta *= BudgetScale;
		FearDelta *= BudgetScale;
		AggressionDelta *= BudgetScale;
		GroupAffinityDelta *= BudgetScale;
		HidePreferenceDelta *= BudgetScale;
		MigrationDelta *= BudgetScale;
		RoamRadiusDelta *= BudgetScale;
		DayActivityDelta *= BudgetScale;
		NightActivityDelta *= BudgetScale;

		Result.TotalDeltaSum = MutationBudget;
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EvolutionValidator: Proposal scaled down by factor %.3f to meet Mutation Budget %.2f"),
			BudgetScale, MutationBudget);
	}

	// 5. Apply Clamped Deltas and Enforce Trait Hard Limits
	FSpeciesEvolutionProfile NewProfile = CurrentProfile;

	// Phenotype
	NewProfile.Phenotype.BodyScale = FMath::Clamp(CurrentProfile.Phenotype.BodyScale + BodyScaleDelta,
		EcoTraitLimits::BodyScaleMin, EcoTraitLimits::BodyScaleMax);
	NewProfile.Phenotype.LegScale = FMath::Clamp(CurrentProfile.Phenotype.LegScale + LegScaleDelta,
		EcoTraitLimits::LegScaleMin, EcoTraitLimits::LegScaleMax);
	NewProfile.Phenotype.BodyBoneScale = FMath::Clamp(CurrentProfile.Phenotype.BodyBoneScale + BodyBoneScaleDelta,
		EcoTraitLimits::BodyBoneScaleMin, EcoTraitLimits::BodyBoneScaleMax);
	NewProfile.Phenotype.ColorBrightness = FMath::Clamp(CurrentProfile.Phenotype.ColorBrightness + ColorBrightnessDelta,
		EcoTraitLimits::ColorBrightnessMin, EcoTraitLimits::ColorBrightnessMax);
	NewProfile.Phenotype.ColorTintStrength = FMath::Clamp(CurrentProfile.Phenotype.ColorTintStrength + ColorTintStrengthDelta,
		EcoTraitLimits::ColorTintStrengthMin, EcoTraitLimits::ColorTintStrengthMax);
	NewProfile.Phenotype.MorphWeight = FMath::Clamp(CurrentProfile.Phenotype.MorphWeight + MorphWeightDelta,
		EcoTraitLimits::MorphWeightMin, EcoTraitLimits::MorphWeightMax);

	// Gameplay
	NewProfile.Gameplay.MoveSpeedMultiplier = FMath::Clamp(CurrentProfile.Gameplay.MoveSpeedMultiplier + MoveSpeedDelta,
		EcoTraitLimits::MoveSpeedMultiplierMin, EcoTraitLimits::MoveSpeedMultiplierMax);
	NewProfile.Gameplay.HealthMultiplier = FMath::Clamp(CurrentProfile.Gameplay.HealthMultiplier + HealthDelta,
		EcoTraitLimits::HealthMultiplierMin, EcoTraitLimits::HealthMultiplierMax);
	NewProfile.Gameplay.AttackMultiplier = FMath::Clamp(CurrentProfile.Gameplay.AttackMultiplier + AttackDelta,
		EcoTraitLimits::AttackMultiplierMin, EcoTraitLimits::AttackMultiplierMax);

	// Behavior
	NewProfile.Behavior.Fear = FMath::Clamp(CurrentProfile.Behavior.Fear + FearDelta,
		EcoTraitLimits::FearMin, EcoTraitLimits::FearMax);
	NewProfile.Behavior.Aggression = FMath::Clamp(CurrentProfile.Behavior.Aggression + AggressionDelta,
		EcoTraitLimits::AggressionMin, EcoTraitLimits::AggressionMax);
	NewProfile.Behavior.GroupAffinity = FMath::Clamp(CurrentProfile.Behavior.GroupAffinity + GroupAffinityDelta,
		EcoTraitLimits::GroupAffinityMin, EcoTraitLimits::GroupAffinityMax);
	NewProfile.Behavior.HidePreference = FMath::Clamp(CurrentProfile.Behavior.HidePreference + HidePreferenceDelta,
		EcoTraitLimits::HidePreferenceMin, EcoTraitLimits::HidePreferenceMax);

	// Ecology
	NewProfile.Ecology.MigrationTendency = FMath::Clamp(CurrentProfile.Ecology.MigrationTendency + MigrationDelta,
		EcoTraitLimits::MigrationTendencyMin, EcoTraitLimits::MigrationTendencyMax);
	NewProfile.Ecology.RoamRadiusMultiplier = FMath::Clamp(CurrentProfile.Ecology.RoamRadiusMultiplier + RoamRadiusDelta,
		EcoTraitLimits::RoamRadiusMultiplierMin, EcoTraitLimits::RoamRadiusMultiplierMax);
	NewProfile.Ecology.DayActivityPreference = FMath::Clamp(CurrentProfile.Ecology.DayActivityPreference + DayActivityDelta,
		EcoTraitLimits::DayActivityPreferenceMin, EcoTraitLimits::DayActivityPreferenceMax);
	NewProfile.Ecology.NightActivityPreference = FMath::Clamp(CurrentProfile.Ecology.NightActivityPreference + NightActivityDelta,
		EcoTraitLimits::NightActivityPreferenceMin, EcoTraitLimits::NightActivityPreferenceMax);

	// 6. Increment Generation & Profile Revision
	NewProfile.Generation = CurrentProfile.Generation + 1;
	NewProfile.ProfileRevision = CurrentProfile.ProfileRevision + 1;

	Result.bAccepted = true;
	Result.CommittedProfile = NewProfile;

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EvolutionValidator: Successfully validated proposal for [%s x %s] -> New Gen: %d, Rev: %lld"),
		*NewProfile.RegionId.ToString(), *NewProfile.SpeciesId.ToString(), NewProfile.Generation, NewProfile.ProfileRevision);

	return Result;
}

FVegetationValidationResult UEvolutionValidator::ValidateAndApplyVegetationProposal(
	const FVegetationEvolutionProfile& CurrentProfile,
	const FVegetationEvolutionProposal& Proposal,
	int32 ExpectedWorldEpoch,
	int32 ExpectedContextRevision,
	float MutationBudget,
	float MaxDeltaPerGen)
{
	FVegetationValidationResult Result;
	Result.bAccepted = false;
	Result.CommittedProfile = CurrentProfile;

	// 1. Check Staleness
	if (Proposal.WorldEpoch != ExpectedWorldEpoch)
	{
		Result.RejectReason = FString::Printf(TEXT("Stale WorldEpoch: Expected %d, Got %d"), ExpectedWorldEpoch, Proposal.WorldEpoch);
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EvolutionValidator (Vegetation): %s"), *Result.RejectReason);
		return Result;
	}

	if (Proposal.ContextRevision != ExpectedContextRevision)
	{
		Result.RejectReason = FString::Printf(TEXT("Stale ContextRevision: Expected %d, Got %d"), ExpectedContextRevision, Proposal.ContextRevision);
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EvolutionValidator (Vegetation): %s"), *Result.RejectReason);
		return Result;
	}

	// 2. Check Finite Values
	const float Deltas[] = {
		Proposal.GrowthRateDelta,
		Proposal.RegenerationRateDelta,
		Proposal.GrazingResistanceDelta
	};

	for (float Delta : Deltas)
	{
		if (!IsValidFloat(Delta))
		{
			Result.RejectReason = TEXT("Non-finite delta detected in vegetation evolution proposal.");
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EvolutionValidator (Vegetation): %s"), *Result.RejectReason);
			return Result;
		}
	}

	// 3. Clamp Individual Deltas to MaxDeltaPerGen
	float GrowthRateDelta = FMath::Clamp(Proposal.GrowthRateDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float RegenerationRateDelta = FMath::Clamp(Proposal.RegenerationRateDelta, -MaxDeltaPerGen, MaxDeltaPerGen);
	float GrazingResistanceDelta = FMath::Clamp(Proposal.GrazingResistanceDelta, -MaxDeltaPerGen, MaxDeltaPerGen);

	// 4. Calculate Total Delta and Enforce Mutation Budget
	float TotalDelta = FMath::Abs(GrowthRateDelta) + FMath::Abs(RegenerationRateDelta) + FMath::Abs(GrazingResistanceDelta);
	Result.TotalDeltaSum = TotalDelta;

	if (TotalDelta > MutationBudget && TotalDelta > KINDA_SMALL_NUMBER)
	{
		const float BudgetScale = MutationBudget / TotalDelta;
		GrowthRateDelta *= BudgetScale;
		RegenerationRateDelta *= BudgetScale;
		GrazingResistanceDelta *= BudgetScale;

		Result.TotalDeltaSum = MutationBudget;
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EvolutionValidator (Vegetation): Proposal scaled down by factor %.3f to meet Mutation Budget %.2f"),
			BudgetScale, MutationBudget);
	}

	// 5. Apply Clamped Deltas and Enforce Trait Hard Limits
	FVegetationEvolutionProfile NewProfile = CurrentProfile;

	NewProfile.Traits.GrowthRate = FMath::Clamp(
		CurrentProfile.Traits.GrowthRate + GrowthRateDelta,
		EcoVegetationTraitLimits::GrowthRateMin,
		EcoVegetationTraitLimits::GrowthRateMax);

	NewProfile.Traits.RegenerationRate = FMath::Clamp(
		CurrentProfile.Traits.RegenerationRate + RegenerationRateDelta,
		EcoVegetationTraitLimits::RegenerationRateMin,
		EcoVegetationTraitLimits::RegenerationRateMax);

	NewProfile.Traits.GrazingResistance = FMath::Clamp(
		CurrentProfile.Traits.GrazingResistance + GrazingResistanceDelta,
		EcoVegetationTraitLimits::GrazingResistanceMin,
		EcoVegetationTraitLimits::GrazingResistanceMax);

	// 6. Increment Generation & Profile Revision
	NewProfile.Generation = CurrentProfile.Generation + 1;
	NewProfile.ProfileRevision = CurrentProfile.ProfileRevision + 1;

	Result.bAccepted = true;
	Result.CommittedProfile = NewProfile;

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EvolutionValidator (Vegetation): Successfully validated proposal for [%s x %s] -> New Gen: %d, Rev: %lld (Growth: %.2f, Regen: %.2f, Resist: %.2f)"),
		*NewProfile.RegionId.ToString(), *NewProfile.VegetationSpeciesId.ToString(),
		NewProfile.Generation, NewProfile.ProfileRevision,
		NewProfile.Traits.GrowthRate, NewProfile.Traits.RegenerationRate, NewProfile.Traits.GrazingResistance);

	return Result;
}
