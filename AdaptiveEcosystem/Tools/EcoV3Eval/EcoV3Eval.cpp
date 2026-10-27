// EcoV3Eval — 엔진 없는 네이티브 두뇌 평가기 (10-21 사용자 '언리얼에서 도는 두뇌를 굳이 파이썬으로 다시 시험하지 말고 언리얼 자체에서 평가',
// 게임 세계 하나는 자료가 너무 적다 — 같은 세계 규칙을 여러 세계로 최고 속도로 돌린다. 학습은 그대로 파이썬).
//
// 무엇을 하나:
//   게임이 쓰는 엔진 무관 v3 세계 코드(AI/Policy/EcoWorldV3.h — Mass 통합 처리기와 같은 Step·DecideHerb·ObserveAll)를 그대로 include 해
//   지역 무대 하나 = 세계 하나를 통합 모드처럼(부활 없음 — 죽은 사슴은 다음 Step 부터 뺀다, 산 사슴만 넘긴다) 돌리고, 파이썬 판정 기록
//   (results/v3/r4/r4_eval.py `_one`·results/v3/live/live.py `_world_multi`)과 같은 칸·같은 뜻의 세계 기록을 JSON 한 줄로 낸다.
//   언리얼에만 있는 이동 제약(FStepHooks — 팀 지형 TraceMove)은 넣지 않는다 — 파이썬 거울 세계와 같은 세계 안 이동만 쓴다.
//
// 일 파일 (herbivore_rl/results/v3/live/ceval.py 가 쓴다 — 형식 eco_v3_eval_jobs 판 1):
//   brain  두뇌 파일 경로 (export_weights_v3.py --brain-file, 형식 eco_v3_brain 판 1 — 계약 해시·차원·마스크 문턱·sha256·골든 자체 확인)
//   jobs[] 세계마다: world (스냅숏 지역 world 블록과 같은 이름·뜻 — EcoV3Snapshot.cpp WorldConfigJson), covers·discs (x, y, r),
//          foliage_trees (선택 — 숲 시야 나무 표, 원판마다 0/1. world.obstacle_rules 의 foliage·foliage_r·foliage_block 과 함께, 10-21),
//          food (gw·cell·cap·food·regen, 행 우선 k = iy·gw + ix), deer (슬롯 순서 x·y·hx·hy·energy·reserve·repro_cd·slot),
//          wolves (kind stalker|chaser·x·y·hx·hy·slot·speed), rng (pcg64 = 파이썬 numpy 상태 이어 받기, native = 게임 SplitMix64),
//          steps·horizons·trace·id·seed·region
//   시작 상태는 파이썬 거울 세계가 reset 뒤 만든 값 그대로다(시작 자리·방향·먹이 지도·재생률 — ceval.py). 행동 상태는 AdoptHerb(InitAgent,
//   개체 키 = 슬롯·2^32 + 세대 0, Seed = 파이썬 세계 시드 — 파리티 키)로, 늑대 밤잠은 AdoptThreat(NightSlot = 위협 슬롯)로 만든다.
//   pcg64 난수는 EcoWorldV3::FRng::External 로 바꿔 끼운다(거울 세계의 스텝 안 뽑기 = 위협 슬롯 순서의 배회 선회뿐 — 파이썬 v1 스트림과 같은 수열).
//   감지 기록(bSenseStats)은 끈다 — 평가 기록에 없고 궤적과 무관하다(통합 모드는 켠다). 나머지 설정은 통합 모드 MakeRegionWorldConfig 와 같은 칸.
//   검증 (10-21, ceval.py compare): 파이썬의 동족 무리 중심·분리 행렬곱만 같은 차례 합으로 바꾸면 1800 스텝 궤적·기록이 비트 단위로 같다.
//
// 쓰는 법:
//   EcoV3Eval.exe --jobs <일.json> --out <기록.jsonl> [--quiet]
//   EcoV3Eval.exe --brain-check <두뇌.json>          두뇌 파일 검사만
//   EcoV3Eval.exe --pcg-selftest <state> <inc> <n>  numpy PCG64 이어 받기 n 개 (ceval.py selftest 가 numpy 와 견준다)
//   빌드: Tools/EcoV3Eval/build.ps1 (VS 2022 cl /O2 /std:c++20, AI/Policy 헤더만) → Tools/EcoV3Eval/bin/EcoV3Eval.exe
//
// 기록 한 줄 = {"id", "record": {seed, region, n, caught, starved, alive, shelter_steps, live_steps, beh_steps, catch_cover, catch_fled, catches,
//   starve_fled, hunt{...}, weather{...}, obstacles_n, flight{...}, at{h: {caught, starved, alive, flight}}, wall_s, steps_per_s},
//   "init"·"trace" (trace > 0 일 때만 — 파리티 진단)}. 실패한 세계는 {"id", "error"} 한 줄이고 종료 코드 1.
//   flight 는 파이썬 world.py flight_stats 와 같은 칸이다 — 10-23 부터 숨은 뒤 10 초 지켜보기 hide{chased, hidden, watching, cover_then_caught,
//   cover_then_starved, watch_steps}(옛 1차 숨음 비율 — 보고만)도, 10-24 부터 쫓김 사건 episode{started, chased, hidden, caught, starved, other,
//   truncated, watching, other_chased, joined, joined_cover, joined_other, window_caught, window_starved, link_cover_steps, link_other_steps}(실시간 관문
//   1차 사건 숨음 비율·지킴 GH·GE 의 재료)도 낸다.
//   10-24 두 길 두뇌 (이식 계획서 Docs/RL_Policy/RL_V3_ROUTE_CPP_PORT_PLAN.md 7절): 두뇌 파일 관측 24·마스크 판 4(계약 0xe302dee198197444)·판 5(0xad7bad5e1acaf071 —
//   반사 밖 두뇌 FLEE 막음)를 받는다. 일의 world.wild_flight.route·brain_flee_outside_reflex 가 두뇌 판과 같아야 하고(아니면 그 일은 오류), 두뇌 판이
//   SetModelRoute·SetModelFleeGate 로 세계를 켠다. 길 켬 세계면 flight 에 route{route_stats 칸·by_route·drop_obstacle·chased_steps·hidden_steps·refled}
//   (파이썬 flight_stats 의 route 와 같은 칸)를, trace 에 관측 24·길 칸(route·route_k·route_age·route_feas·route_decide·route_req·route_gap)을 더한다.
//   trace 의 gap = 망을 돌린 사슴의 로짓 1·2 위 차 (근접 동점 갈림 진단). 기록의 min_gap·near_ties·min_route_gap = 판 전체의 그 최솟값·1e-4 밑 수.
//   일의 선택 칸 trace_digest (스텝 수) 면 전체 궤적 대신 스텝마다 칸 아홉의 지문을 traj 로 낸다 (TrajDigest — herbivore_rl/results/v3/route/port/
//   make_traces.py digest_state 와 같은 바이트, port/native_check.py 가 traj/ 와 견준다).
//   10-27 (사용자 '평소 사슴이 제자리에서 빙빙 돈다'·'쉬는 늑대 곁에서 멈춰 있다'): world 블록의 선택 칸 wild_flight.rest_keep·rest_keep_margin·rest_keep_band·
//   rest_keep_asleep(거리 두기 — 덮기 4 = kKeepRest, trace keep 칸에도 4 가 나온다)과 선택 블록 graze_calm{graze_edge_r, graze_edge_w, graze_inertia,
//   graze_wall_margin}(먹기 걷기 고침 — FWorldConfig::GrazeCalm)을 읽는다. 없으면 끔 = 옛 일 그대로.

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <initializer_list>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "EcoSha256.h"
#include "EcoWorldV3.h"

#include "MiniJson.h"
#include "Pcg64.h"

namespace EcoV3Eval
{
	namespace R3 = EcoRepertoireV3;
	namespace P3 = EcoPolicyV3;
	namespace O3 = EcoObservationV3;
	namespace T3 = EcoThreatV3;
	namespace W3 = EcoWorldV3;
	using MiniJson::FValue;

	inline constexpr std::int32_t kFledSteps = 38;   // 진단 '마지막 5초' (run_mirror.py FLED_STEPS)

	std::string ReadFile(const std::string& Path)
	{
		std::ifstream F(Path, std::ios::binary);
		if (!F)
		{
			throw std::runtime_error("파일을 열지 못했다: " + Path);
		}
		std::ostringstream S;
		S << F.rdbuf();
		return S.str();
	}

	// ---- JSON 쓰기 ----

	struct FOut
	{
		std::string S;
		std::vector<bool> First;

		void Sep()
		{
			if (!First.empty())
			{
				if (!First.back())
				{
					S += ',';
				}
				First.back() = false;
			}
		}
		void Key(const char* K)
		{
			Sep();
			S += '"';
			S += K;
			S += "\":";
			if (!First.empty())
			{
				First.back() = true;   // 값이 Sep 을 다시 부르지 않게
			}
		}
		void Raw(const std::string& V)
		{
			Sep();
			S += V;
		}
		void Num(double V)
		{
			Sep();
			if (!std::isfinite(V))
			{
				S += "null";
				return;
			}
			char B[40];
			std::snprintf(B, sizeof(B), "%.17g", V);
			S += B;
		}
		void Int(std::int64_t V)
		{
			Sep();
			S += std::to_string(V);
		}
		void Bool(bool V)
		{
			Sep();
			S += V ? "true" : "false";
		}
		void Str(const std::string& V)
		{
			Sep();
			S += '"';
			for (const char C : V)
			{
				if (C == '"' || C == '\\')
				{
					S += '\\';
					S += C;
				}
				else if (static_cast<unsigned char>(C) < 0x20)
				{
					char B[8];
					std::snprintf(B, sizeof(B), "\\u%04x", static_cast<unsigned>(static_cast<unsigned char>(C)));
					S += B;
				}
				else
				{
					S += C;
				}
			}
			S += '"';
		}
		void BeginObj()
		{
			Sep();
			S += '{';
			First.push_back(true);
		}
		void EndObj()
		{
			S += '}';
			First.pop_back();
		}
		void BeginArr()
		{
			Sep();
			S += '[';
			First.push_back(true);
		}
		void EndArr()
		{
			S += ']';
			First.pop_back();
		}
		void KNum(const char* K, double V)
		{
			Key(K);
			Num(V);
		}
		void KInt(const char* K, std::int64_t V)
		{
			Key(K);
			Int(V);
		}
		void KBool(const char* K, bool V)
		{
			Key(K);
			Bool(V);
		}
		void KStr(const char* K, const std::string& V)
		{
			Key(K);
			Str(V);
		}
		template <typename TV>
		void KIntArr(const char* K, const TV* V, std::int32_t N)
		{
			Key(K);
			BeginArr();
			for (std::int32_t i = 0; i < N; ++i)
			{
				Int(static_cast<std::int64_t>(V[i]));
			}
			EndArr();
		}
	};

	// ---- 두뇌 파일 (EcoV3Brain.cpp 와 같은 검사 — 언리얼 JSON 대신 MiniJson) ----

	struct FBrain
	{
		std::string Id;
		std::string WeightsSha256;
		std::int32_t ObsDim = 0;
		std::int32_t MaskVersion = 2;        // 마스크 판 (2 = 관측 18·21, 4 = 두 길 두뇌 관측 24, 5 = 판 4 + 반사 밖 두뇌 FLEE 막음 — 10-24 이식)
		std::uint8_t Allowed[R3::kNumBehaviors] = {};
		std::vector<float> Wt0, Bs0, Wt1, Bs1, Wt2, Bs2;
		P3::FPolicyNetV3 Net{};
		std::int32_t GoldenCases = 0;
		double GoldenMaxErr = 0.0;

		bool Route() const { return P3::IsRouteMaskVersion(MaskVersion); }            // 두 길 두뇌 (SetModelRoute)
		bool FleeGate() const { return MaskVersion == P3::kMaskVersionRouteGate; }    // 판 5 (SetModelFleeGate)
	};

