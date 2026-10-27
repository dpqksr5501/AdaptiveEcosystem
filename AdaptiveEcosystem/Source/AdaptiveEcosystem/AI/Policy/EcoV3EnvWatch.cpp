// 통합 v3 모드 환경 바뀜 감시 (10-21 사용자 '게임 중 실시간 두뇌 교체', 설계 LIVE_ADAPT_SPEC.md 5.1·5.3).
//
// 환경을 바꾸는 규칙은 레벨(팀)의 몫이다 — 우리는 규칙을 만들지 않는다 (사람 결정 10-20 '환경이 변하는 규칙은 우리가 만들지 않는다').
// 여기서는 레벨이 Play 중에 바꾼 것을 알아채 v3 지역 세계에 옮기기만 한다:
//   나무  꼬리표 EcoV3Trunk 줄기 막이 (EcoV3PlaceTreesCommandlet 이 놓는 나무 + 줄기 막이 짝) — GatherLevelTrunks 로 싸게 읽어 무대마다 줄기 원판을 만든다.
//         줄기 셈은 시작 레벨 읽기(ScanStageObstacles)가 줄기 막이에 하는 셈을 같은 순서·같은 식으로 따른다 (무대 안 → 무대 단위 → 은신처 원 안 뺌 → 배치 표 맞춤).
//         세계 원판 = 지금 원판에서 지금 넣은 줄기를 뺀 것(시작 읽기의 바위 등·실행 중 무대 나무) + 새 줄기, (x, y, r) 순 — 그 나무로 Play 를 시작했을 때
//         TryCreateContexts 가 만들었을 목록(MergeDiscs(레벨 읽기, 무대 나무))과 같다 (시험 AdaptiveEcosystem.Policy.V3.EnvWatch.Trees). 실행 중 무대 나무
//         (eco.IntegratedV3.StageTrees 1, 기본 0)는 시작 때처럼 무대 안 줄기 막이가 생기면 원판을 빼고 액터를 숨기며, 다 없어지면 다시 넣는다.
//         먹이 격자는 그대로 둔다: 팀 자원 계약(UEcologySimulationSubsystem::CommitSpatialFood)은 스텝 밖에서 먹이 합이 바뀌거나 등록 용량을 넘으면 그 스텝을
//         거부하고 통합 모드를 끈다(용량을 다시 등록하는 길이 없다). 줄기 원판은 반지름 0.36~0.45 단위라 4 m 먹이 셀 하나의 1/6 밑만 덮는다. 파이썬 거울은
//         스냅숏 food.cap 을 그대로 쓰므로(adapt.py apply_snapshot_food) 언리얼과 같은 먹이로 돈다.
//   날씨  우리 지역 날씨 콘솔 변수 eco.IntegratedV3.WeatherForest·WeatherHighland·WeatherBarren (Play 중에도 읽는다 — 값이 바뀌면, 빈 값 = 팀 설계 기본)과
//         팀 FRegionEnvironmentState (UEcologyWorldSubsystem — 지역 세계를 만들 때 값이 바탕, 바뀌면 비·폭풍 = 비 세기 Rainfall(0 이면 1), 맑음·가뭄 = 맑음.
//         팀에는 눈이 없다. 팀 콘솔 eco.Environment.Rain <지역> <0..1> 이 레벨 쪽 계기로 쓰인다). 세계 설정 Weather.Kind·Intensity 를 바꾸고 UpdateDayNight 로
//         배수를 다시 정한다. 시간표(Weather.Schedule)는 쓰지 않는다 (파이썬이 거부한다). 날씨를 끈 세계(eco.IntegratedV3.Weather 0)는 무시한다.
//         시작 날씨 (10-27 사용자 결정 (C)): 팀 날씨 출처(FindTeamWeatherSource — 그 지역을 맡아 실제로 쓰는 팀 환경 어댑터 AEcoRegionEnvironmentAdapter,
//         조연우 BP_JYU_EcosystemWeather 등)가 있는 지역은 지역 세계를 만들 때(InitContextEnv) 팀 지역 환경을 규칙 날씨로 넣는다 — 그 날씨로 세계를 만든 것과 같다
//         (InitWorld 는 날씨로 난수·먹이를 정하지 않는다). 출처가 없는 지역만 우리 고정 날씨(팀 설계 기본·덮기). Play 시작 덮기 글자가 날씨를 고르면 그것,
//         eco.IntegratedV3.TeamWeatherStart 0 이나 감시 끔(EnvWatch 0)이면 지금까지처럼 우리 고정 날씨로 시작한다. 늦게 등록된 지역은 처음 읽을 때 바뀜(team_env)으로 넣는다.
//         스냅숏은 세계 설정 날씨를 적으므로 파이썬 변환·짝 비교는 그대로 맞는다.
// 읽기: eco.IntegratedV3.EnvWatchSeconds(실시간 1 초)마다와 액터가 생기거나 지워진 다음 프레임 (꼬리표는 생긴 뒤에 붙을 수 있다 — 표시만 하고 다음 읽기에서 본다).
//   움직인 액터·월드 파티션 스트리밍은 알림이 없어 정기 읽기가 잡는다. PIE 중 편집기 월드를 고친 것은 PIE 월드에 닿지 않는다.
// 넣기: 처리기가 전역 결정 스텝 경계(두뇌 바꾸기와 같은 곳, 스텝 앞)에서 ApplyEnvChange. 새 원판 안 산 사슴·늑대를 밖으로 밀고(PushOutAndCount) 돌아가기를 지운다.
//   넣은 묶음마다 환경 판 + 1, '[EcoV3I] 환경 바뀜 #n |' 한 줄·화면 알림. 바뀐 것이 없으면 아무것도 하지 않는다 — 지금까지의 실행과 비트 단위로 같다.
// 은신처는 여기서 다루지 않는다 (RefreshRefuges 가 맡고, 파이썬은 바뀐 은신처를 거부한다). eco.IntegratedV3.EnvWatch 0 = 옛 동작 (Play 시작 때 환경 고정).
// 남는 차이 (기록만): 시작 읽기가 원판 상한(512)을 넘었던 무대, 줄기 꼬리표를 단 인스턴스 메시(시작 읽기는 인스턴스마다, 줄기 읽기는 컴포넌트 하나),
//   StageTrees 1 인데 시작 때 레벨 줄기가 있어 무대 나무를 놓지 않은 무대에서 줄기가 다 없어진 경우 (시작이었으면 무대 나무를 놓았다 — 실행 중에 새로 놓지 않는다).
//
// 시험용 대역 (시험용 — 레벨 팀이 할 일을 흉내 낼 뿐 세계 규칙이 아니다. 개발 빌드. 나무 놓기·지우기는 단독 실행만 — 놓는 짝은 복제하지 않아
//   서버에서 놓으면 클라이언트 세계·충돌과 달라진다. 예약은 서버·단독, 예약 명령이 바꾼 콘솔 변수는 Play 가 끝나면 예약 전 값으로 되돌린다):
//   eco.IntegratedV3.Test.AddTrees <지역> <수> [씨]   명령과 같은 나무 + 줄기 막이 짝을 무대 안 빈자리에 놓는다
//   eco.IntegratedV3.Test.RemoveTrees <지역> <수>     시험용으로 놓은 짝을 나중 것부터 (모자라면 그 무대의 레벨 나무 짝) 지운다
//   eco.IntegratedV3.Test.At <초> <명령>[; <명령>…]   시뮬레이션 초가 되면 콘솔 명령을 한 번 (명령줄 -EcoV3TestAt=<초> -EcoV3TestCmd="명령1; 명령2", 쌍 여러 개)
//   eco.IntegratedV3.EnvInfo                          지역마다 줄기·원판·날씨, 환경 판·마지막 바뀜

#include "EcoPolicyV3IntegratedSubsystem.h"

#include "Components/StaticMeshComponent.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Engine/CollisionProfile.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "HAL/IConsoleManager.h"
#include "Misc/OutputDevice.h"
#include "Misc/Parse.h"
#include "World/EcoRegionEnvironmentAdapter.h"
#include "World/EcologyWorldSubsystem.h"

