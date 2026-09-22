#include "EcoBehaviorTraits.h"

#include "Mass/EcoMassFragments.h"
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
}
