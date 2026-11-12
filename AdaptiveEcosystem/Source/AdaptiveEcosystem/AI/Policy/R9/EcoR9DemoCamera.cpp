// R9 데모 플레이어 — 카메라·키. 보기만 바꾼다 (프레임·규칙·두뇌에 손대지 않음).
//
// 2026-11-13 03:30 옛 관찰 카메라 꼴로 다시 씀 (사용자: '0,1,2,3,4,5 번 키들로 시점 변경하는건 옛날 방식이 더 좋은데? 이렇게 좌상단에 띄우지 말고
// 옛날처럼 우상단에 띄우고 0번 누르면 그냥 자유시점으로 보게 하고 시점 변경할때도 한번에 보여줘'). 키·뜻·거리는 EcoR9DemoCam.h.
// 옛 관찰 카메라(EcoV3ObserverCamera)는 Mass 통합 개체만 찾아 R9 개체를 따라가지 못해 우리 카메라 액터를 쓴다. 옛 코드는 고치지 않고,
// 공용 함수(EcoV3Observe — 임계 감쇠 따라가기·가림 피하기 팔·자유 카메라 한 프레임·마우스 시야·키 입력)만 다시 써 같은 움직임을 낸다.
// 옛 카메라는 데모가 켜져 있는 동안 꺼 둔다 (eco.Cam.Enable 0 — 같은 숫자 키를 두 카메라가 같이 읽지 않게, EcoR9DemoSubsystem.cpp HoldObserverCamera).

#include "EcoR9DemoSubsystem.h"

#include "EcoR9DemoState.h"

#include "AI/Policy/EcoV3ObserverCamera.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Components/PrimitiveComponent.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Engine/Console.h"
#include "Engine/GameViewportClient.h"
#include "Engine/HitResult.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Volume.h"
#include "InputCoreTypes.h"

// =============================================================================
// EcoR9DemoCam — 키·모드 (엔진 월드 없이 — 시험 CamKeys)
// =============================================================================

TConstArrayView<EcoR9DemoCam::FKeyBind> EcoR9DemoCam::Keys()
{
	// 함수 안 static — EKeys 가 먼저 만들어진 뒤에 채운다 (옛 EcoV3Observe::Keys 와 같은 꼴·같은 별칭)
	static const TArray<FKeyBind> Table = {
		{EKeys::One, EAction::Wolf},		 {EKeys::NumPadOne, EAction::Wolf},
		{EKeys::Two, EAction::Deer},		 {EKeys::NumPadTwo, EAction::Deer},
		{EKeys::Three, EAction::Top},		 {EKeys::NumPadThree, EAction::Top},
		{EKeys::Four, EAction::Quarter},	 {EKeys::NumPadFour, EAction::Quarter},
		{EKeys::Five, EAction::Auto},		 {EKeys::NumPadFive, EAction::Auto},
		{EKeys::Zero, EAction::Free},		 {EKeys::NumPadZero, EAction::Free},
		{EKeys::Six, EAction::Boar},		 {EKeys::NumPadSix, EAction::Boar},
		{EKeys::Seven, EAction::NextSite},	 {EKeys::NumPadSeven, EAction::NextSite}, {EKeys::G, EAction::NextSite},
		{EKeys::Comma, EAction::Prev},		 {EKeys::Period, EAction::Next},
		{EKeys::Hyphen, EAction::ZoomOut},	 {EKeys::Subtract, EAction::ZoomOut},	  {EKeys::MouseScrollDown, EAction::ZoomOut},
		{EKeys::Equals, EAction::ZoomIn},	 {EKeys::Add, EAction::ZoomIn},			  {EKeys::MouseScrollUp, EAction::ZoomIn},
		{EKeys::H, EAction::Help},
		// 동물 세계 (11-13 05:00): 8 물소 · 9 표범 · J 여우 — 팀 입력 매핑·BP·C++ 키 읽기에 없는 키 (fauna/UE_FAUNA.md)
		{EKeys::Eight, EAction::Buffalo},	 {EKeys::NumPadEight, EAction::Buffalo},
		{EKeys::Nine, EAction::Leopard},	 {EKeys::NumPadNine, EAction::Leopard},
		{EKeys::J, EAction::Fox},
	};
	return Table;
}

bool EcoR9DemoCam::ActionOf(const FKey& Key, EAction& Out)
{
	for (const FKeyBind& B : Keys())
	{
		if (B.Key == Key)
		{
			Out = B.Action;
			return true;
		}
	}
	return false;
}

bool EcoR9DemoCam::ModeOf(EAction Action, EEcoR9DemoCam& Out)
{
	switch (Action)
	{
	case EAction::Free: Out = EEcoR9DemoCam::Free; return true;
	case EAction::Wolf: Out = EEcoR9DemoCam::Wolf; return true;
	case EAction::Deer: Out = EEcoR9DemoCam::Deer; return true;
	case EAction::Top: Out = EEcoR9DemoCam::Top; return true;
	case EAction::Quarter: Out = EEcoR9DemoCam::Quarter; return true;
	case EAction::Auto: Out = EEcoR9DemoCam::Auto; return true;
	case EAction::Boar: Out = EEcoR9DemoCam::Boar; return true;
	case EAction::Buffalo: Out = EEcoR9DemoCam::Buffalo; return true;
	case EAction::Leopard: Out = EEcoR9DemoCam::Leopard; return true;
	case EAction::Fox: Out = EEcoR9DemoCam::Fox; return true;
	default: return false;
	}
}

bool EcoR9DemoCam::ModeFromInt(int32 Value, EEcoR9DemoCam& Out)
{
	if (Value < 0 || Value > static_cast<int32>(EEcoR9DemoCam::Fox) || Value == 7)
	{
		return false;   // 7 은 모드가 아니다 (다음 무리 자리)
	}
	Out = static_cast<EEcoR9DemoCam>(Value);
	return true;
}

const TCHAR* EcoR9DemoCam::ModeNameKo(EEcoR9DemoCam Mode)
{
	switch (Mode)
	{
	case EEcoR9DemoCam::Free: return TEXT("자유 카메라");
	case EEcoR9DemoCam::Wolf: return TEXT("늑대 시점");
	case EEcoR9DemoCam::Deer: return TEXT("사슴 시점");
	case EEcoR9DemoCam::Top: return TEXT("탑뷰");
	case EEcoR9DemoCam::Quarter: return TEXT("쿼터뷰");
	case EEcoR9DemoCam::Auto: return TEXT("자동 추적");
	case EEcoR9DemoCam::Boar: return TEXT("멧돼지 시점");
	case EEcoR9DemoCam::Buffalo: return TEXT("물소 시점");
	case EEcoR9DemoCam::Leopard: return TEXT("표범 시점");
	case EEcoR9DemoCam::Fox: return TEXT("여우 시점");
	default: return TEXT("?");
	}
}

TArray<FString> EcoR9DemoCam::KeyHelpLines(bool bSites, bool bFauna)
{
	// 옛 EcoV3Observe::KeyHelpLines 꼴 (같은 키 같은 글) + R9 의 6 · 7 · G (+ 동물 세계 8 · 9 · J)
	TArray<FString> L = {
		TEXT("1   늑대 시점 (다시 누르면 다음 늑대)"),
		TEXT("2   사슴 시점 (다시 누르면 다음 사슴)"),
		TEXT("3   탑뷰          4   쿼터뷰 (45°)"),
		bFauna ? TEXT("5   자동 추적 (사냥·물기·반격·들이받기·사체 먹기)") : TEXT("5   자동 추적 (사냥·물기·반격·사체 먹기)"),
		TEXT("6   멧돼지 시점 (다시 누르면 다음 멧돼지)"),
	};
	if (bFauna)
	{
		L.Add(TEXT("8   물소 · 9   표범 · J   여우 시점"));
	}
	if (bSites)
	{
		L.Add(TEXT("7  G   다음 무리 자리 (끝에 섬 전체)"));
	}
	L.Append({
		TEXT(",  .   이전·다음 대상"),
		TEXT("-  =  휠   줌 (자유 카메라: 이동 속도)"),
		TEXT("0   자유 카메라 (그 자리에서 추적 풀기)"),
		TEXT("자유 카메라   W A S D 이동 · Q E 아래·위"),
		TEXT("     마우스 시야 · Shift 빠르게"),
	});
	return L;
}

double EcoR9DemoCam::FitTopCm(double SizeCm)
{
	const double HalfV = FMath::Atan(FMath::Tan(FMath::DegreesToRadians(0.5 * static_cast<double>(kFov))) * 9.0 / 16.0);
	return 0.55 * SizeCm / FMath::Tan(HalfV);
}

double EcoR9DemoCam::IslandViewSizeCm(double SizeXCm, double SizeYCm)
{
	return FMath::Max(SizeXCm * 9.0 / 16.0, SizeYCm);
}

int32 EcoR9DemoCam::CenterPick(TConstArrayView<FVector> Points, TConstArrayView<uint32> Ids, const FVector& Eye, const FVector& Forward, double MaxAngleDeg,
							   double MaxRangeCm)
{
	const FVector Fwd = Forward.GetSafeNormal();
	if (Fwd.IsNearlyZero() || Points.Num() != Ids.Num())
	{
		return INDEX_NONE;
	}
	const double MinCos = FMath::Cos(FMath::DegreesToRadians(FMath::Clamp(MaxAngleDeg, 0.0, 180.0)));
	int32 Best = INDEX_NONE;
	double BestCos = -2.0;
	double BestDist = 0.0;
	for (int32 i = 0; i < Points.Num(); ++i)
	{
		const FVector To = Points[i] - Eye;
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
							 || (C >= BestCos - Eps && (D < BestDist - 1.0e-6 || (D <= BestDist + 1.0e-6 && Ids[i] < Ids[Best])));
		if (bBetter)
		{
			Best = i;
			BestCos = C;
			BestDist = D;
		}
	}
	return Best;
}

// =============================================================================
// 안쪽 도우미
// =============================================================================

