// 통합 v3 숲 자람 모드 — 순수 계획 (10-27 사용자 결정 '모드를 하나 만들어서 해당 모드에서는 숲이 점점 자라게', 설계 Docs/RL_Policy/FOREST_GROWTH_MODE.md 1절).
//
// 레벨 팀이 할 '숲이 자라는 레벨 바뀜'을 흉내 내는 시험 모드다 — 세계 규칙이 아니다. 여기에는 엔진 없이 시험하는 시간표·자리 고르기만 있다.
// 실행(묘목 놓기·다 자람·세계에 넣기·화면)은 EcoV3ForestGrowth.cpp, 복제 나무 액터는 EcoV3ForestTree.{h,cpp}.
//   시간표  단계 k (0..K−1, K = ⌈놓은 수 ÷ 단계 그루⌉): 묘목 돋음 = 반올림((첫 단계 초 + k × 단계 간격) ÷ 2/15) 전역 스텝,
//           다 자람 = 반올림((첫 단계 초 + k × 단계 간격 + 자람 초) ÷ 2/15). 기본 30·70·110·150 초 돋음, 50·90·130·170 초(스텝 375·675·975·1275) 다 자람.
//   자리    Play 시작 때 목표 수만큼 한꺼번에: eco.IntegratedV3.Test.AddTrees 와 같은 규칙 — 크기 1.8~2.2·방위 0~360°, 줄기 가장자리가 벽에서 4 m·
//           은신처 원 둘레에서 2 m·다른 원판(그때 세계 원판 + 앞서 고른 숲 자리)에서 3 m 밖, 땅(가운데 점 필수)에 붙임, 한 그루에 400 번 시도.
//           난수 = HashChain3("V3FG", 씨, 지역 색인 + 1) 하나에서 그루 순서대로 뽑는다 (뽑는 순서 = 크기·방위·X·Y — Test.AddTrees 와 같다). 씨가 같으면 같은 자리.
//           못 찾은 그루는 빼고 (기록) 놓은 수가 그만큼 준다.

#pragma once

#include "CoreMinimal.h"
#include "Templates/Function.h"

#include <vector>

#include "EcoObservationV3.h"
#include "EcoRepertoire.h"
#include "EcoWorldV3.h"
#include "TreeLayoutV3.h"

namespace EcoV3Forest
{
	/** 숲 자리 난수의 첫 해시 입력 (세계·시작 자리·시험용 나무 난수와 다른 값). */
	inline constexpr uint64 kForestTag = 0x56334647ULL;   // "V3FG"
	/** 줄기 사이 틈 (m — Test.AddTrees·배치 표와 같은 3 m). */
	inline constexpr double kGapM = 3.0;
	/** 한 그루에 자리를 찾는 횟수. */
	inline constexpr int32 kTries = 400;
	/** 목표 상한. */
	inline constexpr int32 kMaxTarget = 64;

	/** 설정 (Play 시작 때 콘솔 변수 eco.IntegratedV3.Forest* 에서 한 번 읽는다 — 시험은 직접 채운다). */
	struct FSettings
	{
		bool bOn = false;                    // eco.IntegratedV3.ForestGrowth
		FName Region = FName(TEXT("Barren")); // eco.IntegratedV3.ForestRegion (메마른 땅이 숲이 되는 이야기)
		int32 PerStage = 6;                  // eco.IntegratedV3.ForestPerStage — 한 단계에 돋는 그루 수
		double StageSeconds = 40.0;          // eco.IntegratedV3.ForestStageSeconds — 단계 간격 (시뮬레이션 초)
		double GrowSeconds = 20.0;           // eco.IntegratedV3.ForestGrowSeconds — 묘목이 다 자라는 시뮬레이션 초
		int32 Target = 24;                   // eco.IntegratedV3.ForestTarget — 이 수에서 멈춤
		double StartSeconds = 30.0;          // eco.IntegratedV3.ForestStartSeconds — 첫 단계 시뮬레이션 초
		int64 Seed = -1;                     // eco.IntegratedV3.ForestSeed (−1 = 세션 시드)
		double SaplingFrac = 0.15;           // eco.IntegratedV3.ForestSapling — 묘목 처음 크기 몫 (그리기만)
	};

