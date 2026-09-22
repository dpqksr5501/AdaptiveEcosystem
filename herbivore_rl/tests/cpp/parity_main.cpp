// §9.8-1 파리티 하네스 — 언리얼 없이 C++ 추론이 파이썬과 같은 값을 내는지 본다.
//
//   gcc/g++ 로 컴파일해서 실행하면 최대 오차를 stdout에 찍고,
//   1e-5 를 넘으면 종료 코드 1.
//
// 이 파일이 include하는 것:
//   EcoPolicyInference.h      실제 언리얼 모듈의 추론 함수 (엔진 의존 없음)
//   PolicyWeights.h           export_weights.py 생성
//   PolicyGoldenVectors.h     export_weights.py 생성 (파이썬 출력 100쌍)
//
// 자동 실행: herbivore_rl/tests/test_export.py

#include <cmath>
#include <cstdio>

#include "EcoPolicyInference.h"
#include "EcoSteering.h"
#include "PolicyGoldenVectors.h"
#include "SteeringGoldenVectors.h"

/** §9.8-2 — 조향 단독. 파이썬 steer() 와 같은 값이 나오는가. */
static int CheckSteering()
{
	EcoPolicy::FSteerConfig Cfg;
	Cfg.SeeRadius = kSteerSeeRadius;
	Cfg.SepWeight = kSteerSepWeight;
	Cfg.FleeWeight = kSteerFleeWeight;
	Cfg.HerbSpeed = kSteerHerbSpeed;

	double MaxErr = 0.0;
	for (int n = 0; n < kSteerGoldenCount; ++n)
	{
		const float* In = &kSteerGoldenInput[n * 11];
		EcoPolicy::FSteerInput G;
		G.FoodGrad[0] = In[0];      G.FoodGrad[1] = In[1];
		G.ToCentroid[0] = In[2];    G.ToCentroid[1] = In[3];
		G.ToCover[0] = In[4];       G.ToCover[1] = In[5];
		G.Separation[0] = In[6];    G.Separation[1] = In[7];
		G.AwayFromPred[0] = In[8];  G.AwayFromPred[1] = In[9];
		G.DistPredMin = In[10];

		// 골든은 (forage, cohesion, flee_dist, cover) 순서를 그대로 쓴다.
		const float A[4] = {kSteerGoldenAction[n * 4 + 0], kSteerGoldenAction[n * 4 + 1],
							kSteerGoldenAction[n * 4 + 2], kSteerGoldenAction[n * 4 + 3]};
		float Out[2];
		EcoPolicy::Steer(G, A, Cfg, Out);

		for (int j = 0; j < 2; ++j)
		{
			const double Err = std::fabs(static_cast<double>(Out[j]) -
										 static_cast<double>(kSteerGoldenExpected[n * 2 + j]));
			if (Err > MaxErr) { MaxErr = Err; }
		}
	}
	std::printf("steering pairs: %d\n", kSteerGoldenCount);
	std::printf("max abs error : %.3e\n", MaxErr);
	return MaxErr > 1e-5 ? 1 : 0;
}

int main()
{
	double MaxErr = 0.0;
	int WorstN = -1;
	int WorstJ = -1;

	for (int n = 0; n < kGoldenCount; ++n)
	{
		float Out[EcoPolicy::ActDim];
		EcoPolicy::RunPolicy(&kGoldenObs[n * EcoPolicy::ObsDim], Out);

		for (int j = 0; j < EcoPolicy::ActDim; ++j)
		{
			const double Err =
				std::fabs(static_cast<double>(Out[j]) -
						  static_cast<double>(kGoldenExpected[n * EcoPolicy::ActDim + j]));
			if (Err > MaxErr)
			{
				MaxErr = Err;
				WorstN = n;
				WorstJ = j;
			}
		}
	}

	std::printf("golden pairs : %d\n", kGoldenCount);
	std::printf("max abs error: %.3e  (vector %d, action %d)\n", MaxErr, WorstN, WorstJ);

	if (MaxErr > 1e-5)
	{
		std::printf("FAIL: policy 1e-5 tolerance exceeded\n");
		return 1;
	}

	if (CheckSteering() != 0)
	{
		std::printf("FAIL: steering 1e-5 tolerance exceeded\n");
		return 1;
	}

	std::printf("PASS\n");
	return 0;
}
