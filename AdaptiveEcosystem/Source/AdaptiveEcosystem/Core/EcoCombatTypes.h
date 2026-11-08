#pragma once
#include "CoreMinimal.h"
#include "EcoCombatTypes.generated.h"

UENUM(BlueprintType)
enum class EEcoDamageResult : uint8 { Queued, Committed, DeathCommitted, Duplicate, InvalidTarget, InvalidAttack, Expired, AlreadyDead, QueueFull, InvalidAvatar };

USTRUCT(BlueprintType)
struct FEcoCombatDamageOutcome
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) EEcoDamageResult Result = EEcoDamageResult::InvalidTarget;
    UPROPERTY(BlueprintReadOnly) int32 WorldEpoch = 0;
    UPROPERTY(BlueprintReadOnly) int64 AttackExecutionId = 0;
    UPROPERTY(BlueprintReadOnly) int32 StepId = INDEX_NONE;
    UPROPERTY(BlueprintReadOnly) int64 TargetStableAgentId = 0;
    UPROPERTY(BlueprintReadOnly) float AppliedDamage = 0;
    UPROPERTY(BlueprintReadOnly) float RemainingHP = 0;
    UPROPERTY(BlueprintReadOnly) float QueueSeconds = 0;
};

USTRUCT(BlueprintType)
struct FEcoCombatDiagnostics
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) int32 ActiveProxies = 0;
    UPROPERTY(BlueprintReadOnly) int32 PooledProxies = 0;
    UPROPERTY(BlueprintReadOnly) int32 PendingDamage = 0;
    UPROPERTY(BlueprintReadOnly) int32 ContactsQueued = 0;
    UPROPERTY(BlueprintReadOnly) int32 DamageCommitted = 0;
    UPROPERTY(BlueprintReadOnly) int32 DamageRejected = 0;
    UPROPERTY(BlueprintReadOnly) int32 HuntingDeaths = 0;
    UPROPERTY(BlueprintReadOnly) int32 WolfAttacks = 0;
    UPROPERTY(BlueprintReadOnly) int32 PlayerHits = 0;
    UPROPERTY(BlueprintReadOnly) float MaximumQueueSeconds = 0;
};
