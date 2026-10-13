#include "AI/Social/Senses/EcoSensoryTypes.h"

namespace EcoSensoryValidation
{
	bool InRange(float Value, float Min, float Max) { return FMath::IsFinite(Value) && Value >= Min && Value <= Max; }
}

bool FEcoSensorySettings::IsValid() const
{
	using namespace EcoSensoryValidation;
	return InRange(HearingRange, 0, 10000) && InRange(HearingConfidence, 0, 1)
		&& InRange(OccludedHearingMultiplier, 0, 1) && InRange(MinimumConfidence, 0.001f, 1)
		&& InRange(MemorySeconds, 0.1f, 60) && InRange(SharedInformationMaxAge, 0.1f, 60)
		&& InRange(HearingUncertainty, 0, 10000)
		&& InRange(UncertaintyGrowthPerSecond, 0, 1000) && InRange(NightVisionMultiplier, 0, 2)
		&& InRange(RainVisionMultiplier, 0, 2) && InRange(RainHearingMultiplier, 0, 2);
}

bool FEcoSensoryProfileFragment::IsValid() const
{
	using namespace EcoSensoryValidation;
	return InRange(VisionMultiplier, 0, 4) && InRange(HearingMultiplier, 0, 4) && InRange(MemoryMultiplier, 0.1f, 4);
}

void FEcoSensoryStateFragment::Forget()
{
	Source = LastDirectSense = EEcoSenseSource::None;
	LastKnownPosition = FVector::ZeroVector;
	Confidence = InitialConfidence = UncertaintyRadius = InitialUncertainty = ThreatStrength = 0;
	SourceKey = 0;
	LastObservedTime = 0;
	bSensedThisScan = false;
	// Keep the noise watermark: forgetting cannot make an old sound audible again.
}

void FEcoSensoryStateFragment::Age(double Now, const FEcoSensorySettings& Settings, float MemoryMultiplier)
{
	bSensedThisScan = false;
	if (Source == EEcoSenseSource::None) { return; }
	if (!Settings.IsValid() || !FMath::IsFinite(Now) || Now < 0.0 || !FMath::IsFinite(LastObservedTime)
		|| LastObservedTime < 0.0 || !EcoSensoryValidation::InRange(InitialConfidence, 0.0f, 1.0f)
		|| !FMath::IsFinite(InitialUncertainty) || InitialUncertainty < 0.0f || !FMath::IsFinite(MemoryMultiplier)
		|| MemoryMultiplier < 0.1f || MemoryMultiplier > 4 || Now < LastObservedTime)
	{
		Forget(); return;
	}
	const double Elapsed = Now - LastObservedTime;
	const double Lifetime = Settings.MemorySeconds * MemoryMultiplier;
	Confidence = InitialConfidence * static_cast<float>(FMath::Max(0.0, 1.0 - Elapsed / Lifetime));
	if (Elapsed >= Lifetime || Confidence < Settings.MinimumConfidence) { Forget(); return; }
	Source = EEcoSenseSource::Memory;
	UncertaintyRadius = InitialUncertainty + Settings.UncertaintyGrowthPerSecond * static_cast<float>(Elapsed);
}

void FEcoSensoryStateFragment::Observe(EEcoSenseSource Sense, const FVector& Position, float Certainty,
	float Uncertainty, float Strength, uint64 Key, double Now)
{
	if ((Sense != EEcoSenseSource::Sight && Sense != EEcoSenseSource::Hearing) || Position.ContainsNaN()
		|| !FMath::IsFinite(Certainty) || !FMath::IsFinite(Uncertainty) || Uncertainty < 0
		|| !FMath::IsFinite(Strength) || !FMath::IsFinite(Now) || Now < 0 || Certainty <= 0 || Strength <= 0) { return; }
	Source = LastDirectSense = Sense;
	LastKnownPosition = Position;
	Confidence = InitialConfidence = FMath::Clamp(Certainty, 0.0f, 1.0f);
	UncertaintyRadius = InitialUncertainty = Uncertainty;
	ThreatStrength = FMath::Clamp(Strength, 0.0f, 1.0f);
	SourceKey = Key;
	LastObservedTime = Now;
	bSensedThisScan = true;
}

