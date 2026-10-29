// 관찰 카메라 (10-27 사용자 '카메라가 느려서 행동 관찰이 어렵다 → 늑대 시점·사슴 시점·탑·쿼터뷰로 행동을 잘 따라가는 단축키').
//
// 보기만 바꾼다 — 사슴·늑대·먹이·난수·Mass 조각·플레이어 폰에 쓰지 않는다 (Mass 읽기도 지연 명령을 비우지 않는다). 로컬 플레이어 화면마다 따로 돈다(단독·리슨 서버·클라이언트, 데디케이티드 서버는 없음).
// 다만 보는 자리(PlayerController view point)를 옮기므로, 그 자리를 읽는 엔진·팀 코드는 플레이어가 카메라를 옮길 때처럼 따라 바뀐다:
// 팀 종 AI 결정 간격 단계(EcoSpeciesAIInputProcessor — 통합 v3 Native 세계는 읽지 않는다)·표현 액터 예산·복제 관련도·World Partition 스트리밍 원천.
// 관찰 중(1~5 모드와 자유 카메라)에는 로컬 플레이어 컨트롤러의 이동 입력만 막는다 (10-27 사용자 결정 — 안 보이는 폰이 WASD 로 걸어 발소리 Player.Footstep 를 사슴이 듣지 않게).
//   이동 무시 수(AController::SetIgnoreMoveInput — 쌓인다)를 하나 더하고, 원래 카메라(자유 카메라에서 0·eco.Cam.Player)·eco.Cam.Enable 0·eco.Cam.BlockMove 0·월드 닫기에서 그 하나만 뺀다.
//   폰 자체(자리·속도·부품)에는 쓰지 않는다 — 누르던 중이면 폰의 제동으로 멈춘다. 시야(마우스)·점프·F(플레이어 치기)·Shift·Ctrl 은 그대로.
// 자유 카메라 (10-29 사용자 '1·2 로 따라가다 0 을 누르면 그 자리에서 추적이 풀려 바로 직접 움직이게'): 관찰 중(1~5) 0 = 지금 카메라 자리·방향 그대로 추적을 푼다.
//   W A S D (방향키도) = 보는 방향 기준 앞뒤(숙임 포함)·옆, Q·E = 아래·위(세계 위), 마우스 = 시야(컨트롤러 방향이 바뀐 만큼 — 컨트롤러 방향에는 쓰지 않는다),
//   Shift = 4 배 빠르게, - = 휠 = 이동 속도. 폰은 그대로 서 있고 이동 입력 막기도 그대로다 (WASD 가 폰을 걷게 하지 않는다). 땅 2 m 위 밑으로 가지 않는다.
//   자유 카메라에서 0 을 한 번 더 = 원래 카메라(폰). 1~5 = 그 자리에서 다시 그 모드 (화면 가운데 가까운 대상 — EcoV3Observe::CenterSubject, 없으면 지금 규칙).
//   Q·E 는 팀·기본 입력이 쓰지 않는다 (Space = 점프·Ctrl = 살금살금은 팀 키라 위아래로 쓰지 않았다). Shift·WASD·방향키는 자유 카메라에서만 누른 채로 읽는다.
// 촬영 감독(-EcoV3Film=)이 도는 실행에는 만들지 않는다 — 촬영 카메라와 보기 대상을 다투지 않고, 촬영 프레임(-EcoV3FilmUI 포함)이 전과 같다.
//   1. 카메라 액터 하나를 띄워 첫 로컬 플레이어 컨트롤러의 보기 대상으로 삼는다. 0 (eco.Cam.Player) 이면 원래 폰으로 돌려준다.
//   2. 대상 찾기 = EcoV3Observe::Gather: 논리 Mass 개체(통합 개체 꼬리표)를 읽는다 — 팀 표현 액터는 보는 자리 200 m 안 가까운 64 마리에게만
//      생기므로(AEcoCreatureIntegrationSpawner::HostVisualDistance·MaxActorRepresentations), 표현 액터로만 찾으면 멀리 있는 대상을 못 고른다.
//      자리는 표현 액터(팀 BP_EcoDeer/Wolf, JYU BP_JYU_Deer/Wolf — 모두 AEcoCreatureRepresentationActor 하위)가 있으면 그 자리(화면과 같다),
//      없으면 논리 자리다. 카메라가 대상 곁으로 가면 팀 표현이 그 곁 개체에게 액터를 붙인다.
//      상태: 서버·단독 통합 v3 = 지역 세계의 행동·도주 덮기·두 길·늑대 상태(EcoPolicyV3IntegratedSubsystem 의 위협 설정), 그 밖(클라이언트·v1) = 팀 표현 활동 값.
//   3. 부드러운 따라가기: 초점·방위·숙임·거리를 임계 감쇠(EcoV3Observe::SmoothDamp)로 옮기고 초점은 대상 속도 × 시간 상수만큼 앞을 본다
//      — 9 m/s 로 뛰는 늑대도 따라잡는다(정상 상태 뒤처짐 0). 150 m 넘게 건너뛰면(지역 바꾸기) 끊어 옮긴다. 카메라는 땅 2 m 위 밑으로 가지 않는다.
//      초점→카메라 사이가 막히면(보이는 WorldStatic 물체 — 바위·지형·줄기) 그 앞으로 바로 당기고 트이면 천천히 편다(EcoV3Observe::ArmStep).
//      잎에 충돌이 없는 나무는 이 화면에서만 숨긴다(EcoV3Observe::IsOccluderBox — PlayerController 숨김 목록, 원래 카메라로 돌아가면 되돌린다). 움직임 흐림은 끈다.
//   4. 화면 글: 오른쪽 위 묶음 하나(어두운 반투명 바탕·흰 글자, UDebugDrawService "Game" — HUD 위 디버그 캔버스).
//      위 = 단축키 목록(H 로 숨기기/보이기 — 숨겨도 맨 윗줄 'H 단축키 보이기'는 남는다), 아래 = 모드·대상(종·id·지역)·상태·가장 가까운 늑대(사슴이면)·
//      사슴(늑대면) 거리. 통합 개체가 있는 월드에서는 원래 카메라일 때도 늘 보인다(개체가 없는 레벨에는 볼 것이 없어 그리지 않는다 — 1 초마다 다시 본다).
//      왼쪽 위(두뇌 교체 알림·상태 줄)와 팀 ECO INSPECTOR(왼쪽 위, x 15~655 px)를 비켜 오른쪽에 붙이고, 팀 HERD MIGRATION 판(오른쪽 위)이 보이면
//      그 밑(안 들어가면 왼쪽 옆)에 둔다. 1280×720 에서도 잘리지 않게 글 배율을 줄인다(EcoV3Observe::LayoutPanel). HUD 를 숨기면(showhud) 같이 숨는다.
//
// 단축키 (PlayerController 키 상태 WasInputKeyJustPressed — 프로젝트 Enhanced Input 매핑은 그대로. 콘솔 입력 중에는 반응하지 않는다.
// 팀 키 Tab·R·M·[ ]·마우스 가운데(JYU 검사 HUD·무리 이주 판), F·Shift·Ctrl(플레이어), WASD·Space·방향키(기본 입력)와 겹치지 않게 골랐다 — EcoV3Observe::Keys):
//   1 늑대 시점(뒤에서 따라감, 다시 누르면 다음 늑대)  2 사슴 시점(다시 누르면 다음 사슴)  3 탑뷰(대상 위, 대상 없으면 지역 무대 전체)
//   4 쿼터뷰(대상 기준 45° 사선)  5 자동 추적(쫓기는 사슴·사냥 중인 늑대 — 사건이 끝나면 다음)  , . 이전·다음 대상  - = 또는 휠 줌
//   G 지역 바꾸기(자유 카메라면 그 지역 무대 전체가 보이는 자리로)  0 관찰 중 = 그 자리에서 추적 풀기(자유 카메라), 자유 카메라 = 원래 카메라로
//   (원래 카메라일 때 0 은 아무 일 없음)  H 단축키 목록 숨기기/보이기
// 콘솔 (시험·촬영용): eco.Cam.Wolf [id] · Deer [id] · Top · Quarter · Auto · Next · Prev · Zoom <m> · Region <이름> · Player(바로 폰으로) · Help,
//   Free (지금 보는 자리에서 자유 카메라 — 원래 카메라에서도) · Speed <m/s> (자유 카메라 이동 속도) · Status (지금 상태 한 줄),
//   콘솔 변수 eco.Cam.Enable (기본 1 — 0 이면 키·화면 글을 끄고 원래 카메라로), eco.Cam.HudScale (기본 1, 화면 글 배율),
//   eco.Cam.BlockMove (기본 1 — 관찰 중 플레이어 이동 입력 막기, 0 이면 막지 않는다).
// 문서: AdaptiveEcosystem/Docs/RL_Policy/OBSERVER_CAMERA.md

