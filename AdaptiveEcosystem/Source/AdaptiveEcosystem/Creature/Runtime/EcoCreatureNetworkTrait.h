#pragma once

#include "Mass/EcoMassNetworkTrait.h"
#include "MassEntityConfigAsset.h"
#include "EcoCreatureNetworkTrait.generated.h"

/** One complete, role-aware template for this opt-in vertical slice. */
UCLASS(EditInlineNew, meta=(DisplayName="Eco Integrated Creature"))
class ADAPTIVEECOSYSTEM_API UEcoCreatureNetworkTrait : public UEcoMassNetworkTrait
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere, Category="Creature") bool bPredator = false;
	virtual void BuildTemplate(FMassEntityTemplateBuildContext& Context, const UWorld& World) const override;
};

/** Editor tool supplies the complete trait; asset GUID remains the template's network identity. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoCreatureEntityConfig : public UMassEntityConfigAsset
{
	GENERATED_BODY()
public:
#if WITH_EDITOR
	UFUNCTION(CallInEditor, BlueprintCallable, Category="Creature") void ConfigureCreature(bool bPredator);
#endif
};
