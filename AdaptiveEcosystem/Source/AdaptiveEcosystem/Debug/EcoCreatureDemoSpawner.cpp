#include "Debug/EcoCreatureDemoSpawner.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoWorldProviders.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntitySubsystem.h"
#include "MassMovementFragments.h"
#include "Engine/World.h"

AEcoCreatureDemoSpawner::AEcoCreatureDemoSpawner()
{
	HerbivoreCount = 8;
	PredatorCount = 1;
	SpawnRadius = 2500.0f;
	bDrawDebug = false;
	bAssignStableAgentIds = true;
	WolfActorClass = AEcoWolfRepresentation::StaticClass();
	HerbivoreActorClass = AEcoHerbivoreRepresentation::StaticClass();
}

void AEcoCreatureDemoSpawner::BeginPlay()
{
	const auto* Dummy = GetWorld() ? GetWorld()->GetSubsystem<UEcoDummyWorldProviderSubsystem>() : nullptr;
	const auto ValidClass = [](UClass* Class, FName Species)
	{
		return Class && !Class->HasAnyClassFlags(CLASS_Abstract)
			&& Class->GetDefaultObject<AEcoCreatureRepresentationActor>()->VisualSpeciesId == Species;
	};
	if (!GetWorld() || GetWorld()->GetNetMode() != NM_Standalone || !Dummy
		|| HerbivoreCount < 1 || PredatorCount < 0 || HerbivoreCount + int64(PredatorCount) > 128
		|| !FMath::IsFinite(SpawnRadius) || SpawnRadius <= 0.0f || SpawnRadius > Dummy->WorldExtent
		|| !FMath::IsFinite(PredatorSpeedRatio) || PredatorSpeedRatio < 0.0f
		|| !GetActorLocation().IsNearlyZero(1.0f)
		|| !ValidClass(WolfActorClass, TEXT("Wolf")) || !ValidClass(HerbivoreActorClass, TEXT("Herbivore")))
	{
		AActor::BeginPlay();
		UE_LOG(LogTemp, Warning, TEXT("Creature demo requires Standalone, origin=(0,0,0), valid species visual classes and <=128 animals on the dummy flat world."));
		return;
	}
	bAssignStableAgentIds = true;
	Super::BeginPlay();
	bDemoActive = GetTestHerbivores().Num() > 0;
	RebuildVisuals();
}

void AEcoCreatureDemoSpawner::DestroyVisuals()
{
	for (auto& Binding : Bindings)
	{
		if (auto* Actor = Binding.Actor.Get()) { Actor->ClearBinding(); Actor->Destroy(); }
	}
	Bindings.Reset();
}

void AEcoCreatureDemoSpawner::EndPlay(const EEndPlayReason::Type Reason)
{
	bDemoActive = false;
	DestroyVisuals();
	Super::EndPlay(Reason);
}

void AEcoCreatureDemoSpawner::RebuildVisuals()
{
	if (!bDemoActive || !GetWorld() || GetWorld()->GetNetMode() != NM_Standalone) { return; }
	DestroyVisuals();
	auto* Mass = GetWorld()->GetSubsystem<UMassEntitySubsystem>();
	if (!Mass) { return; }
	auto& EM = Mass->GetMutableEntityManager();
	auto Add = [&](TConstArrayView<FMassEntityHandle> Entities, TSubclassOf<AEcoCreatureRepresentationActor> Class, bool bPredator)
	{
		for (int32 I = 0; I < Entities.Num(); ++I)
		{
			if (!EM.IsEntityValid(Entities[I]) || !Class) { continue; }
			const auto& Identity = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entities[I]);
			const auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entities[I]).GetTransform();
			FActorSpawnParameters Params;
			Params.Owner = this;
			Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			auto* Actor = GetWorld()->SpawnActor<AEcoCreatureRepresentationActor>(Class, Transform, Params);
			if (!Actor) { continue; }
			if (!Actor->BindIdentity(Identity.StableAgentId, Identity.SpeciesId)) { Actor->Destroy(); continue; }
			auto& Binding = Bindings.AddDefaulted_GetRef();
			Binding.Entity = Entities[I]; Binding.Actor = Actor;
			Binding.bPredator = bPredator; Binding.PredatorIndex = bPredator ? I : INDEX_NONE;
		}
	};
	Add(GetTestHerbivores(), HerbivoreActorClass, false);
	Add(GetTestPredators(), WolfActorClass, true);
	SyncVisuals(0.0f);
}

void AEcoCreatureDemoSpawner::OnTestEntityReset(FMassEntityHandle Entity)
{
	for (auto& Binding : Bindings) { if (Binding.Entity == Entity) { Binding.bDiscontinuity = true; } }
}

void AEcoCreatureDemoSpawner::SyncVisuals(float DeltaSeconds)
{
	auto* Mass = GetWorld()->GetSubsystem<UMassEntitySubsystem>();
	if (!Mass) { DestroyVisuals(); return; }
	auto& EM = Mass->GetMutableEntityManager();
	for (int32 I = Bindings.Num() - 1; I >= 0; --I)
	{
		auto& Binding = Bindings[I];
		auto* Actor = Binding.Actor.Get();
		if (!Actor || !EM.IsEntityValid(Binding.Entity))
		{
			if (Actor) { Actor->ClearBinding(); Actor->Destroy(); }
			Bindings.RemoveAtSwap(I); continue;
		}
		const auto& Identity = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Binding.Entity);
		FEcoCreatureVisualState State;
		State.StableAgentId = Identity.StableAgentId; State.SpeciesId = Identity.SpeciesId;
		State.Sequence = ++Binding.Sequence; State.WorldTime = GetWorld()->GetTimeSeconds();
		State.Position = EM.GetFragmentDataChecked<FTransformFragment>(Binding.Entity).GetTransform().GetLocation();
		State.Velocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(Binding.Entity).Value;
		State.bDiscontinuity = Binding.bDiscontinuity;
		Binding.bDiscontinuity = false;
		if (Binding.bPredator)
		{
			State.bEating = EM.GetFragmentDataChecked<FEcoPredatorStateFragment>(Binding.Entity).EatCooldown > 0.0f;
			State.bPursuingPrey = GetTestPredatorTarget(Binding.PredatorIndex) != INDEX_NONE;
		}
		else
		{
			const auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Binding.Entity);
			State.bHasVitals = true;
			State.bAlive = FMath::IsFinite(Vitals.HP) && Vitals.HP > 0.0f;
			State.NormalizedHealth = Vitals.MaxHP > 0.0f ? FMath::Clamp(Vitals.HP / Vitals.MaxHP, 0.0f, 1.0f) : 0.0f;
			State.NormalizedEnergy = Vitals.MaxEnergy > 0.0f ? FMath::Clamp(Vitals.Energy / Vitals.MaxEnergy, 0.0f, 1.0f) : 0.0f;
		}
		Actor->ConsumeVisualState(State, DeltaSeconds);
	}
}

void AEcoCreatureDemoSpawner::Tick(float DeltaSeconds)
{
	if (!bDemoActive || !FMath::IsFinite(DeltaSeconds) || DeltaSeconds < 0.0f) { return; }
	Super::Tick(DeltaSeconds); // Existing predator writer, once. Herbivore writer remains PrePhysics PPO Steering.
	SyncVisuals(DeltaSeconds);
}

int32 AEcoCreatureDemoSpawner::GetRepresentedCreatureCount() const
{
	int32 Count = 0;
	for (const auto& Binding : Bindings) { Count += Binding.Actor.IsValid() ? 1 : 0; }
	return Count;
}
