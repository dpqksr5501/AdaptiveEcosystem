#include "Creature/Runtime/EcoCreatureNetworkTrait.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "AI/Policy/EcoBehaviorTraits.h"
#include "AI/Social/EcoSocialTrait.h"
#include "Mass/EcoMassFragments.h"
#include "MassEntityTemplateRegistry.h"
#include "MassEntityUtils.h"
#include "MassCommonUtils.h"
#include "MassMovementFragments.h"
#include "Engine/World.h"

void UEcoCreatureNetworkTrait::BuildTemplate(FMassEntityTemplateBuildContext& Context, const UWorld& World) const
{
	Super::BuildTemplate(Context, World);
	Context.AddTag<FEcoIntegratedCreatureTag>();
	Context.AddFragment<FEcoCreaturePresentationFragment>();
	if (World.GetNetMode() == NM_Client && !Context.IsInspectingData()) return;
	// Custom movement excludes engine ApplyMovement; the PPO/predator writers are disjoint by species.
	Context.AddTag<FMassCustomMovementTag>();
	Context.AddFragment<FEcoCreatureLifecycleFragment>();
	FMassEntityManager& Manager = UE::Mass::Utils::GetEntityManagerChecked(World);
	FEcoSpeciesSharedFragment Species;
	Species.BaseMoveSpeed = EcoBehaviorConfig::HerbSpeedCmS;
	Species.ViewDistance = EcoBehaviorConfig::SeeRadiusCm;
	Species.FOV = EcoBehaviorConfig::FovDeg;
	Context.AddSharedFragment(Manager.GetOrCreateSharedFragment(Species));
	if (bPredator)
	{
		GetDefault<UEcoPredatorTrait>()->BuildTemplate(Context, World);
	}
	else
	{
		GetDefault<UEcoHerbivoreTrait>()->BuildTemplate(Context, World);
		GetDefault<UEcoSocialTrait>()->BuildTemplate(Context, World);
	}
}

#if WITH_EDITOR
void UEcoCreatureEntityConfig::ConfigureCreature(bool bPredator)
{
	Modify();
	auto* Trait = CastChecked<UEcoCreatureNetworkTrait>(AddTrait(UEcoCreatureNetworkTrait::StaticClass()));
	Trait->bPredator = bPredator;
	MarkPackageDirty();
}
#endif
