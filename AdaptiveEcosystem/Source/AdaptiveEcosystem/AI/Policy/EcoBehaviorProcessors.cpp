#include "EcoBehaviorProcessors.h"

#include "EcoBehaviorConfig.h"
#include "EcoBehaviorFragments.h"
#include "EcoHeading.h"
#include "EcoNeighborhoodSubsystem.h"
#include "EcoPolicyClock.h"
#include "EcoPolicyInference.h"
#include "EcoSteering.h"
#include "EcoRegionPredationSubsystem.h"
#include "EcoWorldProviders.h"
#include "Mass/EntityFragments.h"
#include "MassCommandBuffer.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"

namespace
{
	/**
	 * 포식 사망 표시. 사망 규칙은 이 한 곳에만 둔다 — 나중에 Lifecycle 에 Kill(Entity, Cause) 가
	 * 생기면 이 함수만 바꾼다.
	 *  - HP = 0 은 즉시 쓴다. 태그 교체는 지연되므로 같은 틱의 다른 포식자가 이 개체를 보는 방식은
	 *    포식 프로세서가 따로 기억한다(CaughtThisTick).
	 *  - Alive → PendingDeath 는 명령 버퍼로 넣는다(구조 변경, MASS_PROCESSOR_ORDER.md).
	 *    이 처리 페이즈 끝에 반영되고, 다음 틱부터 초식 쿼리 다섯 개 어디에도 걸리지 않는다.
	 *    시체 정리(파괴·슬롯 해제·복제 제거)는 Lifecycle 몫이다.
	 */
	void MarkPredationKill(FMassCommandBuffer& Commands, FEcoVitalsFragment& Vitals, FMassEntityHandle Victim)
	{
		Vitals.HP = 0.0f;
		Commands.SwapTags<FEcoAliveTag, FEcoPendingDeathTag>(Victim);
	}

	/** §9.4 — 학습 정책과 §5.1 Utility 비교군을 런타임에 갈아끼운다. */
	static TAutoConsoleVariable<int32> CVarUseLearnedPolicy(
		TEXT("eco.UseLearnedPolicy"),
		1,
		TEXT("1이면 학습된 PPO 정책(RunPolicy), 0이면 §5.1 Utility 비교군(RunUtilityPolicy)."),
		ECVF_Default);

	/** 시야 각도 판정. 파이썬 관측과 같은 규약이다 (진행 방향 기준 FOV/2). */
	bool IsInView(const FVector& Self, const FVector& Heading, const FVector& Other,
				  float CosHalfFov)
	{
		const FVector D(Other.X - Self.X, Other.Y - Self.Y, 0.0f);
		const float Len = D.Size2D();
		if (Len <= KINDA_SMALL_NUMBER)
		{
			return false;
		}
		return FVector::DotProduct(D / Len, Heading) >= CosHalfFov;
	}
}

// -----------------------------------------------------------------------------
// UEcoNeighborhoodGatherProcessor
// -----------------------------------------------------------------------------

UEcoNeighborhoodGatherProcessor::UEcoNeighborhoodGatherProcessor()
	: HerbivoreQuery(*this)
	, PredatorQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server
									  | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	// 공유 색인을 쓰므로 게임 스레드에서만 돈다.
	bRequiresGameThreadExecution = true;
}

void UEcoNeighborhoodGatherProcessor::ConfigureQueries(
	const TSharedRef<FMassEntityManager>& EntityManager)
{
	HerbivoreQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	HerbivoreQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
	HerbivoreQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
	// 죽은 초식은 색인에 넣지 않는다 — 동료로 세어지거나 포식자의 표적이 되면 안 된다.
	HerbivoreQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);

	// 포식자는 생존 태그를 요구하지 않는다. v1·파이썬 모두 포식자는 죽지 않고,
	// 생존 태그가 없는 포식자 템플릿(플레이어 등)도 계속 보여야 한다.
	PredatorQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	PredatorQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
	PredatorQuery.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::All);
}

