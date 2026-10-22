#include "EcoV3FilmDirector.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Components/AudioComponent.h"
#include "Components/TextRenderComponent.h"
#include "Components/TimelineComponent.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "EcoPolicyV3IntegratedSubsystem.h"
#include "EcoV3WeatherPresenter.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/HUD.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PawnMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Sound/SoundBase.h"
#include "UObject/UObjectIterator.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UObject/UnrealType.h"
#include "UnrealClient.h"

DEFINE_LOG_CATEGORY_STATIC(LogEcoV3Film, Log, All);

namespace EcoV3FilmImpl
{
	static const FName WolfSpecies(TEXT("Wolf"));
	constexpr double kPrerollSeconds = 2.0;    // 장면 시작 전 카메라를 먼저 옮겨 노출이 자리 잡게 한다
	constexpr double kScoutEvery = 0.5;        // 정찰 기록 간격 (시뮬레이션 초)
	constexpr int32 kQuitWaitFrames = 30;      // 마지막 캡처 뒤 끝내기까지 기다리는 프레임 (PNG 쓰기)
	constexpr float kFov = 60.0f;
	constexpr double kFreePrerollSeconds = 3.0; // 단독 촬영: 멀리 옮길 때 땅 조각이 들어올 시간

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

TArray<UEcoV3FilmDirectorSubsystem::FFreeShot> UEcoV3FilmDirectorSubsystem::ParseFreeShots(const FString& Text)
{
	TArray<FFreeShot> Out;
	TArray<FString> Items;
	Text.ParseIntoArray(Items, TEXT(";"), true);
	for (const FString& Item : Items)
	{
		TArray<FString> F;
		Item.ParseIntoArray(F, TEXT(","), false);
		for (FString& Field : F)
		{
			Field.TrimStartAndEndInline();
		}
		const bool bMove = F.Num() >= 11;
		if (F.Num() < 8 || (F.Num() > 8 && !bMove) || F[0].IsEmpty())
		{
			UE_LOG(LogEcoV3Film, Warning, TEXT("[EcoV3Film] 단독 장면 '%s' 를 건너뜀 (이름,x,y,h,방위,숙임,시작초,길이초[,x1,y1,h1])"), *Item);
			continue;
		}
		FFreeShot S;
		S.Tag = F[0];
		S.FromM = FVector2D(FCString::Atod(*F[1]), FCString::Atod(*F[2]));
		S.FromH = FCString::Atod(*F[3]);
		S.YawDeg = FCString::Atod(*F[4]);
		S.PitchDeg = FMath::Clamp(FCString::Atod(*F[5]), -89.9, 89.9);
		S.StartSeconds = FCString::Atod(*F[6]);
		S.DurationSeconds = FMath::Max(FCString::Atod(*F[7]), 0.1);
		S.bMove = bMove;
		S.ToM = bMove ? FVector2D(FCString::Atod(*F[8]), FCString::Atod(*F[9])) : S.FromM;
		S.ToH = bMove ? FCString::Atod(*F[10]) : S.FromH;
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
	bStandalone = FParse::Param(Cmd, TEXT("EcoV3FilmStandalone"));
	FString ShotText;
	if (FParse::Value(Cmd, TEXT("EcoV3FilmShots="), ShotText, false))
	{
		if (bStandalone)
		{
			FreeShots = ParseFreeShots(ShotText);
		}
		else
		{
			Shots = ParseShots(ShotText);
		}
	}
	FParse::Value(Cmd, TEXT("EcoV3FilmScout="), ScoutUntil);
	bKeepUI = FParse::Param(Cmd, TEXT("EcoV3FilmUI"));
	bNoQuit = FParse::Param(Cmd, TEXT("EcoV3FilmNoQuit"));
	FParse::Value(Cmd, TEXT("EcoV3FilmEvery="), Every);
	Every = FMath::Max(Every, 1);
	bMovePawn = bStandalone && FParse::Value(Cmd, TEXT("EcoV3FilmPawn="), PawnAheadM);
	FString WatchText;
	if (FParse::Value(Cmd, TEXT("EcoV3FilmWatch="), WatchText, false))
	{
		WatchText.ParseIntoArray(WatchNames, TEXT(";"), true);
	}
	IFileManager::Get().MakeDirectory(*OutDir, true);
	UE_LOG(LogEcoV3Film, Log, TEXT("[EcoV3Film] 촬영 '%s' → %s | %s 장면 %d | 정찰 %s | %d 프레임마다 | 지켜볼 클래스 %d"), *Name, *OutDir,
		   bStandalone ? TEXT("단독") : TEXT("통합 v3"), bStandalone ? FreeShots.Num() : Shots.Num(),
		   ScoutUntil > 0.0 ? *FString::Printf(TEXT("%.1f초까지"), ScoutUntil) : TEXT("없음"), Every, WatchNames.Num());
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
	// -EcoV3FilmUI 면 화면 글(두뇌 교체 알림·상태 줄 등 화면 메시지)도 프레임에 넣는다 (10-22). 아니면 게임 화면만
	FScreenshotRequest::RequestScreenshot(Path, /*bInShowUI*/ bKeepUI, false);
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
	if (WatchLines.Num() > 0)
	{
		FFileHelper::SaveStringToFile(FString::Join(WatchLines, TEXT("\n")) + TEXT("\n"), *(OutDir / TEXT("watch.txt")),
									  FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	}
}

double UEcoV3FilmDirectorSubsystem::GroundZ(double XCm, double YCm, double Fallback) const
{
	// 땅 = 곧은 선이 맞은 WorldStatic 중 가장 낮은 것 (나무 충돌 껍질 같은 위의 것은 건너뛴다)
	TArray<FHitResult> Hits;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3FilmGround), false);
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

void UEcoV3FilmDirectorSubsystem::NotePerf(double T)
{
	const double Wall = FPlatformTime::Seconds();
	if (PerfWallStart < 0.0)
	{
		PerfWallStart = Wall;
		PerfSimStart = T;
		PerfTicks = 0;
		PerfCaptures = 0;
		return;
	}
	++PerfTicks;
	if (T - PerfSimStart >= 1.0 - 1e-6 && PerfTicks > 0)
	{
		const double Ms = 1000.0 * (Wall - PerfWallStart) / PerfTicks;
		WatchLines.Add(FString::Printf(TEXT("perf t=%.2f frames=%d wall_ms_per_frame=%.1f (fps %.1f) captures=%d"), T, PerfTicks, Ms,
									   Ms > 0.0 ? 1000.0 / Ms : 0.0, PerfCaptures));
		PerfWallStart = Wall;
		PerfSimStart = T;
		PerfTicks = 0;
		PerfCaptures = 0;
	}
}

void UEcoV3FilmDirectorSubsystem::WriteWatch(double T)
{
	if (WatchNames.IsEmpty())
	{
		return;
	}
	const FVector Cam = Camera ? Camera->GetActorLocation() : FVector::ZeroVector;
	FString Line = FString::Printf(TEXT("t=%.2f frame=%d cam=(%.0f,%.0f,%.0f)"), T, TotalFrames - 1, Cam.X, Cam.Y, Cam.Z);
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (const APawn* Pawn = PC ? PC->GetPawn() : nullptr)
	{
		const FVector L = Pawn->GetActorLocation();
		Line += FString::Printf(TEXT(" pawn=(%.0f,%.0f,%.0f)"), L.X, L.Y, L.Z);
	}
	else
	{
		Line += TEXT(" pawn=none");
	}
	// 소리: 이 월드에서 재생 중인 오디오 컴포넌트 모두 (팀 블루프린트 변수에 안 담긴 것도)
	Line += FString::Printf(TEXT(" audio_device=%d"), GetWorld()->GetAudioDeviceRaw() ? 1 : 0);
	for (TObjectIterator<UAudioComponent> It; It; ++It)
	{
		const UAudioComponent* Au = *It;
		if (!Au || Au->GetWorld() != GetWorld() || !Au->IsPlaying())
		{
			continue;
		}
		Line += FString::Printf(TEXT(" playing_sound=%s@%s(%.1fm,vol %.2f)"), Au->Sound ? *Au->Sound->GetName() : TEXT("?"),
								Au->GetOwner() ? *Au->GetOwner()->GetName() : TEXT("-"), FVector::Dist(Au->GetComponentLocation(), Cam) / 100.0,
								Au->VolumeMultiplier);
	}
	int32 Found = 0;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		AActor* Actor = *It;
		const FString Cls = Actor ? Actor->GetClass()->GetName() : FString();
		if (!Actor || !WatchNames.ContainsByPredicate([&Cls](const FString& N) { return Cls.Contains(N); }))
		{
			continue;
		}
		++Found;
		Line += FString::Printf(TEXT(" | %s"), *Actor->GetName());
		// 블루프린트가 선언한 변수만 (C++ 부모 클래스 변수는 건너뛴다). 10-18: 우리 연출 액터(EcoV3WeatherFx — C++ 클래스)는 그 클래스의 칸도 적는다
		for (TFieldIterator<FProperty> P(Actor->GetClass()); P; ++P)
		{
			const UClass* OwnerClass = P->GetOwnerClass();
			if (!OwnerClass || (OwnerClass->HasAnyClassFlags(CLASS_Native) && !OwnerClass->GetName().StartsWith(TEXT("EcoV3WeatherFx"))))
			{
				continue;
			}
			const void* V = P->ContainerPtrToValuePtr<void>(Actor);
			const FString PName = P->GetName();
			if (const FBoolProperty* B = CastField<FBoolProperty>(*P))
			{
				Line += FString::Printf(TEXT(" %s=%d"), *PName, B->GetPropertyValue(V) ? 1 : 0);
			}
			else if (const FNumericProperty* N = CastField<FNumericProperty>(*P))
			{
				if (N->IsFloatingPoint())
				{
					Line += FString::Printf(TEXT(" %s=%.3f"), *PName, N->GetFloatingPointPropertyValue(V));
				}
				else if (N->IsInteger() && !N->IsEnum())
				{
					Line += FString::Printf(TEXT(" %s=%lld"), *PName, static_cast<long long>(N->GetSignedIntPropertyValue(V)));
				}
			}
			else if (const FStructProperty* S = CastField<FStructProperty>(*P); S && S->Struct == TBaseStructure<FRotator>::Get())
			{
				const FRotator* R = static_cast<const FRotator*>(V);
				Line += FString::Printf(TEXT(" %s=(p%.1f,y%.1f,r%.1f)"), *PName, R->Pitch, R->Yaw, R->Roll);
			}
			else if (const FObjectPropertyBase* O = CastField<FObjectPropertyBase>(*P))
			{
				const UObject* Obj = O->GetObjectPropertyValue(V);
				if (!Obj)
				{
					Line += FString::Printf(TEXT(" %s=none"), *PName);
				}
				else if (const UActorComponent* C = Cast<UActorComponent>(Obj))
				{
					Line += FString::Printf(TEXT(" %s=%s[active=%d"), *PName, *C->GetClass()->GetName(), C->IsActive() ? 1 : 0);
					if (const UAudioComponent* Au = Cast<UAudioComponent>(C))
					{
						Line += FString::Printf(TEXT(" playing=%d vol=%.2f"), Au->IsPlaying() ? 1 : 0, Au->VolumeMultiplier);
					}
					// 10-18: 나이아가라 컴포넌트는 사용자 칸 User.SpawnRate (팀 비 Rain_System 의 세기 칸 — 없으면 −1, 읽기만)
					if (const double Rate = EcoV3WeatherFx::NiagaraUserFloat(const_cast<UActorComponent*>(C), EcoV3WeatherFx::kSpawnRateName); Rate >= 0.0)
					{
						Line += FString::Printf(TEXT(" spawn_rate=%.1f"), Rate);
					}
					if (const UTimelineComponent* Tl = Cast<UTimelineComponent>(C))
					{
						Line += FString::Printf(TEXT(" playing=%d pos=%.2f/%.2f"), Tl->IsPlaying() ? 1 : 0, Tl->GetPlaybackPosition(), Tl->GetTimelineLength());
					}
					if (const USceneComponent* Sc = Cast<USceneComponent>(C))
					{
						const FVector L = Sc->GetComponentLocation();
						const USceneComponent* Parent = Sc->GetAttachParent();
						Line += FString::Printf(TEXT(" visible=%d at=(%.0f,%.0f,%.0f) cam_d=%.1fm parent=%s"), Sc->IsVisible() ? 1 : 0, L.X, L.Y, L.Z,
												FVector::Dist(L, Cam) / 100.0,
												Parent && Parent->GetOwner() ? *Parent->GetOwner()->GetName() : TEXT("-"));
					}
					Line += TEXT("]");
				}
				else if (const AActor* A = Cast<AActor>(Obj))
				{
					const FRotator R = A->GetActorRotation();
					Line += FString::Printf(TEXT(" %s=%s(p%.1f,y%.1f)"), *PName, *A->GetName(), R.Pitch, R.Yaw);
				}
				else
				{
					Line += FString::Printf(TEXT(" %s=%s"), *PName, *Obj->GetName());
				}
			}
		}
	}
	if (Found == 0)
	{
		Line += TEXT(" | 지켜볼 액터 없음");
	}
	WatchLines.Add(Line);
}

void UEcoV3FilmDirectorSubsystem::TickStandalone(double T)
{
	using namespace EcoV3FilmImpl;
	if (!FreeShots.IsValidIndex(ShotIndex))
	{
		Finish();
		return;
	}
	const FFreeShot& Shot = FreeShots[ShotIndex];
	const double ShotTime = T - Shot.StartSeconds;
	if (ShotTime < -kFreePrerollSeconds)
	{
		return;
	}
	EnsureCamera();
	if (!Camera)
	{
		return;
	}
	const double A = Shot.bMove ? FMath::Clamp(ShotTime / Shot.DurationSeconds, 0.0, 1.0) : 0.0;
	const FVector2D P = FMath::Lerp(Shot.FromM, Shot.ToM, A) * 100.0;
	const double H = FMath::Lerp(Shot.FromH, Shot.ToH, A) * 100.0;
	LastGroundZ = GroundZ(P.X, P.Y, LastGroundZ);
	Camera->SetActorLocationAndRotation(FVector(P.X, P.Y, LastGroundZ + H), FRotator(Shot.PitchDeg, Shot.YawDeg, 0.0));
	Camera->GetCameraComponent()->SetFieldOfView(kFov);
	if (bMovePawn)
	{
		// 폰을 카메라 앞(뒤) 땅 위에 둔다 — 3인칭 놀이처럼 폰과 카메라가 같은 곳에 있게 (떨어지지 않게 이동 컴포넌트를 끈다)
		APlayerController* PC = GetWorld()->GetFirstPlayerController();
		if (APawn* Pawn = PC ? PC->GetPawn() : nullptr)
		{
			if (!bPawnMovementOff)
			{
				if (UPawnMovementComponent* Move = Pawn->GetMovementComponent())
				{
					Move->StopMovementImmediately();
					Move->Deactivate();
				}
				bPawnMovementOff = true;
			}
			const double Yaw = FMath::DegreesToRadians(Shot.YawDeg);
			const double X = P.X + FMath::Cos(Yaw) * PawnAheadM * 100.0;
			const double Y = P.Y + FMath::Sin(Yaw) * PawnAheadM * 100.0;
			const double Z = GroundZ(X, Y, LastGroundZ) + Pawn->GetSimpleCollisionHalfHeight();
			Pawn->SetActorLocationAndRotation(FVector(X, Y, Z), FRotator(0.0, Shot.YawDeg, 0.0), false, nullptr, ETeleportType::TeleportPhysics);
		}
	}
	if (ShotTime < 0.0)
	{
		return;
	}
	if (ShotTicks == 0)
	{
		ShotFirstSim = T;
		ShotFirstFrame = TotalFrames;
		UE_LOG(LogEcoV3Film, Log, TEXT("[EcoV3Film] 단독 장면 %d '%s' 시작 t=%.2f 카메라 (%.0f, %.0f, %.0f) cm"), ShotIndex, *Shot.Tag, T, P.X, P.Y,
			   LastGroundZ + H);
	}
	if (ShotTicks % Every == 0)
	{
		CaptureFrame();
		++PerfCaptures;
		WriteWatch(T);
		ShotLastSim = T;
	}
	++ShotTicks;
	if (ShotTicks >= FMath::RoundToInt32(Shot.DurationSeconds * 30.0))
	{
		ManifestShots.Add(FString::Printf(
			TEXT("    {\"tag\": \"%s\", \"from_m\": [%.2f, %.2f, %.2f], \"to_m\": [%.2f, %.2f, %.2f], \"yaw\": %.1f, \"pitch\": %.1f, \"start\": %.3f, ")
			TEXT("\"duration\": %.3f, \"every\": %d, \"first_frame\": %d, \"frames\": %d, \"t_first\": %.3f, \"t_last\": %.3f}"),
			*Shot.Tag, Shot.FromM.X, Shot.FromM.Y, Shot.FromH, Shot.ToM.X, Shot.ToM.Y, Shot.ToH, Shot.YawDeg, Shot.PitchDeg, Shot.StartSeconds,
			Shot.DurationSeconds, Every, ShotFirstFrame, ShotFrames, ShotFirstSim, ShotLastSim));
		++ShotIndex;
		ShotFrames = 0;
		ShotTicks = 0;
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
	if (bStandalone)
	{
		// 단독 촬영: 통합 v3 모드를 보지 않고 월드 시간으로 카메라만 옮긴다
		const double T = GetWorld()->GetTimeSeconds();
		NotePerf(T);
		HideIdentityLabels();   // 10-18: 통합 v3 모드와 함께 돌 때 팀 개체 이름표가 보이므로 단독 촬영도 화면에서만 숨긴다 (-EcoV3FilmUI 면 그대로)
		TickStandalone(T);
		return;
	}
	UEcoPolicyV3IntegratedSubsystem* V3 = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	if (!V3 || !V3->IsActive() || V3->NumContexts() == 0)
	{
		return;
	}
	const double Sim = SimSeconds(*V3);
	if (!WatchNames.IsEmpty())
	{
		NotePerf(Sim);
	}

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
	if (ShotTicks == 0)
	{
		ShotFirstSim = Sim;
		ShotFirstFrame = TotalFrames;
		ShotStartAlive = Ctx->AliveDeer;
		ShotStartCaught = Ctx->Sim.Stats.Caught;
		ShotStartStarved = Ctx->Sim.Stats.Starved;
	}
	if (ShotTicks % Every == 0)
	{
		CaptureFrame();
		++PerfCaptures;
		WriteWatch(Sim);
	}
	ShotLastSim = Sim;
	++ShotTicks;
	if (ShotTicks >= FMath::RoundToInt32(Shot.DurationSeconds * 30.0))
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
		ShotTicks = 0;
		bLocked = false;
		LockedId = 0;
	}
}