namespace EcoV3EnvWatchImpl
{
#if !UE_BUILD_SHIPPING
	static TAutoConsoleVariable<int32> CVarEnvWatch(
		TEXT("eco.IntegratedV3.EnvWatch"),
		1,
		TEXT("통합 v3 모드 환경 바뀜 감시 (1 = 켬, 기본 — 10-21 '게임 중 실시간 두뇌 교체'). Play 중에 레벨이 바꾼 나무(꼬리표 EcoV3Trunk 줄기 막이)와 지역 날씨")
		TEXT("(eco.IntegratedV3.WeatherForest·WeatherHighland·WeatherBarren 콘솔 변수, 팀 지역 환경 FRegionEnvironmentState)를 eco.IntegratedV3.EnvWatchSeconds 마다·")
		TEXT("액터가 생기거나 지워진 뒤 읽어 다음 결정 스텝 경계에서 지역 세계에 넣는다 (새 원판 안 사슴·늑대는 밀어냄, 먹이 격자 그대로). 바뀐 것이 없으면 아무것도 ")
		TEXT("하지 않는다. 환경을 바꾸는 규칙은 레벨(팀) 몫이다. 0 = Play 시작 때 환경 고정 (지금까지). 명령줄 -EcoV3EnvWatch= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarEnvWatchSeconds(
		TEXT("eco.IntegratedV3.EnvWatchSeconds"),
		1.0f,
		TEXT("통합 v3 모드 환경 바뀜 감시 주기 (실시간 초, 기본 1 — 0.1~60 으로 자른다). 액터가 생기거나 지워지면 다음 프레임에 곧바로 읽는다."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarTeamWeatherStart(
		TEXT("eco.IntegratedV3.TeamWeatherStart"),
		1,
		TEXT("통합 v3 모드 시작 날씨를 팀 날씨 출처에서 (1 = 켬, 기본 — 10-27 사용자 결정 (C)). 지역을 맡아 실제로 쓰는 팀 환경 어댑터(AEcoRegionEnvironmentAdapter — ")
		TEXT("조연우 BP_JYU_EcosystemWeather 등, 비 주기 또는 작성 날씨 켬)가 있는 지역은 지역 세계를 만들 때 팀 지역 환경(FRegionEnvironmentState)을 규칙 날씨로 ")
		TEXT("넣는다 (Play 시작 덮기 글자 eco.IntegratedV3.WeatherForest·WeatherHighland·WeatherBarren 이 날씨를 고르면 그것). 출처가 없는 지역은 우리 고정 날씨 ")
		TEXT("(팀 설계 기본·덮기) 그대로. 환경 감시(eco.IntegratedV3.EnvWatch)가 꺼졌으면 쓰지 않는다. 0 = 10-27 전 (시작은 우리 고정 날씨, 팀 값은 바뀔 때만 — ")
		TEXT("앞선 측정 다시 내기용). Play 전에 바꾼다."),
		ECVF_Default);
#endif

	/** 액터 알림으로 당기는 읽기 사이 최소 간격 (실시간 초). */
	constexpr double kDirtyPollGapSeconds = 0.1;
	/** 시험용 나무 자리 난수의 첫 해시 입력 (세계 난수·시작 자리 난수와 다른 값). */
	constexpr uint64 kTestTreeTag = 0x56335454ULL;   // "V3TT"
	/** 시험용 나무 줄기 사이 틈 (m — 배치 표 make_tree_layout.py 와 같은 3 m). */
	constexpr double kTestTreeGapM = 3.0;
	/** 시험용 나무 하나에 자리를 찾는 횟수. */
	constexpr int32 kTestTreeTries = 400;
	/** 한 번에 놓는 시험용 나무 상한. */
	constexpr int32 kTestTreeMax = 64;
	/** 짝 꼬리표 머리 (EcoV3PlaceTreesCommandlet 과 같다 — EcoV3TreeId_<지역>_<번호>). */
	const TCHAR* const kIdTagPrefix = TEXT("EcoV3TreeId_");

	/** 원판 하나 + 표시 (나무 표시 또는 레벨 줄기 표시). */
	struct FDisc
	{
		double X, Y, R;
		uint8 bFlag;
	};

	/** ScanStageObstacles·MergeDiscs 와 같은 순서 (x, 다음 y, 다음 r). */
	bool DiscLess(const FDisc& A, const FDisc& B)
	{
		return A.X < B.X || (A.X == B.X && (A.Y < B.Y || (A.Y == B.Y && A.R < B.R)));
	}

	int32 NumOf(const std::vector<double>& Flat)
	{
		return static_cast<int32>(Flat.size() / 3);
	}

	/** A − B (같은 (x, y, r) 를 하나씩 지운다, A 의 순서 그대로). */
	std::vector<double> MinusDiscs(const std::vector<double>& A, const std::vector<double>& B)
	{
		TArray<bool> Used;
		Used.Init(false, NumOf(B));
		std::vector<double> Out;
		for (int32 k = 0; k < NumOf(A); ++k)
		{
			bool bFound = false;
			for (int32 j = 0; j < Used.Num() && !bFound; ++j)
			{
				if (!Used[j] && A[3 * k] == B[3 * j] && A[3 * k + 1] == B[3 * j + 1] && A[3 * k + 2] == B[3 * j + 2])
				{
					Used[j] = true;
					bFound = true;
				}
			}
			if (!bFound)
			{
				Out.insert(Out.end(), {A[3 * k], A[3 * k + 1], A[3 * k + 2]});
			}
		}
		return Out;
	}

	double EnvWatchSeconds()
	{
#if !UE_BUILD_SHIPPING
		const double S = static_cast<double>(CVarEnvWatchSeconds.GetValueOnGameThread());
		return FMath::IsFinite(S) ? FMath::Clamp(S, 0.1, 60.0) : 1.0;
#else
		return 1.0;
#endif
	}

	/** 시작 날씨를 팀 날씨 출처에서 가져오나 (eco.IntegratedV3.TeamWeatherStart — Shipping 은 감시가 늘 꺼져 쓰이지 않는다). */
	bool TeamWeatherStartEnabled()
	{
#if !UE_BUILD_SHIPPING
		return CVarTeamWeatherStart.GetValueOnGameThread() != 0;
#else
		return true;
#endif
	}

	/** 덮기 글자가 날씨를 고르나 (비지 않고 읽힌다). 빈 값·못 읽는 글자는 고르지 않는다 (WeatherFor 도 그때 팀 설계 기본을 쓴다). */
	bool PicksWeather(const FString& Text)
	{
		int32 Kind = EcoWorldV3::kWeatherClear;
		double Intensity = 0.0;
		return !Text.TrimStartAndEnd().IsEmpty() && FEcoV3IntegratedSettings::ParseWeather(Text, Kind, Intensity);
	}

	/**
	 * 팀 날씨 출처 (10-27 사용자 결정 (C)): 그 지역의 팀 지역 환경(FRegionEnvironmentState)을 Play 중에 실제로 쓰는 팀 환경 어댑터가 있나.
	 * 어댑터 = AEcoRegionEnvironmentAdapter (World/EcoRegionEnvironmentAdapter.h — 팀 C++, 조연우 BP_JYU_EcosystemWeather 같은 자식 블루프린트 포함).
	 * 어댑터 Tick 이 지역 환경을 쓰는 조건을 그대로 본다 (서버·단독 월드, 팀 월드 시계가 돌면 0.2 초마다):
	 *   ① 이 지역을 맡는다 — RegionIds 에 있거나 비었다 (빈 목록 = 등록된 모든 지역).
	 *   ② 쓰는 길이 켜졌다 — 비 주기(bCycleRainfall: EvaluateCycleRainfall 이 설정을 받아들인다. 작성 날씨와 함께 켜면 어댑터가 거부해 아무것도 쓰지 않는다)
	 *      또는 작성 날씨(bApplyAuthoredWeather, 비 주기 끔).
	 * 둘 다 끈 어댑터(블루프린트가 ApplyWeather·ApplyRainfall 을 직접 부르는 다리일 수 있다 — 언제 무엇을 쓸지 미리 알 수 없다), 팀 지역 환경을 쓰지 않고
	 * 그리기만 하는 날씨 BP(SHC BP_SHC_*RegionalWeather), 팀 콘솔 eco.Environment.Rain 은 시작 출처로 보지 않는다 — 그 값은 바뀔 때 Play 중 바뀜(team_env)으로 따른다.
	 * 어댑터가 실제로 못 쓰는 경우(다른 지정 지역이 등록되지 않아 묶음을 거부, 월드 시계가 서 있음)에도 팀 지역 환경은 팀 화면이 보이는 값이라 그 값으로
	 * 시작하는 쪽이 화면과 어긋나지 않는다.
	 * OutWho = 찾은 어댑터 (이름·종류·쓰는 길 — 기록·EnvInfo), 없으면 빈 값.
	 */
	bool FindTeamWeatherSource(UWorld& World, FName RegionId, FString& OutWho)
	{
		TArray<FString> Who;
		for (TActorIterator<AEcoRegionEnvironmentAdapter> It(&World); It; ++It)
		{
			const AEcoRegionEnvironmentAdapter* A = *It;
			if (!A || !(A->RegionIds.IsEmpty() || A->RegionIds.Contains(RegionId)))
			{
				continue;
			}
			float Probe = 0.0f;
			const bool bCycle = A->EvaluateCycleRainfall(0.0, Probe);   // 비 주기 켬 ∧ 작성 날씨 끔 ∧ 주기 설정이 맞다
			const bool bAuthored = A->bApplyAuthoredWeather && !A->bCycleRainfall;
			if (bCycle || bAuthored)
			{
				Who.Add(FString::Printf(TEXT("%s (%s · %s%s)"), *A->GetActorNameOrLabel(), *A->GetClass()->GetName(),
										bCycle ? *FString::Printf(TEXT("비 주기 %.0f초·위상 %.0f초"), A->RainCycleSeconds, A->RainPhaseOffsetSeconds)
											   : TEXT("작성 날씨"),
										A->RegionIds.IsEmpty() ? TEXT(" · 모든 지역") : TEXT("")));
			}
		}
		OutWho = FString::Join(Who, TEXT(", "));
		return !Who.IsEmpty();
	}

	/** 팀 날씨 상태 이름 (기록 — Clear·Rain·Storm·Drought). */
	FString TeamStateName(uint8 State)
	{
		const UEnum* E = StaticEnum<EEcoWeatherState>();
		return E ? E->GetNameStringByValue(static_cast<int64>(State)) : FString::FromInt(State);
	}

	/** 지역의 날씨 덮기 콘솔 변수 이름 (숲·고지·메마른 땅 밖은 없다). */
	const TCHAR* WeatherCvarName(FName RegionId)
	{
		return RegionId == FName(TEXT("Forest"))	 ? TEXT("eco.IntegratedV3.WeatherForest")
			   : RegionId == FName(TEXT("Highland")) ? TEXT("eco.IntegratedV3.WeatherHighland")
			   : RegionId == FName(TEXT("Barren"))	 ? TEXT("eco.IntegratedV3.WeatherBarren")
													 : nullptr;
	}

	/** 그 지역의 Play 시작 날씨 덮기 글자 (FEcoV3IntegratedSettings — Play 시작 때 콘솔 변수에서 읽은 값). */
	const FString* WeatherOverride(const FEcoV3IntegratedSettings& S, FName RegionId)
	{
		return RegionId == FName(TEXT("Forest"))	 ? &S.WeatherForest
			   : RegionId == FName(TEXT("Highland")) ? &S.WeatherHighland
			   : RegionId == FName(TEXT("Barren"))	 ? &S.WeatherBarren
													 : nullptr;
	}

	/** 날씨 글자 (기록): 맑음 / 비 1.00 / 눈 0.50. */
	FString WeatherText(int32 Kind, double Intensity)
	{
		const FString Name(UTF8_TO_TCHAR(EcoWorldV3::WeatherNameKoUtf8(Kind)));
		return Kind == EcoWorldV3::kWeatherClear ? Name : FString::Printf(TEXT("%s %.2f"), *Name, Intensity);
	}

	/** 팀 지역 환경 → v3 날씨: 비·폭풍 = 비 (세기 = Rainfall 을 0~1 로, 0 이하면 1), 맑음·가뭄 = 맑음. 팀에는 눈이 없다. */
	void TeamWeather(const FRegionEnvironmentState& S, int32& OutKind, double& OutIntensity)
	{
		if (S.WeatherState == EEcoWeatherState::Rain || S.WeatherState == EEcoWeatherState::Storm)
		{
			OutKind = EcoWorldV3::kWeatherRain;
			OutIntensity = S.Rainfall > 0.0f ? FMath::Clamp(static_cast<double>(S.Rainfall), 0.0, 1.0) : 1.0;
		}
		else
		{
			OutKind = EcoWorldV3::kWeatherClear;
			OutIntensity = 0.0;
		}
	}

	/**
	 * 무대 안 레벨 줄기 원판 (무대 단위, (x, y, r) 순). 시작 레벨 읽기(ScanStageObstacles)가 줄기 막이 하나에 하는 셈을 같은 순서·같은 식으로 따른다:
	 * 충돌 상자 가로 중심이 무대 밖이면 뺌 → 무대 단위로 나눔 → 은신처 원(반지름 > 0) 안이면 뺌(맞추기 전 값으로) → 반지름 → 배치 표와 맞춤(SnapToLayout).
	 * TrunksCm = GatherLevelTrunks (같은 충돌 상자·같은 반지름 식 — 그래서 시작 읽기의 줄기 원판과 비트 단위로 같다).
	 * OutInStage = 무대 안 줄기 막이 수 (은신처 원 안 포함), OutSnapped·OutMaxSnapCm = 넣은 줄기 가운데 표 값으로 바꾼 수·그 차이 최대.
	 */
	std::vector<double> StageTrunkDiscs(const TArray<FVector>& TrunksCm, FName RegionId, const FVector& OriginCm, double SizeUnits,
										const std::vector<EcoObservationV3::FCoverInput>& Covers, int32& OutInStage, int32& OutSnapped, double& OutMaxSnapCm)
	{
		using EcoRepertoireV3::kUnitCm;
		OutInStage = 0;
		OutSnapped = 0;
		OutMaxSnapCm = 0.0;
		const double SizeCm = SizeUnits * kUnitCm;
		TArray<FDisc> Kept;
		for (const FVector& T : TrunksCm)
		{
			const double X = T.X - OriginCm.X;
			const double Y = T.Y - OriginCm.Y;
			if (X < 0.0 || Y < 0.0 || X > SizeCm || Y > SizeCm)
			{
				continue;   // 중심이 무대 밖
			}
			++OutInStage;
			double Xu = X / kUnitCm;
			double Yu = Y / kUnitCm;
			bool bInCover = false;
			for (const EcoObservationV3::FCoverInput& Cv : Covers)
			{
				bInCover = bInCover || (Cv.Radius > 0.0 && FMath::Square(Xu - Cv.X) + FMath::Square(Yu - Cv.Y) <= Cv.Radius * Cv.Radius);
			}
			if (bInCover)
			{
				continue;   // 은신처 원 안은 원판으로 넣지 않는다 (시작 읽기와 같다)
			}
			double Ru = T.Z / kUnitCm;
			double Dev = 0.0;
			if (UEcoPolicyV3IntegratedSubsystem::SnapToLayout(RegionId, SizeUnits, Xu, Yu, Ru, &Dev))
			{
				++OutSnapped;
				OutMaxSnapCm = FMath::Max(OutMaxSnapCm, Dev);
			}
			Kept.Add({Xu, Yu, Ru, 1});
		}
		Kept.Sort([](const FDisc& A, const FDisc& B) { return DiscLess(A, B); });
		std::vector<double> Out;
		Out.reserve(static_cast<size_t>(Kept.Num()) * 3);
		for (const FDisc& D : Kept)
		{
			Out.insert(Out.end(), {D.X, D.Y, D.R});
		}
		return Out;
	}

	/**
	 * ';' 로 나눈 콘솔 명령을 차례로 돌린다 (콘솔 변수·등록 명령은 콘솔 관리자, 그 밖은 엔진 Exec — 월드를 넘긴다).
	 * 명령이 콘솔 변수면 그 이름의 처음 값을 CvarBefore 에 적는다 (이미 있으면 그대로 — Play 에서 처음 바꾸기 전 값).
	 */
	void RunCommands(UWorld* World, const FString& Commands, TMap<FString, FString>& CvarBefore)
	{
		TArray<FString> Parts;
		Commands.ParseIntoArray(Parts, TEXT(";"), /*InCullEmpty*/ true);
		for (const FString& Part : Parts)
		{
			const FString Cmd = Part.TrimStartAndEnd();
			if (Cmd.IsEmpty())
			{
				continue;
			}
			FString Name = Cmd;
			int32 Space = INDEX_NONE;
			if (Cmd.FindChar(TEXT(' '), Space))
			{
				Name = Cmd.Left(Space);
			}
			if (const IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(*Name, /*bTrackFrequentCalls*/ false))
			{
				if (!CvarBefore.Contains(Name))
				{
					CvarBefore.Add(Name, Var->GetString());
				}
			}
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 시험용 예약 실행 | %s"), *Cmd);
			if (!IConsoleManager::Get().ProcessUserConsoleInput(*Cmd, *GLog, World) && GEngine)
			{
				GEngine->Exec(World, *Cmd, *GLog);
			}
		}
	}

	/**
	 * 시험용 나무 놓기·지우기는 단독 실행만 (명령과 같은 짝은 복제하지 않는다 — 서버에서 놓거나 지우면 클라이언트의 나무·줄기 충돌과 달라져 클라이언트 폰이
	 * 서버에만 있는 줄기에 막혀 되돌려진다). 단독이 아니면 OutMessage 에 까닭을 적고 참.
	 */
	bool RefuseNetworked(const UWorld& World, const TCHAR* What, FString& OutMessage)
	{
		const ENetMode Mode = World.GetNetMode();
		if (Mode == NM_Standalone)
		{
			return false;
		}
		OutMessage = FString::Printf(TEXT("[EcoV3I] %s: 단독 실행만 — 놓는 짝은 복제하지 않아 %s 에서 바꾸면 클라이언트 세계와 달라진다 (아무것도 하지 않음)"), What,
									 Mode == NM_Client ? TEXT("클라이언트") : TEXT("서버"));
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("%s"), *OutMessage);
		return true;
	}

	/** 짝 꼬리표 EcoV3TreeId_<Id> 의 <Id> (없으면 빈 문자열). */
	FString PairIdOf(const AActor& A)
	{
		for (const FName& Tag : A.Tags)
		{
			const FString S = Tag.ToString();
			if (S.StartsWith(kIdTagPrefix))
			{
				return S.RightChop(FCString::Strlen(kIdTagPrefix));
			}
		}
		return FString();
	}
}

// -----------------------------------------------------------------------------
// 감시 켬·끔
// -----------------------------------------------------------------------------

bool UEcoPolicyV3IntegratedSubsystem::IsEnvWatchEnabled()
{
#if !UE_BUILD_SHIPPING
	return EcoV3EnvWatchImpl::CVarEnvWatch.GetValueOnGameThread() != 0;
#else
	return false;
#endif
}

void UEcoPolicyV3IntegratedSubsystem::InitContextEnv(FEcoV3RegionContext& Ctx)
{
	using namespace EcoV3EnvWatchImpl;
	// 바탕: 시작 레벨 읽기가 쓴 은신처 원(= 세계 설정 원 목록), 날씨 콘솔 변수의 Play 시작 값, 지금 줄기 원판, 팀 지역 환경 (읽기만 — 세계는 그대로.
	// 시작 날씨만 아래 팀 날씨 출처 판정에 따라 바꿀 수 있다)
	Ctx.EnvScanCovers = Ctx.Sim.Config.Covers;
	const FString* Override = WeatherOverride(Settings, Ctx.RegionId);
	Ctx.EnvWeatherCvarSeen = Override ? *Override : FString();
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	TArray<FVector> Trunks;
	GatherLevelTrunks(*World, Trunks);
	int32 Snapped = 0;
	double MaxSnapCm = 0.0;
	Ctx.EnvTrunks = StageTrunkDiscs(Trunks, Ctx.RegionId, Ctx.OriginCm, Ctx.SizeUnits, Ctx.EnvScanCovers, Ctx.EnvLevelTrunks, Snapped, MaxSnapCm);
	FRegionEnvironmentState Team;
	if (const UEcologyWorldSubsystem* Regions = World->GetSubsystem<UEcologyWorldSubsystem>())
	{
		if (Regions->GetEnvironmentState(Ctx.RegionId, Team))
		{
			Ctx.bEnvTeamKnown = true;
			Ctx.EnvTeamWeather = static_cast<uint8>(Team.WeatherState);
			Ctx.EnvTeamRainfall = Team.Rainfall;
		}
	}

	// 시작 날씨 = 팀 날씨 출처 (10-27 사용자 결정 (C)): 팀 날씨 BP 가 도는 맵(조연우 BP_JYU_EcosystemWeather — 비 주기 180 초, 위상 숲 0·메마른 땅 30·고지 60 초)에서
	// 우리 고정 날씨(숲 비 1·고지 눈 1)로 시작하면 팀 값이 처음 바뀔 때까지(숲 0~73 초·고지 0~13 초) 규칙 ≠ 화면(팀 지역 환경을 그리는 식생 맵 보기)이었다.
	// 출처가 맡는 지역은 지금 팀 값을 세계 설정 날씨로 넣는다 — InitWorld 직후 같은 T 라 그 날씨로 세계를 만든 것과 같다 (InitWorld 는 날씨로 난수·먹이를
	// 정하지 않고, 날씨 검사는 TeamWeather 의 값(맑음 0·비 (0, 1])이 늘 통과한다). 바뀜이 아니라 시작값이라 환경 판·기록·알림은 그대로다.
	Ctx.bEnvTeamSource = FindTeamWeatherSource(*World, Ctx.RegionId, Ctx.EnvTeamSourceWho);
	EcoWorldV3::FWorldState& W = Ctx.Sim;
	if (!Ctx.bEnvTeamSource || !W.Config.Weather.bEnabled || !IsEnvWatchEnabled())
	{
		return;   // 출처 없음 = 우리 고정 날씨 (지금까지와 같다). 날씨를 끈 세계·감시를 끈 실행(Play 시작 때 환경 고정 — 옛 동작)도 그대로
	}
	const FString Region = Ctx.RegionId.ToString();
	const FString Ours = WeatherText(W.Config.Weather.Kind, W.Config.Weather.Intensity);
	if (!Ctx.bEnvTeamKnown)
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 시작 날씨 | 팀 날씨 출처 %s 가 있지만 팀 지역이 아직 등록되지 않았다 — 우리 고정 날씨 %s 로 시작하고 팀 지역을 처음 읽을 때 ")
										 TEXT("그 값을 바뀜(team_env)으로 넣는다"),
			   *Region, *Ctx.EnvTeamSourceWho, *Ours);
		return;
	}
	int32 Kind = EcoWorldV3::kWeatherClear;
	double Intensity = 0.0;
	TeamWeather(Team, Kind, Intensity);
	const FString TeamText = FString::Printf(TEXT("%s (팀 지역 환경 %s·비 세기 %.2f)"), *WeatherText(Kind, Intensity), *TeamStateName(Ctx.EnvTeamWeather),
											 static_cast<double>(Team.Rainfall));
	if (!TeamWeatherStartEnabled())
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 시작 날씨 | 팀 날씨 출처 %s 가 있지만 우리 고정 날씨 %s 로 시작한다 (eco.IntegratedV3.TeamWeatherStart 0 — 10-27 전 동작, ")
										 TEXT("팀 값 %s 은 바뀔 때만 따른다)"),
			   *Region, *Ctx.EnvTeamSourceWho, *Ours, *TeamText);
		return;
	}
	if (PicksWeather(Ctx.EnvWeatherCvarSeen))
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 시작 날씨 | 팀 날씨 출처 %s 가 있지만 Play 시작 덮기 글자 '%s' 의 %s 로 시작한다 (사람이 고른 값 — 팀 값 %s 은 다음 팀 바뀜부터 ")
										 TEXT("따른다. 빈 값이면 팀 값으로 시작)"),
			   *Region, *Ctx.EnvTeamSourceWho, *Ctx.EnvWeatherCvarSeen, *Ours, *TeamText);
		return;
	}
	W.Config.Weather.Kind = Kind;
	W.Config.Weather.Intensity = Intensity;
	EcoWorldV3::UpdateDayNight(W);
	Ctx.bEnvStartFromTeam = true;
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 시작 날씨 | 팀 날씨 출처 %s → %s — 우리 고정 날씨 %s 대신 (eco.IntegratedV3.TeamWeatherStart 1, 10-27 (C))"), *Region,
		   *Ctx.EnvTeamSourceWho, *TeamText, *Ours);
}

