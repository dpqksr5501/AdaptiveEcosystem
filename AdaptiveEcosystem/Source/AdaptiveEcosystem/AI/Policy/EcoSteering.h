// §3.3 조향 수식 — 파이썬 `herbivore_rl/env/steering.py` 의 C++ 대응.
//
// **의도적으로 언리얼에 의존하지 않는다** (EcoPolicyInference.h 와 같은 이유).
// FVector 대신 float[2] 를 쓰므로 엔진 없이 gcc 로 컴파일되고, 그래서 §9.8-2
// ("조향 단독 — 같은 기하 입력에 파이썬 steer() 와 C++ 출력 일치")를 UE 빌드 없이
// 검증할 수 있다. 같은 함수가 UE 자동화 테스트와 SteeringProcessor 에서도 돈다.
//
// §1.5: 이 수식은 파이썬과 **한 줄씩 대응**해야 한다. 계수 하나도 임의로 바꾸지 않는다.
//
// 파이썬 원본:
//     v  = a[:, 0:1] * g["food_grad"]
//     v += a[:, 1:2] * g["to_centroid"]
//     v += a[:, 3:4] * g["to_cover"]
//     v += 1.35 * g["separation"]
//     fleeing = g["d_pred_min"] < a[:, 2] * cfg.see_r
//     v[fleeing] += g["away_from_pred"][fleeing] * 3.0
//     return normalize(v) * cfg.herb_speed
//
// 경계 반발(BoundaryRepulsion)은 여기 없다. §9.5 가 "언리얼에만 있는 항"이라고
// 못박았고, 파이썬에는 대응물이 없어서 파리티 검증 대상이 아니기 때문이다.
// SteeringProcessor 가 이 함수 **뒤에** 더한다.

#pragma once

#include <cmath>

namespace EcoPolicy
{
	/** §3.3 의 기하 입력. 방향은 전부 단위벡터 또는 영벡터. XY 평면만 쓴다. */
	struct FSteerInput
	{
		float FoodGrad[2] = {0.0f, 0.0f};
		float ToCentroid[2] = {0.0f, 0.0f};
		float ToCover[2] = {0.0f, 0.0f};
		float Separation[2] = {0.0f, 0.0f};      // 크기 1 이하로 clamp 된 상태
		float AwayFromPred[2] = {0.0f, 0.0f};
		/** 가장 가까운 포식자까지 거리. 시야에 없으면 매우 큰 값. */
		float DistPredMin = 3.4e38f;
	};

	/** §3.3 계수. configs/default.yaml → EcoBehaviorConfig.h 에서 온다. */
	struct FSteerConfig
	{
		float SeeRadius = 1.0f;
		float SepWeight = 1.35f;
		float FleeWeight = 3.0f;
		float HerbSpeed = 1.0f;
	};

	/**
	 * 행동 가중치 4개 (forage, cohesion, flee_dist, cover) → 속도 (XY).
	 *
	 * 도주 항은 다른 항을 **대체하지 않고 더한다**. 대체하면 도망칠 때 무리가 흩어진다
	 * (§3.3, §12).
	 */
	inline void Steer(const FSteerInput& G, const float A[4], const FSteerConfig& C,
					  float OutVelocity[2])
	{
		float Vx = A[0] * G.FoodGrad[0];
		float Vy = A[0] * G.FoodGrad[1];

		Vx += A[1] * G.ToCentroid[0];
		Vy += A[1] * G.ToCentroid[1];

		Vx += A[3] * G.ToCover[0];
		Vy += A[3] * G.ToCover[1];

		Vx += C.SepWeight * G.Separation[0];
		Vy += C.SepWeight * G.Separation[1];

		if (G.DistPredMin < A[2] * C.SeeRadius)
		{
			Vx += G.AwayFromPred[0] * C.FleeWeight;
			Vy += G.AwayFromPred[1] * C.FleeWeight;
		}

		// normalize(v) * herb_speed. 영벡터는 영벡터로 남긴다 (파이썬 normalize 와 같은 규약).
		const float Len = std::sqrt(Vx * Vx + Vy * Vy);
		if (Len > 1.0e-9f)
		{
			OutVelocity[0] = Vx / Len * C.HerbSpeed;
			OutVelocity[1] = Vy / Len * C.HerbSpeed;
		}
		else
		{
			OutVelocity[0] = 0.0f;
			OutVelocity[1] = 0.0f;
		}
	}
}
