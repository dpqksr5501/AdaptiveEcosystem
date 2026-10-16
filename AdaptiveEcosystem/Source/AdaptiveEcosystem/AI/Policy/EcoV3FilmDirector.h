#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoV3FilmDirector.generated.h"

class ACameraActor;
class AEcoCreatureRepresentationActor;
struct FEcoV3RegionContext;

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
//             shelter 대상 = 은신처 원 번호 (FWorldConfig::Covers). 둘레를 천천히 돎 (기본 26 m, 높이 14 m)
//   -EcoV3FilmScout=<초>       촬영 없이 0.5 초마다 늑대별 상태를 scout.csv 로 남기고 그 시뮬레이션 초에 끝낸다 (시간 창 고르기)
//   -EcoV3FilmUI               HUD·화면 메시지를 숨기지 않는다 (eco.V3Debug 글자는 이것 없이도 그대로 그려진다)
//   -EcoV3FilmNoQuit           마지막 장면 뒤 끝내지 않는다
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

	/** 명령줄 장면 목록 하나를 읽는다 (시험·도구용). 잘못된 장면은 건너뛴다. */
	static TArray<FShot> ParseShots(const FString& Text);

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	/** 지역의 표현 액터 (산 것만): 늑대는 StableAgentId 차례. */
	void GatherActors(FName RegionId, TArray<AEcoCreatureRepresentationActor*>& OutWolves, TArray<AEcoCreatureRepresentationActor*>& OutDeer) const;
	AEcoCreatureRepresentationActor* FindById(int64 Id) const;
	/** 장면 카메라 자리 (cm) 와 방향. 따라갈 대상을 못 찾으면 거짓. */
	bool ComputeView(const FShot& Shot, const FEcoV3RegionContext& Ctx, double ShotTime, FVector& OutLoc, FRotator& OutRot, float& OutFov);
	void EnsureCamera();
	void ApplyViewEnvironment();
	void CaptureFrame();
	void WriteScoutRows(double SimSeconds);
	void WriteManifest();
	void Finish();

	FString Name;
	FString OutDir;
	TArray<FShot> Shots;
	double ScoutUntil = -1.0;
	bool bKeepUI = false;
	bool bNoQuit = false;

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
