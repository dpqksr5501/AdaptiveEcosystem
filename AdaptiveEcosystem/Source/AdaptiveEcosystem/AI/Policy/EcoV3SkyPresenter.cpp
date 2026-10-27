#include "EcoV3SkyPresenter.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "UObject/Class.h"
#include "UObject/UnrealType.h"

#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Network/EcoGameState.h"
#include "World/EcoWorldClockSubsystem.h"

#include "EcoPolicyV3IntegratedSubsystem.h"

// 단일 번역 단위 빌드(unity)에서 다른 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoV3SkyImpl
{
	static TAutoConsoleVariable<int32> CVarSkyLink(
		TEXT("eco.Sky.Link"), 1,
		TEXT("하늘 연출 (EcoV3SkyPresenter.h — 해·달이 팀 시계 낮 60 초·밤 60 초를 따라 돈다): 0 = 끔 (켜져 있었으면 해·달·하늘빛·팀 하늘 BP 칸을 처음 값으로 되돌린다), ")
			TEXT("1 = 통합 v3 모드 월드에서 켬 (기본 — 팀 기본 v1 월드는 그대로), 2 = 팀 시계가 도는 모든 게임 월드에서 켬 (팀 v1 확인용, 고른 사람만). ")
			TEXT("보기만 바꾼다 — 규칙·관측·팀 시계에 쓰지 않는다. 실행 중에 바꿔도 된다."),
		ECVF_Default);
	static TAutoConsoleVariable<float> CVarSkyNightBrightness(
		TEXT("eco.Sky.NightBrightness"), static_cast<float>(EcoV3Sky::kDefaultNightLux),
		TEXT("하늘 연출: 한밤 달빛 세기 (lux, 기본 1 = 팀 해 8 lux 의 1/8). 팀 달빛 0.01 lux 는 거의 깜깜해 늑대·사슴이 안 보인다. ")
			TEXT("어스름(v3 d 0.5 → 1, 해가 지고 6 초) 동안 팀 값에서 이 값으로 올라가고 새벽에 내려간다. 팀 값보다 어둡게 하지는 않는다. 실행 중에 바꿔도 된다."),
		ECVF_Default);
	static TAutoConsoleVariable<float> CVarSkyMoonTint(
		TEXT("eco.Sky.MoonTint"), static_cast<float>(EcoV3Sky::kDefaultMoonTint),
		TEXT("하늘 연출: 밤 달빛 색을 팀 색(노랑 255,242,77)에서 차가운 달빛(0.55, 0.65, 1.0 선형)으로 섞는 몫 (0~1, 기본 1 — 자동 노출이 한밤을 낮 밝기로 ")
			TEXT("맞춰 팀 노랑이면 노란 낮처럼 보인다. 0 = 팀 색 그대로)."),
		ECVF_Default);
	static TAutoConsoleVariable<float> CVarSkyNightSkyLight(
		TEXT("eco.Sky.NightSkyLight"), 1.0f,
		TEXT("하늘 연출: 한밤 하늘빛(SkyLight) 세기 배수 (기본 1 = 팀 값 그대로). 그늘이 너무 검으면 올린다 (낮에는 늘 팀 값)."),
		ECVF_Default);
	static TAutoConsoleVariable<float> CVarSkyLogSeconds(
		TEXT("eco.Sky.LogSeconds"), static_cast<float>(EcoV3Sky::kLogEverySecondsDefault),
		TEXT("하늘 연출 기록 [EcoV3I] 하늘 줄 간격 (팀 시계 초, 기본 10 — 0 이면 켬·끔·낮밤 바뀜 때만). 서버·단독 통합 v3 는 v3 지역 세계의 어둠 d 도 같이 적는다."),
		ECVF_Default);

	double Finite(double V, double Fallback)
	{
		return FMath::IsFinite(V) ? V : Fallback;
	}

	/** 액터(방향광·아무 액터)나 컴포넌트 → 방향광 컴포넌트. */
	UDirectionalLightComponent* LightOf(UObject* Obj)
	{
		if (UDirectionalLightComponent* C = Cast<UDirectionalLightComponent>(Obj))
		{
			return C;
		}
		if (const ADirectionalLight* L = Cast<ADirectionalLight>(Obj))
		{
			return L->GetComponent();
		}
		if (const AActor* A = Cast<AActor>(Obj))
		{
			return A->FindComponentByClass<UDirectionalLightComponent>();
		}
		return nullptr;
	}

	/** 블루프린트 칸 (반사로 이름 찾기 — 팀 BP 를 고치지 않고 읽는다). */
	UObject* ObjectProp(UObject* Container, const TCHAR* Name)
	{
		const FObjectPropertyBase* P = Container ? FindFProperty<FObjectPropertyBase>(Container->GetClass(), FName(Name)) : nullptr;
		return P ? P->GetObjectPropertyValue_InContainer(Container) : nullptr;
	}

	FStructProperty* RotatorProp(const UClass* Class, const TCHAR* Name)
	{
		FStructProperty* P = Class ? FindFProperty<FStructProperty>(Class, FName(Name)) : nullptr;
		return P && P->Struct == TBaseStructure<FRotator>::Get() ? P : nullptr;
	}

	double FloatProp(UObject* Container, const TCHAR* Name, double Fallback)
	{
		const FNumericProperty* N = Container ? FindFProperty<FNumericProperty>(Container->GetClass(), FName(Name)) : nullptr;
		return N && N->IsFloatingPoint() ? N->GetFloatingPointPropertyValue(N->ContainerPtrToValuePtr<void>(Container)) : Fallback;
	}

	/** 팀 BP 처럼 액터 회전으로 (빛이 뿌리 컴포넌트일 때), 아니면 컴포넌트 회전. */
	void SetRotation(UDirectionalLightComponent* C, const FRotator& R)
	{
		AActor* Owner = C ? C->GetOwner() : nullptr;
		if (Owner && Owner->GetRootComponent() == C)
		{
			Owner->SetActorRotation(R, ETeleportType::None);
		}
		else if (C)
		{
			C->SetWorldRotation(R);
		}
	}

	/** 빛이 나아가는 방위 (도) — roll 이 180 이어도 앞 방향으로 잰다. */
	double ForwardYaw(const FRotator& R)
	{
		const FVector F = R.Vector();
		return F.X * F.X + F.Y * F.Y > 1e-6 ? FMath::RadiansToDegrees(FMath::Atan2(F.Y, F.X)) : R.Yaw;
	}

	bool Movable(const UDirectionalLightComponent* C)
	{
		return C && C->Mobility != EComponentMobility::Static;
	}

	void Fill(EcoV3Sky::FClockSample& Out, const FEcoServerTimeSnapshot& T)
	{
		Out.Epoch = T.WorldEpoch;
		Out.ServerSeconds = T.ServerTimeSeconds;
		Out.bDay = T.DayCycle.Phase == EEcoDayPhase::Day;
		Out.PhaseStart = T.DayCycle.PhaseStartSeconds;
		Out.PhaseEnd = T.DayCycle.PhaseEndSeconds;
	}

	FString LightName(const UDirectionalLightComponent* C)
	{
		return C ? GetNameSafe(C->GetOwner()) : FString(TEXT("없음"));
	}
}

