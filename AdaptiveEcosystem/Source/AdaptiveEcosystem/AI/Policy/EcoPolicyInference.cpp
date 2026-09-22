// §9.3 정책 추론 구현.
//
// `RunPolicy` 는 헤더에 inline으로 있다 (엔진 없이도 컴파일되게 하기 위해서다 —
// `EcoPolicyInference.h` 주석 참조). 이 파일은
//   1) 그 헤더를 실제 UE 빌드에서 한 번은 컴파일시키는 앵커이고,
//   2) §5.1 Utility AI 비교군을 C++로 옮긴 `RunUtilityPolicy` 를 담는다.
//
// §0: 학습 정책과 비교군이 **같은 관측·행동·조향**을 써야 한다. 그래서 두 함수의
// 시그니처가 같다. 콘솔 변수로 갈아끼우기만 하면 된다 (§9.4).

#include "EcoPolicyInference.h"

#include "UtilityParams.h"

namespace EcoPolicy
{
	namespace
	{
		inline float Clamp01(float X)
		{
			return X < 0.0f ? 0.0f : (X > 1.0f ? 1.0f : X);
		}
	}

	/**
	 * §5.1 Utility AI 비교군. 파이썬 `policies/utility.py: utility_policy()` 와 한 줄씩 대응한다.
	 *
	 *   forage    = clip(k_forage * (1 - energy))
	 *   cohesion  = clip(k_coh * recent_predation)
	 *   flee_dist = clip(flee_base + flee_k * recent_predation)
	 *   cover     = clip(k_cover * predator_count)
	 *
	 * 계수는 `UtilityParams.h` (§5.2 튜닝 산출물에서 자동 생성). 손으로 적지 않는다 —
	 * 여기와 파이썬이 갈라지면 비교 자체가 무의미해진다 (§12).
	 *
	 * 주의: `food_density`, `predator_distance`, `cover_distance` 는 쓰지 않는다.
	 * §5.1이 그렇게 정의했고, 항을 더하면 비교군이 달라진다.
	 */
	void RunUtilityPolicy(const float Obs[ObsDim], float Out[ActDim])
	{
		const float PredatorCount = Obs[1];
		const float Energy = Obs[4];
		const float RecentPredation = Obs[5];

		Out[0] = Clamp01(EcoUtilityParams::K_forage * (1.0f - Energy));
		Out[1] = Clamp01(EcoUtilityParams::K_coh * RecentPredation);
		Out[2] = Clamp01(EcoUtilityParams::Flee_base
						 + EcoUtilityParams::Flee_k * RecentPredation);
		Out[3] = Clamp01(EcoUtilityParams::K_cover * PredatorCount);
	}

	/** 빌드에서 헤더가 실제로 인스턴스화되는지 확인하는 앵커. */
	int GetPolicySchemaVersion()
	{
		float Probe[ActDim] = {0.0f, 0.0f, 0.0f, 0.0f};
		const float Zero[ObsDim] = {0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f};
		RunPolicy(Zero, Probe);
		return 1;   // PolicySchemaVersion. EcoPolicyContracts.h 와 맞춘다.
	}
}
