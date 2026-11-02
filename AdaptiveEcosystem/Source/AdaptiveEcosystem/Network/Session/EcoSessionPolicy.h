#pragma once

#include "CoreMinimal.h"

namespace EcoSessionPolicy
{
    // Increment whenever our advertised/session handshake or client payload contract becomes incompatible.
    inline constexpr int32 ProtocolVersion = 1;
    inline constexpr int32 DefaultRemoteClients = 10;
    inline constexpr int32 DefaultTotalPlayers = DefaultRemoteClients + 1;

    inline bool IsCompatible(const FString& Tag, int32 Protocol, const FString& Map,
                             const FString& ExpectedTag, const FString& ExpectedMap)
    {
        return Tag == ExpectedTag && Protocol == ProtocolVersion && Map == ExpectedMap;
    }

    inline FString RoomName(FString Name)
    {
        Name.TrimStartAndEndInline();
        Name = Name.Left(64);
        Name.ReplaceInline(TEXT("\r"), TEXT(" "));
        Name.ReplaceInline(TEXT("\n"), TEXT(" "));
        Name.ReplaceInline(TEXT("\t"), TEXT(" "));
        return Name.IsEmpty() ? TEXT("Adaptive Ecosystem") : Name;
    }
}

