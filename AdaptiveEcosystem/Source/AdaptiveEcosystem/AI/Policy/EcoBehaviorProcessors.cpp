#include "EcoBehaviorProcessors.h"

#include "EcoBehaviorConfig.h"
#include "EcoBehaviorFragments.h"
#include "EcoNeighborhoodSubsystem.h"
#include "EcoPolicyInference.h"
#include "EcoSteering.h"
#include "EcoRegionPredationSubsystem.h"
#include "EcoWorldProviders.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "AI/Social/Senses/EcoPredatorPerception.h"
#include "World/EcoWorldClockSubsystem.h"

namespace
{
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
	HerbivoreQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);

	PredatorQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	PredatorQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
	PredatorQuery.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::All);
	PredatorQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
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
		const auto Vitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FMassVelocityFragment> Velocities =
			Ctx.GetFragmentView<FMassVelocityFragment>();

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (!Vitals.IsEmpty() && Vitals[i].HP <= 0) continue;
			const FVector Location = Transforms[i].GetTransform().GetLocation();
			FEcoNeighborEntry Entry;
			Entry.Entity = Ctx.GetEntity(i);
			Entry.Location = Location;
			Entry.bPredator = bPredator;
			Entry.bInCover = Cover ? Cover->IsInCover(Location) : false;

			// 진행 방향. 정지 상태면 전방 축으로 둔다 (시야 판정이 무너지지 않게).
			const FVector V = Velocities[i].Value;
			Entry.Heading = V.SizeSquared2D() > KINDA_SMALL_NUMBER
								? FVector(V.X, V.Y, 0.0f).GetSafeNormal()
								: Transforms[i].GetTransform().GetRotation().GetForwardVector();
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
			const FVector V = Velocities[i].Value;
			const FVector Heading = V.SizeSquared2D() > KINDA_SMALL_NUMBER
				? FVector(V.X, V.Y, 0.0f).GetSafeNormal()
				: Transforms[i].GetTransform().GetRotation().GetForwardVector();

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
	UEcoRegionPredationSubsystem* Predation = World->GetSubsystem<UEcoRegionPredationSubsystem>();
	const IEcoWorldFoodProvider* Food = Registry ? Registry->GetFoodProvider() : nullptr;
	const IEcoWorldCoverProvider* Cover = Registry ? Registry->GetCoverProvider() : nullptr;

	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	const float SeeRadius = EcoBehaviorConfig::SeeRadiusCm;
	const bool bLearned = CVarUseLearnedPolicy.GetValueOnGameThread() != 0;

	EntityQuery.ForEachEntityChunk(Context,
		[Food, Cover, Predation, Interval, SeeRadius, bLearned](FMassExecutionContext& Ctx)
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
			// §9.4 "++TicksSinceUpdate < PolicyInterval 이면 skip".
			// 스폰 시 NextPolicyStep 을 0~Interval 로 흩어 두면 부하가 틱마다 고르게 퍼진다.
			FEcoPolicyRuntimeFragment& Runtime = Runtimes[i];
			if (++Runtime.LastPolicyStep < Interval)
			{
				continue;
			}
			Runtime.LastPolicyStep = 0;

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
			const float RegionalHistory = Food ? Food->GetRecentPredation(Self) : -1.f;
			Obs.RecentPredation = RegionalHistory >= 0 ? FMath::Clamp(RegionalHistory, 0.f, 1.f) : (Predation ? Predation->Get(Self) : 0.0f);
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

	// §9.6 — PolicyInterval 틱마다 지역 EMA 한 번. 개체 루프 밖이다.
	if (Predation && ++TickCounter >= Interval)
	{
		TickCounter = 0;
		Predation->Tick();
	}
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
	// 필요한 건 이번 틱 이웃 색인(게더)뿐이다. 지각 뒤에 두는 건 기존 실행 순서를 유지하려고.
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPerceptionProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoPredationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	// Vitals 는 ReadWrite 로 선언한다. 실제 쓰기는 포식자 루프에서 핸들로 하지만,
	// 선언이 있어야 Mass 가 이 프로세서가 Vitals 를 쓴다는 걸 안다.
	HerbivoreQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	HerbivoreQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadWrite);
	HerbivoreQuery.AddRequirement<FEcoCreatureLifecycleFragment>(EMassFragmentAccess::ReadWrite, EMassFragmentPresence::Optional);
	HerbivoreQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);

	PredatorQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	PredatorQuery.AddRequirement<FEcoPredatorStateFragment>(EMassFragmentAccess::ReadWrite);
    PredatorQuery.AddRequirement<FEcoPreySenseFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
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

	// --- 지역 개체 수 (§3.1 EMA 의 분모). 살아 있는 개체만 센다 ---
	HerbivoreQuery.ForEachEntityChunk(Context, [Predation](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FEcoVitalsFragment> Vitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (Vitals[i].HP > 0.0f)
			{
				Predation->ReportPopulation(Transforms[i].GetTransform().GetLocation(), 1);
			}
		}
	});

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

	PredatorQuery.ForEachEntityChunk(Context,
		[&EntityManager, Predation, Grid, World, &Entries, Dt, CatchRadius, HideMult, EatCooldown]
		(FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TArrayView<FEcoPredatorStateFragment> States =
			Ctx.GetMutableFragmentView<FEcoPredatorStateFragment>();
		TArray<int32> Nearby;
        const auto PreySenses = Ctx.GetFragmentView<FEcoPreySenseFragment>();

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
                // Opt-in Creature wolves require fresh direct sight, plus current LOS at contact.
                // Legacy/Python-parity predator archetypes have no PreySense and keep their V1 rule.
                if (!PreySenses.IsEmpty())
                {
                    const auto& Sense = PreySenses[i];
                    if (Sense.Target != E.Entity || Sense.Cue.LastDirectSense != EEcoSenseSource::Sight
                        || Sense.Cue.Confidence <= 0 || World->GetTimeSeconds() < Sense.Cue.LastObservedTime
                        || World->GetTimeSeconds() - Sense.Cue.LastObservedTime > .25) continue;
                    FHitResult Hit; FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoCreatureCaptureLOS), true);
                    if (World->LineTraceSingleByChannel(Hit, P + FVector(0,0,80), E.Location + FVector(0,0,80), ECC_Visibility, Params)) continue;
                }
				if (Perceived > CatchRadius || Perceived >= BestPerceived)
				{
					continue;
				}
				// 같은 틱에 다른 포식자가 먼저 잡았을 수 있다.
				const FEcoVitalsFragment* V = EntityManager.GetFragmentDataPtr<FEcoVitalsFragment>(E.Entity);
				if (!V || V->HP <= 0.0f)
				{
					continue;
				}
				Best = Index;
				BestPerceived = Perceived;
			}
			if (Best == INDEX_NONE)
			{
				continue;
			}

			// 잡혔다. 파이썬은 슬롯을 즉시 리스폰하지만(§4.3) 여기서는 HP 를 0으로 두고
			// 생명주기는 Lifecycle 계층에 맡긴다 — 이 프로세서의 책임은 **판정과 지역 보고**다
			// (§9.6). 테스트 레벨에서는 AEcoPolicyTestSpawner 가 리스폰을 대신한다.
			EntityManager.GetFragmentDataChecked<FEcoVitalsFragment>(Entries[Best].Entity).HP = 0.0f;
			if (auto* Life = EntityManager.GetFragmentDataPtr<FEcoCreatureLifecycleFragment>(Entries[Best].Entity)) Life->bPredated = true;
			Predation->ReportPredation(Entries[Best].Location);
			S.EatCooldown = EatCooldown;
		}
	});
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
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoShelterLifecycleProcessor"));
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPredationProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoSteeringProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoSocialMovementRequestFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoShelterMovementFeedbackFragment>(EMassFragmentAccess::ReadWrite, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	// Transform 은 ReadWrite 다 — 이 프로세서가 속도를 위치에 적분까지 한다. 이유는 Execute 참조.
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoSteeringGeometryFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
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
	if (!World || !FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0) return;
	// Lease expiry uses the same World-time domain as the Social lifecycle.
	const double Now = World->GetTimeSeconds();

	EntityQuery.ForEachEntityChunk(Context,
		[World, Now, SeeRadius, SepWeight, FleeWeight, HerbSpeed, WorldExtent, DeltaSeconds]
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
		const auto Requests = Ctx.GetFragmentView<FEcoSocialMovementRequestFragment>();
		const auto Feedback = Ctx.GetMutableFragmentView<FEcoShelterMovementFeedbackFragment>();
		const auto Travel = Ctx.GetFragmentView<FEcoTravelFragment>();
		const auto Regions = Ctx.GetFragmentView<FEcoRegionFragment>();
		const auto Vitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		const bool Integrated = Ctx.DoesArchetypeHaveTag<FEcoIntegratedCreatureTag>();

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const FEcoSteeringGeometryFragment& G = Geometries[i];
			if (!Vitals.IsEmpty() && Vitals[i].HP <= 0) { Velocities[i].Value = FVector::ZeroVector; continue; }
			const auto* Request = Requests.IsEmpty() ? nullptr : &Requests[i];
			auto* Result = Feedback.IsEmpty() ? nullptr : &Feedback[i];
			const auto* Residence = Travel.IsEmpty() ? nullptr : &Travel[i];
			const FEcoPolicyActionV1& P = Request && Request->bValid ? Request->EffectiveAction : Outputs[i].Action;

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
			if (!Integrated && WorldExtent > 0.0f)
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

			// §9.5 — 속도를 위치에 적분한다. 파이썬 World.step() 이 `pos += v` 를 하는 자리다.
			//
			// 엔진의 UMassApplyMovementProcessor 에 맡기지 않는 이유:
			// 그 쿼리는 FMassDesiredMovementFragment 와 FMassCodeDrivenMovementTag 를 함께
			// 요구한다. 둘을 아키타입에 넣으면 이동이 엔진의 가감속 모델을 타게 되는데,
			// §3.3 은 `normalize(v) * herb_speed` 로 **속력이 항상 일정**하다고 못박고 있어
			// 파이썬과 궤적이 어긋난다. 여기서 직접 적분하는 편이 계약에 맞는다.
			FTransform& T = Transforms[i].GetMutableTransform();
			V = EcoCreatureMovement::SelectVelocity(T.GetLocation(), V, HerbSpeed, DeltaSeconds, Now, Residence, Request, Result);
			FVector NewPos = T.GetLocation() + V * DeltaSeconds;
			if (Integrated && World && !Regions.IsEmpty())
			{
				if (!EcoCreatureMovement::ConstrainStep(*World, Regions[i].CurrentRegionId, Residence && Residence->State == EEcoResidenceState::Traveling, T.GetLocation(), NewPos))
				{
					NewPos = T.GetLocation(); V = FVector::ZeroVector;
					if (Request && Request->bValid && Request->ReservationId > 0 && Result) Result->Report(Request->ReservationId, EEcoShelterMovementStatus::Failed);
				}
				if (!V.IsNearlyZero()) T.SetRotation(V.ToOrientationQuat());
			}
			if (!Integrated && WorldExtent > 0.0f)
			{
				// 파이썬은 좌표를 월드 경계로 clamp 한다 (§4.1). 위 반발항이 그 전에
				// 방향을 돌려놓지만, 프레임이 튀면 넘어갈 수 있어 최종 clamp 를 둔다.
				NewPos.X = FMath::Clamp(NewPos.X, -WorldExtent, WorldExtent);
				NewPos.Y = FMath::Clamp(NewPos.Y, -WorldExtent, WorldExtent);
			}
			T.SetLocation(NewPos);
			Velocities[i].Value = V;
		}
	});
}
