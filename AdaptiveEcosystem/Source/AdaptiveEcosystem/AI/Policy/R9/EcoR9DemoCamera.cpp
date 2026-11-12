// R9 데모 플레이어 — 카메라·키. 보기만 바꾼다 (프레임·규칙에 손대지 않음).
//
// 관찰 카메라(EcoV3ObserverCamera)는 Mass 통합 개체만 찾아 R9 개체를 따라가지 못한다 — 그래서 우리 카메라 액터를 쓰고,
// 따라가기 수학(임계 감쇠 SmoothDamp — Game Programming Gems 4)만 같은 꼴로 따로 둔다 (그쪽 헤더는 다른 워크플로가 고칠 수 있어 포함하지 않음).
// 모드: 0 자동 (사냥·물기·반격·사체 먹기·은신처 안 사슴을 따라가고, 없으면 전체 보기) · 1 전체 · 2 사슴 · 3 늑대 · 4 멧돼지 · 5 위에서 · 6 무리 자리.
// 키: 1~6 = 모드 (3~5 를 다시 누르면 다음 개체), 7 = 다음 무리 자리, H = 글자. 콘솔 eco.R9Demo.Cam 0~6 도 같다.
// 맵 전체 땅 (2026-11-13): 1 자동은 지금 초점에서 가까운 사건을 먼저 (점수 − 거리/250 m), 사건이 없으면 지금 무리 자리 보기 · 2 섬(맵 땅) 전체 ·
//   3/4/5 처음 누르면 초점에서 가장 가까운 그 종 · 6 지금 무리 자리 위에서 · 7 다음 무리 자리.

#include "EcoR9DemoSubsystem.h"

#include "EcoR9DemoState.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"

namespace EcoR9DemoCameraImpl
{
	using namespace EcoR9Demo;

	constexpr float kFov = 60.0f;

	void SmoothDamp(double& Value, double& Velocity, double Target, double SmoothTime, double Dt)
	{
		const double Time = FMath::Max(1e-4, SmoothTime);
		const double Omega = 2.0 / Time;
		const double X = Omega * Dt;
		const double Exp = 1.0 / (1.0 + X + 0.48 * X * X + 0.235 * X * X * X);
		const double Change = Value - Target;
		const double Temp = (Velocity + Omega * Change) * Dt;
		Velocity = (Velocity - Omega * Temp) * Exp;
		Value = Target + (Change + Temp) * Exp;
	}

	void SmoothDampVector(FVector& Value, FVector& Velocity, const FVector& Target, double SmoothTime, double Dt)
	{
		SmoothDamp(Value.X, Velocity.X, Target.X, SmoothTime, Dt);
		SmoothDamp(Value.Y, Velocity.Y, Target.Y, SmoothTime, Dt);
		SmoothDamp(Value.Z, Velocity.Z, Target.Z, SmoothTime, Dt);
	}

	void SmoothDampAngle(double& Deg, double& Velocity, double TargetDeg, double SmoothTime, double Dt)
	{
		const double Delta = FMath::FindDeltaAngleDegrees(Deg, TargetDeg);
		double V = Deg;
		SmoothDamp(V, Velocity, Deg + Delta, SmoothTime, Dt);
		Deg = FRotator::NormalizeAxis(V);
	}

	/** 볼 만한 것 하나. A = 주인공(늑대·사슴), B = 짝(없으면 0). */
	struct FInterest
	{
		uint32 A = 0;
		uint32 B = 0;
		double Score = 0.0;
		FString What;
	};

	/** 맵 전체 땅: 자동 카메라가 같은 점수면 지금 초점에 가까운 사건을 먼저 (250 m 에 1 점) [어림]. */
	constexpr double kNearPerCm = 1.0 / 25000.0;

	/** 무리 자리 k 가운데 (언리얼 cm, z = 땅). 자리가 없으면 거짓. */
	bool SiteCenter(const FEcoR9DemoState& S, int32 K, FVector& Out)
	{
		const int32 N = static_cast<int32>(S.Info.HerdXY.size() / 2);
		if (N <= 0)
		{
			return false;
		}
		const int32 I = ((K % N) + N) % N;
		double X = 0.0, Y = 0.0;
		S.Map.ToWorld(S.Info.HerdXY[static_cast<std::size_t>(2 * I)], S.Info.HerdXY[static_cast<std::size_t>(2 * I + 1)], X, Y);
		Out = FVector(X, Y, S.Heights.At(X, Y));
		return true;
	}

