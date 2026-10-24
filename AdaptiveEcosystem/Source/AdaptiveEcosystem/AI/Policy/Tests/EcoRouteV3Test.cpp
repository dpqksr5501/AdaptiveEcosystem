// v3 두 길 두뇌(RUN·SHELTER) 자동화 시험 — 엔진 함수 EcoWorldV3.h (Detail::RouteShelterGeometry·RouteStep·RouteApply·ClearRoute, 단계 함수의 bRoute 줄,
// FlightUpdate 의 도망 길 기록), EcoObservationV3.h (WriteRouteObs), EcoPolicyV3Inference.h (ApplyRouteMaskRows — 마스크 판 4·5)를 파이썬 두 길 세계
// (herbivore_rl/env_v2/world.py `_route_step`·`_route_apply`·`route_stats`, rep_policy.py 마스크 판 4·5)와 대조한다. 이식 계획서
// Docs/RL_Policy/RL_V3_ROUTE_CPP_PORT_PLAN.md 10-3 (10-24 이식 2/2).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Route"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `RouteGoldenVectorsV3.h` (herbivore_rl/export_golden_v3_route.py)이고, 검사 본문은 `RouteGoldenCheckV3.h` 다. 같은 검사를 g++ 하네스
// (herbivore_rl/tests/cpp/route_v3_main.cpp — herbivore_rl/tests/test_route_port_v3.py)도 부른다.
//
// 묶음:
//   Route.Geometry      정의(골든 상수 = 엔진 상수 — 계획서 10-1 표, 기본 꺼짐), SHELTER 기하 90 사례 (k*·μ*·e*·방향·유지 — 가능·유지·벽 여유로 바뀐 방향이 나온다)
//   Route.StepGolden    길 셈 줄 923 (결정·무효·관측 21~23 float 비트), 적용 117, 손 장면 통계 32, 다시 난 개체 9 (지움·terminal_obs 0), 관측 사례 37
//   Route.MaskRows      마스크 판 4 51 줄 + 판 5 6 줄 (칸 3 늘 0, 판 5 덮기 밖 결정 줄 칸 1 막힘)
//   Route.World         기준 루프 (거울 세계 사슴 48, 450 스텝) 두뇌 둘 — route0 (SHELTER 를 고르지 않는다)·늘 SHELTER 시험 두뇌 — 스텝마다 지문·90 스텝마다 기록·
//                       끝 도망 길 덩어리·두뇌 가중치 sha256
//   Route.FlightRecord  도망 길 기록 장면 10 틱 (FlightUpdate + FFlightRouteStats, StepNow = 틱 − 1): refled 38 스텝 째 하나·원판 놓침·쫓김.
//                       + 10-24 검토: Step 의 H(FlightStepEnd)가 refled 를 도망 기록 시계(FFlightStats::Clock)로 잰다 — W.T 가 뒤·앞으로 뛰어도 그대로
//   Route.Off           길 끔 = 지금: 기본 꺼짐, WildFlight 를 끈 세계는 켜지지 않음, 판 2 두뇌 900 스텝 동안 길 칸·관측 21~23·길 통계·도망 길 기록이 늘 0,
//                       두 길 → 길 없는 두뇌 경계(A 는 반사 방향, 그 H 가 지움 — 계획서 8-2·12절 질문 2), 길 없는 두뇌 → 두 길 경계(그 H 에서 길 없음 결정 — 질문 1)
//   Route.ZeroIdentity  C++ 안에서 route0(관측 24 · 길 켬) 궤적 = obs21zero(관측 21 · 길 끔) 궤적 — 통합 지역 셋(숲·고지·메마른 땅) × 1800 스텝, 스텝마다 지문·
//                       끝 기록 (파이썬 쪽 같은 확인은 results/v3/route/port stats 의 route_off.same)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoV3Brain.h"
#include "../EcoWorldV3.h"
#include "../TreeLayoutV3.h"
#include "Math/RandomStream.h"
#include "RouteGoldenCheckV3.h"

