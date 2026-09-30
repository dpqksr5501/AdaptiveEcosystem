#pragma once

#include "CoreMinimal.h"
#include "EcoSocialMovementTypes.generated.h"

/** Social-owned suggestion, consumed by the single movement writer. No velocity or path. */
UENUM()
enum class EEcoSocialMovementMode : uint8
{
	None,
	ShelterTravel,
	ShelterHold
};

/** Movement-owned feedback. The reservation ID and sequence must match the current request. */
UENUM()
enum class EEcoShelterMovementStatus : uint8
{
	None,
	Moving,
	Arrived,
	Failed,
	Yielded
};

USTRUCT()
struct FEcoShelterLifecycleSettings
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, Category = "Shelter", meta = (ClampMin = "0.1"))
	double LeaseDuration = 12.0;
	UPROPERTY(EditAnywhere, Category = "Shelter", meta = (ClampMin = "0.1"))
	double FeedbackTimeout = 2.0;
	UPROPERTY(EditAnywhere, Category = "Shelter", meta = (ClampMin = "0.1"))
	double ProgressTimeout = 8.0;
	UPROPERTY(EditAnywhere, Category = "Shelter", meta = (ClampMin = "1", Units = "cm"))
	float ArrivalRadius = 60.0f;
	UPROPERTY(EditAnywhere, Category = "Shelter", meta = (ClampMin = "1", Units = "cm"))
	float ExitRadius = 120.0f;
	UPROPERTY(EditAnywhere, Category = "Shelter", meta = (ClampMin = "1", Units = "cm"))
	float ProgressDistance = 10.0f;
	UPROPERTY(EditAnywhere, Category = "Shelter", meta = (ClampMin = "0.1"))
	double RetryCooldown = 1.0;

	bool IsValid() const
	{
		return FMath::IsFinite(LeaseDuration) && LeaseDuration >= 0.1
			&& FMath::IsFinite(FeedbackTimeout) && FeedbackTimeout >= 0.1 && FeedbackTimeout <= LeaseDuration
			&& FMath::IsFinite(ProgressTimeout) && ProgressTimeout >= 0.1
			&& FMath::IsFinite(ArrivalRadius) && ArrivalRadius >= 1.0f
			&& FMath::IsFinite(ExitRadius) && ExitRadius >= ArrivalRadius
			&& FMath::IsFinite(ProgressDistance) && ProgressDistance >= 1.0f
			&& FMath::IsFinite(RetryCooldown) && RetryCooldown >= 0.1;
	}
};
