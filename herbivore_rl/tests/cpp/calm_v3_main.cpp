// v3 10-27 고침 파리티 하네스 — 언리얼 없이 C++ (EcoRepertoire.h GrazeCalmDir·Control, EcoWorldV3.h UpdateWildFlight 의 거리 두기·FlightRestControl·
// FlightRestBand·FlightAlertControl·단계 함수)이 파이썬(repertoire.py `graze_calm_dir`·`control`, world.py `_wf_update`·`_wf_rest_control`·`_wf_rest_band`·`step`,
// configs/v3_wild3_calm_mirror.yaml)과 같은 값을 내는지 본다 (사용자 10-27 '평소 사슴이 제자리에서 빙빙 돈다'·'쉬는 늑대 곁에서 멈춰 있다').
//
//   g++ 로 컴파일해서 실행하면 묶음별 사례 수·불일치 수를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 본문은 UE 자동화 시험(AI/Policy/Tests/EcoCalmV3Test.cpp)과 같은 AI/Policy/Tests/CalmGoldenCheckV3.h 다.
//
// 자동 실행: herbivore_rl/tests/test_calm_golden_v3.py

#include <cstdint>
#include <cstdio>

#include "Tests/CalmGoldenCheckV3.h"

namespace CC = EcoWorldV3::CalmCheck;

namespace
{
	int Print(const char* Name, const CC::FReport& R)
	{
		std::printf("%-10s n=%d mismatch=%d first=%d field=%d c0=%lld c1=%lld c2=%lld\n", Name, R.Cases, R.Failures, R.FirstCase, R.FirstField,
					static_cast<long long>(R.Count0), static_cast<long long>(R.Count1), static_cast<long long>(R.Count2));
		return R.Passed() ? 0 : 1;
	}
}

int main()
{
	int Fail = 0;
	Fail += Print("defs", CC::CheckDefinitions());
	const CC::FReport Dir = CC::CheckDirections();
	Fail += Print("dir", Dir);
	Fail += (Dir.Count0 > 0 && Dir.Count1 > 0) ? 0 : 1;          // 방향을 바꾼 사례와 원래 방향으로 돌아간 사례가 모두 있다
	Fail += Print("control", CC::CheckControl());
	const CC::FReport Sc = CC::CheckScenes();
	Fail += Print("scenes", Sc);
	Fail += (Sc.Count0 > 0 && Sc.Count1 > 0 && Sc.Count2 > 0) ? 0 : 1;   // 거리 두기·경계·도주가 모두 나온다
	const CC::FReport B = CC::CheckBScenes();
	Fail += Print("bscenes", B);
	Fail += (B.Count0 > 0 && B.Count1 > 0 && B.Count2 > 0) ? 0 : 1;      // 띠가 바꾼·거리 두기 제어·멈춤이 모두 나온다
	for (std::int32_t Li = 0; Li < EcoWorldV3::GoldenCalm::kLoops; ++Li)
	{
		char Name[32];
		std::snprintf(Name, sizeof(Name), "loop%d", static_cast<int>(Li));
		const CC::FReport On = CC::CheckLoop(Li, true);
		Fail += Print(Name, On);
		Fail += (On.Count0 > 0 && On.Count1 > 0 && On.Count2 > 0) ? 0 : 1;   // 거리 두기·띠·잡힘이 루프에 있다
		std::snprintf(Name, sizeof(Name), "loop%d_off", static_cast<int>(Li));
		Fail += Print(Name, CC::CheckLoop(Li, false));
		std::snprintf(Name, sizeof(Name), "loop%d_junk", static_cast<int>(Li));
		Fail += Print(Name, CC::CheckLoop(Li, false, true));
	}
	std::printf("%s\n", Fail == 0 ? "PASS" : "FAIL");
	return Fail == 0 ? 0 : 1;
}
