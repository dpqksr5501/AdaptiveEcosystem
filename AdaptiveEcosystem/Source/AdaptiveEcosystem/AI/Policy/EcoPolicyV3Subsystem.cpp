#include "EcoPolicyV3Subsystem.h"

#include "EcoBehaviorConfig.h"
#include "EcoHeading.h"
#include "EcoPolicyV3Fragments.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassMovementFragments.h"

DEFINE_LOG_CATEGORY(LogEcoPolicyV3);

namespace EcoPolicyV3SubsystemImpl
{
	/** 판 고르기. v1 이 기본이다 — v3 는 우리 시험 경로에서만 켠다. */
	static TAutoConsoleVariable<int32> CVarPolicyVersion(
		TEXT("eco.PolicyVersion"),
		1,
		TEXT("정책 판. 1 = v1 (관측 7 → 조향 무게 4, 기본), 3 = v3 R1b (관측 18 → 행동 고르기 GRAZE/FLEE/HIDE/FREEZE). ")
		TEXT("AEcoPolicyTestSpawner 가 시작과 매 틱 시작에 읽어 개체군을 바꿔 만든다."),
		ECVF_Default);

	const TCHAR* BehaviorNameKo(int32 B)
	{
		static const TCHAR* Names[EcoRepertoireV3::kNumBehaviors] = {TEXT("먹기"), TEXT("도망"), TEXT("숨기"), TEXT("얼기"),
																	 TEXT("잠")};
		return (B >= 0 && B < EcoRepertoireV3::kNumBehaviors) ? Names[B] : TEXT("?");
	}

	/** 은신처 원들이 맵에서 차지하는 넓이 비율 (셀 중심 표본, 파이썬 cover_frac_actual 과 같은 정의). */
	double CoverAreaFraction(const EcoWorldV3::FWorldConfig& C)
	{
		const int32 G = FMath::Max(1, FMath::CeilToInt32(C.WorldSize / C.FoodCell));
		int32 In = 0;
		for (int32 y = 0; y < G; ++y)
		{
			const double Cy = (y + 0.5) * C.FoodCell;
			for (int32 x = 0; x < G; ++x)
			{
				const double Cx = (x + 0.5) * C.FoodCell;
				for (const EcoObservationV3::FCoverInput& Cv : C.Covers)
				{
					if ((Cx - Cv.X) * (Cx - Cv.X) + (Cy - Cv.Y) * (Cy - Cv.Y) <= Cv.Radius * Cv.Radius)
					{
						++In;
						break;
					}
				}
			}
		}
		return static_cast<double>(In) / static_cast<double>(G * G);
	}
}

void UEcoPolicyV3Subsystem::Deinitialize()
{
	EndSession();
	Super::Deinitialize();
}

int32 UEcoPolicyV3Subsystem::GetRequestedPolicyVersion()
{
	return EcoPolicyV3SubsystemImpl::CVarPolicyVersion.GetValueOnGameThread() == 3 ? 3 : 1;
}

EcoWorldV3::FWorldConfig UEcoPolicyV3Subsystem::MakeWorldConfig(const FEcoPolicyV3Settings& S)
{
	EcoWorldV3::FWorldConfig C;
	C.Seed = S.Seed;
	C.NumHerbivores = FMath::Max(1, S.HerbivoreCount);
	C.WorldSize = EcoRepertoireV3::CmToUnits(FMath::Max(400.0, static_cast<double>(S.WorldSizeCm)));
	C.NumStalkers = FMath::Max(0, S.NumStalkers);
	C.NumChasers = FMath::Max(0, S.NumChasers);
	C.NumRanged = FMath::Max(0, S.NumRanged);
	C.NumNocturnal = FMath::Clamp(S.NumNocturnal, 0, C.NumBaseThreats());
	C.bPlayerProxy = S.bPlayerProxy;
	C.PredSpeedMult = FMath::Max(0.0, static_cast<double>(S.PredSpeedMult));
	C.DayPeriod = S.DayPeriodSteps > 1 ? S.DayPeriodSteps : 0;
	C.DayOffset = FMath::Max(0, S.DayOffsetSteps);
	C.TwilightSteps = 0;   // InitWorld 가 round(0.05·T) 로 정한다
	C.FoodRegenMult = FMath::Max(0.0, static_cast<double>(S.FoodRegenMult));
	if (S.CoverRadiusCm > 0.0f)
	{
		C.Covers = EcoWorldV3::QuadCovers(C.WorldSize, EcoRepertoireV3::CmToUnits(S.CoverRadiusCm));
	}
	return C;
}