#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"
#include "Core/EcoActivityTypes.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "InputCoreTypes.h"
#include "Math/Box2D.h"
#include "Subsystems/WorldSubsystem.h"
#include "Templates/Function.h"

#include "EcoV3ObserverCamera.generated.h"

class ACameraActor;
class AEcoCreatureRepresentationActor;
class APlayerController;
class UCanvas;
class UPrimitiveComponent;

DECLARE_LOG_CATEGORY_EXTERN(LogEcoV3Cam, Log, All);

/** 관찰 카메라 찾기·고르기·따라가기 도우미 (촬영 감독 EcoV3FilmDirector 도 같은 찾기를 쓴다). 읽기만 한다. */
namespace EcoV3Observe
{
	/** 화면 글 상태 (사슴: 먹기·경계·도망(트인 쪽/은신처)·웅크림…, 늑대: 배회·사냥·먹기·쉼). */
	enum class EState : uint8
	{
		Unknown,
		Eat,          // 사슴 먹기
		Alert,        // 경계 (먹으며 멀어짐)
		KeepAway,     // 거리 두기 (쉬는 늑대 시야 밖으로 걸어 물러남 — 10-27 덮기 EcoWorldV3::kKeepRest)
		Flee,         // 도망 (반사 도주·두뇌 도망 — 길 없음)
		FleeOpen,     // 도망(트인 쪽) — 두 길 두뇌 RUN
		FleeShelter,  // 도망(은신처) — 두 길 두뇌 SHELTER
		Hide,         // 숨으러 감 (HIDE 가는 중)
		Crouch,       // 웅크림 (은신처 안)
		Freeze,       // 얼기
		Sleep,        // 사슴 잠
		Travel,       // 이동 (무리 이주·걷기)
		Roam,         // 늑대 배회 (깨는 중 포함)
		Hunt,         // 늑대 사냥 (잠행·돌진·추격·지침)
		WolfEat,      // 늑대 먹기
		Rest,         // 늑대 쉼 (잠·눕는 중·배부름)
		Dead,
		Count
	};

