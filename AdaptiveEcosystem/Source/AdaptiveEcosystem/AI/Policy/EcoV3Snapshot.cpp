// 통합 v3 모드 환경 스냅숏 (10-18 사용자 '나무나 풀 같은 식생이 점점 변해서 환경이 달라지면 … 가중치 로더 써서 두뇌 바꿔 주는 기술을 한번 적용해 보자').
//
// 적응 고리의 첫 칸이다: 언리얼(서버·단독)이 지금 세계를 파일 하나로 쓰고 → 파이썬 herbivore_rl/results/v3/adapt/adapt.py 가 그 파일로 거울 세계를
// 다시 지어 지금 두뇌를 짧게 이어 배우고 → 미리 적은 자동 관문을 통과한 두뇌만 두뇌 파일(EcoV3Brain.h)로 내보내 eco.V3Brain.Load 로 바꿔 끼운다.
// 형식은 Docs/RL_Policy/SEASON_SNAPSHOT_SPEC.md 11절 (eco_v3_snapshot 판 1). 세계를 읽기만 한다 — 상태·난수·기록을 바꾸지 않는다.
//
// 쓰는 길 (개발 빌드):
//   콘솔   eco.IntegratedV3.Snapshot [경로]                 지금 바로 (서버·단독, 통합 v3 Play 중)
//   예정   eco.IntegratedV3.SnapshotAt <초>                 전역 스텝 × 2/15 초가 그 시각 이상인 첫 결정 스텝 경계에서 한 번 (명령줄 -EcoV3SnapshotAt=)
//          eco.IntegratedV3.SnapshotOut <파일|폴더>         예정·콘솔(경로를 안 주면) 경로 (명령줄 -EcoV3SnapshotOut=). 비면 Saved/EcoSnapshots/
//   자동   eco.IntegratedV3.AutoSnapshot <-1|0|1>           (10-21 실시간 두뇌 교체) 환경 판이 바뀐 뒤 AutoSnapshotSettle 초(기본 3) 그대로면 판마다 한 번.
//                                                            -1 = eco.IntegratedV3.AutoAdapt 를 따름 (기본). 명령줄 -EcoV3AutoSnapshot=
//          eco.IntegratedV3.SnapshotEvery <초>              주기 스냅숏 (0 = 끔, 기본). 명령줄 -EcoV3SnapshotEvery=
//          eco.IntegratedV3.AutoSnapshotOut <폴더>          자동·주기 폴더 (비면 Saved/EcoAdapt/snapshots — 파이썬 live.py 가 본다). 명령줄 -EcoV3AutoSnapshotOut=
// 먹이 격자 값은 double 을 17 자리로 적어(엔진 Json 쓰개) 파이썬이 비트 단위로 같은 값을 읽는다.
// 10-21 (LIVE_ADAPT_SPEC.md 2절): 'env' 블록 (환경 감시·환경 판·바뀐 스텝·계기·바뀜 목록 — EcoV3EnvWatch.cpp)과 지역마다 obstacles.level_trunks 를 더했다 (판 1 그대로,
// 새 칸은 더하기만). 모든 쓰기(자동·주기·콘솔·예정)는 바꿔 끼우기다 — '<이름>.json.tmp' 에 다 쓴 뒤 '<이름>.json' 으로 옮긴다 (감시하는 쪽은 *.tmp 를 보지 않는다).
// 10-22 숲 시야 (eco.IntegratedV3.Foliage, EcoWorldV3.h FObstacleConfig::Foliage — 판 1 그대로, 더하기만): 지역 world.obstacle_rules 에 foliage·foliage_r·foliage_block,
// 지역 obstacles 에 foliage_trees (discs 순서로 원판마다 나무 0/1), settings 에 foliage (스위치), 켠 세계의 flight 에 lost_foliage {n, steps, contact}.
// 파이썬 adapt.convert 는 켠 세계(장애물 ∧ 눈길 가림 ∧ foliage)를 거부한다(Refused — 대응을 아직 옮기지 않았다). 옮길 때 대응은 obstacle_rules.foliage →
// features.obstacles.foliage.enabled, foliage_r → .r, foliage_block → .block, obstacles.foliage_trees → .trees (fixed 원판 순서의 0/1 목록).
// 10-27 '큰 변화만' 다시 배우기 (설계·구현 기록 FOREST_GROWTH_MODE.md 2절, LIVE_ADAPT_SPEC.md 5.2): eco.IntegratedV3.AutoSnapshotRule 1 (기본) = 자동 스냅숏을
// 나무가 BigTrees(10) 이상 바뀌었거나 날씨 종류가 WeatherHold(120 초) 이상 바뀐 채일 때만, 큰 변화 바뀜이 BigSettle(20 초) 멈춘 뒤 한 번 쓴다. 숲 자람 모드가
// 자라는 동안('레벨 바뀜 진행 중')은 기다린다 — 조건 뒤 BigMaxWait(300 초)가 지나면 무엇이든 쓴다. 쓰면 기준선 = 지금. 0 = 옛 동작 (환경 판마다 AutoSnapshotSettle 뒤 한 번).
// 이 규칙은 언제 쓰는지만 바꾼다 — 세계는 그대로다. 'env' 블록에 더하기만: rule ("big"·"each"), big (규칙 1 — 기준선·대칭차·날씨 종류·묶기·기다림), forest (숲 자람 켬일 때만).
// 적응 고리 폴더 eco.IntegratedV3.AdaptRoot (빈 값 = Saved/EcoAdapt) 하나가 자동·주기 스냅숏(<root>/snapshots)·두뇌 감시·상태 파일·파이썬 감시 --root 의 기본을 묶는다.

#include "EcoPolicyV3IntegratedSubsystem.h"

