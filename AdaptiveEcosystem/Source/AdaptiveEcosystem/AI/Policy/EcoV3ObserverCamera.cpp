#include "EcoV3ObserverCamera.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/StaticMeshComponent.h"
#include "CanvasItem.h"
#include "CollisionQueryParams.h"
#include "Creature/Debug/EcoCreatureInspection.h"
#include "Creature/Debug/EcoHerdMigrationDebug.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Debug/DebugDrawService.h"
#include "EcoPolicyV3Fragments.h"
#include "EcoPolicyV3IntegratedFragments.h"
#include "EcoPolicyV3IntegratedSubsystem.h"
#include "Engine/Canvas.h"
#include "Engine/Console.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/HUD.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Volume.h"
#include "HAL/IConsoleManager.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassPresentationFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityQuery.h"
#include "MassEntitySubsystem.h"
#include "MassExecutionContext.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/UObjectIterator.h"

DEFINE_LOG_CATEGORY(LogEcoV3Cam);

namespace EcoV3ObserverCameraImpl
{
	static TAutoConsoleVariable<int32> CVarCamEnable(
		TEXT("eco.Cam.Enable"), 1,
		TEXT("관찰 카메라 (EcoV3ObserverCamera.h): 1 = 단축키 1~5·0·, .·- =·휠·G·H(자유 카메라는 W A S D·Q E·Shift·마우스)와 오른쪽 위 화면 글, ")
			TEXT("0 = 끔 (원래 카메라로 돌아가고 플레이어 이동 막기를 풀며 키·글·eco.Cam 명령을 받지 않는다). 보기만 바꾼다 — 시뮬레이션에 쓰지 않는다."));
	static TAutoConsoleVariable<float> CVarCamHudScale(
		TEXT("eco.Cam.HudScale"), 1.0f,
		TEXT("관찰 카메라 오른쪽 위 글 배율 (기본 1 — 화면 높이에 맞춘 배율에 곱한다, 0.5~3)."));
	static TAutoConsoleVariable<int32> CVarCamBlockMove(
		TEXT("eco.Cam.BlockMove"), 1,
		TEXT("관찰 카메라로 보는 동안(1~5 모드·자유 카메라) 플레이어 폰 이동 입력 막기: 1 = 막음 (기본 — 안 보이는 폰이 걸어 발소리 Player.Footstep 를 사슴이 듣지 않게, ")
			TEXT("원래 카메라로 돌아오면(따라가기에서 0 두 번·자유 카메라에서 0·eco.Cam.Player) 풀린다), ")
			TEXT("0 = 막지 않음 (다음 프레임에 풀린다). 로컬 플레이어 컨트롤러의 이동 무시 수(AController::SetIgnoreMoveInput — 쌓인다)를 하나 더하고 빼기만 한다 — ")
			TEXT("시야(마우스)·점프·F·Shift·Ctrl 은 그대로."));

	constexpr float kFov = 70.0f;
	constexpr double kFocusSmooth = 0.18;     // 초점 시간 상수 (초) — 대상 속도 × 이 값만큼 앞을 봐 9 m/s 도 뒤처지지 않는다
	constexpr double kYawSmooth = 0.45;
	constexpr double kPitchSmooth = 0.30;
	constexpr double kDistSmooth = 0.35;
	constexpr double kMaxLeadCm = 600.0;
	constexpr double kSnapCm = 15000.0;       // 150 m 넘게 건너뛰면 끊어 옮긴다 (지역 바꾸기)
	constexpr double kGroundClearCm = 200.0;  // 카메라는 땅 2 m 위 밑으로 가지 않는다
	constexpr double kArmProbeCm = 25.0;      // 가림 피하기: 초점→카메라를 쓰는 공 반지름
	constexpr double kArmGapCm = 40.0;        // 막힌 곳 앞 여유
	constexpr double kArmMinCm = 250.0;       // 이보다 가까이 당기지 않는다 (대상 몸 속으로 들어가지 않게)
	constexpr double kArmOutSmooth = 0.6;     // 트였을 때 펴는 시간 상수 (초) — 당길 때는 바로
	constexpr double kLingerSeconds = 2.5;    // 자동 추적: 사건이 끝난 뒤 머무는 실시간
	constexpr double kDeadHoldSeconds = 3.0;  // 죽은 대상에 머무는 실시간
	constexpr double kFramePairCm = 6000.0;   // 자동 추적 화면에 짝으로 넣는 거리
	constexpr double kHeadingMinSpeed = 80.0; // 이보다 빠르면 몸 방향 대신 속도 방향을 본다 (cm/s)
	constexpr double kFocusUpCm = 100.0;
	constexpr double kWolfDistCm = 1400.0, kWolfPitch = -20.0;
	constexpr double kDeerDistCm = 1100.0, kDeerPitch = -18.0;
	constexpr double kTopDistCm = 4500.0, kTopPitch = -89.0;
	constexpr double kQuarterDistCm = 3000.0, kQuarterPitch = -45.0, kQuarterYaw = 45.0;
	constexpr double kAutoDistCm = 2400.0, kAutoPitch = -35.0, kAutoMaxCm = 12000.0;
	constexpr double kOverviewPitch = -40.0;
	constexpr double kIdleSpeedCm = 5.0;      // AEcoCreatureRepresentationActor 기본 IdleSpeed·RunSpeed (액터가 없을 때 동작 셈)
	constexpr double kRunSpeedCm = 400.0;
	constexpr double kMinZoom = 0.15, kMaxZoom = 8.0;
	constexpr double kPresenceEverySeconds = 1.0;   // 원래 카메라일 때 통합 개체가 있는지 다시 보는 간격 (화면 글 보이기)

	EEcoCreatureVisualMotion MotionOf(bool bAlive, bool bEating, double Speed)
	{
		return !bAlive								  ? EEcoCreatureVisualMotion::Dead
			   : bEating && Speed <= kIdleSpeedCm	  ? EEcoCreatureVisualMotion::Eating
			   : Speed <= kIdleSpeedCm				  ? EEcoCreatureVisualMotion::Idle
			   : Speed >= FMath::Max(kIdleSpeedCm + 1.0, kRunSpeedCm) ? EEcoCreatureVisualMotion::Run
																	  : EEcoCreatureVisualMotion::Walk;
	}

	FColor StateColor(EcoV3Observe::EState S)
	{
		using EcoV3Observe::EState;
		switch (S)
		{
		case EState::Eat: return FColor(120, 225, 120);
		case EState::Alert: return FColor(255, 175, 80);
		case EState::KeepAway: return FColor(230, 200, 120);   // DeerLabel 거리 두기와 같은 옅은 주황
		case EState::Flee: return FColor(255, 130, 40);
		case EState::FleeOpen: return FColor(255, 240, 120);
		case EState::FleeShelter: return FColor(110, 230, 255);
		case EState::Hide:
		case EState::Crouch: return FColor(120, 170, 255);
		case EState::Freeze: return FColor(245, 245, 245);
		case EState::Sleep:
		case EState::Rest: return FColor(175, 175, 235);
		case EState::Travel: return FColor(210, 210, 210);
		case EState::Roam: return FColor(235, 180, 180);
		case EState::Hunt: return FColor(255, 95, 95);
		case EState::WolfEat: return FColor(215, 215, 150);
		case EState::Dead: return FColor(150, 150, 150);
		default: return FColor(220, 220, 220);
		}
	}

	/** 탑뷰 무대 전체 높이: 무대 한 변의 1.1 배가 세로 화면(16:9)에 들어가는 거리. */
	double FitTopCm(double SizeCm)
	{
		const double HalfV = FMath::Atan(FMath::Tan(FMath::DegreesToRadians(0.5 * kFov)) * 9.0 / 16.0);
		return 0.55 * SizeCm / FMath::Tan(HalfV);
	}

	const EcoV3Observe::FRegionInfo* FindRegion(TConstArrayView<EcoV3Observe::FRegionInfo> Regions, FName Id)
	{
		for (const EcoV3Observe::FRegionInfo& R : Regions)
		{
			if (R.Id == Id)
			{
				return &R;
			}
		}
		return nullptr;
	}

	constexpr double kFreeCenterTraceCm = 50000.0;   // 자유 카메라 화면 가운데 점을 찾는 거리 (500 m)

	/** 콘솔에 글을 치는 중인가 (그동안 단축키·자유 카메라 키를 읽지 않는다). */
	bool IsConsoleOpen(const APlayerController& PC)
	{
		const ULocalPlayer* LP = PC.GetLocalPlayer();
		return LP && LP->ViewportClient && LP->ViewportClient->ViewportConsole && LP->ViewportClient->ViewportConsole->ConsoleActive();
	}

	/** 보이는 막힘인가 (처음부터 박힌 것·보이지 않는 부품·숨긴 액터·막는 부피는 아니다 — 무대 밖 보이지 않는 벽에 끌려가지 않게). */
	bool IsVisibleBlock(const FHitResult& H)
	{
		const UPrimitiveComponent* C = H.GetComponent();
		const AActor* A = H.GetActor();
		return !H.bStartPenetrating && C && C->IsVisible() && !C->bHiddenInGame && !(A && (A->IsHidden() || A->IsA<AVolume>()));
	}

	/** 화면 속도 글 (정수면 '12', 아니면 '14.4'). */
	FString SpeedText(double MetersPerSecond)
	{
		return FMath::IsNearlyEqual(MetersPerSecond, FMath::RoundToDouble(MetersPerSecond), 0.05) ? FString::Printf(TEXT("%.0f"), MetersPerSecond)
																								  : FString::Printf(TEXT("%.1f"), MetersPerSecond);
	}
}

// =============================================================================
// EcoV3Observe — 찾기·고르기·따라가기 (순수 함수 + 월드 읽기)
// =============================================================================

const TCHAR* EcoV3Observe::StateNameKo(EState S)
{
	switch (S)
	{
	case EState::Eat: return TEXT("먹기");
	case EState::Alert: return TEXT("경계");
	case EState::KeepAway: return TEXT("거리 두기(쉬는 늑대)");
	case EState::Flee: return TEXT("도망");
	case EState::FleeOpen: return TEXT("도망(트인 쪽)");
	case EState::FleeShelter: return TEXT("도망(은신처)");
	case EState::Hide: return TEXT("숨으러 감");
	case EState::Crouch: return TEXT("웅크림");
	case EState::Freeze: return TEXT("얼기");
	case EState::Sleep: return TEXT("잠");
	case EState::Travel: return TEXT("이동");
	case EState::Roam: return TEXT("배회");
	case EState::Hunt: return TEXT("사냥");
	case EState::WolfEat: return TEXT("먹기");
	case EState::Rest: return TEXT("쉼");
	case EState::Dead: return TEXT("죽음");
	default: return TEXT("?");
	}
}

bool EcoV3Observe::IsChased(EState S)
{
	return S == EState::Flee || S == EState::FleeOpen || S == EState::FleeShelter;
}

EcoV3Observe::EState EcoV3Observe::DeerStateV3(int32 Behavior, bool bArrived, int32 KeepMode, int32 ShownRoute)
{
	if (KeepMode == EcoWorldV3::kKeepPanic)
	{
		return ShownRoute == EcoWorldV3::kRouteRun ? EState::FleeOpen : ShownRoute == EcoWorldV3::kRouteShelter ? EState::FleeShelter : EState::Flee;
	}
	if (KeepMode == EcoWorldV3::kKeepShelter)
	{
		return EState::Crouch;
	}
	if (KeepMode == EcoWorldV3::kKeepAlert && Behavior == EcoRepertoireV3::kGraze)
	{
		return EState::Alert;
	}
	// 10-27 거리 두기(쉬는 늑대): 경계와 같이 두뇌가 먹기일 때만 (DeerLabel 과 같다)
	if (KeepMode == EcoWorldV3::kKeepRest && Behavior == EcoRepertoireV3::kGraze)
	{
		return EState::KeepAway;
	}
	switch (Behavior)
	{
	case EcoRepertoireV3::kGraze: return EState::Eat;
	case EcoRepertoireV3::kFlee: return EState::Flee;
	case EcoRepertoireV3::kHide: return bArrived ? EState::Crouch : EState::Hide;
	case EcoRepertoireV3::kFreeze: return EState::Freeze;
	case EcoRepertoireV3::kSleep: return EState::Sleep;
	default: return EState::Unknown;
	}
}

EcoV3Observe::EState EcoV3Observe::WolfStateV3(int32 WolfState, bool bSated)
{
	using EcoV3Integrated::EWolfState;
	if (bSated)
	{
		return EState::Rest;
	}
	switch (static_cast<EWolfState>(WolfState))
	{
	case EWolfState::Roam:
	case EWolfState::Waking: return EState::Roam;
	case EWolfState::Stalk:
	case EWolfState::Pounce:
	case EWolfState::Exhaust:
	case EWolfState::Chase: return EState::Hunt;
	case EWolfState::Eat: return EState::WolfEat;
	case EWolfState::Sleep:
	case EWolfState::Settle: return EState::Rest;
	default: return EState::Unknown;
	}
}

EcoV3Observe::EState EcoV3Observe::StateFromActivity(bool bWolf, EEcoSpeciesActivity A)
{
	using Act = EEcoSpeciesActivity;
	if (bWolf)
	{
		switch (A)
		{
		case Act::Stalk:
		case Act::Pounce:
		case Act::Pursue:
		case Act::Attack:
		case Act::Exhaust: return EState::Hunt;
		case Act::Eat:
		case Act::Graze: return EState::WolfEat;
		case Act::Sleep:
		case Act::Rest:
		case Act::SatedRest:
		case Act::Recover: return EState::Rest;
		default: return EState::Roam;
		}
	}
	switch (A)
	{
	case Act::Graze:
	case Act::Forage:
	case Act::Eat: return EState::Eat;
	case Act::AlertGraze:
	case Act::Vigilant:
	case Act::Curious:
	case Act::Investigate: return EState::Alert;
	case Act::Flee:
	case Act::Recover: return EState::Flee;
	case Act::ShelterTravel: return EState::Hide;
	case Act::ShelterHold: return EState::Crouch;
	case Act::Freeze: return EState::Freeze;
	case Act::Sleep:
	case Act::Rest:
	case Act::SatedRest: return EState::Sleep;
	case Act::Travel:
	case Act::WeakTravel:
	case Act::Wander:
	case Act::Regroup:
	case Act::Search: return EState::Travel;
	default: return EState::Unknown;
	}
}

