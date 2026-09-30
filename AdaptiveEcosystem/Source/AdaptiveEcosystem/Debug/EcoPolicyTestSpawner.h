// §9.8-3/§9.8-4 시각 확인용 테스트 액터.
//
// 레벨에 하나 놓고 Play 를 누르면:
//   - 초식/포식자 Mass 엔티티를 반경 안에 스폰한다
//   - §9.4 Policy → §9.5 Steering 프로세서가 자동으로 돌아 개체가 움직인다
//   - 포식자는 파이썬 §4.2 와 같은 규칙으로 움직인다 (시야·배회·벽 반사·식사 쿨다운)
//   - 잡힌 초식은 파이썬 §4.3 처럼 즉시 리스폰한다 — 실제 게임의 Lifecycle 계층 대역
//   - 디버그 드로우로 상태를 그린다 (Mass 표현/ISM 설정 없이도 보인다)
//
// 포식자 AI 를 파이썬과 맞추는 이유: 정책은 그 포식자를 상대로 학습됐다. 여기 포식자가
// 전지적이면(예전처럼 맵 전체의 최근접을 직선 추격) 초식이 먼저 발견하는 이점(see_r 20 >
// pred_view_r 14)이 사라져, 학습 정책이 한 일을 제대로 볼 수 없다.
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

	/**
	 * 포식자 속도 = HerbSpeed × 이 값. 파이썬은 에피소드마다 0.8~1.2 에서 뽑는다 (§4.4).
	 * 1.0 은 그 평균이다. 초식은 항상 최고 속력(§3.3)이라 1.0 이하면 곧게 도망치는 개체는
	 * 못 따라잡는다 — 잡히는 건 방향을 트는 개체다.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test", meta = (ClampMin = "0"))
	float PredatorSpeedRatio = 1.0f;

	/** 디버그 드로우를 켠다. 끄면 로그로만 확인한다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test")
	bool bDrawDebug = true;

	/** 이 주기로 상태를 로그에 남긴다. 초. 0이면 끈다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test")
	float LogInterval = 5.0f;

	/** 초식 표시 크기. **화면 픽셀**이라 줌과 무관하게 같은 크기로 보인다. 0이면 안 그린다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test|Debug", meta = (ClampMin = "0"))
	float HerbivorePointSize = 12.0f;

	/** 초식 진행 방향 선 길이. cm. 0이면 안 그린다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test|Debug", meta = (ClampMin = "0"))
	float HeadingLineLength = 700.0f;

	/** 포식자 X 표시 반폭. cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test|Debug", meta = (ClampMin = "0"))
	float PredatorMarkSize = 450.0f;

	/** 포식자 시야(부채꼴)와 추격선을 그린다. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Test|Debug")
	bool bDrawPredatorView = true;

private:
	void SpawnEntities();
	void RespawnCaught();
	void MovePredators(float DeltaSeconds);
	void DrawDebug() const;
	void LogSummary() const;
	/** 초식 조향이 좌표를 clamp 하는 경계 (더미 월드 제공자). 포식자·리스폰도 이걸 쓴다. */
	float GetWorldExtent() const;

	TArray<FMassEntityHandle> Herbivores;
	TArray<FMassEntityHandle> Predators;
	/** 포식자 진행 방향. 시야 판정과 배회에 쓴다 (파이썬 pred_head). */
	TArray<FVector> PredatorHeadings;
	/** 포식자가 지금 쫓는 초식의 Herbivores 인덱스. 없으면 INDEX_NONE. 표시용. */
	TArray<int32> PredatorTargets;

	/** 파이썬 배회 선회는 스텝 단위라 StepSeconds 마다 한 번씩만 돈다. */
	float WanderAccumulator = 0.0f;
	/** 배회 선회·리스폰 위치. 결정적이어야 같은 장면을 다시 볼 수 있다. */
	FRandomStream SimRand;

	int32 CatchesSinceLog = 0;
	int32 TotalCatches = 0;
	float LogAccumulator = 0.0f;
	bool bSpawned = false;
};
