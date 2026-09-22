// §9.8-3/§9.8-4 시각 확인용 테스트 액터.
//
// 레벨에 하나 놓고 Play 를 누르면:
//   - 초식/포식자 Mass 엔티티를 반경 안에 스폰한다
//   - §9.4 Policy → §9.5 Steering 프로세서가 자동으로 돌아 개체가 움직인다
//   - 디버그 드로우로 상태를 그린다 (Mass 표현/ISM 설정 없이도 보인다)
//
// 왜 MassSpawner 를 안 쓰나:
// MassSpawner 의 스폰 위치 생성기는 UE 5.8 에 EQS·ZoneGraph 두 가지뿐이라 별도 에셋
// 작성이 필요하다. 최소 테스트 레벨의 목적은 "프로세서가 도는 걸 보는 것"이므로
// 엔티티를 직접 만드는 쪽이 의존을 줄인다. 디자이너 워크플로용 트레잇
// (UEcoHerbivoreTrait / UEcoPredatorTrait)은 별도로 있으니 실제 콘텐츠는 그쪽을 쓴다.
//
// 콘솔에서 `eco.UseLearnedPolicy 0` 으로 §5.1 Utility 비교군, `1` 로 학습 정책 (§9.8-4).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MassEntityHandle.h"
#include "MassEntityTypes.h"

#include "EcoPolicyTestSpawner.generated.h"

UCLASS(BlueprintType, Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoPolicyTestSpawner : public AActor
{
	GENERATED_BODY()

public:
	AEcoPolicyTestSpawner();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void Tick(float DeltaSeconds) override;

	/** 스폰할 초식 수. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test", meta = (ClampMin = "1"))
	int32 HerbivoreCount = 96;

	/** 스폰할 포식자 수. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test", meta = (ClampMin = "0"))
	int32 PredatorCount = 5;

	/** 스폰 반경. cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test")
	float SpawnRadius = 12000.0f;

	/** 포식자 속도. §4.4 에서 herb_speed 의 0.8~1.2배. cm/s. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test")
	float PredatorSpeedRatio = 1.0f;

	/** 디버그 드로우를 켠다. 끄면 로그로만 확인한다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test")
	bool bDrawDebug = true;

	/** 이 주기로 상태를 로그에 남긴다. 초. 0이면 끈다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test")
	float LogInterval = 5.0f;

private:
	void SpawnEntities();
	void MovePredators(float DeltaSeconds);
	void DrawDebug() const;
	void LogSummary() const;

	TArray<FMassEntityHandle> Herbivores;
	TArray<FMassEntityHandle> Predators;
	/** 포식자 진행 방향. 간단한 배회 + 추적에 쓴다. */
	TArray<FVector> PredatorHeadings;

	float LogAccumulator = 0.0f;
	bool bSpawned = false;
};
