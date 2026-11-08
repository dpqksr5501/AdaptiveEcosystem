#pragma once
#include "Components/ActorComponent.h"
#include "Player/EcoDamageReceiver.h"
#include "EcoGASDamageReceiverComponent.generated.h"
UCLASS(ClassGroup=(Combat),meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoGASDamageReceiverComponent : public UActorComponent, public IEcoDamageReceiver
{
    GENERATED_BODY()
public:
    bool SubmitPointDamage_Implementation(const FEcoPointDamage& Request) override;
};
