// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Alarm/EcoAlarmProcessors.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/Herd/EcoHerdProcessors.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassCommonTypes.h"
#include "MassExecutionContext.h"
#include "Engine/World.h"

// -----------------------------------------------------------------------------
// UEcoAlarmPropagationProcessor
// -----------------------------------------------------------------------------

UEcoAlarmPropagationProcessor::UEcoAlarmPropagationProcessor()
	: EntityQuery(*this)
{
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(UEcoHerdAggregateProcessor::StaticClass()->GetFName());
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true; // Ensures GameThread serialized access for HerdSubsystem
}

void UEcoAlarmPropagationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddSharedRequirement<FEcoSocialSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoAlarmPropagationProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World)
	{
		return;
	}

	UEcoHerdSubsystem* HerdSubsystem = World->GetSubsystem<UEcoHerdSubsystem>();
	const float DeltaTime = Context.GetDeltaTimeSeconds();

	// Step 1: GameThread serialized decay of herd-level alarms
	if (HerdSubsystem)
	{
		HerdSubsystem->DecayHerdAlarms(DeltaTime, 0.2f);
	}

	const UEcoHerdSubsystem* ConstHerdSubsystem = HerdSubsystem;

	// Step 2: Per-agent alarm propagation, distance attenuation, and state transition
	EntityQuery.ForEachEntityChunk(Context, [ConstHerdSubsystem, DeltaTime](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoIdentityFragment> IdentityList = ChunkContext.GetFragmentView<FEcoIdentityFragment>();
		TConstArrayView<FEcoHerdMemberFragment> MemberList = ChunkContext.GetFragmentView<FEcoHerdMemberFragment>();
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetMutableFragmentView<FEcoAlarmStateFragment>();
		const FEcoSocialSpeciesSharedFragment& SocialConfig = ChunkContext.GetSharedFragment<FEcoSocialSpeciesSharedFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			FEcoAlarmStateFragment& Alarm = AlarmList[i];
			const FVector AgentLocation = TransformList[i].GetTransform().GetLocation();
			const int32 HerdIndex = MemberList[i].HerdRuntimeIndex;

			// 1. Continuous time-based decay of individual alarm intensity
			if (Alarm.AlarmStrength > 0.0f)
			{
				Alarm.AlarmStrength = FMath::Max(0.0f, Alarm.AlarmStrength - SocialConfig.AlarmTimeDecay * DeltaTime);
			}

			// 2. Synchronize threat signals from herd aggregate if available
			if (ConstHerdSubsystem && HerdIndex != INDEX_NONE_ECO)
			{
				FEcoHerdRuntimeData HerdData;
				if (ConstHerdSubsystem->GetHerdData(HerdIndex, HerdData) && HerdData.AlarmStrength > 0.0f)
				{
					// Distance-attenuated reception from herd's threat center
					const float DistToThreat = FVector::Dist(AgentLocation, HerdData.LastThreatPosition);
					const float DistanceAttenuation = FMath::Exp(-SocialConfig.AlarmDistanceDecay * DistToThreat);
					const float ReceivedStrength = HerdData.AlarmStrength * DistanceAttenuation;

					if (ReceivedStrength > Alarm.AlarmStrength)
					{
						Alarm.AlarmStrength = FMath::Clamp(ReceivedStrength, 0.0f, 1.0f);
						Alarm.LastThreatPosition = HerdData.LastThreatPosition;
					}
				}
			}

			// 3. Social state machine transition based on normalized intensity
			if (Alarm.AlarmStrength >= SocialConfig.PanicThreshold)
			{
				Alarm.State = EEcoSocialState::Panic;
			}
			else if (Alarm.AlarmStrength >= SocialConfig.AlertThreshold)
			{
				Alarm.State = EEcoSocialState::Alert;
			}
			else if (Alarm.AlarmStrength > 0.0f)
			{
				// Transition to Recovering when cooling down from Panic/Alert, or Regrouping if scattered
				Alarm.State = (Alarm.State == EEcoSocialState::Panic || Alarm.State == EEcoSocialState::Alert || Alarm.State == EEcoSocialState::Recovering)
					? EEcoSocialState::Recovering
					: EEcoSocialState::Regrouping;
			}
			else
			{
				Alarm.State = EEcoSocialState::Calm;
			}
		}
	});
}

