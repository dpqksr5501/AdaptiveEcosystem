// 초식 heading(시야 기준 방향) 규약. 파이썬 env/world.py 와 같다:
//   moving = |v| > EPS;  head = normalize(v) if moving else head
//
// UE 타입을 쓴다 — EcoSteering.h 에 넣지 말 것 (herbivore_rl/tests/cpp 의 g++ 파리티 하네스가
// EcoSteering.h 를 엔진 없이 컴파일한다).

#pragma once

#include "CoreMinimal.h"

namespace EcoHeading
{
	/** world.py `moving = |v| > EPS`. 조향 속도는 0 또는 HerbSpeed 라 문턱 차이가 결과를 바꾸지 않는다. */
	inline bool IsMoving2D(const FVector& V)
	{
		return V.SizeSquared2D() > KINDA_SMALL_NUMBER;
	}

	/** 파이썬 head. 움직이면 normalize(V), 멈추면 조향이 마지막으로 쓴 yaw(Transform 전방). */
	inline FVector HeadingOf(const FTransform& T, const FVector& V)
	{
		if (IsMoving2D(V))
		{
			return FVector(V.X, V.Y, 0.0).GetSafeNormal();
		}
		const FVector F = T.GetRotation().GetForwardVector().GetSafeNormal2D();
		return F.IsNearlyZero() ? FVector::ForwardVector : F;
	}

	/** Z축 회전만. 전방 = (cos, sin, 0). */
	inline FQuat YawQuatFromDir(const FVector& Dir)
	{
		return FQuat(FVector::UpVector, FMath::Atan2(Dir.Y, Dir.X));
	}

	/** world.py — 움직일 때만 heading 을 바꾼다. 멈추면 유지한다. */
	inline void WriteYawIfMoving(FTransform& T, const FVector& Dir)
	{
		if (IsMoving2D(Dir))
		{
			T.SetRotation(YawQuatFromDir(Dir));
		}
	}
}