void UEcoPolicyV3IntegratedSubsystem::BeginEnvWatch(UWorld& InWorld)
{
	const bool bWatch = IsEnvWatchEnabled();
	if (bWatch)
	{
		// 액터 생김·지움 알림 (월드에 걸고 Deinitialize 에서 푼다). 꼬리표는 생긴 뒤에 붙을 수 있으므로 표시만 하고 다음 프레임 읽기에서 본다
		EnvSpawnHandle = InWorld.AddOnActorSpawnedHandler(FOnActorSpawned::FDelegate::CreateUObject(this, &UEcoPolicyV3IntegratedSubsystem::HandleEnvActorChanged));
		EnvDestroyHandle = InWorld.AddOnActorDestroyedHandler(FOnActorDestroyed::FDelegate::CreateUObject(this, &UEcoPolicyV3IntegratedSubsystem::HandleEnvActorChanged));
	}
#if !UE_BUILD_SHIPPING
	TestAts = CommandLineTestAts();   // 명령줄 예약 (-EcoV3TestAt= -EcoV3TestCmd=) — Play 마다 그대로
#endif
	FString Schedule;
	for (const FEcoV3TestAt& T : TestAts)
	{
		Schedule += FString::Printf(TEXT(" · %.1f초: %s"), T.Seconds, *T.Commands);
	}
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 환경 감시: %s | 자동 스냅숏 %s | 시험용 예약 %d%s"),
		   bWatch ? *FString::Printf(TEXT("켬 (eco.IntegratedV3.EnvWatch 1 — %.1f초마다·액터가 생기거나 지워지면 곧바로 읽어 결정 스텝 경계에서 넣는다: 레벨 나무 줄기 막이(꼬리표 %s)·")
										 TEXT("지역 날씨 콘솔 변수·팀 지역 환경. 환경 규칙은 레벨 몫, 먹이 격자 그대로. 시작 날씨 %s)"),
									 EcoV3EnvWatchImpl::EnvWatchSeconds(), *LevelTrunkTag().ToString(),
									 EcoV3EnvWatchImpl::TeamWeatherStartEnabled()
										 ? TEXT("= 팀 날씨 출처(팀 환경 어댑터)가 맡는 지역은 팀 값, 없는 지역은 우리 고정 날씨 (eco.IntegratedV3.TeamWeatherStart 1)")
										 : TEXT("= 우리 고정 날씨 (eco.IntegratedV3.TeamWeatherStart 0 — 10-27 전)"))
				  : TEXT("끔 (eco.IntegratedV3.EnvWatch 0 — Play 시작 때 환경 고정)"),
		   *DescribeAutoSnapshot(), TestAts.Num(), *Schedule);
}

