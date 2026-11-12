// R9 데모 플레이어 자동화 시험 (2026-11-12).
//
//   AdaptiveEcosystem.R9Demo.FlagOffNoop      깃발이 없으면 서브시스템이 생기지 않고 액터를 하나도 만들지 않는다 (설정 읽기 포함)
//   AdaptiveEcosystem.R9Demo.ReplayFormat     재생 파일 v1·곁 파일 R9FD1 읽기 (쓰고 → 읽기, 덜 써진 끝, 잘못된 마법 글자·값)
//   AdaptiveEcosystem.R9Demo.StageMath        좌표 바꾸기(y 뒤집기·머리 yaw)·무대 고르기·높이 표
//   AdaptiveEcosystem.R9Demo.CoreDeterminism  코어 실시간 원천: 같은 시드 = 같은 프레임, 다른 시드 = 갈림, 죽은 칸은 같은 스텝에 다시 남
//                                             (장면·두뇌 파일이 있어야 함: -EcoR9Demo=<폴더> · eco.R9Demo.Brains · <Saved>/R9Demo/brains. 없으면 경고 뒤 건너뜀)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "EcoR9DemoFrame.h"
#include "EcoR9DemoLiveSource.h"
#include "EcoR9DemoSubsystem.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

#include <limits>

namespace EcoR9DemoTestImpl
{
	using namespace EcoR9Demo;

	bool SameFrame(const FR9Frame& A, const FR9Frame& B)
	{
		if (A.Step != B.Step || A.Agents.size() != B.Agents.size() || A.Carcasses.size() != B.Carcasses.size() || A.Events.size() != B.Events.size() ||
			A.Grass != B.Grass || A.Root != B.Root)
		{
			return false;
		}
		for (std::size_t i = 0; i < A.Agents.size(); ++i)
		{
			const FR9Agent& X = A.Agents[i];
			const FR9Agent& Y = B.Agents[i];
			if (X.Id != Y.Id || X.Species != Y.Species || X.Action != Y.Action || X.Flags != Y.Flags || X.X != Y.X || X.Y != Y.Y || X.Hx != Y.Hx ||
				X.Hy != Y.Hy)
			{
				return false;
			}
		}
		return true;
	}

