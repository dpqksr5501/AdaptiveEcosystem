// 자동 생성. 수정 금지.
// §9.7 단위 대응 — 파이썬(격자 단위/스텝) -> 언리얼(cm/초).
//   1 스텝        = PolicyInterval 틱
//   1 격자 단위   = GridUnitCm
//   HerbSpeed     = herb_speed × GridUnitCm ÷ (PolicyInterval/60) cm/s
//   SeeRadius     = see_r × GridUnitCm
//   StepSeconds   = PolicyInterval ÷ 60 — 스텝 단위 값(쿨다운 등)을 초로 바꿀 때 쓴다
//   PredWanderTurnRad 는 스텝당 값이다. 틱마다 나눠 돌리면 분산이 달라지므로
//   StepSeconds 경계마다 한 번씩 적용한다.
// generated: 2026-09-23T07:11:48+00:00, from configs/default.yaml
#pragma once

#include "CoreMinimal.h"

namespace EcoBehaviorConfig
{
	static constexpr float GridUnitCm = 200.0f;
	static constexpr int32 PolicyInterval = 8;
	static constexpr float SeeRadiusCm = 4000.0f;
	static constexpr float HerbSpeedCmS = 900.0f;
	static constexpr float MaxEnergy = 1.0f;
	static constexpr float ObsPredCountNorm = 8.0f;
	static constexpr float ObsKinCountNorm = 20.0f;
	static constexpr float ObsCoverNormCm = 4000.0f;
	static constexpr float FovDeg = 120.0f;
	static constexpr float SepWeight = 1.35f;
	static constexpr float SepRadiusCm = 1000.0f;
	static constexpr float FleeWeight = 3.0f;
	static constexpr float PredationEmaDecay = 0.95f;
	static constexpr float PredationEmaGain = 10.0f;
	static constexpr float StepSeconds = 0.13333333333333333f;
	static constexpr float PredViewRadiusCm = 2800.0f;
	static constexpr float PredFovDeg = 150.0f;
	static constexpr float PredCatchRadiusCm = 200.0f;
	static constexpr float PredEatCooldownS = 0.6666666666666666f;
	static constexpr float PredWanderTurnRad = 0.15f;
	static constexpr float CoverHideMult = 2.5f;
	static constexpr float InitEnergyFrac = 0.5f;
}
