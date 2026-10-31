// v3 야생 2단계 3 세로 장애물 파리티 하네스 — 언리얼 없이 C++ (EcoThreatModel.h 의 ObstacleSlide·SightBlocked·Step, EcoWorldV3.h 의
// ObstaclePushOut·FFoodGrid::ApplyObstacleFood)이 파이썬(world.py obstacle_slide·sight_blocked·obstacle_push_out·obstacle_food_factor·
// _step_predators_v3, configs/v3_wild2_obstacle_mirror.yaml)과 비트 단위로 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 묶음별 사례 수·불일치 수를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 본문은 UE 자동화 시험(AI/Policy/Tests/EcoObstacleV3Test.cpp)과 같은 AI/Policy/Tests/ObstacleGoldenCheckV3.h 다.
//
// 자동 실행: herbivore_rl/tests/test_wild2_obstacle.py

#include <cstdint>
#include <cstdio>

#include "Tests/ObstacleGoldenCheckV3.h"

namespace OC = EcoWorldV3::ObstacleCheck;

namespace
{
	int Print(const char* Name, const OC::FReport& R)
	{
		std::printf("%-8s n=%d mismatch=%d first=%d field=%d c0=%d c1=%d c2=%d\n", Name, R.Cases, R.Failures, R.FirstCase, R.FirstField, R.Count0,
					R.Count1, R.Count2);
		return R.Passed() ? 0 : 1;
	}
}

int main()
{
	namespace G = EcoWorldV3::GoldenObstacle;
	int Fail = 0;
	Fail += Print("config", OC::CheckConfig());
	const OC::FReport Slides = OC::CheckSlides();
	Fail += Print("slides", Slides);
	Fail += (Slides.Count0 == G::kSlideHits && Slides.Count1 == G::kSlideBacks) ? 0 : 1;
	const OC::FReport Sights = OC::CheckSights();
	Fail += Print("sights", Sights);
	Fail += Sights.Count0 == G::kSightBlocked ? 0 : 1;
	Fail += Print("food", OC::CheckFood());
	const OC::FReport Pushes = OC::CheckPushes();
	Fail += Print("pushes", Pushes);
	Fail += (Pushes.Count0 == G::kPushMoved && Pushes.Count1 == G::kPushFailed) ? 0 : 1;
	const OC::FReport Steps = OC::CheckSteps();
	Fail += Print("steps", Steps);
	Fail += (Steps.Count0 == G::kStepHits && Steps.Count1 == G::kStepDeads && Steps.Count2 == G::kStepCatches) ? 0 : 1;
	Fail += Print("off", OC::CheckOffIgnores());
	std::printf("%s\n", Fail == 0 ? "PASS" : "FAIL");
	return Fail == 0 ? 0 : 1;
}
