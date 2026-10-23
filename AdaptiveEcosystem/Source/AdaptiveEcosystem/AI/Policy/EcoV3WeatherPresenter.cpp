#include "EcoV3WeatherPresenter.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "Components/BoxComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Misc/App.h"
#include "HAL/IConsoleManager.h"
#include "Particles/ParticleSystem.h"
#include "Particles/ParticleSystemComponent.h"
#include "Sound/SoundBase.h"
#include "UObject/UnrealType.h"
#include "World/EcologyRegion.h"
#include "Network/EcoGameState.h"

#include "EcoPolicyV3IntegratedSubsystem.h"
#include "EcoWorldV3.h"

// -----------------------------------------------------------------------------
// 순수 함수 (시험 Policy.V3.Weather.Presenter)
// -----------------------------------------------------------------------------

double EcoV3WeatherFx::Approach(double Alpha, double Target, double DeltaSeconds, double FadeInSeconds, double FadeOutSeconds)
{
	if (!(DeltaSeconds > 0.0))
	{
		return Alpha;
	}
	if (Target > Alpha)
	{
		return FadeInSeconds > 0.0 ? FMath::Min(Target, Alpha + DeltaSeconds / FadeInSeconds) : Target;
	}
	if (Target < Alpha)
	{
		return FadeOutSeconds > 0.0 ? FMath::Max(Target, Alpha - DeltaSeconds / FadeOutSeconds) : Target;
	}
	return Alpha;
}

void EcoV3WeatherFx::Targets(int32 Kind, double Intensity, double& OutRain, double& OutSnow)
{
	const double I = FMath::IsFinite(Intensity) ? FMath::Clamp(Intensity, 0.0, 1.0) : 0.0;
	OutRain = Kind == EcoWorldV3::kWeatherRain ? I : 0.0;
	OutSnow = Kind == EcoWorldV3::kWeatherSnow ? I : 0.0;
}

bool EcoV3WeatherFx::ContainsXY(const FTransform& BoxTransform, const FVector& Extent, const FVector& P)
{
	if (P.ContainsNaN())
	{
		return false;
	}
	const FVector Local = BoxTransform.InverseTransformPosition(P);
	return FMath::Abs(Local.X) <= Extent.X && FMath::Abs(Local.Y) <= Extent.Y;
}

// -----------------------------------------------------------------------------
// 액터
// -----------------------------------------------------------------------------

AEcoV3WeatherFxActor::AEcoV3WeatherFxActor()
{
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	PrimaryActorTick.bCanEverTick = false;
	SetCanBeDamaged(false);
	bReplicates = false;
}

void FEcoV3WeatherFxTickFunction::ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread,
											  const FGraphEventRef& MyCompletionGraphEvent)
{
	if (UEcoV3WeatherPresenterSubsystem* Sub = Owner.Get())
	{
		Sub->TickPresenter(DeltaTime);
	}
}

// -----------------------------------------------------------------------------
// 반사 호출 (Niagara 모듈에 기대지 않는다 — 엔진 기반 클래스 UFXSystemComponent 와 UFUNCTION 만 쓴다)
// -----------------------------------------------------------------------------

namespace EcoV3WeatherFxImpl
{
	/** UFUNCTION 하나를 이름으로 부른다. Fill 이 인자를 넣고 Read 가 결과를 읽는다. 함수가 없으면 거짓. */
	bool CallFunction(UObject* Obj, const TCHAR* Name, TFunctionRef<void(UFunction&, uint8*)> Fill, TFunctionRef<void(UFunction&, uint8*)> Read)
	{
		UFunction* Fn = Obj ? Obj->FindFunction(FName(Name)) : nullptr;
		if (!Fn)
		{
			return false;
		}
		uint8* Parms = static_cast<uint8*>(FMemory_Alloca(FMath::Max<int32>(Fn->ParmsSize, 1)));
		FMemory::Memzero(Parms, FMath::Max<int32>(Fn->ParmsSize, 1));
		for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
		{
			It->InitializeValue_InContainer(Parms);
		}
		Fill(*Fn, Parms);
		Obj->ProcessEvent(Fn, Parms);
		Read(*Fn, Parms);
		for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
		{
			It->DestroyValue_InContainer(Parms);
		}
		return true;
	}

