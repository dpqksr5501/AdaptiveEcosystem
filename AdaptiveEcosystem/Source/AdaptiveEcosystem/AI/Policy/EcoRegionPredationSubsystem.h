// §9.6 피식 EMA 서브시스템 — 관측 5번(`recent_predation`)의 출처.
//
// 파이썬 env/world.py 와 같은 **전역 스칼라 하나**다:
//
//     ema_k = d*ema_{k-1} + (1-d) * (D_k / P_k) * g          관측 = min(ema, 1)
//
//   d, g : EcoBehaviorConfig::PredationEmaDecay / PredationEmaGain (configs/default.yaml 에서 생성)
//   D_k  : 스텝 k 의 피식 사망 수 (포식자 포획 + 플레이어 사냥. 아사는 제외 — 파이썬도 그렇다)
//   P_k  : 스텝 k 동안 보고된 '포획 판정 전 생존 초식 수'의 최대값 = 스텝 시작 때 산 개체 수.
//          파이썬 N 과 같은 양이다 (그 스텝에 잡힌 개체도 분모에 들어간다)
//
// 스텝 경계는 UEcoPredationProcessor 가 포획 판정 직후에 정한다 (world.py: 포획 → EMA → 관측).
// 관측은 다음 틱부터의 정책 결정이 읽는다. 결정 위상을 흩어 둔 개체는 1스텝 미만 늦게 읽는다.
//
// 이름의 Region 은 v1 지역별 구현의 흔적이다. 예전에는 17000cm 격자 지역마다 EMA 를 따로 돌렸고,
// 개체마다 개수 1을 보고하는데 받는 쪽이 max 를 취해 분모가 늘 1이었다(피식 1건에 0.5 상승).
// 지역 단위 위험 기억은 v2 의 별도 관측 / Ecology PredationHistory 몫이다.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "Subsystems/WorldSubsystem.h"

#include "EcoRegionPredationSubsystem.generated.h"

/** §9.6 SaveGame. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPredationSaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	/** 0 = v1 지역별 저장(분모 버그 값). 기본값이 0이어야 이 필드가 없는 옛 파일과 구분된다. */
	UPROPERTY()
	int32 SchemaVersion = 0;

	UPROPERTY()
	float Ema = 0.0f;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoRegionPredationSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	static constexpr int32 SaveSchemaVersion = 2;

	/** §3.1 관측 5번. 항상 [0,1]. */
	UFUNCTION(BlueprintPure, Category = "Ecology|Predation")
	float GetRecentPredation() const;

	/** 호환용. 위치와 무관하게 전역 값을 돌려준다. */
	UFUNCTION(BlueprintPure, Category = "Ecology|Predation",
			  meta = (DeprecatedFunction, DeprecationMessage = "관측 5는 전역 값이다. GetRecentPredation()을 쓴다."))
	float Get(const FVector& Location) const { return GetRecentPredation(); }

	/**
	 * 피식 사망 1건. 포식자 포획이든 플레이어 사냥이든 여기로 들어온다 (§9.6).
	 * Location 은 지역 위험 기억·Ecology 연결용으로 남겨 두며 지금 식에는 쓰지 않는다.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Predation")
	void ReportPredation(const FVector& Location);

	/** UEcoPredationProcessor 가 틱마다 한 번, 포획 판정 전에 센 생존 초식 전체 수. 스텝 안에서는 최대값을 쓴다. */
	void ReportAlivePopulation(int32 AliveCount);

	/** 스텝 경계에서 한 번. UEcoPredationProcessor 가 부른다. */
	void Tick();

	/** SaveGame 직렬화. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Predation")
	bool SaveToSlot(const FString& SlotName, int32 UserIndex = 0) const;

	/** 다른 스키마(v1 지역별 저장)는 불러오지 않는다. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Predation")
	bool LoadFromSlot(const FString& SlotName, int32 UserIndex = 0);

	// 테스트·디버그용
	float GetRawEma() const { return Ema; }
	int32 GetPendingDeaths() const { return PendingDeaths; }
	int32 GetStepPopulation() const { return StepPopulation; }

private:
	UPROPERTY()
	float Ema = 0.0f;

	int32 PendingDeaths = 0;
	int32 StepPopulation = 0;
};