TArray<FString> UEcoPolicyV3Subsystem::CheckTrainingRange(const EcoWorldV3::FWorldConfig& C)
{
	// 학습 세계 범위: configs/default.yaml rand.* + v3_r1_on.yaml (계약 7-7). 'EcoThreatV3::FThreatConfig' 의 범위 칸과 같다.
	const EcoThreatV3::FThreatConfig T;
	TArray<FString> Out;
	if (C.WorldSize < T.WorldSizeLo || C.WorldSize > T.WorldSizeHi)
	{
		Out.Add(FString::Printf(TEXT("맵 한 변 %.0f단위 (학습 %.0f~%.0f)"), C.WorldSize, T.WorldSizeLo, T.WorldSizeHi));
	}
	const int32 Base = C.NumBaseThreats();
	if (Base < T.PredatorCountLo || Base > T.PredatorCountHi)
	{
		Out.Add(FString::Printf(TEXT("보통 위협 %d마리 (학습 %d~%d)"), Base, T.PredatorCountLo, T.PredatorCountHi));
	}
	if (Base > 0)
	{
		const double Stalk = static_cast<double>(C.NumStalkers) / Base;
		const double Ranged = static_cast<double>(C.NumRanged) / Base;
		const double Noct = static_cast<double>(C.NumNocturnal) / Base;
		if (Stalk < T.StalkFracLo || Stalk > T.StalkFracHi)
		{
			Out.Add(FString::Printf(TEXT("잠행형 비율 %.2f (학습 %.1f~%.1f)"), Stalk, T.StalkFracLo, T.StalkFracHi));
		}
		if (Ranged > T.RangedFracHi)
		{
			Out.Add(FString::Printf(TEXT("원거리형 비율 %.2f (학습 0~%.1f)"), Ranged, T.RangedFracHi));
		}
		if (Noct > T.NocturnalFracHi)
		{
			Out.Add(FString::Printf(TEXT("야행성 비율 %.2f (학습 0~%.2f)"), Noct, T.NocturnalFracHi));
		}
	}
	if (Base > C.NumStalkers && (C.PredSpeedMult < T.PredSpeedMultLo || C.PredSpeedMult > T.PredSpeedMultHi))
	{
		Out.Add(FString::Printf(TEXT("늑대 속력 배수 %.2f (학습 %.2f~%.2f)"), C.PredSpeedMult, T.PredSpeedMultLo, T.PredSpeedMultHi));
	}
	if (C.DayPeriod > 0 && C.DayPeriod != T.DayPeriods[0] && C.DayPeriod != T.DayPeriods[1] && C.DayPeriod != T.DayPeriods[2])
	{
		Out.Add(FString::Printf(TEXT("낮밤 주기 %d스텝 (학습 %d/%d/%d)"), C.DayPeriod, T.DayPeriods[0], T.DayPeriods[1],
								T.DayPeriods[2]));
	}
	for (const EcoObservationV3::FCoverInput& Cv : C.Covers)
	{
		if (Cv.Radius < 4.0 || Cv.Radius > 9.0)
		{
			Out.Add(FString::Printf(TEXT("은신처 반경 %.1f단위 (학습 4~9)"), Cv.Radius));
			break;
		}
	}
	const double Area = EcoPolicyV3SubsystemImpl::CoverAreaFraction(C);
	if (Area < 0.05 || Area > 0.30)
	{
		Out.Add(FString::Printf(TEXT("은신처 넓이 %.1f%% (학습 5~30%%)"), Area * 100.0));
	}
	if (C.FoodRegenMult < 0.5 || C.FoodRegenMult > 2.0)
	{
		Out.Add(FString::Printf(TEXT("먹이 재생 배수 %.2f (학습 0.5~2)"), C.FoodRegenMult));
	}
	return Out;
}

