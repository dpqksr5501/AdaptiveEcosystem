#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"
#include "Core/EcoRepresentationTypes.h"
#include "EcoMassPresentationFragments.generated.h"

/** Authority-only signal. Increment after a teleport/reset, even if position is unchanged. */
USTRUCT()
struct FEcoMovementDiscontinuityFragment : public FMassFragment
{
	GENERATED_BODY()
	uint32 Revision = 0;
};

/** Client-only receive buffer. Does not write transforms or authoritative vitals. */
USTRUCT()
struct FEcoClientPresentationFragment : public FMassFragment
{
	GENERATED_BODY()
	FEcoRepresentationSnapshot Previous;
	FEcoRepresentationSnapshot Current;
	double ReceivedRealTimeSeconds = 0.0;
	bool bHasSample = false;
	bool bResetInterpolation = true;

	bool Receive(const FEcoRepresentationSnapshot& Sample, double ReceiveTime)
	{
		if (bHasSample && Sample.StableAgentId == Current.StableAgentId
			&& static_cast<int32>(Sample.SampleSequence - Current.SampleSequence) <= 0)
		{
			return false;
		}
		bResetInterpolation = !bHasSample || Sample.StableAgentId != Current.StableAgentId
			|| Sample.MovementDiscontinuityRevision != Current.MovementDiscontinuityRevision;
		Previous = bResetInterpolation ? Sample : Current;
		Current = Sample;
		ReceivedRealTimeSeconds = ReceiveTime;
		bHasSample = true;
		return true;
	}
};