// -----------------------------------------------------------------------------
// 순수 함수 (시험 AdaptiveEcosystem.Policy.V3.Sky.*)
// -----------------------------------------------------------------------------

FLinearColor EcoV3Sky::CoolMoonColor()
{
	return FLinearColor(0.55f, 0.65f, 1.0f, 1.0f);
}

double EcoV3Sky::SunPitchDeg(bool bDay, double Progress)
{
	const double P = FMath::IsFinite(Progress) ? FMath::Clamp(Progress, 0.0, 1.0) : 0.0;
	double Pitch = FMath::Fmod((bDay ? 180.0 : 360.0) + 180.0 * P, 360.0);
	if (Pitch < 0.0)
	{
		Pitch += 360.0;
	}
	return Pitch;
}

double EcoV3Sky::SunElevationDeg(double PitchDeg)
{
	if (!FMath::IsFinite(PitchDeg))
	{
		return 0.0;
	}
	const double S = FMath::Clamp(-FMath::Sin(FMath::DegreesToRadians(PitchDeg)), -1.0, 1.0);
	return FMath::RadiansToDegrees(FMath::Asin(S));
}

double EcoV3Sky::Darkness(double ElevationDeg)
{
	return FMath::IsFinite(ElevationDeg) ? FMath::Clamp(0.5 - ElevationDeg / (2.0 * kTwilightDeg), 0.0, 1.0) : 0.0;
}

