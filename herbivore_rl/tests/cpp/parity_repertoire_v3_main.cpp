// v3 R1b 세계 개체 논리 파리티 하네스 — 언리얼 없이 EcoRepertoire.h·EcoObservationV3.h 가 파이썬 세계와 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 검사마다 사례 수·어긋난 수·실수 최대 오차를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 본문은 UE 자동화 시험(AI/Policy/Tests/EcoRepertoireV3Test.cpp)과 같은 Tests/RepertoireGoldenCheckV3.h 다.
//
// 이 파일이 include 하는 것 (-I AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy):
//   Tests/RepertoireGoldenCheckV3.h   대조 검사 (EcoRepertoire.h·EcoObservationV3.h·EcoPolicyV3Inference.h·골든을 싣는다)
//
// 자동 실행: herbivore_rl/tests/test_repertoire_golden_v3.py

#include <cstdint>
#include <cstdio>

#include "Tests/RepertoireGoldenCheckV3.h"

using namespace EcoRepertoireV3::Check;

static int Report(const char* Name, const FReport& R)
{
	std::printf("%-16s cases=%d skipped=%d failures=%d max_err=%.3e exact=%d/%d first_case=%d first_field=%d\n", Name,
				R.Cases, R.Skipped, R.Failures, R.MaxError, R.FloatExact, R.FloatCount, R.FirstCase, R.FirstField);
	return R.Passed() ? 0 : 1;
}

int main()
{
	int Fail = 0;
	Fail += Report("constants", CheckConstants());
	Fail += Report("jitter_hash", CheckJitterHash());
	Fail += Report("arbitrate", CheckSequences(ESequenceMode::Arbitrate));
	Fail += Report("prepare_commit", CheckSequences(ESequenceMode::PrepareCommit));
	Fail += Report("closed_loop", CheckSequences(ESequenceMode::ClosedLoop));
	Fail += Report("init_agent", CheckInitAgent());
	Fail += Report("respawn", CheckRespawn());
	Fail += Report("control", CheckControl());
	Fail += Report("move", CheckMove());
	Fail += Report("energy", CheckEnergy());
	Fail += Report("perceive", CheckPerceive());
	Fail += Report("obs_build", CheckObservationBuild());
	Fail += Report("perception", CheckPerception());
	Fail += Report("daynight", CheckDayNight());
	Fail += Report("predation_ema", CheckPredationEma());
	if (Fail == 0)
	{
		std::printf("PASS\n");
		return 0;
	}
	std::printf("FAIL (%d)\n", Fail);
	return 1;
}
