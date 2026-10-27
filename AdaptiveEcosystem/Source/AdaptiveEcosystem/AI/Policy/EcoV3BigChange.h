// 통합 v3 '큰 변화만' 다시 배우기 규칙 (10-27 사용자 결정 — 설계 Docs/RL_Policy/FOREST_GROWTH_MODE.md 2절, LIVE_ADAPT_SPEC.md 5.2).
//
// 자동 스냅숏(= 파이썬 다시 배우기의 계기)을 '큰 변화'일 때만, 그리고 바뀜이 멈춘 뒤 한 번만 쓰게 하는 순수 규칙이다 (엔진·세계 없이 시험한다).
// 세계는 읽기만 한다 — 이 규칙은 스냅숏을 언제 쓰는지만 정한다 (세계에 넣는 것은 EcoV3EnvWatch.cpp ApplyEnvChange 그대로).
//   기준선  Play 시작(지역 세계를 만든 때) 또는 마지막 자동 스냅숏 때의 지역마다 (세계 원판 모음, 날씨 종류).
//   나무    어느 지역이든 지금 세계 원판과 기준선 원판의 대칭차 개수(같은 (x, y, r) 끼리 하나씩 지우고 남은 양쪽 합) ≥ BigTrees.
//   날씨    어느 지역이든 지금 날씨 종류(맑음·비·눈)가 기준선과 다르고 그 종류가 된 뒤 WeatherHold 초 이상 이어짐. 세기만 바뀐 것은 세지 않는다.
//   묶기    조건이 선 뒤, 큰 변화 바뀜(원판·날씨 종류)이 Settle 초 동안 없을 때 한 번 쓴다.
//   기다림  '레벨 바뀜 진행 중'(숲 자람 모드가 아직 목표에 닿지 않음 등)이면 쓰지 않는다. 조건이 선 뒤 MaxWait 초가 지나면 무엇이든 쓴다(상한).
//   쓴 뒤   기준선 = 지금 (Rebase).
// 시간은 모두 전역 결정 스텝 × 2/15 초 (시뮬레이션 초 — Test.At·스냅숏 sim_seconds 와 같은 시계).

#pragma once

#include "CoreMinimal.h"
#include "Templates/Function.h"

#include <vector>

#include "EcoRepertoire.h"
#include "EcoWorldV3.h"

namespace EcoV3BigChange
{
	/** 규칙 값 (콘솔 변수 eco.IntegratedV3.BigTrees·WeatherHold·BigSettle·BigMaxWait — EcoV3Snapshot.cpp). */
	struct FConfig
	{
		int32 BigTrees = 10;              // 한 지역 원판 대칭차 문턱 (1 밑은 1)
		double WeatherHoldSeconds = 120.0; // 바뀐 날씨 종류가 이어져야 하는 시뮬레이션 초
		double SettleSeconds = 20.0;      // 조건이 선 뒤 큰 변화 바뀜이 없어야 하는 시뮬레이션 초
		double MaxWaitSeconds = 300.0;    // 조건이 선 뒤 기다림 상한 (시뮬레이션 초)
	};

	/** 지역 하나의 기준선과 지금. */
	struct FRegion
	{
		FName RegionId;
		std::vector<double> BaseDiscs;   // 기준선 세계 원판 (x, y, r) × K
		std::vector<double> NowDiscs;    // 지금 세계 원판 (원판이 바뀐 묶음마다 다시 적는다)
		int32 BaseKind = EcoWorldV3::kWeatherClear;   // 기준선 날씨 종류
		int32 NowKind = EcoWorldV3::kWeatherClear;    // 지금 날씨 종류
		int64 KindSinceStep = 0;         // 지금 종류가 된 전역 스텝
		int32 Added = 0;                 // 기준선에 없던 지금 원판
		int32 Removed = 0;               // 지금 없는 기준선 원판
		int32 TreeDiff() const { return Added + Removed; }
	};