	/** 두뇌 파일의 관측 이름이 계약 차례(관측 18 · 장애물 세 칸 · 길 세 칸)와 같은가. */
	bool ObsNamesOk(const FValue& R, std::int32_t Dim)
	{
		const FValue* Nv = R.Find("obs_names");
		if (Nv == nullptr || !Nv->IsArray() || Nv->Arr().size() != static_cast<size_t>(Dim))
		{
			return false;
		}
		for (std::int32_t i = 0; i < Dim; ++i)
		{
			const char* Want = i < O3::kObsDim ? O3::kObsNames[i]
							   : i < O3::kObsDimObstacle ? O3::kObstacleObsNames[i - O3::kObsDim]
														 : O3::kRouteObsNames[i - O3::kObsDimObstacle];
			if (Nv->Arr()[static_cast<size_t>(i)].Str() != Want)
			{
				return false;
			}
		}
		return true;
	}

	/**
	 * 두 길 두뇌 파일의 계약 dict flight_route 가 이 빌드의 상수와 같은가 (이식 계획서 5-2 의 5 — 해시가 이미 덮지만 어긋난 칸을 거부 글에 적는다).
	 * 다르면 그 칸 이름을 돌려준다 (같으면 빈 글).
	 */
	std::string RouteContractDiff(const FValue& R, std::int32_t MaskVersion)
	{
		const FValue* Ct = R.Find("contract");
		const FValue* Fr = Ct != nullptr ? Ct->Find("flight_route") : nullptr;
		if (Fr == nullptr || !Fr->IsObject())
		{
			return "contract.flight_route 없음";
		}
		const FValue& Sl = Fr->At("slots");
		if (static_cast<int>(Sl.At("run").Num()) != W3::kRouteSlotRun || static_cast<int>(Sl.At("shelter").Num()) != W3::kRouteSlotShelter
			|| Sl.At("reserved_masked").Arr().size() != 1 || static_cast<int>(Sl.At("reserved_masked").Arr()[0].Num()) != W3::kRouteSlotReserved)
		{
			return "flight_route.slots";
		}
		const std::vector<FValue>& Ob = Fr->At("obs").Arr();
		for (std::int32_t j = 0; j < O3::kNumRouteObs; ++j)
		{
			if (Ob.size() != static_cast<size_t>(O3::kNumRouteObs) || Ob[static_cast<size_t>(j)].Str() != O3::kRouteObsNames[j])
			{
				return "flight_route.obs";
			}
		}
		// 글자 배열이 Want 와 같은 차례·같은 길이인가
		auto StringList = [](const FValue& A, std::initializer_list<const char*> Want)
		{
			const std::vector<FValue>& V = A.Arr();
			if (V.size() != Want.size())
			{
				return false;
			}
			size_t j = 0;
			for (const char* W : Want)
			{
				if (V[j++].Str() != W)
				{
					return false;
				}
			}
			return true;
		};
		// 결정 조건 on = 시작·무효·잠금 뒤 가능 바뀜 (world.py `_route_step` — EcoWorldV3 Detail::RouteStep 의 onset·invalid·refeas. UE 로더와 같은 칸)
		const FValue& De = Fr->At("decide");
		if (static_cast<int>(De.At("lock_steps").Num()) != W3::kRouteLockSteps
			|| !StringList(De.At("on"), {"onset", "invalid", "lock_and_feasible_changed"}) || !StringList(De.At("feasible"), {"shelter"})
			|| !StringList(De.At("refeas_from"), {"run"}))
		{
			return "flight_route.decide";
		}
		const FValue& Sh = Fr->At("shelter");
		if (Sh.At("max_edge_u").Num() != W3::kRouteShelterMaxEdgeU || Sh.At("cos_min").Num() != W3::kRouteShelterCosMin
			|| Sh.At("enter_margin_u").Num() != W3::kRouteShelterEnterU || Sh.At("exit_margin_u").Num() != W3::kRouteShelterExitU
			|| Sh.At("reach_norm_u").Num() != W3::kRouteShelterReachU || Sh.At("edge_norm_u").Num() != W3::kRouteShelterEdgeNormU)
		{
			return "flight_route.shelter";
		}
		if (Fr->StrOr("freeze_sleep_must_be_blocked", "") != "effective_allowed")
		{
			return "flight_route.freeze_sleep_must_be_blocked";
		}
		const FValue* Gate = Ct->Find("brain_flee_outside_reflex");
		if (MaskVersion == P3::kMaskVersionRouteGate && (Gate == nullptr || Gate->IsNull() || Gate->Bool()))
		{
			return "brain_flee_outside_reflex (판 5 는 false)";
		}
		if (MaskVersion == P3::kMaskVersionRoute && Gate != nullptr && !Gate->IsNull())
		{
			return "brain_flee_outside_reflex (판 4 에는 없다)";
		}
		return "";
	}

	std::vector<std::uint8_t> Base64Decode(const std::string& In)
	{
		auto Val = [](char C) -> int
		{
			if (C >= 'A' && C <= 'Z')
			{
				return C - 'A';
			}
			if (C >= 'a' && C <= 'z')
			{
				return C - 'a' + 26;
			}
			if (C >= '0' && C <= '9')
			{
				return C - '0' + 52;
			}
			if (C == '+')
			{
				return 62;
			}
			if (C == '/')
			{
				return 63;
			}
			return -1;
		};
		std::vector<std::uint8_t> Out;
		std::uint32_t Acc = 0;
		int Bits = 0;
		for (const char C : In)
		{
			if (C == '=')
			{
				break;
			}
			const int V = Val(C);
			if (V < 0)
			{
				throw std::runtime_error("base64 글자가 아니다");
			}
			Acc = (Acc << 6) | static_cast<std::uint32_t>(V);
			Bits += 6;
			if (Bits >= 8)
			{
				Bits -= 8;
				Out.push_back(static_cast<std::uint8_t>((Acc >> Bits) & 0xFFu));
			}
		}
		return Out;
	}

	std::vector<float> DecodeFloats(const std::string& B64, size_t Want, const char* What)
	{
		const std::vector<std::uint8_t> Bytes = Base64Decode(B64);
		if (Bytes.size() != Want * sizeof(float))
		{
			throw std::runtime_error(std::string("두뇌 층 ") + What + " 바이트 수가 모양과 다르다");
		}
		std::vector<float> Out(Want);
		std::memcpy(Out.data(), Bytes.data(), Bytes.size());   // float32 리틀 엔디언 (x64)
		for (const float V : Out)
		{
			if (!std::isfinite(V))
			{
				throw std::runtime_error(std::string("두뇌 층 ") + What + " 에 NaN·Inf 가 있다");
			}
		}
		return Out;
	}

	std::string Sha256Hex(const P3::FPolicyNetV3& Net)
	{
		EcoSha256::FState S;
		EcoSha256::Update(S, Net.W0, sizeof(float) * P3::kHiddenDim * Net.ObsDim);
		EcoSha256::Update(S, Net.B0, sizeof(float) * P3::kHiddenDim);
		EcoSha256::Update(S, Net.W1, sizeof(float) * P3::kHiddenDim * P3::kHiddenDim);
		EcoSha256::Update(S, Net.B1, sizeof(float) * P3::kHiddenDim);
		EcoSha256::Update(S, Net.W2, sizeof(float) * P3::kNumBehaviors * P3::kHiddenDim);
		EcoSha256::Update(S, Net.B2, sizeof(float) * P3::kNumBehaviors);
		std::uint8_t Digest[EcoSha256::kDigestBytes];
		EcoSha256::Final(S, Digest);
		char Hex[2 * EcoSha256::kDigestBytes + 1];
		EcoSha256::ToHex(Digest, Hex);
		return std::string(Hex);
	}

	std::string Lower(std::string S)
	{
		for (char& C : S)
		{
			C = (C >= 'A' && C <= 'Z') ? static_cast<char>(C - 'A' + 'a') : C;
		}
		return S;
	}

