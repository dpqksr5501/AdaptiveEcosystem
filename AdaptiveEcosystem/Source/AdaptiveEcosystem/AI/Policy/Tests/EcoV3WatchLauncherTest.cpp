// Play 때 파이썬 감시 자동 시작 자동화 시험 (10-27, EcoV3WatchLauncher.{h,cpp} — 설계 Docs/RL_Policy/FOREST_GROWTH_MODE.md 3절).
// 학습 파이프라인을 따로 띄우는 개발용 도구다 (추론 아님). 이 시험은 파이썬을 띄우지 않는다 — 순수 함수와, 윈도에서는 cmd.exe 로 띄우기·끝 까닭·끝내기만 본다.
//
// 묶음:
//   WatchLauncher.Command  명령 글 (기본 '-X utf8 -u results/v3/live/live.py watch --root "<root>"'·덮기 자리표), python 찾기 (PATH·WindowsApps 스토어 대역 거부·
//                          전체 경로), live.py 잠금·watcher.pid JSON, 끝 까닭 (잠김·다른 고리·종료 코드), 상태 줄·알림 글, 폴더 안전장치, 띄우기 판정 (끔·AutoAdapt 끔·
//                          시험 중·클라이언트·폴더·이미 돈다(우리·사람·다른 언리얼)·python 없음·live.py 없음), 프로세스 살았나 (이 편집기 pid·시작 시각·python 이름),
//                          기록 끝 읽기 (UTF-8), 기록 20 개만 남기기
//   WatchLauncher.Process  (윈도) cmd.exe 를 창 없이 띄워: 잠김 글을 쓰고 종료 코드 1 → 까닭 '잠김'·watcher.pid 지움, 오래 도는 것 → Stop 이 작업 개체째 끝냄
//   WatchLauncher.Deactivate (윈도, 10-27 적대적 검토) 서브시스템이 띄운 감시: 켜진 동안 그대로, Play 중 통합 v3 모드가 꺼지면(자원 계약 거부) 그때 나무째 끝냄

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoV3WatchLauncher.h"
#include "EcoTestWorld.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoV3WatchTestImpl
{
	using namespace EcoV3Watch;

	FString TempDir(const TCHAR* Name)
	{
		const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"), Name));
		IFileManager::Get().DeleteDirectory(*Dir, false, true);
		IFileManager::Get().MakeDirectory(*Dir, true);
		return Dir;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3WatchCommandTest,
	"AdaptiveEcosystem.Policy.V3.WatchLauncher.Command",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3WatchCommandTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3WatchTestImpl;
	// 1. 명령 글
	TestEqual(TEXT("기본 인자"), BuildArgs(TEXT(""), TEXT("C:/x/Saved/EcoAdapt"), TEXT("p1"), TEXT("C:/x/log.txt")),
			  FString(TEXT("-X utf8 -u results/v3/live/live.py watch --root \"C:/x/Saved/EcoAdapt\"")));
	TestEqual(TEXT("덮기 자리표 {root}·{play}·{log}"), BuildArgs(TEXT(" -X utf8 -u fake.py --root {root} --play {play} --log {log} "), TEXT("R"), TEXT("P"), TEXT("L")),
			  FString(TEXT("-X utf8 -u fake.py --root R --play P --log L")));

	// 2. python 찾기 (가짜 파일 목록)
	const TSet<FString> Have = {TEXT("C:\\Users\\U\\AppData\\Local\\Microsoft\\WindowsApps/python.exe"), TEXT("C:\\Users\\U\\anaconda3/python.exe"),
								TEXT("D:/py/python3.exe")};
	auto Exists = [&Have](const FString& P) { return Have.Contains(P); };
	FString Why;
	TestEqual(TEXT("PATH: WindowsApps 를 건너뛰고 anaconda"),
			  ResolvePython(TEXT("python"), TEXT("C:\\Users\\U\\AppData\\Local\\Microsoft\\WindowsApps;C:\\Users\\U\\anaconda3;C:\\Other"), Exists, Why),
			  FString(TEXT("C:\\Users\\U\\anaconda3\\python.exe")));
	TestTrue(TEXT("PATH 에 스토어 대역만 → 못 찾음 (까닭에 WindowsApps)"),
			 ResolvePython(TEXT("python"), TEXT("C:\\Users\\U\\AppData\\Local\\Microsoft\\WindowsApps"), Exists, Why).IsEmpty() && Why.Contains(TEXT("WindowsApps")));
	TestEqual(TEXT("전체 경로 그대로"), ResolvePython(TEXT("D:/py/python3.exe"), TEXT(""), Exists, Why), FString(TEXT("D:/py/python3.exe")));
	TestTrue(TEXT("없는 전체 경로 → 빈 값"), ResolvePython(TEXT("D:/py/nope.exe"), TEXT(""), Exists, Why).IsEmpty() && !Why.IsEmpty());
	TestTrue(TEXT("전체 경로라도 WindowsApps 는 거부"),
			 ResolvePython(TEXT("C:\\Users\\U\\AppData\\Local\\Microsoft\\WindowsApps/python.exe"), TEXT(""), Exists, Why).IsEmpty());

	// 3. live.py 잠금·watcher.pid
	{
		FLock L;
		TestTrue(TEXT("잠금 JSON (pid·create_time·what·time)"),
				 ParseLock(TEXT("{\"pid\": 4321, \"create_time\": 1761543210.25, \"what\": \"watch\", \"time\": \"2026-10-27T05:00:00Z\"}"), L) && L.Pid == 4321
					 && L.bHasCreateTime && L.CreateTime == 1761543210.25 && L.What == TEXT("watch"));
		TestTrue(TEXT("create_time null → 시각 없음"), ParseLock(TEXT("{\"pid\": 7, \"create_time\": null, \"what\": \"round\"}"), L) && L.Pid == 7 && !L.bHasCreateTime);
		TestFalse(TEXT("깨진 JSON"), ParseLock(TEXT("{\"pid\": "), L));
		TestFalse(TEXT("pid 없음"), ParseLock(TEXT("{\"what\": \"watch\"}"), L));
		FPidFile P;
		P.Pid = 99;
		P.CreateUnix = 1761543210.5;
		P.PlayId = TEXT("p20261027T000000_1");
		P.EditorPid = 12;
		P.Exe = TEXT("C:\\py\\python.exe");
		P.Args = TEXT("-X utf8 -u results/v3/live/live.py watch --root \"C:/r\"");
		P.Log = TEXT("C:/r/watch_p.log");
		P.StartedUtc = TEXT("2026-10-27T05:00:00.000Z");
		FPidFile Q;
		TestTrue(TEXT("watcher.pid 왕복"), ParsePidFile(PidFileJson(P), Q) && Q.Pid == 99 && Q.CreateUnix == P.CreateUnix && Q.PlayId == P.PlayId && Q.EditorPid == 12
												 && Q.Exe == P.Exe && Q.Args == P.Args && Q.Log == P.Log);
	}

	// 4. 끝 까닭 → 상태 줄·알림
	TestTrue(TEXT("잠김 (flight_sizes_confirmed)"),
			 ClassifyEnd(1, TEXT("SystemExit: 1차 사건 숨음 비율 기준의 크기 … (LIVE flight_sizes_confirmed 거짓, …")) == EEnd::Locked);
	TestTrue(TEXT("다른 고리"), ClassifyEnd(1, TEXT("다른 실시간 고리(watch, pid 5, …)가 … 를 쓰고 있다")) == EEnd::OtherLoop);
	TestTrue(TEXT("그 밖 종료 코드 ≠ 0"), ClassifyEnd(2, TEXT("Traceback …")) == EEnd::Failed);
	TestTrue(TEXT("종료 코드 0"), ClassifyEnd(0, TEXT("")) == EEnd::Done);
	TestEqual(TEXT("잠김 상태 줄"), EndStatusText(EEnd::Locked, 1, TEXT("watch_p.log"), 0), FString(TEXT("적응 고리 | 파이썬 감시 꺼짐 — 실제 폴더 잠김 (관문 크기 확정 전)")));
	TestEqual(TEXT("다른 고리 상태 줄"), EndStatusText(EEnd::OtherLoop, 1, TEXT("watch_p.log"), 4321), FString(TEXT("적응 고리 | 다른 감시가 돈다 (pid 4321)")));
	TestEqual(TEXT("실패 상태 줄"), EndStatusText(EEnd::Failed, 3, TEXT("watch_p.log"), 0), FString(TEXT("적응 고리 | 파이썬 감시 꺼짐 — 종료 코드 3 (기록 watch_p.log)")));
	TestEqual(TEXT("끝남 상태 줄"), EndStatusText(EEnd::Done, 0, TEXT("watch_p.log"), 0), FString(TEXT("적응 고리 | 파이썬 감시 끝남")));
	TestTrue(TEXT("알림: 잠김·실패만 (다른 고리·끝남은 없음)"), EndNoticeText(EEnd::Locked, TEXT("w.log")).Contains(TEXT("실제 폴더 잠김"))
															  && EndNoticeText(EEnd::Failed, TEXT("w.log")).Contains(TEXT("w.log"))
															  && EndNoticeText(EEnd::OtherLoop, TEXT("w.log")).IsEmpty() && EndNoticeText(EEnd::Done, TEXT("w.log")).IsEmpty());

	// 5. 폴더 안전장치
	TestTrue(TEXT("같은 경로 (구분자·끝 구분자·대소문자)"), SamePath(TEXT("C:\\A\\b\\"), TEXT("c:/a/B")));
	TestTrue(TEXT("한 root 아래 → 맞음"),
			 RootMismatch(TEXT("C:/P/Saved/EcoAdapt"), TEXT("C:/P/Saved/EcoAdapt/snapshots"), TEXT("C:\\P\\Saved\\EcoAdapt\\brains"), TEXT("C:/P/Saved/EcoAdapt/status.json"))
				 .IsEmpty());
	TestTrue(TEXT("스냅숏 폴더를 따로 덮음 → 안 맞음"),
			 RootMismatch(TEXT("C:/P/Saved/EcoAdapt"), TEXT("C:/tmp/snaps"), TEXT("C:/P/Saved/EcoAdapt/brains"), TEXT("C:/P/Saved/EcoAdapt/status.json")).Contains(TEXT("스냅숏")));
	TestTrue(TEXT("두뇌 감시 끔 → 안 맞음"), !RootMismatch(TEXT("C:/R"), TEXT("C:/R/snapshots"), TEXT(""), TEXT("C:/R/status.json")).IsEmpty());

	// 6. 띄우기 판정
	{
		FDecideIn In;
		In.bAutoAdapt = true;
		TestTrue(TEXT("기본 → 띄움"), Decide(In) == EDecide::Launch);
		FDecideIn X = In;
		X.bAutoWatch = false;
		TestTrue(TEXT("AutoWatch 0 → 끔"), Decide(X) == EDecide::Off);
		X = In;
		X.bAutoAdapt = false;
		TestTrue(TEXT("AutoAdapt 0 → 끔"), Decide(X) == EDecide::NoAdapt);
		X = In;
		X.bTesting = true;
		TestTrue(TEXT("자동화 시험 중 → 안 띄움"), Decide(X) == EDecide::Testing);
		X = In;
		X.bClient = true;
		TestTrue(TEXT("클라이언트 → 안 띄움"), Decide(X) == EDecide::Client);
		X = In;
		X.RootMismatch = TEXT("스냅숏 폴더 …");
		X.bLockAlive = true;
		TestTrue(TEXT("폴더 안전장치가 먼저"), Decide(X) == EDecide::Unsafe);
		X = In;
		X.bOursAlive = true;
		X.bLockAlive = true;
		TestTrue(TEXT("이 편집기가 띄운 감시가 돈다 → 그대로"), Decide(X) == EDecide::OursRunning);
		X = In;
		X.bLockAlive = true;
		TestTrue(TEXT("잠금 주인이 산 python → 사람이 띄움 (건드리지 않음)"), Decide(X) == EDecide::HumanRunning);
		X.bLockIsOurs = true;
		X.bPidFileAlive = true;
		TestTrue(TEXT("잠금 주인 = watcher.pid → 다른 언리얼이 띄움"), Decide(X) == EDecide::OtherEditor);
		X = In;
		X.bPidFileAlive = true;
		TestTrue(TEXT("watcher.pid 주인이 삶 (잠금 전) → 다른 언리얼이 띄움"), Decide(X) == EDecide::OtherEditor);
		X = In;
		X.bPython = false;
		TestTrue(TEXT("python 없음"), Decide(X) == EDecide::NoPython);
		X = In;
		X.bScript = false;
		TestTrue(TEXT("live.py 없음"), Decide(X) == EDecide::NoScript);
	}

	// 7. 프로세스 살았나 (이 편집기 프로세스 — 윈도만)
#if PLATFORM_WINDOWS
	{
		const int32 Me = static_cast<int32>(FPlatformProcess::GetCurrentProcessId());
		double Created = 0.0;
		TestTrue(TEXT("이 프로세스 시작 시각을 읽는다"), FEcoV3WatchLauncher::ProcessCreateUnix(Me, Created) && Created > 1.5e9);
		FString Image;
		TestTrue(TEXT("이 프로세스는 살아 있다 (시작 시각 같음)"), FEcoV3WatchLauncher::IsProcessAlive(Me, Created, false, &Image) && !Image.IsEmpty());
		TestFalse(TEXT("시작 시각이 다르면 다른 프로세스 (pid 재사용)"), FEcoV3WatchLauncher::IsProcessAlive(Me, Created - 10.0, false));
		TestFalse(TEXT("python 이 아니면 잠금 주인이 아니다"), FEcoV3WatchLauncher::IsProcessAlive(Me, Created, true));
		TestFalse(TEXT("pid 0 → 아님"), FEcoV3WatchLauncher::IsProcessAlive(0, -1.0, false));
	}
#endif

	// 8. 기록 끝 읽기 (UTF-8) · 기록 20 개만
	{
		const FString Dir = TempDir(TEXT("EcoV3WatchLogs"));
		ON_SCOPE_EXIT
		{
			IFileManager::Get().DeleteDirectory(*Dir, false, true);
		};
		const FString Log = Dir / TEXT("watch_t.log");
		FFileHelper::SaveStringToFile(TEXT("앞 줄\n감시 시작: 스냅숏 기다림\n"), *Log, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
		TestTrue(TEXT("기록 끝 (UTF-8 한국어)"), FEcoV3WatchLauncher::ReadTail(Log, 4096).Contains(TEXT("스냅숏 기다림")));
		for (int32 i = 0; i < 5; ++i)
		{
			const FString P = Dir / FString::Printf(TEXT("watch_%d.log"), i);
			FFileHelper::SaveStringToFile(TEXT("x"), *P);
			IFileManager::Get().SetTimeStamp(*P, FDateTime(2026, 10, 1 + i));
		}
		IFileManager::Get().SetTimeStamp(*Log, FDateTime(2026, 9, 1));
		FEcoV3WatchLauncher::PruneLogs(Dir, 2);
		TArray<FString> Left;
		IFileManager::Get().FindFiles(Left, *(Dir / TEXT("watch_*.log")), true, false);
		Left.Sort();
		TestTrue(TEXT("새것 둘만 남김 (watch_3·watch_4)"), Left.Num() == 2 && Left[0] == TEXT("watch_3.log") && Left[1] == TEXT("watch_4.log"));
	}
	return true;
}

#if PLATFORM_WINDOWS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3WatchProcessTest,
	"AdaptiveEcosystem.Policy.V3.WatchLauncher.Process",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3WatchProcessTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3WatchTestImpl;
	FEcoV3WatchLauncher& L = FEcoV3WatchLauncher::Get();
	if (L.IsRunning())
	{
		AddWarning(TEXT("이 프로세스에 띄운 감시가 돈다 — 시험을 건너뛴다"));
		return true;
	}
	const FString Cmd = FPlatformMisc::GetEnvironmentVariable(TEXT("ComSpec"));
	const FString Exe = Cmd.IsEmpty() ? FString(TEXT("C:\\Windows\\System32\\cmd.exe")) : Cmd;
	if (!FPaths::FileExists(Exe))
	{
		AddWarning(TEXT("cmd.exe 가 없다 — 시험을 건너뛴다"));
		return true;
	}
	const FString Root = TempDir(TEXT("EcoV3WatchRoot"));
	ON_SCOPE_EXIT
	{
		L.ResetEnded();
		IFileManager::Get().DeleteDirectory(*Root, false, true);
	};
	static int32 OwnerTag = 0;
	const void* Owner = &OwnerTag;

	// 1. 잠김 글을 stderr 에 쓰고 종료 코드 1 → 까닭 '잠김', watcher.pid 를 쓰고 끝나면 지운다
	{
		const FString Log = Root / TEXT("watch_lock.log");
		FString Why;
		const bool bLaunched = L.Launch(Exe, TEXT("/d /c echo LIVE flight_sizes_confirmed false 1>&2 & exit 1"), Root, Log, Root, TEXT("ptest"), Owner, Why);
		if (!TestTrue(*FString::Printf(TEXT("띄움 (%s)"), *Why), bLaunched))
		{
			return false;
		}
		TestTrue(TEXT("watcher.pid 를 썼다"), FPaths::FileExists(Root / TEXT("watcher.pid")));
		if (!L.UsesJob())
		{
			AddWarning(TEXT("작업 개체에 넣지 못했다 (이 프로세스가 겹친 작업 개체를 받지 않는 작업 안이다) — 끝낼 때 프로세스 나무 걷기로"));
		}
		bool bEnded = false;
		for (int32 i = 0; i < 100 && !bEnded; ++i)
		{
			bEnded = L.Poll();
			if (!bEnded)
			{
				FPlatformProcess::Sleep(0.05f);
			}
		}
		TestTrue(TEXT("5 초 안에 끝남"), bEnded);
		TestTrue(TEXT("종료 코드 1 · 까닭 잠김"), L.GetExitCode() == 1 && L.GetEnd() == EEnd::Locked);
		TestFalse(TEXT("끝나면 watcher.pid 지움"), FPaths::FileExists(Root / TEXT("watcher.pid")));
		TestTrue(TEXT("기록 파일에 stderr 글"), FEcoV3WatchLauncher::ReadTail(Log, 4096).Contains(TEXT("flight_sizes_confirmed")));
	}
	// 2. 오래 도는 프로세스 나무 (cmd → ping) → Stop 이 작업 개체째 끝낸다 (다른 주인은 못 끝낸다)
	{
		FString Why;
		const bool bLaunched = L.Launch(Exe, TEXT("/d /c ping -n 60 127.0.0.1 >nul"), Root, Root / TEXT("watch_long.log"), Root, TEXT("ptest2"), Owner, Why);
		if (!TestTrue(*FString::Printf(TEXT("띄움 (%s)"), *Why), bLaunched))
		{
			return false;
		}
		const int32 Pid = L.GetPid();
		double Created = 0.0;
		FEcoV3WatchLauncher::ProcessCreateUnix(Pid, Created);
		FPlatformProcess::Sleep(0.3f);
		TestFalse(TEXT("돈다 (아직 안 끝남)"), L.Poll());
		static int32 OtherTag = 0;
		TestFalse(TEXT("다른 주인은 끝내지 못한다"), L.Stop(&OtherTag, TEXT("시험")));
		TestTrue(TEXT("주인이 끝냄"), L.Stop(Owner, TEXT("시험")));
		TestTrue(TEXT("까닭 '우리가 끝냄' · 더 돌지 않음"), L.GetEnd() == EEnd::Stopped && !L.IsRunning());
		TestFalse(TEXT("그 pid 는 더 살아 있지 않다"), FEcoV3WatchLauncher::IsProcessAlive(Pid, Created, false));
		TestFalse(TEXT("watcher.pid 지움"), FPaths::FileExists(Root / TEXT("watcher.pid")));
	}
	return true;
}

// 10-27 적대적 검토: Play 중 통합 v3 모드가 꺼지면(자원 계약 거부 등) 서브시스템이 띄운 감시를 그때 끝낸다 (HandlePreActorTick → StopAutoWatchIfInactive).
// 켜진 동안은 건드리지 않는다. cmd.exe → ping 나무를 서브시스템 주인으로 띄워 본다 (파이썬 없음)
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3WatchDeactivateTest,
	"AdaptiveEcosystem.Policy.V3.WatchLauncher.Deactivate",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3WatchDeactivateTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3WatchTestImpl;
	FEcoV3WatchLauncher& L = FEcoV3WatchLauncher::Get();
	if (L.IsRunning())
	{
		AddWarning(TEXT("이 프로세스에 띄운 감시가 돈다 — 시험을 건너뛴다"));
		return true;
	}
	const FString Cmd = FPlatformMisc::GetEnvironmentVariable(TEXT("ComSpec"));
	const FString Exe = Cmd.IsEmpty() ? FString(TEXT("C:\\Windows\\System32\\cmd.exe")) : Cmd;
	if (!FPaths::FileExists(Exe))
	{
		AddWarning(TEXT("cmd.exe 가 없다 — 시험을 건너뛴다"));
		return true;
	}
	const FString Root = TempDir(TEXT("EcoV3WatchDeactivate"));
	ON_SCOPE_EXIT
	{
		L.ResetEnded();
		IFileManager::Get().DeleteDirectory(*Root, false, true);
	};
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World))
	{
		return false;
	}
	UEcoPolicyV3IntegratedSubsystem* Sub = W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	if (!TestNotNull(TEXT("통합 서브시스템"), Sub))
	{
		return false;
	}
	FEcoV3IntegratedSettings S;
	S.Seed = 38200;
	Sub->ActivateForTest(S, false);
	FString Why;
	const bool bLaunched = Sub->LaunchWatchForTest(Exe, TEXT("/d /c ping -n 60 127.0.0.1 >nul"), Root, Why);
	if (!TestTrue(*FString::Printf(TEXT("서브시스템 주인으로 띄움 (%s)"), *Why), bLaunched))
	{
		return false;
	}
	const int32 Pid = L.GetPid();
	double Created = 0.0;
	FEcoV3WatchLauncher::ProcessCreateUnix(Pid, Created);
	FPlatformProcess::Sleep(0.3f);
	TestFalse(TEXT("켜진 동안은 끝내지 않는다"), Sub->StopAutoWatchIfInactive());
	TestTrue(TEXT("켜진 동안 감시가 돈다"), L.IsRunning() && FEcoV3WatchLauncher::IsProcessAlive(Pid, Created, false));
	AddExpectedErrorPlain(TEXT("통합 v3 모드를 끈다"), EAutomationExpectedErrorFlags::Contains, 1);
	Sub->RejectResourceContract();   // Play 중 꺼짐 (자원 계약 거부 — Deactivate)
	TestFalse(TEXT("통합 v3 모드 꺼짐"), Sub->IsActive());
	TestTrue(TEXT("꺼지면 우리가 띄운 감시를 끝낸다"), Sub->StopAutoWatchIfInactive());
	TestTrue(TEXT("까닭 '우리가 끝냄' · 더 돌지 않음"), L.GetEnd() == EEnd::Stopped && !L.IsRunning());
	TestFalse(TEXT("그 pid 는 더 살아 있지 않다"), FEcoV3WatchLauncher::IsProcessAlive(Pid, Created, false));
	TestFalse(TEXT("watcher.pid 지움"), FPaths::FileExists(Root / TEXT("watcher.pid")));
	TestFalse(TEXT("두 번째는 할 일이 없다"), Sub->StopAutoWatchIfInactive());
	return true;
}
#endif

#endif // WITH_DEV_AUTOMATION_TESTS
