#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "AI/Policy/EcoBehaviorProcessors.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoNeighborhoodSubsystem.h"
#include "AI/Social/Senses/EcoPredatorPerception.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassEntitySubsystem.h"
#include "Components/BoxComponent.h"

namespace EcoPreyTests
{
    struct FRig
    {
        EcoTest::FScopedTestWorld Scoped;
        FMassEntityManager& EM;
        FMassEntityHandle Wolf, Deer;
        UEcoNeighborhoodGatherProcessor* Gather;
        UEcoPredatorPerceptionProcessor* Sense;
        UEcoPredationProcessor* Capture;
        FRig() : EM(Scoped.World->GetSubsystem<UMassEntitySubsystem>()->GetMutableEntityManager())
        {
            const TArray<const UScriptStruct*> Composition = {FTransformFragment::StaticStruct(), FMassVelocityFragment::StaticStruct(),
                FEcoIdentityFragment::StaticStruct(), FEcoVitalsFragment::StaticStruct(), FEcoRegionFragment::StaticStruct(),
                FEcoPredatorTag::StaticStruct(), FEcoIntegratedCreatureTag::StaticStruct(), FEcoPredatorStateFragment::StaticStruct(),
                FEcoPreySenseFragment::StaticStruct(), FEcoSensoryProfileFragment::StaticStruct()};
            FEcoSpeciesSharedFragment Species; Species.ViewDistance = 1000; Species.FOV = 120;
            FMassArchetypeSharedFragmentValues Shared;
            Shared.Add(EM.GetOrCreateSharedFragment(Species)); Shared.Add(EM.GetOrCreateSharedFragment(FEcoPredatorSensesSharedFragment())); Shared.Sort();
            TArray<FMassEntityHandle> Entities;
            EM.BatchCreateEntities(EM.CreateArchetype(Composition), Shared, 1, Entities); Wolf = Entities[0];
            EM.GetFragmentDataChecked<FEcoIdentityFragment>(Wolf).StableAgentId = 1;
            EM.GetFragmentDataChecked<FMassVelocityFragment>(Wolf).Value = FVector(100,0,0);
            const TArray<const UScriptStruct*> Prey = {FTransformFragment::StaticStruct(), FMassVelocityFragment::StaticStruct(),
                FEcoVitalsFragment::StaticStruct(), FEcoIdentityFragment::StaticStruct(), FEcoHerbivoreTag::StaticStruct()};
            Deer = EM.CreateEntity(EM.CreateArchetype(Prey));
            auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Deer); Id.StableAgentId = 2; Id.SpeciesId = TEXT("Herbivore");
            Gather = NewObject<UEcoNeighborhoodGatherProcessor>(Scoped.World);
            Sense = NewObject<UEcoPredatorPerceptionProcessor>(Scoped.World); Capture = NewObject<UEcoPredationProcessor>(Scoped.World);
            for (auto* Processor : TArray<UMassProcessor*>{Gather, Sense, Capture}) Processor->CallInitialize(Scoped.World, EM.AsShared());
        }
        void Position(FVector P) { EM.GetFragmentDataChecked<FTransformFragment>(Deer).GetMutableTransform().SetLocation(P); }
        void Scan(float Delta=.2f) { Scoped.World->TimeSeconds += Delta; EcoTest::RunProcessor(*Gather, EM, Delta); EcoTest::RunProcessor(*Sense, EM, Delta); }
        FEcoPreySenseFragment& State() { return EM.GetFragmentDataChecked<FEcoPreySenseFragment>(Wolf); }
        AActor* Wall(FVector P)
        {
            auto* Actor = Scoped.World->SpawnActor<AActor>(); auto* Box = NewObject<UBoxComponent>(Actor);
            Actor->SetRootComponent(Box); Box->SetBoxExtent(FVector(10,200,200));
            Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly); Box->SetCollisionResponseToAllChannels(ECR_Block);
            Box->RegisterComponent(); Actor->SetActorLocation(P); return Actor;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoPreyMemoryTest, "AdaptiveEcosystem.Social.Predator.SightHearingAndPrivateMemory",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoPreyMemoryTest::RunTest(const FString&)
{
    EcoPreyTests::FRig R; R.Position(FVector(300,0,0)); R.Scan();
    TestTrue(TEXT("Wolf sees live identified herbivore"), R.State().Cue.Source == EEcoSenseSource::Sight && R.State().TargetAgentId == 2);
    R.Position(FVector(-300,0,0)); R.Scan();
    TestTrue(TEXT("Hidden prey live position is never followed"), R.State().Cue.Source == EEcoSenseSource::Memory
        && R.State().Cue.LastKnownPosition.Equals(FVector(300,0,0)));
    TestTrue(TEXT("Sensory processor never writes observer transform"), R.EM.GetFragmentDataChecked<FTransformFragment>(R.Wolf).GetTransform().GetLocation().IsZero());
    FVector Goal;
    TestFalse(TEXT("Reader expires old cue without waiting for another scan"), EcoPredatorSenses::ReadPursuit(R.State(), FEcoSensorySettings(), FEcoSensoryProfileFragment(), 7, Goal));
    R.Scan(7);
    auto* Noise = R.Scoped.World->GetSubsystem<UEcoNoiseSubsystem>();
    Noise->ReportCreatureFootstep(FVector(-300,0,0), 1, 2000, 0, 2, TEXT("Herbivore")); R.Scan();
    TestTrue(TEXT("Ambient prey footstep behind FOV guides wolf without manufacturing threat"), R.State().Cue.Source == EEcoSenseSource::Hearing && R.State().TargetAgentId == 2);
    const double ObservedAt = R.State().Cue.LastObservedTime;
    R.Position(FVector(-600,0,0)); R.Scan();
    TestTrue(TEXT("Same emission is not refreshed or moved with hidden source"), R.State().Cue.LastObservedTime == ObservedAt
        && R.State().Cue.LastKnownPosition.Equals(FVector(-300,0,0)));
    R.EM.GetFragmentDataChecked<FEcoVitalsFragment>(R.Deer).HP = 0; R.Scan();
    TestTrue(TEXT("Dead prey is released"), R.State().TargetAgentId == 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoPreyCaptureTest, "AdaptiveEcosystem.Social.Predator.OcclusionAndCaptureGuard",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoPreyCaptureTest::RunTest(const FString&)
{
    EcoPreyTests::FRig R; R.Position(FVector(100,0,0)); auto* Wall = R.Wall(FVector(50,0,0)); R.Scan();
    TestTrue(TEXT("Wall blocks wolf vision"), R.State().TargetAgentId == 0);
    R.Scoped.World->GetSubsystem<UEcoNoiseSubsystem>()->ReportCreatureFootstep(FVector(100,0,0),1,2000,0,2,TEXT("Herbivore")); R.Scan();
    TestTrue(TEXT("Wall muffles but does not erase prey hearing"), R.State().Cue.Source == EEcoSenseSource::Hearing && R.State().Cue.Confidence < .3f);
    EcoTest::RunProcessor(*R.Capture, R.EM, .016f);
    TestTrue(TEXT("Hearing/memory cannot capture through wall"), R.EM.GetFragmentDataChecked<FEcoVitalsFragment>(R.Deer).HP > 0);
    Wall->Destroy(); R.Scan(); EcoTest::RunProcessor(*R.Capture, R.EM, .016f);
    TestTrue(TEXT("Fresh unobstructed sight permits existing close capture"), R.EM.GetFragmentDataChecked<FEcoVitalsFragment>(R.Deer).HP <= 0);
    R.Scan(); TestEqual(TEXT("Capture removes pursuit target"), R.State().TargetAgentId, int64(0));
    return true;
}
#endif