	void LoadBrain(const std::string& Path, FBrain& B)
	{
		const FValue R = MiniJson::Parse(ReadFile(Path));
		if (R.StrOr("format", "") != "eco_v3_brain" || static_cast<int>(R.NumOr("format_version", -1)) != 1)
		{
			throw std::runtime_error("두뇌 형식이 eco_v3_brain 판 1 이 아니다: " + Path);
		}
		const std::string Hash = Lower(R.At("contract_hash").Str());
		// 받는 계약 (해시 · 관측 칸 수 · 마스크 판): 관측 18·21 판 2, 10-24 두 길 두뇌 관측 24 판 4·5 (이식 계획서 5-1·13-2)
		struct FContractRow
		{
			std::uint64_t Hash;
			std::int32_t Dim;
			std::int32_t Mask;
		};
		static constexpr FContractRow kContracts[4] = {{P3::kContractHashObs18Mask2, O3::kObsDim, 2},
													   {P3::kContractHashObs21Mask2, O3::kObsDimObstacle, 2},
													   {P3::kContractHashObs24Mask4, O3::kObsDimRoute, P3::kMaskVersionRoute},
													   {P3::kContractHashObs24Mask5, O3::kObsDimRoute, P3::kMaskVersionRouteGate}};
		const std::int32_t Dim = static_cast<std::int32_t>(R.At("obs_dim").Num());
		const FContractRow* Row = nullptr;
		for (const FContractRow& C : kContracts)
		{
			char Want[32];
			std::snprintf(Want, sizeof(Want), "0x%016llx", static_cast<unsigned long long>(C.Hash));
			if (Hash == Want)
			{
				Row = &C;
			}
		}
		if (Row == nullptr || Row->Dim != Dim)
		{
			throw std::runtime_error("두뇌 계약 해시 " + Hash + " · 관측 " + std::to_string(Dim) +
									 " 을 이 세계가 만들 수 없다 (관측 18·21 판 2, 관측 24 판 4·5 만)");
		}
		if (static_cast<int>(R.At("hidden").Num()) != P3::kHiddenDim || static_cast<int>(R.At("num_behaviors").Num()) != P3::kNumBehaviors
			|| static_cast<int>(R.At("mask_version").Num()) != Row->Mask)
		{
			throw std::runtime_error("두뇌 차원·마스크 판이 계약과 다르다");
		}
		if (!ObsNamesOk(R, Dim))
		{
			throw std::runtime_error("두뇌 관측 이름이 계약 차례와 다르다 (관측 18 · escape_room·obstacle_near·threat_hidden · in_panic·shelter_reach·shelter_edge)");
		}
		B.MaskVersion = Row->Mask;
		if (B.Route())
		{
			const std::string Why = RouteContractDiff(R, B.MaskVersion);
			if (!Why.empty())
			{
				throw std::runtime_error("두 길 두뇌 계약 칸이 이 빌드와 다르다: " + Why);
			}
		}
		const FValue& Th = R.At("thresholds");
		if (static_cast<float>(Th.At("threat_recency_obs").Num()) != P3::kThreatRecencyObs
			|| static_cast<float>(Th.At("hide_cover_obs").Num()) != P3::kHideCoverObs)
		{
			throw std::runtime_error("두뇌 마스크 문턱이 이 빌드와 다르다");
		}
		const std::vector<FValue>& Am = R.At("allowed_mask").Arr();
		if (Am.size() != static_cast<size_t>(R3::kNumBehaviors) || Am[R3::kGraze].Num() == 0.0)
		{
			throw std::runtime_error("두뇌 허용 칸이 5 칸이 아니거나 먹기가 없다");
		}
		for (std::int32_t b = 0; b < R3::kNumBehaviors; ++b)
		{
			B.Allowed[b] = Am[static_cast<size_t>(b)].Num() != 0.0 ? 1 : 0;
		}
		if (B.Route() && (B.Allowed[R3::kFreeze] != 0 || B.Allowed[R3::kSleep] != 0))
		{
			// 판 4·5 는 칸 3·4 를 도주 중 길 칸으로 다시 쓴다 — 모델 허용에 얼기·잠이 있으면 거부 (이식 계획서 5-2 의 4, 걸 때 실제 허용도 Init 이 본다)
			throw std::runtime_error("두 길 두뇌(마스크 판 4·5)의 허용에 얼기·잠이 있다");
		}
		const std::vector<FValue>& L = R.At("layers").Arr();
		if (L.size() != 3)
		{
			throw std::runtime_error("두뇌 층이 셋이 아니다");
		}
		const std::int32_t Ins[3] = {Dim, P3::kHiddenDim, P3::kHiddenDim};
		const std::int32_t Outs[3] = {P3::kHiddenDim, P3::kHiddenDim, P3::kNumBehaviors};
		std::vector<float>* Ws[3] = {&B.Wt0, &B.Wt1, &B.Wt2};
		std::vector<float>* Bs[3] = {&B.Bs0, &B.Bs1, &B.Bs2};
		for (int k = 0; k < 3; ++k)
		{
			const FValue& Lk = L[static_cast<size_t>(k)];
			if (static_cast<int>(Lk.At("in").Num()) != Ins[k] || static_cast<int>(Lk.At("out").Num()) != Outs[k])
			{
				throw std::runtime_error("두뇌 층 모양이 계약과 다르다");
			}
			*Ws[k] = DecodeFloats(Lk.At("w_f32le_b64").Str(), static_cast<size_t>(Ins[k]) * Outs[k], "weight");
			*Bs[k] = DecodeFloats(Lk.At("b_f32le_b64").Str(), static_cast<size_t>(Outs[k]), "bias");
		}
		B.ObsDim = Dim;
		B.Net = P3::FPolicyNetV3{Dim, B.Wt0.data(), B.Bs0.data(), B.Wt1.data(), B.Bs1.data(), B.Wt2.data(), B.Bs2.data()};
		B.WeightsSha256 = Sha256Hex(B.Net);
		if (B.WeightsSha256 != Lower(R.At("weights_sha256").Str()))
		{
			throw std::runtime_error("두뇌 가중치 sha256 " + B.WeightsSha256.substr(0, 16) + " 이 파일에 적힌 값과 다르다");
		}
		B.Id = R.StrOr("id", "?");
		// 골든 자체 확인 (EcoV3Brain 과 같은 규칙: 로짓 |C++ − 파이썬| ≤ min(파일 허용 오차, 1e-3), 행동 같음, 8 사례 이상)
		const FValue& G = R.At("golden");
		const double Tol = std::min(G.NumOr("logit_tolerance", 1e-4), 1e-3);
		const std::vector<FValue>& Cases = G.At("cases").Arr();
		if (Cases.size() < 8)
		{
			throw std::runtime_error("두뇌 골든 사례가 8 개보다 적다");
		}
		for (const FValue& C : Cases)
		{
			float Obs[P3::kMaxObsDim] = {};
			const std::vector<FValue>& Ov = C.At("obs").Arr();
			if (Ov.size() < static_cast<size_t>(Dim))
			{
				throw std::runtime_error("두뇌 골든 관측 칸이 모자란다");
			}
			for (std::int32_t i = 0; i < Dim; ++i)
			{
				Obs[i] = static_cast<float>(Ov[static_cast<size_t>(i)].Num());
			}
			std::uint8_t Mask[R3::kNumBehaviors] = {};
			const std::vector<FValue>& Mv = C.At("mask").Arr();
			for (std::int32_t b = 0; b < R3::kNumBehaviors; ++b)
			{
				Mask[b] = Mv[static_cast<size_t>(b)].Num() != 0.0 ? 1 : 0;
			}
			float Lg[R3::kNumBehaviors] = {};
			const std::int32_t Act = P3::RunPolicyV3(B.Net, Obs, Mask, Lg);
			const std::vector<FValue>& Lv = C.At("logits").Arr();
			for (std::int32_t b = 0; b < R3::kNumBehaviors; ++b)
			{
				const double E = std::fabs(static_cast<double>(Lg[b]) - Lv[static_cast<size_t>(b)].Num());
				B.GoldenMaxErr = E > B.GoldenMaxErr ? E : B.GoldenMaxErr;
			}
			if (Act != static_cast<std::int32_t>(C.At("action").Num()))
			{
				throw std::runtime_error("두뇌 골든 행동이 다르다");
			}
			++B.GoldenCases;
		}
		if (B.GoldenMaxErr > Tol)
		{
			throw std::runtime_error("두뇌 골든 로짓 오차가 허용보다 크다");
		}
	}

	// ---- 세계 설정 (스냅숏 지역 world 블록 → FWorldConfig, EcoV3Snapshot.cpp WorldConfigJson 의 거꾸로) ----

	std::int32_t WeatherKindOf(const std::string& Name)
	{
		if (Name == "clear")
		{
			return W3::kWeatherClear;
		}
		if (Name == "rain")
		{
			return W3::kWeatherRain;
		}
		if (Name == "snow")
		{
			return W3::kWeatherSnow;
		}
		throw std::runtime_error("모르는 날씨: " + Name);
	}

	std::vector<O3::FCoverInput> CoversOf(const FValue& V)
	{
		std::vector<O3::FCoverInput> Out;
		for (const FValue& C : V.Arr())
		{
			const std::vector<FValue>& A = C.Arr();
			Out.push_back({A.at(0).Num(), A.at(1).Num(), A.at(2).Num()});
		}
		return Out;
	}

	W3::FWorldConfig ConfigOf(const FValue& Wb, const FValue& Job)
	{
		W3::FWorldConfig C;
		C.WorldSize = Wb.At("world_size").Num();
		C.Seed = static_cast<std::int64_t>(Wb.At("seed").Num());
		C.RngStream = static_cast<std::uint64_t>(Wb.NumOr("rng_stream", 0.0));
		C.NumHerbivores = static_cast<std::int32_t>(Wb.At("num_herbivores").Num());
		C.NumStalkers = static_cast<std::int32_t>(Wb.At("num_stalkers").Num());
		C.NumChasers = static_cast<std::int32_t>(Wb.At("num_chasers").Num());
		C.NumRanged = static_cast<std::int32_t>(Wb.At("num_ranged").Num());
		C.NumNocturnal = static_cast<std::int32_t>(Wb.At("num_nocturnal").Num());
		C.bPlayerProxy = Wb.At("player_proxy").Bool();
		if (C.NumRanged != 0 || C.NumNocturnal != 0 || C.bPlayerProxy)
		{
			throw std::runtime_error("원거리형·야행성·플레이어 대역은 평가기가 받지 않는다 (통합 무대에 없다)");
		}
		C.PredSpeedMult = Wb.At("pred_speed_mult").Num();
		C.PredEatCdOverride = static_cast<std::int32_t>(Wb.At("pred_eat_cd").Num());   // 스냅숏 값 = 실제 쿨다운 (학습 5 와 같아도 덮어 같다)
		C.bEatInPlace = Wb.At("eat_in_place").Bool();
		C.bRealismNight = Wb.At("realism_night").Bool();
		C.bRespawnDead = Wb.At("respawn_dead").Bool();
		if (C.bRespawnDead)
		{
			throw std::runtime_error("평가기는 부활 없는 세계(통합 무대)만 돈다");
		}
		C.PredEmaDenominator = static_cast<std::int32_t>(Wb.At("pred_ema_denominator").Num());
		C.DayPeriod = static_cast<std::int32_t>(Wb.At("day_period").Num());
		C.DayOffset = static_cast<std::int32_t>(Wb.At("day_offset").Num());
		C.TwilightSteps = static_cast<std::int32_t>(Wb.At("twilight_steps").Num());
		C.bShelterSafe = Wb.At("shelter_safe").Bool();
		C.ShelterWolfMargin = Wb.At("shelter_wolf_margin").Num();
		C.bProtectedRefuges = Wb.At("protected_refuges").Bool();
		const std::vector<FValue>& Wa = Wb.At("world_allowed").Arr();
		for (std::int32_t b = 0; b < R3::kNumBehaviors; ++b)
		{
			C.WorldAllowed[b] = Wa.at(static_cast<size_t>(b)).Num() != 0.0 ? 1 : 0;
		}
		{
			const FValue& F = Wb.At("food_rules");
			C.FoodCell = F.At("cell").Num();
			C.FoodPatchBlur = static_cast<std::int32_t>(F.At("patch_blur").Num());
			C.FoodPatchThreshold = F.At("patch_threshold").Num();
			C.FoodGradBlur = static_cast<std::int32_t>(F.At("grad_blur").Num());
			C.FoodRegenBase = F.At("regen_base").Num();
			C.FoodRegenMult = F.At("regen_mult").Num();
			C.FoodCoverRegenMult = F.At("cover_regen_mult").Num();
		}
		{
			const FValue& F = Wb.At("wild_flight");
			W3::FWildFlightConfig& K = C.WildFlight;
			K.bEnabled = F.At("enabled").Bool();
			K.AlertR = F.At("alert_r").Num();
			K.FlightR = F.At("flight_r").Num();
			K.SafeR = F.At("safe_r").Num();
			K.Approach = F.At("approach").Num();
			K.AlertW = F.At("alert_w").Num();
			K.bRestAlert = F.At("rest_alert").Bool();
			K.ShelterCos = F.At("shelter_cos").Num();
			K.ShelterR = F.At("shelter_r").Num();
			K.bCrouch = F.At("crouch").Bool();
			K.WallMargin = F.At("wall_margin").Num();
			K.bHoldAwake = F.At("hold_awake").Bool();
			K.EdgeR = F.At("edge_r").Num();
			// 10-24 두 길 두뇌 (선택 칸 — 옛 일은 없다): 세계 키 route. 실제로 켜는 것은 두뇌 판(SetModelRoute — Init 이 어긋나면 거부한다)
			K.bRoute = F.BoolOr("route", false);
			// 10-27 거리 두기(쉬는 늑대) (선택 칸 — 옛 일은 없다 = 끔. 파이썬 wild_flight.rest_keep* 와 같은 이름)
			K.bRestKeep = F.BoolOr("rest_keep", false);
			K.RestKeepMargin = F.NumOr("rest_keep_margin", K.RestKeepMargin);
			K.RestKeepBand = F.NumOr("rest_keep_band", K.RestKeepBand);
			K.bRestKeepAsleep = F.BoolOr("rest_keep_asleep", false);
		}
		if (const FValue* G = Wb.Find("graze_calm"))
		{
			// 10-27 먹기 걷기 고침 (선택 블록 — 옛 일은 없다 = 끔. 파이썬 repertoire.graze_* 와 같은 이름, adapt.FEATURE_MAPS 'graze_calm')
			C.GrazeCalm.EdgeR = G->NumOr("graze_edge_r", 0.0);
			C.GrazeCalm.EdgeW = G->NumOr("graze_edge_w", 0.0);
			C.GrazeCalm.Inertia = G->NumOr("graze_inertia", 0.0);
			C.GrazeCalm.WallMargin = G->NumOr("graze_wall_margin", 0.0);
		}
		{
			const FValue& F = Wb.At("wild_reserve");
			W3::FWildReserveConfig& K = C.WildReserve;
			K.bEnabled = F.At("enabled").Bool();
			K.ReserveDays = F.At("reserve_days").Num();
			K.Init = F.At("init").Num();
			K.RefillE = F.At("refill_e").Num();
			K.RefillFrac = F.At("refill_frac").Num();
			K.WeakE = F.At("weak_e").Num();
			K.WeakSpeed = F.At("weak_speed").Num();
		}
		{
			const FValue& F = Wb.At("wild_satiation");
			C.WildSatiation.bEnabled = F.At("enabled").Bool();
			C.WildSatiation.SatDays = F.At("sat_days").Num();
			C.WildSatiation.RestSpeed = F.At("rest_speed").Num();
		}
		{
			const FValue& F = Wb.At("realism_vision");
			C.RealismVision.bEnabled = F.At("enabled").Bool();
			C.RealismVision.ThreatFovDeg = F.At("threat_fov_deg").Num();
		}
		{
			const FValue& F = Wb.At("realism_hearing");
			O3::FHearingConfig& H = C.RealismHearing;
			H.bEnabled = F.At("enabled").Bool();
			H.SSilent = F.At("s_silent").Num();
			H.SQuiet = F.At("s_quiet").Num();
			H.SLoud = F.At("s_loud").Num();
			H.RQuiet = F.At("r_quiet").Num();
			H.RLoud = F.At("r_loud").Num();
			H.bRoamQuiet = F.At("roam_quiet").Bool();
			H.bCapToSight = F.At("cap_to_sight").Bool();
		}
		{
			const FValue& F = Wb.At("shelter_food");
			C.ShelterFood.bEnabled = F.At("enabled").Bool();
			C.ShelterFood.CapFrac = F.At("cap_frac").Num();
			C.ShelterFood.RegenFrac = F.At("regen_frac").Num();
		}
		{
			const FValue& F = Wb.At("pack_hunt");
			T3::FPackHuntConfig& P = C.PackHunt;
			P.bEnabled = F.At("enabled").Bool();
			P.JoinR = F.At("join_r").Num();
			P.Lead = F.At("lead").Num();
			P.DoorR = F.At("door_r").Num();
			P.DoorCos = F.At("door_cos").Num();
			P.WaitR = F.At("wait_r").Num();
		}
		{
			const FValue& F = Wb.At("obstacle_rules");
			W3::FObstacleConfig& O = C.Obstacles;
			O.bEnabled = F.At("enabled").Bool();
			O.BodyR = F.At("body_r").Num();
			O.bBlockSight = F.At("block_sight").Bool();
			O.bNoFood = F.At("no_food").Bool();
			O.Detour.bEnabled = F.At("detour").Bool();
			O.Detour.BlockFrac = F.At("detour_block").Num();
			O.Detour.FreeFrac = F.At("detour_free").Num();
			O.Detour.Probe = F.At("detour_probe").Num();
			O.Detour.MaxSteps = static_cast<std::int32_t>(F.At("detour_steps").Num());
			O.Detour.HelpBlock = static_cast<std::int32_t>(F.At("detour_help_block").Num());
			O.Detour.HelpDrop = static_cast<std::int32_t>(F.At("detour_help_drop").Num());
			O.Discs.clear();
			for (const FValue& D : Job.At("discs").Arr())
			{
				const std::vector<FValue>& A = D.Arr();
				O.Discs.push_back(A.at(0).Num());
				O.Discs.push_back(A.at(1).Num());
				O.Discs.push_back(A.at(2).Num());
			}
			// 숲 시야 (10-21, 파이썬 obstacles.foliage — 선택 칸, 없으면 끔): foliage·foliage_r·foliage_block (스냅숏 obstacle_rules 와 같은 이름),
			// 나무 표 = 일의 foliage_trees (원판마다 0/1, discs 순서 — 파이썬 _fol_centers 의 표. 비면 모두 나무)
			O.Foliage.bEnabled = O.bEnabled && F.BoolOr("foliage", false);
			O.Foliage.R = F.NumOr("foliage_r", O.Foliage.R);
			O.Foliage.Block = F.NumOr("foliage_block", O.Foliage.Block);
			O.Foliage.Trees.clear();
			if (const FValue* Ft = Job.Find("foliage_trees"); O.Foliage.bEnabled && Ft != nullptr && Ft->IsArray())
			{
				for (const FValue& V : Ft->Arr())
				{
					O.Foliage.Trees.push_back(V.Num() != 0.0 ? 1 : 0);
				}
			}
			if (O.Foliage.bEnabled)
			{
				if (!O.bBlockSight)
				{
					throw std::runtime_error("숲 시야는 block_sight 를 켠 세계만 받는다 (파이썬도 그렇다)");
				}
				if (!(O.Foliage.R > 0.0) || !(O.Foliage.Block > 0.0))
				{
					throw std::runtime_error("숲 시야 foliage_r·foliage_block 은 0 보다 커야 한다");
				}
				if (!O.Foliage.Trees.empty() && static_cast<std::int32_t>(O.Foliage.Trees.size()) != O.Num())
				{
					throw std::runtime_error("숲 시야 나무 표(foliage_trees) 길이가 원판 수와 다르다");
				}
			}
		}
		{
			const FValue& F = Wb.At("weather");
			W3::FWeatherConfig& Wx = C.Weather;
			Wx.bEnabled = F.At("enabled").Bool();
			Wx.Kind = WeatherKindOf(F.At("kind").Str());
			Wx.Intensity = F.At("intensity").Num();
			Wx.RainSight = F.At("rain_sight").Num();
			Wx.RainHear = F.At("rain_hear").Num();
			Wx.SnowSight = F.At("snow_sight").Num();
			Wx.SnowHear = F.At("snow_hear").Num();
			Wx.SnowDeerSpeed = F.At("snow_deer_speed").Num();
			Wx.SnowWolfSpeed = F.At("snow_wolf_speed").Num();
			Wx.bObsVisibility = F.At("obs_visibility").Bool();
			if (F.NumOr("schedule_rows", 0.0) != 0.0)
			{
				throw std::runtime_error("날씨 시간표는 평가기가 받지 않는다 (스냅숏도 싣지 않는다)");
			}
		}
		C.Covers = CoversOf(Job.At("covers"));
		C.bSenseStats = false;   // 감지 기록은 평가 기록에 없다 (기록만 — 통합 모드는 켠다. 끄면 Step 이 5% 빠르고 궤적은 그대로)
		C.bFlightStats = true;   // 통합 모드와 같다 (기록만 — 도주 반사를 켠 세계만 센다)
		return C;
	}

