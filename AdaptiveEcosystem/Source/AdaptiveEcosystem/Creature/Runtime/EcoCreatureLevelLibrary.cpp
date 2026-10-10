#include "Creature/Runtime/EcoCreatureLevelLibrary.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Engine/Engine.h"
#include "Engine/World.h"

FEcoCreatureGroundProbe UEcoCreatureLevelLibrary::ProbeGround(UObject* WorldContext, FVector Hint)
{
    FEcoCreatureGroundProbe Result;
    if (UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr)
        Result.bValid = EcoCreatureMovement::ProjectSpawnPoint(*World, Hint, Result.Position);
    return Result;
}
