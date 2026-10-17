// v3 야생 3단계 지역 날씨 파리티 하네스 — 언리얼 없이 C++ (EcoWorldV3.h 의 WeatherAt·WeatherMults·UpdateDayNight·SeePredNow·발소리·사슴 속도,
// EcoThreatModel.h 의 Step 날씨 시야·속력)이 파이썬(world.py wild_weather, configs/v3_wild3_mirror.yaml)과 비트 단위로 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 묶음별 사례 수·불일치 수를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 본문은 UE 자동화 시험(AI/Policy/Tests/EcoWeatherV3Test.cpp)과 같은 AI/Policy/Tests/WeatherGoldenCheckV3.h 다.
//
// 자동 실행: herbivore_rl/tests/test_wild3_weather.py

#include <cstdint>
#include <cstdio>

#include "Tests/WeatherGoldenCheckV3.h"

namespace WC = EcoWorldV3::WeatherCheck;

namespace
{
	int Print(const char* Name, const WC::FReport& R)
	{
		std::printf("%-8s n=%d mismatch=%d first=%d field=%d changed=%d count=%d\n", Name, R.Cases, R.Failures, R.FirstCase, R.FirstField, R.Changed,
					R.Count);
		return R.Passed() ? 0 : 1;
	}
}

int main()
{
	namespace G = EcoWorldV3::GoldenWeather;
	int Fail = 0;
	Fail += Print("config", WC::CheckConfig());
	Fail += Print("mults", WC::CheckMults());
	Fail += Print("sched", WC::CheckSchedule());
	Fail += Print("daynight", WC::CheckDayNight());
	const WC::FReport Perc = WC::CheckPerception();
	Fail += Print("percept", Perc);
	Fail += (Perc.Count == G::kPercSeen && Perc.Changed > 0) ? 0 : 1;
	const WC::FReport Steps = WC::CheckSteps();
	Fail += Print("steps", Steps);
	Fail += (Steps.Count == G::kStepCatches && Steps.Changed > 0) ? 0 : 1;
	const WC::FReport Off = WC::CheckOffIdentical();
	Fail += Print("off", Off);
	const WC::FReport Snow = WC::CheckSnowFirstStep();
	Fail += Print("snow1", Snow);
	Fail += Snow.Count > 0 ? 0 : 1;
	std::printf("%s\n", Fail == 0 ? "PASS" : "FAIL");
	return Fail == 0 ? 0 : 1;
}