	/** 값 자르기: 단계 그루 1~64, 간격 1~3600 초, 자람 1~600 초, 목표 1~64, 첫 단계 0~36000 초, 묘목 몫 0.01~1. 수가 아니면 기본값. */
	inline FSettings Sanitize(FSettings S)
	{
		const FSettings D;
		auto Clamp = [](double V, double Lo, double Hi, double Def) { return FMath::IsFinite(V) ? FMath::Clamp(V, Lo, Hi) : Def; };
		S.PerStage = FMath::Clamp(S.PerStage, 1, kMaxTarget);
		S.Target = FMath::Clamp(S.Target, 1, kMaxTarget);
		S.StageSeconds = Clamp(S.StageSeconds, 1.0, 3600.0, D.StageSeconds);
		S.GrowSeconds = Clamp(S.GrowSeconds, 1.0, 600.0, D.GrowSeconds);
		S.StartSeconds = Clamp(S.StartSeconds, 0.0, 36000.0, D.StartSeconds);
		S.SaplingFrac = Clamp(S.SaplingFrac, 0.01, 1.0, D.SaplingFrac);
		if (S.Region.IsNone())
		{
			S.Region = D.Region;
		}
		return S;
	}

	/** 시뮬레이션 초 → 전역 결정 스텝 (반올림, 0.5 는 올림 — FEcoV3IntegratedSettings::WolfEatSteps 와 같은 식). */
	inline int64 SecondsToSteps(double Seconds)
	{
		return static_cast<int64>(FMath::FloorToDouble(Seconds / EcoRepertoireV3::kStepSeconds + 0.5));
	}

	/** 단계 수 = ⌈놓은 수 ÷ 단계 그루⌉. */
	inline int32 NumStages(const FSettings& S, int32 Planned)
	{
		const int32 Per = FMath::Max(1, S.PerStage);
		return Planned <= 0 ? 0 : (Planned + Per - 1) / Per;
	}

	/** 자리 순번 → 단계. */
	inline int32 StageOfSlot(const FSettings& S, int32 Slot)
	{
		return Slot / FMath::Max(1, S.PerStage);
	}

	/** 단계 k 묘목이 돋는 전역 스텝. */
	inline int64 SproutStep(const FSettings& S, int32 Stage)
	{
		return SecondsToSteps(S.StartSeconds + static_cast<double>(Stage) * S.StageSeconds);
	}

	/** 단계 k 가 다 자라 세계에 들어가는 전역 스텝. */
	inline int64 MatureStep(const FSettings& S, int32 Stage)
	{
		return SecondsToSteps(S.StartSeconds + static_cast<double>(Stage) * S.StageSeconds + S.GrowSeconds);
	}

	/** 자리 난수 시작 상태 (지역 색인 = 팀 RegionRuntimeIndex — 음수는 0). */
	inline uint64 RngState(int64 Seed, int32 RegionRuntimeIndex)
	{
		return EcoRepertoireV3::HashChain3(kForestTag, static_cast<uint64>(Seed), static_cast<uint64>(FMath::Max(0, RegionRuntimeIndex)) + 1);
	}

	/** 숲 자리 하나 (무대 단위 — 줄기 원판 (Tree.X, Tree.Y, Tree.R), 땅 = 줄기 아래 가장 낮은 땅 cm). */
	struct FSlot
	{
		EcoTreeLayoutV3::FTree Tree{};
		double GroundMinZ = 0.0;
		int32 Index = 0;   // 놓은 순번 (F<nn>)
	};