	// ---- 세계 하나 ----

	struct FEval
	{
		W3::FWorldState W;
		std::vector<R3::FRepState> Reps;
		std::vector<W3::FHerbDecision> Dec;
		std::vector<W3::FHerbBody> Bodies;
		std::vector<W3::FHerbPerception> Perc;
		std::vector<R3::FControlOutput> Ctl;
		std::vector<W3::FThreatAgent> Threats;
		std::vector<W3::FThreatAgent*> ThreatPtrs;
		std::vector<W3::FHerbView> Live;      // 산 사슴 (슬롯 순서 — 통합 모드는 산 개체만 넘긴다)
		std::vector<std::int32_t> LiveSlot;
		std::vector<std::int64_t> DeathT;     // 죽은 스텝 끝 T (산 −1)
		std::vector<std::int32_t> Cause;      // 0 산, 1 잡힘, 2 굶음 (world.py death_cause)
		std::vector<std::int64_t> LastFlee;
		std::int64_t Catches = 0, CatchFled = 0, Starves = 0, StarveFled = 0;
		// 10-24 근접 동점 진단 (기록만): 산 사슴의 망 결정(열린 칸 둘 이상) 가운데 로짓 1·2 위 차 최솟값·1e-4 밑 수, 길 결정의 |ℓ4 − ℓ1| 최솟값
		double MinGap = 1e300, MinRouteGap = 1e300;
		std::int64_t GapDecisions = 0, RouteGapDecisions = 0, NearTies = 0;
		FPcg64 Pcg;
		std::string Region;
	};

	/** 10-24 근접 동점 진단: 지금 산 사슴(E.Live)의 다음 결정 (H 의 DecideHerb 가 망을 돌린 사슴만 — 열린 칸 둘 이상). */
	void TallyGaps(FEval& E)
	{
		for (const W3::FHerbView& H : E.Live)
		{
			const W3::FHerbDecision& D = *H.Decision;
			if (!(D.Prep.bReads || D.bRouteReads))
			{
				continue;
			}
			double A = -1e300, B = -1e300;
			std::int32_t Open = 0;
			for (std::int32_t b = 0; b < R3::kNumBehaviors; ++b)
			{
				if (D.Mask[b] == 0)
				{
					continue;
				}
				++Open;
				const double V = static_cast<double>(D.Logits[b]);
				if (V > A)
				{
					B = A;
					A = V;
				}
				else if (V > B)
				{
					B = V;
				}
			}
			if (Open < 2)
			{
				continue;
			}
			const double G = A - B;
			E.MinGap = G < E.MinGap ? G : E.MinGap;
			++E.GapDecisions;
			E.NearTies += G < 1e-4 ? 1 : 0;
			if (D.bRouteReads)
			{
				E.MinRouteGap = G < E.MinRouteGap ? G : E.MinRouteGap;
				++E.RouteGapDecisions;
			}
		}
	}

	W3::FHerbView ViewOf(FEval& E, std::int32_t s)
	{
		const size_t k = static_cast<size_t>(s);
		return W3::FHerbView{&E.Reps[k], &E.Dec[k], &E.Bodies[k], &E.Perc[k], &E.Ctl[k]};
	}

