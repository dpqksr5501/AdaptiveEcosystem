// 통합 v3 적응 고리 — 파이썬 감시 자동 시작 (EcoV3WatchLauncher.h 머리 주석 — 학습 파이프라인을 따로 띄우는 개발용 도구, 추론이 아니다).

#include "EcoV3WatchLauncher.h"

#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/Archive.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#include "EcoV3Brain.h"

#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#endif

// -----------------------------------------------------------------------------
// 순수 함수 (시험 EcoV3WatchLauncherTest.cpp)
// -----------------------------------------------------------------------------

namespace EcoV3WatchImpl
{
	/** 경로 정규화 (구분자 '/', '..' 접기, 끝 구분자 없앰). */
	FString Norm(const FString& In)
	{
		FString P = In.TrimStartAndEnd().TrimQuotes();
		FPaths::NormalizeFilename(P);
		FPaths::CollapseRelativeDirectories(P);
		while (P.Len() > 1 && P.EndsWith(TEXT("/")) && !P.EndsWith(TEXT(":/")))
		{
			P.LeftChopInline(1);
		}
		return P;
	}

	/** '\WindowsApps\' 아래 (스토어 대역 — 파이썬이 없으면 스토어 창을 띄운다). */
	bool IsStoreAlias(const FString& Path)
	{
		FString P = Path.Replace(TEXT("/"), TEXT("\\"));
		if (!P.EndsWith(TEXT("\\")))
		{
			P += TEXT("\\");
		}
		return P.Contains(TEXT("\\WindowsApps\\"), ESearchCase::IgnoreCase);
	}
}

FString EcoV3Watch::BuildArgs(const FString& Override, const FString& Root, const FString& PlayId, const FString& InLogFile)
{
	const FString Trimmed = Override.TrimStartAndEnd();
	if (Trimmed.IsEmpty())
	{
		return FString::Printf(TEXT("-X utf8 -u %s watch --root \"%s\""), kScriptRel, *Root);
	}
	return Trimmed.Replace(TEXT("{root}"), *Root).Replace(TEXT("{play}"), *PlayId).Replace(TEXT("{log}"), *InLogFile);
}

FString EcoV3Watch::ResolvePython(const FString& Setting, const FString& PathEnv, TFunctionRef<bool(const FString&)> FileExists, FString& OutWhy)
{
	using namespace EcoV3WatchImpl;
	OutWhy.Empty();
	FString Name = Setting.TrimStartAndEnd().TrimQuotes();
	if (Name.IsEmpty())
	{
		Name = TEXT("python");
	}
	if (Name.Contains(TEXT("/")) || Name.Contains(TEXT("\\")))
	{
		if (IsStoreAlias(FPaths::GetPath(Name)))
		{
			OutWhy = FString::Printf(TEXT("%s 는 WindowsApps 스토어 대역이라 쓰지 않는다"), *Name);
			return FString();
		}
		if (!FileExists(Name))
		{
			OutWhy = FString::Printf(TEXT("python 실행 파일 %s 가 없다 (eco.IntegratedV3.AutoWatchPython)"), *Name);
			return FString();
		}
		return Name;
	}
	const FString Exe = Name.EndsWith(TEXT(".exe"), ESearchCase::IgnoreCase) ? Name : Name + TEXT(".exe");
	TArray<FString> Dirs;
	PathEnv.ParseIntoArray(Dirs, TEXT(";"), /*InCullEmpty*/ true);
	int32 Store = 0;
	for (const FString& Raw : Dirs)
	{
		const FString Dir = Raw.TrimStartAndEnd().TrimQuotes();
		if (Dir.IsEmpty())
		{
			continue;
		}
		const FString Candidate = FPaths::Combine(Dir, Exe);
		if (IsStoreAlias(Dir))
		{
			Store += FileExists(Candidate) ? 1 : 0;
			continue;
		}
		if (FileExists(Candidate))
		{
			return Candidate.Replace(TEXT("/"), TEXT("\\"));
		}
	}
	OutWhy = FString::Printf(TEXT("PATH 에서 %s 를 찾지 못했다%s (eco.IntegratedV3.AutoWatchPython 에 전체 경로를 준다)"), *Exe,
							 Store > 0 ? *FString::Printf(TEXT(" — WindowsApps 스토어 대역 %d 개는 쓰지 않음"), Store) : TEXT(""));
	return FString();
}