	ADAPTIVEECOSYSTEM_API const TCHAR* StateNameKo(EState S);
	/** 쫓기는 사슴 상태인가 (도망·도망(트인 쪽)·도망(은신처)). */
	ADAPTIVEECOSYSTEM_API bool IsChased(EState S);
	/** 사냥 중인 늑대 상태인가. */
	inline bool IsHunting(EState S) { return S == EState::Hunt; }

	/**
	 * 통합 v3 사슴 상태 (EcoV3Integrated::DeerLabel 과 같은 판정): 도주 반사 덮기(KeepMode)가 먼저 — 도주는 고른 길(ShownRoute)로 트인 쪽·은신처,
	 * 웅크림, 경계·거리 두기(쉬는 늑대, 10-27)(두뇌가 먹기일 때만). 덮기가 없으면 두뇌 행동(먹기·도망·숨기(도착이면 웅크림)·얼기·잠).
	 */
	ADAPTIVEECOSYSTEM_API EState DeerStateV3(int32 Behavior, bool bArrived, int32 KeepMode, int32 ShownRoute);
	/** 통합 v3 늑대 상태: EcoV3Integrated::EWolfState 번호(0 배회 … 8 깨는 중)와 배부름(야생 포만 — 자지 않는 동안) → 배회·사냥·먹기·쉼. */
	ADAPTIVEECOSYSTEM_API EState WolfStateV3(int32 WolfState, bool bSated);
	/** 팀 표현 활동 값(EEcoSpeciesActivity — 클라이언트·v1 도 받는다) → 상태. */
	ADAPTIVEECOSYSTEM_API EState StateFromActivity(bool bWolf, EEcoSpeciesActivity Activity);

	/** 개체 하나 (복사본 — 월드 상태를 가리키지 않는다). */
	struct FSubject
	{
		int64 Id = 0;
		bool bWolf = false;
		bool bAlive = true;
		bool bEating = false;      // 표현 깃발 (팀 '먹는 중')
		bool bPursuing = false;    // 표현 깃발 (팀 '쫓는 중')
		bool bHasActor = false;    // 표현 액터가 지금 붙어 있다
		FName Region;
		FVector Location = FVector::ZeroVector;   // cm. 표현 액터가 있으면 그 자리, 없으면 논리 자리
		FVector Velocity = FVector::ZeroVector;   // cm/s
		float YawDeg = 0.0f;                      // 몸 방향
		EState State = EState::Unknown;
		FString Detail;                           // '잠행형'·'식사 3.2초'·'배부름 42초'·'에너지 64%' 같은 덧말 (없으면 빈 글)
		EEcoCreatureVisualMotion Motion = EEcoCreatureVisualMotion::Idle;   // 표현 동작 (액터가 없으면 같은 문턱으로 셈)
		// 같은 지역 이웃 (FillNeighbors)
		int64 NearestWolfId = 0;    double NearestWolfCm = -1.0;       // 사슴: 가장 가까운 산 늑대
		int64 NearestHuntWolfId = 0; double NearestHuntWolfCm = -1.0;  // 사슴: 가장 가까운 사냥 중인 늑대
		int64 NearestDeerId = 0;    double NearestDeerCm = -1.0;       // 늑대: 가장 가까운 산 사슴
	};

	/** 지역 하나 (무대 중심·한 변). 통합 v3 서버·단독은 무대, 그 밖은 그 지역 개체의 둘레 상자. */
	struct FRegionInfo
	{
		FName Id;
		FVector CenterCm = FVector::ZeroVector;
		double SizeCm = 0.0;
		bool bStage = false;
	};

	/**
	 * 월드의 통합 개체를 모두 읽는다 (논리 Mass 개체 — 표현 액터 예산과 무관). id 차례로 돌려주고 이웃(FillNeighbors)까지 채운다.
	 * 클라이언트에서 아직 표본을 못 받은 개체(FEcoClientPresentationFragment::bHasSample 거짓)는 자리가 없어 뺀다 (팀 표현과 같다).
	 * Mass 처리 중이거나 엔티티 관리자가 없으면 거짓 (Out 은 비운다). 읽기만 한다. 촬영 감독 wolf·deer 장면도 이것으로 고른다.
	 */
	ADAPTIVEECOSYSTEM_API bool Gather(UWorld& World, TArray<FSubject>& Out);
	/** 같은 지역 이웃 거리 (산 개체만). */
	ADAPTIVEECOSYSTEM_API void FillNeighbors(TArray<FSubject>& Subjects);
	/** 지역 목록 (이름 순). */
	ADAPTIVEECOSYSTEM_API void GatherRegions(UWorld& World, TConstArrayView<FSubject> Subjects, TArray<FRegionInfo>& Out);
	/** 지금 그 id 에 붙은 표현 액터 (없으면 nullptr). */
	ADAPTIVEECOSYSTEM_API AEcoCreatureRepresentationActor* FindActor(UWorld& World, int64 Id);

