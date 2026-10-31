#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/EcoWorldV3.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "Mass/EcoHerdMigration.h"
#include "World/EcoVegetationField.h"
#include "Components/BoxComponent.h"
#include "Components/ArrowComponent.h"
#include "AI/Social/Shelter/EcoRefugeHabitat.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoReviewShelterArrow,"AdaptiveEcosystem.Review.ShelterFacingTemplateIsEditorOnly",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoReviewShelterArrow::RunTest(const FString&)
{
#if WITH_EDITORONLY_DATA
    const auto* Refuge=GetDefault<AEcoRefugeHabitat>();
    if(!TestNotNull(TEXT("Inherited refuge direction template"),Refuge->FacingArrow.Get()))return false;
    TestTrue(TEXT("Cook strips the native direction template and derived BP overrides"),Refuge->FacingArrow->IsEditorOnly());
#endif
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoReviewGroundPawn,"AdaptiveEcosystem.Review.GroundProjectionRejectsPawnAsTerrain",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoReviewGroundPawn::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto AddBox=[&](FVector Position,FVector Extent,ECollisionChannel Type){
        auto* Actor=W.World->SpawnActor<AActor>();auto* Box=NewObject<UBoxComponent>(Actor);
        Actor->SetRootComponent(Box);Box->SetBoxExtent(Extent);Box->SetCollisionObjectType(Type);
        Box->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);Box->SetCollisionResponseToAllChannels(ECR_Block);
        Box->RegisterComponent();Box->SetWorldLocation(Position);return Box;
    };
    AddBox(FVector(0,0,-10),FVector(500,500,10),ECC_WorldStatic);
    AddBox(FVector(0,0,160),FVector(40,40,40),ECC_Pawn);
    FVector Ground;
    TestTrue(TEXT("Real static ground remains usable below a player"),EcoCreatureMovement::ProjectSpawnPoint(*W.World,FVector::ZeroVector,Ground));
    TestTrue(TEXT("The dynamic pawn top is never returned as ground"),FMath::Abs(Ground.Z)<.1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoReviewHabitatBounds,"AdaptiveEcosystem.Review.HabitatRejectsCollapsedBounds",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoReviewHabitatBounds::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;auto* H=W.World->SpawnActor<AEcoVegetationHabitat>();
    if(!TestNotNull(TEXT("Actual habitat actor"),H))return false;
    H->SetActorScale3D(FVector(0,1,1));
    TestFalse(TEXT("Collapsed scale is unsupported"),H->IsValidHabitat());
    TestFalse(TEXT("Zero scale cannot turn a finite box into an unlimited supply axis"),H->ContainsGround(FVector(100000,0,0)));
    H->SetActorScale3D(FVector(-1,1,1));
    TestTrue(TEXT("Finite mirrored authoring remains supported"),H->IsValidHabitat());
    H->Bounds->SetBoxExtent(FVector(100,0,100));
    TestFalse(TEXT("Zero volume is rejected"),H->IsValidHabitat());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoReviewGridLayout,"AdaptiveEcosystem.Review.SoilCannotFallBackOnInvalidLayout",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoReviewGridLayout::RunTest(const FString&)
{
    EcoWorldV3::FFoodGrid G;G.Gw=1;G.Cell=2;G.Food={.2};G.Cap={1};G.Regen={.1};G.Vegetation.bEnabled=true;
    TestFalse(TEXT("Missing soil arrays are not a valid ON world"),G.HasValidVegetationLayout());
    G.Regrow();TestEqual(TEXT("Invalid ON cannot silently use legacy regrowth"),G.Food[0],.2);
    G.VegetationCells.assign(1,{});G.Habitats.assign(1,{});
    TestTrue(TEXT("Supported layout is accepted"),G.HasValidVegetationLayout());
    G.Regrow();TestTrue(TEXT("A valid ON grid actually grows"),G.Food[0]>.2&&G.VegetationGrown>0);
    G.Vegetation.Infiltration=-1;TestFalse(TEXT("Invalid model config is rejected too"),G.HasValidVegetationLayout());
    G.Vegetation.bEnabled=false;G.Food[0]=.2;G.Regrow();
    TestTrue(TEXT("OFF retains exact legacy regeneration"),FMath::IsNearlyEqual(G.Food[0],.28,1.e-12));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoReviewRoute,"AdaptiveEcosystem.Review.NativeRouteRejectsInvalidAndUnboundedSweep",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoReviewRoute::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;auto* R=W.World->SpawnActor<AEcoHerdMigrationRoute>();
    if(!TestNotNull(TEXT("Actual route authoring actor"),R))return false;
    R->FromRegion=TEXT("A");R->ToRegion=TEXT("B");R->Points={FVector::ZeroVector,FVector(13000,0,0)};
    TestTrue(TEXT("Existing 130m route remains supported"),R->IsValidRoute());
    R->Points[1].X=std::numeric_limits<double>::quiet_NaN();TestFalse(TEXT("NaN cannot reach World sweep"),R->IsValidRoute());
    R->Points[1]=FVector(13000,0,0);R->CorridorWidth=std::numeric_limits<float>::infinity();
    TestFalse(TEXT("Infinite formation width rejected"),R->IsValidRoute());R->CorridorWidth=600;
    R->Points[1].X=20001;TestFalse(TEXT("Oversized single sweep rejected"),R->IsValidRoute());
    R->Points.Init(FVector::ZeroVector,257);TestFalse(TEXT("Candidate work is bounded"),R->IsValidRoute());
    R->Points={FVector(0,0,0),FVector(20000,0,0),FVector(40000,0,0),FVector(60000,0,0),FVector(80000,0,0),FVector(100000,0,0),FVector(120000,0,0)};
    TestFalse(TEXT("Total route budget is bounded too"),R->IsValidRoute());
    auto* Native=W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();double Z=0;
    if(!TestNotNull(TEXT("Actual native movement entry point"),Native))return false;
    TestFalse(TEXT("Non-finite direct caller rejected before physics"),Native->TraceMove(TEXT("A"),FVector::ZeroVector,FVector(std::numeric_limits<double>::infinity(),0,0),Z,true));
    TestFalse(TEXT("Huge direct caller cannot run an unbounded GT trace loop"),Native->TraceMove(TEXT("A"),FVector::ZeroVector,FVector(1.e12,0,0),Z,true));
    return true;
}
#endif