bool UEcoPolicyV3Subsystem::BeginSession(const EcoWorldV3::FWorldConfig& Config, const FVector& CenterCm,
										 float LogIntervalSeconds)
{
	const UWorld* World = GetWorld();
	if (!World || World->GetNetMode() == NM_Client)
	{
		return false;   // 논리 상태는 서버·단독에만 있다
	}
	if (bSessionActive)
	{
		UE_LOG(LogEcoPolicyV3, Warning, TEXT("[EcoV3] 이미 세션이 열려 있다 — 한 월드에 v3 시험 개체군은 하나다"));
		return false;
	}
	if (Config.NumHerbivores < 1 || !(Config.WorldSize > 0.0) || Config.NumThreats() < 0)
	{
		UE_LOG(LogEcoPolicyV3, Error, TEXT("[EcoV3] 세계 설정이 잘못됐다 (사슴 %d, 맵 %.1f단위)"), Config.NumHerbivores,
			   Config.WorldSize);
		return false;
	}

	EcoWorldV3::InitWorld(Sim, Config);
	const double SizeCm = Config.WorldSize * EcoRepertoireV3::kUnitCm;
	OriginCm = FVector(CenterCm.X - 0.5 * SizeCm, CenterCm.Y - 0.5 * SizeCm, CenterCm.Z);
	Clock = EcoPolicy::FStepClock();
	ClockPhase = 0;
	LogEverySteps = LogIntervalSeconds > 0.0f
						? FMath::Max(1, FMath::RoundToInt32(LogIntervalSeconds / EcoBehaviorConfig::StepSeconds))
						: 0;
	LastLogStep = 0;
	LastLogStats = EcoWorldV3::FWorldStats();
	RecentCatches.Reset();
	bSessionActive = true;

	UE_LOG(LogEcoPolicyV3, Log,
		   TEXT("[EcoV3] 세션 시작: 모델 %s (관측 %d, 마스크 판 %d) | 사슴 %d, 위협 %d (잠행 %d, 추격 %d, 원거리 %d, 야행성 %d, 플레이어 대역 %d) | ")
			   TEXT("맵 %.0f m, 은신처 %d, 낮밤 %d스텝, 시드 %lld"),
		   UTF8_TO_TCHAR(EcoPolicyV3::kModelName), EcoPolicyV3::kObsDim, EcoPolicyV3::kMaskVersion, Config.NumHerbivores, Config.NumThreats(),
		   Config.NumStalkers, Config.NumChasers, Config.NumRanged, Config.NumNocturnal, Config.bPlayerProxy ? 1 : 0,
		   SizeCm / 100.0, static_cast<int32>(Config.Covers.size()), Config.DayPeriod, static_cast<long long>(Config.Seed));
	for (const FString& Why : CheckTrainingRange(Sim.Config))
	{
		UE_LOG(LogEcoPolicyV3, Warning, TEXT("[EcoV3] 학습 범위 밖: %s"), *Why);
	}
	return true;
}

void UEcoPolicyV3Subsystem::EndSession()
{
	if (bSessionActive)
	{
		UE_LOG(LogEcoPolicyV3, Log, TEXT("[EcoV3] 세션 끝 (스텝 %lld)"), static_cast<long long>(Sim.T));
	}
	bSessionActive = false;
	Sim = EcoWorldV3::FWorldState();
	RecentCatches.Reset();
}

TArray<const UScriptStruct*> UEcoPolicyV3Subsystem::HerbivoreComposition()
{
	return {
		FTransformFragment::StaticStruct(),
		FMassVelocityFragment::StaticStruct(),
		FEcoBehaviorStateFragment::StaticStruct(),
		FEcoPerceptionCacheFragment::StaticStruct(),
		FEcoControlOutFragment::StaticStruct(),
		FEcoHerbivoreBodyV3Fragment::StaticStruct(),
		FEcoPolicyV3Tag::StaticStruct(),
		// 이동은 v3 프로세서가 직접 쓴다. 엔진 이동 프로세서가 같은 개체를 움직이지 않게 막아 둔다(v1 과 같은 방법).
		FMassCustomMovementTag::StaticStruct(),
	};
}

