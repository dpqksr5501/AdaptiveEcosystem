// v3 야생 (w3) 도망 기록 파리티 하네스 — 언리얼 없이 C++ (EcoWorldV3.h 의 FlightUpdate·FlightReportOf·FlightPairOf·단계 함수의 bFlightStats 줄)이
// 파이썬(world.py `_fl_update`·`flight_stats`·`_step_predators_v3` 의 _fl_pred, configs/v3_wild3_obs_mirror.yaml)과 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 묶음별 사례 수·불일치 수를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 본문은 UE 자동화 시험(AI/Policy/Tests/EcoFlightV3Test.cpp)과 같은 AI/Policy/Tests/FlightGoldenCheckV3.h 다.
//
// 자동 실행: herbivore_rl/tests/test_flight_golden_v3.py

#include <cstdint>
#include <cstdio>

#include "Tests/FlightGoldenCheckV3.h"

namespace FC = EcoWorldV3::FlightCheck;

namespace
{
	int Print(const char* Name, const FC::FReport& R)
	{
		std::printf("%-8s n=%d mismatch=%d first=%d field=%d c0=%lld c1=%lld c2=%lld hidden=%lld cover_died=%lld ep_joined=%lld ep_hidden=%lld ep_other=%lld\n",
					Name, R.Cases, R.Failures, R.FirstCase, R.FirstField, static_cast<long long>(R.Count0), static_cast<long long>(R.Count1),
					static_cast<long long>(R.Count2), static_cast<long long>(R.Hidden), static_cast<long long>(R.CoverDied), static_cast<long long>(R.EpJoined),
					static_cast<long long>(R.EpHidden), static_cast<long long>(R.EpOther));
		return R.Passed() ? 0 : 1;
	}
}

int main()
{
	int Fail = 0;
	Fail += Print("defs", FC::CheckDefinitions());
	const FC::FReport Scenes = FC::CheckScenes();
	Fail += Print("scenes", Scenes);
	Fail += (Scenes.Hidden > 0 && Scenes.CoverDied > 0) ? 0 : 1;   // 10-23 숨은 뒤 지켜보기: 숨음·지켜보는 동안 죽음이 장면에 있다
	Fail += (Scenes.EpJoined > 0 && Scenes.EpHidden > 0 && Scenes.EpOther > 0) ? 0 : 1;   // 10-24 쫓김 사건: 이어진 도망·숨음·그 밖·잘림이 장면에 있다
	Fail += Print("loop", FC::CheckLoop());
	const FC::FReport Pairs = FC::CheckPairs();
	Fail += Print("pairs", Pairs);
	Fail += (Pairs.Count0 > 0 && Pairs.Count1 > 0 && Pairs.Count2 > 0) ? 0 : 1;
	EcoWorldV3::FFlightReport Rp;
	const FC::FReport Run = FC::CheckRunIdentity(900, &Rp);
	Fail += Print("same", Run);
	std::printf("run: started=%lld own=%lld flee=%lld reflex=%lld chased=%lld hidden=%lld watching=%lld cover_caught=%lld cover_starved=%lld causes=",
				static_cast<long long>(Rp.Started), static_cast<long long>(Rp.OwnN), static_cast<long long>(Rp.FleeSteps), static_cast<long long>(Rp.ReflexSteps),
				static_cast<long long>(Rp.Chased), static_cast<long long>(Rp.Hidden), static_cast<long long>(Rp.Watching), static_cast<long long>(Rp.CoverCaught),
				static_cast<long long>(Rp.CoverStarved));
	for (std::int32_t c = 0; c < EcoWorldV3::kNumFlightCauses; ++c)
	{
		std::printf("%s:%lld ", EcoWorldV3::FlightCauseName(c), static_cast<long long>(Rp.Num[c]));
	}
	// 10-24 쫓김 사건 (파이썬 flight_stats 의 episode 와 같은 칸)
	std::printf("\nepisode: started=%lld chased=%lld hidden=%lld caught=%lld starved=%lld other=%lld truncated=%lld watching=%lld other_chased=%lld joined=%lld "
				"(cover %lld · other %lld) window_caught=%lld window_starved=%lld",
				static_cast<long long>(Rp.EpStarted), static_cast<long long>(Rp.EpChased), static_cast<long long>(Rp.EpHidden),
				static_cast<long long>(Rp.EpCaught), static_cast<long long>(Rp.EpStarved), static_cast<long long>(Rp.EpOther),
				static_cast<long long>(Rp.EpTruncated), static_cast<long long>(Rp.EpWatching), static_cast<long long>(Rp.EpOtherChased),
				static_cast<long long>(Rp.EpJoined), static_cast<long long>(Rp.EpJoinedCover), static_cast<long long>(Rp.EpJoinedOther),
				static_cast<long long>(Rp.EpWindowCaught), static_cast<long long>(Rp.EpWindowStarved));
	std::printf("\n%s\n", Fail == 0 ? "PASS" : "FAIL");
	return Fail == 0 ? 0 : 1;
}
