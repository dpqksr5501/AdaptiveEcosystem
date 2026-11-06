// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AbilitySystemInterface.h"
#include "Logging/LogMacros.h"
#include "AdaptiveEcosystemCharacter.generated.h"

class USpringArmComponent;
class UCameraComponent;
class UInputAction;
class UEcoAbilityAvatarComponent;
class UEcoPlayerCombatComponent;
class UEcoMeleeHitComponent;
class UEcoEquipmentComponent;
class UEcoAimComponent;
class UEcoWeaponFireComponent;
class UEcoCombatRelevanceComponent;
class UEcoGASDamageReceiverComponent;
struct FInputActionValue;

DECLARE_LOG_CATEGORY_EXTERN(LogTemplateCharacter, Log, All);

/**
 *  A simple player-controllable third person character
 *  Implements a controllable orbiting camera
 */
UCLASS(abstract)
class AAdaptiveEcosystemCharacter : public ACharacter, public IAbilitySystemInterface
{
	GENERATED_BODY()

	/** Camera boom positioning the camera behind the character */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	USpringArmComponent* CameraBoom;

	/** Follow camera */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UCameraComponent* FollowCamera;
	
protected:

	/** Jump Input Action */
	UPROPERTY(EditAnywhere, Category="Input")
	UInputAction* JumpAction;

	/** Move Input Action */
	UPROPERTY(EditAnywhere, Category="Input")
	UInputAction* MoveAction;

	/** Look Input Action */
	UPROPERTY(EditAnywhere, Category="Input")
	UInputAction* LookAction;

	/** Mouse Look Input Action */
	UPROPERTY(EditAnywhere, Category="Input")
	UInputAction* MouseLookAction;

public:

	/** Constructor */
	AAdaptiveEcosystemCharacter();
    UAbilitySystemComponent* GetAbilitySystemComponent() const override;
    void PossessedBy(AController* NewController) override;
    void UnPossessed() override;
    void OnRep_PlayerState() override;
    void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UPROPERTY(VisibleAnywhere, Category="Abilities")
    TObjectPtr<UEcoAbilityAvatarComponent> AbilityAvatar;

    UPROPERTY(VisibleAnywhere, Category="Combat")
    TObjectPtr<UEcoPlayerCombatComponent> Combat;

    UPROPERTY(VisibleAnywhere, Category="Combat")
    TObjectPtr<UEcoMeleeHitComponent> MeleeHit;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat", meta=(AllowPrivateAccess="true")) TObjectPtr<UEcoEquipmentComponent> Equipment;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat", meta=(AllowPrivateAccess="true")) TObjectPtr<UEcoAimComponent> Aim;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat", meta=(AllowPrivateAccess="true")) TObjectPtr<UEcoWeaponFireComponent> WeaponFire;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat", meta=(AllowPrivateAccess="true")) TObjectPtr<UEcoCombatRelevanceComponent> CombatRelevance;
    UPROPERTY(VisibleAnywhere, Category="Combat") TObjectPtr<UEcoGASDamageReceiverComponent> DamageReceiver;
protected:

	/** Initialize input action bindings */
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

protected:

	/** Called for movement input */
	void Move(const FInputActionValue& Value);

	/** Called for looking input */
	void Look(const FInputActionValue& Value);

public:

	/** Handles move inputs from either controls or UI interfaces */
	UFUNCTION(BlueprintCallable, Category="Input")
	virtual void DoMove(float Right, float Forward);

	/** Handles look inputs from either controls or UI interfaces */
	UFUNCTION(BlueprintCallable, Category="Input")
	virtual void DoLook(float Yaw, float Pitch);

	/** Handles jump pressed inputs from either controls or UI interfaces */
	UFUNCTION(BlueprintCallable, Category="Input")
	virtual void DoJumpStart();

	/** Handles jump pressed inputs from either controls or UI interfaces */
	UFUNCTION(BlueprintCallable, Category="Input")
	virtual void DoJumpEnd();

public:

	/** Returns CameraBoom subobject **/
	FORCEINLINE class USpringArmComponent* GetCameraBoom() const { return CameraBoom; }

	/** Returns FollowCamera subobject **/
	FORCEINLINE class UCameraComponent* GetFollowCamera() const { return FollowCamera; }
};