TArray<const UScriptStruct*> UEcoPolicyV3Subsystem::ThreatComposition()
{
	return {
		FTransformFragment::StaticStruct(),
		FMassVelocityFragment::StaticStruct(),
		FEcoThreatStateFragment::StaticStruct(),
		FEcoThreatV3Tag::StaticStruct(),
		FMassCustomMovementTag::StaticStruct(),
	};
}

EcoWorldV3::FHerbView UEcoPolicyV3Subsystem::MakeHerbView(const FMassEntityManager& EM, FMassEntityHandle E)
{
	EcoWorldV3::FHerbView V;
	if (!EM.IsEntityValid(E))
	{
		return V;
	}
	FEcoBehaviorStateFragment* State = EM.GetFragmentDataPtr<FEcoBehaviorStateFragment>(E);
	FEcoPerceptionCacheFragment* Perc = EM.GetFragmentDataPtr<FEcoPerceptionCacheFragment>(E);
	FEcoControlOutFragment* Ctrl = EM.GetFragmentDataPtr<FEcoControlOutFragment>(E);
	FEcoHerbivoreBodyV3Fragment* Body = EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E);
	if (State && Perc && Ctrl && Body)
	{
		V.Rep = &State->Rep;
		V.Decision = &State->Decision;
		V.Perception = &Perc->Perception;
		V.Control = &Ctrl->Control;
		V.Body = &Body->Body;
	}
	return V;
}

bool UEcoPolicyV3Subsystem::SpawnPopulation(FMassEntityManager& EM, TArray<FMassEntityHandle>& OutHerbivores,
											TArray<FMassEntityHandle>& OutThreats)
{
	OutHerbivores.Reset();
	OutThreats.Reset();
	if (!bSessionActive)
	{
		return false;
	}
	if (EM.IsProcessing())
	{
		UE_LOG(LogEcoPolicyV3, Error, TEXT("[EcoV3] Mass 처리 중에는 개체를 만들지 않는다"));
		return false;
	}
	const int32 N = Sim.Config.NumHerbivores;
	const int32 M = Sim.Config.NumThreats();

	const FMassArchetypeHandle HerbArch = EM.CreateArchetype(HerbivoreComposition());
	const FMassArchetypeHandle ThreatArch = EM.CreateArchetype(ThreatComposition());
	for (int32 i = 0; i < N; ++i)
	{
		OutHerbivores.Add(EM.CreateEntity(HerbArch));
	}
	for (int32 m = 0; m < M; ++m)
	{
		OutThreats.Add(EM.CreateEntity(ThreatArch));
	}

	// 다 만든 뒤에 조각 주소를 잡는다. 슬롯 = 배열 색인. 세계 난수 순서: 초식 슬롯 순서 → 위협 슬롯 순서 (기준 루프와 같다)
	TArray<EcoWorldV3::FHerbView> Views;
	Views.SetNum(N);
	TArray<EcoWorldV3::FThreatAgent*> Threats;
	Threats.SetNum(M);
	for (int32 i = 0; i < N; ++i)
	{
		Views[i] = MakeHerbView(EM, OutHerbivores[i]);
		if (!Views[i].IsValid())
		{
			DestroyPopulation(EM, OutHerbivores, OutThreats);
			return false;
		}
		EcoWorldV3::InitHerb(Sim, static_cast<uint32>(i), Views[i]);
	}
	for (int32 m = 0; m < M; ++m)
	{
		Threats[m] = &EM.GetFragmentDataChecked<FEcoThreatStateFragment>(OutThreats[m]).Agent;
		EcoWorldV3::InitThreat(Sim, static_cast<uint32>(m), *Threats[m]);
	}
	EcoWorldV3::ObserveAndDecideAll(Sim, Views.GetData(), N, Threats.GetData(), M);

	for (int32 i = 0; i < N; ++i)
	{
		const FMassEntityHandle E = OutHerbivores[i];
		EM.GetFragmentDataChecked<FEcoBehaviorStateFragment>(E).SyncSummary(*Views[i].Control);
		FVector Vel;
		ComputeHerbVisual(*Views[i].Body, 0.0f, EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform(), Vel);
		EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value = Vel;
	}
	for (int32 m = 0; m < M; ++m)
	{
		const FMassEntityHandle E = OutThreats[m];
		FVector Vel;
		ComputeThreatVisual(*Threats[m], 0.0f, EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform(), Vel);
		EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value = Vel;
	}
	return true;
}

