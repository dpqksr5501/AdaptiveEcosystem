#if WITH_DEV_AUTOMATION_TESTS && !UE_BUILD_SHIPPING
#include "Debug/EcoMoveAvoidance.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoMoveAvoidanceShadowParity,
	"AdaptiveEcosystem.Policy.V3.Movement.AvoidanceShadowParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoMoveAvoidanceShadowParity::RunTest(const FString& Parameters)
{
	using namespace EcoMoveAvoidance;
	constexpr int32 Steps = 90;
	for (const EScenario Scenario : {EScenario::HeadOn, EScenario::Crossing})
	{
		auto Run = MakeUnique<FRun>();
		Run->Init(Scenario, 20000, Steps);
		for (int32 Index = 0; Index < Steps && !Run->Mismatch && !Run->bTargetDied; ++Index) Run->Step();
		const FString Context(Name(Scenario));
		TestEqual(Context + TEXT(" retains Native trajectory and state"), Run->Mismatch, 0u);
		TestEqual(Context + TEXT(" reached intended step count"), Run->Samples.Num(), Steps);
		TestTrue(Context + TEXT(" observed risk and calculated proposals"), Run->RiskRows > 0 && Run->ChangedRows > 0);
		TestTrue(Context + TEXT(" includes a joint prediction with increased gap"),
			Run->Samples.ContainsByPredicate([](const FStepSample& S) { return S.CombinedProposalGap > S.ExistingGap + 1.e-9; }));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoMoveAvoidanceCandidateLimit,
	"AdaptiveEcosystem.Policy.V3.Movement.AvoidanceCandidateLimit",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoMoveAvoidanceCandidateLimit::RunTest(const FString& Parameters)
{
	using namespace EcoPredictiveAvoidanceV3;
	std::array<FAgent, 12> Agents{};
	Agents[0] = {1, {0., 0.}, {.24, 0.}, .15, false};
	for (int32 Index = 1; Index < 11; ++Index)
		Agents[Index] = {Index + 1, {0., 1.}, {.24, 0.}, .15, false};
	Agents[11] = {12, {1.5, 0.}, {-.24, 0.}, .25, false};
	const auto Moving = Evaluate(Agents, 0);
	TestEqual(TEXT("Candidate capacity respected"), Moving.Retained, MaxCandidates);
	TestEqual(TEXT("Remainder counted"), int32(Moving.Dropped), 3);
	TestEqual(TEXT("Closest predicted opponent retained even when encountered last"), int64(Moving.RiskId), int64(12));
	TestTrue(TEXT("Proposal improves worst retained clearance"), Moving.bChanged && Moving.ProposedGap > Moving.BaseGap);
	TestTrue(TEXT("Proposal retains forward speed magnitude"), FMath::IsNearlyEqual(std::hypot(Moving.Delta.X, Moving.Delta.Y), .24));
	Agents[0].DesiredDelta = {};
	Agents[0].bStill = true;
	const auto Still = Evaluate(Agents, 0);
	TestTrue(TEXT("Stationary agent reports a risk without being moved"),
		Still.RiskId == 12 && Still.BaseGap < 0. && !Still.bChanged && Still.Delta.X == 0. && Still.Delta.Y == 0.);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoMoveAvoidanceAppliedComparison,
	"AdaptiveEcosystem.Policy.V3.Movement.AvoidanceAppliedComparison",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoMoveAvoidanceAppliedComparison::RunTest(const FString& Parameters)
{
	using namespace EcoMoveAvoidance;
	constexpr int32 Steps = 90;
	for (const EScenario Scenario : {EScenario::HeadOn, EScenario::Graze, EScenario::Flight})
	{
		auto Run = MakeUnique<FRun>();
		Run->Init(Scenario, 20000, Steps, true);
		for (int32 Index = 0; Index < Steps && !Run->bTargetDied; ++Index) Run->Step();
		const FString Context(Name(Scenario));
		TestEqual(Context + TEXT(" completed comparison"), Run->CompletedSteps, Steps);
		TestEqual(Context + TEXT(" records both agents in both modes"), Run->AppliedSamples.Num(), 4 * Steps);
		if (const TCHAR* Reason = Run->MissingCoverage())
		{
			AddError(FString::Printf(TEXT("%s missing coverage: %s (risk_rows=%d, applied_rows=%d, detour_rows Off=%d Enabled=%d, food_eaten Off=%.6f Enabled=%.6f)"),
				*Context, Reason, Run->Enabled.RiskRows, Run->Enabled.AppliedRows, Run->Off.DetourRows, Run->Enabled.DetourRows,
				Run->Off.FoodEaten, Run->Enabled.FoodEaten));
		}
		if (const TCHAR* Reason = Run->Regression()) AddError(Context + TEXT(" regression: ") + Reason);
		TestEqual(Context + TEXT(" Off does not apply proposals"), Run->Off.AppliedRows, 0);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoMoveAvoidanceTerrainGuard,
	"AdaptiveEcosystem.Policy.V3.Movement.AvoidanceTerrainGuard",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoMoveAvoidanceTerrainGuard::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	FWorldConfig Config;
	Config.NumHerbivores = 2;
	Config.NumStalkers = Config.NumChasers = Config.NumRanged = Config.NumNocturnal = 0;
	Config.Obstacles.bEnabled = true;
	Config.Obstacles.Discs = {10.17, 10.17, .01};
	FReferenceWorld Native;
	Native.Init(Config);
	Native.Bodies[0].Pos = {10., 10.};
	Native.Bodies[1].Pos = {20., 20.};
	FStepHooks Hooks;
	Hooks.HerbControl = [](void*, int32 Index, const FHerbView& Herb)
	{
		Herb.Control->bStill = Index == 1;
		Herb.Control->Velocity = Index == 0 ? FVec2{.24, 0.} : FVec2{};
	};
	bool bSawBothBeforeMove = false;
	Hooks.User = &bSawBothBeforeMove;
	Hooks.HerbAvoidance = [](void* User, const FHerbSteeringRow* Inputs, FVec2* Deltas, int32 Count)
	{
		if (Count != 2) return;
		*static_cast<bool*>(User) = Inputs[0].Position.X == 10. && Inputs[1].Position.X == 20.;
		const double Diagonal = .24 / std::sqrt(2.);
		Deltas[0] = {Diagonal, Diagonal};
		Deltas[1] = {.24, 0.};
	};
	Step(Native.World, Native.Views.data(), Native.NumHerbivores(), nullptr, 0, EcoPolicyV3::kBuiltinNet, &Hooks);
	TestTrue(TEXT("Batch sees both pre-integration positions"), bSawBothBeforeMove);
	TestTrue(TEXT("Turn into obstacle falls back to terrain-approved direction"),
		FMath::IsNearlyEqual(Native.Bodies[0].Pos.X, 10.24) && Native.Bodies[0].Pos.Y == 10.);
	TestTrue(TEXT("Stationary deer ignores injected movement"), Native.Bodies[1].Pos.X == 20. && Native.Bodies[1].Pos.Y == 20.);
	return true;
}
#endif
