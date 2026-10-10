#pragma once

#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"

namespace EcoShelter
{
	inline void AddEligibilityRequirements(FMassEntityQuery& Query)
	{
		Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
		Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	}

	inline const TCHAR* IneligibilityReason(FMassExecutionContext& Chunk, int32 Index)
	{
		if (!Chunk.DoesArchetypeHaveTag<FEcoAliveTag>()) { return TEXT("NotAlive"); }
		if (Chunk.DoesArchetypeHaveTag<FEcoClientProxyTag>()) { return TEXT("ClientProxy"); }
		if (Chunk.DoesArchetypeHaveTag<FEcoPendingDeathTag>()) { return TEXT("PendingDeath"); }
		const auto Vitals = Chunk.GetFragmentView<FEcoVitalsFragment>();
		const auto Travel = Chunk.GetFragmentView<FEcoTravelFragment>();
		if (!Vitals.IsEmpty() && (!FMath::IsFinite(Vitals[Index].HP) || Vitals[Index].HP <= 0.0f)) { return TEXT("DeadOrInvalidHP"); }
		if (!Travel.IsEmpty() && Travel[Index].State == EEcoResidenceState::Traveling) { return TEXT("Migrating"); }
		return nullptr;
	}

	inline bool IsEligible(FMassExecutionContext& Chunk, int32 Index)
	{
		return IneligibilityReason(Chunk, Index) == nullptr;
	}
}
