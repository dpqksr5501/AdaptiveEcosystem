#include "Player/EcoAttackNotifies.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
namespace
{
void Send(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, EEcoAttackWindow Window, bool bOpen)
{
    if (!Mesh || !Mesh->GetOwner() || !Mesh->GetWorld()->IsGameWorld()) return;
    for (auto* Component : Mesh->GetOwner()->GetComponents())
        if (auto* Receiver = Cast<IEcoAttackWindowReceiver>(Component)) Receiver->ReceiveAttackWindow(Window, bOpen, Animation);
}
}
void UEcoAnimNotifyState_AttackWindow::NotifyBegin(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, float Duration, const FAnimNotifyEventReference& Ref) { Send(Mesh, Animation, Window, true); }
void UEcoAnimNotifyState_AttackWindow::NotifyEnd(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, const FAnimNotifyEventReference& Ref) { Send(Mesh, Animation, Window, false); }
void UEcoAnimNotify_ComboBranch::Notify(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, const FAnimNotifyEventReference& Ref) { Send(Mesh, Animation, EEcoAttackWindow::Branch, true); }
