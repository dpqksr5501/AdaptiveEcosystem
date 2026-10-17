// v3 야생 2단계 2 늑대 무리 협동 파리티 하네스 — 언리얼 없이 C++ (EcoThreatModel.h 의 PackPeek·PackGoals·Step 6b′)이 파이썬
// (world.py pack_goals·_step_predators_v3, configs/v3_wild2_pack_mirror.yaml)과 비트 단위로 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 묶음별 사례 수·불일치 수를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 본문은 UE 자동화 시험(AI/Policy/Tests/EcoPackV3Test.cpp)과 같은 AI/Policy/Tests/PackGoldenCheckV3.h 다.
//
// 자동 실행: herbivore_rl/tests/test_wild2_pack.py

#include <cstdint>
#include <cstdio>

#include "Tests/PackGoldenCheckV3.h"

namespace PC = EcoThreatV3::PackCheck;

namespace
{
	int Print(const char* Name, const PC::FReport& R)
	{
		std::printf("%-8s n=%d mismatch=%d first=%d field=%d help=%d wait=%d door=%d catches=%d\n", Name, R.Cases, R.Failures, R.FirstCase,
					R.FirstField, R.Help, R.Wait, R.Door, R.Catches);
		return R.Passed() ? 0 : 1;
	}
}

int main()
{
	namespace G = EcoThreatV3::GoldenPack;
	int Fail = 0;
	Fail += Print("config", PC::CheckConfig());
	const PC::FReport Goals = PC::CheckGoals();
	Fail += Print("goals", Goals);
	Fail += (Goals.Help == G::kGoalHelp && Goals.Wait == G::kGoalWait && Goals.Door == G::kGoalDoor) ? 0 : 1;
	const PC::FReport Steps = PC::CheckSteps();
	Fail += Print("steps", Steps);
	Fail += (Steps.Help == G::kStepHelp && Steps.Wait == G::kStepWait && Steps.Door == G::kStepDoor && Steps.Catches == G::kStepCatches) ? 0 : 1;
	Fail += Print("off", PC::CheckOffIgnores());
	std::printf("%s\n", Fail == 0 ? "PASS" : "FAIL");
	return Fail == 0 ? 0 : 1;
}