void UEcoNeighborhoodGatherProcessor::Execute(FMassEntityManager& EntityManager,
											  FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	UEcoNeighborhoodSubsystem* Grid = World->GetSubsystem<UEcoNeighborhoodSubsystem>();
	if (!Grid)
	{
		return;
	}
	const UEcoWorldProviderRegistry* Registry = World->GetSubsystem<UEcoWorldProviderRegistry>();
	const IEcoWorldCoverProvider* Cover = Registry ? Registry->GetCoverProvider() : nullptr;

	// 셀 크기를 시야 반경으로 잡는다 — 조회 때 3x3 이면 충분해진다.
	Grid->BeginFrame(EcoBehaviorConfig::SeeRadiusCm);

	auto GatherInto = [Grid, Cover](FMassExecutionContext& Ctx, bool bPredator)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FMassVelocityFragment> Velocities =
			Ctx.GetFragmentView<FMassVelocityFragment>();

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const FVector Location = Transforms[i].GetTransform().GetLocation();
			FEcoNeighborEntry Entry;
			Entry.Entity = Ctx.GetEntity(i);
			Entry.Location = Location;
			Entry.bPredator = bPredator;
			Entry.bInCover = Cover ? Cover->IsInCover(Location) : false;

			// 진행 방향. 멈추면 조향이 마지막으로 쓴 yaw (world.py head 규약).
			Entry.Heading = EcoHeading::HeadingOf(Transforms[i].GetTransform(), Velocities[i].Value);
			Grid->Add(Entry);
		}
	};

	HerbivoreQuery.ForEachEntityChunk(Context,
		[&GatherInto](FMassExecutionContext& Ctx) { GatherInto(Ctx, false); });
	PredatorQuery.ForEachEntityChunk(Context,
		[&GatherInto](FMassExecutionContext& Ctx) { GatherInto(Ctx, true); });

	Grid->Build();
}

// -----------------------------------------------------------------------------
// UEcoPerceptionProcessor
// -----------------------------------------------------------------------------

UEcoPerceptionProcessor::UEcoPerceptionProcessor()
	: EntityQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server
									  | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoNeighborhoodGatherProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoPerceptionProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoSteeringGeometryFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
}

void UEcoPerceptionProcessor::Execute(FMassEntityManager& EntityManager,
									  FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	const UEcoNeighborhoodSubsystem* Grid = World->GetSubsystem<UEcoNeighborhoodSubsystem>();
	const UEcoWorldProviderRegistry* Registry = World->GetSubsystem<UEcoWorldProviderRegistry>();
	if (!Grid || !Grid->IsBuilt() || !Registry)
	{
		return;
	}
	const IEcoWorldFoodProvider* Food = Registry->GetFoodProvider();
	const IEcoWorldCoverProvider* Cover = Registry->GetCoverProvider();

	const float SeeRadius = EcoBehaviorConfig::SeeRadiusCm;
	const float SepRadius = EcoBehaviorConfig::SepRadiusCm;
	const float CosHalfFov = FMath::Cos(FMath::DegreesToRadians(EcoBehaviorConfig::FovDeg) * 0.5f);

	EntityQuery.ForEachEntityChunk(Context,
		[Grid, Food, Cover, SeeRadius, SepRadius, CosHalfFov](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FMassVelocityFragment> Velocities =
			Ctx.GetFragmentView<FMassVelocityFragment>();
		const TArrayView<FEcoSteeringGeometryFragment> Geometries =
			Ctx.GetMutableFragmentView<FEcoSteeringGeometryFragment>();

		const TArray<FEcoNeighborEntry>& Entries = Grid->GetEntries();
		TArray<int32> Nearby;

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const FVector Self = Transforms[i].GetTransform().GetLocation();
			// 움직이면 속도 방향, 멈추면 조향이 마지막으로 쓴 yaw (world.py head 규약).
			const FVector Heading = EcoHeading::HeadingOf(Transforms[i].GetTransform(), Velocities[i].Value);

			FEcoSteeringGeometryFragment& G = Geometries[i];
			G = FEcoSteeringGeometryFragment();   // 매 틱 새로 만든다

			FVector KinSum = FVector::ZeroVector;
			FVector SepSum = FVector::ZeroVector;
			float BestPredDist = TNumericLimits<float>::Max();
			FVector BestPredDir = FVector::ZeroVector;

			Grid->QueryRadius(Self, SeeRadius, Nearby);
			for (int32 Index : Nearby)
			{
				const FEcoNeighborEntry& Other = Entries[Index];
				const FVector D(Other.Location.X - Self.X, Other.Location.Y - Self.Y, 0.0f);
				const float Dist = D.Size2D();
				// 자기 자신은 거리 0으로 잡히므로 걸러진다 (§3.1 "자기 제외").
				if (Dist <= KINDA_SMALL_NUMBER)
				{
					continue;
				}

				if (Other.bPredator)
				{
					if (!IsInView(Self, Heading, Other.Location, CosHalfFov))
					{
						continue;
					}
					++G.PredatorCount;
					if (Dist < BestPredDist)
					{
						BestPredDist = Dist;
						BestPredDir = -D / Dist;   // 반대 방향 단위벡터
					}
					continue;   // 포식자는 조향 대상이 아니다 (§9.5)
				}

				// --- 동족 ---
				if (IsInView(Self, Heading, Other.Location, CosHalfFov))
				{
					++G.KinCount;
					KinSum += Other.Location;
				}
				// separation 은 시야와 무관하다 — 뒤에서 밀려도 비켜야 한다.
				if (Dist < SepRadius)
				{
					SepSum += (-D / Dist) * (1.0f - Dist / SepRadius);
				}
			}

			if (G.KinCount > 0)
			{
				const FVector Centroid = KinSum / static_cast<float>(G.KinCount);
				G.ToCentroid = FVector(Centroid.X - Self.X, Centroid.Y - Self.Y, 0.0f)
								   .GetSafeNormal();
			}
			G.Separation = SepSum.GetClampedToMaxSize(1.0f);
			G.DistPredMin = BestPredDist;
			G.AwayFromPred = BestPredDir;
			G.FoodGrad = Food ? Food->GetFoodGradient(Self, SeeRadius) : FVector::ZeroVector;
			G.ToCover = Cover ? Cover->GetCoverDirection(Self) : FVector::ZeroVector;
		}
	});
}

