#pragma once
#include "CoreMinimal.h"
#include "MassStateTreeTypes.h"
#include "StateTreeExecutionContext.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "Mass/EcoMassFragments.h"
#include "EcoSpeciesAIStateTreeNodes.generated.h"

USTRUCT() struct FEcoSpeciesAIScores
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere,Category="Output") float Wander=0;
    UPROPERTY(EditAnywhere,Category="Output") float Forage=0;
    UPROPERTY(EditAnywhere,Category="Output") float Rest=0;
    UPROPERTY(EditAnywhere,Category="Output") float Flee=0;
    UPROPERTY(EditAnywhere,Category="Output") float Regroup=0;
    UPROPERTY(EditAnywhere,Category="Output") float Hunt=0;
    UPROPERTY(EditAnywhere,Category="Output") float Search=0;
    UPROPERTY(EditAnywhere,Category="Output") float Eat=0;
    UPROPERTY(EditAnywhere,Category="Output") float Hold=1;
};
USTRUCT(meta=(DisplayName="Eco Species Utility Inputs"))
struct ADAPTIVEECOSYSTEM_API FEcoSpeciesAIInputEvaluator : public FMassStateTreeEvaluatorBase
{
    GENERATED_BODY()
    using FInstanceDataType=FEcoSpeciesAIScores;
    virtual const UStruct* GetInstanceDataType() const override { return FEcoSpeciesAIScores::StaticStruct(); }
    virtual bool Link(FStateTreeLinker& Linker) override;
    virtual void GetDependencies(UE::MassBehavior::FStateTreeDependencyBuilder& Builder) const override;
    virtual void TreeStart(FStateTreeExecutionContext& Context) const override;
    virtual void Tick(FStateTreeExecutionContext& Context,float DeltaTime) const override;
    TStateTreeExternalDataHandle<FEcoSpeciesAIInputFragment> InputHandle;
};
USTRUCT() struct FEcoSpeciesAITaskData
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere,Category="Parameter") EEcoSpeciesActivity Activity=EEcoSpeciesActivity::Hold;
};
USTRUCT(meta=(DisplayName="Eco Publish Species Decision"))
struct ADAPTIVEECOSYSTEM_API FEcoSpeciesAIDecisionTask : public FMassStateTreeTaskBase
{
    GENERATED_BODY()
    using FInstanceDataType=FEcoSpeciesAITaskData;
    virtual const UStruct* GetInstanceDataType() const override { return FEcoSpeciesAITaskData::StaticStruct(); }
    virtual bool Link(FStateTreeLinker& Linker) override;
    virtual void GetDependencies(UE::MassBehavior::FStateTreeDependencyBuilder& Builder) const override;
    virtual EStateTreeRunStatus EnterState(FStateTreeExecutionContext& Context,const FStateTreeTransitionResult& Transition) const override;
    virtual EStateTreeRunStatus Tick(FStateTreeExecutionContext& Context,float DeltaTime) const override;
    TStateTreeExternalDataHandle<FEcoSpeciesAIInputFragment> InputHandle;
    TStateTreeExternalDataHandle<FEcoSpeciesAIDecisionFragment> DecisionHandle;
    TStateTreeExternalDataHandle<FEcoSpeciesAISharedFragment> ProfileHandle;
    TStateTreeExternalDataHandle<FEcoPolicyOutputFragment> RawHandle;
};
