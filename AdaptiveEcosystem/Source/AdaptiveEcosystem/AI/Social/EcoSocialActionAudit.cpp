#include "AI/Social/EcoSocialActionAudit.h"

void FEcoSocialActionAudit::Record(const FEcoPolicyActionV1& Raw, const FEcoPolicyActionV1& Effective,
	EEcoSocialState State, double Now)
{
	*this = {};
	if (!FMath::IsFinite(Now) || Now < 0.0) { return; }
	const float Before[] = {Raw.Forage, Raw.Cohesion, Raw.FleeDist, Raw.Cover};
	const float After[] = {Effective.Forage, Effective.Cohesion, Effective.FleeDist, Effective.Cover};
	for (int32 I = 0; I < 4; ++I)
	{
		if (!FMath::IsFinite(Before[I]) || !FMath::IsFinite(After[I])) { *this = {}; return; }
		MaxAbsoluteDelta = FMath::Max(MaxAbsoluteDelta, FMath::Abs(After[I] - Before[I]));
	}
	bValid = true;
	WorldTime = Now;
	AppliedState = State;
	RawAction = Raw;
}
