#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Core/EcoActivityTypes.h"
#include "EcoSpeciesAIProfile.generated.h"
class UStateTree;

UENUM(BlueprintType)
enum class EEcoEnabledSpecies : uint8 { Both, DeerOnly, WolfOnly };
UENUM(BlueprintType)
enum class EEcoActivitySlotKind : uint8 { Graze, Rest, Feed };

/** Immutable authored tuning; mutable individual state belongs to Entity fragments. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoSpeciesAIProfile : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, Category="Contract") int32 Version = 1;
    UPROPERTY(EditAnywhere, Category="Contract") bool bPredator = false;
    UPROPERTY(EditAnywhere, Category="Contract") bool bPolicyOnly = false;
    UPROPERTY(EditAnywhere, Category="Behavior") TObjectPtr<UStateTree> StateTree;
    UPROPERTY(EditAnywhere, Category="Behavior") float DecisionInterval = .25f;
    UPROPERTY(EditAnywhere, Category="Behavior") float HungryEnter = .45f;
    UPROPERTY(EditAnywhere, Category="Behavior") float SatiatedExit = .8f;
    UPROPERTY(EditAnywhere, Category="Behavior") float MinimumDwell = 1.f;
    UPROPERTY(EditAnywhere, Category="Behavior") float CalmSeconds = 3.f;
    UPROPERTY(EditAnywhere, Category="Movement") float WalkSpeed = 200.f;
    UPROPERTY(EditAnywhere, Category="Movement") float RunSpeed = 650.f;
    UPROPERTY(EditAnywhere, Category="Movement") float BodyRadius = 30.f;
    UPROPERTY(EditAnywhere, Category="Movement") float BodyHeight = 130.f;
    UPROPERTY(EditAnywhere, Category="Movement") float WanderRadius = 1200.f;
    UPROPERTY(EditAnywhere, Category="Movement") float ArrivalRadius = 100.f;
    UPROPERTY(EditAnywhere, Category="Navigation") float RepathInterval = .75f;
    UPROPERTY(EditAnywhere, Category="Navigation") float RetargetDistance = 200.f;
    UPROPERTY(EditAnywhere, Category="Navigation") float CorridorWidth = 300.f;
    UPROPERTY(EditAnywhere, Category="Navigation") float PathTimeout = 8.f;
    UPROPERTY(EditAnywhere, Category="Interaction") float SlotLease = 12.f;
    UPROPERTY(EditAnywhere, Category="Interaction") float FoodUnitsPerSecond = 1.f;
    UPROPERTY(EditAnywhere, Category="Interaction") float GrazeMaxSpeed = 80.f;
    UPROPERTY(EditAnywhere, Category="Predator") float PursuitSeconds = 12.f;
    UPROPERTY(EditAnywhere, Category="Predator") float SearchSeconds = 4.f;
    UPROPERTY(EditAnywhere, Category="Predator") float AttackCooldown = 3.f;
    UPROPERTY(EditAnywhere, Category="Predator") float AttackRadius = 120.f;
    UPROPERTY(EditAnywhere, Category="Scheduling") float MediumDistance = 10000.f;
    UPROPERTY(EditAnywhere, Category="Scheduling") float FarDistance = 20000.f;
    bool Validate(FString& Error) const;
};
