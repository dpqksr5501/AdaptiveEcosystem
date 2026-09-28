// §9.8-1 파리티 자동화 테스트 — 엔진 **안에서** 파이썬 출력과 대조한다.
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy"
//                        -unattended -nopause -nosplash -NullRHI
//                        -testexit="Automation Test Queue Empty"
//
// 골든 벡터는 `PolicyGoldenVectors.h` 에 배열로 박혀 있다 (export_weights.py 생성).
// 파일 I/O가 없으므로 레벨도, 에셋도, 월드도 필요 없다 — 순수 수치 검증이다.
//
// 이 테스트가 통과하면 "파이썬에서 학습한 정책이 언리얼에서 같은 행동을 낸다"가
// 엔진 런타임에서 증명된 것이다.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoBehaviorConfig.h"
#include "../EcoPolicyInference.h"
#include "../EcoSteering.h"
#include "../PolicyGoldenVectors.h"
#include "../SteeringGoldenVectors.h"
#include "../UtilityParams.h"

namespace
{
	// §8.2 / §9.8-1 허용 오차
	constexpr float kTolerance = 1.0e-5f;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyGoldenVectorTest,
	"AdaptiveEcosystem.Policy.GoldenVectorParity",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyGoldenVectorTest::RunTest(const FString& Parameters)
{
	float MaxError = 0.0f;
	int32 WorstVector = INDEX_NONE;
	int32 WorstAction = INDEX_NONE;

	for (int32 n = 0; n < kGoldenCount; ++n)
	{
		float Out[EcoPolicy::ActDim];
		EcoPolicy::RunPolicy(&kGoldenObs[n * EcoPolicy::ObsDim], Out);

		for (int32 j = 0; j < EcoPolicy::ActDim; ++j)
		{
			const float Expected = kGoldenExpected[n * EcoPolicy::ActDim + j];
			const float Error = FMath::Abs(Out[j] - Expected);
			if (Error > MaxError)
			{
				MaxError = Error;
				WorstVector = n;
				WorstAction = j;
			}
		}
	}

	AddInfo(FString::Printf(
		TEXT("골든 벡터 %d쌍, 최대 오차 %.3e (벡터 %d, 행동 %d)"),
		kGoldenCount, MaxError, WorstVector, WorstAction));

	TestTrue(
		FString::Printf(TEXT("최대 오차 %.3e 가 허용치 %.0e 이내여야 한다"),
						MaxError, kTolerance),
		MaxError <= kTolerance);

	return true;
}

/** 출력이 §3.2 계약대로 [0,1] 안에 있는가. clamp/sigmoid 순서가 깨지면 여기서 걸린다. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyOutputRangeTest,
	"AdaptiveEcosystem.Policy.OutputRange",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyOutputRangeTest::RunTest(const FString& Parameters)
{
	// clamp(-3,3) 뒤 sigmoid 이므로 출력은 이 범위를 벗어날 수 없다.
	const float Lo = EcoPolicy::Sigmoid(-EcoPolicy::ActionClamp);
	const float Hi = EcoPolicy::Sigmoid(EcoPolicy::ActionClamp);

	for (int32 n = 0; n < kGoldenCount; ++n)
	{
		float Out[EcoPolicy::ActDim];
		EcoPolicy::RunPolicy(&kGoldenObs[n * EcoPolicy::ObsDim], Out);
		for (int32 j = 0; j < EcoPolicy::ActDim; ++j)
		{
			TestTrue(FString::Printf(TEXT("Out[%d][%d]=%f 가 [%f, %f] 안"), n, j, Out[j], Lo, Hi),
					 Out[j] >= Lo - KINDA_SMALL_NUMBER && Out[j] <= Hi + KINDA_SMALL_NUMBER);
		}
	}
	return true;
}

/** §5.1 Utility 비교군이 파이썬 수식과 같은 값을 내는가. 계수는 자동 생성 헤더에서 온다. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoUtilityPolicyTest,
	"AdaptiveEcosystem.Policy.UtilityBaseline",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoUtilityPolicyTest::RunTest(const FString& Parameters)
{
	for (int32 n = 0; n < kGoldenCount; ++n)
	{
		const float* Obs = &kGoldenObs[n * EcoPolicy::ObsDim];
		float Out[EcoPolicy::ActDim];
		EcoPolicy::RunUtilityPolicy(Obs, Out);

		// §5.1 을 여기서 다시 써서 대조한다. 구현이 흔들리면 걸린다.
		const float Expected[EcoPolicy::ActDim] = {
			FMath::Clamp(EcoUtilityParams::K_forage * (1.0f - Obs[4]), 0.0f, 1.0f),
			FMath::Clamp(EcoUtilityParams::K_coh * Obs[5], 0.0f, 1.0f),
			FMath::Clamp(EcoUtilityParams::Flee_base + EcoUtilityParams::Flee_k * Obs[5],
						 0.0f, 1.0f),
			FMath::Clamp(EcoUtilityParams::K_cover * Obs[1], 0.0f, 1.0f),
		};

		for (int32 j = 0; j < EcoPolicy::ActDim; ++j)
		{
			TestEqual(FString::Printf(TEXT("Utility[%d][%d]"), n, j), Out[j], Expected[j],
					  kTolerance);
			TestTrue(FString::Printf(TEXT("Utility[%d][%d] 가 [0,1]"), n, j),
					 Out[j] >= 0.0f && Out[j] <= 1.0f);
		}
	}
	return true;
}

/**
 * §9.8-2 — 조향 단독. 같은 기하 입력에 파이썬 `steer()` 와 C++ 출력이 일치하는가.
 *
 * 골든은 파이썬 격자 단위로 만들었다. 검증 대상이 §3.3 수식이지 단위 변환이 아니라서,
 * 헤더에 같이 박힌 `kSteer*` 설정값을 그대로 쓴다.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoSteeringParityTest,
	"AdaptiveEcosystem.Policy.SteeringParity",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoSteeringParityTest::RunTest(const FString& Parameters)
{
	EcoPolicy::FSteerConfig Cfg;
	Cfg.SeeRadius = kSteerSeeRadius;
	Cfg.SepWeight = kSteerSepWeight;
	Cfg.FleeWeight = kSteerFleeWeight;
	Cfg.HerbSpeed = kSteerHerbSpeed;

	float MaxError = 0.0f;
	int32 FleeSamples = 0;

	for (int32 n = 0; n < kSteerGoldenCount; ++n)
	{
		const float* In = &kSteerGoldenInput[n * 11];
		EcoPolicy::FSteerInput G;
		G.FoodGrad[0] = In[0];      G.FoodGrad[1] = In[1];
		G.ToCentroid[0] = In[2];    G.ToCentroid[1] = In[3];
		G.ToCover[0] = In[4];       G.ToCover[1] = In[5];
		G.Separation[0] = In[6];    G.Separation[1] = In[7];
		G.AwayFromPred[0] = In[8];  G.AwayFromPred[1] = In[9];
		G.DistPredMin = In[10];

		const float* A = &kSteerGoldenAction[n * 4];
		if (G.DistPredMin < A[2] * Cfg.SeeRadius)
		{
			++FleeSamples;
		}

		float Out[2];
		EcoPolicy::Steer(G, A, Cfg, Out);
		for (int32 j = 0; j < 2; ++j)
		{
			MaxError = FMath::Max(MaxError,
								  FMath::Abs(Out[j] - kSteerGoldenExpected[n * 2 + j]));
		}
	}

	AddInfo(FString::Printf(TEXT("조향 골든 %d쌍 (도주 분기 %d), 최대 오차 %.3e"),
							kSteerGoldenCount, FleeSamples, MaxError));

	// 두 분기가 다 밟히지 않으면 도주 항이 검증되지 않은 것이다.
	TestTrue(TEXT("도주 분기가 켜진 표본이 있어야 한다"), FleeSamples > 0);
	TestTrue(TEXT("도주 분기가 꺼진 표본도 있어야 한다"), FleeSamples < kSteerGoldenCount);
	TestTrue(FString::Printf(TEXT("최대 오차 %.3e <= %.0e"), MaxError, kTolerance),
			 MaxError <= kTolerance);
	return true;
}

/** §9.7 단위 대응이 자동 생성 헤더에 제대로 들어왔는가. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoBehaviorConfigTest,
	"AdaptiveEcosystem.Policy.BehaviorConfigUnits",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoBehaviorConfigTest::RunTest(const FString& Parameters)
{
	// §9.7: SeeRadius = see_r × GridUnitCm, 그리고 조향 골든은 격자 단위 see_r 을 쓴다.
	const float ExpectedSeeRadiusCm = kSteerSeeRadius * EcoBehaviorConfig::GridUnitCm;
	TestEqual(TEXT("SeeRadiusCm = see_r × GridUnitCm"),
			  EcoBehaviorConfig::SeeRadiusCm, ExpectedSeeRadiusCm, 0.01f);

	// §3.3 조향 계수는 파이썬과 같은 값이어야 한다.
	TestEqual(TEXT("SepWeight"), EcoBehaviorConfig::SepWeight, kSteerSepWeight, 1e-6f);
	TestEqual(TEXT("FleeWeight"), EcoBehaviorConfig::FleeWeight, kSteerFleeWeight, 1e-6f);

	// §9.7: HerbSpeed = herb_speed × GridUnitCm ÷ (PolicyInterval/60)
	const float ExpectedHerbSpeed = kSteerHerbSpeed * EcoBehaviorConfig::GridUnitCm
								  / (EcoBehaviorConfig::PolicyInterval / 60.0f);
	TestEqual(TEXT("HerbSpeedCmS = herb_speed × GridUnitCm ÷ (PolicyInterval/60)"),
			  EcoBehaviorConfig::HerbSpeedCmS, ExpectedHerbSpeed, 0.01f);

	// §1.2 관측 정규화는 고정 상수다.
	TestEqual(TEXT("ObsPredCountNorm"), EcoBehaviorConfig::ObsPredCountNorm, 8.0f, 1e-6f);
	TestEqual(TEXT("ObsKinCountNorm"), EcoBehaviorConfig::ObsKinCountNorm, 20.0f, 1e-6f);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