#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace EcoV3SnapshotImpl
{
	static TAutoConsoleVariable<float> CVarSnapshotAt(
		TEXT("eco.IntegratedV3.SnapshotAt"),
		-1.0f,
		TEXT("통합 v3 모드 환경 스냅숏 예정 시각 (초, 음수 = 끔 — 기본). 전역 결정 스텝 × 2/15 초가 이 값 이상인 첫 경계에서 한 번 ")
		TEXT("eco.IntegratedV3.SnapshotOut 에 쓴다 (적응 고리 — herbivore_rl/results/v3/adapt/). 명령줄 -EcoV3SnapshotAt= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<FString> CVarSnapshotOut(
		TEXT("eco.IntegratedV3.SnapshotOut"),
		TEXT(""),
		TEXT("통합 v3 모드 환경 스냅숏 경로 ('.json' 파일 또는 폴더, 상대 경로는 프로젝트 폴더 기준). 비면 <프로젝트>/Saved/EcoSnapshots/")
		TEXT("eco_v3_snapshot_s<세션 시드>_t<전역 스텝>.json. 명령줄 -EcoV3SnapshotOut= 는 시작값."),
		ECVF_Default);

#if !UE_BUILD_SHIPPING
	// 10-21 실시간 두뇌 교체 (LIVE_ADAPT_SPEC.md 5.2 — 개발 빌드만. Shipping 은 자동·주기 스냅숏이 늘 끔)
	static TAutoConsoleVariable<int32> CVarAutoSnapshot(
		TEXT("eco.IntegratedV3.AutoSnapshot"),
		-1,
		TEXT("통합 v3 모드 환경 바뀜 자동 스냅숏 (-1 = eco.IntegratedV3.AutoAdapt 를 따름, 기본 / 0 = 끔 / 1 = 켬). 환경 감시(eco.IntegratedV3.EnvWatch)가 넣은 마지막 환경 판이 ")
		TEXT("eco.IntegratedV3.AutoSnapshotSettle 시뮬레이션 초 동안 그대로이면 판마다 한 번 eco.IntegratedV3.AutoSnapshotOut 에 쓴다 (계기 env_change). 명령줄 -EcoV3AutoSnapshot= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarSnapshotEvery(
		TEXT("eco.IntegratedV3.SnapshotEvery"),
		0.0f,
		TEXT("통합 v3 모드 주기 스냅숏 (시뮬레이션 초, 0 = 끔 — 기본). 켜거나 값을 바꾼 때부터 이 주기로 eco.IntegratedV3.AutoSnapshotOut 에 쓴다 (계기 periodic). ")
		TEXT("명령줄 -EcoV3SnapshotEvery= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarAutoSnapshotSettle(
		TEXT("eco.IntegratedV3.AutoSnapshotSettle"),
		3.0f,
		TEXT("통합 v3 모드 자동 스냅숏을 쓰기 전 환경 판이 그대로여야 하는 시뮬레이션 초 (기본 3 — 레벨이 나무를 여럿 놓는 동안 판마다 쓰지 않게)."),
		ECVF_Default);

	static TAutoConsoleVariable<FString> CVarAutoSnapshotOut(
		TEXT("eco.IntegratedV3.AutoSnapshotOut"),
		TEXT(""),
		TEXT("통합 v3 모드 자동·주기 스냅숏 폴더 (상대 경로는 프로젝트 폴더 기준, 비면 <eco.IntegratedV3.AdaptRoot>/snapshots — 기본 <프로젝트>/Saved/EcoAdapt/snapshots, ")
		TEXT("파이썬 live.py 가 본다). 파일 이름 eco_v3_snapshot_s<세션 시드>_t<전역 스텝>_e<환경 판>.json. 명령줄 -EcoV3AutoSnapshotOut= 는 시작값."),
		ECVF_Default);

	// 10-27 '큰 변화만' 다시 배우기 (FOREST_GROWTH_MODE.md 2절 — Play 중 바꿔도 다음 결정 스텝부터. 세계에 닿지 않는다)
	static TAutoConsoleVariable<int32> CVarAutoSnapshotRule(
		TEXT("eco.IntegratedV3.AutoSnapshotRule"),
		1,
		TEXT("자동 스냅숏(= 파이썬 다시 배우기 계기)을 언제 쓰나 (1 = 큰 변화만, 기본 — 10-27 사용자 결정). 나무가 eco.IntegratedV3.BigTrees 이상 바뀌었거나 날씨 종류가 ")
		TEXT("eco.IntegratedV3.WeatherHold 초 이상 바뀐 채일 때만, 큰 변화 바뀜이 eco.IntegratedV3.BigSettle 초 멈춘 뒤 한 번 쓴다. 숲 자람 모드가 자라는 동안은 기다린다 ")
		TEXT("(상한 eco.IntegratedV3.BigMaxWait). 세기만 바뀐 날씨는 세계에는 넣되 세지 않는다. 0 = 옛 동작 (환경 판마다 eco.IntegratedV3.AutoSnapshotSettle 뒤 한 번). ")
		TEXT("세계는 그대로다. 명령줄 -EcoV3AutoSnapshotRule= 는 시작값."),
		ECVF_Default);
	static TAutoConsoleVariable<int32> CVarBigTrees(
		TEXT("eco.IntegratedV3.BigTrees"), 10,
		TEXT("'큰 변화만' 나무 문턱 — 한 지역 세계 원판이 기준선(Play 시작·마지막 자동 스냅숏)과 이만큼 이상 다르면 (같은 (x, y, r) 끼리 지우고 남은 양쪽 합, 기본 10). ")
		TEXT("명령줄 -EcoV3BigTrees= 는 시작값."),
		ECVF_Default);
	static TAutoConsoleVariable<float> CVarWeatherHold(
		TEXT("eco.IntegratedV3.WeatherHold"), 120.0f,
		TEXT("'큰 변화만' 날씨 — 기준선과 다른 날씨 종류가 이만큼 이어져야 한다 (시뮬레이션 초, 기본 120 — 팀 비 주기 180 초의 맑음·비 반 주기 약 90 초를 넘는다). ")
		TEXT("명령줄 -EcoV3WeatherHold= 는 시작값."),
		ECVF_Default);
	static TAutoConsoleVariable<float> CVarBigSettle(
		TEXT("eco.IntegratedV3.BigSettle"), 20.0f,
		TEXT("'큰 변화만' 묶기 — 조건이 선 뒤 큰 변화 바뀜(원판·날씨 종류)이 이만큼 없을 때 쓴다 (시뮬레이션 초, 기본 20). 명령줄 -EcoV3BigSettle= 는 시작값."),
		ECVF_Default);
	static TAutoConsoleVariable<float> CVarBigMaxWait(
		TEXT("eco.IntegratedV3.BigMaxWait"), 300.0f,
		TEXT("'큰 변화만' 기다림 상한 — 조건이 선 뒤 이만큼 지나면 '레벨 바뀜 진행 중'·묶기와 상관없이 쓴다 (시뮬레이션 초, 기본 300). 명령줄 -EcoV3BigMaxWait= 는 시작값."),
		ECVF_Default);
	static TAutoConsoleVariable<FString> CVarAdaptRoot(
		TEXT("eco.IntegratedV3.AdaptRoot"), TEXT(""),
		TEXT("적응 고리 폴더 하나 (빈 값 = <프로젝트>/Saved/EcoAdapt, 상대 경로는 프로젝트 폴더 기준): 자동·주기 스냅숏 <root>/snapshots·두뇌 감시 <root>/brains·")
		TEXT("상태 파일 <root>/status.json·파이썬 감시 --root 의 기본. 시험이 실제 폴더를 건드리지 않게 이것 하나만 바꾼다 (eco.IntegratedV3.AutoSnapshotOut·")
		TEXT("eco.V3Brain.WatchFolder·StatusFile 은 지금처럼 따로 덮을 수 있다). Play 전에 바꾼다. 명령줄 -EcoV3AdaptRoot= 는 시작값."),
		ECVF_Default);
#endif

	/** 큰 변화 규칙 기다림 표시 (숲 자람 모드). */
	const TCHAR* const kForestHoldWhat = TEXT("숲이 다 자랄 때까지");

	/** 자동 스냅숏 켬 (eco.IntegratedV3.AutoSnapshot: -1 = AutoAdapt 따름). Shipping 은 늘 끔. */
	bool AutoSnapshotOn()
	{
#if !UE_BUILD_SHIPPING
		const int32 V = CVarAutoSnapshot.GetValueOnGameThread();
		return V < 0 ? UEcoPolicyV3IntegratedSubsystem::IsAutoAdaptEnabled() : V != 0;
#else
		return false;
#endif
	}

	/** 주기 스냅숏 시뮬레이션 초 (0 = 끔). */
	double SnapshotEverySeconds()
	{
#if !UE_BUILD_SHIPPING
		const double V = static_cast<double>(CVarSnapshotEvery.GetValueOnGameThread());
		return FMath::IsFinite(V) && V > 0.0 ? V : 0.0;
#else
		return 0.0;
#endif
	}

	/** 자동 스냅숏 가라앉음 시뮬레이션 초 (음수·수가 아닌 값은 기본 3). */
	double AutoSnapshotSettleSeconds()
	{
#if !UE_BUILD_SHIPPING
		const double V = static_cast<double>(CVarAutoSnapshotSettle.GetValueOnGameThread());
		return FMath::IsFinite(V) && V >= 0.0 ? V : 3.0;
#else
		return 3.0;
#endif
	}

	FString AutoSnapshotOutFolder()
	{
#if !UE_BUILD_SHIPPING
		return CVarAutoSnapshotOut.GetValueOnGameThread().TrimStartAndEnd();
#else
		return FString();
#endif
	}

	/**
	 * 바꿔 끼우기 쓰기: '<경로>.tmp' 에 다 쓴 뒤 '<경로>' 로 옮긴다 (이름 안 *.json 만 보는 파이썬 감시가 반쯤 쓴 파일을 읽지 않게).
	 * 실패하면 .tmp 를 지우고 거짓.
	 */
	bool SaveAtomic(const FString& Text, const FString& Path)
	{
		IFileManager& Files = IFileManager::Get();
		Files.MakeDirectory(*FPaths::GetPath(Path), /*Tree*/ true);
		const FString Tmp = Path + TEXT(".tmp");
		if (!FFileHelper::SaveStringToFile(Text, *Tmp, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)
			|| !Files.Move(*Path, *Tmp, /*Replace*/ true, /*EvenIfReadOnly*/ true))
		{
			Files.Delete(*Tmp, /*RequireExists*/ false, /*EvenReadOnly*/ true, /*Quiet*/ true);
			return false;
		}
		return true;
	}

	TArray<TSharedPtr<FJsonValue>> Nums(std::initializer_list<double> Values)
	{
		TArray<TSharedPtr<FJsonValue>> Out;
		for (const double V : Values)
		{
			Out.Add(MakeShared<FJsonValueNumber>(V));
		}
		return Out;
	}

	TArray<TSharedPtr<FJsonValue>> NumArray(const std::vector<double>& Values)
	{
		TArray<TSharedPtr<FJsonValue>> Out;
		Out.Reserve(static_cast<int32>(Values.size()));
		for (const double V : Values)
		{
			Out.Add(MakeShared<FJsonValueNumber>(V));
		}
		return Out;
	}

	TArray<TSharedPtr<FJsonValue>> Triples(const std::vector<double>& Flat)
	{
		TArray<TSharedPtr<FJsonValue>> Out;
		for (size_t k = 0; k + 2 < Flat.size(); k += 3)
		{
			Out.Add(MakeShared<FJsonValueArray>(Nums({Flat[k], Flat[k + 1], Flat[k + 2]})));
		}
		return Out;
	}

	template <typename T, size_t N>
	TArray<TSharedPtr<FJsonValue>> IntArray(const T (&Values)[N])
	{
		TArray<TSharedPtr<FJsonValue>> Out;
		for (size_t i = 0; i < N; ++i)
		{
			Out.Add(MakeShared<FJsonValueNumber>(static_cast<double>(Values[i])));
		}
		return Out;
	}

	/** 도망 기록 창·두뇌 판 합 (EcoV3Flight::FSum — 끝난 도망만, 열린 도망 없음. 초 = 결정 스텝 × 2/15). */
	TSharedRef<FJsonObject> FlightSumJson(const EcoV3Flight::FSum& S)
	{
		TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
		J->SetNumberField(TEXT("started"), static_cast<double>(S.Started));
		J->SetNumberField(TEXT("ended"), static_cast<double>(S.Ended));
		J->SetNumberField(TEXT("ended_steps"), static_cast<double>(S.EndedSteps));
		J->SetNumberField(TEXT("own_n"), static_cast<double>(S.OwnN()));
		J->SetNumberField(TEXT("own_steps"), static_cast<double>(S.OwnSteps));
		J->SetNumberField(TEXT("own_contact"), static_cast<double>(S.OwnContact));
		TSharedRef<FJsonObject> Own = MakeShared<FJsonObject>();
		for (int32 c = 0; c < EcoWorldV3::kNumFlightOwn; ++c)
		{
			Own->SetNumberField(UTF8_TO_TCHAR(EcoWorldV3::FlightCauseName(c)), static_cast<double>(S.Own[c]));
		}
		J->SetObjectField(TEXT("own"), Own);
		J->SetNumberField(TEXT("unsafe"), static_cast<double>(S.Unsafe));
		J->SetNumberField(TEXT("mean_seconds"), S.MeanSeconds());
		J->SetNumberField(TEXT("own_chase_seconds"), S.OwnChaseSeconds());
		J->SetNumberField(TEXT("own_share"), S.OwnShare());
		// 10-23 쫓긴 도망 중 숨음·잡힘 (옛 도망 단위 1차 숨음 비율·GH — 10-24 부터 보고만, EcoV3FlightTally.h)
		J->SetNumberField(TEXT("chased"), static_cast<double>(S.Chased));
		J->SetNumberField(TEXT("hidden"), static_cast<double>(S.Hidden));
		J->SetNumberField(TEXT("caught"), static_cast<double>(S.Caught));
		J->SetNumberField(TEXT("hide_share"), S.HideShare());
		J->SetNumberField(TEXT("caught_share"), S.CaughtShare());
		// 10-24 닫힌 쫓김 사건 (관문 1차 사건 숨음 비율·지킴 GH 와 같은 몫 — 화면 '쫓긴 사건 중 숨음·잡힘', EcoV3FlightTally.h)
		J->SetNumberField(TEXT("ep_started"), static_cast<double>(S.EpStarted));
		J->SetNumberField(TEXT("ep_ended"), static_cast<double>(S.EpEnded));
		J->SetNumberField(TEXT("ep_chased"), static_cast<double>(S.EpChased));
		J->SetNumberField(TEXT("ep_hidden"), static_cast<double>(S.EpHidden));
		J->SetNumberField(TEXT("ep_caught"), static_cast<double>(S.EpCaught));
		J->SetNumberField(TEXT("ep_hide_share"), S.EpHideShare());
		J->SetNumberField(TEXT("ep_caught_share"), S.EpCaughtShare());
		return J;
	}

	const TCHAR* WeatherName(int32 Kind)
	{
		static const TCHAR* const Names[EcoWorldV3::kNumWeatherKinds] = {TEXT("clear"), TEXT("rain"), TEXT("snow")};
		return Names[FMath::Clamp(Kind, 0, EcoWorldV3::kNumWeatherKinds - 1)];
	}

	/** 스냅숏 env.big (10-27 '큰 변화만' — 쓰는 순간의 기준선·대칭차·날씨 종류·묶기·기다림. 규칙 1 일 때만). */
	TSharedRef<FJsonObject> BigJson(const EcoV3BigChange::FState& B, const EcoV3BigChange::FConfig& C, int64 Step, bool bHold)
	{
		const EcoV3BigChange::FDecision D = EcoV3BigChange::Evaluate(B, C, Step, bHold);
		TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
		J->SetNumberField(TEXT("baseline_step"), static_cast<double>(B.BaselineStep));
		J->SetNumberField(TEXT("big_trees"), FMath::Max(1, C.BigTrees));
		J->SetNumberField(TEXT("weather_hold_s"), C.WeatherHoldSeconds);
		J->SetNumberField(TEXT("settle_s"), C.SettleSeconds);
		J->SetNumberField(TEXT("max_wait_s"), C.MaxWaitSeconds);
		TSharedRef<FJsonObject> Trees = MakeShared<FJsonObject>();
		TSharedRef<FJsonObject> Weather = MakeShared<FJsonObject>();
		for (const EcoV3BigChange::FRegion& R : B.Regions)
		{
			Trees->SetNumberField(R.RegionId.ToString(), R.TreeDiff());
			TSharedRef<FJsonObject> W = MakeShared<FJsonObject>();
			W->SetStringField(TEXT("base"), WeatherName(R.BaseKind));
			W->SetStringField(TEXT("now"), WeatherName(R.NowKind));
			W->SetNumberField(TEXT("held_s"), R.NowKind != R.BaseKind ? EcoV3BigChange::StepsToSeconds(Step - R.KindSinceStep) : 0.0);
			Weather->SetObjectField(R.RegionId.ToString(), W);
		}
		J->SetObjectField(TEXT("trees"), Trees);
		J->SetObjectField(TEXT("weather"), Weather);
		J->SetBoolField(TEXT("condition"), D.bCondition);
		J->SetNumberField(TEXT("quiet_s"), D.QuietSeconds);
		J->SetNumberField(TEXT("held_s"), D.WaitSeconds);
		J->SetBoolField(TEXT("level_change_hold"), bHold);
		J->SetBoolField(TEXT("capped"), D.bCapped);
		return J;
	}

	/** 지역 세계 설정 값 (파이썬 거울 설정과 하나씩 견줄 칸 — adapt.py 변환표). */
	TSharedRef<FJsonObject> WorldConfigJson(const EcoWorldV3::FWorldState& W)
	{
		const EcoWorldV3::FWorldConfig& C = W.Config;
		TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
		J->SetNumberField(TEXT("world_size"), C.WorldSize);
		J->SetNumberField(TEXT("seed"), static_cast<double>(C.Seed));
		J->SetNumberField(TEXT("rng_stream"), static_cast<double>(C.RngStream));
		J->SetNumberField(TEXT("num_herbivores"), C.NumHerbivores);
		J->SetNumberField(TEXT("num_stalkers"), C.NumStalkers);
		J->SetNumberField(TEXT("num_chasers"), C.NumChasers);
		J->SetNumberField(TEXT("num_ranged"), C.NumRanged);
		J->SetNumberField(TEXT("num_nocturnal"), C.NumNocturnal);
		J->SetBoolField(TEXT("player_proxy"), C.bPlayerProxy);
		J->SetNumberField(TEXT("pred_speed_mult"), C.PredSpeedMult);
		J->SetNumberField(TEXT("pred_eat_cd"), W.ThreatCfg.PredEatCd);
		J->SetBoolField(TEXT("eat_in_place"), C.bEatInPlace);
		J->SetBoolField(TEXT("realism_night"), C.bRealismNight);
		J->SetBoolField(TEXT("respawn_dead"), C.bRespawnDead);
		J->SetNumberField(TEXT("pred_ema_denominator"), C.PredEmaDenominator);
		J->SetNumberField(TEXT("day_period"), C.DayPeriod);
		J->SetNumberField(TEXT("day_offset"), C.DayOffset);
		J->SetNumberField(TEXT("twilight_steps"), C.TwilightSteps);
		J->SetBoolField(TEXT("shelter_safe"), C.bShelterSafe);
		J->SetNumberField(TEXT("shelter_wolf_margin"), C.ShelterWolfMargin);
		J->SetBoolField(TEXT("protected_refuges"), C.bProtectedRefuges);
		J->SetArrayField(TEXT("world_allowed"), IntArray(C.WorldAllowed));
		{
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetNumberField(TEXT("cell"), C.FoodCell);
			F->SetNumberField(TEXT("patch_blur"), C.FoodPatchBlur);
			F->SetNumberField(TEXT("patch_threshold"), C.FoodPatchThreshold);
			F->SetNumberField(TEXT("grad_blur"), C.FoodGradBlur);
			F->SetNumberField(TEXT("regen_base"), C.FoodRegenBase);
			F->SetNumberField(TEXT("regen_mult"), C.FoodRegenMult);
			F->SetNumberField(TEXT("cover_regen_mult"), C.FoodCoverRegenMult);
			J->SetObjectField(TEXT("food_rules"), F);
		}
		{
			const EcoWorldV3::FWildFlightConfig& K = C.WildFlight;
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("enabled"), K.bEnabled);
			F->SetNumberField(TEXT("alert_r"), K.AlertR);
			F->SetNumberField(TEXT("flight_r"), K.FlightR);
			F->SetNumberField(TEXT("safe_r"), K.SafeR);
			F->SetNumberField(TEXT("approach"), K.Approach);
			F->SetNumberField(TEXT("alert_w"), K.AlertW);
			F->SetBoolField(TEXT("rest_alert"), K.bRestAlert);
			F->SetNumberField(TEXT("shelter_cos"), K.ShelterCos);
			F->SetNumberField(TEXT("shelter_r"), K.ShelterR);
			F->SetBoolField(TEXT("crouch"), K.bCrouch);
			F->SetNumberField(TEXT("wall_margin"), K.WallMargin);
			F->SetBoolField(TEXT("hold_awake"), K.bHoldAwake);
			F->SetNumberField(TEXT("edge_r"), K.EdgeR);
			// 10-24 두 길 두뇌 (더하기만 — 기록. 세계 설정이 아니라 지금 두뇌가 정한 값이다: 판 4·5 두뇌면 route 참, 판 5 면 brain_flee_outside_reflex 거짓.
			// 파이썬 이름 그대로 — ceval.world_block 의 wild_flight.route·brain_flee_outside_reflex. adapt.py 는 FEATURE_MAPS 밖이라 읽지 않는다)
			F->SetBoolField(TEXT("route"), K.bRoute);
			F->SetBoolField(TEXT("brain_flee_outside_reflex"), !W.bFleeGate);
			// 10-27 거리 두기(쉬는 늑대) (더하기만 — 파이썬 선택 키 wild_flight.rest_keep* 이름 그대로, adapt.FEATURE_MAPS·ceval.world_block 이 옮긴다)
			F->SetBoolField(TEXT("rest_keep"), K.bRestKeep);
			F->SetNumberField(TEXT("rest_keep_margin"), K.RestKeepMargin);
			F->SetNumberField(TEXT("rest_keep_band"), K.RestKeepBand);
			F->SetBoolField(TEXT("rest_keep_asleep"), K.bRestKeepAsleep);
			J->SetObjectField(TEXT("wild_flight"), F);
		}
		{
			// 10-27 먹기 걷기 고침 (더하기만 — 실제로 쓰는 W.RepCfg 값. 파이썬 선택 키 repertoire.graze_* 이름 그대로, adapt.FEATURE_MAPS 'graze_calm')
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetNumberField(TEXT("graze_edge_r"), W.RepCfg.GrazeEdgeR);
			F->SetNumberField(TEXT("graze_edge_w"), W.RepCfg.GrazeEdgeW);
			F->SetNumberField(TEXT("graze_inertia"), W.RepCfg.GrazeInertia);
			F->SetNumberField(TEXT("graze_wall_margin"), W.RepCfg.GrazeWallMargin);
			J->SetObjectField(TEXT("graze_calm"), F);
		}
		{
			const EcoWorldV3::FWildReserveConfig& R = C.WildReserve;
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("enabled"), R.bEnabled);
			F->SetNumberField(TEXT("reserve_days"), R.ReserveDays);
			F->SetNumberField(TEXT("init"), R.Init);
			F->SetNumberField(TEXT("refill_e"), R.RefillE);
			F->SetNumberField(TEXT("refill_frac"), R.RefillFrac);
			F->SetNumberField(TEXT("weak_e"), R.WeakE);
			F->SetNumberField(TEXT("weak_speed"), R.WeakSpeed);
			J->SetObjectField(TEXT("wild_reserve"), F);
		}
		{
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("enabled"), C.WildSatiation.bEnabled);
			F->SetNumberField(TEXT("sat_days"), C.WildSatiation.SatDays);
			F->SetNumberField(TEXT("rest_speed"), C.WildSatiation.RestSpeed);
			J->SetObjectField(TEXT("wild_satiation"), F);
		}
		{
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("enabled"), C.RealismVision.bEnabled);
			F->SetNumberField(TEXT("threat_fov_deg"), C.RealismVision.ThreatFovDeg);
			J->SetObjectField(TEXT("realism_vision"), F);
		}
		{
			const EcoObservationV3::FHearingConfig& H = C.RealismHearing;
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("enabled"), H.bEnabled);
			F->SetNumberField(TEXT("s_silent"), H.SSilent);
			F->SetNumberField(TEXT("s_quiet"), H.SQuiet);
			F->SetNumberField(TEXT("s_loud"), H.SLoud);
			F->SetNumberField(TEXT("r_quiet"), H.RQuiet);
			F->SetNumberField(TEXT("r_loud"), H.RLoud);
			F->SetBoolField(TEXT("roam_quiet"), H.bRoamQuiet);
			F->SetBoolField(TEXT("cap_to_sight"), H.bCapToSight);
			J->SetObjectField(TEXT("realism_hearing"), F);
		}
		{
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("enabled"), C.ShelterFood.bEnabled);
			F->SetNumberField(TEXT("cap_frac"), C.ShelterFood.CapFrac);
			F->SetNumberField(TEXT("regen_frac"), C.ShelterFood.RegenFrac);
			J->SetObjectField(TEXT("shelter_food"), F);
		}
		{
			const EcoThreatV3::FPackHuntConfig& P = C.PackHunt;
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("enabled"), P.bEnabled);
			F->SetNumberField(TEXT("join_r"), P.JoinR);
			F->SetNumberField(TEXT("lead"), P.Lead);
			F->SetNumberField(TEXT("door_r"), P.DoorR);
			F->SetNumberField(TEXT("door_cos"), P.DoorCos);
			F->SetNumberField(TEXT("wait_r"), P.WaitR);
			J->SetObjectField(TEXT("pack_hunt"), F);
		}
		{
			const EcoWorldV3::FObstacleConfig& O = C.Obstacles;
			const EcoThreatV3::FDetourConfig& D = O.Detour;
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("enabled"), O.bEnabled);
			F->SetNumberField(TEXT("body_r"), O.BodyR);
			F->SetBoolField(TEXT("block_sight"), O.bBlockSight);
			F->SetBoolField(TEXT("no_food"), O.bNoFood);
			F->SetBoolField(TEXT("detour"), D.bEnabled);
			F->SetNumberField(TEXT("detour_block"), D.BlockFrac);
			F->SetNumberField(TEXT("detour_free"), D.FreeFrac);
			F->SetNumberField(TEXT("detour_probe"), D.Probe);
			F->SetNumberField(TEXT("detour_steps"), D.MaxSteps);
			F->SetNumberField(TEXT("detour_help_block"), D.HelpBlock);
			F->SetNumberField(TEXT("detour_help_drop"), D.HelpDrop);
			// 10-22 숲 시야 (더하기만 — 나무 표는 지역 obstacles.foliage_trees)
			F->SetBoolField(TEXT("foliage"), O.Foliage.bEnabled);
			F->SetNumberField(TEXT("foliage_r"), O.Foliage.R);
			F->SetNumberField(TEXT("foliage_block"), O.Foliage.Block);
			J->SetObjectField(TEXT("obstacle_rules"), F);
		}
		{
			const EcoWorldV3::FWeatherConfig& Wx = C.Weather;
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("enabled"), Wx.bEnabled);
			F->SetStringField(TEXT("kind"), WeatherName(Wx.Kind));
			F->SetNumberField(TEXT("intensity"), Wx.Intensity);
			F->SetNumberField(TEXT("rain_sight"), Wx.RainSight);
			F->SetNumberField(TEXT("rain_hear"), Wx.RainHear);
			F->SetNumberField(TEXT("snow_sight"), Wx.SnowSight);
			F->SetNumberField(TEXT("snow_hear"), Wx.SnowHear);
			F->SetNumberField(TEXT("snow_deer_speed"), Wx.SnowDeerSpeed);
			F->SetNumberField(TEXT("snow_wolf_speed"), Wx.SnowWolfSpeed);
			F->SetBoolField(TEXT("obs_visibility"), Wx.bObsVisibility);
			F->SetNumberField(TEXT("schedule_rows"), static_cast<double>(Wx.Schedule.size()));
			J->SetObjectField(TEXT("weather"), F);
		}
		return J;
	}

	/** 통합 설정 스위치 (콘솔 변수에서 읽은 값 — 파이썬 변환이 기능 블록 켬·끔과 견준다). */
	TSharedRef<FJsonObject> SettingsJson(const FEcoV3IntegratedSettings& S)
	{
		TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
		J->SetNumberField(TEXT("seed"), static_cast<double>(S.Seed));
		J->SetNumberField(TEXT("deer_per_region"), S.DeerPerRegion);
		J->SetNumberField(TEXT("wolves_per_region"), S.WolvesPerRegion);
		J->SetNumberField(TEXT("stage_size_units"), S.StageSizeUnits);
		J->SetNumberField(TEXT("pred_speed_mult"), S.PredSpeedMult);
		J->SetBoolField(TEXT("gradual_night"), S.bGradualNight);
		J->SetBoolField(TEXT("no_freeze"), S.bNoFreeze);
		J->SetBoolField(TEXT("protected_refuges"), S.bProtectedRefuges);
		J->SetBoolField(TEXT("social_control"), S.bSocialControl);
		J->SetNumberField(TEXT("wolf_eat_seconds"), S.WolfEatSeconds);
		J->SetNumberField(TEXT("wolf_eat_steps"), S.WolfEatSteps());
		J->SetBoolField(TEXT("wild_flight"), S.bWildFlight);
		J->SetBoolField(TEXT("flight_hold_awake"), S.bFlightHoldAwake);
		J->SetBoolField(TEXT("flight_edge_avoid"), S.bFlightEdgeAvoid);
		J->SetBoolField(TEXT("rest_keep"), S.bRestKeep);     // 10-27 거리 두기 스위치 (세계 값은 지역 world.wild_flight.rest_keep*)
		J->SetBoolField(TEXT("graze_calm"), S.bGrazeCalm);   // 10-27 먹기 걷기 고침 스위치 (세계 값은 지역 world.graze_calm)
		J->SetNumberField(TEXT("alert_dist_m"), S.AlertDistM);
		J->SetNumberField(TEXT("panic_dist_m"), S.PanicDistM);
		J->SetNumberField(TEXT("safe_dist_m"), S.SafeDistM);
		J->SetBoolField(TEXT("wild_reserve"), S.bWildReserve);
		J->SetBoolField(TEXT("wild_satiation"), S.bWildSatiation);
		J->SetBoolField(TEXT("realism_vision"), S.bRealismVision);
		J->SetBoolField(TEXT("realism_hearing"), S.bRealismHearing);
		J->SetBoolField(TEXT("shelter_safe"), S.bShelterSafe);
		J->SetNumberField(TEXT("wolf_body_margin_m"), S.WolfBodyMarginM);
		J->SetBoolField(TEXT("shelter_food"), S.bShelterFood);
		J->SetBoolField(TEXT("pack_hunt"), S.bPackHunt);
		J->SetBoolField(TEXT("obstacles"), S.bObstacles);
		J->SetBoolField(TEXT("obstacle_detour"), S.bObstacleDetour);
		J->SetBoolField(TEXT("foliage"), S.bFoliage);   // 10-22 숲 시야 스위치 (세계 값은 지역 world.obstacle_rules.foliage*)
		J->SetBoolField(TEXT("obstacle_import"), !S.ObstacleImportPath.IsEmpty());
		J->SetBoolField(TEXT("stage_trees"), S.bStageTrees);
		J->SetBoolField(TEXT("weather"), S.bWeather);
		J->SetStringField(TEXT("weather_forest"), S.WeatherForest);
		J->SetStringField(TEXT("weather_highland"), S.WeatherHighland);
		J->SetStringField(TEXT("weather_barren"), S.WeatherBarren);
		J->SetNumberField(TEXT("extra_cover_count"), S.ExtraCoverCount);
		J->SetNumberField(TEXT("extra_cover_radius_frac"), S.ExtraCoverRadiusFrac);
		J->SetNumberField(TEXT("wolf_start_corner_frac"), S.WolfStartCornerFrac);
		J->SetNumberField(TEXT("wolf_min_start_dist_cm"), S.WolfMinStartDistCm);
		J->SetNumberField(TEXT("deer_min_spacing_cm"), S.DeerMinSpacingCm);
		return J;
	}
}

