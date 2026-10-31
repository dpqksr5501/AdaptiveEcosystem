#include "AI/Behavior/StateTree/EcoSpeciesAIAssetBuilder.h"
#include "AI/Behavior/StateTree/EcoSpeciesAIStateTreeNodes.h"
#include "AI/Behavior/EcoSpeciesAIProfile.h"
#include "Creature/Runtime/EcoCreatureNetworkTrait.h"
#include "MassSmartObjectBehaviorDefinition.h"
#include "StateTree.h"
#include "AI/Policy/EcoBehaviorConfig.h"
#if WITH_EDITOR
#include "StateTreeEditorData.h"
#include "StateTreeEditorSchema.h"
#include "StateTreeState.h"
#include "StateTreeCompiler.h"
#include "StateTreeCompilerLog.h"
#include "MassStateTreeSchema.h"
#include "MassNavigationProcessors.h"
#include "Considerations/StateTreeCommonConsiderations.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "UObject/SavePackage.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "UObject/UnrealType.h"
#endif

UEcoSpeciesAIAssetsCommandlet::UEcoSpeciesAIAssetsCommandlet()
{IsClient=false;IsServer=false;IsEditor=true;LogToConsole=true;}
int32 UEcoSpeciesAIAssetsCommandlet::Main(const FString&)
{return UEcoSpeciesAIAssetBuilder::CreateDefaultAssets()?0:1;}