	void Init(FEval& E, const FValue& Job, const FBrain& Brain)
	{
		W3::InitWorld(E.W, ConfigOf(Job.At("world"), Job));
		W3::SetModelAllowed(E.W, Brain.Allowed);
		W3::SetModelObsDim(E.W, Brain.ObsDim);
		{
			// 10-24 두 길 두뇌 (이식 계획서 7-2·13-3): 세계 키(route·brain_flee_outside_reflex)와 두뇌 판이 같아야 한다 — 파이썬 rep_policy.check_mask_version 과 같은 뜻.
			// 판 4·5 두뇌는 도주 반사(WildFlight)를 켠 세계만, 실제 허용(두뇌 ∧ 세계)의 얼기·잠이 0 이어야 한다(rep_policy.check_route_allowed)
			const FValue& Wf = Job.At("world").At("wild_flight");
			const bool bWorldRoute = Wf.BoolOr("route", false);
			const bool bWorldGate = !Wf.BoolOr("brain_flee_outside_reflex", true);
			if (bWorldRoute != Brain.Route() || bWorldGate != Brain.FleeGate())
			{
				throw std::runtime_error("세계(wild_flight.route " + std::string(bWorldRoute ? "true" : "false") + "·brain_flee_outside_reflex " +
										 (bWorldGate ? "false" : "true") + ")와 두뇌 마스크 판 " + std::to_string(Brain.MaskVersion) + " 이 다르다");
			}
			if (Brain.Route() && !E.W.Config.WildFlight.bEnabled)
			{
				throw std::runtime_error("두 길 두뇌(마스크 판 4·5)는 도주 반사(wild_flight)를 켠 세계만 받는다");
			}
			W3::SetModelRoute(E.W, Brain.Route());
			W3::SetModelFleeGate(E.W, Brain.FleeGate());
			if (Brain.Route() && (E.W.Allowed[R3::kFreeze] != 0 || E.W.Allowed[R3::kSleep] != 0))
			{
				throw std::runtime_error("두 길 두뇌(마스크 판 4·5)는 실제 허용의 얼기·잠이 막혀 있어야 한다");
			}
		}
		E.Region = Job.StrOr("region", "");
		// 먹이 격자: 파이썬 거울 세계가 reset·스냅숏 덮기 뒤 남긴 용량·먹이·재생률 (InitWorld 의 난수 지도는 버린다 — 은신처 셀 칸은 같은 원으로 이미 같다)
		{
			const FValue& F = Job.At("food");
			W3::FFoodGrid& G = E.W.Food;
			if (static_cast<std::int32_t>(F.At("gw").Num()) != G.Gw || F.At("cell").Num() != G.Cell)
			{
				throw std::runtime_error("먹이 격자 크기가 세계와 다르다");
			}
			const size_t Cells = static_cast<size_t>(G.Gw) * G.Gw;
			auto Fill = [&](const char* K, std::vector<double>& Dst)
			{
				const std::vector<FValue>& A = F.At(K).Arr();
				if (A.size() != Cells)
				{
					throw std::runtime_error(std::string("먹이 칸 수가 다르다: ") + K);
				}
				Dst.resize(Cells);
				for (size_t k = 0; k < Cells; ++k)
				{
					Dst[k] = A[k].Num();
				}
			};
			Fill("cap", G.Cap);
			Fill("food", G.Food);
			Fill("regen", G.Regen);
			G.Cap0 = G.Cap;   // 은신처가 바뀌는 일이 없다 (기록만)
		}
		// 사슴 (슬롯 순서)
		const FValue& D = Job.At("deer");
		const std::vector<FValue>& Xs = D.At("x").Arr();
		const std::int32_t N = static_cast<std::int32_t>(Xs.size());
		E.Reps.assign(static_cast<size_t>(N), R3::FRepState());
		E.Dec.assign(static_cast<size_t>(N), W3::FHerbDecision());
		E.Bodies.assign(static_cast<size_t>(N), W3::FHerbBody());
		E.Perc.assign(static_cast<size_t>(N), W3::FHerbPerception());
		E.Ctl.assign(static_cast<size_t>(N), R3::FControlOutput());
		E.DeathT.assign(static_cast<size_t>(N), -1);
		E.Cause.assign(static_cast<size_t>(N), 0);
		E.LastFlee.assign(static_cast<size_t>(N), -1000000000LL);
		const std::vector<FValue>& Ys = D.At("y").Arr();
		const std::vector<FValue>& Hx = D.At("hx").Arr();
		const std::vector<FValue>& Hy = D.At("hy").Arr();
		const std::vector<FValue>& En = D.At("energy").Arr();
		const std::vector<FValue>& Rs = D.At("reserve").Arr();
		const std::vector<FValue>& Rc = D.At("repro_cd").Arr();
		const std::vector<FValue>& Sl = D.At("slot").Arr();
		for (std::int32_t i = 0; i < N; ++i)
		{
			const size_t k = static_cast<size_t>(i);
			const W3::FHerbView H = ViewOf(E, i);
			const R3::FVec2 P{Xs[k].Num(), Ys[k].Num()};
			const R3::FVec2 Hd{Hx[k].Num(), Hy[k].Num()};
			const std::uint32_t Slot = static_cast<std::uint32_t>(Sl[k].Num());
			const double Energy = En[k].Num();
			if (Energy != E.W.RepCfg.InitEnergy)
			{
				throw std::runtime_error("시작 에너지가 InitEnergy 와 다르다 (InitAgent 의 E01 이 어긋난다)");
			}
			W3::AdoptHerb(E.W, H, P, Hd, R3::MakeAgentKey(Slot, 0));
			// 파이썬 값 그대로 (AdoptHerb 는 heading 을 다시 정규화한다 — 끝 비트가 바뀔 수 있다)
			H.Body->Pos = P;
			H.Body->PrevPos = P;
			H.Body->Head = Hd;
			H.Body->Slot = Slot;
			H.Body->Reserve = Rs[k].Num();
			H.Body->ReproCd = static_cast<std::int32_t>(Rc[k].Num());
			E.Live.push_back(H);
			E.LiveSlot.push_back(i);
		}
		// 늑대 (위협 슬롯 순서)
		const std::vector<FValue>& Wv = Job.At("wolves").Arr();
		E.Threats.assign(Wv.size(), W3::FThreatAgent());
		for (size_t m = 0; m < Wv.size(); ++m)
		{
			const FValue& A = Wv[m];
			const std::string Kind = A.At("kind").Str();
			T3::FThreatSpec Spec;
			if (Kind == "stalker")
			{
				Spec = T3::MakeStalkerSpec(E.W.Config.PredSpeedMult, false, E.W.ThreatCfg);
			}
			else if (Kind == "chaser")
			{
				Spec = T3::MakeChaserSpec(E.W.Config.PredSpeedMult, false, false, E.W.ThreatCfg);
			}
			else
			{
				throw std::runtime_error("모르는 늑대 종류: " + Kind);
			}
			if (A.Find("speed") != nullptr && A.At("speed").Num() != Spec.BaseSpeed)
			{
				throw std::runtime_error("늑대 기본 속력이 파이썬 세계와 다르다");
			}
			const double X = A.At("x").Num(), Y = A.At("y").Num(), HX = A.At("hx").Num(), HY = A.At("hy").Num();
			const std::int64_t Slot = static_cast<std::int64_t>(A.At("slot").Num());
			W3::AdoptThreat(E.W, E.Threats[m], Spec, X, Y, HX, HY, Slot);
			E.Threats[m].Slot = static_cast<std::uint32_t>(Slot);
			E.Threats[m].State.PosX = X;
			E.Threats[m].State.PosY = Y;
			E.Threats[m].State.HeadX = HX;   // 파이썬 값 그대로 (Normalize2 를 거치지 않은 cos·sin)
			E.Threats[m].State.HeadY = HY;
			E.Threats[m].PrevX = X;
			E.Threats[m].PrevY = Y;
		}
		E.ThreatPtrs.clear();
		for (W3::FThreatAgent& A : E.Threats)
		{
			E.ThreatPtrs.push_back(&A);
		}
		// 난수: pcg64 = 파이썬 v1 스트림(np.random.default_rng(시드)) 이어 받기, native = 게임 SplitMix64 (InitWorld 의 먹이 잡음 뒤 상태)
		const FValue& Rg = Job.At("rng");
		const std::string RKind = Rg.At("kind").Str();
		if (RKind == "pcg64")
		{
			E.Pcg.State = ParseU128(Rg.At("state").Str());
			E.Pcg.Inc = ParseU128(Rg.At("inc").Str());
			E.W.Rng.External = &FPcg64::Hook;
			E.W.Rng.ExternalUser = &E.Pcg;
		}
		else if (RKind != "native")
		{
			throw std::runtime_error("모르는 난수 종류: " + RKind);
		}
		W3::ObserveAndDecideAll(E.W, E.Live.data(), static_cast<std::int32_t>(E.Live.size()), E.ThreatPtrs.data(),
								static_cast<std::int32_t>(E.ThreatPtrs.size()), Brain.Net);
		TallyGaps(E);
	}

	// ---- 기록 ----

	/**
	 * 10-24 두 길 두뇌 도망 길 기록 (파이썬 flight_stats 의 route = `_flight_route_block` 과 같은 칸·차례: route_stats 칸 + by_route·drop_obstacle·chased_steps·
	 * hidden_steps·refled·refled_steps, 숲 시야 켬 세계만 drop_foliage). C++ 두뇌 길에 없는 칸(fixed·quiet_end·fallback·onset_cover·onset_both)은 늘 같은 값이다.
	 */
	void WriteRoute(FOut& O, const W3::FFlightRouteReport& R, bool bFoliage)
	{
		auto Routes = [&](const char* K, const std::int64_t* V, std::int32_t N)
		{
			O.Key(K);
			O.BeginObj();
			for (std::int32_t r = 0; r < N; ++r)
			{
				O.KInt(W3::RouteName(r), V[r]);
			}
			O.EndObj();
		};
		O.BeginObj();
		O.Key("fixed");
		O.Raw("null");
		O.KInt("quiet_end", 0);
		Routes("steps", R.Route.Steps, W3::kNumRoutes);
		O.KInt("onsets", R.Route.Onsets);
		O.KInt("onset_cover", 0);
		O.KInt("onset_shelter", R.Route.OnsetShelter);
		O.KInt("onset_both", 0);
		O.KInt("decisions", R.Route.Decisions);
		O.KInt("redecide_feas", R.Route.RedecideFeas);
		O.KInt("switches", R.Route.Switches);
		O.KInt("fallback", 0);
		Routes("invalid", R.Route.Invalid, W3::kNumRoutes);
		Routes("picked", R.Route.Picked, W3::kNumRoutes);
		O.KBool("brain", true);
		O.KInt("choice", R.Route.Choice);
		O.KInt("bad_shelter", R.Route.BadShelter);
		O.Key("by_route");
		O.BeginObj();
		for (std::int32_t r = 0; r < W3::kNumFlightRouteRows; ++r)
		{
			O.Key(W3::RouteName(r));
			O.BeginObj();
			const std::int64_t* Parts[3] = {R.N[r], R.Steps[r], R.Contact[r]};
			const char* Names[3] = {"n", "steps", "contact"};
			for (int p = 0; p < 3; ++p)
			{
				O.Key(Names[p]);
				O.BeginObj();
				for (std::int32_t c = 0; c < W3::kNumFlightCauses; ++c)
				{
					O.KInt(W3::FlightCauseName(c), Parts[p][c]);
				}
				O.EndObj();
			}
			O.EndObj();
		}
		O.EndObj();
		Routes("drop_obstacle", R.DropObstacle, W3::kNumFlightRouteRows);
		Routes("chased_steps", R.Chased, W3::kNumFlightRouteRows);
		Routes("hidden_steps", R.Hidden, W3::kNumFlightRouteRows);
		O.KInt("refled", R.Refled);
		O.KInt("refled_steps", W3::kFlightRefleeSteps);
		if (bFoliage)
		{
			Routes("drop_foliage", R.DropFoliage, W3::kNumFlightRouteRows);
		}
		O.EndObj();
	}

	void WriteFlight(FOut& O, const W3::FFlightReport& F, bool bFoliage, const W3::FFlightRouteReport* Route = nullptr)
	{
		O.BeginObj();
		O.KInt("started", F.Started);
		O.KInt("live_steps", F.LiveSteps);
		O.KInt("flee_steps", F.FleeSteps);
		O.KInt("reflex_steps", F.ReflexSteps);
		const std::int64_t* Parts[3] = {F.Num, F.Steps, F.Contact};
		const char* Names[3] = {"n", "steps", "contact"};
		for (int p = 0; p < 3; ++p)
		{
			O.Key(Names[p]);
			O.BeginObj();
			for (std::int32_t c = 0; c < W3::kNumFlightCauses; ++c)
			{
				O.KInt(W3::FlightCauseName(c), Parts[p][c]);
			}
			O.EndObj();
		}
		O.KInt("own_n", F.OwnN);
		O.KInt("own_steps", F.OwnSteps);
		O.KInt("own_contact", F.OwnContact);
		O.KInt("shelter_end", F.ShelterEnd);
		O.KIntArr("hist", F.Hist, W3::kNumFlightHistEdges + 1);
		O.KIntArr("hist_edges", W3::kFlightHistSteps, W3::kNumFlightHistEdges);
		// 10-23 숨은 뒤 지켜보기 (파이썬 flight_stats 의 hide 와 같은 칸 — 옛 도망 단위 1차 숨음 비율·GH 의 재료, 10-24 부터 보고만. EcoWorldV3.h 머리 주석)
		O.Key("hide");
		O.BeginObj();
		O.KInt("chased", F.Chased);
		O.KInt("hidden", F.Hidden);
		O.KInt("watching", F.Watching);
		O.KInt("cover_then_caught", F.CoverCaught);
		O.KInt("cover_then_starved", F.CoverStarved);
		O.KInt("watch_steps", W3::kFlightHideWatchSteps);
		O.EndObj();
		// 10-24 쫓김 사건 (파이썬 flight_stats 의 episode 와 같은 칸·차례 — 실시간 관문 1차 사건 숨음 비율·지킴 GH·GE 의 재료, EcoWorldV3.h 머리 주석 '쫓김 사건')
		O.Key("episode");
		O.BeginObj();
		O.KInt("started", F.EpStarted);
		O.KInt("chased", F.EpChased);
		O.KInt("hidden", F.EpHidden);
		O.KInt("caught", F.EpCaught);
		O.KInt("starved", F.EpStarved);
		O.KInt("other", F.EpOther);
		O.KInt("truncated", F.EpTruncated);
		O.KInt("watching", F.EpWatching);
		O.KInt("other_chased", F.EpOtherChased);
		O.KInt("joined", F.EpJoined);
		O.KInt("joined_cover", F.EpJoinedCover);
		O.KInt("joined_other", F.EpJoinedOther);
		O.KInt("window_caught", F.EpWindowCaught);
		O.KInt("window_starved", F.EpWindowStarved);
		O.KInt("link_cover_steps", W3::kEpisodeLinkCoverSteps);
		O.KInt("link_other_steps", W3::kEpisodeLinkOtherSteps);
		O.EndObj();
		if (bFoliage)
		{
			// 숲 시야 켬 세계만 (파이썬 flight_stats 의 lost_foliage — 끈 세계에는 칸이 없다)
			O.Key("lost_foliage");
			O.BeginObj();
			O.KInt("n", F.LostFoliage[0]);
			O.KInt("steps", F.LostFoliage[1]);
			O.KInt("contact", F.LostFoliage[2]);
			O.EndObj();
		}
		if (Route != nullptr)
		{
			// 10-24 두 길 두뇌 세계만 (파이썬 flight_stats 의 route — 길 끈 세계에는 칸이 없다)
			O.Key("route");
			WriteRoute(O, *Route, bFoliage);
		}
		O.EndObj();
	}

