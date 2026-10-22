// 통합 v3 도망 기록 화면·기록 집계 (10-21 사용자 결정 (a) '게임 화면에 도망 시간 — 두뇌 교체 전·후도'). 기록만 — 세계·두뇌에 쓰지 않는다.
//
// 재료는 지역 세계의 누적 도망 기록 EcoWorldV3::FWorldStats::Flight (FWorldConfig::bFlightStats — 정의는 EcoWorldV3.h 머리 주석 '도망 기록',
// 파이썬 world.py `flight_stats` 와 같다). 결정 스텝마다 누적을 한 번 넣고(FTally::Push) 두 가지를 낸다:
//   (i)  최근 60 초 창 (kWindowSteps = 450 결정 스텝): 그 사이에 끝난 도망 — 지금 누적 − 450 스텝 전 누적 (Play 시작이 450 스텝 안이면 시작부터)
//   (ii) 두뇌 판 합: 두뇌가 바뀔 때(OnBrainSwap — 되돌림 포함) 지금 판의 합을 '교체 전'으로 넘기고 새 판을 0 에서 센다. 바뀌는 순간 열려 있던 도망은
//        끝나는 판(새 판)에 든다
// 화면의 '쫓긴' = 스스로 벗어난 도망(은신처·나무·시야각 밖·시야 밖)의 쫓긴 시간 평균 — 실시간 고리 관문 1차(results/v3/live/LIVE_GATE.md 5-1 P1)와 같은 재료다.
// 교체 전·지금 비교는 두 판 모두 스스로 벗어난 도망이 kMinCompare 번 이상일 때만 숫자로 (적으면 '모으는 중'). 판정이 아니라 화면 비교다 (관문은 파이썬 쪽).

#pragma once

#include "CoreMinimal.h"
#include "EcoWorldV3.h"

namespace EcoV3Flight
{
	inline constexpr int32 kWindowSteps = 450;   // 최근 60 초 (1 결정 스텝 = 2/15 초)
	inline constexpr int32 kMinCompare = 10;     // 교체 전·지금 비교에 필요한 판마다 스스로 벗어난 도망 수

	/** 끝난 도망 합 (FFlightStats 에서 화면에 쓰는 칸만). 누적끼리 빼면 구간 합이다. 잘림(열린 도망)은 넣지 않는다. */
	struct FSum
	{
		int64 Started = 0;                              // 시작한 도망
		int64 Ended = 0;                                // 끝난 도망 (모든 끝 까닭)
		int64 EndedSteps = 0;                           // 그 실행한 FLEE 스텝 합
		int64 Own[EcoWorldV3::kNumFlightOwn] = {};      // 스스로 벗어난 도망 (은신처·나무·시야각 밖·시야 밖)
		int64 OwnSteps = 0;                             // 그 FLEE 스텝 합
		int64 OwnContact = 0;                           // 그 쫓긴 스텝 합 (관문 1차 재료)
		int64 Unsafe = 0;                               // 잡힘·굶음으로 끝난 도망

		static FSum Of(const EcoWorldV3::FFlightStats& S)
		{
			FSum R;
			R.Started = S.Started;
			for (int32 c = 0; c < EcoWorldV3::kNumFlightCauses; ++c)
			{
				R.Ended += S.Num[c];
				R.EndedSteps += S.Steps[c];
			}
			for (int32 c = 0; c < EcoWorldV3::kNumFlightOwn; ++c)
			{
				R.Own[c] = S.Num[c];
				R.OwnSteps += S.Steps[c];
				R.OwnContact += S.Contact[c];
			}
			R.Unsafe = S.Num[EcoWorldV3::kFlightCaught] + S.Num[EcoWorldV3::kFlightStarved];
			return R;
		}

		FSum Plus(const FSum& O, int64 Sign = 1) const
		{
			FSum R;
			R.Started = Started + Sign * O.Started;
			R.Ended = Ended + Sign * O.Ended;
			R.EndedSteps = EndedSteps + Sign * O.EndedSteps;
			for (int32 c = 0; c < EcoWorldV3::kNumFlightOwn; ++c)
			{
				R.Own[c] = Own[c] + Sign * O.Own[c];
			}
			R.OwnSteps = OwnSteps + Sign * O.OwnSteps;
			R.OwnContact = OwnContact + Sign * O.OwnContact;
			R.Unsafe = Unsafe + Sign * O.Unsafe;
			return R;
		}
		FSum Minus(const FSum& O) const { return Plus(O, -1); }