	/** 규칙 상태 (서브시스템이 하나 쥔다). */
	struct FState
	{
		TArray<FRegion> Regions;         // 컨텍스트 색인 순
		int64 BaselineStep = 0;          // 기준선을 정한 전역 스텝
		int64 LastActivityStep = 0;      // 큰 변화 바뀜(원판·날씨 종류)을 마지막으로 넣은 전역 스텝 (없으면 기준선 스텝)
		int64 ConditionStep = -1;        // 조건이 처음 선 전역 스텝 (-1 = 조건 아님)
		int32 Writes = 0;                // 이 규칙으로 쓴 스냅숏 수
	};

	/** 한 경계의 판정. */
	struct FDecision
	{
		bool bTrees = false;             // 나무 큰 변화
		bool bWeather = false;           // 날씨 큰 변화
		bool bCondition = false;         // 둘 중 하나
		bool bNewCondition = false;      // 이 경계에서 처음 섰다 (Tick 만)
		bool bHold = false;              // '진행 중' 이라 기다린다 (상한 전)
		bool bCapped = false;            // 조건 뒤 MaxWait 초가 지났다 — 무엇이든 쓴다
		bool bWrite = false;             // 이 경계에서 쓴다
		double QuietSeconds = 0.0;       // 마지막 큰 변화 바뀜 뒤 흐른 초
		double WaitSeconds = 0.0;        // 조건이 선 뒤 흐른 초
	};

	inline double StepsToSeconds(int64 Steps)
	{
		return static_cast<double>(Steps) * EcoRepertoireV3::kStepSeconds;
	}

	/** 지역 이름 (화면·기록): 숲·고지·메마른 땅, 그 밖은 ID. */
	inline FString RegionNameKo(FName RegionId)
	{
		return RegionId == FName(TEXT("Forest"))	 ? FString(TEXT("숲"))
			   : RegionId == FName(TEXT("Highland")) ? FString(TEXT("고지"))
			   : RegionId == FName(TEXT("Barren"))	 ? FString(TEXT("메마른 땅"))
													 : RegionId.ToString();
	}

	inline FString WeatherKo(int32 Kind)
	{
		return FString(UTF8_TO_TCHAR(EcoWorldV3::WeatherNameKoUtf8(Kind)));
	}

	/** 대칭차: Now 에만 있는 원판 수(OutAdded)와 Base 에만 있는 원판 수(OutRemoved). 같은 (x, y, r) 를 하나씩 지운다 (EcoV3EnvWatch.cpp MinusDiscs 두 번과 같다). */
	inline void CountDiff(const std::vector<double>& Now, const std::vector<double>& Base, int32& OutAdded, int32& OutRemoved)
	{
		const int32 NumNow = static_cast<int32>(Now.size() / 3);
		const int32 NumBase = static_cast<int32>(Base.size() / 3);
		TArray<bool> Used;
		Used.Init(false, NumBase);
		int32 Matched = 0;
		for (int32 k = 0; k < NumNow; ++k)
		{
			for (int32 j = 0; j < NumBase; ++j)
			{
				if (!Used[j] && Now[3 * k] == Base[3 * j] && Now[3 * k + 1] == Base[3 * j + 1] && Now[3 * k + 2] == Base[3 * j + 2])
				{
					Used[j] = true;
					++Matched;
					break;
				}
			}
		}
		OutAdded = NumNow - Matched;
		OutRemoved = NumBase - Matched;
	}

	/** 지역 세계가 생겼다 (기준선 = 지금). 컨텍스트 색인 순서로 부른다. */
	inline void AddRegion(FState& S, FName RegionId, const std::vector<double>& Discs, int32 Kind, int64 Step)
	{
		FRegion& R = S.Regions.AddDefaulted_GetRef();
		R.RegionId = RegionId;
		R.BaseDiscs = Discs;
		R.NowDiscs = Discs;
		R.BaseKind = Kind;
		R.NowKind = Kind;
		R.KindSinceStep = Step;
		if (S.Regions.Num() == 1)
		{
			S.BaselineStep = Step;
			S.LastActivityStep = Step;
			S.ConditionStep = -1;
		}
	}

