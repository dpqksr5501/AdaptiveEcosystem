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
			Obs.RecentPredation = Predation ? Predation->Get(Self) : 0.0f;
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
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
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

	EntityQuery.ForEachEntityChunk(Context,
		[SeeRadius, SepWeight, FleeWeight, HerbSpeed, WorldExtent](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
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
		}
	});
}
