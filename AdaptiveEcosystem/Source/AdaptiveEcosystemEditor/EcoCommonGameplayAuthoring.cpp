#include "EcoCommonGameplayAuthoring.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"

FString UEcoCommonGameplayAuthoring::InspectBlueprint(UBlueprint* Blueprint)
{
    if (!Blueprint) return TEXT("Invalid blueprint");
    FString Result = FString::Printf(TEXT("Parent=%s\n"), *GetPathNameSafe(Blueprint->ParentClass));
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (const UEdGraph* Graph : Graphs)
    {
        Result += FString::Printf(TEXT("Graph=%s\n"), *Graph->GetName());
        for (const UEdGraphNode* Node : Graph->Nodes)
        {
            if (!Node) continue;
            Result += Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString() + TEXT("\n");
            for (const UEdGraphPin* Pin : Node->Pins)
                if (Pin) Result += FString::Printf(TEXT("  %s=%s object=%s links=%d\n"),
                    *Pin->PinName.ToString(), *Pin->DefaultValue, *GetPathNameSafe(Pin->DefaultObject), Pin->LinkedTo.Num());
        }
    }
    return Result;
}