	/** UNiagaraComponent::SetAsset(InAsset, bResetExistingOverrideParameters = true). */
	bool SetAsset(UFXSystemComponent* C, UFXSystemAsset* Asset)
	{
		bool bOk = false;
		const bool bCalled = CallFunction(
			C, TEXT("SetAsset"),
			[Asset, &bOk](UFunction& Fn, uint8* Parms)
			{
				if (FObjectPropertyBase* P = CastField<FObjectPropertyBase>(Fn.FindPropertyByName(TEXT("InAsset"))))
				{
					P->SetObjectPropertyValue_InContainer(Parms, Asset);
					bOk = true;
				}
				if (FBoolProperty* B = CastField<FBoolProperty>(Fn.FindPropertyByName(TEXT("bResetExistingOverrideParameters"))))
				{
					B->SetPropertyValue_InContainer(Parms, true);
				}
			},
			[](UFunction&, uint8*) {});
		return bCalled && bOk;
	}

	/** UNiagaraComponent::GetVariableFloat(Name, bIsValid) — 사용자 칸 지금 값. 칸이 없으면 −1. */
	double GetVariableFloat(UObject* C, const TCHAR* Name)
	{
		double Out = -1.0;
		CallFunction(
			C, TEXT("GetVariableFloat"),
			[Name](UFunction& Fn, uint8* Parms)
			{
				if (FNameProperty* P = CastField<FNameProperty>(Fn.FindPropertyByName(TEXT("InVariableName"))))
				{
					P->SetPropertyValue_InContainer(Parms, FName(Name));
				}
			},
			[&Out](UFunction& Fn, uint8* Parms)
			{
				const FBoolProperty* Valid = CastField<FBoolProperty>(Fn.FindPropertyByName(TEXT("bIsValid")));
				const FFloatProperty* Ret = CastField<FFloatProperty>(Fn.GetReturnProperty());
				if (Valid && Ret && Valid->GetPropertyValue_InContainer(Parms))
				{
					Out = static_cast<double>(Ret->GetPropertyValue_InContainer(Parms));
				}
			});
		return Out;
	}

	UFXSystemComponent* MakeNiagara(AEcoV3WeatherFxActor& Owner, UClass* NiagaraClass, UFXSystemAsset* Asset, const TCHAR* Name)
	{
		if (!NiagaraClass || !Asset)
		{
			return nullptr;
		}
		UFXSystemComponent* C = NewObject<UFXSystemComponent>(&Owner, NiagaraClass, FName(Name), RF_Transient);
		if (!C)
		{
			return nullptr;
		}
		C->bAutoActivate = false;
		C->SetupAttachment(Owner.GetRootComponent());
		if (!SetAsset(C, Asset))
		{
			C->MarkAsGarbage();
			return nullptr;
		}
		C->RegisterComponent();
		return C;
	}
}

double EcoV3WeatherFx::NiagaraUserFloat(UObject* Component, const TCHAR* Name)
{
	if (!Component || Component->GetClass()->GetPathName() != EcoV3WeatherFx::kNiagaraComponentClass)
	{
		return -1.0;
	}
	return EcoV3WeatherFxImpl::GetVariableFloat(Component, Name);
}

// -----------------------------------------------------------------------------
// 서브시스템
// -----------------------------------------------------------------------------

bool UEcoV3WeatherPresenterSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UEcoV3WeatherPresenterSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	// Dedicated는 그리지 않는다. opt-in BP 맵의 Client는 수신 Environment만 소비한다.
	if (!FApp::CanEverRender() || InWorld.GetNetMode() == NM_DedicatedServer || !InWorld.PersistentLevel)
	{
		return;
	}
	for (TActorIterator<AEcoCreatureIntegrationSpawner> It(&InWorld); It; ++It)
		bEcologyWeatherView = bEcologyWeatherView || (It->bUseV3Policy && It->bEnableVegetation);
	if (InWorld.GetNetMode() == NM_Client && !bEcologyWeatherView) return;
	if (!UEcoPolicyV3IntegratedSubsystem::IsRequested())
	{
		bool bCoordinator = false;
		for (TActorIterator<AEcoCreatureIntegrationSpawner> It(&InWorld); It; ++It)
		{
			bCoordinator = bCoordinator || It->bUseV3Policy;
		}
		if (!bCoordinator)
		{
			return;   // 통합 v3 모드가 아닌 맵 (팀 날씨 시험 레벨 등 — 팀 블루프린트가 그대로 돈다)
		}
	}
	TickFn.Owner = this;
	TickFn.bCanEverTick = true;
	TickFn.bStartWithTickEnabled = true;
	TickFn.bTickEvenWhenPaused = false;
	TickFn.TickGroup = TG_PostUpdateWork;   // 카메라 갱신(UWorld::Tick 의 UpdateCameraManager) 뒤 — 이번 프레임 카메라 자리
	TickFn.EndTickGroup = TG_PostUpdateWork;
	TickFn.RegisterTickFunction(InWorld.PersistentLevel);
	bTickRegistered = true;
}