FString UEcoPolicyV3IntegratedSubsystem::SnapshotPath(const FString& Out) const
{
	const FString Name = FString::Printf(TEXT("eco_v3_snapshot_s%lld_t%lld.json"), static_cast<long long>(Settings.Seed), static_cast<long long>(GlobalT));
	const FString Trimmed = Out.TrimStartAndEnd();
	if (Trimmed.IsEmpty())
	{
		return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("EcoSnapshots"), Name));
	}
	FString P = FPaths::IsRelative(Trimmed) ? FPaths::Combine(FPaths::ProjectDir(), Trimmed) : Trimmed;
	if (!P.EndsWith(TEXT(".json"), ESearchCase::IgnoreCase))
	{
		P = FPaths::Combine(P, Name);
	}
	return FPaths::ConvertRelativePathToFull(P);
}

bool UEcoPolicyV3IntegratedSubsystem::ExportSnapshot(const FString& Path, const FString& Why, const TCHAR* Trigger) const
{
	using namespace EcoV3SnapshotImpl;
	for (const auto& Ctx : Contexts)
	{
		if (Ctx->Sim.Food.Vegetation.bEnabled||Ctx->Sim.Config.bEcosystemLife)
		{
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoVegetation] RL snapshot v1 rejected: soil/life world requires the separate ecosystem evaluation schema and a complete Python mirror."));
			return false;
		}
	}
	if (Path.IsEmpty() || Contexts.Num() == 0)
	{
		return false;
	}
	const UWorld* World = GetWorld();
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("format"), TEXT("eco_v3_snapshot"));
	Root->SetNumberField(TEXT("version"), 1);
	Root->SetStringField(TEXT("units"), TEXT("stage units, 1 unit = 200 cm, x·y from stage origin; 1 step = 2/15 s; food grid row-major (k = iy·gw + ix)"));
	Root->SetNumberField(TEXT("step_seconds"), EcoRepertoireV3::kStepSeconds);
	Root->SetStringField(TEXT("map"), World ? UWorld::RemovePIEPrefix(World->GetMapName()) : FString());
	Root->SetStringField(TEXT("net_mode"), !World ? TEXT("none") : World->GetNetMode() == NM_Standalone ? TEXT("standalone") : TEXT("server"));
	Root->SetNumberField(TEXT("session_seed"), static_cast<double>(Settings.Seed));
	Root->SetNumberField(TEXT("global_step"), static_cast<double>(GlobalT));
	Root->SetNumberField(TEXT("sim_seconds"), static_cast<double>(GlobalT) * EcoRepertoireV3::kStepSeconds);
	Root->SetStringField(TEXT("why"), Why);
	Root->SetStringField(TEXT("play_id"), PlayId);   // 적응 고리 Play 번호 (끄면 빈 값 — 파이썬이 두뇌 파일 adapt.play_id 로 돌려준다)
	Root->SetStringField(TEXT("contract_hash"), FString::Printf(TEXT("0x%016llx"), static_cast<unsigned long long>(EcoPolicyV3::kContractHash)));
	Root->SetStringField(TEXT("tree_layout"), FString::Printf(TEXT("%s %s"), UTF8_TO_TCHAR(EcoTreeLayoutV3::kVersion), UTF8_TO_TCHAR(EcoTreeLayoutV3::kDigest)));
	{
		const FEcoV3Brain& B = GetActiveBrain();
		TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
		J->SetStringField(TEXT("id"), B.Id);
		J->SetStringField(TEXT("model"), B.ModelName);
		J->SetStringField(TEXT("model_path"), B.ModelPath);
		J->SetStringField(TEXT("model_sha256"), B.ModelSha256);
		J->SetStringField(TEXT("weights_sha256"), B.WeightsSha256);
		J->SetBoolField(TEXT("builtin"), B.bBuiltin);
		J->SetStringField(TEXT("train_world"), B.TrainWorld);
		J->SetStringField(TEXT("source_file"), B.SourceFile.IsEmpty() ? FString() : FPaths::GetCleanFilename(B.SourceFile));
		J->SetArrayField(TEXT("allowed"), IntArray(B.Allowed));
		J->SetNumberField(TEXT("last_swap_step"), static_cast<double>(LastBrainSwapStep));
		// 두뇌의 입출력 계약 (10-19 R5: 관측 18 또는 21 — 위 contract_hash 는 빌드 내장 계약)
		J->SetStringField(TEXT("contract_hash"), FString::Printf(TEXT("0x%016llx"), static_cast<unsigned long long>(B.ContractHash)));
		J->SetNumberField(TEXT("obs_dim"), B.ObsDim);
		// 10-24 두 길 두뇌 (더하기만): 마스크 판 (2·4·5), 길·반사 밖 FLEE 막음 (판 4·5 / 판 5 — 지역 world.wild_flight.route·brain_flee_outside_reflex 가 실제로 건 값)
		J->SetNumberField(TEXT("mask_version"), B.MaskVersion);
		J->SetBoolField(TEXT("route"), B.bRoute());
		J->SetBoolField(TEXT("flee_gate"), B.bFleeGate());
		// 적응 고리 판 (10-21, LIVE_ADAPT_SPEC.md 2절): 지금 두뇌 파일의 'adapt' 블록 (판·시도·실행·바탕 스냅숏). 블록이 없는 두뇌(내장·손 파일)는 빈 객체
		{
			TSharedRef<FJsonObject> A = MakeShared<FJsonObject>();
			if (B.bAdapt)
			{
				A->SetNumberField(TEXT("round"), B.AdaptRound);
				A->SetNumberField(TEXT("attempt"), B.AdaptAttempt);
				A->SetStringField(TEXT("run"), B.AdaptRun);
				A->SetStringField(TEXT("snapshot"), B.AdaptSnapshot);
			}
			J->SetObjectField(TEXT("adapt"), A);
		}
		Root->SetObjectField(TEXT("brain"), J);
	}
	Root->SetObjectField(TEXT("settings"), SettingsJson(Settings));
	{
		// 환경 바뀜 (10-21, LIVE_ADAPT_SPEC.md 2절 — EcoV3EnvWatch.cpp): 감시·환경 판(Play 시작부터 넣은 묶음 수, 0 = 그대로)·마지막·처음 바뀐 스텝·이 스냅숏의 계기·
		// Play 시작부터 넣은 바뀜 (오래된 것부터). 파이썬은 'env' 가 없으면 판 0 으로 읽는다
		TSharedRef<FJsonObject> E = MakeShared<FJsonObject>();
		E->SetBoolField(TEXT("watch"), IsEnvWatchEnabled());
		E->SetNumberField(TEXT("revision"), EnvRevision);
		E->SetNumberField(TEXT("changed_step"), static_cast<double>(EnvChangedStep));
		E->SetNumberField(TEXT("first_changed_step"), static_cast<double>(EnvFirstChangedStep));
		E->SetStringField(TEXT("trigger"), Trigger ? Trigger : TEXT("console"));
		TArray<TSharedPtr<FJsonValue>> Changes;
		for (const FEcoV3EnvChange& Ch : EnvChanges)
		{
			TSharedRef<FJsonObject> C = MakeShared<FJsonObject>();
			C->SetNumberField(TEXT("revision"), Ch.Revision);
			C->SetNumberField(TEXT("step"), static_cast<double>(Ch.Step));
			C->SetNumberField(TEXT("seconds"), Ch.Seconds);
			C->SetStringField(TEXT("region"), Ch.Region.ToString());
			C->SetStringField(TEXT("kind"), Ch.Kind);
			C->SetStringField(TEXT("detail"), Ch.Detail);
			C->SetStringField(TEXT("source"), Ch.Source);
			Changes.Add(MakeShared<FJsonValueObject>(C));
		}
		E->SetArrayField(TEXT("changes"), Changes);
		// 10-27 (더하기만 — 파이썬은 모르는 칸을 읽지 않는다): 자동 스냅숏 규칙, 큰 변화 셈 (규칙 1), 숲 자람 모드 (켰을 때만)
		const int32 Rule = AutoSnapshotRule();
		E->SetStringField(TEXT("rule"), Rule == 1 ? TEXT("big") : TEXT("each"));
		if (Rule == 1)
		{
			E->SetObjectField(TEXT("big"), BigJson(BigState, BigChangeConfig(), GlobalT, IsLevelChangeHeld()));
		}
		if (bForestOn)
		{
			TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
			F->SetBoolField(TEXT("on"), true);
			F->SetStringField(TEXT("region"), ForestSettings.Region.ToString());
			F->SetNumberField(TEXT("target"), ForestSettings.Target);
			F->SetNumberField(TEXT("planned"), ForestSlots.Num());
			F->SetNumberField(TEXT("mature"), ForestMatureCount());
			F->SetNumberField(TEXT("saplings"), ForestSaplingCount());
			F->SetNumberField(TEXT("per_stage"), ForestSettings.PerStage);
			F->SetNumberField(TEXT("start_seconds"), ForestSettings.StartSeconds);
			F->SetNumberField(TEXT("stage_seconds"), ForestSettings.StageSeconds);
			F->SetNumberField(TEXT("grow_seconds"), ForestSettings.GrowSeconds);
			F->SetNumberField(TEXT("next_mature_step"), static_cast<double>(ForestNextMatureStep()));
			F->SetBoolField(TEXT("done"), !IsForestGrowing());
			E->SetObjectField(TEXT("forest"), F);
		}
		Root->SetObjectField(TEXT("env"), E);
	}

	TArray<TSharedPtr<FJsonValue>> Regions;
	for (const TUniquePtr<FEcoV3RegionContext>& CtxPtr : Contexts)
	{
		const FEcoV3RegionContext& Ctx = *CtxPtr;
		const EcoWorldV3::FWorldState& W = Ctx.Sim;
		TSharedRef<FJsonObject> R = MakeShared<FJsonObject>();
		R->SetStringField(TEXT("region"), Ctx.RegionId.ToString());
		R->SetNumberField(TEXT("region_index"), Ctx.RegionRuntimeIndex);
		R->SetNumberField(TEXT("size"), Ctx.SizeUnits);
		R->SetArrayField(TEXT("origin_cm"), Nums({Ctx.OriginCm.X, Ctx.OriginCm.Y, Ctx.OriginCm.Z}));
		R->SetNumberField(TEXT("t"), static_cast<double>(W.T));
		R->SetNumberField(TEXT("dark"), W.Dark);
		R->SetNumberField(TEXT("steps_to_transition"), W.StepsToTransition);
		R->SetObjectField(TEXT("world"), WorldConfigJson(W));
		R->SetArrayField(TEXT("allowed"), IntArray(W.Allowed));
		{
			TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
			J->SetStringField(TEXT("kind"), WeatherName(W.WeatherKind));
			J->SetNumberField(TEXT("intensity"), W.WeatherIntensity);
			J->SetNumberField(TEXT("sight"), W.Weather.Sight);
			J->SetNumberField(TEXT("hear"), W.Weather.Hear);
			J->SetNumberField(TEXT("deer_speed"), W.Weather.DeerSpeed);
			J->SetNumberField(TEXT("wolf_speed"), W.Weather.WolfSpeed);
			R->SetObjectField(TEXT("weather_now"), J);
		}
		{
			std::vector<double> Flat;
			for (const EcoObservationV3::FCoverInput& Cv : W.Config.Covers)
			{
				Flat.push_back(Cv.X);
				Flat.push_back(Cv.Y);
				Flat.push_back(Cv.Radius);
			}
			R->SetArrayField(TEXT("covers"), Triples(Flat));
			R->SetNumberField(TEXT("team_covers"), Ctx.TeamCovers);
			R->SetNumberField(TEXT("skipped_team_covers"), Ctx.SkippedTeamCovers);
			R->SetNumberField(TEXT("extra_covers"), Ctx.ExtraCovers);
		}
		{
			const FEcoV3ObstacleScan& S = Ctx.ObstacleScan;
			TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
			// discs = 세계가 쓰는 원판 (장애물을 끈 세계는 빈 목록 — 세계가 원판을 읽지 않는다). scan_discs = 레벨에서 읽은 원판 (기록)
			J->SetArrayField(TEXT("discs"), Triples(W.Config.Obstacles.bEnabled ? W.Config.Obstacles.Discs : std::vector<double>()));
			J->SetArrayField(TEXT("scan_discs"), Triples(S.Discs));
			{
				// 10-22 숲 시야 나무 표 (discs 순서, 원판마다 나무 1·아님 0 — 세계가 쓰는 표. 표가 비면 모든 원판이 나무, 장애물을 끈 세계는 빈 목록)
				const EcoWorldV3::FObstacleConfig& Ob = W.Config.Obstacles;
				TArray<TSharedPtr<FJsonValue>> Trees;
				if (Ob.bEnabled)
				{
					for (int32 k = 0; k < Ob.Num(); ++k)
					{
						const bool bTree = Ob.Foliage.Trees.empty() || (k < static_cast<int32>(Ob.Foliage.Trees.size()) && Ob.Foliage.Trees[static_cast<size_t>(k)] != 0);
						Trees.Add(MakeShared<FJsonValueNumber>(bTree ? 1.0 : 0.0));
					}
				}
				J->SetArrayField(TEXT("foliage_trees"), Trees);
			}
			J->SetBoolField(TEXT("imported"), Ctx.bObstaclesImported);
			J->SetBoolField(TEXT("level_trees_on"), Ctx.bLevelTrees);
			J->SetNumberField(TEXT("level_trees"), S.LevelTrees);
			J->SetNumberField(TEXT("level_trees_snapped"), S.LevelTreesSnapped);
			J->SetNumberField(TEXT("level_trees_unmatched"), S.LevelTreesUnmatched);
			J->SetNumberField(TEXT("level_trunks"), Ctx.EnvLevelTrunks);   // 10-21: 지금 무대 안 줄기 막이 수 (은신처 원 안 포함 — 환경 감시가 읽은 값)
			J->SetNumberField(TEXT("stage_trees"), Ctx.Trees.Num());
			J->SetNumberField(TEXT("seen_meshes"), S.SeenMeshes);
			J->SetNumberField(TEXT("near_edge"), S.NearEdge);
			R->SetObjectField(TEXT("obstacles"), J);
		}
		{
			const EcoWorldV3::FFoodGrid& G = W.Food;
			TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
			J->SetNumberField(TEXT("cell"), W.Config.FoodCell);
			J->SetNumberField(TEXT("gw"), G.Gw);
			J->SetArrayField(TEXT("cap"), NumArray(G.Cap));
			J->SetArrayField(TEXT("food"), NumArray(G.Food));
			double CapTotal = 0.0;
			for (const double V : G.Cap)
			{
				CapTotal += V;
			}
			J->SetNumberField(TEXT("cap_total"), CapTotal);
			J->SetNumberField(TEXT("food_total"), G.Total());
			J->SetNumberField(TEXT("start_total"), Ctx.StartFood);
			J->SetNumberField(TEXT("eaten_total"), W.Stats.FoodEaten);
			R->SetObjectField(TEXT("food"), J);
		}
		{
			const int64 Caught = W.Stats.Caught;
			const int64 Starved = W.Stats.Starved;
			TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
			J->SetNumberField(TEXT("planned"), Ctx.PlannedDeer);
			J->SetNumberField(TEXT("adopted"), Ctx.AdoptedDeer);
			J->SetNumberField(TEXT("caught"), static_cast<double>(Caught));
			J->SetNumberField(TEXT("starved"), static_cast<double>(Starved));
			// 부활이 없으므로 지금 산 사슴 = 입양 − 잡힘 − 굶음 (프레임 끝 집계 alive_frame 은 같은 프레임 안 앞 스텝 값일 수 있다)
			J->SetNumberField(TEXT("alive"), static_cast<double>(FMath::Max<int64>(0, Ctx.AdoptedDeer - Caught - Starved)));
			J->SetNumberField(TEXT("alive_frame"), Ctx.AliveDeer);
			J->SetNumberField(TEXT("mean_energy"), Ctx.MeanEnergy);
			J->SetNumberField(TEXT("starving"), Ctx.StarvingDeer);
			J->SetNumberField(TEXT("caught_in_cover"), static_cast<double>(W.Stats.CaughtInCover));
			J->SetArrayField(TEXT("behavior_steps"), IntArray(W.Stats.BehaviorSteps));
			J->SetNumberField(TEXT("live_steps"), static_cast<double>(W.Stats.LiveDeerSteps));
			J->SetNumberField(TEXT("shelter_steps"), static_cast<double>(W.Stats.ShelterDeerSteps));
			R->SetObjectField(TEXT("deer"), J);
		}
		{
			TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
			J->SetNumberField(TEXT("planned"), Ctx.PlannedWolves);
			J->SetNumberField(TEXT("adopted"), Ctx.AdoptedWolves);
			J->SetNumberField(TEXT("now"), Ctx.Wolves);
			J->SetArrayField(TEXT("hunt_starts"), IntArray(W.Stats.HuntStarts));
			J->SetArrayField(TEXT("hunt_ends"), IntArray(W.Stats.HuntEnds));
			J->SetArrayField(TEXT("hunt_success"), IntArray(W.Stats.HuntSuccess));
			J->SetArrayField(TEXT("hunt_outside"), IntArray(W.Stats.HuntOutside));
			R->SetObjectField(TEXT("wolves"), J);
		}
		{
			// 야생 (w3) 도망 기록 (10-21, 더한 칸 — 앞 칸은 그대로). 앞 칸 = 파이썬 world.py flight_stats 와 같은 이름·정의 (지금 열린 도망은 truncated).
			// window = 최근 60 초에 끝난 도망, generation·prev_generation = 지금·바로 앞 두뇌 판 (EcoV3FlightTally.h). 기록을 세지 않는 세계는 on 거짓·모두 0
			const EcoWorldV3::FFlightReport F = EcoWorldV3::FlightReportOf(W.Stats.Flight, Ctx.FlightOpen);
			TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
			J->SetBoolField(TEXT("on"), Ctx.FlightOn());
			J->SetNumberField(TEXT("started"), static_cast<double>(F.Started));
			J->SetNumberField(TEXT("live_steps"), static_cast<double>(F.LiveSteps));
			J->SetNumberField(TEXT("flee_steps"), static_cast<double>(F.FleeSteps));
			J->SetNumberField(TEXT("reflex_steps"), static_cast<double>(F.ReflexSteps));
			auto ByCause = [](const int64* Values)
			{
				TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
				for (int32 c = 0; c < EcoWorldV3::kNumFlightCauses; ++c)
				{
					O->SetNumberField(UTF8_TO_TCHAR(EcoWorldV3::FlightCauseName(c)), static_cast<double>(Values[c]));
				}
				return O;
			};
			J->SetObjectField(TEXT("n"), ByCause(F.Num));
			J->SetObjectField(TEXT("steps"), ByCause(F.Steps));
			J->SetObjectField(TEXT("contact"), ByCause(F.Contact));
			J->SetNumberField(TEXT("own_n"), static_cast<double>(F.OwnN));
			J->SetNumberField(TEXT("own_steps"), static_cast<double>(F.OwnSteps));
			J->SetNumberField(TEXT("own_contact"), static_cast<double>(F.OwnContact));
			J->SetNumberField(TEXT("shelter_end"), static_cast<double>(F.ShelterEnd));
			if (W.Config.Obstacles.FoliageConfigured())
			{
				// 숲 시야 켠 세계만 (10-22, 파이썬 flight_stats 의 lost_foliage — 원판 놓침 가운데 잎 때문, 끈 세계에는 칸이 없다)
				TSharedRef<FJsonObject> L = MakeShared<FJsonObject>();
				L->SetNumberField(TEXT("n"), static_cast<double>(F.LostFoliage[0]));
				L->SetNumberField(TEXT("steps"), static_cast<double>(F.LostFoliage[1]));
				L->SetNumberField(TEXT("contact"), static_cast<double>(F.LostFoliage[2]));
				J->SetObjectField(TEXT("lost_foliage"), L);
			}
			J->SetArrayField(TEXT("hist"), IntArray(F.Hist));
			J->SetArrayField(TEXT("hist_edges"), IntArray(EcoWorldV3::kFlightHistSteps));
			{
				// 10-23 숨은 뒤 10 초 지켜보기 (파이썬 flight_stats 의 hide 와 같은 이름·정의 — EcoWorldV3.h 머리 주석)
				TSharedRef<FJsonObject> H = MakeShared<FJsonObject>();
				H->SetNumberField(TEXT("chased"), static_cast<double>(F.Chased));
				H->SetNumberField(TEXT("hidden"), static_cast<double>(F.Hidden));
				H->SetNumberField(TEXT("watching"), static_cast<double>(F.Watching));
				H->SetNumberField(TEXT("cover_then_caught"), static_cast<double>(F.CoverCaught));
				H->SetNumberField(TEXT("cover_then_starved"), static_cast<double>(F.CoverStarved));
				H->SetNumberField(TEXT("watch_steps"), EcoWorldV3::kFlightHideWatchSteps);
				J->SetObjectField(TEXT("hide"), H);
			}
			{
				// 10-24 쫓김 사건 (파이썬 flight_stats 의 episode 와 같은 이름·정의 — EcoWorldV3.h 머리 주석 '쫓김 사건'. 지금 열린 사건은 지켜본 만큼 숨음·잘림)
				TSharedRef<FJsonObject> E = MakeShared<FJsonObject>();
				const TPair<const TCHAR*, int64> EpFields[] = {
					{TEXT("started"), F.EpStarted}, {TEXT("chased"), F.EpChased}, {TEXT("hidden"), F.EpHidden}, {TEXT("caught"), F.EpCaught},
					{TEXT("starved"), F.EpStarved}, {TEXT("other"), F.EpOther}, {TEXT("truncated"), F.EpTruncated}, {TEXT("watching"), F.EpWatching},
					{TEXT("other_chased"), F.EpOtherChased}, {TEXT("joined"), F.EpJoined}, {TEXT("joined_cover"), F.EpJoinedCover},
					{TEXT("joined_other"), F.EpJoinedOther}, {TEXT("window_caught"), F.EpWindowCaught}, {TEXT("window_starved"), F.EpWindowStarved}};
				for (const TPair<const TCHAR*, int64>& Fd : EpFields)
				{
					E->SetNumberField(Fd.Key, static_cast<double>(Fd.Value));
				}
				E->SetNumberField(TEXT("link_cover_steps"), EcoWorldV3::kEpisodeLinkCoverSteps);
				E->SetNumberField(TEXT("link_other_steps"), EcoWorldV3::kEpisodeLinkOtherSteps);
				J->SetObjectField(TEXT("episode"), E);
			}
			if (Ctx.RouteSeen())
			{
				// 10-24 두 길 두뇌 도망 길 기록 (길 통계가 있는 세계만 — 파이썬 flight_stats 의 route = `_flight_route_block` 과 같은 이름·칸. 지금 열린 도망은 그 길의
				// truncated. 도망 길 칸(by_route 등)은 길을 켠 동안만 센다 — 두뇌를 바꿔 끈 뒤에는 그 앞까지)
				const EcoWorldV3::FFlightRouteReport Rr = EcoWorldV3::FlightRouteReportOf(W.Stats.Route, W.Stats.FlightRoute, Ctx.FlightOpen);
				auto Routes = [](const int64* V, int32 N)
				{
					TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
					for (int32 r = 0; r < N; ++r)
					{
						O->SetNumberField(UTF8_TO_TCHAR(EcoWorldV3::RouteName(r)), static_cast<double>(V[r]));
					}
					return O;
				};
				TSharedRef<FJsonObject> Rt = MakeShared<FJsonObject>();
				Rt->SetBoolField(TEXT("on"), Ctx.RouteOn());
				Rt->SetBoolField(TEXT("brain"), true);
				Rt->SetObjectField(TEXT("steps"), Routes(Rr.Route.Steps, EcoWorldV3::kNumRoutes));
				Rt->SetNumberField(TEXT("onsets"), static_cast<double>(Rr.Route.Onsets));
				Rt->SetNumberField(TEXT("onset_shelter"), static_cast<double>(Rr.Route.OnsetShelter));
				Rt->SetNumberField(TEXT("decisions"), static_cast<double>(Rr.Route.Decisions));
				Rt->SetNumberField(TEXT("redecide_feas"), static_cast<double>(Rr.Route.RedecideFeas));
				Rt->SetNumberField(TEXT("switches"), static_cast<double>(Rr.Route.Switches));
				Rt->SetObjectField(TEXT("invalid"), Routes(Rr.Route.Invalid, EcoWorldV3::kNumRoutes));
				Rt->SetObjectField(TEXT("picked"), Routes(Rr.Route.Picked, EcoWorldV3::kNumRoutes));
				Rt->SetNumberField(TEXT("choice"), static_cast<double>(Rr.Route.Choice));
				Rt->SetNumberField(TEXT("bad_shelter"), static_cast<double>(Rr.Route.BadShelter));
				TSharedRef<FJsonObject> By = MakeShared<FJsonObject>();
				for (int32 r = 0; r < EcoWorldV3::kNumFlightRouteRows; ++r)
				{
					TSharedRef<FJsonObject> One = MakeShared<FJsonObject>();
					One->SetObjectField(TEXT("n"), ByCause(Rr.N[r]));
					One->SetObjectField(TEXT("steps"), ByCause(Rr.Steps[r]));
					One->SetObjectField(TEXT("contact"), ByCause(Rr.Contact[r]));
					By->SetObjectField(UTF8_TO_TCHAR(EcoWorldV3::RouteName(r)), One);
				}
				Rt->SetObjectField(TEXT("by_route"), By);
				Rt->SetObjectField(TEXT("drop_obstacle"), Routes(Rr.DropObstacle, EcoWorldV3::kNumFlightRouteRows));
				Rt->SetObjectField(TEXT("chased_steps"), Routes(Rr.Chased, EcoWorldV3::kNumFlightRouteRows));
				Rt->SetObjectField(TEXT("hidden_steps"), Routes(Rr.Hidden, EcoWorldV3::kNumFlightRouteRows));
				Rt->SetNumberField(TEXT("refled"), static_cast<double>(Rr.Refled));
				Rt->SetNumberField(TEXT("refled_steps"), EcoWorldV3::kFlightRefleeSteps);
				if (W.Config.Obstacles.FoliageConfigured())
				{
					Rt->SetObjectField(TEXT("drop_foliage"), Routes(Rr.DropFoliage, EcoWorldV3::kNumFlightRouteRows));
				}
				// 화면 창 (최근 60 초 — FEcoV3RouteTally)
				const FEcoV3RouteSum Win = Ctx.RouteTally.Window();
				TSharedRef<FJsonObject> Wj = MakeShared<FJsonObject>();
				Wj->SetNumberField(TEXT("window_steps"), static_cast<double>(Ctx.RouteTally.WindowSteps()));
				Wj->SetNumberField(TEXT("run_steps"), static_cast<double>(Win.RunSteps));
				Wj->SetNumberField(TEXT("shelter_steps"), static_cast<double>(Win.ShelterSteps));
				Wj->SetNumberField(TEXT("decisions"), static_cast<double>(Win.Decisions));
				Wj->SetNumberField(TEXT("picked_shelter"), static_cast<double>(Win.PickedShelter));
				Wj->SetNumberField(TEXT("choice"), static_cast<double>(Win.Choice));
				Wj->SetNumberField(TEXT("invalid_shelter"), static_cast<double>(Win.Invalid));
				Rt->SetObjectField(TEXT("window"), Wj);
				J->SetObjectField(TEXT("route"), Rt);
			}
			const EcoV3Flight::FTally& T = Ctx.FlightTally;
			J->SetNumberField(TEXT("window_steps"), static_cast<double>(T.WindowSteps()));
			J->SetObjectField(TEXT("window"), FlightSumJson(T.Window()));
			J->SetObjectField(TEXT("generation"), FlightSumJson(T.CurrentGen()));
			J->SetObjectField(TEXT("prev_generation"), FlightSumJson(T.PrevGen));
			J->SetBoolField(TEXT("has_prev_generation"), T.bHasPrev);
			J->SetNumberField(TEXT("swaps"), T.Swaps);
			J->SetNumberField(TEXT("min_compare"), EcoV3Flight::kMinCompare);
			R->SetObjectField(TEXT("flight"), J);
		}
		Regions.Add(MakeShared<FJsonValueObject>(R));
	}
	Root->SetArrayField(TEXT("regions"), Regions);

	FString Text;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
	if (!FJsonSerializer::Serialize(Root, Writer))
	{
		return false;
	}
	return SaveAtomic(Text, Path);   // 10-21: 바꿔 끼우기 (.tmp 에 다 쓴 뒤 옮긴다)
}