double EcoV3Sky::NightFactor(double Dark)
{
	if (!FMath::IsFinite(Dark))
	{
		return 0.0;
	}
	const double X = FMath::Clamp(2.0 * Dark - 1.0, 0.0, 1.0);
	return X * X * (3.0 - 2.0 * X);
}

double EcoV3Sky::SunIntensityScale(double ElevationDeg)
{
	if (!FMath::IsFinite(ElevationDeg) || ElevationDeg >= 0.0)
	{
		return 1.0;
	}
	const double X = FMath::Clamp(1.0 + ElevationDeg / kSunSetFadeDeg, 0.0, 1.0);
	return X * X * (3.0 - 2.0 * X);
}

FRotator EcoV3Sky::SunRotation(double PitchDeg, double YawDeg)
{
	return FRotator(PitchDeg, YawDeg, 0.0);
}

FRotator EcoV3Sky::MoonRotation(const FRotator& Sun)
{
	return FRotator(Sun.Pitch + 180.0, Sun.Yaw, Sun.Roll);
}

EcoV3Sky::FPose EcoV3Sky::ComputePose(bool bDay, double Progress, const FLook& Look)
{
	using EcoV3SkyImpl::Finite;
	FPose O;
	O.SunPitchDeg = SunPitchDeg(bDay, Progress);
	O.SunElevationDeg = SunElevationDeg(O.SunPitchDeg);
	O.Dark = Darkness(O.SunElevationDeg);
	O.Night = NightFactor(O.Dark);
	O.Sun = SunRotation(O.SunPitchDeg, Finite(Look.SunYawDeg, 0.0));
	O.Moon = MoonRotation(O.Sun);

	const double TeamSun = FMath::Max(0.0, Finite(Look.TeamSunIntensity, 0.0));
	O.SunIntensity = static_cast<float>(TeamSun * SunIntensityScale(O.SunElevationDeg));

	// 달: 팀 값 → 밤 달빛 (팀 값보다 어둡게 하지 않는다). Night = 0 이면 팀 값 그대로 (Lerp 의 A + 0·(B − A))
	const double TeamMoon = FMath::Max(0.0, Finite(Look.TeamMoonIntensity, 0.0));
	const double NightLux = FMath::Max(TeamMoon, FMath::Clamp(Finite(Look.NightLux, kDefaultNightLux), 0.0, 1000.0));
	O.MoonIntensity = static_cast<float>(TeamMoon + O.Night * (NightLux - TeamMoon));
	const double Tint = FMath::Clamp(Finite(Look.MoonTint, 0.0), 0.0, 1.0) * O.Night;
	O.MoonTintWeight = static_cast<float>(Tint);
	O.MoonColor = Tint > 0.0 ? Look.TeamMoonColor + (CoolMoonColor() - Look.TeamMoonColor) * static_cast<float>(Tint) : Look.TeamMoonColor;

	const double SkyMult = FMath::Clamp(Finite(Look.NightSkyLight, 1.0), 0.0, 100.0);
	const double TeamSky = FMath::Max(0.0, Finite(Look.TeamSkyIntensity, 0.0));
	O.SkyIntensity = static_cast<float>(TeamSky * (1.0 + O.Night * (SkyMult - 1.0)));
	return O;
}

bool EcoV3Sky::PhaseAt(const FClockSample& Sample, double T, double OtherPhaseSeconds, bool& bOutDay, double& OutProgress)
{
	const double Len = Sample.PhaseEnd - Sample.PhaseStart;
	if (!FMath::IsFinite(T) || !FMath::IsFinite(Sample.PhaseStart) || !FMath::IsFinite(Len) || !(Len > 0.0))
	{
		return false;
	}
	const double OtherLen = FMath::IsFinite(OtherPhaseSeconds) && OtherPhaseSeconds > 0.0 ? OtherPhaseSeconds : Len;
	const double Cycle = Len + OtherLen;
	double Off = FMath::Fmod(T - Sample.PhaseStart, Cycle);
	if (Off < 0.0)
	{
		Off += Cycle;
	}
	if (!(Off < Cycle))
	{
		Off = 0.0;   // 반올림으로 한 바퀴가 된 경우
	}
	if (Off < Len)
	{
		bOutDay = Sample.bDay;
		OutProgress = Off / Len;
	}
	else
	{
		bOutDay = !Sample.bDay;
		OutProgress = (Off - Len) / OtherLen;
	}
	OutProgress = FMath::Clamp(OutProgress, 0.0, 1.0);
	return true;
}

