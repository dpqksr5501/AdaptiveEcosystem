// R9 데모 플레이어 (2026-11-12, 발표용) — 파이썬에서 배운 사슴·늑대·멧돼지 두뇌가 언리얼 맵 위에서 움직이는 화면.
//
// 기본 꺼짐. 켜는 길은 둘뿐이다 (둘 다 없으면 이 서브시스템은 만들어지지도 않는다):
//   명령줄  -EcoR9Demo=<두뇌 폴더>          실시간 판 (R9 코어 C++ 추론, 두뇌 폴더 = {deer,wolf,boar}.r9brain)
//           -EcoR9Replay=<파일.r9rp>        재생 판 (파이썬 실행 기록 재생 — 화면에 그렇게 밝힌다). 곁 파일 .r9fd·.events.json 은 있으면 읽는다
//   콘솔    eco.R9Demo 1 (실시간) · 2 (재생) — PIE 는 Play 전에. 경로는 eco.R9Demo.Brains·Scene·Replay (비면 <프로젝트>/Saved/R9Demo/brains · replay/demo.r9rp)
// 도는 곳: 서버·단독(넷 모드가 클라이언트·데디케이티드가 아닌 곳). **맵 제한 없음 (2026-11-12 22:30)** — 지형(Landscape)이나 바닥 메시가 있는 아무 맵
//   (World Partition 맵·일반 맵 둘 다). 맵마다 설정할 것이 없다: 무대 자리는 그 맵에서 자동으로 고른다.
// 맵에 통합 조정자·생태 지역·서식지·통합 v3 가 이미 있어도 거부하지 않는다 — 그쪽은 건드리지 않고 데모만 따로 돈다 (R9 개체는 Mass 개체가 아니라
//   팀 시뮬레이션이 보지 못하고, 데모도 팀 개체를 읽지 않는다). 무대는 그 지역 상자·동물에서 떨어진 곳을 먼저 고르고, 기록 줄로 알린다.
//
// 하는 일 (모두 실행 중에만, 저장하지 않는다 — 액터는 RF_Transient, 팀 맵·에셋·Config 는 그대로):
//   1. 무대 자리 고르기: 플레이어 시작점(플레이어 몸 → PlayerStart → 시점 → 원점) 둘레를 200 · 400 · 800 m 로 넓혀 가며 불러와 4 m 칸으로
//      땅 높이(지형, 없으면 바닥 메시)·물·가파름·나무/바위/건물을 훑어 120 m 열린 평지를 찾는다 (기존 생태 둘레는 되도록 피함). 못 찾으면 가장 덜 막힌
//      곳 + 기록 줄. 콘솔 eco.R9Demo.At x,y (m) · 명령줄 -EcoR9DemoAt=x,y 로 덮어쓰기 → 그 자리 스트리밍 (World Partition 맵만, 아니면 그대로)
//   2. 프레임 원천: 실시간 = R9 코어 한 스텝(2/15 초)씩, 재생 = 파일 프레임. 스텝 사이는 이어 그린다
//   3. 보이는 것: 사슴·늑대 = 조연우 BP_JYU_Deer/Wolf (없으면 팀 BP_EcoDeer/Wolf), 멧돼지 = 갈색 자리표시, 풀 덩어리(조연우 식생과 같은 메시·재질·
//      custom data 꼴), 멧돼지가 판 자리, 사체(누운 몸), 은신처 수풀·바위, 무대 가장자리 돌, 물기 표시(작은 점 — 번쩍임·소리 없음)
//   4. 카메라: 옛 관찰 카메라 꼴 (11-13 03:30 — 아래 '카메라' 줄, EcoR9DemoCam.h)
//   5. 오른쪽 위 글 묶음 (단축키 · 실시간 · 마릿수 · 잡힘·반격·굶음 · 카메라 대상·행동) — H = 단축키 목록 숨기기/보이기, eco.R9Demo.Text 0 = 글 모두 끔
//   6. 녹화: -EcoR9Capture=<폴더>,<fps>,<초> — 창 없는 실행(-RenderOffscreen)에서 프레임 PNG 를 남기고 끝낸다
// 행동 규칙은 코어(학습 세계 그대로)가 정한다. 이 파일은 그리기만 한다 — 위치·먹이·죽음은 프레임 값 그대로다.
//
// 2026-11-13 맵 전체 땅 모드 (사용자 '명령 없이 지금 맵에서 플레이하면 바로 … 돼지도 같이 풀리도록'):
//   - 명령 없이: 이 PC 의 Config/UserEngine.ini [ConsoleVariables] 에 eco.R9Demo=1 한 줄이면 Play 할 때마다 켜진다 (git 제외 파일 — 팀 기본값 그대로).
//     끄려면 그 줄을 지우거나 콘솔 eco.R9Demo 0 (Play 중에도 바로 멈춤 — 콘솔 값 바뀜 콜백). Play 중 eco.R9Demo 1 이면 그 자리에서 시작 (두 번 만들지 않음).
//   - eco.R9Demo.Area 0 (기본) = 그 맵의 쓸 수 있는 땅 전체를 4 m 로 훑어 땅/물/가파름/나무·바위 지도를 코어에 넘기고, 코어 큰 세계 장면 생성기가
//     무리 자리 K 곳(eco.R9Demo.Herds, 기본 6)에 사슴·늑대·멧돼지를 함께 푼다 (학습 밀도와 비슷하게 자리마다 eco.R9Demo.PerHerd 24,2,8).
//     시작 뒤에는 벽 없이 땅 어디든 다닌다 (막힌 칸은 벽처럼 미끄러짐 — 길을 대신 찾지 않음, CORE_API.md).
//     eco.R9Demo.Area 1 ~ 120 = 예전 한 무대 (학습 세계 120 m 그대로) · 120 넘음 = 시작점 둘레 그 크기(m) 정사각만 큰 세계로.
//   - 맵의 예전 v3·Fauna 동물 몸·먼 표식은 데모 동안 보이는 것만 숨긴다 (eco.R9Demo.HideOthers 1 — 그쪽 시뮬레이션·코드·에셋은 그대로).
//   - 멧돼지 몸: 에셋 레지스트리에서 /Game/AnimalVarietyPack/Pig → /Game/JYU/Fauna → /Game 차례로 Pig·Boar·Hog·Swine·villsvin 이름의 표현 BP·스켈레탈
//     메시를 찾아 상태별 애니를 재생한다 (eco.R9Demo.BoarMesh 로 덮어쓰기). 없으면 자리표시 + 기록 줄 한 줄.
//   - 카메라: (11-13 03:30 옛 관찰 카메라 꼴로 바꿈 — EcoR9DemoCam.h) 1 늑대 · 2 사슴 · 3 탑뷰 · 4 쿼터뷰 · 5 자동 추적 · 0 자유 카메라 ·
//     6 멧돼지 · 7(G) 다음 무리 자리 · , . 대상 · - = 휠 줌 · H 단축키 목록. 키로 바꾸면 한 번에 그 자리로. 글은 오른쪽 위 묶음 하나.
//
// 2026-11-13 03:30 시작 맵에서만 저절로 켜기 (사용자 — 편집기 시작 맵 /Game/EcoTest/Maps/LV_EcoV3_Island 에서만 씀):
//   콘솔 eco.R9Demo.OnlyMap (기본 빈 값 = 모든 맵) 에 맵 경로(쉼표로 여럿)를 두면 Play 시작 때 그 맵에서만 켠다 — 다른 맵은 예전처럼 아무것도 만들지 않는다.
//   명령줄 깃발(-EcoR9Demo= 등)·Play 중 직접 친 콘솔 eco.R9Demo 1 은 거르지 않는다 (직접 켠 것).
//
// 2026-11-13 05:00 동물 세계 (사용자 '나머지 동물들도 학습시켜서 생태계에 넣고 … 지금 언리얼 기본맵에서만'):
//   <두뇌 폴더>/fauna/ 에 buffalo·leopard·fox.r9brain 과 scene.txt(파이썬 동물 세계 v3_r9_fauna.yaml 장면)가 다 있으면 Play 할 때 물소·표범·여우도
//   섬 땅에 함께 푼다 (eco.R9Demo.Fauna 1 기본 · 0 = 세 종만 · 명령줄 -EcoR9Fauna=0/1). 세계 몸 규칙은 코어가 장면 파일로 켠다 (파이썬과 비트 같음 — 손 규칙 없음).
//   사슴·늑대·멧돼지 두뇌는 fauna/ 에 있으면 그것, 없으면 <두뇌 폴더> 의 S′ 두뇌 (파이썬 rebody 와 같은 뜻 — 가중치 그대로). 하나라도 없거나 동물 장면이
//   시작에 실패하면 기록 줄을 남기고 지금 세 종 장면으로 돈다. 자리마다 eco.R9Demo.FaunaPerHerd (물소,표범,여우 기본 4,1,2).
//   몸 = 조연우 /Game/JYU/Fauna/{Buffalo,Leopard,Fox}/BP_* (표현 BP — 읽기만). 카메라 8 물소 · 9 표범 · J 여우 (EcoR9DemoCam.h).

