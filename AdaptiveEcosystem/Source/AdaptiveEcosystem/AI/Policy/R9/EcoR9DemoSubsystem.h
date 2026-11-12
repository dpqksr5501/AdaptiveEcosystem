// R9 데모 플레이어 (2026-11-12, 발표용) — 파이썬에서 배운 사슴·늑대·멧돼지 두뇌가 팀 섬 원본 맵 위에서 움직이는 화면.
//
// 기본 꺼짐. 켜는 길은 둘뿐이다 (둘 다 없으면 이 서브시스템은 만들어지지도 않는다):
//   명령줄  -EcoR9Demo=<두뇌 폴더>          실시간 판 (R9 코어 C++ 추론, 두뇌 폴더 = {deer,wolf,boar}.r9brain)
//           -EcoR9Replay=<파일.r9rp>        재생 판 (파이썬 실행 기록 재생 — 화면에 그렇게 밝힌다). 곁 파일 .r9fd·.events.json 은 있으면 읽는다
//   콘솔    eco.R9Demo 1 (실시간) · 2 (재생) — PIE 는 Play 전에. 경로는 eco.R9Demo.Brains·Scene·Replay (비면 <프로젝트>/Saved/R9Demo/brains · replay/demo.r9rp)
// 도는 곳: 서버·단독(넷 모드가 클라이언트·데디케이티드가 아닌 곳), 맵 = 팀 섬 원본 /Game/Map/LV_SHC_IslandEcosystem1_WP (eco.R9Demo.AnyMap 1 이면 아무 맵).
// 거부: 통합 조정자·생태 지역이 있거나 통합 v3 가 켜졌으면 한 줄 남기고 아무것도 하지 않는다 (라이브 맵 워크플로와 섞이지 않게).
//
// 하는 일 (모두 실행 중에만, 저장하지 않는다 — 액터는 RF_Transient, 팀 맵·에셋·Config 는 그대로):
//   1. 섬 위 트인 평지 자리 고르기 (선호점 둘레를 불러와 높이·물·나무·바위를 훑음, -EcoR9DemoAt=x,y(m) 로 덮어쓰기) → 그 자리 스트리밍
//   2. 프레임 원천: 실시간 = R9 코어 한 스텝(2/15 초)씩, 재생 = 파일 프레임. 스텝 사이는 이어 그린다
//   3. 보이는 것: 사슴·늑대 = 조연우 BP_JYU_Deer/Wolf (없으면 팀 BP_EcoDeer/Wolf), 멧돼지 = 갈색 자리표시, 풀 덩어리(조연우 식생과 같은 메시·재질·
//      custom data 꼴), 멧돼지가 판 자리, 사체(누운 몸), 은신처 수풀·바위, 무대 가장자리 돌, 물기 표시(작은 점 — 번쩍임·소리 없음)
//   4. 카메라: 자동(사냥·물기·반격·사체 먹기를 따라가고 없으면 전체 보기) · 전체 · 종별 따라가기 · 위에서
//   5. 작은 글자 (종별 마릿수·시간·판) — H 또는 eco.R9Demo.Text 0 으로 끔
//   6. 녹화: -EcoR9Capture=<폴더>,<fps>,<초> — 창 없는 실행(-RenderOffscreen)에서 프레임 PNG 를 남기고 끝낸다
// 행동 규칙은 코어(학습 세계 그대로)가 정한다. 이 파일은 그리기만 한다 — 위치·먹이·죽음은 프레임 값 그대로다.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Templates/SharedPointer.h"
#include "EcoR9DemoSubsystem.generated.h"

class ACameraActor;
class APlayerController;
class UInstancedStaticMeshComponent;
class AEcoCreatureRepresentationActor;
class UCanvas;
class UMaterialInterface;
class UStaticMesh;
struct FEcoR9DemoState;

/** 켜는 설정 (명령줄·콘솔에서 읽음 — 시험용으로 공개). */
struct ADAPTIVEECOSYSTEM_API FEcoR9DemoSettings
{
	enum class EMode : uint8
	{
		Off,
		Live,
		Replay
	};
	EMode Mode = EMode::Off;
	FString BrainDir;          // 실시간: 두뇌 폴더
	FString ScenePath;         // 실시간: 장면 파일 (없으면 <두뇌 폴더>/scene.txt)
	FString ReplayPath;        // 재생: .r9rp
	uint64 Seed = 1;
	bool bSample = true;       // 실시간 고르기: 참 = 확률대로 (학습 때와 같음), 거짓 = 가장 높은 칸
	bool bHasAt = false;       // 무대 가운데를 직접 줌
	FVector2D AtM = FVector2D::ZeroVector;
	FVector2D PrefM = FVector2D(759.0, -156.0);   // 자동 고르기 선호점 (m)
	FString CaptureDir;        // 녹화 (비면 안 함)
	float CaptureFps = 30.0f;
	float CaptureSeconds = 0.0f;
	float ExitAfterSeconds = 0.0f;   // 무대가 선 뒤 이만큼 지나면 끝냄 (0 = 안 끝냄)
	bool bAnyMap = false;

