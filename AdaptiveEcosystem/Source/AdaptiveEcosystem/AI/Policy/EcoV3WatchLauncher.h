// 통합 v3 적응 고리 — Play 때 파이썬 감시(live.py watch) 자동 시작 (10-27 사용자 결정, 설계 Docs/RL_Policy/FOREST_GROWTH_MODE.md 3절, LIVE_ADAPT_SPEC.md 5.5).
//
// AGENTS.md 원칙과의 관계: 게임 런타임 추론은 지금처럼 C++ 네이티브만이다 (사슴 결정은 내장·두뇌 파일 가중치를 C++ 가 계산한다). 여기서 띄우는 것은
// 학습 파이프라인(herbivore_rl/results/v3/live/live.py watch)을 따로 띄우는 개발용 도구다 — 추론이 아니고, 게임 스레드를 막지 않으며(띄우기는 몇 ms,
// 살아 있나 보기는 2 초마다 기다림 없는 WaitForSingleObject(…, 0), 끝낼 때만 최대 3 초), #if !UE_BUILD_SHIPPING 이고, eco.IntegratedV3.AutoAdapt 를 켰을 때만,
// 서버·단독 월드에서만 돈다. 파이썬이 내는 것은 지금처럼 두뇌 파일뿐이고, 언리얼은 그것을 결정 스텝 경계에서 C++ 가중치로 바꿔 끼운다.
//
// 띄우는 명령 (작업 폴더 <프로젝트>/../herbivore_rl, 표준 출력·오류 = <root>/watch_<play_id>.log):
//   <python 전체 경로> -X utf8 -u results/v3/live/live.py watch --root "<root 절대 경로>"
// 창 없이: CreateProcessW(CREATE_NO_WINDOW | CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT) — 숨은 콘솔을 받아 감시가 띄우는 판·학습 자식도 그 콘솔을
//   물려받아 창이 없다. 물려줄 손잡이는 기록 파일·NUL 둘뿐(PROC_THREAD_ATTRIBUTE_HANDLE_LIST). 멈춘 채 만들어 윈도 작업 개체(KILL_ON_JOB_CLOSE)에 넣은 뒤
//   깨운다 — 그래서 감시가 자식을 띄우기 전에 작업 개체 안이다 (엔진 FPlatformProcess::CreateProc 은 작업 개체를 모르고 '띄운 뒤 넣기' 경주가 남는다).
// 중복 방지 (먼저 맞는 것에서 멈춘다): 이 편집기가 띄운 감시가 살아 있음 → <root>/live/watch.lock (live.py 잠금 — pid·시작 시각) 주인이 산 python →
//   <root>/watcher.pid (다른 언리얼 프로세스가 띄움) 주인이 삶. 그래도 경주가 나면 live.py 의 O_EXCL 잠금이 마지막 심판이다.
// 정리: Play 끝(서브시스템 Deinitialize, 띄운 그 서브시스템만) — 작업 개체째 끝냄(학습 자식 포함 프로세스 나무), 최대 3 초 기다림, watcher.pid 지움.
//   편집기가 죽으면 작업 개체 손잡이가 닫히며 감시 나무도 끝난다. 사람이 띄운 감시·다른 워크플로의 파이썬·live.py 의 파일은 건드리지 않는다.

#pragma once

#include "CoreMinimal.h"
#include "Templates/Function.h"

namespace EcoV3Watch
{
	/** live.py 위치 (작업 폴더 herbivore_rl 기준). */
	inline constexpr const TCHAR* kScriptRel = TEXT("results/v3/live/live.py");
	/** 감시 살핌 간격 (실시간 초). */
	inline constexpr double kPollSeconds = 2.0;
	/** 끝낼 때 기다리는 최대 실시간 초. */
	inline constexpr uint32 kStopWaitMs = 3000;
	/** 남기는 watch_*.log 수. */
	inline constexpr int32 kKeepLogs = 20;
	/** 잠금·pid 파일의 시작 시각을 프로세스 시작 시각과 견주는 허용 (초). */
	inline constexpr double kCreateTolerance = 0.5;

	/** 기본 인자 (Override 가 비면): -X utf8 -u results/v3/live/live.py watch --root "<Root>". Override 는 자리표 {root}·{play}·{log} 를 바꾼다. */
	ADAPTIVEECOSYSTEM_API FString BuildArgs(const FString& Override, const FString& Root, const FString& PlayId, const FString& InLogFile);