	const TCHAR* SpeciesKo(uint8 Sp)
	{
		return Sp == kDeer ? TEXT("사슴") : (Sp == kWolf ? TEXT("늑대") : TEXT("멧돼지"));
	}

	double Dist(const FR9Agent& P, const FR9Agent& Q)
	{
		return FMath::Sqrt(FMath::Square(static_cast<double>(P.X - Q.X)) + FMath::Square(static_cast<double>(P.Y - Q.Y)));
	}

	/**
	 * 볼 만한 것 모으기 [어림 — 점수는 화면 고르기용]: 최근 4 초 사건(죽임 6 · 반격 5 · 상처 4.5), 사체를 먹는 늑대 2.6,
	 * 먹잇감 쪽 12 단위(24 m) 안에서 뛰는 늑대 3~4, 먹잇감 5 단위 안 늑대 2.6, 늑대 12 단위 안 은신처 속 사슴 2.2.
	 */
	void GatherInterests(const FEcoR9DemoState& S, double Now, TArray<FInterest>& Out)
	{
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
			default:
				continue;
			}
			Out.Add(I);
		}
		for (const FR9Agent& W : F.Agents)
		{
			if (!W.Alive() || W.Species != kWolf)
			{
				continue;
			}
			const FR9Agent* Near = nullptr;
			double Best = TNumericLimits<double>::Max();
			for (const FR9Agent& O : F.Agents)
			{
				if (O.Alive() && O.Species != kWolf)
				{
					const double D = Dist(W, O);
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
				if (W.Alive() && W.Species == kWolf && Dist(D, W) < 12.0)
				{
					FInterest I;
					I.A = D.Id;
					I.B = W.Id;
					I.Score = 2.2;
					I.What = TEXT("은신처 안 사슴 · 늑대 곁");
					Out.Add(I);
					break;
				}
			}
		}
	}
}

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
		Camera->GetCameraComponent()->SetFieldOfView(EcoR9DemoCameraImpl::kFov);
		// 카메라가 따라가며 돌 때 화면이 번지지 않게 이 카메라에서만 움직임 흐림을 끈다 (팀 후처리 볼륨·설정은 그대로)
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
	const double Now = GetWorld()->GetTimeSeconds();
	auto SetMode = [&S, Now](EEcoR9DemoCam Mode)
	{
		if (S.CamMode != Mode)
		{
			S.CamMode = Mode;
			S.CamModeSince = Now;
			S.bAutoFollowing = false;
			S.FollowA = S.FollowB = 0;
		}
	};
	// 콘솔 값이 바뀌었으면 따른다
	const int32 Cv = EcoR9DemoCVars::Cam();
	if (Cv != S.LastCamCVar)
	{
		S.LastCamCVar = Cv;
		SetMode(static_cast<EEcoR9DemoCam>(FMath::Clamp(Cv, 0, 6)));
	}
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (!PC)
	{
		return;
	}
	static const FKey Keys[7] = {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five, EKeys::Six, EKeys::Seven};
	for (int32 i = 0; i < 7; ++i)
	{
		if (!PC->WasInputKeyJustPressed(Keys[i]))
		{
			continue;
		}
		if (i == 6)
		{
			// 키 7 = 다음 무리 자리 (맵 전체 땅). 자리가 없으면 무대 하나 보기
			const int32 N = static_cast<int32>(S.Info.HerdXY.size() / 2);
			S.SiteIndex = N > 0 ? (S.SiteIndex + 1) % N : 0;
			SetMode(EEcoR9DemoCam::Site);
			S.LastCamCVar = 6;
			EcoR9DemoCVars::SetCam(6);
			continue;
		}
		// 키 1 = 자동(0), 2 = 전체(1), 3 사슴(2), 4 늑대(3), 5 멧돼지(4), 6 위(5)
		const EEcoR9DemoCam Want = static_cast<EEcoR9DemoCam>(i);
		if (S.CamMode == Want && i >= 2 && i <= 4)
		{
			// 같은 종 키를 다시 누르면 다음 개체
			const uint8 Sp = static_cast<uint8>(i - 2);
			TArray<uint32> Ids;
			for (const EcoR9Demo::FR9Agent& A : S.Cur.Agents)
			{
				if (A.Alive() && A.Species == Sp)
				{
					Ids.Add(A.Id);
				}
			}
			Ids.Sort();
			if (!Ids.IsEmpty())
			{
				const int32 At = Ids.Find(S.FollowA);
				S.FollowA = Ids[(At + 1) % Ids.Num()];
			}
		}
		else
		{
			SetMode(Want);
		}
		S.LastCamCVar = i;
		EcoR9DemoCVars::SetCam(i);
	}
	if (PC->WasInputKeyJustPressed(EKeys::H))
	{
		EcoR9DemoCVars::SetText(!EcoR9DemoCVars::Text());
	}
}

