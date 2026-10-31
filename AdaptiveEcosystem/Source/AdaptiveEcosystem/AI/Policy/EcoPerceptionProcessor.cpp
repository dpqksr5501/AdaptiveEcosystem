#include "EcoBehaviorProcessors.h"
#include "EcoBehaviorConfig.h"
#include "EcoBehaviorFragments.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Engine/World.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "EcoNeighborhoodSubsystem.h"
#include "EcoWorldProviders.h"

namespace
{
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
	EntityQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoSteeringGeometryFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
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

		const auto Vitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		const auto Ids = Ctx.GetFragmentView<FEcoIdentityFragment>();
		const TArray<FEcoNeighborEntry>& Entries = Grid->GetEntries();
		TArray<int32> Nearby;

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (!Vitals.IsEmpty() && Vitals[i].HP <= 0) continue;
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

				// --- 동족: separation remains physical; species filters only kin/cohesion. ---
				if ((Ids.IsEmpty() || Other.SpeciesId.IsNone() || Other.SpeciesId == Ids[i].SpeciesId)
					&& IsInView(Self, Heading, Other.Location, CosHalfFov))
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
