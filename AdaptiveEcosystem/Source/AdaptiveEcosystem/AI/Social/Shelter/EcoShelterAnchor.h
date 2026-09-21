// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "EcoShelterAnchor.generated.h"

class USceneComponent;
class UArrowComponent;

/**
 * Level authoring anchor designating physical shelter / refuge locations.
 * Automatically registers with UEcoShelterSubsystem on BeginPlay.
 */
UCLASS(BlueprintType, Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoShelterAnchor : public AActor
{
	GENERATED_BODY()

public:
	AEcoShelterAnchor();

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

public:
	/** Maximum number of simultaneous occupants this shelter can hold */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Shelter", meta = (ClampMin = "1", ClampMax = "16"))
	int32 Capacity = 2;

	/** Shelter defense / obscurity quality rating (0.0 .. 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Shelter", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Quality = 1.0f;

	/** Effective refuge radius around the anchor point */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Shelter", meta = (ClampMin = "50.0"))
	float Radius = 300.0f;

	/** Assigned runtime index in UEcoShelterSubsystem */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Shelter")
	int32 ShelterRuntimeIndex = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|Shelter")
	TObjectPtr<USceneComponent> SceneRoot;

#if WITH_EDITORONLY_DATA
	/** Visual indicator of defensive facing direction */
	UPROPERTY(VisibleAnywhere, Category = "Ecology|Shelter")
	TObjectPtr<UArrowComponent> FacingArrow;
#endif
};
