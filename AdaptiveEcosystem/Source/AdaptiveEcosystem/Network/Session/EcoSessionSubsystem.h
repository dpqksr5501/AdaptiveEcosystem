#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Engine/EngineBaseTypes.h"
#include "Interfaces/OnlineSessionInterface.h"
#include "OnlineSessionSettings.h"
#include "EcoSessionSubsystem.generated.h"

class UEcoSessionMenuWidget;
class UNetDriver;
class IConsoleObject;

UENUM(BlueprintType)
enum class EEcoSessionState : uint8 { Idle, Creating, Starting, Searching, Joining, Travelling, InSession, Leaving, Error };

USTRUCT(BlueprintType)
struct FEcoSessionBrowserEntry
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) FString Name;
    UPROPERTY(BlueprintReadOnly) FString Host;
    UPROPERTY(BlueprintReadOnly) int32 Players = 0;
    UPROPERTY(BlueprintReadOnly) int32 Capacity = 0;
    UPROPERTY(BlueprintReadOnly) int32 PingMs = 0;
    UPROPERTY(BlueprintReadOnly) int32 SearchRevision = 0;
    UPROPERTY(BlueprintReadOnly) bool bCompatible = false;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FEcoSessionUpdated);

/** Local session coordinator. No ecological state or replicated subsystem properties. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoSessionSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    virtual UWorld* GetWorld() const override;

    UFUNCTION(BlueprintCallable, Category="Ecology|Multiplayer") bool HostSession(FString RoomName, bool bLAN = false);
    UFUNCTION(BlueprintCallable, Category="Ecology|Multiplayer") bool FindSessions(bool bLAN = false);
    UFUNCTION(BlueprintCallable, Category="Ecology|Multiplayer") bool JoinSession(int32 Index, int32 ExpectedSearchRevision);
    UFUNCTION(BlueprintCallable, Category="Ecology|Multiplayer") void LeaveSession();
    UFUNCTION(BlueprintCallable, Category="Ecology|Multiplayer") void ShowSessionMenu();
    UFUNCTION(BlueprintCallable, Category="Ecology|Multiplayer") void CloseSessionMenu();
    UFUNCTION(BlueprintPure, Category="Ecology|Multiplayer") bool IsBusy() const;
    UFUNCTION(BlueprintPure, Category="Ecology|Multiplayer") FString GetProviderName() const;
    UFUNCTION(BlueprintCallable, Category="Ecology|Multiplayer") void DumpRuntime();

    UPROPERTY(BlueprintReadOnly, Category="Ecology|Multiplayer") EEcoSessionState State = EEcoSessionState::Idle;
    UPROPERTY(BlueprintReadOnly, Category="Ecology|Multiplayer") FString Status;
    UPROPERTY(BlueprintReadOnly, Category="Ecology|Multiplayer") TArray<FEcoSessionBrowserEntry> Results;
    UPROPERTY(BlueprintReadOnly, Category="Ecology|Multiplayer") int32 SearchRevision = 0;
    UPROPERTY(BlueprintAssignable, Category="Ecology|Multiplayer") FEcoSessionUpdated OnUpdated;

private:
    bool Prepare(bool bLAN);
    bool Tick(float DeltaSeconds);
    void SetState(EEcoSessionState Next, const FString& Message);
    void BeginOperation(EEcoSessionState Next, const FString& Message);
    void ClearOperationDelegates();
    void Fail(const FString& Message, bool bCleanup = false);
    void DestroyLocalSession(bool bReturnToMap, const FString& Failure = FString());
    void Created(FName Name, bool bSuccess);
    void Started(FName Name, bool bSuccess);
    void Found(bool bSuccess);
    void Joined(FName Name, EOnJoinSessionCompleteResult::Type Result);
    void Destroyed(FName Name, bool bSuccess);
    void MapLoaded(UWorld* World);
    void NetworkFailed(UWorld* World, UNetDriver* Driver, ENetworkFailure::Type Type, const FString& Error);
    void TravelFailed(UWorld* World, ETravelFailure::Type Type, const FString& Error);
    bool StartJoin(const FOnlineSessionSearchResult& Result);

    IOnlineSessionPtr Sessions;
    TSharedPtr<FOnlineSessionSearch> Search;
    TArray<FOnlineSessionSearchResult> SearchResults;
    FDelegateHandle CreateHandle, StartHandle, FindHandle, CancelFindHandle, JoinHandle, DestroyHandle, InviteHandle;
    FDelegateHandle PostLoadHandle, NetworkFailureHandle, TravelFailureHandle;
    FTSTicker::FDelegateHandle TickerHandle;
    UPROPERTY(Transient) TObjectPtr<UEcoSessionMenuWidget> Menu;
    TWeakObjectPtr<APlayerController> MenuController;
    bool bPreviousCursor = false;
    bool bUsingLAN = false;
    bool bHosted = false;
    bool bAutoActionDone = false;
    bool bAutoMenuDone = false;
    bool bTimedOut = false;
    bool bReturnAfterDestroy = false;
    FString FailureAfterDestroy;
    FString PendingRoomName;
    double Deadline = 0;
    double LastMenuRefresh = 0;
    double TravelStartedAt = 0;
    double SessionEnteredAt = 0;
    double LastRuntimeAudit = 0;
    bool bTestLeaveDone = false;
    bool bTestRejoinDone = false;
    bool bTestCaptureDone = false;
    int32 OperationGeneration = 0;
};