#if WITH_EDITOR
namespace
{
    template<class T>T* Create(const FString& PackageName,bool& New)
    {
        const FString Name=FPackageName::GetLongPackageAssetName(PackageName);
        const FString ObjectPath=PackageName+TEXT(".")+Name;
        if(FPackageName::DoesPackageExist(PackageName))
        {New=false;return LoadObject<T>(nullptr,*ObjectPath);}
        auto* Package=CreatePackage(*PackageName);New=true;
        auto* Asset=NewObject<T>(Package,*Name,RF_Public|RF_Standalone);
        FAssetRegistryModule::AssetCreated(Asset);return Asset;
    }
    bool Save(UObject& Asset)
    {
        auto* Package=Asset.GetOutermost();Package->MarkPackageDirty();
        FString File;if(!FPackageName::TryConvertLongPackageNameToFilename(Package->GetName(),File,FPackageName::GetAssetPackageExtension()))return false;
        IFileManager::Get().MakeDirectory(*FPaths::GetPath(File),true);
        FSavePackageArgs Args;Args.TopLevelFlags=RF_Public|RF_Standalone;
        const bool OK=UPackage::SavePackage(Package,&Asset,*File,Args);
        UE_LOG(LogTemp,Display,TEXT("[SpeciesAI Assets] %s Saved=%d"),*Asset.GetPathName(),OK);return OK;
    }
    UStateTree* CreateTree(const FString& PackageName)
    {
        bool New=false;auto* Tree=Create<UStateTree>(PackageName,New);if(!Tree)return nullptr;
        if(!New)
        {
            auto* ExistingEditor=Cast<UStateTreeEditorData>(Tree->EditorData);
            if(!ExistingEditor)return nullptr;
            // Repair only the missing authoring schema from the initial generated defaults.
            if(!ExistingEditor->Schema)
            {
                ExistingEditor->Schema=NewObject<UMassStateTreeSchema>(ExistingEditor,NAME_None,RF_Transactional);
                if(!ExistingEditor->EditorSchema)ExistingEditor->EditorSchema=NewObject<UStateTreeEditorSchema>(ExistingEditor,NAME_None,RF_Transactional);
                FStateTreeCompilerLog Log;FStateTreeCompiler Compiler(Log);
                if(!Compiler.Compile(Tree)){Log.DumpToLog(LogTemp);return nullptr;}
                if(!Save(*Tree))return nullptr;
            }
            return Tree->IsReadyToRun()?Tree:nullptr;
        }
        auto* Editor=NewObject<UStateTreeEditorData>(Tree,TEXT("EditorData"),RF_Transactional);Tree->EditorData=Editor;
        // The authoring schema belongs to EditorData. Compilation duplicates it under Tree.
        // A schema authored directly under Tree is removed by ResetCompiled() before saving.
        Editor->Schema=NewObject<UMassStateTreeSchema>(Editor,NAME_None,RF_Transactional);
        Editor->EditorSchema=NewObject<UStateTreeEditorSchema>(Editor,NAME_None,RF_Transactional);
        auto& Evaluator=Editor->AddEvaluator<FEcoSpeciesAIInputEvaluator>();
        auto& Root=Editor->AddSubTree(TEXT("UtilityRoot"));Root.SelectionBehavior=EStateTreeStateSelectionBehavior::TrySelectChildrenWithHighestUtility;
        struct FChoice{const TCHAR* Name;EEcoSpeciesActivity Activity;};
        const FChoice Choices[]={{TEXT("Wander"),EEcoSpeciesActivity::Wander},{TEXT("Forage"),EEcoSpeciesActivity::Forage},
            {TEXT("Rest"),EEcoSpeciesActivity::Rest},{TEXT("Flee"),EEcoSpeciesActivity::Flee},{TEXT("Regroup"),EEcoSpeciesActivity::Regroup},
            {TEXT("Hunt"),EEcoSpeciesActivity::Pursue},{TEXT("Search"),EEcoSpeciesActivity::Search},{TEXT("Eat"),EEcoSpeciesActivity::Eat},{TEXT("Hold"),EEcoSpeciesActivity::Hold}};
        for(const auto& Choice:Choices)
        {
            auto& State=Root.AddChildState(Choice.Name);
            auto& Consideration=State.AddConsideration<FStateTreeFloatInputConsideration>();
            auto* Curve=Consideration.GetNode().ResponseCurve.CurveInfo.GetRichCurve();Curve->AddKey(0,0);Curve->AddKey(1,1);
            if(!Editor->AddPropertyBinding(Evaluator,Choice.Name,Consideration,TEXT("Input")))return nullptr;
            State.AddTask<FEcoSpeciesAIDecisionTask>().GetInstanceData().Activity=Choice.Activity;
            State.AddTransition(EStateTreeTransitionTrigger::OnStateCompleted,EStateTreeTransitionType::GotoState,&Root);
        }
        FStateTreeCompilerLog Log;FStateTreeCompiler Compiler(Log);
        if(!Compiler.Compile(Tree)){Log.DumpToLog(LogTemp);return nullptr;}
        return Save(*Tree)?Tree:nullptr;
    }
}
#endif
bool UEcoSpeciesAIAssetBuilder::CreateDefaultAssets()
{
#if WITH_EDITOR
    const FString Base=TEXT("/Game/Experiments/SpeciesAI/");
    const bool StockHeight=GetDefault<UMassNavigationSmoothHeightProcessor>()->ShouldAutoAddToGlobalList();
    UE_LOG(LogTemp,Display,TEXT("[SpeciesAI Assets] StockHeightAutoRegister=%d Expected=0"),StockHeight);
    if(StockHeight)return false;
    for(int32 Mode=0;Mode<3;++Mode)
    {
        const FString Role=Mode==0?TEXT("Deer"):Mode==1?TEXT("Wolf"):TEXT("DeerV1");
        auto* Tree=CreateTree(Base+TEXT("ST_")+Role);if(!Tree)return false;
        bool New=false;auto* P=Create<UEcoSpeciesAIProfile>(Base+TEXT("DA_")+Role,New);if(!P)return false;
        if(New)
        {
            P->bPredator=Mode==1;P->bPolicyOnly=Mode==2;P->StateTree=Tree;
            if(Mode==2)P->DecisionInterval=EcoBehaviorConfig::PolicyInterval/60.f;
            if(!Save(*P))return false;
        }
        auto* Config=Create<UEcoCreatureEntityConfig>(Base+TEXT("EC_")+Role,New);if(!Config)return false;
        if(New)
        {
            Config->ConfigureCreature(Mode==1);
            auto* Trait=const_cast<UEcoCreatureNetworkTrait*>(CastChecked<UEcoCreatureNetworkTrait>(Config->FindTrait(UEcoCreatureNetworkTrait::StaticClass())));
            Trait->bUseSpeciesAI=true;Trait->SpeciesAIProfile=P;if(!Save(*Config))return false;
        }
        FString Error;const auto* Trait=Cast<UEcoCreatureNetworkTrait>(Config->FindTrait(UEcoCreatureNetworkTrait::StaticClass()));
        if(!P->Validate(Error)||P->bPredator!=(Mode==1)||P->bPolicyOnly!=(Mode==2)||!Trait||!Trait->bUseSpeciesAI||Trait->SpeciesAIProfile!=P)
        {UE_LOG(LogTemp,Error,TEXT("[SpeciesAI Assets] Role=%s configuration mismatch: %s"),*Role,*Error);return false;}
        UE_LOG(LogTemp,Display,TEXT("[SpeciesAI Assets] Role=%s TreeReady=%d ProfileValid=1 ConfigReferenceValid=1"),*Role,Tree->IsReadyToRun());
    }
    bool New=false;auto* Slot=Create<USmartObjectDefinition>(Base+TEXT("SO_ActivitySlot"),New);
    if(!Slot)return false;
    if(New)
    {
        // Editor authoring through reflected properties, without engine private-member access.
        auto* SlotsProperty=FindFProperty<FArrayProperty>(USmartObjectDefinition::StaticClass(),TEXT("Slots"));
        auto* BehaviorsProperty=FindFProperty<FArrayProperty>(USmartObjectDefinition::StaticClass(),TEXT("DefaultBehaviorDefinitions"));
        if(!SlotsProperty||!BehaviorsProperty)return false;
        FScriptArrayHelper SlotArray(SlotsProperty,SlotsProperty->ContainerPtrToValuePtr<void>(Slot));SlotArray.AddValue();
        FScriptArrayHelper Definitions(BehaviorsProperty,BehaviorsProperty->ContainerPtrToValuePtr<void>(Slot));
        const int32 Index=Definitions.AddValue();
        CastFieldChecked<FObjectPropertyBase>(BehaviorsProperty->Inner)->SetObjectPropertyValue(Definitions.GetRawPtr(Index),NewObject<USmartObjectMassBehaviorDefinition>(Slot));
    }
    bool Repair=New;
    const auto Schema=Slot->GetWorldConditionSchemaClass();
    if(!Schema)return false;
    auto& Preconditions=Slot->GetMutablePreconditions();
    if(Preconditions.GetSchemaClass()!=Schema){Preconditions.SetSchemaClass(Schema);Repair=true;}
    for(auto& Definition:Slot->GetMutableSlots())
        if(Definition.SelectionPreconditions.GetSchemaClass()!=Schema)
        {Definition.SelectionPreconditions.SetSchemaClass(Schema);Repair=true;}
    if(!Slot->Validate())return false;
    return !Repair||Save(*Slot);
#else
    UE_LOG(LogTemp,Error,TEXT("SpeciesAI asset authoring requires an Editor build."));return false;
#endif
}
