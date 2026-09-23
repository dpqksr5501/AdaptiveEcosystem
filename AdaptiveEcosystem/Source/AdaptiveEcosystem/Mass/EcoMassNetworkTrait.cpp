// Copyright Epic Games, Inc. All Rights Reserved.

#include "Mass/EcoMassNetworkTrait.h"

#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassCommonFragments.h"
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
	Super::BuildTemplate(BuildContext, World);

	BuildContext.AddFragment<FTransformFragment>();
	BuildContext.AddFragment<FEcoIdentityFragment>();
	BuildContext.AddFragment<FEcoRegionFragment>();

	if (BuildContext.IsInspectingData())
	{
		BuildContext.AddFragment<FEcoVitalsFragment>();
		BuildContext.AddTag<FEcoAliveTag>();
		BuildContext.AddTag<FEcoAuthorityTag>();
		BuildContext.AddTag<FEcoClientProxyTag>();
	}
	else if (World.GetNetMode() == NM_Client)
	{
		BuildContext.AddTag<FEcoClientProxyTag>();
	}
	else
	{
		BuildContext.AddFragment<FEcoVitalsFragment>();
		BuildContext.AddTag<FEcoAliveTag>();
		BuildContext.AddTag<FEcoAuthorityTag>();
	}
}
