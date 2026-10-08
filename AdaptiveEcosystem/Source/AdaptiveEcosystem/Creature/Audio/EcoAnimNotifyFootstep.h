#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "EcoAnimNotifyFootstep.generated.h"

/** Local audible contact only. Never emits authoritative AI noise or writes movement. */
UCLASS(meta=(DisplayName="Eco Foot Contact"))
class ADAPTIVEECOSYSTEM_API UEcoAnimNotifyFootstep : public UAnimNotify
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Footstep") FName FootBone;
    virtual void Notify(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, const FAnimNotifyEventReference& Reference) override;
    virtual FString GetNotifyName_Implementation() const override { return TEXT("EcoFootContact"); }
};