	W3::FFlightReport FlightNow(FEval& E)
	{
		return W3::FlightReportOf(E.W.Stats.Flight, W3::FlightOpenOf(E.Live.data(), static_cast<std::int32_t>(E.Live.size())));
	}

	/** 10-24 두 길 두뇌 도망 길 보고 (지금 열린 도망은 잘림). */
	W3::FFlightRouteReport RouteNow(FEval& E)
	{
		return W3::FlightRouteReportOf(E.W.Stats.Route, E.W.Stats.FlightRoute, W3::FlightOpenOf(E.Live.data(), static_cast<std::int32_t>(E.Live.size())));
	}

	void WriteHunt(FOut& O, const FEval& E)
	{
		const W3::FWorldStats& S = E.W.Stats;
		auto Put = [&](const char* Tag, std::int64_t St, std::int64_t En, std::int64_t Su, std::int64_t Ou)
		{
			const std::string T(Tag);
			O.KInt((T + "starts").c_str(), St);
			O.KInt((T + "ends").c_str(), En);
			O.KInt((T + "success").c_str(), Su);
			O.KInt((T + "outside").c_str(), Ou);
			O.Key((T + "rate").c_str());
			if (En > 0)
			{
				O.Num(static_cast<double>(Su) / static_cast<double>(En));
			}
			else
			{
				O.Raw("null");   // 파이썬 메타는 nan 을 None 으로 적는다 (run_mirror.run_world)
			}
		};
		const size_t Ch = static_cast<size_t>(T3::EThreatType::Chaser), Sk = static_cast<size_t>(T3::EThreatType::Stalker);
		O.BeginObj();
		Put("", S.HuntStarts[Ch] + S.HuntStarts[Sk], S.HuntEnds[Ch] + S.HuntEnds[Sk], S.HuntSuccess[Ch] + S.HuntSuccess[Sk],
			S.HuntOutside[Ch] + S.HuntOutside[Sk]);
		Put("chaser_", S.HuntStarts[Ch], S.HuntEnds[Ch], S.HuntSuccess[Ch], S.HuntOutside[Ch]);
		Put("stalker_", S.HuntStarts[Sk], S.HuntEnds[Sk], S.HuntSuccess[Sk], S.HuntOutside[Sk]);
		std::int64_t On = 0;
		for (const W3::FThreatAgent& A : E.Threats)
		{
			On += A.bHuntOn ? 1 : 0;
		}
		O.KInt("ongoing", On);
		O.EndObj();
	}

	void WriteWeather(FOut& O, const FEval& E)
	{
		const W3::FWorldState& W = E.W;
		static const char* const Names[W3::kNumWeatherKinds] = {"clear", "rain", "snow"};
		O.BeginObj();
		O.KStr("region", E.Region);
		O.KStr("kind", Names[W.WeatherKind]);
		O.KNum("intensity", W.WeatherIntensity);
		O.KNum("sight", W.Weather.Sight);
		O.KNum("hear", W.Weather.Hear);
		O.KNum("deer_speed", W.Weather.DeerSpeed);
		O.KNum("wolf_speed", W.Weather.WolfSpeed);
		O.KNum("wolf_view_r", W3::WolfViewNow(W));
		O.KBool("schedule", !W.Config.Weather.Schedule.empty());
		for (std::int32_t k = 0; k < W3::kNumWeatherKinds; ++k)
		{
			O.KInt((std::string("steps_") + Names[k]).c_str(), W.Stats.WeatherSteps[k]);
		}
		O.EndObj();
	}

	struct FAt
	{
		std::int64_t H = 0, Caught = 0, Starved = 0, Alive = 0;
		W3::FFlightReport Flight;
		W3::FFlightRouteReport Route;   // 10-24 두 길 두뇌 세계만 쓴다
	};

	/**
	 * 파리티 진단: 지금 상태 (모든 슬롯 — 죽은 사슴은 죽은 자리·값). StepSlots = 이번 Step 에 넘긴 사슴의 슬롯(색인 → 슬롯) — 주면 늑대의
	 * 이번 스텝 표적을 슬롯으로 적는다 (없으면 −1).
	 */
	void WriteState(FOut& O, FEval& E, const std::vector<std::int32_t>* StepSlots)
	{
		const std::int32_t N = static_cast<std::int32_t>(E.Bodies.size());
		O.BeginObj();
		O.KInt("t", E.W.T);
		O.KNum("dark", E.W.Dark);
		O.KNum("pred_ema", E.W.PredEma);
		auto Arr = [&](const char* K, auto Fn)
		{
			O.Key(K);
			O.BeginArr();
			for (std::int32_t i = 0; i < N; ++i)
			{
				Fn(i);
			}
			O.EndArr();
		};
		Arr("x", [&](std::int32_t i) { O.Num(E.Bodies[static_cast<size_t>(i)].Pos.X); });
		Arr("y", [&](std::int32_t i) { O.Num(E.Bodies[static_cast<size_t>(i)].Pos.Y); });
		Arr("hx", [&](std::int32_t i) { O.Num(E.Bodies[static_cast<size_t>(i)].Head.X); });
		Arr("hy", [&](std::int32_t i) { O.Num(E.Bodies[static_cast<size_t>(i)].Head.Y); });
		Arr("energy", [&](std::int32_t i) { O.Num(E.Bodies[static_cast<size_t>(i)].Energy); });
		Arr("reserve", [&](std::int32_t i) { O.Num(E.Bodies[static_cast<size_t>(i)].Reserve); });
		Arr("behavior", [&](std::int32_t i) { O.Int(E.Reps[static_cast<size_t>(i)].Behavior); });
		Arr("request", [&](std::int32_t i) { O.Int(E.Dec[static_cast<size_t>(i)].Request); });
		Arr("keep", [&](std::int32_t i) { O.Int(E.Dec[static_cast<size_t>(i)].KeepMode); });
		Arr("cause", [&](std::int32_t i) { O.Int(E.Cause[static_cast<size_t>(i)]); });
		// 스텝 끝 지각 (조향 입력 — 파이썬 기하 to_centroid·separation·away_from_pred·food_grad 와 견준다)
		auto Vec = [&](const char* K, auto Get)
		{
			O.Key(K);
			O.BeginArr();
			for (std::int32_t i = 0; i < N; ++i)
			{
				const R3::FVec2 V = Get(E.Perc[static_cast<size_t>(i)]);
				O.BeginArr();
				O.Num(V.X);
				O.Num(V.Y);
				O.EndArr();
			}
			O.EndArr();
		};
		Vec("to_centroid", [](const W3::FHerbPerception& P) { return P.Kin.ToCentroid; });
		Vec("separation", [](const W3::FHerbPerception& P) { return P.Kin.Separation; });
		Vec("away_from_pred", [](const W3::FHerbPerception& P) { return P.Threat.AwayFromPred; });
		Vec("food_grad", [](const W3::FHerbPerception& P) { return P.FoodGrad; });
		const bool bRouteObs = E.W.ObsDim >= O3::kObsDimRoute;   // 10-24 관측 24 두뇌: 길 세 칸까지 (파이썬 w._obs 24 칸)
		O.Key("obs");
		O.BeginArr();
		for (std::int32_t i = 0; i < N; ++i)
		{
			const W3::FHerbPerception& P = E.Perc[static_cast<size_t>(i)];
			O.BeginArr();
			for (std::int32_t k = 0; k < O3::kObsDim; ++k)
			{
				O.Num(static_cast<double>(P.Obs[k]));
			}
			for (std::int32_t k = 0; k < O3::kNumObstacleObs; ++k)
			{
				O.Num(static_cast<double>(P.ObstacleObs[k]));
			}
			for (std::int32_t k = 0; bRouteObs && k < O3::kNumRouteObs; ++k)
			{
				O.Num(static_cast<double>(P.RouteObs[k]));
			}
			O.EndArr();
		}
		O.EndArr();
		if (E.W.Config.WildFlight.bRoute)
		{
			// 10-24 두 길 두뇌 길 칸 (이식 계획서 7-2 — make_traces.trace_state 와 같은 칸: H 뒤·다음 A 앞). route_req = 길 결정 ∧ 도주 사슴의 두뇌 출력, 아니면 −1.
			// route_gap = 그 사슴의 로짓 차 ℓ4 − ℓ1 (칸 4 SHELTER − 칸 1 RUN, 길 결정 아니면 null — 근접 동점 갈림 진단, 계획서 9절 R13)
			Arr("route", [&](std::int32_t i) { O.Int(E.Dec[static_cast<size_t>(i)].Route); });
			Arr("route_k", [&](std::int32_t i) { O.Int(E.Dec[static_cast<size_t>(i)].RouteK); });
			Arr("route_age", [&](std::int32_t i) { O.Int(E.Dec[static_cast<size_t>(i)].RouteAge); });
			Arr("route_feas", [&](std::int32_t i) { O.Int(E.Dec[static_cast<size_t>(i)].RouteFeas); });
			Arr("route_decide", [&](std::int32_t i) { O.Bool(E.Dec[static_cast<size_t>(i)].bRouteDecide); });
			Arr("route_req", [&](std::int32_t i)
				{
					const W3::FHerbDecision& D = E.Dec[static_cast<size_t>(i)];
					O.Int((D.bRouteDecide && D.KeepMode == W3::kKeepPanic && E.Cause[static_cast<size_t>(i)] == 0) ? D.RouteRequest : -1);
				});
			Arr("route_gap", [&](std::int32_t i)
				{
					const W3::FHerbDecision& D = E.Dec[static_cast<size_t>(i)];
					if (D.bRouteReads && E.Cause[static_cast<size_t>(i)] == 0)
					{
						O.Num(static_cast<double>(D.Logits[W3::kRouteSlotShelter]) - static_cast<double>(D.Logits[W3::kRouteSlotRun]));
					}
					else
					{
						O.Raw("null");
					}
				});
		}
		// 결정 로짓 1·2 위 차 (막은 칸 빼고, 망을 돌린 사슴만 — 아니면 null): 갈림이 근접 동점 결정에서 났는지 가른다
		Arr("gap", [&](std::int32_t i)
			{
				const W3::FHerbDecision& D = E.Dec[static_cast<size_t>(i)];
				if (!(D.Prep.bReads || D.bRouteReads) || E.Cause[static_cast<size_t>(i)] != 0)
				{
					O.Raw("null");
					return;
				}
				double A = -1e300, B = -1e300;
				std::int32_t Open = 0;
				for (std::int32_t b = 0; b < R3::kNumBehaviors; ++b)
				{
					if (D.Mask[b] == 0)
					{
						continue;
					}
					++Open;
					const double V = static_cast<double>(D.Logits[b]);
					if (V > A)
					{
						B = A;
						A = V;
					}
					else if (V > B)
					{
						B = V;
					}
				}
				if (Open < 2)
				{
					O.Raw("null");
				}
				else
				{
					O.Num(A - B);
				}
			});
		O.Key("wolves");
		O.BeginObj();
		const std::int32_t M = static_cast<std::int32_t>(E.Threats.size());
		auto WArr = [&](const char* K, auto Fn)
		{
			O.Key(K);
			O.BeginArr();
			for (std::int32_t m = 0; m < M; ++m)
			{
				Fn(E.Threats[static_cast<size_t>(m)]);
			}
			O.EndArr();
		};
		WArr("x", [&](const W3::FThreatAgent& A) { O.Num(A.State.PosX); });
		WArr("y", [&](const W3::FThreatAgent& A) { O.Num(A.State.PosY); });
		WArr("hx", [&](const W3::FThreatAgent& A) { O.Num(A.State.HeadX); });
		WArr("hy", [&](const W3::FThreatAgent& A) { O.Num(A.State.HeadY); });
		WArr("cd", [&](const W3::FThreatAgent& A) { O.Int(A.State.Cooldown); });
		WArr("sat", [&](const W3::FThreatAgent& A) { O.Int(A.State.SatLeft); });
		WArr("asleep", [&](const W3::FThreatAgent& A) { O.Bool(W3::ThreatAsleepNow(E.W, A)); });
		WArr("night_act", [&](const W3::FThreatAgent& A) { O.Int(A.State.NightAct); });
		WArr("night_delay", [&](const W3::FThreatAgent& A) { O.Int(A.State.NightDelay); });
		if (StepSlots != nullptr)
		{
			WArr("target", [&](const W3::FThreatAgent& A)
				 {
					 const std::int32_t Ti = A.Last.bHasTarget ? A.Last.Target : -1;
					 O.Int(Ti >= 0 && Ti < static_cast<std::int32_t>(StepSlots->size()) ? (*StepSlots)[static_cast<size_t>(Ti)] : -1);
				 });
		}
		O.EndObj();
		O.KInt("draws", static_cast<std::int64_t>(E.Pcg.Draws));
		O.EndObj();
	}

