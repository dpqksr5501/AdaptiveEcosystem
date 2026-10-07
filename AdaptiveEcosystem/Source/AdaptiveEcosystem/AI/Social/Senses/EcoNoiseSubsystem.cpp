#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

bool UEcoNoiseSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return Super::ShouldCreateSubsystem(Outer) && World && World->IsGameWorld() && World->GetNetMode() != NM_Client;
}

void UEcoNoiseSubsystem::Prune(double Now)
{
	Events.RemoveAll([Now](const FEcoNoiseEvent& Event) { return Now < Event.EmittedAt || Now - Event.EmittedAt >= EventLifetime; });
}

int64 UEcoNoiseSubsystem::ReportNoise(FVector Position, float Loudness, float MaxRange, float ThreatStrength,
	AActor* Instigator, FName Tag)
{
	UWorld* World = GetWorld();
	if (!IsInGameThread() || !World || !World->IsGameWorld() || World->GetNetMode() == NM_Client
		|| Position.ContainsNaN() || !FMath::IsFinite(Loudness) || Loudness <= 0 || Loudness > 1
		|| !FMath::IsFinite(MaxRange) || MaxRange <= 0 || MaxRange > 10000
		|| !FMath::IsFinite(ThreatStrength) || ThreatStrength < 0 || ThreatStrength > 1
		|| (Instigator && (!IsValid(Instigator) || Instigator->IsActorBeingDestroyed()
			|| Instigator->GetWorld() != World || !Instigator->HasAuthority())) || NextId == MAX_int64) { return 0; }
	const double Now = World->GetTimeSeconds();
	if (!FMath::IsFinite(Now) || Now < 0) { return 0; }
	Prune(Now);
	// Reject overflow rather than silently dropping already accepted stimuli.
	if (Events.Num() >= MaxEvents) { return 0; }
	FEcoNoiseEvent& Event = Events.AddDefaulted_GetRef();
	Event.Id = NextId++;
	Event.EmittedAt = Now;
	Event.Position = Position;
	Event.Loudness = Loudness;
	Event.MaxRange = MaxRange;
	Event.ThreatStrength = ThreatStrength;
	Event.Instigator = Instigator;
	Event.Tag = Tag;
	return Event.Id;
}

void UEcoNoiseSubsystem::GatherRecent(TArray<FEcoNoiseEvent>& Out)
{
	Out.Reset();
	if (!IsInGameThread() || !GetWorld() || GetWorld()->GetNetMode() == NM_Client) { return; }
	Prune(GetWorld()->GetTimeSeconds());
	Out = Events;
}

void UEcoNoiseSubsystem::Deinitialize()
{
	Events.Reset(); NextId = 1;
	Super::Deinitialize();
}
