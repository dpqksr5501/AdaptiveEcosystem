#pragma once
#include "Animation/AnimNotifies/AnimNotifyState.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "Player/EcoAttackWindowReceiver.h"
#include "EcoAttackNotifies.generated.h"
UCLASS(Abstract)
class ADAPTIVEECOSYSTEM_API UEcoAnimNotifyState_AttackWindow : public UAnimNotifyState
{
    GENERATED_BODY()
public:
    void NotifyBegin(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, float Duration, const FAnimNotifyEventReference& Ref) override;
    void NotifyEnd(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, const FAnimNotifyEventReference& Ref) override;
protected:
    EEcoAttackWindow Window = EEcoAttackWindow::Input;
};
UCLASS(meta=(DisplayName="Eco Combo Input Window"))
class ADAPTIVEECOSYSTEM_API UEcoAnimNotifyState_ComboInputWindow : public UEcoAnimNotifyState_AttackWindow { GENERATED_BODY() };
UCLASS(meta=(DisplayName="Eco Melee Hit Window"))
class ADAPTIVEECOSYSTEM_API UEcoAnimNotifyState_MeleeHitWindow : public UEcoAnimNotifyState_AttackWindow
{
    GENERATED_BODY()
public: UEcoAnimNotifyState_MeleeHitWindow() { Window = EEcoAttackWindow::Hit; }
};
UCLASS(meta=(DisplayName="Eco Combo Branch"))
class ADAPTIVEECOSYSTEM_API UEcoAnimNotify_ComboBranch : public UAnimNotify
{
    GENERATED_BODY()
public:
    void Notify(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, const FAnimNotifyEventReference& Ref) override;
};
