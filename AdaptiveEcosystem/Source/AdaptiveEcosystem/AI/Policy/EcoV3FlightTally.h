// 통합 v3 도망 기록 화면·기록 집계 (10-21 사용자 결정 (a) '게임 화면에 도망 시간 — 두뇌 교체 전·후도'). 기록만 — 세계·두뇌에 쓰지 않는다.
//
// 재료는 지역 세계의 누적 도망 기록 EcoWorldV3::FWorldStats::Flight (FWorldConfig::bFlightStats — 정의는 EcoWorldV3.h 머리 주석 '도망 기록',
// 파이썬 world.py `flight_stats` 와 같다). 결정 스텝마다 누적을 한 번 넣고(FTally::Push) 두 가지를 낸다:
//   (i)  최근 60 초 창 (kWindowSteps = 450 결정 스텝): 그 사이에 끝난 도망 — 지금 누적 − 450 스텝 전 누적 (Play 시작이 450 스텝 안이면 시작부터)
//   (ii) 두뇌 판 합: 두뇌가 바뀔 때(OnBrainSwap — 되돌림 포함) 지금 판의 합을 '교체 전'으로 넘기고 새 판을 0 에서 센다. 바뀌는 순간 열려 있던 도망은
//        끝나는 판(새 판)에 든다
// 화면의 '쫓긴' = 스스로 벗어난 도망(은신처·나무·시야각 밖·시야 밖)의 쫓긴 시간 평균 — 10-21 (3) 관문 1차였고 10-23 (6) 부터 보고만이다.
// 10-24 (LIVE_GATE.md 변경 기록 (7) — 관문 1차 사건 숨음 비율·지킴 GH 와 같은 재료, 사람 결정 "'쫓김 사건' 단위로 셈"): '쫓긴 사건 중 숨음 x% · 잡힘 y%' =
// 쫓긴 사건(같은 사슴의 이어진 도망 — 은신처 끝 뒤 10 초·그 밖 끝 뒤 5 초 안 다시 도망 — 을 한 사건으로 묶은 것, 정의는 EcoWorldV3.h 머리 주석 '쫓김 사건')
// 가운데 마지막 도망이 은신처로 끝나 그 뒤 10 초를 잡히지·굶지 않고 지난 몫·잡힘으로 끝난 몫. 창·두뇌 판은 '그 사이에 닫힌 사건'만 센다(FFlightStats::EpClosed
// — 누적이 늘기만 해 구간 차이가 0 이상이고 숨음 + 잡힘 ≤ 쫓긴 사건). 그래서 은신처 뒤 10 초를 지켜보는 중인 사건은 닫힐 때(최대 10 초 늦게) 들고, 판 끝에
// 그것을 '지켜본 만큼 숨음'으로 넣는 관문 셈(FlightReportOf 의 Ep*)과는 지켜보는 중인 사건만큼 다르다. 10-23 의 도망 단위 '쫓긴 도망 중 숨음·잡힘'
// (은신처 들락날락이 숨음을 두 번 센다)은 화면에서 빼고 스냅숏 칸(hide_share 등)에 보고만 남긴다.
// 교체 전·지금 비교는 사건 숨음·잡힘 몫을 두 판 모두 쫓긴 사건이 kMinCompare 개 이상일 때만 숫자로 (적으면 '모으는 중'). 판정이 아니라 화면 비교다 (관문은
// results/v3/live/live.py — 판마다 시드 짝).

#pragma once

#include "CoreMinimal.h"
#include "EcoWorldV3.h"

