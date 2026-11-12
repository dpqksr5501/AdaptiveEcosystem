// R9 데모 플레이어 — 서브시스템 안쪽 상태 (EcoR9DemoSubsystem / Visuals / Camera .cpp 가 같이 씀). 공개 API 아님.

#pragma once

#include "CoreMinimal.h"
#include "EcoR9DemoFrame.h"
#include "EcoR9DemoLiveSource.h"
#include "EcoR9DemoSubsystem.h"
#include "EcoR9DemoWhole.h"
#include "UObject/WeakObjectPtrTemplates.h"

#include <memory>

class AEcoCreatureRepresentationActor;
class APawn;
class UInstancedStaticMeshComponent;
class USceneComponent;
class USkeletalMeshComponent;
class UWorldPartitionStreamingSourceComponent;

DECLARE_LOG_CATEGORY_EXTERN(LogEcoR9Demo, Log, All);

/** 콘솔 값 읽기 (정의는 EcoR9DemoSubsystem.cpp — 파일 셋이 같은 값을 본다). */
namespace EcoR9DemoCVars
{
	int32 Cam();          // eco.R9Demo.Cam : 0 자동 · 1 전체 · 2 사슴 · 3 늑대 · 4 멧돼지 · 5 위
	float Speed();        // eco.R9Demo.Speed : 시간 배율 (0 = 멈춤)
	bool Text();          // eco.R9Demo.Text : 작은 글자
	bool HpBars();        // eco.R9Demo.HpBars : 다친 늑대·멧돼지 체력 막대 (실시간 판)
	bool Grass();         // eco.R9Demo.Grass : 보이는 풀
	bool Loop();          // eco.R9Demo.Loop : 재생 끝·실시간 다시 시작 스텝에서 처음부터
	int32 RestartSteps(); // eco.R9Demo.RestartSteps : 실시간 판을 새 시드로 다시 시작하는 스텝 (학습 세계는 5,000 스텝마다 바뀜)
	FString Bodies();     // eco.R9Demo.Bodies : jyu (조연우 BP) · team (팀 BP)
	bool Daylight();      // eco.R9Demo.Daylight : 팀 하늘의 해 돌기를 데모 동안만 멈추고 낮에 둠
	void SetText(bool bOn);
	void SetCam(int32 Mode);
	// 맵 전체 땅 모드 (2026-11-13)
	bool HideOthers();    // eco.R9Demo.HideOthers : 맵에 있던 예전 v3·Fauna 동물 몸·먼 표식을 데모 동안 숨김 (보이는 것만 — 그쪽 시뮬레이션은 그대로)
	float BodyNearM();    // eco.R9Demo.BodyNear : 카메라에서 이만큼(m) 안 개체만 몸 액터 (나머지는 작은 표식)
	int32 BodyBudget();   // eco.R9Demo.BodyBudget : 몸 액터 상한
	float GrassRadiusM(); // eco.R9Demo.GrassRadius : 큰 세계에서 풀을 그리는 카메라 둘레 반 변 (m)
	FString BoarMesh();   // eco.R9Demo.BoarMesh : 멧돼지 몸 덮어쓰기 (스켈레탈 메시 또는 표현 BP 경로)
}

enum class EEcoR9DemoPhase : uint8
{
	Off,
	Refused,
	WaitScan,    // 자리 찾기: 시작점 둘레(고리 ScanRing)를 불러오는 중 (훑기 전)
	WaitWhole,   // 맵 전체 땅: 맵 땅을 불러오는 중 (훑기 전)
	WaitStage,   // 무대 자리를 불러오는 중
	Running,
	Failed
};

enum class EEcoR9DemoCam : uint8
{
	Auto = 0,
	Wide = 1,
	FollowDeer = 2,
	FollowWolf = 3,
	FollowBoar = 4,
	Top = 5,
	Site = 6     // 무리 자리 하나 (키 7 = 다음 자리)
};

