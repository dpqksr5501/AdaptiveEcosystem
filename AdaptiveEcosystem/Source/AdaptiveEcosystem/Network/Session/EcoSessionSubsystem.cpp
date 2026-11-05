#include "Network/Session/EcoSessionSubsystem.h"
#include "Network/Session/EcoSessionMenuWidget.h"
#include "Network/Session/EcoSessionPolicy.h"
#include "Network/Session/EcoSessionSettings.h"
#include "Network/EcoGameState.h"
#include "OnlineSubsystem.h"
#include "OnlineSubsystemUtils.h"
#include "OnlineSubsystemNames.h"
#include "Online/OnlineSessionNames.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "HAL/IConsoleManager.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/PackageName.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/Package.h"
#include "InputCoreTypes.h"

DEFINE_LOG_CATEGORY_STATIC(LogEcoSession, Log, All);

namespace EcoSession
{
    const FName TagKey(TEXT("ECO_PROJECT")), ProtocolKey(TEXT("ECO_PROTOCOL")), RoomKey(TEXT("ECO_ROOM"));
    UEcoSessionSubsystem* FromWorld(UWorld* World)
    {
        return World && World->GetGameInstance() ? World->GetGameInstance()->GetSubsystem<UEcoSessionSubsystem>() : nullptr;
    }
    FString JoinOptions()
    {
        return FString::Printf(TEXT("?EcoProtocol=%d"), EcoSessionPolicy::ProtocolVersion);
    }
    FAutoConsoleCommandWithWorldAndArgs Host(TEXT("eco.Session.Host"), TEXT("Host <room name> [lan]."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& A, UWorld* W)
        { if (auto* S=FromWorld(W)) S->HostSession(A.IsEmpty()?TEXT("Adaptive Ecosystem"):A[0], A.Contains(TEXT("lan"))); }));
    FAutoConsoleCommandWithWorldAndArgs Find(TEXT("eco.Session.Find"), TEXT("Find [lan]."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& A, UWorld* W)
        { if (auto* S=FromWorld(W)) S->FindSessions(A.Contains(TEXT("lan"))); }));
    FAutoConsoleCommandWithWorldAndArgs Join(TEXT("eco.Session.Join"), TEXT("Join <result index> <search revision>."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& A, UWorld* W)
        { if (auto* S=FromWorld(W); S && A.Num()==2) S->JoinSession(FCString::Atoi(*A[0]), FCString::Atoi(*A[1])); }));
    FAutoConsoleCommandWithWorldAndArgs Leave(TEXT("eco.Session.Leave"), TEXT("Leave and return to the JWJ map."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* W)
        { if (auto* S=FromWorld(W)) S->LeaveSession(); }));
    FAutoConsoleCommandWithWorldAndArgs Menu(TEXT("eco.Session.Menu"), TEXT("Show session menu (F10)."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* W)
        { if (auto* S=FromWorld(W)) S->ShowSessionMenu(); }));
    FAutoConsoleCommandWithWorldAndArgs Dump(TEXT("eco.Session.Dump"), TEXT("Read-only session/authority diagnostics."),
        FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* W)
        { if (auto* S=FromWorld(W)) S->DumpRuntime(); }));
}

UWorld* UEcoSessionSubsystem::GetWorld() const
{
    return GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
}

void UEcoSessionSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    Status = TEXT("방을 만들거나 목록을 검색하세요. F10: 접속 메뉴");
    PostLoadHandle = FCoreUObjectDelegates::PostLoadMapWithWorld.AddUObject(this, &ThisClass::MapLoaded);
    if (GEngine)
    {
        NetworkFailureHandle = GEngine->OnNetworkFailure().AddUObject(this, &ThisClass::NetworkFailed);
        TravelFailureHandle = GEngine->OnTravelFailure().AddUObject(this, &ThisClass::TravelFailed);
    }
    TickerHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateUObject(this, &ThisClass::Tick));
}

