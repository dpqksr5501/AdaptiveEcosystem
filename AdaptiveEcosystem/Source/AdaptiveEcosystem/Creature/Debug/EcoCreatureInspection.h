#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "GameFramework/HUD.h"
#include "EcoCreatureInspection.generated.h"
class AEcoCreatureRepresentationActor;

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoCreatureInspectionLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Read-only authority inventory for diagnostics; clients always return an empty list. */
    UFUNCTION(BlueprintCallable,Category="Creature|Inspection",meta=(WorldContext="WorldContext"))
    static TArray<int64> GetAuthorityAgentIds(UObject* WorldContext);
    UFUNCTION(BlueprintCallable,Category="Creature|Inspection",meta=(WorldContext="WorldContext"))
    static bool CaptureAgent(UObject* WorldContext,int64 AgentId,FString& Json);
};

/** Local read-only inspection. Tab cycles; middle mouse picks under crosshair; R records JSONL. */
UCLASS()
class ADAPTIVEECOSYSTEM_API AEcoCreatureInspectorHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
private:
    TWeakObjectPtr<AEcoCreatureRepresentationActor> Selected;
    int64 SelectedId=0;
    bool bRecording=false;
    double NextRecord=0;
    FString RecordPath;
    double NextInspection=0;
    FString InspectionJson;
    FString InspectionDetail;
};