void EcoV3Sky::StepClock(FDisplayClock& Clock, double DeltaSeconds, const FClockSample* NewSample, double BlendSeconds, double SnapSeconds)
{
	const double Dt = FMath::IsFinite(DeltaSeconds) && DeltaSeconds > 0.0 ? DeltaSeconds : 0.0;
	if (Clock.bHas)
	{
		Clock.Shown += Dt;
	}
	if (NewSample && FMath::IsFinite(NewSample->ServerSeconds) && FMath::IsFinite(NewSample->PhaseStart)
		&& FMath::IsFinite(NewSample->PhaseEnd) && NewSample->PhaseEnd > NewSample->PhaseStart)
	{
		(NewSample->bDay ? Clock.DaySeconds : Clock.NightSeconds) = NewSample->PhaseEnd - NewSample->PhaseStart;
		const double Err = NewSample->ServerSeconds - Clock.Shown;
		if (!Clock.bHas || NewSample->Epoch != Clock.Last.Epoch || !(FMath::Abs(Err) <= SnapSeconds))
		{
			Clock.Shown = NewSample->ServerSeconds;
			Clock.Pending = 0.0;
			Clock.bHas = true;
			++Clock.Snaps;
		}
		else
		{
			Clock.Pending = Err;
		}
		Clock.Last = *NewSample;
	}
	if (Clock.bHas && Clock.Pending != 0.0)
	{
		const double A = BlendSeconds > 0.0 ? FMath::Min(1.0, Dt / BlendSeconds) : 1.0;
		const double Move = Clock.Pending * A;
		Clock.Shown += Move;
		Clock.Pending -= Move;
	}
}

bool EcoV3Sky::ClockPhase(const FDisplayClock& Clock, bool& bOutDay, double& OutProgress)
{
	if (!Clock.bHas)
	{
		return false;
	}
	const double Other = Clock.Last.bDay ? Clock.NightSeconds : Clock.DaySeconds;
	return PhaseAt(Clock.Last, Clock.Shown, Other, bOutDay, OutProgress);
}

// -----------------------------------------------------------------------------
// 레벨의 하늘 빛
// -----------------------------------------------------------------------------

