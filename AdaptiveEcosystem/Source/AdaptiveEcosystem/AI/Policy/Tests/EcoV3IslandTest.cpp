// 섬 무대 자동화 시험 (2026-11-05, Docs/RL_Policy/ISLAND_STAGE.md 14절) — 땅/물 지도(EcoV3Island.h)와 세계 연결(EcoWorldV3.h FWorldConfig::Island).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Island" -unattended -nopause -nosplash -NullRHI
//                        -testexit="Automation Test Queue Empty"
//
// 묶음:
//   Island.Mask        거리장·미끄러짐·반사·광선·가장 가까운 땅·해안 굽힘, 지문은 같은 지도면 같고 칸 하나만 달라도 다르다 (결정성)
//   Island.Sites       무리 자리 고르기: 두 번 고르면 같다, 자리 정사각 + 둘레 여유가 모두 땅, 자리끼리 간격, 여유를 줄여서라도 찾는다
//   Island.StartOnLand 무리 자리마다 지금 무대 계획(PlanStage — 늑대 모서리·사슴 고르게)을 땅 칸만 받게 돌리면 모든 시작 자리가 땅 칸이다
//   Island.OpenMaskNoOp 모든 칸이 열린 지도를 건 세계 = 지도 없는 세계 (300 스텝 사슴·늑대 자리·먹이 비트 단위로 같다 — 끄면 지금 그대로의 바탕)
//   Island.Confined    가운데 둥근 섬 + 호수 지도를 건 세계 600 스텝: 사슴·늑대가 막힌 칸에 한 번도 서지 않고, 막힌 칸 먹이는 늘 0
//   Island.Settings    설정 기본값 (끔 = 맵 조정자 따름, 무리 4 × 사슴 120·늑대 4, 합계 ≤ 512)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoV3Island.h"
#include "../EcoWorldV3.h"

#include <cstring>

namespace EcoV3IslandTest
{
	using namespace EcoV3Island;

	/** 가운데 (Cx, Cy) 반지름 R (단위) 둥근 섬 + 그 안의 호수 (Lx, Ly, Lr) — 나머지는 바다. */
	inline std::shared_ptr<FLandMask> DiskIsland(std::int32_t Gw, double Cell, double Cx, double Cy, double R, double Lx = 0, double Ly = 0, double Lr = 0)
	{
		auto M = std::make_shared<FLandMask>();
		M->Gw = Gw;
		M->Cell = Cell;
		M->Kind.assign(static_cast<size_t>(Gw) * Gw, kSea);
		for (std::int32_t y = 0; y < Gw; ++y)
		{
			for (std::int32_t x = 0; x < Gw; ++x)
			{
				const double Px = (x + 0.5) * Cell;
				const double Py = (y + 0.5) * Cell;
				const bool bIn = (Px - Cx) * (Px - Cx) + (Py - Cy) * (Py - Cy) <= R * R;
				const bool bLake = Lr > 0.0 && (Px - Lx) * (Px - Lx) + (Py - Ly) * (Py - Ly) <= Lr * Lr;
				M->Kind[M->Index(x, y)] = bLake ? kLake : (bIn ? kLand : kSea);
			}
		}
		M->BuildDistance();
		return M;
	}

	inline std::shared_ptr<FLandMask> OpenMask(std::int32_t Gw, double Cell)
	{
		auto M = std::make_shared<FLandMask>();
		M->Gw = Gw;
		M->Cell = Cell;
		M->Kind.assign(static_cast<size_t>(Gw) * Gw, kLand);
		M->BuildDistance();
		return M;
	}

	/** 작은 통합 꼴 세계 (평면 맵 설정 + 산 사슴만 Step — 기준 루프와 같은 꼴). */
	struct FMiniWorld
	{
		EcoWorldV3::FWorldState W;
		std::vector<EcoRepertoireV3::FRepState> Reps;
		std::vector<EcoWorldV3::FHerbDecision> Dec;
		std::vector<EcoWorldV3::FHerbBody> Bodies;
		std::vector<EcoWorldV3::FHerbPerception> Perc;
		std::vector<EcoRepertoireV3::FControlOutput> Ctl;
		std::vector<EcoWorldV3::FThreatAgent> Threats;
		std::vector<EcoWorldV3::FThreatAgent*> ThreatPtrs;
		std::vector<EcoWorldV3::FHerbView> Live;
	};