bool EcoV3Observe::Gather(UWorld& World, TArray<FSubject>& Out)
{
	using namespace EcoV3ObserverCameraImpl;
	Out.Reset();
	UMassEntitySubsystem* MassSub = World.GetSubsystem<UMassEntitySubsystem>();
	if (!MassSub)
	{
		return false;
	}
	FMassEntityManager& EM = MassSub->GetMutableEntityManager();
	if (EM.IsProcessing())
	{
		return false;
	}
	// 지금 붙어 있는 표현 액터 (id → 액터). 팀 표현은 보는 자리 둘레 일부에게만 액터를 붙인다 — 없으면 논리 자리를 쓴다
	TMap<int64, AEcoCreatureRepresentationActor*> Actors;
	for (TActorIterator<AEcoCreatureRepresentationActor> It(&World); It; ++It)
	{
		if (AEcoCreatureRepresentationActor* A = *It; A && A->bBound && A->VisualState.StableAgentId > 0)
		{
			Actors.Add(A->VisualState.StableAgentId, A);
		}
	}
	const UEcoPolicyV3IntegratedSubsystem* V3 = World.GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	const bool bV3 = V3 && V3->IsActive() && World.GetNetMode() != NM_Client;
	static const FName WolfSpecies(TEXT("Wolf"));

	FMassEntityQuery Q(EM.AsShared());
	Q.AddTagRequirement<FEcoIntegratedCreatureTag>(EMassFragmentPresence::All);
	Q.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	Q.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	Q.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	Q.AddRequirement<FEcoCreaturePresentationFragment>(EMassFragmentAccess::ReadOnly);
	Q.AddRequirement<FEcoClientPresentationFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Q.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Q.AddRequirement<FEcoBehaviorStateFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Q.AddRequirement<FEcoThreatStateFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Q.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	FMassExecutionContext Exec = EM.CreateExecutionContext(0.0f);
	// 읽기만 한다: CreateExecutionContext 는 엔티티 관리자가 지금 연 공용 지연 명령 버퍼를 묶고, 쿼리가 끝나면 그 버퍼를 비운다
	// (FScopedEntityQueryContext → FlushDeferred). 다른 코드가 쌓아 둔 명령을 카메라·촬영 감독 틱 시점에 앞당겨 반영하지 않게 끈다
	Exec.SetFlushDeferredCommands(false);
	Q.ForEachEntityChunk(Exec, [&](FMassExecutionContext& C)
	{
		const TConstArrayView<FEcoIdentityFragment> Ids = C.GetFragmentView<FEcoIdentityFragment>();
		const TConstArrayView<FEcoRegionFragment> Regs = C.GetFragmentView<FEcoRegionFragment>();
		const TConstArrayView<FTransformFragment> Xfs = C.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FEcoCreaturePresentationFragment> Pres = C.GetFragmentView<FEcoCreaturePresentationFragment>();
		const TConstArrayView<FEcoClientPresentationFragment> Clients = C.GetFragmentView<FEcoClientPresentationFragment>();
		const TConstArrayView<FEcoIntegratedV3Fragment> Ints = C.GetFragmentView<FEcoIntegratedV3Fragment>();
		const TConstArrayView<FEcoBehaviorStateFragment> Behaviors = C.GetFragmentView<FEcoBehaviorStateFragment>();
		const TConstArrayView<FEcoThreatStateFragment> Threats = C.GetFragmentView<FEcoThreatStateFragment>();
		const TConstArrayView<FEcoHerbivoreBodyV3Fragment> Bodies = C.GetFragmentView<FEcoHerbivoreBodyV3Fragment>();
		for (int32 i = 0; i < C.GetNumEntities(); ++i)
		{
			// 클라이언트가 아직 표본을 못 받은 개체는 자리가 없다 (팀 표현 SyncVisuals 와 같이 뺀다)
			if (Ids[i].StableAgentId <= 0 || (!Clients.IsEmpty() && !Clients[i].bHasSample))
			{
				continue;
			}
			FSubject S;
			S.Id = Ids[i].StableAgentId;
			S.bWolf = Ids[i].SpeciesId == WolfSpecies;
			S.Region = Regs[i].CurrentRegionId;
			const FEcoCreaturePresentationFragment& P = Pres[i];
			S.bAlive = (P.Flags & 1) != 0;
			S.bEating = (P.Flags & 2) != 0;
			S.bPursuing = (P.Flags & 4) != 0;
			const FEcoIntegratedV3Fragment* Int = Ints.IsEmpty() ? nullptr : &Ints[i];
			if (Int && Int->bAdopted && Int->bDead)
			{
				S.bAlive = false;
			}
			S.Velocity = S.bAlive ? P.Velocity : FVector::ZeroVector;
			S.Location = Xfs[i].GetTransform().GetLocation();
			S.YawDeg = static_cast<float>(Xfs[i].GetTransform().Rotator().Yaw);
			if (!Clients.IsEmpty())
			{
				S.Location = Clients[i].Current.Location;
				S.YawDeg = static_cast<float>(Clients[i].Current.Rotation.Yaw);
			}
			const FEcoV3RegionContext* Ctx = (bV3 && Int && Int->bAdopted) ? V3->GetContext(Int->ContextIndex) : nullptr;
			if (!S.bAlive)
			{
				S.State = EState::Dead;
				S.Detail = !Int ? FString() : Int->DeathCause == EcoWorldV3::kDeathCaught ? FString(TEXT("잡힘"))
											: Int->DeathCause == EcoWorldV3::kDeathStarved ? FString(TEXT("굶음")) : FString();
			}
			else if (Ctx && S.bWolf && !Threats.IsEmpty())
			{
				const EcoWorldV3::FThreatAgent& A = Threats[i].Agent;
				const EcoThreatV3::FThreatConfig& Cfg = Ctx->Sim.ThreatCfg;
				const EcoV3Integrated::EWolfState St = EcoV3Integrated::WolfStateOf(A, Cfg);
				const bool bSated = Cfg.bWildSatiation && A.Last.bSated && !A.State.bAsleep;   // EcoV3Integrated::WolfLabel 과 같은 판정
				S.State = WolfStateV3(static_cast<int32>(St), bSated);
				const FString Sub = bSated ? FString::Printf(TEXT("배부름 %.0f초"), static_cast<double>(A.State.SatLeft) * EcoRepertoireV3::kStepSeconds)
									: St == EcoV3Integrated::EWolfState::Eat
										? FString::Printf(TEXT("식사 %.1f초"), static_cast<double>(A.State.Cooldown) * EcoRepertoireV3::kStepSeconds)
										: FString(EcoV3Integrated::WolfStateNameKo(St));
				S.Detail = Sub + (A.Spec.Type == EcoThreatV3::EThreatType::Stalker ? TEXT(" · 잠행형") : TEXT(" · 추격형"));
			}
			else if (Ctx && !S.bWolf && !Behaviors.IsEmpty())
			{
				const FEcoBehaviorStateFragment& B = Behaviors[i];
				S.State = DeerStateV3(B.Rep.Behavior, B.Rep.bArrived, B.Decision.KeepActive, EcoV3Integrated::ShownRoute(B.Decision));
				if (!Bodies.IsEmpty())
				{
					S.Detail = FString::Printf(TEXT("에너지 %d%%"), FMath::RoundToInt32(100.0 * FMath::Clamp(Bodies[i].Body.Energy, 0.0, 1.0)));
				}
			}
			else
			{
				const EEcoSpeciesActivity Act = P.Activity <= static_cast<uint8>(EEcoSpeciesActivity::Investigate)
													? static_cast<EEcoSpeciesActivity>(P.Activity)
													: EEcoSpeciesActivity::Hold;
				S.State = StateFromActivity(S.bWolf, Act);
			}
			if (AEcoCreatureRepresentationActor* const* A = Actors.Find(S.Id))
			{
				S.bHasActor = true;
				S.Location = (*A)->GetActorLocation();
				S.YawDeg = static_cast<float>((*A)->GetActorRotation().Yaw);
				S.Motion = (*A)->VisualMotion;
			}
			else
			{
				S.Motion = MotionOf(S.bAlive, S.bEating, S.Velocity.Size2D());
			}
			if (!S.Location.ContainsNaN())
			{
				Out.Add(MoveTemp(S));
			}
		}
	});
	Out.Sort([](const FSubject& A, const FSubject& B) { return A.Id < B.Id; });
	FillNeighbors(Out);
	return true;
}

void EcoV3Observe::FillNeighbors(TArray<FSubject>& Subjects)
{
	for (FSubject& S : Subjects)
	{
		S.NearestWolfId = S.NearestHuntWolfId = S.NearestDeerId = 0;
		S.NearestWolfCm = S.NearestHuntWolfCm = S.NearestDeerCm = -1.0;
		if (!S.bAlive)
		{
			continue;
		}
		for (const FSubject& O : Subjects)
		{
			if (!O.bAlive || O.Id == S.Id || O.Region != S.Region || O.bWolf == S.bWolf)
			{
				continue;
			}
			const double D = FVector::Dist2D(S.Location, O.Location);
			if (S.bWolf)
			{
				if (S.NearestDeerCm < 0.0 || D < S.NearestDeerCm)
				{
					S.NearestDeerCm = D;
					S.NearestDeerId = O.Id;
				}
				continue;
			}
			if (S.NearestWolfCm < 0.0 || D < S.NearestWolfCm)
			{
				S.NearestWolfCm = D;
				S.NearestWolfId = O.Id;
			}
			if (IsHunting(O.State) && (S.NearestHuntWolfCm < 0.0 || D < S.NearestHuntWolfCm))
			{
				S.NearestHuntWolfCm = D;
				S.NearestHuntWolfId = O.Id;
			}
		}
	}
}

void EcoV3Observe::GatherRegions(UWorld& World, TConstArrayView<FSubject> Subjects, TArray<FRegionInfo>& Out)
{
	Out.Reset();
	const UEcoPolicyV3IntegratedSubsystem* V3 = World.GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	if (V3 && V3->IsActive() && World.GetNetMode() != NM_Client)
	{
		for (int32 c = 0; c < V3->NumContexts(); ++c)
		{
			if (const FEcoV3RegionContext* Ctx = V3->GetContext(c))
			{
				FRegionInfo R;
				R.Id = Ctx->RegionId;
				R.SizeCm = Ctx->SizeCm();
				R.CenterCm = Ctx->OriginCm + FVector(0.5 * R.SizeCm, 0.5 * R.SizeCm, 0.0);
				R.bStage = true;
				Out.Add(R);
			}
		}
	}
	// 무대가 없는 지역 (클라이언트·v1): 그 지역 개체 둘레 상자
	TMap<FName, FBox> Boxes;
	for (const FSubject& S : Subjects)
	{
		if (S.Region.IsNone() || Out.ContainsByPredicate([&S](const FRegionInfo& R) { return R.Id == S.Region; }))
		{
			continue;
		}
		Boxes.FindOrAdd(S.Region, FBox(ForceInit)) += S.Location;
	}
	for (const TPair<FName, FBox>& B : Boxes)
	{
		FRegionInfo R;
		R.Id = B.Key;
		R.CenterCm = B.Value.GetCenter();
		const FVector Size = B.Value.GetSize();
		R.SizeCm = FMath::Max3(Size.X, Size.Y, 6000.0);
		Out.Add(R);
	}
	Out.Sort([](const FRegionInfo& A, const FRegionInfo& B) { return A.Id.LexicalLess(B.Id); });
}

AEcoCreatureRepresentationActor* EcoV3Observe::FindActor(UWorld& World, int64 Id)
{
	for (TActorIterator<AEcoCreatureRepresentationActor> It(&World); It; ++It)
	{
		if (*It && It->bBound && It->VisualState.StableAgentId == Id)
		{
			return *It;
		}
	}
	return nullptr;
}

int32 EcoV3Observe::FindIndex(TConstArrayView<FSubject> Subjects, int64 Id)
{
	if (Id <= 0)
	{
		return INDEX_NONE;
	}
	for (int32 i = 0; i < Subjects.Num(); ++i)
	{
		if (Subjects[i].Id == Id)
		{
			return i;
		}
	}
	return INDEX_NONE;
}

int32 EcoV3Observe::CycleSubject(TConstArrayView<FSubject> Subjects, bool bWolf, FName Region, int64 CurrentId, int32 Dir)
{
	TArray<int32> Idx;
	for (int32 i = 0; i < Subjects.Num(); ++i)
	{
		const FSubject& S = Subjects[i];
		if (S.bAlive && S.bWolf == bWolf && (Region.IsNone() || S.Region == Region))
		{
			Idx.Add(i);
		}
	}
	if (Idx.IsEmpty())
	{
		return INDEX_NONE;
	}
	Idx.Sort([&Subjects](int32 A, int32 B) { return Subjects[A].Id < Subjects[B].Id; });
	const int32 Pos = Idx.IndexOfByPredicate([&](int32 i) { return Subjects[i].Id == CurrentId; });
	if (Pos == INDEX_NONE)
	{
		return Dir >= 0 ? Idx[0] : Idx.Last();
	}
	const int32 N = Idx.Num();
	return Idx[(Pos + (Dir >= 0 ? 1 : N - 1)) % N];
}

bool EcoV3Observe::IsEvent(const FSubject& S)
{
	if (!S.bAlive)
	{
		return false;
	}
	return S.bWolf ? IsHunting(S.State) : (IsChased(S.State) || S.State == EState::Hide);
}

int32 EcoV3Observe::NearestSubject(TConstArrayView<FSubject> Subjects, bool bWolf, FName Region, const FVector& From, bool bPreferEvent)
{
	for (int32 Pass = bPreferEvent ? 0 : 1; Pass < 2; ++Pass)
	{
		int32 Best = INDEX_NONE;
		double BestD = TNumericLimits<double>::Max();
		for (int32 i = 0; i < Subjects.Num(); ++i)
		{
			const FSubject& S = Subjects[i];
			if (!S.bAlive || S.bWolf != bWolf || (!Region.IsNone() && S.Region != Region) || (Pass == 0 && !IsEvent(S)))
			{
				continue;
			}
			const double D = FVector::DistSquared2D(S.Location, From);
			if (D < BestD || (D == BestD && Best != INDEX_NONE && S.Id < Subjects[Best].Id))
			{
				BestD = D;
				Best = i;
			}
		}
		if (Best != INDEX_NONE)
		{
			return Best;
		}
	}
	return INDEX_NONE;
}

int64 EcoV3Observe::PartnerOf(const FSubject& S, double PairCm)
{
	if (!S.bAlive)
	{
		return 0;
	}
	if (S.bWolf)
	{
		return (S.NearestDeerCm >= 0.0 && S.NearestDeerCm <= PairCm) ? S.NearestDeerId : 0;
	}
	if (S.NearestHuntWolfCm >= 0.0 && S.NearestHuntWolfCm <= PairCm)
	{
		return S.NearestHuntWolfId;
	}
	return (S.NearestWolfCm >= 0.0 && S.NearestWolfCm <= PairCm) ? S.NearestWolfId : 0;
}