bool EcoV3Sky::FSkyRig::Capture(UWorld& World)
{
	using namespace EcoV3SkyImpl;
	*this = FSkyRig();

	// 1. 팀 하늘 BP: SunCurrentRotation(FRotator) 과 Sun 칸이 있는 블루프린트 액터 (이름 순 첫째). 클래스마다 한 번만 칸을 찾는다
	AActor* Manager = nullptr;
	FStructProperty* RotProp = nullptr;
	TMap<const UClass*, FStructProperty*> Checked;
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		AActor* A = *It;
		const UClass* Class = ::IsValid(A) ? A->GetClass() : nullptr;
		if (!Class || Class->HasAnyClassFlags(CLASS_Native))
		{
			continue;
		}
		FStructProperty** Found = Checked.Find(Class);
		if (!Found)
		{
			FStructProperty* P = RotatorProp(Class, TEXT("SunCurrentRotation"));
			Found = &Checked.Add(Class, P && FindFProperty<FObjectPropertyBase>(Class, FName(TEXT("Sun"))) ? P : nullptr);
		}
		if (*Found && (!Manager || A->GetName() < Manager->GetName()))
		{
			Manager = A;
			RotProp = *Found;
		}
	}
	UDirectionalLightComponent* SunC = Manager ? LightOf(ObjectProp(Manager, TEXT("Sun"))) : nullptr;
	UDirectionalLightComponent* MoonC = Manager ? LightOf(ObjectProp(Manager, TEXT("Moon"))) : nullptr;

	// 2. BP 가 없거나 칸이 비었으면 대기 빛 색인 0(해)·1(달) 중 가장 밝은 것, 대기 빛이 없으면 가장 밝은 방향광을 해로
	if (!SunC || !MoonC)
	{
		UDirectionalLightComponent* Best[2] = {nullptr, nullptr};
		UDirectionalLightComponent* Brightest = nullptr;
		for (TActorIterator<ADirectionalLight> It(&World); It; ++It)
		{
			UDirectionalLightComponent* C = ::IsValid(*It) ? It->GetComponent() : nullptr;
			if (!C || C == SunC || C == MoonC)
			{
				continue;
			}
			if (!Brightest || C->Intensity > Brightest->Intensity)
			{
				Brightest = C;
			}
			if (C->IsUsedAsAtmosphereSunLight())
			{
				const int32 Index = static_cast<int32>(C->GetAtmosphereSunLightIndex());
				if ((Index == 0 || Index == 1) && (!Best[Index] || C->Intensity > Best[Index]->Intensity))
				{
					Best[Index] = C;
				}
			}
		}
		if (!SunC)
		{
			SunC = Best[0] ? Best[0] : (Brightest != Best[1] ? Brightest : nullptr);
		}
		if (!MoonC && Best[1] && Best[1] != SunC)
		{
			MoonC = Best[1];
		}
	}
	if (MoonC == SunC)
	{
		MoonC = nullptr;
	}
	if (!Movable(SunC))
	{
		return false;   // 해가 없거나 Static — 아무것도 바꾸지 않는다
	}
	if (!Movable(MoonC))
	{
		MoonC = nullptr;   // 움직일 수 없는 달은 손대지 않는다
	}
	USkyLightComponent* SkyC = nullptr;
	for (TActorIterator<ASkyLight> It(&World); It && !SkyC; ++It)
	{
		SkyC = ::IsValid(*It) ? It->GetLightComponent() : nullptr;
	}

	if (Manager && RotProp)
	{
		SkyManager = Manager;
		SunRotationProp = RotProp;
		OriginalBPRotation = *RotProp->ContainerPtrToValuePtr<FRotator>(Manager);
		BPSunSpeed = FloatProp(Manager, TEXT("SunSpeed"), 0.0);
	}
	Sun = SunC;
	OriginalSunRotation = SunC->GetComponentRotation();
	OriginalSunIntensity = SunC->Intensity;
	if (MoonC)
	{
		Moon = MoonC;
		OriginalMoonRotation = MoonC->GetComponentRotation();
		OriginalMoonIntensity = MoonC->Intensity;
		OriginalMoonColor = MoonC->LightColor;
	}
	if (SkyC)
	{
		Sky = SkyC;
		OriginalSkyIntensity = SkyC->Intensity;
	}
	// 해 길 방위: 팀 BP Tick 은 SunCurrentRotation 의 yaw·roll 을 0 으로 넣으므로 BP 가 있으면 0, 없으면 해 방향광이 놓인 방위 (그 자리가 길 위에 온다)
	SunYawDeg = SkyManager.IsValid() ? 0.0 : ForwardYaw(OriginalSunRotation);
	bCaptured = true;
	return true;
}

bool EcoV3Sky::FSkyRig::IsAlive() const
{
	return bCaptured && Sun.IsValid() && !Moon.IsStale() && !Sky.IsStale() && !SkyManager.IsStale();
}

EcoV3Sky::FLook EcoV3Sky::FSkyRig::BaseLook() const
{
	FLook L;
	L.TeamSunIntensity = OriginalSunIntensity;
	L.TeamMoonIntensity = OriginalMoonIntensity;
	L.TeamMoonColor = FLinearColor(OriginalMoonColor);
	L.TeamSkyIntensity = OriginalSkyIntensity;
	L.SunYawDeg = SunYawDeg;
	return L;
}

void EcoV3Sky::FSkyRig::Apply(const FPose& Pose)
{
	using namespace EcoV3SkyImpl;
	if (!bCaptured)
	{
		return;
	}
	// 팀 BP 칸: BP Tick 이 다음 프레임에 이 값(+ SunSpeed·dt, 지금 0)을 해에 넣고 달 = 해 + 180° 로 돌린다 — 우리와 같은 값이라 다투지 않는다
	if (AActor* M = SkyManager.Get(); M && SunRotationProp)
	{
		*SunRotationProp->ContainerPtrToValuePtr<FRotator>(M) = FRotator(Pose.SunPitchDeg, 0.0, 0.0);
	}
	if (UDirectionalLightComponent* S = Sun.Get())
	{
		SetRotation(S, Pose.Sun);
		S->SetIntensity(Pose.SunIntensity);
	}
	if (UDirectionalLightComponent* Mo = Moon.Get())
	{
		SetRotation(Mo, Pose.Moon);
		Mo->SetIntensity(Pose.MoonIntensity);
		if (Pose.MoonTintWeight > 0.0f)
		{
			Mo->SetLightColor(Pose.MoonColor);
		}
		else if (Mo->LightColor != OriginalMoonColor)
		{
			Mo->SetLightFColor(OriginalMoonColor);   // 섞지 않으면 팀 색을 바이트 그대로
		}
	}
	if (USkyLightComponent* K = Sky.Get())
	{
		K->SetIntensity(Pose.SkyIntensity);
	}
}

