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
	FEcoRepresentationSnapshot Current;
	double ReceivedRealTimeSeconds = 0.0;
	bool bHasSample = false;
	uint64 MovementUpdates = 0;
	uint64 PresentationUpdates = 0;
	uint64 RejectedUpdates = 0;
	uint64 ResetUpdates = 0;

	FVector GetRenderPosition(double ClientTime, double MinimumDelay) const
	{
		if (MovementCount < 2) return Current.Location;
		const double Delay = FMath::Max(MinimumDelay, FMath::Min(SampleInterval, 1.0));
		const double RenderTime = ClientTime - ServerToClientTimeOffset - Delay;
		for (int32 I = 1; I < MovementCount; ++I)
		{
			const auto& Before = Movement[I - 1];
			const auto& After = Movement[I];
			if (RenderTime > After.Time) continue;
			const double Alpha = FMath::Clamp((RenderTime - Before.Time) / (After.Time - Before.Time), 0.0, 1.0);
			return FMath::Lerp(Before.Position, After.Position, Alpha);
		}
		return Movement[MovementCount - 1].Position;
	}

	bool Receive(const FEcoRepresentationSnapshot& Sample, double ReceiveTime)
	{
		if (!FMath::IsFinite(ReceiveTime) || !FMath::IsFinite(Sample.ServerSampleRealTimeSeconds) || Sample.Location.ContainsNaN())
		{
			++RejectedUpdates;
			return false;
		}
		const bool bSameIdentity = bHasSample && Sample.StableAgentId == Current.StableAgentId;
		const int32 MovementDelta = static_cast<int32>(Sample.SampleSequence - Current.SampleSequence);
		const int32 VisualDelta = static_cast<int32>(Sample.VisualRevision - Current.VisualRevision);
		if (bSameIdentity && (MovementDelta < 0 || (MovementDelta == 0 && VisualDelta <= 0)))
		{
			++RejectedUpdates;
			return false;
		}
		const bool bResetInterpolation = !bSameIdentity
			|| Sample.MovementDiscontinuityRevision != Current.MovementDiscontinuityRevision;
		if (bResetInterpolation)
		{
			++ResetUpdates;
			MovementCount = 1;
			Movement[0] = {Sample.Location, Sample.ServerSampleRealTimeSeconds};
			SampleInterval = 0.0;
			ServerToClientTimeOffset = ReceiveTime - Sample.ServerSampleRealTimeSeconds;
			LastMovementReceiveTime = ReceiveTime;
		}
		else if (MovementDelta > 0)
		{
			const double Span = Sample.ServerSampleRealTimeSeconds - Movement[MovementCount - 1].Time;
			if (Span < 0.0) { ++RejectedUpdates; return false; }
			if (Span > 0.0)
			{
				// Retain samples behind the render cursor, and adjust the clock gradually under packet jitter.
				const double MaxAdjustment = FMath::Max(0.0, ReceiveTime - LastMovementReceiveTime) * .05;
				const double ObservedOffset = ReceiveTime - Sample.ServerSampleRealTimeSeconds;
				ServerToClientTimeOffset += FMath::Clamp(ObservedOffset - ServerToClientTimeOffset, -MaxAdjustment, MaxAdjustment);
				SampleInterval = SampleInterval > 0.0
					? SampleInterval + FMath::Clamp(Span - SampleInterval, -MaxAdjustment, MaxAdjustment) : Span;
				if (MovementCount >= UE_ARRAY_COUNT(Movement))
				{
					for (int32 I = 1; I < MovementCount; ++I) Movement[I - 1] = Movement[I];
					--MovementCount;
				}
				Movement[MovementCount++] = {Sample.Location, Sample.ServerSampleRealTimeSeconds};
				LastMovementReceiveTime = ReceiveTime;
			}
			else Movement[MovementCount - 1].Position = Sample.Location;
			++MovementUpdates;
		}
		// Presentation-only updates leave both the render clock and the movement history alone.
		else ++PresentationUpdates;
		Current = Sample;
		ReceivedRealTimeSeconds = ReceiveTime;
		bHasSample = true;
		return true;
	}

private:
	struct FMovementSample
	{
		FVector Position = FVector::ZeroVector;
		double Time = 0.0;
	};
	FMovementSample Movement[4];
	int32 MovementCount = 0;
	double ServerToClientTimeOffset = 0.0;
	double LastMovementReceiveTime = 0.0;
	double SampleInterval = 0.0;
};