	/** 지역 Index 의 원판이 바뀐 묶음을 넣었다 (결정 스텝 경계 Step) — 큰 변화 바뀜. */
	inline void OnTrees(FState& S, int32 Index, const std::vector<double>& NowDiscs, int64 Step)
	{
		if (!S.Regions.IsValidIndex(Index))
		{
			return;
		}
		FRegion& R = S.Regions[Index];
		R.NowDiscs = NowDiscs;
		CountDiff(R.NowDiscs, R.BaseDiscs, R.Added, R.Removed);
		S.LastActivityStep = Step;
	}

	/** 지역 Index 의 날씨를 넣었다. 종류가 바뀌었을 때만 큰 변화 바뀜이다 (세기만 바뀐 것은 아무것도 하지 않는다). 종류가 바뀌었으면 참. */
	inline bool OnWeather(FState& S, int32 Index, int32 NewKind, int64 Step)
	{
		if (!S.Regions.IsValidIndex(Index) || S.Regions[Index].NowKind == NewKind)
		{
			return false;
		}
		FRegion& R = S.Regions[Index];
		R.NowKind = NewKind;
		R.KindSinceStep = Step;
		S.LastActivityStep = Step;
		return true;
	}

	/** 판정 (상태를 바꾸지 않는다 — 화면 줄). bHold = '레벨 바뀜 진행 중'. */
	inline FDecision Evaluate(const FState& S, const FConfig& C, int64 Step, bool bHold)
	{
		FDecision D;
		const int32 Big = FMath::Max(1, C.BigTrees);
		for (const FRegion& R : S.Regions)
		{
			D.bTrees = D.bTrees || R.TreeDiff() >= Big;
			D.bWeather = D.bWeather || (R.NowKind != R.BaseKind && StepsToSeconds(Step - R.KindSinceStep) + 1e-9 >= C.WeatherHoldSeconds);
		}
		D.bCondition = D.bTrees || D.bWeather;
		if (!D.bCondition)
		{
			return D;
		}
		const int64 Since = S.ConditionStep >= 0 ? S.ConditionStep : Step;
		D.QuietSeconds = StepsToSeconds(Step - S.LastActivityStep);
		D.WaitSeconds = StepsToSeconds(Step - Since);
		D.bCapped = D.WaitSeconds + 1e-9 >= C.MaxWaitSeconds;
		D.bHold = bHold && !D.bCapped;
		D.bWrite = D.bCapped || (!D.bHold && D.QuietSeconds + 1e-9 >= C.SettleSeconds);
		return D;
	}

	/** 결정 스텝 경계마다 (MaybeAutoSnapshot): 판정하고 조건이 선 스텝을 적는다 (조건이 없어지면 지운다). */
	inline FDecision Tick(FState& S, const FConfig& C, int64 Step, bool bHold)
	{
		FDecision D = Evaluate(S, C, Step, bHold);
		if (!D.bCondition)
		{
			S.ConditionStep = -1;
			return D;
		}
		if (S.ConditionStep < 0)
		{
			S.ConditionStep = Step;
			D.bNewCondition = true;
		}
		return D;
	}

	/** 썼다 — 기준선 = 지금, 바뀜 시계·조건 지움. */
	inline void Rebase(FState& S, int64 Step)
	{
		for (FRegion& R : S.Regions)
		{
			R.BaseDiscs = R.NowDiscs;
			R.BaseKind = R.NowKind;
			R.Added = 0;
			R.Removed = 0;
		}
		S.BaselineStep = Step;
		S.LastActivityStep = Step;
		S.ConditionStep = -1;
		++S.Writes;
	}