void UEcoSessionSubsystem::ClearOperationDelegates()
{
    if (Sessions.IsValid())
    {
        Sessions->ClearOnCreateSessionCompleteDelegate_Handle(CreateHandle);
        Sessions->ClearOnStartSessionCompleteDelegate_Handle(StartHandle);
        Sessions->ClearOnFindSessionsCompleteDelegate_Handle(FindHandle);
        Sessions->ClearOnCancelFindSessionsCompleteDelegate_Handle(CancelFindHandle);
        Sessions->ClearOnJoinSessionCompleteDelegate_Handle(JoinHandle);
        Sessions->ClearOnDestroySessionCompleteDelegate_Handle(DestroyHandle);
    }
    CreateHandle.Reset(); StartHandle.Reset(); FindHandle.Reset(); CancelFindHandle.Reset();
    JoinHandle.Reset(); DestroyHandle.Reset();
    Deadline=0;
}

void UEcoSessionSubsystem::Deinitialize()
{
    FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
    FCoreUObjectDelegates::PostLoadMapWithWorld.Remove(PostLoadHandle);
    if (GEngine)
    {
        GEngine->OnNetworkFailure().Remove(NetworkFailureHandle);
        GEngine->OnTravelFailure().Remove(TravelFailureHandle);
    }
    ClearOperationDelegates();
    if (Sessions.IsValid())
    {
        Sessions->ClearOnSessionUserInviteAcceptedDelegate_Handle(InviteHandle);
        if (Sessions->GetNamedSession(NAME_GameSession)) Sessions->DestroySession(NAME_GameSession);
    }
    CloseSessionMenu();
    Search.Reset(); SearchResults.Reset(); Sessions.Reset();
    Super::Deinitialize();
}

bool UEcoSessionSubsystem::IsBusy() const
{
    return State==EEcoSessionState::Creating || State==EEcoSessionState::Starting ||
        State==EEcoSessionState::Searching || State==EEcoSessionState::Joining ||
        State==EEcoSessionState::Travelling || State==EEcoSessionState::Leaving;
}

FString UEcoSessionSubsystem::GetProviderName() const
{
    IOnlineSubsystem* Provider = Online::GetSubsystem(GetWorld(), bUsingLAN ? NULL_SUBSYSTEM : NAME_None);
    return Provider ? Provider->GetSubsystemName().ToString() : TEXT("Unavailable");
}

void UEcoSessionSubsystem::SetState(EEcoSessionState Next, const FString& Message)
{
    State=Next; Status=Message;
    UE_LOG(LogEcoSession, Log, TEXT("[EcoSession] State=%d Provider=%s Message=%s"), int32(State), *GetProviderName(), *Status);
    OnUpdated.Broadcast();
}

void UEcoSessionSubsystem::BeginOperation(EEcoSessionState Next, const FString& Message)
{
    ClearOperationDelegates();
    ++OperationGeneration; bTimedOut=false;
    Deadline=FPlatformTime::Seconds()+FMath::Clamp(GetDefault<UEcoSessionSettings>()->OperationTimeoutSeconds, 10.f, 180.f);
    SetState(Next, Message);
}

