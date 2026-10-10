#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "Components/BoxComponent.h"
#include "NavModifierVolume.h"
#include "NavAreas/NavArea_Null.h"
#include "NavAreas/NavArea_Default.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLevelGround, "AdaptiveEcosystem.Creature.Level.GroundClearanceAndWaterExclusion", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoLevelGround::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* Floor = W.World->SpawnActor<AStaticMeshActor>();
    Floor->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
    Floor->SetActorScale3D(FVector(100,100,1));
    Floor->SetActorLocation(FVector(0,0,-2050));
    Floor->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
    FVector Ground;
    TestTrue(TEXT("Spawn authoring at zero finds terrain two thousand cm below"), EcoCreatureMovement::ProjectSpawnPoint(*W.World, FVector::ZeroVector, Ground));
    TestTrue(TEXT("Spawn stays on the actual floor"), FMath::IsNearlyEqual(Ground.Z, -2000.0, 0.1));
    TestFalse(TEXT("No ground cannot produce a floating spawn"), EcoCreatureMovement::ProjectSpawnPoint(*W.World, FVector(20000,0,0), Ground));
    auto* Water = W.World->SpawnActor<ANavModifierVolume>();
    auto* Bounds = NewObject<UBoxComponent>(Water);
    Water->AddInstanceComponent(Bounds); Water->SetRootComponent(Bounds);
    Bounds->SetBoxExtent(FVector(250,250,3000)); Bounds->SetCollisionEnabled(ECollisionEnabled::NoCollision); Bounds->RegisterComponent();
    Water->SetAreaClass(UNavArea_Null::StaticClass());
    TestFalse(TEXT("No-move water volume rejects otherwise valid ground"), EcoCreatureMovement::ProjectSpawnPoint(*W.World, FVector::ZeroVector, Ground));
    TestTrue(TEXT("An entire step across water is rejected even when both endpoints are dry"), EcoCreatureMovement::CrossesExcludedArea(*W.World, FVector(-1000,0,-2000), FVector(1000,0,-2000)));
    TestFalse(TEXT("Dry path beside water remains allowed"), EcoCreatureMovement::CrossesExcludedArea(*W.World, FVector(-1000,400,-2000), FVector(1000,400,-2000)));
    Water->SetAreaClass(UNavArea_Default::StaticClass());
    TestFalse(TEXT("Walkable modifier volumes do not block direct movement"), EcoCreatureMovement::CrossesExcludedArea(*W.World, FVector(-1000,0,-2000), FVector(1000,0,-2000)));
    return true;
}
#endif