	ADAPTIVEECOSYSTEM_API int32 FindIndex(TConstArrayView<FSubject> Subjects, int64 Id);
	/**
	 * 같은 종·지역(None = 모든 지역)의 산 개체를 id 순으로 돌 때 CurrentId 다음(Dir > 0)·앞(Dir < 0) 색인.
	 * CurrentId 가 그 목록에 없으면 Dir > 0 은 첫째, Dir < 0 은 마지막. 없으면 INDEX_NONE.
	 */
	ADAPTIVEECOSYSTEM_API int32 CycleSubject(TConstArrayView<FSubject> Subjects, bool bWolf, FName Region, int64 CurrentId, int32 Dir);
	/** 같은 종·지역의 산 개체 가운데 From 에 가장 가까운 것. bPreferEvent 면 사건 중(늑대 사냥·사슴 쫓김)인 것을 먼저 본다. 같으면 id 가 작은 것. */
	ADAPTIVEECOSYSTEM_API int32 NearestSubject(TConstArrayView<FSubject> Subjects, bool bWolf, FName Region, const FVector& From, bool bPreferEvent);
	/** 사건 중인가 (자동 추적 유지): 산 사슴의 도망·숨으러 감, 산 늑대의 사냥. */
	ADAPTIVEECOSYSTEM_API bool IsEvent(const FSubject& S);
	/** 자동 추적 짝 (사슴 → 사냥 중인 늑대(없으면 아무 늑대), 늑대 → 가장 가까운 사슴). PairCm 밖이면 0. */
	ADAPTIVEECOSYSTEM_API int64 PartnerOf(const FSubject& S, double PairCm);

	/** 자동 추적이 쫓김을 짝으로 보는 거리 (40 m — 야생 도주 안전 거리 SafeDistM 기본과 같다). */
	inline constexpr double kAutoPairCm = 4000.0;
	/**
	 * 자동 추적 대상 고르기. Region 이 None 이 아니면 그 지역을 먼저, bRegionOnly 가 아니면 그다음 모든 지역을 본다.
	 * 차례: (1) 쫓기는 사슴 — 도망 중이고 사냥 중인 늑대가 PairCm 안에 있는 사슴 가운데 그 늑대가 가장 가까운 것,
	 *       (2) 사냥 중인 늑대 — 가장 가까운 사슴이 가까운 것, (3) 도망 중인 사슴 — 아무 늑대가 가까운 것.
	 * ExcludeId(방금 끝난 대상)는 다른 후보가 없을 때만 고른다. OutPartnerId = 짝 (없으면 0). 없으면 INDEX_NONE.
	 */
	ADAPTIVEECOSYSTEM_API int32 PickAuto(TConstArrayView<FSubject> Subjects, FName Region, bool bRegionOnly, int64 ExcludeId, int64& OutPartnerId,
										 double PairCm = kAutoPairCm);
	/** 지역 고르기: 점 P 를 가로로 품는 무대, 없으면 중심이 가장 가까운 지역. 없으면 None. */
	ADAPTIVEECOSYSTEM_API FName RegionAt(TConstArrayView<FRegionInfo> Regions, const FVector& P);
	/** 지역 목록에서 Current 다음(Dir > 0)·앞 지역 (없으면 첫째). 목록이 비면 None. */
	ADAPTIVEECOSYSTEM_API FName CycleRegion(TConstArrayView<FRegionInfo> Regions, FName Current, int32 Dir);

	/**
	 * 임계 감쇠 따라가기 한 프레임 (Game Programming Gems 4 의 SmoothDamp — 무조건 안정, 넘침 없음). SmoothTime ≈ 목표에 닿는 시간 상수.
	 * 일정 속도 v 로 움직이는 목표의 정상 상태 뒤처짐은 v × SmoothTime 이다 — 목표에 v × SmoothTime 만큼 앞을 더해 주면 0 이다 (관찰 카메라 초점).
	 */
	ADAPTIVEECOSYSTEM_API void SmoothDamp(double& Value, double& Velocity, double Target, double SmoothTime, double DeltaSeconds);
	ADAPTIVEECOSYSTEM_API void SmoothDampVector(FVector& Value, FVector& Velocity, const FVector& Target, double SmoothTime, double DeltaSeconds);
	/** 각도(도) 판: 가장 짧은 쪽으로 돈다. 결과는 −180~180. */
	ADAPTIVEECOSYSTEM_API void SmoothDampAngle(double& Deg, double& Velocity, double TargetDeg, double SmoothTime, double DeltaSeconds);
	/**
	 * 가림 피하기 팔 길이 한 프레임 (스프링 팔처럼, 10-27 PIE 확인 — 숲 지역에서 카메라가 나뭇잎 속에 들어가 대상이 가려졌다):
	 * 초점→카메라 사이를 가리는 것이 있어 바라는 길이 Want 가 지금 Arm 보다 짧으면 바로 당기고, 트이면 SmoothTime 으로 천천히 편다 (넘침 없음).
	 */
	ADAPTIVEECOSYSTEM_API void ArmStep(double& Arm, double& ArmVel, double Want, double SmoothTime, double DeltaSeconds);