void UEcoPolicyV3IntegratedSubsystem::MaybeScheduledSnapshot()
{
	if (bScheduledSnapshotDone || Contexts.Num() == 0)
	{
		return;
	}
	const float At = EcoV3SnapshotImpl::CVarSnapshotAt.GetValueOnGameThread();
	const double Seconds = static_cast<double>(GlobalT) * EcoRepertoireV3::kStepSeconds;
	if (!(At >= 0.0f) || Seconds + 1e-9 < static_cast<double>(At))
	{
		return;
	}
	bScheduledSnapshotDone = true;
	const FString Path = SnapshotPath(EcoV3SnapshotImpl::CVarSnapshotOut.GetValueOnGameThread());
	const FString Why = FString::Printf(TEXT("예정 eco.IntegratedV3.SnapshotAt %.1f"), At);
	if (ExportSnapshot(Path, Why, TEXT("scheduled")))
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 환경 스냅숏 | %.1f초 (전역 스텝 %lld) | %s | 지역 %d | 두뇌 %s | 계기 scheduled · 환경 판 #%d"), Seconds,
			   static_cast<long long>(GlobalT), *Path, Contexts.Num(), *GetActiveBrain().Id, EnvRevision);
	}
	else
	{
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 환경 스냅숏을 쓰지 못했다: %s"), *Path);
	}
}

