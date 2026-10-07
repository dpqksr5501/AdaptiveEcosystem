// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Alarm/EcoAlarmProcessors.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/Herd/EcoHerdProcessors.h"
#include "AI/Social/Alarm/EcoThreatDetectionProcessor.h"
#include "AI/Policy/EcoBehaviorProcessors.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassCommonTypes.h"
#include "MassExecutionContext.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogEcoSocialActionAudit, Log, All);
static TAutoConsoleVariable<int32> CVarEcoSocialActionAudit(TEXT("eco.Social.ActionAudit"), 0,
	TEXT("Log Raw/Effective Social action comparisons every 5 game seconds (server/standalone)."));

// -----------------------------------------------------------------------------
// UEcoAlarmPropagationProcessor
// -----------------------------------------------------------------------------

UEcoAlarmPropagationProcessor::UEcoAlarmPropagationProcessor()
	: EntityQuery(*this)
{
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionFlags = int32(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ExecutionOrder.ExecuteAfter.Add(UEcoHerdAggregateProcessor::StaticClass()->GetFName());
	ExecutionOrder.ExecuteAfter.Add(UEcoThreatDetectionProcessor::StaticClass()->GetFName());
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true; // Ensures GameThread serialized access for HerdSubsystem
}

void UEcoAlarmPropagationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoSensoryStateFragment>(EMassFragmentAccess::ReadWrite, EMassFragmentPresence::Optional);
	EntityQuery.AddSharedRequirement<FEcoSocialSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoAlarmPropagationProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World || World->GetNetMode() == NM_Client)
	{
		return;
	}

	UEcoHerdSubsystem* HerdSubsystem = World->GetSubsystem<UEcoHerdSubsystem>();
	const float DeltaTime = FMath::IsFinite(Context.GetDeltaTimeSeconds()) ? FMath::Max(0.0f, Context.GetDeltaTimeSeconds()) : 0.0f;

	// Step 1: GameThread serialized decay of herd-level alarms
	if (HerdSubsystem)
	{
		HerdSubsystem->DecayHerdAlarms(DeltaTime, 0.2f);
	}

	const UEcoHerdSubsystem* ConstHerdSubsystem = HerdSubsystem;
	const double Now = World->GetTimeSeconds();

	// Step 2: Per-agent alarm propagation, distance attenuation, and state transition
	EntityQuery.ForEachEntityChunk(Context, [ConstHerdSubsystem, DeltaTime, Now](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoHerdMemberFragment> MemberList = ChunkContext.GetFragmentView<FEcoHerdMemberFragment>();
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetMutableFragmentView<FEcoAlarmStateFragment>();
		auto Senses = ChunkContext.GetMutableFragmentView<FEcoSensoryStateFragment>();
		const FEcoSocialSpeciesSharedFragment& SocialConfig = ChunkContext.GetSharedFragment<FEcoSocialSpeciesSharedFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			FEcoAlarmStateFragment& Alarm = AlarmList[i];
			if (!Senses.IsEmpty()) { Senses[i].ClearSharedInformation(); }
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
					if (!Senses.IsEmpty())
					{
						Senses[i].ReceiveSharedInformation(HerdData.LastThreatPosition, ReceivedStrength,
							HerdData.PersistentHerdId, HerdData.LastThreatEvidenceTime, Now);
					}

					Alarm.AlarmStrength = FMath::Clamp(FMath::Max(ReceivedStrength, Alarm.AlarmStrength), 0.0f, 1.0f);
					// Keep memory strength, but always track the currently selected live threat.
					// Otherwise a moving/weaker source leaves shelter scoring tied to an old position.
					Alarm.LastThreatPosition = HerdData.LastThreatPosition;
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
				Alarm.LastThreatPosition = FVector::ZeroVector;
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
	ExecutionFlags = int32(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ExecutionOrder.ExecuteAfter.Add(UEcoAlarmPropagationProcessor::StaticClass()->GetFName());
	ExecutionOrder.ExecuteAfter.Add(UEcoPolicyProcessor::StaticClass()->GetFName());
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true; // Diagnostic throttle and World time are serialized.
}

void UEcoSocialResponseProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoSocialBehaviorFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoSocialResponseProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World || World->GetNetMode() == NM_Client) { return; }
	const double Now = World->GetTimeSeconds();
	const bool bLog = CVarEcoSocialActionAudit.GetValueOnGameThread() > 0;
	if (!bLog) { NextActionAuditLogTime = 0.0; }
	const bool bWriteSummary = bLog && Now >= NextActionAuditLogTime;
	int32 Matched = 0, Adjusted = 0, Invalid = 0;
	FString Sample;
	bool bSampleAdjusted = false;
	EntityQuery.ForEachEntityChunk(Context, [&](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetFragmentView<FEcoAlarmStateFragment>();
		TConstArrayView<FEcoPolicyOutputFragment> PolicyOutputList = ChunkContext.GetFragmentView<FEcoPolicyOutputFragment>();
		TArrayView<FEcoSocialBehaviorFragment> SocialBehaviorList = ChunkContext.GetMutableFragmentView<FEcoSocialBehaviorFragment>();
		const auto Ids = ChunkContext.GetFragmentView<FEcoIdentityFragment>();

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
			SocialBehavior.ActionAudit.Record(RawAction, Modulated, Alarm.State, Now);
			if (bWriteSummary)
			{
				++Matched;
				const auto& Audit = SocialBehavior.ActionAudit;
				Invalid += Audit.bValid ? 0 : 1;
				const bool bChanged = Audit.bValid && Audit.MaxAbsoluteDelta > KINDA_SMALL_NUMBER;
				Adjusted += bChanged ? 1 : 0;
				if (Sample.IsEmpty() || (bChanged && !bSampleAdjusted))
				{
					bSampleAdjusted = bChanged;
					Sample = FString::Printf(TEXT("Agent=%lld State=%d Changed=%d Raw=[%.3f %.3f %.3f %.3f] Effective=[%.3f %.3f %.3f %.3f] MaxDelta=%.3f"),
						Ids.IsEmpty() ? int64(0) : Ids[i].StableAgentId, int32(Alarm.State), int32(bChanged),
						RawAction.Forage, RawAction.Cohesion, RawAction.FleeDist, RawAction.Cover,
						Modulated.Forage, Modulated.Cohesion, Modulated.FleeDist, Modulated.Cover, Audit.MaxAbsoluteDelta);
				}
			}
		}
	});
	if (bWriteSummary)
	{
		UE_LOG(LogEcoSocialActionAudit, Log, TEXT("[SocialAction] World=%s Time=%.2f Matched=%d Adjusted=%d Invalid=%d %s"),
			*GetNameSafe(World), Now, Matched, Adjusted, Invalid, *Sample);
		NextActionAuditLogTime = Now + 5.0;
	}
}