	/**
	 * 가리는 나무 숨기기 (10-27 창 모드 확인 — 숲 지역 나무(Beech_Tree)는 잎에 충돌이 없어 쓸기로는 못 찾는다): 그리기 상자(Bounds)가
	 * 높이 4 m 이상·가로 반폭 1~30 m 인 보이는 정적 메시(인스턴스 묶음 말고)를 후보로 두고, 초점→카메라 선분이 그 상자를 지나면 이 화면에서만 숨긴다
	 * (APlayerController::HiddenPrimitiveComponents — 액터·충돌·시뮬레이션은 그대로, 다른 화면·다른 플레이어도 그대로).
	 */
	inline constexpr double kOccluderMinHeightCm = 400.0;
	inline constexpr double kOccluderMinHalfCm = 100.0;
	inline constexpr double kOccluderMaxHalfCm = 3000.0;   // 이 레벨 너도밤나무는 키운 것이 많아 잎 폭이 30 m 를 넘는다
	/** 가리는 나무 후보 상자인가 (위 크기). */
	ADAPTIVEECOSYSTEM_API bool IsOccluderBox(const FBox& Box);
	/** 선분 A→B 가 상자를 지나는가 (A 가 상자 안이어도 참). */
	ADAPTIVEECOSYSTEM_API bool SegmentHitsBox(const FBox& Box, const FVector& A, const FVector& B);

	/** 오른쪽 위 글 묶음 자리. */
	struct FPanelLayout
	{
		float X = 0.0f;
		float Y = 0.0f;
		float Scale = 1.0f;
		bool bBeside = false;   // 팀 판 왼쪽 옆에 놓았다
	};
	/** 오른쪽 위 묶음의 화면 가장자리·팀 판과의 틈·가장 작은 배율 (픽셀·배). */
	inline constexpr float kPanelMargin = 16.0f;
	inline constexpr float kPanelGap = 8.0f;
	inline constexpr float kPanelMinScale = 0.55f;
	/** 팀 ECO INSPECTOR 판 오른쪽 끝 (AEcoCreatureInspectorHUD::DrawHUD — x 15 에서 너비 640). 묶음 왼쪽 끝은 이것 + kPanelGap 보다 오른쪽. */
	inline constexpr double kTeamInspectorRightPx = 655.0;
	/**
	 * 오른쪽 위 글 묶음 자리. Canvas = 화면 크기(픽셀), Content = 배율 1 의 묶음 크기(안쪽 여백 포함), BaseScale = 바라는 배율,
	 * Reserved = 오른쪽 위에 이미 그려지는 팀 판(없으면 nullptr). 먼저 오른쪽 위(팀 판이 있으면 그 밑)에 바라는 배율로, 너비는 화면의 48% 이면서
	 * 팀 ECO INSPECTOR 판(왼쪽 위) 오른쪽 안, 높이는 남은 높이 안에 들게 배율을 줄인다(0.55 까지). 그래도 안 들면 팀 판 왼쪽 옆
	 * (화면 오른쪽 절반·검사 판 오른쪽 안), 그래도 안 되면 0.55 배로 화면 안에 붙인다 (이때만 팀 판과 겹칠 수 있다).
	 */
	ADAPTIVEECOSYSTEM_API FPanelLayout LayoutPanel(const FVector2D& Canvas, const FVector2D& Content, float BaseScale, const FBox2D* Reserved);
	/** 팀 HERD MIGRATION 판 자리 (EcoHerdMigrationDebug::Draw 와 같은 셈 — 너비 화면 32% 를 300~430 으로, 오른쪽 16 px, 위 16 px, 높이 376). */
	ADAPTIVEECOSYSTEM_API FBox2D TeamMigrationPanelRect(const FVector2D& Canvas);

	/**
	 * 화면 가운데 대상 (자유 카메라에서 1~5 — 10-29): Eye 에서 Forward 쪽 MaxAngleDeg 안·MaxRangeCm 안의 산 개체 가운데 보는 방향과의 각이 가장 작은 것
	 * (같으면 가까운 것, 그다음 id 작은 것). Species: −1 아무 종, 0 사슴, 1 늑대. 없으면 INDEX_NONE.
	 */
	ADAPTIVEECOSYSTEM_API int32 CenterSubject(TConstArrayView<FSubject> Subjects, int32 Species, const FVector& Eye, const FVector& Forward, double MaxAngleDeg,
											  double MaxRangeCm);
	/** 자유 카메라에서 1~5 를 누를 때 화면 가운데 대상으로 보는 원뿔 (반각 20°, 300 m). 밖이면 지금 규칙(보는 자리 곁)으로 고른다. */
	inline constexpr double kCenterPickDeg = 20.0;
	inline constexpr double kCenterPickCm = 30000.0;

