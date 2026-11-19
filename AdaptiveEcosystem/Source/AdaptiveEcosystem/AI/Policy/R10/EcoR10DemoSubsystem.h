// R10 데모 (2026-11-19) — 파이썬에서 배운 R10 두뇌 16 종을 언리얼 맵 위에서 실시간으로 돌려 보여 주는 화면.
//
// 기본 꺼짐. 켜는 길:
//   명령줄  -EcoR10Demo                 (두뇌 폴더 = <프로젝트>/Saved/R10Demo)
//           -EcoR10Demo=<폴더>          (species.txt + <종>.r10brain — herbivore_rl/results/v3/r10/export_r10.py 가 만듦)
//   콘솔    eco.R10Demo 1 (Play 중이면 그 자리에서 시작, 0 이면 멈춤) · eco.R10Demo.Dir <폴더>
// R10 데모가 켜지면 같은 실행에서 R9 데모(eco.R9Demo)는 끈다 (콘솔 값을 코드로 0 — 저장하지 않음. 두 데모가 같은 화면·키를 같이 쓰지 않게).
// 도는 곳: 서버·단독만 (클라이언트·데디케이티드 거부). 맵 제한 없음 — 지형(Landscape)이나 바닥 메시가 있는 맵.
//
// 하는 일 (모두 실행 중에만, 저장하지 않음 — 액터 RF_Transient, 팀 맵·에셋·Config 그대로):
//   1. 플레이어 시작점(플레이어 몸 → PlayerStart → 원점, 명령줄 -EcoR10DemoAt=x,y m 로 덮어쓰기) 둘레 정사각 eco.R10Demo.Area (기본 300 m)를
//      eco.R10Demo.Cell (기본 1 m — 학습 맵 mapgen 칸 크기와 같게: 먹이 용량·재생이 '칸마다' 값이라 칸이 커지면 먹이 밀도가 바뀐다.
//      300 m 면 9 만 칸 × 층 약 40 개 float ≈ 15 MB) 칸으로 훑는다: 땅 높이(지형, 없으면 바닥 메시) · 물(WaterBody — 바다 = 수면 높이,
//      호수·강 = 그 물 몸체 충돌을 선 검사) · 나무(줄기 = 막힘, 갓 = canopy) · 바위·건물(막힘) · 덤불·고사리(가림).
//      → EcoR10DemoMap.h 가 mapgen 규칙으로 R10 코어 지형 층(먹이 8 층·은신처 포함)을 만든다.
//   2. 종 16 개를 species.txt 차례로 eco.R10Demo.PerSpecies (기본 8,12 = 시작 수, 상한) 만큼 풀고 다시 남(학습 세계처럼 50 결정 뒤) 켬.
//      한 결정(2/15 초 × 2 = 0.267 초)마다 감각 206 → 두뇌(없는 종은 공통 규칙 두뇌) 확률 뽑기 → 세계 한 결정. 사이는 이어 그린다.
//   3. 몸: 종마다 조연우 표현 BP (/Game/JYU/Fauna·ExpandedFauna·Creatures — 부모 AEcoCreatureRepresentationActor) 를 띄워 ConsumeVisualState 로
//      자리·속도·자세를 준다. BP 를 못 읽은 종은 색 공 자리표시 + 기록 줄. 나는 몸은 높이, 헤엄 몸은 물속 높이.
//   4. 카메라·키: N/P 다음·이전 종 · , . 같은 종 다음·이전 개체 · T 위에서 보기 · F 자유(플레이어 시점) · - = 거리 · H 글 숨기기.
//   5. 확인용: -EcoR10Capture=<폴더>,<fps>,<초> (창 없는 실행 -RenderOffscreen 에서 PNG), -EcoR10CamCycle=<초> (그 초마다 다음 종),
//      -EcoR10ExitAfter=<초> (돌기 시작 뒤 그만큼 지나면 끝냄 — -NullRHI 점검).
// 행동은 두뇌, 세계 규칙은 코어(EcoR10Core.h — 파이썬 r10/world.py·senses.py 를 옮긴 것). 이 파일은 땅 훑기·풀기·그리기만 한다.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoR10DemoSubsystem.generated.h"

class ACameraActor;
class APlayerController;
class UCanvas;
class UStaticMesh;
class UMaterialInterface;
class IConsoleVariable;
struct FEcoR10DemoState;

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoR10DemoSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	/** 세계가 돌고 있는가 · 산 개체 수 · 지난 결정 수 · 종 수 (시험·기록용). */
	bool IsRunning() const;
	int32 NumAlive() const;
	int64 NumDecisions() const;
	int32 NumSpecies() const;

	void StartDemo(const TCHAR* Why);
	void StopDemo(const TCHAR* Why);
	static void OnCVarChanged(IConsoleVariable* Var);

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	bool LoadInputs(FString& OutError);
	bool ScanAndBuild(FString& OutError, bool bLastTry);
	void ChooseCenter();
	void StepSim();
	void SyncBodies(double Alpha, float DeltaTime);
	void HandleKeys();
	void UpdateCamera(float DeltaTime);
	void TickCapture(float DeltaTime);
	void DrawOverlay(UCanvas* Canvas, APlayerController* PC);
	void HideOthers();
	void Teardown(bool bRestoreView);
	void Fail(const FString& Why);
	void LogSummary(const TCHAR* Tag);
	double GroundCm(double X, double Y, double FallbackCm) const;
	FVector BodyLocation(int32 Slot, double Alpha) const;
	void PickSubject(int32 Species, int32 Dir);

	TSharedPtr<FEcoR10DemoState> State;

	UPROPERTY(Transient) TArray<TObjectPtr<UClass>> SpeciesClasses;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> SphereMesh;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> BasicMaterial;
	UPROPERTY(Transient) TObjectPtr<ACameraActor> Camera;
	UPROPERTY(Transient) TArray<TObjectPtr<AActor>> SpawnedActors;
};