	/**
	 * 목표 수만큼 자리를 고른다 (순수 — 땅은 Ground 로 묻는다). MakeTree = UEcoPolicyV3IntegratedSubsystem::MakeLevelTree (X, Y, 크기, 방위 → 줄기 원판·기준점).
	 * Avoid = 피할 원판 (x, y, r) × K (그때 세계 원판 등). 고른 자리는 다음 그루의 피할 원판에 더한다. 고른 수 (OutMissing = 못 찾은 수).
	 */
	inline int32 PlanSlots(int32 Target, double SizeUnits, const std::vector<EcoObservationV3::FCoverInput>& Covers, std::vector<double> Avoid, uint64 InRngState,
						   TFunctionRef<EcoTreeLayoutV3::FTree(double X, double Y, double Scale, double YawDeg)> MakeTree,
						   TFunctionRef<bool(const EcoTreeLayoutV3::FTree& T, double& OutMinZ)> Ground, TArray<FSlot>& Out, int32& OutMissing)
	{
		using EcoRepertoireV3::kUnitCm;
		Out.Reset();
		OutMissing = 0;
		EcoWorldV3::FRng Rng;
		Rng.State = InRngState;
		const double Wall = EcoTreeLayoutV3::kWallClearM * 100.0 / kUnitCm;
		const double Clear = EcoTreeLayoutV3::kCoverClearM * 100.0 / kUnitCm;
		const double Gap = kGapM * 100.0 / kUnitCm;
		Target = FMath::Clamp(Target, 0, kMaxTarget);
		for (int32 n = 0; n < Target; ++n)
		{
			bool bPlaced = false;
			for (int32 Try = 0; Try < kTries && !bPlaced; ++Try)
			{
				// 뽑는 순서·식 = UEcoPolicyV3IntegratedSubsystem::TestAddTrees
				const double Scale = Rng.Uniform(EcoTreeLayoutV3::kScaleLo, EcoTreeLayoutV3::kScaleHi);
				const double Yaw = Rng.Uniform(0.0, 360.0);
				const double R = EcoTreeLayoutV3::kTrunkRadiusMeshCm * Scale / kUnitCm;
				const double X = Rng.Uniform(Wall + R, SizeUnits - Wall - R);
				const double Y = Rng.Uniform(Wall + R, SizeUnits - Wall - R);
				bool bFree = true;
				for (const EcoObservationV3::FCoverInput& Cv : Covers)
				{
					bFree = bFree && !(Cv.Radius > 0.0 && FMath::Sqrt(FMath::Square(X - Cv.X) + FMath::Square(Y - Cv.Y)) < Cv.Radius + Clear + R);
				}
				for (size_t k = 0; bFree && k + 2 < Avoid.size(); k += 3)
				{
					bFree = FMath::Sqrt(FMath::Square(X - Avoid[k]) + FMath::Square(Y - Avoid[k + 1])) >= Avoid[k + 2] + R + Gap;
				}
				if (!bFree)
				{
					continue;
				}
				const EcoTreeLayoutV3::FTree T = MakeTree(X, Y, Scale, Yaw);
				double MinZ = 0.0;
				if (!Ground(T, MinZ))
				{
					continue;
				}
				FSlot& S = Out.AddDefaulted_GetRef();
				S.Tree = T;
				S.GroundMinZ = MinZ;
				S.Index = Out.Num() - 1;
				Avoid.insert(Avoid.end(), {T.X, T.Y, T.R});
				bPlaced = true;
			}
			OutMissing += bPlaced ? 0 : 1;
		}
		return Out.Num();
	}

	/** 묘목 크기 몫 (그리기만): 몫 + (1 − 몫) × smoothstep(경과 ÷ 자람 초). */
	inline double GrowFraction(double ElapsedSeconds, double GrowSeconds, double SaplingFrac)
	{
		const double U = GrowSeconds > 0.0 ? FMath::Clamp(ElapsedSeconds / GrowSeconds, 0.0, 1.0) : 1.0;
		const double Smooth = U * U * (3.0 - 2.0 * U);
		return SaplingFrac + (1.0 - SaplingFrac) * Smooth;
	}
}