namespace EcoR9DemoCameraImpl
{
	// 옛 관찰 카메라 값 그대로 (EcoV3ObserverCamera.cpp:61-85)
	constexpr double kFocusSmooth = 0.18;     // 초점 시간 상수 — 대상 속도 × 이 값만큼 앞을 봐 9 m/s 도 뒤처지지 않는다
	constexpr double kYawSmooth = 0.45;
	constexpr double kPitchSmooth = 0.30;
	constexpr double kDistSmooth = 0.35;
	constexpr double kMaxLeadCm = 600.0;
	constexpr double kSnapCm = 15000.0;       // 150 m 넘게 건너뛰면 끊어 옮긴다
	constexpr double kGroundClearCm = 200.0;  // 카메라는 땅 2 m 위 밑으로 가지 않는다
	constexpr double kArmProbeCm = 25.0;      // 가림 피하기: 초점→카메라를 쓰는 공 반지름
	constexpr double kArmGapCm = 40.0;        // 막힌 곳 앞 여유
	constexpr double kArmMinCm = 250.0;       // 이보다 가까이 당기지 않는다
	constexpr double kArmOutSmooth = 0.6;     // 트였을 때 펴는 시간 상수 (당길 때는 바로)
	constexpr double kLingerSeconds = 2.5;    // 자동 추적: 사건이 끝난 뒤 머무는 시간
	constexpr double kDeadHoldSeconds = 3.0;  // 죽은 대상에 머무는 시간
	constexpr double kFramePairCm = 6000.0;   // 자동 추적 화면에 짝으로 넣는 거리
	constexpr double kHeadingMinSpeed = 80.0; // 이보다 빠르면 몸 방향 대신 속도 방향 (cm/s)
	constexpr double kFocusUpCm = 100.0;
	constexpr double kFreeCenterCm = 50000.0; // 자유 카메라 화면 가운데 땅을 찾는 거리 (500 m)
	constexpr double kSiteSideUnits = 60.0;   // 무리 자리 한 판 = 학습 세계 한 변 (60 단위 = 120 m)
	/** 맵 전체 땅: 자동 추적이 같은 점수면 지금 초점에 가까운 사건을 먼저 (250 m 에 1 점) [어림 — 11-13 그대로]. */
	constexpr double kNearPerCm = 1.0 / 25000.0;

	/** 콘솔에 글을 치는 중인가 (그동안 단축키·자유 카메라 키를 읽지 않는다 — 옛 IsConsoleOpen). */
	bool IsConsoleOpen(const APlayerController& PC)
	{
		const ULocalPlayer* LP = PC.GetLocalPlayer();
		return LP && LP->ViewportClient && LP->ViewportClient->ViewportConsole && LP->ViewportClient->ViewportConsole->ConsoleActive();
	}

	const TCHAR* SpeciesKo(uint8 Sp)
	{
		static const TCHAR* const Names[EcoR9Demo::kNumSpecies] = {TEXT("사슴"), TEXT("늑대"), TEXT("멧돼지"), TEXT("물소"), TEXT("표범"), TEXT("여우")};
		return Sp < EcoR9Demo::kNumSpecies ? Names[Sp] : TEXT("멧돼지");
	}

	uint8 SpeciesOfMode(EEcoR9DemoCam M)
	{
		switch (M)
		{
		case EEcoR9DemoCam::Deer: return EcoR9Demo::kDeer;
		case EEcoR9DemoCam::Boar: return EcoR9Demo::kBoar;
		case EEcoR9DemoCam::Buffalo: return EcoR9Demo::kBuffalo;
		case EEcoR9DemoCam::Leopard: return EcoR9Demo::kLeopard;
		case EEcoR9DemoCam::Fox: return EcoR9Demo::kFox;
		default: return EcoR9Demo::kWolf;
		}
	}

	bool IsFollowMode(EEcoR9DemoCam M)
	{
		return M == EEcoR9DemoCam::Wolf || M == EEcoR9DemoCam::Deer || M == EEcoR9DemoCam::Boar || M == EEcoR9DemoCam::Buffalo || M == EEcoR9DemoCam::Leopard ||
			   M == EEcoR9DemoCam::Fox;
	}

	/** 화면 속도 글 (정수면 '12', 아니면 '14.4' — 옛 SpeedText). */
	FString SpeedText(double MetersPerSecond)
	{
		return FMath::IsNearlyEqual(MetersPerSecond, FMath::RoundToDouble(MetersPerSecond), 0.05) ? FString::Printf(TEXT("%.0f"), MetersPerSecond)
																								  : FString::Printf(TEXT("%.1f"), MetersPerSecond);
	}

	/** 행동 글과 색 (옛 상태 색 꼴: 먹기 초록 · 늑대 뛰기 빨강 · 뛰기 주황 · 은신처 파랑 · 죽음 회색). */
	FString ActionKo(const EcoR9Demo::FR9Agent& A, FColor& OutColor)
	{
		using namespace EcoR9Demo;
		if (!A.Alive())
		{
			OutColor = FColor(150, 150, 150);
			return TEXT("죽음");
		}
		FString T;
		if (A.Action == kActEat)
		{
			T = TEXT("먹기");
			OutColor = FColor(120, 225, 120);
		}
		else if (IsRun(A.Action))
		{
			T = TEXT("뛰기");
			OutColor = IsBiter(A.Species) ? FColor(255, 95, 95) : FColor(255, 130, 40);
		}
		else if (IsWalk(A.Action))
		{
			T = TEXT("걷기");
			OutColor = FColor(210, 210, 210);
		}
		else if (A.Action == kActShelter)
		{
			T = TEXT("은신처로");
			OutColor = FColor(110, 230, 255);
		}
		else
		{
			T = TEXT("지켜봄");
			OutColor = FColor(245, 245, 245);
		}
		if (A.Flags & kFlagInShelter)
		{
			T += TEXT(" · 은신처 안");
			OutColor = FColor(120, 170, 255);
		}
		if (A.Energy >= 0.0f)
		{
			T += FString::Printf(TEXT(" · 에너지 %.0f%%"), 100.0f * A.Energy);
		}
		if (A.Hp >= 0.0f && A.Hp < 0.999f)   // S′ 사슴은 늘 1 (체력 없음) — 동물 세계는 사슴도 체력
		{
			T += FString::Printf(TEXT(" · 체력 %.0f%%"), 100.0f * A.Hp);
		}
		return T;
	}

	/** 볼 만한 것 하나. A = 주인공(늑대·사슴), B = 짝(없으면 0). */
	struct FInterest
	{
		uint32 A = 0;
		uint32 B = 0;
		double Score = 0.0;
		FString What;
	};

	double UnitDist(const EcoR9Demo::FR9Agent& P, const EcoR9Demo::FR9Agent& Q)
	{
		return FMath::Sqrt(FMath::Square(static_cast<double>(P.X - Q.X)) + FMath::Square(static_cast<double>(P.Y - Q.Y)));
	}

	/**
	 * 볼 만한 것 모으기 (11-13 자동 카메라 그대로) [어림 — 점수는 화면 고르기용]: 최근 4 초 사건(죽임 6 · 반격 5 · 상처 4.5), 사체를 먹는 늑대 2.6,
	 * 먹잇감 쪽 12 단위(24 m) 안에서 뛰는 늑대 3~4, 먹잇감 5 단위 안 늑대 2.6, 늑대 12 단위 안 은신처 속 사슴 2.2.
	 * 동물 세계 (11-13 05:00): 물소 들이받기 5.5 · 받아 죽임 6, 무는 종(표범·여우)도 늑대와 같은 점수 (S′ 판에는 늑대만 있어 지금과 같다).
	 */
	void GatherInterests(const FEcoR9DemoState& S, double Now, TArray<FInterest>& Out)
	{
		using namespace EcoR9Demo;
		Out.Reset();
		const FR9Frame& F = S.Cur;
		for (const FEcoR9DemoRecent& R : S.Recent)
		{
			if (Now - R.Time > 4.0)
			{
				continue;
			}
			FInterest I;
			I.A = R.A != 0 ? R.A : R.B;
			I.B = R.A != 0 ? R.B : 0;
			switch (R.Kind)
			{
			case ER9Event::BiteKill:
				I.Score = 6.0;
				I.What = TEXT("물어 잡음");
				break;
			case ER9Event::Counter:
				I.Score = 5.0;
				I.What = TEXT("멧돼지 반격");
				break;
			case ER9Event::BiteWound:
				I.Score = 4.5;
				I.What = TEXT("물기");
				break;
			case ER9Event::GoreKill:
				I.Score = 6.0;
				I.What = TEXT("물소가 들이받아 죽임");
				break;
			case ER9Event::Gore:
				I.Score = 5.5;
				I.What = TEXT("물소 들이받기");
				break;
			default:
				continue;
			}
			if (S.Info.NumSpecies > kNumOldSpecies && (R.Kind == ER9Event::BiteKill || R.Kind == ER9Event::BiteWound))
			{
				if (const FR9Agent* Who = S.FindCur(I.A))
				{
					I.What = FString::Printf(TEXT("%s %s"), SpeciesKo(Who->Species), *I.What);   // 동물 세계: 늑대·표범·여우 가운데 누가 물었나
				}
			}
			else if (S.Info.NumSpecies > kNumOldSpecies && R.Kind == ER9Event::Counter)
			{
				if (const FR9Agent* Who = S.FindCur(I.B))
				{
					I.What = FString::Printf(TEXT("%s 반격"), SpeciesKo(Who->Species));   // 동물 세계: 멧돼지·물소 가운데 누가 받아쳤나 (B = 받아친 개체)
				}
			}
			Out.Add(I);
		}
		for (const FR9Agent& W : F.Agents)
		{
			if (!W.Alive() || !IsBiter(W.Species))
			{
				continue;
			}
			const FR9Agent* Near = nullptr;
			double Best = TNumericLimits<double>::Max();
			for (const FR9Agent& O : F.Agents)
			{
				if (O.Alive() && O.Species != W.Species)
				{
					const double D = UnitDist(W, O);
					if (D < Best)
					{
						Best = D;
						Near = &O;
					}
				}
			}
			FInterest I;
			I.A = W.Id;
			if (W.Action == kActEat && (W.Flags & kFlagEating))
			{
				I.Score = 2.6;
				I.What = TEXT("사체를 먹음");
			}
			if (Near && (W.Flags & kFlagRunning) && Best < 12.0 && 3.0 + (12.0 - Best) / 12.0 > I.Score)
			{
				I.Score = 3.0 + (12.0 - Best) / 12.0;
				I.B = Near->Id;
				I.What = FString::Printf(TEXT("%s 쪽으로 뜀"), SpeciesKo(Near->Species));
			}
			else if (Near && Best < 5.0 && I.Score < 2.6)
			{
				I.Score = 2.6;
				I.B = Near->Id;
				I.What = FString::Printf(TEXT("%s 곁"), SpeciesKo(Near->Species));
			}
			if (I.Score > 0.0)
			{
				Out.Add(I);
			}
		}
		for (const FR9Agent& D : F.Agents)
		{
			if (!D.Alive() || D.Species != kDeer || !(D.Flags & kFlagInShelter))
			{
				continue;
			}
			for (const FR9Agent& W : F.Agents)
			{
				if (W.Alive() && IsBiter(W.Species) && UnitDist(D, W) < 12.0)
				{
					FInterest I;
					I.A = D.Id;
					I.B = W.Id;
					I.Score = 2.2;
					I.What = FString::Printf(TEXT("은신처 안 사슴 · %s 곁"), SpeciesKo(W.Species));
					Out.Add(I);
					break;
				}
			}
		}
	}
}

