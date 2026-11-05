// '큰 변화만' 다시 배우기 자동화 시험 (10-27, EcoV3BigChange.h·EcoV3Snapshot.cpp — 설계 Docs/RL_Policy/FOREST_GROWTH_MODE.md 2절).
//
// 묶음:
//   AutoSnapshot.BigRule   순수 규칙: 원판 대칭차(더함·지움·같은 원판 둘), 숲 기본 시간표(+6 없음 · +12 조건·기다림 · 다 자란 뒤 20 초에 한 번 = 전역 스텝 1425),
//                          세기만 바뀜 = 셈·바뀜 시계 없음, 종류 < 120 초 없음·≥ 120 초 있음, 되돌아온 종류 없음, 묶기(10 초 사이 +5 +5 → 마지막 뒤 20 초),
//                          기다림 상한 300 초, 기준선 다시 정함, 상태 줄 글
//   EnvWatch.BigRule       서브시스템: 자동 스냅숏 규칙 1 — 날씨 세기만 바뀐 판은 스냅숏 없음, 종류는 120 초 뒤 한 번 (env.rule big·env.big), 시험용 나무 +6 +6 은
//                          마지막 바뀜 뒤 20 초에 한 번 (env.big.trees 12), 규칙 0 이면 판마다 (옛 동작)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoV3BigChange.h"
#include "../EcoWorldV3.h"
#include "../TreeLayoutV3.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "EcoTestWorld.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoV3BigChangeTestImpl
{
	using namespace EcoV3BigChange;
	using FSub = UEcoPolicyV3IntegratedSubsystem;

	/** 원판 n 개 (서로 다른 (x, y, r)) — 앞에서부터 같은 값. */
	std::vector<double> Discs(int32 N, double Y = 1.0)
	{
		std::vector<double> Out;
		for (int32 i = 0; i < N; ++i)
		{
			Out.insert(Out.end(), {2.0 * i + 3.0, Y, 0.4});
		}
		return Out;
	}

	void SetCVar(const TCHAR* Name, const TCHAR* Value)
	{
		if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name))
		{
			V->Set(Value, ECVF_SetByCode);
		}
	}

	FString GetCVar(const TCHAR* Name)
	{
		const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name);
		return V ? V->GetString() : FString();
	}

	TSharedPtr<FJsonObject> ReadJson(const FString& Path)
	{
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *Path))
		{
			return nullptr;
		}
		TSharedPtr<FJsonObject> Root;
		FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root);
		return Root;
	}

	/** 바닥 상자 (윗면 TopZ, 무대 (0, 0) 의 한 변 SideCm 정사각을 덮는다). */
	AStaticMeshActor* Floor(UWorld& World, double SideCm, double TopZ)
	{
		AStaticMeshActor* A = World.SpawnActor<AStaticMeshActor>(FVector(0.5 * SideCm, 0.5 * SideCm, TopZ - 50.0), FRotator::ZeroRotator);
		if (!A)
		{
			return nullptr;
		}
		A->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
		A->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
		A->SetActorScale3D(FVector(SideCm / 100.0 + 20.0, SideCm / 100.0 + 20.0, 1.0));
		A->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
		return A;
	}
}