// -----------------------------------------------------------------------------
// UEcoSocialResponseProcessor
// -----------------------------------------------------------------------------

UEcoSocialResponseProcessor::UEcoSocialResponseProcessor()
	: EntityQuery(*this)
{
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(UEcoAlarmPropagationProcessor::StaticClass()->GetFName());
	bAutoRegisterWithProcessingPhases = true;
}

void UEcoSocialResponseProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoSocialBehaviorFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoSocialResponseProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	EntityQuery.ForEachEntityChunk(Context, [](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetFragmentView<FEcoAlarmStateFragment>();
		TConstArrayView<FEcoPolicyOutputFragment> PolicyOutputList = ChunkContext.GetFragmentView<FEcoPolicyOutputFragment>();
		TArrayView<FEcoSocialBehaviorFragment> SocialBehaviorList = ChunkContext.GetMutableFragmentView<FEcoSocialBehaviorFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			const FEcoAlarmStateFragment& Alarm = AlarmList[i];
			const FEcoPolicyActionV1& RawAction = PolicyOutputList[i].Action;
			FEcoSocialBehaviorFragment& SocialBehavior = SocialBehaviorList[i];

			// Start from the pure, uncorrupted PPO raw action
			FEcoPolicyActionV1 Modulated = RawAction;
			float CohesionMultiplier = 1.0f;

			switch (Alarm.State)
			{
			case EEcoSocialState::Panic:
				// Extreme danger: suppress foraging, boost flee sensitivity and cover intention
				Modulated.Forage = FMath::Clamp(RawAction.Forage * 0.05f, 0.0f, 1.0f);
				Modulated.FleeDist = FMath::Clamp(RawAction.FleeDist + 0.5f * Alarm.AlarmStrength, 0.0f, 1.0f);
				Modulated.Cover = FMath::Clamp(RawAction.Cover + 0.6f * Alarm.AlarmStrength, 0.0f, 1.0f);
				CohesionMultiplier = 1.5f;
				Modulated.Cohesion = FMath::Clamp(RawAction.Cohesion * CohesionMultiplier, 0.0f, 1.0f);
				break;

			case EEcoSocialState::Alert:
				// Mild danger: moderate foraging suppression, increase cohesion and readiness
				Modulated.Forage = FMath::Clamp(RawAction.Forage * 0.4f, 0.0f, 1.0f);
				Modulated.FleeDist = FMath::Clamp(RawAction.FleeDist + 0.25f, 0.0f, 1.0f);
				Modulated.Cover = FMath::Clamp(RawAction.Cover + 0.2f, 0.0f, 1.0f);
				CohesionMultiplier = 1.25f;
				Modulated.Cohesion = FMath::Clamp(RawAction.Cohesion * CohesionMultiplier, 0.0f, 1.0f);
				break;

			case EEcoSocialState::Recovering:
			case EEcoSocialState::Regrouping:
				// Calming down: strong cohesion to reassemble the herd before resuming full foraging
				CohesionMultiplier = 1.35f;
				Modulated.Cohesion = FMath::Clamp(RawAction.Cohesion * CohesionMultiplier, 0.0f, 1.0f);
				Modulated.Forage = FMath::Clamp(RawAction.Forage * 0.7f, 0.0f, 1.0f);
				break;

			case EEcoSocialState::Calm:
			default:
				// Undisturbed: retain authentic PPO inference weights unmodified
				CohesionMultiplier = 1.0f;
				break;
			}

			SocialBehavior.ModulatedAction = Modulated;
			SocialBehavior.SocialCohesionMultiplier = CohesionMultiplier;
		}
	});
}
