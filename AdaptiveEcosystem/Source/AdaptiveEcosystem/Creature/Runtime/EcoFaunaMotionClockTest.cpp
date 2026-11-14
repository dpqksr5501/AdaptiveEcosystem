#include "Creature/Runtime/EcoFaunaMotionClock.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaMotionClockTest, "AdaptiveEcosystem.Fauna.MotionClock.FramePartition",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoFaunaMotionClockTest::RunTest(const FString&)
{
    using namespace EcoFaunaMotionClock;
    const auto Boundaries = [](float GameFrameDelta, int32 Frames)
    {
        TArray<double> Result;
        double WorldTime = 0.;
        int64 LastCompleted = 0;
        for (int32 Frame = 0; Frame < Frames; ++Frame)
        {
            WorldTime += GameFrameDelta;
            const int64 LastReady = CompletedStepAt(WorldTime);
            for (int32 Slice = 0; Slice < MaxStepsPerFrame && LastCompleted < LastReady; ++Slice)
                Result.Add(StepTime(++LastCompleted));
        }
        return Result;
    };
    const auto Baseline = Boundaries(1.f / 60.f, 60 * 120);
    const auto Accelerated = Boundaries(4.f / 30.f, 30 * 30);
    TestEqual(TEXT("Two game minutes at 60 Hz"), Baseline.Num(), 7200);
    TestTrue(TEXT("Four times acceleration at 30 FPS reaches the identical boundary sequence"),
        Baseline == Accelerated);

    const auto LongFrame = Boundaries(.5f, 1);
    TestEqual(TEXT("A large frame spends only the work budget"), LongFrame.Num(), MaxStepsPerFrame);
    TestTrue(TEXT("Remaining whole steps stay available after the work budget"),
        CompletedStepAt(.5) > CompletedStepAt(StepTime(MaxStepsPerFrame)));
    TestEqual(TEXT("Sub-step remainder is preserved by storing world time"),
        CompletedTimeAt(3.01), 3.);
    TestEqual(TEXT("A contact substep does not consume its enclosing boundary"),
        CompletedStepAt(3.01) + 1, int64(181));
    return true;
}
#endif