// -----------------------------------------------------------------------------
// UEcoPolicyProcessor  (§9.4)
// -----------------------------------------------------------------------------

UEcoPolicyProcessor::UEcoPolicyProcessor()
	: EntityQuery(*this)
{
	// §9.4 ExecutionFlags = Server. 스탠드얼론도 권위를 가지므로 함께 켠다 (AGENTS.md §2.2).
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server
									  | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPerceptionProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoPolicyProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoSteeringGeometryFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoObservationFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoPolicyRuntimeFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
}

void UEcoPolicyProcessor::Execute(FMassEntityManager& EntityManager,
								  FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	const UEcoWorldProviderRegistry* Registry = World->GetSubsystem<UEcoWorldProviderRegistry>();
	const UEcoRegionPredationSubsystem* Predation = World->GetSubsystem<UEcoRegionPredationSubsystem>();
	const IEcoWorldFoodProvider* Food = Registry ? Registry->GetFoodProvider() : nullptr;
	const IEcoWorldCoverProvider* Cover = Registry ? Registry->GetCoverProvider() : nullptr;

	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	// §9.4 결정 주기는 프레임 수가 아니라 시간이다 (EcoPolicyClock.h). 논리 틱이 지나지 않은
	// 프레임(60FPS 초과의 절반 프레임, dt <= 0)은 아무도 결정하지 않는다.
	const int32 Ticks = StepClock.Advance(Context.GetDeltaTimeSeconds(), EcoBehaviorConfig::StepSeconds, Interval);
	if (Ticks == 0)
	{
		return;
	}
	const float SeeRadius = EcoBehaviorConfig::SeeRadiusCm;
	const bool bLearned = CVarUseLearnedPolicy.GetValueOnGameThread() != 0;
	// 관측 5는 전역 값이다(world.py). EMA 스텝은 UEcoPredationProcessor 가 포획 직후에 한다.
	const float RecentPredation = Predation ? Predation->GetRecentPredation() : 0.0f;

	EntityQuery.ForEachEntityChunk(Context,
		[Food, Cover, RecentPredation, Interval, Ticks, SeeRadius, bLearned](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FEcoSteeringGeometryFragment> Geometries =
			Ctx.GetFragmentView<FEcoSteeringGeometryFragment>();
		const TConstArrayView<FEcoVitalsFragment> Vitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		const TArrayView<FEcoObservationFragment> Observations =
			Ctx.GetMutableFragmentView<FEcoObservationFragment>();
		const TArrayView<FEcoPolicyOutputFragment> Outputs =
			Ctx.GetMutableFragmentView<FEcoPolicyOutputFragment>();
		const TArrayView<FEcoPolicyRuntimeFragment> Runtimes =
			Ctx.GetMutableFragmentView<FEcoPolicyRuntimeFragment>();

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			// §9.4 "++TicksSinceUpdate < PolicyInterval 이면 skip" — 논리 틱 기준.
			// 위상을 0~Interval 로 흩어 두면 부하가 틱마다 고르게 퍼진다.
			int32& Phase = Runtimes[i].LastPolicyStep;
			if (Phase < 0)
			{
				// 트레잇 스폰 표시(-1): 템플릿 값은 모든 개체에 같으므로 여기서 엔티티 인덱스로 흩는다.
				Phase = static_cast<int32>(Ctx.GetEntity(i).Index % Interval);
			}
			if (!EcoPolicy::AdvanceDecisionPhase(Phase, Ticks, Interval))
			{
				continue;
			}

			const FVector Self = Transforms[i].GetTransform().GetLocation();
			const FEcoSteeringGeometryFragment& G = Geometries[i];

			// --- §3.1 관측 7개. 정규화 상수는 전부 고정값이다 (§1.2) ---
			FEcoPolicyObservationV1& Obs = Observations[i].Observation;
			Obs.FoodDensity = Food ? FMath::Clamp(Food->GetFoodDensity(Self, SeeRadius), 0.f, 1.f)
								   : 0.0f;
			Obs.PredatorCount = FMath::Clamp(
				static_cast<float>(G.PredatorCount) / EcoBehaviorConfig::ObsPredCountNorm, 0.f, 1.f);
			Obs.PredatorDistance = FMath::Clamp(G.DistPredMin / SeeRadius, 0.f, 1.f);
			Obs.ConspecificCount = FMath::Clamp(
				static_cast<float>(G.KinCount) / EcoBehaviorConfig::ObsKinCountNorm, 0.f, 1.f);
			Obs.Energy = FMath::Clamp(
				Vitals[i].Energy / FMath::Max(Vitals[i].MaxEnergy, KINDA_SMALL_NUMBER), 0.f, 1.f);
			Obs.RecentPredation = RecentPredation;
			Obs.CoverDistance = Cover
				? FMath::Clamp(Cover->GetCoverDistance(Self) / EcoBehaviorConfig::ObsCoverNormCm,
							   0.f, 1.f)
				: 1.0f;

			// --- 추론 ---
			float ObsArray[EcoPolicy::ObsDim];
			Obs.ToFloatArray(ObsArray);
			float Action[EcoPolicy::ActDim];
			if (bLearned)
			{
				EcoPolicy::RunPolicy(ObsArray, Action);
			}
			else
			{
				EcoPolicy::RunUtilityPolicy(ObsArray, Action);
			}

			// §9.4 "필드별 대입 (집합 초기화 금지)"
			FEcoPolicyActionV1& Out = Outputs[i].Action;
			Out.Forage = Action[0];
			Out.Cohesion = Action[1];
			Out.FleeDist = Action[2];
			Out.Cover = Action[3];
		}
	});
}

