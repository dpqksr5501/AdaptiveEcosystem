#include "EcoBehaviorTraits.h"

#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassCommonUtils.h"
#include "MassEntityManager.h"
#include "MassEntityTemplateRegistry.h"
#include "MassMovementFragments.h"

void UEcoHerbivoreTrait::BuildTemplate(FMassEntityTemplateBuildContext& BuildContext,
									   const UWorld& World) const
{
	// 위치·속도는 Mass 기본 이동 트레잇 소관이다. 여기서는 있어야 한다고 선언만 한다.
	BuildContext.RequireFragment<FTransformFragment>();
	BuildContext.RequireFragment<FMassVelocityFragment>();

	BuildContext.AddTag<FEcoHerbivoreTag>();
	// 초식 쿼리는 전부 생존 태그를 요구한다. 논리 상태는 서버/스탠드얼론에만 있으므로
	// EcoMassNetworkTrait 와 같은 규칙으로 붙인다. 여러 트레잇이 같은 태그를 넣어도 된다.
	if (BuildContext.IsInspectingData() || World.GetNetMode() != NM_Client)
	{
		BuildContext.AddTag<FEcoAliveTag>();
	}
	// 이동은 UEcoSteeringProcessor 가 직접 적분한다. 엔진 UMassMovementTrait 는 기본값
	// (bIsCodeDrivenMovement = true)에서 FMassCodeDrivenMovementTag 를 붙이므로, 같이 쓰면
	// UMassApplyMovementProcessor 도 이 개체를 움직여 이동이 이중으로 적용되거나 속도가
	// 덮어써진다. 이 태그가 있으면 엔진 프로세서가 건너뛴다 (엔진이 정해 둔 방법).
	BuildContext.AddTag<FMassCustomMovementTag>();

	BuildContext.AddFragment<FEcoSteeringGeometryFragment>();
	BuildContext.AddFragment<FEcoObservationFragment>();
	BuildContext.AddFragment<FEcoPolicyOutputFragment>();

	// §9.2 "스폰 시 0~PolicyInterval 랜덤으로 초기화" — 정책 계산 부하를 틱마다 고르게
	// 흩기 위해서다. 전부 같은 틱에 몰리면 8틱에 한 번 스파이크가 생긴다.
	FEcoPolicyRuntimeFragment& Runtime = BuildContext.AddFragment_GetRef<FEcoPolicyRuntimeFragment>();
	Runtime.LastPolicyStep = FMath::RandRange(0, FMath::Max(BehaviorConfig.PolicyInterval - 1, 0));

	FEcoVitalsFragment& Vitals = BuildContext.AddFragment_GetRef<FEcoVitalsFragment>();
	Vitals.MaxEnergy = MaxEnergy;
	Vitals.Energy = MaxEnergy * FMath::Clamp(InitialEnergyRatio, 0.0f, 1.0f);

	// 공유 설정은 값이 같은 개체끼리 하나만 만들어진다 (아키타입 폭발 방지).
	FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(World);
	const FConstSharedStruct Config = EntityManager.GetOrCreateConstSharedFragment(BehaviorConfig);
	BuildContext.AddConstSharedFragment(Config);
}

void UEcoPredatorTrait::BuildTemplate(FMassEntityTemplateBuildContext& BuildContext,
									  const UWorld& World) const
{
	BuildContext.RequireFragment<FTransformFragment>();
	BuildContext.RequireFragment<FMassVelocityFragment>();
	BuildContext.AddTag<FEcoPredatorTag>();
	// §4.2 식사 쿨다운. 없으면 UEcoPredationProcessor 의 포식자 쿼리에 안 걸려 아무것도 못 잡는다.
	BuildContext.AddFragment<FEcoPredatorStateFragment>();
}
