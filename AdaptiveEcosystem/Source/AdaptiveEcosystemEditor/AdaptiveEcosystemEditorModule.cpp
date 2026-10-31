#include "Modules/ModuleManager.h"
#include "Creature/Representation/EcoCreatureAnimationBuilder.h"
#include "Creature/Representation/EcoCreatureAnimationProfile.h"
#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "EcoGroundFeetGraphNode.h"
#include "Animation/AnimBlueprint.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_BlendListByInt.h"
#include "AnimGraphNode_BlendSpacePlayer.h"
#include "AnimGraphNode_SequencePlayer.h"
#include "AnimGraphNode_LayeredBoneBlend.h"
#include "K2Node_VariableGet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "EdGraph/EdGraphNodeUtils.h"
#include "EdGraph/EdGraphSchema.h"
#include "UObject/UnrealType.h"
class FAdaptiveEcosystemEditorModule : public IModuleInterface {
public:
    virtual void StartupModule() override {EcoPoseGraphAuthoring().BindRaw(this,&FAdaptiveEcosystemEditorModule::BuildPoseGraph);}
    virtual void ShutdownModule() override {EcoPoseGraphAuthoring().Unbind();}
    bool BuildPoseGraph(UAnimBlueprint* BP,UEcoCreatureAnimationProfile* P);
};
IMPLEMENT_MODULE(FAdaptiveEcosystemEditorModule,AdaptiveEcosystemEditor)
bool FAdaptiveEcosystemEditorModule::BuildPoseGraph(UAnimBlueprint* BP,UEcoCreatureAnimationProfile* P)
{
#if WITH_EDITOR
    if(!BP || !P || !P->IsValidProfile() || !BP->ParentClass->IsChildOf(UEcoCreatureAnimInstance::StaticClass())
        || BP->TargetSkeleton!=P->Locomotion->GetSkeleton()
        || !BP->GetPathName().StartsWith(TEXT("/Game/JYU/"))) return false;
    TArray<UEdGraph*> Graphs; BP->GetAllGraphs(Graphs);
    UEdGraph* Graph=nullptr; for(auto* Candidate:Graphs)if(Candidate->GetFName()==TEXT("AnimGraph")){Graph=Candidate;break;}
    if(!Graph) return false;
    BP->Modify(); Graph->Modify();
    auto Nodes=Graph->Nodes;
    for(const auto& N:Nodes) FBlueprintEditorUtils::RemoveNode(BP,N.Get(),true);
    const UEdGraphSchema* Schema=Graph->GetSchema();
    auto NewNode=[Graph]<typename T>(int32 X,int32 Y) {
        FGraphNodeCreator<T> Creator(*Graph); T* N=Creator.CreateNode(); N->NodePosX=X;N->NodePosY=Y; Creator.Finalize();return N;
    };
    auto* Root=NewNode.operator()<UAnimGraphNode_Root>(600,0);
    auto* Blend=NewNode.operator()<UAnimGraphNode_BlendListByInt>(300,0);
    // Standard reflected editor property (UE 5.8 spells it ChildUpateMode).
    if(auto* Property=FindFProperty<FEnumProperty>(FAnimNode_BlendListBase::StaticStruct(),TEXT("ChildUpateMode")))
        Property->GetUnderlyingProperty()->SetIntPropertyValue(Property->ContainerPtrToValuePtr<void>(&Blend->Node),int64(EBlendListChildUpdateMode::ResetChildOnActivate));

    auto PosePins=[Blend](){
        TArray<UEdGraphPin*> Pins;
        for(auto* Pin:Blend->Pins) if(Pin->Direction==EGPD_Input && Pin->PinName.ToString().StartsWith(TEXT("BlendPose_"))) Pins.Add(Pin);
        return Pins;
    };
    while(PosePins().Num()<9) Blend->AddPinToBlendList();
    const auto Inputs=PosePins();
    if(Inputs.Num()!=9) return false;
    auto Connect=[Schema](UEdGraphPin* A,UEdGraphPin* B) {return A&&B&&Schema->TryCreateConnection(A,B);};
    auto Getter=[&]<typename T>(FName Name,int32 X,int32 Y) {
        auto* N=NewNode.operator()<UK2Node_VariableGet>(X,Y);
        N->VariableReference.SetSelfMember(Name);N->ReconstructNode();return N->FindPin(Name);
    };
    if(!Connect(Getter.operator()<int32>(TEXT("AnimationIndex"),0,-150),Blend->FindPin(TEXT("ActiveChildIndex")))
        || !Connect(Blend->FindPin(TEXT("Pose")),Root->FindPin(TEXT("Result")))) return false;
    auto* Move=NewNode.operator()<UAnimGraphNode_BlendSpacePlayer>(0,0);
    Move->SetAnimationAsset(P->Locomotion);
    for(auto& Pin:Move->ShowPinForProperties) if(Pin.PropertyName==TEXT("X")||Pin.PropertyName==TEXT("Y")) Pin.bShowPin=true;
    Move->ReconstructNode();
    if(!Connect(Getter.operator()<float>(TEXT("SpeedCmPerSecond"),-250,-75),Move->FindPin(TEXT("X")))
        || !Connect(Getter.operator()<float>(TEXT("TurnAmount"),-250,75),Move->FindPin(TEXT("Y")))
        || !Connect(Move->FindPin(TEXT("Pose")),Inputs[0])) return false;
    for(int32 I=1;I<9;++I) {
        auto* Player=NewNode.operator()<UAnimGraphNode_SequencePlayer>(0,I*150);
        Player->SetAnimationAsset(P->Poses[I].Clip);
        Player->Node.SetLoopAnimation(P->Poses[I].bLoop);
        Player->Node.SetPlayRate(P->Poses[I].PlayRate);
        Player->ReconstructNode();
        if(!Connect(Player->FindPin(TEXT("Pose")),Inputs[I])) return false;
        if(auto* Time=Blend->FindPin(FName(*FString::Printf(TEXT("BlendTime_%d"),I))))
            Schema->TrySetDefaultValue(*Time,LexToString(P->Poses[I].BlendSeconds));
    }
    UEdGraphPin* FinalPose=Blend->FindPin(TEXT("Pose"));
    if(!P->AlertHeadBone.IsNone()){
        auto* Head=NewNode.operator()<UAnimGraphNode_SequencePlayer>(300,-400);
        Head->SetAnimationAsset(P->Poses[2].Clip);Head->Node.SetLoopAnimation(true);Head->ReconstructNode();
        auto* Layer=NewNode.operator()<UAnimGraphNode_LayeredBoneBlend>(500,-200);
        while(Layer->Node.BlendPoses.Num()<1)Layer->AddPinToBlendByFilter();
        Layer->Node.LayerSetup.SetNum(1);Layer->Node.LayerSetup[0].BranchFilters.Reset();
        FBranchFilter Filter;Filter.BoneName=P->AlertHeadBone;Filter.BlendDepth=1;
        Layer->Node.LayerSetup[0].BranchFilters.Add(Filter);
        for(auto& Pin:Layer->ShowPinForProperties)if(Pin.PropertyName==TEXT("BlendWeights"))Pin.bShowPin=true;
        Layer->ReconstructNode();
        if(!Connect(FinalPose,Layer->FindPin(TEXT("BasePose")))||!Connect(Head->FindPin(TEXT("Pose")),Layer->FindPin(TEXT("BlendPoses_0")))
            ||!Connect(Getter.operator()<float>(TEXT("AlertHeadAlpha"),100,-250),Layer->FindPin(TEXT("BlendWeights_0"))))return false;
        FinalPose=Layer->FindPin(TEXT("Pose"));
    }
    Root->FindPin(TEXT("Result"))->BreakAllPinLinks();
    if(!Connect(FinalPose,Root->FindPin(TEXT("Result"))))return false;
    if(P->bEnableGroundIK) {
        auto* IK=NewNode.operator()<UAnimGraphNode_EcoGroundFeet>(650,0);
        IK->Node.Body.BoneName=P->BodyBone;
        IK->Node.MaximumCorrection=P->MaxFootCorrectionCm;IK->Node.Clearance=P->FootClearanceCm;
        for(int32 Index=0;Index<4;++Index){FEcoGroundLeg& Leg=IK->Node.Legs.AddDefaulted_GetRef();Leg.Contact.BoneName=P->FootBones[Index];Leg.End.BoneName=P->IKEndBones[Index];Leg.ContactHeight=P->ContactHeights[Index];}
        for(auto& Pin:IK->ShowPinForProperties)if(Pin.PropertyName==TEXT("Alpha"))Pin.bShowPin=true;
        IK->ReconstructNode();Root->FindPin(TEXT("Result"))->BreakAllPinLinks();
        if(!Connect(FinalPose,IK->FindPin(TEXT("ComponentPose")))||!Connect(IK->FindPin(TEXT("Pose")),Root->FindPin(TEXT("Result"))))return false;
        for(int32 Index=0;Index<4;++Index) {
            const FName Point(*FString::Printf(TEXT("GroundPoint%d"),Index)),Valid(*FString::Printf(TEXT("GroundValid%d"),Index));
            if(!Connect(Getter.operator()<FVector>(Point,400,300+Index*120),IK->FindPin(Point))||!Connect(Getter.operator()<float>(Valid,400,350+Index*120),IK->FindPin(Valid)))return false;
        }
        if(!Connect(Getter.operator()<FVector>(TEXT("GroundRootPoint"),400,800),IK->FindPin(TEXT("GroundRootPoint"))))return false;
        if(!Connect(Getter.operator()<FVector>(TEXT("GroundUp"),400,850),IK->FindPin(TEXT("GroundUp")))
            ||!Connect(Getter.operator()<float>(TEXT("GroundWorldToComponent"),400,950),IK->FindPin(TEXT("GroundWorldToComponent")))
            ||!Connect(Getter.operator()<float>(TEXT("GroundIKAlpha"),400,1050),IK->FindPin(TEXT("Alpha"))))return false;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP);
    return BP->Status!=BS_Error && BP->GeneratedClass;
#else
    return false;
#endif
}