int32 EcoV3Observe::PickAuto(TConstArrayView<FSubject> Subjects, FName Region, bool bRegionOnly, int64 ExcludeId, int64& OutPartnerId,
							 double PairCm)
{
	OutPartnerId = 0;
	auto Pass = [&](FName R, bool bAllowExclude, int64& OutPartner) -> int32
	{
		auto Eligible = [&](const FSubject& S) { return S.bAlive && (R.IsNone() || S.Region == R) && (bAllowExclude || S.Id != ExcludeId); };
		auto Better = [&](int32 Best, double BestKey, int32 i, double Key)
		{ return Best == INDEX_NONE || Key < BestKey || (Key == BestKey && Subjects[i].Id < Subjects[Best].Id); };
		// (1) 쫓기는 사슴: 도망 중이고 사냥 중인 늑대가 짝 거리 안
		int32 Best = INDEX_NONE;
		double BestKey = 0.0;
		for (int32 i = 0; i < Subjects.Num(); ++i)
		{
			const FSubject& S = Subjects[i];
			if (Eligible(S) && !S.bWolf && IsChased(S.State) && S.NearestHuntWolfCm >= 0.0 && S.NearestHuntWolfCm <= PairCm
				&& Better(Best, BestKey, i, S.NearestHuntWolfCm))
			{
				Best = i;
				BestKey = S.NearestHuntWolfCm;
			}
		}
		if (Best != INDEX_NONE)
		{
			OutPartner = Subjects[Best].NearestHuntWolfId;
			return Best;
		}
		// (2) 사냥 중인 늑대: 가장 가까운 사슴이 가까운 것
		for (int32 i = 0; i < Subjects.Num(); ++i)
		{
			const FSubject& S = Subjects[i];
			const double Key = S.NearestDeerCm >= 0.0 ? S.NearestDeerCm : 1.0e12;
			if (Eligible(S) && S.bWolf && IsHunting(S.State) && Better(Best, BestKey, i, Key))
			{
				Best = i;
				BestKey = Key;
			}
		}
		if (Best != INDEX_NONE)
		{
			OutPartner = Subjects[Best].NearestDeerCm >= 0.0 && Subjects[Best].NearestDeerCm <= PairCm ? Subjects[Best].NearestDeerId : 0;
			return Best;
		}
		// (3) 도망 중인 사슴: 아무 늑대가 가까운 것
		for (int32 i = 0; i < Subjects.Num(); ++i)
		{
			const FSubject& S = Subjects[i];
			const double Key = S.NearestWolfCm >= 0.0 ? S.NearestWolfCm : 1.0e12;
			if (Eligible(S) && !S.bWolf && IsChased(S.State) && Better(Best, BestKey, i, Key))
			{
				Best = i;
				BestKey = Key;
			}
		}
		if (Best != INDEX_NONE)
		{
			OutPartner = PartnerOf(Subjects[Best], PairCm);
		}
		return Best;
	};
	for (const bool bAllowExclude : {false, true})
	{
		if (!Region.IsNone())
		{
			if (const int32 i = Pass(Region, bAllowExclude, OutPartnerId); i != INDEX_NONE)
			{
				return i;
			}
		}
		if (!bRegionOnly || Region.IsNone())
		{
			if (const int32 i = Pass(NAME_None, bAllowExclude, OutPartnerId); i != INDEX_NONE)
			{
				return i;
			}
		}
	}
	OutPartnerId = 0;
	return INDEX_NONE;
}

FName EcoV3Observe::RegionAt(TConstArrayView<FRegionInfo> Regions, const FVector& P)
{
	for (const FRegionInfo& R : Regions)
	{
		const double Half = 0.5 * R.SizeCm;
		if (R.bStage && FMath::Abs(P.X - R.CenterCm.X) <= Half && FMath::Abs(P.Y - R.CenterCm.Y) <= Half)
		{
			return R.Id;
		}
	}
	FName Best;
	double BestD = TNumericLimits<double>::Max();
	for (const FRegionInfo& R : Regions)
	{
		const double D = FVector::DistSquared2D(R.CenterCm, P);
		if (D < BestD)
		{
			BestD = D;
			Best = R.Id;
		}
	}
	return Best;
}

FName EcoV3Observe::CycleRegion(TConstArrayView<FRegionInfo> Regions, FName Current, int32 Dir)
{
	if (Regions.IsEmpty())
	{
		return NAME_None;
	}
	int32 Pos = INDEX_NONE;
	for (int32 i = 0; i < Regions.Num(); ++i)
	{
		if (Regions[i].Id == Current)
		{
			Pos = i;
			break;
		}
	}
	if (Pos == INDEX_NONE)
	{
		return Regions[0].Id;
	}
	const int32 N = Regions.Num();
	return Regions[(Pos + (Dir >= 0 ? 1 : N - 1)) % N].Id;
}

void EcoV3Observe::SmoothDamp(double& Value, double& Velocity, double Target, double SmoothTime, double DeltaSeconds)
{
	if (!(DeltaSeconds > 0.0))
	{
		return;
	}
	const double Omega = 2.0 / FMath::Max(SmoothTime, 1.0e-4);
	const double X = Omega * DeltaSeconds;
	const double Exp = 1.0 / (1.0 + X + 0.48 * X * X + 0.235 * X * X * X);   // e^{-x} 근사 (모든 x 에서 안정)
	const double Change = Value - Target;
	const double Temp = (Velocity + Omega * Change) * DeltaSeconds;
	Velocity = (Velocity - Omega * Temp) * Exp;
	Value = Target + (Change + Temp) * Exp;
}

void EcoV3Observe::SmoothDampVector(FVector& Value, FVector& Velocity, const FVector& Target, double SmoothTime, double DeltaSeconds)
{
	SmoothDamp(Value.X, Velocity.X, Target.X, SmoothTime, DeltaSeconds);
	SmoothDamp(Value.Y, Velocity.Y, Target.Y, SmoothTime, DeltaSeconds);
	SmoothDamp(Value.Z, Velocity.Z, Target.Z, SmoothTime, DeltaSeconds);
}

void EcoV3Observe::SmoothDampAngle(double& Deg, double& Velocity, double TargetDeg, double SmoothTime, double DeltaSeconds)
{
	const double Target = Deg + FMath::FindDeltaAngleDegrees(Deg, TargetDeg);
	SmoothDamp(Deg, Velocity, Target, SmoothTime, DeltaSeconds);
	Deg = FRotator::NormalizeAxis(Deg);
}

void EcoV3Observe::ArmStep(double& Arm, double& ArmVel, double Want, double SmoothTime, double DeltaSeconds)
{
	if (!(Arm >= 0.0) || Want <= Arm)
	{
		// 처음이거나 가려졌다: 바로 당긴다 (가린 것 뒤에 머물지 않게)
		Arm = Want;
		ArmVel = 0.0;
		return;
	}
	SmoothDamp(Arm, ArmVel, Want, SmoothTime, DeltaSeconds);
	if (Arm > Want)
	{
		Arm = Want;
		ArmVel = 0.0;
	}
}

bool EcoV3Observe::IsOccluderBox(const FBox& Box)
{
	if (!Box.IsValid)
	{
		return false;
	}
	const FVector E = Box.GetExtent();
	const double Half = FMath::Max(E.X, E.Y);
	return 2.0 * E.Z >= kOccluderMinHeightCm && Half >= kOccluderMinHalfCm && Half <= kOccluderMaxHalfCm;
}

bool EcoV3Observe::SegmentHitsBox(const FBox& Box, const FVector& A, const FVector& B)
{
	if (!Box.IsValid)
	{
		return false;
	}
	if (Box.IsInsideOrOn(A) || Box.IsInsideOrOn(B))
	{
		return true;
	}
	const FVector D = B - A;
	return !D.IsNearlyZero() && FMath::LineBoxIntersection(Box, A, B, D);
}

FBox2D EcoV3Observe::TeamMigrationPanelRect(const FVector2D& Canvas)
{
	const double W = FMath::Clamp(Canvas.X * 0.32, 300.0, 430.0);
	const double X = Canvas.X - W - 16.0;
	return FBox2D(FVector2D(X, 16.0), FVector2D(X + W, 16.0 + 376.0));
}

EcoV3Observe::FPanelLayout EcoV3Observe::LayoutPanel(const FVector2D& Canvas, const FVector2D& Content, float BaseScale, const FBox2D* Reserved)
{
	constexpr float Margin = kPanelMargin;
	constexpr float Gap = kPanelGap;
	constexpr float MinScale = kPanelMinScale;
	// 왼쪽 끝 한계: 팀 ECO INSPECTOR 판(왼쪽 위) 오른쪽 + 틈
	constexpr double LeftLimit = kTeamInspectorRightPx + static_cast<double>(Gap);
	FPanelLayout L;
	if (Content.X <= 0.0 || Content.Y <= 0.0 || Canvas.X <= 0.0 || Canvas.Y <= 0.0)
	{
		return L;
	}
	auto Fit = [&](double AvailW, double AvailH)
	{ return static_cast<float>(FMath::Min3(static_cast<double>(BaseScale), AvailW / Content.X, AvailH / Content.Y)); };
	// 1. 오른쪽 위 (팀 판이 있으면 그 밑). 너비 = 화면 48% 이면서 검사 판 오른쪽 안
	const float Top = Reserved ? static_cast<float>(Reserved->Max.Y) + Gap : Margin;
	const double MaxW = FMath::Min(Canvas.X * 0.48, Canvas.X - Margin - LeftLimit);
	const float S = Fit(MaxW, Canvas.Y - Top - Margin);
	if (S >= MinScale)
	{
		L.Scale = S;
		L.X = static_cast<float>(Canvas.X - Margin - Content.X * S);
		L.Y = Top;
		return L;
	}
	// 2. 팀 판 왼쪽 옆 (화면 오른쪽 절반·검사 판 오른쪽 안 — 왼쪽은 팀 검사 판·두뇌 알림 자리)
	if (Reserved)
	{
		const float S2 = Fit(Reserved->Min.X - Gap - FMath::Max(Canvas.X * 0.5, LeftLimit), Canvas.Y - 2.0 * Margin);
		if (S2 >= MinScale)
		{
			L.Scale = S2;
			L.X = static_cast<float>(Reserved->Min.X - Gap - Content.X * S2);
			L.Y = Margin;
			L.bBeside = true;
			return L;
		}
	}
	// 3. 그래도 안 들면 가장 작은 배율로 화면 안에 붙인다
	L.Scale = FMath::Max(MinScale, FMath::Min(S, BaseScale));
	L.X = FMath::Max(0.0f, static_cast<float>(Canvas.X - Margin - Content.X * L.Scale));
	L.Y = FMath::Max(0.0f, FMath::Min(Top, static_cast<float>(Canvas.Y - Margin - Content.Y * L.Scale)));
	return L;
}

TConstArrayView<EcoV3Observe::FKeyBind> EcoV3Observe::Keys()
{
	// 함수 안 static — EKeys 가 먼저 만들어진 뒤에 채운다
	static const TArray<FKeyBind> Table = {
		{EKeys::One, EAction::Wolf},		 {EKeys::NumPadOne, EAction::Wolf},
		{EKeys::Two, EAction::Deer},		 {EKeys::NumPadTwo, EAction::Deer},
		{EKeys::Three, EAction::Top},		 {EKeys::NumPadThree, EAction::Top},
		{EKeys::Four, EAction::Quarter},	 {EKeys::NumPadFour, EAction::Quarter},
		{EKeys::Five, EAction::Auto},		 {EKeys::NumPadFive, EAction::Auto},
		{EKeys::Zero, EAction::Player},		 {EKeys::NumPadZero, EAction::Player},
		{EKeys::Comma, EAction::Prev},		 {EKeys::Period, EAction::Next},
		{EKeys::Hyphen, EAction::ZoomOut},	 {EKeys::Subtract, EAction::ZoomOut}, {EKeys::MouseScrollDown, EAction::ZoomOut},
		{EKeys::Equals, EAction::ZoomIn},	 {EKeys::Add, EAction::ZoomIn},		  {EKeys::MouseScrollUp, EAction::ZoomIn},
		{EKeys::G, EAction::Region},		 {EKeys::H, EAction::Help},
	};
	return Table;
}

TConstArrayView<FKey> EcoV3Observe::TeamReservedKeys()
{
	// JYU 검사 HUD(Tab·R·마우스 가운데)·무리 이주 판(M·[ ])·플레이어(F·Shift·Ctrl)·기본 입력(WASD·Space·방향키)
	static const TArray<FKey> Reserved = {
		EKeys::Tab,	  EKeys::R,			   EKeys::M,		   EKeys::LeftBracket, EKeys::RightBracket, EKeys::MiddleMouseButton,
		EKeys::F,	  EKeys::LeftShift,	   EKeys::LeftControl, EKeys::W,		   EKeys::A,			EKeys::S,
		EKeys::D,	  EKeys::SpaceBar,	   EKeys::Up,		   EKeys::Down,		   EKeys::Left,			EKeys::Right,
	};
	return Reserved;
}

TConstArrayView<EcoV3Observe::FFreeKey> EcoV3Observe::FreeMoveKeys()
{
	// (앞, 오른쪽, 위). W A S D·방향키는 팀 기본 이동 키지만 자유 카메라에서는 폰 이동 입력이 막혀 있어 폰이 걷지 않는다. Q·E 는 팀·기본 입력이 쓰지 않는다
	static const TArray<FFreeKey> Table = {
		{EKeys::W, FVector(1.0, 0.0, 0.0)},	 {EKeys::S, FVector(-1.0, 0.0, 0.0)},	 {EKeys::D, FVector(0.0, 1.0, 0.0)},	 {EKeys::A, FVector(0.0, -1.0, 0.0)},
		{EKeys::Up, FVector(1.0, 0.0, 0.0)}, {EKeys::Down, FVector(-1.0, 0.0, 0.0)}, {EKeys::Right, FVector(0.0, 1.0, 0.0)}, {EKeys::Left, FVector(0.0, -1.0, 0.0)},
		{EKeys::E, FVector(0.0, 0.0, 1.0)},	 {EKeys::Q, FVector(0.0, 0.0, -1.0)},
	};
	return Table;
}

TConstArrayView<FKey> EcoV3Observe::FreeFastKeys()
{
	static const TArray<FKey> Fast = {EKeys::LeftShift, EKeys::RightShift};
	return Fast;
}

FVector EcoV3Observe::FreeMoveInput(TFunctionRef<bool(const FKey&)> IsDown)
{
	FVector Pos = FVector::ZeroVector;   // 칸마다 + 쪽이 눌렸는가 (W 와 위 방향키를 같이 눌러도 1)
	FVector Neg = FVector::ZeroVector;
	for (const FFreeKey& K : FreeMoveKeys())
	{
		if (IsDown(K.Key))
		{
			for (int32 c = 0; c < 3; ++c)
			{
				if (K.Axis[c] > 0.0)
				{
					Pos[c] = 1.0;
				}
				else if (K.Axis[c] < 0.0)
				{
					Neg[c] = 1.0;
				}
			}
		}
	}
	return Pos - Neg;   // 반대 키를 같이 누르면 0
}

void EcoV3Observe::FreeFlyStep(FVector& Location, FVector& Velocity, const FRotator& View, const FVector& Input, double SpeedCm, double DeltaSeconds)
{
	if (!(DeltaSeconds > 0.0) || !FMath::IsFinite(DeltaSeconds) || !FMath::IsFinite(SpeedCm))
	{
		return;
	}
	FVector In = Input.ContainsNaN() ? FVector::ZeroVector : Input;
	if (In.SizeSquared() > 1.0)
	{
		In.Normalize();
	}
	const FVector Fwd = View.Vector();
	const FVector Right = FRotationMatrix(FRotator(0.0, View.Yaw, 0.0)).GetUnitAxis(EAxis::Y);
	FVector Want = (Fwd * In.X + Right * In.Y + FVector::UpVector * In.Z);
	if (Want.SizeSquared() > 1.0)
	{
		Want.Normalize();   // 앞(숙임) + 위를 같이 눌러도 바라는 속도는 SpeedCm 을 넘지 않는다
	}
	Want *= FMath::Max(SpeedCm, 0.0);
	// 지수 다가가기 (넘침 없음·큰 프레임에도 안정): 시간 상수 kFreeAccelSmooth 마다 남은 차이가 1/e 로
	const double Alpha = 1.0 - FMath::Exp(-DeltaSeconds / kFreeAccelSmooth);
	Velocity += (Want - Velocity) * Alpha;
	if (Want.IsNearlyZero() && Velocity.SizeSquared() < 1.0)
	{
		Velocity = FVector::ZeroVector;   // 1 cm/s 밑이면 선다
	}
	Location += Velocity * DeltaSeconds;
}

