#pragma once

#include "CoreMinimal.h"

class AActor;

/** One result per herd from a complete detection pass. Persistent ID prevents slot reuse bugs. */
struct FEcoObservedHerdThreat
{
	int32 HerdRuntimeIndex = INDEX_NONE;
	int64 PersistentHerdId = 0;
	FVector Position = FVector::ZeroVector;
	float Strength = 0.0f;
	float Priority = 0.0f;
	uint64 SourceKey = MAX_uint64;
};

struct FEcoActorThreatSnapshot
{
	TWeakObjectPtr<AActor> Actor;
	FVector Position = FVector::ZeroVector;
	float Strength = 1.0f;
	uint64 SourceKey = 0;
};

struct FEcoHerdAlarmInput
{
	FVector Position = FVector::ZeroVector;
	float Strength = 0.0f;
};
