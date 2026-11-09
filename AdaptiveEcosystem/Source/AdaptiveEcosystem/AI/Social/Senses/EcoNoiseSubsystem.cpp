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
    if (Instigator && (!IsValid(Instigator) || Instigator->IsActorBeingDestroyed())) return 0;
    FEcoNoiseEvent Event;
    Event.Position = Position;
    Event.Loudness = Loudness;
    Event.MaxRange = MaxRange;
    Event.ThreatStrength = ThreatStrength;
    Event.Instigator = Instigator;
    Event.Tag = Tag;
    return Accept(Event, false);
}

int64 UEcoNoiseSubsystem::Accept(FEcoNoiseEvent Event, bool bProfiledCreature)
{
	UWorld* World = GetWorld();
    const auto& Position = Event.Position;
    const auto Loudness = Event.Loudness, MaxRange = Event.MaxRange, ThreatStrength = Event.ThreatStrength;
    const FName Tag = Event.Tag;
    const AActor* Instigator = Event.Instigator.Get();
	if (!IsInGameThread() || !World || !World->IsGameWorld() || World->GetNetMode() == NM_Client
		|| Position.ContainsNaN() || !FMath::IsFinite(Loudness) || Loudness <= 0 || Loudness > 1
		|| !FMath::IsFinite(MaxRange) || MaxRange <= 0 || MaxRange > 10000
		|| !FMath::IsFinite(ThreatStrength) || ThreatStrength < 0 || ThreatStrength > 1
		|| (Instigator && (!IsValid(Instigator) || Instigator->IsActorBeingDestroyed()
			|| Instigator->GetWorld() != World || !Instigator->HasAuthority())) || NextId == MAX_int64) { return 0; }
	const double Now = World->GetTimeSeconds();
	if (!FMath::IsFinite(Now) || Now < 0) { return 0; }
    if (bProfiledCreature)
    {
        constexpr int32 MaxProfiledSources = 512;
        if (ProfiledFootsteps.Num() >= MaxProfiledSources && !ProfiledFootsteps.Contains(Event.SourceAgentId))
        {
            for (auto It = ProfiledFootsteps.CreateIterator(); It; ++It)
                if (Now < It.Value().EmittedAt || Now - It.Value().EmittedAt >= EventLifetime) It.RemoveCurrent();
            if (ProfiledFootsteps.Num() >= MaxProfiledSources) return 0;
        }
    }
    else
    {
        Prune(Now);
        if (Events.Num() >= MaxEvents) return 0;
    }
	Event.Id = NextId++;
	Event.EmittedAt = Now;
    if (bProfiledCreature) ProfiledFootsteps.Add(Event.SourceAgentId, Event);
    else Events.Add(Event);
    if(CVarEcoNoiseLog.GetValueOnGameThread()&&(Tag==TEXT("Player.Footstep")||Tag==TEXT("Herd.Alarm")))
        UE_LOG(LogTemp,Log,TEXT("[Eco GameplayNoise] Tag=%s Mode=%d Loudness=%.2f Range=%.0f Position=%s"),
            *Tag.ToString(),int32(World->GetNetMode()),Loudness,MaxRange,*Position.ToCompactString());

	if (CVarEcoDrawNoise.GetValueOnGameThread() && World->GetNetMode() != NM_DedicatedServer)
		DrawDebugSphere(World, Position + FVector(0, 0, 20), MaxRange, 20, FColor::Orange, false, 0.2f, 0, 1.f);
	return Event.Id;
}

int64 UEcoNoiseSubsystem::ReportCreatureFootstep(FVector Position, float Loudness, float MaxRange,
	float ThreatStrength, int64 StableAgentId, FName SpeciesId, FName RegionId)
{
	if (StableAgentId <= 0 || SpeciesId.IsNone()) return 0;
    FEcoNoiseEvent Event;
    Event.Position = Position;
    Event.Loudness = Loudness;
    Event.MaxRange = MaxRange;
    Event.ThreatStrength = ThreatStrength;
    Event.Tag = TEXT("Footstep");
    Event.SourceAgentId = StableAgentId;
    Event.SourceSpeciesId = SpeciesId;
    Event.RegionId = RegionId;
	const int64 Id = Accept(Event, !RegionId.IsNone());
	if (Id > 0)
	{
		if (CVarEcoNoiseLog.GetValueOnGameThread()) UE_LOG(LogTemp, Log,
			TEXT("[Eco FootstepNoise] Mode=%d Agent=%lld Species=%s Range=%.0f Threat=%.2f Position=%s Loudness=%.3f Region=%s"),
			int32(GetWorld()->GetNetMode()), StableAgentId, *SpeciesId.ToString(), MaxRange, ThreatStrength, *Position.ToCompactString(),
            Loudness, *RegionId.ToString());
	}
	return Id;
}

void UEcoNoiseSubsystem::GatherRecent(TArray<FEcoNoiseEvent>& Out)
{
	Out.Reset();
	if (!IsInGameThread() || !GetWorld() || GetWorld()->GetNetMode() == NM_Client) { return; }
	const double Now = GetWorld()->GetTimeSeconds();
	Prune(Now);
	Out = Events;
    if (ProfiledFootsteps.IsEmpty()) return;
    for (auto It = ProfiledFootsteps.CreateIterator(); It; ++It)
    {
        if (Now < It.Value().EmittedAt || Now - It.Value().EmittedAt >= EventLifetime) It.RemoveCurrent();
        else Out.Add(It.Value());
    }
    Out.Sort([](const auto& A, const auto& B) { return A.Id < B.Id; });
}

void UEcoNoiseSubsystem::Deinitialize()
{
	Events.Reset(); ProfiledFootsteps.Reset(); NextId = 1;
	Super::Deinitialize();
}

int64 UEcoNoiseSubsystem::ReportCreatureAlarm(FVector Position,int64 StableAgentId,FName SpeciesId)
{
    if(StableAgentId<=0||SpeciesId.IsNone())return 0;
    const int64 Id=ReportNoise(Position,.8f,3000.f,.7f,nullptr,TEXT("Herd.Alarm"));
    if(Id>0){Events.Last().SourceAgentId=StableAgentId;Events.Last().SourceSpeciesId=SpeciesId;}
    return Id;
}