// =============================================================================
// 서브시스템 — 카메라 액터·키
// =============================================================================

void UEcoR9DemoSubsystem::EnsureCamera()
{
	UWorld* World = GetWorld();
	if (!IsValid(Camera))
	{
		FActorSpawnParameters P;
		P.Name = MakeUniqueObjectName(World->PersistentLevel, ACameraActor::StaticClass(), TEXT("EcoR9Demo_Camera"));
		P.ObjectFlags |= RF_Transient;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Camera = World->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), FTransform::Identity, P);
		if (!Camera)
		{
			return;
		}
		Camera->SetReplicates(false);
		Camera->GetCameraComponent()->bConstrainAspectRatio = false;
		Camera->GetCameraComponent()->SetFieldOfView(EcoR9DemoCam::kFov);   // 옛 관찰 카메라 70°
		// 빠르게 따라갈 때 대상이 뭉개지지 않게 이 카메라에서만 움직임 흐림을 끈다 (옛 관찰 카메라와 같음 — 팀 후처리 볼륨·설정은 그대로)
		Camera->GetCameraComponent()->PostProcessSettings.bOverride_MotionBlurAmount = true;
		Camera->GetCameraComponent()->PostProcessSettings.MotionBlurAmount = 0.0f;
		Camera->GetCameraComponent()->PostProcessBlendWeight = 1.0f;
		SpawnedActors.Add(Camera);
	}
	APlayerController* PC = World->GetFirstPlayerController();
	if (PC && PC->GetViewTarget() != Camera)
	{
		PC->SetViewTarget(Camera);
	}
}

void UEcoR9DemoSubsystem::HandleKeys()
{
	FEcoR9DemoState& S = *State;
	// 콘솔 값 eco.R9Demo.Cam (키 숫자와 같은 수) 이 바뀌었으면 따른다
	const int32 Cv = EcoR9DemoCVars::Cam();
	if (Cv != S.LastCamCVar)
	{
		S.LastCamCVar = Cv;
		EEcoR9DemoCam M = EEcoR9DemoCam::Auto;
		if (EcoR9DemoCam::ModeFromInt(Cv, M) && M != S.CamMode)
		{
			SetCamMode(M, TEXT("콘솔 eco.R9Demo.Cam"));
		}
	}
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (!PC || !PC->IsLocalController() || EcoR9DemoCameraImpl::IsConsoleOpen(*PC))
	{
		return;   // 콘솔에 치는 중이면 반응하지 않는다 (옛 그대로)
	}
	uint32 Done = 0;   // 별칭(숫자패드·휠·G)이 같은 프레임에 겹쳐도 동작은 한 번
	for (const EcoR9DemoCam::FKeyBind& B : EcoR9DemoCam::Keys())
	{
		const uint32 Bit = 1u << static_cast<uint32>(B.Action);
		if ((Done & Bit) == 0 && PC->WasInputKeyJustPressed(B.Key))
		{
			Done |= Bit;
			DoCamAction(B.Action);
		}
	}
}

bool UEcoR9DemoSubsystem::PressCamKey(const FKey& Key)
{
	EcoR9DemoCam::EAction A = EcoR9DemoCam::EAction::Help;
	if (!State || State->Phase != EEcoR9DemoPhase::Running || !EcoR9DemoCam::ActionOf(Key, A))
	{
		return false;
	}
	DoCamAction(A);
	return true;
}

void UEcoR9DemoSubsystem::DoCamAction(EcoR9DemoCam::EAction Action)
{
	using EcoR9DemoCam::EAction;
	FEcoR9DemoState& S = *State;
	const bool bFree = S.CamMode == EEcoR9DemoCam::Free;
	EEcoR9DemoCam M = EEcoR9DemoCam::Auto;
	if (EcoR9DemoCam::ModeOf(Action, M))
	{
		if (M == EEcoR9DemoCam::Free)
		{
			EnterFreeCam(TEXT("0 — 그 자리에서 추적 풀기"));   // 사용자 11-13: 0 = 그냥 자유 시점 (자유 카메라에서 다시 0 이어도 그대로)
		}
		else if (M == S.CamMode && EcoR9DemoCameraImpl::IsFollowMode(M))
		{
			StepCamSubject(+1);   // 같은 키를 다시 = 다음 개체 (옛 그대로)
		}
		else
		{
			SetCamMode(M, TEXT("키"));
		}
		return;
	}
	switch (Action)
	{
	case EAction::NextSite:
		CycleCamSite();
		break;
	case EAction::Prev:
		if (!bFree)
		{
			StepCamSubject(-1);
		}
		break;
	case EAction::Next:
		if (!bFree)
		{
			StepCamSubject(+1);
		}
		break;
	case EAction::ZoomOut:
	case EAction::ZoomIn:
	{
		const double Step = Action == EAction::ZoomOut ? EcoR9DemoCam::kZoomStep : 1.0 / EcoR9DemoCam::kZoomStep;
		if (bFree)
		{
			// 자유 카메라: 이동 속도 (- 느리게 · = 빠르게, 1~150 m/s — 옛 SetFreeSpeed)
			S.FreeSpeedCm = FMath::Clamp(S.FreeSpeedCm / Step, EcoV3Observe::kFreeMinSpeedCm, EcoV3Observe::kFreeMaxSpeedCm);
		}
		else
		{
			S.CamZoom = FMath::Clamp(S.CamZoom * Step, EcoR9DemoCam::kMinZoom, EcoR9DemoCam::kMaxZoom);
		}
		break;
	}
	case EAction::Help:
		S.bShowKeys = !S.bShowKeys;
		break;
	default:
		break;
	}
}

// =============================================================================
// 대상 찾기
// =============================================================================

bool UEcoR9DemoSubsystem::CamWhere(uint32 Id, FVector& Out, uint8* OutSpecies, bool* bOutAlive) const
{
	using namespace EcoR9Demo;
	const FEcoR9DemoState& S = *State;
	if (Id == 0)
	{
		return false;
	}
	const FR9Agent* A = S.FindCur(Id);
	if (const FEcoR9DemoBody* B = S.Bodies.Find(Id))
	{
		const AActor* Body = B->Rep.IsValid() ? static_cast<const AActor*>(B->Rep.Get()) : static_cast<const AActor*>(B->Boar.Get());
		if (Body)
		{
			Out = Body->GetActorLocation();   // 보이는 몸 자리 (화면과 같다)
			if (OutSpecies)
			{
				*OutSpecies = B->Species;
			}
			if (bOutAlive)
			{
				*bOutAlive = A ? A->Alive() : !B->bDead;
			}
			return true;
		}
	}
	if (A)
	{
		double X = 0.0, Y = 0.0;
		S.Map.ToWorld(A->X, A->Y, X, Y);
		Out = FVector(X, Y, GroundZ(X, Y));
		if (OutSpecies)
		{
			*OutSpecies = A->Species;
		}
		if (bOutAlive)
		{
			*bOutAlive = A->Alive();
		}
		return true;
	}
	return false;
}

FVector UEcoR9DemoSubsystem::CamVelocity(uint32 Id) const
{
	const FEcoR9DemoState& S = *State;
	const EcoR9Demo::FR9Agent* C = S.FindCur(Id);
	const EcoR9Demo::FR9Agent* P = S.bHavePrev ? S.FindPrev(Id) : nullptr;
	if (!C || !P)
	{
		return FVector::ZeroVector;
	}
	const double Step = S.Info.StepSeconds > 0.0 ? S.Info.StepSeconds : 2.0 / 15.0;
	double Vx = 0.0, Vy = 0.0;
	S.Map.VecToWorld((static_cast<double>(C->X) - P->X) / Step, (static_cast<double>(C->Y) - P->Y) / Step, Vx, Vy);
	const FVector V(Vx, Vy, 0.0);
	return V.SizeSquared() > FMath::Square(3000.0) ? FVector::ZeroVector : V;   // 30 m/s 넘음 = 다시 남·순간 이동 (속도 아님)
}

uint32 UEcoR9DemoSubsystem::NearestOfSpecies(uint8 Species, const FVector& From, bool bPreferRunning) const
{
	using namespace EcoR9Demo;
	const FEcoR9DemoState& S = *State;
	// 검토 (11-13 04:20): 옛 NearestSubject 처럼 From 과 같은 무리 자리(옛 '같은 지역')를 먼저 보고, 없을 때만 맵 전체에서 가장 가까운 것.
	// 맵 전체 땅은 무리 자리가 수백 m 떨어져 있어, 자리를 가리지 않고 '뛰는 늑대 먼저'를 하면 보던 사슴 곁 늑대 대신 섬 반대쪽 늑대로 건너뛴다.
	// 뛰는 것 먼저(bPreferRunning)는 같은 자리 안에서만 (작은 무대는 무대 하나가 곧 그 자리).
	const int32 Site = NumSites() > 0 ? NearestSite(From) : -1;
	for (int32 Pass = Site >= 0 ? 0 : 1; Pass < 2; ++Pass)
	{
		const bool bLocal = Pass == 0 || Site < 0;
		uint32 Best = 0;
		double BestD = TNumericLimits<double>::Max();
		bool bBestRun = false;
		for (const FR9Agent& A : S.Cur.Agents)
		{
			if (!A.Alive() || A.Species != Species)
			{
				continue;
			}
			double X = 0.0, Y = 0.0;
			S.Map.ToWorld(A.X, A.Y, X, Y);
			if (Pass == 0 && NearestSite(FVector(X, Y, 0.0)) != Site)
			{
				continue;
			}
			const double D = FVector::Dist2D(FVector(X, Y, 0.0), From);
			const bool bRun = bPreferRunning && bLocal && (A.Flags & kFlagRunning) != 0;
			const bool bBetter = Best == 0 || (bRun && !bBestRun) || (bRun == bBestRun && (D < BestD - 1.0e-6 || (D <= BestD + 1.0e-6 && A.Id < Best)));
			if (bBetter)
			{
				Best = A.Id;
				BestD = D;
				bBestRun = bRun;
			}
		}
		if (Best != 0)
		{
			return Best;
		}
	}
	return 0;
}

uint32 UEcoR9DemoSubsystem::CenterOfView(int32 Species) const
{
	const FEcoR9DemoState& S = *State;
	TArray<FVector> Pts;
	TArray<uint32> Ids;
	for (const EcoR9Demo::FR9Agent& A : S.Cur.Agents)
	{
		if (!A.Alive() || (Species >= 0 && A.Species != Species))
		{
			continue;
		}
		FVector P;
		if (CamWhere(A.Id, P))
		{
			Pts.Add(P + FVector(0.0, 0.0, EcoR9DemoCameraImpl::kFocusUpCm));
			Ids.Add(A.Id);
		}
	}
	const int32 I = EcoR9DemoCam::CenterPick(Pts, Ids, S.FreeLoc, FRotator(S.FreePitch, S.FreeYaw, 0.0).Vector(), EcoV3Observe::kCenterPickDeg,
											 EcoV3Observe::kCenterPickCm);
	return I != INDEX_NONE ? Ids[I] : 0;
}