bool EcoV3Watch::ParseLock(const FString& JsonText, FLock& Out)
{
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) || !Root.IsValid())
	{
		return false;
	}
	double Pid = 0.0;
	if (!Root->TryGetNumberField(TEXT("pid"), Pid) || !(Pid > 0.0))
	{
		return false;
	}
	FLock L;
	L.Pid = static_cast<int32>(Pid);
	L.bHasCreateTime = Root->TryGetNumberField(TEXT("create_time"), L.CreateTime) && FMath::IsFinite(L.CreateTime);
	Root->TryGetStringField(TEXT("what"), L.What);
	Root->TryGetStringField(TEXT("time"), L.Time);
	Out = L;
	return true;
}

FString EcoV3Watch::PidFileJson(const FPidFile& P)
{
	TSharedRef<FJsonObject> J = MakeShared<FJsonObject>();
	J->SetNumberField(TEXT("pid"), P.Pid);
	J->SetNumberField(TEXT("create_unix"), P.CreateUnix);
	J->SetStringField(TEXT("play_id"), P.PlayId);
	J->SetNumberField(TEXT("editor_pid"), P.EditorPid);
	J->SetStringField(TEXT("exe"), P.Exe);
	J->SetStringField(TEXT("args"), P.Args);
	J->SetStringField(TEXT("log"), P.Log);
	J->SetStringField(TEXT("started_utc"), P.StartedUtc);
	FString Text;
	const TSharedRef<TJsonWriter<>> W = TJsonWriterFactory<>::Create(&Text);
	FJsonSerializer::Serialize(J, W);
	return Text;
}

bool EcoV3Watch::ParsePidFile(const FString& JsonText, FPidFile& Out)
{
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) || !Root.IsValid())
	{
		return false;
	}
	double Pid = 0.0;
	if (!Root->TryGetNumberField(TEXT("pid"), Pid) || !(Pid > 0.0))
	{
		return false;
	}
	FPidFile P;
	P.Pid = static_cast<int32>(Pid);
	Root->TryGetNumberField(TEXT("create_unix"), P.CreateUnix);
	Root->TryGetStringField(TEXT("play_id"), P.PlayId);
	double Editor = 0.0;
	Root->TryGetNumberField(TEXT("editor_pid"), Editor);
	P.EditorPid = static_cast<int32>(Editor);
	Root->TryGetStringField(TEXT("exe"), P.Exe);
	Root->TryGetStringField(TEXT("args"), P.Args);
	Root->TryGetStringField(TEXT("log"), P.Log);
	Root->TryGetStringField(TEXT("started_utc"), P.StartedUtc);
	Out = P;
	return true;
}

EcoV3Watch::EEnd EcoV3Watch::ClassifyEnd(int32 ExitCode, const FString& LogTail)
{
	if (LogTail.Contains(TEXT("flight_sizes_confirmed")))
	{
		return EEnd::Locked;   // live.py plan_from_args: 실제 폴더인데 LIVE.flight_sizes_confirmed 거짓 (잠금·상태 파일을 쓰기 전에 끝남)
	}
	if (LogTail.Contains(TEXT("다른 실시간 고리")))
	{
		return EEnd::OtherLoop;   // live.py acquire_lock: 다른 고리가 폴더를 쓴다
	}
	return ExitCode != 0 ? EEnd::Failed : EEnd::Done;
}

