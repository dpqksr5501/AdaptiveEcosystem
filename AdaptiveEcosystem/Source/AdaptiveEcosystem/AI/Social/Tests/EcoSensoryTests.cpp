#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "AI/Policy/Tests/EcoTestWorld.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoBehaviorProcessors.h"
#include "AI/Social/Alarm/EcoThreatDetectionProcessor.h"
#include "AI/Social/Alarm/EcoAlarmProcessors.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "AI/Social/Senses/EcoNoiseEmitterComponent.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassEntitySubsystem.h"
#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "GameFramework/Actor.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcoWorldClockSubsystem.h"

namespace EcoSensoryTests
{
	struct FFixture
	{
		EcoTest::FScopedTestWorld Scoped;
		FMassEntityManager& EM;
		UEcoHerdSubsystem& Herds;
		UEcoNoiseSubsystem& Noise;
		int32 HerdIndex;
		FMassEntityHandle Observer;
		UEcoNeighborhoodGatherProcessor* Gather;
		UEcoThreatDetectionProcessor* Detect;
		UEcoAlarmPropagationProcessor* Propagate;

		FFixture() : EM(Scoped.World->GetSubsystem<UMassEntitySubsystem>()->GetMutableEntityManager()),
			Herds(*Scoped.World->GetSubsystem<UEcoHerdSubsystem>()),
			Noise(*Scoped.World->GetSubsystem<UEcoNoiseSubsystem>()), HerdIndex(Herds.AllocateHerd(0, FVector::ZeroVector))
		{
			const TArray<const UScriptStruct*> Composition = {FTransformFragment::StaticStruct(), FMassVelocityFragment::StaticStruct(),
				FEcoIdentityFragment::StaticStruct(), FEcoHerdMemberFragment::StaticStruct(), FEcoAlarmStateFragment::StaticStruct(),
				FEcoSensoryStateFragment::StaticStruct(), FEcoSensoryProfileFragment::StaticStruct(), FEcoVitalsFragment::StaticStruct(),
				FEcoRegionFragment::StaticStruct(), FEcoAliveTag::StaticStruct()};
			FEcoSocialSpeciesSharedFragment Social;
			Social.Senses.NightVisionMultiplier = 0.5f;
			Social.Senses.RainVisionMultiplier = 0.5f;
			FMassArchetypeSharedFragmentValues Shared;
			Shared.Add(EM.GetOrCreateSharedFragment(Social));
			Shared.Add(EM.GetOrCreateSharedFragment(FEcoSpeciesSharedFragment()));
			Shared.Sort();
			TArray<FMassEntityHandle> Entities;
			EM.BatchCreateEntities(EM.CreateArchetype(Composition), Shared, 1, Entities);
			Observer = Entities[0];
			EM.GetFragmentDataChecked<FEcoIdentityFragment>(Observer).StableAgentId = 456;
			EM.GetFragmentDataChecked<FEcoHerdMemberFragment>(Observer).HerdRuntimeIndex = HerdIndex;
			Gather = NewObject<UEcoNeighborhoodGatherProcessor>(Scoped.World);
			Detect = NewObject<UEcoThreatDetectionProcessor>(Scoped.World);
			Propagate = NewObject<UEcoAlarmPropagationProcessor>(Scoped.World);
			for (UMassProcessor* P : TArray<UMassProcessor*>{Gather, Detect, Propagate}) { P->CallInitialize(Scoped.World, EM.AsShared()); }
		}
		void Scan(double Seconds = 0.2)
		{
			Scoped.World->TimeSeconds += Seconds;
			EcoTest::RunProcessor(*Gather, EM, Seconds);
			EcoTest::RunProcessor(*Detect, EM, Seconds);
		}
		void Alarm() { EcoTest::RunProcessor(*Propagate, EM, 0.016f); }
		FEcoSensoryStateFragment& State() { return EM.GetFragmentDataChecked<FEcoSensoryStateFragment>(Observer); }
		const FEcoHerdRuntimeData& Herd() { return Herds.GetActiveHerds()[HerdIndex]; }
		void Position(FMassEntityHandle E, FVector P) { EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(P); }
		FMassEntityHandle Predator(FVector P)
		{
			const TArray<const UScriptStruct*> Composition = {FTransformFragment::StaticStruct(), FMassVelocityFragment::StaticStruct(),
				FEcoPredatorTag::StaticStruct(), FEcoVitalsFragment::StaticStruct()};
			const auto E = EM.CreateEntity(EM.CreateArchetype(Composition)); Position(E, P); return E;
		}
		AActor* Wall(FVector P)
		{
			AActor* A = Scoped.World->SpawnActor<AActor>();
			UBoxComponent* Box = NewObject<UBoxComponent>(A);
			A->SetRootComponent(Box); Box->SetBoxExtent(FVector(10, 200, 200));
			Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly); Box->SetCollisionResponseToAllChannels(ECR_Block);
			Box->RegisterComponent(); A->SetActorLocation(P); return A;
		}
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSensoryMemoryTest, "AdaptiveEcosystem.Social.Senses.SightLossAndReacquisition",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoSensoryMemoryTest::RunTest(const FString& Parameters)
{
	using namespace EcoSensoryTests; FFixture F;
	const auto Predator = F.Predator(FVector(300, 0, 0));
	F.Scan();
	TestTrue(TEXT("Direct sight has exact position and full confidence"), F.State().Source == EEcoSenseSource::Sight
		&& F.State().Confidence == 1 && F.State().UncertaintyRadius == 0);
	F.Position(Predator, FVector(-300, 0, 0)); F.Scan();
	TestTrue(TEXT("Hidden moving threat retains last observed position, not true location"),
		F.State().Source == EEcoSenseSource::Memory && F.State().LastKnownPosition.Equals(FVector(300, 0, 0))
		&& F.State().Confidence < 1 && F.State().UncertaintyRadius > 0 && !F.State().bSensedThisScan);
	TestEqual(TEXT("Memory does not re-emit the herd alarm"), F.Herd().AlarmStrength, 0.0f);
	F.Position(Predator, FVector(400, 0, 0)); F.Scan();
	TestTrue(TEXT("Reacquisition replaces stale position"), F.State().Source == EEcoSenseSource::Sight
		&& F.State().LastKnownPosition.Equals(FVector(400, 0, 0)) && F.State().Confidence == 1);
	F.EM.DestroyEntity(Predator); F.Scan(7);
	TestTrue(TEXT("Memory expires after world-time lifetime"), F.State().Source == EEcoSenseSource::None);
	F.Predator(FVector(300, 0, 0)); F.Scan();
	F.EM.GetFragmentDataChecked<FEcoVitalsFragment>(F.Observer).HP = 0; F.Scan();
	TestTrue(TEXT("Dead observer forgets and cannot publish"), F.State().Source == EEcoSenseSource::None && F.Herd().AlarmStrength == 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSensoryHearingTest, "AdaptiveEcosystem.Social.Senses.HearingOcclusionAndOnceOnly",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoSensoryHearingTest::RunTest(const FString& Parameters)
{
	using namespace EcoSensoryTests; FFixture F;
	const FVector Emission(-300, 0, 0);
	const int64 Id = F.Noise.ReportNoise(Emission, 1, 2000, 1, nullptr, TEXT("Run"));
	F.Scan();
	TestTrue(TEXT("Hearing works behind FOV with uncertain position"), Id > 0 && F.State().Source == EEcoSenseSource::Hearing
		&& F.State().Confidence < 1 && F.State().UncertaintyRadius == 200 && F.Herd().AlarmStrength > 0);
	const float OpenConfidence = F.State().Confidence;
	const double ObservedAt = F.State().LastObservedTime;
	F.Scan();
	TestTrue(TEXT("Same live event cannot refresh memory or broadcast again"), F.State().Source == EEcoSenseSource::Memory
		&& F.State().LastObservedTime == ObservedAt && F.Herd().AlarmStrength == 0);
	F.Wall(FVector(-150, 0, 0));
	F.Scan(7); // Forget the earlier stronger evidence.
	F.Noise.ReportNoise(Emission, 1, 2000, 1, nullptr, TEXT("Run")); F.Scan();
	TestTrue(TEXT("Wall muffles rather than completely blocking hearing"), F.State().Source == EEcoSenseSource::Hearing
		&& F.State().Confidence > 0 && F.State().Confidence < OpenConfidence);
	F.Scan(7);
	F.Noise.ReportNoise(FVector(5000, 0, 0), 1, 2000, 1, nullptr, TEXT("Run")); F.Scan();
	TestTrue(TEXT("Out-of-range event cannot be heard"), F.State().Source == EEcoSenseSource::None);
	F.Position(F.Observer, FVector(5000, 0, 0)); F.Scan();
	TestTrue(TEXT("Entering later does not hear an already processed emission"), F.State().Source == EEcoSenseSource::None);
	F.Noise.ReportNoise(FVector(5000, 0, 0), 1, 2000, 0, nullptr, TEXT("Ambient")); F.Scan();
	TestEqual(TEXT("Ambient sound does not manufacture a threat alarm"), F.Herd().AlarmStrength, 0.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSensoryEnvironmentTest, "AdaptiveEcosystem.Social.Senses.EnvironmentAndProfile",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoSensoryEnvironmentTest::RunTest(const FString& Parameters)
{
	using namespace EcoSensoryTests; FFixture F;
	const auto Predator = F.Predator(FVector(900, 0, 0)); F.Scan();
	TestTrue(TEXT("Day default profile sees the source"), F.State().Source == EEcoSenseSource::Sight);
	auto* Clock = F.Scoped.World->GetSubsystem<UEcoWorldClockSubsystem>();
	TestTrue(TEXT("Authority clock starts"), Clock->StartClock(1, 10, 10));
	Clock->AdvanceClock(11); F.Scan();
	TestTrue(TEXT("Night range uses running authority clock"), F.State().Source == EEcoSenseSource::Memory);
	F.Position(Predator, FVector(700, 0, 0)); F.Scan();
	TestTrue(TEXT("Nearer threat is visible at night"), F.State().Source == EEcoSenseSource::Sight);
	auto* Region = F.Scoped.World->SpawnActor<AEcologyRegion>(); Region->RegionId = TEXT("SensoryRegion");
	Region->EnvironmentState.Rainfall = 1;
	F.Scoped.World->GetSubsystem<UEcologyWorldSubsystem>()->RegisterRegion(Region);
	F.EM.GetFragmentDataChecked<FEcoRegionFragment>(F.Observer).CurrentRegionId = Region->RegionId; F.Scan();
	TestTrue(TEXT("Regional rain scales vision"), F.State().Source == EEcoSenseSource::Memory);
	F.EM.GetFragmentDataChecked<FEcoSensoryProfileFragment>(F.Observer).VisionMultiplier = 2; F.Scan();
	TestTrue(TEXT("Per-agent profile changes perception, not policy weights"), F.State().Source == EEcoSenseSource::Sight);
	F.EM.GetFragmentDataChecked<FEcoSensoryProfileFragment>(F.Observer).VisionMultiplier = -1; F.Scan();
	TestTrue(TEXT("Invalid profile is rejected"), F.State().Source == EEcoSenseSource::None);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSensorySharedTest, "AdaptiveEcosystem.Social.Senses.SharedInformationIsNotDirectSight",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoSensorySharedTest::RunTest(const FString& Parameters)
{
	using namespace EcoSensoryTests; FFixture F;
	F.Herds.EmitHerdAlarm(F.HerdIndex, FVector(300, 0, 0), 1); F.Alarm();
	TestTrue(TEXT("Herd information is separate from personal knowledge"), F.State().SharedAlarmStrength > 0
		&& F.State().SharedThreatPosition.Equals(FVector(300, 0, 0)) && F.State().Source == EEcoSenseSource::None);
	F.Scan();
	TestEqual(TEXT("Received alarm never becomes a new observed input"), F.State().Confidence, 0.0f);
	F.Herds.ClearHerdAlarms(); F.Alarm();
	TestEqual(TEXT("Shared channel clears independently"), F.State().SharedAlarmStrength, 0.0f);
	F.EM.GetFragmentDataChecked<FEcoHerdMemberFragment>(F.Observer).HerdRuntimeIndex = INDEX_NONE;
	F.Predator(FVector(300, 0, 0)); F.Scan();
	TestTrue(TEXT("Unassigned individual can still perceive"), F.State().Source == EEcoSenseSource::Sight);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSensoryNoiseTest, "AdaptiveEcosystem.Social.Senses.NoiseLifecycleAndEmitter",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoSensoryNoiseTest::RunTest(const FString& Parameters)
{
	using namespace EcoSensoryTests; FFixture F;
	TestEqual(TEXT("Invalid noise rejected"), F.Noise.ReportNoise(FVector::ZeroVector, -1, 1000, 1, nullptr, NAME_None), int64(0));
	AActor* Actor = F.Scoped.World->SpawnActor<AActor>();
	auto* Root = NewObject<USceneComponent>(Actor); Actor->SetRootComponent(Root); Root->RegisterComponent();
	Actor->SetActorLocation(FVector(-200, 0, 0));
	auto* Emitter = NewObject<UEcoNoiseEmitterComponent>(Actor); Actor->AddInstanceComponent(Emitter);
	Emitter->RegisterComponent(); Emitter->Activate(true);
	TestTrue(TEXT("Component reports authoritative gameplay noise"), Emitter->EmitNoise(1, 2000, 1, TEXT("Run")) > 0);
	Actor->SetActorLocation(FVector(-900, 0, 0)); F.Scan();
	TestTrue(TEXT("Emission snapshot does not track a moving source"), F.State().LastKnownPosition.Equals(FVector(-200, 0, 0)));
	TestFalse(TEXT("Audio asset is optional for gameplay hearing"), Emitter->PlayNoiseSound());
	Emitter->Deactivate();
	TestEqual(TEXT("Inactive component cannot emit"), Emitter->EmitNoise(1, 2000, 1, NAME_None), int64(0));
	Actor->Destroy(); F.Scan(1);
	TArray<FEcoNoiseEvent> Events; F.Noise.GatherRecent(Events);
	TestEqual(TEXT("Expired events are removed"), Events.Num(), 0);
	for (int32 I = 0; I < UEcoNoiseSubsystem::MaxEvents; ++I) { F.Noise.ReportNoise(FVector::ZeroVector, 1, 1000, 1, nullptr, NAME_None); }
	TestEqual(TEXT("Queue rejects overflow without discarding accepted events"), F.Noise.ReportNoise(FVector::ZeroVector, 1, 1000, 1, nullptr, NAME_None), int64(0));
	F.Noise.GatherRecent(Events); TestEqual(TEXT("Queue size bounded"), Events.Num(), UEcoNoiseSubsystem::MaxEvents);
	F.Scan(1); F.Noise.GatherRecent(Events); TestEqual(TEXT("Queue recovers after expiry"), Events.Num(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSensoryReadContractTest, "AdaptiveEcosystem.Social.Senses.ReadSnapshotExpiryAndIsolation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoSensoryReadContractTest::RunTest(const FString& Parameters)
{
	FEcoSensoryStateFragment State;
	FEcoSensorySettings Settings;
	FEcoSensoryProfileFragment Profile;
	State.Observe(EEcoSenseSource::Hearing, FVector(100, 0, 0), 0.6f, 200.0f, 0.8f, 15, 1.0);
	State.ReceiveSharedInformation(FVector(-500, 0, 0), 0.9f, 42, 0.0, 1.0);
	const auto Fresh = State.MakeReadSnapshot(1.0, Settings, Profile, 42);
	TestTrue(TEXT("Direct evidence and received herd report retain separate positions and meanings"),
		Fresh.bValid && Fresh.bHasPersonalThreat && Fresh.bFreshDirectEvidence
		&& Fresh.PersonalSource == EEcoSenseSource::Hearing && Fresh.bHasSharedThreat
		&& Fresh.LastKnownPosition.Equals(FVector(100, 0, 0))
		&& Fresh.SharedReportedPosition.Equals(FVector(-500, 0, 0))
		&& Fresh.SharedEvidenceAgeSeconds == 1.0 && Fresh.SharedReceptionAgeSeconds == 0.0);
	const auto Later = State.MakeReadSnapshot(2.0, Settings, Profile, 42);
	TestTrue(TEXT("Reading between scans ages a copy and never follows the hidden source"),
		Later.bHasPersonalThreat && Later.PersonalSource == EEcoSenseSource::Memory
		&& Later.LastDirectSense == EEcoSenseSource::Hearing && !Later.bFreshDirectEvidence
		&& Later.Confidence < Fresh.Confidence && Later.UncertaintyRadiusCm > Fresh.UncertaintyRadiusCm
		&& Later.LastKnownPosition.Equals(Fresh.LastKnownPosition));
	TestTrue(TEXT("Snapshot read leaves authoritative memory unchanged"),
		State.Source == EEcoSenseSource::Hearing && State.Confidence == 0.6f
		&& State.UncertaintyRadius == 200.0f && State.LastObservedTime == 1.0);
	const auto Expired = State.MakeReadSnapshot(7.0, Settings, Profile, 42);
	TestTrue(TEXT("No detection pass is required for expired cues to disappear at read time"),
		Expired.bValid && !Expired.bHasPersonalThreat && !Expired.bHasSharedThreat
		&& Expired.LastKnownPosition.IsZero() && Expired.SharedReportedPosition.IsZero());
	TestFalse(TEXT("A herd report cannot be consumed after membership changes"),
		State.MakeReadSnapshot(2.0, Settings, Profile, 43).bHasSharedThreat);
	const auto Rewound = State.MakeReadSnapshot(0.5, Settings, Profile, 42);
	TestTrue(TEXT("Future personal/reception timestamps do not leak cues after a clock rewind"),
		Rewound.bValid && !Rewound.bHasPersonalThreat && !Rewound.bHasSharedThreat);
	Profile.MemoryMultiplier = 0.0f;
	TestFalse(TEXT("Malformed read settings produce an invalid contract"),
		State.MakeReadSnapshot(2.0, Settings, Profile, 42).bValid);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSharedEvidenceAgeTest, "AdaptiveEcosystem.Social.Senses.SharedEvidenceAgeAndHerdReuse",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoSharedEvidenceAgeTest::RunTest(const FString& Parameters)
{
	using namespace EcoSensoryTests; FFixture F;
	F.Herds.EmitHerdAlarm(F.HerdIndex, FVector(300, 0, 0), 1.0f); F.Alarm();
	const int64 HerdId = F.Herd().PersistentHerdId;
	const double EvidenceTime = F.State().SharedEvidenceWorldTime;
	F.Scoped.World->TimeSeconds += 1.0;
	F.Herds.EmitHerdAlarm(F.HerdIndex, FVector(900, 0, 0), 0.1f); // Weaker ignored input is not new selected evidence.
	F.Alarm();
	TestTrue(TEXT("Repeated reception and ignored weaker inputs never refresh selected evidence"),
		F.State().SharedEvidenceWorldTime == EvidenceTime
		&& F.State().SharedReceivedWorldTime == F.Scoped.World->GetTimeSeconds()
		&& F.State().SharedThreatPosition.Equals(FVector(300, 0, 0)));
	FEcoSensorySettings Settings; Settings.SharedInformationMaxAge = 0.5f;
	TestFalse(TEXT("Fresh reception cannot make old evidence fresh"),
		F.State().MakeReadSnapshot(F.Scoped.World->GetTimeSeconds(), Settings, FEcoSensoryProfileFragment(), HerdId).bHasSharedThreat);
	F.Herds.ReleaseHerd(F.HerdIndex);
	const int32 Reused = F.Herds.AllocateHerd(0, FVector::ZeroVector);
	TestEqual(TEXT("Runtime slot is reused for the test"), Reused, F.HerdIndex);
	const int64 NewId = F.Herds.GetActiveHerds()[Reused].PersistentHerdId;
	TestTrue(TEXT("Old report cannot belong to a new herd in the same slot"), NewId != HerdId
		&& !F.State().MakeReadSnapshot(1.0, FEcoSensorySettings(), FEcoSensoryProfileFragment(), NewId).bHasSharedThreat);
	F.Alarm();
	TestTrue(TEXT("No selected alarm clears all shared metadata without creating direct sight"),
		F.State().SharedPersistentHerdId == 0 && F.State().SharedEvidenceWorldTime == -1.0
		&& F.State().Source == EEcoSenseSource::None);
	F.Predator(FVector(300, 0, 0)); F.Scan(); F.Alarm();
	TestTrue(TEXT("New detected evidence is stamped and delivered with new persistent membership"),
		F.State().SharedPersistentHerdId == NewId
		&& F.State().SharedEvidenceWorldTime == F.Scoped.World->GetTimeSeconds());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSocialActionAuditTest, "AdaptiveEcosystem.Social.ActionAudit.RawPreservationAndNoCompounding",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoSocialActionAuditTest::RunTest(const FString& Parameters)
{
	EcoTest::FScopedTestWorld Scoped;
	auto& EM = Scoped.World->GetSubsystem<UMassEntitySubsystem>()->GetMutableEntityManager();
	const TArray<const UScriptStruct*> Composition = {FEcoAlarmStateFragment::StaticStruct(),
		FEcoHerdMemberFragment::StaticStruct(), FEcoPolicyOutputFragment::StaticStruct(),
		FEcoSocialBehaviorFragment::StaticStruct(), FEcoAliveTag::StaticStruct()};
	const auto Entity = EM.CreateEntity(EM.CreateArchetype(Composition));
	auto& Raw = EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(Entity).Action;
	Raw.Forage = 0.8f; Raw.Cohesion = 0.4f; Raw.FleeDist = 0.2f; Raw.Cover = 0.1f;
	auto& Alarm = EM.GetFragmentDataChecked<FEcoAlarmStateFragment>(Entity);
	Alarm.AlarmStrength = 0.8f;
	auto* Response = NewObject<UEcoSocialResponseProcessor>(Scoped.World);
	Response->CallInitialize(Scoped.World, EM.AsShared());
	const EEcoSocialState States[] = {EEcoSocialState::Calm, EEcoSocialState::Alert, EEcoSocialState::Panic,
		EEcoSocialState::Recovering, EEcoSocialState::Regrouping};
	const float Expected[][4] = {{0.8f, 0.4f, 0.2f, 0.1f}, {0.32f, 0.5f, 0.45f, 0.3f},
		{0.04f, 0.6f, 0.6f, 0.58f}, {0.56f, 0.54f, 0.2f, 0.1f}, {0.56f, 0.54f, 0.2f, 0.1f}};
	for (int32 S = 0; S < UE_ARRAY_COUNT(States); ++S)
	{
		Alarm.State = States[S];
		for (int32 Pass = 0; Pass < 2; ++Pass)
		{
			EcoTest::RunProcessor(*Response, EM, 0.016f);
			const auto& Behavior = EM.GetFragmentDataChecked<FEcoSocialBehaviorFragment>(Entity);
			const auto& Effective = Behavior.ModulatedAction;
			// Decimal reference values and float multiplies/adds can differ by one ULP.
			const float Error = FMath::Max(FMath::Max(FMath::Abs(Effective.Forage - Expected[S][0]),
				FMath::Abs(Effective.Cohesion - Expected[S][1])), FMath::Max(FMath::Abs(Effective.FleeDist - Expected[S][2]),
				FMath::Abs(Effective.Cover - Expected[S][3])));
			AddInfo(FString::Printf(TEXT("V1 compatibility State=%d Pass=%d MaxError=%.9g"), int32(States[S]), Pass, Error));
			TestTrue(TEXT("V1 actions are unchanged by diagnostics and never compound across passes"), Error <= 1.e-6f);
			TestTrue(TEXT("Policy raw output remains intact and audit identifies its applied rule"),
				Raw.Forage == 0.8f && Raw.Cohesion == 0.4f && Raw.FleeDist == 0.2f && Raw.Cover == 0.1f
				&& Behavior.ActionAudit.bValid && Behavior.ActionAudit.AppliedState == States[S]
				&& Behavior.ActionAudit.RawAction.Forage == Raw.Forage);
			TestTrue(TEXT("Audit distinguishes unchanged Calm and adjusted alert states"),
				S == 0 ? Behavior.ActionAudit.MaxAbsoluteDelta == 0.0f : Behavior.ActionAudit.MaxAbsoluteDelta > 0.0f);
		}
	}
	FEcoSocialActionAudit InvalidAudit;
	InvalidAudit.Record(Raw, Raw, EEcoSocialState::Calm, -1.0);
	TestFalse(TEXT("Invalid timestamps do not produce a valid audit"), InvalidAudit.bValid);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoCreatureFootstepHearingTest, "AdaptiveEcosystem.Social.Senses.LogicalFootstepsWithoutVisualActors",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoCreatureFootstepHearingTest::RunTest(const FString& Parameters)
{
	using namespace EcoSensoryTests; FFixture F;
	TestTrue(TEXT("Ambient herbivore footsteps accepted"), F.Noise.ReportCreatureFootstep(FVector(-200, 0, 0), 1, 2000, 0, 123, TEXT("Herbivore")) > 0);
	F.Scan(); TestTrue(TEXT("Friendly footstep is not a predator alarm"), F.State().Source == EEcoSenseSource::None);
	F.Noise.ReportCreatureFootstep(FVector(-200, 0, 0), 1, 2000, 1, 456, TEXT("Wolf"));
	F.Scan(); TestTrue(TEXT("Own stable agent noise excluded without an Actor"), F.State().Source == EEcoSenseSource::None);
	F.Noise.ReportCreatureFootstep(FVector(-200, 0, 0), 1, 2000, 0.8f, 789, TEXT("Wolf"));
	F.Scan(); F.Alarm();
	TestTrue(TEXT("Wolf behind FOV is heard with no audio or visual Actor"), F.State().Source == EEcoSenseSource::Hearing
		&& F.State().LastKnownPosition.Equals(FVector(-200, 0, 0)) && F.State().UncertaintyRadius > 0);
	TestTrue(TEXT("Fresh hearing feeds persistent herd alarm"), F.Herd().AlarmStrength > 0);
	TArray<FEcoNoiseEvent> Events; F.Noise.GatherRecent(Events);
	TestTrue(TEXT("Logical source metadata preserved"), Events.Last().SourceAgentId == 789 && Events.Last().SourceSpeciesId == TEXT("Wolf"));
	return true;
}

#endif
