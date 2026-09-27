// Copyright Epic Games, Inc. All Rights Reserved.


#include "AdaptiveEcosystemPlayerController.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "InputMappingContext.h"
#include "Blueprint/UserWidget.h"
#include "AdaptiveEcosystem.h"
#include "Network/EcoGameState.h"
#include "Widgets/Input/SVirtualJoystick.h"

AEcoGameState* AAdaptiveEcosystemPlayerController::GetEcoGameState() const
{
	return GetWorld() ? GetWorld()->GetGameState<AEcoGameState>() : nullptr;
}

void AAdaptiveEcosystemPlayerController::BeginPlay()
{
	Super::BeginPlay();

	// only spawn touch controls on local player controllers
	if (IsLocalPlayerController() && ShouldUseTouchControls())
	{
		// spawn the mobile controls widget
		MobileControlsWidget = CreateWidget<UUserWidget>(this, MobileControlsWidgetClass);

		if (MobileControlsWidget)
		{
			// add the controls to the player screen
			MobileControlsWidget->AddToPlayerScreen(0);

		} else {

			UE_LOG(LogAdaptiveEcosystem, Error, TEXT("Could not spawn mobile controls widget."));

		}

	}
}

void AAdaptiveEcosystemPlayerController::BeginPlayingState()
{
	Super::BeginPlayingState();

	if (const AEcoGameState* EcoGameState = GetEcoGameState())
	{
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("Player entered world epoch %d (phase %d, Mass ready: %s)."),
			EcoGameState->GetWorldEpoch(),
			static_cast<int32>(EcoGameState->GetWorldPhase()),
			EcoGameState->IsMassReplicationReady() ? TEXT("true") : TEXT("false"));
	}
}

void AAdaptiveEcosystemPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	// only add IMCs for local player controllers
	if (IsLocalPlayerController())
	{
		// Add Input Mapping Contexts
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
		{
			for (UInputMappingContext* CurrentContext : DefaultMappingContexts)
			{
				Subsystem->AddMappingContext(CurrentContext, 0);
			}

			// only add these IMCs if we're not using mobile touch input
			if (!ShouldUseTouchControls())
			{
				for (UInputMappingContext* CurrentContext : MobileExcludedMappingContexts)
				{
					Subsystem->AddMappingContext(CurrentContext, 0);
				}
			}
		}
	}
}

bool AAdaptiveEcosystemPlayerController::ShouldUseTouchControls() const
{
	// are we on a mobile platform? Should we force touch?
	return SVirtualJoystick::ShouldDisplayTouchInterface() || bForceTouchControls;
}
