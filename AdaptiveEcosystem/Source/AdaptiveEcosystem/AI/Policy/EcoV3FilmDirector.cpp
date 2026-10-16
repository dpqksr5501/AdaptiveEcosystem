#include "EcoV3FilmDirector.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/TextRenderComponent.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "EcoPolicyV3IntegratedSubsystem.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

DEFINE_LOG_CATEGORY_STATIC(LogEcoV3Film, Log, All);

namespace EcoV3FilmImpl
{
	static const FName WolfSpecies(TEXT("Wolf"));
	constexpr double kPrerollSeconds = 2.0;    // 장면 시작 전 카메라를 먼저 옮겨 노출이 자리 잡게 한다
	constexpr double kScoutEvery = 0.5;        // 정찰 기록 간격 (시뮬레이션 초)
	constexpr int32 kQuitWaitFrames = 30;      // 마지막 캡처 뒤 끝내기까지 기다리는 프레임 (PNG 쓰기)
	constexpr float kFov = 60.0f;

	double SimSeconds(const UEcoPolicyV3IntegratedSubsystem& V3)
	{
		return (static_cast<double>(V3.GetGlobalStep()) + static_cast<double>(V3.GetVisualAlpha())) * EcoRepertoireV3::kStepSeconds;
	}

	FVector StageCenter(const FEcoV3RegionContext& Ctx)
	{
		const double Half = 0.5 * Ctx.SizeCm();
		return FVector(Ctx.OriginCm.X + Half, Ctx.OriginCm.Y + Half, Ctx.OriginCm.Z);
	}

	FVector CoverCenter(const FEcoV3RegionContext& Ctx, int32 K)
	{
		const EcoObservationV3::FCoverInput& Cv = Ctx.Sim.Config.Covers[static_cast<size_t>(K)];
		const double Z = Ctx.CoverGroundZ.IsValidIndex(K) ? Ctx.CoverGroundZ[K] : Ctx.OriginCm.Z;
		return Ctx.UnitsToCm(Cv.X, Cv.Y, Z);
	}
}

TArray<UEcoV3FilmDirectorSubsystem::FShot> UEcoV3FilmDirectorSubsystem::ParseShots(const FString& Text)
{
	TArray<FShot> Out;
	TArray<FString> Items;
	Text.ParseIntoArray(Items, TEXT(";"), true);
	for (const FString& Item : Items)
	{
		TArray<FString> F;
		Item.ParseIntoArray(F, TEXT(","), false);
		if (F.Num() < 5)
		{
			UE_LOG(LogEcoV3Film, Warning, TEXT("[EcoV3Film] 장면 '%s' 를 건너뜀 (지역,방식,대상,시작초,길이초 가 필요)"), *Item);
			continue;
		}
		FShot S;
		S.RegionId = FName(*F[0].TrimStartAndEnd());
		S.Mode = F[1].TrimStartAndEnd().ToLower();
		S.Subject = FCString::Atoi(*F[2]);
		S.StartSeconds = FCString::Atod(*F[3]);
		S.DurationSeconds = FMath::Max(FCString::Atod(*F[4]), 0.1);
		if (F.Num() > 5 && !F[5].IsEmpty()) { S.DistM = FCString::Atod(*F[5]); }
		if (F.Num() > 6 && !F[6].IsEmpty()) { S.HeightM = FCString::Atod(*F[6]); }
		if (F.Num() > 7 && !F[7].IsEmpty()) { S.YawDeg = FCString::Atod(*F[7]); }
		if (F.Num() > 8 && !F[8].IsEmpty()) { S.Debug = FCString::Atoi(*F[8]) != 0 ? 1 : 0; }
		Out.Add(S);
	}
	return Out;
}

bool UEcoV3FilmDirectorSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	// 명령줄 스위치가 없으면 만들지 않는다 — 보통 게임·에디터·자동화 시험에는 이 감독이 없다
	FString Dummy;
	return FParse::Value(FCommandLine::Get(), TEXT("EcoV3Film="), Dummy) && Super::ShouldCreateSubsystem(Outer);
}