	/** 자유 카메라 (10-29). 속도는 cm/s. */
	inline constexpr double kFreeDefaultSpeedCm = 1200.0;   // 12 m/s (늑대 돌진 9 m/s 보다 조금 빠르게)
	inline constexpr double kFreeMinSpeedCm = 100.0;
	inline constexpr double kFreeMaxSpeedCm = 15000.0;
	inline constexpr double kFreeFastMul = 4.0;              // Shift
	inline constexpr double kFreeSpeedStep = 1.2;            // - = 휠 한 번 (줌과 같은 배)
	inline constexpr double kFreeAccelSmooth = 0.12;         // 바라는 속도에 다가가는 시간 상수 (초) — 넘침 없이 부드럽게 서고 출발한다
	inline constexpr double kFreePitchLimit = 89.0;
	inline constexpr double kFreeLookJumpDeg = 90.0;         // 컨트롤러 방향이 한 프레임에 이보다 크게 바뀌면 마우스가 아니다 (폰 다시 잡기 등) — 시야에 더하지 않는다
	/** 자유 카메라 조작 키 하나: 누르고 있으면 Axis(앞, 오른쪽, 위)를 더한다. */
	struct FFreeKey
	{
		FKey Key;
		FVector Axis;
	};
	/** 자유 카메라 이동 키 (W A S D·방향키 = 앞뒤·옆, E·Q = 위·아래). 모드가 자유 카메라일 때만 누른 채로 읽는다 (그때는 폰 이동 입력이 막혀 있다). */
	ADAPTIVEECOSYSTEM_API TConstArrayView<FFreeKey> FreeMoveKeys();
	/** 자유 카메라 빠르게 키 (왼·오른 Shift). */
	ADAPTIVEECOSYSTEM_API TConstArrayView<FKey> FreeFastKeys();
	/** 누른 키로 (앞, 오른쪽, 위) 입력 — 칸마다 −1~1 (반대 키를 같이 누르면 0). */
	ADAPTIVEECOSYSTEM_API FVector FreeMoveInput(TFunctionRef<bool(const FKey&)> IsDown);
	/**
	 * 자유 카메라 한 프레임: 앞뒤 = 보는 방향(숙임 포함), 옆 = 보는 방향의 가로 오른쪽, 위아래 = 세계 위. 입력 길이가 1 을 넘으면 1 로 줄인다 (사선도 같은 속도).
	 * 속도는 임계 감쇠(SmoothDampVector, kFreeAccelSmooth)로 입력 × SpeedCm 에 다가가고(넘침 없음 — 키를 떼면 부드럽게 선다), 자리는 속도 × 시간만큼 간다.
	 */
	ADAPTIVEECOSYSTEM_API void FreeFlyStep(FVector& Location, FVector& Velocity, const FRotator& View, const FVector& Input, double SpeedCm, double DeltaSeconds);
	/**
	 * 자유 카메라 마우스 시야: 컨트롤러 방향(마우스가 돌리는 것)이 Prev → Now 로 바뀐 만큼(짧은 쪽) 방위·숙임에 더한다. 숙임은 ±kFreePitchLimit.
	 * 컨트롤러 방향을 쓰지 않고 바뀐 양만 읽는다 — 폰·컨트롤러에는 손대지 않는다.
	 */
	ADAPTIVEECOSYSTEM_API void FreeLookStep(double& YawDeg, double& PitchDeg, const FRotator& PrevControl, const FRotator& NowControl);

	/** 단축키 동작. Player = 키 0 (관찰 중이면 자유 카메라, 자유 카메라면 원래 카메라, 원래 카메라면 아무 일 없음). */
	enum class EAction : uint8
	{
		Wolf, Deer, Top, Quarter, Auto, Player, Prev, Next, ZoomOut, ZoomIn, Region, Help
	};
	struct FKeyBind
	{
		FKey Key;
		EAction Action;
	};
	/** 단축키 표 (숫자패드·휠 같은 별칭 포함). */
	ADAPTIVEECOSYSTEM_API TConstArrayView<FKeyBind> Keys();
	/** 팀·기본 입력이 쓰는 키 (겹치면 안 된다 — 시험이 본다): Tab·R·M·[ ]·마우스 가운데·F·왼 Shift·왼 Ctrl·W·A·S·D·Space·방향키. */
	ADAPTIVEECOSYSTEM_API TConstArrayView<FKey> TeamReservedKeys();
	/** 화면·도움말 단축키 줄 (위에서 아래로). */
	ADAPTIVEECOSYSTEM_API TArray<FString> KeyHelpLines();
}

/** 관찰 카메라 모드. */
enum class EEcoV3CamMode : uint8
{
	Player,    // 원래 카메라 (보기 대상에 손대지 않는다)
	Wolf,      // 늑대 시점 (뒤에서 따라감)
	Deer,      // 사슴 시점 (뒤에서 따라감)
	Top,       // 탑뷰 (대상 위, 없으면 무대 전체)
	Quarter,   // 쿼터뷰 (45° 사선)
	Auto,      // 자동 추적
	Free       // 자유 카메라 (10-29 — 관찰 중 0: 그 자리에서 추적을 풀고 W A S D·Q E·마우스로 직접 움직인다, 폰 이동 막기는 그대로)
};

