#include "Mass/Movement/EcoSpeciesAIGroundSceneSubsystem.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "NavModifierVolume.h"
#include "NavAreas/NavArea_Null.h"
bool UEcoSpeciesAIGroundSceneSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{const auto* W=Cast<UWorld>(Outer);return W&&W->IsGameWorld()&&W->GetNetMode()!=NM_Client&&Super::ShouldCreateSubsystem(Outer);}
bool UEcoSpeciesAIGroundSceneSubsystem::CrossesExcluded(const FVector& Start,const FVector& End)
{
    check(IsInGameThread());
    if(SnapshotFrame!=GFrameCounter)
    {
        Exclusions.Reset();SnapshotFrame=GFrameCounter;
        // Once per world/frame, rather than iterating Actors for every entity/substep.
        for(TActorIterator<ANavModifierVolume> It(GetWorld());It;++It)
            if(const UClass* Area=It->GetAreaClass();Area&&Area->IsChildOf(UNavArea_Null::StaticClass())&&!It->GetAreaClassToReplace())
                Exclusions.Add(It->GetNavigationBounds().ExpandBy(30));
    }
    for(const auto& Box:Exclusions)if(FMath::LineBoxIntersection(Box,Start,End,End-Start))return true;
    return false;
}