bool UEcoV3FilmDirectorSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UEcoV3FilmDirectorSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	const TCHAR* Cmd = FCommandLine::Get();
	FParse::Value(Cmd, TEXT("EcoV3Film="), Name);
	FString Base = FPaths::ProjectSavedDir() / TEXT("EcoV3Film");
	FParse::Value(Cmd, TEXT("EcoV3FilmOut="), Base, false);
	OutDir = FPaths::ConvertRelativePathToFull(Base / Name);
	FString ShotText;
	if (FParse::Value(Cmd, TEXT("EcoV3FilmShots="), ShotText, false))
	{
		Shots = ParseShots(ShotText);
	}
	FParse::Value(Cmd, TEXT("EcoV3FilmScout="), ScoutUntil);
	bKeepUI = FParse::Param(Cmd, TEXT("EcoV3FilmUI"));
	bNoQuit = FParse::Param(Cmd, TEXT("EcoV3FilmNoQuit"));
	IFileManager::Get().MakeDirectory(*OutDir, true);
	UE_LOG(LogEcoV3Film, Log, TEXT("[EcoV3Film] 촬영 '%s' → %s | 장면 %d | 정찰 %s"), *Name, *OutDir, Shots.Num(),
		   ScoutUntil > 0.0 ? *FString::Printf(TEXT("%.1f초까지"), ScoutUntil) : TEXT("없음"));
	if (ScoutUntil > 0.0)
	{
		ScoutLines.Add(TEXT("t,region,alive,caught,starved,dark,panic,alert,shelter,widx,wid,x,y,eat,pursue,motion,catches,nd,run20,edge25,cov,covd,covin"));
	}
}

TStatId UEcoV3FilmDirectorSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UEcoV3FilmDirectorSubsystem, STATGROUP_Tickables);
}

void UEcoV3FilmDirectorSubsystem::GatherActors(FName RegionId, TArray<AEcoCreatureRepresentationActor*>& OutWolves,
											   TArray<AEcoCreatureRepresentationActor*>& OutDeer) const
{
	OutWolves.Reset();
	OutDeer.Reset();
	for (TActorIterator<AEcoCreatureRepresentationActor> It(GetWorld()); It; ++It)
	{
		AEcoCreatureRepresentationActor* Rep = *It;
		if (!Rep || !Rep->bBound || !Rep->VisualState.bAlive || Rep->VisualState.RegionId != RegionId)
		{
			continue;
		}
		(Rep->VisualState.SpeciesId == EcoV3FilmImpl::WolfSpecies ? OutWolves : OutDeer).Add(Rep);
	}
	OutWolves.Sort([](const AEcoCreatureRepresentationActor& A, const AEcoCreatureRepresentationActor& B)
				   { return A.VisualState.StableAgentId < B.VisualState.StableAgentId; });
}

AEcoCreatureRepresentationActor* UEcoV3FilmDirectorSubsystem::FindById(int64 Id) const
{
	for (TActorIterator<AEcoCreatureRepresentationActor> It(GetWorld()); It; ++It)
	{
		if (*It && (*It)->bBound && (*It)->VisualState.StableAgentId == Id)
		{
			return *It;
		}
	}
	return nullptr;
}

