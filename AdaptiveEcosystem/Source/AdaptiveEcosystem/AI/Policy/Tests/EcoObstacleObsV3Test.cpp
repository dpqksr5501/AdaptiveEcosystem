// R5 장애물 관측(10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계약 Docs/RL_Policy/POLICY_CONTRACT_V3.md 2-4)의 자동화 시험 —
// C++ EcoObservationV3::ObstacleObsValues·WriteObstacleObs 를 파이썬 골든(ObstacleObsGoldenVectorsV3.h, herbivore_rl/export_golden_v3_obstacle_obs.py)과
// 비트 단위로 대조하고, 세계 층(EcoWorldV3 — 관측 21 두뇌의 망 입력 = 관측 18 + 세 칸)을 엔진 없이 돌린다.
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.ObstacleObs"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 묶음:
//   ObstacleObs.Golden  설정 칸(관측 21·첫 칸 18·칸 이름·계약 해시·분모·몸·eps)이 C++ 상수와 같다, 사례 435(손 35·장면 256·롤아웃 144)의
//                       원시 거리 E·N(double)·가림·관측 세 칸(float)이 파이썬과 비트 단위로 같다, 로더가 관측 21 계약을 안다
//   ObstacleObs.World   기준 루프 (무대 60, 사슴 64, 늑대 4, 원판 = 골든 묶음 3 숲 + 덤불 240, 시야 300°·발소리) 600 스텝 다섯 판:
//                       (A) 관측 18 + 내장  (B) 관측 21 세계 + 내장 망 — A 와 궤적·요청·로짓·관측 18 이 비트 단위로 같고 세 칸은 그 스텝 기하로 다시 잰 값
//                       (C) 관측 21 + 새 열 0 인 망 — A 와 요청·로짓이 비트 단위로 같다  (D) 새 열에 값이 있는 망 — 결정이 달라진다(세 칸이 망에 닿는다)
//                       (E) 관측 18 세계 + 관측 21 망 — 어긋남 셈(ObsLayoutMismatch)이 센다. A~D 는 0

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoObservationV3.h"
#include "../EcoV3Brain.h"
#include "../EcoWorldV3.h"
#include "../ObstacleObsGoldenVectorsV3.h"