namespace EcoV3Flight
{
	inline constexpr int32 kWindowSteps = 450;   // 최근 60 초 (1 결정 스텝 = 2/15 초)
	inline constexpr int32 kMinCompare = 10;     // 교체 전·지금 비교에 필요한 판마다 쫓긴 사건 수 (10-24 — 10-23 에는 쫓긴 도망, 그 전에는 스스로 벗어난 도망 수)

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
		// 10-23 숨은 뒤 지켜보기 (옛 도망 단위 1차 숨음 비율·GH 의 재료 — 10-24 부터 화면에 쓰지 않고 스냅숏에 보고만. EcoWorldV3.h 머리 주석)
		int64 Chased = 0;                               // 쫓긴 도망 (끝난 도망 가운데 안 쫓김·잘림 아닌 것)
		int64 Hidden = 0;                               // 은신처로 끝나 지켜보는 10 초 안에 죽지 않은 도망 (= 은신처 끝 − 지켜보는 동안 잡힘·굶음, 지켜보는 중 포함)
		int64 Caught = 0;                               // 잡혀 끝난 도망 (끝 까닭 잡힘)
		// 10-24 쫓김 사건 (관문 1차 사건 숨음 비율·지킴 GH 의 재료 — 닫힌 사건만, 머리 주석)
		int64 EpStarted = 0;                            // 시작한 사건
		int64 EpEnded = 0;                              // 닫힌 사건 (숨음·잡힘·굶음·그 밖 — 잘림은 없다)
		int64 EpChased = 0;                             // 닫힌 쫓긴 사건 (숨음 + 잡힘 + 굶음 + 쫓긴 그 밖 — 화면 숨음·잡힘 몫의 분모)
		int64 EpHidden = 0;                             // 닫힌 숨음 사건 (마지막 도망이 은신처로 끝나 10 초를 다 지남)
		int64 EpCaught = 0;                             // 닫힌 잡힘 사건 (GH 의 분자)

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
			R.Chased = R.Ended;
			for (const int32 c : EcoWorldV3::kFlightNotChased)
			{
				R.Chased -= S.Num[c];
			}
			// 지켜보는 중인 도망은 사슴 쪽(FFlightTrack::Watch)에 있지만, 숨음 + 지켜보는 동안 잡힘·굶음 = 은신처 끝 이라 누적만으로 같은 값이 나온다
			// (FlightReportOf 의 Hidden 과 같은 식 — 로그·스냅숏 누적과 화면 창·판이 같은 셈이다)
			R.Hidden = S.Num[EcoWorldV3::kFlightCover] - S.CoverCaught - S.CoverStarved;
			R.Caught = S.Num[EcoWorldV3::kFlightCaught];
			// 10-24 쫓김 사건: 닫힌 사건만 (EcoWorldV3.h FFlightStats::EpClosed — 늘기만 하는 누적)
			R.EpStarted = S.EpStarted;
			for (const int64 V : S.EpClosed)
			{
				R.EpEnded += V;
			}
			R.EpHidden = S.EpClosed[EcoWorldV3::kEpisodeHidden];
			R.EpCaught = S.EpClosed[EcoWorldV3::kEpisodeCaught];
			R.EpChased = R.EpHidden + R.EpCaught + S.EpClosed[EcoWorldV3::kEpisodeStarved] + S.EpOtherChased;
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
			R.Chased = Chased + Sign * O.Chased;
			R.Hidden = Hidden + Sign * O.Hidden;
			R.Caught = Caught + Sign * O.Caught;
			R.EpStarted = EpStarted + Sign * O.EpStarted;
			R.EpEnded = EpEnded + Sign * O.EpEnded;
			R.EpChased = EpChased + Sign * O.EpChased;
			R.EpHidden = EpHidden + Sign * O.EpHidden;
			R.EpCaught = EpCaught + Sign * O.EpCaught;
			return R;
		}
		FSum Minus(const FSum& O) const { return Plus(O, -1); }

		bool operator==(const FSum& O) const
		{
			bool bSame = Started == O.Started && Ended == O.Ended && EndedSteps == O.EndedSteps && OwnSteps == O.OwnSteps && OwnContact == O.OwnContact
						 && Unsafe == O.Unsafe && Chased == O.Chased && Hidden == O.Hidden && Caught == O.Caught && EpStarted == O.EpStarted
						 && EpEnded == O.EpEnded && EpChased == O.EpChased && EpHidden == O.EpHidden && EpCaught == O.EpCaught;
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
		/**
		 * 10-23 쫓긴 도망 가운데 숨어 살아남은 몫 (0~1 — 옛 도망 단위 1차 숨음 비율, 10-24 부터 스냅숏 보고만, 이 구간 합). 없으면 0. 구간 차이는 구간 앞에
		 * 은신처로 끝난 도망이 구간 안에 잡히면 숨음이 1 줄어 드물게 음수가 될 수 있어 0 아래는 0 으로 본다.
		 */
		double HideShare() const { return Chased > 0 ? FMath::Max(0.0, static_cast<double>(Hidden) / static_cast<double>(Chased)) : 0.0; }
		/** 10-23 쫓긴 도망 가운데 잡혀 끝난 몫 (0~1 — 옛 도망 단위 GH, 10-24 부터 보고만). 없으면 0. */
		double CaughtShare() const { return Chased > 0 ? static_cast<double>(Caught) / static_cast<double>(Chased) : 0.0; }
		/** 10-24 닫힌 쫓긴 사건 가운데 숨음 사건 몫 (0~1 — 관문 1차 사건 숨음 비율과 같은 셈, 이 구간에 닫힌 사건). 없으면 0. */
		double EpHideShare() const { return EpChased > 0 ? static_cast<double>(EpHidden) / static_cast<double>(EpChased) : 0.0; }
		/** 10-24 닫힌 쫓긴 사건 가운데 잡힘 사건 몫 (0~1 — 지킴 GH 와 같은 셈). 없으면 0. */
		double EpCaughtShare() const { return EpChased > 0 ? static_cast<double>(EpCaught) / static_cast<double>(EpChased) : 0.0; }
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

	/** 10-24 '숨음 25% · 잡힘 8%' (닫힌 쫓긴 사건 가운데 — EpHideShare·EpCaughtShare, 정수 %. 10-23 에는 쫓긴 도망 가운데였다). */
	inline FString HideCaughtText(const FSum& S)
	{
		return FString::Printf(TEXT("숨음 %.0f%% · 잡힘 %.0f%%"), 100.0 * S.EpHideShare(), 100.0 * S.EpCaughtShare());
	}

	/**
	 * 창 요약 '최근 60초 도망 12번: 평균 6.2초 · 쫓긴 사건 중 숨음 50% · 잡힘 10% · 쫓긴 3.1초 · 스스로 벗어남 67% (은신처 6·나무 1·시야 밖 1)'.
	 * 도망 12번·평균·스스로 벗어남 = 그 사이에 끝난 도망, 쫓긴 사건 중 숨음·잡힘 = 10-24 관문 1차·GH 와 같은 몫 (그 사이에 닫힌 쫓긴 사건 — 없으면 뺀다),
	 * 쫓긴 = 스스로 벗어난 도망의 쫓긴 시간 (보고만).
	 */
	inline FString SummaryText(const FSum& S, const TCHAR* Span = TEXT("최근 60초"))
	{
		if (S.Ended <= 0)
		{
			return FString::Printf(TEXT("%s 끝난 도망 없음"), Span);
		}
		const FString Hide = S.EpChased > 0 ? FString::Printf(TEXT(" · 쫓긴 사건 중 %s"), *HideCaughtText(S)) : FString();
		const FString Chase = S.OwnN() > 0 ? FString::Printf(TEXT("%.1f초"), S.OwnChaseSeconds()) : FString(TEXT("-"));
		const FString Own = OwnBreakdownText(S);
		return FString::Printf(TEXT("%s 도망 %lld번: 평균 %.1f초%s · 쫓긴 %s · 스스로 벗어남 %.0f%%%s"), Span, static_cast<long long>(S.Ended), S.MeanSeconds(),
							   *Hide, *Chase, 100.0 * S.OwnShare(), Own.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *Own));
	}

	/**
	 * 두뇌 판 비교 '교체 전 숨음 80% · 잡힘 20% → 지금 숨음 67% · 잡힘 20%' (그 판에 닫힌 쫓긴 사건 가운데 — 10-24 관문 1차 사건 숨음 비율·지킴 GH 와 같은
	 * 몫. 10-23 에는 쫓긴 도망 가운데, 10-21 에는 쫓긴 시간이었다 — 쫓긴 시간은 창 요약에 남는다). 두 판 모두 쫓긴 사건이 kMinCompare 개 이상일 때만 숫자,
	 * 지금 판이 모자라면 '모으는 중 b/10 사건', 교체 전 판이 모자라면 '표본 부족 a/10 사건'. 바뀐 적이 없으면 '이 두뇌 숨음 x% · 잡힘 y%'.
	 */
	inline FString CompareText(const FSum& Prev, const FSum& Cur, bool bHasPrev)
	{
		const FString Now = Cur.EpChased >= kMinCompare ? HideCaughtText(Cur)
														: FString::Printf(TEXT("모으는 중 %lld/%d 사건"), static_cast<long long>(Cur.EpChased), kMinCompare);
		if (!bHasPrev)
		{
			return FString::Printf(TEXT("이 두뇌 %s"), *Now);
		}
		const FString Before = Prev.EpChased >= kMinCompare ? HideCaughtText(Prev)
															: FString::Printf(TEXT("표본 부족 %lld/%d 사건"), static_cast<long long>(Prev.EpChased), kMinCompare);
		return FString::Printf(TEXT("교체 전 %s → 지금 %s"), *Before, *Now);
	}

	inline FString CompareText(const FTally& T) { return CompareText(T.PrevGen, T.CurrentGen(), T.bHasPrev); }
}
