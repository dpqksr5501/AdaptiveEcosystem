// §9.6 지역 피식 서브시스템.
//
// §3.1 관측 5번(`recent_predation`)의 출처다. 갱신식은 파이썬과 같아야 한다:
//
//     ema = 0.95*ema + 0.05*(그 구간 지역 내 사망 수 / 지역 개체 수) * 10
//
// 계수는 `EcoBehaviorConfig.h` (configs/default.yaml 에서 자동 생성) 에서 온다.
//
// §9.6 규약 세 가지:
//   - **PolicyInterval 틱마다** 1회 갱신 (매 틱이 아니다 — 파이썬 1 스텝에 대응)
//   - 포식자 포획 + **플레이어 사냥** 모두 사망 수에 포함
//   - SaveGame 으로 세션 간 유지
//
// 주의: 파이썬 환경은 지역이 하나뿐이라 EMA 가 전역 스칼라다. 언리얼은 지역별로
// 나뉘므로 같은 수식이 지역 단위로 돈다. 학습 시 본 값의 분포와 런타임 분포가
// 달라질 수 있다 — 지역이 너무 작으면 사망 수가 0 또는 1 로 튀어 EMA 가 거칠어진다.
// `RegionSize` 기본값은 파이썬 세계 크기(60~110 격자 단위)에 맞춰 잡았다.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "Subsystems/WorldSubsystem.h"

#include "EcoRegionPredationSubsystem.generated.h"

/** 한 지역의 피식 상태. */
USTRUCT()
struct FEcoRegionPredationState
{
	GENERATED_BODY()

	/** §3.1 관측 5번으로 나가는 값. [0,1] 로 clamp 해서 쓴다. */
	UPROPERTY()
	float Ema = 0.0f;

	/** 이번 갱신 구간에 누적된 사망 수. 갱신 후 0으로 리셋. */
	UPROPERTY()
	int32 PendingDeaths = 0;

	/** 이번 갱신 구간에 관측된 지역 개체 수의 최대값. 0 나눗셈 방지용. */
	UPROPERTY()
	int32 Population = 0;
};

/** §9.6 SaveGame 으로 세션 간 유지. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPredationSaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	UPROPERTY()
	TMap<int64, FEcoRegionPredationState> Regions;

	UPROPERTY()
	float RegionSize = 0.0f;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoRegionPredationSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** §3.1 관측 5번. 항상 [0,1]. */
	UFUNCTION(BlueprintPure, Category = "Ecology|Predation")
	float Get(const FVector& Location) const;

	/**
	 * 개체 하나가 죽었다. 포식자 포획이든 플레이어 사냥이든 여기로 들어온다 (§9.6).
	 * 아사는 포함하지 않는다 — 파이썬도 피식 사망만 센다.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Predation")
	void ReportPredation(const FVector& Location);

	/** 갱신 구간 동안 지역 개체 수를 알린다. 분모가 된다. */
	void ReportPopulation(const FVector& Location, int32 Count);

	/** §9.6 PolicyInterval 틱마다 한 번. 프로세서가 호출한다. */
	void Tick();

	/** SaveGame 직렬화. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Predation")
	bool SaveToSlot(const FString& SlotName, int32 UserIndex = 0) const;

	UFUNCTION(BlueprintCallable, Category = "Ecology|Predation")
	bool LoadFromSlot(const FString& SlotName, int32 UserIndex = 0);

	/** 지역 한 변의 크기. cm. */
	UPROPERTY(EditAnywhere, Category = "Ecology|Predation")
	float RegionSize = 17000.0f;

	int32 NumRegions() const { return Regions.Num(); }

private:
	int64 RegionKey(const FVector& Location) const;

	UPROPERTY()
	TMap<int64, FEcoRegionPredationState> Regions;
};