FString UEcoPolicyV3IntegratedSubsystem::AdaptRootDir()
{
	FString Root;
#if !UE_BUILD_SHIPPING
	Root = EcoV3SnapshotImpl::CVarAdaptRoot.GetValueOnGameThread().TrimStartAndEnd().TrimQuotes();
#endif
	if (Root.IsEmpty())
	{
		Root = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("EcoAdapt"));
	}
	else if (FPaths::IsRelative(Root))
	{
		Root = FPaths::Combine(FPaths::ProjectDir(), Root);
	}
	Root = FPaths::ConvertRelativePathToFull(Root);
	FPaths::NormalizeDirectoryName(Root);
	return Root;
}

FString UEcoPolicyV3IntegratedSubsystem::AutoSnapshotDir()
{
	FString Dir = EcoV3SnapshotImpl::AutoSnapshotOutFolder();
	if (Dir.IsEmpty())
	{
		Dir = FPaths::Combine(AdaptRootDir(), TEXT("snapshots"));
	}
	else if (FPaths::IsRelative(Dir))
	{
		Dir = FPaths::Combine(FPaths::ProjectDir(), Dir);
	}
	return FPaths::ConvertRelativePathToFull(Dir);
}

FString UEcoPolicyV3IntegratedSubsystem::AutoSnapshotPath() const
{
	const FString Name = FString::Printf(TEXT("eco_v3_snapshot_s%lld_t%lld_e%d.json"), static_cast<long long>(Settings.Seed), static_cast<long long>(GlobalT),
										 EnvRevision);
	return FPaths::ConvertRelativePathToFull(FPaths::Combine(AutoSnapshotDir(), Name));
}