#include <cstring>
#include <vector>

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoRouteV3Test
{
	using EcoWorldV3::RouteCheck::FReport;
	namespace GR = EcoWorldV3::GoldenRoute;
	namespace W3 = EcoWorldV3;
	namespace O3 = EcoObservationV3;
	namespace P3 = EcoPolicyV3;
	namespace R3 = EcoRepertoireV3;

	// 골든 상수 = 엔진 상수 (이식 계획서 10-1 표 — 컴파일 때 본다)
	static_assert(GR::kContractHashObs24Mask4 == P3::kContractHashObs24Mask4, "계약 해시");
	static_assert(GR::kObsDim == O3::kObsDimRoute && GR::kRouteObsFirst == O3::kObsInPanic && O3::kObsShelterReach == GR::kRouteObsFirst + 1
					  && O3::kObsShelterEdge == GR::kRouteObsFirst + 2,
				  "관측 24 칸 번호");
	static_assert(GR::kSlotRun == W3::kRouteSlotRun && GR::kSlotShelter == W3::kRouteSlotShelter && GR::kSlotReserved == W3::kRouteSlotReserved, "길 칸");
	static_assert(GR::kRouteNone == W3::kRouteNone && GR::kRouteRun == W3::kRouteRun && GR::kRouteShelter == W3::kRouteShelter, "길 번호");
	static_assert(GR::kFeasShelter == W3::kRouteFeasShelter && GR::kLockSteps == W3::kRouteLockSteps, "가능 비트·잠금");
	static_assert(GR::kModeNone == W3::kKeepNone && GR::kModeAlert == W3::kKeepAlert && GR::kModePanic == W3::kKeepPanic && GR::kModeShelter == W3::kKeepShelter,
				  "덮기 번호");
	static_assert(GR::kMaxEdgeU == W3::kRouteShelterMaxEdgeU && GR::kCosMin == W3::kRouteShelterCosMin && GR::kEnterU == W3::kRouteShelterEnterU
					  && GR::kExitU == W3::kRouteShelterExitU && GR::kReachNormU == W3::kRouteShelterReachU && GR::kEdgeNormU == W3::kRouteShelterEdgeNormU,
				  "SHELTER 문턱");
	static_assert(GR::kFsRefleeSteps == W3::kFlightRefleeSteps && GR::kEps == R3::kEps, "도망 기록 GR·EPS");
	static_assert(GR::kMaskVersion == P3::kMaskVersionRoute, "마스크 판 4");

	void Report(FAutomationTestBase& Test, const TCHAR* What, const FReport& R)
	{
		Test.AddInfo(FString::Printf(TEXT("%s: 사례 %d, 어긋남 %d (처음 사례 %d 칸 %d), 셈 %lld·%lld·%lld"), What, R.Cases, R.Failures, R.FirstCase, R.FirstField,
									 static_cast<long long>(R.Count0), static_cast<long long>(R.Count1), static_cast<long long>(R.Count2)));
		Test.TestTrue(*FString::Printf(TEXT("%s: 파이썬과 비트 단위로 같다"), What), R.Passed());
	}

	/**
	 * 통합 지역 하나의 엔진 무관 작은 세계 (통합 처리기처럼 산 사슴만 Step 에 넘긴다). 설정 = 통합 기본값(MakeRegionWorldConfig — 도주 반사·도망 기록·장애물·날씨 켬)
	 * + 그 지역의 무대 나무 줄기 원판 + 은신처 넷. 두뇌는 UEcoPolicyV3IntegratedSubsystem::ApplyBrainToWorld 로 건다 (통합 SyncBrain 과 같은 줄).
	 */
	struct FMini
	{
		W3::FWorldState W;
		std::vector<R3::FRepState> Reps;
		std::vector<W3::FHerbDecision> Dec;
		std::vector<W3::FHerbBody> Bodies;
		std::vector<W3::FHerbPerception> Perc;
		std::vector<R3::FControlOutput> Ctl;
		std::vector<W3::FThreatAgent> Threats;
		std::vector<W3::FThreatAgent*> ThreatPtrs;
		std::vector<W3::FHerbView> All;
		std::vector<W3::FHerbView> Live;

		static W3::FWorldConfig RegionConfig(int32 Region, int32 NumDeer, int32 NumWolves)
		{
			static const TCHAR* const Names[3] = {TEXT("Forest"), TEXT("Highland"), TEXT("Barren")};
			const FEcoV3IntegratedSettings S;
			W3::FWorldConfig C = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, Region, NumDeer, NumWolves,
																						 W3::QuadCovers(S.StageSizeUnits, 6.0), FName(Names[Region]));
			C.Obstacles.Discs.clear();
			const EcoTreeLayoutV3::FStageTrees* Trees = UEcoPolicyV3IntegratedSubsystem::FindStageTrees(FName(Names[Region]), S.StageSizeUnits);
			for (int32 k = 0; Trees && k < Trees->Num; ++k)
			{
				const EcoTreeLayoutV3::FTree& T = Trees->Trees[k];
				C.Obstacles.Discs.insert(C.Obstacles.Discs.end(), {T.X, T.Y, T.R});
			}
			return C;
		}

		void Init(const W3::FWorldConfig& C, const FEcoV3Brain& Brain, int32 N, int32 M, int32 PlaceSeed)
		{
			W3::InitWorld(W, C);
			UEcoPolicyV3IntegratedSubsystem::ApplyBrainToWorld(W, Brain);
			const size_t Nz = static_cast<size_t>(N);
			Reps.assign(Nz, R3::FRepState());
			Dec.assign(Nz, W3::FHerbDecision());
			Bodies.assign(Nz, W3::FHerbBody());
			Perc.assign(Nz, W3::FHerbPerception());
			Ctl.assign(Nz, R3::FControlOutput());
			All.resize(Nz);
			const double Size = W.Config.WorldSize;
			// 늑대: 네 귀퉁이에서 가운데를 본다 (통합 처리기와 같은 입양 — 순번 짝수 잠행·홀수 추격)
			Threats.assign(static_cast<size_t>(M), W3::FThreatAgent());
			ThreatPtrs.clear();
			for (int32 m = 0; m < M; ++m)
			{
				const double X = (m % 2 == 0) ? 6.0 : Size - 6.0;
				const double Y = ((m / 2) % 2 == 0) ? 6.0 : Size - 6.0;
				W3::AdoptThreat(W, Threats[static_cast<size_t>(m)], EcoV3Integrated::WolfSpecForOrdinal(m, W.Config.PredSpeedMult), X, Y, 0.5 * Size - X,
								0.5 * Size - Y, 1000 + m);
				ThreatPtrs.push_back(&Threats[static_cast<size_t>(m)]);
			}
			// 사슴: 정해진 난수 자리 (늑대 14 단위·줄기 원판 여유 밖)
			FRandomStream Rs(PlaceSeed);
			for (int32 i = 0; i < N; ++i)
			{
				const size_t k = static_cast<size_t>(i);
				All[k] = W3::FHerbView{&Reps[k], &Dec[k], &Bodies[k], &Perc[k], &Ctl[k]};
				W3::FVec2 P{0.0, 0.0};
				for (int32 Try = 0; Try < 200; ++Try)
				{
					P = W3::FVec2{4.0 + (Size - 8.0) * Rs.GetFraction(), 4.0 + (Size - 8.0) * Rs.GetFraction()};
					bool bOk = true;
					for (const W3::FThreatAgent& A : Threats)
					{
						bOk = bOk && FMath::Square(A.State.PosX - P.X) + FMath::Square(A.State.PosY - P.Y) > 14.0 * 14.0;
					}
					const std::vector<double>& Dsc = W.Config.Obstacles.Discs;
					for (size_t d = 0; d + 2 < Dsc.size(); d += 3)
					{
						bOk = bOk && FMath::Square(Dsc[d] - P.X) + FMath::Square(Dsc[d + 1] - P.Y) > FMath::Square(Dsc[d + 2] + 1.5);
					}
					if (bOk)
					{
						break;
					}
				}
				const double Yaw = Rs.GetFraction() * 6.283185307179586;
				W3::AdoptHerb(W, All[k], P, W3::FVec2{FMath::Cos(Yaw), FMath::Sin(Yaw)}, R3::MakeAgentKeyFromStableId(5000 + i));
			}
			Live = All;
			W3::ObserveAndDecideAll(W, Live.data(), static_cast<int32>(Live.size()), ThreatPtrs.data(), M, Brain.Net);
		}

		void StepOnce(const P3::FPolicyNetV3& Net)
		{
			W3::Step(W, Live.data(), static_cast<int32>(Live.size()), ThreatPtrs.data(), static_cast<int32>(ThreatPtrs.size()), Net);
			std::vector<W3::FHerbView> Next;
			for (const W3::FHerbView& V : Live)
			{
				if (V.Body->DeathCause == W3::kDeathNone)
				{
					Next.push_back(V);
				}
			}
			Live = Next;
		}

		/** 스텝 지문 (FNV-1a 64): 사슴마다 자리·heading·에너지·비축·죽음·행동·다음 요청·덮기(실행·다음)·덮기 방향, 늑대 자리·heading. 길 칸·마스크·로짓은 넣지 않는다. */
		uint64 Fingerprint() const
		{
			uint64 H = 14695981039346656037ULL;
			auto Mix = [&H](const void* Data, size_t Bytes)
			{
				const uint8* B = static_cast<const uint8*>(Data);
				for (size_t i = 0; i < Bytes; ++i)
				{
					H = (H ^ B[i]) * 1099511628211ULL;
				}
			};
			for (size_t i = 0; i < Bodies.size(); ++i)
			{
				const W3::FHerbBody& B = Bodies[i];
				const W3::FHerbDecision& D = Dec[i];
				Mix(&B.Pos, sizeof(B.Pos));
				Mix(&B.Head, sizeof(B.Head));
				Mix(&B.Energy, sizeof(B.Energy));
				Mix(&B.Reserve, sizeof(B.Reserve));
				Mix(&B.DeathCause, sizeof(B.DeathCause));
				Mix(&Reps[i].Behavior, sizeof(Reps[i].Behavior));
				Mix(&D.Request, sizeof(D.Request));
				Mix(&D.KeepActive, sizeof(D.KeepActive));
				Mix(&D.KeepMode, sizeof(D.KeepMode));
				Mix(&D.KeepDir, sizeof(D.KeepDir));
			}
			for (const W3::FThreatAgent& A : Threats)
			{
				Mix(&A.State.PosX, sizeof(double));
				Mix(&A.State.PosY, sizeof(double));
				Mix(&A.State.HeadX, sizeof(double));
				Mix(&A.State.HeadY, sizeof(double));
			}
			return H;
		}

		int32 PanicNow() const
		{
			int32 N = 0;
			for (const W3::FHerbView& V : Live)
			{
				N += V.Decision->KeepMode == W3::kKeepPanic ? 1 : 0;
			}
			return N;
		}
	};

	/** 길 상태가 모두 지워졌나 (길 칸·관측 21~23·요청). */
	bool RouteCleared(const W3::FHerbDecision& D, const W3::FHerbPerception& P)
	{
		return D.Route == W3::kRouteNone && D.RouteK == -1 && D.RouteRequest == -1 && !D.bRouteDecide && !D.bRouteReads && P.RouteObs[0] == 0.0f
			   && P.RouteObs[1] == 0.0f && P.RouteObs[2] == 0.0f;
	}

	bool StatsZero(const W3::FRouteStats& S)
	{
		const FEcoV3RouteSum R = FEcoV3RouteSum::Of(S);
		int64 Rest = S.Steps[W3::kRouteCover] + S.Steps[W3::kRouteOpen] + S.OnsetShelter + S.RedecideFeas + S.BadShelter;
		for (int32 r = 0; r < W3::kNumRoutes; ++r)
		{
			Rest += S.Invalid[r] + S.Picked[r];
		}
		return R.RouteSteps() == 0 && R.Onsets == 0 && R.Decisions == 0 && R.Choice == 0 && R.Switches == 0 && Rest == 0;
	}

	bool FlightRouteZero(const W3::FFlightRouteStats& S)
	{
		int64 Sum = S.Refled;
		for (int32 r = 0; r < W3::kNumFlightRouteRows; ++r)
		{
			Sum += S.DropObstacle[r] + S.DropFoliage[r] + S.Chased[r] + S.Hidden[r];
			for (int32 c = 0; c < W3::kNumFlightCauses; ++c)
			{
				Sum += S.N[r][c] + S.Steps[r][c] + S.Contact[r][c];
			}
		}
		return Sum == 0;
	}

	FEcoV3BrainLoad LoadBrain(FAutomationTestBase& Test, const TCHAR* Name)
	{
		FEcoV3BrainLoad L = FEcoV3BrainRegistry::LoadFile(Name);
		Test.TestTrue(FString::Printf(TEXT("두뇌 파일 %s (%s: %s)"), Name, EcoV3Brain::RejectName(L.Reason), *L.Message), L.Ok());
		return L;
	}
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoRouteV3GeometryTest, "AdaptiveEcosystem.Policy.V3.Route.Geometry",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRouteV3GeometryTest::RunTest(const FString& Parameters)
{
	namespace RC = EcoWorldV3::RouteCheck;
	using namespace EcoRouteV3Test;
	Report(*this, TEXT("정의 (골든 상수 = 엔진 상수, 기본 꺼짐)"), RC::CheckDefinitions());
	const FReport Geo = RC::CheckGeometry();
	Report(*this, TEXT("SHELTER 기하 (k*·μ*·e*·방향·유지)"), Geo);
	TestTrue(TEXT("기하: 가능·유지·벽 여유로 바뀐 방향이 모두 나온다"), Geo.Count0 > 0 && Geo.Count1 > 0 && Geo.Count2 > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoRouteV3StepGoldenTest, "AdaptiveEcosystem.Policy.V3.Route.StepGolden",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRouteV3StepGoldenTest::RunTest(const FString& Parameters)
{
	namespace RC = EcoWorldV3::RouteCheck;
	using namespace EcoRouteV3Test;
	const FReport Rows = RC::CheckRows();
	Report(*this, TEXT("길 셈 줄 (결정·무효·잠금·관측 21~23)"), Rows);
	TestTrue(TEXT("길 셈 줄: 결정·무효가 나온다"), Rows.Count0 > 0 && Rows.Count1 > 0);
	const FReport Ap = RC::CheckApplies();
	Report(*this, TEXT("적용 (다음 스텝 첫머리 RouteApply)"), Ap);
	TestTrue(TEXT("적용: SHELTER 적용·길 바꿈이 나온다"), Ap.Count0 > 0 && Ap.Count1 > 0);
	Report(*this, TEXT("손 장면 길 통계"), RC::CheckSceneStats());
	Report(*this, TEXT("다시 난 개체 (지움·terminal_obs 0)"), RC::CheckRespawn());
	Report(*this, TEXT("관측 세 칸 사례 (WriteRouteObs float 비트)"), RC::CheckObsCases());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoRouteV3MaskRowsTest, "AdaptiveEcosystem.Policy.V3.Route.MaskRows",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRouteV3MaskRowsTest::RunTest(const FString& Parameters)
{
	namespace RC = EcoWorldV3::RouteCheck;
	using namespace EcoRouteV3Test;
	const FReport Mask = RC::CheckMask();
	Report(*this, TEXT("마스크 판 4·5 줄 (칸 3 늘 0)"), Mask);
	TestTrue(TEXT("마스크: 칸 4 열림·판 5 막힘·덮기 줄이 모두 나온다"), Mask.Count0 > 0 && Mask.Count1 > 0 && Mask.Count2 > 0);
	// 판 2 는 그대로 (ApplyRouteMaskRows 는 판 4·5 가 아니면 아무것도 하지 않는다)
	uint8 M[P3::kNumBehaviors] = {1, 1, 0, 1, 0};
	P3::ApplyRouteMaskRows(2, P3::kMaskOverridePanic, true, false, 0.5f, true, M);
	TestTrue(TEXT("판 2 마스크는 바꾸지 않는다"), M[0] == 1 && M[1] == 1 && M[2] == 0 && M[3] == 1 && M[4] == 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoRouteV3WorldTest, "AdaptiveEcosystem.Policy.V3.Route.World",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRouteV3WorldTest::RunTest(const FString& Parameters)
{
	namespace RC = EcoWorldV3::RouteCheck;
	using namespace EcoRouteV3Test;
	for (int32 b = 0; b < GR::kWorldBrains; ++b)
	{
		const FReport W = RC::CheckWorld(b);
		Report(*this, b == 0 ? TEXT("기준 루프 route0 (450 스텝 지문·기록·끝 도망 길 덩어리)") : TEXT("기준 루프 늘 SHELTER 시험 두뇌"), W);
		TestTrue(FString::Printf(TEXT("기준 루프 두뇌 %d: 길 결정이 있다"), b), W.Count1 > 0);
		TestTrue(FString::Printf(TEXT("기준 루프 두뇌 %d: %s"), b, b == 0 ? TEXT("route0 은 SHELTER 를 고르지 않는다") : TEXT("늘 SHELTER 두뇌는 SHELTER 를 고른다")),
				 b == 0 ? W.Count0 == 0 : W.Count0 > 0);
		AddInfo(FString::Printf(TEXT("두뇌 %d: SHELTER 고름 %lld · 길 결정 %lld · 잡힘 %lld"), b, static_cast<long long>(W.Count0), static_cast<long long>(W.Count1),
								static_cast<long long>(W.Count2)));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoRouteV3FlightRecordTest, "AdaptiveEcosystem.Policy.V3.Route.FlightRecord",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRouteV3FlightRecordTest::RunTest(const FString& Parameters)
{
	namespace RC = EcoWorldV3::RouteCheck;
	using namespace EcoRouteV3Test;
	const FReport Fs = RC::CheckFlightScene();
	Report(*this, TEXT("도망 길 기록 장면 (FlightUpdate + FFlightRouteStats — 길 덩어리 182 칸·사슴 칸)"), Fs);
	TestEqual(TEXT("refled 는 38 스텝 째 하나뿐 (39 는 아님)"), Fs.Count0, static_cast<int64>(1));
	TestTrue(TEXT("원판 놓침·쫓기는 스텝이 있다"), Fs.Count1 > 0 && Fs.Count2 > 0);
	// 10-24 적대적 검토: Step 의 H(FlightStepEnd)는 refled 의 스텝 번호로 도망 기록 시계 FFlightStats::Clock 을 넘긴다 — 통합 모드의 W.T 는 팀 시계에 다시
	// 맞출 때(CheckClockDrift) 뛰므로 W.T − 1 로 재면 refled 가 틀린다. 사슴 하나·늑대 없음: 도망 2 스텝 → 멈춤(살아 끝남) → W.T 가 뛴 뒤 k 스텝 쉬고 다시 도망
	{
		auto Run = [](int64 T0, int64 JumpTo, int32 Rest, int64& OutLastEnd)
		{
			W3::FWorldState W;
			W.Config.WildFlight.bEnabled = true;
			W.Config.WildFlight.bRoute = true;
			R3::FRepState Rep;
			W3::FHerbDecision Dec;
			W3::FHerbBody Body;
			W3::FHerbPerception Perc;
			R3::FControlOutput Ctl;
			const W3::FHerbView H{&Rep, &Dec, &Body, &Perc, &Ctl};
			int64 T = T0;
			auto Tick = [&](bool bFlee)
			{
				W.T = ++T;
				Dec.KeepActive = bFlee ? W3::kKeepPanic : W3::kKeepNone;
				Dec.Route = bFlee ? W3::kRouteRun : W3::kRouteNone;
				Dec.ExecutedBehavior = bFlee ? R3::kFlee : R3::kGraze;
				W3::Detail::FlightStepEnd(W, &H, 1, nullptr, 0);
			};
			Tick(true);
			Tick(true);
			Tick(false);   // 살아 끝남 (끝 FLEE 스텝 뒤 1 스텝 째): 끝 FLEE 스텝 = 지난 스텝 (시계 1)
			OutLastEnd = Dec.Flight.LastEndT;
			T = JumpTo;    // 팀 시계에 다시 맞춤 (뒤로·앞으로)
			for (int32 k = 2; k < Rest; ++k)
			{
				Tick(false);
			}
			Tick(true);    // 끝 FLEE 스텝 뒤 Rest 스텝 째 새 도망 (Rest ≥ 2)
			return W.Stats.FlightRoute.Refled;
		};
		int64 LastEnd = 0;
		const int64 Back = Run(1000, 10, 50, LastEnd);
		TestEqual(TEXT("시계: 끝난 도망의 끝 스텝 = 도망 기록 시계 1 (W.T 가 아니다)"), LastEnd, static_cast<int64>(1));
		TestEqual(TEXT("시계: W.T 가 뒤로 뛰어도 50 스텝 뒤 새 도망은 refled 가 아니다"), Back, static_cast<int64>(0));
		TestEqual(TEXT("시계: W.T 가 앞으로 뛰어도 20 스텝 뒤 새 도망은 refled"), Run(100, 5000, 20, LastEnd), static_cast<int64>(1));
		TestEqual(TEXT("시계: 38 스텝 째 refled · 39 는 아님 (경계 — 파이썬 self.t 차이와 같다)"), Run(0, 2, 38, LastEnd) * 10 + Run(0, 2, 39, LastEnd),
				  static_cast<int64>(10));
	}
	return true;
}

// -----------------------------------------------------------------------------
// Route.Off — 길 끔 = 지금 (이식 계획서 10-3, 지킬 것 1: 끈 세계는 지금 C++ 와 비트 단위로 같다 — 기존 골든 지문은 Wild·Flight·Foliage·Obstacle 시험이 그대로 본다)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoRouteV3OffTest, "AdaptiveEcosystem.Policy.V3.Route.Off",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRouteV3OffTest::RunTest(const FString& Parameters)
{
	using namespace EcoRouteV3Test;
	FEcoV3BrainRegistry::Get().ResetForTest();
	// (가) 기본 꺼짐, 도주 반사를 끈 세계는 켜지지 않는다 (InitWorld·SetModelRoute·SetModelFleeGate 모두 bEnabled 와 묶음)
	{
		const W3::FWorldConfig Def;
		const W3::FWorldState Ws;
		TestTrue(TEXT("기본 세계: 길 끔·판 5 막음 끔"), !Def.WildFlight.bRoute && !Ws.bFleeGate && !Def.WildFlight.bEnabled);
		W3::FWorldConfig C = FMini::RegionConfig(2, 8, 2);
		C.WildFlight.bRoute = true;   // 세계 설정에 켜도
		C.WildFlight.bEnabled = false;
		W3::FWorldState W;
		W3::InitWorld(W, C);
		W3::SetModelRoute(W, true);
		W3::SetModelFleeGate(W, true);
		TestTrue(TEXT("WildFlight 를 끈 세계: InitWorld·SetModelRoute·SetModelFleeGate 가 켜지 않는다"), !W.Config.WildFlight.bRoute && !W.bFleeGate);
		W3::FWorldConfig Cd = FMini::RegionConfig(2, 8, 2);
		W3::FWorldState Wd;
		W3::InitWorld(Wd, Cd);
		TestTrue(TEXT("통합 세계 설정은 길을 켜지 않는다 (두뇌가 정한다)"), Cd.WildFlight.bEnabled && !Wd.Config.WildFlight.bRoute && !Wd.bFleeGate);
		UEcoPolicyV3IntegratedSubsystem::ApplyBrainToWorld(Wd, *FEcoV3BrainRegistry::Builtin());
		TestTrue(TEXT("내장 두뇌를 걸어도 꺼짐·관측 18"), !Wd.Config.WildFlight.bRoute && !Wd.bFleeGate && Wd.ObsDim == O3::kObsDim);
	}
	// (나) 판 2 두뇌(내장 R1b-F)로 통합 지역 900 스텝: 길 칸·관측 21~23·길 통계·도망 길 기록이 늘 0
	{
		FMini M;
		M.Init(FMini::RegionConfig(0, 32, 4), *FEcoV3BrainRegistry::Builtin(), 32, 4, 41000);
		int32 BadSteps = 0;
		int64 PanicSteps = 0;
		for (int32 t = 0; t < 900; ++t)
		{
			M.StepOnce(P3::kBuiltinNet);
			bool bBad = false;
			for (size_t i = 0; i < M.All.size(); ++i)
			{
				bBad = bBad || !RouteCleared(M.Dec[i], M.Perc[i]) || M.Dec[i].bCommittedRouteReads;
				PanicSteps += M.Dec[i].KeepActive == W3::kKeepPanic ? 1 : 0;
			}
			BadSteps += bBad ? 1 : 0;
		}
		AddInfo(FString::Printf(TEXT("판 2 두뇌 900 스텝: 도주 사슴-스텝 %lld"), PanicSteps));
		TestTrue(TEXT("도주가 있었다 (길 끈 세계의 반사 도주)"), PanicSteps > 0);
		TestEqual(TEXT("길 끔: 사슴 길 칸·관측 21~23·길 요청이 늘 0 (모든 스텝)"), BadSteps, 0);
		TestTrue(TEXT("길 끔: 길 통계 0"), StatsZero(M.W.Stats.Route));
		TestTrue(TEXT("길 끔: 도망 길 기록 0"), FlightRouteZero(M.W.Stats.FlightRoute));
	}
	// (다) 두 길 → 길 없는 두뇌의 경계 스텝 (이식 계획서 8-2·12절 질문 2): A 는 고른 칸을 버리고 열린 도주를 그 H 의 반사 방향(RouteRunDir)으로 둔다
	{
		W3::FHerbDecision D;
		W3::FRouteStats St;
		D.KeepMode = W3::kKeepPanic;
		D.Route = W3::kRouteShelter;
		D.RouteK = 2;
		D.bRouteDecide = true;
		D.bRouteSok = true;
		D.RouteRequest = W3::kRouteSlotShelter;
		D.bRouteReads = true;
		D.RouteRunDir = W3::FVec2{0.6, 0.8};
		D.RouteShelterDir = W3::FVec2{-1.0, 0.0};
		D.KeepDir = W3::FVec2{0.0, -1.0};
		W3::Detail::RouteApply(D, false, St);
		TestTrue(TEXT("길 끔 A: 덮기 방향 = 반사 방향 (곧바로 RUN), 고른 SHELTER 는 버림"), D.KeepDir.X == 0.6 && D.KeepDir.Y == 0.8 && D.Route == W3::kRouteShelter);
		TestTrue(TEXT("길 끔 A: 결정 수·길 통계에 들지 않는다"), !D.bCommittedRouteReads && StatsZero(St));
		W3::FHerbDecision E = D;
		E.KeepMode = W3::kKeepNone;
		E.KeepDir = W3::FVec2{0.0, -1.0};
		W3::Detail::RouteApply(E, false, St);
		TestTrue(TEXT("길 끔 A: 도주가 아니면 덮기 방향 그대로"), E.KeepDir.X == 0.0 && E.KeepDir.Y == -1.0);
	}
	// (라) 세계 안 경계 두 가지 — route0(관측 24·판 4)과 obs21zero(관측 21·판 2) 두뇌 파일
	const FEcoV3BrainLoad Z24 = LoadBrain(*this, TEXT("v3_r1_g995_s3_obs24route0"));
	const FEcoV3BrainLoad Z21 = LoadBrain(*this, TEXT("v3_r1_g995_s3_obs21zero"));
	if (!Z24.Ok() || !Z21.Ok())
	{
		return false;
	}
	{
		// 길 없는 두뇌 → 두 길 (질문 1 — 권고대로): 열린 도주는 길 상태 없이 들어오므로 그 H 에서 길 없음(cur < 0) 결정 — 새 두뇌가 곧바로 고른다
		FMini M;
		M.Init(FMini::RegionConfig(0, 32, 4), *Z21.Brain, 32, 4, 41001);
		int32 t = 0;
		while (t < 1500 && M.PanicNow() < 2)
		{
			M.StepOnce(Z21.Brain->Net);
			++t;
		}
		std::vector<uint8> WasPanic(M.All.size(), 0);
		for (size_t i = 0; i < M.All.size(); ++i)
		{
			WasPanic[i] = (M.Dec[i].KeepMode == W3::kKeepPanic && M.Bodies[i].DeathCause == W3::kDeathNone) ? 1 : 0;
		}
		UEcoPolicyV3IntegratedSubsystem::ApplyBrainToWorld(M.W, *Z24.Brain);
		const W3::FRouteStats Before = M.W.Stats.Route;
		M.StepOnce(Z24.Brain->Net);
		int32 Continued = 0;
		int32 DecidedNone = 0;
		for (size_t i = 0; i < M.All.size(); ++i)
		{
			if (WasPanic[i] && M.Dec[i].KeepActive == W3::kKeepPanic && M.Dec[i].KeepMode == W3::kKeepPanic)
			{
				++Continued;
				DecidedNone += (M.Dec[i].bRouteDecide && M.Dec[i].RouteDecPrev == W3::kRouteNone && M.Dec[i].Route == W3::kRouteRun && M.Dec[i].bRouteReads
								&& (M.Dec[i].RouteRequest == W3::kRouteSlotRun || M.Dec[i].RouteRequest == W3::kRouteSlotShelter))
								   ? 1
								   : 0;
			}
		}
		AddInfo(FString::Printf(TEXT("길 없는 두뇌 → 두 길: %d 스텝에 도주 %d 마리, 이어진 도주 %d 마리 가운데 길 없음 결정 %d (길 결정 %lld − 시작 %lld)"), t,
								M.PanicNow(), Continued, DecidedNone, static_cast<long long>(M.W.Stats.Route.Decisions - Before.Decisions),
								static_cast<long long>(M.W.Stats.Route.Onsets - Before.Onsets)));
		TestTrue(TEXT("교체 순간 열린 도주가 있었다"), Continued > 0);
		TestEqual(TEXT("이어진 도주는 모두 그 H 에서 길 없음 결정 (새 두뇌가 곧바로 고름 — RouteDecPrev NONE)"), DecidedNone, Continued);
		TestTrue(TEXT("길 결정 ≥ 시작 + 이어진 도주"), M.W.Stats.Route.Decisions - Before.Decisions >= (M.W.Stats.Route.Onsets - Before.Onsets) + Continued);
		TestTrue(TEXT("교체 경계 스텝은 길 통계 실행 칸에 들지 않는다 (그 스텝 A 때 길이 없었다 — 질문 17)"),
				 M.W.Stats.Route.Steps[W3::kRouteRun] + M.W.Stats.Route.Steps[W3::kRouteShelter] == 0);

		// 두 길 → 길 없는 두뇌 (질문 2): 길이 있는 열린 도주를 만든 뒤 바꾸면, 그 스텝 H 가 길 상태·관측 21~23 을 모두 지우고 길 통계는 그대로다
		int32 t2 = 0;
		auto RouteNow = [&M]()
		{
			int32 N = 0;
			for (const W3::FHerbView& V : M.Live)
			{
				N += V.Decision->Route != W3::kRouteNone ? 1 : 0;
			}
			return N;
		};
		while (t2 < 1500 && RouteNow() == 0)
		{
			M.StepOnce(Z24.Brain->Net);
			++t2;
		}
		const int32 WithRoute = RouteNow();
		UEcoPolicyV3IntegratedSubsystem::ApplyBrainToWorld(M.W, *Z21.Brain);
		TestTrue(TEXT("길 없는 두뇌를 걸면 길 끔·관측 21"), !M.W.Config.WildFlight.bRoute && M.W.ObsDim == O3::kObsDimObstacle);
		const W3::FRouteStats Frozen = M.W.Stats.Route;
		const W3::FFlightRouteStats FrozenFl = M.W.Stats.FlightRoute;
		M.StepOnce(Z21.Brain->Net);
		int32 Left = 0;
		for (const W3::FHerbView& V : M.Live)
		{
			Left += RouteCleared(*V.Decision, *V.Perception) ? 0 : 1;
		}
		for (int32 k = 0; k < 120; ++k)
		{
			M.StepOnce(Z21.Brain->Net);
		}
		AddInfo(FString::Printf(TEXT("두 길 → 길 없는 두뇌: 길 있는 사슴 %d 마리 (%d 스텝 뒤), 경계 뒤 남은 길 상태 %d"), WithRoute, t2, Left));
		TestTrue(TEXT("교체 순간 길이 있는 열린 도주가 있었다"), WithRoute > 0);
		TestEqual(TEXT("경계 스텝 H 뒤 길 상태·관측 21~23 이 모두 지워진다"), Left, 0);
		TestTrue(TEXT("길 끈 뒤 길 통계·도망 길 기록은 더 늘지 않는다 (120 스텝)"),
				 FEcoV3RouteSum::Of(M.W.Stats.Route).Minus(FEcoV3RouteSum::Of(Frozen)).RouteSteps() == 0 && M.W.Stats.Route.Decisions == Frozen.Decisions
					 && M.W.Stats.FlightRoute.Refled == FrozenFl.Refled);
		TestEqual(TEXT("마스크 위반 0"), M.W.Stats.MaskViolations, static_cast<int64>(0));
		TestEqual(TEXT("망 칸 수와 세계 관측 칸 수 어긋남 0"), M.W.Stats.ObsLayoutMismatch, static_cast<int64>(0));
	}
	return true;
}

// -----------------------------------------------------------------------------
// Route.ZeroIdentity — route0 (길 켬) = obs21zero (길 끔): C++ 안에서 통합 지역 셋 × 1800 스텝 (이식 계획서 10-3, 16-6 '배포 동일')

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoRouteV3ZeroIdentityTest, "AdaptiveEcosystem.Policy.V3.Route.ZeroIdentity",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoRouteV3ZeroIdentityTest::RunTest(const FString& Parameters)
{
	using namespace EcoRouteV3Test;
	FEcoV3BrainRegistry::Get().ResetForTest();
	const FEcoV3BrainLoad Z24 = LoadBrain(*this, TEXT("v3_r1_g995_s3_obs24route0"));
	const FEcoV3BrainLoad Z21 = LoadBrain(*this, TEXT("v3_r1_g995_s3_obs21zero"));
	if (!Z24.Ok() || !Z21.Ok())
	{
		return false;
	}
	constexpr int32 kSteps = 1800;
	constexpr int32 kDeer = 32;
	constexpr int32 kWolves = 4;
	static const TCHAR* const Names[3] = {TEXT("숲"), TEXT("고지"), TEXT("메마른 땅")};
	int64 RouteDecisions = 0;
	int64 RouteSteps = 0;
	int64 PickedShelter = 0;
	int64 Choice = 0;
	for (int32 r = 0; r < 3; ++r)
	{
		FMini A;
		FMini B;
		const W3::FWorldConfig C = FMini::RegionConfig(r, kDeer, kWolves);
		A.Init(C, *Z21.Brain, kDeer, kWolves, 42000 + r);
		B.Init(C, *Z24.Brain, kDeer, kWolves, 42000 + r);
		TestTrue(FString::Printf(TEXT("%s: 길 끔 관측 21 · 길 켬 관측 24 (판 4 — 반사 밖 FLEE 막음 아님)"), Names[r]),
				 !A.W.Config.WildFlight.bRoute && A.W.ObsDim == O3::kObsDimObstacle && B.W.Config.WildFlight.bRoute && B.W.ObsDim == O3::kObsDimRoute
					 && !B.W.bFleeGate);
		int32 FirstSplit = A.Fingerprint() == B.Fingerprint() ? -1 : 0;
		for (int32 t = 1; t <= kSteps && FirstSplit < 0; ++t)
		{
			A.StepOnce(Z21.Brain->Net);
			B.StepOnce(Z24.Brain->Net);
			FirstSplit = A.Fingerprint() == B.Fingerprint() ? -1 : t;
		}
		const W3::FWorldStats& Sa = A.W.Stats;
		const W3::FWorldStats& Sb = B.W.Stats;
		const W3::FFlightReport Fa = W3::FlightReportOf(Sa.Flight, W3::FlightOpenOf(A.Live.data(), static_cast<int32>(A.Live.size())));
		const W3::FFlightReport Fb = W3::FlightReportOf(Sb.Flight, W3::FlightOpenOf(B.Live.data(), static_cast<int32>(B.Live.size())));
		const bool bSameRecord = Sa.Caught == Sb.Caught && Sa.Starved == Sb.Starved && FMemory::Memcmp(Sa.BehaviorSteps, Sb.BehaviorSteps, sizeof(Sa.BehaviorSteps)) == 0
								 && Fa.Started == Fb.Started && FMemory::Memcmp(Fa.Num, Fb.Num, sizeof(Fa.Num)) == 0
								 && FMemory::Memcmp(Fa.Steps, Fb.Steps, sizeof(Fa.Steps)) == 0 && FMemory::Memcmp(Fa.Contact, Fb.Contact, sizeof(Fa.Contact)) == 0
								 && Fa.ReflexSteps == Fb.ReflexSteps && Fa.EpStarted == Fb.EpStarted && Fa.EpHidden == Fb.EpHidden && Fa.EpCaught == Fb.EpCaught;
		AddInfo(FString::Printf(TEXT("%s: 첫 갈림 %d (−1 = 없음) · 잡힘 %lld · 굶음 %lld · 도망 %lld · 반사 스텝 %lld · 길 결정 %lld · 고름 RUN %lld / SHELTER %lld (열린 %lld)"),
								Names[r], FirstSplit, static_cast<long long>(Sb.Caught), static_cast<long long>(Sb.Starved), static_cast<long long>(Fb.Started),
								static_cast<long long>(Fb.ReflexSteps), static_cast<long long>(Sb.Route.Decisions),
								static_cast<long long>(Sb.Route.Picked[W3::kRouteRun]), static_cast<long long>(Sb.Route.Picked[W3::kRouteShelter]),
								static_cast<long long>(Sb.Route.Choice)));
		TestEqual(FString::Printf(TEXT("%s: route0 궤적 = obs21zero 궤적 (스텝마다 지문, %d 스텝)"), Names[r], kSteps), FirstSplit, -1);
		TestTrue(FString::Printf(TEXT("%s: 기록 같음 (잡힘·굶음·행동 스텝·도망 끝 까닭·반사·쫓김 사건)"), Names[r]), bSameRecord);
		TestTrue(FString::Printf(TEXT("%s: 길 끈 판은 길 통계 0"), Names[r]), StatsZero(Sa.Route) && FlightRouteZero(Sa.FlightRoute));
		TestEqual(FString::Printf(TEXT("%s: 마스크 위반·관측 칸 어긋남 0 (두 판)"), Names[r]),
				  Sa.MaskViolations + Sb.MaskViolations + Sa.ObsLayoutMismatch + Sb.ObsLayoutMismatch, static_cast<int64>(0));
		RouteDecisions += Sb.Route.Decisions;
		RouteSteps += Sb.Route.Steps[W3::kRouteRun] + Sb.Route.Steps[W3::kRouteShelter];
		PickedShelter += Sb.Route.Picked[W3::kRouteShelter];
		Choice += Sb.Route.Choice;
	}
	TestTrue(TEXT("길 켠 판에 길 결정·실행한 길 스텝이 있다 (지역 셋 합)"), RouteDecisions > 0 && RouteSteps > 0);
	TestEqual(TEXT("route0 은 SHELTER 를 고르지 않는다 (칸 4 = 칸 1 − 2)"), PickedShelter, static_cast<int64>(0));
	AddInfo(FString::Printf(TEXT("지역 셋 합: 길 결정 %lld · 실행한 길 스텝 %lld · SHELTER 가 열린 결정 %lld"), static_cast<long long>(RouteDecisions),
							static_cast<long long>(RouteSteps), static_cast<long long>(Choice)));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
