// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "AdaptiveEcosystemPlayerController.generated.h"

class UInputMappingContext;
class UUserWidget;
class AEcoGameState;

/**
 *  Basic PlayerController class for a third person game
 *  Manages input mappings
 */
UCLASS(Abstract)
class ADAPTIVEECOSYSTEM_API AAdaptiveEcosystemPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	/** Read-only access to the replicated authority summary. */
	UFUNCTION(BlueprintPure, Category = "Ecology|Match")
	AEcoGameState* GetEcoGameState() const;
	
protected:

	/** Input Mapping Contexts */
	UPROPERTY(EditAnywhere, Category ="Input|Input Mappings")
	TArray<UInputMappingContext*> DefaultMappingContexts;

	/** Input Mapping Contexts */
	UPROPERTY(EditAnywhere, Category="Input|Input Mappings")
	TArray<UInputMappingContext*> MobileExcludedMappingContexts;

	/** Mobile controls widget to spawn */
	UPROPERTY(EditAnywhere, Category="Input|Touch Controls")
	TSubclassOf<UUserWidget> MobileControlsWidgetClass;

	/** Pointer to the mobile controls widget */
	UPROPERTY()
	TObjectPtr<UUserWidget> MobileControlsWidget;

	/** If true, the player will use UMG touch controls even if not playing on mobile platforms */
	UPROPERTY(EditAnywhere, Config, Category = "Input|Touch Controls")
	bool bForceTouchControls = false;

	/** Gameplay initialization */
	virtual void BeginPlay() override;
	virtual void BeginPlayingState() override;

	/** Input mapping context setup */
	virtual void SetupInputComponent() override;

	/** Returns true if the player should use UMG touch controls */
	bool ShouldUseTouchControls() const;

};