int32 UEcoPolicyV3IntegratedSubsystem::AutoSnapshotRule()
{
#if !UE_BUILD_SHIPPING
	return EcoV3SnapshotImpl::CVarAutoSnapshotRule.GetValueOnGameThread() != 0 ? 1 : 0;
#else
	return 0;
#endif
}

EcoV3BigChange::FConfig UEcoPolicyV3IntegratedSubsystem::BigChangeConfig()
{
	EcoV3BigChange::FConfig C;
#if !UE_BUILD_SHIPPING
	using namespace EcoV3SnapshotImpl;
	auto Seconds = [](float V, double Def) { return FMath::IsFinite(V) && V >= 0.0f ? static_cast<double>(V) : Def; };
	C.BigTrees = FMath::Max(1, CVarBigTrees.GetValueOnGameThread());
	C.WeatherHoldSeconds = Seconds(CVarWeatherHold.GetValueOnGameThread(), C.WeatherHoldSeconds);
	C.SettleSeconds = Seconds(CVarBigSettle.GetValueOnGameThread(), C.SettleSeconds);
	C.MaxWaitSeconds = Seconds(CVarBigMaxWait.GetValueOnGameThread(), C.MaxWaitSeconds);
#endif
	return C;
}

bool UEcoPolicyV3IntegratedSubsystem::IsAutoSnapshotOn()
{
	return EcoV3SnapshotImpl::AutoSnapshotOn();
}

