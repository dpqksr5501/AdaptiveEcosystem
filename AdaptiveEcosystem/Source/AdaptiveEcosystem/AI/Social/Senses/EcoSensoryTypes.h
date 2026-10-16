#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"
#include "EcoSensoryTypes.generated.h"

UENUM(BlueprintType)
enum class EEcoSenseSource : uint8
{
	None, Sight, Hearing, Memory
};

/** Species defaults. Environmental modifiers are neutral until the team tunes them. */
USTRUCT(BlueprintType)
struct FEcoSensorySettings
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0", ClampMax="10000", Units="cm"))
	float HearingRange = 2000.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0", ClampMax="1"))
	float HearingConfidence = 0.65f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0", ClampMax="1"))
	float OccludedHearingMultiplier = 0.35f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0.001", ClampMax="1"))
	float MinimumConfidence = 0.05f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0.1", ClampMax="60", Units="s"))
	float MemorySeconds = 6.0f;
	/** Maximum age of the original selected herd input, not of its repeated reception. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0.1", ClampMax="60", Units="s"))
	float SharedInformationMaxAge = 6.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0", ClampMax="10000", Units="cm"))
	float HearingUncertainty = 200.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0", ClampMax="1000"))
	float UncertaintyGrowthPerSecond = 150.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0", ClampMax="2"))
	float NightVisionMultiplier = 1.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0", ClampMax="2"))
	float RainVisionMultiplier = 1.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Senses", meta=(ClampMin="0", ClampMax="2"))
	float RainHearingMultiplier = 1.0f;

	bool IsValid() const;
};

/** Per-agent sensory ability, not a policy action or a birth-profile owner. */
USTRUCT()
struct FEcoSensoryProfileFragment : public FMassFragment
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, Category="Senses", meta=(ClampMin="0", ClampMax="4"))
	float VisionMultiplier = 1.0f;
	UPROPERTY(EditAnywhere, Category="Senses", meta=(ClampMin="0", ClampMax="4"))
	float HearingMultiplier = 1.0f;
	UPROPERTY(EditAnywhere, Category="Senses", meta=(ClampMin="0.1", ClampMax="4"))
	float MemoryMultiplier = 1.0f;
	bool IsValid() const;
};

/** Social-owned read contract. Physical units; not a normalized PPO observation or a movement command. */
struct FEcoSensoryReadSnapshot
{
	static constexpr int32 SchemaVersion = 1;
	bool bValid = false;
	double WorldTime = 0.0;
	bool bHasPersonalThreat = false;
	EEcoSenseSource PersonalSource = EEcoSenseSource::None;
	EEcoSenseSource LastDirectSense = EEcoSenseSource::None;
	FVector LastKnownPosition = FVector::ZeroVector;
	float Confidence = 0.0f;
	float UncertaintyRadiusCm = 0.0f;
	float ThreatStrength = 0.0f;
	double PersonalAgeSeconds = 0.0;
	bool bFreshDirectEvidence = false;
	bool bHasSharedThreat = false;
	FVector SharedReportedPosition = FVector::ZeroVector;
	float SharedAlarmStrength = 0.0f; // Alarm intensity, not a calibrated confidence.
	int64 SourcePersistentHerdId = 0;
	double SharedEvidenceAgeSeconds = 0.0;
	double SharedReceptionAgeSeconds = 0.0;
};

/** Personal knowledge. Position is the last observation, never a hidden actor's live transform. */
USTRUCT()
struct FEcoSensoryStateFragment : public FMassFragment
{
	GENERATED_BODY()
	UPROPERTY(VisibleAnywhere, Category="Senses")
	EEcoSenseSource Source = EEcoSenseSource::None;
	UPROPERTY(VisibleAnywhere, Category="Senses")
	EEcoSenseSource LastDirectSense = EEcoSenseSource::None;
	UPROPERTY(VisibleAnywhere, Category="Senses")
	FVector LastKnownPosition = FVector::ZeroVector;
	UPROPERTY(VisibleAnywhere, Category="Senses")
	float Confidence = 0.0f;
	UPROPERTY(VisibleAnywhere, Category="Senses")
	float UncertaintyRadius = 0.0f;
	UPROPERTY(VisibleAnywhere, Category="Senses")
	float ThreatStrength = 0.0f;
	UPROPERTY(VisibleAnywhere, Category="Senses")
	double LastObservedTime = 0.0;
	UPROPERTY(VisibleAnywhere, Category="Senses")
	bool bSensedThisScan = false;
	// Social information remains separate and cannot refresh/rebroadcast personal memory.
	UPROPERTY(VisibleAnywhere, Category="Senses")
	FVector SharedThreatPosition = FVector::ZeroVector;
	UPROPERTY(VisibleAnywhere, Category="Senses")
	float SharedAlarmStrength = 0.0f;
	int64 SharedPersistentHerdId = 0;
	double SharedEvidenceWorldTime = -1.0;
	double SharedReceivedWorldTime = -1.0;
	uint64 SourceKey = 0;
	int64 LastProcessedNoiseId = 0;
	float InitialConfidence = 0.0f;
	float InitialUncertainty = 0.0f;
	void Forget();
	void Age(double Now, const FEcoSensorySettings& Settings, float MemoryMultiplier);
	void Observe(EEcoSenseSource Sense, const FVector& Position, float Certainty, float Uncertainty,
		float Strength, uint64 Key, double Now);
	void ClearSharedInformation();
	void ReceiveSharedInformation(const FVector& Position, float Strength, int64 PersistentHerdId,
		double EvidenceTime, double ReceivedTime);
	/** Const copy aged at read time. Caller supplies current membership ID (0 when unassigned).
	 * Caller must separately check authority/alive state. Does not query an actor, grid, or policy. */
	FEcoSensoryReadSnapshot MakeReadSnapshot(double Now, const FEcoSensorySettings& Settings,
		const FEcoSensoryProfileFragment& Profile, int64 CurrentPersistentHerdId) const;
};
