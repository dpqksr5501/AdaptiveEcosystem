#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameSession.h"
#include "EcoGameSession.generated.h"

/** Server-side admission; the Steam lobby limit alone is not a gameplay capacity check. */
UCLASS()
class ADAPTIVEECOSYSTEM_API AEcoGameSession : public AGameSession
{
    GENERATED_BODY()
public:
    AEcoGameSession();
    virtual void InitOptions(const FString& Options) override;
    virtual FString ApproveLogin(const FString& Options) override;
    virtual bool AtCapacity(bool bSpectator) override;
};