void UEcoPolicyV3IntegratedSubsystem::EndEnvWatch()
{
	if (UWorld* World = GetWorld())
	{
		if (EnvSpawnHandle.IsValid())
		{
			World->RemoveOnActorSpawnedHandler(EnvSpawnHandle);
		}
		if (EnvDestroyHandle.IsValid())
		{
			World->RemoveOnActorDestroyedHandler(EnvDestroyHandle);
		}
	}
	EnvSpawnHandle.Reset();
	EnvDestroyHandle.Reset();
	// 예약 명령이 바꾼 콘솔 변수는 예약 전 값으로 (콘솔 변수는 프로세스에 남는다 — 명령줄 예약은 다음 Play 에서 다시 돌므로 같은 시작값에서 같은 바뀜을 내게)
	for (const TPair<FString, FString>& Before : TestAtCvarBefore)
	{
		IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(*Before.Key, /*bTrackFrequentCalls*/ false);
		if (Var && Var->GetString() != Before.Value)
		{
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 시험용 예약이 바꾼 콘솔 변수 %s '%s' → 예약 전 값 '%s' 로 되돌림 (Play 끝)"), *Before.Key, *Var->GetString(),
				   *Before.Value);
			Var->Set(*Before.Value, ECVF_SetByConsole);
		}
	}
	TestAtCvarBefore.Reset();
	PendingEnv.Reset();
	bEnvPending = false;
	bEnvDirty = false;
	bEnvTestEdit = false;
	NextEnvPoll = 0.0;
	LastEnvPoll = -1.0e9;
	EnvRevision = 0;
	EnvChangedStep = 0;
	EnvFirstChangedStep = 0;
	EnvChanges.Reset();
	TestAts.Reset();
	TestTrees.Reset();
	TestTreeSerial.Reset();
	AutoSnapshotRevision = 0;
	PeriodicNextSeconds = -1.0;
	PeriodicEverySeen = 0.0;
}

void UEcoPolicyV3IntegratedSubsystem::HandleEnvActorChanged(AActor* Actor)
{
	// 동물 표현·폰은 나무가 아니다 (Play 시작 때 많이 생긴다 — 읽기를 당기지 않는다)
	if (!Actor || Actor->IsA<APawn>() || Actor->IsA<AEcoCreatureRepresentationActor>())
	{
		return;
	}
	bEnvDirty = true;
}

void UEcoPolicyV3IntegratedSubsystem::TickEnvWatch()
{
	RunTestSchedule();          // 예약 명령이 나무를 놓으면 바로 아래 읽기가 본다
	PollEnvironment(/*bForce*/ false);
}

// -----------------------------------------------------------------------------
// 읽기 (세계는 바꾸지 않는다)
// -----------------------------------------------------------------------------

bool UEcoPolicyV3IntegratedSubsystem::PollEnvironment(bool bForce)
{
	using namespace EcoV3EnvWatchImpl;
	UWorld* World = GetWorld();
	if (!bActive || !World || Contexts.IsEmpty() || !IsEnvWatchEnabled())
	{
		return false;
	}
	const double Now = FPlatformTime::Seconds();
	// 정기 읽기 때가 아니면 액터 알림이 있을 때만 (FX·표현 액터가 잦게 생겨도 kDirtyPollGapSeconds 에 한 번 — 줄기 읽기는 모든 액터를 훑는다)
	if (!bForce && Now < NextEnvPoll && (!bEnvDirty || Now < LastEnvPoll + kDirtyPollGapSeconds))
	{
		return false;
	}
	NextEnvPoll = Now + EnvWatchSeconds();
	LastEnvPoll = Now;
	bEnvDirty = false;
	const bool bTestEdit = bEnvTestEdit;
	bEnvTestEdit = false;
	PendingEnv.SetNum(Contexts.Num());

	TArray<FVector> Trunks;
	GatherLevelTrunks(*World, Trunks);
	const UEcologyWorldSubsystem* Regions = World->GetSubsystem<UEcologyWorldSubsystem>();
	bool bAny = false;
	for (int32 c = 0; c < Contexts.Num(); ++c)
	{
		FEcoV3RegionContext& Ctx = *Contexts[c];
		FEcoV3EnvPending& P = PendingEnv[c];
		const EcoWorldV3::FWorldState& W = Ctx.Sim;

		// 1. 나무: 무대 안 레벨 줄기 원판 (시작 레벨 읽기와 같은 셈) — 지금 넣은 줄기(또는 대기 줄기)와 다르면 대기
		int32 InStage = 0;
		int32 Snapped = 0;
		double MaxSnapCm = 0.0;
		std::vector<double> StageTrunks = StageTrunkDiscs(Trunks, Ctx.RegionId, Ctx.OriginCm, Ctx.SizeUnits, Ctx.EnvScanCovers, InStage, Snapped, MaxSnapCm);
		Ctx.EnvLevelTrunks = InStage;
		// 실행 중 무대 나무 (eco.IntegratedV3.StageTrees, 기본 0): 시작 때 TryCreateContexts 는 무대 안 줄기 막이가 없을 때만 놓는다 — 그 판정이 바뀌어도 바뀜이다
		const bool bStageTreesNow = Ctx.Trees.Num() > 0 && !Ctx.bLevelTrees;
		const bool bStageTreesWant = Ctx.Trees.Num() > 0 && InStage == 0;
		if (StageTrunks == Ctx.EnvTrunks && bStageTreesNow == bStageTreesWant)
		{
			P.bTrees = false;   // 그대로이거나 바뀌었다 되돌아왔다 — 넣을 것이 없다
			P.Trunks.clear();
		}
		else if (!P.bTrees || StageTrunks != P.Trunks || InStage != P.InStage)
		{
			if (!W.Config.Obstacles.bEnabled || Ctx.bObstaclesImported)
			{
				if (!Ctx.bEnvTreesIgnoredLogged)
				{
					Ctx.bEnvTreesIgnoredLogged = true;
					UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 환경 감시: 레벨 나무 줄기가 바뀌었지만(%d → %d) 세계에 넣지 않는다 — %s"), *Ctx.RegionId.ToString(),
						   NumOf(Ctx.EnvTrunks), NumOf(StageTrunks),
						   Ctx.bObstaclesImported ? TEXT("이 지역 원판을 가져왔다 (eco.IntegratedV3.ObstacleImport, 측정 전용)")
												  : TEXT("Play 시작 때 장애물이 꺼져 있었다 (eco.IntegratedV3.Obstacles 0)"));
				}
			}
			else
			{
				P.bTrees = true;
				P.Trunks = MoveTemp(StageTrunks);
				P.InStage = InStage;
				P.Snapped = Snapped;
				P.MaxSnapCm = MaxSnapCm;
				P.TreeSource = bTestEdit ? TEXT("test") : TEXT("level");
			}
		}

		// 2. 날씨: 팀 지역 환경 (바뀌었을 때만 — 늦게 등록된 지역은 팀 날씨 출처가 맡을 때 처음 값도), 그 뒤 우리 지역 날씨 콘솔 변수 (바뀌었을 때만 — 같은 읽기에서
		//    둘 다 바뀌면 콘솔 변수가 이긴다)
		bool bWant = false;
		int32 WantKind = EcoWorldV3::kWeatherClear;
		double WantIntensity = 0.0;
		FString WantSource;
		FRegionEnvironmentState Team;
		if (Regions && Regions->GetEnvironmentState(Ctx.RegionId, Team))
		{
			const uint8 State = static_cast<uint8>(Team.WeatherState);
			if (!Ctx.bEnvTeamKnown)
			{
				// 처음 본 값이 바탕 (지역이 늦게 등록됐다). 팀 날씨 출처가 맡는 지역이면 그 값은 시작 때 넣었을 날씨다 (InitContextEnv) — 이미 세계가 돌고 있으므로
				// 바뀜(team_env)으로 넣는다. 덮기 글자가 날씨를 고르거나 eco.IntegratedV3.TeamWeatherStart 0 이면 지금까지처럼 바탕만 적는다
				Ctx.bEnvTeamKnown = true;
				Ctx.bEnvTeamSource = FindTeamWeatherSource(*World, Ctx.RegionId, Ctx.EnvTeamSourceWho);
				if (Ctx.bEnvTeamSource && TeamWeatherStartEnabled() && !PicksWeather(Ctx.EnvWeatherCvarSeen))
				{
					TeamWeather(Team, WantKind, WantIntensity);
					WantSource = TEXT("team_env");
					bWant = true;
				}
			}
			else if (State != Ctx.EnvTeamWeather || Team.Rainfall != Ctx.EnvTeamRainfall)
			{
				TeamWeather(Team, WantKind, WantIntensity);
				WantSource = TEXT("team_env");
				bWant = true;
			}
			Ctx.EnvTeamWeather = State;
			Ctx.EnvTeamRainfall = Team.Rainfall;
		}
		if (const TCHAR* Name = WeatherCvarName(Ctx.RegionId))
		{
			const IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(Name, /*bTrackFrequentCalls*/ false);   // 1 초마다 읽는다 (Play 중 바뀐 값)
			const FString Live = Var ? Var->GetString() : FString();
			if (Var && Live != Ctx.EnvWeatherCvarSeen)
			{
				Ctx.EnvWeatherCvarSeen = Live;
				const FString Text = Live.TrimStartAndEnd();
				int32 Kind = EcoWorldV3::kWeatherClear;
				double Intensity = 0.0;
				bool bOk = true;
				if (Text.IsEmpty())
				{
					// 빈 값 = 팀 설계 기본 (kRegionWeatherDefaults — Play 시작 때 빈 값이면 쓰는 날씨)
					FEcoV3IntegratedSettings Def;
					Def.bWeather = true;
					const EcoWorldV3::FWeatherConfig D = Def.WeatherFor(Ctx.RegionId);
					Kind = D.Kind;
					Intensity = D.Intensity;
				}
				else if (!FEcoV3IntegratedSettings::ParseWeather(Text, Kind, Intensity))
				{
					bOk = false;
					UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] %s 날씨 콘솔 변수 %s '%s' 를 못 읽었다 — 날씨 그대로 ('날씨[:세기]', 날씨 = clear·rain·snow)"),
						   *Ctx.RegionId.ToString(), Name, *Live);
				}
				if (bOk)
				{
					WantKind = Kind;
					WantIntensity = Intensity;
					WantSource = FString::Printf(TEXT("cvar:%s"), Name);
					bWant = true;
				}
			}
		}
		if (bWant)
		{
			const EcoWorldV3::FWeatherConfig& Cur = W.Config.Weather;
			if (!Cur.bEnabled)
			{
				if (!Ctx.bEnvWeatherIgnoredLogged)
				{
					Ctx.bEnvWeatherIgnoredLogged = true;
					UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 환경 감시: 날씨가 바뀌었지만(%s, 출처 %s) 세계에 넣지 않는다 — Play 시작 때 날씨가 꺼져 있었다 (eco.IntegratedV3.Weather 0)"),
						   *Ctx.RegionId.ToString(), *WeatherText(WantKind, WantIntensity), *WantSource);
				}
			}
			else if (WantKind == Cur.Kind && WantIntensity == Cur.Intensity)
			{
				P.bWeather = false;   // 지금 날씨와 같다 (앞서 대기한 바뀜도 버린다)
			}
			else
			{
				P.bWeather = true;
				P.WeatherKind = WantKind;
				P.WeatherIntensity = WantIntensity;
				P.WeatherSource = WantSource;
			}
		}
		bAny = bAny || P.bTrees || P.bWeather;
	}
	bEnvPending = bAny;
	return true;
}

