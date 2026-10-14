// v3 행동 고르기 정책 파리티 하네스 — 언리얼 없이 C++ 추론이 파이썬 배포 경로와 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 최대 로짓 오차와 묶음별 결과를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 내용은 UE 자동화 시험(AI/Policy/Tests/EcoPolicyV3InferenceTest.cpp)과 같다.
//
// 이 파일이 include 하는 것:
//   EcoPolicyV3Inference.h    실제 언리얼 모듈의 v3 추론 함수 (엔진 의존 없음)
//   PolicyGoldenVectorsV3.h   export_weights_v3.py 생성 (PolicyWeightsV3.h 를 함께 싣는다)
//
// 자동 실행: herbivore_rl/tests/test_export_v3.py

#include <cmath>
#include <cstdint>
#include <cstdio>

#include "EcoPolicyV3Inference.h"
#include "PolicyGoldenVectorsV3.h"

using namespace EcoPolicyV3;
using namespace EcoPolicyV3::Golden;

static bool SameMask(const std::uint8_t* A, const std::uint8_t* B)
{
	for (int j = 0; j < kNumBehaviors; ++j)
	{
		if ((A[j] != 0) != (B[j] != 0))
		{
			return false;
		}
	}
	return true;
}

int main()
{
	int Fail = 0;

	// 1. 본 묶음
	double MaxErr = 0.0;
	int ActMismatch = 0;
	for (int n = 0; n < kCount; ++n)
	{
		float Logits[kNumBehaviors];
		const int Action = RunPolicyV3(&kObs[n * kObsDim], &kMask[n * kNumBehaviors], Logits);
		for (int j = 0; j < kNumBehaviors; ++j)
		{
			const double E = std::fabs(static_cast<double>(Logits[j]) - kLogits[n * kNumBehaviors + j]);
			MaxErr = E > MaxErr ? E : MaxErr;
		}
		ActMismatch += Action != kAction[n] ? 1 : 0;
	}
	std::printf("main     n=%d max_logit_err=%.3e argmax_mismatch=%d\n", kCount, MaxErr, ActMismatch);
	Fail += (MaxErr > kLogitTolerance || ActMismatch != 0) ? 1 : 0;

	// 2. 근접 동점 묶음
	double NearErr = 0.0;
	int NearBad = 0;
	int NearExact = 0;
	for (int n = 0; n < kNearTieCount; ++n)
	{
		float Logits[kNumBehaviors];
		const std::uint8_t* Mask = &kNearTieMask[n * kNumBehaviors];
		const float* Expected = &kNearTieLogits[n * kNumBehaviors];
		const int Action = RunPolicyV3(&kNearTieObs[n * kObsDim], Mask, Logits);
		float PyMax = -3.0e38f;
		for (int j = 0; j < kNumBehaviors; ++j)
		{
			const double E = std::fabs(static_cast<double>(Logits[j]) - Expected[j]);
			NearErr = E > NearErr ? E : NearErr;
			if (Mask[j] != 0 && Expected[j] > PyMax)
			{
				PyMax = Expected[j];
			}
		}
		NearBad += (Mask[Action] == 0 || Expected[Action] < PyMax - kNearTieGap) ? 1 : 0;
		NearExact += Action == kNearTieAction[n] ? 1 : 0;
	}
	std::printf("near_tie n=%d max_logit_err=%.3e outside_tie=%d exact=%d\n", kNearTieCount, NearErr, NearBad, NearExact);
	Fail += (NearErr > kLogitTolerance || NearBad != 0) ? 1 : 0;

	// 3. 동점 규칙
	int TieBad = 0;
	for (int n = 0; n < kTieCount; ++n)
	{
		TieBad += SelectAction(&kTieLogits[n * kNumBehaviors], &kTieMask[n * kNumBehaviors]) != kTieAction[n] ? 1 : 0;
	}
	std::printf("tie      n=%d mismatch=%d\n", kTieCount, TieBad);
	Fail += TieBad != 0 ? 1 : 0;

	// 4. 가능 칸·정책 입력 마스크·문턱
	int FeasBad = 0;
	int ComposeBad = 0;
	for (int n = 0; n < kCount; ++n)
	{
		std::uint8_t Feasible[kNumBehaviors];
		ComputeFeasibleMask(&kObs[n * kObsDim], Feasible);
		FeasBad += SameMask(Feasible, &kFeasible[n * kNumBehaviors]) ? 0 : 1;
		if (kKind[n] != kKindSynthetic)
		{
			std::uint8_t Mask[kNumBehaviors];
			ComposeActionMask(Feasible, kReads[n] != 0, kWakeDecide[n] != 0, kBehavior[n], Mask);
			ComposeBad += SameMask(Mask, &kMask[n * kNumBehaviors]) ? 0 : 1;
		}
	}
	int EdgeBad = 0;
	for (int n = 0; n < kMaskEdgeCount; ++n)
	{
		std::uint8_t Feasible[kNumBehaviors];
		ComputeFeasibleMask(&kMaskEdgeObs[n * kObsDim], Feasible);
		EdgeBad += SameMask(Feasible, &kMaskEdgeFeasible[n * kNumBehaviors]) ? 0 : 1;
	}
	std::printf("mask     feasible_mismatch=%d compose_mismatch=%d edge_mismatch=%d (edge n=%d)\n", FeasBad, ComposeBad,
				EdgeBad, kMaskEdgeCount);
	Fail += (FeasBad != 0 || ComposeBad != 0 || EdgeBad != 0) ? 1 : 0;

	// 5. 마스크 판 3 + 경보 0 이면 판 3 = 판 2
	const FMaskLayoutV3 Alarm = {kAlarmObsDim, kAlarmPredCount, kAlarmThreatRecency, kAlarmCoverDist, kAlarmHeard};
	int AlarmBad = 0;
	for (int n = 0; n < kAlarmCount; ++n)
	{
		std::uint8_t Feasible[kNumBehaviors];
		ComputeFeasibleMask(Alarm, &kAlarmObs[n * kAlarmObsDim], Feasible);
		AlarmBad += SameMask(Feasible, &kAlarmFeasible[n * kNumBehaviors]) ? 0 : 1;
	}
	int AlarmOffBad = 0;
	for (int n = 0; n < kCount; ++n)
	{
		float AlarmObs[kMaxObsDim] = {};
		for (int i = 0; i < kAlarmObsDim; ++i)
		{
			AlarmObs[i] = kAlarmFromBuiltin[i] >= 0 ? kObs[n * kObsDim + kAlarmFromBuiltin[i]] : 0.0f;
		}
		AlarmObs[kAlarmHeard] = 0.0f;
		std::uint8_t V2[kNumBehaviors];
		std::uint8_t V3[kNumBehaviors];
		ComputeFeasibleMask(&kObs[n * kObsDim], V2);
		ComputeFeasibleMask(Alarm, AlarmObs, V3);
		AlarmOffBad += SameMask(V2, V3) ? 0 : 1;
	}
	std::printf("alarm    n=%d mismatch=%d alarm_off_differs=%d\n", kAlarmCount, AlarmBad, AlarmOffBad);
	Fail += (AlarmBad != 0 || AlarmOffBad != 0) ? 1 : 0;

	const bool bHashOk = kContractHash == kContractHashObs18Mask2 || kContractHash == kContractHashObs19Mask3;
	std::printf("contract 0x%016llx known=%d alarm=0x%016llx\n", static_cast<unsigned long long>(kContractHash),
				bHashOk ? 1 : 0, static_cast<unsigned long long>(kAlarmContractHash));
	Fail += (bHashOk && kAlarmContractHash == kContractHashObs19Mask3) ? 0 : 1;

	std::printf(Fail == 0 ? "PASS\n" : "FAIL\n");
	return Fail == 0 ? 0 : 1;
}
