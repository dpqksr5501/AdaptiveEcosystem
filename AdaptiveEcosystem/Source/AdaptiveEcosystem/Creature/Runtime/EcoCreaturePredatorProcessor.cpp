#include "Creature/Runtime/EcoCreaturePredatorProcessor.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoBehaviorConfig.h"
#include "AI/Policy/EcoNeighborhoodSubsystem.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassExecutionContext.h"
#include "Engine/World.h"

UEcoCreaturePredatorProcessor::UEcoCreaturePredatorProcessor() : Query(*this)
{
    ExecutionFlags = int32(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
    ProcessingPhase = EMassProcessingPhase::PrePhysics;
    ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPredationProcessor"));
    bRequiresGameThreadExecution = true;
}
void UEcoCreaturePredatorProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
    Query.AddTagRequirement<FEcoIntegratedCreatureTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::All);
    Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoCreatureLifecycleFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoPredatorStateFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
}
void UEcoCreaturePredatorProcessor::Execute(FMassEntityManager& EM, FMassExecutionContext& Context)
{
    UWorld* World = GetWorld();
    auto* Grid = World ? World->GetSubsystem<UEcoNeighborhoodSubsystem>() : nullptr;
    const float Delta = Context.GetDeltaTimeSeconds();
    if (!Grid || !Grid->IsBuilt() || !FMath::IsFinite(Delta) || Delta <= 0) return;
    const double Now = World->GetTimeSeconds();
    Query.ForEachEntityChunk(Context, [&](FMassExecutionContext& C)
    {
        auto Transforms = C.GetMutableFragmentView<FTransformFragment>(); auto Velocities = C.GetMutableFragmentView<FMassVelocityFragment>();
        auto Lives = C.GetMutableFragmentView<FEcoCreatureLifecycleFragment>();
        const auto Ids = C.GetFragmentView<FEcoIdentityFragment>(); const auto Regions = C.GetFragmentView<FEcoRegionFragment>();
        const auto States = C.GetFragmentView<FEcoPredatorStateFragment>(); const auto Vitals = C.GetFragmentView<FEcoVitalsFragment>();
        const auto Travel = C.GetFragmentView<FEcoTravelFragment>();
        TArray<int32> Nearby;
        for (int32 I = 0; I < C.GetNumEntities(); ++I)
        {
            auto& T = Transforms[I].GetMutableTransform(); auto& Life = Lives[I]; Life.bPursuing = false;
            if (Vitals[I].HP <= 0 || States[I].EatCooldown > 0) { Velocities[I].Value = FVector::ZeroVector; continue; }
            const FVector Position = T.GetLocation(), Heading = T.GetRotation().GetForwardVector();
            FVector Direction = Heading; float Best = MAX_flt;
            Grid->QueryRadius(Position, EcoBehaviorConfig::PredViewRadiusCm, Nearby);
            for (int32 Index : Nearby)
            {
                const auto& Other = Grid->GetEntries()[Index];
                if (Other.bPredator || !EM.IsEntityValid(Other.Entity)) continue;
                const auto* V = EM.GetFragmentDataPtr<FEcoVitalsFragment>(Other.Entity); if (!V || V->HP <= 0) continue;
                const FVector D = Other.Location - Position;
                const float Distance = D.Size2D() * (Other.bInCover ? EcoBehaviorConfig::CoverHideMult : 1.f);
                if (Distance >= Best || Distance > EcoBehaviorConfig::PredViewRadiusCm || FVector::DotProduct(D.GetSafeNormal2D(), Heading)
                    < FMath::Cos(FMath::DegreesToRadians(EcoBehaviorConfig::PredFovDeg * 0.5f))) continue;
                Best = Distance; Direction = D.GetSafeNormal2D(); Life.bPursuing = true;
            }
            if (!Life.bPursuing && Now >= Life.NextWanderTime)
            {
                Life.NextWanderTime = Now + EcoBehaviorConfig::StepSeconds;
                FRandomStream Random(int32(HashCombine(GetTypeHash(Ids[I].StableAgentId), GetTypeHash(int32(Now / EcoBehaviorConfig::StepSeconds)))));
                Direction = Heading.RotateAngleAxis(FMath::RadiansToDegrees(Random.FRandRange(-EcoBehaviorConfig::PredWanderTurnRad, EcoBehaviorConfig::PredWanderTurnRad)), FVector::UpVector);
            }
            FVector Velocity = Direction * EcoBehaviorConfig::HerbSpeedCmS;
            Velocity = EcoCreatureMovement::SelectVelocity(Position, Velocity, Velocity.Size2D(), Delta, Now, &Travel[I], nullptr, nullptr);
            FVector Next = Position + Velocity * Delta;
            if (!EcoCreatureMovement::ConstrainStep(*World, Regions[I].CurrentRegionId, Travel[I].State == EEcoResidenceState::Traveling, Position, Next))
            { Velocity = FVector::ZeroVector; Next = Position; T.SetRotation((-Direction).ToOrientationQuat()); }
            else if (!Velocity.IsNearlyZero()) T.SetRotation(Velocity.ToOrientationQuat());
            T.SetLocation(Next); Velocities[I].Value = Velocity;
        }
    });
}