#pragma once

#include "CoreMinimal.h"
#include "EcoR9DemoCam.h"
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
class USkeletalMesh;
class USkeletalMeshComponent;
class UAnimSequence;
class IConsoleVariable;
struct FEcoR9DemoState;
struct FEcoR9ScanCounts;
namespace EcoR9Demo
{
	struct FR9ScanGrid;
	struct FR9WholeSpec;
	struct FR9CoverPoint;
}

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
	bool bHasAt = false;       // 무대 가운데를 직접 줌 (콘솔 eco.R9Demo.At · 명령줄 -EcoR9DemoAt=, m)
	FVector2D AtM = FVector2D::ZeroVector;
	bool bHasPref = false;     // 자동 고르기 시작점을 직접 줌 (명령줄 -EcoR9DemoPref=x,y, m — 창 없는 실행·시험용). 없으면 플레이어 시작점
	FVector2D PrefM = FVector2D::ZeroVector;
	FString CaptureDir;        // 녹화 (비면 안 함)
	float CaptureFps = 30.0f;
	float CaptureSeconds = 0.0f;
	float ExitAfterSeconds = 0.0f;   // 무대가 선 뒤 이만큼 지나면 끝냄 (0 = 안 끝냄)
	bool bCaptureUI = false;         // -EcoR9CaptureUI : 녹화 프레임에 오른쪽 위 글 묶음도 넣는다 (확인용 — 없으면 예전처럼 그림만)
	FString CamKeys;                 // -EcoR9CamKeys=<초>:<키>[,<초>:<키>…] : 무대가 선 뒤 그 초에 카메라 키를 누른 것처럼 (확인용 — 키 이름은 One·Zero·G 꼴)
	// 맵 전체 땅 모드 (2026-11-13)
	int32 AreaM = 0;                 // eco.R9Demo.Area · -EcoR9DemoArea= : 0 = 맵 전체 땅 · 1 ~ 120 = 예전 한 무대 · 그 밖 = 시작점 둘레 그 크기 정사각
	int32 Herds = 6;                 // eco.R9Demo.Herds : 무리 자리 수 (1 ~ 8)
	int32 PerHerd[6] = {24, 2, 8, 4, 1, 2};   // eco.R9Demo.PerHerd : 자리마다 사슴·늑대·멧돼지 · eco.R9Demo.FaunaPerHerd : 물소·표범·여우 (동물 장면만)
	int32 Fauna = 1;                 // eco.R9Demo.Fauna · -EcoR9Fauna= : 1 = 새 종 두뇌·동물 장면이 다 있으면 켬 · 0 = 세 종만
	bool bSceneExplicit = false;     // 장면 파일을 직접 줌 (-EcoR9Scene= · eco.R9Demo.Scene) — 동물 장면으로 저절로 바꾸지 않는다
	bool bHideOthers = true;         // eco.R9Demo.HideOthers : 예전 동물 몸·먼 표식 숨김
	// 시작 맵에서만 (2026-11-13 03:30)
	bool bFromCommandLine = false;   // 판을 명령줄 깃발(-EcoR9Demo= · -EcoR9Demo · -EcoR9Replay=)이 정했다 — 맵 거르기를 하지 않는다
	FString OnlyMap;                 // eco.R9Demo.OnlyMap : 비면 모든 맵 · 맵 경로(쉼표로 여럿)면 Play 시작 때 그 맵에서만 켠다

	/** 이 설정이 맵 전체 땅(큰 세계) 길인가 (실시간 판 + 무대 자리 덮어쓰기 없음 + Area 0 또는 120 넘음). */
	bool WantsWhole() const { return Mode == EMode::Live && !bHasAt && (AreaM <= 0 || AreaM > 120); }

	/** 명령줄 글과 콘솔 값(eco.R9Demo …)에서 읽는다. 둘 다 없으면 Mode = Off. 맵 거르기(OnlyMap)는 여기서 하지 않는다 (OnWorldBeginPlay). */
	static FEcoR9DemoSettings Resolve(const TCHAR* CommandLine);
	/**
	 * 맵 거르기: OnlyMap 이 비면(공백뿐 포함) 참. 아니면 쉼표·쌍반점으로 나눈 항목 가운데 하나가 월드 패키지와 같으면 참 (대소문자 무시).
	 * 항목 꼴: 패키지 경로 '/Game/EcoTest/Maps/LV_EcoV3_Island' · 오브젝트 경로 '….LV_EcoV3_Island' · 짧은 이름 'LV_EcoV3_Island'.
	 * 월드 패키지의 PIE 머리(UEDPIE_0_)는 떼고 견준다.
	 */
	static bool MapAllowed(const FString& OnlyMap, const FString& WorldPackage);
	/** 기본 폴더 <프로젝트>/Saved/R9Demo (커밋되지 않는 곳). 경로를 주지 않으면 두뇌 = brains/ (장면 = brains/scene.txt), 재생 = replay/demo.r9rp. */
	static FString DefaultDir();
	/** 동물 세계 폴더 <두뇌 폴더>/fauna (buffalo·leopard·fox.r9brain + scene.txt, 있으면 deer·wolf·boar.r9brain 도). */
	FString FaunaDir() const;
};

