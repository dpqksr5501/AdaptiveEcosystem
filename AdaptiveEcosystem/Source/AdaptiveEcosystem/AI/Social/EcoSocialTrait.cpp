// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/EcoSocialTrait.h"
#include "MassEntityTemplateRegistry.h"
#include "MassEntityUtils.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"

void UEcoSocialTrait::BuildTemplate(FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const
{
	if (World.GetNetMode() == NM_Client && !BuildContext.IsInspectingData())
	{
		return;
	}
	// Social consumes these contracts; the owning traits must supply them.
	BuildContext.RequireFragment<FEcoIdentityFragment>();
	BuildContext.RequireFragment<FTransformFragment>();
	BuildContext.RequireFragment<FMassVelocityFragment>();
	BuildContext.RequireFragment<FEcoPolicyOutputFragment>();
	BuildContext.AddFragment<FEcoHerdMemberFragment>();
	BuildContext.AddFragment<FEcoAlarmStateFragment>();
	BuildContext.AddFragment<FEcoShelterIntentFragment>();
	BuildContext.AddFragment<FEcoSocialBehaviorFragment>();

	FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(World);
	const FSharedStruct SharedConfig = EntityManager.GetOrCreateSharedFragment(SocialConfig);
	BuildContext.AddSharedFragment(SharedConfig);
}