void EcoV3Observe::FreeLookStep(double& YawDeg, double& PitchDeg, const FRotator& PrevControl, const FRotator& NowControl)
{
	const double DYaw = FMath::FindDeltaAngleDegrees(PrevControl.Yaw, NowControl.Yaw);
	const double DPitch = FMath::FindDeltaAngleDegrees(PrevControl.Pitch, NowControl.Pitch);
	if (!FMath::IsFinite(DYaw) || !FMath::IsFinite(DPitch) || FMath::Abs(DYaw) > kFreeLookJumpDeg || FMath::Abs(DPitch) > kFreeLookJumpDeg)
	{
		return;   // 한 프레임에 크게 바뀐 것은 마우스가 아니다 (폰 다시 잡기 등이 컨트롤러 방향을 새로 정함) — 카메라를 돌리지 않는다
	}
	YawDeg = FRotator::NormalizeAxis(YawDeg + DYaw);
	PitchDeg = FMath::Clamp(FRotator::NormalizeAxis(PitchDeg) + DPitch, -kFreePitchLimit, kFreePitchLimit);
}

int32 EcoV3Observe::CenterSubject(TConstArrayView<FSubject> Subjects, int32 Species, const FVector& Eye, const FVector& Forward, double MaxAngleDeg,
								  double MaxRangeCm)
{
	const FVector Fwd = Forward.GetSafeNormal();
	if (Fwd.IsNearlyZero())
	{
		return INDEX_NONE;
	}
	const double MinCos = FMath::Cos(FMath::DegreesToRadians(FMath::Clamp(MaxAngleDeg, 0.0, 180.0)));
	int32 Best = INDEX_NONE;
	double BestCos = -2.0;
	double BestDist = 0.0;
	for (int32 i = 0; i < Subjects.Num(); ++i)
	{
		const FSubject& S = Subjects[i];
		if (!S.bAlive || (Species >= 0 && S.bWolf != (Species == 1)))
		{
			continue;
		}
		const FVector To = S.Location + FVector(0.0, 0.0, EcoV3ObserverCameraImpl::kFocusUpCm) - Eye;
		const double D = To.Size();
		if (D > MaxRangeCm)
		{
			continue;
		}
		const double C = D > UE_KINDA_SMALL_NUMBER ? FVector::DotProduct(To / D, Fwd) : 1.0;
		if (C < MinCos)
		{
			continue;
		}
		constexpr double Eps = 1.0e-9;
		const bool bBetter = Best == INDEX_NONE || C > BestCos + Eps
							 || (C >= BestCos - Eps && (D < BestDist - 1.0e-6 || (D <= BestDist + 1.0e-6 && S.Id < Subjects[Best].Id)));
		if (bBetter)
		{
			Best = i;
			BestCos = C;
			BestDist = D;
		}
	}
	return Best;
}

TArray<FString> EcoV3Observe::KeyHelpLines()
{
	return {
		TEXT("1   늑대 시점 (다시 누르면 다음 늑대)"),
		TEXT("2   사슴 시점 (다시 누르면 다음 사슴)"),
		TEXT("3   탑뷰          4   쿼터뷰 (45°)"),
		TEXT("5   자동 추적 (쫓기는 사슴·사냥 늑대)"),
		TEXT(",  .   이전·다음 대상     G   지역 바꾸기"),
		TEXT("-  =  휠   줌 (자유 카메라: 이동 속도)"),
		TEXT("0   관찰 중: 그 자리에서 추적 풀기 (자유 카메라)"),
		TEXT("     자유 카메라에서 다시 0: 플레이어로"),
		TEXT("자유 카메라   W A S D 이동 · Q E 아래·위"),
		TEXT("     마우스 시야 · Shift 빠르게"),
	};
}

// =============================================================================
// UEcoV3ObserverCameraSubsystem
// =============================================================================

const TCHAR* UEcoV3ObserverCameraSubsystem::ModeNameKo(EEcoV3CamMode M)
{
	switch (M)
	{
	case EEcoV3CamMode::Wolf: return TEXT("늑대 시점");
	case EEcoV3CamMode::Deer: return TEXT("사슴 시점");
	case EEcoV3CamMode::Top: return TEXT("탑뷰");
	case EEcoV3CamMode::Quarter: return TEXT("쿼터뷰");
	case EEcoV3CamMode::Auto: return TEXT("자동 추적");
	case EEcoV3CamMode::Free: return TEXT("자유 카메라");
	default: return TEXT("원래 카메라");
	}
}

bool UEcoV3ObserverCameraSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	// 데디케이티드 서버(보는 화면이 없다)와 촬영 감독 실행(-EcoV3Film= — 촬영 카메라와 보기 대상을 다투지 않고 촬영 프레임이 전과 같게)에는 만들지 않는다
	FString FilmName;
	if (IsRunningDedicatedServer() || FParse::Value(FCommandLine::Get(), TEXT("EcoV3Film="), FilmName))
	{
		return false;
	}
	return Super::ShouldCreateSubsystem(Outer);
}

bool UEcoV3ObserverCameraSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UEcoV3ObserverCameraSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	DrawHandle = UDebugDrawService::Register(TEXT("Game"), FDebugDrawDelegate::CreateUObject(this, &UEcoV3ObserverCameraSubsystem::DrawPanel));
}

void UEcoV3ObserverCameraSubsystem::Deinitialize()
{
	if (DrawHandle.IsValid())
	{
		UDebugDrawService::Unregister(DrawHandle);
		DrawHandle.Reset();
	}
	// 월드를 닫는 중이면 카메라 액터는 레벨과 함께 사라진다 — 그때는 지우지 않는다
	const UWorld* World = GetWorld();
	if (IsValid(Camera.Get()) && World && !World->bIsTearingDown)
	{
		Camera->Destroy();
	}
	if (World && !World->bIsTearingDown)
	{
		ClearOccluders(LocalPlayerController());
	}
	// 이동 막기는 월드를 닫는 중에도 푼다 — 끊김 없는 이동(seamless travel)이면 플레이어 컨트롤러가 다음 월드로 넘어간다
	ReleaseMoveInputBlock(TEXT("월드 닫기"));
	HiddenOccluders.Reset();
	OccluderCandidates.Reset();
	Camera = nullptr;
	bViewOwned = false;
	Super::Deinitialize();
}

TStatId UEcoV3ObserverCameraSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UEcoV3ObserverCameraSubsystem, STATGROUP_Tickables);
}

APlayerController* UEcoV3ObserverCameraSubsystem::LocalPlayerController() const
{
	UWorld* World = GetWorld();
	if (!World || World->GetNetMode() == NM_DedicatedServer)
	{
		return nullptr;
	}
	for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
	{
		if (APlayerController* PC = It->Get(); PC && PC->IsLocalController())
		{
			return PC;
		}
	}
	return nullptr;
}

void UEcoV3ObserverCameraSubsystem::Tick(float DeltaTime)
{
	using namespace EcoV3ObserverCameraImpl;
	Super::Tick(DeltaTime);
	APlayerController* PC = LocalPlayerController();
	if (!PC)
	{
		SyncMoveInputBlock(nullptr);   // 로컬 플레이어 컨트롤러가 없어졌다 — 막아 둔 것이 있으면 푼다
		return;
	}
	if (CVarCamEnable.GetValueOnGameThread() == 0)
	{
		if (Mode != EEcoV3CamMode::Player)
		{
			RestorePlayerView(TEXT("eco.Cam.Enable 0"));
		}
		SyncMoveInputBlock(PC);   // 꺼짐 = 막지 않는다
		return;
	}
	HandleKeys(*PC);
	// 관찰 중(1~5·자유 카메라)이면 플레이어 이동 입력을 막고 원래 카메라면 푼다 (eco.Cam.BlockMove 를 바꾸면 이 자리에서 따른다)
	SyncMoveInputBlock(PC);
	const double Now = FPlatformTime::Seconds();
	if (Mode == EEcoV3CamMode::Free)
	{
		// 자유 카메라: 대상이 없다 — 개체 수(화면 글)만 1 초마다 다시 읽고 키·마우스로 카메라를 옮긴다 (실시간)
		if (Now >= NextPresenceCheck)
		{
			NextPresenceCheck = Now + kPresenceEverySeconds;
			Refresh();
		}
		UpdateFreeCamera(FMath::Clamp(FApp::GetDeltaTime(), 0.0, 0.1), *PC);
	}
	else if (Mode != EEcoV3CamMode::Player)
	{
		// 실시간 (느린 재생 slomo·멈춤에서도 카메라는 제 속도로)
		const double Dt = FMath::Clamp(FApp::GetDeltaTime(), 0.0, 0.1);
		Refresh();
		MaintainSubject(Now);
		UpdateCamera(Dt, *PC);
	}
	else if (Now >= NextPresenceCheck)
	{
		// 원래 카메라: 화면 글을 그릴지(통합 개체가 있는지)만 1 초마다 다시 본다
		NextPresenceCheck = Now + kPresenceEverySeconds;
		Refresh();
	}
	BuildStatusLines();
}

void UEcoV3ObserverCameraSubsystem::HandleKeys(APlayerController& PC)
{
	// 콘솔에 치는 중이면 반응하지 않는다
	if (EcoV3ObserverCameraImpl::IsConsoleOpen(PC))
	{
		return;
	}
	uint32 Done = 0;   // 별칭(숫자패드·휠)이 같은 프레임에 겹쳐도 동작은 한 번
	for (const EcoV3Observe::FKeyBind& B : EcoV3Observe::Keys())
	{
		const uint32 Bit = 1u << static_cast<uint32>(B.Action);
		if ((Done & Bit) == 0 && PC.WasInputKeyJustPressed(B.Key))
		{
			Done |= Bit;
			DoAction(B.Action);
		}
	}
}

void UEcoV3ObserverCameraSubsystem::DoAction(EcoV3Observe::EAction Action)
{
	using EcoV3Observe::EAction;
	const bool bFollow = IsFollowing();
	const bool bFree = Mode == EEcoV3CamMode::Free;
	switch (Action)
	{
	case EAction::Wolf: SetMode(EEcoV3CamMode::Wolf); break;
	case EAction::Deer: SetMode(EEcoV3CamMode::Deer); break;
	case EAction::Top: SetMode(EEcoV3CamMode::Top); break;
	case EAction::Quarter: SetMode(EEcoV3CamMode::Quarter); break;
	case EAction::Auto: SetMode(EEcoV3CamMode::Auto); break;
	case EAction::Player:
		// 10-29 사용자: 관찰 중 0 = 그 자리에서 추적 풀기(자유 카메라), 자유 카메라에서 다시 0 = 원래 카메라. 원래 카메라일 때는 아무 일 없음
		if (bFollow)
		{
			EnterFree(TEXT("0 — 그 자리에서 추적 풀기"));
		}
		else if (bFree)
		{
			RestorePlayerView(TEXT("원래 카메라"));
		}
		break;
	case EAction::Prev: if (bFollow) { StepSubject(-1); } break;
	case EAction::Next: if (bFollow) { StepSubject(+1); } break;
	case EAction::ZoomOut:
		if (bFollow)
		{
			ZoomBy(1.2);
		}
		else if (bFree)
		{
			SetFreeSpeed(FreeSpeedCm / 100.0 / EcoV3Observe::kFreeSpeedStep);   // 자유 카메라: 느리게
		}
		break;
	case EAction::ZoomIn:
		if (bFollow)
		{
			ZoomBy(1.0 / 1.2);
		}
		else if (bFree)
		{
			SetFreeSpeed(FreeSpeedCm / 100.0 * EcoV3Observe::kFreeSpeedStep);   // 자유 카메라: 빠르게
		}
		break;
	case EAction::Region: if (bFollow || bFree) { CycleRegionBy(+1); } break;
	case EAction::Help: ToggleKeyList(); break;
	default: break;
	}
}

void UEcoV3ObserverCameraSubsystem::Refresh()
{
	if (UWorld* World = GetWorld())
	{
		TArray<EcoV3Observe::FSubject> Fresh;
		if (EcoV3Observe::Gather(*World, Fresh))   // Mass 처리 중이면 지난 목록을 그대로 쓴다
		{
			Subjects = MoveTemp(Fresh);
		}
		EcoV3Observe::GatherRegions(*World, Subjects, Regions);
		bHasCreatures = !Subjects.IsEmpty();
	}
}

FVector UEcoV3ObserverCameraSubsystem::ReferencePoint() const
{
	if (Mode == EEcoV3CamMode::Free)
	{
		return FreeViewCenter();   // 자유 카메라: 화면 가운데 (1~5·G 가 그 곁 지역·개체를 고른다)
	}
	if (Mode != EEcoV3CamMode::Player && Camera)
	{
		return Focus;
	}
	if (const APlayerController* PC = LocalPlayerController())
	{
		FVector Loc;
		FRotator Rot;
		PC->GetPlayerViewPoint(Loc, Rot);
		return Loc;
	}
	return FVector::ZeroVector;
}

void UEcoV3ObserverCameraSubsystem::EnsureRegion()
{
	if (Region.IsNone() || !EcoV3ObserverCameraImpl::FindRegion(Regions, Region))
	{
		Region = EcoV3Observe::RegionAt(Regions, ReferencePoint());
	}
}

void UEcoV3ObserverCameraSubsystem::SelectSubject(int64 Id, const TCHAR* Why)
{
	const int32 i = EcoV3Observe::FindIndex(Subjects, Id);
	const int64 NewId = i != INDEX_NONE ? Id : 0;
	if (i != INDEX_NONE)
	{
		Region = Subjects[i].Region;
		LastSubjectLoc = Subjects[i].Location;
	}
	if (NewId == SubjectId)
	{
		return;
	}
	SubjectId = NewId;
	EventEndAt = -1.0;
	if (i != INDEX_NONE)
	{
		const EcoV3Observe::FSubject& S = Subjects[i];
		UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] %s · 대상 %s #%lld (%s) · %s — %s"), ModeNameKo(Mode), S.bWolf ? TEXT("늑대") : TEXT("사슴"), S.Id,
			   *S.Region.ToString(), EcoV3Observe::StateNameKo(S.State), Why);
	}
	else
	{
		UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] %s · 대상 없음 (%s 무대 전체) — %s"), ModeNameKo(Mode), *Region.ToString(), Why);
	}
}