void EcoV3Sky::FSkyRig::Restore()
{
	using namespace EcoV3SkyImpl;
	if (bCaptured)
	{
		if (AActor* M = SkyManager.Get(); M && SunRotationProp)
		{
			*SunRotationProp->ContainerPtrToValuePtr<FRotator>(M) = OriginalBPRotation;
		}
		if (UDirectionalLightComponent* S = Sun.Get())
		{
			SetRotation(S, OriginalSunRotation);
			S->SetIntensity(OriginalSunIntensity);
		}
		if (UDirectionalLightComponent* Mo = Moon.Get())
		{
			SetRotation(Mo, OriginalMoonRotation);
			Mo->SetIntensity(OriginalMoonIntensity);
			Mo->SetLightFColor(OriginalMoonColor);
		}
		if (USkyLightComponent* K = Sky.Get())
		{
			K->SetIntensity(OriginalSkyIntensity);
		}
	}
	*this = FSkyRig();
}

// -----------------------------------------------------------------------------
// 서브시스템
// -----------------------------------------------------------------------------

void FEcoV3SkyTickFunction::ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread,
										const FGraphEventRef& MyCompletionGraphEvent)
{
	if (UEcoV3SkyPresenterSubsystem* Sub = Owner.Get())
	{
		Sub->TickPresenter(DeltaTime);
	}
}

bool UEcoV3SkyPresenterSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UEcoV3SkyPresenterSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	// 데디케이티드 서버는 보이는 화면이 없다. 리슨 서버·단독·클라이언트는 돈다 (NullRHI 헤드리스도 — 빛만 돌린다)
	if (InWorld.GetNetMode() == NM_DedicatedServer || !InWorld.PersistentLevel)
	{
		return;
	}
	for (TActorIterator<AEcoCreatureIntegrationSpawner> It(&InWorld); It; ++It)
	{
		bSpawnerV3 = bSpawnerV3 || It->bUseV3Policy;
	}
	// 월드마다 늘 등록한다 (eco.Sky.Link 를 실행 중에 바꿀 수 있게) — 꺼진 월드에서는 콘솔 값 하나만 읽고 돌아간다
	TickFn.Owner = this;
	TickFn.bCanEverTick = true;
	TickFn.bStartWithTickEnabled = true;
	TickFn.bTickEvenWhenPaused = false;
	TickFn.TickGroup = TG_PostUpdateWork;   // 팀 하늘 BP Tick(TG_PrePhysics) 뒤 — 이번 프레임 해·달은 우리 값
	TickFn.EndTickGroup = TG_PostUpdateWork;
	TickFn.RegisterTickFunction(InWorld.PersistentLevel);
	bTickRegistered = true;
}

void UEcoV3SkyPresenterSubsystem::Deinitialize()
{
	if (bTickRegistered)
	{
		TickFn.UnRegisterTickFunction();
		bTickRegistered = false;
	}
	// 월드가 닫힌다 — 빛 액터도 같이 사라지므로 되돌리지 않고 손잡이만 놓는다
	Rig = EcoV3Sky::FSkyRig();
	bLinked = false;
	Super::Deinitialize();
}

bool UEcoV3SkyPresenterSubsystem::WantsLink(const UWorld& World) const
{
	const int32 Mode = EcoV3SkyImpl::CVarSkyLink.GetValueOnGameThread();
	if (Mode <= 0)
	{
		return false;
	}
	if (Mode >= 2)
	{
		return true;
	}
	// 1: 통합 v3 모드. 클라이언트에는 통합 서브시스템이 켜지지 않으므로(표현만) 요청 스위치·조정자 칸을 본다
	if (World.GetNetMode() == NM_Client)
	{
		return bSpawnerV3 || UEcoPolicyV3IntegratedSubsystem::IsRequested();
	}
	const UEcoPolicyV3IntegratedSubsystem* Sub = World.GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	return Sub && Sub->IsActive();
}

