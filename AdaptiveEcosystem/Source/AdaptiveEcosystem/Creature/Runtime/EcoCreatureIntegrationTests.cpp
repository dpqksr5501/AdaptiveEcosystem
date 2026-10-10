#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureNetworkTrait.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Representation/EcoCreatureBlendSpace.h"
#include "Network/Mass/EcoMassReplicationTypes.h"
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "AI/Policy/EcoBehaviorProcessors.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include <limits>
#include "AI/Social/Shelter/EcoShelterLifecycleProcessor.h"
#include "AI/Social/Shelter/EcoShelterProcessors.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassEntitySubsystem.h"
#include "MassEntityTemplate.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Components/SkeletalMeshComponent.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoIntegratedHandoff, "AdaptiveEcosystem.Creature.Integration.ActualMovementAndShelterLifecycle", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoIntegratedHandoff::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto& EM = W.World->GetSubsystem<UMassEntitySubsystem>()->GetMutableEntityManager();
    auto* Shelters = W.World->GetSubsystem<UEcoShelterSubsystem>();
    Shelters->RegisterShelter(FVector::ZeroVector, FVector::ForwardVector, 1.f, 1, 50.f);
    const TArray<const UScriptStruct*> Types = {FTransformFragment::StaticStruct(), FMassVelocityFragment::StaticStruct(), FEcoSteeringGeometryFragment::StaticStruct(),
        FEcoHerbivoreTag::StaticStruct(), FEcoAliveTag::StaticStruct(), FEcoIdentityFragment::StaticStruct(), FEcoVitalsFragment::StaticStruct(), FEcoTravelFragment::StaticStruct(),
        FEcoPolicyOutputFragment::StaticStruct(), FEcoAlarmStateFragment::StaticStruct(), FEcoSocialBehaviorFragment::StaticStruct(), FEcoShelterIntentFragment::StaticStruct(),
        FEcoSocialMovementRequestFragment::StaticStruct(), FEcoShelterMovementFeedbackFragment::StaticStruct()};
    FMassArchetypeSharedFragmentValues Shared;
    Shared.Add(EM.GetOrCreateSharedFragment(FEcoSpeciesSharedFragment())); Shared.Add(EM.GetOrCreateSharedFragment(FEcoSocialSpeciesSharedFragment())); Shared.Sort();
    TArray<FMassEntityHandle> Entities; EM.BatchCreateEntities(EM.CreateArchetype(Types), Shared, 1, Entities);
    const auto E = Entities[0]; EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId = 321;
    EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(FVector(-500,0,0));
    auto& Raw = EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action; Raw.Forage = 0.8f; Raw.Cover = 0.1f;
    auto& Social = EM.GetFragmentDataChecked<FEcoSocialBehaviorFragment>(E); Social.ModulatedAction = Raw; Social.ModulatedAction.Cover = 0.9f;
    auto* Query = NewObject<UEcoShelterQueryProcessor>(W.World); auto* Reserve = NewObject<UEcoShelterReservationProcessor>(W.World);
    auto* Life = NewObject<UEcoShelterLifecycleProcessor>(W.World); auto* Move = NewObject<UEcoSteeringProcessor>(W.World);
    for (auto* P : TArray<UMassProcessor*>{Query, Reserve, Life, Move}) P->CallInitialize(W.World, EM.AsShared());
    EcoTest::RunProcessor(*Query, EM, 0.1f); EcoTest::RunProcessor(*Reserve, EM, 0.1f); EcoTest::RunProcessor(*Life, EM, 0.1f);
    auto& Intent = EM.GetFragmentDataChecked<FEcoShelterIntentFragment>(E);
    if (!TestTrue(TEXT("A real lease is acquired"), Intent.ReservationId > 0)) return false;
    const FVector Target = Intent.TargetPosition;
    for (int32 I=0; I<12; ++I) { EcoTest::RunProcessor(*Move, EM, 0.1f); W.World->TimeSeconds += 0.1f; EcoTest::RunProcessor(*Life, EM, 0.1f); }
    TestTrue(TEXT("Actual writer reaches authored slot and Lifecycle occupies it"), Intent.State == EEcoShelterIntentState::Occupied
        && FVector::Dist(EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation(), Target) <= 60);
    TestTrue(TEXT("Occupied animals stop rather than continuing raw PPO movement"), EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value.IsNearlyZero());
    TestEqual(TEXT("Raw PPO cover remains unchanged"), Raw.Cover, 0.1f);
    auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(E); Travel.State = EEcoResidenceState::Traveling; Travel.TargetPosition = FVector(1000,0,0); Travel.MoveSpeed = 400;
    EcoTest::RunProcessor(*Move, EM, 0.1f);
    TestTrue(TEXT("Migration yields the shelter lease"), EM.GetFragmentDataChecked<FEcoShelterMovementFeedbackFragment>(E).Status == EEcoShelterMovementStatus::Yielded);
    EcoTest::RunProcessor(*Life, EM, 0.1f);
    TestTrue(TEXT("Migration releases occupancy"), Intent.State == EEcoShelterIntentState::None);
    EM.GetFragmentDataChecked<FEcoVitalsFragment>(E).HP = 0;
    const FVector Before = EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation(); EcoTest::RunProcessor(*Move, EM, 0.1f);
    TestTrue(TEXT("Dead creatures cannot move even with a travel destination"), EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation().Equals(Before));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoIntegratedFailure, "AdaptiveEcosystem.Creature.Integration.ExpiredMalformedAndHoldRequests", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoIntegratedFailure::RunTest(const FString&)
{
    FEcoSocialMovementRequestFragment R; R.bValid = true; R.Mode = EEcoSocialMovementMode::ShelterTravel;
    R.ReservationId=42; R.TargetPosition=FVector(500,0,0); R.ArrivalRadius=60; R.ValidUntilWorldTime=10;
    FEcoShelterMovementFeedbackFragment F;
    auto V = EcoCreatureMovement::SelectVelocity(FVector::ZeroVector, FVector(0,900,0), 900, 0.1f, 11, nullptr, &R, &F);
    TestTrue(TEXT("Expired leases stop movement and report failure with matching generation"), V.IsZero() && F.Status == EEcoShelterMovementStatus::Failed && F.ReservationId==42);
    R.ValidUntilWorldTime=20; R.Mode=EEcoSocialMovementMode::ShelterHold;
    V=EcoCreatureMovement::SelectVelocity(R.TargetPosition, FVector(0,900,0),900,0.1f,11,nullptr,&R,&F);
    TestTrue(TEXT("Hold suppresses raw locomotion and acknowledges arrival"), V.IsZero() && F.Status==EEcoShelterMovementStatus::Arrived);
    R.TargetPosition.X = std::numeric_limits<double>::quiet_NaN();
    V=EcoCreatureMovement::SelectVelocity(FVector::ZeroVector,FVector(0,900,0),900,0.1f,11,nullptr,&R,&F);
    TestTrue(TEXT("Malformed targets cannot reach Transform"), V.IsZero() && F.Status==EEcoShelterMovementStatus::Failed);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoIntegratedAssets, "AdaptiveEcosystem.Creature.Integration.SavedAnimalAssetsAndTemplate", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoIntegratedAssets::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    for (const FString Kind : {TEXT("Deer"),TEXT("Wolf")})
    {
        const FString Root = TEXT("/Game/Creatures/Integrated/");
        auto* Config=LoadObject<UEcoCreatureEntityConfig>(nullptr, *(Root+TEXT("DA_Eco")+Kind+TEXT(".DA_Eco")+Kind));
        auto* BS=LoadObject<UBlendSpace>(nullptr,*(Root+TEXT("BS_Eco")+Kind+TEXT("_Turning.BS_Eco")+Kind+TEXT("_Turning")));
        UClass* BP=LoadClass<AEcoCreatureRepresentationActor>(nullptr,*(Root+TEXT("BP_Eco")+Kind+TEXT(".BP_Eco")+Kind+TEXT("_C")));
        if (!TestNotNull(TEXT("Saved config"),Config)||!TestNotNull(TEXT("Saved BS"),BS)||!TestNotNull(TEXT("Saved BP"),BP)) return false;
        auto* Actor=W.World->SpawnActor<AEcoCreatureRepresentationActor>(BP);
        TestTrue(TEXT("BP owns imported mesh and matching BS"), Actor->VisualMesh && Actor->LocomotionBlendSpace==BS && BS->GetSkeleton());
        TestEqual(TEXT("Speed x signed-turn sample grid"),BS->GetBlendSamples().Num(),9);
        TestFalse(TEXT("Active locomotion is a 2D BS"),BS->IsA<UBlendSpace1D>());
        TestEqual(TEXT("Signed turn minimum"),BS->GetBlendParameter(1).Min,-1.f);
        TestEqual(TEXT("Signed turn maximum"),BS->GetBlendParameter(1).Max,1.f);
        for (const auto& Sample : BS->GetBlendSamples()) TestTrue(TEXT("In-place compatible samples"), Sample.Animation && Sample.Animation->GetSkeleton()==BS->GetSkeleton() && !Sample.Animation->bEnableRootMotion);
        const auto& Template=Config->GetOrCreateEntityTemplate(*W.World);
        TestTrue(TEXT("Role-aware native template builds"),Template.IsValid());
        const auto& Data=Template.GetTemplateData();
        TestTrue(TEXT("Authoritative template has identity/vitals and one custom movement path"),Data.HasFragment<FEcoIdentityFragment>() && Data.HasFragment<FEcoVitalsFragment>() && Data.HasTag<FMassCustomMovementTag>());
        TestTrue(TEXT("Only herbivores receive policy and Social requests"), Data.HasFragment<FEcoPolicyOutputFragment>()==(Kind==TEXT("Deer")) && Data.HasFragment<FEcoSocialMovementRequestFragment>()==(Kind==TEXT("Deer")));
        Actor->BindIdentity(Kind==TEXT("Wolf")?2:1,Kind==TEXT("Wolf")?FName(TEXT("Wolf")):FName(TEXT("Herbivore")));
        FEcoCreatureVisualState State; State.StableAgentId=Actor->VisualState.StableAgentId; State.SpeciesId=Actor->VisualSpeciesId; State.Sequence=1; State.Velocity=FVector(900,0,0);
        TestTrue(TEXT("Actual visual update accepts authoritative locomotion"),Actor->ConsumeVisualState(State,0.016f));
        TestTrue(TEXT("Single-node animation uses the saved BS"),Actor->CreatureMesh->GetSingleNodeInstance() && Actor->CreatureMesh->GetSingleNodeInstance()->GetCurrentAsset()==BS);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoIntegratedPayload, "AdaptiveEcosystem.Creature.Integration.VisualPayloadDeltas", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoIntegratedPayload::RunTest(const FString&)
{
    FReplicatedEcoMassAgent A;
    TestTrue(TEXT("Initial movement changes payload"), A.SetPresentation(FVector(900,0,0),9,255,128));
    TestFalse(TEXT("Unchanged payload creates no delta"),A.SetPresentation(FVector(900,0,0),9,255,128));
    TestTrue(TEXT("Stationary death still creates a transport delta"),A.SetPresentation(FVector::ZeroVector,8,0,0));
    TestTrue(TEXT("Client receives visual death and energy without logical vitals"),A.GetVelocity().IsZero() && A.GetVisualFlags()==8 && A.GetHealth()==0 && A.GetEnergy()==0);
    return true;
}
#endif