void UEcoV3ObserverCameraSubsystem::SetMode(EEcoV3CamMode NewMode, int64 ExplicitId)
{
	using namespace EcoV3Observe;
	if (EcoV3ObserverCameraImpl::CVarCamEnable.GetValueOnGameThread() == 0)
	{
		return;
	}
	if (NewMode == EEcoV3CamMode::Player)
	{
		RestorePlayerView(TEXT("원래 카메라"));
		return;
	}
	if (NewMode == EEcoV3CamMode::Free)
	{
		EnterFree(TEXT("eco.Cam.Free"));
		return;
	}
	Refresh();
	if (Subjects.IsEmpty())
	{
		UE_LOG(LogEcoV3Cam, Warning, TEXT("[EcoCam] 통합 개체가 없다 — 관찰 카메라를 켜지 않는다 (팀 조정자가 개체를 만든 뒤, 통합 v3·팀 생태 레벨에서 쓴다)"));
		return;
	}
	const EEcoV3CamMode Prev = Mode;
	const bool bFromFree = Prev == EEcoV3CamMode::Free;
	if (bFromFree)
	{
		// 자유 카메라가 지금 보는 지역에서 고른다 (G 로 고른 지역에 그대로 있으면 고정도 그대로, 날아서 다른 지역으로 갔으면 그 지역·고정 풀기)
		const FName At = RegionAt(Regions, ReferencePoint());
		if (!At.IsNone() && At != Region)
		{
			Region = At;
			bRegionLocked = false;
		}
	}
	EnsureRegion();
	const int32 CurIdx = FindIndex(Subjects, SubjectId);
	const FSubject* Cur = CurIdx != INDEX_NONE ? &Subjects[CurIdx] : nullptr;
	int64 NewId = 0;
	const TCHAR* Why = TEXT("모드 바꿈");
	switch (NewMode)
	{
	case EEcoV3CamMode::Wolf:
	case EEcoV3CamMode::Deer:
	{
		const bool bWolf = NewMode == EEcoV3CamMode::Wolf;
		int32 Idx = INDEX_NONE;
		if (ExplicitId > 0)
		{
			Idx = FindIndex(Subjects, ExplicitId);
			if (Idx != INDEX_NONE && Subjects[Idx].bWolf != bWolf)
			{
				UE_LOG(LogEcoV3Cam, Warning, TEXT("[EcoCam] #%lld 는 %s 가 아니다"), ExplicitId, bWolf ? TEXT("늑대") : TEXT("사슴"));
				Idx = INDEX_NONE;
			}
			Why = TEXT("id 로 고름");
		}
		else if (Prev == NewMode && Cur && Cur->bWolf == bWolf)
		{
			Idx = CycleSubject(Subjects, bWolf, Cur->Region, Cur->Id, +1);   // 같은 키를 다시 누름 = 다음 개체
			Why = TEXT("다음 개체");
		}
		else if (Cur && Cur->bWolf == bWolf && Cur->bAlive)
		{
			Idx = CurIdx;   // 지금 보던 개체를 그 시점으로
		}
		else
		{
			if (bFromFree)
			{
				// 자유 카메라에서: 화면 가운데에 보이는 그 종 (10-29 — 날아가서 보던 개체를 바로 따라간다)
				Idx = CenterSubject(Subjects, bWolf ? 1 : 0, FreeLoc, GetFreeRotation().Vector(), kCenterPickDeg, kCenterPickCm);
				Why = TEXT("화면 가운데");
			}
			if (Idx == INDEX_NONE)
			{
				// 늑대: 사냥 중인 늑대를 먼저. 사슴: 지금 보던 늑대 곁(없으면 보는 자리 곁) 사슴
				const FVector From = Cur ? Cur->Location : ReferencePoint();
				const FName R = Cur ? Cur->Region : Region;
				Idx = NearestSubject(Subjects, bWolf, R, From, bWolf);
				if (Idx == INDEX_NONE)
				{
					Idx = NearestSubject(Subjects, bWolf, NAME_None, From, bWolf);
				}
				Why = Cur ? TEXT("보던 개체 곁") : TEXT("보는 자리 곁");
			}
		}
		NewId = Idx != INDEX_NONE ? Subjects[Idx].Id : 0;
		if (NewId == 0)
		{
			if (ExplicitId <= 0)
			{
				UE_LOG(LogEcoV3Cam, Warning, TEXT("[EcoCam] 산 %s 가 없다"), bWolf ? TEXT("늑대") : TEXT("사슴"));
			}
			if (Prev == EEcoV3CamMode::Player || bFromFree)
			{
				return;   // 원래 카메라·자유 카메라 그대로
			}
		}
		break;
	}
	case EEcoV3CamMode::Top:
	case EEcoV3CamMode::Quarter:
		NewId = ExplicitId > 0 ? ExplicitId : (Cur ? Cur->Id : 0);
		if (NewId == 0 && bFromFree)
		{
			const int32 Ci = CenterSubject(Subjects, -1, FreeLoc, GetFreeRotation().Vector(), kCenterPickDeg, kCenterPickCm);
			if (Ci != INDEX_NONE)
			{
				NewId = Subjects[Ci].Id;
				Why = TEXT("화면 가운데");
			}
		}
		break;
	case EEcoV3CamMode::Auto:
	{
		int64 Partner = 0;
		const int32 Idx = PickAuto(Subjects, Region, bRegionLocked, 0, Partner);
		NewId = Idx != INDEX_NONE ? Subjects[Idx].Id : (Cur ? Cur->Id : 0);
		Why = Idx != INDEX_NONE ? TEXT("사건 고름") : TEXT("사건 없음 — 기다림");
		break;
	}
	default:
		break;
	}
	if (Prev != NewMode)
	{
		Zoom = 1.0;
	}
	Mode = NewMode;
	if (Prev != NewMode)
	{
		UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 모드 %s → %s"), ModeNameKo(Prev), ModeNameKo(NewMode));
	}
	SelectSubject(NewId, Why);
	EventEndAt = -1.0;
	if (bFromFree)
	{
		// 카메라가 자유 카메라 자리에서 대상(없으면 지역 무대)으로 부드럽게 옮겨 간다
		const int32 Si = FindIndex(Subjects, SubjectId);
		const FRegionInfo* R = EcoV3ObserverCameraImpl::FindRegion(Regions, Region);
		FollowFromFree(Si != INDEX_NONE ? Subjects[Si].Location : (R ? R->CenterCm : FreeViewCenter()));
	}
	if (APlayerController* PC = LocalPlayerController())
	{
		ActivateCamera(*PC);
	}
}

void UEcoV3ObserverCameraSubsystem::EnterFree(const TCHAR* Why)
{
	using namespace EcoV3ObserverCameraImpl;
	if (CVarCamEnable.GetValueOnGameThread() == 0)
	{
		return;
	}
	if (Mode == EEcoV3CamMode::Free)
	{
		UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 이미 자유 카메라 — 0 을 한 번 더(eco.Cam.Player) 누르면 원래 카메라"));
		return;
	}
	const EEcoV3CamMode Prev = Mode;
	APlayerController* PC = LocalPlayerController();
	// 지금 화면의 카메라 자리·방향 그대로 (카메라 액터가 없으면 따라가기 상태, 원래 카메라면 지금 보는 자리)
	FVector Loc = FVector::ZeroVector;
	FRotator Rot = FRotator::ZeroRotator;
	if (IsValid(Camera.Get()) && bViewOwned)
	{
		Loc = Camera->GetActorLocation();
		Rot = Camera->GetActorRotation();
	}
	else if (Prev != EEcoV3CamMode::Player)
	{
		Rot = FRotator(Pitch, Yaw, 0.0);
		Loc = Focus - Rot.Vector() * (Arm >= 0.0 ? Arm : Dist);
	}
	else if (PC)
	{
		PC->GetPlayerViewPoint(Loc, Rot);
	}
	Mode = EEcoV3CamMode::Free;
	SubjectId = 0;
	PartnerId = 0;
	EventEndAt = -1.0;
	FreeLoc = Loc;
	FreeVel = FVector::ZeroVector;
	FreeYaw = FRotator::NormalizeAxis(Rot.Yaw);
	FreePitch = FMath::Clamp(FRotator::NormalizeAxis(Rot.Pitch), -EcoV3Observe::kFreePitchLimit, EcoV3Observe::kFreePitchLimit);
	bFreeFast = false;
	bFreeGround = false;
	bHasLastControl = false;
	if (PC)
	{
		ClearOccluders(PC);   // 따라가기에서 숨긴 나무를 되돌린다 (자유 카메라는 보이는 그대로)
		ActivateCamera(*PC);  // 원래 카메라에서 왔으면 카메라를 띄워 보기 대상으로 (이동 막기도 바로)
		if (Camera)
		{
			Camera->SetActorLocationAndRotation(FreeLoc, GetFreeRotation());
		}
		LastControlRot = PC->GetControlRotation();
		bHasLastControl = true;
	}
	UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 모드 %s → 자유 카메라 — %s (자리 %.1f, %.1f, %.1f m · 방위 %.0f° · 숙임 %.0f° · 속도 %s m/s)"), ModeNameKo(Prev), Why,
		   FreeLoc.X / 100.0, FreeLoc.Y / 100.0, FreeLoc.Z / 100.0, FreeYaw, FreePitch, *SpeedText(FreeSpeedCm / 100.0));
}

void UEcoV3ObserverCameraSubsystem::SetFreeSpeed(double MetersPerSecond)
{
	using namespace EcoV3Observe;
	if (FMath::IsFinite(MetersPerSecond) && MetersPerSecond > 0.0)
	{
		FreeSpeedCm = FMath::Clamp(MetersPerSecond * 100.0, kFreeMinSpeedCm, kFreeMaxSpeedCm);
	}
}

void UEcoV3ObserverCameraSubsystem::SetFreePose(const FVector& Location, const FRotator& Rotation)
{
	if (Mode != EEcoV3CamMode::Free)
	{
		return;
	}
	FreeLoc = Location;
	FreeVel = FVector::ZeroVector;
	FreeYaw = FRotator::NormalizeAxis(Rotation.Yaw);
	FreePitch = FMath::Clamp(FRotator::NormalizeAxis(Rotation.Pitch), -EcoV3Observe::kFreePitchLimit, EcoV3Observe::kFreePitchLimit);
	if (Camera && bViewOwned)
	{
		Camera->SetActorLocationAndRotation(FreeLoc, GetFreeRotation());
	}
}

FVector UEcoV3ObserverCameraSubsystem::FreeViewCenter() const
{
	using namespace EcoV3ObserverCameraImpl;
	UWorld* World = GetWorld();
	if (!World)
	{
		return FreeLoc;
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3CamFreeCenter), false);
	if (Camera)
	{
		Params.AddIgnoredActor(Camera);
	}
	if (const APlayerController* PC = LocalPlayerController(); PC && PC->GetPawn())
	{
		Params.AddIgnoredActor(PC->GetPawn());
	}
	TArray<FHitResult> Hits;
	World->LineTraceMultiByObjectType(Hits, FreeLoc, FreeLoc + GetFreeRotation().Vector() * kFreeCenterTraceCm, FCollisionObjectQueryParams(ECC_WorldStatic),
									  Params);
	double Best = TNumericLimits<double>::Max();
	FVector Out = FreeLoc;
	for (const FHitResult& H : Hits)
	{
		if (IsVisibleBlock(H) && H.Distance < Best)
		{
			Best = H.Distance;
			Out = H.ImpactPoint;
		}
	}
	return Out;
}

void UEcoV3ObserverCameraSubsystem::FollowFromFree(const FVector& TargetPoint)
{
	using namespace EcoV3ObserverCameraImpl;
	// 카메라 자리 = Focus − 방향 × Arm 이 지금 자유 카메라 자리와 같게 두고, 다음 프레임부터 초점·방위·숙임·거리가 대상 쪽으로 부드럽게 간다
	const FRotator R = GetFreeRotation();
	const double D = FMath::Clamp(FVector::Dist(FreeLoc, TargetPoint), kArmMinCm, 0.9 * kSnapCm);
	Focus = FreeLoc + R.Vector() * D;
	FocusVel = FVector::ZeroVector;
	Yaw = FreeYaw;
	Pitch = FreePitch;
	Dist = D;
	Arm = D;
	YawVel = PitchVel = DistVel = ArmVel = 0.0;
	bSnap = false;
}

void UEcoV3ObserverCameraSubsystem::MoveFreeToRegion(const EcoV3Observe::FRegionInfo& R)
{
	using namespace EcoV3ObserverCameraImpl;
	// 대상 없는 무대 전체 보기와 같은 자리 (45° 사선 · −40° · 무대 한 변 0.95 배)
	FreeYaw = kQuarterYaw;
	FreePitch = kOverviewPitch;
	FreeVel = FVector::ZeroVector;
	const FRotator View = GetFreeRotation();
	FreeLoc = R.CenterCm + FVector(0.0, 0.0, kFocusUpCm) - View.Vector() * (0.95 * FMath::Max(R.SizeCm, 1000.0));
	if (GetWorld())
	{
		const double G = GroundZ(FreeLoc.X, FreeLoc.Y, FreeLoc.Z - 1.0e7);
		FreeLoc.Z = FMath::Max(FreeLoc.Z, G + kGroundClearCm);
	}
	if (Camera && bViewOwned)
	{
		Camera->SetActorLocationAndRotation(FreeLoc, View);
	}
	UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 자유 카메라 → %s 무대 전체가 보이는 자리 (%.1f, %.1f, %.1f m)"), *R.Id.ToString(), FreeLoc.X / 100.0,
		   FreeLoc.Y / 100.0, FreeLoc.Z / 100.0);
}

void UEcoV3ObserverCameraSubsystem::UpdateFreeCamera(double Dt, APlayerController& PC)
{
	using namespace EcoV3Observe;
	using namespace EcoV3ObserverCameraImpl;
	if (!Camera)
	{
		ActivateCamera(PC);
		if (!Camera)
		{
			return;
		}
	}
	if (PC.GetViewTarget() != Camera)
	{
		PC.SetViewTarget(Camera);   // 폰 다시 잡기 등으로 보기 대상이 바뀌었으면 되찾는다
	}
	// 마우스 시야: 컨트롤러 방향이 바뀐 만큼만 (컨트롤러·폰에는 쓰지 않는다)
	const FRotator Ctrl = PC.GetControlRotation();
	if (bHasLastControl)
	{
		FreeLookStep(FreeYaw, FreePitch, LastControlRot, Ctrl);
	}
	LastControlRot = Ctrl;
	bHasLastControl = true;
	// 키: 콘솔에 치는 중이면 읽지 않는다 (그동안 부드럽게 선다)
	FVector Input = FVector::ZeroVector;
	bFreeFast = false;
	if (!IsConsoleOpen(PC))
	{
		Input = FreeMoveInput([&PC](const FKey& K) { return PC.IsInputKeyDown(K); });
		for (const FKey& K : FreeFastKeys())
		{
			bFreeFast = bFreeFast || PC.IsInputKeyDown(K);
		}
	}
	const FRotator View = GetFreeRotation();
	FreeFlyStep(FreeLoc, FreeVel, View, Input, FreeSpeedCm * (bFreeFast ? kFreeFastMul : 1.0), Dt);
	// 땅 2 m 위 밑으로 가지 않는다 (따라가기와 같은 땅 찾기)
	constexpr double kNoGround = -1.0e7;
	LastGroundZ = GroundZ(FreeLoc.X, FreeLoc.Y, FreeLoc.Z + kNoGround);
	bFreeGround = LastGroundZ > FreeLoc.Z + 0.5 * kNoGround;
	if (bFreeGround && FreeLoc.Z < LastGroundZ + kGroundClearCm)
	{
		FreeLoc.Z = LastGroundZ + kGroundClearCm;
		FreeVel.Z = FMath::Max(FreeVel.Z, 0.0);
	}
	Camera->SetActorLocationAndRotation(FreeLoc, View);
}

void UEcoV3ObserverCameraSubsystem::StepSubject(int32 Dir)
{
	using namespace EcoV3Observe;
	if (!IsFollowing())
	{
		return;   // 원래 카메라·자유 카메라에는 대상이 없다
	}
	Refresh();
	if (Mode == EEcoV3CamMode::Auto)
	{
		int64 Partner = 0;
		const int32 Idx = PickAuto(Subjects, Region, bRegionLocked, SubjectId, Partner);
		if (Idx != INDEX_NONE && Subjects[Idx].Id != SubjectId)
		{
			SelectSubject(Subjects[Idx].Id, TEXT("다음 사건"));
		}
		else
		{
			UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 자동 추적: 다른 사건이 없다"));
		}
		return;
	}
	const int32 CurIdx = FindIndex(Subjects, SubjectId);
	const bool bWolf = CurIdx != INDEX_NONE ? Subjects[CurIdx].bWolf : Mode != EEcoV3CamMode::Deer;
	const FName R = CurIdx != INDEX_NONE ? Subjects[CurIdx].Region : Region;
	const int32 Idx = CycleSubject(Subjects, bWolf, R, SubjectId, Dir);
	if (Idx != INDEX_NONE)
	{
		SelectSubject(Subjects[Idx].Id, Dir >= 0 ? TEXT("다음 대상") : TEXT("이전 대상"));
	}
}

