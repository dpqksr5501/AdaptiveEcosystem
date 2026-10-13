#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "DrawDebugHelpers.h"
#include "HAL/IConsoleManager.h"

static TAutoConsoleVariable<int32> CVarEcoDrawNoise(TEXT("eco.Senses.DrawNoise"), 0,
	TEXT("Draw accepted gameplay sound emission range (orange, authority only)."));
static TAutoConsoleVariable<int32> CVarEcoNoiseLog(TEXT("eco.Senses.NoiseLog"), 0,
	TEXT("Log accepted logical creature footstep emissions, including on dedicated servers."));

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
	if (CVarEcoDrawNoise.GetValueOnGameThread() && World->GetNetMode() != NM_DedicatedServer)
		DrawDebugSphere(World, Position + FVector(0, 0, 20), MaxRange, 20, FColor::Orange, false, 0.2f, 0, 1.f);
	return Event.Id;
}

int64 UEcoNoiseSubsystem::ReportCreatureFootstep(FVector Position, float Loudness, float MaxRange,
	float ThreatStrength, int64 StableAgentId, FName SpeciesId)
{
	if (StableAgentId <= 0 || SpeciesId.IsNone()) return 0;
	const int64 Id = ReportNoise(Position, Loudness, MaxRange, ThreatStrength, nullptr, TEXT("Footstep"));
	if (Id > 0)
	{
		Events.Last().SourceAgentId = StableAgentId;
		Events.Last().SourceSpeciesId = SpeciesId;
		if (CVarEcoNoiseLog.GetValueOnGameThread()) UE_LOG(LogTemp, Log,
			TEXT("[Eco FootstepNoise] Mode=%d Agent=%lld Species=%s Range=%.0f Threat=%.2f Position=%s"),
			int32(GetWorld()->GetNetMode()), StableAgentId, *SpeciesId.ToString(), MaxRange, ThreatStrength, *Position.ToCompactString());
	}
	return Id;
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
