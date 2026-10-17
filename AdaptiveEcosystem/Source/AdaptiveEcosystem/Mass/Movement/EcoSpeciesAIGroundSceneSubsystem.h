#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoSpeciesAIGroundSceneSubsystem.generated.h"
/** World geometry cache only. Holds no entity state and performs no movement. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoSpeciesAIGroundSceneSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    bool CrossesExcluded(const FVector& Start,const FVector& End);
private:
    uint64 SnapshotFrame=MAX_uint64;
    TArray<FBox> Exclusions;
};