FString EcoV3Watch::EndStatusText(EEnd Reason, int32 ExitCode, const FString& LogName, int32 OtherPid)
{
	switch (Reason)
	{
	case EEnd::Locked:
		return TEXT("적응 고리 | 파이썬 감시 꺼짐 — 실제 폴더 잠김 (관문 크기 확정 전)");
	case EEnd::OtherLoop:
		return OtherPid > 0 ? FString::Printf(TEXT("적응 고리 | 다른 감시가 돈다 (pid %d)"), OtherPid) : FString(TEXT("적응 고리 | 다른 감시가 돈다"));
	case EEnd::Failed:
		return FString::Printf(TEXT("적응 고리 | 파이썬 감시 꺼짐 — 종료 코드 %d (기록 %s)"), ExitCode, *LogName);
	case EEnd::Done:
		return TEXT("적응 고리 | 파이썬 감시 끝남");
	case EEnd::Stopped:
		return TEXT("적응 고리 | 파이썬 감시 끝냄 (Play 끝)");
	default:
		return FString();
	}
}

FString EcoV3Watch::EndNoticeText(EEnd Reason, const FString& LogName)
{
	switch (Reason)
	{
	case EEnd::Locked:
		return TEXT("파이썬 감시가 끝났다 — 실제 폴더 잠김 (관문 크기 확정 전). 두뇌는 그대로다");
	case EEnd::Failed:
		return FString::Printf(TEXT("파이썬 감시가 멈췄다 — 기록 %s"), *LogName);
	default:
		return FString();
	}
}

bool EcoV3Watch::SamePath(const FString& A, const FString& B)
{
	return EcoV3WatchImpl::Norm(A).Equals(EcoV3WatchImpl::Norm(B), ESearchCase::IgnoreCase);
}

FString EcoV3Watch::RootMismatch(const FString& Root, const FString& SnapshotDir, const FString& BrainDir, const FString& StatusFile)
{
	TArray<FString> Bad;
	const FString R = EcoV3WatchImpl::Norm(Root);
	if (!SamePath(SnapshotDir, R / TEXT("snapshots")))
	{
		Bad.Add(FString::Printf(TEXT("스냅숏 폴더 %s"), *SnapshotDir));
	}
	if (!SamePath(BrainDir, R / TEXT("brains")))
	{
		Bad.Add(FString::Printf(TEXT("두뇌 감시 폴더 %s"), BrainDir.IsEmpty() ? TEXT("(끔)") : *BrainDir));
	}
	if (!SamePath(StatusFile, R / TEXT("status.json")))
	{
		Bad.Add(FString::Printf(TEXT("상태 파일 %s"), StatusFile.IsEmpty() ? TEXT("(끔)") : *StatusFile));
	}
	return Bad.IsEmpty() ? FString() : FString::Printf(TEXT("%s 가 root %s 아래가 아니다"), *FString::Join(Bad, TEXT(" · ")), *R);
}

EcoV3Watch::EDecide EcoV3Watch::Decide(const FDecideIn& In)
{
	if (!In.bAutoWatch)
	{
		return EDecide::Off;
	}
	if (!In.bAutoAdapt)
	{
		return EDecide::NoAdapt;
	}
	if (In.bTesting)
	{
		return EDecide::Testing;
	}
	if (In.bClient)
	{
		return EDecide::Client;
	}
	if (!In.RootMismatch.IsEmpty())
	{
		return EDecide::Unsafe;
	}
	if (In.bOursAlive)
	{
		return EDecide::OursRunning;
	}
	if (In.bLockAlive)
	{
		return In.bLockIsOurs ? EDecide::OtherEditor : EDecide::HumanRunning;
	}
	if (In.bPidFileAlive)
	{
		return EDecide::OtherEditor;
	}
	if (!In.bPython)
	{
		return EDecide::NoPython;
	}
	if (!In.bScript)
	{
		return EDecide::NoScript;
	}
	return EDecide::Launch;
}

