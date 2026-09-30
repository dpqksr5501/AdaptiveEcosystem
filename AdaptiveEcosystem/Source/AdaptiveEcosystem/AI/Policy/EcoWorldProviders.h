// §9.4 월드팀 인터페이스 + 더미 구현.
//
// 정책이 쓰는 관측 7개 중 둘은 월드(지형·식생)에서 온다:
//   food_density   IEcoWorldFoodProvider::GetFoodDensity(Location, Radius)
//   cover_distance IEcoWorldCoverProvider::GetCoverDistance(Location)
//
// §9.4: "월드팀 인터페이스는 **더미 구현**을 함께 만든다 (평면 + 고정 패턴).
// 최소 테스트 레벨용." — 그래야 월드팀 작업과 무관하게 정책 파이프라인을 돌려볼 수 있다.
//
// 조향에는 밀도가 아니라 **기울기**가 필요하다 (§3.3 food_grad). 파이썬에서도 관측용
// 밀도(see_r 반경 평균)와 조향용 기울기(좁은 반경)를 분리해 뒀다 — 넓은 반경에서 뽑은
// 기울기는 국소 고갈에 반응하지 못해 개체가 전부 한 곳에 몰린다.
// 근거: herbivore_rl/docs/phase1_env_calibration.md §2.1

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "UObject/Interface.h"

#include "EcoWorldProviders.generated.h"

UINTERFACE(MinimalAPI, BlueprintType)
class UEcoWorldFoodProvider : public UInterface
{
	GENERATED_BODY()
};

class ADAPTIVEECOSYSTEM_API IEcoWorldFoodProvider
{
	GENERATED_BODY()

public:
	/** 반경 내 먹이 풍부도 평균. 반환값은 [0,1] 이어야 한다 (§3.1 관측 0번). */
	virtual float GetFoodDensity(const FVector& Location, float Radius) const = 0;

	/** 먹이가 많아지는 방향. **단위벡터 또는 영벡터**. §3.3 food_grad. */
	virtual FVector GetFoodGradient(const FVector& Location, float Radius) const = 0;

	/** 개체가 이 위치에서 먹이를 소비한다. 반환값은 실제로 먹은 양. */
	virtual float ConsumeFood(const FVector& Location, float Amount) = 0;
};

UINTERFACE(MinimalAPI, BlueprintType)
class UEcoWorldCoverProvider : public UInterface
{
	GENERATED_BODY()
};

class ADAPTIVEECOSYSTEM_API IEcoWorldCoverProvider
{
	GENERATED_BODY()

public:
	/** 가장 가까운 은신처 가장자리까지 거리. 안에 있으면 0. cm. */
	virtual float GetCoverDistance(const FVector& Location) const = 0;

	/** 가장 가까운 은신처 방향. 이미 안이면 **영벡터**. §3.3 to_cover. */
	virtual FVector GetCoverDirection(const FVector& Location) const = 0;

	/** 이 위치가 은신처 안인가. 포식자 감지 거리 보정에 쓴다 (§4.2 2.5배). */
	virtual bool IsInCover(const FVector& Location) const = 0;
};