void UEcoPolicyV3Subsystem::DestroyPopulation(FMassEntityManager& EM, TArray<FMassEntityHandle>& Herbivores,
											  TArray<FMassEntityHandle>& Threats)
{
	for (const FMassEntityHandle& E : Herbivores)
	{
		if (EM.IsEntityValid(E))
		{
			EM.DestroyEntity(E);
		}
	}
	for (const FMassEntityHandle& E : Threats)
	{
		if (EM.IsEntityValid(E))
		{
			EM.DestroyEntity(E);
		}
	}
	Herbivores.Reset();
	Threats.Reset();
}

int32 UEcoPolicyV3Subsystem::AdvanceClock(float DeltaSeconds)
{
	if (!bSessionActive)
	{
		return 0;
	}
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	return EcoPolicy::ConsumeSteps(ClockPhase, Clock.Advance(DeltaSeconds, EcoBehaviorConfig::StepSeconds, Interval), Interval);
}

float UEcoPolicyV3Subsystem::GetVisualAlpha() const
{
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	return FMath::Clamp(static_cast<float>(ClockPhase) / static_cast<float>(Interval), 0.0f, 1.0f);
}

FVector UEcoPolicyV3Subsystem::UnitsToCm(double X, double Y) const
{
	return FVector(OriginCm.X + X * EcoRepertoireV3::kUnitCm, OriginCm.Y + Y * EcoRepertoireV3::kUnitCm, OriginCm.Z);
}

EcoWorldV3::FVec2 UEcoPolicyV3Subsystem::CmToUnits(const FVector& P) const
{
	return {(P.X - OriginCm.X) / EcoRepertoireV3::kUnitCm, (P.Y - OriginCm.Y) / EcoRepertoireV3::kUnitCm};
}

void UEcoPolicyV3Subsystem::ComputeHerbVisual(const EcoWorldV3::FHerbBody& B, float Alpha, FTransform& OutTransform,
											  FVector& OutVelocity) const
{
	const double A = FMath::Clamp(static_cast<double>(Alpha), 0.0, 1.0);
	OutTransform.SetLocation(UnitsToCm(B.PrevPos.X + (B.Pos.X - B.PrevPos.X) * A, B.PrevPos.Y + (B.Pos.Y - B.PrevPos.Y) * A));
	if (B.Head.X != 0.0 || B.Head.Y != 0.0)
	{
		OutTransform.SetRotation(EcoHeading::YawQuatFromDir(FVector(B.Head.X, B.Head.Y, 0.0)));
	}
	// 이번 결정 스텝의 실제 변위를 cm/s 로 (리스폰이면 PrevPos == Pos 라 0)
	const double K = EcoRepertoireV3::kUnitCm / EcoRepertoireV3::kStepSeconds;
	OutVelocity = FVector((B.Pos.X - B.PrevPos.X) * K, (B.Pos.Y - B.PrevPos.Y) * K, 0.0);
}

