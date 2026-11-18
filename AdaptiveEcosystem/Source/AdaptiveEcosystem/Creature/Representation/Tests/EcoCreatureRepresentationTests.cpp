#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "AI/Policy/EcoBehaviorProcessors.h"
#include "AI/Policy/EcoBehaviorConfig.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Debug/EcoCreatureDemoSpawner.h"
#include "MassEntitySubsystem.h"
#include "Mass/EntityFragments.h"
#include "Mass/EcoMassFragments.h"
#include "MassMovementFragments.h"
#include "EngineUtils.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/BlendSpace.h"
#include "Animation/AnimSequence.h"
#include "UI/EcoHealthBarComponent.h"
#include "UI/EcoHealthBarWidget.h"
#include "Network/Mass/EcoMassReplicationTypes.h"
#include "Mass/EcoMassPresentationFragments.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoPresentationJitterTest, "AdaptiveEcosystem.Creature.Visual.PacketJitterAndReset",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoPresentationJitterTest::RunTest(const FString& Parameters)
{
	FEcoClientPresentationFragment Client;
	FEcoRepresentationSnapshot Sample;
	Sample.StableAgentId = 7;
	Sample.SampleSequence = 1;
	Sample.ServerSampleRealTimeSeconds = 1.0;
	Sample.Location = FVector::ZeroVector;
	TestTrue(TEXT("First movement sample accepted"), Client.Receive(Sample, 1.08));
	Sample.SampleSequence = 2;
	Sample.ServerSampleRealTimeSeconds = 1.1;
	Sample.Location = FVector(100.0, 0.0, 0.0);
	TestTrue(TEXT("Second movement sample accepted"), Client.Receive(Sample, 1.18));
	const FVector Before = Client.GetRenderPosition(1.22, .1);
	Sample.SampleSequence = 3;
	Sample.ServerSampleRealTimeSeconds = 1.2;
	Sample.Location = FVector(200.0, 0.0, 0.0);
	TestTrue(TEXT("Earlier than usual delivery is accepted"), Client.Receive(Sample, 1.22));
	const FVector After = Client.GetRenderPosition(1.22, .1);
	TestTrue(TEXT("A 60 ms delay change does not snap the render position"), FVector::Distance(Before, After) < 5.0);
	++Sample.VisualRevision;
	TestTrue(TEXT("Visual-only update accepted"), Client.Receive(Sample, 1.23));
	TestTrue(TEXT("Visual-only update preserves the movement timeline"), Client.GetRenderPosition(1.22, .1).Equals(After));
	++Sample.SampleSequence;
	++Sample.MovementDiscontinuityRevision;
	Sample.Location = FVector(900.0, 0.0, 0.0);
	TestTrue(TEXT("Teleport accepted"), Client.Receive(Sample, 1.24));
	TestTrue(TEXT("Teleport snaps and discards buffered movement"), Client.GetRenderPosition(1.24, .1).Equals(Sample.Location));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoHealthBarTest, "AdaptiveEcosystem.Creature.Visual.HealthBarReplicationAndPooling",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoHealthBarTest::RunTest(const FString&)
{
	EcoTest::FScopedTestWorld W;
	for (const FString Kind : {TEXT("Deer"), TEXT("Wolf")})
	{
		UClass* BP = LoadClass<AEcoCreatureRepresentationActor>(nullptr,
			*(TEXT("/Game/Creatures/Integrated/BP_Eco") + Kind + TEXT(".BP_Eco") + Kind + TEXT("_C")));
		if (!TestNotNull(TEXT("Saved species Blueprint"), BP)) return false;
		auto* Visual = W.World->SpawnActor<AEcoCreatureRepresentationActor>(BP);
		auto* Other = W.World->SpawnActor<AEcoCreatureRepresentationActor>(BP);
		if (!TestNotNull(TEXT("Every saved species inherits a health bar"), Visual->HealthBar.Get())) return false;
		TestTrue(TEXT("Screen space faces each local viewer"), Visual->HealthBar->GetWidgetSpace() == EWidgetSpace::Screen);
		TestTrue(TEXT("Works without a widget asset"), Visual->HealthBar->GetWidgetClass() == UEcoHealthBarWidget::StaticClass());
		Visual->BindIdentity(7, Visual->VisualSpeciesId);
		Other->BindIdentity(8, Other->VisualSpeciesId);
		TestFalse(TEXT("No guessed HP before the first sample"), Visual->HealthBar->IsVisible());
		FReplicatedEcoMassAgent Agent;
		Agent.SetStableAgentId(7); Agent.SetSpeciesId(Visual->VisualSpeciesId);
		Agent.SetVisualState(1.f, 1.f, EEcoVisualLifeState::Alive);
		Agent.SetPresentation(FVector::ZeroVector, 9, 255, 255);
		Agent.StampSample(1.0);
		FEcoClientPresentationFragment ClientA, ClientB;
		FEcoCreatureVisualState State;
		State.StableAgentId = 7; State.SpeciesId = Visual->VisualSpeciesId;
		State.Sequence = 1; State.bHasVitals = true; State.NormalizedHealth = 1.f;
		TestTrue(TEXT("First client accepts full HP"), ClientA.Receive(Agent.MakeRepresentationSnapshot(), 1.1));
		TestTrue(TEXT("Second client accepts full HP"), ClientB.Receive(Agent.MakeRepresentationSnapshot(), 1.2));
		Visual->ConsumeVisualState(State, .016f);
		TestTrue(TEXT("Full health is always shown"), Visual->HealthBar->IsVisible() && Visual->HealthBar->GetHealthFraction() == 1.f);
		// Damage without movement: visual revision must deliver HP to both clients.
		Agent.SetVisualState(.7f, 1.f, EEcoVisualLifeState::Alive);
		Agent.SetPresentation(FVector::ZeroVector, 9, EcoRepresentation::QuantizeUnit(.7f), 255);
		TestTrue(TEXT("Stationary damage reaches client A"), ClientA.Receive(Agent.MakeRepresentationSnapshot(), 1.3));
		TestTrue(TEXT("Stationary damage reaches client B"), ClientB.Receive(Agent.MakeRepresentationSnapshot(), 1.4));
		State.Sequence++; State.NormalizedHealth = Agent.GetHealth() / 255.f;
		Visual->ConsumeVisualState(State, .016f);
		TestTrue(TEXT("Bar consumes received HP"), FMath::IsNearlyEqual(Visual->HealthBar->GetHealthFraction(), .7f, 1.f / 255.f));
		TestFalse(TEXT("A different agent never inherits damaged health"), Other->HealthBar->HasHealthSample());
		State.NormalizedHealth = 1.f;
		TestFalse(TEXT("Late visual snapshot is rejected"), Visual->ConsumeVisualState(State, .016f));
		TestTrue(TEXT("Rejected snapshot cannot refill bar"), Visual->HealthBar->GetHealthFraction() < 1.f);
		State.Sequence++; State.bAlive = false;
		Visual->ConsumeVisualState(State, .016f);
		TestTrue(TEXT("Explicit death displays empty bar even with rounded HP"), Visual->HealthBar->IsVisible() && Visual->HealthBar->GetHealthFraction() == 0.f);
		Visual->ClearBinding();
		TestFalse(TEXT("Pool clears visibility and health sample"), Visual->HealthBar->IsVisible() || Visual->HealthBar->HasHealthSample());
		Visual->BindIdentity(9, Visual->VisualSpeciesId);
		TestFalse(TEXT("Reused actor waits for the new identity's HP"), Visual->HealthBar->IsVisible());
		Visual->HealthBar->SetHealth(50.f, 200.f);
		TestEqual(TEXT("Reusable adapter supports arbitrary maximum health"), Visual->HealthBar->GetHealthFraction(), .25f);
		Visual->HealthBar->SetHealth(50.f, 0.f);
		TestFalse(TEXT("Missing health capacity does not invent HP"), Visual->HealthBar->IsVisible());
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoVisualBindingTest, "AdaptiveEcosystem.Creature.Visual.BindingAndStaleSnapshots",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoVisualBindingTest::RunTest(const FString& Parameters)
{
	EcoTest::FScopedTestWorld Scoped;
	auto* Visual = Scoped.World->SpawnActor<AEcoWolfRepresentation>();
	TestFalse(TEXT("Species mismatches cannot bind a wolf representation"), Visual->BindIdentity(7, TEXT("Herbivore")));
	TestTrue(TEXT("Correct logical identity binds once"), Visual->BindIdentity(7, TEXT("Wolf")));
	TestFalse(TEXT("Binding cannot silently overwrite an existing identity"), Visual->BindIdentity(8, TEXT("Wolf")));
	FEcoCreatureVisualState State;
	State.StableAgentId = 7; State.SpeciesId = TEXT("Wolf"); State.Sequence = 1;
	State.Position = FVector(300, 400, 0); State.Velocity = FVector(0, 900, 0);
	TestTrue(TEXT("Valid state applies"), Visual->ConsumeVisualState(State, 0.016f));
	TestTrue(TEXT("First placement snaps facing to actual velocity"), FMath::IsNearlyEqual(Visual->GetActorRotation().Yaw, 90.0f, 0.001f)
		&& Visual->GetActorLocation().Equals(State.Position) && Visual->GetVelocity().Equals(State.Velocity));
	State.Position = FVector(999, 0, 0);
	TestFalse(TEXT("Duplicate sequence cannot move the visual"), Visual->ConsumeVisualState(State, 0.016f));
	TestTrue(TEXT("Rejected input does not change position"), Visual->GetActorLocation().Equals(FVector(300, 400, 0)));
	State.Sequence = 2; State.StableAgentId = 8;
	TestFalse(TEXT("Wrong logical identity cannot control this Actor"), Visual->ConsumeVisualState(State, 0.016f));
	State.StableAgentId = 7; State.WorldTime = -1.0;
	TestFalse(TEXT("Malformed time rejected"), Visual->ConsumeVisualState(State, 0.016f));
	Visual->ClearBinding();
	TestTrue(TEXT("Clearing detaches and hides representation"), !Visual->bBound && Visual->GetVelocity().IsZero() && Visual->IsHidden());
	TestFalse(TEXT("Detached visual rejects late updates"), Visual->ConsumeVisualState(State, 0.016f));
	TestTrue(TEXT("Pooled wolf accepts a new identity"), Visual->BindIdentity(8, TEXT("Wolf")));
	State.StableAgentId = 8; State.Sequence = 1; State.WorldTime = 0;
	State.Velocity = FVector::ZeroVector; State.bAlive = false;
	State.bHasFacing = true; State.FacingYawDegrees = -45.f;
	TestTrue(TEXT("Late corpse snapshot applies"), Visual->ConsumeVisualState(State, 0.016f));
	TestTrue(TEXT("Reused corpse actor uses snapshot yaw"), FMath::IsNearlyEqual(Visual->GetActorRotation().Yaw, -45.0f, 0.001f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoVisualMotionTest, "AdaptiveEcosystem.Creature.Visual.MotionAndReadOnlyMass",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoVisualMotionTest::RunTest(const FString& Parameters)
{
	EcoTest::FScopedTestWorld Scoped;
	auto& EM = Scoped.World->GetSubsystem<UMassEntitySubsystem>()->GetMutableEntityManager();
	const TArray<const UScriptStruct*> Composition = {FTransformFragment::StaticStruct(), FMassVelocityFragment::StaticStruct()};
	const auto E = EM.CreateEntity(EM.CreateArchetype(Composition));
	EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(FVector(20, 30, 0));
	EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value = FVector(100, 0, 0);
	auto* Visual = Scoped.World->SpawnActor<AEcoHerbivoreRepresentation>();
	Visual->BindIdentity(20, TEXT("Herbivore"));
	FEcoCreatureVisualState State;
	State.StableAgentId = 20; State.SpeciesId = TEXT("Herbivore"); State.Sequence = 1;
	State.Position = EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
	State.Velocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value;
	Visual->ConsumeVisualState(State, 0.016f);
	TestTrue(TEXT("Walking is derived from actual velocity"), Visual->VisualMotion == EEcoCreatureVisualMotion::Walk);
	State.Sequence++; State.Velocity = FVector(900, 0, 0); Visual->ConsumeVisualState(State, 0.016f);
	TestTrue(TEXT("Running does not change the logical speed"), Visual->VisualMotion == EEcoCreatureVisualMotion::Run
		&& EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value.Equals(FVector(100, 0, 0)));
	State.Sequence++; State.Velocity = FVector::ZeroVector; State.bEating = true;
	Visual->ConsumeVisualState(State, 0.016f);
	TestTrue(TEXT("Stationary eating is visual state only"), Visual->VisualMotion == EEcoCreatureVisualMotion::Eating);
	State.Sequence++; State.bAlive = false; State.Velocity = FVector(900, 0, 0);
	Visual->ConsumeVisualState(State, 0.016f);
	TestTrue(TEXT("Dead representation reports no locomotion"), Visual->VisualMotion == EEcoCreatureVisualMotion::Dead && Visual->GetVelocity().IsZero());
	TestTrue(TEXT("No representation update wrote Mass position"),
		EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation().Equals(FVector(20, 30, 0)));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoCreatureDemoTest, "AdaptiveEcosystem.Creature.Demo.PPOAndPredatorBridgeLifecycle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoCreatureDemoTest::RunTest(const FString& Parameters)
{
	EcoTest::FScopedTestWorld Scoped;
	auto& EM = Scoped.World->GetSubsystem<UMassEntitySubsystem>()->GetMutableEntityManager();
	UClass* DemoClass = LoadClass<AEcoCreatureDemoSpawner>(nullptr, TEXT("/Game/Creatures/Demo/BP_EcoCreatureDemoSpawner.BP_EcoCreatureDemoSpawner_C"));
	UClass* WolfClass = LoadClass<AEcoCreatureRepresentationActor>(nullptr, TEXT("/Game/Creatures/Demo/BP_EcoWolf.BP_EcoWolf_C"));
	UClass* HerbClass = LoadClass<AEcoCreatureRepresentationActor>(nullptr, TEXT("/Game/Creatures/Demo/BP_EcoHerbivore.BP_EcoHerbivore_C"));
	if (!TestNotNull(TEXT("Saved demo Blueprint"), DemoClass) || !TestNotNull(TEXT("Saved wolf Blueprint"), WolfClass)
		|| !TestNotNull(TEXT("Saved herbivore Blueprint"), HerbClass)) { return false; }
	auto* Demo = Scoped.World->SpawnActor<AEcoCreatureDemoSpawner>(DemoClass);
	TestTrue(TEXT("Saved spawner defaults reference both generated species Blueprints"),
		Demo->WolfActorClass == WolfClass && Demo->HerbivoreActorClass == HerbClass);
	Demo->HerbivoreCount = 2; Demo->PredatorCount = 1;
	Demo->DispatchBeginPlay();
	TestEqual(TEXT("Every logical creature has exactly one representation"), Demo->GetRepresentedCreatureCount(), 3);
	if (Demo->GetTestHerbivores().Num() != 2 || Demo->GetTestPredators().Num() != 1) { return false; }
	const auto Herb = Demo->GetTestHerbivores()[0]; const auto Wolf = Demo->GetTestPredators()[0];
	const int64 HerbId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Herb).StableAgentId;
	TestTrue(TEXT("Demo identities are valid and unique"), HerbId > 0
		&& HerbId != EM.GetFragmentDataChecked<FEcoIdentityFragment>(Wolf).StableAgentId);
	const FVector BeforeHerb = EM.GetFragmentDataChecked<FTransformFragment>(Herb).GetTransform().GetLocation();
	const FVector BeforeWolf = EM.GetFragmentDataChecked<FTransformFragment>(Wolf).GetTransform().GetLocation();
	const TArray<UMassProcessor*> Pipeline = {NewObject<UEcoNeighborhoodGatherProcessor>(Scoped.World),
		NewObject<UEcoPerceptionProcessor>(Scoped.World), NewObject<UEcoPolicyProcessor>(Scoped.World), NewObject<UEcoSteeringProcessor>(Scoped.World)};
	for (auto* P : Pipeline) { P->CallInitialize(Scoped.World, EM.AsShared()); }
	for (int32 Step = 0; Step <= EcoBehaviorConfig::PolicyInterval; ++Step)
	{
		for (auto* P : Pipeline) { EcoTest::RunProcessor(*P, EM, 0.1f); }
		Scoped.World->TimeSeconds += 0.1f; Demo->Tick(0.1f);
	}
	TestFalse(TEXT("Existing herbivore PPO/steering actually changes position"),
		EM.GetFragmentDataChecked<FTransformFragment>(Herb).GetTransform().GetLocation().Equals(BeforeHerb));
	TestFalse(TEXT("Existing predator rule writer actually changes position"),
		EM.GetFragmentDataChecked<FTransformFragment>(Wolf).GetTransform().GetLocation().Equals(BeforeWolf));
	int32 BoundBlueprints = 0;
	for (TActorIterator<AEcoCreatureRepresentationActor> It(Scoped.World); It; ++It)
	{
		BoundBlueprints += It->bBound && (It->GetClass() == WolfClass || It->GetClass() == HerbClass) ? 1 : 0;
		if (It->bBound && It->VisualState.StableAgentId == HerbId)
		{
			TestTrue(TEXT("Representation follows the resulting Mass position"), It->GetActorLocation().Equals(
				EM.GetFragmentDataChecked<FTransformFragment>(Herb).GetTransform().GetLocation()));
		}
	}
	TestEqual(TEXT("Actual species Blueprint instances are bound to logical creatures"), BoundBlueprints, 3);
	Demo->RebuildVisuals(); TestEqual(TEXT("Rebuild replaces rather than duplicates visuals"), Demo->GetRepresentedCreatureCount(), 3);
	EM.DestroyEntity(Herb); Demo->Tick(0.016f);
	TestEqual(TEXT("Deleted logical owner removes its visual"), Demo->GetRepresentedCreatureCount(), 2);
	// This helper world does not run the engine game loop; exercise the teardown callback explicitly.
	Demo->EndPlay(EEndPlayReason::Destroyed); Demo->Destroy();
	TestFalse(TEXT("Spawner EndPlay removes its surviving logical entities"), EM.IsEntityValid(Wolf));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoAnatomicalFacingTest, "AdaptiveEcosystem.Creature.Visual.ImportedAnatomyFacingAndReversals",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoAnatomicalFacingTest::RunTest(const FString&)
{
	EcoTest::FScopedTestWorld W;
	for (const FString Kind : {TEXT("Deer"), TEXT("Wolf")})
	{
		UClass* BP = LoadClass<AEcoCreatureRepresentationActor>(nullptr, *(TEXT("/Game/Creatures/Integrated/BP_Eco") + Kind + TEXT(".BP_Eco") + Kind + TEXT("_C")));
		if (!TestNotNull(TEXT("Saved animal BP"), BP)) return false;
		auto* Visual = W.World->SpawnActor<AEcoCreatureRepresentationActor>(BP);
		if (!TestNotNull(TEXT("Imported mesh"), Visual->VisualMesh.Get())) return false;
		const FReferenceSkeleton& Skeleton = Visual->VisualMesh->GetRefSkeleton();
		// Derive anatomy independently from authored MeshForwardAxis, so a wrong
		// asset correction cannot pass by comparing the same setting to itself.
		const FString BonePrefix = Kind == TEXT("Wolf") ? TEXT("Wolf_-") : TEXT("STAG_-");
		const int32 Head = Skeleton.FindBoneIndex(FName(*(BonePrefix + TEXT("Head"))));
		const int32 Pelvis = Skeleton.FindBoneIndex(FName(*(BonePrefix + TEXT("Pelvis"))));
		if (!TestTrue(TEXT("Anatomical reference bones exist"), Head != INDEX_NONE && Pelvis != INDEX_NONE)) return false;
		TArray<FTransform> ComponentPose = Skeleton.GetRefBonePose();
		for (int32 I = 1; I < ComponentPose.Num(); ++I)
			if (Skeleton.GetParentIndex(I) != INDEX_NONE) ComponentPose[I] = ComponentPose[I] * ComponentPose[Skeleton.GetParentIndex(I)];
		const FVector AnatomicalForward = (ComponentPose[Head].GetLocation() - ComponentPose[Pelvis].GetLocation()).GetSafeNormal2D();
		Visual->BindIdentity(50, Visual->VisualSpeciesId);
		FEcoCreatureVisualState State; State.StableAgentId = 50; State.SpeciesId = Visual->VisualSpeciesId;
		for (const float Yaw : {0.f, 180.f, 90.f, -90.f, 45.f, -135.f, 179.f, -179.f})
		{
			State.Sequence++; State.WorldTime += 0.016; State.Velocity = FRotator(0, Yaw, 0).Vector() * 900;
			State.Position += State.Velocity * 0.016;
			TestTrue(TEXT("Directional snapshot accepted"), Visual->ConsumeVisualState(State, 0.016f));
			const FVector WorldAnatomy = Visual->CreatureMesh->GetComponentTransform().TransformVectorNoScale(AnatomicalForward).GetSafeNormal2D();
			TestTrue(TEXT("Real head/pelvis face motion within 10 degrees, including reversals and yaw wrap"),
				FVector::DotProduct(WorldAnatomy, State.Velocity.GetSafeNormal2D()) >= FMath::Cos(FMath::DegreesToRadians(10.1f)));
			TestTrue(TEXT("Calibrated diagnostic agrees with independent anatomy"), FVector::DotProduct(WorldAnatomy, Visual->GetVisualForwardDirection()) > 0.999);
		}
		const FRotator LastFacing = Visual->GetActorRotation();
		State.Sequence++; State.Velocity = FVector::ZeroVector; Visual->ConsumeVisualState(State, 0.016f);
		TestTrue(TEXT("Stopping keeps last facing and clears turn input"), Visual->GetActorRotation().Equals(LastFacing) && Visual->VisualTurnAmount == 0);
		State.Sequence++; State.Velocity = FVector(0, 900, 0); State.bDiscontinuity = true;
		Visual->ConsumeVisualState(State, 0.016f);
		TestTrue(TEXT("Discontinuity snaps without a spurious turn animation"), Visual->GetActorRotation().Equals(FRotator(0, 90, 0)) && Visual->VisualTurnAmount == 0);
		State.Sequence++; State.bDiscontinuity = false; State.Velocity = FVector(-900, 0, 0);
		Visual->ConsumeVisualState(State, 0);
		TestTrue(TEXT("Zero delta is finite and clears rate input"), FMath::IsFinite(Visual->DirectionDegrees) && Visual->VisualTurnAmount == 0);
		State.Sequence++; State.bAlive = false; Visual->ConsumeVisualState(State, 0.016f);
		TestTrue(TEXT("Death clears locomotion turn input"), Visual->VisualTurnAmount == 0 && Visual->DirectionDegrees == 0 && Visual->GetVelocity().IsZero());
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoTurningInputTest, "AdaptiveEcosystem.Creature.Visual.SignedTurnAndAssetFallback",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoTurningInputTest::RunTest(const FString&)
{
	EcoTest::FScopedTestWorld W;
	auto* Visual = W.World->SpawnActor<AEcoWolfRepresentation>();
	Visual->MaxFacingLagDegrees = 0;
	for (const float Yaw : {90.f, -90.f})
	{
		Visual->ClearBinding(); Visual->BindIdentity(77, TEXT("Wolf"));
		FEcoCreatureVisualState S; S.StableAgentId = 77; S.SpeciesId = TEXT("Wolf"); S.Sequence = 1; S.Velocity = FVector(300, 0, 0);
		Visual->ConsumeVisualState(S, 0.1f);
		S.Sequence++; S.Velocity = FRotator(0, Yaw, 0).Vector() * 300; Visual->ConsumeVisualState(S, 0.1f);
		TestTrue(TEXT("UE positive yaw selects right, negative selects left; normalized and bounded"),
			Visual->VisualTurnAmount * Yaw > 0 && FMath::Abs(Visual->VisualTurnAmount) <= 1);
		for (int32 I = 0; I < 10; ++I) { S.Sequence++; Visual->ConsumeVisualState(S, 0.1f); }
		TestTrue(TEXT("Straight motion decays to the central sample"), FMath::Abs(Visual->VisualTurnAmount) < 0.001);
	}
	for (const FString Kind : {TEXT("Deer"), TEXT("Wolf")})
	{
		const FString Path = TEXT("/Game/Creatures/Integrated/BS_Eco") + Kind + TEXT("_Turning.BS_Eco") + Kind + TEXT("_Turning");
		auto* BS = LoadObject<UBlendSpace>(nullptr, *Path);
		if (!TestNotNull(TEXT("Saved turning BS"), BS)) return false;
		for (const auto& Sample : BS->GetBlendSamples())
		{
			if (Sample.SampleValue.X == 300 && Sample.SampleValue.Y != 0)
				TestTrue(TEXT("Walk turns use actual left/right clips"), Sample.Animation->GetName().EndsWith(Sample.SampleValue.Y < 0 ? TEXT("WalkTurnL") : TEXT("WalkTurnR")));
			if (Sample.SampleValue.X == 900 && Sample.SampleValue.Y != 0)
				TestTrue(TEXT("Wolf uses run turn clips; deer explicitly falls back to straight run"),
					Sample.Animation->GetName().EndsWith(Kind == TEXT("Deer") ? TEXT("_Run") : Sample.SampleValue.Y < 0 ? TEXT("RunTurnL") : TEXT("RunTurnR")));
		}
	}
	return true;
}
#endif