/** 보이는 몸 하나 (R9 uid 하나). */
struct FEcoR9DemoBody
{
	uint32 Id = 0;
	uint8 Species = 0;
	TWeakObjectPtr<AEcoCreatureRepresentationActor> Rep;   // 사슴·늑대
	TWeakObjectPtr<AActor> Boar;                            // 멧돼지 자리표시 또는 스켈레탈 몸
	TWeakObjectPtr<USceneComponent> BoarPivot;
	TWeakObjectPtr<USceneComponent> BoarHead;
	TWeakObjectPtr<USkeletalMeshComponent> BoarSkel;        // 멧돼지 스켈레탈 몸 (돼지 메시를 찾았을 때 — 애니는 상태별 한 마디 재생)
	uint8 BoarAnim = 0;                                     // 지금 재생 중인 애니 쓰임 (EcoR9Demo::ER9AnimRole)
	FName VisualSpecies;
	int64 Sequence = 0;
	bool bSnapNext = true;
	bool bDead = false;
	double DeadAt = 0.0;
	FVector2D CorpseUnits = FVector2D::ZeroVector;
	float CorpseYaw = 0.0f;
	float CorpseFrac = 1.0f;
	double RemoveAt = -1.0;
	double AttackUntil = -1.0;   // 늑대 물기 자세
	double RearUntil = -1.0;     // 멧돼지 받아치기 (자리표시 몸 들기)
	float Scale = 1.0f;
	float Maturity = 1.0f;
	float BoarYaw = 0.0f;
	float BobPhase = 0.0f;
	FVector LastLocation = FVector::ZeroVector;
};

/** 짧은 표시 (작은 점 — 번쩍임·소리 없음). */
struct FEcoR9DemoMarker
{
	int32 Kind = 0;            // 0 물림(빨강) · 1 받아침(주황) · 2 굶음(회색)
	uint32 FollowId = 0;       // 그 몸 위에 둔다 (0 = 고정 자리)
	FVector Location = FVector::ZeroVector;
	double Until = 0.0;
};

/** 최근 사건 (카메라·글자). */
struct FEcoR9DemoRecent
{
	double Time = 0.0;
	EcoR9Demo::ER9Event Kind = EcoR9Demo::ER9Event::BiteKill;
	uint32 A = 0;
	uint32 B = 0;
};

/** 4 m 훑기 셈 (기록 줄). */
struct FEcoR9ScanCounts
{
	int32 FromLand = 0;
	int32 FromMesh = 0;
	int32 NoGround = 0;
	int32 Sea = 0;
	int32 Water = 0;
	int32 Steep = 0;
	int64 Objects = 0;
	int64 Trees = 0;
	int64 Rocks = 0;
};

struct FEcoR9DemoState
{
	FEcoR9DemoSettings Settings;
	int32 Starts = 0;            // 이 월드에서 시작한 횟수 (Play 중 켜기/끄기 — 두 번 만들지 않음 시험)
	bool bWorldBegan = false;    // OnWorldBeginPlay 를 지났다 (그 순간에는 UWorld::HasBegunPlay 가 아직 거짓 — 게임 모드 StartPlay 앞)
	EEcoR9DemoPhase Phase = EEcoR9DemoPhase::Off;
	double PhaseStart = 0.0;
	FString Why;

	// 프레임 원천
	EcoR9Demo::FR9WorldInfo Info;
	std::unique_ptr<EcoR9Demo::FR9LiveSource> Live;
	EcoR9Demo::FR9Replay Replay;
	int32 ReplayCursor = 0;
	bool bFoodKnown = false;     // 먹이 격자·사체를 안다 (실시간, 또는 재생 + .r9fd)
	bool bEventsKnown = false;   // 사건을 안다 (실시간, 또는 재생 + .events.json)
	EcoR9Demo::FR9Frame Prev;
	EcoR9Demo::FR9Frame Cur;
	bool bHavePrev = false;
	double Accum = 0.0;
	double Alpha = 0.0;
	int64 StepsShown = 0;        // 이번 판에서 보여 준 스텝
	int32 RunIndex = 0;          // 다시 시작한 횟수
	double SimSeconds = 0.0;

	// 무대
	EcoR9Demo::FR9StageMap Map;
	EcoR9Demo::FR9HeightTable Heights;
	FVector StageCenter = FVector::ZeroVector;   // z = 무대 평균 높이
	FString StageLine;
	TWeakObjectPtr<UWorldPartitionStreamingSourceComponent> Streamer;
	TWeakObjectPtr<AActor> Decor;

	// 자리 찾기 (맵 제한 없음 — 맵마다 설정 없이 그 맵에서 고른다)
	int32 ScanRing = 0;                          // 지금 훑는 고리 (0 = 200 m · 1 = 400 m · 2 = 800 m)
	FVector SearchOrigin = FVector::ZeroVector;  // 시작점 (cm): 플레이어 몸 → PlayerStart → 시점 → 원점
	FString OriginLabel;                         // 시작점이 어디서 왔나 (기록 줄)
	int32 NumAvoid = 0;                          // 피한 기존 생태 상자 수 (마지막 훑기)
	TArray<TWeakObjectPtr<AActor>> ProbeIgnore;  // 바닥 선 검사에서 뺄 액터 (물 몸체 — 바다 충돌 상자가 바닥처럼 잡히지 않게)

