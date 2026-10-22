#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureNetworkTrait.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Senses/EcoPredatorPerception.h"
#include "Mass/EcoMassNetworkSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassPresentationFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassSpringMovementFragments.h"
#include "MassEntityTemplate.h"
#include "Engine/World.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "MassStateTreeFragments.h"
#include "MassNavMeshNavigationFragments.h"
#include "MassSimulationLOD.h"
#include "MassNavigationProcessors.h"
#include "NavigationSystem.h"
#include "AI/Policy/EcoCreatureV3Trait.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"

bool AEcoCreatureIntegrationSpawner::RegisterTemplates()
{
	const auto* Network = GetWorld()->GetSubsystem<UEcoMassNetworkSubsystem>();
	if (!Network || !Network->IsBubbleInfoClassRegistered()) return false;
	const bool bClient = GetNetMode() == NM_Client;
	// Register both immutable v3 proxy templates even when this client starts without the server's console switch.
	// Saved V1 templates remain registered below, so late joins can consume either server backend.
	if (bClient) for (bool bPredator : {false, true})
	{
		auto* Config = UEcoCreatureV3Trait::MakeNetworkConfig(bPredator);
		AdditionalClientConfigs.AddUnique(Config);
		if (!Config->GetOrCreateEntityTemplate(*GetWorld()).IsValid()) return false;
	}
	for (int32 ConfigRoleIndex = 0; ConfigRoleIndex < 2; ++ConfigRoleIndex)
	{
		if (!IsSpeciesEnabled(ConfigRoleIndex == 1)) continue;
		UMassEntityConfigAsset* Config = ConfigRoleIndex == 0 ? HerbivoreConfig.Get() : WolfConfig.Get();
		const auto* Trait = Config ? Cast<UEcoCreatureNetworkTrait>(Config->FindTrait(UEcoCreatureNetworkTrait::StaticClass())) : nullptr;
		FString NetworkError;
		if (!Trait || Trait->bPredator != (ConfigRoleIndex == 1) || !Trait->ValidateNetworkSettings(NetworkError))
		{
			UE_LOG(LogTemp, Error, TEXT("[Eco Setup] Invalid %s Config=%s. Expected Eco Integrated Creature Predator=%d. %s"),
				ConfigRoleIndex == 0 ? TEXT("Herbivore") : TEXT("Wolf"), *GetPathNameSafe(Config), ConfigRoleIndex, *NetworkError);
			return false;
		}
		const auto& Template = Config->GetOrCreateEntityTemplate(*GetWorld());
		if (!Template.IsValid()) return false;
		const auto& Composition = Template.GetCompositionDescriptor();
		const bool bV3 = Trait->IsA<UEcoCreatureV3Trait>();
		TArray<FString> Problems;
		const auto Require = [&Composition, &Problems]<typename T>()
		{ if (!Composition.Contains<T>()) Problems.Add(TEXT("Missing ") + T::StaticStruct()->GetName()); };
		const auto Forbid = [&Composition, &Problems]<typename T>()
		{ if (Composition.Contains<T>()) Problems.Add(TEXT("Forbidden ") + T::StaticStruct()->GetName()); };
		Require.operator()<FEcoIdentityFragment>(); Require.operator()<FEcoRegionFragment>();
		Require.operator()<FTransformFragment>(); Require.operator()<FEcoIntegratedCreatureTag>();
		Require.operator()<FEcoCreaturePresentationFragment>();
		if (bClient)
		{
			Require.operator()<FEcoClientProxyTag>(); Require.operator()<FEcoClientPresentationFragment>();
			Forbid.operator()<FEcoAuthorityTag>(); Forbid.operator()<FEcoAliveTag>();
			Forbid.operator()<FEcoVitalsFragment>(); Forbid.operator()<FEcoVitalsRuntimeFragment>();
			Forbid.operator()<FEcoDeathFragment>(); Forbid.operator()<FEcoTravelFragment>();
			Forbid.operator()<FEcoFeedingFragment>(); Forbid.operator()<FEcoCreatureSurvivalFragment>();
			Forbid.operator()<FEcoLifetimeFragment>(); Forbid.operator()<FEcoMovementDiscontinuityFragment>();
			Forbid.operator()<FMassVelocityFragment>(); Forbid.operator()<FMassDesiredMovementFragment>();
			Forbid.operator()<FEcoCreatureLifecycleFragment>(); Forbid.operator()<FEcoCreatureFootstepFragment>();
			Forbid.operator()<FEcoObservationFragment>(); Forbid.operator()<FEcoSteeringGeometryFragment>();
			Forbid.operator()<FEcoPreySenseFragment>(); Forbid.operator()<FEcoPredatorStateFragment>();
			Forbid.operator()<FEcoPolicyOutputFragment>(); Forbid.operator()<FEcoPolicyRuntimeFragment>();
			Forbid.operator()<FEcoSocialBehaviorFragment>(); Forbid.operator()<FEcoSocialMovementRequestFragment>();
			Forbid.operator()<FEcoHerbivoreTag>(); Forbid.operator()<FEcoPredatorTag>();
		}
		else
		{
			Forbid.operator()<FEcoClientProxyTag>();
			Forbid.operator()<FSpringMovementSettings>();
			Require.operator()<FEcoAuthorityTag>(); Require.operator()<FEcoAliveTag>();
			Require.operator()<FMassCustomMovementTag>(); Require.operator()<FMassVelocityFragment>();
			Require.operator()<FMassDesiredMovementFragment>(); Require.operator()<FEcoMovementDiscontinuityFragment>();
			Require.operator()<FEcoVitalsFragment>(); Require.operator()<FEcoVitalsRuntimeFragment>();
			Require.operator()<FEcoDeathFragment>(); Require.operator()<FEcoTravelFragment>();
			Require.operator()<FEcoLifetimeFragment>(); Require.operator()<FEcoFeedingFragment>();
			Require.operator()<FEcoCreatureSurvivalFragment>(); Require.operator()<FEcoCreatureLifecycleFragment>();
			Require.operator()<FEcoCreatureFootstepFragment>(); Require.operator()<FEcoSpeciesSharedFragment>();
			if (bV3)
			{
				Require.operator()<FEcoIntegratedV3Fragment>();
				Forbid.operator()<FEcoHerbivoreTag>(); Forbid.operator()<FEcoPredatorTag>();
				Forbid.operator()<FEcoStateTreeBehaviorTag>(); Forbid.operator()<FEcoGroundedNavigationTag>();
				if (ConfigRoleIndex == 0)
				{ Require.operator()<FEcoIntegratedPolicyV3Tag>(); Require.operator()<FEcoHerbivoreBodyV3Fragment>(); Require.operator()<FEcoBehaviorStateFragment>(); }
				else { Require.operator()<FEcoIntegratedThreatV3Tag>(); Require.operator()<FEcoThreatStateFragment>(); }
			}
			else if (ConfigRoleIndex == 0)
			{
				Require.operator()<FEcoHerbivoreTag>(); Forbid.operator()<FEcoPredatorTag>();
				Require.operator()<FEcoSteeringGeometryFragment>(); Require.operator()<FEcoObservationFragment>();
				Require.operator()<FEcoPolicyOutputFragment>(); Require.operator()<FEcoPolicyRuntimeFragment>();
				Require.operator()<FEcoSocialMovementRequestFragment>(); Require.operator()<FEcoShelterMovementFeedbackFragment>();
			}
			else
			{
				Require.operator()<FEcoPredatorTag>(); Forbid.operator()<FEcoHerbivoreTag>();
				Require.operator()<FEcoPredatorStateFragment>(); Require.operator()<FEcoPreySenseFragment>();
				Require.operator()<FEcoSensoryProfileFragment>(); Require.operator()<FEcoPredatorSensesSharedFragment>();
			}
		}
		if (!Problems.IsEmpty())
		{
			UE_LOG(LogTemp, Error, TEXT("[Eco Setup] Invalid base creature composition: %s"), *FString::Join(Problems, TEXT(", ")));
			return false;
		}
		if (bClient)
		{
			Forbid.operator()<FEcoStateTreeBehaviorTag>(); Forbid.operator()<FEcoGroundedNavigationTag>();
			Forbid.operator()<FEcoSpeciesAIInputFragment>(); Forbid.operator()<FMassStateTreeInstanceFragment>();
			Forbid.operator()<FEcoSpeciesAIDecisionFragment>(); Forbid.operator()<FEcoSpeciesAIExecutionFragment>();
			Forbid.operator()<FEcoSpeciesAIMoveFragment>(); Forbid.operator()<FEcoSpeciesAIAttackFragment>();
			Forbid.operator()<FEcoSpeciesAIFeedingFragment>(); Forbid.operator()<FEcoSpeciesAISharedFragment>();
		}
		else if (Trait->bUseSpeciesAI)
		{
			FString ProfileError;
			if (!Trait->SpeciesAIProfile || Trait->SpeciesAIProfile->bPredator != (ConfigRoleIndex == 1)
				|| !Trait->SpeciesAIProfile->Validate(ProfileError)) Problems.Add(TEXT("SpeciesAIProfile: ") + ProfileError);
			Require.operator()<FEcoStateTreeBehaviorTag>(); Require.operator()<FEcoSpeciesAIInputFragment>();
			Require.operator()<FEcoSpeciesAIDecisionFragment>(); Require.operator()<FEcoSpeciesAISharedFragment>();
			Require.operator()<FMassStateTreeInstanceFragment>();
			if (Trait->SpeciesAIProfile && !Trait->SpeciesAIProfile->bPolicyOnly)
			{
				if(GetDefault<UMassNavigationSmoothHeightProcessor>()->ShouldAutoAddToGlobalList())
					Problems.Add(TEXT("Stock SmoothHeight still enabled: load DefaultMass.ini compatibility override before using grounded SpeciesAI."));
				const auto* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
				const auto& P=*Trait->SpeciesAIProfile;
				if(!Nav||!Nav->GetNavDataForProps(FNavAgentProperties(P.BodyRadius,P.BodyHeight)))
					Problems.Add(TEXT("Missing supported NavMesh for the SpeciesAI body radius/height. Build navigation before starting."));
				Require.operator()<FEcoGroundedNavigationTag>(); Require.operator()<FMassNavMeshShortPathFragment>();
				Require.operator()<FEcoSpeciesAIMoveFragment>(); Require.operator()<FEcoSpeciesAIFeedingFragment>();
				Forbid.operator()<FMassOffLODTag>();
			}
		}
		if (!Problems.IsEmpty())
		{
			UE_LOG(LogTemp, Error, TEXT("[Eco Setup] Template rejected before Entity spawn: Config=%s Mode=%d [%s]"),
				*Config->GetPathName(), int32(GetNetMode()), *FString::Join(Problems, TEXT(", ")));
			return false;
		}
		UE_LOG(LogTemp, Log, TEXT("[Eco Integration] Template=%s Config=%s NetMode=%d Role=%s Validated=1"),
			*Template.GetTemplateID().ToString(), *Config->GetPathName(), int32(GetNetMode()), ConfigRoleIndex == 0 ? TEXT("Herbivore") : TEXT("Wolf"));
	}
	return true;
}
