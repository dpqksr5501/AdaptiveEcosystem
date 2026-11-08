#include "Misc/AutomationTest.h"
#include "Network/EcoClockSchedule.h"
#include "World/EcoWorldClockSubsystem.h"
#include <limits>

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoCommonClockScheduleTest, "AdaptiveEcosystem.CommonGameplay.ClockSchedule",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoCommonClockScheduleTest::RunTest(const FString&)
{
    FEcoClockSchedule S;
    S.Sample.WorldEpoch = 7; S.Sample.ServerTimeSeconds = 8; S.ServerWorldSeconds = 100;
    for (double T : {8.0, 10.0, 30.0, 40.0})
    {
        FEcoDayCycleState Phase; EcoClock::EvaluateFixedCycle(T, 10, 20, Phase); S.Phases.Add(Phase);
    }
    FEcoServerTimeSnapshot A;
    TestTrue(TEXT("Before boundary"), S.Evaluate(101.99, A));
    TestEqual(TEXT("Still day"), A.DayCycle.Phase, EEcoDayPhase::Day);
    TestTrue(TEXT("Exact boundary"), S.Evaluate(102, A));
    TestEqual(TEXT("Night at scheduled time"), A.DayCycle.Phase, EEcoDayPhase::Night);
    TestTrue(TEXT("Late join reconstructs current phase"), S.Evaluate(125, A));
    TestEqual(TEXT("Late join cycle"), A.DayCycle.CycleId, int64(1));
    TestEqual(TEXT("Epoch preserved"), A.WorldEpoch, 7);
    TestFalse(TEXT("Expired schedule rejected"), S.Evaluate(200, A));
    TestFalse(TEXT("NaN rejected"), S.Evaluate(std::numeric_limits<double>::quiet_NaN(), A));
    S.Rate = 0;
    TestTrue(TEXT("Stopped clock holds state"), S.Evaluate(200, A));
    TestEqual(TEXT("Stopped time"), A.ServerTimeSeconds, 8.0);
    S.Rate = -1;
    TestFalse(TEXT("Invalid rate"), S.Evaluate(101, A));
    S.Rate = 1; S.Sample.WorldEpoch = 0;
    TestFalse(TEXT("Uninitialized epoch"), S.Evaluate(101, A));
    return true;
}
#endif