bool UEcoSessionSubsystem::Prepare(bool bLAN)
{
    if (IsBusy()) return false;
    UWorld* World=GetWorld();
    if (!World || !World->IsGameWorld() || World->GetNetMode()!=NM_Standalone)
    { Fail(TEXT("먼저 현재 방에서 나가세요.")); return false; }
    if (!World->GetFirstLocalPlayerFromController())
    { Fail(TEXT("로컬 플레이어가 준비되지 않았습니다.")); return false; }
    if (Sessions.IsValid() && Sessions->GetNamedSession(NAME_GameSession))
    { Fail(TEXT("기존 방 연결을 먼저 종료하세요.")); return false; }
    ClearOperationDelegates();
    if (Sessions.IsValid()) Sessions->ClearOnSessionUserInviteAcceptedDelegate_Handle(InviteHandle);
    Sessions.Reset(); InviteHandle.Reset();
    bUsingLAN=bLAN;
    IOnlineSubsystem* Provider=Online::GetSubsystem(World, bLAN ? NULL_SUBSYSTEM : NAME_None);
    if (!Provider || (!bLAN && Provider->GetSubsystemName()!=STEAM_SUBSYSTEM))
    { Fail(TEXT("Steam 연결이 없습니다. Steam 실행·로그인과 App ID 설정을 확인하세요.")); return false; }
    if (bLAN)
    {
        const IOnlineSubsystem* DefaultProvider=Online::GetSubsystem(World);
        if (DefaultProvider && DefaultProvider->GetSubsystemName()==STEAM_SUBSYSTEM)
        { Fail(TEXT("로컬망 시험은 게임을 -nosteam 옵션으로 다시 실행하세요. 현재는 Steam 통신을 사용 중입니다.")); return false; }
    }
    Sessions=Provider->GetSessionInterface();
    if (!Sessions.IsValid()) { Fail(TEXT("이 환경에서 방 기능을 사용할 수 없습니다.")); return false; }
    InviteHandle=Sessions->AddOnSessionUserInviteAcceptedDelegate_Handle(
        FOnSessionUserInviteAcceptedDelegate::CreateWeakLambda(this,
            [this](bool bSuccess, int32, FUniqueNetIdPtr, const FOnlineSessionSearchResult& Result)
            { if (bSuccess && !IsBusy() && State!=EEcoSessionState::InSession) StartJoin(Result); }));
    return true;
}

bool UEcoSessionSubsystem::HostSession(FString RoomName, bool bLAN)
{
    if (!Prepare(bLAN)) return false;
    const auto* Settings=GetDefault<UEcoSessionSettings>();
    if (!FPackageName::IsValidLongPackageName(Settings->GameplayMap) || !FPackageName::DoesPackageExist(Settings->GameplayMap))
    { Fail(TEXT("설정한 JWJ 레벨을 찾지 못했습니다.")); return false; }
    PendingRoomName=EcoSessionPolicy::RoomName(MoveTemp(RoomName));
    bHosted=true;
    FOnlineSessionSettings Options;
    Options.NumPublicConnections=Settings->TotalPlayers(false);
    Options.NumPrivateConnections=0;
    Options.bShouldAdvertise=true;
    Options.bAllowJoinInProgress=true;
    Options.bIsLANMatch=bLAN;
    Options.bUsesPresence=!bLAN;
    Options.bUseLobbiesIfAvailable=!bLAN;
    Options.bAllowJoinViaPresence=!bLAN;
    Options.bAllowInvites=!bLAN;
    // Keep the engine build ID: Null discovery rejects packets with a different build ID.
    // Our application protocol is independently advertised below.
    Options.Set(EcoSession::TagKey, Settings->DiscoveryTag, EOnlineDataAdvertisementType::ViaOnlineServiceAndPing);
    Options.Set(EcoSession::ProtocolKey, EcoSessionPolicy::ProtocolVersion, EOnlineDataAdvertisementType::ViaOnlineServiceAndPing);
    Options.Set(EcoSession::RoomKey, PendingRoomName, EOnlineDataAdvertisementType::ViaOnlineServiceAndPing);
    Options.Set(SETTING_MAPNAME, Settings->GameplayMap, EOnlineDataAdvertisementType::ViaOnlineServiceAndPing);
    BeginOperation(EEcoSessionState::Creating, TEXT("방을 만드는 중입니다."));
    const int32 Generation=OperationGeneration;
    CreateHandle=Sessions->AddOnCreateSessionCompleteDelegate_Handle(FOnCreateSessionCompleteDelegate::CreateWeakLambda(this,
        [this,Generation](FName N,bool S){if(Generation==OperationGeneration) Created(N,S);}));
    if (!Sessions->CreateSession(0, NAME_GameSession, Options)) { Fail(TEXT("방 생성 요청을 시작하지 못했습니다."), true); return false; }
    return true;
}

