// 자동 생성. 수정 금지.
// §9.7 단위 대응 — 파이썬(격자 단위/스텝) -> 언리얼(cm/초).
//   1 스텝        = PolicyInterval 틱
//   1 격자 단위   = GridUnitCm
//   HerbSpeed     = herb_speed × GridUnitCm ÷ (PolicyInterval/60) cm/s
//   SeeRadius     = see_r × GridUnitCm
// generated: 2026-09-22T06:19:26+00:00, from configs/default.yaml
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
}