/** 관찰 카메라 (로컬 보기만 — 헤더 머리말). */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoV3ObserverCameraSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool IsTickableWhenPaused() const override { return true; }   // 멈춘 동안에도 카메라를 옮겨 볼 수 있게

	static const TCHAR* ModeNameKo(EEcoV3CamMode InMode);

	// ---- 동작 (단축키·콘솔이 부른다) ----
	/** 단축키 하나의 동작 (HandleKeys 가 키마다 부른다 — 시험도 같은 길로 부른다). */
	void DoAction(EcoV3Observe::EAction Action);
	/**
	 * 모드 바꾸기. ExplicitId > 0 이면 그 개체(종이 맞아야)를 대상으로. 늑대·사슴 모드에서 같은 모드를 다시 고르면 다음 개체.
	 * Player = 바로 원래 카메라(eco.Cam.Player), Free = EnterFree. 자유 카메라에서 1~5 는 화면 가운데 대상을 먼저 보고, 카메라가 그 자리에서 부드럽게 옮겨 간다.
	 */
	void SetMode(EEcoV3CamMode NewMode, int64 ExplicitId = 0);
	/**
	 * 자유 카메라로 (관찰 중 0·eco.Cam.Free): 지금 화면의 카메라 자리·방향 그대로 추적을 푼다. 원래 카메라에서 부르면 지금 보는 자리(폰 카메라)에서 시작한다.
	 * 폰 이동 입력 막기는 그대로(원래 카메라에서 부르면 새로 막는다). 이미 자유 카메라면 아무 일 없음.
	 */
	void EnterFree(const TCHAR* Why);
	/** 자유 카메라 이동 속도 (m/s, 1~150). */
	void SetFreeSpeed(double MetersPerSecond);
	/** 자유 카메라 자리·방향 (시험 — 자유 카메라가 아니면 쓰지 않는다). */
	void SetFreePose(const FVector& Location, const FRotator& Rotation);
	double GetFreeSpeedCm() const { return FreeSpeedCm; }
	FVector GetFreeLocation() const { return FreeLoc; }
	FRotator GetFreeRotation() const { return FRotator(FreePitch, FreeYaw, 0.0); }
	/** 이전·다음 대상 (자동 추적이면 다음 사건). */
	void StepSubject(int32 Dir);
	/** 줌 배율 곱 (> 1 = 멀리). */
	void ZoomBy(double Factor);
	/** 지금 모드의 거리를 m 로. */
	void SetZoomMeters(double Meters);
	/** 지역 바꾸기 (이름이 없으면 거짓). Dir 판은 다음·앞 지역. */
	bool SetRegion(FName RegionId);
	void CycleRegionBy(int32 Dir);
	void ToggleKeyList();
	/** 지금 상태 한 줄 (기록·콘솔). */
	FString DescribeStatus() const;
	/**
	 * 관찰 중 플레이어 이동 입력 막기를 맞춘다 (10-27 사용자 결정 — 안 보이는 폰이 걸어 발소리 Player.Footstep 를 사슴이 듣지 않게).
	 * 바라는 상태 = PC 가 있고 관찰 중(1~5 모드·자유 카메라)이며 eco.Cam.Enable·eco.Cam.BlockMove 가 켜짐. 막을 때 PC 의 이동 무시 수(AController::SetIgnoreMoveInput
	 * — 쌓인다)를 하나 더하고, 풀 때 우리가 더한 하나만 뺀다 (팀·엔진이 건 막기는 그대로). PC 가 바뀌면 전 PC 를 먼저 풀고, 엔진이 수를 지웠으면
	 * (폰 다시 시작 — APlayerController::ClientRestart 의 ResetIgnoreInputFlags) 다시 건다. 시야(마우스) 입력은 건드리지 않는다.
	 * Tick 이 매 프레임 로컬 플레이어 컨트롤러로 부르고(없으면 nullptr — 막아 둔 것을 푼다), 카메라를 켤 때도 바로 부른다. 시험은 직접 부른다.
	 */
	void SyncMoveInputBlock(APlayerController* PC);
	/** 지금 우리가 플레이어 이동 입력을 막고 있는가. */
	bool IsBlockingMoveInput() const { return MoveBlockedPC.IsValid(); }

	EEcoV3CamMode GetMode() const { return Mode; }
	int64 GetSubjectId() const { return SubjectId; }
	int64 GetPartnerId() const { return PartnerId; }
	FName GetRegion() const { return Region; }
	bool IsKeyListShown() const { return bShowKeys; }

