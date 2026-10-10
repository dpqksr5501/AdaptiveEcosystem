#pragma once

#include "AI/Policy/EcoPolicyContracts.h"
#include "AI/Social/EcoSocialTypes.h"

/** Diagnostic snapshot only. Does not choose an action or authorize movement. */
struct FEcoSocialActionAudit
{
	bool bValid = false;
	double WorldTime = 0.0;
	EEcoSocialState AppliedState = EEcoSocialState::Calm;
	FEcoPolicyActionV1 RawAction;
	float MaxAbsoluteDelta = 0.0f;

	void Record(const FEcoPolicyActionV1& Raw, const FEcoPolicyActionV1& Effective,
		EEcoSocialState State, double Now);
};
