// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/EcoSocialTrait.h"
#include "MassEntityTemplateRegistry.h"
#include "MassEntityUtils.h"
#include "Engine/World.h"

void UEcoSocialTrait::BuildTemplate(FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const
{
	BuildContext.AddFragment<FEcoHerdMemberFragment>();
	BuildContext.AddFragment<FEcoAlarmStateFragment>();
	BuildContext.AddFragment<FEcoShelterIntentFragment>();
	BuildContext.AddFragment<FEcoSocialBehaviorFragment>();

	FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(World);
	const FSharedStruct SharedConfig = EntityManager.GetOrCreateSharedFragment(SocialConfig);
	BuildContext.AddSharedFragment(SharedConfig);
}