#include <cstring>
#include <vector>

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoObstacleObsV3Test
{
	namespace G = EcoObservationV3::GoldenObstacleObs;
	namespace O3 = EcoObservationV3;
	namespace P3 = EcoPolicyV3;

	bool SameBits(double A, double B) { return std::memcmp(&A, &B, sizeof(double)) == 0; }

	/** 골든 원판 묶음 k 의 원판 (x, y, r) 배열. */
	std::vector<double> SetDiscs(int32 Set)
	{
		const int32 Start = G::kSetIndex[2 * Set];
		const int32 Num = G::kSetIndex[2 * Set + 1];
		return std::vector<double>(G::kSetDiscs + 3 * Start, G::kSetDiscs + 3 * (Start + Num));
	}

	/** 기준 루프 세계 (Obstacle.Run 과 같은 꼴 + 시야 300°·발소리 — 줄기 뒤 늑대를 발소리로만 아는 사슴이 나온다). */
	EcoWorldV3::FWorldConfig WorldConfig()
	{
		EcoWorldV3::FWorldConfig C;
		C.WorldSize = G::kStageSize;
		C.Seed = 20011;
		C.NumHerbivores = 64;
		C.NumStalkers = 2;
		C.NumChasers = 2;
		C.NumRanged = 0;
		C.NumNocturnal = 0;
		C.Covers = EcoWorldV3::QuadCovers(C.WorldSize, 6.0);
		C.bShelterSafe = true;
		C.ShelterWolfMargin = 0.5;
		C.RealismVision.bEnabled = true;
		C.RealismHearing.bEnabled = true;
		C.Obstacles.bEnabled = true;
		C.Obstacles.Discs = SetDiscs(3);   // 숲 나무 24 + 덤불 (1 ha 150, 반지름 1~2 m)
		C.Obstacles.Detour.bEnabled = true;
		return C;
	}

	/** 관측 21 망: 내장 첫 층 가중치 (64 × 18) 뒤에 새 세 열 (Extra[j·3 + c]). 나머지 층은 내장 그대로. */
	struct FNet21
	{
		std::vector<float> Layer0;
		P3::FPolicyNetV3 Net{};

		explicit FNet21(TFunctionRef<float(int32 /*j*/, int32 /*c*/)> Extra)
		{
			const int32 D = O3::kObsDimObstacle;
			Layer0.assign(static_cast<size_t>(P3::kHiddenDim) * D, 0.0f);
			for (int32 j = 0; j < P3::kHiddenDim; ++j)
			{
				for (int32 i = 0; i < P3::kObsDim; ++i)
				{
					Layer0[static_cast<size_t>(j) * D + i] = P3::kW0[j * P3::kObsDim + i];
				}
				for (int32 c = 0; c < O3::kNumObstacleObs; ++c)
				{
					Layer0[static_cast<size_t>(j) * D + P3::kObsDim + c] = Extra(j, c);
				}
			}
			Net = {D, Layer0.data(), P3::kB0, P3::kW1, P3::kB1, P3::kW2, P3::kB2};
		}
	};

	/** 한 판 (배열 저장 세계 — FReferenceWorld 와 같은 순서, 관측 칸 수와 망을 고른다). */
	struct FRun
	{
		EcoWorldV3::FWorldState W;
		std::vector<EcoRepertoireV3::FRepState> Reps;
		std::vector<EcoWorldV3::FHerbDecision> Decisions;
		std::vector<EcoWorldV3::FHerbBody> Bodies;
		std::vector<EcoWorldV3::FHerbPerception> Perceptions;
		std::vector<EcoRepertoireV3::FControlOutput> Controls;
		std::vector<EcoWorldV3::FThreatAgent> Threats;
		std::vector<EcoWorldV3::FHerbView> Views;
		std::vector<EcoWorldV3::FThreatAgent*> ThreatPtrs;
		const P3::FPolicyNetV3* Net = &P3::kBuiltinNet;

		void Init(const EcoWorldV3::FWorldConfig& C, int32 ObsDim, const P3::FPolicyNetV3& InNet)
		{
			Net = &InNet;
			EcoWorldV3::InitWorld(W, C);
			EcoWorldV3::SetModelObsDim(W, ObsDim);
			const size_t N = static_cast<size_t>(C.NumHerbivores);
			const size_t M = static_cast<size_t>(C.NumThreats());
			Reps.assign(N, {});
			Decisions.assign(N, {});
			Bodies.assign(N, {});
			Perceptions.assign(N, {});
			Controls.assign(N, {});
			Threats.assign(M, {});
			Views.resize(N);
			ThreatPtrs.resize(M);
			for (size_t i = 0; i < N; ++i)
			{
				Views[i] = {&Reps[i], &Decisions[i], &Bodies[i], &Perceptions[i], &Controls[i]};
				EcoWorldV3::InitHerb(W, static_cast<std::uint32_t>(i), Views[i]);
			}
			for (size_t m = 0; m < M; ++m)
			{
				ThreatPtrs[m] = &Threats[m];
				EcoWorldV3::InitThreat(W, static_cast<std::uint32_t>(m), Threats[m]);
			}
			EcoWorldV3::ObserveAndDecideAll(W, Views.data(), static_cast<int32>(N), ThreatPtrs.data(), static_cast<int32>(M), *Net);
		}

		void StepOnce()
		{
			EcoWorldV3::Step(W, Views.data(), static_cast<int32>(Views.size()), ThreatPtrs.data(), static_cast<int32>(ThreatPtrs.size()), *Net);
		}
	};

	/** 두 판의 이 스텝: 몸·행동·요청·로짓·관측 18 이 비트 단위로 같은가. bObs18 이 거짓이면 관측은 보지 않는다. */
	bool SameStep(const FRun& A, const FRun& B, bool bObs18, bool bLogits)
	{
		bool bSame = A.W.Rng.State == B.W.Rng.State;
		for (size_t i = 0; i < A.Bodies.size() && bSame; ++i)
		{
			bSame = SameBits(A.Bodies[i].Pos.X, B.Bodies[i].Pos.X) && SameBits(A.Bodies[i].Pos.Y, B.Bodies[i].Pos.Y)
					&& SameBits(A.Bodies[i].Energy, B.Bodies[i].Energy) && A.Reps[i].Behavior == B.Reps[i].Behavior
					&& A.Decisions[i].Request == B.Decisions[i].Request;
			if (bSame && bLogits)
			{
				bSame = std::memcmp(A.Decisions[i].Logits, B.Decisions[i].Logits, sizeof(A.Decisions[i].Logits)) == 0;
			}
			if (bSame && bObs18)
			{
				bSame = std::memcmp(A.Perceptions[i].Obs, B.Perceptions[i].Obs, sizeof(A.Perceptions[i].Obs)) == 0;
			}
		}
		for (size_t m = 0; m < A.Threats.size() && bSame; ++m)
		{
			bSame = SameBits(A.Threats[m].State.PosX, B.Threats[m].State.PosX) && SameBits(A.Threats[m].State.PosY, B.Threats[m].State.PosY);
		}
		return bSame;
	}
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObstacleObsV3GoldenTest,
	"AdaptiveEcosystem.Policy.V3.ObstacleObs.Golden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoObstacleObsV3GoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoObstacleObsV3Test;

	// 설정 칸 = C++ 상수 (파이썬 거울 설정 obstacle_obs·obstacles 계수)
	TestEqual(TEXT("관측 21 = 관측 18 + 3"), G::kObsDim, O3::kObsDimObstacle);
	TestEqual(TEXT("첫 칸 18"), G::kFirstSlot, O3::kObsEscapeRoom);
	TestTrue(TEXT("칸 번호 18·19·20"), O3::kObsEscapeRoom == O3::kObsDim && O3::kObsObstacleNear == O3::kObsDim + 1 && O3::kObsThreatHidden == O3::kObsDim + 2);
	for (int32 c = 0; c < O3::kNumObstacleObs; ++c)
	{
		TestEqual(FString::Printf(TEXT("칸 이름 %d"), c), FString(UTF8_TO_TCHAR(O3::kObstacleObsNames[c])), FString(UTF8_TO_TCHAR(G::kSlotNames[c])));
	}
	TestEqual(TEXT("계약 해시 (관측 21·마스크 판 2) = 파이썬 contract_hash"), P3::kContractHashObs21Mask2, G::kContractHashObs21Mask2);
	TestTrue(TEXT("분모 escape 10·near 5 단위 = 거울 설정"), O3::kR5ObstacleObsConfig.EscapeNorm == G::kEscapeNorm && O3::kR5ObstacleObsConfig.NearNorm == G::kNearNorm);
	TestEqual(TEXT("몸 반지름 = 세로 장애물 기본 (0.15)"), EcoWorldV3::FObstacleConfig().BodyR, G::kBodyR);
	TestEqual(TEXT("eps = EcoRepertoireV3::kEps"), EcoRepertoireV3::kEps, G::kEps);
	TestTrue(TEXT("관측 18 이름 = 정책 생성 헤더"), FCStringAnsi::Strcmp(O3::kObsNames[17], P3::kObsNames[17]) == 0);
	{
		const EcoV3Brain::FContract* C = EcoV3Brain::FindContract(P3::kContractHashObs21Mask2);
		bool bNames = C != nullptr;
		for (int32 i = 0; bNames && i < G::kObsDim; ++i)
		{
			const char* Want = i < P3::kObsDim ? P3::kObsNames[i] : G::kSlotNames[i - P3::kObsDim];
			bNames = FCStringAnsi::Strcmp(EcoV3Brain::ContractObsName(*C, i), Want) == 0;
		}
		TestTrue(TEXT("두뇌 로더가 관측 21 계약을 안다 (칸 수·마스크 판 2·이름 = 골든)"), C && C->ObsDim == G::kObsDim && C->MaskVersion == 2 && bNames);
		TestTrue(TEXT("두뇌 로더의 관측 18 계약 = 내장"), EcoV3Brain::FindContract(P3::kContractHash) && EcoV3Brain::FindContract(P3::kContractHash)->ObsDim == P3::kObsDim);
		TestNull(TEXT("R2 관측 19·판 3 계약은 받지 않는다"), EcoV3Brain::FindContract(P3::kContractHashObs19Mask3));
	}

	// 사례 435: 원시 거리·가림·관측 세 칸이 비트 단위로 같다
	int32 Bad = 0;
	int32 First = -1;
	int32 Hidden = 0;
	int32 Seen = 0;
	int32 ByKind[3] = {};
	for (int32 c = 0; c < G::kCases; ++c)
	{
		const std::int32_t* I = G::kCaseInt + 4 * c;
		const double* In = G::kCaseIn + 10 * c;
		O3::FObstacleObsInput Oi;
		Oi.Pos = {In[0], In[1]};
		Oi.Head = {In[2], In[3]};
		Oi.bSeen = I[2] != 0;
		Oi.Away = {In[4], In[5]};
		Oi.Threat = {In[6], In[7]};
		Oi.Discs = G::kSetDiscs + 3 * G::kSetIndex[2 * I[1]];
		Oi.NumDiscs = G::kSetIndex[2 * I[1] + 1];
		Oi.BodyR = In[8];
		Oi.StageSize = In[9];
		Oi.bBlockSight = I[3] != 0;
		const O3::FObstacleObs R = O3::ObstacleObsValues(Oi);
		float Obs[O3::kNumObstacleObs];
		O3::WriteObstacleObs(R, Obs);
		const double N = std::isinf(R.Near) ? G::kNoDist : R.Near;
		const bool bOk = SameBits(R.Escape, G::kCaseOut[2 * c]) && SameBits(N, G::kCaseOut[2 * c + 1]) && static_cast<int32>(R.bThreatHidden) == G::kCaseHidden[c]
						 && std::memcmp(Obs, &G::kCaseObs[3 * c], sizeof(Obs)) == 0;
		if (!bOk)
		{
			if (First < 0)
			{
				First = c;
				AddInfo(FString::Printf(TEXT("처음 어긋남 사례 %d (종류 %d): E %.17g / %.17g, N %.17g / %.17g, 가림 %d / %d"), c, I[0], R.Escape, G::kCaseOut[2 * c], N,
										G::kCaseOut[2 * c + 1], R.bThreatHidden ? 1 : 0, G::kCaseHidden[c]));
			}
			++Bad;
		}
		Hidden += R.bThreatHidden ? 1 : 0;
		Seen += Oi.bSeen ? 1 : 0;
		++ByKind[FMath::Clamp(I[0], 0, 2)];
	}
	AddInfo(FString::Printf(TEXT("사례 %d (손 %d·장면 %d·롤아웃 %d), 어긋남 %d, 가림 %d, 위협을 앎 %d"), G::kCases, ByKind[0], ByKind[1], ByKind[2], Bad, Hidden, Seen));
	TestTrue(TEXT("사례 수 = 손 + 장면 + 롤아웃"), ByKind[0] == G::kHandCases && ByKind[1] == G::kSceneCases && ByKind[2] == G::kRolloutCases);
	TestEqual(TEXT("E·N(double)·가림·관측 세 칸(float)이 파이썬과 비트 단위로 같다"), Bad, 0);
	TestEqual(TEXT("가림 사례 수 = 골든"), Hidden, G::kHiddenCases);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObstacleObsV3WorldTest,
	"AdaptiveEcosystem.Policy.V3.ObstacleObs.World",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoObstacleObsV3WorldTest::RunTest(const FString& Parameters)
{
	using namespace EcoObstacleObsV3Test;
	constexpr int32 kSteps = 600;   // 80 초
	const EcoWorldV3::FWorldConfig C = WorldConfig();
	const FNet21 Zero([](int32, int32) { return 0.0f; });
	// 새 열에 값이 있는 망: escape_room 이 크면(트였으면) 도망·숨기 쪽 은닉을 크게 민다 — 세 칸이 망에 닿는지 보는 시험용
	const FNet21 Probe([](int32 j, int32 c) { return c == 0 ? ((j % 2) ? 3.0f : -3.0f) : (c == 2 ? 2.0f : 0.0f); });

	FRun A, B, Cz, D, E;
	A.Init(C, O3::kObsDim, P3::kBuiltinNet);
	B.Init(C, O3::kObsDimObstacle, P3::kBuiltinNet);
	Cz.Init(C, O3::kObsDimObstacle, Zero.Net);
	D.Init(C, O3::kObsDimObstacle, Probe.Net);
	E.Init(C, O3::kObsDim, Zero.Net);

	int32 DiffB = SameStep(A, B, true, true) ? 0 : 1;
	int32 DiffC = SameStep(A, Cz, true, true) ? 0 : 1;
	int32 DiffE = SameStep(A, E, true, true) ? 0 : 1;
	int32 DiffDFrames = 0;
	int64 SlotBad = 0;          // B: 세 칸 ≠ 그 스텝 기하로 다시 잰 값, 또는 [0, 1] 밖
	int64 ZeroSlotsA = 0;       // A: 세 칸을 만들지 않으면 0·기본값
	int64 DecisionsC = 0;       // C: 두뇌를 부른 결정
	int64 LogitBadC = 0;        // C: 21 칸 입력을 다시 붙여 돌린 로짓 ≠ 저장 로짓
	int64 Rows = 0, Hidden = 0, NearTrunk = 0, EscapeZero = 0, SeenRows = 0;
	auto CheckRun = [&](const FRun& R, bool bWantSlots)
	{
		for (size_t i = 0; i < R.Perceptions.size(); ++i)
		{
			const EcoWorldV3::FHerbPerception& P = R.Perceptions[i];
			if (!bWantSlots)
			{
				ZeroSlotsA += (P.ObstacleObs[0] != 0.0f || P.ObstacleObs[1] != 0.0f || P.ObstacleObs[2] != 0.0f || P.Obstacle.Escape != 0.0 || !std::isinf(P.Obstacle.Near)
							   || P.Obstacle.bThreatHidden) ? 1 : 0;
				continue;
			}
			const O3::FObstacleObs V = O3::ObstacleObsValues(EcoWorldV3::Detail::ObstacleObsInputOf(R.W, P, R.Bodies[i]));
			float Want[O3::kNumObstacleObs];
			O3::WriteObstacleObs(V, Want);
			bool bOk = SameBits(V.Escape, P.Obstacle.Escape) && SameBits(V.Near, P.Obstacle.Near) && V.bThreatHidden == P.Obstacle.bThreatHidden
					   && std::memcmp(Want, P.ObstacleObs, sizeof(Want)) == 0;
			for (const float X : P.ObstacleObs)
			{
				bOk = bOk && X >= 0.0f && X <= 1.0f;
			}
			SlotBad += bOk ? 0 : 1;
			if (R.Bodies[i].DeathCause == EcoWorldV3::kDeathNone)
			{
				++Rows;
				Hidden += P.ObstacleObs[2] > 0.5f ? 1 : 0;
				NearTrunk += P.ObstacleObs[1] < 1.0f ? 1 : 0;
				EscapeZero += P.ObstacleObs[0] == 0.0f ? 1 : 0;
				SeenRows += P.Threat.PredCount > 0 ? 1 : 0;
			}
		}
	};
	auto CheckZeroLogits = [&](const FRun& R)
	{
		for (size_t i = 0; i < R.Decisions.size(); ++i)
		{
			const EcoWorldV3::FHerbDecision& Dc = R.Decisions[i];
			if (!Dc.bPrepared || !Dc.Prep.bReads)
			{
				continue;
			}
			++DecisionsC;
			float In[O3::kObsDimObstacle];
			std::memcpy(In, R.Perceptions[i].Obs, sizeof(R.Perceptions[i].Obs));
			std::memcpy(In + O3::kObsDim, R.Perceptions[i].ObstacleObs, sizeof(R.Perceptions[i].ObstacleObs));
			float L[P3::kNumBehaviors];
			const int32 Got = P3::RunPolicyV3(*R.Net, In, Dc.Mask, L);
			LogitBadC += (Got != Dc.Request || std::memcmp(L, Dc.Logits, sizeof(L)) != 0) ? 1 : 0;
		}
	};
	CheckRun(A, false);
	CheckRun(B, true);
	CheckZeroLogits(Cz);
	for (int32 s = 0; s < kSteps; ++s)
	{
		A.StepOnce();
		B.StepOnce();
		Cz.StepOnce();
		D.StepOnce();
		E.StepOnce();
		DiffB += SameStep(A, B, true, true) ? 0 : 1;
		DiffC += SameStep(A, Cz, true, true) ? 0 : 1;
		DiffE += SameStep(A, E, true, true) ? 0 : 1;
		DiffDFrames += SameStep(A, D, false, false) ? 0 : 1;
		CheckRun(A, false);
		CheckRun(B, true);
		CheckZeroLogits(Cz);
	}
	AddInfo(FString::Printf(TEXT("관측 21 세계 산 사슴·스텝 %lld: 위협을 앎 %lld, 줄기 가림 %lld, 10 m 안 원판 %lld, 도망칠 쪽 거리 0 %lld · 새 열 0 망 결정 %lld · 값 있는 망이 다른 스텝 %d/%d · 어긋남 셈 A %lld B %lld C %lld D %lld E %lld"),
							Rows, SeenRows, Hidden, NearTrunk, EscapeZero, DecisionsC, DiffDFrames, kSteps, A.W.Stats.ObsLayoutMismatch, B.W.Stats.ObsLayoutMismatch,
							Cz.W.Stats.ObsLayoutMismatch, D.W.Stats.ObsLayoutMismatch, E.W.Stats.ObsLayoutMismatch));
	TestEqual(TEXT("관측 18 세계는 세 칸을 만들지 않는다 (0·기본값 — 조각 바이트 그대로)"), ZeroSlotsA, static_cast<int64>(0));
	TestEqual(TEXT("관측 21 세계 + 내장 망 = 관측 18 세계 (궤적·요청·로짓·관측 18 비트 단위)"), DiffB, 0);
	TestEqual(TEXT("세 칸 = 그 스텝 기하로 다시 잰 ObstacleObsValues, [0, 1] 안"), SlotBad, static_cast<int64>(0));
	TestEqual(TEXT("새 열 0 인 관측 21 망 = 내장 (요청·로짓 비트 단위)"), DiffC, 0);
	TestTrue(TEXT("새 열 0 망의 결정이 있다"), DecisionsC > 100);
	TestEqual(TEXT("새 열 0 망 결정의 로짓 = 관측 18 + 세 칸 입력으로 다시 돌린 값"), LogitBadC, static_cast<int64>(0));
	TestTrue(TEXT("새 열에 값이 있으면 결정이 달라진다 (세 칸이 망에 닿는다)"), DiffDFrames > 0);
	TestTrue(TEXT("관측 21 세계에서 세 칸이 움직인다 (가림·가까운 원판·벽 끝)"), Hidden > 0 && NearTrunk > 0 && EscapeZero > 0 && NearTrunk < Rows);
	TestEqual(TEXT("관측 21 세계·관측 18 망·관측 18 세계는 어긋남 0"),
			  A.W.Stats.ObsLayoutMismatch + B.W.Stats.ObsLayoutMismatch + Cz.W.Stats.ObsLayoutMismatch + D.W.Stats.ObsLayoutMismatch, static_cast<int64>(0));
	TestTrue(TEXT("관측 18 세계에 관측 21 망이면 어긋남을 센다"), E.W.Stats.ObsLayoutMismatch > 0);
	TestEqual(TEXT("관측 18 세계에 새 열 0 망은 그래도 결정이 같다 (세 칸이 0)"), DiffE, 0);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