const TCHAR* EcoV3Watch::DecideName(EDecide D)
{
	switch (D)
	{
	case EDecide::Launch:		return TEXT("띄움");
	case EDecide::Off:			return TEXT("끔 (eco.IntegratedV3.AutoWatch 0)");
	case EDecide::NoAdapt:		return TEXT("끔 (eco.IntegratedV3.AutoAdapt 0)");
	case EDecide::Testing:		return TEXT("안 띄움 — 자동화 시험 중");
	case EDecide::Client:		return TEXT("안 띄움 — 클라이언트");
	case EDecide::Unsafe:		return TEXT("안 띄움 — 스냅숏·두뇌·상태 폴더가 한 root 아래가 아니다");
	case EDecide::OursRunning:	return TEXT("이 편집기가 띄운 감시가 돈다 — 그대로");
	case EDecide::HumanRunning:	return TEXT("이미 돈다 — 사람이 띄움, 건드리지 않음");
	case EDecide::OtherEditor:	return TEXT("이미 돈다 — 다른 언리얼 프로세스가 띄움");
	case EDecide::NoPython:		return TEXT("못 켬 — python 없음");
	case EDecide::NoScript:		return TEXT("못 켬 — live.py·작업 폴더 없음");
	case EDecide::LaunchFailed:	return TEXT("못 켬 — 띄우기 실패");
	default:					return TEXT("?");
	}
}

// -----------------------------------------------------------------------------
// 프로세스 (윈도)
// -----------------------------------------------------------------------------

FEcoV3WatchLauncher& FEcoV3WatchLauncher::Get()
{
	static FEcoV3WatchLauncher Instance;
	return Instance;
}

void FEcoV3WatchLauncher::ResetEnded()
{
	if (!bRunning && !Process)
	{
		bLaunched = false;
		End = EcoV3Watch::EEnd::None;
		ExitCode = 0;
		Owner = nullptr;
		Pid = 0;
	}
}

FString FEcoV3WatchLauncher::ReadTail(const FString& Path, int32 MaxBytes)
{
	TUniquePtr<FArchive> Reader(IFileManager::Get().CreateFileReader(*Path, FILEREAD_AllowWrite | FILEREAD_Silent));
	if (!Reader)
	{
		return FString();
	}
	const int64 Size = Reader->TotalSize();
	const int64 Start = FMath::Max<int64>(0, Size - FMath::Max(1, MaxBytes));
	TArray<uint8> Bytes;
	Bytes.SetNumUninitialized(static_cast<int32>(Size - Start));
	Reader->Seek(Start);
	Reader->Serialize(Bytes.GetData(), Bytes.Num());
	Reader->Close();
	FString Out;
	FFileHelper::BufferToString(Out, Bytes.GetData(), Bytes.Num());   // UTF-8 (BOM 이 있으면 건너뜀)
	return Out;
}

void FEcoV3WatchLauncher::PruneLogs(const FString& InRoot, int32 Keep)
{
	TArray<FString> Names;
	IFileManager::Get().FindFiles(Names, *(InRoot / TEXT("watch_*.log")), /*Files*/ true, /*Directories*/ false);
	if (Names.Num() <= Keep)
	{
		return;
	}
	TArray<TPair<FDateTime, FString>> ByTime;
	for (const FString& N : Names)
	{
		const FString P = InRoot / N;
		ByTime.Emplace(IFileManager::Get().GetTimeStamp(*P), P);
	}
	ByTime.Sort([](const TPair<FDateTime, FString>& A, const TPair<FDateTime, FString>& B) { return A.Key > B.Key || (A.Key == B.Key && A.Value > B.Value); });
	for (int32 i = FMath::Max(0, Keep); i < ByTime.Num(); ++i)
	{
		IFileManager::Get().Delete(*ByTime[i].Value, /*RequireExists*/ false, /*EvenReadOnly*/ true, /*Quiet*/ true);
	}
}

void FEcoV3WatchLauncher::RemovePidFile()
{
	const FString Path = Root / TEXT("watcher.pid");
	FString Text;
	EcoV3Watch::FPidFile P;
	if (FFileHelper::LoadFileToString(Text, *Path) && EcoV3Watch::ParsePidFile(Text, P) && P.Pid == Pid)
	{
		IFileManager::Get().Delete(*Path, false, true, true);
	}
}

#if PLATFORM_WINDOWS
#include "Windows/AllowWindowsPlatformTypes.h"