/**
 * §9.4 더미 구현 — 평면 + 고정 패턴. 최소 테스트 레벨용.
 *
 * 월드팀 구현이 붙기 전까지 정책·조향 프로세서를 돌려보는 용도다. 실제 생태계 자원과는
 * 무관하며, 월드팀 구현이 생기면 `UEcoWorldProviderRegistry` 가 그쪽을 가리키게 한다.
 *
 * 먹이: 저주파 사인 격자. 파이썬 환경의 "패치" 구조를 대충 흉내 낸다 (연속이라 기울기가
 *       해석적으로 나오고, 국소 소비를 `ConsumedGrid` 로 빼서 고갈도 반영한다).
 * 은신처: 원점 주변 고정 4곳.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoDummyWorldProviderSubsystem
	: public UWorldSubsystem
	, public IEcoWorldFoodProvider
	, public IEcoWorldCoverProvider
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	// IEcoWorldFoodProvider
	virtual float GetFoodDensity(const FVector& Location, float Radius) const override;
	virtual FVector GetFoodGradient(const FVector& Location, float Radius) const override;
	virtual float ConsumeFood(const FVector& Location, float Amount) override;

	// IEcoWorldCoverProvider
	virtual float GetCoverDistance(const FVector& Location) const override;
	virtual FVector GetCoverDirection(const FVector& Location) const override;
	virtual bool IsInCover(const FVector& Location) const override;

	/** 소비분이 시간에 따라 회복된다. 테스트 레벨에서 먹이가 영구 고갈되지 않도록. */
	void RegenerateConsumed(float DeltaSeconds);

	/** 맵 반경. 경계 반발·좌표 clamp(§9.5)와 은신처 배치에 쓴다. cm.
	 *
	 * 15000 = L_EcoPolicyTest 의 바닥(Plane 스케일 300 → 반경 15000cm)과 같은 값이다.
	 * 전에는 20000 이라 개체가 바닥 밖 50m 띠까지 걸어 나갔다 — 오류가 아니라 시뮬레이션
	 * 경계와 눈에 보이는 바닥이 안 맞았을 뿐이다. 바닥을 바꾸면 이 값도 같이 바꿔야 한다.
	 */
	UPROPERTY(EditAnywhere, Category = "Ecology|World|Dummy")
	float WorldExtent = 15000.0f;

	/** 은신처 중심들 (XY). 디버그 표시용이다 — 판정은 IsInCover() 로 한다. */
	const TArray<FVector>& GetCoverPoints() const { return CoverPoints; }
	float GetCoverRadius() const { return CoverRadius; }

protected:
	/** 사인 패턴의 파장. cm. 클수록 먹이 패치가 넓다. */
	UPROPERTY(EditAnywhere, Category = "Ecology|World|Dummy")
	float FoodWavelength = 6000.0f;

	/** 이 값 아래는 먹이 0으로 자른다. 빈 영역을 만들어 탐색이 의미를 갖게 한다. */
	UPROPERTY(EditAnywhere, Category = "Ecology|World|Dummy")
	float FoodThreshold = 0.35f;

	UPROPERTY(EditAnywhere, Category = "Ecology|World|Dummy")
	float ConsumeRegenPerSecond = 0.02f;

	UPROPERTY(EditAnywhere, Category = "Ecology|World|Dummy")
	float CoverRadius = 2500.0f;

	/** 고정 은신처 위치 (XY). Initialize 에서 채운다. */
	UPROPERTY(Transient)
	TArray<FVector> CoverPoints;

private:
	/** 소비 격자. 키는 셀 인덱스, 값은 깎인 양 [0,1]. */
	TMap<int64, float> ConsumedGrid;

	float RawFoodAt(const FVector& Location) const;
	int64 CellKey(const FVector& Location) const;
	static constexpr float FoodCellCm = 400.0f;
};

/**
 * 정책 프로세서가 월드 제공자를 찾는 단일 진입점.
 *
 * 월드팀 구현이 있으면 그걸 쓰고, 없으면 더미로 떨어진다. 프로세서가 더미를 직접
 * 알지 않게 하려는 것이다 — 나중에 구현이 바뀌어도 프로세서는 그대로다.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoWorldProviderRegistry : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	/** 등록된 구현이 없으면 더미를 돌려준다. 널이 아님을 보장한다. */
	IEcoWorldFoodProvider* GetFoodProvider() const { return FoodProvider; }
	IEcoWorldCoverProvider* GetCoverProvider() const { return CoverProvider; }

	/** 월드팀이 자기 구현을 끼워 넣는 지점. */
	void SetFoodProvider(IEcoWorldFoodProvider* InProvider) { FoodProvider = InProvider; }
	void SetCoverProvider(IEcoWorldCoverProvider* InProvider) { CoverProvider = InProvider; }

private:
	IEcoWorldFoodProvider* FoodProvider = nullptr;
	IEcoWorldCoverProvider* CoverProvider = nullptr;
};