// -----------------------------------------------------------------------------
// 넣기 (전역 결정 스텝 경계 — 처리기)
// -----------------------------------------------------------------------------

void UEcoPolicyV3IntegratedSubsystem::ApplyEnvChange(TConstArrayView<TArray<EcoWorldV3::FHerbBody*>> Bodies,
													TConstArrayView<TArray<EcoWorldV3::FThreatAgent*>> Agents)
{
	using namespace EcoV3EnvWatchImpl;
	if (!bEnvPending)
	{
		return;
	}
	bEnvPending = false;
	TArray<FEcoV3EnvPending> Pending = MoveTemp(PendingEnv);
	PendingEnv.Reset();
	if (!IsEnvWatchEnabled())
	{
		return;   // 대기 중에 감시를 껐다 — 넣지 않는다 (옛 동작)
	}
	UWorld* World = GetWorld();
	const int32 Rev = EnvRevision + 1;
	const double Seconds = static_cast<double>(GlobalT) * EcoRepertoireV3::kStepSeconds;
	TArray<FEcoV3EnvChange> Changes;
	TArray<FString> LogParts;
	TArray<FString> NoticeParts;
	for (int32 c = 0; c < Contexts.Num() && c < Pending.Num(); ++c)
	{
		FEcoV3RegionContext& Ctx = *Contexts[c];
		const FEcoV3EnvPending& P = Pending[c];
		EcoWorldV3::FWorldState& W = Ctx.Sim;
		const FString Region = Ctx.RegionId.ToString();
		if (P.bTrees && W.Config.Obstacles.bEnabled && !Ctx.bObstaclesImported)
		{
			// 1. 세계 원판 = 지금 원판 − 지금 넣은 줄기 (남는 것: 시작 읽기의 바위 등·실행 중 무대 나무, 나무 표시 그대로) + 새 줄기, (x, y, r) 순.
			//    시작 때 TryCreateContexts 는 MergeDiscs(레벨 읽기, 무대 나무) 이고 레벨 읽기 = (줄기 아닌 것 ∪ 줄기) 를 (x, y, r) 로 정렬한 것이라, 같은 나무 모음이면
			//    같은 값·같은 순서다 (완전히 같은 (x, y, r) 둘의 순서만 다를 수 있다 — 값은 같다).
			//    실행 중 무대 나무(eco.IntegratedV3.StageTrees)는 시작 때 무대 안 줄기 막이가 없을 때만 놓으므로 같은 판정으로 그 원판을 빼거나 다시 넣는다
			//    (줄기를 표 값에 맞추면 무대 나무 원판과 값이 같다 — 둘 다 두면 원판이 겹친다)
			const bool bStageTreesNow = Ctx.Trees.Num() > 0 && !Ctx.bLevelTrees;
			const bool bStageTreesWant = Ctx.Trees.Num() > 0 && P.InStage == 0;
			const bool bStageTreesOut = bStageTreesNow && !bStageTreesWant;
			const bool bStageTreesIn = bStageTreesWant && !bStageTreesNow;
			std::vector<double>& Discs = W.Config.Obstacles.Discs;
			const int32 OldNum = NumOf(Discs);
			const int32 OldTrunks = NumOf(Ctx.EnvTrunks);
			std::vector<double> RemoveDiscs = Ctx.EnvTrunks;   // 뺄 원판 (지금 넣은 줄기 + 빼는 무대 나무)
			if (bStageTreesOut)
			{
				RemoveDiscs.insert(RemoveDiscs.end(), Ctx.Trees.Discs.begin(), Ctx.Trees.Discs.end());
			}
			const int32 NumRemove = NumOf(RemoveDiscs);
			TArray<bool> Taken;
			Taken.Init(false, NumRemove);
			TArray<FDisc> All;
			for (int32 k = 0; k < OldNum; ++k)
			{
				const double X = Discs[3 * k];
				const double Y = Discs[3 * k + 1];
				const double R = Discs[3 * k + 2];
				bool bTrunk = false;
				for (int32 j = 0; j < NumRemove && !bTrunk; ++j)
				{
					if (!Taken[j] && RemoveDiscs[3 * j] == X && RemoveDiscs[3 * j + 1] == Y && RemoveDiscs[3 * j + 2] == R)
					{
						Taken[j] = true;
						bTrunk = true;
					}
				}
				if (!bTrunk)
				{
					All.Add({X, Y, R, static_cast<uint8>(Ctx.ObstacleIsTree.IsValidIndex(k) && Ctx.ObstacleIsTree[k] != 0 ? 1 : 0)});
				}
			}
			int32 Missing = 0;
			for (const bool bTaken : Taken)
			{
				Missing += bTaken ? 0 : 1;
			}
			const int32 NewTrunks = NumOf(P.Trunks);
			for (int32 j = 0; j < NewTrunks; ++j)
			{
				All.Add({P.Trunks[3 * j], P.Trunks[3 * j + 1], P.Trunks[3 * j + 2], 1});
			}
			if (bStageTreesIn)
			{
				for (int32 j = 0; j < Ctx.Trees.Num(); ++j)
				{
					All.Add({Ctx.Trees.Discs[3 * j], Ctx.Trees.Discs[3 * j + 1], Ctx.Trees.Discs[3 * j + 2], 1});   // 시작 때처럼 레벨 읽기 원판 뒤 (같은 값이면 레벨 것이 앞)
				}
			}
			All.StableSort([](const FDisc& A, const FDisc& B) { return DiscLess(A, B); });
			Discs.clear();
			Discs.reserve(static_cast<size_t>(All.Num()) * 3);
			Ctx.ObstacleIsTree.Reset(All.Num());
			for (const FDisc& D : All)
			{
				Discs.insert(Discs.end(), {D.X, D.Y, D.R});
				Ctx.ObstacleIsTree.Add(D.bFlag);
			}
			// 숲 시야 나무 표 (10-22, FObstacleConfig::Foliage.Trees — 원판과 같은 순서로 다시 맞춘다. 무대를 만들 때와 같은 표)
			W.Config.Obstacles.Foliage.Trees.assign(Ctx.ObstacleIsTree.GetData(), Ctx.ObstacleIsTree.GetData() + Ctx.ObstacleIsTree.Num());
			// 먹이 격자는 그대로 둔다 — 팀 자원 계약(CommitSpatialFood)이 스텝 밖 먹이·용량 변화를 거부하면 통합 모드가 꺼진다. 줄기는 먹이 셀 하나의 1/6 밑만 덮는다
			// (EcoV3EnvWatch.cpp 머리 주석). 파이썬 거울은 스냅숏 food.cap 을 그대로 쓴다

			// 2. 레벨 읽기 기록 (스냅숏 scan_discs·level_trees, 10 초 장애물 줄): 줄기 아닌 읽기 원판 + 새 줄기, (x, y, r) 순
			{
				FEcoV3ObstacleScan& S = Ctx.ObstacleScan;
				TArray<FDisc> Scan;
				for (int32 k = 0; k < S.Num(); ++k)
				{
					if (!(S.IsLevelTree.IsValidIndex(k) && S.IsLevelTree[k] != 0))
					{
						Scan.Add({S.Discs[3 * k], S.Discs[3 * k + 1], S.Discs[3 * k + 2], 0});
					}
				}
				for (int32 j = 0; j < NewTrunks; ++j)
				{
					Scan.Add({P.Trunks[3 * j], P.Trunks[3 * j + 1], P.Trunks[3 * j + 2], 1});
				}
				Scan.StableSort([](const FDisc& A, const FDisc& B) { return DiscLess(A, B); });
				S.Discs.clear();
				S.IsLevelTree.Reset(Scan.Num());
				for (const FDisc& D : Scan)
				{
					S.Discs.insert(S.Discs.end(), {D.X, D.Y, D.R});
					S.IsLevelTree.Add(D.bFlag);
				}
				S.LevelTrees = NewTrunks;
				S.LevelTreesSnapped = P.Snapped;
				S.LevelTreesUnmatched = NewTrunks - P.Snapped;
				S.LevelTreeMaxSnapCm = FMath::Max(S.LevelTreeMaxSnapCm, P.MaxSnapCm);
			}

			// 3. 새 원판 안 산 사슴·늑대는 밖으로 (입양과 같은 PushOutAndCount, 화면 보간 앞 자리도 — 순간이동으로 보이지 않게), 돌아가기 상태는 지운다
			//    (원판 색인이 바뀌어도 돌아가기 상태는 쪽·남은 스텝뿐이라 안전하지만, 없어진 줄기를 계속 돌지 않게)
			std::vector<double> Added = MinusDiscs(P.Trunks, Ctx.EnvTrunks);
			const int32 NumAddedTrunks = NumOf(Added);
			const int32 NumRemoved = NumOf(MinusDiscs(Ctx.EnvTrunks, P.Trunks));
			if (bStageTreesIn)
			{
				Added.insert(Added.end(), Ctx.Trees.Discs.begin(), Ctx.Trees.Discs.end());   // 다시 넣는 무대 나무 원판도 새 원판이다
			}
			const int32 NumAdded = NumOf(Added);
			const double BodyR = W.Config.Obstacles.BodyR;
			int32 PushedDeer = 0;
			int32 PushedWolves = 0;
			if (Bodies.IsValidIndex(c))
			{
				for (EcoWorldV3::FHerbBody* B : Bodies[c])
				{
					if (!B)
					{
						continue;
					}
					B->Detour = EcoThreatV3::FDetourState();
					if (NumAdded > 0 && EcoThreatV3::InsideAnyObstacle(B->Pos.X, B->Pos.Y, Added.data(), NumAdded, BodyR))
					{
						EcoWorldV3::PushOutAndCount(W, B->Pos, false);
						B->PrevPos = B->Pos;
						++PushedDeer;
					}
				}
			}
			if (Agents.IsValidIndex(c))
			{
				for (EcoWorldV3::FThreatAgent* A : Agents[c])
				{
					if (!A)
					{
						continue;
					}
					A->State.Detour = EcoThreatV3::FDetourState();
					if (NumAdded > 0 && EcoThreatV3::InsideAnyObstacle(A->State.PosX, A->State.PosY, Added.data(), NumAdded, BodyR))
					{
						EcoWorldV3::FVec2 Pw{A->State.PosX, A->State.PosY};
						EcoWorldV3::PushOutAndCount(W, Pw, true);
						A->State.PosX = A->PrevX = Pw.X;
						A->State.PosY = A->PrevY = Pw.Y;
						++PushedWolves;
					}
				}
			}

			// 4. 거울 칸: 디버그 그리기 높이(TryCreateContexts 와 같은 아래쪽 선 검사), 레벨 나무 여부, 원판 대조 줄 다시
			Ctx.ObstacleGroundZ.Reset();
			for (int32 k = 0; k < NumOf(Discs); ++k)
			{
				const FVector Pc = Ctx.UnitsToCm(Discs[3 * k], Discs[3 * k + 1], Ctx.OriginCm.Z);
				FHitResult Hit;
				FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3ObstacleDraw), false);
				Ctx.ObstacleGroundZ.Add(World && World->LineTraceSingleByChannel(Hit, Pc + FVector(0, 0, 5000), Pc - FVector(0, 0, 20000), ECC_WorldStatic, Params)
											? Hit.ImpactPoint.Z
											: Ctx.OriginCm.Z);
			}
			Ctx.bLevelTrees = P.InStage > 0;   // 시작 때와 같은 판정 (무대 안 줄기 막이가 있다 — 은신처 원 안 포함)
			Ctx.bObsParityDiscsLogged = false;
			Ctx.EnvTrunks = P.Trunks;
			if (bStageTreesOut || bStageTreesIn)
			{
				// 무대 나무 액터(충돌 없음 — 원판만 막는다)도 원판과 같이 숨기거나 보인다 (보이는 나무 = 세계 원판)
				for (const TWeakObjectPtr<AActor>& Tree : Ctx.Trees.Actors)
				{
					if (AActor* A = Tree.Get())
					{
						A->SetActorHiddenInGame(bStageTreesOut);
					}
				}
			}

			FEcoV3EnvChange& Ch = Changes.AddDefaulted_GetRef();
			Ch.Revision = Rev;
			Ch.Step = GlobalT;
			Ch.Seconds = Seconds;
			Ch.Region = Ctx.RegionId;
			Ch.Kind = TEXT("trees");
			Ch.Detail = FString::Printf(TEXT("나무 %d→%d (+%d −%d)%s"), OldTrunks, NewTrunks, NumAddedTrunks, NumRemoved,
										bStageTreesOut ? *FString::Printf(TEXT(" · 무대 나무 %d 뺌"), Ctx.Trees.Num())
										: bStageTreesIn ? *FString::Printf(TEXT(" · 무대 나무 %d 다시 넣음"), Ctx.Trees.Num())
														: TEXT(""));
			Ch.Source = P.TreeSource;
			LogParts.Add(FString::Printf(TEXT("%s: %s (출처 %s · 세계 원판 %d→%d · 밀어냄 사슴 %d·늑대 %d)"), *Region, *Ch.Detail, *Ch.Source, OldNum, NumOf(Discs),
										 PushedDeer, PushedWolves));
			NoticeParts.Add(FString::Printf(TEXT("%s: 나무 %d→%d"), *Region, OldTrunks, NewTrunks));
			if (Missing > 0)
			{
				UE_LOG(LogEcoPolicyV3I, Warning,
					   TEXT("[EcoV3I] %s 환경 바뀜: 넣었던 줄기 원판 %d 개를 세계 원판에서 찾지 못했다 — 시작 레벨 읽기와 줄기 읽기가 다르다 (원판 상한 512 넘침·")
						   TEXT("인스턴스 줄기 막이 등). 남은 원판은 그대로 두었다"),
					   *Region, Missing);
			}
		}
		if (P.bWeather && W.Config.Weather.bEnabled)
		{
			// 날씨: 세계 설정의 고정 날씨를 바꾸고 같은 T 로 배수를 다시 (어둠은 그대로). InitWorld 와 같은 검사 — 맑음 = 세기 0, 세기 [0, 1].
			// 시간표는 쓰지 않는다 (파이썬 adapt.py 가 schedule_rows ≠ 0 을 거부한다)
			EcoWorldV3::FWeatherConfig& Wx = W.Config.Weather;
			const bool bOk = P.WeatherKind >= EcoWorldV3::kWeatherClear && P.WeatherKind < EcoWorldV3::kNumWeatherKinds && P.WeatherIntensity >= 0.0
							 && P.WeatherIntensity <= 1.0 && (P.WeatherKind != EcoWorldV3::kWeatherClear || P.WeatherIntensity == 0.0);
			if (bOk)
			{
				const int32 OldKind = Wx.Kind;
				const double OldIntensity = Wx.Intensity;
				Wx.Kind = P.WeatherKind;
				Wx.Intensity = P.WeatherIntensity;
				EcoWorldV3::UpdateDayNight(W);
				FEcoV3EnvChange& Ch = Changes.AddDefaulted_GetRef();
				Ch.Revision = Rev;
				Ch.Step = GlobalT;
				Ch.Seconds = Seconds;
				Ch.Region = Ctx.RegionId;
				Ch.Kind = TEXT("weather");
				Ch.Detail = FString::Printf(TEXT("%s→%s"), *WeatherText(OldKind, OldIntensity), *WeatherText(Wx.Kind, Wx.Intensity));
				Ch.Source = P.WeatherSource;
				LogParts.Add(FString::Printf(TEXT("%s: 날씨 %s (출처 %s)"), *Region, *Ch.Detail, *Ch.Source));
				NoticeParts.Add(FString::Printf(TEXT("%s: %s→%s"), *Region, UTF8_TO_TCHAR(EcoWorldV3::WeatherNameKoUtf8(OldKind)),
												UTF8_TO_TCHAR(EcoWorldV3::WeatherNameKoUtf8(Wx.Kind))));
			}
		}
	}
	if (Changes.IsEmpty())
	{
		return;
	}
	EnvRevision = Rev;
	if (EnvChanges.IsEmpty())
	{
		EnvFirstChangedStep = GlobalT;
	}
	EnvChangedStep = GlobalT;
	EnvChanges.Append(Changes);
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 환경 바뀜 #%d | %.1f초 (전역 스텝 %lld) | %s"), Rev, Seconds, static_cast<long long>(GlobalT),
		   *FString::Join(LogParts, TEXT(" | ")));
	PostNotice(EcoV3Integrated::ENotice::Env, FString::Printf(TEXT("환경 바뀜 #%d — %s"), Rev, *FString::Join(NoticeParts, TEXT(" · "))));
}

