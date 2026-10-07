#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoNoiseSubsystem.generated.h"

/** A short-lived, immutable emission snapshot. Audio playback is not its authority. */
struct FEcoNoiseEvent
{
	int64 Id = 0;
	double EmittedAt = 0;
	FVector Position = FVector::ZeroVector;
	float Loudness = 0;
	float MaxRange = 0;
	float ThreatStrength = 0;
	FName Tag;
	TWeakObjectPtr<AActor> Instigator;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoNoiseSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()
public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Deinitialize() override;
	/** Server gameplay calls this once per sound-producing action. 0 means rejected. */
	UFUNCTION(BlueprintCallable, Category="Ecology|Senses")
	int64 ReportNoise(FVector Position, float Loudness, float MaxRange, float ThreatStrength,
		AActor* Instigator, FName Tag);
	void GatherRecent(TArray<FEcoNoiseEvent>& Out);
	static constexpr int32 MaxEvents = 128;
	static constexpr double EventLifetime = 0.6;
private:
	void Prune(double Now);
	int64 NextId = 1;
	TArray<FEcoNoiseEvent> Events;
};
