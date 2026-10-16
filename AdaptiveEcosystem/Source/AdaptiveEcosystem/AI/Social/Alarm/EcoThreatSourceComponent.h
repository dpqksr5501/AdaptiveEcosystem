#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "EcoThreatSourceComponent.generated.h"

/** Opt-in Social threat for a real player pawn or predator actor. No movement or attack logic. */
UCLASS(ClassGroup = (Ecology), meta = (BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoThreatSourceComponent : public UActorComponent
{
	GENERATED_BODY()
public:
	UEcoThreatSourceComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Social|Threat")
	bool bThreatEnabled = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Social|Threat", meta = (ClampMin = "0", ClampMax = "1"))
	float ThreatStrength = 1.0f;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
};