	/** 명령줄 글과 콘솔 값(eco.R9Demo …)에서 읽는다. 둘 다 없으면 Mode = Off. */
	static FEcoR9DemoSettings Resolve(const TCHAR* CommandLine);
	/** 이 맵에서 도는가 (팀 섬 원본, 또는 bAnyMap). PIE 앞붙이는 뗀 이름. */
	static bool MapAllowed(const FString& PackageName, bool bAnyMap);
	/** 팀 섬 원본 맵 (복사하지 않음). */
	static const TCHAR* IslandMap() { return TEXT("/Game/Map/LV_SHC_IslandEcosystem1_WP"); }
	/** 기본 폴더 <프로젝트>/Saved/R9Demo (커밋되지 않는 곳). 경로를 주지 않으면 두뇌 = brains/ (장면 = brains/scene.txt), 재생 = replay/demo.r9rp. */
	static FString DefaultDir();
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoR9DemoSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	/** 무대가 서서 프레임을 그리는 중인가. */
	bool IsRunning() const;
	/** 거부·실패 없이 켜져 있는가 (무대를 준비하는 중 포함). */
	bool IsActive() const;
	/** 만든 액터 수 (시험용). */
	int32 NumSpawnedActors() const;
	/** 지금 그리는 동물 몸 수 · 이번 판에 보여 준 스텝 수 (시험용). */
	int32 NumBodies() const;
	int64 NumStepsShown() const;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	// --- EcoR9DemoSubsystem.cpp: 켜기·무대 자리·프레임 원천·녹화·글자
	bool RefuseReason(UWorld& World, FString& OutWhy) const;
	void BeginStreamingAt(const FVector& CenterCm, float RadiusCm);
	void ScanAndPick();
	void BuildStage();
	bool OpenSource(FString& OutError);
	bool AdvanceFrame();
	void RestartRun(const TCHAR* Why);
	void TickRunning(float DeltaTime);
	void TickCapture(float DeltaTime);
	void DrawOverlay(UCanvas* Canvas, APlayerController* PC);
	void LogSummary(const TCHAR* Tag);
	void Fail(const FString& Why);
	double GroundZ(double XCm, double YCm) const;
	void ApplyViewEnvironment();
	void FreezePawn();
	void ParkPawn();
	void RequestQuit(const TCHAR* Why);
	void HoldDaylight();
	void ReleaseDaylight();

	// --- EcoR9DemoVisuals.cpp: 몸·먹이·은신처·표시
	void LoadVisualAssets();
	void SpawnStaticDecor();
	void SyncBodies(double Alpha, float DeltaTime);
	void OnFrameAdvanced();
	void UpdateFood();
	void UpdateMarkers(double Now);
	void ClearBodies();
	AActor* SpawnBoarPlaceholder(uint32 Id, const FVector& Location, float YawDeg);
	UInstancedStaticMeshComponent* MakeIsm(AActor* Owner, const TCHAR* Name, UStaticMesh* Mesh, UMaterialInterface* Material, int32 NumCustom,
										   bool bShadow);

	// --- EcoR9DemoCamera.cpp: 카메라·키
	void EnsureCamera();
	void HandleKeys();
	void UpdateCamera(float DeltaTime);

	TSharedPtr<FEcoR9DemoState> State;

	// 불러온 에셋·클래스 (GC 가 지우지 않게)
	UPROPERTY(Transient) TObjectPtr<UClass> DeerClass;
	UPROPERTY(Transient) TObjectPtr<UClass> WolfClass;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> GrassMesh;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> GrassMaterial;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> ShrubMesh;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> StoneMesh;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> SphereMesh;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> CylinderMesh;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> BasicMaterial;
	UPROPERTY(Transient) TObjectPtr<AActor> Manager;
	UPROPERTY(Transient) TObjectPtr<ACameraActor> Camera;
	UPROPERTY(Transient) TArray<TObjectPtr<AActor>> SpawnedActors;
};