bool UEcoV3SkyPresenterSubsystem::ReadNewSample(const UWorld& World, EcoV3Sky::FClockSample& Out)
{
	// 서버·단독: 팀 시계 (권위 — 조정자가 매 프레임 월드 dt 로 앞으로 보낸다)
	if (World.GetNetMode() != NM_Client)
	{
		if (const UEcoWorldClockSubsystem* TeamClock = World.GetSubsystem<UEcoWorldClockSubsystem>(); TeamClock && TeamClock->IsClockRunning())
		{
			EcoV3SkyImpl::Fill(Out, TeamClock->GetServerTime());
			return !Clock.bHas || Out.ServerSeconds != Clock.Last.ServerSeconds || Out.Epoch != Clock.Last.Epoch;
		}
	}
	// 클라이언트 (또는 시계가 없는 권위 월드): GameState 요약 — 판이 바뀔 때만 복사한다
	const AEcoGameState* State = World.GetGameState<AEcoGameState>();
	if (!State || State->GetStateRevision() == LastRevision)
	{
		return false;
	}
	LastRevision = State->GetStateRevision();
	const FEcoCompletedWorldSummary Summary = State->GetEcologySummary();
	if (Summary.Time.WorldEpoch <= 0)
	{
		return false;
	}
	EcoV3SkyImpl::Fill(Out, Summary.Time);
	return !Clock.bHas || Out.ServerSeconds != Clock.Last.ServerSeconds || Out.Epoch != Clock.Last.Epoch;
}

bool UEcoV3SkyPresenterSubsystem::Link(UWorld& World)
{
	using namespace EcoV3SkyImpl;
	const double Now = World.GetRealTimeSeconds();
	if (Now < NextCaptureTry)
	{
		return false;
	}
	if (!Rig.Capture(World))
	{
		NextCaptureTry = Now + 1.0;
		if (!bToldNoSun)
		{
			bToldNoSun = true;
			UE_LOG(LogEcoPolicyV3I, Log,
				   TEXT("[EcoV3I] 하늘 연출: 움직일 수 있는 해 방향광을 못 찾았다 — 찾을 때까지 1 초마다 다시 본다 (하늘은 팀 그대로, 규칙은 그대로)"));
		}
		return false;
	}
	bLinked = true;
	bToldNoSun = false;
	const UDirectionalLightComponent* S = Rig.Sun.Get();
	const UDirectionalLightComponent* Mo = Rig.Moon.Get();
	const USkyLightComponent* K = Rig.Sky.Get();
	const FString Bp = Rig.SkyManager.IsValid()
						   ? FString::Printf(TEXT("%s (SunSpeed %.2f 그대로 · SunCurrentRotation p%.1f → 실행 중 우리 pitch 를 쓴다)"),
											 *GetNameSafe(Rig.SkyManager.Get()), Rig.BPSunSpeed, Rig.OriginalBPRotation.Pitch)
						   : FString(TEXT("없음 (방향광을 직접 돌린다)"));
	UE_LOG(LogEcoPolicyV3I, Log,
		   TEXT("[EcoV3I] 하늘 연출 켬 (eco.Sky.Link %d, %s): 해 %s 세기 %.2f · 달 %s 세기 %.3f 색 (%d,%d,%d) · 하늘빛 %s 세기 %.2f | 팀 하늘 BP %s | ")
			   TEXT("해 길 yaw %.0f° (낮 180+180p·밤 360+180p) | 밤 달빛 %.2f lux · 달 색 섞기 %.2f · 밤 하늘빛 ×%.2f"),
		   CVarSkyLink.GetValueOnGameThread(),
		   World.GetNetMode() == NM_Client ? TEXT("클라이언트 — GameState 요약 사이를 이어 그린다") : TEXT("권위 — 팀 시계"),
		   *LightName(S), S ? S->Intensity : 0.0f, *LightName(Mo), Mo ? Mo->Intensity : 0.0f, Rig.OriginalMoonColor.R, Rig.OriginalMoonColor.G,
		   Rig.OriginalMoonColor.B, K ? *GetNameSafe(K->GetOwner()) : TEXT("없음"), K ? K->Intensity : 0.0f, *Bp, Rig.SunYawDeg,
		   CVarSkyNightBrightness.GetValueOnGameThread(), CVarSkyMoonTint.GetValueOnGameThread(), CVarSkyNightSkyLight.GetValueOnGameThread());
	return true;
}