namespace EcoV3WatchImpl
{
	double FileTimeToUnix(const FILETIME& Ft)
	{
		const uint64 Ticks = (static_cast<uint64>(Ft.dwHighDateTime) << 32) | static_cast<uint64>(Ft.dwLowDateTime);
		return static_cast<double>(Ticks) / 1.0e7 - 11644473600.0;
	}
}

bool FEcoV3WatchLauncher::ProcessCreateUnix(int32 InPid, double& OutUnix)
{
	HANDLE H = ::OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, static_cast<DWORD>(InPid));
	if (!H)
	{
		return false;
	}
	FILETIME C, E, K, U;
	const bool bOk = ::GetProcessTimes(H, &C, &E, &K, &U) != 0;
	if (bOk)
	{
		OutUnix = EcoV3WatchImpl::FileTimeToUnix(C);
	}
	::CloseHandle(H);
	return bOk;
}

bool FEcoV3WatchLauncher::IsProcessAlive(int32 InPid, double InCreateUnix, bool bRequirePython, FString* OutImage)
{
	if (InPid <= 0)
	{
		return false;
	}
	HANDLE H = ::OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, static_cast<DWORD>(InPid));
	if (!H)
	{
		return false;
	}
	bool bAlive = false;
	DWORD Code = 0;
	if (::GetExitCodeProcess(H, &Code) && Code == STILL_ACTIVE)
	{
		bAlive = true;
		FILETIME C, E, K, U;
		if (InCreateUnix >= 0.0 && ::GetProcessTimes(H, &C, &E, &K, &U))
		{
			bAlive = FMath::Abs(EcoV3WatchImpl::FileTimeToUnix(C) - InCreateUnix) <= EcoV3Watch::kCreateTolerance;
		}
		WCHAR Image[1024];
		DWORD Len = UE_ARRAY_COUNT(Image);
		const FString ImagePath = ::QueryFullProcessImageNameW(H, 0, Image, &Len) ? FString(Image) : FString();
		if (OutImage)
		{
			*OutImage = ImagePath;
		}
		if (bAlive && bRequirePython)
		{
			bAlive = FPaths::GetCleanFilename(ImagePath).StartsWith(TEXT("python"), ESearchCase::IgnoreCase);
		}
	}
	::CloseHandle(H);
	return bAlive;
}