TArray<FString> UEcoPolicyV3IntegratedSubsystem::EnvInfoLines() const
{
	using namespace EcoV3EnvWatchImpl;
	TArray<FString> Lines;
	const FEcoV3EnvChange* Last = EnvChanges.IsEmpty() ? nullptr : &EnvChanges.Last();
	Lines.Add(FString::Printf(TEXT("[EcoV3I] 환경 | 감시 %s | 환경 판 #%d%s | 대기 변화 %s"),
							  IsEnvWatchEnabled() ? *FString::Printf(TEXT("켬 (%.1f초마다)"), EnvWatchSeconds()) : TEXT("끔 (eco.IntegratedV3.EnvWatch 0)"), EnvRevision,
							  Last ? *FString::Printf(TEXT(" (처음 전역 스텝 %lld · 마지막 %.1f초 전역 스텝 %lld: %s %s %s, 출처 %s)"),
													  static_cast<long long>(EnvFirstChangedStep), Last->Seconds, static_cast<long long>(Last->Step),
													  *Last->Region.ToString(), *Last->Kind, *Last->Detail, *Last->Source)
								   : TEXT(" (바뀐 적 없음)"),
							  bEnvPending ? TEXT("있음 (다음 결정 스텝 경계에서 넣는다)") : TEXT("없음")));
	for (int32 c = 0; c < Contexts.Num(); ++c)
	{
		const FEcoV3RegionContext& Ctx = *Contexts[c];
		const EcoWorldV3::FWorldState& W = Ctx.Sim;
		FString Wait;
		if (PendingEnv.IsValidIndex(c) && PendingEnv[c].bTrees)
		{
			Wait += FString::Printf(TEXT(" · 대기 줄기 %d (출처 %s)"), NumOf(PendingEnv[c].Trunks), *PendingEnv[c].TreeSource);
		}
		if (PendingEnv.IsValidIndex(c) && PendingEnv[c].bWeather)
		{
			Wait += FString::Printf(TEXT(" · 대기 날씨 %s (출처 %s)"), *WeatherText(PendingEnv[c].WeatherKind, PendingEnv[c].WeatherIntensity),
									*PendingEnv[c].WeatherSource);
		}
		const FString TeamSource = Ctx.bEnvTeamSource ? FString::Printf(TEXT("%s%s"), *Ctx.EnvTeamSourceWho, Ctx.bEnvStartFromTeam ? TEXT(" — 시작 날씨 = 팀 값") : TEXT(""))
													  : FString(TEXT("없음"));
		Lines.Add(FString::Printf(TEXT("[EcoV3I] %s | 무대 안 줄기 막이 %d · 세계에 넣은 줄기 %d · 세계 원판 %d (장애물 %s) | 날씨 %s (%s) · 지금 %s · 팀 날씨 출처 %s%s"),
								  *Ctx.RegionId.ToString(), Ctx.EnvLevelTrunks, NumOf(Ctx.EnvTrunks), W.Config.Obstacles.Num(), W.Config.Obstacles.bEnabled ? TEXT("켬") : TEXT("끔"),
								  *WeatherText(W.Config.Weather.Kind, W.Config.Weather.Intensity), W.Config.Weather.bEnabled ? TEXT("켬") : TEXT("끔"),
								  *WeatherText(W.WeatherKind, W.WeatherIntensity), *TeamSource, *Wait));
	}
	return Lines;
}

// -----------------------------------------------------------------------------
// 시험용 대역 (레벨 팀이 할 일을 흉내 낸다 — 세계 규칙이 아니다)
// -----------------------------------------------------------------------------

EcoTreeLayoutV3::FTree UEcoPolicyV3IntegratedSubsystem::MakeLevelTree(double X, double Y, double Scale, double YawDeg)
{
	using EcoRepertoireV3::kUnitCm;
	EcoTreeLayoutV3::FTree T{};
	T.X = X;
	T.Y = Y;
	T.Scale = Scale;
	T.YawDeg = YawDeg;
	T.R = EcoTreeLayoutV3::kTrunkRadiusMeshCm * Scale / kUnitCm;   // 배치 표와 같은 식·같은 순서
	// 기준점 = 줄기 중심 − 방위로 돌린 (메시 기준점 → 밑동 중심) × 크기 (FRotator 방위 = x 축에서 y 축 쪽으로 돈다)
	const double A = FMath::DegreesToRadians(YawDeg);
	const double Ox = EcoTreeLayoutV3::kPivotOffsetMeshCmX * Scale / kUnitCm;
	const double Oy = EcoTreeLayoutV3::kPivotOffsetMeshCmY * Scale / kUnitCm;
	T.PivotX = X - (Ox * FMath::Cos(A) - Oy * FMath::Sin(A));
	T.PivotY = Y - (Ox * FMath::Sin(A) + Oy * FMath::Cos(A));
	return T;
}