void UEcoPolicyV3Subsystem::ComputeThreatVisual(const EcoWorldV3::FThreatAgent& Ag, float Alpha, FTransform& OutTransform,
												FVector& OutVelocity) const
{
	const double A = FMath::Clamp(static_cast<double>(Alpha), 0.0, 1.0);
	const EcoThreatV3::FThreatState& S = Ag.State;
	OutTransform.SetLocation(UnitsToCm(Ag.PrevX + (S.PosX - Ag.PrevX) * A, Ag.PrevY + (S.PosY - Ag.PrevY) * A));
	if (S.HeadX != 0.0 || S.HeadY != 0.0)
	{
		OutTransform.SetRotation(EcoHeading::YawQuatFromDir(FVector(S.HeadX, S.HeadY, 0.0)));
	}
	const double K = EcoRepertoireV3::kUnitCm / EcoRepertoireV3::kStepSeconds;
	OutVelocity = FVector((S.PosX - Ag.PrevX) * K, (S.PosY - Ag.PrevY) * K, 0.0);
}

void UEcoPolicyV3Subsystem::NotifyStepCompleted(const EcoWorldV3::FStepReport& Report)
{
	const UWorld* World = GetWorld();
	const double Now = World ? World->GetTimeSeconds() : 0.0;
	for (const EcoWorldV3::FVec2& P : Sim.StepCatches)
	{
		RecentCatches.Add({UnitsToCm(P), Now});
	}
	RecentCatches.RemoveAll([Now](const FEcoPolicyV3CatchMark& Mark) { return Now - Mark.Time > 1.5; });

	if (LogEverySteps > 0 && Sim.T - LastLogStep >= LogEverySteps)
	{
		LogSummary();
	}
}

void UEcoPolicyV3Subsystem::LogSummary()
{
	const EcoWorldV3::FWorldStats& S = Sim.Stats;
	const EcoWorldV3::FWorldStats& P = LastLogStats;
	const double Seconds = static_cast<double>(Sim.T) * EcoRepertoireV3::kStepSeconds;
	const bool bNight = Sim.Dark >= 0.5;

	// 네 행동(GRAZE·FLEE·HIDE·FREEZE)을 모두 썼는가 — 계획서 e3 끝난 기준 '평면 시험 맵에서 v3 사슴이 네 행동을 모두 쓴다'
	bool bAllFour = true;
	for (int32 b = 0; b < EcoRepertoireV3::kSleep; ++b)
	{
		bAllFour = bAllFour && S.BehaviorSteps[b] > 0;
	}

	FString Interval;
	FString Entries;
	FString Total;
	for (int32 b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
	{
		Interval += FString::Printf(TEXT(" %s %lld"), EcoPolicyV3SubsystemImpl::BehaviorNameKo(b), static_cast<long long>(S.BehaviorSteps[b] - P.BehaviorSteps[b]));
		Entries += FString::Printf(TEXT(" %s %lld"), EcoPolicyV3SubsystemImpl::BehaviorNameKo(b), static_cast<long long>(S.Entries[b] - P.Entries[b]));
		Total += FString::Printf(TEXT(" %s %lld"), EcoPolicyV3SubsystemImpl::BehaviorNameKo(b), static_cast<long long>(S.BehaviorSteps[b]));
	}
	UE_LOG(LogEcoPolicyV3, Log,
		   TEXT("[EcoV3] 스텝 %lld (%.1f초, %s d=%.2f) | 사슴 %d 늑대 %d | 행동 사용(개체·스텝):%s | 진입:%s | 누적 사용:%s | ")
			   TEXT("네 행동 모두 씀=%s | 포획 %lld (누적 %lld) 굶음 %lld (누적 %lld) 번식 %lld | 결정 %lld | 마스크 위반 %lld | 피식EMA %.3f"),
		   static_cast<long long>(Sim.T), Seconds, bNight ? TEXT("밤") : TEXT("낮"), Sim.Dark, Sim.Config.NumHerbivores,
		   Sim.Config.NumThreats(), *Interval, *Entries, *Total, bAllFour ? TEXT("예") : TEXT("아니오"),
		   static_cast<long long>(S.Caught - P.Caught), static_cast<long long>(S.Caught),
		   static_cast<long long>(S.Starved - P.Starved), static_cast<long long>(S.Starved),
		   static_cast<long long>(S.Reproduced - P.Reproduced), static_cast<long long>(S.Decisions - P.Decisions),
		   static_cast<long long>(S.MaskViolations), Sim.PredEma);

	LastLogStep = Sim.T;
	LastLogStats = S;
}
