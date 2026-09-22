// §9.4/§9.5 이웃 조회.
//
// §9.1 은 MassFlock 의 이웃 순회를 이식하라고 하지만 그건 UE 5.1 기준이고, 5.8 까지의
// API 변경 폭이 커서 마이그레이션 위험이 마이그레이션 이득보다 크다고 판단했다.
// 필요한 것은 "반경 내 개체 목록" 하나뿐이라 여기서 직접 만든다.
//
// 자료구조는 균일 격자다. 셀 크기를 시야 반경으로 잡으면 3x3 셀만 보면 된다.
// 개체 수가 수천을 넘어가면 MassNavigation 의 계층 해시 그리드로 갈아탈 수 있지만,
// 그건 개체가 그 그리드에 등록되도록 트레잇을 붙여야 해서 지금은 의존을 만들지 않는다.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"

#include "EcoNeighborhoodSubsystem.generated.h"

/** 격자에 들어가는 한 개체. 조회에 필요한 것만 담는다. */
struct FEcoNeighborEntry
{
	FVector Location = FVector::ZeroVector;
	/** 진행 방향 단위벡터. 시야 각도 판정에 쓴다. */
	FVector Heading = FVector::ForwardVector;
	/** 포식자면 true. §9.5 "이웃 순회에서 FPredatorTag면 조향 대상이 아니라 도주 판정". */
	bool bPredator = false;
	/** 은신처 안이면 true. §4.2 포식자에게는 거리가 CoverHideMult 배로 보인다. */
	bool bInCover = false;
};

/**
 * 매 틱 갱신되는 개체 위치 색인.
 *
 * 쓰는 순서가 정해져 있다:
 *   1. `BeginFrame()`        — 이전 틱 내용을 비운다
 *   2. `Add()` × N           — 게더 프로세서가 개체를 넣는다
 *   3. `Build()`             — 격자를 만든다
 *   4. `QueryRadius()` × N   — 지각·조향 프로세서가 조회한다
 * 3번 전에 조회하면 빈 결과가 나온다. 프로세서 실행 순서로 이를 보장한다.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoNeighborhoodSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	void BeginFrame(float InCellSize);
	int32 Add(const FEcoNeighborEntry& Entry);
	void Build();

	/** 반경 내 개체 인덱스를 모은다. 자기 자신은 호출부가 걸러야 한다. */
	void QueryRadius(const FVector& Location, float Radius, TArray<int32>& OutIndices) const;

	const TArray<FEcoNeighborEntry>& GetEntries() const { return Entries; }
	int32 Num() const { return Entries.Num(); }
	bool IsBuilt() const { return bBuilt; }

	/** §4.2 은신처 안 개체는 포식자에게 이 배수만큼 멀어 보인다. */
	static constexpr float CoverHideMult = 2.5f;

private:
	int64 CellKey(const FVector& Location) const;

	TArray<FEcoNeighborEntry> Entries;
	TMap<int64, TArray<int32>> Cells;
	float CellSize = 1000.0f;
	bool bBuilt = false;
};