void UEcoV3SkyPresenterSubsystem::Unlink(const TCHAR* Why)
{
	Rig.Restore();
	bLinked = false;
	NextCaptureTry = 0.0;
	// 표시 시계를 비운다 — 다시 켜면 다음 표본(클라이언트는 지금 요약)에서 곧바로 맞춘다 (멈춰 있던 시각을 잠깐 보이지 않게)
	Clock = EcoV3Sky::FDisplayClock();
	LastRevision = -1;
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 하늘 연출 끔 (%s) — 해·달·하늘빛·팀 하늘 BP 칸을 처음 값으로 되돌렸다"), Why);
}

void UEcoV3SkyPresenterSubsystem::LogPose(const UWorld& World, const TCHAR* Why)
{
	bool bDay = true;
	double P = 0.0;
	EcoV3Sky::ClockPhase(Clock, bDay, P);
	FString V3;
	if (World.GetNetMode() != NM_Client)
	{
		const UEcoPolicyV3IntegratedSubsystem* Sub = World.GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
		if (const FEcoV3RegionContext* Ctx = Sub && Sub->IsActive() ? Sub->GetContext(0) : nullptr)
		{
			V3 = FString::Printf(TEXT(" (v3 %s 세계 d=%.2f)"), *Ctx->RegionId.ToString(), Ctx->Sim.Dark);
		}
	}
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 하늘 | %s | 팀 시계 %.1f초 %s %.0f%% | 해 pitch %.1f° 높이 %+.1f° → 하늘 d=%.2f%s | 해 %.2f · 달 %.3f · 하늘빛 %.2f"),
		   Why, Clock.Shown, bDay ? TEXT("낮") : TEXT("밤"), P * 100.0, LastPose.SunPitchDeg, LastPose.SunElevationDeg, LastPose.Dark, *V3,
		   LastPose.SunIntensity, LastPose.MoonIntensity, LastPose.SkyIntensity);
}

void UEcoV3SkyPresenterSubsystem::TickPresenter(float DeltaSeconds)
{
	using namespace EcoV3SkyImpl;
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (!WantsLink(*World))
	{
		if (bLinked)
		{
			Unlink(TEXT("eco.Sky.Link 0 이거나 통합 v3 모드가 아님"));
		}
		return;
	}
	EcoV3Sky::FClockSample Sample;
	const bool bNew = ReadNewSample(*World, Sample);
	EcoV3Sky::StepClock(Clock, static_cast<double>(DeltaSeconds), bNew ? &Sample : nullptr);
	bool bDay = true;
	double P = 0.0;
	if (!EcoV3Sky::ClockPhase(Clock, bDay, P))
	{
		return;   // 팀 시계·요약이 아직 없다 — 하늘은 팀 그대로
	}
	if (bLinked && !Rig.IsAlive())
	{
		Unlink(TEXT("잡았던 빛·하늘 BP 액터가 사라졌다 — 다시 찾는다"));
		return;   // 표시 시계도 비웠다 — 다음 표본부터 다시
	}
	bool bJustLinked = false;
	if (!bLinked)
	{
		if (!Link(*World))
		{
			return;
		}
		bJustLinked = true;
	}
	EcoV3Sky::FLook Look = Rig.BaseLook();
	Look.NightLux = CVarSkyNightBrightness.GetValueOnGameThread();
	Look.MoonTint = CVarSkyMoonTint.GetValueOnGameThread();
	Look.NightSkyLight = CVarSkyNightSkyLight.GetValueOnGameThread();
	LastPose = EcoV3Sky::ComputePose(bDay, P, Look);
	Rig.Apply(LastPose);

	// 기록: 켬·낮밤 바뀜·eco.Sky.LogSeconds 간격 (표시 시계 초)
	const double Every = FMath::Max(0.0, static_cast<double>(CVarSkyLogSeconds.GetValueOnGameThread()));
	if (NextLogAt > Clock.Shown + Every)
	{
		NextLogAt = Clock.Shown;   // 시계가 뒤로 맞춰졌다 (판 바뀜 등)
	}
	if (bJustLinked || bDay != bLastDay)
	{
		LogPose(*World, bJustLinked ? TEXT("켬") : (bDay ? TEXT("낮 시작") : TEXT("밤 시작")));
		bLastDay = bDay;
		NextLogAt = Clock.Shown + Every;
	}
	else if (Every > 0.0 && Clock.Shown >= NextLogAt)
	{
		LogPose(*World, TEXT("간격"));
		NextLogAt = Clock.Shown + Every;
	}
}