void UEcoV3WeatherPresenterSubsystem::Deinitialize()
{
	if (bTickRegistered)
	{
		TickFn.UnRegisterTickFunction();
		bTickRegistered = false;
	}
	if (Fx)
	{
		if (Fx->RainSound)
		{
			Fx->RainSound->Stop();
		}
		Fx->Destroy();
	}
	Fx = nullptr;
	bReady = false;
	Super::Deinitialize();
}

FName UEcoV3WeatherPresenterSubsystem::RegionAt(const FVector& P)
{
	UWorld* World = GetWorld();
	if (!bRegionsGathered && World)
	{
		for (TActorIterator<AEcologyRegion> It(World); It; ++It)
		{
			Regions.Add(*It);
		}
		Regions.Sort([](const TWeakObjectPtr<AEcologyRegion>& A, const TWeakObjectPtr<AEcologyRegion>& B)
					 { return A.IsValid() && B.IsValid() && A->RegionId.LexicalLess(B->RegionId); });
		bRegionsGathered = true;
		FString Boxes;
		for (const TWeakObjectPtr<AEcologyRegion>& R : Regions)
		{
			if (const AEcologyRegion* Reg = R.Get(); Reg && Reg->RegionBounds)
			{
				const FTransform& X = Reg->RegionBounds->GetComponentTransform();
				const FVector E = Reg->RegionBounds->GetUnscaledBoxExtent() * X.GetScale3D();
				Boxes += FString::Printf(TEXT(" %s 중심 (%.0f, %.0f) m 반폭 (%.0f, %.0f) m 방위 %.0f°"), *Reg->RegionId.ToString(), X.GetLocation().X / 100.0,
										 X.GetLocation().Y / 100.0, E.X / 100.0, E.Y / 100.0, X.Rotator().Yaw);
			}
		}
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 날씨 연출 지역 상자 (가로만 본다):%s"), Boxes.IsEmpty() ? TEXT(" 없음") : *Boxes);
	}
	for (const TWeakObjectPtr<AEcologyRegion>& R : Regions)
	{
		const AEcologyRegion* Reg = R.Get();
		if (Reg && Reg->RegionBounds && EcoV3WeatherFx::ContainsXY(Reg->RegionBounds->GetComponentTransform(), Reg->RegionBounds->GetUnscaledBoxExtent(), P))
		{
			return Reg->RegionId;
		}
	}
	return NAME_None;
}