/** 카메라 상태 한 장 (시험·기록용 — 읽기만). */
struct ADAPTIVEECOSYSTEM_API FEcoR9DemoCamProbe
{
	int32 Mode = -1;                 // EEcoR9DemoCam 값 (= 키 숫자, 0 자유 … 6 멧돼지)
	uint32 Subject = 0;              // 따라가는 R9 uid (0 = 없음)
	int32 SubjectSpecies = -1;       // 0 사슴 · 1 늑대 · 2 멧돼지 · 3 물소 · 4 표범 · 5 여우 (없으면 −1)
	uint32 Partner = 0;
	FVector Focus = FVector::ZeroVector;         // 지금 초점
	FVector TargetFocus = FVector::ZeroVector;   // 이번 프레임 목표 초점
	double Yaw = 0.0, TargetYaw = 0.0;
	double Pitch = 0.0, TargetPitch = 0.0;
	double Dist = 0.0, TargetDist = 0.0;
	double Arm = 0.0;                            // 가림 피하기 뒤 실제 거리
	bool bHaveCamera = false;
	FVector CameraLocation = FVector::ZeroVector;
	FRotator CameraRotation = FRotator::ZeroRotator;
	double FreeSpeedMps = 0.0;
	int32 SiteIndex = 0;
	bool bShowKeys = true;
	double Zoom = 1.0;
	int32 NumLines = 0;                          // 오른쪽 위 카메라 줄 수
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
	/** 무대 정사각 가운데 (cm, z = 땅 높이) · 자리 찾기 시작점 · 피한 기존 생태 상자 수 · 맵에 팀 생태 장치가 있는가 (시험·기록용). */
	FVector StageCenterCm() const;
	FVector SearchOriginCm() const;
	int32 NumAvoidZones() const;
	bool HasTeamEco() const;
	/** 맵 전체 땅 모드 (시험·기록용): 큰 세계로 도는가 · 땅 지도 (없으면 nullptr) · 무리 자리 수 · 숨긴 예전 동물 수 · 몸 액터·먼 표식 수 · 시작 횟수 · 멧돼지 몸 설명. */
	bool IsWhole() const;
	const EcoR9Demo::FR9WholeSpec* WholeSpecForTest() const;
	int32 NumHerdSites() const;
	int32 NumHiddenOthers() const;
	int32 NumBodyActors() const;
	int32 NumFarMarkers() const;
	int32 NumStarts() const;
	FVector WholeCenterCm() const;   // 땅 지도 정사각 가운데 (cm) — 코어 칸 ↔ 언리얼 자리 (FR9StageMap, W = H = G × 2 단위)
	FString BoarBodyLine() const;
	/** 이번 판이 동물 세계 장면인가 (물소·표범·여우 함께 — 시험·기록용). */
	bool IsFaunaScene() const;
	/** 이번 판 종 수 (3 또는 6, 시작 전 0). */
	int32 NumSceneSpecies() const;
	/** 지금 그 종을 그린 수 (산 몸 액터 + 먼 표식 — 시험용, 종 번호 = EcoR9Demo::kDeer..kFox). */
	int32 NumShownOfSpecies(uint8 Species) const;
	/** 동물 장면을 골랐나·왜 아닌가 (기록 줄 FaunaLine — 시험용). */
	FString FaunaChoiceLine() const;
	/** Play 중 켜기/끄기 (콘솔 eco.R9Demo 바뀜 콜백이 부름 — 시험도 부름). 이미 켜져 있으면 다시 만들지 않는다. */
	void StartDemo(const TCHAR* Why);
	void StopDemo(const TCHAR* Why);
	/** 콘솔 eco.R9Demo 가 바뀌면: 지금 도는 게임·PIE 월드마다 시작·정지. */
	static void OnDemoCVarChanged(IConsoleVariable* Var);
	/** Play 시작 때 맵 거르기(eco.R9Demo.OnlyMap)로 켜지 않았는가 (시험·기록용). */
	bool WasMapFiltered() const;

