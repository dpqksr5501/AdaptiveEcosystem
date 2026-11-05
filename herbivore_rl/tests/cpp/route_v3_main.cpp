// v3 두 길 두뇌(RUN·SHELTER) 파리티 하네스 — 언리얼 없이 엔진 함수(EcoWorldV3.h Detail::RouteShelterGeometry·RouteStep·RouteApply·ClearRoute,
// FlightUpdate 의 도망 길 기록·FlightRouteReportOf, 단계 함수 Step 의 bRoute 줄 전체, EcoObservationV3.h WriteRouteObs, EcoPolicyV3Inference.h ApplyRouteMaskRows)이
// 파이썬 두 길 세계(env_v2/world.py `_route_step`·`_route_apply`·`flight_route_geometry` SHELTER·`route_stats`·`_fl_update` 의 길 칸, rep_policy.py 마스크 판 4·5)와
// 같은 값을 내는지 본다 — 골든 AI/Policy/RouteGoldenVectorsV3.h (herbivore_rl/export_golden_v3_route.py).
//
//   g++ -std=c++17 -O2 -ffp-contract=off -Wall -Wextra -Werror -Wshadow -I <AI/Policy 폴더> route_v3_main.cpp
//   묶음별 사례 수·불일치 수를 찍고, 하나라도 어긋나면 종료 코드 1. 검사 본문은 AI/Policy/Tests/RouteGoldenCheckV3.h (UE 자동화 Route.* 가 다음 단계에서 같은 본문을 부른다).
//   식의 스칼라 참조(엔진 코드가 아님)는 route_ref_main.cpp 다 — 둘 다 같은 골든을 비트 단위로 다시 낸다.
//
// 자동 실행: herbivore_rl/tests/test_route_port_v3.py

#include <cstdint>
#include <cstdio>

#include "Tests/RouteGoldenCheckV3.h"

namespace RC = EcoWorldV3::RouteCheck;

namespace
{
	int Print(const char* Name, const RC::FReport& R)
	{
		std::printf("%-8s n=%d mismatch=%d first=%d field=%d c0=%lld c1=%lld c2=%lld\n", Name, R.Cases, R.Failures, R.FirstCase, R.FirstField,
					static_cast<long long>(R.Count0), static_cast<long long>(R.Count1), static_cast<long long>(R.Count2));
		return R.Passed() ? 0 : 1;
	}
}

int main()
{
	int Fail = 0;
	Fail += Print("defs", RC::CheckDefinitions());
	const RC::FReport Geo = RC::CheckGeometry();
	Fail += Print("geo", Geo);
	Fail += (Geo.Count0 > 0 && Geo.Count1 > 0 && Geo.Count2 > 0) ? 0 : 1;   // 가능·유지·벽 여유로 바뀐 방향이 모두 나온다
	const RC::FReport Rows = RC::CheckRows();
	Fail += Print("rows", Rows);
	Fail += (Rows.Count0 > 0 && Rows.Count1 > 0) ? 0 : 1;                  // 결정·무효가 나온다
	const RC::FReport Ap = RC::CheckApplies();
	Fail += Print("apply", Ap);
	Fail += (Ap.Count0 > 0 && Ap.Count1 > 0) ? 0 : 1;                      // SHELTER 적용·길 바꿈이 나온다
	Fail += Print("scene", RC::CheckSceneStats());
	const RC::FReport Mask = RC::CheckMask();
	Fail += Print("mask", Mask);
	Fail += (Mask.Count0 > 0 && Mask.Count1 > 0 && Mask.Count2 > 0) ? 0 : 1;   // 칸 4 열림·판 5 막힘·덮기 줄이 나온다
	Fail += Print("respawn", RC::CheckRespawn());
	Fail += Print("obs", RC::CheckObsCases());
	const RC::FReport Fs = RC::CheckFlightScene();
	Fail += Print("flight", Fs);
	Fail += Fs.Count0 == 1 ? 0 : 1;                                         // refled 는 38 스텝 째 하나뿐
	for (std::int32_t b = 0; b < EcoWorldV3::GoldenRoute::kWorldBrains; ++b)
	{
		const RC::FReport W = RC::CheckWorld(b);
		Fail += Print(b == 0 ? "world0" : "world1", W);
		Fail += W.Count1 > 0 ? 0 : 1;                                       // 길 결정이 있다
		Fail += (b == 0 ? W.Count0 == 0 : W.Count0 > 0) ? 0 : 1;            // route0 은 SHELTER 를 고르지 않고 늘 SHELTER 두뇌는 고른다
	}
	std::printf("%s\n", Fail == 0 ? "PASS" : "FAIL");
	return Fail == 0 ? 0 : 1;
}