		bool operator==(const FSum& O) const
		{
			bool bSame = Started == O.Started && Ended == O.Ended && EndedSteps == O.EndedSteps && OwnSteps == O.OwnSteps && OwnContact == O.OwnContact
						 && Unsafe == O.Unsafe;
			for (int32 c = 0; c < EcoWorldV3::kNumFlightOwn; ++c)
			{
				bSame = bSame && Own[c] == O.Own[c];
			}
			return bSame;
		}

		int64 OwnN() const
		{
			int64 N = 0;
			for (const int64 V : Own)
			{
				N += V;
			}
			return N;
		}
		/** 끝난 도망 평균 길이 (초). 없으면 0. */
		double MeanSeconds() const { return Ended > 0 ? static_cast<double>(EndedSteps) * EcoRepertoireV3::kStepSeconds / static_cast<double>(Ended) : 0.0; }
		/** 스스로 벗어난 도망의 쫓긴 시간 평균 (초, 관문 1차). 없으면 0. */
		double OwnChaseSeconds() const
		{
			const int64 N = OwnN();
			return N > 0 ? static_cast<double>(OwnContact) * EcoRepertoireV3::kStepSeconds / static_cast<double>(N) : 0.0;
		}
		/** 끝난 도망 가운데 스스로 벗어난 몫 (0~1). */
		double OwnShare() const { return Ended > 0 ? static_cast<double>(OwnN()) / static_cast<double>(Ended) : 0.0; }
	};

	/** 한 지역의 창·두뇌 판 장부 (FEcoV3RegionContext::FlightTally). */
	struct FTally
	{
		TArray<FSum> Ring;      // 결정 스텝마다 넣은 누적 (최근 kWindowSteps + 1 개 — 처음 칸은 시작 0)
		int32 Head = 0;         // 다음에 쓸 칸
		int32 Count = 0;        // 든 칸 수
		int64 Pushes = 0;       // 넣은 결정 스텝 수 (시작 0 빼고)
		FSum Latest;            // 마지막으로 넣은 누적
		FSum GenBase;           // 지금 두뇌 판이 시작될 때의 누적
		FSum PrevGen;           // 바로 앞 두뇌 판의 합 ('교체 전')
		bool bHasPrev = false;  // 이 Play 에서 두뇌가 바뀐 적이 있다
		int32 Swaps = 0;        // 바뀐 횟수 (되돌림 포함)

		/** 모두 처음으로 (창·두뇌 판). */
		void Reset()
		{
			Ring.Reset();
			EnsureRing();
			Latest = FSum();
			GenBase = FSum();
			PrevGen = FSum();
			bHasPrev = false;
			Swaps = 0;
		}

		/** 창 칸을 처음 한 번 연다 (처음 칸 = 시작 0). 두뇌 판 칸은 건드리지 않는다 — 첫 결정 스텝 전에 바뀐 두뇌(OnBrainSwap)를 지우지 않게. */
		void EnsureRing()
		{
			if (Ring.Num() != kWindowSteps + 1)
			{
				Ring.Init(FSum(), kWindowSteps + 1);
				Head = 1;
				Count = 1;
				Pushes = 0;
			}
		}

		/** 결정 스텝 하나 끝: 그 스텝 뒤 누적. */
		void Push(const FSum& Cum)
		{
			EnsureRing();
			Ring[Head] = Cum;
			Head = (Head + 1) % Ring.Num();
			Count = FMath::Min(Count + 1, Ring.Num());
			Latest = Cum;
			++Pushes;
		}

		/** 최근 kWindowSteps 결정 스텝에 끝난 도망 (Play 시작이 그 안이면 시작부터). */
		FSum Window() const
		{
			if (Ring.Num() == 0 || Count == 0)
			{
				return Latest;
			}
			const int32 Oldest = (Head - Count + Ring.Num()) % Ring.Num();
			return Latest.Minus(Ring[Oldest]);
		}

