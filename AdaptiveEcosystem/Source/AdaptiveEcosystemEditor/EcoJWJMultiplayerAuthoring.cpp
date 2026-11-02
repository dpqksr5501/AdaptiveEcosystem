#include "EcoJWJMultiplayerAuthoring.h"
#include "Engine/World.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionEditorLoaderAdapter.h"
#include "WorldPartition/LoaderAdapter/LoaderAdapterShape.h"

bool UEcoJWJMultiplayerAuthoring::LoadStartTerrain(UWorld* World, FVector Center)
{
    if (!World || World->WorldType != EWorldType::Editor ||
        World->GetPackage()->GetName() != TEXT("/Game/JWJ/Integration_JwJ")) return false;
    if (auto* Partition = World->GetWorldPartition())
    {
        const FVector Extent(6000, 6000, 100000);
        auto* Loader = Partition->CreateEditorLoaderAdapter<FLoaderAdapterShape>(
            World, FBox(Center - Extent, Center + Extent), TEXT("JWJ multiplayer start terrain"));
        Loader->GetLoaderAdapter()->Load();
    }
    return true;
}
