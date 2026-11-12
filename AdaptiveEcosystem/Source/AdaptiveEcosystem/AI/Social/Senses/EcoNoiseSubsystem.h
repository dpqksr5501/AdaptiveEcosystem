#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoNoiseSubsystem.generated.h"

namespace EcoNoise
{
    inline bool IsPlayerShot(FName Tag) { static const FName Shot(TEXT("Player.Shot")); return Tag == Shot; }
    inline bool IsPlayerThreat(FName Tag)
    {
        static const FName Footstep(TEXT("Player.Footstep"));
        return Tag == Footstep || IsPlayerShot(Tag);
    }
}

/** A short-lived, immutable emission snapshot. Audio playback is not its authority. */
struct FEcoNoiseEvent
{
	int64 Id = 0;
	int64 SourceAgentId = 0; // 0 for Actor-based emissions.
	FName SourceSpeciesId;
	FName RegionId;
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
	/** Logical Mass source: no representation Actor is required, including on dedicated servers. */
	int64 ReportCreatureFootstep(FVector Position, float Loudness, float MaxRange, float ThreatStrength,
		int64 StableAgentId, FName SpeciesId, FName RegionId = NAME_None);
	/** Presentation alarm emission; authority position and logical identity only. */
	int64 ReportCreatureAlarm(FVector Position,int64 StableAgentId,FName SpeciesId);
	static constexpr int32 MaxEvents = 128;
	static constexpr double EventLifetime = 0.6;
private:
    int64 Accept(FEcoNoiseEvent Event, bool bProfiledCreature);
	void Prune(double Now);
	int64 NextId = 1;
	TArray<FEcoNoiseEvent> Events;
    // Latest contact per creature, with separate capacity for player and alarm events.
    TMap<int64, FEcoNoiseEvent> ProfiledFootsteps;
};