void UEcoV3ObserverCameraSubsystem::ZoomBy(double Factor)
{
	using namespace EcoV3ObserverCameraImpl;
	if (FMath::IsFinite(Factor) && Factor > 0.0)
	{
		Zoom = FMath::Clamp(Zoom * Factor, kMinZoom, kMaxZoom);
	}
}

void UEcoV3ObserverCameraSubsystem::SetZoomMeters(double Meters)
{
	using namespace EcoV3ObserverCameraImpl;
	const double Base = BaseDistanceCm();
	if (FMath::IsFinite(Meters) && Meters > 0.0 && Base > 0.0)
	{
		Zoom = FMath::Clamp(Meters * 100.0 / Base, kMinZoom, kMaxZoom);
	}
}

bool UEcoV3ObserverCameraSubsystem::SetRegion(FName RegionId)
{
	using namespace EcoV3Observe;
	Refresh();
	const FRegionInfo* R = EcoV3ObserverCameraImpl::FindRegion(Regions, RegionId);
	if (!R)
	{
		TArray<FString> Names;
		for (const FRegionInfo& Info : Regions)
		{
			Names.Add(Info.Id.ToString());
		}
		UE_LOG(LogEcoV3Cam, Warning, TEXT("[EcoCam] 지역 '%s' 없음 — 있는 지역: %s"), *RegionId.ToString(), *FString::Join(Names, TEXT(", ")));
		return false;
	}
	Region = R->Id;
	bRegionLocked = true;
	bSnap = true;
	switch (Mode)
	{
	case EEcoV3CamMode::Wolf:
	case EEcoV3CamMode::Deer:
	{
		const bool bWolf = Mode == EEcoV3CamMode::Wolf;
		const int32 Idx = NearestSubject(Subjects, bWolf, Region, R->CenterCm, bWolf);
		SelectSubject(Idx != INDEX_NONE ? Subjects[Idx].Id : 0, TEXT("지역 바꿈"));
		break;
	}
	case EEcoV3CamMode::Auto:
	{
		int64 Partner = 0;
		const int32 Idx = PickAuto(Subjects, Region, true, 0, Partner);
		SelectSubject(Idx != INDEX_NONE ? Subjects[Idx].Id : 0, TEXT("지역 바꿈"));
		break;
	}
	case EEcoV3CamMode::Top:
	case EEcoV3CamMode::Quarter:
		SelectSubject(0, TEXT("지역 바꿈"));
		break;
	case EEcoV3CamMode::Free:
		MoveFreeToRegion(*R);   // 자유 카메라 그대로, 그 지역 무대 전체가 보이는 자리로
		break;
	default:
		break;
	}
	Region = R->Id;   // 대상이 없어도 고른 지역에 머문다
	UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 지역 %s"), *Region.ToString());
	return true;
}

void UEcoV3ObserverCameraSubsystem::CycleRegionBy(int32 Dir)
{
	Refresh();
	if (Mode == EEcoV3CamMode::Free)
	{
		// 자유 카메라: 지금 보는 지역의 다음 지역 (날아서 옮겼을 수 있다)
		const FName At = EcoV3Observe::RegionAt(Regions, FreeViewCenter());
		if (!At.IsNone())
		{
			Region = At;
		}
	}
	EnsureRegion();
	const FName Next = EcoV3Observe::CycleRegion(Regions, Region, Dir);
	if (!Next.IsNone())
	{
		SetRegion(Next);
	}
}

void UEcoV3ObserverCameraSubsystem::ToggleKeyList()
{
	bShowKeys = !bShowKeys;
}

void UEcoV3ObserverCameraSubsystem::MaintainSubject(double Now)
{
	using namespace EcoV3Observe;
	using namespace EcoV3ObserverCameraImpl;
	int32 Idx = FindIndex(Subjects, SubjectId);
	if (SubjectId != 0 && Idx == INDEX_NONE && !Subjects.IsEmpty())
	{
		// 대상이 사라졌다 (조정자가 지운 개체 등)
		if (Mode == EEcoV3CamMode::Wolf || Mode == EEcoV3CamMode::Deer)
		{
			const int32 Near = NearestSubject(Subjects, Mode == EEcoV3CamMode::Wolf, Region, LastSubjectLoc, false);
			SelectSubject(Near != INDEX_NONE ? Subjects[Near].Id : 0, TEXT("대상이 사라져 가까운 개체로"));
		}
		else if (Mode == EEcoV3CamMode::Auto)
		{
			int64 Partner = 0;
			const int32 Next = PickAuto(Subjects, Region, bRegionLocked, SubjectId, Partner);
			SelectSubject(Next != INDEX_NONE ? Subjects[Next].Id : 0, TEXT("대상이 사라져 다음 사건으로"));
		}
		else
		{
			SelectSubject(0, TEXT("대상이 사라져 무대 전체로"));
		}
		Idx = FindIndex(Subjects, SubjectId);
	}
	const FSubject* S = Idx != INDEX_NONE ? &Subjects[Idx] : nullptr;
	if (S)
	{
		LastSubjectLoc = S->Location;
		Region = S->Region;
	}
	if (Mode == EEcoV3CamMode::Wolf || Mode == EEcoV3CamMode::Deer)
	{
		if (S && !S->bAlive)
		{
			if (EventEndAt < 0.0)
			{
				EventEndAt = Now;
			}
			else if (Now - EventEndAt >= kDeadHoldSeconds)
			{
				const int32 Near = NearestSubject(Subjects, S->bWolf, S->Region, S->Location, false);
				SelectSubject(Near != INDEX_NONE ? Subjects[Near].Id : 0, TEXT("대상이 죽어 가까운 개체로"));
			}
		}
		else
		{
			EventEndAt = -1.0;
		}
		PartnerId = 0;
		return;
	}
	if (Mode != EEcoV3CamMode::Auto)
	{
		PartnerId = 0;
		return;
	}
	if (S && IsEvent(*S))
	{
		EventEndAt = -1.0;
	}
	else if (EventEndAt < 0.0)
	{
		EventEndAt = Now;
	}
	const double Hold = (S && !S->bAlive) ? kDeadHoldSeconds : kLingerSeconds;
	if (EventEndAt >= 0.0 && Now - EventEndAt >= Hold && Now >= NextAutoSearch)
	{
		NextAutoSearch = Now + 0.5;
		int64 Partner = 0;
		const int32 Next = PickAuto(Subjects, Region, bRegionLocked, SubjectId, Partner);
		if (Next != INDEX_NONE && Subjects[Next].Id != SubjectId)
		{
			SelectSubject(Subjects[Next].Id, TEXT("사건 끝 — 다음 사건"));
		}
		else if (Next != INDEX_NONE && IsEvent(Subjects[Next]))
		{
			EventEndAt = -1.0;   // 같은 대상이 다시 사건 중
		}
		Idx = FindIndex(Subjects, SubjectId);
		S = Idx != INDEX_NONE ? &Subjects[Idx] : nullptr;
	}
	PartnerId = S ? PartnerOf(*S, kFramePairCm) : 0;
}

double UEcoV3ObserverCameraSubsystem::BaseDistanceCm() const
{
	using namespace EcoV3ObserverCameraImpl;
	const bool bSubject = EcoV3Observe::FindIndex(Subjects, SubjectId) != INDEX_NONE;
	if (!bSubject)
	{
		const EcoV3Observe::FRegionInfo* R = FindRegion(Regions, Region);
		const double Size = R ? R->SizeCm : 12000.0;
		return Mode == EEcoV3CamMode::Top ? FitTopCm(Size) : 0.95 * Size;
	}
	switch (Mode)
	{
	case EEcoV3CamMode::Wolf: return kWolfDistCm;
	case EEcoV3CamMode::Deer: return kDeerDistCm;
	case EEcoV3CamMode::Top: return kTopDistCm;
	case EEcoV3CamMode::Quarter: return kQuarterDistCm;
	case EEcoV3CamMode::Auto: return kAutoDistCm;
	default: return kQuarterDistCm;
	}
}

void UEcoV3ObserverCameraSubsystem::ActivateCamera(APlayerController& PC)
{
	using namespace EcoV3ObserverCameraImpl;
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (!Camera)
	{
		FVector Loc;
		FRotator Rot;
		PC.GetPlayerViewPoint(Loc, Rot);
		FActorSpawnParameters P;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		P.ObjectFlags |= RF_Transient;
		Camera = World->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), Loc, Rot, P);
		if (!Camera)
		{
			return;
		}
		Camera->GetCameraComponent()->bConstrainAspectRatio = false;
		Camera->GetCameraComponent()->SetFieldOfView(kFov);
		// 10-27 PIE 확인: 빠르게 따라가는 동안 움직임 흐림이 대상을 뭉갰다 — 관찰 카메라만 끈다 (다른 후처리는 그대로)
		FPostProcessSettings& PP = Camera->GetCameraComponent()->PostProcessSettings;
		PP.bOverride_MotionBlurAmount = true;
		PP.MotionBlurAmount = 0.0f;
	}
	if (!bViewOwned)
	{
		SavedViewTarget = PC.GetViewTarget();
		bViewOwned = true;
		bSnap = true;
		FVector Loc;
		FRotator Rot;
		PC.GetPlayerViewPoint(Loc, Rot);
		Yaw = Rot.Yaw;
	}
	if (PC.GetViewTarget() != Camera)
	{
		PC.SetViewTarget(Camera);
	}
	SyncMoveInputBlock(&PC);   // 콘솔 명령(eco.Cam.*)으로 켜도 다음 Tick 을 기다리지 않고 바로 막는다
}

void UEcoV3ObserverCameraSubsystem::SyncMoveInputBlock(APlayerController* PC)
{
	using namespace EcoV3ObserverCameraImpl;
	const bool bWant = PC != nullptr && Mode != EEcoV3CamMode::Player && CVarCamEnable.GetValueOnGameThread() != 0
					   && CVarCamBlockMove.GetValueOnGameThread() != 0;
	APlayerController* Held = MoveBlockedPC.Get();
	if (!Held)
	{
		MoveBlockedPC.Reset();   // 막아 둔 컨트롤러가 사라졌다 — 뺄 것이 없다
	}
	else if (!bWant || Held != PC)
	{
		const TCHAR* Why = TEXT("eco.Cam.BlockMove 0");
		if (bWant)
		{
			Why = TEXT("플레이어 컨트롤러 바뀜");   // 새 컨트롤러는 아래에서 막는다
		}
		else if (!PC)
		{
			Why = TEXT("로컬 플레이어 컨트롤러 없음");
		}
		else if (Mode == EEcoV3CamMode::Player)
		{
			Why = TEXT("원래 카메라");
		}
		else if (CVarCamEnable.GetValueOnGameThread() == 0)
		{
			Why = TEXT("eco.Cam.Enable 0");
		}
		ReleaseMoveInputBlock(Why);
		Held = nullptr;
	}
	if (!bWant)
	{
		return;
	}
	if (Held)
	{
		// 엔진이 이동 무시 수를 지웠으면 (폰 다시 시작 — APlayerController::ClientRestart 의 ResetIgnoreInputFlags) 다시 건다
		if (!PC->IsMoveInputIgnored())
		{
			PC->SetIgnoreMoveInput(true);
			UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 플레이어 이동 막기가 지워졌다 (폰 다시 시작) — 다시 막음"));
		}
		return;
	}
	PC->SetIgnoreMoveInput(true);   // 쌓이는 수에 하나만 더한다 (풀 때 이 하나만 뺀다)
	MoveBlockedPC = PC;
	UE_LOG(LogEcoV3Cam, Log,
		   TEXT("[EcoCam] 플레이어 이동 입력 막음 — 관찰 중 (원래 카메라로 돌아오면 풀린다 — 따라가기에서 0 두 번·자유 카메라에서 0, eco.Cam.BlockMove 0 이면 막지 않는다)"));
}

void UEcoV3ObserverCameraSubsystem::ReleaseMoveInputBlock(const TCHAR* Why)
{
	if (APlayerController* Held = MoveBlockedPC.Get())
	{
		Held->SetIgnoreMoveInput(false);   // 우리가 더한 하나만 뺀다 — 팀·엔진이 건 막기(영화 모드 등)는 남는다
		UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 플레이어 이동 입력 풀림 — %s"), Why);
	}
	MoveBlockedPC.Reset();
}

void UEcoV3ObserverCameraSubsystem::RestorePlayerView(const TCHAR* Why)
{
	const EEcoV3CamMode Prev = Mode;
	Mode = EEcoV3CamMode::Player;
	SubjectId = 0;
	PartnerId = 0;
	bRegionLocked = false;
	EventEndAt = -1.0;
	if (APlayerController* PC = LocalPlayerController(); PC && bViewOwned)
	{
		AActor* Back = PC->GetPawn() ? static_cast<AActor*>(PC->GetPawn()) : SavedViewTarget.Get();
		PC->SetViewTarget(Back ? Back : static_cast<AActor*>(PC));
	}
	ClearOccluders(LocalPlayerController());   // 이 화면에서 숨긴 나무를 되돌린다
	ReleaseMoveInputBlock(Why);                // 플레이어 이동 입력을 다시 받는다
	bViewOwned = false;
	bSnap = true;
	FreeVel = FVector::ZeroVector;             // 자유 카메라 (다음에 들어갈 때 그때 화면에서 새로 시작한다)
	bFreeFast = false;
	bHasLastControl = false;
	if (Prev != EEcoV3CamMode::Player)
	{
		UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 모드 %s → 원래 카메라 — %s"), ModeNameKo(Prev), Why);
	}
}

double UEcoV3ObserverCameraSubsystem::GroundZ(double XCm, double YCm, double Fallback) const
{
	// 땅 = 곧은 선이 맞은 WorldStatic 가운데 가장 낮은 것 (나무 잎·줄기 같은 위의 것은 건너뛴다 — 촬영 감독 GroundZ 와 같다)
	TArray<FHitResult> Hits;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3CamGround), false);
	if (Camera)
	{
		Params.AddIgnoredActor(Camera);
	}
	GetWorld()->LineTraceMultiByObjectType(Hits, FVector(XCm, YCm, 500000.0), FVector(XCm, YCm, -500000.0),
										   FCollisionObjectQueryParams(ECC_WorldStatic), Params);
	double Best = TNumericLimits<double>::Max();
	for (const FHitResult& H : Hits)
	{
		Best = FMath::Min(Best, H.ImpactPoint.Z);
	}
	return Best < TNumericLimits<double>::Max() ? Best : Fallback;
}