protected:
	/** 게임·PIE 월드만 (에디터·미리보기 월드에는 보는 플레이어가 없다). */
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	APlayerController* LocalPlayerController() const;
	void HandleKeys(APlayerController& PC);
	/** 따라가기 모드(1~5)인가 (원래 카메라·자유 카메라가 아님). */
	bool IsFollowing() const { return Mode != EEcoV3CamMode::Player && Mode != EEcoV3CamMode::Free; }
	/** 자유 카메라 한 프레임 (키·마우스 → 자리·방향, 땅 위로). */
	void UpdateFreeCamera(double Dt, APlayerController& PC);
	/** 자유 카메라를 그 지역 무대 전체가 보이는 자리로 (G·eco.Cam.Region). */
	void MoveFreeToRegion(const EcoV3Observe::FRegionInfo& R);
	/** 자유 카메라 화면 가운데 점: 보는 방향 500 m 안 처음 닿는 보이는 WorldStatic 물체, 없으면 카메라 자리. */
	FVector FreeViewCenter() const;
	/** 자유 카메라에서 따라가기로: 카메라가 지금 자유 카메라 자리에서 출발하도록 따라가기 상태를 맞춘다 (끊어 옮기지 않는다). */
	void FollowFromFree(const FVector& TargetPoint);
	/** 개체·지역 다시 읽기. */
	void Refresh();
	/** 대상이 없어졌거나 죽었거나(사건 끝) 자동 추적 차례면 다음 대상으로. */
	void MaintainSubject(double Now);
	/** 지역이 없으면 지금 보는 자리로 정한다. */
	void EnsureRegion();
	FVector ReferencePoint() const;
	void SelectSubject(int64 Id, const TCHAR* Why);
	void ActivateCamera(APlayerController& PC);
	void RestorePlayerView(const TCHAR* Why);
	/** 우리가 건 이동 입력 막기를 푼다 (원래 카메라·끔·닫기). 건 것이 없으면 아무 일도 하지 않는다. */
	void ReleaseMoveInputBlock(const TCHAR* Why);
	void UpdateCamera(double Dt, APlayerController& PC);
	double BaseDistanceCm() const;
	double GroundZ(double XCm, double YCm, double Fallback) const;
	/** 초점에서 Dir 쪽 WantCm 까지 공을 쓸어 처음 닿는 보이는 WorldStatic 물체 앞 길이 (트이면 WantCm). 카메라·폰·대상·짝 표현 액터·보이지 않는 부피는 건너뛴다. */
	double ClearArmCm(const FVector& From, const FVector& Dir, double WantCm) const;
	/** 가리는 나무 숨기기 (EcoV3Observe::IsOccluderBox): 후보를 5 초마다 다시 모으고, 초점→카메라 선분이 지나는 후보만 이 화면에서 숨긴다. */
	void UpdateOccluders(APlayerController& PC, const FVector& From, const FVector& To);
	/** 우리가 숨긴 것을 모두 되돌린다 (원래 카메라·끔·닫기). */
	void ClearOccluders(APlayerController* PC);
	void BuildStatusLines();
	void DrawPanel(UCanvas* Canvas, APlayerController* PC);

	UPROPERTY(Transient)
	TObjectPtr<ACameraActor> Camera;
	TWeakObjectPtr<AActor> SavedViewTarget;
	bool bViewOwned = false;         // 보기 대상을 우리 카메라로 바꿔 두었다 (원래 대상 = SavedViewTarget, 0 이면 폰으로 돌려준다)
	TWeakObjectPtr<APlayerController> MoveBlockedPC;   // 이동 무시 수를 하나 더해 둔 컨트롤러 (비었으면 막지 않음 — 풀 때 이것에서 하나만 뺀다)

	TArray<EcoV3Observe::FSubject> Subjects;
	TArray<EcoV3Observe::FRegionInfo> Regions;
	bool bHasCreatures = false;      // 지난 읽기에 통합 개체가 있었다 (없으면 화면 글을 그리지 않는다)
	double NextPresenceCheck = 0.0;  // 원래 카메라일 때 개체를 다시 볼 실시간 (1 초마다)

	EEcoV3CamMode Mode = EEcoV3CamMode::Player;
	int64 SubjectId = 0;
	int64 PartnerId = 0;
	FName Region;
	bool bRegionLocked = false;      // 사용자가 지역을 골랐다 (자동 추적이 그 지역에만 머문다)
	double Zoom = 1.0;
	double EventEndAt = -1.0;        // 대상의 사건이 끝난(또는 죽은) 실시간 (자동 추적·죽은 대상 넘기기)
	double NextAutoSearch = 0.0;
	FVector LastSubjectLoc = FVector::ZeroVector;

	// 부드러운 따라가기 상태
	bool bSnap = true;
	FVector Focus = FVector::ZeroVector;
	FVector FocusVel = FVector::ZeroVector;
	double Yaw = 45.0, YawVel = 0.0;
	double Pitch = -30.0, PitchVel = 0.0;
	double Dist = 2000.0, DistVel = 0.0;
	double Arm = -1.0, ArmVel = 0.0;   // 가림 피하기로 줄인 실제 거리 (음수 = 아직 없음 — 다음 프레임에 바로 정한다)
	TArray<TWeakObjectPtr<UPrimitiveComponent>> OccluderCandidates;   // 가리는 나무 후보 (5 초마다 다시 모은다)
	TArray<TWeakObjectPtr<UPrimitiveComponent>> HiddenOccluders;      // 지금 이 화면에서 숨긴 것 (PC->HiddenPrimitiveComponents 에 우리가 넣은 것만)
	double NextOccluderScan = 0.0;
	double LastGroundZ = 0.0;

	// 자유 카메라 (10-29)
	FVector FreeLoc = FVector::ZeroVector;
	FVector FreeVel = FVector::ZeroVector;
	double FreeYaw = 0.0;
	double FreePitch = 0.0;
	double FreeSpeedCm = EcoV3Observe::kFreeDefaultSpeedCm;
	bool bFreeFast = false;             // 이 프레임 Shift (화면 글)
	bool bFreeGround = false;           // 이 프레임 자유 카메라 밑에 땅을 찾았다 (LastGroundZ — 화면 글 '땅에서 n m')
	FRotator LastControlRot = FRotator::ZeroRotator;   // 지난 프레임 컨트롤러 방향 (마우스 시야 = 바뀐 양)
	bool bHasLastControl = false;

	// 화면 글
	bool bShowKeys = true;
	TArray<FString> StatusLines;
	TArray<FColor> StatusColors;
	FDelegateHandle DrawHandle;
};