void UEcoPolicyV3IntegratedSubsystem::BigAddRegion(const FEcoV3RegionContext& Ctx)
{
	EcoV3BigChange::AddRegion(BigState, Ctx.RegionId, Ctx.Sim.Config.Obstacles.Discs, Ctx.Sim.Config.Weather.Kind, GlobalT);
}

void UEcoPolicyV3IntegratedSubsystem::SetLevelChangeHold(FName Who, bool bOn)
{
	if (bOn)
	{
		LevelChangeHolds.Add(Who);
	}
	else
	{
		LevelChangeHolds.Remove(Who);
	}
}

bool UEcoPolicyV3IntegratedSubsystem::IsLevelChangeHeld(FString* OutWhat) const
{
	TArray<FString> What;
	if (IsForestGrowing())
	{
		What.Add(EcoV3SnapshotImpl::kForestHoldWhat);
	}
	for (const FName& Who : LevelChangeHolds)
	{
		What.Add(FString::Printf(TEXT("%s 이 끝날 때까지"), *Who.ToString()));
	}
	if (OutWhat)
	{
		*OutWhat = FString::Join(What, TEXT("·"));
	}
	return !What.IsEmpty();
}

FString UEcoPolicyV3IntegratedSubsystem::BigChangeStatusText() const
{
	if (AutoSnapshotRule() == 0)
	{
		return TEXT("다시 배우기: 환경 판마다 (eco.IntegratedV3.AutoSnapshotRule 0)");
	}
	FString What;
	const bool bHold = IsLevelChangeHeld(&What);
	return EcoV3BigChange::ProgressText(BigState, BigChangeConfig(), GlobalT, bHold, What);
}

