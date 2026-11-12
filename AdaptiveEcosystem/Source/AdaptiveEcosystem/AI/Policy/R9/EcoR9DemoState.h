// R9 데모 플레이어 — 서브시스템 안쪽 상태 (EcoR9DemoSubsystem / Visuals / Camera .cpp 가 같이 씀). 공개 API 아님.

#pragma once

#include "CoreMinimal.h"
#include "EcoR9DemoFrame.h"
#include "EcoR9DemoLiveSource.h"
#include "EcoR9DemoSubsystem.h"
#include "UObject/WeakObjectPtrTemplates.h"

#include <memory>

class AEcoCreatureRepresentationActor;
class UInstancedStaticMeshComponent;
class USceneComponent;
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
}

enum class EEcoR9DemoPhase : uint8
{
	Off,
	Refused,
	WaitScan,    // 선호점 둘레를 불러오는 중 (훑기 전)
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
	Top = 5
};

/** 보이는 몸 하나 (R9 uid 하나). */
struct FEcoR9DemoBody
{
	uint32 Id = 0;
	uint8 Species = 0;
	TWeakObjectPtr<AEcoCreatureRepresentationActor> Rep;   // 사슴·늑대
	TWeakObjectPtr<AActor> Boar;                            // 멧돼지 자리표시
	TWeakObjectPtr<USceneComponent> BoarPivot;
	TWeakObjectPtr<USceneComponent> BoarHead;
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

struct FEcoR9DemoState
{
	FEcoR9DemoSettings Settings;
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
};
