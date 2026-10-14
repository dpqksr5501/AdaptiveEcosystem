#include "EcoCreatureV3Trait.h"

#include "AI/Policy/EcoBehaviorConfig.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityTemplateRegistry.h"
#include "MassEntityUtils.h"
#include "MassMovementFragments.h"

void UEcoCreatureV3Trait::BuildTemplate(FMassEntityTemplateBuildContext& Context, const UWorld& World) const
{
	BuildV3Composition(Context, World, World.GetNetMode() == NM_Client && !Context.IsInspectingData());
}

void UEcoCreatureV3Trait::BuildV3Composition(FMassEntityTemplateBuildContext& Context, const UWorld& World, bool bClientProxy) const
{
	// 할아버지만 부른다 — 부모(팀 트레잇)를 부르면 v1 초식·Social·포식 트레잇이 같이 붙는다
	UEcoMassNetworkTrait::BuildTemplate(Context, World);

	// 몸: 클라이언트에도 (표현·복제 경계는 팀 트레잇과 같다)
	Context.AddTag<FEcoIntegratedCreatureTag>();
	Context.AddFragment<FEcoCreaturePresentationFragment>();
	if (bClientProxy)
	{
		return;
	}

	// 몸: 서버만 (팀 트레잇 본문과 같은 줄)
	Context.AddTag<FMassCustomMovementTag>();
	Context.AddFragment<FEcoCreatureLifecycleFragment>();
	Context.AddFragment<FEcoCreatureCueFragment>();
	Context.AddFragment<FEcoCreatureSurvivalFragment>();
	Context.AddFragment<FEcoCreatureFootstepFragment>();
	FMassEntityManager& Manager = UE::Mass::Utils::GetEntityManagerChecked(World);
	FEcoSpeciesSharedFragment Species;
	Species.BaseMoveSpeed = EcoBehaviorConfig::HerbSpeedCmS;
	Species.ViewDistance = bPredator ? EcoBehaviorConfig::PredViewRadiusCm : EcoBehaviorConfig::SeeRadiusCm;
	Species.FOV = bPredator ? EcoBehaviorConfig::PredFovDeg : EcoBehaviorConfig::FovDeg;
	Context.AddSharedFragment(Manager.GetOrCreateSharedFragment(Species));

	// 머리: v3 (서버만)
	Context.AddFragment<FEcoIntegratedV3Fragment>();
	if (bPredator)
	{
		Context.AddFragment<FEcoThreatStateFragment>();
		Context.AddTag<FEcoIntegratedThreatV3Tag>();
		// 자리표시: 조정자가 '먹는 중' 깃발로 읽는다 (GetFragmentDataPtr). 값은 우리 처리기가 v3 쿨다운에서 옮겨 적는다
		Context.AddFragment<FEcoPredatorStateFragment>();
	}
	else
	{
		Context.AddFragment<FEcoBehaviorStateFragment>();
		Context.AddFragment<FEcoPerceptionCacheFragment>();
		Context.AddFragment<FEcoControlOutFragment>();
		Context.AddFragment<FEcoHerbivoreBodyV3Fragment>();
		Context.AddTag<FEcoIntegratedPolicyV3Tag>();
		// 자리표시: 조정자 1초 정산이 산 Resident 사슴마다 GetFragmentDataChecked 로 읽는다. 기본값(bValid 거짓·Forage 0)이라
		// 지역 장부 섭식 요청이 생기지 않는다 — v3 섭식은 무대 먹이 격자가 맡는다(팀 장부 연결은 팀 몫)
		Context.AddFragment<FEcoPolicyOutputFragment>();
		Context.AddFragment<FEcoSocialMovementRequestFragment>();
	}
}

UMassEntityConfigAsset* UEcoCreatureV3Trait::MakeConfig(UObject* Outer, bool bPredator)
{
	if (!Outer)
	{
		return nullptr;
	}
	const FName Name = MakeUniqueObjectName(Outer, UMassEntityConfigAsset::StaticClass(),
											bPredator ? FName(TEXT("EcoV3WolfConfig")) : FName(TEXT("EcoV3DeerConfig")));
	UMassEntityConfigAsset* Config = NewObject<UMassEntityConfigAsset>(Outer, Name, RF_Transient);
	UEcoCreatureV3Trait* Trait = NewObject<UEcoCreatureV3Trait>(Config, NAME_None, RF_Transient);
	Trait->bPredator = bPredator;
	Config->GetMutableConfig().AddTrait(*Trait);
	return Config;
}

UMassEntityConfigAsset* UEcoCreatureV3Trait::MakeNetworkConfig(bool bPredator)
{
	const FName Name(bPredator ? TEXT("EcoIntegratedV3Wolf_v1") : TEXT("EcoIntegratedV3Deer_v1"));
	if (auto* Existing = FindObject<UMassEntityConfigAsset>(GetTransientPackage(), *Name.ToString())) return Existing;
	auto* Config = NewObject<UMassEntityConfigAsset>(GetTransientPackage(), Name, RF_Transient);
	auto* Trait = NewObject<UEcoCreatureV3Trait>(Config, NAME_None, RF_Transient);
	Trait->bPredator = bPredator;
	Config->GetMutableConfig().AddTrait(*Trait);
	return Config;
}