FVector UEcoR9DemoSubsystem::FreeViewCenter() const
{
	// 보는 방향으로 높이 표를 따라가 처음 땅 밑으로 들어가는 점 (물리 쿼리 없음). 위를 보거나 500 m 안에 없으면 카메라 밑 땅
	const FEcoR9DemoState& S = *State;
	const FVector Dir = FRotator(S.FreePitch, S.FreeYaw, 0.0).Vector();
	if (Dir.Z < -1.0e-3)
	{
		for (double T = 400.0; T <= EcoR9DemoCameraImpl::kFreeCenterCm; T += 400.0)
		{
			const FVector P = S.FreeLoc + Dir * T;
			const double G = S.Heights.At(P.X, P.Y);
			if (P.Z <= G)
			{
				return FVector(P.X, P.Y, G);
			}
		}
	}
	return FVector(S.FreeLoc.X, S.FreeLoc.Y, S.Heights.At(S.FreeLoc.X, S.FreeLoc.Y));
}

int32 UEcoR9DemoSubsystem::NumSites() const
{
	const FEcoR9DemoState& S = *State;
	return S.Info.bWhole ? static_cast<int32>(S.Info.HerdXY.size() / 2) : 0;
}

int32 UEcoR9DemoSubsystem::NearestSite(const FVector& P) const
{
	const FEcoR9DemoState& S = *State;
	const int32 N = NumSites();
	int32 Best = 0;
	double BestD = TNumericLimits<double>::Max();
	for (int32 k = 0; k < N; ++k)
	{
		double X = 0.0, Y = 0.0;
		S.Map.ToWorld(S.Info.HerdXY[static_cast<std::size_t>(2 * k)], S.Info.HerdXY[static_cast<std::size_t>(2 * k + 1)], X, Y);
		const double D = FVector::Dist2D(FVector(X, Y, 0.0), P);
		if (D < BestD)
		{
			BestD = D;
			Best = k;
		}
	}
	return Best;
}

FVector UEcoR9DemoSubsystem::CamReferencePoint() const
{
	// 지금 보는 자리 (따라가기 초점 · 자유 카메라 화면 가운데). 처음에는 첫 무리 자리 (플레이어 시작점에 가장 가까운 자리 — 코어가 그 차례로 고름)
	const FEcoR9DemoState& S = *State;
	if (S.bCamInit)
	{
		return S.CamFocus;
	}
	if (NumSites() > 0)
	{
		const int32 K = FMath::Clamp(S.SiteIndex, 0, NumSites() - 1);
		double X = 0.0, Y = 0.0;
		S.Map.ToWorld(S.Info.HerdXY[static_cast<std::size_t>(2 * K)], S.Info.HerdXY[static_cast<std::size_t>(2 * K + 1)], X, Y);
		return FVector(X, Y, S.Heights.At(X, Y));
	}
	return S.StageCenter;
}

void UEcoR9DemoSubsystem::OverviewRegion(FVector& OutCenter, double& OutSizeCm, FString& OutName) const
{
	// 대상 없는 보기 (옛 '지역 무대 전체'): 맵 전체 땅 = 무리 자리 한 판(120 m) 또는 섬 전체(7·G 마지막), 작은 세계 = 무대
	const FEcoR9DemoState& S = *State;
	const int32 N = NumSites();
	if (N > 0)
	{
		const int32 K = S.bSiteLocked ? S.SiteIndex : NearestSite(CamReferencePoint());
		if (K >= N && S.LandBox.IsValid)
		{
			// 섬 전체 (옛 섬 무대: 땅 경계, 초점 높이 = 가장 높은 땅 + 30 m — 언덕 밑으로 들어가지 않게)
			const FVector C = S.LandBox.GetCenter();
			OutCenter = FVector(C.X, C.Y, S.bHeightHi ? S.HeightHi + 3000.0 : S.WholeCenter.Z);
			OutSizeCm = EcoR9DemoCam::IslandViewSizeCm(S.LandBox.GetSize().X, S.LandBox.GetSize().Y);
			OutName = TEXT("섬 전체");
			return;
		}
		const int32 Kc = FMath::Clamp(K, 0, N - 1);
		double X = 0.0, Y = 0.0;
		S.Map.ToWorld(S.Info.HerdXY[static_cast<std::size_t>(2 * Kc)], S.Info.HerdXY[static_cast<std::size_t>(2 * Kc + 1)], X, Y);
		OutCenter = FVector(X, Y, S.Heights.At(X, Y));
		OutSizeCm = EcoR9DemoCameraImpl::kSiteSideUnits * S.Info.UnitCm;
		OutName = FString::Printf(TEXT("무리 자리 %d/%d"), Kc + 1, N);
		return;
	}
	OutCenter = S.StageCenter;
	OutSizeCm = FMath::Max(S.Map.SideXCm(), S.Map.SideYCm());
	OutName = S.Info.bWhole ? TEXT("섬 전체") : TEXT("무대 전체");
}

double UEcoR9DemoSubsystem::ClearArmCm(const FVector& From, const FVector& Dir, double WantCm) const
{
	using namespace EcoR9DemoCameraImpl;
	UWorld* World = GetWorld();
	if (!World || WantCm <= kArmMinCm)
	{
		return WantCm;
	}
	// 옛 ClearArmCm 그대로: 카메라·플레이어 폰·대상·짝 몸은 건너뛰고, 보이는 WorldStatic(지형·바위·줄기) 앞으로. 읽기만 한다
	const FEcoR9DemoState& S = *State;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoR9DemoCamArm), false);
	if (Camera)
	{
		Params.AddIgnoredActor(Camera);
	}
	if (const APlayerController* PC = World->GetFirstPlayerController(); PC && PC->GetPawn())
	{
		Params.AddIgnoredActor(PC->GetPawn());
	}
	for (const uint32 Id : {S.FollowA, S.FollowB})
	{
		if (const FEcoR9DemoBody* B = Id != 0 ? S.Bodies.Find(Id) : nullptr)
		{
			const AActor* Body = B->Rep.IsValid() ? static_cast<const AActor*>(B->Rep.Get()) : static_cast<const AActor*>(B->Boar.Get());
			if (Body)
			{
				Params.AddIgnoredActor(Body);
			}
		}
	}
	TArray<FHitResult> Hits;
	World->SweepMultiByObjectType(Hits, From, From + Dir * WantCm, FQuat::Identity, FCollisionObjectQueryParams(ECC_WorldStatic),
								  FCollisionShape::MakeSphere(static_cast<float>(kArmProbeCm)), Params);
	double Best = WantCm;
	for (const FHitResult& H : Hits)
	{
		const UPrimitiveComponent* C = H.GetComponent();
		const AActor* A = H.GetActor();
		if (H.bStartPenetrating || !C || !C->IsVisible() || C->bHiddenInGame || (A && (A->IsHidden() || A->IsA<AVolume>())))
		{
			continue;   // 처음부터 박힌 것·보이지 않는 것 (무대 밖 보이지 않는 벽에 끌려 들어가지 않게)
		}
		Best = FMath::Min(Best, H.Distance - kArmGapCm);
	}
	return FMath::Clamp(Best, kArmMinCm, WantCm);
}

// =============================================================================
// 모드·대상 바꾸기 (키·콘솔)
// =============================================================================