bool UEcoV3WeatherPresenterSubsystem::EnsureFx()
{
	if (bTried)
	{
		return bReady;
	}
	bTried = true;
	UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}
	UClass* NiagaraClass = FindObject<UClass>(nullptr, EcoV3WeatherFx::kNiagaraComponentClass);
	if (!NiagaraClass)
	{
		NiagaraClass = LoadObject<UClass>(nullptr, EcoV3WeatherFx::kNiagaraComponentClass);
	}
	RainAsset = LoadObject<UFXSystemAsset>(nullptr, EcoV3WeatherFx::kRainSystemPath);
	SnowAsset = LoadObject<UFXSystemAsset>(nullptr, EcoV3WeatherFx::kSnowSystemPath);
	RainCue = LoadObject<USoundBase>(nullptr, EcoV3WeatherFx::kRainSoundPath);
	FActorSpawnParameters Params;
	Params.Name = MakeUniqueObjectName(World->PersistentLevel, AEcoV3WeatherFxActor::StaticClass(), TEXT("EcoV3WeatherFx"));
	Params.ObjectFlags |= RF_Transient;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Fx = World->SpawnActor<AEcoV3WeatherFxActor>(AEcoV3WeatherFxActor::StaticClass(), FTransform::Identity, Params);
	if (!Fx)
	{
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 날씨 연출: 연출 액터를 못 만들었다 — 비·눈이 보이지 않는다 (규칙은 그대로)"));
		return false;
	}
	Fx->Rain = EcoV3WeatherFxImpl::MakeNiagara(*Fx, NiagaraClass, RainAsset, TEXT("RainSystem"));
	Fx->Snow = EcoV3WeatherFxImpl::MakeNiagara(*Fx, NiagaraClass, SnowAsset, TEXT("SnowSystem"));
	if (RainCue)
	{
		UAudioComponent* A = NewObject<UAudioComponent>(Fx, TEXT("RainSound"), RF_Transient);
		A->bAutoActivate = false;
		A->bAutoDestroy = false;
		A->SetupAttachment(Fx->GetRootComponent());
		A->SetSound(RainCue);
		A->RegisterComponent();
		Fx->RainSound = A;
	}
	const double RainDefaultRate = Fx->Rain ? EcoV3WeatherFxImpl::GetVariableFloat(Fx->Rain, EcoV3WeatherFx::kSpawnRateName) : -1.0;
	bRainRateParam = RainDefaultRate >= 0.0;
	bReady = Fx->Rain != nullptr || Fx->Snow != nullptr;
	UE_LOG(LogEcoPolicyV3I, Log,
		   TEXT("[EcoV3I] 날씨 연출 준비 (eco.IntegratedV3.WeatherVisuals 1): 나이아가라 컴포넌트 클래스 %s | 비 %s (User.SpawnRate %s) · 빗소리 %s · 눈 %s | ")
			   TEXT("카메라 곁에 켬, 들어가면 %.1f 초 동안 세지고 나오면 %.1f 초 동안 약해진 뒤 끔 (빗소리 멈춤)"),
		   NiagaraClass ? TEXT("있음") : TEXT("없음 (Niagara 플러그인)"), RainAsset ? EcoV3WeatherFx::kRainSystemPath : TEXT("애셋 없음"),
		   bRainRateParam ? *FString::Printf(TEXT("애셋 기본 %.1f → 세기 1 에 %.0f (팀 블루프린트 값) × 세기 × 페이드"), RainDefaultRate, EcoV3WeatherFx::kRainSpawnRateFull)
						  : TEXT("칸 없음 — 켬·끔만"),
		   RainCue ? EcoV3WeatherFx::kRainSoundPath : TEXT("애셋 없음"), SnowAsset ? EcoV3WeatherFx::kSnowSystemPath : TEXT("애셋 없음"),
		   EcoV3WeatherFx::kFadeInSeconds, EcoV3WeatherFx::kFadeOutSeconds);
	if (!bReady)
	{
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 날씨 연출: 비·눈 나이아가라를 하나도 못 만들었다 — 비·눈이 보이지 않는다 (규칙은 그대로)"));
	}
	return bReady;
}

void UEcoV3WeatherPresenterSubsystem::Apply(double RainTarget, double SnowTarget, double DeltaSeconds)
{
	AEcoV3WeatherFxActor& A = *Fx;
	A.RainAlpha = EcoV3WeatherFx::Approach(A.RainAlpha, RainTarget, DeltaSeconds);
	A.SnowAlpha = EcoV3WeatherFx::Approach(A.SnowAlpha, SnowTarget, DeltaSeconds);
	// 비: 세기·페이드 = 빗줄기 수(User.SpawnRate 기본 × 세기)·빗소리 음량. 0 이 되면 끄고 소리를 멈춘다 (음량 0 으로 남기지 않는다)
	if (A.Rain)
	{
		const bool bWant = A.RainAlpha > 0.0;
		if (bWant && !A.bRainOn)
		{
			A.Rain->Activate(true);
			A.bRainOn = true;
		}
		else if (!bWant && A.bRainOn)
		{
			A.Rain->Deactivate();
			A.bRainOn = false;
		}
		if (A.bRainOn && bRainRateParam)
		{
			A.RainSpawnRate = EcoV3WeatherFx::kRainSpawnRateFull * RainDensity * A.RainAlpha;
			A.Rain->SetFloatParameter(FName(EcoV3WeatherFx::kSpawnRateName), static_cast<float>(A.RainSpawnRate));
		}
	}
	if (A.RainSound)
	{
		const bool bWant = A.RainAlpha > 0.0;
		if (bWant && !A.bRainSoundOn)
		{
			A.RainSound->Play();
			A.bRainSoundOn = true;
		}
		else if (!bWant && A.bRainSoundOn)
		{
			A.RainSound->Stop();
			A.bRainSoundOn = false;
		}
		if (A.bRainSoundOn)
		{
			A.RainSound->SetVolumeMultiplier(static_cast<float>(A.RainAlpha));
		}
	}
	// 눈: 애셋에 세기 칸이 없어 목표가 있으면 곧바로 켜고, 목표가 0 이 되는 순간 새 눈송이를 멈춘다 (떠 있는 눈송이는 마저 내린다)
	if (A.Snow)
	{
		const bool bWant = SnowTarget > 0.0;
		if (bWant && !A.bSnowOn)
		{
			A.Snow->Activate(true);
			A.bSnowOn = true;
		}
		else if (!bWant && A.bSnowOn)
		{
			A.Snow->Deactivate();
			A.bSnowOn = false;
		}
	}
}