	/** 원판 바뀜 글자: '+7' (더하기만)·'−3' (지우기만)·'±7' (섞임). */
	inline FString TreeDiffText(const FRegion& R)
	{
		const TCHAR* Sign = R.Removed == 0 ? TEXT("+") : R.Added == 0 ? TEXT("−") : TEXT("±");
		return FString::Printf(TEXT("%s%d"), Sign, R.TreeDiff());
	}

	/** 가장 많이 바뀐 지역 (같으면 앞 지역), 바뀜이 없으면 INDEX_NONE. */
	inline int32 TopTreeRegion(const FState& S)
	{
		int32 Best = INDEX_NONE;
		for (int32 i = 0; i < S.Regions.Num(); ++i)
		{
			if (S.Regions[i].TreeDiff() > 0 && (Best == INDEX_NONE || S.Regions[i].TreeDiff() > S.Regions[Best].TreeDiff()))
			{
				Best = i;
			}
		}
		return Best;
	}

	/** 기준선과 종류가 다른 지역 가운데 가장 오래 이어진 곳, 없으면 INDEX_NONE. */
	inline int32 TopWeatherRegion(const FState& S)
	{
		int32 Best = INDEX_NONE;
		for (int32 i = 0; i < S.Regions.Num(); ++i)
		{
			const FRegion& R = S.Regions[i];
			if (R.NowKind != R.BaseKind && (Best == INDEX_NONE || R.KindSinceStep < S.Regions[Best].KindSinceStep))
			{
				Best = i;
			}
		}
		return Best;
	}

	/** 나무·날씨 요약 (기록·까닭): '메마른 땅 나무 +12/10 · 날씨 그대로'. */
	inline FString SummaryText(const FState& S, const FConfig& C, int64 Step)
	{
		const int32 T = TopTreeRegion(S);
		const FString Trees = T == INDEX_NONE ? FString(TEXT("나무 그대로"))
											  : FString::Printf(TEXT("%s 나무 %s/%d"), *RegionNameKo(S.Regions[T].RegionId), *TreeDiffText(S.Regions[T]),
																FMath::Max(1, C.BigTrees));
		const int32 W = TopWeatherRegion(S);
		const FString Weather = W == INDEX_NONE ? FString(TEXT("날씨 그대로"))
												: FString::Printf(TEXT("%s 날씨 %s→%s %.0f/%.0f초"), *RegionNameKo(S.Regions[W].RegionId),
																  *WeatherKo(S.Regions[W].BaseKind), *WeatherKo(S.Regions[W].NowKind),
																  StepsToSeconds(Step - S.Regions[W].KindSinceStep), C.WeatherHoldSeconds);
		return FString::Printf(TEXT("%s · %s"), *Trees, *Weather);
	}

	/**
	 * 상태 줄 칸: 쌓는 중 '다시 배우기까지: 메마른 땅 나무 +7/10 · 날씨 그대로', 조건 됨 '다시 배우기: 조건 됨 — <HoldWhat> 기다림' 또는
	 * '다시 배우기: 조건 됨 — 바뀜이 멈추길 기다림 12/20초'. HoldWhat = 진행 중 표시 (예 '숲이 다 자랄 때까지').
	 */
	inline FString ProgressText(const FState& S, const FConfig& C, int64 Step, bool bHold, const FString& HoldWhat)
	{
		const FDecision D = Evaluate(S, C, Step, bHold);
		if (!D.bCondition)
		{
			return FString::Printf(TEXT("다시 배우기까지: %s"), *SummaryText(S, C, Step));
		}
		if (D.bHold)
		{
			return FString::Printf(TEXT("다시 배우기: 조건 됨 — %s 기다림 (%.0f/%.0f초)"), HoldWhat.IsEmpty() ? TEXT("레벨 바뀜이 끝날 때까지") : *HoldWhat,
								   D.WaitSeconds, C.MaxWaitSeconds);
		}
		return FString::Printf(TEXT("다시 배우기: 조건 됨 — 바뀜이 멈추길 기다림 %.0f/%.0f초"), FMath::Min(D.QuietSeconds, C.SettleSeconds), C.SettleSeconds);
	}
}
