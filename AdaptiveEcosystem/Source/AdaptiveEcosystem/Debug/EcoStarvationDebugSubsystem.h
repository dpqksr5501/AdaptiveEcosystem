#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoStarvationDebugSubsystem.generated.h"

/** Example feature registration: each loaded region receives Debug.Starvation.<RegionId>. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoStarvationDebugSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()
public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
};