void FEcoSensoryStateFragment::ClearSharedInformation()
{
	SharedThreatPosition = FVector::ZeroVector;
	SharedAlarmStrength = 0.0f;
	SharedPersistentHerdId = 0;
	SharedEvidenceWorldTime = SharedReceivedWorldTime = -1.0;
}

void FEcoSensoryStateFragment::ReceiveSharedInformation(const FVector& Position, float Strength,
	int64 PersistentHerdId, double EvidenceTime, double ReceivedTime)
{
	ClearSharedInformation();
	if (Position.ContainsNaN() || !FMath::IsFinite(Strength) || Strength <= 0.0f || PersistentHerdId <= 0
		|| !FMath::IsFinite(EvidenceTime) || !FMath::IsFinite(ReceivedTime)
		|| EvidenceTime < 0.0 || ReceivedTime < EvidenceTime) { return; }
	SharedThreatPosition = Position;
	SharedAlarmStrength = FMath::Clamp(Strength, 0.0f, 1.0f);
	SharedPersistentHerdId = PersistentHerdId;
	SharedEvidenceWorldTime = EvidenceTime;
	SharedReceivedWorldTime = ReceivedTime;
}

FEcoSensoryReadSnapshot FEcoSensoryStateFragment::MakeReadSnapshot(double Now,
	const FEcoSensorySettings& Settings, const FEcoSensoryProfileFragment& Profile,
	int64 CurrentPersistentHerdId) const
{
	FEcoSensoryReadSnapshot Out;
	if (!FMath::IsFinite(Now) || Now < 0.0 || !Settings.IsValid() || !Profile.IsValid()) { return Out; }
	Out.bValid = true;
	Out.WorldTime = Now;
	// Never age the authoritative source while a downstream consumer is reading it.
	FEcoSensoryStateFragment Personal = *this;
	Personal.Age(Now, Settings, Profile.MemoryMultiplier);
	if (Personal.Source != EEcoSenseSource::None && !Personal.LastKnownPosition.ContainsNaN()
		&& FMath::IsFinite(Personal.Confidence) && Personal.Confidence > 0.0f
		&& FMath::IsFinite(Personal.ThreatStrength) && Personal.ThreatStrength > 0.0f
		&& FMath::IsFinite(Personal.UncertaintyRadius) && Personal.UncertaintyRadius >= 0.0f)
	{
		Out.bHasPersonalThreat = true;
		Out.PersonalAgeSeconds = Now - Personal.LastObservedTime;
		Out.bFreshDirectEvidence = bSensedThisScan && Out.PersonalAgeSeconds == 0.0
			&& (Source == EEcoSenseSource::Sight || Source == EEcoSenseSource::Hearing);
		Out.PersonalSource = Out.bFreshDirectEvidence ? Source : EEcoSenseSource::Memory;
		Out.LastDirectSense = Personal.LastDirectSense;
		Out.LastKnownPosition = Personal.LastKnownPosition;
		Out.Confidence = Personal.Confidence;
		Out.UncertaintyRadiusCm = Personal.UncertaintyRadius;
		Out.ThreatStrength = Personal.ThreatStrength;
	}
	// Receiving the same herd alarm again must not renew the age of its original input.
	if (CurrentPersistentHerdId > 0 && SharedPersistentHerdId == CurrentPersistentHerdId
		&& !SharedThreatPosition.ContainsNaN() && FMath::IsFinite(SharedAlarmStrength) && SharedAlarmStrength > 0.0f
		&& FMath::IsFinite(SharedEvidenceWorldTime) && FMath::IsFinite(SharedReceivedWorldTime)
		&& SharedEvidenceWorldTime >= 0.0 && SharedReceivedWorldTime >= SharedEvidenceWorldTime
		&& Now >= SharedReceivedWorldTime && Now - SharedEvidenceWorldTime < Settings.SharedInformationMaxAge)
	{
		Out.bHasSharedThreat = true;
		Out.SharedReportedPosition = SharedThreatPosition;
		Out.SharedAlarmStrength = FMath::Clamp(SharedAlarmStrength, 0.0f, 1.0f);
		Out.SourcePersistentHerdId = SharedPersistentHerdId;
		Out.SharedEvidenceAgeSeconds = Now - SharedEvidenceWorldTime;
		Out.SharedReceptionAgeSeconds = Now - SharedReceivedWorldTime;
	}
	return Out;
}