void UEcoSessionSubsystem::Created(FName Name, bool bSuccess)
{
    if (Name!=NAME_GameSession || State!=EEcoSessionState::Creating) return;
    if (!bSuccess || bTimedOut) { Fail(bTimedOut?TEXT("방 생성 시간이 초과됐습니다."):TEXT("방 생성에 실패했습니다."), true); return; }
    BeginOperation(EEcoSessionState::Starting, TEXT("방을 열고 있습니다."));
    const int32 Generation=OperationGeneration;
    StartHandle=Sessions->AddOnStartSessionCompleteDelegate_Handle(FOnStartSessionCompleteDelegate::CreateWeakLambda(this,
        [this,Generation](FName N,bool S){if(Generation==OperationGeneration) Started(N,S);}));
    if (!Sessions->StartSession(Name)) Fail(TEXT("방 시작 요청에 실패했습니다."), true);
}

void UEcoSessionSubsystem::Started(FName Name, bool bSuccess)
{
    if (Name!=NAME_GameSession || State!=EEcoSessionState::Starting) return;
    if (!bSuccess || bTimedOut) { Fail(TEXT("방 시작에 실패했거나 시간이 초과됐습니다."), true); return; }
    const auto* Settings=GetDefault<UEcoSessionSettings>();
    BeginOperation(EEcoSessionState::Travelling, TEXT("JWJ 레벨로 이동 중입니다."));
    CloseSessionMenu();
    TravelStartedAt=FPlatformTime::Seconds();
    const FString Options=FString::Printf(TEXT("listen?EcoSession=1?EcoProtocol=%d?MaxPlayers=%d%s"),
        EcoSessionPolicy::ProtocolVersion, Settings->TotalPlayers(false), bUsingLAN?TEXT("?bIsLanMatch=1"):TEXT(""));
    UGameplayStatics::OpenLevel(this, FName(*Settings->GameplayMap), true, Options);
}

bool UEcoSessionSubsystem::FindSessions(bool bLAN)
{
    if (!Prepare(bLAN)) return false;
    Search=MakeShared<FOnlineSessionSearch>();
    Search->bIsLanQuery=bLAN;
    Search->MaxSearchResults=FMath::Clamp(GetDefault<UEcoSessionSettings>()->MaxSearchResults,1,200);
    Search->TimeoutInSeconds=GetDefault<UEcoSessionSettings>()->OperationTimeoutSeconds;
    if (!bLAN) Search->QuerySettings.Set(SEARCH_LOBBIES, true, EOnlineComparisonOp::Equals);
    Search->QuerySettings.Set(EcoSession::TagKey, GetDefault<UEcoSessionSettings>()->DiscoveryTag, EOnlineComparisonOp::Equals);
    Results.Reset(); SearchResults.Reset(); ++SearchRevision;
    BeginOperation(EEcoSessionState::Searching, TEXT("방을 검색 중입니다."));
    const int32 Generation=OperationGeneration;
    FindHandle=Sessions->AddOnFindSessionsCompleteDelegate_Handle(FOnFindSessionsCompleteDelegate::CreateWeakLambda(this,
        [this,Generation](bool S){if(Generation==OperationGeneration) Found(S);}));
    if (!Sessions->FindSessions(0, Search.ToSharedRef())) { Fail(TEXT("방 검색을 시작하지 못했습니다.")); return false; }
    return true;
}

