#pragma once
#include "CoreMinimal.h"
#include "AnimGraphNode_SkeletalControlBase.h"
#include "Creature/Representation/EcoGroundFeetNode.h"
#include "EcoGroundFeetGraphNode.generated.h"
UCLASS()
class UAnimGraphNode_EcoGroundFeet : public UAnimGraphNode_SkeletalControlBase {
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere,Category="Settings") FAnimNode_EcoGroundFeet Node;
    virtual FText GetNodeTitle(ENodeTitleType::Type) const override {return NSLOCTEXT("EcoIK","Title","Eco Ground Feet (pre-IK pose)");}
protected:
    virtual const FAnimNode_SkeletalControlBase* GetNode() const override {return &Node;}
    virtual FText GetControllerDescription() const override {return NSLOCTEXT("EcoIK","Description","Ground contact with rig-specific limb chains");}
};