	// 맵에 이미 있는 팀 생태 (거부하지 않고 건드리지 않는다 — 알리기만)
	bool bTeamEco = false;
	FString TeamEcoNote;

	// 맵 전체 땅 모드 (eco.R9Demo.Area 0 = 맵 전체 · > 120 = 시작점 둘레 그 크기)
	bool bWhole = false;                         // 이번 판은 큰 세계 (땅 지도 + 큰 세계 장면 생성기)
	FBox AreaBox = FBox(ForceInit);              // 훑는 사각 (cm)
	FString AreaLine;                            // 어디서 왔나 (기록 줄)
	std::shared_ptr<const EcoR9Demo::FR9WholeSpec> WholeSpec;   // 훑은 땅 지도 (다시 시작할 때 그대로 다시 쓴다 — 다시 훑지 않음)
	FVector WholeCenter = FVector::ZeroVector;   // 땅 지도 정사각 가운데 (cm)
	FBox LandBox = FBox(ForceInit);              // 열린 땅 경계 (cm) — 카메라 2 (섬 전체)
	FString WholeLine;                           // 훑기 기록 줄
	int32 SiteIndex = 0;                         // 카메라 7: 지금 보는 무리 자리
	// 풀 그리기 창 (큰 세계 — 카메라 둘레 칸만)
	EcoR9Demo::FR9FoodWindow FoodWin;
	std::vector<float> WinGrass;
	std::vector<float> WinRoot;
	std::vector<float> WinPrevRoot;
	TArray<int16> WinQuant;                      // 창 칸마다 그린 풀 양 (0..64, −1 숨김, −2 아직)
	bool bWinPrevValid = false;
	// 몸 배정 (큰 세계: 카메라에 가까운 개체만 몸, 나머지는 작은 표식)
	TWeakObjectPtr<UInstancedStaticMeshComponent> FarIsm[3];
	int32 NumFar = 0;
	int32 NumBodyActors = 0;
	// 프레임 색인 (uid → 프레임 안 번호)
	TMap<uint32, int32> CurIndex;
	TMap<uint32, int32> PrevIndex;
	// 숨긴 예전 동물 (eco.R9Demo.HideOthers) — 끌 때 되돌린다
	TArray<TWeakObjectPtr<AActor>> HiddenOthers;
	TArray<TWeakObjectPtr<USceneComponent>> HiddenComps;
	double NextHide = 0.0;
	// 멧돼지 몸
	FString BoarLine;
	// 결정 비용 (기록 줄)
	double AdvanceMsSum = 0.0;
	int32 AdvanceCount = 0;
	// 확인용 (11-13 빌드·확인): 실제 프레임 간격·데모 틱 일 시간 (10 초 기록 줄마다 다시 셈, 읽기만)
	double FrameLastReal = 0.0;
	double FrameMsSum = 0.0;
	double FrameMsMax = 0.0;
	double TickMsSum = 0.0;
	double TickMsMax = 0.0;
	int32 FrameCount = 0;

	// 보이는 것
	TMap<uint32, FEcoR9DemoBody> Bodies;
	TWeakObjectPtr<UInstancedStaticMeshComponent> GrassIsm;
	TWeakObjectPtr<UInstancedStaticMeshComponent> DugIsm;
	TWeakObjectPtr<UInstancedStaticMeshComponent> MarkIsm[3];
	TArray<FTransform> TuftBase;     // 풀 덩어리 자리 (셀 × 5, 크기 1)
	TArray<double> DugUntil;         // 셀마다 판 자국이 사라지는 때
	bool bDugShown = false;          // 판 자국이 하나라도 보이는 중 (아무것도 없으면 스텝마다 900 개를 다시 쓰지 않는다)
	float GrassCapMax = 1.0f;
	bool bGrassHidden = false;
	TArray<FEcoR9DemoMarker> Markers;
	TArray<FEcoR9DemoRecent> Recent;

	// 누계 (이번 판)
	int32 DeerKilled = 0;
	int32 BoarKilled = 0;
	int32 BoarWounded = 0;
	int32 Counters = 0;
	int32 WolvesKilled = 0;
	int32 Starved = 0;
	int32 Respawns = 0;
	int32 Eats[3][4] = {};       // 실제로 먹은 개체·스텝 [종][먹이 + 1] (0 = 모름 — 재생 판, 1 풀 · 2 땅속 · 3 고기 = 사체). 기록 줄 셈용