void UEcoSessionSubsystem::Found(bool bSuccess)
{
    if (State!=EEcoSessionState::Searching) return;
    if (!bSuccess || bTimedOut || !Search.IsValid()) { Fail(TEXT("검색에 실패했거나 시간이 초과됐습니다.")); return; }
    const auto* Settings=GetDefault<UEcoSessionSettings>();
    for (const auto& Candidate:Search->SearchResults)
    {
        FString Tag, Map, Room; int32 Protocol=-1;
        Candidate.Session.SessionSettings.Get(EcoSession::TagKey,Tag);
        Candidate.Session.SessionSettings.Get(EcoSession::ProtocolKey,Protocol);
        Candidate.Session.SessionSettings.Get(SETTING_MAPNAME,Map);
        Candidate.Session.SessionSettings.Get(EcoSession::RoomKey,Room);
        if (Tag!=Settings->DiscoveryTag) continue; // App ID 480 may contain unrelated games.
        auto& Entry=Results.AddDefaulted_GetRef();
        Entry.Name=EcoSessionPolicy::RoomName(Room); Entry.Host=Candidate.Session.OwningUserName;
        Entry.Capacity=Candidate.Session.SessionSettings.NumPublicConnections;
        Entry.Players=FMath::Max(0,Entry.Capacity-Candidate.Session.NumOpenPublicConnections);
        Entry.PingMs=Candidate.PingInMs; Entry.SearchRevision=SearchRevision;
        Entry.bCompatible=EcoSessionPolicy::IsCompatible(Tag,Protocol,Map,Settings->DiscoveryTag,Settings->GameplayMap);
        SearchResults.Add(Candidate);
    }
    ClearOperationDelegates();
    SetState(EEcoSessionState::Idle,FString::Printf(TEXT("검색된 방: %d개"),Results.Num()));
    if (FParse::Param(FCommandLine::Get(),TEXT("EcoSessionAutoJoin")) && !Results.IsEmpty()) JoinSession(0,SearchRevision);
}

bool UEcoSessionSubsystem::JoinSession(int32 Index, int32 ExpectedSearchRevision)
{
    if (IsBusy()) return false;
    if (ExpectedSearchRevision!=SearchRevision || !Results.IsValidIndex(Index) || !SearchResults.IsValidIndex(Index))
    { Fail(TEXT("검색 결과가 바뀌었습니다. 다시 검색한 뒤 선택하세요.")); return false; }
    if (!Results[Index].bCompatible) { Fail(TEXT("다른 버전 또는 다른 레벨의 방입니다.")); return false; }
    if (SearchResults[Index].Session.NumOpenPublicConnections<=0) { Fail(TEXT("방이 가득 찼습니다.")); return false; }
    return StartJoin(SearchResults[Index]);
}

bool UEcoSessionSubsystem::StartJoin(const FOnlineSessionSearchResult& Result)
{
    UWorld* World=GetWorld();
    if (!World || World->GetNetMode()!=NM_Standalone || !Sessions.IsValid() || Sessions->GetNamedSession(NAME_GameSession)) return false;
    FString Tag,Map; int32 Protocol=-1;
    Result.Session.SessionSettings.Get(EcoSession::TagKey,Tag);
    Result.Session.SessionSettings.Get(EcoSession::ProtocolKey,Protocol);
    Result.Session.SessionSettings.Get(SETTING_MAPNAME,Map);
    const auto* Settings=GetDefault<UEcoSessionSettings>();
    if (!EcoSessionPolicy::IsCompatible(Tag,Protocol,Map,Settings->DiscoveryTag,Settings->GameplayMap))
    { Fail(TEXT("참가할 방의 게임 버전과 레벨이 맞지 않습니다.")); return false; }
    FOnlineSessionSearchResult Candidate=Result;
    Candidate.Session.SessionSettings.bUsesPresence=!bUsingLAN;
    Candidate.Session.SessionSettings.bUseLobbiesIfAvailable=!bUsingLAN;
    bHosted=false;
    BeginOperation(EEcoSessionState::Joining,TEXT("선택한 방에 참가 중입니다."));
    const int32 Generation=OperationGeneration;
    JoinHandle=Sessions->AddOnJoinSessionCompleteDelegate_Handle(FOnJoinSessionCompleteDelegate::CreateWeakLambda(this,
        [this,Generation](FName N,EOnJoinSessionCompleteResult::Type R){if(Generation==OperationGeneration) Joined(N,R);}));
    if (!Sessions->JoinSession(0,NAME_GameSession,Candidate)) { Fail(TEXT("참가 요청을 시작하지 못했습니다."),true); return false; }
    return true;
}