bool UEcoV3FilmDirectorSubsystem::ComputeView(const FShot& Shot, const FEcoV3RegionContext& Ctx, double ShotTime, FVector& OutLoc,
											  FRotator& OutRot, float& OutFov)
{
	using namespace EcoV3FilmImpl;
	const double Side = Ctx.SizeCm();
	OutFov = kFov;
	auto Orbit = [&](const FVector& Target, double DefDist, double DefHeight, double DefYaw, double YawRate)
	{
		const double D = Shot.DistM >= 0.0 ? Shot.DistM * 100.0 : DefDist;
		const double H = Shot.HeightM >= 0.0 ? Shot.HeightM * 100.0 : DefHeight;
		const double Yaw = FMath::DegreesToRadians((Shot.YawDeg > -999.0 ? Shot.YawDeg : DefYaw) + YawRate * ShotTime);
		OutLoc = Target + FVector(FMath::Cos(Yaw) * D, FMath::Sin(Yaw) * D, H);
		OutRot = (Target - OutLoc).Rotation();
	};
	if (Shot.Mode == TEXT("wide"))
	{
		Orbit(StageCenter(Ctx), 0.8 * Side, 0.45 * Side, 225.0, 0.0);
		return true;
	}
	if (Shot.Mode == TEXT("top"))
	{
		const double HalfV = FMath::Atan(FMath::Tan(FMath::DegreesToRadians(0.5 * kFov)) * 9.0 / 16.0);
		const double H = Shot.HeightM >= 0.0 ? Shot.HeightM * 100.0 : 0.54 * Side / FMath::Tan(HalfV);
		OutLoc = StageCenter(Ctx) + FVector(0.0, 0.0, H);
		OutRot = FRotator(-89.9, 0.0, 0.0);
		return true;
	}
	if (Shot.Mode == TEXT("shelter"))
	{
		const int32 NumCovers = static_cast<int32>(Ctx.Sim.Config.Covers.size());
		if (NumCovers <= 0)
		{
			return false;
		}
		Orbit(CoverCenter(Ctx, FMath::Clamp(Shot.Subject, 0, NumCovers - 1)) + FVector(0, 0, 100), 2600.0, 1400.0, 225.0, 12.0);
		return true;
	}
	// wolf·deer: 장면 첫 프레임에 대상을 정하고 끝까지 같은 개체를 따라간다
	if (!bLocked)
	{
		TArray<AEcoCreatureRepresentationActor*> Wolves, Deer;
		GatherActors(Shot.RegionId, Wolves, Deer);
		if (Wolves.Num() == 0)
		{
			return false;
		}
		const AEcoCreatureRepresentationActor* W = Wolves[FMath::Clamp(Shot.Subject, 0, Wolves.Num() - 1)];
		LockedId = W->VisualState.StableAgentId;
		if (Shot.Mode == TEXT("deer"))
		{
			double Best = TNumericLimits<double>::Max();
			for (const AEcoCreatureRepresentationActor* D : Deer)
			{
				const double Dist = FVector::DistSquared2D(D->GetActorLocation(), W->GetActorLocation());
				if (Dist < Best)
				{
					Best = Dist;
					LockedId = D->VisualState.StableAgentId;
				}
			}
		}
		bLocked = true;
		UE_LOG(LogEcoV3Film, Log, TEXT("[EcoV3Film] 장면 %d (%s %s) 대상 StableAgentId %lld"), ShotIndex, *Shot.RegionId.ToString(), *Shot.Mode, LockedId);
	}
	if (const AEcoCreatureRepresentationActor* A = FindById(LockedId))
	{
		LastTarget = A->GetActorLocation() + FVector(0, 0, 80);
	}
	Orbit(LastTarget, 2200.0, 1600.0, 225.0, 0.0);
	return true;
}

void UEcoV3FilmDirectorSubsystem::EnsureCamera()
{
	UWorld* World = GetWorld();
	if (!Camera)
	{
		FActorSpawnParameters P;
		P.Name = TEXT("EcoV3FilmCamera");
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Camera = World->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), FTransform::Identity, P);
		if (Camera)
		{
			Camera->GetCameraComponent()->bConstrainAspectRatio = false;
		}
	}
	APlayerController* PC = World->GetFirstPlayerController();
	if (Camera && PC && PC->GetViewTarget() != Camera)
	{
		PC->SetViewTarget(Camera);
	}
	ApplyViewEnvironment();
}

void UEcoV3FilmDirectorSubsystem::ApplyViewEnvironment()
{
	// 보기만 바꾼다: HUD 그림·화면 메시지 숨김. eco.V3Debug 글자(HUD 디버그 글자 목록)는 bShowHUD 와 무관하게 그려지고 캡처에도 든다
	if (bEnvApplied || bKeepUI)
	{
		return;
	}
	if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		if (AHUD* Hud = PC->GetHUD())
		{
			Hud->bShowHUD = false;
			bEnvApplied = true;
		}
	}
	if (GEngine)
	{
		GEngine->bEnableOnScreenDebugMessages = false;
	}
}

void UEcoV3FilmDirectorSubsystem::HideIdentityLabels()
{
	// 팀 표현 액터의 이름표('Herbivore #8' 글자 컴포넌트)를 화면에서만 숨긴다 — 팀 파일·상태는 그대로, 촬영 판에서만
	if (bKeepUI)
	{
		return;
	}
	for (TActorIterator<AEcoCreatureRepresentationActor> It(GetWorld()); It; ++It)
	{
		if (UTextRenderComponent* Label = It->IdentityLabel; Label && !Label->bHiddenInGame)
		{
			Label->SetHiddenInGame(true);
		}
	}
}

void UEcoV3FilmDirectorSubsystem::CaptureFrame()
{
	const FString Path = OutDir / FString::Printf(TEXT("f_%05d.png"), TotalFrames);
	FScreenshotRequest::RequestScreenshot(Path, false, false);
	++TotalFrames;
	++ShotFrames;
}