		/** 창이 덮는 결정 스텝 수 (≤ kWindowSteps). */
		int64 WindowSteps() const { return FMath::Min<int64>(Pushes, kWindowSteps); }

		/** 지금 두뇌 판의 합. */
		FSum CurrentGen() const { return Latest.Minus(GenBase); }

		/** 두뇌가 바뀜 (결정 스텝 경계 — Cum = 그때 누적): 지금 판의 합을 '교체 전'으로, 새 판은 0 에서. */
		void OnBrainSwap(const FSum& Cum)
		{
			EnsureRing();
			Latest = Cum;
			PrevGen = Cum.Minus(GenBase);
			GenBase = Cum;
			bHasPrev = true;
			++Swaps;
		}
	};

	/** 스스로 벗어난 까닭별 수 '은신처 6·나무 1·시야 밖 1' (0 인 까닭은 뺀다, 없으면 빈 글). */
	inline FString OwnBreakdownText(const FSum& S)
	{
		FString Out;
		for (int32 c = 0; c < EcoWorldV3::kNumFlightOwn; ++c)
		{
			if (S.Own[c] > 0)
			{
				Out += FString::Printf(TEXT("%s%s %lld"), Out.IsEmpty() ? TEXT("") : TEXT("·"), UTF8_TO_TCHAR(EcoWorldV3::FlightCauseNameKoUtf8(c)),
									   static_cast<long long>(S.Own[c]));
			}
		}
		return Out;
	}

	/** 창 요약 '최근 60초 도망 12번: 평균 6.2초 · 쫓긴 3.1초 · 스스로 벗어남 8% (은신처 6·나무 1·시야 밖 1)'. 쫓긴 = 스스로 벗어난 도망의 쫓긴 시간. */
	inline FString SummaryText(const FSum& S, const TCHAR* Span = TEXT("최근 60초"))
	{
		if (S.Ended <= 0)
		{
			return FString::Printf(TEXT("%s 끝난 도망 없음"), Span);
		}
		const FString Chase = S.OwnN() > 0 ? FString::Printf(TEXT("%.1f초"), S.OwnChaseSeconds()) : FString(TEXT("-"));
		const FString Own = OwnBreakdownText(S);
		return FString::Printf(TEXT("%s 도망 %lld번: 평균 %.1f초 · 쫓긴 %s · 스스로 벗어남 %.0f%%%s"), Span, static_cast<long long>(S.Ended), S.MeanSeconds(),
							   *Chase, 100.0 * S.OwnShare(), Own.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *Own));
	}

	/**
	 * 두뇌 판 비교 '교체 전 x초 → 지금 y초' (스스로 벗어난 도망의 쫓긴 시간 — 관문 1차). 두 판 모두 kMinCompare 번 이상일 때만 숫자, 지금 판이 모자라면
	 * '모으는 중 b/10', 교체 전 판이 모자라면 '표본 부족 a/10'. 바뀐 적이 없으면 '이 두뇌 쫓긴 y초'.
	 */
	inline FString CompareText(const FSum& Prev, const FSum& Cur, bool bHasPrev)
	{
		const FString Now = Cur.OwnN() >= kMinCompare ? FString::Printf(TEXT("%.1f초"), Cur.OwnChaseSeconds())
													  : FString::Printf(TEXT("모으는 중 %lld/%d"), static_cast<long long>(Cur.OwnN()), kMinCompare);
		if (!bHasPrev)
		{
			return FString::Printf(TEXT("이 두뇌 쫓긴 %s"), *Now);
		}
		const FString Before = Prev.OwnN() >= kMinCompare ? FString::Printf(TEXT("%.1f초"), Prev.OwnChaseSeconds())
														  : FString::Printf(TEXT("표본 부족 %lld/%d"), static_cast<long long>(Prev.OwnN()), kMinCompare);
		return FString::Printf(TEXT("교체 전 %s → 지금 %s"), *Before, *Now);
	}

	inline FString CompareText(const FTally& T) { return CompareText(T.PrevGen, T.CurrentGen(), T.bHasPrev); }
}
