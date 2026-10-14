// 팀 통합 레벨용 v3 트레잇 — "몸은 팀 것, 머리만 우리 것" (계획서 RL_V3_UNREAL_TRAINING_PLAN.md 4-5b).
//
// 팀 트레잇 UEcoCreatureNetworkTrait 의 하위 클래스다. 팀 조정자(AEcoCreatureIntegrationSpawner::RegisterTemplates)는
// FindTrait(UEcoCreatureNetworkTrait) 로 트레잇을 찾는데, 엔진 FindTrait 는 하위 클래스도 받아 준다(IsA). 그래서 팀 파일을 고치지 않고
// 조정자의 HerbivoreConfig·WolfConfig 를 이 트레잇 하나를 가진 실행 중 설정(MakeConfig)으로 바꿔 끼우면 된다.
//
// 몸 (팀 트레잇 본문 EcoCreatureNetworkTrait.cpp:13-28 과 같은 줄을 손으로 다시 붙인다 — 팀 함수가 초식·Social·포식 부분과 한 덩어리라서):
//   할아버지 UEcoMassNetworkTrait::BuildTemplate  Transform·Identity·Region, 서버: Vitals·Travel·Lifetime·Feeding·MassVelocity·
//                                                  DesiredMovement·CodeDrivenMovement·Alive·Authority, 클라이언트: ClientProxy, 복제 조각
//   클라이언트에도: FEcoIntegratedCreatureTag, FEcoCreaturePresentationFragment (여기서 클라이언트는 끝 — 논리 조각 없음)
//   서버만: FMassCustomMovementTag (꼭 — 없으면 엔진 ApplyMovement 가 CodeDrivenMovement 태그를 보고 v3 화면 속도로 한 번 더 움직인다),
//           Lifecycle·Footstep·종 공유 조각(팀과 같은 값)
//   서버만, 조정자가 GetFragmentDataChecked 로 읽는 자리표시 (값은 쓰지 않는다):
//           사슴 FEcoPolicyOutputFragment·FEcoSocialMovementRequestFragment (1초 정산의 Forage 읽기. 기본 0 이라 섭식 요청이 없다)
//           늑대 FEcoPredatorStateFragment (표현 '먹는 중' 깃발. 우리 처리기가 포획 뒤 쿨다운을 옮겨 적는다)
// 머리 (서버만):
//   사슴 FEcoBehaviorStateFragment·FEcoPerceptionCacheFragment·FEcoControlOutFragment·FEcoHerbivoreBodyV3Fragment·
//        FEcoIntegratedV3Fragment·FEcoIntegratedPolicyV3Tag
//   늑대 FEcoThreatStateFragment·FEcoIntegratedV3Fragment·FEcoIntegratedThreatV3Tag
// 넣지 않는 것: FEcoHerbivoreTag(v1 초식 트레잇), UEcoSocialTrait 조각 전부(HerdMember·AlarmState·SensoryState·ShelterIntent·
//   SocialBehavior·ShelterMovementFeedback·Social 공유 조각), FEcoPredatorTag·FEcoPreySenseFragment·FEcoSensoryProfileFragment·
//   FEcoPredatorSensesSharedFragment, v1 Observation·SteeringGeometry·PolicyRuntime, 평면 시험 태그 FEcoPolicyV3Tag·FEcoThreatV3Tag.
//
// 그래서 다음 팀 처리기는 이 개체를 보지 않는다 (쿼리 필수 조건으로 확인, 2026-10-14):
//   v1 사슬    UEcoNeighborhoodGatherProcessor(HerbivoreTag / PredatorTag), UEcoPerceptionProcessor·UEcoPolicyProcessor·
//              UEcoSteeringProcessor(HerbivoreTag+Alive), UEcoPredationProcessor(HerbivoreTag / PredatorTag+PredatorState)
//   Social     UEcoHerdMembershipProcessor·UEcoHerdAggregateProcessor(HerdMember), UEcoThreatDetectionProcessor(HerdMember+Social 공유),
//              UEcoAlarmPropagationProcessor·UEcoSocialResponseProcessor(HerdMember·AlarmState), UEcoShelterQueryProcessor·
//              UEcoShelterReservationProcessor(ShelterIntent), UEcoShelterLifecycleProcessor(AlarmState·SocialBehavior·ShelterIntent)
//   늑대       UEcoPredatorPerceptionProcessor·UEcoCreaturePredatorProcessor(Integrated+PredatorTag+PreySense)
//   이주       UEcoMigrationSteeringProcessor(IntegratedTag None). 이주 정산 EcoMassMigration::Reconcile 은 Authority+Alive 만 보므로
//              이 개체를 잡는다 — 그래서 통합 모드는 조정자의 Migration.bEnabled 를 끈다(끄면 정산이 곧바로 돌아간다)
//   엔진       UMassApplyMovementProcessor(CustomMovementTag None)
//   보는 것    팀 조정자 Reconcile·SyncVisuals·PublishSummary(몸 조각만 읽는다), 복제 UEcoMassReplicator(읽기만)

#pragma once

#include "CoreMinimal.h"
#include "Creature/Runtime/EcoCreatureNetworkTrait.h"

#include "EcoCreatureV3Trait.generated.h"

class UMassEntityConfigAsset;

UCLASS(EditInlineNew, meta = (DisplayName = "Eco Integrated Creature (v3 R1b brain)"))
class ADAPTIVEECOSYSTEM_API UEcoCreatureV3Trait : public UEcoCreatureNetworkTrait
{
	GENERATED_BODY()

public:
	virtual void BuildTemplate(FMassEntityTemplateBuildContext& Context, const UWorld& World) const override;

	/**
	 * 조각 구성 본문. bClientProxy 면 몸의 클라이언트 부분(Integrated 태그·Presentation)까지만 붙인다.
	 * BuildTemplate 은 World 넷 모드로 bClientProxy 를 정한다 (시험이 클라이언트 갈래를 따로 확인할 수 있게 나눠 둔다).
	 */
	void BuildV3Composition(FMassEntityTemplateBuildContext& Context, const UWorld& World, bool bClientProxy) const;

	/**
	 * 이 트레잇 하나를 가진 실행 중 설정 (일시 객체, 저장되지 않는다). 팀 DA_EcoDeer·DA_EcoWolf 를 복제하지 않는다 —
	 * 복제해 트레잇을 더하면 팀 트레잇과 둘이 되어 v1 초식·Social 이 되살아난다.
	 * Outer 는 그 월드의 객체(조정자)로 둔다 — 설정 GUID(= 템플릿 번호)가 경로에서 나오므로 월드마다 다르다.
	 */
	static UMassEntityConfigAsset* MakeConfig(UObject* Outer, bool bPredator);
	/** Immutable canonical path gives Server/Client the same template GUID without changing saved V1 assets. */
	static UMassEntityConfigAsset* MakeNetworkConfig(bool bPredator);
};
