#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoMigrationDebugSubsystem.generated.h"

/** Read-only display. Never selects targets, moves agents, or changes resources. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoMigrationDebugSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()
public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(EcoMigrationDebug, STATGROUP_Tickables); }
};
