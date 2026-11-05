#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "EcoSessionSettings.generated.h"

/** Session discovery rules. Ecology and policy settings remain owned by their existing systems. */
UCLASS(Config=Game, DefaultConfig, meta=(DisplayName="Adaptive Ecosystem Multiplayer"))
class ADAPTIVEECOSYSTEM_API UEcoSessionSettings : public UDeveloperSettings
{
    GENERATED_BODY()
public:
    UPROPERTY(Config, EditAnywhere, Category="Session", meta=(ClampMin="1", ClampMax="64"))
    int32 MaxRemoteClients = 10;
    UPROPERTY(Config, EditAnywhere, Category="Session")
    FString GameplayMap = TEXT("/Game/JWJ/Integration_JwJ");
    UPROPERTY(Config, EditAnywhere, Category="Session")
    FString DiscoveryTag = TEXT("AdaptiveEcosystem.JWJ");
    UPROPERTY(Config, EditAnywhere, Category="Session", meta=(ClampMin="1", ClampMax="200"))
    int32 MaxSearchResults = 100;
    UPROPERTY(Config, EditAnywhere, Category="Session", meta=(ClampMin="10", ClampMax="180"))
    float OperationTimeoutSeconds = 45.f;
    UPROPERTY(Config, EditAnywhere, Category="Menu")
    bool bShowMenuOnStandaloneStart = true;

    int32 TotalPlayers(bool bDedicated) const { return FMath::Clamp(MaxRemoteClients, 1, 64) + (bDedicated ? 0 : 1); }
};

