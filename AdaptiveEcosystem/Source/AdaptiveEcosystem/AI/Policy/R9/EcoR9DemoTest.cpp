// R9 데모 플레이어 자동화 시험 (2026-11-12).
//
//   AdaptiveEcosystem.R9Demo.FlagOffNoop      깃발이 없으면 서브시스템이 생기지 않고 액터를 하나도 만들지 않는다 (설정 읽기 포함)
//   AdaptiveEcosystem.R9Demo.ReplayFormat     재생 파일 v1·곁 파일 R9FD1 읽기 (쓰고 → 읽기, 덜 써진 끝, 잘못된 마법 글자·값)
//   AdaptiveEcosystem.R9Demo.StageMath        좌표 바꾸기(y 뒤집기·머리 yaw)·무대 고르기·높이 표
//   AdaptiveEcosystem.R9Demo.CoreDeterminism  코어 실시간 원천: 같은 시드 = 같은 프레임, 다른 시드 = 갈림, 죽은 칸은 같은 스텝에 다시 남
//                                             (장면·두뇌 파일이 있어야 함: -EcoR9Demo=<폴더> · eco.R9Demo.Brains · <Saved>/R9Demo/brains. 없으면 경고 뒤 건너뜀)
//   AdaptiveEcosystem.R9Demo.ConsoleStart     콘솔 eco.R9Demo 1 만으로 켜짐 (PIE 길 흉내)
//   AdaptiveEcosystem.R9Demo.StagePick        (2026-11-12 맵 제한 없앰) 자리 고르기가 막힌 칸·기존 생태를 피함, 바닥 메시는 막지 않음, 가장 덜 막힌 곳
//   AdaptiveEcosystem.R9Demo.AnyMap           섬이 아닌 아무 맵 + 기존 생태 지역이 있어도 거부하지 않고 켜지며, 무대가 그 지역 상자 밖에 선다
//   AdaptiveEcosystem.R9Demo.AtOverride       콘솔 eco.R9Demo.At x,y 가 자동 고르기를 덮어쓴다 (PIE 는 명령줄이 없어 콘솔 값)
//   (2026-11-13 맵 전체 땅)
//   AdaptiveEcosystem.R9Demo.WholeMath        엔진 없는 부분: 훑기 → 코어 땅 지도 (y 뒤집기 = 화면 좌표와 같은 칸), 가장 큰 이어진 땅, 세계 정사각,
//                                             은신처 곁 후보, 풀 창, 몸 배정, 멧돼지 이름·애니 이름 고르기
//   AdaptiveEcosystem.R9Demo.WholeMap         맵 전체 모드: 바닥 400 m + 기둥(막힌 칸) + 무리 자리 TargetPoint + 팀 동물 몸 → 땅 지도에 막힌 칸이 그 자리로 넘어가고,
//                                             사람이 놓은 무리 자리가 넘어가고, 예전 동물 몸은 숨었다가 끄면 다시 보인다. 코어에 큰 세계 생성기가 있으면 큰 세계로 돈다
//   AdaptiveEcosystem.R9Demo.PlayToggle       Play 중 켜기/끄기: eco.R9Demo 0 으로 시작한 월드에서 1 → 시작, 다시 1 → 두 번 만들지 않음, 0 → 다 치움, 1 → 다시 시작
//   (2026-11-13 03:30 옛 관찰 카메라 꼴 · 시작 맵에서만)
//   AdaptiveEcosystem.R9Demo.CamKeys          키 → 동작 (옛 키 1~5·0·, .·- =·휠·G·H 는 옛 뜻 그대로, R9 만 6·7), 모드 값 = 키 숫자, 한 키 한 동작,
//                                             팀·기본 입력 키·자유 카메라 이동 키와 안 겹침, 화면 줄, 거리·숙임 = 옛 값, 화면 가운데 고르기
//   AdaptiveEcosystem.R9Demo.CamSwitch        도는 데모에서 키 → 모드·대상, 키로 바꾸면 한 프레임 만에 그 시점 (초점·방위·숙임·거리 = 목표),
//                                             0 = 그 자리 자유 카메라 (다시 0 도 자유 카메라), 자유 카메라 속도 = -, 다시 누름·. , = 다음·이전 대상, 줌, H, 콘솔 eco.R9Demo.Cam
//   AdaptiveEcosystem.R9Demo.OnlyMap          맵 거르기 (패키지·오브젝트 경로·짧은 이름·PIE 머리·여럿), 명령줄 깃발은 거르지 않음,
//                                             OnlyMap 밖 시험 월드 = Play 시작 때 아무것도 안 만듦 (옛 관찰 카메라 값도 그대로) · Play 중 직접 eco.R9Demo 1 은 켬 · 목록 안 = 켬

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "AI/Policy/EcoV3ObserverCamera.h"
#include "EcoR9DemoCam.h"
#include "EcoR9DemoFrame.h"
#include "EcoR9DemoLiveSource.h"
#include "EcoR9DemoSubsystem.h"
#include "EcoR9DemoWhole.h"
#include "Components/StaticMeshComponent.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TargetPoint.h"
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

	/** 콘솔 값을 바꾸고 끝날 때 되돌린다. */
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
	};

	/** 콘솔 값만으로 켜는 월드 시험을 돌릴 수 있는가 (명령줄 깃발 없음 + 기본 폴더에 두뇌·장면). 아니면 이유. */
	bool CanRunConsoleWorld(FString& OutWhy)
	{
		const TCHAR* Cmd = FCommandLine::Get();
		FString Ignored;
		if (FParse::Value(Cmd, TEXT("EcoR9Demo="), Ignored, false) || FParse::Value(Cmd, TEXT("EcoR9Replay="), Ignored, false) || FParse::Param(Cmd, TEXT("EcoR9Demo")) ||
			FParse::Value(Cmd, TEXT("EcoR9DemoAt="), Ignored, false) || FParse::Value(Cmd, TEXT("EcoR9DemoPref="), Ignored, false))
		{
			OutWhy = TEXT("명령줄에 R9 데모 깃발이 있다");
			return false;
		}
		const FString Dir = FPaths::Combine(FEcoR9DemoSettings::DefaultDir(), TEXT("brains"));
		if (!FPaths::FileExists(FPaths::Combine(Dir, TEXT("deer.r9brain"))) || !FPaths::FileExists(FPaths::Combine(Dir, TEXT("scene.txt"))))
		{
			OutWhy = FString::Printf(TEXT("기본 두뇌 폴더 %s 에 deer.r9brain·scene.txt 가 없다"), *Dir);
			return false;
		}
		return true;
	}

	/** 월드 시간을 직접 넘기며 이 서브시스템만 틱한다 (다른 서브시스템을 깨우지 않게). */
	void TickDemo(UWorld& World, UEcoR9DemoSubsystem& Sub, int32 Frames)
	{
		const float Dt = 1.0f / 30.0f;
		for (int32 i = 0; i < Frames && Sub.IsActive(); ++i)
		{
			World.TimeSeconds += Dt;
			World.RealTimeSeconds += Dt;
			World.UnpausedTimeSeconds += Dt;
			Sub.Tick(Dt);
		}
	}

	/** 평평한 격자 (높이 0, 모두 열림). */
	FR9ScanGrid FlatGrid(int32 Cells, double CellCm, double X0, double Y0)
	{
		FR9ScanGrid G;
		G.Nx = G.Ny = Cells;
		G.CellCm = CellCm;
		G.X0 = X0;
		G.Y0 = Y0;
		G.Height.assign(static_cast<std::size_t>(Cells) * static_cast<std::size_t>(Cells), 0.0f);
		G.Blocked.assign(G.Height.size(), 0);
		return G;
	}

	/** 고른 무대 정사각 (한 변 Side, 가운데 Cx·Cy) 안 칸 가운데 가운데 Pred 가 참인 칸 수. */
	template <typename PredT>
	int32 CountInStage(const FR9ScanGrid& G, double Cx, double Cy, double Side, PredT&& Pred)
	{
		int32 N = 0;
		for (int32 y = 0; y < G.Ny; ++y)
		{
			for (int32 x = 0; x < G.Nx; ++x)
			{
				if (FMath::Abs(G.CellX(x) - Cx) < 0.5 * Side && FMath::Abs(G.CellY(y) - Cy) < 0.5 * Side)
				{
					N += Pred(G.Index(x, y)) ? 1 : 0;
				}
			}
		}
		return N;
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
	// 맵 제한 없음 (2026-11-12): 설정에 맵 이름이 없다. 자리 찾기 시작점은 주지 않으면 플레이어 시작점 (bHasPref 거짓)
	TestFalse(TEXT("시작점을 주지 않으면 플레이어 시작점에서 찾는다 (예전 섬 선호점 759,-156 없음)"), L.bHasPref);
	const FEcoR9DemoSettings Pf = FEcoR9DemoSettings::Resolve(TEXT("-EcoR9Demo=C:/b -EcoR9DemoPref=12.5,-30"));
	TestTrue(TEXT("-EcoR9DemoPref= 로 시작점을 줌"), Pf.bHasPref && FMath::IsNearlyEqual(Pf.PrefM.X, 12.5) && FMath::IsNearlyEqual(Pf.PrefM.Y, -30.0));
	TestFalse(TEXT("-EcoR9DemoPref= 가 틀리면 무시"), FEcoR9DemoSettings::Resolve(TEXT("-EcoR9Demo=C:/b -EcoR9DemoPref=abc")).bHasPref);

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

	// 맵 제한이 없어졌으니: 콘솔 eco.R9Demo 1 이 켜져 있어도 자동화 시험 중에는 eco.R9Demo.AllowInTests 1 없이 서브시스템이 생기지 않는다
	// (사용자가 데모를 켜 둔 채 다른 팀 시험을 돌려도 그 시험 월드에 데모가 끼지 않음)
	{
		EcoR9DemoTestImpl::FCVarRestore Restore;
		Restore.Set(TEXT("eco.R9Demo.AllowInTests"), TEXT("0"));
		Restore.Set(TEXT("eco.R9Demo"), TEXT("1"));
		UWorld* Other = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
		if (TestNotNull(TEXT("다른 시험 월드"), Other))
		{
			FWorldContext& OtherCtx = GEngine->CreateNewWorldContext(EWorldType::Game);
			OtherCtx.SetCurrentWorld(Other);
			TestNull(TEXT("자동화 중 + AllowInTests 0 = eco.R9Demo 1 이어도 서브시스템 없음"), Other->GetSubsystem<UEcoR9DemoSubsystem>());
			GEngine->DestroyWorldContext(Other);
			Other->DestroyWorld(false);
		}
	}
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

// 맵 제한을 없앤 뒤의 자리 고르기 (엔진 없는 부분 — 월드·물리 없이 격자만): 막힌 칸을 피함, 바닥 메시는 막지 않음, 기존 생태 상자를 먼저 피함,
// 트인 평지가 없으면 가장 덜 막힌 곳.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoStagePick, "AdaptiveEcosystem.R9Demo.StagePick",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoStagePick::RunTest(const FString& Parameters)
{
	using namespace EcoR9Demo;
	using namespace EcoR9DemoTestImpl;
	const double Side = 12000.0;   // 무대 120 m
	// 1. 걸리는 것 표시: 땅 위로 솟은 것만 (바닥 메시·높이 뜬 것은 아님)
	{
		FR9ScanGrid G = FlatGrid(10, 400.0, 0.0, 0.0);
		FR9Box Floor;   // 바닥 메시 (위 = 땅 높이 0)
		Floor.MinX = Floor.MinY = -1000.0;
		Floor.MaxX = Floor.MaxY = 5000.0;
		Floor.MinZ = -100.0;
		Floor.MaxZ = 0.0;
		TestEqual(TEXT("바닥 메시는 막지 않는다 (위가 곧 땅)"), static_cast<int32>(MarkObstacle(G, Floor, 100.0)), 0);
		FR9Box Roof = Floor;   // 땅 위 10 m 에 뜬 판
		Roof.MinZ = 1000.0;
		Roof.MaxZ = 1100.0;
		TestEqual(TEXT("땅 위 3 m 보다 높이 뜬 것은 막지 않는다"), static_cast<int32>(MarkObstacle(G, Roof, 100.0)), 0);
		FR9Box Tree;   // 칸 (2, 2) 가운데의 나무 (폭 1 m, 높이 8 m)
		Tree.MinX = Tree.MinY = 2.5 * 400.0 - 50.0;
		Tree.MaxX = Tree.MaxY = 2.5 * 400.0 + 50.0;
		Tree.MinZ = 0.0;
		Tree.MaxZ = 800.0;
		TestEqual(TEXT("나무는 그 칸을 막는다 (둘레 1 m)"), static_cast<int32>(MarkObstacle(G, Tree, 100.0)), 1);
		TestTrue(TEXT("나무 칸이 막힘"), G.Blocked[G.Index(2, 2)] != 0);
		// 지형 대신 언덕진 바닥 메시: 칸 땅이 0 → 9 m 로 오르고 메시 상자 꼭대기 9 m. 그 칸의 땅이 이 메시면(Skip 참) 막지 않는다
		FR9ScanGrid Hg = FlatGrid(10, 400.0, 0.0, 0.0);
		for (int32 y = 0; y < 10; ++y)
		{
			for (int32 x = 0; x < 10; ++x)
			{
				Hg.Height[Hg.Index(x, y)] = static_cast<float>(x) * 100.0f;
			}
		}
		FR9Box Hill;
		Hill.MinX = Hill.MinY = 0.0;
		Hill.MaxX = Hill.MaxY = 4000.0;
		Hill.MinZ = -100.0;
		Hill.MaxZ = 900.0;
		FR9ScanGrid HgCopy = Hg;
		TestTrue(TEXT("Skip 없이는 언덕 바닥 메시가 제 낮은 칸을 막는다"), MarkObstacle(HgCopy, Hill, 100.0) > 0);
		TestEqual(TEXT("그 칸의 땅인 메시는 그 칸을 막지 않는다"),
				  static_cast<int32>(MarkObstacleIf(Hg, Hill, 100.0, 30.0, 300.0, [](std::size_t) { return true; })), 0);
		// 가파름: 4 m 칸 사이 2 m 단차 = 0.5 > 0.36
		FR9ScanGrid Sg = FlatGrid(4, 400.0, 0.0, 0.0);
		for (int32 y = 0; y < 4; ++y)
		{
			Sg.Height[Sg.Index(2, y)] = 200.0f;
			Sg.Height[Sg.Index(3, y)] = 200.0f;
		}
		TestEqual(TEXT("단차 앞 칸만 가파름"), static_cast<int32>(MarkSteep(Sg, 0.36)), 4);
	}
	// 2. 막힌 칸을 피한다: 400 m 평지 가운데를 가로지르는 나무 줄 (칸 줄 50 = y 202 m). 시작점은 그 줄 곁
	{
		FR9ScanGrid G = FlatGrid(100, 400.0, 0.0, 0.0);
		for (int32 x = 0; x < 100; x += 2)
		{
			FR9Box Tree;
			Tree.MinX = G.CellX(x) - 50.0;
			Tree.MaxX = G.CellX(x) + 50.0;
			Tree.MinY = G.CellY(50) - 50.0;
			Tree.MaxY = G.CellY(50) + 50.0;
			Tree.MinZ = 0.0;
			Tree.MaxZ = 900.0;
			MarkObstacle(G, Tree, 100.0);
		}
		TestEqual(TEXT("나무 줄 50 칸 막힘"), CountInStage(G, 20000.0, 20000.0, 40000.0, [&G](std::size_t k) { return G.Blocked[k] != 0; }), 50);
		FR9PickParams P;
		P.PrefX = 20000.0;
		P.PrefY = 20000.0;
		P.Stride = 3;
		const FR9PickResult R = PickStage(G, P);
		TestTrue(TEXT("나무 줄이 있어도 자리를 찾음"), R.bOk);
		TestEqual(TEXT("고른 무대 안 막힌 칸 0"), CountInStage(G, R.Cx, R.Cy, Side, [&G](std::size_t k) { return G.Blocked[k] != 0; }), 0);
		TestTrue(TEXT("무대가 나무 줄을 넘지 않음 (한쪽에 있음)"), FMath::Abs(R.Cy - G.CellY(50)) >= 0.5 * Side);
	}
	// 3. 기존 생태 상자를 먼저 피한다: 시작점 = 지역 상자 가운데 (팀 PlayerStart 가 지역 안에 있는 맵과 같음)
	{
		FR9ScanGrid G = FlatGrid(100, 400.0, -20000.0, -20000.0);
		FR9Box Region;   // ±62 m (JWJ 1102 지역과 같은 크기)
		Region.MinX = Region.MinY = -6200.0;
		Region.MaxX = Region.MaxY = 6200.0;
		TestTrue(TEXT("피할 칸 표시"), MarkAvoid(G, Region, 1000.0) > 0 && G.HasAvoid());
		FR9PickParams P;
		P.PrefX = 0.0;
		P.PrefY = 0.0;
		P.Stride = 3;
		P.bAvoid = false;
		const FR9PickResult Near = PickStage(G, P);
		TestTrue(TEXT("피하지 않으면 시작점 (지역 안)"), Near.bOk && FMath::Abs(Near.Cx) < 1000.0 && FMath::Abs(Near.Cy) < 1000.0);
		P.bAvoid = true;
		const FR9PickResult Away = PickStage(G, P);
		TestTrue(TEXT("피하면 자리를 찾음"), Away.bOk);
		TestEqual(TEXT("피하면 무대 안 피할 칸 0"), CountInStage(G, Away.Cx, Away.Cy, Side, [&G](std::size_t k) { return G.Avoid[k] != 0; }), 0);
		TestTrue(TEXT("무대 정사각과 지역 상자가 겹치지 않음"), FMath::Max(FMath::Abs(Away.Cx), FMath::Abs(Away.Cy)) >= 0.5 * Side + 6200.0);
	}
	// 4. 트인 평지가 없으면 가장 덜 막힌 곳: 땅 = 가운데 80 m 바닥 하나 (무대 120 m 보다 작은 시험 맵 바닥 — L_CommonGameplayTest 는 100 m)
	{
		FR9ScanGrid G = FlatGrid(100, 400.0, -20000.0, -20000.0);
		for (int32 y = 0; y < 100; ++y)
		{
			for (int32 x = 0; x < 100; ++x)
			{
				if (FMath::Abs(G.CellX(x)) > 4000.0 || FMath::Abs(G.CellY(y)) > 4000.0)
				{
					G.Height[G.Index(x, y)] = std::numeric_limits<float>::quiet_NaN();
				}
			}
		}
		FR9PickParams P;
		P.Stride = 1;
		TestFalse(TEXT("120 m 트인 평지는 없음"), PickStage(G, P).bOk);
		const FR9PickResult R = PickLeastBlocked(G, P);
		TestTrue(TEXT("가장 덜 막힌 곳을 찾음"), R.bOk && R.bHeightKnown);
		TestTrue(TEXT("바닥을 모두 덮는 자리 (바닥 칸 400 = 20×20 이 무대 안)"), R.StageCells - R.BlockedCells == 400);
		TestTrue(TEXT("바닥 가운데 둘레"), FMath::Abs(R.Cx) <= 2000.0 && FMath::Abs(R.Cy) <= 2000.0);
		// 땅이 하나도 없고 피할 상자만 있으면: 막힌 칸은 모두 같으니 피할 칸 0 인 곳
		FR9ScanGrid E = FlatGrid(100, 400.0, -20000.0, -20000.0);
		E.Height.assign(E.Height.size(), std::numeric_limits<float>::quiet_NaN());
		FR9Box Region;
		Region.MinX = Region.MinY = -5000.0;
		Region.MaxX = Region.MaxY = 5000.0;
		MarkAvoid(E, Region, 1000.0);
		const FR9PickResult Re = PickLeastBlocked(E, P);
		TestTrue(TEXT("땅이 없어도 자리는 줌 (높이 모름)"), Re.bOk && !Re.bHeightKnown);
		TestEqual(TEXT("땅이 없으면 피할 칸 0 인 곳"), static_cast<int32>(Re.AvoidCells), 0);
	}
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
// 두뇌·장면으로 무대를 세워 동물 몸을 만들고 스텝이 넘어가는지 본다. 시험 월드에는 땅이 없어 eco.R9Demo.At 0,0 으로 자리 훑기만 건너뛴다
// (자리 훑기를 하는 길은 AnyMap 시험이 본다).
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
	EcoR9DemoTestImpl::FCVarRestore Restore;
	Restore.Set(TEXT("eco.R9Demo.AllowInTests"), TEXT("1"));   // 자동화 시험 중에는 이 값이 있어야 서브시스템이 생긴다
	Restore.Set(TEXT("eco.R9Demo.OnlyMap"), TEXT(""));   // 시작 맵 거르기 끔 (이 PC UserEngine.ini 가 섬 맵만 켜도 시험 월드에서 돈다)
	Restore.Set(TEXT("eco.R9Demo.Brains"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Scene"), TEXT(""));
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

// 맵 제한 없음 + 기존 생태가 있어도 켜짐 (2026-11-12 22:30 사용자 '맵마다 또 설정을 해줘야돼???'):
// 섬이 아닌 시험 월드(/Temp/…)에 팀 생태 지역(AEcologyRegion, 헤더 없이 클래스 이름으로 띄움 — BeginPlay 전이라 팀 시스템에 등록되지 않음)을
// 원점에 두고, 콘솔 eco.R9Demo 1 만 켠다 (eco.R9Demo.At 비움 = 자동 고르기). 거부하지 않고 무대가 서야 하며, 무대 정사각이 지역 상자와 겹치지 않아야 한다.
// 시험 월드에는 땅이 없어 '가장 덜 막힌 곳' 길로 가지만, 그때도 피할 칸이 없는 곳을 고른다.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoAnyMap, "AdaptiveEcosystem.R9Demo.AnyMap", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoAnyMap::RunTest(const FString& Parameters)
{
	using namespace EcoR9DemoTestImpl;
	FString Why;
	if (!CanRunConsoleWorld(Why))
	{
		AddWarning(Why + TEXT(" — 건너뜀"));
		return true;
	}
	UClass* RegionClass = FindObject<UClass>(nullptr, TEXT("/Script/AdaptiveEcosystem.EcologyRegion"));
	if (!TestNotNull(TEXT("팀 생태 지역 클래스 (AEcologyRegion)"), RegionClass))
	{
		return false;
	}
	FCVarRestore Restore;
	Restore.Set(TEXT("eco.R9Demo.AllowInTests"), TEXT("1"));
	Restore.Set(TEXT("eco.R9Demo.OnlyMap"), TEXT(""));   // 시작 맵 거르기 끔 (이 PC UserEngine.ini 가 섬 맵만 켜도 시험 월드에서 돈다)
	Restore.Set(TEXT("eco.R9Demo.Brains"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Scene"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.At"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Area"), TEXT("120"));   // 예전 한 무대 자리 고르기 (맵 전체 땅은 WholeMap 시험)
	Restore.Set(TEXT("eco.R9Demo"), TEXT("1"));
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
	if (!TestNotNull(TEXT("시험 월드"), World))
	{
		return false;
	}
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	const FString Pkg = World->GetPackage()->GetName();
	TestFalse(TEXT("시험 월드는 팀 섬 원본 맵이 아니다"), Pkg.Equals(TEXT("/Game/Map/LV_SHC_IslandEcosystem1_WP"), ESearchCase::IgnoreCase));
	FActorSpawnParameters P;
	P.ObjectFlags |= RF_Transient;
	AActor* Region = World->SpawnActor<AActor>(RegionClass, FTransform::Identity, P);   // 기본 상자 ±50 m
	TestNotNull(TEXT("팀 생태 지역을 원점에 둠"), Region);
	UEcoR9DemoSubsystem* Sub = World->GetSubsystem<UEcoR9DemoSubsystem>();
	TestNotNull(TEXT("콘솔 값만으로 서브시스템이 생김"), Sub);
	if (Sub && Region)
	{
		Sub->OnWorldBeginPlay(*World);
		TestTrue(TEXT("섬이 아닌 맵 + 생태 지역이 있어도 거부하지 않음"), Sub->IsActive());
		TestTrue(TEXT("팀 생태가 있다고 앎 (건드리지 않고 알리기만)"), Sub->HasTeamEco());
		TickDemo(*World, *Sub, 180);   // 월드 6 초 (고리 셋 × 0.5 초 + 무대 0.5 초 + 실행)
		TestTrue(TEXT("자동 고르기로 무대가 서서 도는 중"), Sub->IsRunning());
		TestTrue(TEXT("피할 생태 상자를 셈"), Sub->NumAvoidZones() >= 1);
		TestTrue(TEXT("동물 몸이 생김"), Sub->NumBodies() >= 30);
		TestTrue(TEXT("스텝이 넘어감"), Sub->NumStepsShown() >= 10);
		FVector O = FVector::ZeroVector, E = FVector::ZeroVector;
		Region->GetActorBounds(false, O, E);
		const FVector C = Sub->StageCenterCm();
		const double Half = 6000.0;   // 무대 120 m
		const bool bApartX = FMath::Abs(C.X - O.X) >= Half + E.X;
		const bool bApartY = FMath::Abs(C.Y - O.Y) >= Half + E.Y;
		TestTrue(FString::Printf(TEXT("무대 정사각이 생태 지역 상자와 겹치지 않음 (무대 가운데 %.0f, %.0f m · 지역 ±%.0f m)"), C.X / 100.0, C.Y / 100.0, E.X / 100.0),
				 bApartX || bApartY);
		AddInfo(FString::Printf(TEXT("시작점 %s · 무대 (%.1f, %.1f) m · 몸 %d · 스텝 %lld"), *Sub->SearchOriginCm().ToCompactString(), C.X / 100.0, C.Y / 100.0,
								Sub->NumBodies(), static_cast<long long>(Sub->NumStepsShown())));
	}
	World->DestroyWorld(false);
	GEngine->DestroyWorldContext(World);
	return true;
}

// 콘솔 eco.R9Demo.At x,y (m) 가 자동 고르기를 덮어쓴다 — PIE 는 명령줄이 없어 콘솔 값이어야 한다.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoAtOverride, "AdaptiveEcosystem.R9Demo.AtOverride",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoAtOverride::RunTest(const FString& Parameters)
{
	using namespace EcoR9DemoTestImpl;
	FString Why;
	if (!CanRunConsoleWorld(Why))
	{
		AddWarning(Why + TEXT(" — 건너뜀"));
		return true;
	}
	FCVarRestore Restore;
	Restore.Set(TEXT("eco.R9Demo.AllowInTests"), TEXT("1"));
	Restore.Set(TEXT("eco.R9Demo.OnlyMap"), TEXT(""));   // 시작 맵 거르기 끔 (이 PC UserEngine.ini 가 섬 맵만 켜도 시험 월드에서 돈다)
	Restore.Set(TEXT("eco.R9Demo.Brains"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Scene"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.At"), TEXT("37.5, -12"));
	Restore.Set(TEXT("eco.R9Demo"), TEXT("1"));
	const FEcoR9DemoSettings S = FEcoR9DemoSettings::Resolve(FCommandLine::Get());
	TestTrue(TEXT("콘솔 eco.R9Demo.At 을 읽음"), S.bHasAt && FMath::IsNearlyEqual(S.AtM.X, 37.5) && FMath::IsNearlyEqual(S.AtM.Y, -12.0));
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
	if (!TestNotNull(TEXT("시험 월드"), World))
	{
		return false;
	}
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	UEcoR9DemoSubsystem* Sub = World->GetSubsystem<UEcoR9DemoSubsystem>();
	TestNotNull(TEXT("서브시스템"), Sub);
	if (Sub)
	{
		Sub->OnWorldBeginPlay(*World);
		TestTrue(TEXT("시작함"), Sub->IsActive());
		TickDemo(*World, *Sub, 60);
		TestTrue(TEXT("무대가 서서 도는 중"), Sub->IsRunning());
		const FVector C = Sub->StageCenterCm();
		TestTrue(FString::Printf(TEXT("무대 가운데 = 콘솔 값 (37.5, -12) m (지금 %.2f, %.2f)"), C.X / 100.0, C.Y / 100.0),
				 FMath::IsNearlyEqual(C.X, 3750.0, 1e-6) && FMath::IsNearlyEqual(C.Y, -1200.0, 1e-6));
	}
	World->DestroyWorld(false);
	GEngine->DestroyWorldContext(World);
	return true;
}

// -----------------------------------------------------------------------------
// 2026-11-13 맵 전체 땅
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoWholeMath, "AdaptiveEcosystem.R9Demo.WholeMath",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoWholeMath::RunTest(const FString& Parameters)
{
	using namespace EcoR9Demo;
	// 1. 훑기 → 코어 땅 지도: 칸 종류와 y 뒤집기. 코어 칸 (ix, iy) 가운데를 화면 좌표(FR9StageMap)로 옮기면 바로 그 훑기 칸이어야 한다
	{
		FR9ScanGrid S;
		S.Nx = S.Ny = 4;
		S.CellCm = 400.0;
		S.Height.assign(16, 0.0f);
		S.Blocked.assign(16, 0);
		std::vector<std::uint8_t> K(16, kLandOpen);
		S.Height[S.Index(0, 0)] = std::numeric_limits<float>::quiet_NaN();
		S.Blocked[S.Index(3, 0)] = 1;
		K[S.Index(3, 0)] = kLandSteep;
		S.Blocked[S.Index(1, 3)] = 1;
		K[S.Index(1, 3)] = kLandObstacle;
		std::vector<std::uint8_t> Out;
		FR9LandCounts C;
		TestTrue(TEXT("훑기 → 땅 지도"), ScanToLand(S, K, Out, &C));
		TestEqual(TEXT("땅 없음 = Void (코어 iy 3)"), static_cast<int32>(Out[3 * 4 + 0]), static_cast<int32>(kLandVoid));
		TestEqual(TEXT("가파름 그대로"), static_cast<int32>(Out[3 * 4 + 3]), static_cast<int32>(kLandSteep));
		TestEqual(TEXT("나무·바위 그대로 (훑기 y 3 → 코어 iy 0)"), static_cast<int32>(Out[0 * 4 + 1]), static_cast<int32>(kLandObstacle));
		TestTrue(TEXT("셈"), C.Open == 13 && C.Void == 1 && C.Steep == 1 && C.Obstacle == 1);
		FR9StageMap M;
		M.W = M.H = 8.0;
		M.Cx = 800.0;
		M.Cy = 800.0;
		int32 Bad = 0;
		for (int32 iy = 0; iy < 4; ++iy)
		{
			for (int32 ix = 0; ix < 4; ++ix)
			{
				double X = 0.0, Y = 0.0;
				M.ToWorld((ix + 0.5) * 2.0, (iy + 0.5) * 2.0, X, Y);
				const int32 Sx = FMath::FloorToInt32((X - S.X0) / S.CellCm);
				const int32 Sy = FMath::FloorToInt32((Y - S.Y0) / S.CellCm);
				Bad += ScanToCoreIndex(4, Sx, Sy) == static_cast<std::size_t>(iy * 4 + ix) ? 0 : 1;
			}
		}
		TestEqual(TEXT("코어 칸 가운데 → 화면 → 같은 훑기 칸 (16 칸 모두)"), Bad, 0);
	}
	// 2. 가장 큰 이어진 땅 (4-이웃 — 축마다 미끄러지는 이동은 대각 틈을 못 지난다)
	{
		const std::vector<std::uint8_t> K = {0, 1, 0, 1, 0, 1, 0, 0, 0};
		std::int64_t Comps = 0;
		TestEqual(TEXT("가장 큰 덩어리"), static_cast<int32>(LargestOpenComponent(K, 3, &Comps)), 4);
		TestEqual(TEXT("덩어리 수"), static_cast<int32>(Comps), 3);
	}
	// 3. 세계 정사각: 섬 땅 경계 2.7 × 2.1 km + 둘레 50 m → 한 변 2.8 km (G 700), 4 km 상한, 120 m 하한
	{
		double Cx = 0.0, Cy = 0.0;
		TestEqual(TEXT("섬 G"), SquareFromBounds(-95300.0, -90800.0, 174700.0, 119200.0, 5000.0, 400.0, 12000.0, 400000.0, Cx, Cy), 700);
		TestEqual(TEXT("4 km 상한"), SquareFromBounds(0.0, 0.0, 900000.0, 100.0, 0.0, 400.0, 12000.0, 400000.0, Cx, Cy), 1000);
		TestEqual(TEXT("120 m 하한"), SquareFromBounds(0.0, 0.0, 100.0, 100.0, 0.0, 400.0, 12000.0, 400000.0, Cx, Cy), 30);
	}
	// 4. 은신처 곁 후보: 나무 다섯 그루 묶음 · 외톨이 나무 (빠짐) · 큰 바위 (무게 6) → 무게 큰 차례
	{
		std::vector<FR9CoverPoint> P;
		for (int32 i = 0; i < 5; ++i)
		{
			P.push_back({10.0 + 0.3 * i, 10.0, 1.0});
		}
		P.push_back({50.0, 50.0, 1.0});
		P.push_back({90.0, 20.0, 6.0});
		std::vector<double> A;
		ClusterAnchors(P, 8.0, 2.0, 10, A);
		TestTrue(TEXT("후보 둘 (바위 → 나무 덩어리)"), A.size() == 4 && FMath::IsNearlyEqual(A[0], 90.0) && FMath::IsNearlyEqual(A[2], 10.6, 1e-9));
	}
	// 5. 풀 창: 작은 세계 = 격자 전체, 큰 세계 = 초점 둘레 (8 칸에 맞춤 — 조금 움직여도 그대로), 가장자리에서 잘림
	{
		const FR9FoodWindow Small = PlaceFoodWindow(30, 2.0, 30.0, 30.0, 64, 8);
		TestTrue(TEXT("작은 세계 = 격자 전체"), Small.X0 == 0 && Small.Y0 == 0 && Small.Nx == 30 && Small.Ny == 30);
		const FR9FoodWindow W = PlaceFoodWindow(700, 2.0, 700.0, 300.0, 64, 8);
		TestTrue(TEXT("초점 칸이 창 안"), W.Nx == 64 && W.X0 % 8 == 0 && W.X0 <= 350 && W.X0 + 64 > 350 && W.Y0 <= 150 && W.Y0 + 64 > 150);
		TestTrue(TEXT("조금 움직이면 그대로"), PlaceFoodWindow(700, 2.0, 702.0, 301.0, 64, 8) == W);
		const FR9FoodWindow E = PlaceFoodWindow(700, 2.0, 0.0, 1399.0, 64, 8);
		TestTrue(TEXT("가장자리"), E.X0 == 0 && E.Y0 == 700 - 64);
	}
	// 6. 몸 배정: 몸이 있는 개체는 여유 거리 안이면 지키고, 남은 자리는 가까운 차례
	{
		const std::vector<double> D = {100.0, 5000.0, 30000.0, 26000.0, -1.0, 200.0};
		const std::vector<std::uint8_t> Has = {0, 0, 0, 1, 0, 0};
		std::vector<std::uint8_t> Want;
		TestEqual(TEXT("상한 3"), PickBodies(D, Has, 25000.0, 1.2, 3, Want), 3);
		TestTrue(TEXT("몸 있는 개체 지킴 + 가장 가까운 둘"), Want[3] == 1 && Want[0] == 1 && Want[5] == 1 && Want[1] == 0 && Want[4] == 0);
	}
	// 7. 멧돼지 몸 이름·애니 이름 (AnimalVarietyPack 이름 꼴)
	{
		TestEqual(TEXT("SK_Pig"), BoarNameScore(ToLowerAscii("SK_Pig")), 20);
		TestEqual(TEXT("SK_Boar"), BoarNameScore("sk_boar"), 30);
		TestEqual(TEXT("villsvin"), BoarNameScore("sk_villsvin"), 30);
		TestEqual(TEXT("hedgehog 은 아님"), BoarNameScore("sk_hedgehog"), 0);
		TestEqual(TEXT("늑대는 아님"), BoarNameScore("sk_wolf"), 0);
		TestEqual(TEXT("비둘기(pigeon)·빌보드(billboard)는 아님"), BoarNameScore("sk_pigeon") + BoarNameScore("m_ms_billboard"), 0);
		int Sc = 0;
		TestTrue(TEXT("IdleBreathe = 서기 (breathe 의 eat 를 먹기로 읽지 않음)"), AnimRoleOf("anim_pig_idlebreathe", Sc) == ER9AnimRole::Idle);
		TestTrue(TEXT("Walk"), AnimRoleOf("anim_pig_walk", Sc) == ER9AnimRole::Walk);
		TestTrue(TEXT("Trot = 뛰기"), AnimRoleOf("anim_pig_trot", Sc) == ER9AnimRole::Run);
		TestTrue(TEXT("Eat"), AnimRoleOf("anim_pig_eat", Sc) == ER9AnimRole::Eat);
		TestTrue(TEXT("IdleGraze = 먹기"), AnimRoleOf("anim_deerdoe_idlegraze", Sc) == ER9AnimRole::Eat);
		TestTrue(TEXT("Death"), AnimRoleOf("anim_pig_death", Sc) == ER9AnimRole::Death);
		int ScRm = 0, ScWalk = 0;
		AnimRoleOf("anim_pig_walk_rm", ScRm);
		AnimRoleOf("anim_pig_walk", ScWalk);
		TestTrue(TEXT("뿌리 움직임 변형은 낮게"), ScRm < ScWalk);
	}
	return true;
}

namespace EcoR9DemoTestImpl
{
	/** 시험 월드에 넓은 바닥(정육면체 메시)·기둥을 둔다 (지형 없는 맵 — 바닥 메시 선 검사로 땅을 읽는 길). */
	AStaticMeshActor* SpawnBox(UWorld& World, const FVector& Center, const FVector& SizeCm, const TCHAR* MeshPath)
	{
		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, MeshPath);
		if (!Mesh)
		{
			return nullptr;
		}
		FActorSpawnParameters P;
		P.ObjectFlags |= RF_Transient;
		AStaticMeshActor* A = World.SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), FTransform(Center), P);
		if (!A)
		{
			return nullptr;
		}
		UStaticMeshComponent* C = A->GetStaticMeshComponent();
		C->SetMobility(EComponentMobility::Movable);
		C->SetStaticMesh(Mesh);
		C->SetCollisionProfileName(TEXT("BlockAll"));
		A->SetActorScale3D(SizeCm / 100.0);   // 엔진 기본 도형은 100 cm
		return A;
	}
}

// 맵 전체 땅: 지형 없는 시험 월드 — 바닥 400 m (위 z = 0) · 그 위 기둥 (가로 2 m · 높이 5 m) · 무리 자리 TargetPoint (꼬리표 EcoR9Herd) · 팀 동물 몸 하나.
// eco.R9Demo 1 + Area 0 (기본) → 땅 지도가 생기고 (기둥 자리 = 막힌 칸, 바닥 = 열림, 바닥 밖 = Void), 사람이 놓은 무리 자리가 넘어가고, 팀 동물 몸은 숨는다.
// 끄면 (StopDemo) 데모 액터 0 · 팀 동물 몸은 다시 보인다. 코어에 큰 세계 장면 생성기가 있으면 큰 세계로 돌고 (무리 자리 ≥ 1, 몸·표식), 없으면 예전 한 무대로 돈다.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoWholeMap, "AdaptiveEcosystem.R9Demo.WholeMap", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoWholeMap::RunTest(const FString& Parameters)
{
	using namespace EcoR9DemoTestImpl;
	using namespace EcoR9Demo;
	FString Why;
	if (!CanRunConsoleWorld(Why))
	{
		AddWarning(Why + TEXT(" — 건너뜀"));
		return true;
	}
	FCVarRestore Restore;
	Restore.Set(TEXT("eco.R9Demo.AllowInTests"), TEXT("1"));
	Restore.Set(TEXT("eco.R9Demo.OnlyMap"), TEXT(""));   // 시작 맵 거르기 끔 (이 PC UserEngine.ini 가 섬 맵만 켜도 시험 월드에서 돈다)
	Restore.Set(TEXT("eco.R9Demo.Brains"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Scene"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.At"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Area"), TEXT("0"));
	Restore.Set(TEXT("eco.R9Demo.Herds"), TEXT("2"));
	Restore.Set(TEXT("eco.R9Demo.HideOthers"), TEXT("1"));
	Restore.Set(TEXT("eco.R9Demo"), TEXT("1"));
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
	if (!TestNotNull(TEXT("시험 월드"), World))
	{
		return false;
	}
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	const FVector PillarAt(10000.0, 5000.0, 250.0);
	TestNotNull(TEXT("바닥 400 m"), SpawnBox(*World, FVector(0.0, 0.0, -50.0), FVector(40000.0, 40000.0, 100.0), TEXT("/Engine/BasicShapes/Cube.Cube")));
	TestNotNull(TEXT("기둥"), SpawnBox(*World, PillarAt, FVector(200.0, 200.0, 500.0), TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
	FActorSpawnParameters Tp;
	Tp.ObjectFlags |= RF_Transient;
	ATargetPoint* Site = World->SpawnActor<ATargetPoint>(ATargetPoint::StaticClass(), FTransform(FVector(-10000.0, -10000.0, 0.0)), Tp);
	if (Site)
	{
		Site->Tags.Add(FName(TEXT("EcoR9Herd")));
	}
	AEcoCreatureRepresentationActor* Team = World->SpawnActor<AEcoCreatureRepresentationActor>(AEcoHerbivoreRepresentation::StaticClass(), FTransform(FVector(0.0, 0.0, 0.0)), Tp);
	const bool bTeamBound = Team && Team->BindIdentity(5, Team->VisualSpeciesId);
	TestTrue(TEXT("팀 동물 몸 (묶임·보임)"), bTeamBound && !Team->IsHidden());
	UEcoR9DemoSubsystem* Sub = World->GetSubsystem<UEcoR9DemoSubsystem>();
	TestNotNull(TEXT("서브시스템"), Sub);
	if (Sub)
	{
		Sub->OnWorldBeginPlay(*World);
		TestTrue(TEXT("시작함"), Sub->IsActive());
		TickDemo(*World, *Sub, 240);   // 월드 8 초
		TestTrue(TEXT("무대가 서서 도는 중"), Sub->IsRunning());
		TestTrue(TEXT("팀 동물 몸을 숨김 (보이는 것만)"), bTeamBound && Team->IsHidden() && Sub->NumHiddenOthers() >= 1);
		const FR9WholeSpec* Spec = Sub->WholeSpecForTest();
		if (FR9LiveSource::WholeAvailable())
		{
			TestNotNull(TEXT("땅 지도가 생김"), Spec);
		}
		if (Spec)
		{
			// 땅 지도: 바닥 400 m + 둘레 50 m → 한 변 500 m (G 125), 기둥 자리 = 막힌 칸, 바닥 = 열림, 바닥 밖 = Void
			TestEqual(TEXT("땅 지도 한 변 (바닥 400 m + 둘레 50 m × 2 = 500 m)"), Spec->G, 125);
			const FVector C = Sub->WholeCenterCm();
			FR9StageMap M;
			M.Cx = C.X;
			M.Cy = C.Y;
			M.W = M.H = Spec->G * Spec->CellUnits;
			auto KindAt = [&](double X, double Y) -> int32
			{
				double Ux = 0.0, Uy = 0.0;
				M.ToUnits(X, Y, Ux, Uy);
				const int32 Ix = FMath::FloorToInt32(Ux / Spec->CellUnits);
				const int32 Iy = FMath::FloorToInt32(Uy / Spec->CellUnits);
				return Ix >= 0 && Iy >= 0 && Ix < Spec->G && Iy < Spec->G ? static_cast<int32>(Spec->Kind[static_cast<std::size_t>(Iy * Spec->G + Ix)]) : -1;
			};
			TestEqual(TEXT("기둥 자리 = 막힌 칸 (나무·바위·건물)"), KindAt(PillarAt.X, PillarAt.Y), static_cast<int32>(kLandObstacle));
			TestEqual(TEXT("바닥 가운데 = 열림"), KindAt(-5000.0, 7000.0), static_cast<int32>(kLandOpen));
			TestEqual(TEXT("바닥 밖 (둘레 여유) = Void"), KindAt(22400.0, 0.0), static_cast<int32>(kLandVoid));
			std::int64_t Open = 0;
			for (const std::uint8_t K : Spec->Kind)
			{
				Open += K == kLandOpen ? 1 : 0;
			}
			TestTrue(FString::Printf(TEXT("열린 칸 ≈ 바닥 100² − 기둥 (지금 %lld)"), static_cast<long long>(Open)), Open > 9900 && Open < 10000);
			TestTrue(TEXT("사람이 놓은 무리 자리 (TargetPoint EcoR9Herd) 가 넘어감"), Spec->Sites.size() == 2);
			if (Spec->Sites.size() == 2)
			{
				double X = 0.0, Y = 0.0;
				M.ToWorld(Spec->Sites[0], Spec->Sites[1], X, Y);
				TestTrue(TEXT("무리 자리 = TargetPoint 자리"), FMath::Abs(X + 10000.0) < 1.0 && FMath::Abs(Y + 10000.0) < 1.0);
			}
		}
		if (Sub->IsWhole())
		{
			TestTrue(TEXT("큰 세계: 무리 자리 ≥ 1"), Sub->NumHerdSites() >= 1);
			TestTrue(TEXT("큰 세계: 동물이 있다 (몸 + 먼 표식)"), Sub->NumBodyActors() + Sub->NumFarMarkers() > 0);
			TestTrue(TEXT("큰 세계: 스텝이 넘어감"), Sub->NumStepsShown() >= 10);
		}
		else
		{
			AddWarning(TEXT("코어에 큰 세계 장면 생성기가 없거나 시작을 못 해 예전 한 무대로 돌았다 (기록 줄 [EcoR9Demo] 참고)"));
		}
		AddInfo(FString::Printf(TEXT("큰 세계 %s · 무리 자리 %d · 몸 %d · 먼 표식 %d · 스텝 %lld · 멧돼지 몸 %s"), Sub->IsWhole() ? TEXT("예") : TEXT("아니오"), Sub->NumHerdSites(),
								Sub->NumBodyActors(), Sub->NumFarMarkers(), static_cast<long long>(Sub->NumStepsShown()), *Sub->BoarBodyLine()));
		TestFalse(TEXT("멧돼지 몸 설명이 있다 (찾은 에셋 또는 자리표시)"), Sub->BoarBodyLine().IsEmpty());
		// 끄기: 데모 액터 0, 팀 동물 몸은 다시 보임
		Sub->StopDemo(TEXT("시험"));
		TestFalse(TEXT("끔"), Sub->IsActive());
		int32 Ours = 0;
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			Ours += It->GetName().StartsWith(TEXT("EcoR9Demo_")) ? 1 : 0;
		}
		TestEqual(TEXT("끄면 데모 액터 0"), Ours, 0);
		TestTrue(TEXT("끄면 팀 동물 몸이 다시 보임"), bTeamBound && !Team->IsHidden());
	}
	World->DestroyWorld(false);
	GEngine->DestroyWorldContext(World);
	return true;
}

// Play 중 켜기/끄기: eco.R9Demo 0 인 채 Play 를 시작한 월드 (서브시스템은 늘 있다 — 아무것도 만들지 않음) 에서 콘솔 값을 바꾸면 바뀜 콜백이 그 자리에서
// 시작·정지한다. 이미 켜져 있으면 다시 만들지 않는다. 빠르게 돌게 예전 한 무대 (eco.R9Demo.At 0,0 — 시험 월드에는 땅이 없다).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoPlayToggle, "AdaptiveEcosystem.R9Demo.PlayToggle", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoPlayToggle::RunTest(const FString& Parameters)
{
	using namespace EcoR9DemoTestImpl;
	FString Why;
	if (!CanRunConsoleWorld(Why))
	{
		AddWarning(Why + TEXT(" — 건너뜀"));
		return true;
	}
	IConsoleVariable* Demo = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.R9Demo"));
	if (!TestNotNull(TEXT("콘솔 값 eco.R9Demo"), Demo))
	{
		return false;
	}
	FCVarRestore Restore;
	Restore.Set(TEXT("eco.R9Demo.AllowInTests"), TEXT("1"));
	Restore.Set(TEXT("eco.R9Demo.OnlyMap"), TEXT(""));   // 시작 맵 거르기 끔 (이 PC UserEngine.ini 가 섬 맵만 켜도 시험 월드에서 돈다)
	Restore.Set(TEXT("eco.R9Demo.Brains"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Scene"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.At"), TEXT("0,0"));
	Restore.Set(TEXT("eco.R9Demo"), TEXT("0"));
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
	if (!TestNotNull(TEXT("시험 월드"), World))
	{
		return false;
	}
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	UEcoR9DemoSubsystem* Sub = World->GetSubsystem<UEcoR9DemoSubsystem>();
	TestNotNull(TEXT("꺼진 채로도 서브시스템은 있다 (Play 중 켜려고)"), Sub);
	auto CountOurs = [World]()
	{
		int32 N = 0;
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			N += It->GetName().StartsWith(TEXT("EcoR9Demo_")) ? 1 : 0;
		}
		return N;
	};
	if (Sub)
	{
		Sub->OnWorldBeginPlay(*World);
		TestFalse(TEXT("eco.R9Demo 0 으로 Play 시작 = 꺼짐"), Sub->IsActive());
		TestEqual(TEXT("꺼짐 = 데모 액터 0"), CountOurs(), 0);
		Demo->Set(TEXT("1"), ECVF_SetByConsole);   // 바뀜 콜백 → StartDemo
		TestTrue(TEXT("Play 중 eco.R9Demo 1 → 그 자리에서 시작"), Sub->IsActive());
		TestEqual(TEXT("시작 1 번"), Sub->NumStarts(), 1);
		Sub->StartDemo(TEXT("시험 — 두 번째 시작 요청"));
		Demo->Set(TEXT("1"), ECVF_SetByConsole);
		TestEqual(TEXT("이미 켜져 있으면 다시 만들지 않음"), Sub->NumStarts(), 1);
		TickDemo(*World, *Sub, 90);
		TestTrue(TEXT("무대가 서서 도는 중"), Sub->IsRunning());
		const int32 Bodies = Sub->NumBodies();
		TestTrue(FString::Printf(TEXT("동물 몸 (지금 %d)"), Bodies), Bodies >= 30);
		Demo->Set(TEXT("0"), ECVF_SetByConsole);   // 바뀜 콜백 → StopDemo
		TestFalse(TEXT("Play 중 eco.R9Demo 0 → 그 자리에서 정지"), Sub->IsActive());
		TestEqual(TEXT("정지 = 데모 액터 0"), CountOurs(), 0);
		TestEqual(TEXT("정지 = 몸 0"), Sub->NumBodies(), 0);
		Demo->Set(TEXT("1"), ECVF_SetByConsole);
		TestEqual(TEXT("다시 켜면 시작 2 번째"), Sub->NumStarts(), 2);
		TickDemo(*World, *Sub, 90);
		TestTrue(TEXT("다시 도는 중"), Sub->IsRunning());
		TestTrue(FString::Printf(TEXT("몸이 겹쳐 생기지 않음 (지금 %d, 처음 %d)"), Sub->NumBodies(), Bodies), Sub->NumBodies() <= Bodies + 4);
	}
	World->DestroyWorld(false);
	GEngine->DestroyWorldContext(World);
	return true;
}

// -----------------------------------------------------------------------------
// 2026-11-13 03:30 옛 관찰 카메라 꼴 (EcoR9DemoCam.h) · 시작 맵에서만 (eco.R9Demo.OnlyMap)
// -----------------------------------------------------------------------------

namespace EcoR9DemoTestImpl
{
	bool KeyIs(const FKey& Key, EcoR9DemoCam::EAction Want)
	{
		EcoR9DemoCam::EAction A = EcoR9DemoCam::EAction::Count;
		return EcoR9DemoCam::ActionOf(Key, A) && A == Want;
	}

	/** 옛 관찰 카메라 동작 → R9 동작 (같은 키는 같은 뜻이어야 한다). */
	EcoR9DemoCam::EAction FromOld(EcoV3Observe::EAction Old)
	{
		using EcoR9DemoCam::EAction;
		switch (Old)
		{
		case EcoV3Observe::EAction::Wolf: return EAction::Wolf;
		case EcoV3Observe::EAction::Deer: return EAction::Deer;
		case EcoV3Observe::EAction::Top: return EAction::Top;
		case EcoV3Observe::EAction::Quarter: return EAction::Quarter;
		case EcoV3Observe::EAction::Auto: return EAction::Auto;
		case EcoV3Observe::EAction::Player: return EAction::Free;      // 옛 0: 관찰 중 = 자유 카메라 (R9 는 늘 자유 카메라)
		case EcoV3Observe::EAction::Prev: return EAction::Prev;
		case EcoV3Observe::EAction::Next: return EAction::Next;
		case EcoV3Observe::EAction::ZoomOut: return EAction::ZoomOut;
		case EcoV3Observe::EAction::ZoomIn: return EAction::ZoomIn;
		case EcoV3Observe::EAction::Region: return EAction::NextSite;  // 옛 G 지역 바꾸기 = R9 무리 자리 바꾸기 (ISLAND_STAGE.md 11절 설계)
		case EcoV3Observe::EAction::Help: return EAction::Help;
		default: return EAction::Count;
		}
	}

	int32 CountDemoActors(UWorld& World)
	{
		int32 N = 0;
		for (TActorIterator<AActor> It(&World); It; ++It)
		{
			N += It->GetName().StartsWith(TEXT("EcoR9Demo_")) ? 1 : 0;
		}
		return N;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoCamKeys, "AdaptiveEcosystem.R9Demo.CamKeys", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoCamKeys::RunTest(const FString& Parameters)
{
	using namespace EcoR9DemoTestImpl;
	using EcoR9DemoCam::EAction;
	// 1. 옛 키 그대로 (OBSERVER_CAMERA.md 2절 · ISLAND_STAGE.md I.2 '보기')
	TestTrue(TEXT("1 = 늑대 시점"), KeyIs(EKeys::One, EAction::Wolf) && KeyIs(EKeys::NumPadOne, EAction::Wolf));
	TestTrue(TEXT("2 = 사슴 시점"), KeyIs(EKeys::Two, EAction::Deer) && KeyIs(EKeys::NumPadTwo, EAction::Deer));
	TestTrue(TEXT("3 = 탑뷰"), KeyIs(EKeys::Three, EAction::Top) && KeyIs(EKeys::NumPadThree, EAction::Top));
	TestTrue(TEXT("4 = 쿼터뷰"), KeyIs(EKeys::Four, EAction::Quarter) && KeyIs(EKeys::NumPadFour, EAction::Quarter));
	TestTrue(TEXT("5 = 자동 추적"), KeyIs(EKeys::Five, EAction::Auto) && KeyIs(EKeys::NumPadFive, EAction::Auto));
	TestTrue(TEXT("0 = 자유 카메라"), KeyIs(EKeys::Zero, EAction::Free) && KeyIs(EKeys::NumPadZero, EAction::Free));
	TestTrue(TEXT(", . = 이전·다음 대상"), KeyIs(EKeys::Comma, EAction::Prev) && KeyIs(EKeys::Period, EAction::Next));
	TestTrue(TEXT("- · 숫자패드 - · 휠 아래 = 멀리 (자유 카메라: 느리게)"),
			 KeyIs(EKeys::Hyphen, EAction::ZoomOut) && KeyIs(EKeys::Subtract, EAction::ZoomOut) && KeyIs(EKeys::MouseScrollDown, EAction::ZoomOut));
	TestTrue(TEXT("= · 숫자패드 + · 휠 위 = 가까이 (자유 카메라: 빠르게)"),
			 KeyIs(EKeys::Equals, EAction::ZoomIn) && KeyIs(EKeys::Add, EAction::ZoomIn) && KeyIs(EKeys::MouseScrollUp, EAction::ZoomIn));
	TestTrue(TEXT("H = 단축키 목록"), KeyIs(EKeys::H, EAction::Help));
	// 2. R9 만 (옛 키·옛 문서에 없는 숫자) — 6 멧돼지 · 7 다음 무리 자리 (G 는 옛 '지역 바꾸기' 와 같은 자리 차례)
	TestTrue(TEXT("6 = 멧돼지 시점"), KeyIs(EKeys::Six, EAction::Boar) && KeyIs(EKeys::NumPadSix, EAction::Boar));
	TestTrue(TEXT("7 · G = 다음 무리 자리"), KeyIs(EKeys::Seven, EAction::NextSite) && KeyIs(EKeys::NumPadSeven, EAction::NextSite) && KeyIs(EKeys::G, EAction::NextSite));
	// 3. 모드 값 = 키 숫자 (콘솔 eco.R9Demo.Cam 도 같은 수)
	const FKey Digits[7] = {EKeys::Zero, EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five, EKeys::Six};
	for (int32 k = 0; k < 7; ++k)
	{
		EEcoR9DemoCam M = EEcoR9DemoCam::Auto;
		TestTrue(FString::Printf(TEXT("모드 %d 가 있다"), k), EcoR9DemoCam::ModeFromInt(k, M) && static_cast<int32>(M) == k);
		EAction A = EAction::Count;
		EEcoR9DemoCam Mk = EEcoR9DemoCam::Auto;
		TestTrue(FString::Printf(TEXT("키 %d → 모드 %d (%s)"), k, k, EcoR9DemoCam::ModeNameKo(M)),
				 EcoR9DemoCam::ActionOf(Digits[k], A) && EcoR9DemoCam::ModeOf(A, Mk) && static_cast<int32>(Mk) == k);
	}
	{
		EEcoR9DemoCam M = EEcoR9DemoCam::Auto;
		TestFalse(TEXT("모드 7·−1 은 없다"), EcoR9DemoCam::ModeFromInt(7, M) || EcoR9DemoCam::ModeFromInt(-1, M));
	}
	// 4. 한 키 한 동작 · 모든 동작에 키
	TSet<FKey> Seen;
	TSet<int32> Actions;
	for (const EcoR9DemoCam::FKeyBind& B : EcoR9DemoCam::Keys())
	{
		TestFalse(FString::Printf(TEXT("키 %s 가 두 번 나오지 않음"), *B.Key.ToString()), Seen.Contains(B.Key));
		Seen.Add(B.Key);
		Actions.Add(static_cast<int32>(B.Action));
	}
	for (int32 a = 0; a < static_cast<int32>(EAction::Count); ++a)
	{
		TestTrue(FString::Printf(TEXT("동작 %d 에 키가 있다"), a), Actions.Contains(a));
	}
	// 5. 팀·기본 입력 키(Tab·R·M·[ ]·마우스 가운데·F·Shift·Ctrl·W A S D·Space·방향키)와 겹치지 않음 — 옛 카메라와 같은 표
	for (const FKey& K : EcoV3Observe::TeamReservedKeys())
	{
		EAction A = EAction::Count;
		TestFalse(FString::Printf(TEXT("팀 키 %s 는 카메라 키가 아님"), *K.ToString()), EcoR9DemoCam::ActionOf(K, A));
	}
	// 6. 옛 관찰 카메라와 겹치는 키는 같은 뜻 · R9 만 쓰는 키(6·7)는 옛 표에 없음 (옛 키와 충돌 없음)
	for (const EcoV3Observe::FKeyBind& B : EcoV3Observe::Keys())
	{
		EAction A = EAction::Count;
		TestTrue(FString::Printf(TEXT("옛 키 %s 가 R9 에서도 같은 뜻"), *B.Key.ToString()), EcoR9DemoCam::ActionOf(B.Key, A) && A == FromOld(B.Action));
	}
	const FKey R9Only[4] = {EKeys::Six, EKeys::Seven, EKeys::NumPadSix, EKeys::NumPadSeven};
	for (const FKey& K : R9Only)
	{
		bool bOld = false;
		for (const EcoV3Observe::FKeyBind& B : EcoV3Observe::Keys())
		{
			bOld = bOld || B.Key == K;
		}
		TestFalse(FString::Printf(TEXT("R9 만 쓰는 키 %s 는 옛 관찰 카메라 키가 아님"), *K.ToString()), bOld);
	}
	// 7. 자유 카메라 이동 키 (W A S D·방향키·Q E·Shift) 는 단축키가 아님 (누른 채로 읽는다)
	for (const EcoV3Observe::FFreeKey& F : EcoV3Observe::FreeMoveKeys())
	{
		EAction A = EAction::Count;
		TestFalse(FString::Printf(TEXT("자유 카메라 이동 키 %s 는 단축키가 아님"), *F.Key.ToString()), EcoR9DemoCam::ActionOf(F.Key, A));
	}
	for (const FKey& K : EcoV3Observe::FreeFastKeys())
	{
		EAction A = EAction::Count;
		TestFalse(TEXT("Shift 는 단축키가 아님"), EcoR9DemoCam::ActionOf(K, A));
	}
	// 8. 오른쪽 위 화면 줄에 키가 다 있다 (무리 자리가 있을 때만 7 · G 줄)
	const FString Help = FString::Join(EcoR9DemoCam::KeyHelpLines(true), TEXT("\n"));
	const TCHAR* const Tokens[] = {TEXT("1   늑대"), TEXT("2   사슴"), TEXT("3   탑뷰"), TEXT("4   쿼터뷰"), TEXT("5   자동 추적"), TEXT("6   멧돼지"), TEXT("7  G"),
								   TEXT(",  ."), TEXT("-  =  휠"), TEXT("0   자유 카메라"), TEXT("W A S D"), TEXT("Q E"), TEXT("Shift")};
	for (const TCHAR* Token : Tokens)
	{
		TestTrue(FString::Printf(TEXT("화면 줄에 '%s'"), Token), Help.Contains(Token));
	}
	TestFalse(TEXT("무리 자리가 없으면 7 · G 줄 없음"), FString::Join(EcoR9DemoCam::KeyHelpLines(false), TEXT("\n")).Contains(TEXT("7  G")));
	// 9. 거리·숙임·시야 = 옛 관찰 카메라 (OBSERVER_CAMERA.md 4절 표)
	TestTrue(TEXT("시야 70°"), FMath::IsNearlyEqual(EcoR9DemoCam::kFov, 70.0f));
	TestTrue(TEXT("늑대 14 m · −20°"), FMath::IsNearlyEqual(EcoR9DemoCam::kWolfDistCm, 1400.0) && FMath::IsNearlyEqual(EcoR9DemoCam::kWolfPitch, -20.0));
	TestTrue(TEXT("사슴 11 m · −18°"), FMath::IsNearlyEqual(EcoR9DemoCam::kDeerDistCm, 1100.0) && FMath::IsNearlyEqual(EcoR9DemoCam::kDeerPitch, -18.0));
	TestTrue(TEXT("탑뷰 45 m · −89°"), FMath::IsNearlyEqual(EcoR9DemoCam::kTopDistCm, 4500.0) && FMath::IsNearlyEqual(EcoR9DemoCam::kTopPitch, -89.0));
	TestTrue(TEXT("쿼터뷰 30 m · −45° · 45°"), FMath::IsNearlyEqual(EcoR9DemoCam::kQuarterDistCm, 3000.0) && FMath::IsNearlyEqual(EcoR9DemoCam::kQuarterPitch, -45.0) &&
												 FMath::IsNearlyEqual(EcoR9DemoCam::kQuarterYaw, 45.0));
	TestTrue(TEXT("자동 추적 24 m · −35° · 120 m 까지"), FMath::IsNearlyEqual(EcoR9DemoCam::kAutoDistCm, 2400.0) && FMath::IsNearlyEqual(EcoR9DemoCam::kAutoPitch, -35.0) &&
														FMath::IsNearlyEqual(EcoR9DemoCam::kAutoMaxCm, 12000.0));
	TestTrue(TEXT("탑뷰 전체: 한 변 1.1 배가 세로 화면에 드는 높이 (120 m → 약 168 m)"), FMath::IsNearlyEqual(EcoR9DemoCam::FitTopCm(12000.0), 16757.0, 50.0));
	TestTrue(TEXT("섬 전체 한 변 = max(가로 × 9/16, 세로)"), FMath::IsNearlyEqual(EcoR9DemoCam::IslandViewSizeCm(160000.0, 50000.0), 90000.0) &&
															   FMath::IsNearlyEqual(EcoR9DemoCam::IslandViewSizeCm(50000.0, 70000.0), 70000.0));
	// 10. 화면 가운데 고르기 (옛 CenterSubject 규칙: 반각 20° · 300 m 안 · 각이 가장 작은 것 · 같으면 가까운 것 · 그다음 uid 작은 것)
	{
		const FVector Eye = FVector::ZeroVector;
		const FVector Fwd(1.0, 0.0, 0.0);
		const TArray<FVector> Pts = {FVector(1000.0, 300.0, 0.0), FVector(2000.0, 0.0, 0.0), FVector(0.0, 1000.0, 0.0), FVector(40000.0, 0.0, 0.0), FVector(1000.0, 0.0, 0.0)};
		const TArray<uint32> Ids = {5, 9, 7, 2, 11};
		TestEqual(TEXT("가운데에 가장 가까운 각 (같은 각이면 가까운 것)"), EcoR9DemoCam::CenterPick(Pts, Ids, Eye, Fwd, 20.0, 30000.0), 4);
		const TArray<FVector> Side = {FVector(0.0, 1000.0, 0.0), FVector(40000.0, 0.0, 0.0)};
		const TArray<uint32> SideIds = {1, 2};
		TestEqual(TEXT("원뿔 밖·300 m 밖이면 없음"), EcoR9DemoCam::CenterPick(Side, SideIds, Eye, Fwd, 20.0, 30000.0), static_cast<int32>(INDEX_NONE));
		const TArray<FVector> Tie = {FVector(1000.0, 0.0, 0.0), FVector(1000.0, 0.0, 0.0)};
		const TArray<uint32> TieIds = {8, 3};
		TestEqual(TEXT("같은 자리면 uid 작은 것"), EcoR9DemoCam::CenterPick(Tie, TieIds, Eye, Fwd, 20.0, 30000.0), 1);
	}
	return true;
}

// 도는 데모(예전 한 무대 — eco.R9Demo.At 0,0, 시험 월드에는 땅이 없다)에서 키를 누른다 (HandleKeys 와 같은 길 PressCamKey — 시험 월드에는 플레이어 컨트롤러가 없다).
// 키로 시점·대상을 바꾸면 다음 한 프레임 만에 카메라 초점·방위·숙임·거리가 그 시점의 목표와 같아야 한다 (예전: 0.5~1.4 초 시간 상수로 천천히 옮겨 감).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoCamSwitch, "AdaptiveEcosystem.R9Demo.CamSwitch", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoCamSwitch::RunTest(const FString& Parameters)
{
	using namespace EcoR9DemoTestImpl;
	FString Why;
	if (!CanRunConsoleWorld(Why))
	{
		AddWarning(Why + TEXT(" — 건너뜀"));
		return true;
	}
	FCVarRestore Restore;
	Restore.Set(TEXT("eco.R9Demo.AllowInTests"), TEXT("1"));
	Restore.Set(TEXT("eco.R9Demo.OnlyMap"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Brains"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Scene"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.At"), TEXT("0,0"));
	Restore.Set(TEXT("eco.R9Demo.Cam"), TEXT("5"));
	Restore.Set(TEXT("eco.R9Demo"), TEXT("1"));
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
	if (!TestNotNull(TEXT("시험 월드"), World))
	{
		return false;
	}
	FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
	Ctx.SetCurrentWorld(World);
	UEcoR9DemoSubsystem* Sub = World->GetSubsystem<UEcoR9DemoSubsystem>();
	TestNotNull(TEXT("서브시스템"), Sub);
	if (Sub)
	{
		Sub->OnWorldBeginPlay(*World);
		TickDemo(*World, *Sub, 90);
		if (TestTrue(TEXT("무대가 서서 도는 중"), Sub->IsRunning()))
		{
			auto Step = [World, Sub]()
			{
				TickDemo(*World, *Sub, 1);
				return Sub->CamProbe();
			};
			auto Snapped = [this](const TCHAR* What, const FEcoR9DemoCamProbe& P)
			{
				const double DF = FVector::Dist(P.Focus, P.TargetFocus);
				const double DY = FMath::Abs(FMath::FindDeltaAngleDegrees(P.Yaw, P.TargetYaw));
				const double DP = FMath::Abs(P.Pitch - P.TargetPitch);
				const double DD = FMath::Abs(P.Dist - P.TargetDist);
				TestTrue(FString::Printf(TEXT("%s: 한 프레임 만에 그 시점 (초점 차 %.2f cm · 방위 차 %.3f° · 숙임 차 %.3f° · 거리 차 %.2f cm)"), What, DF, DY, DP, DD),
						 DF < 1.0 && DY < 0.01 && DP < 0.01 && DD < 1.0);
				if (P.bHaveCamera && P.Arm >= P.TargetDist - 1.0)
				{
					// 카메라 액터도 그 자리 (초점 − 보는 방향 × 거리 — 땅 2 m 위로 올렸으면 높이만 다를 수 있어 가로만 본다)
					const FVector Want = P.TargetFocus - FRotator(P.TargetPitch, P.TargetYaw, 0.0).Vector() * P.TargetDist;
					TestTrue(FString::Printf(TEXT("%s: 카메라 액터가 그 자리 (가로 차 %.2f cm)"), What, FVector::Dist2D(P.CameraLocation, Want)),
							 FVector::Dist2D(P.CameraLocation, Want) < 5.0);
				}
			};
			FEcoR9DemoCamProbe P = Sub->CamProbe();
			TestEqual(TEXT("처음 = 5 자동 추적 (eco.R9Demo.Cam 5)"), P.Mode, 5);
			TestTrue(TEXT("카메라 액터가 있다"), P.bHaveCamera);
			TestTrue(TEXT("오른쪽 위 카메라 줄이 있다"), P.NumLines >= 2);
			// 1 늑대 시점
			TestTrue(TEXT("1 은 카메라 키"), Sub->PressCamKey(EKeys::One));
			P = Sub->CamProbe();
			TestTrue(TEXT("1 → 늑대 시점 · 대상 늑대"), P.Mode == 1 && P.Subject != 0 && P.SubjectSpecies == 1);
			const uint32 Wolf1 = P.Subject;
			P = Step();
			Snapped(TEXT("1 늑대 시점"), P);
			TestTrue(TEXT("늑대 시점 14 m · −20°"), FMath::IsNearlyEqual(P.TargetDist, 1400.0, 1.0) && FMath::IsNearlyEqual(P.TargetPitch, -20.0, 0.01));
			// 다시 1 = 다음 늑대
			Sub->PressCamKey(EKeys::One);
			P = Step();
			TestTrue(TEXT("다시 1 = 다른 늑대"), P.Mode == 1 && P.SubjectSpecies == 1 && P.Subject != 0 && P.Subject != Wolf1);
			Snapped(TEXT("다시 1"), P);
			// 2 사슴 시점
			Sub->PressCamKey(EKeys::Two);
			P = Step();
			TestTrue(TEXT("2 → 사슴 시점 · 대상 사슴"), P.Mode == 2 && P.SubjectSpecies == 0);
			TestTrue(TEXT("사슴 시점 11 m · −18°"), FMath::IsNearlyEqual(P.TargetDist, 1100.0, 1.0) && FMath::IsNearlyEqual(P.TargetPitch, -18.0, 0.01));
			Snapped(TEXT("2 사슴 시점"), P);
			// 6 멧돼지 시점
			Sub->PressCamKey(EKeys::Six);
			P = Step();
			TestTrue(TEXT("6 → 멧돼지 시점 · 대상 멧돼지"), P.Mode == 6 && P.SubjectSpecies == 2);
			Snapped(TEXT("6 멧돼지 시점"), P);
			const uint32 Boar = P.Subject;
			// 3 탑뷰 — 보던 멧돼지 위
			Sub->PressCamKey(EKeys::Three);
			P = Step();
			TestTrue(TEXT("3 → 탑뷰 · 보던 멧돼지 위 45 m · −89°"), P.Mode == 3 && P.Subject == Boar && FMath::IsNearlyEqual(P.TargetDist, 4500.0, 1.0) &&
															   FMath::IsNearlyEqual(P.TargetPitch, -89.0, 0.01));
			Snapped(TEXT("3 탑뷰"), P);
			// 4 쿼터뷰
			Sub->PressCamKey(EKeys::Four);
			P = Step();
			TestTrue(TEXT("4 → 쿼터뷰 30 m · −45° · 방위 45°"), P.Mode == 4 && FMath::IsNearlyEqual(P.TargetDist, 3000.0, 1.0) &&
															   FMath::IsNearlyEqual(P.TargetPitch, -45.0, 0.01) && FMath::IsNearlyEqual(P.TargetYaw, 45.0, 0.01));
			Snapped(TEXT("4 쿼터뷰"), P);
			// 5 자동 추적
			Sub->PressCamKey(EKeys::Five);
			P = Step();
			TestEqual(TEXT("5 → 자동 추적"), P.Mode, 5);
			Snapped(TEXT("5 자동 추적"), P);
			// 0 자유 카메라 — 그 자리·방향 그대로
			const FVector Before = P.CameraLocation;
			const FRotator BeforeRot = P.CameraRotation;
			TestTrue(TEXT("0 은 카메라 키"), Sub->PressCamKey(EKeys::Zero));
			P = Sub->CamProbe();
			TestTrue(TEXT("0 → 자유 카메라 · 대상 없음"), P.Mode == 0 && P.Subject == 0);
			P = Step();
			TestTrue(FString::Printf(TEXT("0 = 그 자리 그대로 (자리 차 %.2f cm)"), FVector::Dist(P.CameraLocation, Before)),
					 FVector::Dist(P.CameraLocation, Before) < 1.0 && P.CameraRotation.Equals(BeforeRot, 0.05));
			// 다시 0 = 그대로 자유 카메라 (옛: 원래 카메라 — R9 데모는 폰을 숨겨 두어 0 은 늘 자유 시점)
			Sub->PressCamKey(EKeys::Zero);
			P = Step();
			TestTrue(TEXT("다시 0 = 그대로 자유 카메라 · 그 자리"), P.Mode == 0 && FVector::Dist(P.CameraLocation, Before) < 1.0);
			// 자유 카메라 속도: = 빠르게 · - 느리게 (한 번에 1.2 배, 처음 12 m/s)
			TestTrue(TEXT("자유 카메라 처음 12 m/s"), FMath::IsNearlyEqual(P.FreeSpeedMps, 12.0, 1e-6));
			Sub->PressCamKey(EKeys::Equals);
			TestTrue(TEXT("= → 14.4 m/s"), FMath::IsNearlyEqual(Sub->CamProbe().FreeSpeedMps, 14.4, 1e-6));
			Sub->PressCamKey(EKeys::Hyphen);
			TestTrue(TEXT("- → 12 m/s"), FMath::IsNearlyEqual(Sub->CamProbe().FreeSpeedMps, 12.0, 1e-6));
			// , . 는 자유 카메라에서 아무 일 없음
			Sub->PressCamKey(EKeys::Period);
			TestTrue(TEXT(". 는 자유 카메라에서 아무 일 없음"), Sub->CamProbe().Mode == 0 && Sub->CamProbe().Subject == 0);
			// 자유 카메라에서 2 = 사슴 (화면 가운데, 없으면 보는 자리 곁) — 옮겨 가지 않고 한 번에
			Sub->PressCamKey(EKeys::Two);
			P = Step();
			TestTrue(TEXT("자유 카메라에서 2 → 사슴 시점"), P.Mode == 2 && P.SubjectSpecies == 0);
			Snapped(TEXT("자유 카메라에서 2"), P);
			// H = 단축키 목록 숨기기·보이기
			const bool bKeys = Sub->CamProbe().bShowKeys;
			Sub->PressCamKey(EKeys::H);
			TestTrue(TEXT("H → 단축키 목록 바뀜"), Sub->CamProbe().bShowKeys != bKeys);
			Sub->PressCamKey(EKeys::H);
			TestTrue(TEXT("다시 H → 되돌림"), Sub->CamProbe().bShowKeys == bKeys);
			// 숫자패드 1 = 늑대 · . , = 다음·이전 늑대
			Sub->PressCamKey(EKeys::NumPadOne);
			P = Step();
			TestEqual(TEXT("숫자패드 1 → 늑대 시점"), P.Mode, 1);
			Snapped(TEXT("숫자패드 1"), P);
			const uint32 W = P.Subject;
			Sub->PressCamKey(EKeys::Period);
			P = Step();
			TestTrue(TEXT(". → 다음 늑대"), P.Subject != 0 && P.Subject != W && P.SubjectSpecies == 1);
			Snapped(TEXT(". 다음 대상"), P);
			Sub->PressCamKey(EKeys::Comma);
			P = Step();
			TestTrue(TEXT(", → 이전 늑대 (처음 늑대로)"), P.Subject == W);
			// 줌: = 가까이 (기본 거리 ÷ 1.2) — 모드를 바꾸면 1
			Sub->PressCamKey(EKeys::Equals);
			P = Step();
			TestTrue(TEXT("= → 늑대 시점 거리 14 m ÷ 1.2"), FMath::IsNearlyEqual(P.Zoom, 1.0 / 1.2, 1e-6) && FMath::IsNearlyEqual(P.TargetDist, 1400.0 / 1.2, 1.0));
			Sub->PressCamKey(EKeys::Two);
			TestTrue(TEXT("모드를 바꾸면 줌 1"), FMath::IsNearlyEqual(Sub->CamProbe().Zoom, 1.0, 1e-9));
			// 7 · G: 키는 먹는다 (예전 한 무대는 무리 자리가 없어 그 무대 그대로)
			TestTrue(TEXT("7 은 카메라 키"), Sub->PressCamKey(EKeys::Seven));
			TestTrue(TEXT("G 는 카메라 키"), Sub->PressCamKey(EKeys::G));
			// 카메라 키가 아닌 것
			TestFalse(TEXT("W 는 카메라 키가 아님 (자유 카메라 이동 — 누른 채로 읽음)"), Sub->PressCamKey(EKeys::W));
			TestFalse(TEXT("F 는 카메라 키가 아님 (팀 플레이어 키)"), Sub->PressCamKey(EKeys::F));
			// 콘솔 eco.R9Demo.Cam 4 = 쿼터뷰 (키 숫자와 같은 수)
			if (IConsoleVariable* Cam = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.R9Demo.Cam")))
			{
				Cam->Set(TEXT("4"), ECVF_SetByConsole);
				P = Step();
				TestEqual(TEXT("콘솔 eco.R9Demo.Cam 4 → 쿼터뷰"), P.Mode, 4);
				Snapped(TEXT("콘솔 4"), P);
			}
			// 끄기: 카메라도 치움
			Sub->StopDemo(TEXT("시험"));
			TestEqual(TEXT("끄면 데모 액터 0 (카메라 포함)"), CountDemoActors(*World), 0);
		}
	}
	World->DestroyWorld(false);
	GEngine->DestroyWorldContext(World);
	return true;
}

// 시작 맵에서만 (사용자 11-13 — 편집기 시작 맵 /Game/EcoTest/Maps/LV_EcoV3_Island 에서만 씀): eco.R9Demo.OnlyMap 밖 맵은 Play 시작 때 아무것도 만들지 않는다.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoR9DemoOnlyMap, "AdaptiveEcosystem.R9Demo.OnlyMap", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoR9DemoOnlyMap::RunTest(const FString& Parameters)
{
	using namespace EcoR9DemoTestImpl;
	const FString Island = TEXT("/Game/EcoTest/Maps/LV_EcoV3_Island");
	// 1. 맵 거르기 (월드 없이)
	TestTrue(TEXT("빈 값 = 모든 맵"), FEcoR9DemoSettings::MapAllowed(TEXT(""), TEXT("/Game/Map/LV_SHC_IslandEcosystem1_WP")));
	TestTrue(TEXT("공백·쉼표뿐 = 모든 맵"), FEcoR9DemoSettings::MapAllowed(TEXT("  , "), Island));
	TestTrue(TEXT("같은 맵"), FEcoR9DemoSettings::MapAllowed(Island, Island));
	TestTrue(TEXT("PIE 머리를 떼고 견줌 (편집기 Play)"), FEcoR9DemoSettings::MapAllowed(Island, TEXT("/Game/EcoTest/Maps/UEDPIE_0_LV_EcoV3_Island")));
	TestTrue(TEXT("오브젝트 경로 (…/LV_EcoV3_Island.LV_EcoV3_Island)"), FEcoR9DemoSettings::MapAllowed(Island + TEXT(".LV_EcoV3_Island"), Island));
	TestTrue(TEXT("짧은 이름 · 대소문자 무시"), FEcoR9DemoSettings::MapAllowed(TEXT("lv_ecov3_island"), Island));
	TestTrue(TEXT("쉼표·쌍반점으로 여럿"), FEcoR9DemoSettings::MapAllowed(FString(TEXT("/Game/A/B; ")) + Island, Island));
	TestFalse(TEXT("팀 섬 원본 맵은 아님"), FEcoR9DemoSettings::MapAllowed(Island, TEXT("/Game/Map/LV_SHC_IslandEcosystem1_WP")));
	TestFalse(TEXT("이름이 이어지는 다른 맵은 아님"), FEcoR9DemoSettings::MapAllowed(Island, Island + TEXT("_Copy")));
	TestFalse(TEXT("같은 폴더 다른 맵은 아님"), FEcoR9DemoSettings::MapAllowed(Island, TEXT("/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem")));
	TestFalse(TEXT("팀 통합 맵은 아님"), FEcoR9DemoSettings::MapAllowed(Island, TEXT("/Game/JWJ/Integration_JwJ")));
	TestFalse(TEXT("시험 월드는 아님"), FEcoR9DemoSettings::MapAllowed(Island, TEXT("/Temp/Untitled_1")));
	// 2. 판 출처: 명령줄 깃발은 거르지 않는다 (bFromCommandLine)
	TestTrue(TEXT("-EcoR9Demo= = 명령줄"), FEcoR9DemoSettings::Resolve(TEXT("-EcoR9Demo=C:/b")).bFromCommandLine);
	TestTrue(TEXT("-EcoR9Replay= = 명령줄"), FEcoR9DemoSettings::Resolve(TEXT("-EcoR9Replay=C:/r/demo.r9rp")).bFromCommandLine);
	{
		FCVarRestore R;
		R.Set(TEXT("eco.R9Demo"), TEXT("1"));
		R.Set(TEXT("eco.R9Demo.OnlyMap"), *Island);
		const FEcoR9DemoSettings C = FEcoR9DemoSettings::Resolve(TEXT(""));
		TestTrue(TEXT("콘솔 eco.R9Demo 1 = 콘솔 (거른다) · OnlyMap 을 읽음"), C.Mode == FEcoR9DemoSettings::EMode::Live && !C.bFromCommandLine && C.OnlyMap == Island);
	}
	// 3. 월드 (두뇌·장면이 있어야)
	FString Why;
	if (!CanRunConsoleWorld(Why))
	{
		AddWarning(Why + TEXT(" — 월드 부분 건너뜀"));
		return true;
	}
	IConsoleVariable* Demo = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.R9Demo"));
	IConsoleVariable* OnlyMap = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.R9Demo.OnlyMap"));
	if (!TestNotNull(TEXT("콘솔 값 eco.R9Demo"), Demo) || !TestNotNull(TEXT("콘솔 값 eco.R9Demo.OnlyMap"), OnlyMap))
	{
		return false;
	}
	FCVarRestore Restore;
	Restore.Set(TEXT("eco.R9Demo.AllowInTests"), TEXT("1"));
	Restore.Set(TEXT("eco.R9Demo.Brains"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.Scene"), TEXT(""));
	Restore.Set(TEXT("eco.R9Demo.At"), TEXT("0,0"));
	Restore.Set(TEXT("eco.R9Demo.OnlyMap"), *Island);
	Restore.Set(TEXT("eco.R9Demo"), TEXT("1"));
	// 3-1. 섬 맵이 아닌 시험 월드: Play 시작 때 아무것도 만들지 않는다
	{
		UWorld* World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
		if (!TestNotNull(TEXT("시험 월드"), World))
		{
			return false;
		}
		FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
		Ctx.SetCurrentWorld(World);
		UEcoR9DemoSubsystem* Sub = World->GetSubsystem<UEcoR9DemoSubsystem>();
		TestNotNull(TEXT("서브시스템 (Play 중 켜려고 늘 있다)"), Sub);
		if (Sub)
		{
			const IConsoleVariable* CamEnable = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Cam.Enable"));
			const int32 CamBefore = CamEnable ? CamEnable->GetInt() : 0;
			Sub->OnWorldBeginPlay(*World);
			TestFalse(FString::Printf(TEXT("OnlyMap 밖 맵 (%s) = Play 시작 때 켜지 않음"), *World->GetPackage()->GetName()), Sub->IsActive());
			TestTrue(TEXT("맵 거르기로 안 켰다고 앎"), Sub->WasMapFiltered());
			TestEqual(TEXT("시작 0 번"), Sub->NumStarts(), 0);
			Sub->Tick(1.0f / 30.0f);
			TestEqual(TEXT("데모 액터 0"), CountDemoActors(*World), 0);
			if (CamEnable)
			{
				TestEqual(TEXT("옛 관찰 카메라 eco.Cam.Enable 그대로 (예전 그대로)"), CamEnable->GetInt(), CamBefore);
			}
			// Play 중 직접 친 eco.R9Demo 1 은 켠다 (직접 켠 것 — 거르지 않음)
			Demo->Set(TEXT("1"), ECVF_SetByConsole);
			TestTrue(TEXT("Play 중 직접 eco.R9Demo 1 → 이 맵에서도 켬"), Sub->IsActive());
			TickDemo(*World, *Sub, 90);
			TestTrue(TEXT("무대가 서서 도는 중"), Sub->IsRunning());
			Sub->StopDemo(TEXT("시험"));
			TestEqual(TEXT("끄면 데모 액터 0"), CountDemoActors(*World), 0);
			if (CamEnable)
			{
				TestEqual(TEXT("끄면 eco.Cam.Enable 되돌림"), CamEnable->GetInt(), CamBefore);
			}
		}
		World->DestroyWorld(false);
		GEngine->DestroyWorldContext(World);
	}
	// 3-2. 목록에 이 맵이 있으면 Play 시작 때 켠다
	{
		UWorld* World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
		if (!TestNotNull(TEXT("시험 월드 2"), World))
		{
			return false;
		}
		FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
		Ctx.SetCurrentWorld(World);
		const FString Pkg = World->GetPackage()->GetName();
		OnlyMap->Set(*FString::Printf(TEXT("%s, %s"), *Island, *Pkg), ECVF_SetByConsole);
		UEcoR9DemoSubsystem* Sub = World->GetSubsystem<UEcoR9DemoSubsystem>();
		TestNotNull(TEXT("서브시스템"), Sub);
		if (Sub)
		{
			Sub->OnWorldBeginPlay(*World);
			TestTrue(FString::Printf(TEXT("목록 안 맵 (%s) = Play 시작 때 켬"), *Pkg), Sub->IsActive() && !Sub->WasMapFiltered());
			TickDemo(*World, *Sub, 90);
			TestTrue(TEXT("무대가 서서 도는 중"), Sub->IsRunning());
		}
		World->DestroyWorld(false);
		GEngine->DestroyWorldContext(World);
	}
	return true;
}

#endif
