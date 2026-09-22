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
#include "PolicyGoldenVectors.h"

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
		std::printf("FAIL: 1e-5 tolerance exceeded\n");
		return 1;
	}
	std::printf("PASS\n");
	return 0;
}
