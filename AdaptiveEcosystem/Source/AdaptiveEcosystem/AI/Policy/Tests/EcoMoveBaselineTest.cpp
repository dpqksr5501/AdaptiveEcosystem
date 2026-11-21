#if WITH_DEV_AUTOMATION_TESTS && !UE_BUILD_SHIPPING
#include "Debug/EcoMoveBaseline.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoMoveBaselineParity,
	"AdaptiveEcosystem.Policy.V3.Movement.BaselineParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoMoveBaselineParity::RunTest(const FString& Parameters)
{
	constexpr int32 Steps = 8;
	auto Run = MakeUnique<EcoMoveBaseline::FRun>();
	Run->Init(EcoMoveBaseline::DefaultSeed, Steps);
	for (int32 Index = 0; Index < Steps; ++Index) Run->Step();

	TestEqual(TEXT("Initial state and every sparse step match"), Run->Sparse.Mismatch, 0u);
	TestEqual(TEXT("Initial state and every fallback step match"), Run->Small.Mismatch, 0u);
	TestTrue(TEXT("Sparse input traversed the index"), Run->Sparse.SpatialCandidates < Run->Sparse.FullCandidates);
	TestTrue(TEXT("Small input used the full scan fallback"),
		Run->Small.Queries > 0 && Run->Small.SpatialCandidates == Run->Small.FullCandidates);
	TestEqual(TEXT("Each deer has a pre-move row"), Run->Sparse.Rows.Last().PreMoveRows, EcoMoveBaseline::SparseDeer);
	TestEqual(TEXT("Rows contain initial state and eight steps"), Run->Sparse.Rows.Num(), Steps + 1);
	return true;
}
#endif
