// Integrated v3: common M4 authority/lifecycle/replication plus native R1b brain.
// Deer include Persistent Herd, native direct-evidence adapter, Alarm/Response, Shelter Request/Feedback.
// The discrete v3 policy is projected only for Social preferences; V1 PPO outputs are never fabricated.
// Social owns intents/leases; Native v3 is the only movement/vitals writer. No HerbivoreTag,
// legacy steering geometry, SpeciesAI movement, or flat-test tags are added.
// Wolf sensing/movement remains native. Client config contains presentation/transport only.
// Exact runtime contract: Docs/조연우/JYU_V3_SOCIAL_HANDOFF.md.

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
