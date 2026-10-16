#include "AI/Social/Senses/EcoPredatorPerception.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "AI/Policy/EcoNeighborhoodSubsystem.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoBehaviorConfig.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassExecutionContext.h"
#include "MassEntityView.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcoWorldClockSubsystem.h"
#include "Engine/World.h"
#include "DrawDebugHelpers.h"
#include "HAL/IConsoleManager.h"

static TAutoConsoleVariable<int32> CVarEcoPreyLog(TEXT("eco.Senses.PreyLog"), 0, TEXT("Authority prey observation handoff; not PPO output."));

UEcoPredatorPerceptionProcessor::UEcoPredatorPerceptionProcessor() : Query(*this)
{
    ExecutionFlags = int32(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
    ProcessingPhase = EMassProcessingPhase::PrePhysics;
    ExecutionOrder.ExecuteAfter.Add(TEXT("EcoNeighborhoodGatherProcessor"));
    ExecutionOrder.ExecuteBefore.Add(TEXT("EcoPredationProcessor"));
    bRequiresGameThreadExecution = true;
}
void UEcoPredatorPerceptionProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EM)
{
    Query.AddTagRequirement<FEcoIntegratedCreatureTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
    Query.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
    Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoPreySenseFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoSensoryProfileFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddSharedRequirement<FEcoPredatorSensesSharedFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddSharedRequirement<FEcoSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddIndirectFragmentRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddIndirectFragmentRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
}
void UEcoPredatorPerceptionProcessor::Execute(FMassEntityManager& EM, FMassExecutionContext& Context)
{
    UWorld* World = Context.GetWorld();
    if (!World || World->GetNetMode() == NM_Client || !FMath::IsFinite(Context.GetDeltaTimeSeconds()) || Context.GetDeltaTimeSeconds() < 0) return;
    UntilScan -= Context.GetDeltaTimeSeconds(); if (UntilScan > 0) return; UntilScan = .2f;
    auto* Grid = World->GetSubsystem<UEcoNeighborhoodSubsystem>();
    const double Now = World->GetTimeSeconds();
    TArray<FEcoNoiseEvent> Noises;
    if (auto* Noise = World->GetSubsystem<UEcoNoiseSubsystem>()) Noise->GatherRecent(Noises);
    const auto* Regions = World->GetSubsystem<UEcologyWorldSubsystem>();
    const auto* Clock = World->GetSubsystem<UEcoWorldClockSubsystem>();
    const auto* DrawFOV = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Senses.DrawFOV"));
    const auto* DrawHearing = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Senses.DrawHearing"));
    const auto* DrawSense = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Senses.Debug"));
    const auto* DrawLimit = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Senses.DrawLimit"));
    int32 Drawn = 0;
    Query.ForEachEntityChunk(Context, [&](FMassExecutionContext& C)
    {
        const auto T = C.GetFragmentView<FTransformFragment>(); const auto V = C.GetFragmentView<FMassVelocityFragment>();
        auto Senses = C.GetMutableFragmentView<FEcoPreySenseFragment>();
        const auto Profiles = C.GetFragmentView<FEcoSensoryProfileFragment>(); const auto Ids = C.GetFragmentView<FEcoIdentityFragment>();
        const auto Vitals = C.GetFragmentView<FEcoVitalsFragment>(); const auto Membership = C.GetFragmentView<FEcoRegionFragment>();
        const auto& Settings = C.GetSharedFragment<FEcoPredatorSensesSharedFragment>().Settings;
        const auto& Species = C.GetSharedFragment<FEcoSpeciesSharedFragment>();
        // Bounded lookup per scan: only alive authoritative herbivores with stable identities.
        TMap<int64, const FEcoNeighborEntry*> AlivePrey;
        if (Grid && Grid->IsBuilt()) for (const auto& Entry : Grid->GetEntries())
        {
            if (Entry.bPredator || !EM.IsEntityValid(Entry.Entity)) continue;
            const FMassEntityView View(EM, Entry.Entity);
            if (!View.HasTag<FEcoHerbivoreTag>() || View.HasTag<FEcoClientProxyTag>() || View.HasTag<FEcoPendingDeathTag>()) continue;
            const auto* Vital = C.GetIndirectConstFragmentPtr<FEcoVitalsFragment>(Entry.Entity);
            const auto* Identity = C.GetIndirectConstFragmentPtr<FEcoIdentityFragment>(Entry.Entity);
            if (Vital && FMath::IsFinite(Vital->HP) && Vital->HP > 0 && Identity && Identity->StableAgentId > 0)
                AlivePrey.Add(Identity->StableAgentId, &Entry);
        }
        for (int32 I = 0; I < C.GetNumEntities(); ++I)
        {
            auto& Sense = Senses[I]; const auto& Profile = Profiles[I];
            const FVector Position = T[I].GetTransform().GetLocation();
            if (!Settings.IsValid() || !Profile.IsValid() || !FMath::IsFinite(Species.ViewDistance) || !FMath::IsFinite(Species.FOV)
                || Position.ContainsNaN() || !FMath::IsFinite(Vitals[I].HP) || Vitals[I].HP <= 0)
            { Sense.Forget(); continue; }
            Sense.Cue.Age(Now, Settings, Profile.MemoryMultiplier);
            if (Sense.TargetAgentId > 0 && (!AlivePrey.Contains(Sense.TargetAgentId) || AlivePrey[Sense.TargetAgentId]->Entity != Sense.Target)) Sense.Forget();
            if (Sense.Cue.Source == EEcoSenseSource::None) { Sense.Target = {}; Sense.TargetAgentId = 0; }
            if (Sense.Cue.Source == EEcoSenseSource::Memory && FVector::Dist2D(Position, Sense.Cue.LastKnownPosition)
                <= FMath::Clamp(Sense.Cue.UncertaintyRadius, 100.f, 300.f)) Sense.Forget();
            FRegionEnvironmentState Environment; Environment.Rainfall = 0;
            if (Regions) Regions->GetEnvironmentState(Membership[I].CurrentRegionId, Environment);
            if (Clock && Clock->IsClockRunning()) Environment.DayPhase = Clock->GetServerTime().DayCycle.Phase;
            const float Rain = FMath::IsFinite(Environment.Rainfall) ? FMath::Clamp(Environment.Rainfall, 0.f, 1.f) : 0;
            const float Night = Environment.DayPhase == EEcoDayPhase::Night ? Settings.NightVisionMultiplier : 1;
            const float Radius = FMath::Clamp(Species.ViewDistance * Profile.VisionMultiplier * Night * FMath::Lerp(1.f, Settings.RainVisionMultiplier, Rain), 0.f, 10000.f);
            const float Hearing = FMath::Clamp(Settings.HearingRange * Profile.HearingMultiplier * FMath::Lerp(1.f, Settings.RainHearingMultiplier, Rain), 0.f, 10000.f);
            FVector Heading = V[I].Value.GetSafeNormal2D();
            if (Heading.IsNearlyZero()) Heading = T[I].GetTransform().GetUnitAxis(EAxis::X).GetSafeNormal2D();
            if (Heading.ContainsNaN() || Heading.IsNearlyZero()) Heading = FVector::ForwardVector;
            const float Half = FMath::DegreesToRadians(FMath::Clamp(Species.FOV, 0.f, 360.f) * .5f);
            const FVector Eye(0,0,80);
            auto Blocked = [&](const FVector& Target)
            {
                FHitResult Hit; FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoPreySight), false);
                if (World->LineTraceSingleByChannel(Hit, Position + Eye, Target + Eye, ECC_Visibility, Params)) return true;
                Params.bTraceComplex = true;
                return World->LineTraceSingleByChannel(Hit, Position + Eye, Target + Eye, ECC_Visibility, Params);
            };
            int64 SeenId = 0; const FEcoNeighborEntry* Seen = nullptr; float BestDistance = MAX_flt;
            // Sorting by distance then StableAgentId makes selection independent of TMap iteration.
            for (const auto& Pair : AlivePrey)
            {
                const FVector D = Pair.Value->Location - Position;
                const float Distance = D.Size() * (Pair.Value->bInCover ? EcoBehaviorConfig::CoverHideMult : 1.f);
                if (D.ContainsNaN() || Radius <= 0 || Distance > Radius || Distance > BestDistance
                    || (Distance == BestDistance && SeenId > 0 && Pair.Key >= SeenId)
                    || (!D.GetSafeNormal2D().IsNearlyZero() && FVector::DotProduct(Heading, D.GetSafeNormal2D()) < FMath::Cos(Half))
                    || Blocked(Pair.Value->Location)) continue;
                SeenId = Pair.Key; Seen = Pair.Value; BestDistance = Distance;
            }
            const int64 PreviousNoise = Sense.Cue.LastProcessedNoiseId;
            const FEcoNoiseEvent* Heard = nullptr; float BestConfidence = 0;
            for (const auto& Noise : Noises)
            {
                Sense.Cue.LastProcessedNoiseId = FMath::Max(Sense.Cue.LastProcessedNoiseId, Noise.Id);
                if (Noise.Id <= PreviousNoise || Noise.SourceAgentId == Ids[I].StableAgentId
                    || Noise.SourceSpeciesId != TEXT("Herbivore") || !AlivePrey.Contains(Noise.SourceAgentId)) continue;
                const float Range = FMath::Min(Hearing, Noise.MaxRange); const float Distance = FVector::Dist(Position, Noise.Position);
                if (Range <= 0 || Distance >= Range) continue;
                float Confidence = Settings.HearingConfidence * Noise.Loudness * (1.f - Distance / Range);
                if (Confidence < Settings.MinimumConfidence || Confidence < BestConfidence) continue;
                if (Blocked(Noise.Position)) Confidence *= Settings.OccludedHearingMultiplier;
                if (Confidence < Settings.MinimumConfidence || Confidence < BestConfidence
                    || (Confidence == BestConfidence && Heard && Noise.Id >= Heard->Id)) continue;
                Heard = &Noise; BestConfidence = Confidence;
            }
            if (Seen)
            {
                Sense.Cue.Observe(EEcoSenseSource::Sight, Seen->Location, 1, 0, 1, uint64(SeenId), Now);
                Sense.Target = Seen->Entity; Sense.TargetAgentId = SeenId;
            }
            else if (Heard && BestConfidence >= Sense.Cue.Confidence)
            {
                Sense.Cue.Observe(EEcoSenseSource::Hearing, Heard->Position, BestConfidence, Settings.HearingUncertainty, 1, uint64(Heard->SourceAgentId), Now);
                Sense.Target = AlivePrey[Heard->SourceAgentId]->Entity; Sense.TargetAgentId = Heard->SourceAgentId;
            }
            if (CVarEcoPreyLog.GetValueOnGameThread()) UE_LOG(LogTemp, Log, TEXT("[Eco PreySense] Mode=%d Wolf=%lld Target=%lld Source=%d Confidence=%.3f Position=%s"),
                int32(World->GetNetMode()), Ids[I].StableAgentId, Sense.TargetAgentId, int32(Sense.Cue.Source), Sense.Cue.Confidence, *Sense.Cue.LastKnownPosition.ToCompactString());
            if (World->GetNetMode() != NM_DedicatedServer && Drawn++ < (DrawLimit ? FMath::Clamp(DrawLimit->GetInt(), 0, 128) : 16))
            {
                if (DrawFOV && DrawFOV->GetInt())
                {
                    FVector Previous; const float Yaw = FMath::Atan2(Heading.Y, Heading.X);
                    for (int32 Segment = 0; Segment <= 32; ++Segment)
                    {
                        const float A = Yaw - Half + 2 * Half * Segment / 32;
                        const FVector Point = Position + Eye + FVector(FMath::Cos(A), FMath::Sin(A), 0) * Radius;
                        if (Segment) DrawDebugLine(World, Previous, Point, FColor::Orange, false, .21f, 1, 2);
                        if (Segment == 0 || Segment == 32) DrawDebugLine(World, Position + Eye, Point, FColor::Orange, false, .21f, 1, 2);
                        Previous = Point;
                    }
                }
                if (DrawHearing && DrawHearing->GetInt()) DrawDebugSphere(World, Position + Eye, Hearing, 24, FColor::Cyan, false, .21f, 1, 1);
                if (DrawSense && DrawSense->GetInt() && Sense.TargetAgentId > 0)
                {
                    const FColor Color = Sense.Cue.Source == EEcoSenseSource::Sight ? FColor::Orange : Sense.Cue.Source == EEcoSenseSource::Hearing ? FColor::Yellow : FColor::Cyan;
                    DrawDebugLine(World, Position + Eye, Sense.Cue.LastKnownPosition + Eye, Color, false, .21f, 1, 2);
                    DrawDebugString(World, Position + Eye, FString::Printf(TEXT("Prey=%lld Sense=%d C=%.2f"), Sense.TargetAgentId, int32(Sense.Cue.Source), Sense.Cue.Confidence), nullptr, Color, .21f);
                }
            }
        }
    });
}
