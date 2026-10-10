#include "Creature/Audio/EcoAnimNotifyFootstep.h"
#include "Creature/Audio/EcoFootstepAudioComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"

void UEcoAnimNotifyFootstep::Notify(USkeletalMeshComponent* Mesh, UAnimSequenceBase* Animation, const FAnimNotifyEventReference& Reference)
{
    if (!Mesh || !Mesh->GetWorld() || !Mesh->GetWorld()->IsGameWorld() || !Mesh->GetOwner()) return;
    if (auto* Audio = Mesh->GetOwner()->FindComponentByClass<UEcoFootstepAudioComponent>()) Audio->NotifyContact(Mesh, FootBone);
}