void UEcoV3FilmDirectorSubsystem::WriteScoutRows(double SimSeconds)
{
	using namespace EcoV3FilmImpl;
	UEcoPolicyV3IntegratedSubsystem* V3 = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	for (int32 c = 0; V3 && c < V3->NumContexts(); ++c)
	{
		const FEcoV3RegionContext* Ctx = V3->GetContext(c);
		if (!Ctx)
		{
			continue;
		}
		TArray<AEcoCreatureRepresentationActor*> Wolves, Deer;
		GatherActors(Ctx->RegionId, Wolves, Deer);
		const double Side = Ctx->SizeCm();
		const int32 NumCovers = static_cast<int32>(Ctx->Sim.Config.Covers.size());
		for (int32 w = 0; w < Wolves.Num(); ++w)
		{
			const AEcoCreatureRepresentationActor* W = Wolves[w];
			const FVector WL = W->GetActorLocation();
			double Nd = TNumericLimits<double>::Max();
			int32 Run20 = 0, Edge25 = 0;
			for (const AEcoCreatureRepresentationActor* D : Deer)
			{
				const FVector DL = D->GetActorLocation();
				const double Dist = FVector::Dist2D(DL, WL);
				Nd = FMath::Min(Nd, Dist);
				const bool bRun = D->VisualMotion == EEcoCreatureVisualMotion::Run;
				Run20 += (bRun && Dist < 2000.0) ? 1 : 0;
				const double Rx = DL.X - Ctx->OriginCm.X;
				const double Ry = DL.Y - Ctx->OriginCm.Y;
				const double Edge = FMath::Min(FMath::Min(Rx, Side - Rx), FMath::Min(Ry, Side - Ry));
				Edge25 += (bRun && Dist < 2500.0 && Edge < 1000.0) ? 1 : 0;
			}
			int32 Cov = -1, CovIn = 0;
			double CovD = TNumericLimits<double>::Max();
			for (int32 k = 0; k < NumCovers; ++k)
			{
				const double R = Ctx->Sim.Config.Covers[static_cast<size_t>(k)].Radius * EcoRepertoireV3::kUnitCm;
				const double Dk = FVector::Dist2D(CoverCenter(*Ctx, k), WL) - R;
				if (Dk < CovD)
				{
					CovD = Dk;
					Cov = k;
				}
			}
			if (Cov >= 0)
			{
				const FVector Cc = CoverCenter(*Ctx, Cov);
				const double R = Ctx->Sim.Config.Covers[static_cast<size_t>(Cov)].Radius * EcoRepertoireV3::kUnitCm;
				for (const AEcoCreatureRepresentationActor* D : Deer)
				{
					CovIn += FVector::Dist2D(D->GetActorLocation(), Cc) < R ? 1 : 0;
				}
			}
			ScoutLines.Add(FString::Printf(TEXT("%.2f,%s,%d,%lld,%lld,%.3f,%d,%d,%d,%d,%lld,%.1f,%.1f,%d,%d,%d,%d,%.1f,%d,%d,%d,%.1f,%d"),
										   SimSeconds, *Ctx->RegionId.ToString(), Ctx->AliveDeer, static_cast<long long>(Ctx->Sim.Stats.Caught),
										   static_cast<long long>(Ctx->Sim.Stats.Starved), Ctx->Sim.Dark, Ctx->KeepNow[EcoWorldV3::kKeepPanic],
										   Ctx->KeepNow[EcoWorldV3::kKeepAlert], Ctx->KeepNow[EcoWorldV3::kKeepShelter], w,
										   W->VisualState.StableAgentId, (WL.X - Ctx->OriginCm.X) / 100.0, (WL.Y - Ctx->OriginCm.Y) / 100.0,
										   W->VisualState.bEating ? 1 : 0, W->VisualState.bPursuingPrey ? 1 : 0, static_cast<int32>(W->VisualMotion),
										   Ctx->WolfCatchesById.FindRef(W->VisualState.StableAgentId), Nd / 100.0, Run20, Edge25, Cov,
										   CovD / 100.0, CovIn));
		}
	}
}