	/**
	 * 10-24 궤적 지문 한 스텝 (herbivore_rl/results/v3/route/port/make_traces.py `digest_state` 와 같은 바이트·같은 칸 아홉 — 리틀 엔디언, C 순서):
	 *   clock  t i8 ‖ dark f8 ‖ pred_ema f8                  deer  x·y·hx·hy·energy·reserve (모든 슬롯) f8
	 *   fate   덮기 (N) i4 ‖ 죽음 (N) i4                     beh   행동 i4 (Alive0 슬롯)
	 *   obs    관측 (Alive0 슬롯, 행 우선) f4 — 관측 24 두뇌면 24 칸, 아니면 21 칸
	 *   req    다음 요청 i4 (스텝 끝 산 ∧ 덮기 < 2)          kin   무리 중심·분리·위협 반대·먹이 기울기 (Alive0 슬롯 × 2) f8
	 *   wolf   늑대 x·y·hx·hy f8 ‖ 쿨다운·배부름·잠·표적 i4 (StepSlots 가 없으면 표적 −1)
	 *   route  길·route_k·route_age·route_feas·route_decide·route_req i4 (스텝 끝 산 슬롯)
	 * 칸마다 sha256 앞 8 자리 16 진. 전체 궤적(수백 MB)을 쓰지 않고 판 단위 대조 자료(traj/)와 견준다.
	 */
	std::vector<std::string> TrajDigest(FEval& E, const std::vector<std::uint8_t>& Alive0, const std::vector<std::int32_t>* StepSlots)
	{
		const std::int32_t N = static_cast<std::int32_t>(E.Bodies.size());
		const std::int32_t M = static_cast<std::int32_t>(E.Threats.size());
		const bool bRouteObs = E.W.ObsDim >= O3::kObsDimRoute;
		std::vector<std::string> Out;
		std::vector<std::uint8_t> B;
		auto Put = [&B](const void* P, size_t Len)
		{
			const std::uint8_t* Q = static_cast<const std::uint8_t*>(P);
			B.insert(B.end(), Q, Q + Len);
		};
		auto PutD = [&Put](double V) { Put(&V, 8); };
		auto PutF = [&Put](float V) { Put(&V, 4); };
		auto PutI = [&Put](std::int32_t V) { Put(&V, 4); };
		auto Done = [&B, &Out]()
		{
			EcoSha256::FState S;
			EcoSha256::Update(S, B.data(), B.size());
			std::uint8_t Dg[EcoSha256::kDigestBytes];
			EcoSha256::Final(S, Dg);
			char Hex[2 * EcoSha256::kDigestBytes + 1];
			EcoSha256::ToHex(Dg, Hex);
			Out.emplace_back(Hex, 8);
			B.clear();
		};
		const auto Live = [&E](std::int32_t i) { return E.Cause[static_cast<size_t>(i)] == 0; };
		// clock
		const std::int64_t T = E.W.T;
		Put(&T, 8);
		PutD(E.W.Dark);
		PutD(E.W.PredEma);
		Done();
		// deer
		for (std::int32_t f = 0; f < 6; ++f)
		{
			for (std::int32_t i = 0; i < N; ++i)
			{
				const W3::FHerbBody& Bd = E.Bodies[static_cast<size_t>(i)];
				const double V[6] = {Bd.Pos.X, Bd.Pos.Y, Bd.Head.X, Bd.Head.Y, Bd.Energy, Bd.Reserve};
				PutD(V[f]);
			}
		}
		Done();
		// fate
		for (std::int32_t i = 0; i < N; ++i)
		{
			PutI(E.Dec[static_cast<size_t>(i)].KeepMode);
		}
		for (std::int32_t i = 0; i < N; ++i)
		{
			PutI(E.Cause[static_cast<size_t>(i)]);
		}
		Done();
		// beh
		for (std::int32_t i = 0; i < N; ++i)
		{
			if (Alive0[static_cast<size_t>(i)] != 0)
			{
				PutI(E.Reps[static_cast<size_t>(i)].Behavior);
			}
		}
		Done();
		// obs
		for (std::int32_t i = 0; i < N; ++i)
		{
			if (Alive0[static_cast<size_t>(i)] == 0)
			{
				continue;
			}
			const W3::FHerbPerception& P = E.Perc[static_cast<size_t>(i)];
			for (std::int32_t k = 0; k < O3::kObsDim; ++k)
			{
				PutF(P.Obs[k]);
			}
			for (std::int32_t k = 0; k < O3::kNumObstacleObs; ++k)
			{
				PutF(P.ObstacleObs[k]);
			}
			for (std::int32_t k = 0; bRouteObs && k < O3::kNumRouteObs; ++k)
			{
				PutF(P.RouteObs[k]);
			}
		}
		Done();
		// req
		for (std::int32_t i = 0; i < N; ++i)
		{
			const W3::FHerbDecision& D = E.Dec[static_cast<size_t>(i)];
			if (Live(i) && D.KeepMode < 2)
			{
				PutI(D.Request);
			}
		}
		Done();
		// kin
		for (std::int32_t g = 0; g < 4; ++g)
		{
			for (std::int32_t i = 0; i < N; ++i)
			{
				if (Alive0[static_cast<size_t>(i)] == 0)
				{
					continue;
				}
				const W3::FHerbPerception& P = E.Perc[static_cast<size_t>(i)];
				const R3::FVec2 V = g == 0 ? P.Kin.ToCentroid : g == 1 ? P.Kin.Separation : g == 2 ? P.Threat.AwayFromPred : P.FoodGrad;
				PutD(V.X);
				PutD(V.Y);
			}
		}
		Done();
		// wolf
		for (std::int32_t f = 0; f < 4; ++f)
		{
			for (std::int32_t m = 0; m < M; ++m)
			{
				const T3::FThreatState& S = E.Threats[static_cast<size_t>(m)].State;
				const double V[4] = {S.PosX, S.PosY, S.HeadX, S.HeadY};
				PutD(V[f]);
			}
		}
		for (std::int32_t m = 0; m < M; ++m)
		{
			PutI(E.Threats[static_cast<size_t>(m)].State.Cooldown);
		}
		for (std::int32_t m = 0; m < M; ++m)
		{
			PutI(E.Threats[static_cast<size_t>(m)].State.SatLeft);
		}
		for (std::int32_t m = 0; m < M; ++m)
		{
			PutI(W3::ThreatAsleepNow(E.W, E.Threats[static_cast<size_t>(m)]) ? 1 : 0);
		}
		for (std::int32_t m = 0; m < M; ++m)
		{
			const W3::FThreatAgent& A = E.Threats[static_cast<size_t>(m)];
			const std::int32_t Ti = A.Last.bHasTarget ? A.Last.Target : -1;
			PutI((StepSlots != nullptr && Ti >= 0 && Ti < static_cast<std::int32_t>(StepSlots->size())) ? (*StepSlots)[static_cast<size_t>(Ti)] : -1);
		}
		Done();
		// route
		for (std::int32_t f = 0; f < 6; ++f)
		{
			for (std::int32_t i = 0; i < N; ++i)
			{
				if (!Live(i))
				{
					continue;
				}
				const W3::FHerbDecision& D = E.Dec[static_cast<size_t>(i)];
				const std::int32_t Req = (D.bRouteDecide && D.KeepMode == W3::kKeepPanic) ? D.RouteRequest : -1;
				const std::int32_t V[6] = {D.Route, D.RouteK, D.RouteAge, D.RouteFeas, D.bRouteDecide ? 1 : 0, Req};
				PutI(V[f]);
			}
		}
		Done();
		return Out;
	}

	void WriteDigestLine(FOut& O, std::int64_t S, const std::vector<std::string>& Dg)
	{
		O.BeginArr();
		O.Int(S);
		for (const std::string& H : Dg)
		{
			O.Str(H);
		}
		O.EndArr();
	}

