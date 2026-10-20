// 환경 스냅숏 자동화 시험 (10-18 적응 고리, EcoV3Snapshot.cpp — 명세 Docs/RL_Policy/SEASON_SNAPSHOT_SPEC.md 11절).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Snapshot"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 묶음:
//   Snapshot.Export      지역 둘(숲 원판·비, 메마른 땅 맑음)의 스냅숏을 쓰고 다시 읽는다: 먹이 용량·지금 먹이·원판·은신처가 세계 값과 비트 단위로 같고(17 자리),
//                        수·설정·두뇌·계약 해시가 맞고, 쓰기는 세계(난수·먹이·기록)를 바꾸지 않는다. 경로 규칙(빈 값·폴더·파일)
//   Snapshot.Scheduled   예정 스냅숏 (eco.IntegratedV3.SnapshotAt): 그 시각 앞 경계에서는 쓰지 않고, 처음 넘는 경계에서 한 번만 쓴다

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "Dom/JsonObject.h"
#include "EcoTestWorld.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace EcoV3SnapshotTestImpl
{
	struct FTwoRegions
	{
		EcoTest::FScopedTestWorld W;
		UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
		FEcoV3RegionContext* Forest = nullptr;
		FEcoV3RegionContext* Barren = nullptr;
		std::vector<double> ForestDiscs = {10.25, 20.5, 0.375, 33.125, 41.0625, 0.4296875, 50.1, 12.3, 0.41};

		bool Setup(FAutomationTestBase& Test, int64 Seed)
		{
			Sub = W.World ? W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
			if (!Test.TestNotNull(TEXT("통합 서브시스템"), Sub))
			{
				return false;
			}
			FEcoV3IntegratedSettings S;
			S.Seed = Seed;
			Sub->ActivateForTest(S, /*bTerrain*/ false);
			const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(S.StageSizeUnits, 6.0);
			EcoWorldV3::FWorldConfig Cf = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, 1, 128, 4, Covers, FName(TEXT("Forest")));
			Cf.Obstacles.Discs = ForestDiscs;
			Forest = Sub->AddContext(FName(TEXT("Forest")), 1, FVector(1000.0, 2000.0, 30.0), Cf, 128, 4);
			const EcoWorldV3::FWorldConfig Cb = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, 0, 128, 4, Covers, FName(TEXT("Barren")));
			Barren = Sub->AddContext(FName(TEXT("Barren")), 0, FVector(-50000.0, 0.0, 0.0), Cb, 128, 4);
			return Test.TestNotNull(TEXT("숲 세계"), Forest) && Test.TestNotNull(TEXT("메마른 땅 세계"), Barren);
		}
	};

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

	/** JSON 수 배열이 값 목록과 비트 단위로 같은가 (double ==). */
	bool SameNumbers(const TArray<TSharedPtr<FJsonValue>>& A, const std::vector<double>& B)
	{
		if (A.Num() != static_cast<int32>(B.size()))
		{
			return false;
		}
		for (int32 i = 0; i < A.Num(); ++i)
		{
			if (!A[i].IsValid() || A[i]->AsNumber() != B[static_cast<size_t>(i)])
			{
				return false;
			}
		}
		return true;
	}

	/** [[x, y, r], …] 이 평평한 목록과 비트 단위로 같은가. */
	bool SameTriples(const TArray<TSharedPtr<FJsonValue>>& A, const std::vector<double>& Flat)
	{
		if (A.Num() * 3 != static_cast<int32>(Flat.size()))
		{
			return false;
		}
		for (int32 k = 0; k < A.Num(); ++k)
		{
			const TArray<TSharedPtr<FJsonValue>>& T = A[k]->AsArray();
			if (T.Num() != 3)
			{
				return false;
			}
			for (int32 j = 0; j < 3; ++j)
			{
				if (T[j]->AsNumber() != Flat[static_cast<size_t>(3 * k + j)])
				{
					return false;
				}
			}
		}
		return true;
	}

	void SetCVar(const TCHAR* Name, const TCHAR* Value)
	{
		if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name))
		{
			V->Set(Value, ECVF_SetByCode);
		}
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3SnapshotExportTest,
	"AdaptiveEcosystem.Policy.V3.Snapshot.Export",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3SnapshotExportTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3SnapshotTestImpl;
	FTwoRegions H;
	if (!H.Setup(*this, 37300))
	{
		return false;
	}
	// 지금 상태를 흉내 낸다: 먹은 셀(먹이 < 용량), 잡힘·굶음, 입양 수, 전역 스텝 5
	EcoWorldV3::FWorldState& F = H.Forest->Sim;
	for (size_t k = 0; k < F.Food.Food.size(); k += 7)
	{
		F.Food.Food[k] *= 0.37;
	}
	F.Stats.Caught = 3;
	F.Stats.Starved = 1;
	H.Forest->AdoptedDeer = 128;
	H.Forest->AdoptedWolves = 4;
	H.Barren->AdoptedDeer = 128;
	for (int32 s = 0; s < 5; ++s)
	{
		H.Sub->FinishGlobalStep();
	}
	const uint64 RngBefore = F.Rng.State;
	const std::vector<double> CapBefore = F.Food.Cap;
	const std::vector<double> FoodBefore = F.Food.Food;
	const int64 CaughtBefore = F.Stats.Caught;

	const FString Path = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"), TEXT("EcoV3SnapshotTest.json"));
	ON_SCOPE_EXIT
	{
		IFileManager::Get().Delete(*Path);
	};
	if (!TestTrue(TEXT("쓰기"), H.Sub->ExportSnapshot(Path, TEXT("시험 Snapshot.Export"))))
	{
		return false;
	}
	TestTrue(TEXT("쓰기는 세계를 바꾸지 않는다 (난수·용량·먹이·기록)"),
			 F.Rng.State == RngBefore && F.Food.Cap == CapBefore && F.Food.Food == FoodBefore && F.Stats.Caught == CaughtBefore);

	const TSharedPtr<FJsonObject> Root = ReadJson(Path);
	if (!TestTrue(TEXT("다시 읽기"), Root.IsValid()))
	{
		return false;
	}
	TestEqual(TEXT("형식"), Root->GetStringField(TEXT("format")), FString(TEXT("eco_v3_snapshot")));
	TestEqual(TEXT("판"), static_cast<int32>(Root->GetNumberField(TEXT("version"))), 1);
	TestEqual(TEXT("세션 시드"), static_cast<int64>(Root->GetNumberField(TEXT("session_seed"))), static_cast<int64>(37300));
	TestEqual(TEXT("전역 스텝"), static_cast<int64>(Root->GetNumberField(TEXT("global_step"))), H.Sub->GetGlobalStep());
	TestEqual(TEXT("계약 해시 = 빌드 값"), Root->GetStringField(TEXT("contract_hash")),
			  FString::Printf(TEXT("0x%016llx"), static_cast<unsigned long long>(EcoPolicyV3::kContractHash)));
	TestEqual(TEXT("두뇌 id = 지금 두뇌"), Root->GetObjectField(TEXT("brain"))->GetStringField(TEXT("id")), H.Sub->GetActiveBrain().Id);
	TestEqual(TEXT("두뇌 가중치 sha256"), Root->GetObjectField(TEXT("brain"))->GetStringField(TEXT("weights_sha256")), H.Sub->GetActiveBrain().WeightsSha256);
	{
		// 적응 고리 판 (10-21, LIVE_ADAPT_SPEC.md 2절): brain.adapt 는 늘 객체, 'adapt' 블록이 없는 두뇌(내장·손 파일)면 빈 객체
		const TSharedPtr<FJsonObject>* Adapt = nullptr;
		const bool bAdaptObject = Root->GetObjectField(TEXT("brain"))->TryGetObjectField(TEXT("adapt"), Adapt) && Adapt && Adapt->IsValid();
		TestTrue(TEXT("두뇌 adapt 객체"), bAdaptObject);
		if (bAdaptObject && !H.Sub->GetActiveBrain().bAdapt)
		{
			TestEqual(TEXT("adapt 블록이 없는 두뇌 → 빈 객체"), (*Adapt)->Values.Num(), 0);
		}
	}
	{
		const TSharedPtr<FJsonObject> S = Root->GetObjectField(TEXT("settings"));
		const FEcoV3IntegratedSettings& Want = H.Sub->GetSettings();
		TestTrue(TEXT("설정 스위치 (얼기 막음·도주 반사·은신처 안전·장애물·날씨·늑대 수·식사 스텝)"),
				 S->GetBoolField(TEXT("no_freeze")) == Want.bNoFreeze && S->GetBoolField(TEXT("wild_flight")) == Want.bWildFlight
					 && S->GetBoolField(TEXT("shelter_safe")) == Want.bShelterSafe && S->GetBoolField(TEXT("obstacles")) == Want.bObstacles
					 && S->GetBoolField(TEXT("weather")) == Want.bWeather && static_cast<int32>(S->GetNumberField(TEXT("wolves_per_region"))) == Want.WolvesPerRegion
					 && static_cast<int32>(S->GetNumberField(TEXT("wolf_eat_steps"))) == Want.WolfEatSteps());
	}
	const TArray<TSharedPtr<FJsonValue>>& Regions = Root->GetArrayField(TEXT("regions"));
	if (!TestEqual(TEXT("지역 수"), Regions.Num(), 2))
	{
		return false;
	}
	const FEcoV3RegionContext* Ctxs[2] = {H.Forest, H.Barren};
	for (int32 r = 0; r < 2; ++r)
	{
		const FEcoV3RegionContext& C = *Ctxs[r];
		const EcoWorldV3::FWorldState& Wr = C.Sim;
		const TSharedPtr<FJsonObject> R = Regions[r]->AsObject();
		const FString Tag = C.RegionId.ToString();
		TestEqual(*FString::Printf(TEXT("%s 이름"), *Tag), R->GetStringField(TEXT("region")), Tag);
		TestEqual(*FString::Printf(TEXT("%s 지역 번호"), *Tag), static_cast<int32>(R->GetNumberField(TEXT("region_index"))), C.RegionRuntimeIndex);
		const TSharedPtr<FJsonObject> Food = R->GetObjectField(TEXT("food"));
		const int32 Gw = static_cast<int32>(Food->GetNumberField(TEXT("gw")));
		TestTrue(*FString::Printf(TEXT("%s 먹이 격자 한 변 = 세계 (%d)"), *Tag, Gw), Gw == Wr.Food.Gw && Gw > 0);
		TestTrue(*FString::Printf(TEXT("%s 먹이 용량 = 세계 (비트 단위, 셀 %d)"), *Tag, Gw * Gw), SameNumbers(Food->GetArrayField(TEXT("cap")), Wr.Food.Cap));
		TestTrue(*FString::Printf(TEXT("%s 지금 먹이 = 세계 (비트 단위)"), *Tag), SameNumbers(Food->GetArrayField(TEXT("food")), Wr.Food.Food));
		TestEqual(*FString::Printf(TEXT("%s 먹이 합"), *Tag), Food->GetNumberField(TEXT("food_total")), Wr.Food.Total());
		std::vector<double> CoverFlat;
		for (const EcoObservationV3::FCoverInput& Cv : Wr.Config.Covers)
		{
			CoverFlat.insert(CoverFlat.end(), {Cv.X, Cv.Y, Cv.Radius});
		}
		TestTrue(*FString::Printf(TEXT("%s 은신처 원 = 세계"), *Tag), SameTriples(R->GetArrayField(TEXT("covers")), CoverFlat));
		TestTrue(*FString::Printf(TEXT("%s 원판 = 세계 (비트 단위)"), *Tag),
				 SameTriples(R->GetObjectField(TEXT("obstacles"))->GetArrayField(TEXT("discs")), Wr.Config.Obstacles.Discs));
		const TSharedPtr<FJsonObject> World = R->GetObjectField(TEXT("world"));
		TestTrue(*FString::Printf(TEXT("%s 세계 설정 (무대·늑대 구성·식사·낮밤·난수 갈래)"), *Tag),
				 World->GetNumberField(TEXT("world_size")) == Wr.Config.WorldSize && static_cast<int32>(World->GetNumberField(TEXT("num_stalkers"))) == Wr.Config.NumStalkers
					 && static_cast<int32>(World->GetNumberField(TEXT("num_chasers"))) == Wr.Config.NumChasers
					 && static_cast<int32>(World->GetNumberField(TEXT("pred_eat_cd"))) == Wr.ThreatCfg.PredEatCd
					 && static_cast<int32>(World->GetNumberField(TEXT("day_period"))) == Wr.Config.DayPeriod
					 && static_cast<uint64>(World->GetNumberField(TEXT("rng_stream"))) == Wr.Config.RngStream);
		TestEqual(*FString::Printf(TEXT("%s 날씨"), *Tag), World->GetObjectField(TEXT("weather"))->GetStringField(TEXT("kind")),
				  FString(r == 0 ? TEXT("rain") : TEXT("clear")));
		const TSharedPtr<FJsonObject> Deer = R->GetObjectField(TEXT("deer"));
		const int64 Caught = static_cast<int64>(Deer->GetNumberField(TEXT("caught")));
		const int64 Starved = static_cast<int64>(Deer->GetNumberField(TEXT("starved")));
		TestTrue(*FString::Printf(TEXT("%s 사슴 수 (입양·잡힘·굶음·산 = 입양 − 잡힘 − 굶음)"), *Tag),
				 static_cast<int32>(Deer->GetNumberField(TEXT("adopted"))) == C.AdoptedDeer && Caught == Wr.Stats.Caught && Starved == Wr.Stats.Starved
					 && static_cast<int64>(Deer->GetNumberField(TEXT("alive"))) == C.AdoptedDeer - Caught - Starved);
	}
	TestTrue(TEXT("숲은 원판 셋·먹은 셀이 있다 (시험 장면)"), H.Forest->Sim.Config.Obstacles.Num() == 3 && H.Forest->Sim.Food.Total() < H.Forest->StartFood);
	TestTrue(TEXT("메마른 땅 원판 없음"), H.Barren->Sim.Config.Obstacles.Num() == 0);

	// 경로 규칙
	const FString Name = TEXT("eco_v3_snapshot_s37300_t5.json");
	const FString Def = H.Sub->SnapshotPath(FString());
	TestTrue(*FString::Printf(TEXT("기본 경로 Saved/EcoSnapshots/%s (%s)"), *Name, *Def),
			 Def.EndsWith(FString(TEXT("EcoSnapshots/")) + Name) && FPaths::IsUnderDirectory(Def, FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir())));
	const FString Folder = H.Sub->SnapshotPath(TEXT("C:/EcoSnapTest/sub"));
	TestEqual(TEXT("폴더면 그 안"), Folder, FString(TEXT("C:/EcoSnapTest/sub/")) + Name);
	const FString File = H.Sub->SnapshotPath(TEXT("Saved/x/one.json"));
	TestEqual(TEXT("상대 파일은 프로젝트 폴더 기준"), File, FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("Saved/x/one.json"))));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3SnapshotScheduledTest,
	"AdaptiveEcosystem.Policy.V3.Snapshot.Scheduled",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3SnapshotScheduledTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3SnapshotTestImpl;
	const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"), TEXT("EcoV3SnapshotScheduled.json")));
	IFileManager::Get().Delete(*Path);
	ON_SCOPE_EXIT
	{
		SetCVar(TEXT("eco.IntegratedV3.SnapshotAt"), TEXT("-1"));
		SetCVar(TEXT("eco.IntegratedV3.SnapshotOut"), TEXT(""));
		IFileManager::Get().Delete(*Path);
	};
	FTwoRegions H;
	if (!H.Setup(*this, 37301))
	{
		return false;
	}
	// 1.3 초 = 전역 스텝 9.75 → 처음 넘는 경계는 스텝 10 (1.333 초)
	SetCVar(TEXT("eco.IntegratedV3.SnapshotAt"), TEXT("1.3"));
	SetCVar(TEXT("eco.IntegratedV3.SnapshotOut"), *Path);
	int64 WrittenAt = -1;
	int32 Writes = 0;
	for (int32 s = 0; s <= 30; ++s)
	{
		const bool bBefore = IFileManager::Get().FileExists(*Path);
		H.Sub->MaybeScheduledSnapshot();
		if (!bBefore && IFileManager::Get().FileExists(*Path))
		{
			++Writes;
			WrittenAt = H.Sub->GetGlobalStep();
			const TSharedPtr<FJsonObject> Root = ReadJson(Path);
			TestTrue(TEXT("예정 스냅숏 내용 (전역 스텝·까닭)"), Root.IsValid() && static_cast<int64>(Root->GetNumberField(TEXT("global_step"))) == WrittenAt
						 && Root->GetStringField(TEXT("why")).Contains(TEXT("SnapshotAt")));
			IFileManager::Get().Delete(*Path);   // 지운 뒤 다시 생기면 두 번 쓴 것이다
		}
		H.Sub->FinishGlobalStep();
	}
	TestEqual(TEXT("처음 넘는 경계(전역 스텝 10)에서"), WrittenAt, static_cast<int64>(10));
	TestEqual(TEXT("한 번만 쓴다"), Writes, 1);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