void UEcoSessionSubsystem::Joined(FName Name,EOnJoinSessionCompleteResult::Type Result)
{
    if (Name!=NAME_GameSession || State!=EEcoSessionState::Joining) return;
    FString Address;
    if (Result!=EOnJoinSessionCompleteResult::Success || bTimedOut || !Sessions->GetResolvedConnectString(Name,Address))
    { Fail(FString::Printf(TEXT("방 참가 실패: %s"),LexToString(Result)),true); return; }
    APlayerController* PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;
    if (!PC) { Fail(TEXT("참가할 플레이어가 없습니다."),true); return; }
    BeginOperation(EEcoSessionState::Travelling,TEXT("서버에 연결 중입니다."));
    CloseSessionMenu(); TravelStartedAt=FPlatformTime::Seconds();
    PC->ClientTravel(Address+EcoSession::JoinOptions(),TRAVEL_Absolute);
}

void UEcoSessionSubsystem::Fail(const FString& Message,bool bCleanup)
{
    ClearOperationDelegates();
    if (bCleanup && Sessions.IsValid() && Sessions->GetNamedSession(NAME_GameSession))
    { DestroyLocalSession(false,Message); return; }
    SetState(EEcoSessionState::Error,Message);
}

void UEcoSessionSubsystem::DestroyLocalSession(bool bReturnToMap,const FString& Failure)
{
    bReturnAfterDestroy=bReturnToMap; FailureAfterDestroy=Failure;
    if (!Sessions.IsValid() || !Sessions->GetNamedSession(NAME_GameSession)) { Destroyed(NAME_GameSession,true); return; }
    BeginOperation(EEcoSessionState::Leaving,TEXT("방 연결을 정리 중입니다."));
    const int32 Generation=OperationGeneration;
    DestroyHandle=Sessions->AddOnDestroySessionCompleteDelegate_Handle(FOnDestroySessionCompleteDelegate::CreateWeakLambda(this,
        [this,Generation](FName N,bool S){if(Generation==OperationGeneration) Destroyed(N,S);}));
    if (!Sessions->DestroySession(NAME_GameSession)) Destroyed(NAME_GameSession,false);
}

void UEcoSessionSubsystem::Destroyed(FName Name,bool bSuccess)
{
    if (Name!=NAME_GameSession) return;
    ClearOperationDelegates(); bHosted=false;
    if (!bSuccess) { SetState(EEcoSessionState::Error,TEXT("기존 방 정리에 실패했습니다. 나가기를 다시 시도하세요.")); return; }
    const FString Failure=MoveTemp(FailureAfterDestroy);
    const bool bReturn=bReturnAfterDestroy; bReturnAfterDestroy=false;
    SetState(Failure.IsEmpty()?EEcoSessionState::Idle:EEcoSessionState::Error,
        Failure.IsEmpty()?TEXT("방에서 나왔습니다."):Failure);
    if (bReturn && GetWorld())
    {
        CloseSessionMenu(); bAutoMenuDone=false;
        UGameplayStatics::OpenLevel(this,FName(*GetDefault<UEcoSessionSettings>()->GameplayMap),true);
    }
}

void UEcoSessionSubsystem::LeaveSession()
{
    if (IsBusy()) return;
    DestroyLocalSession(true);
}

void UEcoSessionSubsystem::MapLoaded(UWorld* World)
{
    if (!World || World->GetGameInstance()!=GetGameInstance()) return;
    Menu=nullptr; MenuController.Reset();
    if (State==EEcoSessionState::Travelling)
    {
        ClearOperationDelegates();
        SessionEnteredAt=FPlatformTime::Seconds();
        SetState(EEcoSessionState::InSession,bHosted
            ?FString::Printf(TEXT("방이 열렸습니다. 원격 참가자 %d명까지 접속할 수 있습니다."),GetDefault<UEcoSessionSettings>()->TotalPlayers(true))
            :TEXT("서버에 접속했습니다."));
        DumpRuntime();
    }
}

