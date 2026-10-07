#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "UObject/ConstructorHelpers.h"

bool FEcoCreatureVisualState::IsValid() const
{
	return StableAgentId > 0 && !SpeciesId.IsNone() && Sequence > 0 && FMath::IsFinite(WorldTime) && WorldTime >= 0.0
		&& !Position.ContainsNaN() && !Velocity.ContainsNaN()
		&& FMath::IsFinite(NormalizedHealth) && NormalizedHealth >= 0.0f && NormalizedHealth <= 1.0f
		&& FMath::IsFinite(NormalizedEnergy) && NormalizedEnergy >= 0.0f && NormalizedEnergy <= 1.0f;
}

AEcoCreatureRepresentationActor::AEcoCreatureRepresentationActor()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = false; // The eventual production transport remains the existing Mass network path.
	SetReplicateMovement(false);
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("VisualRoot")));
	CreatureMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("CreatureMesh"));
	CreatureMesh->SetupAttachment(RootComponent);
	CreatureMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	CreatureMesh->SetGenerateOverlapEvents(false);
	CreatureMesh->SetAnimInstanceClass(UEcoCreatureAnimInstance::StaticClass());
	PlaceholderBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderBody"));
	PlaceholderBody->SetupAttachment(RootComponent);
	PlaceholderBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	PlaceholderBody->SetGenerateOverlapEvents(false);
	PlaceholderBody->SetRelativeLocation(FVector(0, 0, 75));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (Cube.Succeeded()) { PlaceholderBody->SetStaticMesh(Cube.Object); }
	IdentityLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("IdentityLabel"));
	IdentityLabel->SetupAttachment(RootComponent);
	IdentityLabel->SetRelativeLocation(FVector(0, 0, 200));
	IdentityLabel->SetWorldSize(55);
	IdentityLabel->SetHorizontalAlignment(EHTA_Center);
}

void AEcoCreatureRepresentationActor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	RefreshAppearance();
}

void AEcoCreatureRepresentationActor::BeginPlay()
{
	Super::BeginPlay();
	RefreshAppearance();
}

void AEcoCreatureRepresentationActor::RefreshAppearance()
{
	PlaceholderBody->SetVisibility(CreatureMesh->GetSkeletalMeshAsset() == nullptr);
	IdentityLabel->SetText(FText::FromString(bBound ? FString::Printf(TEXT("%s #%lld"), *VisualSpeciesId.ToString(), VisualState.StableAgentId)
		: VisualSpeciesId.ToString() + TEXT(" (unbound)")));
}

bool AEcoCreatureRepresentationActor::BindIdentity(int64 AgentId, FName SpeciesId)
{
	if (AgentId <= 0 || SpeciesId != VisualSpeciesId || bBound) { return false; }
	VisualState = {};
	VisualState.StableAgentId = AgentId;
	VisualState.SpeciesId = SpeciesId;
	bBound = true;
	SetActorHiddenInGame(false);
	RefreshAppearance();
	return true;
}

void AEcoCreatureRepresentationActor::ClearBinding()
{
	bBound = false;
	VisualState = {};
	VisualMotion = EEcoCreatureVisualMotion::Idle;
	SetActorHiddenInGame(true);
	RefreshAppearance();
}

FVector AEcoCreatureRepresentationActor::GetVelocity() const
{
	return bBound && VisualState.bAlive ? VisualState.Velocity : FVector::ZeroVector;
}

bool AEcoCreatureRepresentationActor::ConsumeVisualState(const FEcoCreatureVisualState& State, float DeltaSeconds)
{
	if (!bBound || !State.IsValid() || State.StableAgentId != VisualState.StableAgentId || State.SpeciesId != VisualState.SpeciesId
		|| State.Sequence <= VisualState.Sequence || State.WorldTime < VisualState.WorldTime
		|| !FMath::IsFinite(DeltaSeconds) || DeltaSeconds < 0.0f) { return false; }
	const bool bSnap = VisualState.Sequence == 0 || State.bDiscontinuity
		|| FVector::DistSquared(GetActorLocation(), State.Position) > FMath::Square(FMath::Max(1.0f, TeleportDistance));
	const float Speed = State.bAlive ? State.Velocity.Size2D() : 0.0f;
	FRotator Facing = GetActorRotation();
	if (Speed > FMath::Max(0.0f, IdleSpeed))
	{
		const FRotator Desired(0, State.Velocity.Rotation().Yaw, 0);
		Facing = bSnap ? Desired : FMath::RInterpTo(Facing, Desired, DeltaSeconds, FMath::Max(0.0f, TurnInterpolationSpeed));
	}
	// Moves this passive visual Actor only. Never modifies a Mass fragment or evaluates behavior.
	SetActorLocationAndRotation(State.Position, Facing, false, nullptr, ETeleportType::TeleportPhysics);
	VisualState = State;
	PlaceholderBody->SetVisibility(CreatureMesh->GetSkeletalMeshAsset() == nullptr);
	VisualMotion = !State.bAlive ? EEcoCreatureVisualMotion::Dead
		: State.bEating && Speed <= FMath::Max(0.0f, IdleSpeed) ? EEcoCreatureVisualMotion::Eating
		: Speed <= FMath::Max(0.0f, IdleSpeed) ? EEcoCreatureVisualMotion::Idle
		: Speed >= FMath::Max(IdleSpeed + 1.0f, RunSpeed) ? EEcoCreatureVisualMotion::Run : EEcoCreatureVisualMotion::Walk;
	OnVisualStateUpdated();
	return true;
}

AEcoWolfRepresentation::AEcoWolfRepresentation()
{
	VisualSpeciesId = TEXT("Wolf");
	PlaceholderBody->SetRelativeScale3D(FVector(2.2f, 0.65f, 0.8f));
	IdentityLabel->SetTextRenderColor(FColor(255, 100, 80));
}

AEcoHerbivoreRepresentation::AEcoHerbivoreRepresentation()
{
	VisualSpeciesId = TEXT("Herbivore");
	PlaceholderBody->SetRelativeScale3D(FVector(1.4f, 1.0f, 1.3f));
	IdentityLabel->SetTextRenderColor(FColor(100, 255, 140));
}