double UEcoV3ObserverCameraSubsystem::ClearArmCm(const FVector& From, const FVector& Dir, double WantCm) const
{
	using namespace EcoV3ObserverCameraImpl;
	UWorld* World = GetWorld();
	if (!World || WantCm <= kArmMinCm)
	{
		return WantCm;
	}
	// 카메라·플레이어 폰·대상·짝 표현 액터는 건너뛴다. 읽기만 한다
	FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3CamArm), false);
	if (Camera)
	{
		Params.AddIgnoredActor(Camera);
	}
	if (const APlayerController* PC = LocalPlayerController(); PC && PC->GetPawn())
	{
		Params.AddIgnoredActor(PC->GetPawn());
	}
	for (const int64 Id : {SubjectId, PartnerId})
	{
		if (Id > 0)
		{
			if (AEcoCreatureRepresentationActor* A = EcoV3Observe::FindActor(*World, Id))
			{
				Params.AddIgnoredActor(A);
			}
		}
	}
	// WorldStatic 물체 (지형·바위·나무 — 이 레벨의 나무는 카메라 채널을 막지 않아 채널 쓸기로는 잎을 못 찾았다. 땅 찾기 GroundZ 와 같은 물체 종류).
	// 보이지 않는 것(막는 부피·숨긴 액터)은 건너뛴다 — 무대 밖 보이지 않는 벽에 끌려 들어가지 않게
	TArray<FHitResult> Hits;
	World->SweepMultiByObjectType(Hits, From, From + Dir * WantCm, FQuat::Identity, FCollisionObjectQueryParams(ECC_WorldStatic),
								  FCollisionShape::MakeSphere(kArmProbeCm), Params);
	double Best = WantCm;
	for (const FHitResult& H : Hits)
	{
		const UPrimitiveComponent* C = H.GetComponent();
		const AActor* A = H.GetActor();
		if (H.bStartPenetrating || !C || !C->IsVisible() || C->bHiddenInGame || (A && (A->IsHidden() || A->IsA<AVolume>())))
		{
			continue;   // 처음부터 박힌 것(초점이 잎 속 — 당겨도 소용없다)·보이지 않는 것
		}
		Best = FMath::Min(Best, H.Distance - kArmGapCm);
	}
	return FMath::Clamp(Best, kArmMinCm, WantCm);
}

void UEcoV3ObserverCameraSubsystem::UpdateOccluders(APlayerController& PC, const FVector& From, const FVector& To)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	const double Now = FPlatformTime::Seconds();
	if (Now >= NextOccluderScan)
	{
		// 후보: 이 월드의 보이는 정적 메시 (인스턴스 묶음은 한 그루만 숨길 수 없어 뺀다) 가운데 나무 크기 상자. 개체·폰·카메라 것은 뺀다
		NextOccluderScan = Now + 5.0;
		const int32 Before = OccluderCandidates.Num();
		int32 TooBig = 0;
		OccluderCandidates.Reset();
		for (TObjectIterator<UStaticMeshComponent> It; It; ++It)
		{
			UStaticMeshComponent* C = *It;
			if (!C || C->GetWorld() != World || !C->IsRegistered() || C->IsA<UInstancedStaticMeshComponent>() || !C->IsVisible() || C->bHiddenInGame)
			{
				continue;
			}
			const AActor* Owner = C->GetOwner();
			if (!Owner || Owner == Camera || Owner->IsA<APawn>() || Owner->IsA<AEcoCreatureRepresentationActor>())
			{
				continue;
			}
			const FBox Box = C->Bounds.GetBox();
			if (EcoV3Observe::IsOccluderBox(Box))
			{
				OccluderCandidates.Add(C);
			}
			else if (Box.IsValid && FMath::Max(Box.GetExtent().X, Box.GetExtent().Y) > EcoV3Observe::kOccluderMaxHalfCm)
			{
				++TooBig;
			}
		}
		if (OccluderCandidates.Num() != Before)
		{
			UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] 가리는 나무 후보 %d (가로 반폭 %.0f m 넘는 큰 메시 %d 는 숨기지 않는다)"), OccluderCandidates.Num(),
				   EcoV3Observe::kOccluderMaxHalfCm / 100.0, TooBig);
		}
	}
	TArray<TWeakObjectPtr<UPrimitiveComponent>> Want;
	for (const TWeakObjectPtr<UPrimitiveComponent>& W : OccluderCandidates)
	{
		const UPrimitiveComponent* C = W.Get();
		if (C && EcoV3Observe::SegmentHitsBox(C->Bounds.GetBox(), From, To))
		{
			Want.Add(W);
		}
	}
	for (const TWeakObjectPtr<UPrimitiveComponent>& H : HiddenOccluders)
	{
		if (!Want.Contains(H))
		{
			PC.HiddenPrimitiveComponents.Remove(H);
		}
	}
	for (const TWeakObjectPtr<UPrimitiveComponent>& W : Want)
	{
		if (!HiddenOccluders.Contains(W))
		{
			PC.HiddenPrimitiveComponents.AddUnique(W);
		}
	}
	HiddenOccluders = MoveTemp(Want);
}

void UEcoV3ObserverCameraSubsystem::ClearOccluders(APlayerController* PC)
{
	if (PC)
	{
		for (const TWeakObjectPtr<UPrimitiveComponent>& H : HiddenOccluders)
		{
			PC->HiddenPrimitiveComponents.Remove(H);
		}
	}
	HiddenOccluders.Reset();
}

void UEcoV3ObserverCameraSubsystem::UpdateCamera(double Dt, APlayerController& PC)
{
	using namespace EcoV3Observe;
	using namespace EcoV3ObserverCameraImpl;
	if (!Camera)
	{
		ActivateCamera(PC);
		if (!Camera)
		{
			return;
		}
	}
	if (PC.GetViewTarget() != Camera)
	{
		PC.SetViewTarget(Camera);   // 폰 다시 잡기 등으로 보기 대상이 바뀌었으면 되찾는다
	}
	const int32 Si = FindIndex(Subjects, SubjectId);
	const int32 Pi = FindIndex(Subjects, PartnerId);
	const FSubject* S = Si != INDEX_NONE ? &Subjects[Si] : nullptr;
	const FSubject* P = Pi != INDEX_NONE ? &Subjects[Pi] : nullptr;
	const double Base = BaseDistanceCm();
	FVector TFocus;
	double TYaw = Yaw;
	double TPitch = Pitch;
	double TDist = Base * Zoom;
	if (S)
	{
		const FVector Lead = S->bAlive ? (S->Velocity * kFocusSmooth).GetClampedToMaxSize(kMaxLeadCm) : FVector::ZeroVector;
		TFocus = S->Location + FVector(0.0, 0.0, kFocusUpCm) + Lead;
		const double Heading = S->Velocity.Size2D() > kHeadingMinSpeed ? S->Velocity.Rotation().Yaw : static_cast<double>(S->YawDeg);
		switch (Mode)
		{
		case EEcoV3CamMode::Wolf:
			TYaw = Heading;
			TPitch = kWolfPitch;
			break;
		case EEcoV3CamMode::Deer:
			TYaw = Heading;
			TPitch = kDeerPitch;
			break;
		case EEcoV3CamMode::Top:
			TPitch = kTopPitch;   // 방위는 그대로 (들어설 때 돌지 않게)
			break;
		case EEcoV3CamMode::Quarter:
			TYaw = kQuarterYaw;
			TPitch = kQuarterPitch;
			break;
		case EEcoV3CamMode::Auto:
		{
			TPitch = kAutoPitch;
			TDist = kAutoDistCm * Zoom;
			if (P)
			{
				// 짝(쫓는 늑대·쫓기는 사슴)까지 한 화면에: 가운데를 보고, 짝 선과 직각으로 지금 방위에 가까운 쪽에서.
				// 10-27 창 모드 확인: 줌을 짝 맞춤 거리에도 곱하면 당겼을 때(줌 < 1) 가운데만 보여 둘 다 화면 밖이었다 — 줌은 기본 거리에만, 짝 맞춤 거리는 밑한계로
				const FVector Sep = P->Location - S->Location;
				TFocus = 0.5 * (S->Location + P->Location) + FVector(0.0, 0.0, kFocusUpCm) + 0.5 * Lead;
				TDist = FMath::Max(TDist, Sep.Size2D() * 1.25 + 800.0);
				const double Perp = Sep.Rotation().Yaw + 90.0;
				TYaw = FMath::Abs(FMath::FindDeltaAngleDegrees(Yaw, Perp)) <= 90.0 ? Perp : Perp + 180.0;
			}
			TDist = FMath::Min(TDist, FMath::Max(kAutoMaxCm, kAutoDistCm * Zoom));
			break;
		}
		default:
			break;
		}
	}
	else
	{
		// 대상 없음: 지역 무대 전체 (탑 = 위에서, 그 밖 = 45° 사선)
		const FRegionInfo* R = FindRegion(Regions, Region);
		if (!R)
		{
			return;   // 볼 것이 없다 — 카메라는 그 자리
		}
		TFocus = R->CenterCm;
		if (Mode == EEcoV3CamMode::Top)
		{
			TPitch = kTopPitch;
		}
		else
		{
			TPitch = kOverviewPitch;
			TYaw = kQuarterYaw;
		}
	}
	if (bSnap || FVector::Dist(TFocus, Focus) > kSnapCm)
	{
		Focus = TFocus;
		FocusVel = FVector::ZeroVector;
		Yaw = FRotator::NormalizeAxis(TYaw);
		Pitch = TPitch;
		Dist = TDist;
		YawVel = PitchVel = DistVel = 0.0;
		Arm = -1.0;   // 가림 피하기도 새로 (아래 ArmStep 이 바로 정한다)
		ArmVel = 0.0;
		bSnap = false;
	}
	else
	{
		SmoothDampVector(Focus, FocusVel, TFocus, kFocusSmooth, Dt);
		SmoothDampAngle(Yaw, YawVel, TYaw, kYawSmooth, Dt);
		SmoothDamp(Pitch, PitchVel, TPitch, kPitchSmooth, Dt);
		SmoothDamp(Dist, DistVel, TDist, kDistSmooth, Dt);
	}
	const FRotator Rot(Pitch, Yaw, 0.0);
	// 10-27 가림 피하기 (숲 지역 PIE 확인): 초점→카메라 사이를 막는 나무·바위 앞으로 바로 당기고, 트이면 천천히 편다
	ArmStep(Arm, ArmVel, ClearArmCm(Focus, -Rot.Vector(), Dist), kArmOutSmooth, Dt);
	FVector Loc = Focus - Rot.Vector() * Arm;
	FRotator Look = Rot;
	LastGroundZ = GroundZ(Loc.X, Loc.Y, Focus.Z);
	if (Loc.Z < LastGroundZ + kGroundClearCm)
	{
		Loc.Z = LastGroundZ + kGroundClearCm;
		Look = (Focus - Loc).Rotation();
	}
	Camera->SetActorLocationAndRotation(Loc, Look);
	// 10-27 가리는 나무 숨기기 (이 화면만): 대상이 있을 때 초점→카메라 선분이 지나는 나무 (짝이 있으면 짝까지의 선분도)
	if (S)
	{
		UpdateOccluders(PC, Focus, Loc);
		if (P && Mode == EEcoV3CamMode::Auto)
		{
			for (const TWeakObjectPtr<UPrimitiveComponent>& W : OccluderCandidates)
			{
				const UPrimitiveComponent* C = W.Get();
				if (C && !HiddenOccluders.Contains(W) && SegmentHitsBox(C->Bounds.GetBox(), P->Location + FVector(0.0, 0.0, kFocusUpCm), Loc))
				{
					HiddenOccluders.Add(W);
					PC.HiddenPrimitiveComponents.AddUnique(W);
				}
			}
		}
	}
	else
	{
		ClearOccluders(&PC);
	}
}

FString UEcoV3ObserverCameraSubsystem::DescribeStatus() const
{
	const int32 Si = EcoV3Observe::FindIndex(Subjects, SubjectId);
	if (Mode == EEcoV3CamMode::Player)
	{
		return TEXT("모드 원래 카메라");
	}
	const TCHAR* MoveNote = IsBlockingMoveInput() ? TEXT(" · 플레이어 이동 막음") : TEXT("");
	if (Mode == EEcoV3CamMode::Free)
	{
		const FName At = EcoV3Observe::RegionAt(Regions, FreeLoc);
		return FString::Printf(TEXT("모드 자유 카메라 · 속도 %s m/s%s · 자리 (%.1f, %.1f, %.1f) m · 방위 %.0f° · 숙임 %.0f° · 지역 %s%s"),
							   *EcoV3ObserverCameraImpl::SpeedText(FreeSpeedCm / 100.0), bFreeFast ? TEXT(" (Shift ×4)") : TEXT(""), FreeLoc.X / 100.0,
							   FreeLoc.Y / 100.0, FreeLoc.Z / 100.0, FreeYaw, FreePitch, At.IsNone() ? TEXT("-") : *At.ToString(), MoveNote);
	}
	if (Si == INDEX_NONE)
	{
		return FString::Printf(TEXT("모드 %s · 대상 없음 (%s 무대 전체) · 거리 %.0f m%s"), ModeNameKo(Mode), *Region.ToString(), Dist / 100.0, MoveNote);
	}
	const EcoV3Observe::FSubject& S = Subjects[Si];
	return FString::Printf(TEXT("모드 %s · 대상 %s #%lld (%s) · %s%s%s · 거리 %.0f m%s"), ModeNameKo(Mode), S.bWolf ? TEXT("늑대") : TEXT("사슴"), S.Id,
						   *S.Region.ToString(), EcoV3Observe::StateNameKo(S.State), S.Detail.IsEmpty() ? TEXT("") : TEXT(" · "), *S.Detail,
						   Dist / 100.0, MoveNote);
}

