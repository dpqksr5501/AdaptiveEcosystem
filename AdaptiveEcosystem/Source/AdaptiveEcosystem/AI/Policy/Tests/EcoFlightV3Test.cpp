// v3 야생 (w3) 도망 기록 자동화 시험 — C++ 도망 기록(EcoWorldV3.h FlightUpdate·FlightReportOf·FlightPairOf, 단계 함수의 bFlightStats 줄)을 파이썬
// (env_v2/world.py 모듈 docstring '야생 1단계' (w3) 도망 기록 — `_fl_update`·`flight_stats`)과 대조하고, 통합 모드 화면·기록 집계(EcoV3FlightTally.h)를 본다
// (10-21 사용자 결정 (a) 게임 화면의 도망 시간·두뇌 교체 전후, (b) 언리얼 자체 평가기).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Flight"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `FlightGoldenVectorsV3.h` (herbivore_rl/export_golden_v3_flight.py)이고, 검사 본문은 `FlightGoldenCheckV3.h` 다. 같은 검사를
// g++ 하네스(herbivore_rl/tests/cpp/flight_v3_main.cpp)도 부른다. C++ 와 파이썬은 난수열이 달라 세계 궤적은 대조하지 않는다 — 도망 기록은 스텝마다 받는
// 재료의 순수 함수라 파이썬이 적은 재료를 그대로 먹인다.
//
// 묶음:
//   Flight.Golden    정의(끝 까닭 11·스스로 벗어남 4·쫓긴 시간 칸·놓침 → 끝 까닭·10-23 숨은 뒤 지켜보기 75 스텝·10-24 쫓김 사건 이음 창 75·38 스텝), 짜 맞춘
//                    장면 6 (test_flight_v3 장면 셋 + 난수 300 틱 + 10-23 숨은 뒤 지켜보기 100 틱 + 10-24 쫓김 사건 200 틱)·거울 세계 600 스텝 재료 되풀이(스텝마다
//                    지난 표적, 100 스텝마다 보고 68 칸 — 숨은 뒤 지켜보기 5 칸·쫓김 사건 14 칸 포함·사슴 칸 — 지켜보기 칸 비트·사건 칸 포함), 쌍 장면 48 (놓침
//                    까닭 재료 = _fl_pred, 사냥 가능 = 위협 Step) — 비트 단위로 같다
//   Flight.Identity  기준 루프 900 스텝을 기록 켬·끔으로: 궤적·난수·먹이·기록(도망 말고)이 비트 단위로 같고, 켠 세계의 보고가 맞물린다(시작 = 끝 까닭 합,
//                    FLEE 스텝 = 행동 칸, 반사 = 도주 덮기 칸, 산 사슴-스텝 = N × 스텝, 10-23 숨음 + 지켜보는 동안 잡힘·굶음 = 은신처 끝, 10-24 사건 결과 합 =
//                    사건 시작·도망 시작 = 사건 시작 + 이어진 도망)
//   Flight.Window    통합 모드 집계: 최근 60 초 창(450 결정 스텝)·두뇌 판(교체 전·지금)·화면 글(10-24 쫓긴 사건 중 숨음·잡힘 몫 — 닫힌 사건), 기준 루프 누적으로
//                    창 = 450 스텝 전과의 차이(사건 칸은 늘 0 이상), 통합 설정은 기록을 켜고 세계 기본은 끈다

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoV3FlightTally.h"
#include "../EcoWorldV3.h"
#include "FlightGoldenCheckV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoFlightV3Test
{
	using EcoWorldV3::FlightCheck::FReport;

	void Report(FAutomationTestBase& Test, const TCHAR* What, const FReport& R)
	{
		Test.AddInfo(FString::Printf(TEXT("%s: 사례 %d, 어긋남 %d (처음 사례 %d 칸 %d), 셈 %lld·%lld·%lld"), What, R.Cases, R.Failures, R.FirstCase, R.FirstField,
									 static_cast<long long>(R.Count0), static_cast<long long>(R.Count1), static_cast<long long>(R.Count2)));
		Test.TestTrue(*FString::Printf(TEXT("%s: 파이썬과 비트 단위로 같다"), What), R.Passed());
	}

	/** 끝난 도망 k 개를 한꺼번에 더한 누적 (까닭 Cause, 길이 Len, 쫓긴 Contact 스텝씩). */
	EcoV3Flight::FSum AddEnded(const EcoV3Flight::FSum& Cum, int32 Cause, int64 K, int64 Len, int64 Contact)
	{
		EcoWorldV3::FFlightStats D;
		D.Started = K;
		D.Num[Cause] = K;
		D.Steps[Cause] = K * Len;
		D.Contact[Cause] = K * Contact;
		return Cum.Plus(EcoV3Flight::FSum::Of(D));
	}

	/** 10-23: 은신처로 끝난 도망 k 개가 지켜보는 동안 잡힘 (숨음이 k 줄어든다 — 쫓긴 도망·끝 까닭 수는 그대로). */
	EcoV3Flight::FSum AddCoverCaught(const EcoV3Flight::FSum& Cum, int64 K)
	{
		EcoWorldV3::FFlightStats D;
		D.CoverCaught = K;
		return Cum.Plus(EcoV3Flight::FSum::Of(D));
	}

	/** 10-24: 결과 Outcome(kEpisode* — 잘림 밖)으로 닫힌 사건 k 개 (그 밖이면 bChased 가 쫓긴 그 밖인가). */
	EcoV3Flight::FSum AddEpisode(const EcoV3Flight::FSum& Cum, int32 Outcome, int64 K, bool bChased = true)
	{
		EcoWorldV3::FFlightStats D;
		D.EpStarted = K;
		D.EpClosed[Outcome] = K;
		D.EpOtherChased = (Outcome == EcoWorldV3::kEpisodeOther && bChased) ? K : 0;
		return Cum.Plus(EcoV3Flight::FSum::Of(D));
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoFlightV3GoldenTest,
	"AdaptiveEcosystem.Policy.V3.Flight.Golden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoFlightV3GoldenTest::RunTest(const FString& Parameters)
{
	namespace FC = EcoWorldV3::FlightCheck;
	using namespace EcoFlightV3Test;
	Report(*this, TEXT("정의"), FC::CheckDefinitions());
	const FReport Scenes = FC::CheckScenes();
	Report(*this, TEXT("짜 맞춘 장면"), Scenes);
	TestTrue(TEXT("짜 맞춘 장면: 끝 까닭이 고루 나온다 (스스로 벗어남 > 0)"), Scenes.Count0 > 0 && Scenes.Count1 > 0);
	TestTrue(TEXT("짜 맞춘 장면: 숨은 뒤 지켜보기 — 숨음·지켜보는 동안 죽음이 모두 나온다 (10-23)"), Scenes.Hidden > 0 && Scenes.CoverDied > 0);
	TestTrue(TEXT("짜 맞춘 장면: 쫓김 사건 — 이어진 도망·숨음·그 밖·잘림이 모두 나온다 (10-24)"), Scenes.EpJoined > 0 && Scenes.EpHidden > 0 && Scenes.EpOther > 0);
	const FReport Loop = FC::CheckLoop();
	Report(*this, TEXT("거울 세계 600 스텝 재료"), Loop);
	TestTrue(TEXT("거울 세계: 시작 도망·스스로 벗어남이 있다"), Loop.Count0 > 0 && Loop.Count1 > 0);
	const FReport Pairs = FC::CheckPairs();
	Report(*this, TEXT("쌍 장면 (놓침 까닭 재료)"), Pairs);
	TestTrue(TEXT("쌍 장면: 원판 가림·은신처 표적 제외·사냥 못 함이 모두 나온다"), Pairs.Count0 > 0 && Pairs.Count1 > 0 && Pairs.Count2 > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoFlightV3IdentityTest,
	"AdaptiveEcosystem.Policy.V3.Flight.Identity",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoFlightV3IdentityTest::RunTest(const FString& Parameters)
{
	namespace FC = EcoWorldV3::FlightCheck;
	using namespace EcoFlightV3Test;
	EcoWorldV3::FFlightReport Rp;
	const FReport R = FC::CheckRunIdentity(900, &Rp);
	Report(*this, TEXT("기록 켬 = 끔 (기준 루프 900 스텝)"), R);
	FString Causes;
	for (int32 c = 0; c < EcoWorldV3::kNumFlightCauses; ++c)
	{
		Causes += FString::Printf(TEXT(" %s %lld"), UTF8_TO_TCHAR(EcoWorldV3::FlightCauseNameKoUtf8(c)), static_cast<long long>(Rp.Num[c]));
	}
	AddInfo(FString::Printf(TEXT("켠 세계 보고: 시작 %lld · 스스로 벗어남 %lld (쫓긴 %lld 스텝) · FLEE 스텝 %lld (반사 %lld) · 끝 까닭:%s · ")
								TEXT("쫓긴 도망 %lld 중 숨음 %lld (지켜보는 중 %lld) · 숨은 뒤 10초 안 잡힘 %lld·굶음 %lld · ")
									TEXT("사건 시작 %lld · 쫓긴 사건 %lld 중 숨음 %lld · 잡힘 %lld · 굶음 %lld · 그 밖 %lld · 잘림 %lld · 이어진 도망 %lld"),
							static_cast<long long>(Rp.Started), static_cast<long long>(Rp.OwnN), static_cast<long long>(Rp.OwnContact),
							static_cast<long long>(Rp.FleeSteps), static_cast<long long>(Rp.ReflexSteps), *Causes, static_cast<long long>(Rp.Chased),
							static_cast<long long>(Rp.Hidden), static_cast<long long>(Rp.Watching), static_cast<long long>(Rp.CoverCaught),
							static_cast<long long>(Rp.CoverStarved), static_cast<long long>(Rp.EpStarted), static_cast<long long>(Rp.EpChased),
							static_cast<long long>(Rp.EpHidden), static_cast<long long>(Rp.EpCaught), static_cast<long long>(Rp.EpStarved),
							static_cast<long long>(Rp.EpOther), static_cast<long long>(Rp.EpTruncated), static_cast<long long>(Rp.EpJoined)));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoFlightV3WindowTest,
	"AdaptiveEcosystem.Policy.V3.Flight.Window",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoFlightV3WindowTest::RunTest(const FString& Parameters)
{
	using namespace EcoFlightV3Test;
	using EcoV3Flight::FSum;
	using EcoV3Flight::FTally;
	const int32 Wn = EcoV3Flight::kWindowSteps;
	TestEqual(TEXT("창 = 60 초 결정 스텝"), static_cast<double>(Wn) * EcoRepertoireV3::kStepSeconds, 60.0);

	// 1) 손 열: 스텝 t (1..1200) 마다 10 스텝째에 은신처로 끝난 도망 하나 (길이 20, 쫓긴: 600 스텝 전 판 6 · 뒤 판 3), 7 스텝째마다 안 쫓김 하나 (길이 5),
	//    10-23: 40 스텝째마다 잡혀 끝난 도망 하나 (길이 8), 600 스텝 뒤 60 스텝째마다 은신처로 끝난 도망 하나가 지켜보는 동안 잡힘. 600 스텝 끝에 두뇌가 바뀐다.
	//    10-24 사건 (닫힌 사건만 센다): 은신처 도망마다 사건 하나가 닫힌다 — 600 스텝 뒤 60 스텝째는 잡힘, 그 밖은 숨음. 안 쫓김 도망은 쫓기지 않은 그 밖 사건,
	//    잡힌 도망은 잡힘 사건. 교체 전 판: 쫓긴 사건 = 숨음 60 + 잡힘 15 = 75 (80% · 20%). 지금 판(601..1200): 쫓긴 사건 75, 숨음 60 − 10 = 50 (67%),
	//    잡힘 15 + 10 = 25 (33%). 옛 도망 단위: 지금 판 쫓긴 도망 75, 숨음 50, 잡힘 15
	{
		FTally T;
		std::vector<FSum> History(1, FSum());
		FSum Cum;
		bool bOk = true;
		for (int32 t = 1; t <= 1200; ++t)
		{
			if (t % 10 == 0)
			{
				Cum = AddEnded(Cum, EcoWorldV3::kFlightCover, 1, 20, t <= 600 ? 6 : 3);
				Cum = AddEpisode(Cum, (t > 600 && t % 60 == 0) ? EcoWorldV3::kEpisodeCaught : EcoWorldV3::kEpisodeHidden, 1);
			}
			if (t % 7 == 0)
			{
				Cum = AddEnded(Cum, EcoWorldV3::kFlightUnchased, 1, 5, 0);
				Cum = AddEpisode(Cum, EcoWorldV3::kEpisodeOther, 1, false);
			}
			if (t % 40 == 0)
			{
				Cum = AddEnded(Cum, EcoWorldV3::kFlightCaught, 1, 8, 8);
				Cum = AddEpisode(Cum, EcoWorldV3::kEpisodeCaught, 1);
			}
			if (t > 600 && t % 60 == 0)
			{
				Cum = AddCoverCaught(Cum, 1);
			}
			T.Push(Cum);
			History.push_back(Cum);
			const FSum Want = Cum.Minus(History[static_cast<size_t>(FMath::Max(0, t - Wn))]);
			bOk = bOk && T.Window() == Want && T.WindowSteps() == FMath::Min(t, Wn);
			if (t == 600)
			{
				TestEqual(TEXT("바뀌기 전: 비교 글 = 이 두뇌"), EcoV3Flight::CompareText(T), FString(TEXT("이 두뇌 숨음 80% · 잡힘 20%")));
				T.OnBrainSwap(Cum);
				TestTrue(TEXT("바뀜: 교체 전 판 = 그때까지 누적, 지금 판 0"), T.PrevGen == Cum && T.CurrentGen() == FSum() && T.bHasPrev && T.Swaps == 1);
			}
			if (t == 650)
			{
				// 지금 판 쫓긴 사건 6 개 (숨음 5 · 잡힘 1 < 10): 모으는 중
				TestEqual(TEXT("지금 판 표본 부족: 모으는 중"), EcoV3Flight::CompareText(T),
						  FString(TEXT("교체 전 숨음 80% · 잡힘 20% → 지금 모으는 중 6/10 사건")));
			}
		}
		TestTrue(TEXT("창 = 지금 누적 − 450 스텝 전 누적 (시작 450 스텝 안은 시작부터), 스텝마다"), bOk);
		const FSum Win = T.Window();
		TestEqual(TEXT("마지막 창: 은신처 도망 45 번 (751..1200 의 10 의 배수)"), Win.Own[EcoWorldV3::kFlightCover], static_cast<int64>(45));
		TestEqual(TEXT("마지막 창: 끝난 도망 = 45 + 64 (7 의 배수) + 12 (40 의 배수)"), Win.Ended, static_cast<int64>(45 + 64 + 12));
		TestTrue(TEXT("마지막 창 (옛 도망 단위): 쫓긴 도망 57 (은신처 45 + 잡힘 12) · 숨음 45 − 8 (60 의 배수) · 잡힘 12"),
				 Win.Chased == 57 && Win.Hidden == 37 && Win.Caught == 12);
		TestTrue(TEXT("마지막 창 (사건): 닫힌 사건 121 · 쫓긴 57 · 숨음 37 · 잡힘 8 + 12"),
				 Win.EpEnded == 45 + 64 + 12 && Win.EpStarted == Win.EpEnded && Win.EpChased == 57 && Win.EpHidden == 37 && Win.EpCaught == 20);
		TestEqual(TEXT("지금 판: 은신처 도망 60 번, 쫓긴 3 스텝씩"), T.CurrentGen().OwnContact, static_cast<int64>(60 * 3));
		TestEqual(TEXT("교체 전 숨음 80% · 잡힘 20% → 지금 숨음 67% · 잡힘 33%"), EcoV3Flight::CompareText(T),
				  FString(TEXT("교체 전 숨음 80% · 잡힘 20% → 지금 숨음 67% · 잡힘 33%")));
		TestTrue(TEXT("지금 판 옛 도망 단위 몫은 보고만 (숨음 50/75 · 잡힘 15/75)"), T.CurrentGen().Chased == 75 && T.CurrentGen().Hidden == 50
																					 && T.CurrentGen().Caught == 15);
		// 두 번째 바뀜: 바로 앞 판(숨음 67%)이 '교체 전'이 된다
		T.OnBrainSwap(Cum);
		TestEqual(TEXT("두 번째 바뀜: 교체 전 = 바로 앞 판"), EcoV3Flight::CompareText(T),
				  FString(TEXT("교체 전 숨음 67% · 잡힘 33% → 지금 모으는 중 0/10 사건")));
		TestEqual(TEXT("바뀜 횟수"), T.Swaps, 2);
	}
	// 1b) 첫 결정 스텝 전에 두뇌가 바뀜 (SyncBrain 은 첫 스텝 전 프레임에도 돈다): 첫 Push 가 창 칸을 열어도 바뀜(교체 전·횟수)이 남는다
	{
		FTally T;
		T.OnBrainSwap(FSum());
		const FSum Cum = AddEpisode(AddEnded(FSum(), EcoWorldV3::kFlightCover, 1, 20, 6), EcoWorldV3::kEpisodeHidden, 1);
		T.Push(Cum);
		TestTrue(TEXT("첫 스텝 전 바뀜이 남는다"), T.bHasPrev && T.Swaps == 1 && T.PrevGen == FSum() && T.CurrentGen() == Cum);
		TestTrue(TEXT("첫 스텝 전 바뀜 뒤 창 = 시작부터"), T.Window() == Cum && T.WindowSteps() == 1);
		TestEqual(TEXT("첫 스텝 전 바뀜 뒤 비교 글"), EcoV3Flight::CompareText(T), FString(TEXT("교체 전 표본 부족 0/10 사건 → 지금 모으는 중 1/10 사건")));
	}
	// 2) 화면 글 (사용자 예시 꼴)
	{
		FSum S;
		S.Ended = 12;
		S.EndedSteps = 558;   // 평균 558 × 2/15 ÷ 12 = 6.2 초
		S.Own[EcoWorldV3::kFlightCover] = 6;
		S.Own[EcoWorldV3::kFlightObstacle] = 1;
		S.Own[EcoWorldV3::kFlightRange] = 1;
		S.OwnContact = 186;   // 186 × 2/15 ÷ 8 = 3.1 초
		S.Chased = 12;        // 10-23 옛 도망 단위 (보고만 — 화면 글에 쓰지 않는다)
		S.Hidden = 7;
		S.Caught = 1;
		S.EpChased = 10;      // 10-24 닫힌 쫓긴 사건 10 가운데 숨음 5 · 잡힘 1 (은신처 들락날락을 한 사건으로 묶어 도망 단위보다 적다)
		S.EpHidden = 5;
		S.EpCaught = 1;
		TestEqual(TEXT("창 글"), EcoV3Flight::SummaryText(S),
				  FString(TEXT("최근 60초 도망 12번: 평균 6.2초 · 쫓긴 사건 중 숨음 50% · 잡힘 10% · 쫓긴 3.1초 · 스스로 벗어남 67% (은신처 6·나무 1·시야 밖 1)")));
		TestEqual(TEXT("끝난 도망 없음"), EcoV3Flight::SummaryText(FSum()), FString(TEXT("최근 60초 끝난 도망 없음")));
		FSum NoOwn;
		NoOwn.Ended = 3;
		NoOwn.EndedSteps = 45;
		NoOwn.Chased = 2;     // 쫓긴 도망은 있어도 닫힌 쫓긴 사건이 없으면 숨음·잡힘 칸을 뺀다
		TestEqual(TEXT("스스로 벗어난 도망·닫힌 쫓긴 사건이 없으면 쫓긴 -, 숨음·잡힘 칸 없음"), EcoV3Flight::SummaryText(NoOwn),
				  FString(TEXT("최근 60초 도망 3번: 평균 2.0초 · 쫓긴 - · 스스로 벗어남 0%")));
		FSum Few = S;
		Few.EpChased = 3;   // 쫓긴 사건 3 개 < 10 (도망 단위 Chased 12 는 보지 않는다)
		TestEqual(TEXT("교체 전 표본 부족"), EcoV3Flight::CompareText(Few, S, true), FString(TEXT("교체 전 표본 부족 3/10 사건 → 지금 숨음 50% · 잡힘 10%")));
		TestEqual(TEXT("지금 판 표본 부족"), EcoV3Flight::CompareText(S, Few, true), FString(TEXT("교체 전 숨음 50% · 잡힘 10% → 지금 모으는 중 3/10 사건")));
		FSum Neg = S;
		Neg.Hidden = -1;   // 옛 도망 단위 구간 차이: 구간 앞에 숨은 도망이 구간 안에 잡힘 — 0 아래는 0 (스냅숏 hide_share). 사건 칸은 닫힌 것만이라 음수가 없다
		TestTrue(TEXT("옛 도망 단위 숨음 구간 차이가 음수면 0, 화면 글은 사건 단위 그대로"),
				 Neg.HideShare() == 0.0 && EcoV3Flight::HideCaughtText(Neg) == FString(TEXT("숨음 50% · 잡힘 10%")));
	}
	// 3) 기준 루프 누적 (EcoWorldV3 도망 기록): 결정 스텝마다 넣으면 창 = 450 스텝 전과의 차이, 판 합 = 누적, 열린 도망은 창·판에 없다
	{
		using namespace EcoWorldV3;
		FReferenceWorld Ref;
		Ref.Init(FlightCheck::RunConfig(true));
		FTally T;
		std::vector<FSum> History(1, FSum());
		bool bOk = true;
		bool bEpOk = true;   // 10-24 창의 사건 칸은 늘 0 이상이고 숨음 + 잡힘 ≤ 쫓긴 사건 ≤ 닫힌 사건 (닫힌 사건만 센다)
		for (int32 t = 1; t <= 900; ++t)
		{
			Ref.StepOnce();
			const FSum Cum = FSum::Of(Ref.World.Stats.Flight);
			T.Push(Cum);
			History.push_back(Cum);
			bOk = bOk && T.Window() == Cum.Minus(History[static_cast<size_t>(FMath::Max(0, t - Wn))]);
			const FSum W = T.Window();
			bEpOk = bEpOk && W.EpStarted >= 0 && W.EpHidden >= 0 && W.EpCaught >= 0 && W.EpHidden + W.EpCaught <= W.EpChased && W.EpChased <= W.EpEnded;
			if (t == 450)
			{
				T.OnBrainSwap(Cum);
			}
		}
		const FSum Cum = FSum::Of(Ref.World.Stats.Flight);
		TestTrue(TEXT("기준 루프: 스텝마다 창 = 450 스텝 전과의 차이"), bOk);
		TestTrue(TEXT("기준 루프: 스텝마다 창의 사건 칸 0 이상 · 숨음 + 잡힘 ≤ 쫓긴 사건 ≤ 닫힌 사건 (10-24)"), bEpOk);
		TestTrue(TEXT("기준 루프: 교체 전 판 + 지금 판 = 누적"), T.PrevGen.Plus(T.CurrentGen()) == Cum);
		const FFlightReport Rp = FlightReportOf(Ref.World.Stats.Flight, FlightOpenOf(Ref.Views.data(), Ref.NumHerbivores()));
		TestEqual(TEXT("기준 루프: 끝난 도망 = 시작 − 열린 도망"), Cum.Ended, Rp.Started - Rp.Num[kFlightTruncated]);
		TestEqual(TEXT("기준 루프: 스스로 벗어남 = 보고"), Cum.OwnN(), Rp.OwnN);
		TestTrue(TEXT("기준 루프: 쫓긴 도망·숨음(지켜보는 중 포함)·잡힘 = 보고 (10-23)"),
				 Cum.Chased == Rp.Chased && Cum.Hidden == Rp.Hidden && Cum.Caught == Rp.Num[kFlightCaught] && Rp.Chased > 0);
		// 10-24 화면 누적(닫힌 사건) = 보고(관문 셈) − 지금 은신처 뒤 창 안인 사건 (보고는 그것을 지켜본 만큼 숨음·쫓긴 사건에 넣는다), 닫힌 사건 = 시작 − 열린 사건
		TestTrue(TEXT("기준 루프: 닫힌 사건 시작·쫓긴·숨음·잡힘 = 보고 − 지켜보는 중 (10-24)"),
				 Cum.EpStarted == Rp.EpStarted && Cum.EpChased + Rp.EpWatching == Rp.EpChased && Cum.EpHidden + Rp.EpWatching == Rp.EpHidden
					 && Cum.EpCaught == Rp.EpCaught && Cum.EpEnded == Rp.EpStarted - Rp.EpTruncated - Rp.EpWatching && Rp.EpChased > 0);
		AddInfo(FString::Printf(TEXT("기준 루프 900 스텝: %s · %s"), *EcoV3Flight::SummaryText(T.Window()), *EcoV3Flight::CompareText(T)));
	}
	// 4) 설정: 세계 기본은 끔(평면 맵·기준 루프·골든 그대로), 통합 모드는 켬. 지역 장부는 켠 세계만 FlightOn
	{
		TestFalse(TEXT("세계 기본: 도망 기록 끔"), EcoWorldV3::FWorldConfig().bFlightStats);
		const FEcoV3IntegratedSettings Def;
		const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(Def.StageSizeUnits, 6.0);
		const EcoWorldV3::FWorldConfig C = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Def, 0, 128, Def.WolvesPerRegion, Covers);
		TestTrue(TEXT("통합 설정: 도망 기록 켬"), C.bFlightStats);
		FEcoV3RegionContext Ctx;
		Ctx.Sim.Config = C;
		TestEqual(TEXT("통합 지역: 도주 반사 켬이면 FlightOn"), Ctx.FlightOn(), C.WildFlight.bEnabled);
		Ctx.Sim.Config.WildFlight.bEnabled = false;
		TestFalse(TEXT("도주 반사를 끄면 세지 않는다 (파이썬도 wild_flight 세계에만 있다)"), Ctx.FlightOn());
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