	// 카메라
	EEcoR9DemoCam CamMode = EEcoR9DemoCam::Auto;
	int32 LastCamCVar = -1;
	bool bAutoFollowing = false;
	double CamModeSince = 0.0;
	double LastInterest = 0.0;
	double NextPick = 0.0;
	uint32 FollowA = 0;
	uint32 FollowB = 0;
	FString CamLabel;
	FString CamWhat;             // 자동 추적 대상이 하는 일 (글자용)
	bool bCamInit = false;
	FVector CamFocus = FVector::ZeroVector;
	FVector CamFocusVel = FVector::ZeroVector;
	double CamYaw = 225.0;
	double CamYawVel = 0.0;
	double CamArm = 4000.0;
	double CamArmVel = 0.0;
	double CamHeight = 2000.0;
	double CamHeightVel = 0.0;

	// 글자
	FDelegateHandle DrawHandle;

	// 녹화·끝내기
	bool bCaptureDone = false;
	double CaptureClock = -1.0;     // 녹화 시작 뒤 흐른 월드 초 (<0 = 아직)
	bool bShaderWaitLogged = false; // 녹화 전 셰이더 기다림을 한 번 적었다
	int32 CaptureFrames = 0;
	int32 QuitCountdown = -1;
	double RunningSince = 0.0;
	double NextLog = 0.0;

	// 보기 환경
	bool bEnvApplied = false;
	int32 PrevCamEnable = MIN_int32;
	bool bPawnFrozen = false;   // 무대를 불러오는 동안 폰이 원점 땅 밑으로 떨어지거나 팀 날씨 트리거에 닿지 않게 먼저 멈춤
	bool bPawnParked = false;
	TWeakObjectPtr<APawn> FrozenPawn;   // 끌 때 되돌릴 폰 (Play 중 끄기)
	bool bPawnWasHidden = false;
	bool bPawnHadCollision = true;
	bool bPawnMoveWasActive = true;
	FVector PawnStart = FVector::ZeroVector;
	bool bHudHidden = false;
	FString PrevRes;   // 녹화 전 해상도 명령 (끝날 때 되돌림)
	int8 PrevOnScreenMsgs = -1;   // 녹화 동안 화면 메시지를 끈 앞 값 (-1 = 안 바꿈, 끝날 때 되돌림)

	// 팀 하늘 (eco.R9Demo.Daylight): BP_SkyManager 의 해 돌기를 데모 동안만 멈추고 낮에 둔다. 저장하지 않고 끝날 때 해 속도를 되돌린다
	TWeakObjectPtr<AActor> Sky;
	bool bSkySearched = false;
	bool bSkyHeld = false;
	bool bSkyLogged = false;      // '해를 못 찾음' 을 적었다
	bool bSunLogged = false;      // '해를 낮에 고정' 을 적었다
	double PrevSunSpeed = 0.0;
	int32 SunSpeedKind = 0;       // 0 못 찾음 · 1 double · 2 float

	/** 프레임에서 uid 로 찾기 (색인 — 개체가 수백이라 선형 찾기를 피한다). */
	const EcoR9Demo::FR9Agent* FindCur(uint32 Id) const
	{
		const int32* I = CurIndex.Find(Id);
		return I && Cur.Agents.size() > static_cast<std::size_t>(*I) ? &Cur.Agents[static_cast<std::size_t>(*I)] : nullptr;
	}
	const EcoR9Demo::FR9Agent* FindPrev(uint32 Id) const
	{
		const int32* I = PrevIndex.Find(Id);
		return I && Prev.Agents.size() > static_cast<std::size_t>(*I) ? &Prev.Agents[static_cast<std::size_t>(*I)] : nullptr;
	}
	void RebuildIndex()
	{
		PrevIndex = MoveTemp(CurIndex);
		CurIndex.Reset();
		CurIndex.Reserve(static_cast<int32>(Cur.Agents.size()));
		for (std::size_t i = 0; i < Cur.Agents.size(); ++i)
		{
			const EcoR9Demo::FR9Agent& A = Cur.Agents[i];
			int32& Slot = CurIndex.FindOrAdd(A.Id, static_cast<int32>(i));
			if (A.Alive())
			{
				Slot = static_cast<int32>(i);   // 같은 uid 가 죽은 기록과 산 기록 둘이면 (없어야 함) 산 쪽
			}
		}
	}
	void RebuildBothIndex()
	{
		RebuildIndex();
		PrevIndex.Reset();
		for (std::size_t i = 0; i < Prev.Agents.size(); ++i)
		{
			PrevIndex.FindOrAdd(Prev.Agents[i].Id, static_cast<int32>(i));
		}
	}
};
