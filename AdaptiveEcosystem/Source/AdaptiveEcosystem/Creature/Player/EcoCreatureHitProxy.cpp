#include "Creature/Player/EcoCreatureHitProxy.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Components/CapsuleComponent.h"

AEcoCreatureHitProxy::AEcoCreatureHitProxy()
{
    bReplicates = false;
    PrimaryActorTick.bCanEverTick = false;
    Shape = CreateDefaultSubobject<UCapsuleComponent>(TEXT("HitShape"));
    SetRootComponent(Shape);
    Shape->SetCollisionObjectType(ECC_WorldDynamic);
    Shape->SetCollisionResponseToAllChannels(ECR_Ignore);
    Shape->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Shape->SetGenerateOverlapEvents(false);
    SetActorHiddenInGame(true);
}
void AEcoCreatureHitProxy::Bind(AEcoCreatureIntegrationSpawner* InOwner, int32 Epoch, int64 Id)
{
    ClearBinding();
    if (GetNetMode() == NM_Client || !InOwner || Epoch <= 0 || Id <= 0) return;
    Coordinator = InOwner; WorldEpoch = Epoch; StableAgentId = Id;
    Shape->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
}
void AEcoCreatureHitProxy::ClearBinding()
{
    Shape->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    StableAgentId = 0; WorldEpoch = 0; Coordinator.Reset(); ++BindingGeneration;
}
void AEcoCreatureHitProxy::Sync(const FVector& GroundPosition, float BodyScale, bool bPredator)
{
    const float Scale = FMath::Clamp(BodyScale, .25f, 2.f);
    const float HalfHeight = (bPredator ? 52.f : 80.f) * Scale;
    Shape->SetCapsuleSize((bPredator ? 48.f : 42.f) * Scale, HalfHeight);
    SetActorLocation(GroundPosition + FVector(0, 0, HalfHeight), false, nullptr, ETeleportType::TeleportPhysics);
}