// -----------------------------------------------------------------------------
// UEcoPredationProcessor  (§9.6 / §9.8-5)
// -----------------------------------------------------------------------------

UEcoPredationProcessor::UEcoPredationProcessor()
	: HerbivoreQuery(*this)
	, PredatorQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server
									  | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	// 포획은 이동 뒤에 판정한다 (MASS_PROCESSOR_ORDER.md: Steering → … → Interaction → Lifecycle).
	// 그래서 잡힌 개체가 같은 틱에 정책·조향을 다시 받는 일이 없고, 다음 틱부터는 Alive 가
	// 없어 빠진다. 판정 위치는 이번 틱 게더 시점의 색인 위치다(이동 후 위치가 아니다).
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPerceptionProcessor"));
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoSteeringProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoPredationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	// Vitals 는 ReadWrite 로 선언한다. 실제 쓰기는 포식자 루프에서 핸들로 하지만,
	// 선언이 있어야 Mass 가 이 프로세서가 Vitals 를 쓴다는 걸 안다.
	HerbivoreQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	HerbivoreQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadWrite);
	HerbivoreQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
	HerbivoreQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);

	PredatorQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	PredatorQuery.AddRequirement<FEcoPredatorStateFragment>(EMassFragmentAccess::ReadWrite);
	PredatorQuery.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::All);
}

