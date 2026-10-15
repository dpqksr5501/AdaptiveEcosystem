// v3 위협 모델 밤잠 점진화 파리티 하네스 — 언리얼 없이 C++ (EcoThreatModel.h, FThreatConfig::bRealismNight = true 의
// NightInit·NightUpdate·Step)이 파이썬 밤잠 세계(configs/v3_real1_night_on.yaml, world.py `_rz_night_update`)와 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 묶음별 사례 수·최대 실수 오차·불일치 수를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 본문은 UE 자동화 시험(AI/Policy/Tests/EcoThreatNightV3Test.cpp)과 같은 AI/Policy/Tests/ThreatNightGoldenCheckV3.h 다.
//
// 이 파일이 include 하는 것:
//   Tests/ThreatNightGoldenCheckV3.h   검사 본문 (EcoThreatModel.h 와 ThreatNightGoldenVectorsV3.h 를 싣는다)
//   ThreatNightGoldenVectorsV3.h       export_golden_v3_threat.py --night 생성 (언리얼 모듈의 것. 최신인지는 바이트 비교 시험이 본다)
//
// 자동 실행: herbivore_rl/tests/test_threat_golden_v3.py

#include <cstdint>
#include <cstdio>

#include "Tests/ThreatNightGoldenCheckV3.h"

using namespace EcoThreatV3;
namespace NC = EcoThreatV3::NightCheck;

namespace
{
	int Print(const char* Name, const NC::FReport& R, bool bReportOnly = false)
	{
		std::printf("%-12s n=%d max_float_err=%.3e mismatch=%d skipped=%d first=%d field=%d%s\n", Name, R.Cases, R.MaxError,
					R.Failures, R.Skipped, R.FirstCase, R.FirstField, bReportOnly ? " (보고만)" : "");
		return (!bReportOnly && !R.Passed()) ? 1 : 0;
	}
}

int main()
{
	namespace G = EcoThreatV3::GoldenNight;
	int Fail = 0;
	Fail += Print("config", NC::CheckConfig());
	Fail += Print("hash", NC::CheckHash());
	Fail += Print("init", NC::CheckInit());
	Fail += Print("upd_main", NC::CheckUpdates(G::kKindMain));
	Fail += Print("upd_edge", NC::CheckUpdates(G::kKindEdge));
	Fail += Print("upd_life", NC::CheckUpdates(G::kKindLife));
	if (G::kUpdNearBegin < G::kUpdCount)
	{
		Print("upd_near", NC::CheckUpdates(G::kKindNear), true);
	}
	Fail += Print("step_main", NC::CheckSteps(G::kKindMain));
	Fail += Print("step_edge", NC::CheckSteps(G::kKindEdge));
	Fail += Print("step_seq", NC::CheckSteps(G::kKindSeq));
	Fail += Print("step_life", NC::CheckSteps(G::kKindLife));
	Print("step_near", NC::CheckSteps(G::kKindNear), true);
	Fail += Print("seq_chain", NC::CheckStepSequences());
	std::int32_t Onsets = 0;
	std::int32_t Wakes = 0;
	Fail += Print("life_chain", NC::CheckLife(&Onsets, &Wakes));
	std::printf("life_events onsets=%d wakes=%d\n", Onsets, Wakes);
	Fail += (Onsets > 0 && Wakes > 0) ? 0 : 1;
	Fail += Print("off_ignores", NC::CheckOffIgnoresNightState());
	std::printf(Fail == 0 ? "PASS\n" : "FAIL\n");
	return Fail == 0 ? 0 : 1;
}