bool FEcoV3WatchLauncher::Launch(const FString& Exe, const FString& Args, const FString& WorkDir, const FString& InLogPath, const FString& InRoot,
								 const FString& InPlayId, const void* InOwner, FString& OutWhy)
{
	if (bRunning)
	{
		OutWhy = FString::Printf(TEXT("이 편집기가 띄운 감시(pid %d)가 아직 돈다"), Pid);
		return false;
	}
	CloseHandles();
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(InLogPath), /*Tree*/ true);
	SECURITY_ATTRIBUTES Sa;
	Sa.nLength = sizeof(Sa);
	Sa.lpSecurityDescriptor = nullptr;
	Sa.bInheritHandle = TRUE;
	// 기록 파일 (읽기·쓰기·지우기 공유 — 언리얼이 끝 줄을 읽는다). 파이프는 쓰지 않는다: 언리얼이 비우지 않으면(중단점·긴 프레임) 파이썬이 print 에서 멈춘다
	HANDLE Log = ::CreateFileW(*InLogPath, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, &Sa, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
	if (Log == INVALID_HANDLE_VALUE)
	{
		OutWhy = FString::Printf(TEXT("기록 파일 %s 를 못 열었다 (오류 %u)"), *InLogPath, static_cast<uint32>(::GetLastError()));
		return false;
	}
	HANDLE Nul = ::CreateFileW(TEXT("NUL"), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &Sa, OPEN_EXISTING, 0, nullptr);
	if (Nul == INVALID_HANDLE_VALUE)
	{
		::CloseHandle(Log);
		OutWhy = FString::Printf(TEXT("NUL 을 못 열었다 (오류 %u)"), static_cast<uint32>(::GetLastError()));
		return false;
	}
	// 물려줄 손잡이는 기록·NUL 둘뿐 (편집기의 다른 상속 가능 손잡이를 넘기지 않는다)
	SIZE_T AttrSize = 0;
	::InitializeProcThreadAttributeList(nullptr, 1, 0, &AttrSize);
	TArray<uint8> AttrBuf;
	AttrBuf.SetNumZeroed(static_cast<int32>(AttrSize));
	LPPROC_THREAD_ATTRIBUTE_LIST Attr = reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(AttrBuf.GetData());
	HANDLE Inherit[2] = {Log, Nul};
	const bool bAttr = ::InitializeProcThreadAttributeList(Attr, 1, 0, &AttrSize)
					   && ::UpdateProcThreadAttribute(Attr, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST, Inherit, sizeof(Inherit), nullptr, nullptr);
	STARTUPINFOEXW Si;
	FMemory::Memzero(&Si, sizeof(Si));
	Si.StartupInfo.cb = sizeof(Si);
	Si.StartupInfo.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
	Si.StartupInfo.wShowWindow = SW_HIDE;
	Si.StartupInfo.hStdInput = Nul;
	Si.StartupInfo.hStdOutput = Log;
	Si.StartupInfo.hStdError = Log;
	Si.lpAttributeList = bAttr ? Attr : nullptr;
	FString CmdLine = FString::Printf(TEXT("\"%s\" %s"), *Exe, *Args);
	TArray<TCHAR> CmdBuf(*CmdLine, CmdLine.Len() + 1);
	PROCESS_INFORMATION Pi;
	FMemory::Memzero(&Pi, sizeof(Pi));
	// 창 없음 (숨은 콘솔 — 판·학습 자식도 물려받는다), 멈춘 채 만들어 작업 개체에 넣은 뒤 깨운다
	const DWORD Flags = CREATE_NO_WINDOW | CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | (bAttr ? EXTENDED_STARTUPINFO_PRESENT : 0);
	const BOOL bCreated = ::CreateProcessW(*Exe, CmdBuf.GetData(), nullptr, nullptr, TRUE, Flags, nullptr, WorkDir.IsEmpty() ? nullptr : *WorkDir,
										   &Si.StartupInfo, &Pi);
	const uint32 CreateError = bCreated ? 0u : static_cast<uint32>(::GetLastError());
	if (bAttr)
	{
		::DeleteProcThreadAttributeList(Attr);
	}
	::CloseHandle(Log);
	::CloseHandle(Nul);
	if (!bCreated)
	{
		OutWhy = FString::Printf(TEXT("CreateProcess 실패 (오류 %u — %s)"), CreateError, *Exe);
		return false;
	}
	// 작업 개체: 감시가 띄우는 판·학습 프로세스도 물려받는다 (live.py 는 CREATE_NEW_PROCESS_GROUP 만 쓰고 떼어 나가지 않는다). 편집기가 죽으면 손잡이가 닫히며 나무째 끝난다
	HANDLE JobH = ::CreateJobObjectW(nullptr, nullptr);
	bool bJobOk = false;
	if (JobH)
	{
		JOBOBJECT_EXTENDED_LIMIT_INFORMATION Info;
		FMemory::Memzero(&Info, sizeof(Info));
		Info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
		bJobOk = ::SetInformationJobObject(JobH, JobObjectExtendedLimitInformation, &Info, sizeof(Info)) && ::AssignProcessToJobObject(JobH, Pi.hProcess);
		if (!bJobOk)
		{
			::CloseHandle(JobH);
			JobH = nullptr;
		}
	}
	::ResumeThread(Pi.hThread);
	::CloseHandle(Pi.hThread);

	Process = Pi.hProcess;
	Job = JobH;
	bJob = bJobOk;
	bRunning = true;
	bLaunched = true;
	Owner = InOwner;
	Pid = static_cast<int32>(Pi.dwProcessId);
	LaunchedUnix = EcoV3Brain::NowUnixSeconds();
	CreateUnix = LaunchedUnix;
	{
		FILETIME C, E, K, U;
		if (::GetProcessTimes(Pi.hProcess, &C, &E, &K, &U))
		{
			CreateUnix = EcoV3WatchImpl::FileTimeToUnix(C);
		}
	}
	End = EcoV3Watch::EEnd::None;
	ExitCode = 0;
	LogPath = InLogPath;
	Root = InRoot;
	PlayId = InPlayId;
	// 우리 기록 (다른 언리얼 프로세스가 같은 root 에 또 띄우지 않게 — 잠금을 잡기 전 토치를 불러오는 몇 초)
	EcoV3Watch::FPidFile P;
	P.Pid = Pid;
	P.CreateUnix = CreateUnix;
	P.PlayId = PlayId;
	P.EditorPid = static_cast<int32>(FPlatformProcess::GetCurrentProcessId());
	P.Exe = Exe;
	P.Args = Args;
	P.Log = LogPath;
	P.StartedUtc = FDateTime::UtcNow().ToIso8601();
	FFileHelper::SaveStringToFile(EcoV3Watch::PidFileJson(P), *(Root / TEXT("watcher.pid")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	return true;
}

bool FEcoV3WatchLauncher::Poll()
{
	if (!bRunning || !Process)
	{
		return false;
	}
	if (::WaitForSingleObject(static_cast<HANDLE>(Process), 0) != WAIT_OBJECT_0)
	{
		return false;
	}
	DWORD Code = 0;
	::GetExitCodeProcess(static_cast<HANDLE>(Process), &Code);
	ExitCode = static_cast<int32>(Code);
	End = EcoV3Watch::ClassifyEnd(ExitCode, ReadTail(LogPath, 4096));
	bRunning = false;
	CloseHandles();   // 작업 개체를 닫으면 남은 자식도 끝난다 (KILL_ON_JOB_CLOSE)
	RemovePidFile();
	return true;
}

bool FEcoV3WatchLauncher::Stop(const void* InOwner, const TCHAR* Why)
{
	if (!bRunning || !Process || InOwner != Owner)
	{
		return false;
	}
	if (Job)
	{
		::TerminateJobObject(static_cast<HANDLE>(Job), 1);   // 부모가 먼저 죽어 끊긴 손자까지
	}
	else
	{
		FProcHandle H(static_cast<HANDLE>(Process));
		FPlatformProcess::TerminateProc(H, /*KillTree*/ true);
	}
	::WaitForSingleObject(static_cast<HANDLE>(Process), EcoV3Watch::kStopWaitMs);
	DWORD Code = 0;
	::GetExitCodeProcess(static_cast<HANDLE>(Process), &Code);
	ExitCode = static_cast<int32>(Code);
	End = EcoV3Watch::EEnd::Stopped;
	bRunning = false;
	CloseHandles();
	RemovePidFile();
	return true;
}

void FEcoV3WatchLauncher::CloseHandles()
{
	if (Process)
	{
		::CloseHandle(static_cast<HANDLE>(Process));
		Process = nullptr;
	}
	if (Job)
	{
		::CloseHandle(static_cast<HANDLE>(Job));
		Job = nullptr;
	}
}

#include "Windows/HideWindowsPlatformTypes.h"
#else

bool FEcoV3WatchLauncher::ProcessCreateUnix(int32 InPid, double& OutUnix)
{
	return false;
}

bool FEcoV3WatchLauncher::IsProcessAlive(int32 InPid, double InCreateUnix, bool bRequirePython, FString* OutImage)
{
	return false;
}

bool FEcoV3WatchLauncher::Launch(const FString& Exe, const FString& Args, const FString& WorkDir, const FString& InLogPath, const FString& InRoot,
								 const FString& InPlayId, const void* InOwner, FString& OutWhy)
{
	OutWhy = TEXT("이 플랫폼에서는 못 띄움 (윈도만)");
	return false;
}

bool FEcoV3WatchLauncher::Poll()
{
	return false;
}

bool FEcoV3WatchLauncher::Stop(const void* InOwner, const TCHAR* Why)
{
	return false;
}

void FEcoV3WatchLauncher::CloseHandles()
{
	Process = nullptr;
	Job = nullptr;
}

#endif