bool UEcoPolicyV3IntegratedSubsystem::SpawnLevelTreePair(UWorld& World, const EcoTreeLayoutV3::FTree& T, const FVector& OriginCm, double GroundMinZ,
														 UStaticMesh* TreeMesh, UStaticMesh& TrunkMesh, FName IdTag, AActor*& OutTree, AActor*& OutTrunk)
{
	OutTree = nullptr;
	OutTrunk = nullptr;
	FTransform TrunkXf;
	if (!LevelTrunkTransform(T, OriginCm, GroundMinZ, TrunkMesh, TrunkXf))
	{
		return false;
	}
	const FTransform TreeXf = LevelTreeTransform(T, OriginCm, GroundMinZ);
	// 명령(EcoV3PlaceTreesCommandlet Apply)과 같은 설정. 실행 중 액터라 움직임 가능(등록 전 메시를 넣는다 — SpawnStageTrees 와 같다)·저장하지 않음
	auto Spawn = [&World](const FTransform& Xf, UStaticMesh* Mesh, bool bTrunk, const TArray<FName>& Tags) -> AStaticMeshActor*
	{
		FActorSpawnParameters Params;
		Params.bDeferConstruction = true;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Params.ObjectFlags |= RF_Transient;
		AStaticMeshActor* A = World.SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), Xf, Params);
		UStaticMeshComponent* C = A ? A->GetStaticMeshComponent() : nullptr;
		if (!C)
		{
			return nullptr;
		}
		C->SetMobility(EComponentMobility::Movable);
		if (Mesh)
		{
			C->SetStaticMesh(Mesh);
		}
		C->SetCollisionProfileName(bTrunk ? UCollisionProfile::BlockAll_ProfileName : UCollisionProfile::NoCollision_ProfileName);
		C->SetCastShadow(!bTrunk);
		C->SetHiddenInGame(bTrunk);
		C->SetCanEverAffectNavigation(false);   // 팀 내비 메시를 더럽히지 않는다
		if (bTrunk)
		{
			// 보이지 않는 막이: 그림자·거리장·반사·광선 추적에도 넣지 않는다 (명령과 같다)
			C->bAffectDistanceFieldLighting = false;
			C->bAffectDynamicIndirectLighting = false;
			C->bVisibleInReflectionCaptures = false;
			C->bVisibleInRealTimeSkyCaptures = false;
			C->bVisibleInRayTracing = false;
		}
		A->SetActorHiddenInGame(bTrunk);
		A->Tags = Tags;
		A->FinishSpawning(Xf);
		return A;
	};
	AStaticMeshActor* Tree = Spawn(TreeXf, TreeMesh, false, {LevelTreeTag(), IdTag});
	AStaticMeshActor* Trunk = Tree ? Spawn(TrunkXf, &TrunkMesh, true, {LevelTrunkTag(), IdTag}) : nullptr;
	if (!Tree || !Trunk)
	{
		if (Tree)
		{
			Tree->Destroy();
		}
		return false;
	}
	Trunk->AttachToActor(Tree, FAttachmentTransformRules::KeepWorldTransform);   // 나무를 옮기면 줄기 막이가 따라간다 (명령과 같다)
	OutTree = Tree;
	OutTrunk = Trunk;
	return true;
}

int32 UEcoPolicyV3IntegratedSubsystem::TestAddTrees(FName RegionId, int32 Count, TOptional<int32> Seed, FString& OutMessage)
{
	using namespace EcoV3EnvWatchImpl;
	using EcoRepertoireV3::kUnitCm;
	UWorld* World = GetWorld();
	FEcoV3RegionContext* Ctx = FindContext(RegionId);
	if (!World || !bActive || !Ctx)
	{
		OutMessage = FString::Printf(TEXT("[EcoV3I] 시험용 나무: 지역 %s 의 v3 무대가 없다"), *RegionId.ToString());
		return 0;
	}
	if (RefuseNetworked(*World, TEXT("시험용 나무 놓기"), OutMessage))
	{
		return 0;
	}
	UStaticMesh* TrunkMesh = LoadObject<UStaticMesh>(nullptr, LevelTrunkMeshPath());
	UStaticMesh* TreeMesh = LoadObject<UStaticMesh>(nullptr, UTF8_TO_TCHAR(EcoTreeLayoutV3::kMeshPath));
	if (!TrunkMesh)
	{
		OutMessage = FString::Printf(TEXT("[EcoV3I] 시험용 나무: 줄기 막이 메시 %s 를 읽지 못했다"), LevelTrunkMeshPath());
		return 0;
	}
	Count = FMath::Clamp(Count, 1, kTestTreeMax);
	int32& Serial = TestTreeSerial.FindOrAdd(RegionId);
	const int32 UseSeed = Seed.IsSet() ? Seed.GetValue() : static_cast<int32>(Settings.Seed) + Serial;
	EcoWorldV3::FRng Rng;
	Rng.State = EcoRepertoireV3::HashChain3(kTestTreeTag, static_cast<uint64>(static_cast<int64>(UseSeed)),
											 static_cast<uint64>(FMath::Max(0, Ctx->RegionRuntimeIndex)) + 1);

	// 피할 원판: 지금 세계 원판 + 아직 세계에 넣지 않은 줄기 (대기 줄기, 시험용으로 놓은 짝)
	std::vector<double> Avoid = Ctx->Sim.Config.Obstacles.Discs;
	if (PendingEnv.IsValidIndex(Ctx->Index) && PendingEnv[Ctx->Index].bTrees)
	{
		Avoid.insert(Avoid.end(), PendingEnv[Ctx->Index].Trunks.begin(), PendingEnv[Ctx->Index].Trunks.end());
	}
	for (const FEcoV3TestTree& T : TestTrees)
	{
		if (T.Region == RegionId && T.Trunk.IsValid())
		{
			Avoid.insert(Avoid.end(), {T.X, T.Y, T.R});
		}
	}
	// 지면 검사에서 뺄 액터 = 우리 나무·줄기 막이 (줄기 막이 윗면을 땅으로 읽지 않게 — 명령과 같다)
	TArray<AActor*> Ignore;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (It->ActorHasTag(LevelTreeTag()) || It->ActorHasTag(LevelTrunkTag()))
		{
			Ignore.Add(*It);
		}
	}
	const double Size = Ctx->SizeUnits;
	const double Wall = EcoTreeLayoutV3::kWallClearM * 100.0 / kUnitCm;
	const double Clear = EcoTreeLayoutV3::kCoverClearM * 100.0 / kUnitCm;
	const double Gap = kTestTreeGapM * 100.0 / kUnitCm;
	FString Placed;
	int32 Done = 0;
	for (int32 n = 0; n < Count; ++n)
	{
		bool bPlaced = false;
		for (int32 Try = 0; Try < kTestTreeTries && !bPlaced; ++Try)
		{
			const double Scale = Rng.Uniform(EcoTreeLayoutV3::kScaleLo, EcoTreeLayoutV3::kScaleHi);
			const double Yaw = Rng.Uniform(0.0, 360.0);
			const double R = EcoTreeLayoutV3::kTrunkRadiusMeshCm * Scale / kUnitCm;
			const double X = Rng.Uniform(Wall + R, Size - Wall - R);
			const double Y = Rng.Uniform(Wall + R, Size - Wall - R);
			bool bFree = true;
			for (const EcoObservationV3::FCoverInput& Cv : Ctx->Sim.Config.Covers)
			{
				bFree = bFree && !(Cv.Radius > 0.0 && FMath::Sqrt(FMath::Square(X - Cv.X) + FMath::Square(Y - Cv.Y)) < Cv.Radius + Clear + R);
			}
			for (size_t k = 0; bFree && k + 2 < Avoid.size(); k += 3)
			{
				bFree = FMath::Sqrt(FMath::Square(X - Avoid[k]) + FMath::Square(Y - Avoid[k + 1])) >= Avoid[k + 2] + R + Gap;
			}
			if (!bFree)
			{
				continue;
			}
			const EcoTreeLayoutV3::FTree T = MakeLevelTree(X, Y, Scale, Yaw);
			double MinZ = 0.0;
			double MaxZ = 0.0;
			if (!GroundStageTree(*World, Ctx->OriginCm, T, MinZ, MaxZ, &Ignore))
			{
				continue;
			}
			const FString Id = FString::Printf(TEXT("%s_T%02d"), *RegionId.ToString(), Serial);
			AActor* TreeActor = nullptr;
			AActor* TrunkActor = nullptr;
			if (!SpawnLevelTreePair(*World, T, Ctx->OriginCm, MinZ, TreeMesh, *TrunkMesh, FName(*(FString(kIdTagPrefix) + Id)), TreeActor, TrunkActor))
			{
				break;
			}
			++Serial;
			FEcoV3TestTree& Rec = TestTrees.AddDefaulted_GetRef();
			Rec.Region = RegionId;
			Rec.Id = Id;
			Rec.Tree = TreeActor;
			Rec.Trunk = TrunkActor;
			Rec.X = T.X;
			Rec.Y = T.Y;
			Rec.R = T.R;
			Avoid.insert(Avoid.end(), {T.X, T.Y, T.R});
			Ignore.Add(TreeActor);
			Ignore.Add(TrunkActor);
			Placed += FString::Printf(TEXT(" · %s (%.2f, %.2f) r %.3f"), *Id, T.X, T.Y, T.R);
			++Done;
			bPlaced = true;
		}
	}
	if (Done > 0)
	{
		bEnvDirty = true;   // 다음 읽기에서 본다 (출처 test)
		bEnvTestEdit = true;
	}
	OutMessage = FString::Printf(TEXT("[EcoV3I] 시험용 나무 놓기 (레벨 팀 작업 흉내 — 세계 규칙 아님) | %s %d/%d 그루 (씨 %d, 꼬리표 %s·%s)%s%s"), *RegionId.ToString(), Done, Count,
								 UseSeed, *LevelTreeTag().ToString(), *LevelTrunkTag().ToString(), *Placed,
								 TreeMesh ? TEXT("") : TEXT(" | 나무 메시를 읽지 못해 줄기 막이만 보인다"));
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("%s"), *OutMessage);
	return Done;
}

int32 UEcoPolicyV3IntegratedSubsystem::TestRemoveTrees(FName RegionId, int32 Count, FString& OutMessage)
{
	using namespace EcoV3EnvWatchImpl;
	UWorld* World = GetWorld();
	const FEcoV3RegionContext* Ctx = FindContext(RegionId);
	if (!World || !bActive || !Ctx)
	{
		OutMessage = FString::Printf(TEXT("[EcoV3I] 시험용 나무 지우기: 지역 %s 의 v3 무대가 없다"), *RegionId.ToString());
		return 0;
	}
	if (RefuseNetworked(*World, TEXT("시험용 나무 지우기"), OutMessage))
	{
		return 0;
	}
	Count = FMath::Max(1, Count);
	int32 Removed = 0;
	FString Ids;
	// 1. 시험용으로 놓은 짝 (나중 것부터)
	for (int32 i = TestTrees.Num() - 1; i >= 0 && Removed < Count; --i)
	{
		if (TestTrees[i].Region != RegionId)
		{
			continue;
		}
		AActor* Tree = TestTrees[i].Tree.Get();
		AActor* Trunk = TestTrees[i].Trunk.Get();
		if (Tree || Trunk)
		{
			Ids += FString::Printf(TEXT(" %s"), *TestTrees[i].Id);
			++Removed;
		}
		if (Trunk)
		{
			Trunk->Destroy();
		}
		if (Tree)
		{
			Tree->Destroy();
		}
		TestTrees.RemoveAt(i);
	}
	// 2. 모자라면 그 무대의 레벨 나무 짝 (짝 꼬리표 이름 역순 — 줄기 막이와 붙은 나무를 함께)
	if (Removed < Count)
	{
		const double SizeCm = Ctx->SizeCm();
		TArray<TPair<FString, AActor*>> Level;
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			if (!It->ActorHasTag(LevelTrunkTag()))
			{
				continue;
			}
			const FVector L = It->GetActorLocation();
			if (L.X - Ctx->OriginCm.X < 0.0 || L.Y - Ctx->OriginCm.Y < 0.0 || L.X - Ctx->OriginCm.X > SizeCm || L.Y - Ctx->OriginCm.Y > SizeCm)
			{
				continue;
			}
			Level.Emplace(PairIdOf(**It), *It);
		}
		Level.Sort([](const TPair<FString, AActor*>& A, const TPair<FString, AActor*>& B) { return A.Key > B.Key; });
		for (int32 i = 0; i < Level.Num() && Removed < Count; ++i)
		{
			AActor* Trunk = Level[i].Value;
			AActor* Tree = Trunk->GetAttachParentActor();
			if (Tree && Tree->ActorHasTag(LevelTreeTag()))
			{
				Tree->Destroy();
			}
			Trunk->Destroy();
			Ids += FString::Printf(TEXT(" %s(레벨)"), Level[i].Key.IsEmpty() ? TEXT("?") : *Level[i].Key);
			++Removed;
		}
	}
	if (Removed > 0)
	{
		bEnvDirty = true;
		bEnvTestEdit = true;
	}
	OutMessage = FString::Printf(TEXT("[EcoV3I] 시험용 나무 지우기 (레벨 팀 작업 흉내 — 세계 규칙 아님) | %s %d/%d 짝:%s"), *RegionId.ToString(), Removed, Count,
								 Ids.IsEmpty() ? TEXT(" 없음") : *Ids);
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("%s"), *OutMessage);
	return Removed;
}