// -----------------------------------------------------------------------------
// 순수 규칙
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3BigRuleTest,
	"AdaptiveEcosystem.Policy.V3.AutoSnapshot.BigRule",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BigRuleTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3BigChangeTestImpl;
	const FConfig C;   // 기본 10 · 120 초 · 20 초 · 300 초
	TestTrue(TEXT("기본값 10·120·20·300"), C.BigTrees == 10 && C.WeatherHoldSeconds == 120.0 && C.SettleSeconds == 20.0 && C.MaxWaitSeconds == 300.0);

	// 1. 대칭차
	{
		int32 A = 0, R = 0;
		CountDiff(Discs(3), Discs(3), A, R);
		TestTrue(TEXT("같은 원판 → 0"), A == 0 && R == 0);
		std::vector<double> Now = Discs(4);
		Now.erase(Now.begin(), Now.begin() + 3);   // 지움 첫째
		Now.insert(Now.end(), {50.0, 50.0, 0.4});  // 새 하나
		CountDiff(Now, Discs(4), A, R);
		TestTrue(TEXT("지움 1·더함 1 → 대칭차 2"), A == 1 && R == 1);
		const std::vector<double> Two = {1.0, 1.0, 0.4, 1.0, 1.0, 0.4};
		const std::vector<double> One = {1.0, 1.0, 0.4};
		CountDiff(One, Two, A, R);
		TestTrue(TEXT("같은 (x, y, r) 둘 가운데 하나 지움 → 1 (하나씩 지운다)"), A == 0 && R == 1);
	}

	// 2. 숲 기본 시간표 (메마른 땅 0 → 6 → 12 → 18 → 24, 다 자람 스텝 375·675·975·1275) — 숲이 자라는 동안 기다림, 다 자란 뒤 20 초(150 스텝)에 한 번
	{
		FState S;
		AddRegion(S, TEXT("Barren"), {}, EcoWorldV3::kWeatherClear, 0);
		AddRegion(S, TEXT("Forest"), Discs(3, 40.0), EcoWorldV3::kWeatherRain, 0);
		const int64 Mature[4] = {375, 675, 975, 1275};
		int32 Writes = 0;
		int64 WriteStep = -1;
		int64 ConditionStep = -1;
		bool bHoldSeen = false;
		FDecision WriteD;
		for (int64 t = 0; t <= 1600; ++t)
		{
			for (int32 k = 0; k < 4; ++k)
			{
				if (t == Mature[k])
				{
					OnTrees(S, 0, Discs(6 * (k + 1)), t);
				}
			}
			const bool bHold = t < 1275;   // 숲 자라는 중 (마지막 단계가 다 자라는 경계 1275 부터 끝)
			const FDecision D = Tick(S, C, t, bHold);
			if (D.bNewCondition)
			{
				ConditionStep = t;
			}
			bHoldSeen = bHoldSeen || (D.bCondition && D.bHold);
			if (D.bWrite)
			{
				++Writes;
				WriteStep = t;
				WriteD = D;
				Rebase(S, t);
			}
			if (t == 375)
			{
				TestFalse(TEXT("+6 (375) — 조건 아님"), D.bCondition);
				TestEqual(TEXT("+6 상태 줄"), ProgressText(S, C, t, bHold, TEXT("숲이 다 자랄 때까지")),
						  FString(TEXT("다시 배우기까지: 메마른 땅 나무 +6/10 · 날씨 그대로")));
			}
		}
		TestEqual(TEXT("조건 = +12 가 된 스텝 675 (90 초)"), ConditionStep, static_cast<int64>(675));
		TestTrue(TEXT("조건 뒤 숲이 자라는 동안 기다림"), bHoldSeen);
		TestEqual(TEXT("스냅숏 정확히 한 번"), Writes, 1);
		TestEqual(TEXT("다 자란 뒤 20 초 = 전역 스텝 1425 (190 초)"), WriteStep, static_cast<int64>(1425));
		TestTrue(TEXT("쓸 때: 바뀜 없이 20 초 · 조건 뒤 100 초 · 상한 아님"),
				 FMath::IsNearlyEqual(WriteD.QuietSeconds, 20.0, 1e-9) && FMath::IsNearlyEqual(WriteD.WaitSeconds, 100.0, 1e-9) && !WriteD.bCapped);
		TestTrue(TEXT("기준선 다시 정함: 대칭차 0 · 쓴 수 1 · 기준 스텝 1425"), S.Regions[0].TreeDiff() == 0 && S.Writes == 1 && S.BaselineStep == 1425);
	}

	// 3. 세기만 바뀜: 셈·바뀜 시계 없음
	{
		FState S;
		AddRegion(S, TEXT("Forest"), {}, EcoWorldV3::kWeatherRain, 0);
		TestFalse(TEXT("같은 종류(비 → 비) = 큰 변화 바뀜 아님"), OnWeather(S, 0, EcoWorldV3::kWeatherRain, 50));
		TestTrue(TEXT("바뀜 시계 그대로 (기준선 스텝)"), S.LastActivityStep == 0 && S.Regions[0].KindSinceStep == 0);
		TestFalse(TEXT("조건 아님 (1000 스텝 뒤에도)"), Tick(S, C, 1000, false).bCondition);
	}

	// 4. 날씨 종류: 120 초(900 스텝) 미만 없음, 이상이면 그 경계에서 곧바로 (바뀜 뒤 120 초 > 묶기 20 초)
	{
		FState S;
		AddRegion(S, TEXT("Forest"), {}, EcoWorldV3::kWeatherRain, 0);
		TestTrue(TEXT("비 → 맑음 = 큰 변화 바뀜"), OnWeather(S, 0, EcoWorldV3::kWeatherClear, 2000));
		bool bEarly = false;
		int64 WriteStep = -1;
		for (int64 t = 2000; t <= 3000 && WriteStep < 0; ++t)
		{
			const FDecision D = Tick(S, C, t, false);
			bEarly = bEarly || (t < 2900 && D.bCondition);
			if (D.bWrite)
			{
				WriteStep = t;
			}
			if (t == 2450)
			{
				TestEqual(TEXT("종류 기다림 상태 줄"), ProgressText(S, C, t, false, FString()), FString(TEXT("다시 배우기까지: 나무 그대로 · 숲 날씨 비→맑음 60/120초")));
			}
		}
		TestFalse(TEXT("120 초 전에는 조건 아님"), bEarly);
		TestEqual(TEXT("120 초 (900 스텝) 되는 경계에서 쓴다"), WriteStep, static_cast<int64>(2900));
	}

	// 5. 되돌아온 종류: 비 → 맑음 (90 초) → 비 — 조건 없음 (조연우 맵 팀 비 주기 반 주기)
	{
		FState S;
		AddRegion(S, TEXT("Forest"), {}, EcoWorldV3::kWeatherRain, 0);
		OnWeather(S, 0, EcoWorldV3::kWeatherClear, 100);
		OnWeather(S, 0, EcoWorldV3::kWeatherRain, 775);   // 90 초 뒤
		bool bAny = false;
		for (int64 t = 100; t <= 3000; ++t)
		{
			bAny = bAny || Tick(S, C, t, false).bCondition;
		}
		TestFalse(TEXT("오가는 비 (반 주기 90 초) — 큰 변화 아님"), bAny);
	}

	// 6. 묶기: +5 (100) · +5 (175 = 10 초 뒤) → 조건 175, 쓰기 = 마지막 바뀜 뒤 20 초 = 325
	{
		FState S;
		AddRegion(S, TEXT("Barren"), {}, EcoWorldV3::kWeatherClear, 0);
		int64 WriteStep = -1;
		for (int64 t = 0; t <= 600 && WriteStep < 0; ++t)
		{
			if (t == 100)
			{
				OnTrees(S, 0, Discs(5), t);
			}
			if (t == 175)
			{
				OnTrees(S, 0, Discs(10), t);
			}
			const FDecision D = Tick(S, C, t, false);
			if (t == 250)
			{
				TestEqual(TEXT("묶기 상태 줄"), ProgressText(S, C, t, false, FString()), FString(TEXT("다시 배우기: 조건 됨 — 바뀜이 멈추길 기다림 10/20초")));
			}
			if (D.bWrite)
			{
				WriteStep = t;
			}
		}
		TestEqual(TEXT("마지막 바뀜(175) 뒤 20 초 = 325"), WriteStep, static_cast<int64>(325));
	}

	// 7. 기다림 상한: '진행 중'이 끝나지 않아도 조건 뒤 300 초(2250 스텝)에 쓴다
	{
		FState S;
		AddRegion(S, TEXT("Barren"), {}, EcoWorldV3::kWeatherClear, 0);
		OnTrees(S, 0, Discs(10), 100);
		int64 WriteStep = -1;
		bool bCapped = false;
		for (int64 t = 100; t <= 3000 && WriteStep < 0; ++t)
		{
			const FDecision D = Tick(S, C, t, /*bHold*/ true);
			if (t == 200)
			{
				TestEqual(TEXT("기다림 상태 줄"), ProgressText(S, C, t, true, TEXT("숲이 다 자랄 때까지")),
						  FString(TEXT("다시 배우기: 조건 됨 — 숲이 다 자랄 때까지 기다림 (13/300초)")));
			}
			if (D.bWrite)
			{
				WriteStep = t;
				bCapped = D.bCapped;
			}
		}
		TestEqual(TEXT("조건(100) 뒤 300 초 = 2350"), WriteStep, static_cast<int64>(2350));
		TestTrue(TEXT("상한으로 씀 (capped)"), bCapped);
	}

	// 8. 문턱 경계: 9 개는 아님, 10 개면 조건 (지움 5 + 더함 5 도 10)
	{
		FState S;
		AddRegion(S, TEXT("Barren"), Discs(5, 20.0), EcoWorldV3::kWeatherClear, 0);
		OnTrees(S, 0, Discs(4), 10);   // 지움 5 · 더함 4 = 9
		TestFalse(TEXT("대칭차 9 — 조건 아님"), Evaluate(S, C, 10, false).bCondition);
		OnTrees(S, 0, Discs(5), 11);   // 지움 5 · 더함 5 = 10
		TestTrue(TEXT("대칭차 10 (지움 5 + 더함 5) — 조건"), Evaluate(S, C, 11, false).bCondition);
		TestEqual(TEXT("섞인 바뀜 글자 ±10"), TreeDiffText(S.Regions[0]), FString(TEXT("±10")));
	}
	return true;
}

