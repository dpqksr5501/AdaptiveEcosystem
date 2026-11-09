#include "Player/EcoGameplayAbility_MeleeStrike.h"
#include "Player/EcoCombatActionExecutor.h"
#include "GameFramework/Actor.h"

UEcoGameplayAbility_MeleeStrike::UEcoGameplayAbility_MeleeStrike()
{
    NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::ServerOnly;
    NetSecurityPolicy = EGameplayAbilityNetSecurityPolicy::ServerOnlyTermination;
    InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;
}

void UEcoGameplayAbility_MeleeStrike::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
    const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo,
    const FGameplayEventData* TriggerEventData)
{
    bool bAccepted = false;
    if (auto* Avatar = ActorInfo->AvatarActor.Get(); Avatar && Avatar->HasAuthority())
    {
        for (auto* Component : Avatar->GetComponents())
        {
            if (auto* Executor = Cast<IEcoCombatActionExecutor>(Component))
            {
                bAccepted = Executor->TryQueueMeleeStrike();
                break;
            }
        }
    }

    EndAbility(Handle, ActorInfo, ActivationInfo, true, !bAccepted);
}