	/**
	 * 카메라 키 하나 누름 (HandleKeys 가 키마다 부른다 — 시험도 같은 길로 부른다). 카메라 키면 참 (무대가 도는 중이 아니면 아무 일 없이 거짓).
	 * 키 뜻은 EcoR9DemoCam.h. 시점을 바꾸는 키는 다음 프레임에 끊어 옮긴다 (부드럽게 옮겨 가지 않음).
	 */
	bool PressCamKey(const FKey& Key);
	/** 지금 카메라 상태 (시험용 — 읽기만). */
	FEcoR9DemoCamProbe CamProbe() const;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	// --- EcoR9DemoSubsystem.cpp: 켜기·무대 자리·프레임 원천·녹화·글자
	void OnWorldBeginPlayImpl(UWorld& InWorld);
	void DescribeTeamEco(UWorld& World);
	void ChooseSearchOrigin(UWorld& World);
	void RefreshProbeIgnore();
	void BeginStreamingAt(const FVector& CenterCm, float RadiusCm);
	/** 자리 찾기 고리 Ring (0 = 200 m, 1 = 400 m, 2 = 800 m) 를 훑는다. 자리를 정했으면 참 (마지막 고리는 늘 정한다). */
	bool ScanAndPick(int32 Ring);
	/** 훑기 격자 칸마다 땅 높이·물·가파름·걸리는 것 (고리 훑기·맵 전체 훑기가 같이 씀). Kinds = 칸 종류 (ER9Land), Cover = 나무·큰 바위 점 (cm). */
	void ScanCells(EcoR9Demo::FR9ScanGrid& G, TArray<uint8>* Kinds, TArray<EcoR9Demo::FR9CoverPoint>* Cover, FEcoR9ScanCounts& C);
	/** 맵 전체 땅: 훑을 사각 정하기 → 불러오기 시작. */
	void BeginWhole(UWorld& World);
	/** 맵 전체 땅: 훑기 → 땅 지도 → 코어 큰 세계. 실패하면 거짓 (그러면 예전 한 무대로). */
	bool ScanWhole();
	void TeardownDemo(bool bRestoreView);
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
	void RestorePawn();
	void HideOtherVisuals(bool bHide);
	void RequestQuit(const TCHAR* Why);
	void HoldDaylight();
	void ReleaseDaylight();
	/** 옛 관찰 카메라 끄기 (eco.Cam.Enable 0 — 데모가 켜지는 때부터, 끌 때 TeardownDemo 가 되돌림). 같은 숫자 키를 두 카메라가 같이 읽지 않게. */
	void HoldObserverCamera();

