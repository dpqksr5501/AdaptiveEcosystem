#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoV3FilmDirector.generated.h"

class ACameraActor;
struct FEcoV3RegionContext;
namespace EcoV3Observe
{
	struct FSubject;
}

// 통합 v3 촬영 감독 (발표 영상용, 10-16).
//
// 명령줄 -EcoV3Film=<이름> 이 없으면 만들어지지 않는다 (게임·에디터 동작 그대로). 있으면 카메라 하나를 띄워 보기 대상으로 삼고, 장면 목록을
// 따라 카메라를 옮기며, 장면이 도는 동안만 매 프레임 화면을 PNG 로 남긴다. 시뮬레이션은 읽기만 한다 — 사슴·늑대·먹이·난수에 손대지 않는다.
// 같은 시드·지역·카메라·시간 창에서 규칙 스위치만 바꾸면 고치기 전·뒤 영상이 같은 자리에서 시작한다.
//
// 명령줄 (모두 -EcoIntegratedV3 와 함께, -benchmark -fps=30 고정 스텝으로 돌린다)
//   -EcoV3Film=<이름>          출력 폴더 <Out>/<이름>/ (f_00000.png …, shots.json)
//   -EcoV3FilmOut=<폴더>       기본 Saved/EcoV3Film
//   -EcoV3FilmShots=<장면;…>   장면 = 지역,방식,대상,시작초,길이초[,거리m,높이m,방위°,글자0/1]. 시작초 = 시뮬레이션 초 (전역 결정 스텝 × 2/15 초)
//        빈 칸 = 기본값. 글자 = 장면마다 eco.V3Debug 켜고 끄기 (사슴 행동·늑대 상태 글자, 은신처 원 — 그리기만 바뀐다)
//        방식 wide   무대 중심을 비스듬히 내려다봄 (거리·높이 기본 = 한 변 × 0.8·0.45, 방위 45° = 남서쪽에서)
//             top    무대 위에서 곧게 내려다봄 (높이 기본 = 무대가 화면에 들어오는 높이)
//             wolf   대상 = 지역 늑대 번호 (StableAgentId 차례, 0 부터). 고정 거리에서 따라감 (기본 22 m, 높이 16 m, 방위 225°)
//             deer   장면 시작 때 늑대 '대상' 에게 가장 가까운 산 사슴을 잡아 따라감
//             (10-27) wolf·deer 대상과 정찰 기록(scout.csv)은 논리 Mass 개체에서 고른다 (EcoV3Observe::Gather — 관찰 카메라와 같은 찾기).
//             예전에는 팀 표현 액터에서 골랐는데 표현 액터는 보는 자리 200 m 안 가까운 64 마리에게만 생기고(HostVisualDistance·
//             MaxActorRepresentations) 촬영 카메라가 월드 원점(무대에서 300 m+)에서 시작해 대상을 못 찾았다. 자리는 표현 액터가 있으면 그 자리다
//             shelter 대상 = 은신처 원 번호 (FWorldConfig::Covers). 둘레를 천천히 돎 (기본 26 m, 높이 14 m)
//   -EcoV3FilmScout=<초>       촬영 없이 0.5 초마다 늑대별 상태를 scout.csv 로 남기고 그 시뮬레이션 초에 끝낸다 (시간 창 고르기)
//   -EcoV3FilmUI               HUD·화면 메시지·팀 개체 이름표를 숨기지 않는다 (eco.V3Debug 글자는 이것 없이도 그대로 그려진다)
//   -EcoV3FilmNoQuit           마지막 장면 뒤 끝내지 않는다
//   -EcoV3FilmEvery=<n>        장면 동안 n 프레임마다 한 장만 남긴다 (기본 1 = 매 프레임, 장면 길이는 그대로)
//   -EcoV3FilmWatch=<글자;…>   클래스 이름에 이 글자가 든 액터를 캡처마다 watch.txt 에 적는다 (읽기만): 블루프린트 변수 중 참·수·회전,
//        가리키는 컴포넌트(켜짐, 소리 재생·음량, 타임라인 재생·위치, 자리와 카메라까지 거리), 가리키는 액터의 회전. 1 초마다 프레임 벽시계 ms 도 적는다
//
// 단독 촬영 (10-18, 팀 날씨 시험 레벨처럼 통합 조정자가 없는 맵) — -EcoV3FilmStandalone 이 있을 때만:
//   통합 v3 모드 없이 월드 시간(-benchmark -fps=30 이면 프레임 × 1/30 초)으로 돈다. 개체·시뮬레이션·레벨 액터에 손대지 않고 카메라만 옮긴다.
//   -EcoV3FilmShots=<이름,x,y,h,방위°,숙임°,시작초,길이초[,x1,y1,h1];…>
//        x·y = 월드 m, h = 그 자리 땅 위 m (땅 = WorldStatic 맞은 것 중 가장 낮은 것), 방위 0° = +X, 숙임 음수 = 내려다봄.
//        x1·y1·h1 이 있으면 길이초 동안 (x, y, h) 에서 (x1, y1, h1) 로 곧게 옮긴다 (경계 넘기 등)
//   -EcoV3FilmPawn=<m>         플레이어 폰을 매 프레임 카메라 앞 m (음수 = 뒤) 땅 위에 옮겨 둔다 (폰 이동 컴포넌트는 끈다).
//        팀 날씨처럼 폰 자리를 따라가는 연출을 카메라 곁에서 보려고 쓴다. 없으면 폰에 손대지 않는다
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoV3FilmDirectorSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	/** 장면 하나 (명령줄에서 읽는다). */
	struct FShot
	{
		FName RegionId;
		FString Mode;
		int32 Subject = 0;
		double StartSeconds = 0.0;
		double DurationSeconds = 8.0;
		double DistM = -1.0;     // 음수 = 방식 기본값
		double HeightM = -1.0;
		double YawDeg = -1000.0;
		int32 Debug = -1;        // 0·1 = 장면 앞(준비 2 초)에 eco.V3Debug 를 이 값으로 (그리기만 바뀐다), -1 = 그대로
	};

	/** 단독 촬영 장면 하나 (월드 좌표). */
	struct FFreeShot
	{
		FString Tag;
		FVector2D FromM = FVector2D::ZeroVector;   // 월드 m
		FVector2D ToM = FVector2D::ZeroVector;
		double FromH = 2.0;                        // 땅 위 m
		double ToH = 2.0;
		double YawDeg = 0.0;
		double PitchDeg = 0.0;
		double StartSeconds = 0.0;                 // 월드 시간
		double DurationSeconds = 1.0;
		bool bMove = false;
	};

	/** 명령줄 장면 목록 하나를 읽는다 (시험·도구용). 잘못된 장면은 건너뛴다. */
	static TArray<FShot> ParseShots(const FString& Text);
	/** 단독 촬영 장면 목록을 읽는다 (시험·도구용). 잘못된 장면은 건너뛴다. */
	static TArray<FFreeShot> ParseFreeShots(const FString& Text);

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	/**
	 * 지역의 산 개체 (논리 Mass 개체 — EcoV3Observe::Gather, 표현 액터 예산과 무관): 늑대·사슴 모두 StableAgentId 차례.
	 * 자리는 표현 액터가 있으면 그 자리, 없으면 논리 자리. Mass 처리 중이면 거짓 (둘 다 비운다).
	 */
	bool GatherSubjects(FName RegionId, TArray<EcoV3Observe::FSubject>& OutWolves, TArray<EcoV3Observe::FSubject>& OutDeer) const;
	/** 장면 카메라 자리 (cm) 와 방향. 따라갈 대상을 못 찾으면 거짓. */
	bool ComputeView(const FShot& Shot, const FEcoV3RegionContext& Ctx, double ShotTime, FVector& OutLoc, FRotator& OutRot, float& OutFov);
	void EnsureCamera();
	void ApplyViewEnvironment();
	/** 팀 표현 액터 이름표를 보기에서만 숨긴다 (-EcoV3FilmUI 면 그대로). */
	void HideIdentityLabels();
	void CaptureFrame();
	void WriteScoutRows(double SimSeconds);
	void WriteManifest();
	void Finish();
	/** 단독 촬영 한 프레임 (월드 시간 T 초). */
	void TickStandalone(double T);
	/** (x, y) cm 의 땅 높이 cm. 못 찾으면 Fallback. */
	double GroundZ(double XCm, double YCm, double Fallback) const;
	/** -EcoV3FilmWatch 액터 상태 한 줄 (캡처마다). */
	void WriteWatch(double T);
	/** 1 초마다 프레임 벽시계 ms 를 적는다. */
	void NotePerf(double T);

	FString Name;
	FString OutDir;
	TArray<FShot> Shots;
	TArray<FFreeShot> FreeShots;
	TArray<FString> WatchNames;
	double ScoutUntil = -1.0;
	bool bKeepUI = false;
	bool bNoQuit = false;
	bool bStandalone = false;
	bool bMovePawn = false;
	bool bPawnMovementOff = false;
	double PawnAheadM = 0.0;
	int32 Every = 1;
	int32 ShotTicks = 0;             // 이번 장면이 돈 프레임 (Every 와 상관없이)
	double LastGroundZ = 0.0;
	TArray<FString> WatchLines;
	double PerfWallStart = -1.0;     // 이번 1 초 창 시작 벽시계
	double PerfSimStart = -1.0;
	int32 PerfTicks = 0;
	int32 PerfCaptures = 0;

	UPROPERTY(Transient)
	TObjectPtr<ACameraActor> Camera;

	int32 ShotIndex = 0;
	int32 PreparedShot = INDEX_NONE;   // 글자 설정을 적용한 장면
	int32 ShotFrames = 0;            // 이번 장면에서 남긴 프레임
	int32 TotalFrames = 0;           // 모든 장면 프레임 (파일 번호)
	int64 LockedId = 0;              // 이번 장면이 따라가는 개체 (wolf·deer)
	FVector LastTarget = FVector::ZeroVector;   // 따라가는 개체의 마지막 자리 (죽거나 사라지면 카메라가 거기 머문다)
	bool bLocked = false;
	int32 QuitCountdown = -1;        // 마지막 캡처 뒤 파일 쓰기를 기다리는 프레임
	double NextScout = 0.0;
	bool bEnvApplied = false;
	TArray<FString> ScoutLines;
	TArray<FString> ManifestShots;   // 장면마다 JSON 한 덩이
	double ShotFirstSim = -1.0;
	double ShotLastSim = -1.0;
	int32 ShotFirstFrame = 0;
	int32 ShotStartAlive = 0;
	int64 ShotStartCaught = 0;
	int64 ShotStartStarved = 0;
};