void UEcoV3FilmDirectorSubsystem::WriteManifest()
{
	FString Json = FString::Printf(TEXT("{\n  \"name\": \"%s\",\n  \"fps\": 30,\n  \"frames\": %d,\n  \"shots\": [\n%s\n  ]\n}\n"), *Name, TotalFrames,
								   *FString::Join(ManifestShots, TEXT(",\n")));
	FFileHelper::SaveStringToFile(Json, *(OutDir / TEXT("shots.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	if (ScoutLines.Num() > 1)
	{
		FFileHelper::SaveStringToFile(FString::Join(ScoutLines, TEXT("\n")) + TEXT("\n"), *(OutDir / TEXT("scout.csv")),
									  FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	}
}

void UEcoV3FilmDirectorSubsystem::Finish()
{
	WriteManifest();
	UE_LOG(LogEcoV3Film, Log, TEXT("[EcoV3Film] 끝 — 프레임 %d, 장면 %d → %s"), TotalFrames, ManifestShots.Num(), *OutDir);
	QuitCountdown = bNoQuit ? -2 : EcoV3FilmImpl::kQuitWaitFrames;
}

void UEcoV3FilmDirectorSubsystem::Tick(float DeltaTime)
{
	using namespace EcoV3FilmImpl;
	Super::Tick(DeltaTime);
	if (QuitCountdown >= 0)
	{
		if (QuitCountdown-- == 0)
		{
			FPlatformMisc::RequestExit(false, TEXT("EcoV3Film"));
		}
		return;
	}
	if (QuitCountdown == -2)
	{
		return;
	}
	UEcoPolicyV3IntegratedSubsystem* V3 = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	if (!V3 || !V3->IsActive() || V3->NumContexts() == 0)
	{
		return;
	}
	const double Sim = SimSeconds(*V3);

	if (ScoutUntil > 0.0)
	{
		if (Sim >= NextScout)
		{
			WriteScoutRows(Sim);
			NextScout += kScoutEvery;
		}
		if (Sim >= ScoutUntil && !Shots.IsValidIndex(ShotIndex))
		{
			Finish();
			return;
		}
	}
	if (!Shots.IsValidIndex(ShotIndex))
	{
		if (ScoutUntil <= 0.0)
		{
			Finish();
		}
		return;
	}
	const FShot& Shot = Shots[ShotIndex];
	const double ShotTime = Sim - Shot.StartSeconds;
	if (ShotTime < -kPrerollSeconds)
	{
		return;
	}
	FEcoV3RegionContext* Ctx = V3->FindContext(Shot.RegionId);
	if (!Ctx)
	{
		UE_LOG(LogEcoV3Film, Warning, TEXT("[EcoV3Film] 장면 %d: 지역 %s 없음 — 건너뜀"), ShotIndex, *Shot.RegionId.ToString());
		++ShotIndex;
		return;
	}
	EnsureCamera();
	HideIdentityLabels();
	if (PreparedShot != ShotIndex)
	{
		PreparedShot = ShotIndex;
		if (Shot.Debug >= 0)
		{
			if (IConsoleVariable* Dbg = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.V3Debug")))
			{
				Dbg->Set(Shot.Debug, ECVF_SetByConsole);
			}
		}
	}
	FVector Loc;
	FRotator Rot;
	float Fov = kFov;
	if (Camera && ComputeView(Shot, *Ctx, FMath::Max(ShotTime, 0.0), Loc, Rot, Fov))
	{
		Camera->SetActorLocationAndRotation(Loc, Rot);
		Camera->GetCameraComponent()->SetFieldOfView(Fov);
	}
	if (ShotTime < 0.0)
	{
		return;
	}
	if (ShotFrames == 0)
	{
		ShotFirstSim = Sim;
		ShotFirstFrame = TotalFrames;
		ShotStartAlive = Ctx->AliveDeer;
		ShotStartCaught = Ctx->Sim.Stats.Caught;
		ShotStartStarved = Ctx->Sim.Stats.Starved;
	}
	CaptureFrame();
	ShotLastSim = Sim;
	if (ShotFrames >= FMath::RoundToInt32(Shot.DurationSeconds * 30.0))
	{
		ManifestShots.Add(FString::Printf(
			TEXT("    {\"region\": \"%s\", \"mode\": \"%s\", \"subject\": %d, \"subject_id\": %lld, \"start\": %.3f, \"duration\": %.3f, ")
			TEXT("\"first_frame\": %d, \"frames\": %d, \"sim_first\": %.3f, \"sim_last\": %.3f, \"alive_start\": %d, \"alive_end\": %d, ")
			TEXT("\"caught_start\": %lld, \"caught_end\": %lld, \"starved_start\": %lld, \"starved_end\": %lld}"),
			*Shot.RegionId.ToString(), *Shot.Mode, Shot.Subject, bLocked ? LockedId : -1, Shot.StartSeconds, Shot.DurationSeconds, ShotFirstFrame,
			ShotFrames, ShotFirstSim, ShotLastSim, ShotStartAlive, Ctx->AliveDeer, static_cast<long long>(ShotStartCaught),
			static_cast<long long>(Ctx->Sim.Stats.Caught), static_cast<long long>(ShotStartStarved), static_cast<long long>(Ctx->Sim.Stats.Starved)));
		++ShotIndex;
		ShotFrames = 0;
		bLocked = false;
		LockedId = 0;
	}
}
