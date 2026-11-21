#pragma once

#if !UE_BUILD_SHIPPING
#include "AI/Policy/EcoWorldV3.h"
#include "CoreMinimal.h"

namespace EcoMoveBaseline
{
	inline constexpr int64 DefaultSeed = 20000;
	inline constexpr int32 SparseDeer = 128;
	inline constexpr int32 SmallDeer = 32;

	enum EMismatch : uint32
	{
		Kin = 1 << 0, Observation = 1 << 1, Decision = 1 << 2,
		Movement = 1 << 3, Random = 1 << 4, Ledger = 1 << 5, PreMove = 1 << 6
	};

	uint32 CompareNative(const EcoWorldV3::FReferenceWorld& A, const EcoWorldV3::FReferenceWorld& B);

	struct FRow
	{
		int64 Step = 0;
		uint32 Mismatch = 0;
		uint64 FullCandidates = 0, SpatialCandidates = 0, Queries = 0;
		int32 PreMoveRows = 0;
	};

	struct FPair
	{
		EcoWorldV3::FReferenceWorld Full, Spatial;
		TArray<FRow> Rows;
		uint32 Mismatch = 0;
		uint64 FullCandidates = 0, SpatialCandidates = 0, Queries = 0;
		int64 FirstMismatchStep = -1;

		void Init(int64 Seed, int32 Deer, double WorldSize, int32 Steps);
		void Step();

	private:
		void Add(FRow Row);
		std::vector<EcoWorldV3::FHerbPreMoveRow> FullSnapshot, SpatialSnapshot;
		std::vector<EcoWorldV3::FVec2> FullStart, SpatialStart;
	};

	struct FRun
	{
		FPair Sparse, Small;
		int64 Seed = DefaultSeed;
		int32 Completed = 0;

		void Init(int64 InSeed, int32 Steps);
		void Step();
	};
}
#endif
