// Copyright Epic Games, Inc. All Rights Reserved.

#include "Mass/EcoMassNetworkTrait.h"

#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EcoMassPresentationFragments.h"
#include "Core/EcoRuntimeSettings.h"
#include "AdaptiveEcosystem.h"
#include "MassCommonFragments.h"
#include "MassMovementFragments.h"
#include "MassEntityTemplateRegistry.h"
#include "Network/Mass/EcoMassClientBubble.h"
#include "Network/Mass/EcoMassReplicator.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(EcoMassNetworkTrait)

UEcoMassNetworkTrait::UEcoMassNetworkTrait()
{
	Params.BubbleInfoClass = AEcoMassClientBubbleInfo::StaticClass();
	Params.ReplicatorClass = UEcoMassReplicator::StaticClass();
}

void UEcoMassNetworkTrait::BuildTemplate(FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const
{
	FString Error;
	if (!ValidateNetworkSettings(Error))
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("Eco network template rejected: %s (%s)"), *Error, *GetPathName());
		return;
	}
	Super::BuildTemplate(BuildContext, World);

	BuildContext.AddFragment<FTransformFragment>();
	BuildContext.AddFragment<FEcoIdentityFragment>();
	BuildContext.AddFragment<FEcoRegionFragment>();

	if (BuildContext.IsInspectingData())
	{
		BuildContext.AddFragment<FEcoClientPresentationFragment>();
		BuildContext.AddFragment<FEcoMovementDiscontinuityFragment>();
		BuildContext.AddFragment<FEcoVitalsRuntimeFragment>();
		BuildContext.AddFragment<FEcoDeathFragment>();
		BuildContext.AddFragment<FEcoVitalsFragment>();
		BuildContext.AddFragment<FEcoTravelFragment>();
		BuildContext.AddFragment<FEcoLifetimeFragment>();
		BuildContext.AddFragment<FEcoFeedingFragment>();
		BuildContext.AddFragment<FMassVelocityFragment>();
		BuildContext.AddFragment<FMassDesiredMovementFragment>();
		BuildContext.AddTag<FMassCodeDrivenMovementTag>();
		BuildContext.AddTag<FEcoAliveTag>();
		BuildContext.AddTag<FEcoAuthorityTag>();
		BuildContext.AddTag<FEcoClientProxyTag>();
	}
	else if (World.GetNetMode() == NM_Client)
	{
		BuildContext.AddFragment<FEcoClientPresentationFragment>();
		BuildContext.AddTag<FEcoClientProxyTag>();
	}
	else
	{
		BuildContext.AddFragment<FEcoMovementDiscontinuityFragment>();
		BuildContext.AddFragment<FEcoVitalsRuntimeFragment>();
		BuildContext.AddFragment<FEcoDeathFragment>();
		BuildContext.AddFragment<FEcoVitalsFragment>();
		BuildContext.AddFragment<FEcoTravelFragment>();
		BuildContext.AddFragment<FEcoLifetimeFragment>();
		BuildContext.AddFragment<FEcoFeedingFragment>();
		BuildContext.AddFragment<FMassVelocityFragment>();
		BuildContext.AddFragment<FMassDesiredMovementFragment>();
		BuildContext.AddTag<FMassCodeDrivenMovementTag>();
		BuildContext.AddTag<FEcoAliveTag>();
		BuildContext.AddTag<FEcoAuthorityTag>();
	}
}

void UEcoMassNetworkTrait::ApplyM4ExperimentalPreset()
{
	Modify();
	EcoMassNetwork::ApplyExperimentalPreset(Params);
}

bool UEcoMassNetworkTrait::ValidateNetworkSettings(FString& OutError) const
{
	if (!EcoMassNetwork::ValidateParameters(Params, OutError)) return false;
	if (Params.BubbleInfoClass != AEcoMassClientBubbleInfo::StaticClass()
		|| Params.ReplicatorClass != UEcoMassReplicator::StaticClass())
	{
		OutError = TEXT("Eco Network Agent requires the Eco Bubble and Eco Replicator classes.");
		return false;
	}
	if (!GetDefault<UEcoRuntimeSettings>()->ConnectionBudget.IsValid())
	{
		OutError = TEXT("Invalid M4 connection budget: actors/adds must fit the positive relevant-agent budget.");
		return false;
	}
	return true;
}