void UEcoSessionSubsystem::NetworkFailed(UWorld* World,UNetDriver*,ENetworkFailure::Type,const FString& Error)
{
    if (World && World->GetGameInstance()==GetGameInstance())
    {
        UE_LOG(LogEcoSession,Warning,TEXT("[EcoSession] NetworkFailure=%s"),*Error);
        // A provider can close its transport while DestroySession is still completing.
        // Keep that cleanup delegate instead of starting a second destroy request.
        if (State==EEcoSessionState::Leaving)
        { bReturnAfterDestroy=true; if(FailureAfterDestroy.IsEmpty()) FailureAfterDestroy=TEXT("서버 연결이 종료됐습니다: ")+Error; return; }
        ClearOperationDelegates();
        DestroyLocalSession(true,TEXT("서버 연결이 종료됐습니다: ")+Error);
    }
}

void UEcoSessionSubsystem::TravelFailed(UWorld* World,ETravelFailure::Type,const FString& Error)
{
    if (World && World->GetGameInstance()==GetGameInstance())
    {
        if (State==EEcoSessionState::Leaving) return;
        ClearOperationDelegates(); DestroyLocalSession(false,TEXT("레벨 이동 실패: ")+Error); ShowSessionMenu();
    }
}

bool UEcoSessionSubsystem::Tick(float)
{
    UWorld* World=GetWorld();
    if (!World || !World->IsGameWorld() || World->GetNetMode()==NM_DedicatedServer) return true;
    const double Now=FPlatformTime::Seconds();
    if (Deadline>0 && Now>=Deadline && !bTimedOut)
    {
        bTimedOut=true; Deadline=0;
        Status=TEXT("응답 시간이 초과됐습니다. 중복 요청 없이 기존 요청의 정리를 기다립니다.");
        OnUpdated.Broadcast();
        UE_LOG(LogEcoSession,Warning,TEXT("[EcoSession] OperationTimeout State=%d"),int32(State));
        if (State==EEcoSessionState::Searching && Sessions.IsValid())
        {
            const int32 Generation=OperationGeneration;
            CancelFindHandle=Sessions->AddOnCancelFindSessionsCompleteDelegate_Handle(
                FOnCancelFindSessionsCompleteDelegate::CreateWeakLambda(this,[this,Generation](bool bSuccess)
                { if (Generation==OperationGeneration && State==EEcoSessionState::Searching && bSuccess) Fail(TEXT("검색 시간이 초과되어 취소했습니다.")); }));
            Sessions->CancelFindSessions();
        }
        else if (State==EEcoSessionState::Travelling) { ClearOperationDelegates(); DestroyLocalSession(true,TEXT("서버 접속 시간이 초과됐습니다.")); }
    }
    APlayerController* PC=World->GetFirstPlayerController();
    if (!PC || !PC->IsLocalController()) return true;
#if WITH_DEV_AUTOMATION_TESTS
    if (FParse::Param(FCommandLine::Get(),TEXT("EcoSessionAudit")) && Now-LastRuntimeAudit>=5)
    { LastRuntimeAudit=Now; DumpRuntime(); }
    float LeaveAfter=0;
    if (!bTestLeaveDone && State==EEcoSessionState::InSession && !bHosted &&
        FParse::Value(FCommandLine::Get(),TEXT("EcoSessionLeaveAfter="),LeaveAfter) && LeaveAfter>0 &&
        Now-SessionEnteredAt>=LeaveAfter)
    { bTestLeaveDone=true; LeaveSession(); }
    if (bTestLeaveDone && !bTestRejoinDone && State==EEcoSessionState::Idle && World->GetNetMode()==NM_Standalone &&
        FParse::Param(FCommandLine::Get(),TEXT("EcoSessionAutoRejoin")))
    { bTestRejoinDone=true; FindSessions(bUsingLAN); }
#endif
    if (!bAutoActionDone)
    {
        bAutoActionDone=true;
        if (FParse::Param(FCommandLine::Get(),TEXT("EcoSessionAutoHost")))
        {
            FString Room; FParse::Value(FCommandLine::Get(),TEXT("EcoSessionRoom="),Room);
            HostSession(Room,FParse::Param(FCommandLine::Get(),TEXT("EcoSessionLAN")));
        }
        else if (FParse::Param(FCommandLine::Get(),TEXT("EcoSessionAutoFind")))
            FindSessions(FParse::Param(FCommandLine::Get(),TEXT("EcoSessionLAN")));
    }
    if (FApp::CanEverRender() && !IsRunningCommandlet() && !FParse::Param(FCommandLine::Get(),TEXT("EcoSessionNoUI")))
    {
        if (!bAutoMenuDone)
        {
            bAutoMenuDone=true;
            const auto* Settings=GetDefault<UEcoSessionSettings>();
            if (World->GetNetMode()==NM_Standalone && World->GetPackage()->GetName()==Settings->GameplayMap &&
                Settings->bShowMenuOnStandaloneStart && !IsBusy()) ShowSessionMenu();
        }
        if (PC->WasInputKeyJustPressed(EKeys::F10)) { if(Menu && Menu->IsInViewport()) CloseSessionMenu(); else ShowSessionMenu(); }
        if (Menu && Menu->IsInViewport() && Now-LastMenuRefresh>=.5) { LastMenuRefresh=Now; Menu->Refresh(); }
#if WITH_DEV_AUTOMATION_TESTS
        float CaptureAfter=0;
        if (!bTestCaptureDone && Menu && Menu->IsInViewport() &&
            FParse::Value(FCommandLine::Get(),TEXT("EcoSessionCaptureAfter="),CaptureAfter) && CaptureAfter>0 &&
            World->GetTimeSeconds()>=CaptureAfter)
        { bTestCaptureDone=true; PC->ConsoleCommand(TEXT("Shot SHOWUI")); }
#endif
    }
    return true;
}