void UEcoR9DemoSubsystem::SetCamMode(EEcoR9DemoCam NewMode, const TCHAR* Why)
{
	using namespace EcoR9DemoCameraImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	if (NewMode == EEcoR9DemoCam::Free)
	{
		EnterFreeCam(Why);
		return;
	}
	if (IsFollowMode(NewMode) && static_cast<int32>(SpeciesOfMode(NewMode)) >= S.Info.NumSpecies)
	{
		// 이 판에 없는 종의 시점 (세 종 판에서 8 · 9 · J · eco.R9Demo.Cam 8~10): 대상 없는 카메라로 바꾸지 않는다 (검토 11-13 06:10 — 발표 중 실수로 눌러도 화면이 비지 않게).
		// 시작 모드가 그 종이면 (eco.R9Demo.Cam 8 인데 세 종 판) 자동 추적으로 시작한다
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 카메라: 이 판(종 %d)에는 %s 가 없다 — %s"), S.Info.NumSpecies, SpeciesKo(SpeciesOfMode(NewMode)),
			   S.CamMode == NewMode ? TEXT("자동 추적으로 시작") : TEXT("카메라 그대로"));
		if (S.CamMode != NewMode)
		{
			return;
		}
		NewMode = EEcoR9DemoCam::Auto;
	}
	const double Now = GetWorld()->GetTimeSeconds();
	const EEcoR9DemoCam Prev = S.CamMode;
	const bool bFromFree = Prev == EEcoR9DemoCam::Free;
	if (bFromFree && NumSites() > 0)
	{
		// 자유 카메라가 보는 무리 자리 (날아서 다른 자리로 갔으면 그 자리 · 고정 풀기 — 옛 SetMode 의 지역 맞춤)
		const int32 At = NearestSite(FreeViewCenter());
		if (At != S.SiteIndex)
		{
			S.SiteIndex = At;
			S.bSiteLocked = false;
		}
	}
	FVector CurAt = FVector::ZeroVector;
	uint8 CurSp = 0;
	bool bCurAlive = false;
	const bool bCur = S.FollowA != 0 && CamWhere(S.FollowA, CurAt, &CurSp, &bCurAlive);
	uint32 NewA = 0;
	const TCHAR* Pick = TEXT("");
	switch (NewMode)
	{
	case EEcoR9DemoCam::Wolf:
	case EEcoR9DemoCam::Deer:
	case EEcoR9DemoCam::Boar:
	case EEcoR9DemoCam::Buffalo:
	case EEcoR9DemoCam::Leopard:
	case EEcoR9DemoCam::Fox:
	{
		const uint8 Sp = SpeciesOfMode(NewMode);
		if (bCur && bCurAlive && CurSp == Sp)
		{
			NewA = S.FollowA;   // 지금 보던 개체를 그 시점으로
			Pick = TEXT("보던 개체");
		}
		else
		{
			if (bFromFree)
			{
				NewA = CenterOfView(Sp);   // 자유 카메라: 화면 가운데에 보이는 그 종 (옛 10-29)
				Pick = TEXT("화면 가운데");
			}
			if (NewA == 0)
			{
				// 지금 보던 개체가 있으면 그 곁에서 가장 가까운 것 (검토 11-13 04:20 — 사슴을 보다 1 을 누르면 그 사슴 곁 늑대: 사용자가 '늑대 곁 사슴이 안 도망감'을
				// 살필 때 그 둘을 오가게. 옛 카메라는 여기서도 사냥 중인 늑대를 먼저 골랐다). 보던 개체가 없으면 보는 자리의 무리 자리에서 늑대는 뛰는 것을 먼저 (옛 그대로)
				NewA = bCur ? NearestOfSpecies(Sp, CurAt, false) : NearestOfSpecies(Sp, CamReferencePoint(), IsBiter(Sp));
				Pick = bCur ? TEXT("보던 개체 곁") : TEXT("보는 자리 곁");
			}
		}
		if (NewA == 0)
		{
			UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 카메라: 산 %s 가 없다"), SpeciesKo(Sp));
			if (bFromFree)
			{
				return;   // 자유 카메라 그대로 (옛 그대로)
			}
		}
		S.FollowSpecies = Sp;
		break;
	}
	case EEcoR9DemoCam::Top:
	case EEcoR9DemoCam::Quarter:
		NewA = bCur ? S.FollowA : 0;   // 지금 대상 위·사선 (없으면 무리 자리·무대 전체)
		Pick = TEXT("보던 개체");
		if (NewA == 0 && bFromFree)
		{
			NewA = CenterOfView(-1);
			Pick = TEXT("화면 가운데");
		}
		break;
	case EEcoR9DemoCam::Auto:
		NewA = bCur && bCurAlive ? S.FollowA : 0;   // 사건이 없으면 보던 개체에 머문다 (옛 그대로) — 아래에서 사건을 바로 고른다
		Pick = TEXT("사건 고르기");
		break;
	default:
		break;
	}
	if (Prev != NewMode)
	{
		S.CamZoom = 1.0;
	}
	S.CamMode = NewMode;
	S.CamModeSince = Now;
	S.FollowA = NewA;
	S.FollowB = 0;
	if (NewA != 0)
	{
		FVector P;
		uint8 Sp = S.FollowSpecies;
		if (CamWhere(NewA, P, &Sp))
		{
			S.FollowSpecies = Sp;
			S.LastSubjectLoc = P;
		}
	}
	S.SubjectDeadAt = -1.0;
	S.NextSubjectSearch = Now + 0.5;
	S.bAutoFollowing = false;
	S.CamWhat.Reset();
	if (NewMode == EEcoR9DemoCam::Auto)
	{
		S.AutoIdleSince = -1.0e9;
		MaintainAuto(Now, /*bPickNow*/ true);   // 키를 누르면 기다리지 않고 지금 사건을 고른다
	}
	S.bCamSnap = true;   // 사용자 11-13 '시점 변경할때도 한번에' — 다음 프레임에 그 자리로 끊어 옮긴다 (옛: 0.18 초 시간 상수로 옮겨 감)
	// 콘솔 값 eco.R9Demo.Cam 은 키로 바꾸지 않는다 — 다음 Play 도 그 값(기본 5 자동 추적)으로 시작한다 (값을 바꿀 때만 HandleKeys 가 따른다)
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 카메라 %s → %s · 대상 %s%s (%s) — %s"), EcoR9DemoCam::ModeNameKo(Prev), EcoR9DemoCam::ModeNameKo(NewMode),
		   S.FollowA ? SpeciesKo(S.FollowSpecies) : TEXT("없음"), S.FollowA ? *FString::Printf(TEXT(" #%u"), S.FollowA) : TEXT(""), Pick, Why);
}

void UEcoR9DemoSubsystem::EnterFreeCam(const TCHAR* Why)
{
	FEcoR9DemoState& S = *State;
	if (S.CamMode == EEcoR9DemoCam::Free)
	{
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 카메라: 이미 자유 카메라 (1~6 = 여기서 다시 관찰)"));
		return;
	}
	const EEcoR9DemoCam Prev = S.CamMode;
	// 지금 화면의 카메라 자리·방향 그대로 (옛 EnterFree — 끊어 옮기지 않는다)
	FVector Loc = FVector::ZeroVector;
	FRotator Rot = FRotator::ZeroRotator;
	if (IsValid(Camera))
	{
		Loc = Camera->GetActorLocation();
		Rot = Camera->GetActorRotation();
	}
	else
	{
		Rot = FRotator(S.CamPitch, S.CamYaw, 0.0);
		Loc = S.CamFocus - Rot.Vector() * (S.CamArm >= 0.0 ? S.CamArm : S.CamDist);
	}
	S.CamMode = EEcoR9DemoCam::Free;
	S.FollowA = S.FollowB = 0;
	S.bAutoFollowing = false;
	S.SubjectDeadAt = -1.0;
	S.CamWhat.Reset();
	S.FreeLoc = Loc;
	S.FreeVel = FVector::ZeroVector;
	S.FreeYaw = FRotator::NormalizeAxis(Rot.Yaw);
	S.FreePitch = FMath::Clamp(FRotator::NormalizeAxis(Rot.Pitch), -EcoV3Observe::kFreePitchLimit, EcoV3Observe::kFreePitchLimit);
	S.bFreeFast = false;
	S.bHasLastControl = false;   // 다음 프레임 컨트롤러 방향부터 마우스 시야
	S.FreeGroundZ = GroundZ(Loc.X, Loc.Y);
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 카메라 %s → 자유 카메라 — %s (자리 %.1f, %.1f, %.1f m · 방위 %.0f° · 숙임 %.0f° · 속도 %s m/s)"),
		   EcoR9DemoCam::ModeNameKo(Prev), Why, Loc.X / 100.0, Loc.Y / 100.0, Loc.Z / 100.0, S.FreeYaw, S.FreePitch,
		   *EcoR9DemoCameraImpl::SpeedText(S.FreeSpeedCm / 100.0));
}

void UEcoR9DemoSubsystem::StepCamSubject(int32 Dir)
{
	using namespace EcoR9DemoCameraImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	const double Now = GetWorld()->GetTimeSeconds();
	if (S.CamMode == EEcoR9DemoCam::Free)
	{
		return;   // 자유 카메라에는 대상이 없다
	}
	if (S.CamMode == EEcoR9DemoCam::Auto)
	{
		// 다른 사건 (지금 대상이 아닌 것 가운데 점수가 가장 높은 것 — 옛 자동 추적 , .). 맵 전체 땅은 MaintainAuto 와 같이 지금 초점에서 가까운 것을 먼저
		// (점수 − 거리 / 250 m — 검토 11-13 04:20: 옛 PickAuto 는 같은 지역을 먼저 봤다. 거리를 안 보면 , . 가 섬 반대쪽 사건으로 건너뛴다)
		TArray<FInterest> All;
		GatherInterests(S, Now, All);
		const FVector Ref = CamReferencePoint();
		const FInterest* Best = nullptr;
		for (FInterest& I : All)
		{
			if (I.A == S.FollowA)
			{
				continue;
			}
			FVector Pa;
			if (S.Info.bWhole && CamWhere(I.A, Pa))
			{
				I.Score -= FVector::Dist2D(Pa, Ref) * kNearPerCm;
			}
			if (!Best || I.Score > Best->Score)
			{
				Best = &I;
			}
		}
		if (!Best)
		{
			UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 카메라 자동 추적: 다른 사건이 없다"));
			return;
		}
		S.FollowA = Best->A;
		S.FollowB = Best->B;
		S.CamWhat = Best->What;
		S.bAutoFollowing = true;
		S.CamModeSince = Now;
		S.LastInterest = Now;
		S.SubjectDeadAt = -1.0;
		S.bCamSnap = true;
		return;
	}
	FVector CurAt = FVector::ZeroVector;
	uint8 CurSp = S.FollowSpecies;
	const bool bCur = S.FollowA != 0 && CamWhere(S.FollowA, CurAt, &CurSp);
	const uint8 Sp = IsFollowMode(S.CamMode) ? SpeciesOfMode(S.CamMode) : (bCur ? CurSp : kWolf);
	// 같은 무리 자리(맵 전체 땅 — 지금 대상 곁 자리)의 산 개체를 uid 차례로 돈다 (옛: 같은 지역 id 차례). 그 자리에 없으면 모든 자리
	const int32 Site = NumSites() > 0 ? NearestSite(bCur ? CurAt : CamReferencePoint()) : -1;
	TArray<uint32> Ids;
	TArray<uint32> All;
	for (const FR9Agent& A : S.Cur.Agents)
	{
		if (!A.Alive() || A.Species != Sp)
		{
			continue;
		}
		All.Add(A.Id);
		if (Site >= 0)
		{
			double X = 0.0, Y = 0.0;
			S.Map.ToWorld(A.X, A.Y, X, Y);
			if (NearestSite(FVector(X, Y, 0.0)) != Site)
			{
				continue;
			}
		}
		Ids.Add(A.Id);
	}
	if (Ids.IsEmpty())
	{
		Ids = MoveTemp(All);
	}
	if (Ids.IsEmpty())
	{
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 카메라: 산 %s 가 없다"), SpeciesKo(Sp));
		return;
	}
	Ids.Sort();
	const int32 At = Ids.Find(S.FollowA);
	const int32 N = Ids.Num();
	const int32 Next = At == INDEX_NONE ? (Dir >= 0 ? 0 : N - 1) : (((At + (Dir >= 0 ? 1 : -1)) % N) + N) % N;
	S.FollowA = Ids[Next];
	S.FollowB = 0;
	S.FollowSpecies = Sp;
	S.SubjectDeadAt = -1.0;
	S.bCamSnap = true;   // 대상을 바꾸면 한 번에
}

