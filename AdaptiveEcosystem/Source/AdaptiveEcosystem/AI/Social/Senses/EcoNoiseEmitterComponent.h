#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "EcoNoiseEmitterComponent.generated.h"

class USoundBase;
class USoundAttenuation;

/** Opt-in gameplay noise bridge. No audio assets, RPC or movement ownership required. */
UCLASS(ClassGroup=(Ecology), meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoNoiseEmitterComponent : public UActorComponent
{
	GENERATED_BODY()
public:
	UEcoNoiseEmitterComponent();
	/** Enable for a first running-noise demo; use animation/gameplay notifies for precise footsteps. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ecology|Senses")
	bool bEmitMovementNoise = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ecology|Senses", meta=(ClampMin="0"))
	float MinimumSpeed = 250.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ecology|Senses", meta=(ClampMin="0.2"))
	float MovementNoiseInterval = 0.4f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ecology|Senses", meta=(ClampMin="0", ClampMax="1"))
	float MovementLoudness = 0.8f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ecology|Senses", meta=(ClampMin="0", ClampMax="10000"))
	float MovementNoiseRange = 2000.0f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ecology|Senses", meta=(ClampMin="0", ClampMax="1"))
	float MovementThreatStrength = 0.6f;
	/** Optional presentation assets. Attenuation affects rendered audio, not AI hearing. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ecology|Senses|Audio")
	TObjectPtr<USoundBase> NoiseSound;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ecology|Senses|Audio")
	TObjectPtr<USoundAttenuation> AudioAttenuation;
	/** Call on the appropriate local presentation path; does not replicate or emit AI noise. */
	UFUNCTION(BlueprintCallable, Category="Ecology|Senses|Audio")
	bool PlayNoiseSound(float VolumeMultiplier = 1.0f);
	UFUNCTION(BlueprintCallable, Category="Ecology|Senses")
	int64 EmitNoise(float Loudness, float MaxRange, float ThreatStrength, FName Tag);
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
private:
	float TimeUntilNoise = 0;
};