void UEcoR9DemoSubsystem::UpdateCamera(float DeltaTime)
{
	using namespace EcoR9DemoCameraImpl;
	FEcoR9DemoState& S = *State;
	EnsureCamera();
	if (!Camera)
	{
		return;
	}
	const double Now = GetWorld()->GetTimeSeconds();
	const double Dt = FMath::Clamp(static_cast<double>(DeltaTime), 0.0, 0.1);
	const double Side = FMath::Max(S.Map.SideXCm(), S.Map.SideYCm());
	const FVector Center = S.StageCenter;
	// 개체 자리 (보이는 몸이 있으면 그 자리)
	auto Where = [this, &S](uint32 Id, FVector& Out) -> bool
	{
		if (const FEcoR9DemoBody* B = S.Bodies.Find(Id))
		{
			const AActor* Body = B->Rep.IsValid() ? static_cast<const AActor*>(B->Rep.Get()) : B->Boar.Get();
			if (Body)
			{
				Out = Body->GetActorLocation();
				return true;
			}
		}
		if (const FR9Agent* A = S.FindCur(Id))
		{
			double X = 0.0, Y = 0.0;
			S.Map.ToWorld(A->X, A->Y, X, Y);
			Out = FVector(X, Y, GroundZ(X, Y));
			return true;
		}
		return false;
	};
	FVector Focus = Center;
	double Arm = 0.95 * Side;
	double Height = 0.55 * Side;
	double Yaw = 225.0 + 1.5 * (Now - S.RunningSince);
	bool bTop = false;
	const bool bWhole = S.Info.bWhole;
	// 맵 전체 땅: '전체' = 맵 땅 경계, '무리 자리' = 학습 세계 한 판 크기 (120 m) 정사각
	const double SiteSide = 60.0 * S.Info.UnitCm;
	FVector SiteFocus = Center;
	const bool bHaveSite = bWhole && SiteCenter(S, S.SiteIndex, SiteFocus);
	auto SiteView = [&]()
	{
		Focus = SiteFocus;
		Arm = 0.95 * SiteSide;
		Height = 0.55 * SiteSide;
	};
	if (bWhole)
	{
		// 2 섬 전체: 땅 경계 가운데, 긴 변에 맞춰 (초당 1.5° 천천히 돎)
		const FBox& L = S.LandBox;
		const double LandSide = L.IsValid ? FMath::Max(L.GetSize().X, L.GetSize().Y) : Side;
		Focus = L.IsValid ? FVector(L.GetCenter().X, L.GetCenter().Y, S.WholeCenter.Z) : Center;
		Arm = 0.75 * LandSide;
		Height = 0.60 * LandSide;
	}
	auto Follow = [&](uint32 A, uint32 B) -> bool
	{
		FVector Pa;
		if (!Where(A, Pa))
		{
			return false;
		}
		FVector Pb = Pa;
		const bool bPair = B != 0 && Where(B, Pb);
		Focus = 0.5 * (Pa + Pb) + FVector(0.0, 0.0, 80.0);
		const double Sep = FVector::Dist2D(Pa, Pb);
		Arm = FMath::Clamp(1.2 * Sep + 1400.0, 1400.0, 5000.0);
		Height = 0.5 * Arm + 200.0;
		if (bPair && Sep > 100.0)
		{
			// 둘을 옆에서 (사냥 줄에 수직) — 지금 카메라 쪽에 가까운 옆을 고른다
			const double Line = FMath::RadiansToDegrees(FMath::Atan2(Pb.Y - Pa.Y, Pb.X - Pa.X));
			const double SideA = Line - 90.0;
			const double SideB = Line + 90.0;
			Yaw = FMath::Abs(FMath::FindDeltaAngleDegrees(S.CamYaw, SideA)) <= FMath::Abs(FMath::FindDeltaAngleDegrees(S.CamYaw, SideB)) ? SideA : SideB;
		}
		else
		{
			Yaw = S.CamYaw + 4.0 * Dt;   // 짝이 없으면 천천히 돈다 (초당 4°)
		}
		return true;
	};
	switch (S.CamMode)
	{
	case EEcoR9DemoCam::Auto:
	{
		if (Now >= S.NextPick)
		{
			S.NextPick = Now + 0.25;
			TArray<FInterest> All;
			GatherInterests(S, Now, All);
			const FInterest* Best = nullptr;
			const FInterest* Mine = nullptr;
			double BestEff = -TNumericLimits<double>::Max();
			for (FInterest& I : All)
			{
				if (bWhole)
				{
					// 맵 전체 땅: 지금 초점에서 가까운 사건을 먼저 (점수 − 거리 / 250 m)
					FVector Pa;
					if (Where(I.A, Pa))
					{
						I.Score -= FVector::Dist2D(Pa, S.bCamInit ? S.CamFocus : Center) * kNearPerCm;
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
			if (!S.bAutoFollowing)
			{
				if (Best && Best->Score >= (bWhole ? 1.5 : 2.5) && Now - S.CamModeSince >= 4.0)
				{
					S.bAutoFollowing = true;
					S.CamModeSince = Now;
					S.LastInterest = Now;
					S.FollowA = Best->A;
					S.FollowB = Best->B;
					S.CamWhat = Best->What;
				}
			}
			else
			{
				if (Mine && Mine->Score >= 1.5)
				{
					S.LastInterest = Now;
					S.FollowB = Mine->B != 0 ? Mine->B : S.FollowB;
					S.CamWhat = Mine->What;
				}
				const bool bBetter = Best && Best->Score >= (bWhole ? 4.0 : 5.0) && Best->A != S.FollowA && Now - S.CamModeSince >= 5.0;
				if (bBetter)
				{
					S.CamModeSince = Now;
					S.LastInterest = Now;
					S.FollowA = Best->A;
					S.FollowB = Best->B;
					S.CamWhat = Best->What;
				}
				else if (Now - S.LastInterest > 3.5 || Now - S.CamModeSince > 35.0)
				{
					S.bAutoFollowing = false;   // 사건이 끝남 → 전체 보기
					S.CamModeSince = Now;
					S.FollowA = S.FollowB = 0;
				}
			}
		}
		const bool bFollowed = S.bAutoFollowing && Follow(S.FollowA, S.FollowB);
		const FEcoR9DemoBody* Main = S.Bodies.Find(S.FollowA);
		const FR9Agent* MainA = S.FindCur(S.FollowA);
		if (!bFollowed && bHaveSite)
		{
			SiteView();   // 맵 전체 땅: 사건이 없으면 지금 무리 자리 (섬 전체는 동물이 너무 작다)
		}
		S.CamLabel = bFollowed ? FString::Printf(TEXT("카메라 자동 — %s #%u: %s"), Main ? SpeciesKo(Main->Species) : (MainA ? SpeciesKo(MainA->Species) : TEXT("?")),
												 S.FollowA, *S.CamWhat)
					 : bHaveSite ? FString::Printf(TEXT("카메라 자동 — 무리 자리 %d/%d (가까운 사냥·물기·반격·사체 먹기를 기다림)"), S.SiteIndex + 1,
												   static_cast<int32>(S.Info.HerdXY.size() / 2))
								 : FString(TEXT("카메라 자동 — 전체 보기 (사건을 기다림)"));
		break;
	}
	case EEcoR9DemoCam::Wide:
		S.CamLabel = bWhole ? FString(TEXT("카메라 — 섬(맵 땅) 전체 (멀리 있는 동물은 작은 공 · 7 = 무리 자리로)")) : FString(TEXT("카메라 — 전체 보기"));
		break;
	case EEcoR9DemoCam::Site:
		if (bHaveSite)
		{
			SiteView();
			S.CamLabel = FString::Printf(TEXT("카메라 — 무리 자리 %d/%d (7 = 다음 자리)"), S.SiteIndex + 1, static_cast<int32>(S.Info.HerdXY.size() / 2));
		}
		else
		{
			S.CamLabel = TEXT("카메라 — 무대 (무리 자리 없음)");
		}
		break;
	case EEcoR9DemoCam::FollowDeer:
	case EEcoR9DemoCam::FollowWolf:
	case EEcoR9DemoCam::FollowBoar:
	{
		const uint8 Sp = static_cast<uint8>(static_cast<int32>(S.CamMode) - 2);
		const FR9Agent* Cur = S.FindCur(S.FollowA);
		if (!Cur || !Cur->Alive() || Cur->Species != Sp)
		{
			// 처음 (또는 따라가던 개체가 죽음): 작은 세계는 가장 작은 번호, 맵 전체 땅은 지금 초점에서 가장 가까운 그 종
			S.FollowA = 0;
			double BestD = TNumericLimits<double>::Max();
			const FVector From = S.bCamInit ? S.CamFocus : Center;
			for (const FR9Agent& A : S.Cur.Agents)
			{
				if (!A.Alive() || A.Species != Sp)
				{
					continue;
				}
				double D = static_cast<double>(A.Id);
				if (bWhole)
				{
					double X = 0.0, Y = 0.0;
					S.Map.ToWorld(A.X, A.Y, X, Y);
					D = FVector::Dist2D(FVector(X, Y, 0.0), From);
				}
				if (S.FollowA == 0 || D < BestD)
				{
					S.FollowA = A.Id;
					BestD = D;
				}
			}
		}
		S.FollowB = 0;
		if (S.FollowA != 0 && Follow(S.FollowA, 0))
		{
			Arm = 1800.0;
			Height = 900.0;
			const FR9Agent* A = S.FindCur(S.FollowA);
			S.CamLabel = FString::Printf(TEXT("카메라 — %s #%u 따라가기 (같은 키 = 다음) · 행동 %s"), SpeciesKo(Sp), S.FollowA,
										 A ? UTF8_TO_TCHAR(ActionName(A->Action)) : TEXT("?"));
		}
		else
		{
			S.CamLabel = FString::Printf(TEXT("카메라 — 산 %s 없음 · 전체 보기"), SpeciesKo(Sp));
		}
		break;
	}
	case EEcoR9DemoCam::Top:
	{
		bTop = true;
		const double HalfV = FMath::Atan(FMath::Tan(FMath::DegreesToRadians(0.5 * kFov)) * 9.0 / 16.0);
		const double TopSide = bHaveSite ? 1.4 * SiteSide : Side;
		if (bHaveSite)
		{
			Focus = SiteFocus;   // 맵 전체 땅: 지금 무리 자리 위 (자리 정사각 × 1.4 가 화면 세로에)
		}
		Height = 0.56 * TopSide / FMath::Tan(HalfV);
		Arm = 1.0;
		Yaw = S.CamYaw;
		S.CamLabel = bHaveSite ? FString::Printf(TEXT("카메라 — 무리 자리 %d 위에서 (위 = R9 +y, 오른쪽 = +x · 7 = 다음 자리)"), S.SiteIndex + 1)
							   : FString(TEXT("카메라 — 위에서 (위 = R9 +y, 오른쪽 = +x)"));
		break;
	}
	default:
		break;
	}
	if (!S.bCamInit)
	{
		S.CamFocus = Focus;
		S.CamArm = Arm;
		S.CamHeight = Height;
		S.CamYaw = Yaw;
		S.bCamInit = true;
	}
	SmoothDampVector(S.CamFocus, S.CamFocusVel, Focus, 0.5, Dt);
	SmoothDamp(S.CamArm, S.CamArmVel, Arm, 0.9, Dt);
	SmoothDamp(S.CamHeight, S.CamHeightVel, Height, 0.9, Dt);
	SmoothDampAngle(S.CamYaw, S.CamYawVel, Yaw, 1.4, Dt);
	const double YawRad = FMath::DegreesToRadians(S.CamYaw);
	FVector Loc = S.CamFocus + FVector(FMath::Cos(YawRad) * S.CamArm, FMath::Sin(YawRad) * S.CamArm, S.CamHeight);
	Loc.Z = FMath::Max(Loc.Z, GroundZ(Loc.X, Loc.Y) + 300.0);
	const FRotator Rot = bTop ? FRotator(-89.0, -90.0, 0.0) : (S.CamFocus - Loc).Rotation();
	Camera->SetActorLocationAndRotation(Loc, Rot);
}