	/** 장면·두뇌 폴더 찾기 (없으면 빈 글). */
	FString FindBrainDir()
	{
		FString Dir;
		if (FParse::Value(FCommandLine::Get(), TEXT("EcoR9Demo="), Dir, false) && FPaths::FileExists(FPaths::Combine(Dir, TEXT("deer.r9brain"))))
		{
			return Dir;
		}
		if (const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.R9Demo.Brains")))
		{
			Dir = V->GetString();
			if (!Dir.IsEmpty() && FPaths::FileExists(FPaths::Combine(Dir, TEXT("deer.r9brain"))))
			{
				return Dir;
			}
		}
		Dir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("R9Demo"), TEXT("brains"));
		return FPaths::FileExists(FPaths::Combine(Dir, TEXT("deer.r9brain"))) ? Dir : FString();
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoFlagOffNoop, "AdaptiveEcosystem.R9Demo.FlagOffNoop",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoFlagOffNoop::RunTest(const FString& Parameters)
{
	using EMode = FEcoR9DemoSettings::EMode;
	// 설정 읽기 (명령줄 글만 — 콘솔 값이 꺼져 있을 때)
	const IConsoleVariable* Demo = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.R9Demo"));
	TestNotNull(TEXT("콘솔 값 eco.R9Demo 가 있다"), Demo);
	const bool bCVarOff = !Demo || Demo->GetInt() == 0;
	if (bCVarOff)
	{
		TestTrue(TEXT("빈 명령줄 = 끔"), FEcoR9DemoSettings::Resolve(TEXT("")).Mode == EMode::Off);
		TestTrue(TEXT("상관없는 깃발 = 끔"), FEcoR9DemoSettings::Resolve(TEXT("-game -EcoV3Film=x -EcoR9DemoAt=1,2")).Mode == EMode::Off);
	}
	else
	{
		AddWarning(TEXT("eco.R9Demo 가 켜져 있어 '빈 명령줄 = 끔' 검사를 건너뜀"));
	}
	const FEcoR9DemoSettings L = FEcoR9DemoSettings::Resolve(
		TEXT("-game -EcoR9Demo=C:/r9/brains -EcoR9Seed=5 -EcoR9Policy=argmax -EcoR9DemoAt=700.5,-150 -EcoR9Capture=C:/cap,30,12 -EcoR9DemoExitAfter=20"));
	TestTrue(TEXT("-EcoR9Demo= = 실시간"), L.Mode == EMode::Live);
	TestEqual(TEXT("두뇌 폴더"), L.BrainDir, FString(TEXT("C:/r9/brains")));
	TestEqual(TEXT("장면 기본 = <두뇌 폴더>/scene.txt"), L.ScenePath, FPaths::Combine(TEXT("C:/r9/brains"), TEXT("scene.txt")));
	TestEqual(TEXT("시드"), L.Seed, static_cast<uint64>(5));
	TestFalse(TEXT("argmax = 가장 높은 칸"), L.bSample);
	TestTrue(TEXT("무대 자리"), L.bHasAt && FMath::IsNearlyEqual(L.AtM.X, 700.5) && FMath::IsNearlyEqual(L.AtM.Y, -150.0));
	TestEqual(TEXT("녹화 폴더"), L.CaptureDir, FString(TEXT("C:/cap")));
	TestEqual(TEXT("녹화 fps"), L.CaptureFps, 30.0f);
	TestEqual(TEXT("녹화 초"), L.CaptureSeconds, 12.0f);
	TestEqual(TEXT("끝내기"), L.ExitAfterSeconds, 20.0f);
	const FEcoR9DemoSettings R = FEcoR9DemoSettings::Resolve(TEXT("-EcoR9Demo=C:/b -EcoR9Replay=C:/r/demo.r9rp"));
	TestTrue(TEXT("재생 파일이 있으면 재생 판이 먼저"), R.Mode == EMode::Replay && R.ReplayPath == TEXT("C:/r/demo.r9rp"));
	TestTrue(TEXT("팀 섬 원본 맵만"), FEcoR9DemoSettings::MapAllowed(TEXT("/Game/Map/LV_SHC_IslandEcosystem1_WP"), false));
	TestFalse(TEXT("복사 맵은 아님"), FEcoR9DemoSettings::MapAllowed(TEXT("/Game/EcoTest/Maps/LV_EcoV3_Island"), false));
	TestTrue(TEXT("AnyMap 이면 아무 맵"), FEcoR9DemoSettings::MapAllowed(TEXT("/Game/EcoTest/Maps/LV_EcoV3_Island"), true));

	// 실제 월드: 깃발이 없으면 서브시스템도 액터도 없다
	if (FEcoR9DemoSettings::Resolve(FCommandLine::Get()).Mode != EMode::Off)
	{
		AddWarning(TEXT("이 실행에 R9 데모 깃발이 켜져 있어 '월드에 아무것도 없음' 검사를 건너뜀"));
		return true;
	}
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
	if (!TestNotNull(TEXT("시험 월드"), World))
	{
		return false;
	}
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	TestNull(TEXT("깃발 끔 = 서브시스템 없음"), World->GetSubsystem<UEcoR9DemoSubsystem>());
	int32 Ours = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		Ours += It->GetName().StartsWith(TEXT("EcoR9Demo_")) ? 1 : 0;
	}
	TestEqual(TEXT("깃발 끔 = R9 데모 액터 0"), Ours, 0);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoReplayFormat, "AdaptiveEcosystem.R9Demo.ReplayFormat",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoReplayFormat::RunTest(const FString& Parameters)
{
	using namespace EcoR9Demo;
	std::vector<FR9Frame> Frames(3);
	for (int f = 0; f < 3; ++f)
	{
		Frames[static_cast<std::size_t>(f)].Step = static_cast<std::uint32_t>(f);
		for (int i = 0; i < 4; ++i)
		{
			FR9Agent A;
			A.Id = static_cast<std::uint32_t>(i + 1);
			A.Species = static_cast<std::uint8_t>(i % 3);
			A.Action = static_cast<std::uint8_t>((5 * i + f) % kNumActions);
			A.Flags = static_cast<std::uint8_t>(kFlagAlive | (i == 1 ? kFlagEating : 0));
			A.Age = static_cast<std::uint8_t>(i == 3 ? 1 : 0);
			A.X = 1.25f * static_cast<float>(i) + 0.5f * static_cast<float>(f);
			A.Y = 59.0f - A.X;
			A.Hx = 0.6f;
			A.Hy = 0.8f;
			Frames[static_cast<std::size_t>(f)].Agents.push_back(A);
		}
	}
	const std::string Head = "{\"version\":1,\"world_units\":[60.0,60.0],\"note\":\"시험\"}";
	const std::vector<std::uint8_t> Bytes = WriteReplay(Head, Frames);
	FR9Replay R;
	std::string Err;
	TestTrue(TEXT("읽기"), ParseReplay(Bytes.data(), Bytes.size(), R, Err));
	TestTrue(TEXT("머리 그대로"), R.HeaderJson == Head);
	TestEqual(TEXT("프레임 수"), static_cast<int32>(R.Frames.size()), 3);
	if (R.Frames.size() == 3)
	{
		TestEqual(TEXT("좌표 비트 그대로"), R.Frames[2].Agents[3].X, Frames[2].Agents[3].X);
		TestEqual(TEXT("깃발"), static_cast<int32>(R.Frames[1].Agents[1].Flags), static_cast<int32>(kFlagAlive | kFlagEating));
		TestEqual(TEXT("어림"), static_cast<int32>(R.Frames[0].Agents[3].Age), 1);
	}
	FR9Replay Cut;
	TestTrue(TEXT("덜 써진 끝 스텝은 버리고 읽음"), ParseReplay(Bytes.data(), Bytes.size() - 7, Cut, Err) && Cut.Frames.size() == 2 && Cut.bTruncated);
	std::vector<std::uint8_t> Bad = Bytes;
	Bad[1] = 'X';
	TestFalse(TEXT("마법 글자가 틀리면 거부"), ParseReplay(Bad.data(), Bad.size(), Cut, Err));
	std::vector<std::uint8_t> Bad2 = Bytes;
	Bad2[6 + Head.size() + 1 + 6 + 5] = 77;   // 첫 기록의 행동 = 77
	TestFalse(TEXT("행동 번호가 19 이상이면 거부"), ParseReplay(Bad2.data(), Bad2.size(), Cut, Err));
	// 곁 파일: float16 풀·땅속 + 사체
	std::vector<std::uint8_t> Fd(kFoodMagic, kFoodMagic + 6);
	const std::string FoodHead = "{\"version\":1,\"G\":2,\"cell_units\":2.0}";
	Fd.insert(Fd.end(), FoodHead.begin(), FoodHead.end());
	Fd.push_back('\n');
	for (std::uint32_t f = 0; f < 3; ++f)
	{
		AppendU32(Fd, f);
		const std::uint16_t Halves[8] = {0x3C00, 0x3800, 0x0000, 0x3555, 0x3C00, 0x3C00, 0x3C00, 0x3C00};   // 1, 0.5, 0, 1/3 · 땅속 1 ×4
		for (const std::uint16_t H : Halves)
		{
			Fd.push_back(static_cast<std::uint8_t>(H & 0xFF));
			Fd.push_back(static_cast<std::uint8_t>(H >> 8));
		}
		Fd.push_back(static_cast<std::uint8_t>(f == 2 ? 1 : 0));
		if (f == 2)
		{
			Fd.push_back(0);
			Fd.push_back(static_cast<std::uint8_t>(kDeer));
			Fd.push_back(0);
			Fd.push_back(0);
			AppendF32(Fd, 10.0f);
			AppendF32(Fd, 20.0f);
			AppendF32(Fd, 3.0f);
			AppendF32(Fd, 4.0f);
		}
	}
	FR9FoodSide Food;
	TestTrue(TEXT("곁 파일 읽기"), ParseFoodSide(Fd.data(), Fd.size(), Food, Err) && Food.G == 2 && Food.Frames.size() == 3);
	TestEqual(TEXT("곁 파일 붙이기"), static_cast<int32>(AttachFood(Frames, Food)), 3);
	TestTrue(TEXT("float16 풀 값"), Frames[0].Grass.size() == 4 && Frames[0].Grass[1] == 0.5f && FMath::IsNearlyEqual(Frames[0].Grass[3], 1.0f / 3.0f, 1e-3f));
	TestTrue(TEXT("사체"), Frames[2].Carcasses.size() == 1 && Frames[2].Carcasses[0].Meat == 3.0f && Frames[2].Carcasses[0].Species == kDeer);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoStageMath, "AdaptiveEcosystem.R9Demo.StageMath",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoStageMath::RunTest(const FString& Parameters)
{
	using namespace EcoR9Demo;
	FR9StageMap M;
	M.Cx = 75900.0;
	M.Cy = -15600.0;
	double X = 0.0, Y = 0.0;
	M.ToWorld(0.0, 0.0, X, Y);
	TestEqual(TEXT("(0,0) 모서리 x"), X, 75900.0 - 6000.0);
	TestEqual(TEXT("(0,0) 모서리 y (y 뒤집기)"), Y, -15600.0 + 6000.0);
	M.ToWorld(60.0, 60.0, X, Y);
	TestEqual(TEXT("(60,60) 모서리 y"), Y, -15600.0 - 6000.0);
	TestTrue(TEXT("R9 머리 +y (왼쪽 90°) → 언리얼 yaw −90 (위에서 보면 반시계)"), FMath::IsNearlyEqual(FR9StageMap::YawDeg(0.0, 1.0), -90.0, 1e-9));
	TestTrue(TEXT("yaw 사이 (짧은 쪽)"), FMath::IsNearlyEqual(LerpYawDeg(-10.0, 30.0, 0.25), 0.0, 1e-9));
	// 무대 고르기: 왼쪽 언덕, 오른쪽 평지, 오른쪽 위 호수 → 평지에, 호수와 겹치지 않게
	FR9ScanGrid G;
	G.Nx = G.Ny = 100;
	G.CellCm = 400.0;
	G.Height.assign(10000, 0.0f);
	G.Blocked.assign(10000, 0);
	for (int y = 0; y < 100; ++y)
	{
		for (int x = 0; x < 100; ++x)
		{
			G.Height[static_cast<std::size_t>(y * 100 + x)] = x < 50 ? static_cast<float>(x) * 40.0f : 2000.0f;
			G.Blocked[static_cast<std::size_t>(y * 100 + x)] = (x > 85 && y > 85) ? 1 : 0;
		}
	}
	FR9PickParams P;
	P.PrefX = 10000.0;
	P.PrefY = 20000.0;
	const FR9PickResult R = PickStage(G, P);
	TestTrue(TEXT("자리를 찾음"), R.bOk);
	TestTrue(TEXT("평지 쪽 (무대 전체가 x ≥ 50 칸)"), R.Cx >= 50 * 400.0 + 6000.0 - 1e-6);
	TestEqual(TEXT("높이 폭 0"), R.RangeCm, 0.0);
	G.Blocked.assign(10000, 1);
	TestFalse(TEXT("모두 막히면 못 찾음"), PickStage(G, P).bOk);
	// 높이 표: 두 점 사이 잇기·표 밖은 가장자리·빈 표본은 대신값
	FR9HeightTable T;
	T.Nx = T.Ny = 3;
	T.Step = 100.0;
	T.Fallback = -5.0;
	T.Z = {0, 100, 200, 0, 100, 200, 0, 100, 200};
	TestTrue(TEXT("잇기"), FMath::IsNearlyEqual(T.At(50.0, 50.0), 50.0, 1e-9));
	TestTrue(TEXT("표 밖"), FMath::IsNearlyEqual(T.At(-100.0, 0.0), 0.0, 1e-9));
	T.Z[4] = std::numeric_limits<float>::quiet_NaN();
	TestTrue(TEXT("빈 표본"), FMath::IsNearlyEqual(T.At(100.0, 100.0), -5.0, 1e-9));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoCoreDeterminism, "AdaptiveEcosystem.R9Demo.CoreDeterminism",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoCoreDeterminism::RunTest(const FString& Parameters)
{
	using namespace EcoR9Demo;
	using namespace EcoR9DemoTestImpl;
	if (!FR9LiveSource::Available())
	{
		AddWarning(TEXT("이 빌드에는 R9 코어가 없다 — 건너뜀"));
		return true;
	}
	const FString Dir = FindBrainDir();
	FString Scene;
	if (!FParse::Value(FCommandLine::Get(), TEXT("EcoR9Scene="), Scene, false))
	{
		const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.R9Demo.Scene"));
		Scene = V ? V->GetString() : FString();
	}
	if (Scene.IsEmpty() && !Dir.IsEmpty())
	{
		Scene = FPaths::Combine(Dir, TEXT("scene.txt"));
	}
	if (Dir.IsEmpty() || !FPaths::FileExists(Scene))
	{
		AddWarning(TEXT("두뇌 폴더·장면 파일을 못 찾음 (-EcoR9Demo=<폴더> -EcoR9Scene=<파일> · eco.R9Demo.Brains·Scene · <Saved>/R9Demo/brains/scene.txt) — 건너뜀"));
		return true;
	}
	FR9LiveConfig C;
	TArray<uint8> Bytes;
	if (!TestTrue(TEXT("장면 읽기"), FFileHelper::LoadFileToArray(Bytes, *Scene)))
	{
		return false;
	}
	C.SceneText.assign(reinterpret_cast<const char*>(Bytes.GetData()), static_cast<std::size_t>(Bytes.Num()));
	static const TCHAR* const Names[3] = {TEXT("deer.r9brain"), TEXT("wolf.r9brain"), TEXT("boar.r9brain")};
	for (int32 k = 0; k < 3; ++k)
	{
		Bytes.Reset();
		if (!TestTrue(TEXT("두뇌 읽기"), FFileHelper::LoadFileToArray(Bytes, *FPaths::Combine(Dir, Names[k]))))
		{
			return false;
		}
		C.BrainBytes[k].assign(Bytes.GetData(), Bytes.GetData() + Bytes.Num());
	}
	C.Seed = 11;
	C.bSample = true;
	FR9LiveConfig C2 = C;
	C2.Seed = 12;
	FR9LiveSource A, B, D;
	FR9WorldInfo Ia, Ib, Id;
	FR9Frame Fa, Fb, Fd;
	std::string Err;
	if (!TestTrue(TEXT("코어 시작"), A.Init(C, Ia, Fa, Err) && B.Init(C, Ib, Fb, Err) && D.Init(C2, Id, Fd, Err)))
	{
		AddError(FString(UTF8_TO_TCHAR(Err.c_str())));
		return false;
	}
	TestTrue(TEXT("시작 장면 같음"), SameFrame(Fa, Fb));
	TestEqual(TEXT("먹이 격자 크기"), static_cast<int32>(Fa.Grass.size()), Ia.G * Ia.G);
	std::int32_t Alive0[kNumSpecies];
	CountAlive(Fa, Alive0);
	int32 Mismatch = 0, CountsChanged = 0;
	bool bDiverged = false;
	for (int32 t = 0; t < 600; ++t)
	{
		A.Next(Fa, Err);
		B.Next(Fb, Err);
		D.Next(Fd, Err);
		Mismatch += SameFrame(Fa, Fb) ? 0 : 1;
		bDiverged = bDiverged || !SameFrame(Fa, Fd);
		std::int32_t Al[kNumSpecies];
		CountAlive(Fa, Al);
		CountsChanged += (Al[0] != Alive0[0] || Al[1] != Alive0[1] || Al[2] != Alive0[2]) ? 1 : 0;
	}
	TestEqual(TEXT("같은 시드 600 스텝 = 같은 프레임"), Mismatch, 0);
	TestTrue(TEXT("다른 시드 = 갈림"), bDiverged);
	TestEqual(TEXT("학습 세계: 죽은 칸은 같은 스텝에 다시 남 (종별 마릿수 그대로)"), CountsChanged, 0);
	return true;
}

// 에디터 PIE 길 흉내: 명령줄 없이 콘솔 값만 켜고(eco.R9Demo 1) 월드를 만들면 서브시스템이 생기고, 기본 폴더(<Saved>/R9Demo/brains)의
// 두뇌·장면으로 무대를 세워 동물 몸을 만들고 스텝이 넘어가는지 본다. 시험 월드에는 지형이 없어 eco.R9Demo.At 0,0 · AnyMap 1 로 자리 훑기만 건너뛴다.
// 월드 전체 틱 대신 월드 시간을 직접 넘기고 이 서브시스템만 틱한다 (다른 서브시스템을 깨우지 않게). 끝나면 콘솔 값을 되돌린다.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoConsoleStart, "AdaptiveEcosystem.R9Demo.ConsoleStart",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoConsoleStart::RunTest(const FString& Parameters)
{
	using EMode = FEcoR9DemoSettings::EMode;
	const TCHAR* Cmd = FCommandLine::Get();
	FString Ignored;
	if (FParse::Value(Cmd, TEXT("EcoR9Demo="), Ignored, false) || FParse::Value(Cmd, TEXT("EcoR9Replay="), Ignored, false) || FParse::Param(Cmd, TEXT("EcoR9Demo")))
	{
		AddWarning(TEXT("명령줄에 R9 데모 깃발이 있어 '콘솔 값만으로 켜기' 검사를 건너뜀"));
		return true;
	}
	const FString Dir = FPaths::Combine(FEcoR9DemoSettings::DefaultDir(), TEXT("brains"));
	if (!FPaths::FileExists(FPaths::Combine(Dir, TEXT("deer.r9brain"))) || !FPaths::FileExists(FPaths::Combine(Dir, TEXT("scene.txt"))))
	{
		AddWarning(FString::Printf(TEXT("기본 두뇌 폴더 %s 에 deer.r9brain·scene.txt 가 없어 건너뜀"), *Dir));
		return true;
	}
	struct FCVarRestore
	{
		TArray<TPair<IConsoleVariable*, FString>> Saved;
		void Set(const TCHAR* Name, const TCHAR* Value)
		{
			if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name))
			{
				Saved.Add({V, V->GetString()});
				V->Set(Value, ECVF_SetByConsole);
			}
		}
		~FCVarRestore()
		{
			for (int32 i = Saved.Num() - 1; i >= 0; --i)
			{
				Saved[i].Key->Set(*Saved[i].Value, ECVF_SetByConsole);
			}
		}
	} Restore;
	Restore.Set(TEXT("eco.R9Demo.Brains"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Scene"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.AnyMap"), TEXT("1"));
	Restore.Set(TEXT("eco.R9Demo.At"), TEXT("0,0"));
	Restore.Set(TEXT("eco.R9Demo"), TEXT("1"));
	const FEcoR9DemoSettings S = FEcoR9DemoSettings::Resolve(Cmd);
	TestTrue(TEXT("콘솔 eco.R9Demo 1 = 실시간"), S.Mode == EMode::Live);
	TestEqual(TEXT("두뇌 폴더 기본 = <Saved>/R9Demo/brains"), S.BrainDir, Dir);
	TestEqual(TEXT("장면 기본 = <두뇌 폴더>/scene.txt"), S.ScenePath, FPaths::Combine(Dir, TEXT("scene.txt")));

	UWorld* World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
	if (!TestNotNull(TEXT("시험 월드"), World))
	{
		return false;
	}
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	UEcoR9DemoSubsystem* Sub = World->GetSubsystem<UEcoR9DemoSubsystem>();
	TestNotNull(TEXT("월드를 만들 때 콘솔 값을 읽어 서브시스템이 생김 (Play 시작과 같은 때)"), Sub);
	if (Sub)
	{
		Sub->OnWorldBeginPlay(*World);
		TestTrue(TEXT("시작함 (거부·실패 없음)"), Sub->IsActive());
		const float Dt = 1.0f / 30.0f;
		for (int32 i = 0; i < 150 && Sub->IsActive(); ++i)   // 월드 5 초
		{
			World->TimeSeconds += Dt;
			World->RealTimeSeconds += Dt;
			World->UnpausedTimeSeconds += Dt;
			Sub->Tick(Dt);
		}
		TestTrue(TEXT("무대가 서서 도는 중"), Sub->IsRunning());
		TestTrue(TEXT("동물 몸이 생김 (36 = 사슴 24 · 늑대 4 · 멧돼지 8)"), Sub->NumBodies() >= 30);
		TestTrue(TEXT("스텝이 넘어감 (5 초 ≈ 37 스텝)"), Sub->NumStepsShown() >= 20);
		AddInfo(FString::Printf(TEXT("몸 %d · 스텝 %lld · 액터 %d"), Sub->NumBodies(), static_cast<long long>(Sub->NumStepsShown()), Sub->NumSpawnedActors()));
	}
	// 월드를 먼저 지운다 (서브시스템이 액터를 치울 때 월드 컨텍스트가 있어야 경고가 없다)
	World->DestroyWorld(false);
	GEngine->DestroyWorldContext(World);
	return true;
}

#endif
