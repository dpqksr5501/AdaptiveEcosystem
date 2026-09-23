// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassReplicationTrait.h"
#include "EcoMassNetworkTrait.generated.h"

/**
 * Adds the shared network contract to an ecological Mass entity config.
 * The same config asset must be loaded on server and client so its template ID
 * can be used to create client-side proxy entities.
 */
UCLASS(BlueprintType, EditInlineNew, CollapseCategories, meta = (DisplayName = "Eco Network Agent"))
class ADAPTIVEECOSYSTEM_API UEcoMassNetworkTrait : public UMassReplicationTrait
{
	GENERATED_BODY()

public:
	UEcoMassNetworkTrait();

	virtual void BuildTemplate(FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const override;
};
