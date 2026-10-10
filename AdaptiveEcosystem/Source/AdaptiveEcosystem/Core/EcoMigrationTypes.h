#pragma once

#include "CoreMinimal.h"
#include "EcoMigrationTypes.generated.h"

UENUM()
enum class EEcoResidenceState : uint8
{
	Resident,
	Traveling,
	WaitingForFood
};

USTRUCT(BlueprintType)
struct FEcoMigrationSettings
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, Category="Migration")
	bool bEnabled = true;
	UPROPERTY(EditAnywhere, Category="Migration", meta=(ClampMin="0.25"))
	double DecisionIntervalSeconds = 1.0;
	UPROPERTY(EditAnywhere, Category="Migration", meta=(ClampMin="1.0", Units="cm/s"))
	float Speed = 400.0f;
	UPROPERTY(EditAnywhere, Category="Migration", meta=(ClampMin="1.0", Units="cm"))
	float ArrivalRadius = 30.0f;
	UPROPERTY(EditAnywhere, Category="Migration", meta=(ClampMin="0.0", Units="cm"))
	float ArrivalSpread = 300.0f;
	UPROPERTY(EditAnywhere, Category="Migration", meta=(ClampMin="0.0"))
	float FoodEpsilon = 0.0001f;
	UPROPERTY(EditAnywhere, Category="Migration")
	bool bPrintTransitions = true;
	bool IsValid() const
	{
		return FMath::IsFinite(DecisionIntervalSeconds) && DecisionIntervalSeconds >= 0.25
			&& FMath::IsFinite(Speed) && Speed >= 1.0f
			&& FMath::IsFinite(ArrivalRadius) && ArrivalRadius >= 1.0f
			&& FMath::IsFinite(ArrivalSpread) && ArrivalSpread >= 0.0f
			&& FMath::IsFinite(FoodEpsilon) && FoodEpsilon >= 0.0f;
	}
};

UENUM(BlueprintType)
enum class EEcoMigrationReason : uint8 { None, FoodDepletion, Overcrowding, FoodShortage, ReturnHome };

/** One successful cross-region commit. No Actor/EntityHandle crosses the ecology boundary. */
struct FEcoMigrationOutcome
{
	int32 WorldEpoch = 0;
	int64 StepId = 0;
	int64 StableAgentId = 0;
	FName OriginRegionId;
	FName DestinationRegionId;
	EEcoMigrationReason Reason = EEcoMigrationReason::None;
	double DepartureTime = 0.0;
	double ArrivalTime = 0.0;
};

/** World-owned geometry copied at the game-thread boundary. No actor references in Mass. */
struct FEcoRegionSpatialSnapshot
{
	FName RegionId;
	FTransform BoundsTransform;
	FVector BoundsExtent = FVector::ZeroVector;
	FVector ArrivalPosition = FVector::ZeroVector;
	TArray<int32> AdjacentIndices;
	bool Contains(const FVector& Position) const
	{
		const FVector Local = BoundsTransform.InverseTransformPosition(Position);
		return !Local.ContainsNaN() && FMath::Abs(Local.X) <= BoundsExtent.X
			&& FMath::Abs(Local.Y) <= BoundsExtent.Y && FMath::Abs(Local.Z) <= BoundsExtent.Z;
	}
};
