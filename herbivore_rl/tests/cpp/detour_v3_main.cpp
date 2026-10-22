// v3 야생 2단계 3 의 6) 장애물 돌아가기 파리티 하네스 — 언리얼 없이 C++ (EcoThreatModel.h 의 DetourStep·DetourCandidate·Step 7′·8″·PackPeek)이
// 파이썬(world.py detour_moves·_step_predators_v3, configs/v3_wild2_obstacle_mirror.yaml 돌아가기 켬)과 비트 단위로 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 묶음별 사례 수·불일치 수를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 본문은 UE 자동화 시험(AI/Policy/Tests/EcoObstacleV3Test.cpp 의 Policy.V3.Obstacle.DetourGolden)과 같은 AI/Policy/Tests/DetourGoldenCheckV3.h 다.
//
// 자동 실행: herbivore_rl/tests/test_wild2_detour.py

#include <cstdint>
#include <cstdio>

#include "Tests/DetourGoldenCheckV3.h"

namespace DC = EcoWorldV3::DetourCheck;

namespace
{
	int Print(const char* Name, const DC::FReport& R)
	{
		std::printf("%-8s n=%d mismatch=%d first=%d field=%d c0=%d c1=%d c2=%d\n", Name, R.Cases, R.Failures, R.FirstCase, R.FirstField, R.Count0,
					R.Count1, R.Count2);
		return R.Passed() ? 0 : 1;
	}
}

int main()
{
	namespace G = EcoWorldV3::GoldenDetour;
	int Fail = 0;
	Fail += Print("config", DC::CheckConfig());
	const DC::FReport Ones = DC::CheckOnes();
	Fail += Print("ones", Ones);
	Fail += (Ones.Count0 == G::kOneUsed && Ones.Count1 == G::kOneStarts && Ones.Count2 == G::kOneFails) ? 0 : 1;
	const DC::FReport Paths = DC::CheckPaths();
	Fail += Print("paths", Paths);
	Fail += Paths.Count0 == G::kPathUsed ? 0 : 1;
	const DC::FReport Steps = DC::CheckSteps();
	Fail += Print("steps", Steps);
	Fail += (Steps.Count0 == G::kStepUsed && Steps.Count1 == G::kStepDrops && Steps.Count2 == G::kStepDeads) ? 0 : 1;
	Fail += Print("off", DC::CheckOffIgnores());
	std::printf("%s\n", Fail == 0 ? "PASS" : "FAIL");
	return Fail == 0 ? 0 : 1;
}