	/**
	 * python 실행 파일 찾기. Setting 에 경로 구분자가 있으면 그 파일(있을 때만). 없으면 PathEnv(';' 로 나눔)의 폴더마다 Setting(.exe 붙임)을 찾되
	 * '\WindowsApps\' 아래 것(스토어 대역 — 파이썬이 없으면 스토어 창을 띄운다)은 건너뛴다. 못 찾으면 빈 값 (OutWhy = 까닭).
	 */
	ADAPTIVEECOSYSTEM_API FString ResolvePython(const FString& Setting, const FString& PathEnv, TFunctionRef<bool(const FString&)> FileExists, FString& OutWhy);

	/** live.py 잠금 <root>/live/watch.lock ({pid, create_time, what, time}). */
	struct FLock
	{
		int32 Pid = 0;
		double CreateTime = 0.0;
		bool bHasCreateTime = false;   // create_time 이 null 이면 거짓 (psutil 이 없던 파이썬)
		FString What;
		FString Time;
	};
	ADAPTIVEECOSYSTEM_API bool ParseLock(const FString& JsonText, FLock& Out);

	/** 우리 기록 <root>/watcher.pid (언리얼이 띄울 때 쓴다). */
	struct FPidFile
	{
		int32 Pid = 0;
		double CreateUnix = 0.0;
		FString PlayId;
		int32 EditorPid = 0;
		FString Exe;
		FString Args;
		FString Log;
		FString StartedUtc;
	};
	ADAPTIVEECOSYSTEM_API FString PidFileJson(const FPidFile& P);
	ADAPTIVEECOSYSTEM_API bool ParsePidFile(const FString& JsonText, FPidFile& Out);

	/** 감시가 끝난 까닭 (종료 코드 + 기록 끝 줄). */
	enum class EEnd : uint8
	{
		None,        // 아직 돈다·띄우지 않음
		Locked,      // 실제 폴더 잠김 (기록에 'flight_sizes_confirmed')
		OtherLoop,   // 다른 실시간 고리가 폴더를 쓴다 (기록에 '다른 실시간 고리')
		Failed,      // 그 밖 종료 코드 ≠ 0
		Done,        // 종료 코드 0
		Stopped      // 우리가 끝냈다 (Play 끝)
	};
	ADAPTIVEECOSYSTEM_API EEnd ClassifyEnd(int32 ExitCode, const FString& LogTail);
	/** 상태 줄 글 '적응 고리 | …' (3.7 표). OtherPid = 잠금 주인 (다른 고리, 모르면 0). */
	ADAPTIVEECOSYSTEM_API FString EndStatusText(EEnd Reason, int32 ExitCode, const FString& LogName, int32 OtherPid);
	/** 화면 알림 (한 번, 거부 색). 빈 값 = 알림 없음. */
	ADAPTIVEECOSYSTEM_API FString EndNoticeText(EEnd Reason, const FString& LogName);

	/** 경로 같음 (정규화·끝 구분자 무시·대소문자 무시). */
	ADAPTIVEECOSYSTEM_API bool SamePath(const FString& A, const FString& B);
	/** 폴더 안전장치: 스냅숏·두뇌 감시·상태 파일이 <Root>/snapshots·<Root>/brains·<Root>/status.json 이 아니면 그 까닭 (같으면 빈 값). */
	ADAPTIVEECOSYSTEM_API FString RootMismatch(const FString& Root, const FString& SnapshotDir, const FString& BrainDir, const FString& StatusFile);

	/** 띄우기 판정 입력 (모두 바깥에서 잰 값 — 순수 시험). */
	struct FDecideIn
	{
		bool bAutoAdapt = false;     // eco.IntegratedV3.AutoAdapt
		bool bAutoWatch = true;      // eco.IntegratedV3.AutoWatch
		bool bTesting = false;       // 자동화 시험 중 (GIsAutomationTesting)
		bool bClient = false;        // 클라이언트 월드
		FString RootMismatch;        // RootMismatch (빈 값 = 맞음)
		bool bOursAlive = false;     // 이 편집기가 띄운 감시가 살아 있음
		bool bLockAlive = false;     // watch.lock 주인이 산 python
		bool bLockIsOurs = false;    //   그 주인이 watcher.pid 의 pid (다른 언리얼이 띄운 감시)
		bool bPidFileAlive = false;  // watcher.pid 주인이 삶
		bool bPython = true;         // python 을 찾았다
		bool bScript = true;         // live.py 가 있다 (명령 덮기면 늘 참)
	};
	enum class EDecide : uint8
	{
		Launch,
		Off,          // eco.IntegratedV3.AutoWatch 0
		NoAdapt,      // AutoAdapt 0
		Testing,      // 자동화 시험 중
		Client,       // 클라이언트
		Unsafe,       // 폴더 안전장치
		OursRunning,  // 이 편집기가 띄운 감시가 돈다 — 그대로
		HumanRunning, // 사람이 띄운 감시가 돈다 — 건드리지 않음
		OtherEditor,  // 다른 언리얼 프로세스가 띄운 감시가 돈다
		NoPython,
		NoScript,
		LaunchFailed  // 띄우기 실패 (CreateProcess·기록 파일 — Decide 는 내지 않는다, 띄운 뒤 정한다)
	};
	ADAPTIVEECOSYSTEM_API EDecide Decide(const FDecideIn& In);
	ADAPTIVEECOSYSTEM_API const TCHAR* DecideName(EDecide D);
}