void UEcoPredationProcessor::Execute(FMassEntityManager& EntityManager,
									 FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	UEcoRegionPredationSubsystem* Predation =
		World ? World->GetSubsystem<UEcoRegionPredationSubsystem>() : nullptr;
	const UEcoNeighborhoodSubsystem* Grid =
		World ? World->GetSubsystem<UEcoNeighborhoodSubsystem>() : nullptr;
	if (!Predation || !Grid || !Grid->IsBuilt())
	{
		return;
	}

	// --- EMA 분모: 포획 전 생존 초식 전체 수 (world.py 의 N). 틱마다 한 번 ---
	// 쿼리가 이미 Alive 를 요구한다. HP 검사는 다른 피해 경로가 HP 만 0으로 만든 경우의 방어선이다.
	int32 Alive = 0;
	HerbivoreQuery.ForEachEntityChunk(Context, [&Alive](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FEcoVitalsFragment> Vitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (Vitals[i].HP > 0.0f)
			{
				++Alive;
			}
		}
	});
	Predation->ReportAlivePopulation(Alive);

	// --- 포획. 파이썬 env/world.py 의 포식자 스텝과 같은 규칙 ---
	//   pred_cd = max(pred_cd - 1, 0);  hunting = pred_cd == 0
	//   perceived = dist × (은신처면 cover_hide_mult)
	//   hit = perceived <= catch_r & hunting — 초식의 시야와 무관하다
	//   포식자당 한 마리(체감 거리 최소), 잡으면 pred_cd = pred_eat_cd
	const float Dt = Context.GetDeltaTimeSeconds();
	const float CatchRadius = EcoBehaviorConfig::PredCatchRadiusCm;
	const float HideMult = EcoBehaviorConfig::CoverHideMult;
	const float EatCooldown = EcoBehaviorConfig::PredEatCooldownS;
	const TArray<FEcoNeighborEntry>& Entries = Grid->GetEntries();
	// 이번 틱에 잡힌 개체. 파이썬은 포식자마다 반경 안 최근접(argmin)을 따로 고르고, 고른 포식자는
	// 모두 식사 쿨다운에 들어간다. 두 포식자가 같은 개체를 고르면 사망은 1건, 쿨다운은 둘 다다.
	TSet<FMassEntityHandle> CaughtThisTick;

	PredatorQuery.ForEachEntityChunk(Context,
		[&EntityManager, Predation, Grid, &Entries, &CaughtThisTick, Dt, CatchRadius, HideMult, EatCooldown]
		(FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TArrayView<FEcoPredatorStateFragment> States =
			Ctx.GetMutableFragmentView<FEcoPredatorStateFragment>();
		TArray<int32> Nearby;

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			FEcoPredatorStateFragment& S = States[i];
			S.EatCooldown = FMath::Max(S.EatCooldown - Dt, 0.0f);
			if (S.EatCooldown > 0.0f)
			{
				continue;   // 식사 중 — 파이썬 hunting == false
			}

			const FVector P = Transforms[i].GetTransform().GetLocation();
			// 체감 거리는 실제 거리 이상이므로 포획 반경으로 조회하면 후보가 빠지지 않는다.
			Grid->QueryRadius(P, CatchRadius, Nearby);

			int32 Best = INDEX_NONE;
			float BestPerceived = TNumericLimits<float>::Max();
			for (int32 Index : Nearby)
			{
				const FEcoNeighborEntry& E = Entries[Index];
				if (E.bPredator || !EntityManager.IsEntityValid(E.Entity))
				{
					continue;
				}
				const float Perceived =
					FVector::Dist2D(E.Location, P) * (E.bInCover ? HideMult : 1.0f);
				if (Perceived > CatchRadius || Perceived >= BestPerceived)
				{
					continue;
				}
				// 이번 틱에 다른 포식자가 잡은 개체도 최근접 후보로 남긴다(파이썬 argmin 과 같다).
				// 그 밖에 HP 가 0인 개체는 다른 피해 경로로 죽은 것이라 건너뛴다.
				if (!CaughtThisTick.Contains(E.Entity))
				{
					const FEcoVitalsFragment* V = EntityManager.GetFragmentDataPtr<FEcoVitalsFragment>(E.Entity);
					if (!V || V->HP <= 0.0f)
					{
						continue;
					}
				}
				Best = Index;
				BestPerceived = Perceived;
			}
			if (Best == INDEX_NONE)
			{
				continue;
			}

			// 잡혔다. 파이썬은 슬롯을 즉시 리스폰하지만(§4.3) 여기서는 HP=0 + Alive→PendingDeath
			// (지연)로 표시만 하고 생명주기는 Lifecycle 계층에 맡긴다 — 이 프로세서의 책임은
			// **판정과 피식 보고**다 (§9.6). 테스트 레벨에서는 AEcoPolicyTestSpawner 가 리스폰을 대신한다.
			const FMassEntityHandle Victim = Entries[Best].Entity;
			if (!CaughtThisTick.Contains(Victim))
			{
				MarkPredationKill(Ctx.Defer(),
								  EntityManager.GetFragmentDataChecked<FEcoVitalsFragment>(Victim), Victim);
				Predation->ReportPredation(Entries[Best].Location);
				CaughtThisTick.Add(Victim);
			}
			S.EatCooldown = EatCooldown;   // 같은 개체를 고른 포식자도 쿨다운에 들어간다
		}
	});

	// --- §9.6 스텝 경계: 포획 → EMA. 관측은 다음 틱부터의 정책 결정이 읽는다 ---
	// 분모(개수)와 분자(포획)를 만드는 이 프로세서가 스텝도 닫는다. 정책 프로세서가 빠지거나
	// 정책 대상이 없어도 피식 기록이 멈추지 않는다. StepSeconds 마다, 시간 기준이다.
	// 큰 프레임이면 여러 스텝을 돈다 — 첫 스텝이 쌓인 사망을 반영하고 나머지는 감쇠만 한다.
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	const int32 Steps = EcoPolicy::ConsumeSteps(
		EmaPhase, StepClock.Advance(Dt, EcoBehaviorConfig::StepSeconds, Interval), Interval);
	for (int32 s = 0; s < Steps; ++s)
	{
		Predation->Tick();
	}
}