	// --- EcoR9DemoVisuals.cpp: 몸·먹이·은신처·표시
	void LoadVisualAssets();
	void SpawnStaticDecor();
	void SyncBodies(double Alpha, float DeltaTime);
	void OnFrameAdvanced();
	void UpdateFood();
	void UpdateMarkers(double Now);
	void ClearBodies();
	AActor* SpawnBoarPlaceholder(uint32 Id, const FVector& Location, float YawDeg);
	AActor* SpawnBoarSkeletal(uint32 Id, const FVector& Location, float YawDeg, USkeletalMeshComponent*& OutMesh);
	void LoadBoarAssets();
	/** 물소·표범·여우 표현 BP (동물 장면일 때만 — LoadVisualAssets·RestartRun 이 부름. 읽기는 한 번, 기록 줄 FaunaBodyLine 은 늘 다시 씀). */
	void LoadFaunaAssets();
	void UpdateFarMarkers(const TArray<FVector>* Where);
	FVector CameraEye() const;
	UInstancedStaticMeshComponent* MakeIsm(AActor* Owner, const TCHAR* Name, UStaticMesh* Mesh, UMaterialInterface* Material, int32 NumCustom,
										   bool bShadow);

	// --- EcoR9DemoCamera.cpp: 카메라·키 (옛 관찰 카메라 꼴 — EcoR9DemoCam.h)
	void EnsureCamera();
	void HandleKeys();
	void UpdateCamera(float DeltaTime);
	void DoCamAction(EcoR9DemoCam::EAction Action);
	/** 모드 바꾸기 (대상 고르기 + 다음 프레임 끊어 옮김). Free = EnterFreeCam. */
	void SetCamMode(EEcoR9DemoCam NewMode, const TCHAR* Why);
	/** 자유 카메라로: 지금 화면 카메라 자리·방향 그대로 추적을 푼다. 이미 자유 카메라면 아무 일 없음. */
	void EnterFreeCam(const TCHAR* Why);
	/** 이전·다음 대상 (자동 추적이면 다른 사건). */
	void StepCamSubject(int32 Dir);
	/** 7 · G: 다음 무리 자리 (맵 전체 땅 — 끝에 섬 전체). */
	void CycleCamSite();
	/** 대상 유지: 사라짐·죽음(3 초 머묾)·없음이면 가까운 같은 종 (따라가기), 자동 추적은 사건 고르기. */
	void MaintainCamSubject(double Now);
	void MaintainAuto(double Now, bool bPickNow);
	void UpdateFreeCam(double Dt, APlayerController* PC);
	void BuildCamLines();
	/** 확인용 (-EcoR9CamKeys): 차례가 된 키를 누른다 (HandleKeys 바로 뒤). 꺼짐이면 아무 일 없음. */
	void TickCamKeyPlan(double Now);
	/** 확인용 (-EcoR9CamKeys): 누른 프레임과 그 뒤 3 프레임의 카메라 자리를 기록 줄로 (UpdateCamera 뒤 — 읽기만). */
	void LogCamKeyProbe();
	/** 개체 자리 (보이는 몸이 있으면 그 자리, cm) · 종 · 산가. 없으면 거짓. */
	bool CamWhere(uint32 Id, FVector& Out, uint8* OutSpecies = nullptr, bool* bOutAlive = nullptr) const;
	/** 개체 속도 (프레임 차이, cm/s). */
	FVector CamVelocity(uint32 Id) const;
	/** 그 종(0 사슴 · 1 늑대 · 2 멧돼지)의 산 개체 가운데 From 에 가장 가까운 것 (bPreferRunning 이면 뛰는 것을 먼저 · 같으면 uid 작은 것). 없으면 0. */
	uint32 NearestOfSpecies(uint8 Species, const FVector& From, bool bPreferRunning) const;
	/** 자유 카메라 화면 가운데 그 종(−1 아무 종) 대상 (반각 20° · 300 m — 옛 CenterSubject). 없으면 0. */
	uint32 CenterOfView(int32 Species) const;
	/** 자유 카메라 화면 가운데 땅 (높이 표를 따라 500 m 까지, 없으면 카메라 밑). */
	FVector FreeViewCenter() const;
	/** 대상 없는 보기 자리: 무리 자리 · 섬 전체 · 무대 (가운데 cm · 한 변 cm). 이름은 화면 글. */
	void OverviewRegion(FVector& OutCenter, double& OutSizeCm, FString& OutName) const;
	int32 NumSites() const;
	/** 점에서 가장 가까운 무리 자리 (없으면 0). */
	int32 NearestSite(const FVector& P) const;
	/** 초점→카메라 사이를 막는 보이는 WorldStatic 앞 길이 (옛 ClearArmCm — 트이면 WantCm). */
	double ClearArmCm(const FVector& From, const FVector& Dir, double WantCm) const;
	FVector CamReferencePoint() const;