/**
 * 감시 프로세스 관리자 (프로세스에 하나, 게임 스레드에서만). 이 편집기가 띄운 감시 하나의 손잡이·작업 개체를 쥔다.
 * 윈도만 실제로 띄운다 (그 밖 플랫폼은 Launch 가 거짓 — '이 플랫폼에서는 못 띄움').
 */
class ADAPTIVEECOSYSTEM_API FEcoV3WatchLauncher
{
public:
	static FEcoV3WatchLauncher& Get();

	/** 띄운다 (멈춘 채 만들고 작업 개체에 넣은 뒤 깨운다). Owner = 띄운 서브시스템 (끝낼 때 견준다). 성공하면 참 (OutWhy = 실패 까닭). */
	bool Launch(const FString& Exe, const FString& Args, const FString& WorkDir, const FString& InLogPath, const FString& Root, const FString& PlayId,
				const void* Owner, FString& OutWhy);
	/** 살핌 (기다리지 않는다): 끝났으면 종료 코드·기록 끝 줄로 까닭을 정하고 손잡이·작업 개체를 닫고 watcher.pid 를 지운다. 이번에 끝난 것을 알았으면 참. */
	bool Poll();
	/** Owner 가 띄운 감시를 프로세스 나무째 끝낸다 (작업 개체, 최대 3 초 기다림). 끝냈으면 참. */
	bool Stop(const void* Owner, const TCHAR* Why);

	bool IsRunning() const { return bRunning; }
	bool HasLaunched() const { return bLaunched; }
	const void* GetOwner() const { return Owner; }
	int32 GetPid() const { return Pid; }
	double GetLaunchedUnix() const { return LaunchedUnix; }
	EcoV3Watch::EEnd GetEnd() const { return End; }
	int32 GetExitCode() const { return ExitCode; }
	const FString& GetLogPath() const { return LogPath; }
	const FString& GetRoot() const { return Root; }
	bool UsesJob() const { return bJob; }
	/** 시험: 상태를 지운다 (손잡이가 없을 때만). */
	void ResetEnded();

	/** pid 가 살아 있고 시작 시각(유닉스 초)이 CreateUnix 와 허용 안인가 (CreateUnix < 0 이면 시각은 보지 않는다). bRequirePython 이면 실행 파일 이름이 python* 이어야 한다. */
	static bool IsProcessAlive(int32 InPid, double CreateUnix, bool bRequirePython, FString* OutImage = nullptr);
	/** pid 의 시작 시각 (유닉스 초). 못 읽으면 거짓. */
	static bool ProcessCreateUnix(int32 InPid, double& OutUnix);
	/** 파일 끝 MaxBytes 를 읽기·쓰기 공유로 열어 UTF-8 로 (기록 파일 — 감시가 아직 쓰는 중일 수 있다). */
	static FString ReadTail(const FString& Path, int32 MaxBytes);
	/** <Root>/watch_*.log 를 새것부터 Keep 개만 남긴다 (오래된 것부터 지운다). */
	static void PruneLogs(const FString& InRoot, int32 Keep);

private:
	FEcoV3WatchLauncher() = default;
	void CloseHandles();
	void RemovePidFile();

	void* Process = nullptr;   // HANDLE
	void* Job = nullptr;       // HANDLE (작업 개체 — 못 쓰면 nullptr)
	bool bJob = false;
	bool bRunning = false;
	bool bLaunched = false;
	const void* Owner = nullptr;
	int32 Pid = 0;
	double LaunchedUnix = 0.0;
	double CreateUnix = 0.0;
	EcoV3Watch::EEnd End = EcoV3Watch::EEnd::None;
	int32 ExitCode = 0;
	FString LogPath;
	FString Root;
	FString PlayId;
};
