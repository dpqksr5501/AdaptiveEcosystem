#include "Mass/Movement/EcoCompatibleNavigationHeightProcessor.h"
#include "MassCommonTypes.h"
#include "MassCommonFragments.h"
#include "MassMovementFragments.h"
#include "MassMovementTypes.h"
#include "MassNavigationFragments.h"
#include "MassSimulationLOD.h"
#include "MassExecutionContext.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
UEcoCompatibleNavigationHeightProcessor::UEcoCompatibleNavigationHeightProcessor():Query(*this)
{ExecutionFlags=int32(EProcessorExecutionFlags::AllNetModes);ExecutionOrder.ExecuteAfter.Add(UE::Mass::ProcessorGroupNames::Movement);}
void UEcoCompatibleNavigationHeightProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>&)
{
    Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FMassMoveTargetFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddConstSharedRequirement<FMassMovementParameters>();
    Query.AddTagRequirement<FMassOffLODTag>(EMassFragmentPresence::None);
    Query.AddTagRequirement<FEcoGroundedNavigationTag>(EMassFragmentPresence::None);
}
void UEcoCompatibleNavigationHeightProcessor::Execute(FMassEntityManager&,FMassExecutionContext& Context)
{
    Query.ForEachEntityChunk(Context,[](FMassExecutionContext& C)
    {
#if WITH_MASSGAMEPLAY_DEBUG
        if(UE::MassMovement::bFreezeMovement)return;
#endif
        const auto& P=C.GetConstSharedFragment<FMassMovementParameters>();
        auto T=C.GetMutableFragmentView<FTransformFragment>();const auto M=C.GetFragmentView<FMassMoveTargetFragment>();
        for(int32 I=0;I<C.GetNumEntities();++I)
            if(M[I].GetCurrentAction()==EMassMovementAction::Move||M[I].GetCurrentAction()==EMassMovementAction::Stand)
            {
                auto& Transform=T[I].GetMutableTransform();auto Position=Transform.GetLocation();
                FMath::ExponentialSmoothingApprox(Position.Z,M[I].Center.Z,C.GetDeltaTimeSeconds(),P.HeightSmoothingTime);
                Transform.SetLocation(Position);
            }
    });
}
