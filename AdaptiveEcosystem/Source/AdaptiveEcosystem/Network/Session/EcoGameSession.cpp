#include "Network/Session/EcoGameSession.h"
#include "Network/Session/EcoSessionPolicy.h"
#include "Network/Session/EcoSessionSettings.h"
#include "Engine/World.h"
#include "GameFramework/GameModeBase.h"
#include "Kismet/GameplayStatics.h"

AEcoGameSession::AEcoGameSession()
{
    MaxPlayers = EcoSessionPolicy::DefaultTotalPlayers;
    MaxSpectators = 0;
}

void AEcoGameSession::InitOptions(const FString& Options)
{
    Super::InitOptions(Options);
    MaxPlayers = GetDefault<UEcoSessionSettings>()->TotalPlayers(GetNetMode() == NM_DedicatedServer);
}

FString AEcoGameSession::ApproveLogin(const FString& Options)
{
    // Direct legacy integration fixtures remain supported. Advertised sessions require our version.
    if (GetWorld() && GetWorld()->URL.HasOption(TEXT("EcoSession")))
    {
        if (UGameplayStatics::GetIntOption(Options, TEXT("EcoProtocol"), -1) != EcoSessionPolicy::ProtocolVersion)
            return TEXT("ECO_INCOMPATIBLE_PROTOCOL");
        if (UGameplayStatics::HasOption(Options, TEXT("SpectatorOnly")))
            return TEXT("ECO_SPECTATORS_DISABLED");
    }
    return Super::ApproveLogin(Options);
}

bool AEcoGameSession::AtCapacity(bool bSpectator)
{
    if (bSpectator) return true;
    AGameModeBase* Mode = GetWorld() ? GetWorld()->GetAuthGameMode() : nullptr;
    // Do not let a console override or a client's travel option bypass the configured admission limit.
    return Mode && GetNetMode() != NM_Standalone && Mode->GetNumPlayers() >= MaxPlayers;
}

