// §9.2 Mass 트레잇 — 레벨에서 개체를 스폰할 수 있게 하는 조각.
//
// 프래그먼트와 프로세서만 있으면 코드로는 엔티티를 만들 수 있지만, **레벨에 배치**하려면
// `UMassEntityConfigAsset` 에 붙일 트레잇이 있어야 한다. 이게 없으면 디자이너가
// 이 정책을 쓸 방법이 없다.
//
// 쓰는 법:
//   1. 에디터에서 Mass Entity Config 에셋을 만든다
//   2. Traits 에 EcoHerbivore (또는 EcoPredator) 를 추가한다
//   3. 레벨에 MassSpawner 를 놓고 그 config 를 지정한다
//   4. 콘솔에서 `eco.UseLearnedPolicy 0/1` 로 비교군과 학습 정책을 바꾼다

#pragma once

#include "CoreMinimal.h"
#include "EcoBehaviorFragments.h"
#include "MassEntityTraitBase.h"

#include "EcoBehaviorTraits.generated.h"

/**
 * 초식 개체. §9.4 관측 수집과 §9.5 조향의 대상이 된다.
 *
 * 붙는 것: FEcoHerbivoreTag + 관측/행동/주기/기하/생체 프래그먼트 + 공유 설정.
 * 위치·속도(FTransformFragment, FMassVelocityFragment)는 Mass 기본 이동 트레잇이
 * 제공하므로 여기서는 **요구만** 한다 — 중복으로 추가하면 초기화 주체가 흐려진다.
 */
UCLASS(meta = (DisplayName = "Eco Herbivore"))
class ADAPTIVEECOSYSTEM_API UEcoHerbivoreTrait : public UMassEntityTraitBase
{
	GENERATED_BODY()

public:
	virtual void BuildTemplate(FMassEntityTemplateBuildContext& BuildContext,
							   const UWorld& World) const override;

	/**
	 * §9.2 공유 설정. 기본값은 `EcoBehaviorConfig.h` (configs/default.yaml 자동 생성)에서
	 * 온다. 에디터에서 덮어쓸 수 있지만, 그러면 파이썬 학습 조건과 갈라진다는 뜻이다.
	 */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior")
	FEcoBehaviorConfigSharedFragment BehaviorConfig;

	/** 초기 에너지 비율 [0,1]. 관측 4번의 시작값이 된다. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float InitialEnergyRatio = 1.0f;

	/** 개체 최대 에너지. 관측 4번의 정규화 분모. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Behavior", meta = (ClampMin = "0.01"))
	float MaxEnergy = 100.0f;
};

/**
 * 포식자. §9.5 "이웃 순회에서 FPredatorTag면 조향 대상이 아니라 도주 판정 + 관측 수집".
 *
 * 이 트레잇은 포식자에게 **행동을 주지 않는다** — 정책 학습 대상이 초식이기 때문이다.
 * 포식자 이동은 별도 AI(또는 플레이어)가 담당하고, 여기서는 초식이 볼 수 있도록
 * 색인에 등록되는 것만 보장한다.
 */
UCLASS(meta = (DisplayName = "Eco Predator"))
class ADAPTIVEECOSYSTEM_API UEcoPredatorTrait : public UMassEntityTraitBase
{
	GENERATED_BODY()

public:
	virtual void BuildTemplate(FMassEntityTemplateBuildContext& BuildContext,
							   const UWorld& World) const override;
};