	/** 시작: 사슴 N·늑대 M 을 (StartX, StartY) 둘레 고리에 (지도가 있으면 땅 칸만). 같은 입력이면 같은 시작. */
	inline void InitMini(FMiniWorld& L, std::shared_ptr<const FLandMask> Island, std::int32_t N, std::int32_t M, double StartX, double StartY)
	{
		using namespace EcoWorldV3;
		namespace R3 = EcoRepertoireV3;
		FWorldConfig Cfg;
		Cfg.WorldSize = 100.0;
		Cfg.Seed = 20051;
		Cfg.NumHerbivores = N;
		Cfg.NumStalkers = (M + 1) / 2;
		Cfg.NumChasers = M / 2;
		Cfg.NumRanged = 0;
		Cfg.NumNocturnal = 0;
		Cfg.bRespawnDead = false;
		Cfg.PredEmaDenominator = N;
		Cfg.Covers = QuadCovers(Cfg.WorldSize, 6.0);
		Cfg.Island = Island;
		InitWorld(L.W, Cfg);
		SetModelAllowed(L.W, EcoPolicyV3::kAllowedMask);
		const size_t Nz = static_cast<size_t>(N);
		L.Reps.assign(Nz, R3::FRepState());
		L.Dec.assign(Nz, FHerbDecision());
		L.Bodies.assign(Nz, FHerbBody());
		L.Perc.assign(Nz, FHerbPerception());
		L.Ctl.assign(Nz, R3::FControlOutput());
		L.Live.clear();
		for (std::int32_t i = 0; i < N; ++i)
		{
			const size_t k = static_cast<size_t>(i);
			const FHerbView H{&L.Reps[k], &L.Dec[k], &L.Bodies[k], &L.Perc[k], &L.Ctl[k]};
			const double A = 2.0 * 3.14159265358979 * i / N;
			const double Rr = 4.0 + 6.0 * ((i * 7) % 5) / 5.0;
			AdoptHerb(L.W, H, {StartX + Rr * std::cos(A), StartY + Rr * std::sin(A)}, {std::cos(A), std::sin(A)}, R3::MakeAgentKey(static_cast<std::uint32_t>(i), 0));
			L.Live.push_back(H);
		}
		L.Threats.assign(static_cast<size_t>(M), FThreatAgent());
		L.ThreatPtrs.clear();
		for (std::int32_t m = 0; m < M; ++m)
		{
			const EcoThreatV3::FThreatSpec Spec = (m % 2 == 0) ? EcoThreatV3::MakeStalkerSpec(L.W.Config.PredSpeedMult, false, L.W.ThreatCfg)
															   : EcoThreatV3::MakeChaserSpec(L.W.Config.PredSpeedMult, false, false, L.W.ThreatCfg);
			const double A = 2.0 * 3.14159265358979 * (m + 0.5) / M;
			AdoptThreat(L.W, L.Threats[static_cast<size_t>(m)], Spec, StartX + 22.0 * std::cos(A), StartY + 22.0 * std::sin(A), -std::cos(A), -std::sin(A), m);
		}
		for (FThreatAgent& A : L.Threats)
		{
			L.ThreatPtrs.push_back(&A);
		}
		ObserveAndDecideAll(L.W, L.Live.data(), static_cast<std::int32_t>(L.Live.size()), L.ThreatPtrs.data(), M);
	}

	/** 한 스텝 (죽은 사슴은 다음 스텝부터 뺀다). */
	inline void StepMini(FMiniWorld& L)
	{
		EcoWorldV3::Step(L.W, L.Live.data(), static_cast<std::int32_t>(L.Live.size()), L.ThreatPtrs.data(), static_cast<std::int32_t>(L.ThreatPtrs.size()));
		size_t Keep = 0;
		for (size_t r = 0; r < L.Live.size(); ++r)
		{
			if (L.Live[r].Body->DeathCause == EcoWorldV3::kDeathNone)
			{
				L.Live[Keep++] = L.Live[r];
			}
		}
		L.Live.resize(Keep);
	}

