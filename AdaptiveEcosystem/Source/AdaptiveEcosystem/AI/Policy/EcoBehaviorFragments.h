// §9.2 정책·조향 계층이 쓰는 Fragment.
//
// 저장소에 이미 있는 것은 다시 만들지 않는다 (Mass/EcoMassFragments.h):
//   FEcoObservationFragment    §3.1 관측 7개        (§9.2 의 관측 저장소)
//   FEcoPolicyOutputFragment   §3.2 행동 4개        (§9.2 FSteeringParamsFragment 에 해당)
//   FEcoPolicyRuntimeFragment  정책 주기 카운터     (§9.2 TicksSinceUpdate 에 해당)
//   FEcoVitalsFragment         Energy/MaxEnergy     (§9.2 FHerbivoreStateFragment 에 해당)
// AGENTS.md §2.3: PPO 출력은 Shared Fragment 가 아니라 개체별 Entity Fragment 에 둔다.
// 여기서는 그 위에 **없는 것만** 더한다.

#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"

#include "EcoBehaviorConfig.h"   // 자동 생성 (§9.7 단위 대응)

#include "EcoBehaviorFragments.generated.h"

/** 초식 개체. §9.4 관측 수집과 §9.5 조향의 대상이다. */
USTRUCT()
struct FEcoHerbivoreTag : public FMassTag
{
	GENERATED_BODY()
};

/**
 * 포식자. §9.5 "이웃 순회에서 FPredatorTag면 조향 대상이 아니라 도주 판정 + 관측 수집".
 * 플레이어도 §9.4 관측에서는 포식자로 센다 (별도 경로).
 */
USTRUCT()
struct FEcoPredatorTag : public FMassTag
{
	GENERATED_BODY()
};

/**
 * §9.2 FBehaviorConfigSharedFragment.
 *
 * 기본값은 `EcoBehaviorConfig.h` 에서 온다 — 그 헤더는 `configs/default.yaml` 에서
 * `export_weights.py` 가 생성한다. §9.7: 두 곳에 따로 적지 않는다.
 * 여기 값을 손으로 바꾸면 파이썬 학습 조건과 갈라져 §0 의 동일 조건 비교가 깨진다.
 *
 * §9.2 는 `FMassSharedFragment` 상속을 적었지만 UE 5.8 의 const 공유 프래그먼트 API
 * (`GetOrCreateConstSharedFragment`)는 `FMassConstSharedFragment` 를 요구한다. 이 설정은
 * 런타임에 바뀌지 않으므로 const 쪽이 의미상으로도 맞다.
 *
 * **아직 프로세서가 이 값을 읽지 않는다.** 지금은 `EcoBehaviorConfig.h` 상수를 직접 쓴다.
 * 트레잇 템플릿에는 들어가 있으므로, 종별로 다른 값을 주고 싶으면 프로세서에
 * `AddConstSharedRequirement` 를 붙이면 된다 — 에셋을 다시 만들 필요는 없다.
 */
USTRUCT()
struct FEcoBehaviorConfigSharedFragment : public FMassConstSharedFragment
{
	GENERATED_BODY()

	/** §3.1 시야 거리. 관측 2번(predator_distance)의 정규화 분모이기도 하다. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior")
	float SeeRadius = EcoBehaviorConfig::SeeRadiusCm;

	/** §3.1 시야 각도 제한. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior")
	float FovDeg = EcoBehaviorConfig::FovDeg;

	/** §3.1 관측 4번(energy)의 정규화 분모. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior")
	float MaxEnergy = EcoBehaviorConfig::MaxEnergy;

	/** §3.3 `normalize(v) * herb_speed` 의 속력. cm/s. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior")
	float HerbSpeed = EcoBehaviorConfig::HerbSpeedCmS;

	/** §9.7 1 격자 단위 = 이 cm. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior")
	float GridUnitCm = EcoBehaviorConfig::GridUnitCm;

	/** §9.4 이 틱 수마다 한 번만 정책을 돌린다. 파이썬 1 스텝에 해당한다. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior", meta = (ClampMin = "1"))
	int32 PolicyInterval = EcoBehaviorConfig::PolicyInterval;

	// --- §3.3 조향 계수. 파이썬 env/steering.py 와 값이 같아야 한다 ---

	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior|Steering")
	float SepWeight = EcoBehaviorConfig::SepWeight;

	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior|Steering")
	float SepRadius = EcoBehaviorConfig::SepRadiusCm;

	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior|Steering")
	float FleeWeight = EcoBehaviorConfig::FleeWeight;

	// --- 언리얼에만 있는 항 (§9.5) ---

	/** 맵 경계에서 밀어내는 힘의 세기. 파이썬에는 없다 (거기선 좌표를 clamp 한다). */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior|Steering")
	float BoundaryRepulsion = 2.0f;

	/** 경계에서 이 거리 안쪽부터 밀어낸다. cm. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior|Steering")
	float BoundaryMargin = 1000.0f;
};

/**
 * §3.3 조향에 들어가는 기하 입력. 한 틱 안에서 관측 수집과 조향이 같은 값을 쓰도록
 * 캐시한다. 방향 벡터는 전부 **단위벡터 또는 영벡터** 다 (파이썬 env/steering.py 주석 참조).
 */
USTRUCT()
struct FEcoSteeringGeometryFragment : public FMassFragment
{
	GENERATED_BODY()

	/** 먹이 기울기 방향. 평평하면 영벡터. */
	UPROPERTY(Transient)
	FVector FoodGrad = FVector::ZeroVector;

	/** 시야 내 동족 중심으로 향하는 방향. 동족이 없으면 영벡터. */
	UPROPERTY(Transient)
	FVector ToCentroid = FVector::ZeroVector;

	/** 가장 가까운 은신처 방향. 이미 안이면 영벡터. */
	UPROPERTY(Transient)
	FVector ToCover = FVector::ZeroVector;

	/** 최소 간격 유지. 크기 1 이하로 clamp 되어 있다. */
	UPROPERTY(Transient)
	FVector Separation = FVector::ZeroVector;

	/** 가장 가까운 포식자 반대 방향. 없으면 영벡터. */
	UPROPERTY(Transient)
	FVector AwayFromPred = FVector::ZeroVector;

	/** 가장 가까운 포식자까지 거리. 시야에 없으면 매우 큰 값. */
	UPROPERTY(Transient)
	float DistPredMin = TNumericLimits<float>::Max();

	/** 시야 내 동족 수 (자기 제외). §3.1 관측 3번의 원본. */
	UPROPERTY(Transient)
	int32 KinCount = 0;

	/** 시야 내 포식자 수. §3.1 관측 1번의 원본. */
	UPROPERTY(Transient)
	int32 PredatorCount = 0;
};
