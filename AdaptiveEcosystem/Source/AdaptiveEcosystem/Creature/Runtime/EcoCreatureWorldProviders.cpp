#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "World/EcologyRegion.h"

AEcologyRegion* AEcoCreatureIntegrationSpawner::FindRegion(const FVector& Position) const
{
	for (AEcologyRegion* Region : Regions) if (Region && Region->ContainsPosition(Position)) return Region;
	return nullptr;
}

float AEcoCreatureIntegrationSpawner::GetFoodDensity(const FVector& Position, float Radius) const
{
	const auto* Region = FindRegion(Position);
	const auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	FRegionEcologyState State;
	if (!Region || !Ecology || !Ecology->GetRegionState(Region->RegionId, State) || State.FoodCapacity <= 0) return 0;
	const auto* Group = Groups.FindByPredicate([&](const FEcoCreatureSpawnGroup& G) { return G.RegionId == Region->RegionId; });
	const FVector Patch = Group && Group->bUseFoodPatchPosition ? Group->FoodPatchPosition : Region->GetActorLocation() + FVector(1000, 1000, 0);
	return FMath::Clamp(State.FoodAmount / State.FoodCapacity, 0.f, 1.f)
		* (0.3f + 0.7f * FMath::Exp(-FVector::DistSquared2D(Position, Patch) / FMath::Square(2500.f)));
}
FVector AEcoCreatureIntegrationSpawner::GetFoodGradient(const FVector& P, float Radius) const
{
	const float H = FMath::Max(100.f, Radius * 0.2f);
	return FVector(GetFoodDensity(P + FVector(H,0,0), H) - GetFoodDensity(P - FVector(H,0,0), H),
		GetFoodDensity(P + FVector(0,H,0), H) - GetFoodDensity(P - FVector(0,H,0), H), 0).GetSafeNormal();
}
float AEcoCreatureIntegrationSpawner::ConsumeFood(const FVector&, float)
{
	// Mutation is exclusively the sorted, batched resource transaction in Reconcile.
	return 0;
}
float AEcoCreatureIntegrationSpawner::GetRecentPredation(const FVector& P) const
{
	const auto* Region = FindRegion(P); const auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	return Region && Ecology ? Ecology->GetPredationHistory(Region->RegionId) : 0;
}
float AEcoCreatureIntegrationSpawner::GetCoverDistance(const FVector& P) const
{
	float Best = MAX_flt;
	if (auto* Shelters = GetWorld()->GetSubsystem<UEcoShelterSubsystem>())
		for (const auto& S : Shelters->GetShelters()) if (Shelters->IsValidShelterIndex(S.RuntimeIndex)) Best = FMath::Min(Best, float(FVector::Dist2D(P, S.Position) - S.Radius));
	return FMath::Max(0.f, Best);
}
FVector AEcoCreatureIntegrationSpawner::GetCoverDirection(const FVector& P) const
{
	float Best = MAX_flt; FVector Dir = FVector::ZeroVector;
	if (auto* Shelters = GetWorld()->GetSubsystem<UEcoShelterSubsystem>())
		for (const auto& S : Shelters->GetShelters()) if (Shelters->IsValidShelterIndex(S.RuntimeIndex))
		{ const float D = FVector::Dist2D(P, S.Position) - S.Radius; if (D < Best) { Best = D; Dir = S.Position - P; } }
	return Best <= 0 ? FVector::ZeroVector : Dir.GetSafeNormal2D();
}
bool AEcoCreatureIntegrationSpawner::IsInCover(const FVector& P) const { return GetCoverDistance(P) <= 0; }