	std::string RunJob(const FValue& Job, const FBrain& Brain, bool& bOk)
	{
		const auto T0 = std::chrono::steady_clock::now();
		FOut O;
		O.BeginObj();
		O.KInt("id", static_cast<std::int64_t>(Job.NumOr("id", -1.0)));
		try
		{
			FEval E;
			Init(E, Job, Brain);
			const std::int64_t Steps = static_cast<std::int64_t>(Job.At("steps").Num());
			const std::int64_t Trace = static_cast<std::int64_t>(Job.NumOr("trace", 0.0));
			std::vector<std::int64_t> Hs;
			if (const FValue* Hv = Job.Find("horizons"); Hv != nullptr && Hv->IsArray())
			{
				for (const FValue& H : Hv->Arr())
				{
					Hs.push_back(static_cast<std::int64_t>(H.Num()));
				}
			}
			FOut Tr;
			if (Trace > 0)
			{
				Tr.First.push_back(true);   // 바깥 배열 안
				Tr.Key("init");
				WriteState(Tr, E, nullptr);
				Tr.Key("trace");
				Tr.BeginArr();
			}
			// 10-24 궤적 지문 (선택 칸 trace_digest — 스텝 수, 0 = 끔): 스텝 s = 0..trace_digest 마다 칸 아홉의 sha256 앞 8 자리 (TrajDigest)
			const std::int64_t DigestSteps = static_cast<std::int64_t>(Job.NumOr("trace_digest", 0.0));
			FOut Dg;
			std::vector<std::uint8_t> Alive0(E.Bodies.size(), 1);
			if (DigestSteps > 0)
			{
				Dg.First.push_back(true);
				Dg.Key("traj");
				Dg.BeginArr();
				WriteDigestLine(Dg, 0, TrajDigest(E, Alive0, nullptr));
			}
			std::vector<FAt> Ats;
			std::vector<std::int32_t> PrevSlot;
			const std::int32_t M = static_cast<std::int32_t>(E.ThreatPtrs.size());
			for (std::int64_t s = 0; s < Steps; ++s)
			{
				const std::int32_t n = static_cast<std::int32_t>(E.Live.size());
				for (size_t k = 0; k < Alive0.size(); ++k)
				{
					Alive0[k] = E.Cause[k] == 0 ? 1 : 0;   // 이번 스텝 첫머리에 산 슬롯 (지문의 beh·obs·kin)
				}
				W3::Step(E.W, E.Live.data(), n, E.ThreatPtrs.data(), M, Brain.Net, nullptr);
				const std::int64_t T = E.W.T;
				// 진단 칸 (run_mirror.py _Diag.after): 이번 스텝 첫머리에 산 사슴의 이번 스텝 행동이 FLEE 면 마지막 도망 = T, 그다음 죽음
				for (std::int32_t r = 0; r < n; ++r)
				{
					const size_t k = static_cast<size_t>(E.LiveSlot[static_cast<size_t>(r)]);
					if (E.Reps[k].Behavior == R3::kFlee)
					{
						E.LastFlee[k] = T;
					}
				}
				PrevSlot = E.LiveSlot;
				size_t w = 0;
				for (std::int32_t r = 0; r < n; ++r)
				{
					const std::int32_t Slot = E.LiveSlot[static_cast<size_t>(r)];
					const size_t k = static_cast<size_t>(Slot);
					const W3::FHerbBody& B = E.Bodies[k];
					if (B.DeathCause != W3::kDeathNone)
					{
						const bool bCaught = B.DeathCause == W3::kDeathCaught;
						const bool bFled = T - E.LastFlee[k] <= kFledSteps;
						E.DeathT[k] = T;
						E.Cause[k] = bCaught ? 1 : 2;
						(bCaught ? E.Catches : E.Starves) += 1;
						(bCaught ? E.CatchFled : E.StarveFled) += bFled ? 1 : 0;
						continue;   // 통합 모드: 다음 Step 부터 뺀다
					}
					E.Live[w] = E.Live[static_cast<size_t>(r)];
					E.LiveSlot[w] = Slot;
					++w;
				}
				E.Live.resize(w);
				E.LiveSlot.resize(w);
				TallyGaps(E);
				if (Trace > 0 && s < Trace)
				{
					WriteState(Tr, E, &PrevSlot);
				}
				if (DigestSteps > 0 && s < DigestSteps)
				{
					WriteDigestLine(Dg, s + 1, TrajDigest(E, Alive0, &PrevSlot));
				}
				for (const std::int64_t H : Hs)
				{
					if (H == T)
					{
						FAt A;
						A.H = H;
						for (size_t k = 0; k < E.Cause.size(); ++k)
						{
							A.Caught += E.Cause[k] == 1 ? 1 : 0;
							A.Starved += E.Cause[k] == 2 ? 1 : 0;
							A.Alive += E.Cause[k] == 0 ? 1 : 0;
						}
						A.Flight = FlightNow(E);
						A.Route = RouteNow(E);
						Ats.push_back(A);
					}
				}
			}
			if (Trace > 0)
			{
				Tr.EndArr();
			}
			if (DigestSteps > 0)
			{
				Dg.EndArr();
			}
			const double Wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - T0).count();
			const W3::FWorldStats& S = E.W.Stats;
			std::int64_t Caught = 0, Starved = 0, Alive = 0;
			for (const std::int32_t C : E.Cause)
			{
				Caught += C == 1 ? 1 : 0;
				Starved += C == 2 ? 1 : 0;
				Alive += C == 0 ? 1 : 0;
			}
			O.Key("record");
			O.BeginObj();
			O.KInt("seed", static_cast<std::int64_t>(Job.At("seed").Num()));
			O.KStr("region", E.Region);
			O.KInt("n", static_cast<std::int64_t>(E.Bodies.size()));
			O.KInt("caught", Caught);
			O.KInt("starved", Starved);
			O.KInt("alive", Alive);
			O.KInt("shelter_steps", S.ShelterDeerSteps);
			O.KInt("live_steps", S.LiveDeerSteps);
			O.KIntArr("beh_steps", S.BehaviorSteps, R3::kNumBehaviors);
			O.KInt("catch_cover", S.CaughtInCover);
			O.KInt("catch_fled", E.CatchFled);
			O.KInt("catches", E.Catches);
			O.KInt("starve_fled", E.StarveFled);
			O.Key("hunt");
			WriteHunt(O, E);
			if (E.W.Config.Weather.bEnabled)
			{
				O.Key("weather");
				WriteWeather(O, E);
			}
			if (E.W.Config.Obstacles.bEnabled)
			{
				O.KInt("obstacles_n", E.W.Config.Obstacles.Num());
			}
			const bool bRoute = E.W.Config.WildFlight.bRoute;   // 10-24 두 길 두뇌 세계 (flight.route 칸)
			if (E.W.Config.bFlightStats && E.W.Config.WildFlight.bEnabled)
			{
				O.Key("flight");
				const W3::FFlightRouteReport Rr = RouteNow(E);
				WriteFlight(O, FlightNow(E), E.W.Config.Obstacles.FoliageConfigured(), bRoute ? &Rr : nullptr);
			}
			if (!Hs.empty())
			{
				O.Key("at");
				O.BeginObj();
				for (const FAt& A : Ats)
				{
					O.Key(std::to_string(A.H).c_str());
					O.BeginObj();
					O.KInt("caught", A.Caught);
					O.KInt("starved", A.Starved);
					O.KInt("alive", A.Alive);
					if (E.W.Config.bFlightStats && E.W.Config.WildFlight.bEnabled)
					{
						O.Key("flight");
						WriteFlight(O, A.Flight, E.W.Config.Obstacles.FoliageConfigured(), bRoute ? &A.Route : nullptr);
					}
					O.EndObj();
				}
				O.EndObj();
			}
			O.KInt("steps", E.W.T);
			O.KNum("wall_s", Wall);
			O.KNum("steps_per_s", Wall > 0.0 ? static_cast<double>(E.W.T) / Wall : 0.0);
			O.KInt("rng_draws", static_cast<std::int64_t>(E.Pcg.Draws));
			O.KInt("decisions", S.Decisions);
			O.KInt("mask_violations", S.MaskViolations);
			O.KInt("obs_layout_mismatch", S.ObsLayoutMismatch);
			O.KInt("refuge_capture_violations", S.RefugeCaptureViolations);
			O.KInt("gap_decisions", E.GapDecisions);
			O.KNum("min_gap", E.GapDecisions > 0 ? E.MinGap : std::numeric_limits<double>::quiet_NaN());
			O.KInt("near_ties", E.NearTies);
			O.KInt("route_gap_decisions", E.RouteGapDecisions);
			O.KNum("min_route_gap", E.RouteGapDecisions > 0 ? E.MinRouteGap : std::numeric_limits<double>::quiet_NaN());
			O.EndObj();
			if (Trace > 0)
			{
				O.Raw(Tr.S);
			}
			if (DigestSteps > 0)
			{
				O.Raw(Dg.S);
			}
		}
		catch (const std::exception& Ex)
		{
			bOk = false;
			O.KStr("error", Ex.what());
		}
		O.EndObj();
		return O.S;
	}
}

int main(int Argc, char** Argv)
{
	using namespace EcoV3Eval;
	std::string JobsPath, OutPath, BrainCheck;
	bool bQuiet = false;
	for (int a = 1; a < Argc; ++a)
	{
		const std::string A = Argv[a];
		if (A == "--jobs" && a + 1 < Argc)
		{
			JobsPath = Argv[++a];
		}
		else if (A == "--out" && a + 1 < Argc)
		{
			OutPath = Argv[++a];
		}
		else if (A == "--quiet")
		{
			bQuiet = true;
		}
		else if (A == "--brain-check" && a + 1 < Argc)
		{
			BrainCheck = Argv[++a];
		}
		else if (A == "--pcg-selftest" && a + 3 < Argc)
		{
			try
			{
				FPcg64 P;
				P.State = ParseU128(Argv[a + 1]);
				P.Inc = ParseU128(Argv[a + 2]);
				const int N = std::atoi(Argv[a + 3]);
				for (int k = 0; k < N; ++k)
				{
					std::printf("%llu\n", static_cast<unsigned long long>(P.Next()));
				}
				return 0;
			}
			catch (const std::exception& Ex)
			{
				std::fprintf(stderr, "[EcoV3Eval] %s\n", Ex.what());
				return 2;
			}
		}
		else
		{
			std::fprintf(stderr, "쓰는 법: EcoV3Eval --jobs <일.json> --out <기록.jsonl> [--quiet] | --brain-check <두뇌.json> | --pcg-selftest <state> <inc> <n>\n");
			return 2;
		}
	}
	try
	{
		if (!BrainCheck.empty())
		{
			FBrain B;
			LoadBrain(BrainCheck, B);
			std::printf("{\"id\":\"%s\",\"obs_dim\":%d,\"mask_version\":%d,\"weights_sha256\":\"%s\",\"golden_cases\":%d,\"golden_max_err\":%.9g,"
						"\"allowed\":[%d,%d,%d,%d,%d]}\n",
						B.Id.c_str(), B.ObsDim, B.MaskVersion, B.WeightsSha256.c_str(), B.GoldenCases, B.GoldenMaxErr, B.Allowed[0], B.Allowed[1],
						B.Allowed[2], B.Allowed[3], B.Allowed[4]);
			return 0;
		}
		if (JobsPath.empty() || OutPath.empty())
		{
			std::fprintf(stderr, "[EcoV3Eval] --jobs·--out 가 필요하다\n");
			return 2;
		}
		const MiniJson::FValue Root = MiniJson::Parse(ReadFile(JobsPath));
		if (Root.StrOr("format", "") != "eco_v3_eval_jobs" || static_cast<int>(Root.NumOr("version", -1)) != 1)
		{
			std::fprintf(stderr, "[EcoV3Eval] 일 파일 형식이 eco_v3_eval_jobs 판 1 이 아니다\n");
			return 2;
		}
		FBrain Brain;
		LoadBrain(Root.At("brain").Str(), Brain);
		std::ofstream Out(OutPath, std::ios::binary | std::ios::trunc);
		if (!Out)
		{
			std::fprintf(stderr, "[EcoV3Eval] 기록 파일을 열지 못했다: %s\n", OutPath.c_str());
			return 2;
		}
		const std::vector<MiniJson::FValue>& Jobs = Root.At("jobs").Arr();
		bool bAllOk = true;
		const auto T0 = std::chrono::steady_clock::now();
		for (size_t j = 0; j < Jobs.size(); ++j)
		{
			bool bOk = true;
			const std::string Line = RunJob(Jobs[j], Brain, bOk);
			Out << Line << '\n';
			Out.flush();
			bAllOk = bAllOk && bOk;
			if (!bQuiet)
			{
				std::fprintf(stderr, "[EcoV3Eval] %zu/%zu %s\n", j + 1, Jobs.size(), bOk ? "ok" : "오류");
			}
		}
		if (!bQuiet)
		{
			std::fprintf(stderr, "[EcoV3Eval] 세계 %zu 개 %.2f 초 (두뇌 %s)\n", Jobs.size(),
						 std::chrono::duration<double>(std::chrono::steady_clock::now() - T0).count(), Brain.Id.c_str());
		}
		return bAllOk ? 0 : 1;
	}
	catch (const std::exception& Ex)
	{
		std::fprintf(stderr, "[EcoV3Eval] %s\n", Ex.what());
		return 2;
	}
}
