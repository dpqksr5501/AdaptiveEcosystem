#include "Player/EcoAttackNotifies.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
namespace
{
void Send(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, EEcoAttackWindow Window, bool bOpen)
{
    auto* Owner = Mesh ? Mesh->GetOwner() : nullptr;
    if (!Owner || !Owner->GetWorld() || !Owner->GetWorld()->IsGameWorld()) return;
    // A receiver can create or remove components while handling this notify.
    TInlineComponentArray<UActorComponent*> Components;
    Owner->GetComponents(Components);
    for (auto* Component : Components)
        if (IsValid(Component) && Owner->GetComponents().Contains(Component))
            if (auto* Receiver = Cast<IEcoAttackWindowReceiver>(Component))
                Receiver->ReceiveAttackWindow(Window, bOpen, Animation);
}
}
void UEcoAnimNotifyState_AttackWindow::NotifyBegin(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, float Duration, const FAnimNotifyEventReference& Ref) { Send(Mesh, Animation, Window, true); }
void UEcoAnimNotifyState_AttackWindow::NotifyEnd(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, const FAnimNotifyEventReference& Ref) { Send(Mesh, Animation, Window, false); }
void UEcoAnimNotify_ComboBranch::Notify(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, const FAnimNotifyEventReference& Ref) { Send(Mesh, Animation, EEcoAttackWindow::Branch, true); }
