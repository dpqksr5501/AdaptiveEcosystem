#include "AI/Behavior/EcoSpeciesAITemplate.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "MassEntityTemplateRegistry.h"
#include "MassEntityUtils.h"
#include "MassCommonFragments.h"
#include "MassMovementFragments.h"
#include "MassNavigationFragments.h"
#include "MassNavMeshNavigationFragments.h"
#include "Steering/MassSteeringFragments.h"
#include "Avoidance/MassAvoidanceFragments.h"
#include "MassStateTreeFragments.h"
#include "MassSmartObjectFragments.h"
#include "MassLODTrait.h"
#include "MassSimulationLOD.h"
#include "Mass/EcoMassFragments.h"
#include "Engine/World.h"
void EcoSpeciesAI::BuildEngineTemplate(FMassEntityTemplateBuildContext& C,const UWorld& W,UEcoSpeciesAIProfile& P)
{
    if(W.GetNetMode()==NM_Client&&!C.IsInspectingData())return;
    auto& EM=UE::Mass::Utils::GetEntityManagerChecked(W);
    C.AddTag<FEcoStateTreeBehaviorTag>();C.AddFragment<FEcoPolicyOutputFragment>();
    C.AddFragment<FEcoSpeciesAIInputFragment>();C.AddFragment<FEcoSpeciesAIDecisionFragment>();
    C.AddFragment<FEcoSpeciesAIExecutionFragment>();C.AddFragment<FEcoSpeciesAIMoveFragment>();
    C.AddFragment<FEcoSpeciesAIFeedingFragment>();C.AddFragment<FEcoSpeciesAIAttackFragment>();
    FEcoSpeciesAISharedFragment Profile;Profile.Profile=&P;C.AddConstSharedFragment(EM.GetOrCreateConstSharedFragment(Profile));
    FMassStateTreeSharedFragment Tree;Tree.StateTree=P.StateTree;
    C.AddConstSharedFragment(EM.GetOrCreateConstSharedFragment(Tree));C.AddFragment<FMassStateTreeInstanceFragment>();
    if(P.bPolicyOnly)return;
    C.AddTag<FEcoGroundedNavigationTag>();
    C.AddFragment_GetRef<FAgentRadiusFragment>().Radius=P.BodyRadius;C.AddFragment_GetRef<FAgentHeightFragment>().Height=P.BodyHeight;
    C.AddFragment<FMassForceFragment>();C.AddFragment<FMassDesiredMovementFragment>();
    FMassMovementParameters Movement;Movement.MaxSpeed=P.RunSpeed;Movement.MaxAcceleration=1000.f;
    Movement.DefaultDesiredSpeed=P.WalkSpeed;Movement.DefaultDesiredSpeedVariance=0;
    C.AddConstSharedFragment(EM.GetOrCreateConstSharedFragment(Movement.GetValidated()));
    C.AddFragment<FMassMoveTargetFragment>();C.AddFragment<FMassSteeringFragment>();
    C.AddFragment<FMassStandingSteeringFragment>();C.AddFragment<FMassGhostLocationFragment>();
    FMassMovingSteeringParameters Moving;Moving.bAllowSpeedVariance=false;
    FMassStandingSteeringParameters Standing;Standing.TargetMoveThresholdVariance=0;Standing.TargetSelectionCooldownVariance=0;
    C.AddConstSharedFragment(EM.GetOrCreateConstSharedFragment(Moving));C.AddConstSharedFragment(EM.GetOrCreateConstSharedFragment(Standing));
    C.AddFragment<FMassNavMeshCachedPathFragment>();C.AddFragment<FMassNavMeshShortPathFragment>();C.AddFragment<FMassNavMeshBoundaryFragment>();
    C.AddFragment<FMassNavigationEdgesFragment>();C.AddFragment<FMassNavigationObstacleGridCellLocationFragment>();
    C.AddConstSharedFragment(EM.GetOrCreateConstSharedFragment(FMassMovingAvoidanceParameters().GetValidated()));
    C.AddConstSharedFragment(EM.GetOrCreateConstSharedFragment(FMassStandingAvoidanceParameters().GetValidated()));
    C.AddFragment<FMassSmartObjectUserFragment>();
    C.AddFragment<FMassViewerInfoFragment>();C.AddTag<FMassCollectDistanceLODViewerInfoTag>();
    C.AddFragment_GetRef<FMassSimulationLODFragment>().LOD=EMassLOD::Low;
    FMassSimulationLODParameters LOD;LOD.bSetLODTags=false;
    LOD.LODDistance[EMassLOD::High]=0;LOD.LODDistance[EMassLOD::Medium]=P.MediumDistance;
    LOD.LODDistance[EMassLOD::Low]=P.FarDistance;LOD.LODDistance[EMassLOD::Off]=FLT_MAX;
    C.AddConstSharedFragment(EM.GetOrCreateConstSharedFragment(LOD));C.AddSharedFragment(EM.GetOrCreateSharedFragment(FMassSimulationLODSharedFragment(LOD)));
}