void UEcoR9DemoSubsystem::CycleCamSite()
{
	using namespace EcoR9DemoCameraImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	const double Now = GetWorld()->GetTimeSeconds();
	const int32 N = NumSites();
	if (N > 0)
	{
		// 무리 자리 1 → 2 → … → N → 섬 전체 → 1 (ISLAND_STAGE.md 11절 'G' 설계와 같은 차례)
		const int32 Base = S.bSiteLocked ? S.SiteIndex : NearestSite(CamReferencePoint());
		S.SiteIndex = (Base + 1) % (N + 1);
		S.bSiteLocked = true;
	}
	FVector C;
	double Size = 0.0;
	FString Name;
	OverviewRegion(C, Size, Name);
	switch (S.CamMode)
	{
	case EEcoR9DemoCam::Wolf:
	case EEcoR9DemoCam::Deer:
	case EEcoR9DemoCam::Boar:
	case EEcoR9DemoCam::Buffalo:
	case EEcoR9DemoCam::Leopard:
	case EEcoR9DemoCam::Fox:
	{
		const uint8 Sp = SpeciesOfMode(S.CamMode);
		S.FollowA = NearestOfSpecies(Sp, C, IsBiter(Sp));   // 그 자리에서 가장 가까운 그 종 (옛 SetRegion)
		S.FollowB = 0;
		S.FollowSpecies = Sp;
		break;
	}
	case EEcoR9DemoCam::Auto:
		S.FollowA = S.FollowB = 0;
		S.bAutoFollowing = false;
		S.AutoIdleSince = -1.0e9;
		S.CamFocus = C;   // 그 자리 곁 사건을 먼저 (자동 추적 거리 벌점의 기준)
		S.bCamInit = true;
		MaintainAuto(Now, /*bPickNow*/ true);
		break;
	case EEcoR9DemoCam::Top:
	case EEcoR9DemoCam::Quarter:
		S.FollowA = S.FollowB = 0;   // 그 자리 전체
		break;
	case EEcoR9DemoCam::Free:
	{
		// 자유 카메라 그대로, 그 자리 전체가 보이는 자리로 (옛 MoveFreeToRegion — 45° 사선 · −40° · 한 변 0.95 배)
		S.FreeYaw = EcoR9DemoCam::kQuarterYaw;
		S.FreePitch = EcoR9DemoCam::kOverviewPitch;
		S.FreeVel = FVector::ZeroVector;
		const FRotator View(S.FreePitch, S.FreeYaw, 0.0);
		S.FreeLoc = C + FVector(0.0, 0.0, kFocusUpCm) - View.Vector() * (0.95 * FMath::Max(Size, 1000.0));
		S.FreeLoc.Z = FMath::Max(S.FreeLoc.Z, GroundZ(S.FreeLoc.X, S.FreeLoc.Y) + kGroundClearCm);
		S.bHasLastControl = false;
		if (IsValid(Camera))
		{
			Camera->SetActorLocationAndRotation(S.FreeLoc, View);
		}
		break;
	}
	default:
		break;
	}
	S.SubjectDeadAt = -1.0;
	S.bCamSnap = true;
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 카메라 %s · %s (%.0f, %.0f) m"), EcoR9DemoCam::ModeNameKo(S.CamMode), *Name, C.X / 100.0, C.Y / 100.0);
}

// =============================================================================
// 대상 유지 (매 프레임)
// =============================================================================

void UEcoR9DemoSubsystem::MaintainAuto(double Now, bool bPickNow)
{
	using namespace EcoR9DemoCameraImpl;
	FEcoR9DemoState& S = *State;
	if (!bPickNow && Now < S.NextPick)
	{
		return;
	}
	S.NextPick = Now + 0.25;
	const bool bWhole = S.Info.bWhole;
	TArray<FInterest> All;
	GatherInterests(S, Now, All);
	const FVector Ref = CamReferencePoint();
	const FInterest* Best = nullptr;
	const FInterest* Mine = nullptr;
	double BestEff = -TNumericLimits<double>::Max();
	for (FInterest& I : All)
	{
		if (bWhole)
		{
			// 맵 전체 땅: 지금 초점에서 가까운 사건을 먼저 (점수 − 거리 / 250 m)
			FVector Pa;
			if (CamWhere(I.A, Pa))
			{
				I.Score -= FVector::Dist2D(Pa, Ref) * kNearPerCm;
			}
		}
		if (!Best || I.Score > BestEff)
		{
			Best = &I;
			BestEff = I.Score;
		}
		if (S.bAutoFollowing && I.A == S.FollowA && (!Mine || I.Score > Mine->Score))
		{
			Mine = &I;
		}
	}
	auto Follow = [&S, this, Now](const FInterest& I)
	{
		S.bAutoFollowing = true;
		S.CamModeSince = Now;
		S.LastInterest = Now;
		S.FollowA = I.A;
		S.FollowB = I.B;
		S.CamWhat = I.What;
		S.SubjectDeadAt = -1.0;
		FVector P;
		uint8 Sp = S.FollowSpecies;
		if (CamWhere(I.A, P, &Sp))
		{
			S.FollowSpecies = Sp;
			S.LastSubjectLoc = P;
		}
	};
	if (!S.bAutoFollowing)
	{
		// 키로 막 고른 때는 바로, 사건이 끝난 뒤에는 2.5 초 머문 뒤 (옛 kLingerSeconds)
		if (Best && Best->Score >= (bWhole ? 1.5 : 2.5) && (bPickNow || Now - S.AutoIdleSince >= kLingerSeconds))
		{
			Follow(*Best);
		}
		return;
	}
	if (Mine && Mine->Score >= 1.5)
	{
		S.LastInterest = Now;
		S.FollowB = Mine->B != 0 ? Mine->B : S.FollowB;
		S.CamWhat = Mine->What;
	}
	const bool bBetter = Best && Best->Score >= (bWhole ? 4.0 : 5.0) && Best->A != S.FollowA && Now - S.CamModeSince >= 5.0;
	if (bBetter)
	{
		Follow(*Best);
	}
	else if (Now - S.LastInterest > 3.5 || Now - S.CamModeSince > 35.0)
	{
		// 사건이 끝남 → 그 대상에 머물며 다음 사건을 기다린다 (옛 그대로 — 2.5 초 뒤 다음 사건)
		S.bAutoFollowing = false;
		S.CamModeSince = Now;
		S.AutoIdleSince = Now;
		S.FollowB = 0;
		S.CamWhat = TEXT("사건 끝 — 다음 사건을 기다림");
	}
}

void UEcoR9DemoSubsystem::MaintainCamSubject(double Now)
{
	using namespace EcoR9DemoCameraImpl;
	FEcoR9DemoState& S = *State;
	const EEcoR9DemoCam M = S.CamMode;
	if (M == EEcoR9DemoCam::Free)
	{
		return;
	}
	const bool bFollow = IsFollowMode(M);
	if (M == EEcoR9DemoCam::Auto)
	{
		MaintainAuto(Now, false);
	}
	if (S.FollowA != 0)
	{
		FVector P;
		uint8 Sp = S.FollowSpecies;
		bool bAlive = false;
		if (!CamWhere(S.FollowA, P, &Sp, &bAlive))
		{
			// 대상이 사라졌다 (몸·프레임 모두 없음): 따라가기 = 가까운 같은 종, 그 밖 = 대상 없음 (무리 자리·무대 전체)
			S.FollowA = bFollow ? NearestOfSpecies(S.FollowSpecies, S.LastSubjectLoc, false) : 0;
			S.FollowB = 0;
			S.SubjectDeadAt = -1.0;
			if (M == EEcoR9DemoCam::Auto)
			{
				S.bAutoFollowing = false;
				S.AutoIdleSince = Now;
			}
		}
		else
		{
			S.LastSubjectLoc = P;
			S.FollowSpecies = Sp;
			if (bFollow && !bAlive)
			{
				// 죽은 대상: 3 초 머문 뒤 가까운 같은 종 (옛 kDeadHoldSeconds)
				if (S.SubjectDeadAt < 0.0)
				{
					S.SubjectDeadAt = Now;
				}
				else if (Now - S.SubjectDeadAt >= kDeadHoldSeconds)
				{
					S.FollowA = NearestOfSpecies(Sp, P, false);
					S.SubjectDeadAt = -1.0;
				}
			}
			else
			{
				S.SubjectDeadAt = -1.0;
			}
		}
	}
	else if (bFollow && Now >= S.NextSubjectSearch)
	{
		// 따라갈 개체가 없었다 (그 종이 모두 죽음 · 판 다시 시작) — 0.5 초마다 다시 찾는다
		S.NextSubjectSearch = Now + 0.5;
		const uint8 Sp = SpeciesOfMode(M);
		S.FollowA = NearestOfSpecies(Sp, CamReferencePoint(), EcoR9Demo::IsBiter(Sp));
		S.FollowSpecies = Sp;
	}
}

// =============================================================================
// 한 프레임
// =============================================================================

void UEcoR9DemoSubsystem::UpdateFreeCam(double Dt, APlayerController* PC)
{
	using namespace EcoR9DemoCameraImpl;
	FEcoR9DemoState& S = *State;
	FVector Input = FVector::ZeroVector;
	S.bFreeFast = false;
	if (PC)
	{
		// 마우스 시야: 컨트롤러 방향이 바뀐 만큼만 (컨트롤러·폰에는 쓰지 않는다 — 옛 FreeLookStep)
		const FRotator Ctrl = PC->GetControlRotation();
		if (S.bHasLastControl)
		{
			EcoV3Observe::FreeLookStep(S.FreeYaw, S.FreePitch, S.LastControlRot, Ctrl);
		}
		S.LastControlRot = Ctrl;
		S.bHasLastControl = true;
		// 키: 콘솔에 치는 중이면 읽지 않는다 (그동안 부드럽게 선다). 폰은 데모가 멈춰 두어(이동 컴포넌트 끔) W A S D 로 걷지 않는다
		if (!IsConsoleOpen(*PC))
		{
			Input = EcoV3Observe::FreeMoveInput([PC](const FKey& K) { return PC->IsInputKeyDown(K); });
			for (const FKey& K : EcoV3Observe::FreeFastKeys())
			{
				S.bFreeFast = S.bFreeFast || PC->IsInputKeyDown(K);
			}
		}
	}
	const FRotator View(S.FreePitch, S.FreeYaw, 0.0);
	// 맵 전체 땅 (옛 섬 무대 — ISLAND_STAGE.md 11절): 높이 올라가면 빨라진다 — 땅 위 높이 50 m 마다 1 배 (50 m 밑은 그대로)
	const double HeightMul = S.Info.bWhole ? FMath::Clamp((S.FreeLoc.Z - S.FreeGroundZ) / 5000.0, 1.0, 40.0) : 1.0;
	EcoV3Observe::FreeFlyStep(S.FreeLoc, S.FreeVel, View, Input, S.FreeSpeedCm * (S.bFreeFast ? EcoV3Observe::kFreeFastMul : 1.0) * HeightMul, Dt);
	// 땅 2 m 위 밑으로 가지 않는다
	S.FreeGroundZ = GroundZ(S.FreeLoc.X, S.FreeLoc.Y);
	if (S.FreeLoc.Z < S.FreeGroundZ + kGroundClearCm)
	{
		S.FreeLoc.Z = S.FreeGroundZ + kGroundClearCm;
		S.FreeVel.Z = FMath::Max(S.FreeVel.Z, 0.0);
	}
	Camera->SetActorLocationAndRotation(S.FreeLoc, View);
	// 초점 = 화면 가운데 땅 (풀 그리기 창·몸 배정·다시 관찰할 때 기준)
	S.CamFocus = FreeViewCenter();
	S.CamFocusVel = FVector::ZeroVector;
	S.bCamInit = true;
	S.CamYaw = S.FreeYaw;
	S.CamPitch = S.FreePitch;
	S.CamDist = FVector::Dist(S.FreeLoc, S.CamFocus);
	S.CamArm = S.CamDist;
	S.CamTargetFocus = S.CamFocus;
	S.CamTargetYaw = S.FreeYaw;
	S.CamTargetPitch = S.FreePitch;
	S.CamTargetDist = S.CamDist;
}