void UEcoV3WeatherPresenterSubsystem::FadeAll(double DeltaSeconds)
{
	if (Fx && bReady)
	{
		Apply(0.0, 0.0, DeltaSeconds);
	}
}

void UEcoV3WeatherPresenterSubsystem::TickPresenter(float DeltaSeconds)
{
	UWorld* World = GetWorld();
	UEcoPolicyV3IntegratedSubsystem* Sub = World && !bEcologyWeatherView ? World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
	const double DeltaS = static_cast<double>(DeltaSeconds);
	RainDensity = Sub ? Sub->GetSettings().WeatherRainDensity : 1.0;
	// The received-summary view has no native subsystem, but still honors local
	// presentation controls. Disabling visuals must not disable authoritative rain.
	static const auto* VisualsCVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.IntegratedV3.WeatherVisuals"));
	static const auto* DensityCVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.IntegratedV3.WeatherRainDensity"));
	if (bEcologyWeatherView && DensityCVar)
	{
		const double Density = DensityCVar->GetFloat();
		RainDensity = FMath::IsFinite(Density) ? FMath::Clamp(Density, .1, 10.0) : 1.0;
	}
	if (!World || (bEcologyWeatherView && VisualsCVar && VisualsCVar->GetInt() == 0)
		|| (!bEcologyWeatherView && (!Sub || !Sub->IsActive() || Sub->NumContexts() == 0 || !Sub->GetSettings().bWeather || !Sub->GetSettings().bWeatherVisuals)))
	{
		FadeAll(DeltaS);   // 꺼짐·아직 무대 전: 만들지 않는다 (켜져 있던 것은 끈다)
		return;
	}
	APlayerController* PC = World->GetFirstPlayerController();
	if (!PC || !PC->PlayerCameraManager)
	{
		FadeAll(DeltaS);
		return;
	}
	const FVector Cam = PC->PlayerCameraManager->GetCameraLocation();
	const FRotator CamRot = PC->PlayerCameraManager->GetCameraRotation();
	const FName Region = RegionAt(Cam);
	int32 Kind = EcoWorldV3::kWeatherClear;
	double Intensity = 0.0;
	if (bEcologyWeatherView)
	{
		if (const auto* State = World->GetGameState<AEcoGameState>())
			for (const auto& Summary : State->GetEcologySummary().Regions)
				if (Summary.RegionId == Region && Summary.Environment.Rainfall > 0
					&& (Summary.Environment.WeatherState == EEcoWeatherState::Rain || Summary.Environment.WeatherState == EEcoWeatherState::Storm))
				{ Kind = EcoWorldV3::kWeatherRain; Intensity = Summary.Environment.Rainfall; break; }
	}
	else if (const FEcoV3RegionContext* Ctx = Region.IsNone() ? nullptr : Sub->FindContext(Region))
	{
		if (Ctx->Sim.Config.Weather.bEnabled)
		{
			Kind = Ctx->Sim.WeatherKind;
			Intensity = Ctx->Sim.WeatherIntensity;
		}
	}
	double RainTarget = 0.0, SnowTarget = 0.0;
	EcoV3WeatherFx::Targets(Kind, Intensity, RainTarget, SnowTarget);
	if (Region != LastRegion || Kind != LastKind || Intensity != LastIntensity)
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 날씨 연출 | %.2f초 | 카메라 지역 %s → %s %.2f (카메라 %.0f, %.0f, %.0f m)"), World->GetTimeSeconds(),
			   Region.IsNone() ? TEXT("없음") : *Region.ToString(), UTF8_TO_TCHAR(EcoWorldV3::WeatherNameKoUtf8(Kind)), Intensity, Cam.X / 100.0, Cam.Y / 100.0,
			   Cam.Z / 100.0);
		LastRegion = Region;
		LastKind = Kind;
		LastIntensity = Intensity;
	}
	const bool bAny = RainTarget > 0.0 || SnowTarget > 0.0 || (Fx && (Fx->RainAlpha > 0.0 || Fx->SnowAlpha > 0.0 || Fx->bRainOn || Fx->bSnowOn));
	if (!bAny || !EnsureFx())
	{
		return;
	}
	++Frames;
	Fx->CameraRegion = Region;
	Fx->CameraWeather = Kind;
	Fx->CameraIntensity = Intensity;
	Fx->SetActorLocationAndRotation(Cam, FRotator(0.0, CamRot.Yaw, 0.0));   // 보는 사람 둘레 (팀 블루프린트는 폰 자리 — README 4절 1)
	Apply(RainTarget, SnowTarget, DeltaS);
}
