// v3 숲 시야 파리티 하네스 — 언리얼 없이 C++ (EcoThreatModel.h FoliageChord·FoliageBlocked·Step, EcoObservationV3.h ObstacleObsValues,
// EcoWorldV3.h FObstacleConfig::Foliage·FlightPairOf·FlightUpdate·단계 함수)이 파이썬(world.py `foliage_chord`·`foliage_blocked`·`obstacle_obs_values`·
// `_step_predators_v3`·`_fl_update`, configs/v3_wild3_obs_mirror.yaml + 숲 시야)과 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 묶음별 사례 수·불일치 수를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 본문은 UE 자동화 시험(AI/Policy/Tests/EcoFoliageV3Test.cpp)과 같은 AI/Policy/Tests/FoliageGoldenCheckV3.h 다.
//
// 자동 실행: herbivore_rl/tests/test_foliage_golden_v3.py

#include <cstdint>
#include <cstdio>

#include "Tests/FoliageGoldenCheckV3.h"

namespace FC = EcoWorldV3::FoliageCheck;

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
	const FC::FReport Chord = FC::CheckChord();
	Fail += Print("chord", Chord);
	Fail += (Chord.Count0 > 0 && Chord.Count1 > 0) ? 0 : 1;   // 가림·쌓아 두기 칸 넘침 길이 모두 나온다
	const FC::FReport Obs = FC::CheckObs();
	Fail += Print("obs", Obs);
	Fail += Obs.Count0 > 0 ? 0 : 1;                           // 잎만 가린 threat_hidden 이 있다
	const FC::FReport Pairs = FC::CheckPairs();
	Fail += Print("pairs", Pairs);
	Fail += (Pairs.Count0 > 0 && Pairs.Count1 > 0) ? 0 : 1;
	const FC::FReport Fl = FC::CheckFlightScenes();
	Fail += Print("flight", Fl);
	Fail += Fl.Count0 > 0 ? 0 : 1;
	const FC::FReport On = FC::CheckWorld(true);
	Fail += Print("world", On);
	Fail += On.Count0 > 0 ? 0 : 1;                            // 기준 루프에 잎 놓침이 있다
	Fail += Print("off", FC::CheckWorld(false));
	Fail += Print("offjunk", FC::CheckWorld(false, true));
	std::printf("%s\n", Fail == 0 ? "PASS" : "FAIL");
	return Fail == 0 ? 0 : 1;
}