void UEcoR9DemoSubsystem::UpdateCamera(float DeltaTime)
{
	using namespace EcoR9DemoCameraImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	EnsureCamera();
	if (!Camera)
	{
		return;
	}
	UWorld* World = GetWorld();
	const double Now = World->GetTimeSeconds();
	const double Dt = FMath::Clamp(static_cast<double>(DeltaTime), 0.0, 0.1);
	if (S.CamMode == EEcoR9DemoCam::Free)
	{
		UpdateFreeCam(Dt, World->GetFirstPlayerController());
		BuildCamLines();
		return;
	}
	MaintainCamSubject(Now);
	// 목표 (옛 UpdateCamera 와 같은 셈 — 거리·숙임·방위는 EcoR9DemoCam.h)
	FVector Pa = FVector::ZeroVector;
	uint8 SpA = 0;
	bool bAliveA = false;
	const bool bSubject = S.FollowA != 0 && CamWhere(S.FollowA, Pa, &SpA, &bAliveA);
	FVector Pb = FVector::ZeroVector;
	const bool bPartner = bSubject && S.CamMode == EEcoR9DemoCam::Auto && S.FollowB != 0 && CamWhere(S.FollowB, Pb) && FVector::Dist(Pa, Pb) <= kFramePairCm;
	const double Zoom = S.CamZoom;
	FVector TFocus = S.CamFocus;
	double TYaw = S.CamYaw;
	double TPitch = S.CamPitch;
	double TDist = S.CamDist;
	if (bSubject)
	{
		const FVector V = bAliveA ? CamVelocity(S.FollowA) : FVector::ZeroVector;
		const FVector Lead = (V * kFocusSmooth).GetClampedToMaxSize(kMaxLeadCm);   // 9 m/s 로 뛰어도 뒤처지지 않게 앞을 본다
		TFocus = Pa + FVector(0.0, 0.0, kFocusUpCm) + Lead;
		double Heading = S.CamYaw;
		if (V.Size2D() > kHeadingMinSpeed)
		{
			Heading = V.Rotation().Yaw;   // 가는 쪽 뒤
		}
		else if (const FR9Agent* A = S.FindCur(S.FollowA))
		{
			Heading = FR9StageMap::YawDeg(A->Hx, A->Hy);   // 느리면 몸 방향
		}
		switch (S.CamMode)
		{
		case EEcoR9DemoCam::Wolf:
			TYaw = Heading;
			TPitch = EcoR9DemoCam::kWolfPitch;
			TDist = EcoR9DemoCam::kWolfDistCm * Zoom;
			break;
		case EEcoR9DemoCam::Deer:
			TYaw = Heading;
			TPitch = EcoR9DemoCam::kDeerPitch;
			TDist = EcoR9DemoCam::kDeerDistCm * Zoom;
			break;
		case EEcoR9DemoCam::Boar:
		case EEcoR9DemoCam::Buffalo:   // 동물 세계 셋은 멧돼지 값 (사슴과 같은 11 m · −18°)
		case EEcoR9DemoCam::Leopard:
		case EEcoR9DemoCam::Fox:
			TYaw = Heading;
			TPitch = EcoR9DemoCam::kBoarPitch;
			TDist = EcoR9DemoCam::kBoarDistCm * Zoom;
			break;
		case EEcoR9DemoCam::Top:
			TPitch = EcoR9DemoCam::kTopPitch;   // 방위는 그대로 (들어설 때 돌지 않게)
			TDist = EcoR9DemoCam::kTopDistCm * Zoom;
			break;
		case EEcoR9DemoCam::Quarter:
			TYaw = EcoR9DemoCam::kQuarterYaw;
			TPitch = EcoR9DemoCam::kQuarterPitch;
			TDist = EcoR9DemoCam::kQuarterDistCm * Zoom;
			break;
		case EEcoR9DemoCam::Auto:
		{
			TPitch = EcoR9DemoCam::kAutoPitch;
			TDist = EcoR9DemoCam::kAutoDistCm * Zoom;
			if (bPartner)
			{
				// 짝(쫓는 늑대·물린 먹잇감)까지 한 화면에: 가운데를 보고, 짝 선과 직각으로 지금 방위에 가까운 쪽에서. 줌은 기본 거리에만 (옛 10-27 고침)
				const FVector Sep = Pb - Pa;
				TFocus = 0.5 * (Pa + Pb) + FVector(0.0, 0.0, kFocusUpCm) + 0.5 * Lead;
				TDist = FMath::Max(TDist, Sep.Size2D() * 1.25 + 800.0);
				const double Perp = Sep.Rotation().Yaw + 90.0;
				TYaw = FMath::Abs(FMath::FindDeltaAngleDegrees(S.CamYaw, Perp)) <= 90.0 ? Perp : Perp + 180.0;
			}
			TDist = FMath::Min(TDist, FMath::Max(EcoR9DemoCam::kAutoMaxCm, EcoR9DemoCam::kAutoDistCm * Zoom));
			break;
		}
		default:
			break;
		}
	}
	else
	{
		// 대상 없음: 무리 자리·섬 전체·무대 (탑 = 위에서, 그 밖 = 45° 사선 · −40° — 옛 '지역 무대 전체')
		FVector C;
		double Size = 0.0;
		FString Name;
		OverviewRegion(C, Size, Name);
		TFocus = C;
		if (S.CamMode == EEcoR9DemoCam::Top)
		{
			TPitch = EcoR9DemoCam::kTopPitch;
			TDist = EcoR9DemoCam::FitTopCm(Size) * Zoom;
		}
		else
		{
			TPitch = EcoR9DemoCam::kOverviewPitch;
			TYaw = EcoR9DemoCam::kQuarterYaw;
			TDist = 0.95 * Size * Zoom;
		}
	}
	S.CamTargetFocus = TFocus;
	S.CamTargetYaw = FRotator::NormalizeAxis(TYaw);
	S.CamTargetPitch = TPitch;
	S.CamTargetDist = TDist;
	if (!S.bCamInit || S.bCamSnap || FVector::Dist(TFocus, S.CamFocus) > kSnapCm)
	{
		// 끊어 옮김: 키로 시점·대상을 바꿨다 (사용자 11-13 '한번에') · 처음 · 150 m 넘게 건너뜀
		S.CamFocus = TFocus;
		S.CamFocusVel = FVector::ZeroVector;
		S.CamYaw = S.CamTargetYaw;
		S.CamPitch = TPitch;
		S.CamDist = TDist;
		S.CamYawVel = S.CamPitchVel = S.CamDistVel = 0.0;
		S.CamArm = -1.0;   // 가림 피하기도 새로 (아래 ArmStep 이 바로 정한다)
		S.CamArmVel = 0.0;
		S.bCamSnap = false;
		S.bCamInit = true;
	}
	else
	{
		// 바꾼 뒤 움직이는 대상 따라가기는 옛 그대로 (임계 감쇠 — 넘침 없음)
		EcoV3Observe::SmoothDampVector(S.CamFocus, S.CamFocusVel, TFocus, kFocusSmooth, Dt);
		EcoV3Observe::SmoothDampAngle(S.CamYaw, S.CamYawVel, TYaw, kYawSmooth, Dt);
		EcoV3Observe::SmoothDamp(S.CamPitch, S.CamPitchVel, TPitch, kPitchSmooth, Dt);
		EcoV3Observe::SmoothDamp(S.CamDist, S.CamDistVel, TDist, kDistSmooth, Dt);
	}
	const FRotator Rot(S.CamPitch, S.CamYaw, 0.0);
	// 가림 피하기 (옛 10-27): 대상을 따라갈 때 초점→카메라 사이를 막는 바위·줄기·지형 앞으로 바로 당기고, 트이면 천천히 편다
	const double WantArm = bSubject ? ClearArmCm(S.CamFocus, -Rot.Vector(), S.CamDist) : S.CamDist;
	EcoV3Observe::ArmStep(S.CamArm, S.CamArmVel, WantArm, kArmOutSmooth, Dt);
	FVector Loc = S.CamFocus - Rot.Vector() * S.CamArm;
	FRotator Look = Rot;
	const double Ground = GroundZ(Loc.X, Loc.Y);
	if (Loc.Z < Ground + kGroundClearCm)
	{
		Loc.Z = Ground + kGroundClearCm;   // 땅 2 m 위 — 높이를 올리고 초점을 다시 본다
		Look = (S.CamFocus - Loc).Rotation();
	}
	Camera->SetActorLocationAndRotation(Loc, Look);
	BuildCamLines();
}

// =============================================================================
// 오른쪽 위 글 (카메라 줄 — 묶음은 EcoR9DemoSubsystem.cpp DrawOverlay)
// =============================================================================