FString UEcoPolicyV3IntegratedSubsystem::DescribeAutoSnapshot()
{
	using namespace EcoV3SnapshotImpl;
	const double Every = SnapshotEverySeconds();
	const EcoV3BigChange::FConfig Big = BigChangeConfig();
	FString Out = !AutoSnapshotOn() ? FString(TEXT("환경 바뀜 끔 (eco.IntegratedV3.AutoSnapshot — -1 이면 AutoAdapt 를 따른다)"))
				  : AutoSnapshotRule() == 1
					  ? FString::Printf(TEXT("큰 변화만 (eco.IntegratedV3.AutoSnapshotRule 1 — 한 지역 나무 %d 이상·날씨 종류 %.0f초 이상 바뀐 채, 바뀜이 %.0f초 멈춘 뒤 한 번, ")
										 TEXT("숲이 자라는 동안 기다림·상한 %.0f초, 세기만 바뀜은 셈·화면 알림 없음 — eco.IntegratedV3.EnvNoticeMinor)"),
										Big.BigTrees, Big.WeatherHoldSeconds, Big.SettleSeconds, Big.MaxWaitSeconds)
					  : FString::Printf(TEXT("환경 바뀜 켬 (eco.IntegratedV3.AutoSnapshotRule 0 — 판이 %.1f초 그대로면 판마다 한 번)"), AutoSnapshotSettleSeconds());
	Out += Every > 0.0 ? FString::Printf(TEXT(" · 주기 %.1f초"), Every) : FString(TEXT(" · 주기 끔"));
	if (AutoSnapshotOn() || Every > 0.0)
	{
		Out += FString::Printf(TEXT(" → %s"), *AutoSnapshotDir());
	}
	return Out;
}

void UEcoPolicyV3IntegratedSubsystem::MaybeAutoSnapshot()
{
	using namespace EcoV3SnapshotImpl;
	if (Contexts.Num() == 0)
	{
		return;
	}
	const double Seconds = static_cast<double>(GlobalT) * EcoRepertoireV3::kStepSeconds;
	// 1. 환경 바뀜
	//    규칙 0 (옛 동작): 마지막 환경 판이 가라앉음 초 동안 그대로이면 판마다 한 번 (레벨이 나무를 여럿 놓는 동안 판마다 쓰지 않게)
	//    규칙 1 (큰 변화만, 기본 — EcoV3BigChange.h): 나무 대칭차 ≥ BigTrees 또는 날씨 종류가 WeatherHold 넘게 바뀐 채 → 바뀜이 BigSettle 멈추고 '진행 중'이 아닐 때 한 번
	bool bEnvDue = false;
	FString BigWhy;
	const bool bBigRule = AutoSnapshotOn() && AutoSnapshotRule() == 1;
	if (AutoSnapshotOn() && !bBigRule && EnvRevision > AutoSnapshotRevision)
	{
		const double Since = static_cast<double>(GlobalT - EnvChangedStep) * EcoRepertoireV3::kStepSeconds;
		bEnvDue = Since + 1e-9 >= AutoSnapshotSettleSeconds();
	}
	if (bBigRule)
	{
		const EcoV3BigChange::FConfig Big = BigChangeConfig();
		FString HoldWhat;
		const bool bHold = IsLevelChangeHeld(&HoldWhat);
		const EcoV3BigChange::FDecision D = EcoV3BigChange::Tick(BigState, Big, GlobalT, bHold);
		if (D.bNewCondition)
		{
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 다시 배우기 조건 됨 | %.1f초 (전역 스텝 %lld) | %s | %s"), Seconds, static_cast<long long>(GlobalT),
				   *EcoV3BigChange::SummaryText(BigState, Big, GlobalT),
				   bHold ? *FString::Printf(TEXT("기다림: %s (상한 %.0f초)"), *HoldWhat, Big.MaxWaitSeconds)
						 : *FString::Printf(TEXT("바뀜이 %.0f초 멈추면 쓴다"), Big.SettleSeconds));
		}
		if (D.bWrite)
		{
			bEnvDue = true;
			BigWhy = FString::Printf(TEXT("큰 변화 — %s (기준 전역 스텝 %lld) · 바뀜 없이 %.1f초 · 조건 뒤 %.1f초%s"), *EcoV3BigChange::SummaryText(BigState, Big, GlobalT),
									 static_cast<long long>(BigState.BaselineStep), D.QuietSeconds, D.WaitSeconds,
									 D.bCapped ? *FString::Printf(TEXT(" · 기다림 상한 %.0f초 — '%s' 를 더 기다리지 않음"), Big.MaxWaitSeconds,
																  HoldWhat.IsEmpty() ? TEXT("바뀜이 멈추기") : *HoldWhat)
											   : TEXT(""));
		}
	}
	// 2. 주기: 켜거나 값을 바꾼 때부터 그 주기로 (늦었으면 지금부터 다시)
	bool bPeriodicDue = false;
	const double Every = SnapshotEverySeconds();
	if (Every <= 0.0)
	{
		PeriodicNextSeconds = -1.0;
		PeriodicEverySeen = 0.0;
	}
	else if (Every != PeriodicEverySeen || PeriodicNextSeconds < 0.0)
	{
		PeriodicEverySeen = Every;
		PeriodicNextSeconds = Seconds + Every;
	}
	else if (Seconds + 1e-9 >= PeriodicNextSeconds)
	{
		bPeriodicDue = true;
		PeriodicNextSeconds += Every;
		if (PeriodicNextSeconds <= Seconds)
		{
			PeriodicNextSeconds = Seconds + Every;
		}
	}
	if (!bEnvDue && !bPeriodicDue)
	{
		return;
	}
	if (bEnvDue)
	{
		AutoSnapshotRevision = EnvRevision;   // 판마다 한 번 (쓰기에 실패해도 다시 쓰지 않는다 — 다음 판·주기·콘솔로)
	}
	// 같은 경계에서 둘 다 되면 한 번만 쓴다 (계기 env_change — 이름이 같다)
	const TCHAR* Trigger = bEnvDue ? TEXT("env_change") : TEXT("periodic");
	const FString Path = AutoSnapshotPath();
	const FString Why = !BigWhy.IsEmpty() ? BigWhy
						: bEnvDue		  ? FString::Printf(TEXT("환경 바뀜 #%d 뒤 %.1f초 그대로 (eco.IntegratedV3.AutoSnapshot)"), EnvRevision,
															static_cast<double>(GlobalT - EnvChangedStep) * EcoRepertoireV3::kStepSeconds)
										  : FString::Printf(TEXT("주기 eco.IntegratedV3.SnapshotEvery %.1f"), Every);
	const bool bWritten = ExportSnapshot(Path, Why, Trigger);
	if (bWritten)
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 환경 스냅숏 | %.1f초 (전역 스텝 %lld) | %s | 지역 %d | 두뇌 %s | 계기 %s · 환경 판 #%d%s"), Seconds,
			   static_cast<long long>(GlobalT), *Path, Contexts.Num(), *GetActiveBrain().Id, Trigger, EnvRevision,
			   BigWhy.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" | %s"), *BigWhy));
		PostNotice(EcoV3Integrated::ENotice::Snapshot, bEnvDue ? FString::Printf(TEXT("스냅숏 #%d 내보냄 → 파이썬 학습 대기"), EnvRevision)
															   : FString::Printf(TEXT("스냅숏 #%d 내보냄 (주기 %.0f초) → 파이썬 학습 대기"), EnvRevision, Every));
	}
	else
	{
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 환경 스냅숏을 쓰지 못했다 (계기 %s): %s"), Trigger, *Path);
	}
	if (!BigWhy.IsEmpty())
	{
		// 큰 변화 규칙: 쓴 뒤(쓰기에 실패해도 — 다음 경계마다 다시 쓰지 않게) 기준선 = 지금, 바뀜 시계·조건 지움
		EcoV3BigChange::Rebase(BigState, GlobalT);
	}
}

#if !UE_BUILD_SHIPPING
namespace EcoV3SnapshotImpl
{
	void CmdSnapshot(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		if (!World)
		{
			Ar.Log(TEXT("[EcoV3I] 월드가 없다"));
			return;
		}
		if (World->GetNetMode() == NM_Client)
		{
			Ar.Log(TEXT("[EcoV3I] 클라이언트는 세계를 돌리지 않는다 (서버·단독만) — 서버 또는 단독 실행의 콘솔에서 쓴다"));
			return;
		}
		UEcoPolicyV3IntegratedSubsystem* Sub = World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
		if (!Sub || !Sub->IsActive() || Sub->NumContexts() == 0)
		{
			Ar.Log(TEXT("[EcoV3I] 통합 v3 모드가 돌고 있지 않다 (eco.IntegratedPolicyVersion 3 으로 Play, 지역 세계가 생긴 뒤)"));
			return;
		}
		const FString Out = Args.IsEmpty() ? CVarSnapshotOut.GetValueOnGameThread() : FString::Join(Args, TEXT(" "));
		const FString Path = Sub->SnapshotPath(Out);
		const double Seconds = static_cast<double>(Sub->GetGlobalStep()) * EcoRepertoireV3::kStepSeconds;
		if (Sub->ExportSnapshot(Path, TEXT("콘솔 eco.IntegratedV3.Snapshot"), TEXT("console")))
		{
			Ar.Logf(TEXT("[EcoV3I] 환경 스냅숏 | %.1f초 (전역 스텝 %lld) | %s | 지역 %d | 두뇌 %s | 계기 console · 환경 판 #%d"), Seconds,
					static_cast<long long>(Sub->GetGlobalStep()), *Path, Sub->NumContexts(), *Sub->GetActiveBrain().Id, Sub->GetEnvRevision());
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 환경 스냅숏 | %.1f초 (전역 스텝 %lld) | %s | 콘솔 | 계기 console · 환경 판 #%d"), Seconds,
				   static_cast<long long>(Sub->GetGlobalStep()), *Path, Sub->GetEnvRevision());
		}
		else
		{
			Ar.Logf(TEXT("[EcoV3I] 환경 스냅숏을 쓰지 못했다: %s"), *Path);
		}
	}

	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdSnapshotReg(
		TEXT("eco.IntegratedV3.Snapshot"),
		TEXT("통합 v3 모드 환경 스냅숏을 지금 쓴다: eco.IntegratedV3.Snapshot [파일.json|폴더] (비면 eco.IntegratedV3.SnapshotOut, 그것도 비면 ")
			TEXT("Saved/EcoSnapshots/). 파이썬 herbivore_rl/results/v3/adapt/adapt.py 가 이 파일로 거울 세계를 다시 짓는다. 서버·단독만 (EcoV3Snapshot.cpp)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdSnapshot));
}
#endif