void UEcoV3ObserverCameraSubsystem::BuildStatusLines()
{
	using namespace EcoV3Observe;
	using namespace EcoV3ObserverCameraImpl;
	StatusLines.Reset();
	StatusColors.Reset();
	auto Add = [this](const FString& Text, const FColor& Color)
	{
		StatusLines.Add(Text);
		StatusColors.Add(Color);
	};
	const FColor White(235, 235, 235);
	if (Mode == EEcoV3CamMode::Player)
	{
		int32 AliveDeer = 0, AliveWolves = 0;
		for (const FSubject& O : Subjects)
		{
			if (O.bAlive)
			{
				++(O.bWolf ? AliveWolves : AliveDeer);
			}
		}
		Add(TEXT("모드   원래 카메라 (1~5 로 관찰)"), White);
		Add(FString::Printf(TEXT("개체   사슴 %d · 늑대 %d (모든 지역)"), AliveDeer, AliveWolves), White);
		return;
	}
	if (Mode == EEcoV3CamMode::Free)
	{
		int32 AliveDeer = 0, AliveWolves = 0;
		for (const FSubject& O : Subjects)
		{
			if (O.bAlive)
			{
				++(O.bWolf ? AliveWolves : AliveDeer);
			}
		}
		const double Sp = FreeSpeedCm / 100.0;
		Add(FString::Printf(TEXT("모드   자유 카메라 — 속도 %s m/s%s"), *SpeedText(Sp),
							bFreeFast ? *FString::Printf(TEXT(" (Shift → %s m/s)"), *SpeedText(Sp * kFreeFastMul)) : TEXT("")),
			White);
		const FName At = RegionAt(Regions, FreeLoc);
		Add(FString::Printf(TEXT("자리   %s%s"), At.IsNone() ? TEXT("-") : *At.ToString(),
							bFreeGround ? *FString::Printf(TEXT(" · 땅에서 %.0f m"), (FreeLoc.Z - LastGroundZ) / 100.0) : TEXT("")),
			White);
		Add(FString::Printf(TEXT("개체   사슴 %d · 늑대 %d (모든 지역)"), AliveDeer, AliveWolves), White);
		Add(TEXT("1~5   여기서 다시 관찰 (화면 가운데 대상)"), FColor(200, 200, 200));
		if (IsBlockingMoveInput())
		{
			Add(TEXT("플레이어   이동 키 막음 (0 으로 풀림)"), FColor(175, 175, 175));
		}
		return;
	}
	Add(FString::Printf(TEXT("모드   %s · 거리 %.0f m%s"), ModeNameKo(Mode), Dist / 100.0,
						Arm >= 0.0 && Arm < Dist - 100.0 ? *FString::Printf(TEXT(" (가림 피해 %.0f m)"), Arm / 100.0) : TEXT("")),
		White);
	const int32 Si = FindIndex(Subjects, SubjectId);
	if (Si == INDEX_NONE)
	{
		int32 Deer = 0, Wolves = 0;
		for (const FSubject& O : Subjects)
		{
			if (O.bAlive && O.Region == Region)
			{
				++(O.bWolf ? Wolves : Deer);
			}
		}
		Add(FString::Printf(TEXT("대상   %s 무대 전체"), Region.IsNone() ? TEXT("-") : *Region.ToString()), White);
		Add(FString::Printf(TEXT("개체   사슴 %d · 늑대 %d"), Deer, Wolves), White);
	}
	else
	{
		const FSubject& S = Subjects[Si];
		Add(FString::Printf(TEXT("대상   %s #%lld · %s"), S.bWolf ? TEXT("늑대") : TEXT("사슴"), S.Id, *S.Region.ToString()), White);
		Add(FString::Printf(TEXT("상태   %s%s%s"), StateNameKo(S.State), S.Detail.IsEmpty() ? TEXT("") : TEXT(" · "), *S.Detail),
			StateColor(S.State));
		if (!S.bWolf)
		{
			const int32 Wi = FindIndex(Subjects, S.NearestWolfId);
			Add(S.NearestWolfCm >= 0.0 ? FString::Printf(TEXT("가까운 늑대   %.1f m · %s"), S.NearestWolfCm / 100.0,
														 Wi != INDEX_NONE ? StateNameKo(Subjects[Wi].State) : TEXT("?"))
									   : FString(TEXT("가까운 늑대   없음")),
				Wi != INDEX_NONE ? StateColor(Subjects[Wi].State) : White);
		}
		else
		{
			const int32 Di = FindIndex(Subjects, S.NearestDeerId);
			Add(S.NearestDeerCm >= 0.0 ? FString::Printf(TEXT("가까운 사슴   %.1f m · %s"), S.NearestDeerCm / 100.0,
														 Di != INDEX_NONE ? StateNameKo(Subjects[Di].State) : TEXT("?"))
									   : FString(TEXT("가까운 사슴   없음")),
				Di != INDEX_NONE ? StateColor(Subjects[Di].State) : White);
		}
	}
	if (Mode == EEcoV3CamMode::Auto)
	{
		const bool bEvent = Si != INDEX_NONE && IsEvent(Subjects[Si]);
		const int32 Pi = FindIndex(Subjects, PartnerId);
		Add(bEvent ? (Pi != INDEX_NONE ? FString::Printf(TEXT("자동   사건 따라가는 중 · 짝 %s #%lld"), Subjects[Pi].bWolf ? TEXT("늑대") : TEXT("사슴"),
														 Subjects[Pi].Id)
									   : FString(TEXT("자동   사건 따라가는 중")))
				   : FString(TEXT("자동   사건 기다리는 중")),
			FColor(255, 220, 120));
	}
	if (IsBlockingMoveInput())
	{
		Add(TEXT("플레이어   이동 키 막음 (0 두 번이면 풀림)"), FColor(175, 175, 175));
	}
}

void UEcoV3ObserverCameraSubsystem::DrawPanel(UCanvas* Canvas, APlayerController* PC)
{
	using namespace EcoV3Observe;
	using namespace EcoV3ObserverCameraImpl;
	if (!Canvas || !PC || PC->GetWorld() != GetWorld() || !PC->IsLocalController() || CVarCamEnable.GetValueOnGameThread() == 0)
	{
		return;
	}
	if (!bHasCreatures && Mode == EEcoV3CamMode::Player)
	{
		return;   // 통합 개체가 없는 레벨 — 볼 것이 없다 (개체가 생기면 1 초 안에 다시 보인다)
	}
	const AHUD* Hud = PC->GetHUD();
	if (Hud && !Hud->bShowHUD)
	{
		return;   // showhud·촬영 감독(UI 끔)이 HUD 를 숨기면 같이 숨는다
	}
	UFont* Font = GEngine ? GEngine->GetSmallFont() : nullptr;   // 화면 메시지와 같은 글꼴 (한글 됨)
	if (!Font)
	{
		return;
	}
	struct FLine
	{
		FString Text;
		FLinearColor Color;
		bool bGapBefore = false;
	};
	TArray<FLine> Lines;
	Lines.Add({bShowKeys ? FString(TEXT("관찰 카메라      H  단축키 숨기기")) : FString(TEXT("관찰 카메라      H  단축키 보이기")),
			   FLinearColor(FColor(255, 215, 110)), false});
	if (bShowKeys)
	{
		for (const FString& L : KeyHelpLines())
		{
			Lines.Add({L, FLinearColor(FColor(240, 240, 240)), false});
		}
	}
	for (int32 i = 0; i < StatusLines.Num(); ++i)
	{
		Lines.Add({StatusLines[i], FLinearColor(StatusColors.IsValidIndex(i) ? StatusColors[i] : FColor::White), i == 0});
	}
	float LineH = 0.0f;
	float MaxW = 0.0f;
	for (const FLine& L : Lines)
	{
		float XL = 0.0f, YL = 0.0f;
		Canvas->TextSize(Font, L.Text, XL, YL, 1.0f, 1.0f);
		MaxW = FMath::Max(MaxW, XL);
		LineH = FMath::Max(LineH, YL);
	}
	if (LineH <= 0.0f)
	{
		return;
	}
	constexpr float Pad = 9.0f;
	constexpr float Spacing = 1.2f;
	const float GapH = 0.5f * LineH;
	float ContentH = 2.0f * Pad;
	for (const FLine& L : Lines)
	{
		ContentH += LineH * Spacing + (L.bGapBefore ? GapH : 0.0f);
	}
	const FVector2D Size(Canvas->ClipX, Canvas->ClipY);
	const FVector2D Content(MaxW + 2.0f * Pad, ContentH);
	// 1280×720 에서 1.15 배 (글 한 줄 약 16 px), 1080p 에서 1.7 배 — eco.Cam.HudScale 로 더 키우고 줄인다
	const float Base = FMath::Clamp(static_cast<float>(Size.Y) / 720.0f * 1.15f, 1.0f, 2.4f)
					   * FMath::Clamp(CVarCamHudScale.GetValueOnGameThread(), 0.5f, 3.0f);
	FBox2D Reserved(ForceInit);
	bool bReserved = false;
	if (const AEcoCreatureInspectorHUD* Inspector = Cast<AEcoCreatureInspectorHUD>(Hud); Inspector && GetWorld()
		&& EcoHerdMigrationDebug::Mode(*GetWorld()) > 0)
	{
		Reserved = TeamMigrationPanelRect(Size);   // 팀 HERD MIGRATION 판 (오른쪽 위) 을 비킨다
		bReserved = true;
	}
	const FPanelLayout L = LayoutPanel(Size, Content, Base, bReserved ? &Reserved : nullptr);
	FCanvasTileItem Back(FVector2D(L.X, L.Y), FVector2D(Content.X * L.Scale, Content.Y * L.Scale), FLinearColor(0.012f, 0.016f, 0.024f, 0.74f));
	Back.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Back);
	float Y = L.Y + Pad * L.Scale;
	for (const FLine& Line : Lines)
	{
		if (Line.bGapBefore)
		{
			// 단축키와 상태 사이 가는 줄
			Y += 0.5f * GapH * L.Scale;
			FCanvasTileItem Rule(FVector2D(L.X + Pad * L.Scale, Y), FVector2D((Content.X - 2.0f * Pad) * L.Scale, 1.0f),
								 FLinearColor(1.0f, 1.0f, 1.0f, 0.25f));
			Rule.BlendMode = SE_BLEND_Translucent;
			Canvas->DrawItem(Rule);
			Y += 0.5f * GapH * L.Scale;
		}
		FCanvasTextItem Text(FVector2D(L.X + Pad * L.Scale, Y), FText::FromString(Line.Text), Font, Line.Color);
		Text.Scale = FVector2D(L.Scale, L.Scale);
		Text.EnableShadow(FLinearColor(0.0f, 0.0f, 0.0f, 0.9f));
		Canvas->DrawItem(Text);
		Y += LineH * Spacing * L.Scale;
	}
}

// =============================================================================
// 콘솔 명령 (시험·촬영용)
// =============================================================================

namespace EcoV3ObserverCameraImpl
{
	void RunCam(UWorld* World, const TCHAR* Name, TFunctionRef<void(UEcoV3ObserverCameraSubsystem&)> Fn)
	{
		UEcoV3ObserverCameraSubsystem* Cam = World ? World->GetSubsystem<UEcoV3ObserverCameraSubsystem>() : nullptr;
		if (!Cam)
		{
			UE_LOG(LogEcoV3Cam, Warning, TEXT("[EcoCam] %s: 관찰 카메라가 없는 월드다 (게임·PIE 월드의 로컬 화면에서 쓴다 — 데디케이티드 서버 없음)"), Name);
			return;
		}
		if (CVarCamEnable.GetValueOnGameThread() == 0)
		{
			UE_LOG(LogEcoV3Cam, Warning, TEXT("[EcoCam] %s: eco.Cam.Enable 0 — 꺼져 있다"), Name);
			return;
		}
		Fn(*Cam);
		UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam] %s → %s"), Name, *Cam->DescribeStatus());
	}

	int64 IdArg(const TArray<FString>& Args)
	{
		return Args.Num() > 0 ? FCString::Atoi64(*Args[0]) : 0;
	}

	static FAutoConsoleCommandWithWorldAndArgs CmdCamWolf(
		TEXT("eco.Cam.Wolf"), TEXT("관찰 카메라 늑대 시점 [StableAgentId] — 뒤에서 따라감, 다시 = 다음 늑대 (키 1)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Wolf"), [&](UEcoV3ObserverCameraSubsystem& C) { C.SetMode(EEcoV3CamMode::Wolf, IdArg(Args)); }); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamDeer(
		TEXT("eco.Cam.Deer"), TEXT("관찰 카메라 사슴 시점 [StableAgentId] — 다시 = 다음 사슴 (키 2)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Deer"), [&](UEcoV3ObserverCameraSubsystem& C) { C.SetMode(EEcoV3CamMode::Deer, IdArg(Args)); }); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamTop(
		TEXT("eco.Cam.Top"), TEXT("관찰 카메라 탑뷰 — 대상 위, 대상이 없으면 지역 무대 전체 (키 3)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Top"), [&](UEcoV3ObserverCameraSubsystem& C) { C.SetMode(EEcoV3CamMode::Top, IdArg(Args)); }); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamQuarter(
		TEXT("eco.Cam.Quarter"), TEXT("관찰 카메라 쿼터뷰 — 대상 기준 45° 사선 (키 4)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Quarter"), [&](UEcoV3ObserverCameraSubsystem& C) { C.SetMode(EEcoV3CamMode::Quarter, IdArg(Args)); }); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamAuto(
		TEXT("eco.Cam.Auto"), TEXT("관찰 카메라 자동 추적 — 쫓기는 사슴·사냥 중인 늑대를 따라가고 사건이 끝나면 다음 (키 5)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Auto"), [](UEcoV3ObserverCameraSubsystem& C) { C.SetMode(EEcoV3CamMode::Auto); }); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamNext(
		TEXT("eco.Cam.Next"), TEXT("관찰 카메라 다음 대상 (키 .)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Next"), [](UEcoV3ObserverCameraSubsystem& C) { C.StepSubject(+1); }); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamPrev(
		TEXT("eco.Cam.Prev"), TEXT("관찰 카메라 이전 대상 (키 ,)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Prev"), [](UEcoV3ObserverCameraSubsystem& C) { C.StepSubject(-1); }); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamZoom(
		TEXT("eco.Cam.Zoom"), TEXT("관찰 카메라 거리 <m> (지금 모드, 키 - = 휠)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			RunCam(World, TEXT("eco.Cam.Zoom"), [&](UEcoV3ObserverCameraSubsystem& C)
			{
				if (Args.Num() > 0)
				{
					C.SetZoomMeters(FCString::Atod(*Args[0]));
				}
			});
		}));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamRegion(
		TEXT("eco.Cam.Region"), TEXT("관찰 카메라 지역 <이름> (없으면 다음 지역, 키 G)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			RunCam(World, TEXT("eco.Cam.Region"), [&](UEcoV3ObserverCameraSubsystem& C)
			{
				if (Args.Num() > 0)
				{
					C.SetRegion(FName(*Args[0]));
				}
				else
				{
					C.CycleRegionBy(+1);
				}
			});
		}));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamPlayer(
		TEXT("eco.Cam.Player"), TEXT("관찰 카메라 끄기 — 바로 원래 카메라(폰)로 (따라가기·자유 카메라 어디서든. 키로는 자유 카메라에서 0)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Player"), [](UEcoV3ObserverCameraSubsystem& C) { C.SetMode(EEcoV3CamMode::Player); }); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamFree(
		TEXT("eco.Cam.Free"),
		TEXT("관찰 카메라 자유 카메라 — 지금 보는 자리·방향 그대로 추적을 풀고 W A S D(방향키)·Q E·마우스·Shift·- = 휠(속도)로 직접 움직인다 ")
			TEXT("(관찰 중 키 0 과 같다, 원래 카메라에서도 된다). 폰 이동 입력 막기는 그대로."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Free"), [](UEcoV3ObserverCameraSubsystem& C) { C.EnterFree(TEXT("eco.Cam.Free")); }); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamSpeed(
		TEXT("eco.Cam.Speed"), TEXT("자유 카메라 이동 속도 <m/s> (1~150, 기본 12 — 키 - = 휠은 1.2 배씩, Shift 는 4 배)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			RunCam(World, TEXT("eco.Cam.Speed"), [&](UEcoV3ObserverCameraSubsystem& C)
			{
				if (Args.Num() > 0)
				{
					C.SetFreeSpeed(FCString::Atod(*Args[0]));
				}
			});
		}));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamStatus(
		TEXT("eco.Cam.Status"), TEXT("관찰 카메라 지금 상태 한 줄을 기록에 적는다 (모드·대상·거리, 자유 카메라면 자리·방향·속도)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{ RunCam(World, TEXT("eco.Cam.Status"), [](UEcoV3ObserverCameraSubsystem&) {}); }));
	static FAutoConsoleCommandWithWorldAndArgs CmdCamHelp(
		TEXT("eco.Cam.Help"), TEXT("관찰 카메라 단축키 목록 숨기기/보이기 (키 H)와 키 표·지금 상태를 기록에 적는다."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{
			RunCam(World, TEXT("eco.Cam.Help"), [](UEcoV3ObserverCameraSubsystem& C)
			{
				C.ToggleKeyList();
				for (const FString& L : EcoV3Observe::KeyHelpLines())
				{
					UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam]   %s"), *L);
				}
				UE_LOG(LogEcoV3Cam, Log, TEXT("[EcoCam]   H  단축키 목록 %s"), C.IsKeyListShown() ? TEXT("보임") : TEXT("숨김"));
			});
		}));
}
