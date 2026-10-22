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
		std::printf("%-8s n=%d mismatch=%d first=%d field=%d c0=%lld c1=%lld c2=%lld\n", Name, R.Cases, R.Failures, R.FirstCase, R.FirstField,
					static_cast<long long>(R.Count0), static_cast<long long>(R.Count1), static_cast<long long>(R.Count2));
		return R.Passed() ? 0 : 1;
	}
}

int main()
{
	int Fail = 0;
	Fail += Print("defs", FC::CheckDefinitions());
	Fail += Print("scenes", FC::CheckScenes());
	Fail += Print("loop", FC::CheckLoop());
	const FC::FReport Pairs = FC::CheckPairs();
	Fail += Print("pairs", Pairs);
	Fail += (Pairs.Count0 > 0 && Pairs.Count1 > 0 && Pairs.Count2 > 0) ? 0 : 1;
	EcoWorldV3::FFlightReport Rp;
	const FC::FReport Run = FC::CheckRunIdentity(900, &Rp);
	Fail += Print("same", Run);
	std::printf("run: started=%lld own=%lld flee=%lld reflex=%lld causes=", static_cast<long long>(Rp.Started), static_cast<long long>(Rp.OwnN),
				static_cast<long long>(Rp.FleeSteps), static_cast<long long>(Rp.ReflexSteps));
	for (std::int32_t c = 0; c < EcoWorldV3::kNumFlightCauses; ++c)
	{
		std::printf("%s:%lld ", EcoWorldV3::FlightCauseName(c), static_cast<long long>(Rp.Num[c]));
	}
	std::printf("\n%s\n", Fail == 0 ? "PASS" : "FAIL");
	return Fail == 0 ? 0 : 1;
}
