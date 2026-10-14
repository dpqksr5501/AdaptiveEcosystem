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
	double ServerToClientTimeOffset = 0.0;
	uint64 MovementUpdates = 0;
	uint64 PresentationUpdates = 0;
	uint64 RejectedUpdates = 0;
	uint64 ResetUpdates = 0;

	FVector GetRenderPosition(double ClientTime, double MinimumDelay) const
	{
		if (!bHasSample || bResetInterpolation) return Current.Location;
		const double Span = Current.ServerSampleRealTimeSeconds - Previous.ServerSampleRealTimeSeconds;
		if (Span <= 0.0) return Current.Location;
		const double Delay = FMath::Max(MinimumDelay, FMath::Min(Span, 1.0));
		const double RenderTime = ClientTime - ServerToClientTimeOffset - Delay;
		const double Alpha = FMath::Clamp((RenderTime - Previous.ServerSampleRealTimeSeconds) / Span, 0.0, 1.0);
		return FMath::Lerp(FVector(Previous.Location), FVector(Current.Location), Alpha);
	}

	bool Receive(const FEcoRepresentationSnapshot& Sample, double ReceiveTime)
	{
		const bool bSameIdentity = bHasSample && Sample.StableAgentId == Current.StableAgentId;
		const int32 MovementDelta = static_cast<int32>(Sample.SampleSequence - Current.SampleSequence);
		const int32 VisualDelta = static_cast<int32>(Sample.VisualRevision - Current.VisualRevision);
		if (bSameIdentity && (MovementDelta < 0 || (MovementDelta == 0 && VisualDelta <= 0)))
		{
			++RejectedUpdates;
			return false;
		}
		bResetInterpolation = !bHasSample || Sample.StableAgentId != Current.StableAgentId
			|| Sample.MovementDiscontinuityRevision != Current.MovementDiscontinuityRevision;
		// A presentation-only update must not replace the two movement samples or their timeline.
		if (bResetInterpolation) ++ResetUpdates;
		else if (MovementDelta > 0) ++MovementUpdates;
		else ++PresentationUpdates;
		if (bResetInterpolation) Previous = Sample;
		else if (MovementDelta > 0) Previous = Current;
		Current = Sample;
		if (!bSameIdentity || MovementDelta > 0)
			ServerToClientTimeOffset = ReceiveTime - Sample.ServerSampleRealTimeSeconds;
		ReceivedRealTimeSeconds = ReceiveTime;
		bHasSample = true;
		return true;
	}
};
