// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassEntityTraitBase.h"
#include "AI/Social/EcoSocialFragments.h"
#include "EcoSocialTrait.generated.h"

/**
 * Trait that attaches Social Behavior fragments (Herd, Alarm, Shelter, and Social Behavior) to Mass Entity templates.
 */
UCLASS(meta = (DisplayName = "Eco Social Trait"))
class ADAPTIVEECOSYSTEM_API UEcoSocialTrait : public UMassEntityTraitBase
{
	GENERATED_BODY()

public:
	/** Species-wide social parameters attached as shared fragment */
	UPROPERTY(EditAnywhere, Category = "Social")
	FEcoSocialSpeciesSharedFragment SocialConfig;

	virtual void BuildTemplate(FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const override;
};
