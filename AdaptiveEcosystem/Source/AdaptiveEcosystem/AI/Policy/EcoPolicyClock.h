// 정책 결정·피식 EMA 주기의 시간 기준. 엔진에 의존하지 않는다 (EcoSteering.h 와 같은 방식).
//
// 1 스텝 = StepSeconds 초(0.1333초) = 파이썬 1 스텝 = PolicyInterval 논리 틱.
// 1 논리 틱 = StepSeconds / PolicyInterval = 1/60초다. 실제 프레임과 무관하다.
// 예전에는 "PolicyInterval 프레임마다"로 세서 60FPS 를 가정했다 — 30FPS 에서는 결정과 EMA
// 감쇠가 절반 속도로 돌았다. 생성 헤더(EcoBehaviorConfig.h)의 '틱'은 이 논리 틱이다.

#pragma once

#include <cmath>
#include <cstdint>

namespace EcoPolicy
{
	/** 프레임 dt → 지나간 논리 틱 수. */
	struct FStepClock
	{
		/** 논리 틱 단위 오차 허용. 1/50초 × 160 = 191.99999 → 192 로 센다. */
		static constexpr double Epsilon = 1e-4;
		/** 한 프레임에 처리하는 최대 스텝. 64 × 0.1333 = 8.5초 — 엔진 dt 상한을 넉넉히 넘는다. */
		static constexpr int MaxCatchUpSteps = 64;

		double Remainder = 0.0;

		int Advance(float DeltaSeconds, float StepSeconds, int Interval)
		{
			if (!std::isfinite(DeltaSeconds) || !(DeltaSeconds > 0.0f) || !(StepSeconds > 0.0f) || Interval < 1)
			{
				return 0;   // 일시정지, 음수, NaN, Inf — 시간이 흐르지 않은 것으로 본다
			}
			const double TickSeconds = static_cast<double>(StepSeconds) / Interval;
			Remainder += static_cast<double>(DeltaSeconds) / TickSeconds;
			const double Whole = std::floor(Remainder + Epsilon);
			const int MaxTicks = MaxCatchUpSteps * Interval;
			if (Whole > MaxTicks)
			{
				Remainder = 0.0;
				return MaxTicks;
			}
			Remainder -= Whole;
			if (std::fabs(Remainder) < Epsilon)
			{
				Remainder = 0.0;   // 공칭 FPS 에서 오차가 쌓이지 않게
			}
			return static_cast<int>(Whole);
		}
	};

	/**
	 * §9.4 기존 `++Phase < Interval` 을 Ticks 만큼 한 번에 한다. 결정할 프레임이면 true.
	 * 결정은 프레임당 최대 한 번이고, 위상(부하 분산)은 유지한다.
	 */
	inline bool AdvanceDecisionPhase(int32_t& Phase, int Ticks, int Interval)
	{
		if (Ticks <= 0)
		{
			return false;
		}
		if (Phase < 0)
		{
			Phase = 0;
		}
		if (Phase > Interval - 1)
		{
			Phase = Interval - 1;
		}
		Phase += Ticks;
		if (Phase < Interval)
		{
			return false;
		}
		Phase %= Interval;
		return true;
	}

	/** §9.6 이번 프레임에 넘은 스텝 경계의 수. */
	inline int ConsumeSteps(int32_t& Phase, int Ticks, int Interval)
	{
		if (Ticks <= 0 || Interval < 1)
		{
			return 0;
		}
		Phase += Ticks;
		const int Steps = Phase / Interval;
		Phase -= Steps * Interval;
		return Steps;
	}
}