// -----------------------------------------------------------------------------
// 서브시스템: 자동 스냅숏 규칙 1 (스냅숏 파일·env 블록)
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3EnvWatchBigRuleTest,
	"AdaptiveEcosystem.Policy.V3.EnvWatch.BigRule",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3EnvWatchBigRuleTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3BigChangeTestImpl;
	const TCHAR* const Vars[8] = {TEXT("eco.IntegratedV3.AutoSnapshot"),	 TEXT("eco.IntegratedV3.AutoSnapshotOut"), TEXT("eco.IntegratedV3.AutoSnapshotRule"),
								  TEXT("eco.IntegratedV3.SnapshotEvery"),	 TEXT("eco.IntegratedV3.WeatherForest"),   TEXT("eco.IntegratedV3.WeatherBarren"),
								  TEXT("eco.IntegratedV3.AutoSnapshotSettle"), TEXT("eco.IntegratedV3.EnvNoticeMinor")};
	FString Saved[8];
	for (int32 i = 0; i < 8; ++i)
	{
		Saved[i] = GetCVar(Vars[i]);
	}
	const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"), TEXT("EcoV3BigRuleSnapshots")));
	IFileManager::Get().DeleteDirectory(*Dir, false, true);
	ON_SCOPE_EXIT
	{
		for (int32 i = 0; i < 8; ++i)
		{
			SetCVar(Vars[i], *Saved[i]);
		}
		IFileManager::Get().DeleteDirectory(*Dir, false, true);
	};
	SetCVar(Vars[0], TEXT("1"));
	SetCVar(Vars[1], *Dir);
	SetCVar(Vars[2], TEXT("1"));
	SetCVar(Vars[3], TEXT("0"));
	SetCVar(Vars[4], TEXT("rain:0.5"));   // Play 시작 값 = 아래 설정과 같게 (시작 뒤 바뀜이 아니다)
	SetCVar(Vars[5], TEXT(""));
	SetCVar(Vars[6], TEXT("3"));
	SetCVar(Vars[7], TEXT("0"));
	auto Files = [&Dir]()
	{
		TArray<FString> Found;
		IFileManager::Get().FindFiles(Found, *FPaths::Combine(Dir, TEXT("*.json")), true, false);
		Found.Sort();
		return Found;
	};

	EcoTest::FScopedTestWorld W;
	constexpr double kSize = EcoTreeLayoutV3::kStageSizeUnits;
	constexpr double kTopZ = 250.0;
	if (!TestNotNull(TEXT("시험 월드"), W.World) || !TestNotNull(TEXT("바닥"), Floor(*W.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ)))
	{
		return false;
	}
	UEcoPolicyV3IntegratedSubsystem* Sub = W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	if (!TestNotNull(TEXT("통합 서브시스템"), Sub))
	{
		return false;
	}
	FEcoV3IntegratedSettings S;
	S.Seed = 38100;
	S.StageSizeUnits = kSize;
	S.WeatherForest = TEXT("rain:0.5");
	Sub->ActivateForTest(S, false);
	const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(kSize, 6.0);
	FEcoV3RegionContext* Forest = Sub->AddContext(TEXT("Forest"), 1, FVector(0.0, 0.0, kTopZ), FSub::MakeRegionWorldConfig(S, 1, 16, 2, Covers, TEXT("Forest")), 16, 2);
	if (!TestNotNull(TEXT("숲 무대"), Forest) || !TestEqual(TEXT("숲 시작 날씨 비"), Forest->Sim.Config.Weather.Kind, EcoWorldV3::kWeatherRain))
	{
		return false;
	}
	TestTrue(TEXT("기준선: 지역 하나·날씨 비"), Sub->GetBigState().Regions.Num() == 1 && Sub->GetBigState().Regions[0].BaseKind == EcoWorldV3::kWeatherRain);
	auto Run = [Sub](int32 N)
	{
		for (int32 s = 0; s < N; ++s)
		{
			if (Sub->HasPendingEnvChange())
			{
				Sub->ApplyEnvChange({}, {});
			}
			Sub->MaybeAutoSnapshot();
			Sub->FinishGlobalStep();
		}
	};

	// 1. 세기만 바뀜 (비 0.5 → 0.8): 세계에는 넣되 (판 1) 스냅숏 없음
	SetCVar(Vars[4], TEXT("rain:0.8"));
	Sub->PollEnvironment(true);
	Run(400);
	TestTrue(TEXT("세기 바뀜은 세계에 들어간다 (판 1, 세기 0.8)"), Sub->GetEnvRevision() == 1 && Forest->Sim.Config.Weather.Intensity == 0.8);
	TestEqual(TEXT("세기만 바뀜 — 스냅숏 없음 (규칙 0 이면 3 초 뒤 썼다)"), Files().Num(), 0);
	TestTrue(TEXT("세기만 바뀜 — 바뀜 시계 그대로"), Sub->GetBigState().LastActivityStep == Sub->GetBigState().BaselineStep);
	TestTrue(TEXT("세기만 바뀜 — 화면 알림 없음"), Sub->GetLastEnvNotice().IsEmpty());

	// 1b. (10-27 확인 고침) 나무 +2 와 세기만 바뀜(비 0.8 → 0.9)이 한 묶음: 알림은 나무만 — 세기만 바뀐 지역이 '숲: 비→비' 로 섞이지 않는다
	{
		FString Msg;
		TestEqual(TEXT("시험용 나무 2"), Sub->TestAddTrees(TEXT("Forest"), 2, TOptional<int32>(2), Msg), 2);
		SetCVar(Vars[4], TEXT("rain:0.9"));
		Sub->PollEnvironment(true);
		Run(5);
		TestTrue(TEXT("묶음 하나 (판 2, 세기 0.9)"), Sub->GetEnvRevision() == 2 && Forest->Sim.Config.Weather.Intensity == 0.9);
		TestEqual(TEXT("섞인 묶음 알림 = 나무만"), Sub->GetLastEnvNotice(), FString(TEXT("환경 바뀜 #2 — Forest: 나무 0→2")));
	}

	// 2. 종류 (비 → 맑음): 120 초(900 스텝) 뒤 한 번
	SetCVar(Vars[4], TEXT("clear"));
	Sub->PollEnvironment(true);
	const int64 T0 = Sub->GetGlobalStep();
	int64 WrittenAt = -1;
	for (int32 s = 0; s < 1000 && WrittenAt < 0; ++s)
	{
		const int32 Before = Sub->GetBigState().Writes;
		Run(1);
		if (Sub->GetBigState().Writes > Before)
		{
			WrittenAt = Sub->GetGlobalStep() - 1;
		}
	}
	TestEqual(TEXT("종류 바뀜 뒤 120 초 = 900 스텝에 한 번"), WrittenAt, T0 + 900);
	if (TestEqual(TEXT("스냅숏 파일 하나"), Files().Num(), 1))
	{
		const TSharedPtr<FJsonObject> Root = ReadJson(FPaths::Combine(Dir, Files()[0]));
		const TSharedPtr<FJsonObject>* Env = nullptr;
		if (TestTrue(TEXT("env 블록"), Root.IsValid() && Root->TryGetObjectField(TEXT("env"), Env) && Env && Env->IsValid()))
		{
			const FJsonObject& E = **Env;
			TestEqual(TEXT("env.rule = big"), E.GetStringField(TEXT("rule")), FString(TEXT("big")));
			TestEqual(TEXT("env.trigger = env_change (그대로)"), E.GetStringField(TEXT("trigger")), FString(TEXT("env_change")));
			const TSharedPtr<FJsonObject>* Big = nullptr;
			if (TestTrue(TEXT("env.big"), E.TryGetObjectField(TEXT("big"), Big) && Big && Big->IsValid()))
			{
				const TSharedPtr<FJsonObject> Fw = (*Big)->GetObjectField(TEXT("weather"))->GetObjectField(TEXT("Forest"));
				TestTrue(TEXT("env.big.weather.Forest: base rain · now clear · held 120"),
						 Fw->GetStringField(TEXT("base")) == TEXT("rain") && Fw->GetStringField(TEXT("now")) == TEXT("clear")
							 && FMath::IsNearlyEqual(Fw->GetNumberField(TEXT("held_s")), 120.0, 1e-6));
				TestTrue(TEXT("env.big.condition 참 · capped 거짓"), (*Big)->GetBoolField(TEXT("condition")) && !(*Big)->GetBoolField(TEXT("capped")));
			}
			TestFalse(TEXT("숲 자람 끔 — env.forest 없음"), E.HasField(TEXT("forest")));
		}
	}
	TestTrue(TEXT("쓴 뒤 기준선 = 맑음"), Sub->GetBigState().Regions[0].BaseKind == EcoWorldV3::kWeatherClear);

	// 3. 시험용 나무 +6 · 10 초 뒤 +6: 마지막 바뀜 뒤 20 초에 한 번 (대칭차 12)
	FString Message;
	TestEqual(TEXT("시험용 나무 6"), Sub->TestAddTrees(TEXT("Forest"), 6, TOptional<int32>(3), Message), 6);
	Sub->PollEnvironment(true);
	Run(75);
	TestEqual(TEXT("+6 — 아직 스냅숏 하나"), Files().Num(), 1);
	TestEqual(TEXT("시험용 나무 6 더"), Sub->TestAddTrees(TEXT("Forest"), 6, TOptional<int32>(4), Message), 6);
	Sub->PollEnvironment(true);
	const int64 T1 = Sub->GetGlobalStep();
	WrittenAt = -1;
	for (int32 s = 0; s < 400 && WrittenAt < 0; ++s)
	{
		const int32 Before = Sub->GetBigState().Writes;
		Run(1);
		if (Sub->GetBigState().Writes > Before)
		{
			WrittenAt = Sub->GetGlobalStep() - 1;
		}
	}
	TestEqual(TEXT("+12 — 마지막 바뀜 뒤 20 초 = 150 스텝에 한 번"), WrittenAt, T1 + 150);
	if (TestEqual(TEXT("스냅숏 파일 둘"), Files().Num(), 2))
	{
		const TSharedPtr<FJsonObject> Root = ReadJson(FPaths::Combine(Dir, Files().Last()));
		const TSharedPtr<FJsonObject>* Env = nullptr;
		const TSharedPtr<FJsonObject>* Big = nullptr;
		TestTrue(TEXT("env.big.trees.Forest = 12"), Root.IsValid() && Root->TryGetObjectField(TEXT("env"), Env) && (*Env)->TryGetObjectField(TEXT("big"), Big)
														  && static_cast<int32>((*Big)->GetObjectField(TEXT("trees"))->GetNumberField(TEXT("Forest"))) == 12);
	}

	// 4. 규칙 0 (옛 동작): 세기만 바뀌어도 판마다 3 초(23 스텝) 뒤
	SetCVar(Vars[2], TEXT("0"));
	SetCVar(Vars[4], TEXT("rain:0.3"));
	Sub->PollEnvironment(true);
	Run(30);
	SetCVar(Vars[4], TEXT("rain:0.4"));
	Sub->PollEnvironment(true);
	Run(30);
	TestEqual(TEXT("규칙 0 — 판마다 (파일 둘 더)"), Files().Num(), 4);
	TestTrue(TEXT("규칙 0 — 세기만 바뀜도 옛 글 그대로 알림 (비→비)"), Sub->GetLastEnvNotice().EndsWith(TEXT("Forest: 비→비")));
	TestTrue(TEXT("규칙 0 상태 줄"), Sub->BigChangeStatusText().Contains(TEXT("AutoSnapshotRule 0")));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