	/** 상태 바이트 (사슴 자리·heading·에너지, 늑대 자리·heading, 먹이 합) — 비트 단위 견주기. */
	inline std::vector<std::uint8_t> StateBytes(const FMiniWorld& L)
	{
		std::vector<std::uint8_t> B;
		auto Put = [&B](double V)
		{
			std::uint8_t T[8];
			std::memcpy(T, &V, 8);
			B.insert(B.end(), T, T + 8);
		};
		for (const EcoWorldV3::FHerbBody& Bd : L.Bodies)
		{
			Put(Bd.Pos.X);
			Put(Bd.Pos.Y);
			Put(Bd.Head.X);
			Put(Bd.Head.Y);
			Put(Bd.Energy);
			Put(static_cast<double>(Bd.DeathCause));
		}
		for (const EcoWorldV3::FThreatAgent& A : L.Threats)
		{
			Put(A.State.PosX);
			Put(A.State.PosY);
			Put(A.State.HeadX);
			Put(A.State.HeadY);
		}
		Put(L.W.Food.Total());
		Put(static_cast<double>(L.W.Stats.Caught));
		return B;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3IslandMaskTest, "AdaptiveEcosystem.Policy.V3.Island.Mask",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3IslandMaskTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3Island;
	using namespace EcoV3IslandTest;
	// 100 × 100 칸 (칸 2 단위 — 200 단위 정사각), 가운데 반지름 60 단위 섬, 섬 안 (130, 100) 반지름 10 호수
	const auto M = DiskIsland(100, 2.0, 100.0, 100.0, 60.0, 130.0, 100.0, 10.0);
	TestTrue(TEXT("지도 유효"), M->Valid());
	TestTrue(TEXT("섬 가운데는 땅"), M->IsOpen(100.0, 100.0));
	TestFalse(TEXT("바다는 막힘"), M->IsOpen(10.0, 10.0));
	TestFalse(TEXT("호수는 막힘"), M->IsOpen(130.0, 100.0));
	TestTrue(TEXT("격자 밖은 막지 않는다 (정사각 벽이 막는다)"), M->IsOpen(-5.0, 300.0));
	// 거리장: 해안에서 멀수록 크다, 막힌 칸 0
	TestEqual(TEXT("막힌 칸 해안 거리 0"), M->ShoreDist(10.0, 10.0), 0.0);
	TestTrue(TEXT("섬 안쪽이 해안보다 멀다"), M->ShoreDist(80.0, 100.0) > M->ShoreDist(50.0, 100.0));
	TestTrue(TEXT("해안 거리 어림 (가운데 서쪽 80 → 서쪽 해안 40 까지 20 단위 ± 칸)"), FMath::Abs(M->ShoreDist(60.0, 100.0) - 20.0) <= 3.0);
	// 안쪽 법선: 서쪽 해안 곁에서는 동쪽(+x)을 본다
	double Nx = 0, Ny = 0;
	M->InwardNormal(44.0, 100.0, Nx, Ny);
	TestTrue(TEXT("서쪽 해안 안쪽 법선은 +x"), Nx > 0.9 && FMath::Abs(Ny) < 0.3);
	// 미끄러짐: 해안을 비스듬히 넘는 걸음은 한 축만, 곧장 넘는 걸음은 제자리
	{
		double Qx = 38.0, Qy = 103.0;   // (41, 100) 에서 서쪽(바다)으로 3 단위 + 북쪽 3
		const int32 R1 = M->Slide(41.0, 100.0, Qx, Qy);
		TestTrue(TEXT("비스듬히 넘으면 미끄러짐 (y 만)"), R1 == 1 && Qx == 41.0 && Qy == 103.0);
		double Sx = 30.0, Sy = 100.0;
		const int32 R2 = M->Slide(41.0, 100.0, Sx, Sy);
		TestTrue(TEXT("곧장 넘으면 미끄러짐 없음 → y 만도 막히고 x 만은 같은 자리 = 제자리 또는 축 미끄러짐"), R2 >= 1 && M->IsOpen(Sx, Sy));
		double Ox = 90.0, Oy = 95.0;
		TestEqual(TEXT("땅 안 걸음은 그대로"), M->Slide(91.0, 96.0, Ox, Oy), 0);
	}
	// 반사: 바다 쪽(−x)을 보던 heading 은 +x 쪽으로
	{
		double Hx = -1.0, Hy = 0.0;
		M->Reflect(42.0, 100.0, Hx, Hy);
		TestTrue(TEXT("반사 뒤 안쪽을 본다"), Hx > 0.5 && FMath::IsNearlyEqual(Hx * Hx + Hy * Hy, 1.0, 1e-9));
	}
	// 광선: (100, 100) 에서 +x 로 호수(반지름 10 — 120 에서 시작) 까지 약 20 단위 → 상한 16 안에는 없다, (112, 100) 에서는 8 안팎
	TestTrue(TEXT("광선 상한 안에 막힘 없음"), !FMath::IsFinite(M->RayBlocked(100.0, 100.0, 1.0, 0.0)));
	{
		const double T = M->RayBlocked(112.0, 100.0, 1.0, 0.0);
		TestTrue(TEXT("광선이 호수 가장자리에서 멈춘다 (6~10 단위)"), T >= 6.0 && T <= 10.0);
	}
	// 가장 가까운 땅: 바다 점에서 섬 해안 칸
	{
		double Ox = 0, Oy = 0;
		TestTrue(TEXT("바다에서 가장 가까운 땅"), M->NearestOpen(30.0, 100.0, Ox, Oy) && M->IsOpen(Ox, Oy) && Ox > 38.0 && Ox < 44.0);
	}
	// 해안 굽힘: 해안 곁에서 바다 쪽 속도는 해안을 따라가는 쪽으로 (크기 그대로), 안쪽 속도는 그대로
	{
		double Vx = -0.5, Vy = 0.1;
		const bool bSteer = M->ShoreSteer(43.0, 100.0, Vx, Vy);
		TestTrue(TEXT("해안 굽힘: 바다 쪽 성분이 줄고 크기 그대로"),
				 bSteer && Vx > -0.5 && FMath::IsNearlyEqual(FMath::Sqrt(Vx * Vx + Vy * Vy), FMath::Sqrt(0.26), 1e-9));
		double Ix = 0.5, Iy = 0.0;
		TestFalse(TEXT("해안 굽힘: 안쪽으로 가면 그대로"), M->ShoreSteer(43.0, 100.0, Ix, Iy));
		double Fx = -0.5, Fy = 0.0;
		TestFalse(TEXT("해안 굽힘: 해안에서 멀면 그대로"), M->ShoreSteer(100.0, 100.0, Fx, Fy));
	}
	// 결정성: 같은 입력이면 같은 지문, 칸 하나만 달라도 다르다
	{
		const auto M2 = DiskIsland(100, 2.0, 100.0, 100.0, 60.0, 130.0, 100.0, 10.0);
		TestEqual(TEXT("같은 지도 같은 지문"), M2->Fingerprint(), M->Fingerprint());
		auto M3 = DiskIsland(100, 2.0, 100.0, 100.0, 60.0, 130.0, 100.0, 10.0);
		M3->Kind[M3->Index(50, 50)] = kRock;
		TestNotEqual(TEXT("칸 하나가 다르면 지문이 다르다"), M3->Fingerprint(), M->Fingerprint());
		TestEqual(TEXT("같은 지도 같은 거리장"), M2->Dist == M->Dist, true);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3IslandSitesTest, "AdaptiveEcosystem.Policy.V3.Island.Sites",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3IslandSitesTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3Island;
	using namespace EcoV3IslandTest;
	// 400 × 400 칸 (800 단위), 큰 섬 반지름 350 + 호수
	const auto M = DiskIsland(400, 2.0, 400.0, 400.0, 350.0, 500.0, 420.0, 40.0);
	FSiteParams P;
	P.SizeUnits = 60.0;
	P.ClearUnits = 15.0;
	P.GapUnits = 200.0;
	P.Count = 4;
	M->LandCentroid(P.PrefX, P.PrefY);
	const FSiteResult A = PickHerdSites(*M, P);
	const FSiteResult B = PickHerdSites(*M, P);
	TestEqual(TEXT("자리 4 곳"), static_cast<int32>(A.Sites.size() / 2), 4);
	TestTrue(TEXT("두 번 고르면 같다 (결정적)"), A.Sites == B.Sites);
	for (size_t i = 0; i + 1 < A.Sites.size(); i += 2)
	{
		TestTrue(*FString::Printf(TEXT("자리 %d: 자리 정사각 + 둘레 여유가 모두 땅"), static_cast<int32>(i / 2) + 1),
				 SquareOpen(*M, A.Sites[i], A.Sites[i + 1], P.SizeUnits + 2.0 * P.ClearUnits - 2.0 * M->Cell));
		for (size_t j = 0; j < i; j += 2)
		{
			const double D = FMath::Sqrt(FMath::Square(A.Sites[i] - A.Sites[j]) + FMath::Square(A.Sites[i + 1] - A.Sites[j + 1]));
			TestTrue(TEXT("자리끼리 간격 이상"), D >= P.GapUnits);
		}
	}
	// 첫 자리는 땅 무게중심에 가장 가까운 후보
	TestTrue(TEXT("첫 자리가 무게중심 곁"), FMath::Abs(A.Sites[0] - P.PrefX) <= 20.0 && FMath::Abs(A.Sites[1] - P.PrefY) <= 20.0);
	// 좁은 섬: 여유를 줄여서라도 찾는다
	const auto Narrow = DiskIsland(60, 2.0, 60.0, 60.0, 45.0);
	FSiteParams Pn = P;
	Pn.Count = 2;
	Pn.GapUnits = 10.0;
	const FSiteResult C = PickHerdSites(*Narrow, Pn);
	TestTrue(TEXT("좁은 섬: 여유를 줄여 자리를 찾는다"), C.Sites.size() >= 2 && C.ClearUsed < Pn.ClearUnits);
	// 땅이 없으면 자리 0
	auto Sea = DiskIsland(50, 2.0, 0.0, 0.0, 0.0);
	TestEqual(TEXT("땅 없는 지도: 자리 0"), static_cast<int32>(PickHerdSites(*Sea, P).Sites.size()), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3IslandStartOnLandTest, "AdaptiveEcosystem.Policy.V3.Island.StartOnLand",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3IslandStartOnLandTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3Island;
	using namespace EcoV3IslandTest;
	using EcoRepertoireV3::kUnitCm;
	// 섬 정사각 1000 단위 (2 km), 가운데 섬 반지름 420 + 호수 — 서브시스템 IslandValidateNow 와 같은 길: 자리 고르기 → 자리마다 PlanStage (땅 칸·해안 2 m 밖만)
	const auto M = DiskIsland(500, 2.0, 500.0, 500.0, 420.0, 560.0, 520.0, 60.0);
	const FVector Origin(-100000.0, 50000.0, 0.0);
	FSiteParams Sp;
	Sp.SizeUnits = 60.0;
	Sp.ClearUnits = 15.0;
	Sp.GapUnits = 200.0;
	Sp.Count = 4;
	M->LandCentroid(Sp.PrefX, Sp.PrefY);
	const FSiteResult Sites = PickHerdSites(*M, Sp);
	TestEqual(TEXT("무리 자리 4"), static_cast<int32>(Sites.Sites.size() / 2), 4);
	FEcoV3IntegratedSettings S;
	S.StageSizeUnits = 60.0;
	auto Contains = [&M, &Origin](const FVector& P)
	{
		const double Ux = (P.X - Origin.X) / kUnitCm;
		const double Uy = (P.Y - Origin.Y) / kUnitCm;
		return M->IsOpen(Ux, Uy) && M->ShoreDist(Ux, Uy) >= 1.0;
	};
	auto Project = [](const FVector& Hint, FVector& Out)
	{
		Out = Hint;
		return true;
	};
	int32 Deer = 0, Wolves = 0, OffLand = 0;
	TArray<FVector> First;
	for (int32 h = 0; h < 4; ++h)
	{
		const FVector C(Origin.X + Sites.Sites[2 * h] * kUnitCm, Origin.Y + Sites.Sites[2 * h + 1] * kUnitCm, 0.0);
		FEcoV3StagePlan Plan;
		const bool bOk = UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Island"), h, C, C, S, 120, 4, true, Contains, Project, Plan, nullptr);
		TestTrue(*FString::Printf(TEXT("자리 %d: 사슴 120·늑대 4 를 다 놓았다"), h + 1), bOk && Plan.bComplete);
		for (const TArray<FVector>* Pts : {&Plan.DeerPoints, &Plan.WolfPoints})
		{
			for (const FVector& P : *Pts)
			{
				OffLand += M->IsOpen((P.X - Origin.X) / kUnitCm, (P.Y - Origin.Y) / kUnitCm) ? 0 : 1;
			}
		}
		Deer += Plan.DeerPoints.Num();
		Wolves += Plan.WolfPoints.Num();
		if (h == 0)
		{
			First = Plan.DeerPoints;
		}
	}
	TestEqual(TEXT("사슴 480"), Deer, 480);
	TestEqual(TEXT("늑대 16"), Wolves, 16);
	TestEqual(TEXT("땅 칸 밖 시작 자리 0"), OffLand, 0);
	// 같은 씨·같은 자리면 같은 시작 자리
	{
		const FVector C(Origin.X + Sites.Sites[0] * kUnitCm, Origin.Y + Sites.Sites[1] * kUnitCm, 0.0);
		FEcoV3StagePlan Again;
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Island"), 0, C, C, S, 120, 4, true, Contains, Project, Again, nullptr);
		TestTrue(TEXT("같은 씨 같은 시작 자리"), Again.DeerPoints == First);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3IslandOpenMaskNoOpTest, "AdaptiveEcosystem.Policy.V3.Island.OpenMaskNoOp",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3IslandOpenMaskNoOpTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3IslandTest;
	// 지도 없음 vs 모든 칸이 열린 지도: 섬 규칙(먹이·미끄러짐·해안 굽힘·반사·광선)이 하나도 걸리지 않아 300 스텝 내내 비트 단위로 같다
	FMiniWorld A, B;
	InitMini(A, nullptr, 48, 4, 50.0, 50.0);
	InitMini(B, OpenMask(50, 2.0), 48, 4, 50.0, 50.0);
	bool bSame = StateBytes(A) == StateBytes(B);
	TestTrue(TEXT("시작이 같다"), bSame);
	int32 FirstDiff = -1;
	for (int32 t = 1; t <= 300 && FirstDiff < 0; ++t)
	{
		StepMini(A);
		StepMini(B);
		if (StateBytes(A) != StateBytes(B))
		{
			FirstDiff = t;
		}
	}
	TestEqual(TEXT("300 스텝 비트 단위로 같다 (처음 다른 스텝 −1)"), FirstDiff, -1);
	TestEqual(TEXT("섬 기록 0 (굽힘·미끄러짐·제자리·반사)"),
			  B.W.Stats.IslandDeerSteers + B.W.Stats.IslandDeerSlides + B.W.Stats.IslandDeerStops + B.W.Stats.IslandWolfReflects, static_cast<int64>(0));
	TestTrue(TEXT("세계가 실제로 움직였다 (먹이를 먹었다)"), A.W.Stats.FoodEaten > 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3IslandConfinedTest, "AdaptiveEcosystem.Policy.V3.Island.Confined",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3IslandConfinedTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3Island;
	using namespace EcoV3IslandTest;
	// 100 단위 세계에 반지름 30 둥근 섬 (가운데 (50, 50)) + 섬 안 호수 (62, 50) 반지름 5. 사슴·늑대가 섬 안에서 시작
	const auto M = DiskIsland(50, 2.0, 50.0, 50.0, 30.0, 62.0, 50.0, 5.0);
	FMiniWorld L;
	InitMini(L, M, 48, 4, 45.0, 50.0);
	int64 OnBlocked = 0;
	auto Count = [&L, &M]()
	{
		int64 N = 0;
		for (const EcoWorldV3::FHerbView& H : L.Live)
		{
			N += M->IsOpen(H.Body->Pos.X, H.Body->Pos.Y) ? 0 : 1;
		}
		for (const EcoWorldV3::FThreatAgent& A : L.Threats)
		{
			N += M->IsOpen(A.State.PosX, A.State.PosY) ? 0 : 1;
		}
		return N;
	};
	OnBlocked += Count();
	double BlockedFood = 0.0;
	for (int32 t = 1; t <= 600; ++t)
	{
		StepMini(L);
		OnBlocked += Count();
		const EcoWorldV3::FFoodGrid& F = L.W.Food;
		for (std::int32_t y = 0; y < F.Gw; ++y)
		{
			for (std::int32_t x = 0; x < F.Gw; ++x)
			{
				if (!M->IsOpen((x + 0.5) * F.Cell, (y + 0.5) * F.Cell))
				{
					BlockedFood += F.Food[static_cast<size_t>(y) * F.Gw + x] + F.Cap[static_cast<size_t>(y) * F.Gw + x];
				}
			}
		}
	}
	TestEqual(TEXT("막힌 칸 위 사슴·늑대 (600 스텝 내내) 0"), OnBlocked, static_cast<int64>(0));
	TestEqual(TEXT("막힌 칸 먹이·용량 0"), BlockedFood, 0.0);
	TestTrue(TEXT("섬 규칙이 실제로 걸렸다 (굽힘·미끄러짐·반사 가운데 하나 이상)"),
			 L.W.Stats.IslandDeerSteers + L.W.Stats.IslandDeerSlides + L.W.Stats.IslandWolfReflects > 0);
	AddInfo(FString::Printf(TEXT("굽힘 %lld · 미끄러짐 %lld · 제자리 %lld · 늑대 반사 %lld · 잡힘 %lld · 산 사슴 %d"), static_cast<long long>(L.W.Stats.IslandDeerSteers),
							static_cast<long long>(L.W.Stats.IslandDeerSlides), static_cast<long long>(L.W.Stats.IslandDeerStops),
							static_cast<long long>(L.W.Stats.IslandWolfReflects), static_cast<long long>(L.W.Stats.Caught), static_cast<int32>(L.Live.size())));
	// 같은 시작 두 번 = 같은 궤적 (결정성)
	FMiniWorld L2;
	InitMini(L2, M, 48, 4, 45.0, 50.0);
	for (int32 t = 1; t <= 600; ++t)
	{
		StepMini(L2);
	}
	TestTrue(TEXT("같은 시작 같은 궤적"), StateBytes(L) == StateBytes(L2));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3IslandSettingsTest, "AdaptiveEcosystem.Policy.V3.Island.Settings",
								 EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoV3IslandSettingsTest::RunTest(const FString& Parameters)
{
	const FEcoV3IslandSettings D;
	TestEqual(TEXT("기본 = 맵 조정자를 따름 (−1)"), D.Mode, -1);
	TestEqual(TEXT("기본 지역 Island"), D.Region, FName(TEXT("Island")));
	TestTrue(TEXT("기본 무리 4 × (사슴 120 + 늑대 4) ≤ 512"), D.Herds * (D.DeerPerHerd + D.WolvesPerHerd) <= 512 && D.Herds == 4 && D.DeerPerHerd == 120
																	 && D.WolvesPerHerd == 4);
	const FEcoV3IslandSettings C = FEcoV3IslandSettings::FromConsole();
	TestTrue(TEXT("콘솔 값은 범위 안"), C.Herds >= 1 && C.Herds <= 8 && C.DeerPerHerd >= 1 && C.DeerPerHerd <= 128 && C.WolvesPerHerd >= 0 && C.WolvesPerHerd <= 12);
	// 세계 설정 기본: 지도 없음 (다른 맵은 지금 그대로)
	const EcoWorldV3::FWorldConfig Wc;
	TestTrue(TEXT("FWorldConfig::Island 기본 nullptr"), Wc.Island == nullptr);
	TestTrue(TEXT("조정자 bV3IslandStage 기본 거짓"), !GetDefault<AEcoCreatureIntegrationSpawner>()->bV3IslandStage);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