void UEcoPolicyV3IntegratedSubsystem::TestAt(double Seconds, const FString& Commands)
{
	FEcoV3TestAt& T = TestAts.AddDefaulted_GetRef();
	T.Seconds = Seconds;
	T.Commands = Commands.TrimStartAndEnd();
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 시험용 예약 | %.1f초에: %s (지금 %.1f초, 전역 스텝 %lld)"), T.Seconds, *T.Commands,
		   static_cast<double>(GlobalT) * EcoRepertoireV3::kStepSeconds, static_cast<long long>(GlobalT));
}

void UEcoPolicyV3IntegratedSubsystem::RunTestSchedule()
{
	if (TestAts.IsEmpty() || Contexts.IsEmpty())
	{
		return;
	}
	const double Seconds = static_cast<double>(GlobalT) * EcoRepertoireV3::kStepSeconds;
	TArray<FEcoV3TestAt> Due;
	for (int32 i = 0; i < TestAts.Num();)
	{
		if (Seconds + 1e-9 >= TestAts[i].Seconds)
		{
			Due.Add(TestAts[i]);
			TestAts.RemoveAt(i);   // 한 번만 (명령이 새 예약을 넣어도 이 목록은 그대로)
		}
		else
		{
			++i;
		}
	}
	for (const FEcoV3TestAt& T : Due)
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 시험용 예약 | %.1f초 (전역 스텝 %lld) — 예약 %.1f초: %s"), Seconds, static_cast<long long>(GlobalT), T.Seconds,
			   *T.Commands);
		EcoV3EnvWatchImpl::RunCommands(GetWorld(), T.Commands, TestAtCvarBefore);
	}
}

TArray<FEcoV3TestAt>& UEcoPolicyV3IntegratedSubsystem::CommandLineTestAts()
{
	static TArray<FEcoV3TestAt> Queue;
	return Queue;
}

void UEcoPolicyV3IntegratedSubsystem::ParseCommandLineTestAts(const TCHAR* CmdLine)
{
	if (!CmdLine)
	{
		return;
	}
	// -EcoV3TestAt=<초> 다음의 -EcoV3TestCmd=<명령> 을 쌍으로 (따옴표 안 ';'·공백은 그대로 — FParse::Value 의 구분자 멈춤을 끈다)
	TArray<FEcoV3TestAt> Found;
	const TCHAR* Cursor = CmdLine;
	while (Cursor && *Cursor)
	{
		float At = -1.0f;
		const TCHAR* AfterAt = nullptr;
		if (!FParse::Value(Cursor, TEXT("EcoV3TestAt="), At, &AfterAt) || !AfterAt)
		{
			break;
		}
		FString Cmd;
		const TCHAR* AfterCmd = nullptr;
		if (!FParse::Value(AfterAt, TEXT("EcoV3TestCmd="), Cmd, false, &AfterCmd) || !AfterCmd)
		{
			break;
		}
		Cmd.TrimStartAndEndInline();
		if (FMath::IsFinite(At) && At >= 0.0f && !Cmd.IsEmpty())
		{
			Found.Add({static_cast<double>(At), Cmd});
		}
		Cursor = AfterCmd;
	}
	if (Found.IsEmpty())
	{
		// 쌍의 순서가 거꾸로여도 하나는 받는다 (-EcoV3TestCmd= 가 앞)
		float At = -1.0f;
		FString Cmd;
		if (FParse::Value(CmdLine, TEXT("EcoV3TestAt="), At) && FParse::Value(CmdLine, TEXT("EcoV3TestCmd="), Cmd, false) && FMath::IsFinite(At) && At >= 0.0f
			&& !Cmd.TrimStartAndEnd().IsEmpty())
		{
			Found.Add({static_cast<double>(At), Cmd.TrimStartAndEnd()});
		}
	}
	if (!Found.IsEmpty())
	{
		CommandLineTestAts() = MoveTemp(Found);
	}
}

// -----------------------------------------------------------------------------
// 콘솔 (개발 빌드)
// -----------------------------------------------------------------------------

#if !UE_BUILD_SHIPPING
namespace EcoV3EnvWatchImpl
{
	/** 통합 v3 가 도는 서버·단독 월드의 서브시스템 (아니면 까닭을 적고 nullptr). */
	UEcoPolicyV3IntegratedSubsystem* ActiveSubsystem(UWorld* World, FOutputDevice& Ar)
	{
		if (!World)
		{
			Ar.Log(TEXT("[EcoV3I] 월드가 없다"));
			return nullptr;
		}
		if (World->GetNetMode() == NM_Client)
		{
			Ar.Log(TEXT("[EcoV3I] 클라이언트는 세계를 돌리지 않는다 (서버·단독만) — 서버 또는 단독 실행의 콘솔에서 쓴다"));
			return nullptr;
		}
		UEcoPolicyV3IntegratedSubsystem* Sub = World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
		if (!Sub || !Sub->IsActive() || Sub->NumContexts() == 0)
		{
			Ar.Log(TEXT("[EcoV3I] 통합 v3 모드가 돌고 있지 않다 (eco.IntegratedPolicyVersion 3 으로 Play, 지역 세계가 생긴 뒤)"));
			return nullptr;
		}
		return Sub;
	}

	void CmdAddTrees(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		UEcoPolicyV3IntegratedSubsystem* Sub = ActiveSubsystem(World, Ar);
		if (!Sub)
		{
			return;
		}
		if (Args.Num() < 2 || !Args[1].IsNumeric() || (Args.Num() >= 3 && !Args[2].IsNumeric()))
		{
			Ar.Log(TEXT("[EcoV3I] 쓰는 법: eco.IntegratedV3.Test.AddTrees <지역> <수> [씨] (시험용 — 레벨 팀 작업 흉내)"));
			return;
		}
		TOptional<int32> Seed;
		if (Args.Num() >= 3)
		{
			Seed = FCString::Atoi(*Args[2]);
		}
		FString Message;
		Sub->TestAddTrees(FName(*Args[0]), FCString::Atoi(*Args[1]), Seed, Message);
		Ar.Log(Message);
	}

	void CmdRemoveTrees(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		UEcoPolicyV3IntegratedSubsystem* Sub = ActiveSubsystem(World, Ar);
		if (!Sub)
		{
			return;
		}
		if (Args.Num() < 2 || !Args[1].IsNumeric())
		{
			Ar.Log(TEXT("[EcoV3I] 쓰는 법: eco.IntegratedV3.Test.RemoveTrees <지역> <수> (시험용 — 레벨 팀 작업 흉내)"));
			return;
		}
		FString Message;
		Sub->TestRemoveTrees(FName(*Args[0]), FCString::Atoi(*Args[1]), Message);
		Ar.Log(Message);
	}

	void CmdTestAt(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		UEcoPolicyV3IntegratedSubsystem* Sub = ActiveSubsystem(World, Ar);
		if (!Sub)
		{
			return;
		}
		if (Args.Num() < 2 || !Args[0].IsNumeric())
		{
			Ar.Log(TEXT("[EcoV3I] 쓰는 법: eco.IntegratedV3.Test.At <시뮬레이션 초> <명령>[; <명령>…] (시험용 — 시연 대본)"));
			return;
		}
		TArray<FString> Rest(Args);
		Rest.RemoveAt(0);
		Sub->TestAt(FCString::Atod(*Args[0]), FString::Join(Rest, TEXT(" ")));
		Ar.Logf(TEXT("[EcoV3I] 시험용 예약 %d 개 대기"), Sub->GetTestSchedule().Num());
	}

	void CmdEnvInfo(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		UEcoPolicyV3IntegratedSubsystem* Sub = ActiveSubsystem(World, Ar);
		if (!Sub)
		{
			return;
		}
		for (const FString& Line : Sub->EnvInfoLines())
		{
			Ar.Log(Line);
		}
	}

	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdAddTreesReg(
		TEXT("eco.IntegratedV3.Test.AddTrees"),
		TEXT("시험용 (레벨 팀 작업 흉내 — 세계 규칙 아님): eco.IntegratedV3.Test.AddTrees <지역> <수> [씨]. 레벨 나무 놓기 명령과 같은 나무 + 줄기 막이 짝(꼬리표 EcoV3Tree·")
			TEXT("EcoV3Trunk·EcoV3TreeId_<지역>_T<n>)을 그 무대 안 빈자리(벽 4 m·은신처 원 + 2 m·줄기 틈 3 m 밖, 지면)에 놓는다. 환경 감시가 다음 읽기에서 알아챈다. 단독 실행만 (짝은 복제하지 않는다)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdAddTrees));
	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdRemoveTreesReg(
		TEXT("eco.IntegratedV3.Test.RemoveTrees"),
		TEXT("시험용 (레벨 팀 작업 흉내 — 세계 규칙 아님): eco.IntegratedV3.Test.RemoveTrees <지역> <수>. 시험용으로 놓은 나무 짝을 나중 것부터, 모자라면 그 무대의 ")
			TEXT("레벨 나무 짝을 지운다. 단독 실행만 (짝은 복제하지 않는다)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdRemoveTrees));
	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdTestAtReg(
		TEXT("eco.IntegratedV3.Test.At"),
		TEXT("시험용 (시연 대본): eco.IntegratedV3.Test.At <시뮬레이션 초> <명령>[; <명령>…]. 전역 스텝 × 2/15 초가 그 값이 되면 콘솔 명령을 한 번 돌린다 (여러 개 대기 가능). ")
			TEXT("명령줄 -EcoV3TestAt=<초> -EcoV3TestCmd=\"명령1; 명령2\" (쌍 여러 개). 서버·단독만. 예약 명령이 바꾼 콘솔 변수는 Play 가 끝나면 예약 전 값으로 되돌린다."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdTestAt));
	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdEnvInfoReg(
		TEXT("eco.IntegratedV3.EnvInfo"),
		TEXT("통합 v3 환경 바뀜 감시 요약: 감시 켬·끔, 환경 판·마지막 바뀜, 지역마다 무대 안 줄기 막이·세계에 넣은 줄기·세계 원판·날씨·대기 변화 (EcoV3EnvWatch.cpp)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdEnvInfo));
}
#endif