void UEcoR9DemoSubsystem::BuildCamLines()
{
	using namespace EcoR9DemoCameraImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	S.CamLines.Reset();
	S.CamColors.Reset();
	auto Add = [&S](const FString& Text, const FColor& Color)
	{
		S.CamLines.Add(Text);
		S.CamColors.Add(Color);
	};
	const FColor White(235, 235, 235);
	const FColor Gray(175, 175, 175);
	const FColor Gold(255, 220, 120);
	const int32 N = NumSites();
	if (S.CamMode == EEcoR9DemoCam::Free)
	{
		const double Sp = S.FreeSpeedCm / 100.0;
		const double HeightM = (S.FreeLoc.Z - S.FreeGroundZ) / 100.0;
		const double Mul = S.Info.bWhole ? FMath::Clamp(HeightM / 50.0, 1.0, 40.0) : 1.0;
		Add(FString::Printf(TEXT("모드   자유 카메라 — 속도 %s m/s%s%s"), *SpeedText(Sp),
							S.bFreeFast ? *FString::Printf(TEXT(" (Shift → %s m/s)"), *SpeedText(Sp * EcoV3Observe::kFreeFastMul)) : TEXT(""),
							Mul > 1.05 ? *FString::Printf(TEXT(" · 높이 ×%.1f"), Mul) : TEXT("")),
			White);
		Add(FString::Printf(TEXT("자리   땅에서 %.0f m%s"), HeightM, N > 0 ? *FString::Printf(TEXT(" · 무리 자리 %d 곁"), NearestSite(S.CamFocus) + 1) : TEXT("")), White);
		Add(S.Info.NumSpecies > kNumOldSpecies ? TEXT("1~6 · 8 · 9 · J   여기서 다시 관찰 (화면 가운데 대상)") : TEXT("1~6   여기서 다시 관찰 (화면 가운데 대상)"),
			FColor(200, 200, 200));
		S.CamLabel = FString::Printf(TEXT("자유 카메라 (%.0f, %.0f, %.0f) m"), S.FreeLoc.X / 100.0, S.FreeLoc.Y / 100.0, S.FreeLoc.Z / 100.0);
		return;
	}
	const TCHAR* ModeName = EcoR9DemoCam::ModeNameKo(S.CamMode);
	Add(FString::Printf(TEXT("모드   %s · 거리 %.0f m%s"), ModeName, S.CamDist / 100.0,
						S.CamArm >= 0.0 && S.CamArm < S.CamDist - 100.0 ? *FString::Printf(TEXT(" (가림 피해 %.0f m)"), S.CamArm / 100.0) : TEXT("")),
		White);
	FVector P = FVector::ZeroVector;
	uint8 Sp = S.FollowSpecies;
	bool bAlive = false;
	const bool bSubject = S.FollowA != 0 && CamWhere(S.FollowA, P, &Sp, &bAlive);
	if (!bSubject)
	{
		FVector C;
		double Size = 0.0;
		FString Name;
		OverviewRegion(C, Size, Name);
		int32 Count[kNumSpecies] = {};
		const bool bAll = Name == TEXT("섬 전체") || Name == TEXT("무대 전체");
		for (const FR9Agent& A : S.Cur.Agents)
		{
			if (!A.Alive() || A.Species >= kNumSpecies)
			{
				continue;
			}
			double X = 0.0, Y = 0.0;
			S.Map.ToWorld(A.X, A.Y, X, Y);
			if (bAll || (FMath::Abs(X - C.X) <= 0.5 * Size && FMath::Abs(Y - C.Y) <= 0.5 * Size))
			{
				++Count[A.Species];
			}
		}
		Add(FString::Printf(TEXT("대상   %s"), *Name), White);
		Add(FString::Printf(TEXT("개체   사슴 %d · 늑대 %d · 멧돼지 %d"), Count[kDeer], Count[kWolf], Count[kBoar]), White);
		if (S.Info.NumSpecies > kNumOldSpecies)
		{
			Add(FString::Printf(TEXT("      물소 %d · 표범 %d · 여우 %d"), Count[kBuffalo], Count[kLeopard], Count[kFox]), White);
		}
		S.CamLabel = FString::Printf(TEXT("%s · %s"), ModeName, *Name);
	}
	else
	{
		const FR9Agent* A = S.FindCur(S.FollowA);
		Add(FString::Printf(TEXT("대상   %s #%u%s"), SpeciesKo(Sp), S.FollowA, N > 0 ? *FString::Printf(TEXT(" · 무리 자리 %d 곁"), NearestSite(P) + 1) : TEXT("")),
			White);
		FColor ActColor = White;
		FString Act;
		if (A)
		{
			Act = ActionKo(*A, ActColor);
		}
		else
		{
			Act = TEXT("죽음");
			ActColor = FColor(150, 150, 150);
		}
		if (!bAlive && IsFollowMode(S.CamMode))
		{
			Act += TEXT(" (3 초 뒤 가까운 같은 종으로)");
		}
		Add(FString::Printf(TEXT("행동   %s"), *Act), ActColor);
		// 가까운 상대: 늑대 → 먹잇감(사슴·멧돼지), 사슴·멧돼지 → 늑대 (옛 '가까운 늑대·사슴' 줄)
		// 동물 세계: 무는 종(늑대·표범·여우) → 다른 종 아무나, 그 밖(사슴·멧돼지·물소) → 무는 종 아무나
		const bool bFaunaHud = S.Info.NumSpecies > kNumOldSpecies;
		if (A)
		{
			const FR9Agent* Near = nullptr;
			double Best = TNumericLimits<double>::Max();
			for (const FR9Agent& O : S.Cur.Agents)
			{
				const bool bSkip = bFaunaHud ? (IsBiter(A->Species) ? O.Species == A->Species : !IsBiter(O.Species))
											 : (A->Species == kWolf ? O.Species == kWolf : O.Species != kWolf);
				if (!O.Alive() || O.Id == A->Id || bSkip)
				{
					continue;
				}
				const double D = UnitDist(*A, O);
				if (D < Best)
				{
					Best = D;
					Near = &O;
				}
			}
			const TCHAR* Label = bFaunaHud ? (IsBiter(A->Species) ? TEXT("가까운 먹잇감") : TEXT("가까운 포식자"))
										   : (A->Species == kWolf ? TEXT("가까운 먹잇감") : TEXT("가까운 늑대"));
			if (Near)
			{
				FColor NearColor = White;
				const FString NearAct = ActionKo(*Near, NearColor);
				Add(FString::Printf(TEXT("%s   %s #%u · %.1f m · %s"), Label, SpeciesKo(Near->Species), Near->Id, Best * S.Info.UnitCm / 100.0, *NearAct), NearColor);
			}
			else
			{
				Add(FString::Printf(TEXT("%s   없음"), Label), White);
			}
		}
		S.CamLabel = FString::Printf(TEXT("%s · %s #%u · %s"), ModeName, SpeciesKo(Sp), S.FollowA, *Act);
	}
	if (S.CamMode == EEcoR9DemoCam::Auto)
	{
		FString Pair;
		FVector Pb;
		uint8 SpB = 0;
		if (S.bAutoFollowing && S.FollowB != 0 && CamWhere(S.FollowB, Pb, &SpB))
		{
			Pair = FString::Printf(TEXT(" · 짝 %s #%u"), SpeciesKo(SpB), S.FollowB);
		}
		Add(S.bAutoFollowing ? FString::Printf(TEXT("자동   %s%s"), *S.CamWhat, *Pair)
							 : (S.CamWhat.IsEmpty() ? FString(TEXT("자동   사건 기다리는 중")) : FString::Printf(TEXT("자동   %s"), *S.CamWhat)),
			Gold);
		S.CamLabel += S.bAutoFollowing ? FString::Printf(TEXT(" · 자동: %s"), *S.CamWhat) : FString(TEXT(" · 자동: 사건 기다림"));
	}
	(void)Gray;
}

FEcoR9DemoCamProbe UEcoR9DemoSubsystem::CamProbe() const
{
	FEcoR9DemoCamProbe P;
	if (!State)
	{
		return P;
	}
	const FEcoR9DemoState& S = *State;
	P.Mode = static_cast<int32>(S.CamMode);
	P.Subject = S.FollowA;
	P.Partner = S.FollowB;
	if (S.FollowA != 0)
	{
		FVector Where;
		uint8 Sp = S.FollowSpecies;
		P.SubjectSpecies = CamWhere(S.FollowA, Where, &Sp) ? static_cast<int32>(Sp) : static_cast<int32>(S.FollowSpecies);
	}
	P.Focus = S.CamFocus;
	P.TargetFocus = S.CamTargetFocus;
	P.Yaw = S.CamYaw;
	P.TargetYaw = S.CamTargetYaw;
	P.Pitch = S.CamPitch;
	P.TargetPitch = S.CamTargetPitch;
	P.Dist = S.CamDist;
	P.TargetDist = S.CamTargetDist;
	P.Arm = S.CamArm;
	P.bHaveCamera = IsValid(Camera);
	if (P.bHaveCamera)
	{
		P.CameraLocation = Camera->GetActorLocation();
		P.CameraRotation = Camera->GetActorRotation();
	}
	P.FreeSpeedMps = S.FreeSpeedCm / 100.0;
	P.SiteIndex = S.SiteIndex;
	P.bShowKeys = S.bShowKeys;
	P.Zoom = S.CamZoom;
	P.NumLines = S.CamLines.Num();
	return P;
}

// =============================================================================
// 확인용 카메라 키 차례 (명령줄 -EcoR9CamKeys, 11-13 04:40) — 창 없는 실행에서 '키로 바꾸면 한 번에' 를 프레임 차이로 잰다.
// 키는 사람이 누를 때와 같은 PressCamKey 길로 누르고, 카메라 자리는 기록 줄로만 남긴다. 명령줄에 없으면 아무 일 없음.
// =============================================================================

void UEcoR9DemoSubsystem::TickCamKeyPlan(double Now)
{
	FEcoR9DemoState& S = *State;
	if (S.CamKeyNext >= S.CamKeyPlan.Num() || Now - S.RunningSince < S.CamKeyPlan[S.CamKeyNext].Key)
	{
		return;
	}
	const FKey Key = S.CamKeyPlan[S.CamKeyNext].Value;
	++S.CamKeyNext;
	S.CamKeyPrevLoc = IsValid(Camera) ? Camera->GetActorLocation() : FVector::ZeroVector;   // 누르기 앞 프레임 카메라 자리
	const EEcoR9DemoCam PrevMode = S.CamMode;
	const bool bTaken = PressCamKey(Key);
	S.CamKeyLabel = Key.GetFName().ToString();
	S.CamKeyProbeFrame = 0;
	S.CamKeyProbeLeft = bTaken ? 4 : 0;   // 누른 프레임 + 뒤 3 프레임
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 확인 키 %s (무대 %.2f 초) — %s → %s%s"), *S.CamKeyLabel, Now - S.RunningSince, EcoR9DemoCam::ModeNameKo(PrevMode),
		   EcoR9DemoCam::ModeNameKo(S.CamMode), bTaken ? TEXT("") : TEXT(" (카메라 키로 안 받음)"));
}

void UEcoR9DemoSubsystem::LogCamKeyProbe()
{
	FEcoR9DemoState& S = *State;
	if (S.CamKeyProbeLeft <= 0 || !IsValid(Camera))
	{
		return;
	}
	--S.CamKeyProbeLeft;
	const FEcoR9DemoCamProbe P = CamProbe();
	const double MovedM = FVector::Dist(P.CameraLocation, S.CamKeyPrevLoc) / 100.0;
	const FString Gap = S.CamMode == EEcoR9DemoCam::Free
							? FString(TEXT("자유 카메라 (목표 없음)"))
							: FString::Printf(TEXT("초점-목표 %.2f m · 방위 차 %.2f° · 숙임 차 %.2f° · 거리 차 %.2f m"), FVector::Dist(P.Focus, P.TargetFocus) / 100.0,
											  FMath::Abs(FMath::FindDeltaAngleDegrees(P.Yaw, P.TargetYaw)), FMath::Abs(P.Pitch - P.TargetPitch),
											  FMath::Abs(P.Dist - P.TargetDist) / 100.0);
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 확인 키 %s +%d 프레임 | 카메라 (%.1f, %.1f, %.1f) m · 앞 프레임에서 %.2f m 옮김 | %s | %s · 대상 %u"), *S.CamKeyLabel,
		   S.CamKeyProbeFrame, P.CameraLocation.X / 100.0, P.CameraLocation.Y / 100.0, P.CameraLocation.Z / 100.0, MovedM, *Gap,
		   EcoR9DemoCam::ModeNameKo(S.CamMode), P.Subject);
	S.CamKeyPrevLoc = P.CameraLocation;
	++S.CamKeyProbeFrame;
}
