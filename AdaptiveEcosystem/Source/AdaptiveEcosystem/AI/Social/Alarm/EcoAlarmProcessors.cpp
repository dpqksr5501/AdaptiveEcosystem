// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Alarm/EcoAlarmProcessors.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
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
	bAutoRegisterWithProcessingPhases = true;
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

	const UEcoHerdSubsystem* HerdSubsystem = World->GetSubsystem<UEcoHerdSubsystem>();
	const float DeltaTime = Context.GetDeltaTimeSeconds();

	EntityQuery.ForEachEntityChunk(Context, [HerdSubsystem, DeltaTime](FMassExecutionContext& ChunkContext)
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

			// 1. Continuous time-based decay of alarm intensity
			if (Alarm.AlarmStrength > 0.0f)
			{
				Alarm.AlarmStrength = FMath::Max(0.0f, Alarm.AlarmStrength - SocialConfig.AlarmTimeDecay * DeltaTime);
			}

			// 2. Synchronize threat signals from herd aggregate if available
			if (HerdSubsystem && HerdIndex != INDEX_NONE_ECO)
			{
				FEcoHerdRuntimeData HerdData;
				if (HerdSubsystem->GetHerdData(HerdIndex, HerdData) && HerdData.AlarmStrength > 0.0f)
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
				// Recovering if previously alarmed, or regrouping if herd was scattered
				Alarm.State = (Alarm.State == EEcoSocialState::Panic || Alarm.State == EEcoSocialState::Alert)
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
	EntityQuery.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoSocialResponseProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	EntityQuery.ForEachEntityChunk(Context, [](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetFragmentView<FEcoAlarmStateFragment>();
		TArrayView<FEcoPolicyOutputFragment> PolicyOutputList = ChunkContext.GetMutableFragmentView<FEcoPolicyOutputFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			const FEcoAlarmStateFragment& Alarm = AlarmList[i];
			FEcoPolicyActionV1& Action = PolicyOutputList[i].Action;

			switch (Alarm.State)
			{
			case EEcoSocialState::Panic:
				// Extreme danger: suppress foraging, boost flee sensitivity and cover intention
				Action.Forage = FMath::Clamp(Action.Forage * 0.05f, 0.0f, 1.0f);
				Action.FleeDist = FMath::Clamp(Action.FleeDist + 0.5f * Alarm.AlarmStrength, 0.0f, 1.0f);
				Action.Cover = FMath::Clamp(Action.Cover + 0.6f * Alarm.AlarmStrength, 0.0f, 1.0f);
				Action.Cohesion = FMath::Clamp(Action.Cohesion * 1.5f, 0.0f, 1.0f);
				break;

			case EEcoSocialState::Alert:
				// Mild danger: moderate foraging suppression, increase cohesion and readiness
				Action.Forage = FMath::Clamp(Action.Forage * 0.4f, 0.0f, 1.0f);
				Action.FleeDist = FMath::Clamp(Action.FleeDist + 0.25f, 0.0f, 1.0f);
				Action.Cohesion = FMath::Clamp(Action.Cohesion * 1.25f, 0.0f, 1.0f);
				Action.Cover = FMath::Clamp(Action.Cover + 0.2f, 0.0f, 1.0f);
				break;

			case EEcoSocialState::Recovering:
			case EEcoSocialState::Regrouping:
				// Calming down: strong cohesion to reassemble the herd before resuming full foraging
				Action.Cohesion = FMath::Clamp(Action.Cohesion * 1.35f, 0.0f, 1.0f);
				Action.Forage = FMath::Clamp(Action.Forage * 0.7f, 0.0f, 1.0f);
				break;

			case EEcoSocialState::Calm:
			default:
				// Undisturbed: retain authentic PPO inference weights unmodified
				break;
			}
		}
	});
}
