#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Social/EcoSocialFragments.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"

void AEcoCreatureIntegrationSpawner::UpdateSimulationLOD()
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoCreature_SimulationLOD);
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	TArray<FVector> Viewers;
	for (auto It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
		if (const auto* PC = It->Get()) if (const APawn* Pawn = PC->GetPawn()) Viewers.Add(Pawn->GetActorLocation());
	for (const auto E : Owned)
	{
		if (EM.GetFragmentDataPtr<FEcoSpeciesAIInputFragment>(E)) continue;
		auto* Runtime = EM.GetFragmentDataPtr<FEcoPolicyRuntimeFragment>(E); if (!Runtime) continue;
		Runtime->DecisionIntervalMultiplier = 1.f;
		if (!bEnableSimulationLOD || Viewers.IsEmpty()) continue;
		const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(E);
		const auto* Geometry = EM.GetFragmentDataPtr<FEcoSteeringGeometryFragment>(E);
		const auto* Request = EM.GetFragmentDataPtr<FEcoSocialMovementRequestFragment>(E);
		const auto* Alarm = EM.GetFragmentDataPtr<FEcoAlarmStateFragment>(E);
		if (V.HP <= 0 || Travel.State != EEcoResidenceState::Resident || (Geometry && Geometry->PredatorCount > 0)
			|| (Alarm && Alarm->AlarmStrength > 0.01f)
			|| (Request && Request->bValid && Request->ReservationId > 0)) continue;
		const FVector P = EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
		double Closest = TNumericLimits<double>::Max();
		for (const auto& Viewer : Viewers) Closest = FMath::Min(Closest, FVector::DistSquared(P, Viewer));
		if (Closest > FMath::Square(FarSimulationDistance)) Runtime->DecisionIntervalMultiplier = FarPolicyIntervalMultiplier;
	}
}
