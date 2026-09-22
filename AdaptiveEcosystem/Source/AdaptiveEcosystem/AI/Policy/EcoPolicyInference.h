// §9.3 정책 추론 — 파이썬에서 학습한 가중치의 C++ 순전파.
//
// **이 파일은 의도적으로 언리얼에 의존하지 않는다.**
// `<cmath>` 만 쓰므로 엔진 없이도 컴파일된다. 덕분에 파이썬과의 수치 일치(§9.8-1)를
// UE 빌드 없이 gcc 하나로 검증할 수 있고, 같은 파일이 UE 자동화 테스트에서도 그대로
// 돈다. `FMath::Tanh` 는 내부적으로 `tanhf` 를 부르므로 결과가 같다.
//
// 검증: herbivore_rl/tests/test_export.py 가 gcc로 컴파일해 골든 벡터 100쌍을
//       1e-5 이내로 대조한다.
//
// 가중치 레이아웃 (§8.1, export_weights.py 가 생성):
//   W0[j*7  + i]   Linear 7  -> 64
//   W1[j*64 + i]   Linear 64 -> 64
//   W2[j*64 + i]   Linear 64 -> 4
//
// 출력 후처리 순서는 §3.2 / §8.1 계약이다: clamp(-3,3) -> sigmoid.
// 파이썬 쪽에서는 SB3 `predict()` 가 action_space 경계로 clip해 주므로
// `sigmoid(model.predict(obs, deterministic=True)[0])` 가 이와 같다.

#pragma once

#include <cmath>

#include "PolicyWeights.h"

namespace EcoPolicy
{
	static constexpr int ObsDim = 7;    // §3.1
	static constexpr int ActDim = 4;    // §3.2
	static constexpr int HiddenDim = 64;
	static constexpr float ActionClamp = 3.0f;

	inline float Sigmoid(float X)
	{
		return 1.0f / (1.0f + std::exp(-X));
	}

	inline float Clamp3(float X)
	{
		return X < -ActionClamp ? -ActionClamp : (X > ActionClamp ? ActionClamp : X);
	}

	/**
	 * 관측 7개 -> 행동 가중치 4개 (forage, cohesion, flee_dist, cover), 전부 [0,1].
	 *
	 * 정책은 이동 방향을 정하지 않는다. 조향 가중치만 낸다 (§0).
	 * 실제 속도는 SteeringProcessor 가 §3.3 수식으로 계산한다.
	 */
	inline void RunPolicy(const float Obs[ObsDim], float Out[ActDim])
	{
		float H1[HiddenDim];
		float H2[HiddenDim];

		for (int j = 0; j < HiddenDim; ++j)
		{
			float S = B0[j];
			for (int i = 0; i < ObsDim; ++i)
			{
				S += Obs[i] * W0[j * ObsDim + i];
			}
			H1[j] = std::tanh(S);
		}

		for (int j = 0; j < HiddenDim; ++j)
		{
			float S = B1[j];
			for (int i = 0; i < HiddenDim; ++i)
			{
				S += H1[i] * W1[j * HiddenDim + i];
			}
			H2[j] = std::tanh(S);
		}

		for (int j = 0; j < ActDim; ++j)
		{
			float S = B2[j];
			for (int i = 0; i < HiddenDim; ++i)
			{
				S += H2[i] * W2[j * HiddenDim + i];
			}
			Out[j] = Sigmoid(Clamp3(S));
		}
	}

	/** §5.1 Utility AI 비교군. 구현은 EcoPolicyInference.cpp. */
	void RunUtilityPolicy(const float Obs[ObsDim], float Out[ActDim]);

	/** 빌드 앵커 겸 스키마 버전. */
	int GetPolicySchemaVersion();
}
