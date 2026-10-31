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
#include "EcoSteering.h"
#include "EcoWorldProviders.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"

UEcoSteeringProcessor::UEcoSteeringProcessor()
	: EntityQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server
									  | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPolicyProcessor"));
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoShelterLifecycleProcessor"));
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
	EntityQuery.AddTagRequirement<FEcoGroundedNavigationTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
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
			}
			if (!Integrated && WorldExtent > 0.0f)
			{
				// 파이썬은 좌표를 월드 경계로 clamp 한다 (§4.1). 위 반발항이 그 전에
				// 방향을 돌려놓지만, 프레임이 튀면 넘어갈 수 있어 최종 clamp 를 둔다.
				NewPos.X = FMath::Clamp(NewPos.X, -WorldExtent, WorldExtent);
				NewPos.Y = FMath::Clamp(NewPos.Y, -WorldExtent, WorldExtent);
			}
			T.SetLocation(NewPos);
			if (!V.IsNearlyZero()) T.SetRotation(V.ToOrientationQuat());
			Velocities[i].Value = V;
		}
	});
}