	TSharedPtr<FEcoR9DemoState> State;

	// 불러온 에셋·클래스 (GC 가 지우지 않게)
	UPROPERTY(Transient) TObjectPtr<UClass> DeerClass;
	UPROPERTY(Transient) TObjectPtr<UClass> WolfClass;
	UPROPERTY(Transient) TObjectPtr<UClass> BoarClass;                  // 멧돼지 표현 BP (찾았을 때 — 사슴·늑대처럼 표현 액터)
	UPROPERTY(Transient) TObjectPtr<UClass> BuffaloClass;               // 동물 세계: 조연우 BP_Buffalo · BP_Leopard · BP_Fox (표현 BP — 없으면 그 종은 먼 표식만)
	UPROPERTY(Transient) TObjectPtr<UClass> LeopardClass;
	UPROPERTY(Transient) TObjectPtr<UClass> FoxClass;
	bool bFaunaAssetsTried = false;                                     // 물소·표범·여우 BP 를 읽어 봤나 (동물 장면이 처음 섰을 때 한 번 — LoadFaunaAssets)
	UPROPERTY(Transient) TObjectPtr<USkeletalMesh> BoarMesh;            // 멧돼지 스켈레탈 메시 (BP 가 없을 때)
	UPROPERTY(Transient) TArray<TObjectPtr<UAnimSequence>> BoarAnims;   // 쓰임(EcoR9Demo::ER9AnimRole)별 애니
	float BoarYawOffset = -90.0f;     // 메시 앞 = +Y 인 팩(AnimalVarietyPack)은 −90° (CREATURE_PRODUCTION_INTEGRATION.md:36)
	float BoarMeshScale = 1.0f;
	double BoarMeshLiftCm = 0.0;
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
