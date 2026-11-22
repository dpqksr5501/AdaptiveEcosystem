#include "Misc/AutomationTest.h"
#include "Network/Session/EcoSessionPolicy.h"
#include "Network/Session/EcoSessionSettings.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSessionAdmissionPolicyTest,"AdaptiveEcosystem.Network.Session.CapacityAndCompatibility",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoSessionAdmissionPolicyTest::RunTest(const FString&)
{
    const auto* Settings=GetDefault<UEcoSessionSettings>();
    TestEqual(TEXT("Ten remote clients plus listen host"),Settings->TotalPlayers(false),11);
    TestEqual(TEXT("Dedicated has no local host slot"),Settings->TotalPlayers(true),10);
    const FString Tag=TEXT("AdaptiveEcosystem.JWJ"), Map=TEXT("/Game/JWJ/Integration_JwJ");
    constexpr int32 Protocol = EcoSessionPolicy::ProtocolVersion;
    TestTrue(TEXT("Matching session"),EcoSessionPolicy::IsCompatible(Tag,Protocol,Map,Tag,Map));
    TestFalse(TEXT("Other game with App ID 480"),EcoSessionPolicy::IsCompatible(TEXT("Other"),Protocol,Map,Tag,Map));
    TestFalse(TEXT("Protocol mismatch"),EcoSessionPolicy::IsCompatible(Tag,Protocol-1,Map,Tag,Map));
    TestFalse(TEXT("Map mismatch"),EcoSessionPolicy::IsCompatible(Tag,Protocol,TEXT("/Game/Other"),Tag,Map));
    TestEqual(TEXT("Room name fallback"),EcoSessionPolicy::RoomName(TEXT(" \r\n ")),FString(TEXT("Adaptive Ecosystem")));
    TestEqual(TEXT("Bounded room name"),EcoSessionPolicy::RoomName(FString::ChrN(200,TEXT('A'))).Len(),64);
    return true;
}
#endif