void UEcoSessionSubsystem::ShowSessionMenu()
{
    UWorld* World=GetWorld();
    APlayerController* PC=World?World->GetFirstPlayerController():nullptr;
    if (!PC || !PC->IsLocalController() || !FApp::CanEverRender()) return;
    if (!Menu || MenuController.Get()!=PC)
    {
        Menu=CreateWidget<UEcoSessionMenuWidget>(PC,UEcoSessionMenuWidget::StaticClass());
        MenuController=PC; bPreviousCursor=PC->bShowMouseCursor;
    }
    if (!Menu) return;
    if (!Menu->IsInViewport()) Menu->AddToViewport(100);
    PC->bShowMouseCursor=true;
    FInputModeUIOnly Mode; Mode.SetWidgetToFocus(Menu->TakeWidget()); PC->SetInputMode(Mode);
    Menu->Refresh();
}

void UEcoSessionSubsystem::CloseSessionMenu()
{
    if (Menu) Menu->RemoveFromParent();
    if (auto* PC=MenuController.Get()) { PC->bShowMouseCursor=bPreviousCursor; PC->SetInputMode(FInputModeGameOnly()); }
}

void UEcoSessionSubsystem::DumpRuntime()
{
    const UWorld* World=GetWorld();
    const auto* GS=World?World->GetGameState<AEcoGameState>():nullptr;
    UE_LOG(LogEcoSession,Log,TEXT("[EcoSession][Runtime] Map=%s NetMode=%d State=%d Protocol=%d Players=%d Capacity=%d Epoch=%d Ready=%d SinceTravelStartSeconds=%.3f SearchRevision=%d Results=%d"),
        World?*World->GetMapName():TEXT("None"),World?int32(World->GetNetMode()):-1,int32(State),EcoSessionPolicy::ProtocolVersion,
        GS?GS->GetConnectedPlayerCount():0,GS?GS->GetMaxPlayers():0,GS?GS->GetWorldEpoch():0,GS&&GS->IsMassReplicationReady(),
        TravelStartedAt>0?FPlatformTime::Seconds()-TravelStartedAt:0,SearchRevision,Results.Num());
}