// -----------------------------------------------------------------------------
// UEcoSteeringProcessor  (§9.5)
// -----------------------------------------------------------------------------

UEcoSteeringProcessor::UEcoSteeringProcessor()
	: EntityQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server
									  | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPolicyProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoSteeringProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	// Transform 은 ReadWrite 다 — 이 프로세서가 속도를 위치에 적분하고 yaw 도 쓴다. 이유는 Execute 참조.
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoSteeringGeometryFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
}

void UEcoSteeringProcessor::Execute(FMassEntityManager& EntityManager,
									FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	const UEcoDummyWorldProviderSubsystem* Dummy =
		World ? World->GetSubsystem<UEcoDummyWorldProviderSubsystem>() : nullptr;
	const float WorldExtent = Dummy ? Dummy->WorldExtent : 0.0f;

	const float SeeRadius = EcoBehaviorConfig::SeeRadiusCm;
	const float SepWeight = EcoBehaviorConfig::SepWeight;
	const float FleeWeight = EcoBehaviorConfig::FleeWeight;
	const float HerbSpeed = EcoBehaviorConfig::HerbSpeedCmS;
	const float DeltaSeconds = Context.GetDeltaTimeSeconds();

	EntityQuery.ForEachEntityChunk(Context,
		[SeeRadius, SepWeight, FleeWeight, HerbSpeed, WorldExtent, DeltaSeconds]
		(FMassExecutionContext& Ctx)
	{
		const TArrayView<FTransformFragment> Transforms =
			Ctx.GetMutableFragmentView<FTransformFragment>();
		const TConstArrayView<FEcoSteeringGeometryFragment> Geometries =
			Ctx.GetFragmentView<FEcoSteeringGeometryFragment>();
		const TConstArrayView<FEcoPolicyOutputFragment> Outputs =
			Ctx.GetFragmentView<FEcoPolicyOutputFragment>();
		const TArrayView<FMassVelocityFragment> Velocities =
			Ctx.GetMutableFragmentView<FMassVelocityFragment>();

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const FEcoSteeringGeometryFragment& G = Geometries[i];
			const FEcoPolicyActionV1& P = Outputs[i].Action;

			// ===== §3.3 — EcoSteering.h 의 Steer(). 파이썬 env/steering.py 와 대응 =====
			// 수식을 여기 인라인으로 두면 테스트할 수 없어서 함수로 뺐다 (§9.8-2).
			EcoPolicy::FSteerInput In;
			In.FoodGrad[0] = G.FoodGrad.X;         In.FoodGrad[1] = G.FoodGrad.Y;
			In.ToCentroid[0] = G.ToCentroid.X;     In.ToCentroid[1] = G.ToCentroid.Y;
			In.ToCover[0] = G.ToCover.X;           In.ToCover[1] = G.ToCover.Y;
			In.Separation[0] = G.Separation.X;     In.Separation[1] = G.Separation.Y;
			In.AwayFromPred[0] = G.AwayFromPred.X; In.AwayFromPred[1] = G.AwayFromPred.Y;
			In.DistPredMin = G.DistPredMin;

			EcoPolicy::FSteerConfig Cfg;
			Cfg.SeeRadius = SeeRadius;
			Cfg.SepWeight = SepWeight;
			Cfg.FleeWeight = FleeWeight;
			Cfg.HerbSpeed = HerbSpeed;

			const float Action[4] = {P.Forage, P.Cohesion, P.FleeDist, P.Cover};
			float Vel[2];
			EcoPolicy::Steer(In, Action, Cfg, Vel);
			FVector V(Vel[0], Vel[1], 0.0f);
			// ===== §3.3 끝. 아래는 언리얼에만 있는 항이다 =====

			// §9.5 경계 반발. 파이썬은 좌표를 clamp 해서 벽을 표현한다.
			if (WorldExtent > 0.0f)
			{
				const FVector Pos = Transforms[i].GetTransform().GetLocation();
				const float Margin = EcoBehaviorConfig::SeeRadiusCm * 0.25f;
				FVector Push = FVector::ZeroVector;
				if (Pos.X > WorldExtent - Margin)  { Push.X -= 1.0f; }
				if (Pos.X < -WorldExtent + Margin) { Push.X += 1.0f; }
				if (Pos.Y > WorldExtent - Margin)  { Push.Y -= 1.0f; }
				if (Pos.Y < -WorldExtent + Margin) { Push.Y += 1.0f; }
				if (!Push.IsNearlyZero())
				{
					// 경계에서만 방향을 섞고 속력은 그대로 유지한다.
					V = (V.GetSafeNormal() + Push * 2.0f).GetSafeNormal() * HerbSpeed;
				}
			}

			Velocities[i].Value = V;

			FTransform& T = Transforms[i].GetMutableTransform();
			// world.py `head = normalize(v) if moving else head`. 경계 반발까지 반영한 **최종 V** 로
			// 쓴다 — 지각이 읽는 값과 같아야 한다. V = 0 이면 마지막 yaw 를 유지한다.
			EcoHeading::WriteYawIfMoving(T, V);

			// §9.5 — 속도를 위치에 적분한다. 파이썬 World.step() 이 `pos += v` 를 하는 자리다.
			//
			// 엔진의 UMassApplyMovementProcessor 에 맡기지 않는 이유:
			// 그 쿼리는 FMassDesiredMovementFragment 와 FMassCodeDrivenMovementTag 를 함께
			// 요구한다. 둘을 아키타입에 넣으면 이동이 엔진의 가감속 모델을 타게 되는데,
			// §3.3 은 `normalize(v) * herb_speed` 로 **속력이 항상 일정**하다고 못박고 있어
			// 파이썬과 궤적이 어긋난다. 여기서 직접 적분하는 편이 계약에 맞는다.
			FVector NewPos = T.GetLocation() + V * DeltaSeconds;
			if (WorldExtent > 0.0f)
			{
				// 파이썬은 좌표를 월드 경계로 clamp 한다 (§4.1). 위 반발항이 그 전에
				// 방향을 돌려놓지만, 프레임이 튀면 넘어갈 수 있어 최종 clamp 를 둔다.
				NewPos.X = FMath::Clamp(NewPos.X, -WorldExtent, WorldExtent);
				NewPos.Y = FMath::Clamp(NewPos.Y, -WorldExtent, WorldExtent);
			}
			T.SetLocation(NewPos);
		}
	});
}
