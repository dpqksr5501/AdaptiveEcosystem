#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "UObject/ConstructorHelpers.h"
#include "Animation/BlendSpace.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "HAL/IConsoleManager.h"
#include "DrawDebugHelpers.h"

static TAutoConsoleVariable<int32> CVarEcoDrawFacing(TEXT("eco.Creature.DrawFacing"), 0,
	TEXT("Draw actual velocity (green) and calibrated mesh forward (cyan). Visual-only."));
static TAutoConsoleVariable<int32> CVarEcoFacingAudit(TEXT("eco.Creature.FacingAudit"), 0,
	TEXT("Log moving representation facing error once per second, including client proxies."));

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
	if (VisualMesh) { CreatureMesh->SetSkeletalMesh(VisualMesh); }
	CreatureMesh->SetRelativeRotation(MeshRotation);
	UpdateAnimation();
	PlaceholderBody->SetVisibility(CreatureMesh->GetSkeletalMeshAsset() == nullptr);
	IdentityLabel->SetText(FText::FromString(bBound ? FString::Printf(TEXT("%s #%lld"), *VisualSpeciesId.ToString(), VisualState.StableAgentId)
		: VisualSpeciesId.ToString() + TEXT(" (unbound)")));
}

bool AEcoCreatureRepresentationActor::BindIdentity(int64 AgentId, FName SpeciesId)
{
	if (AgentId <= 0 || SpeciesId != VisualSpeciesId || bBound) { return false; }
	VisualState = {};
	VisualTurnAmount = DirectionDegrees = 0.0f;
	LastFacingAuditTime = -1.0;
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
	VisualTurnAmount = DirectionDegrees = 0.0f;
	LastFacingAuditTime = -1.0;
	VisualMotion = EEcoCreatureVisualMotion::Idle;
	SetActorHiddenInGame(true);
	RefreshAppearance();
}

FVector AEcoCreatureRepresentationActor::GetVelocity() const
{
	return bBound && VisualState.bAlive ? VisualState.Velocity : FVector::ZeroVector;
}

FVector AEcoCreatureRepresentationActor::GetVisualForwardDirection() const
{
	return CreatureMesh->GetComponentTransform().TransformVectorNoScale(MeshForwardAxis).GetSafeNormal2D();
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
	const float PreviousYaw = Facing.Yaw;
	DirectionDegrees = 0.0f;
	if (Speed > FMath::Max(0.0f, IdleSpeed))
	{
		const FRotator Desired(0, State.Velocity.Rotation().Yaw, 0);
		Facing = bSnap ? Desired : FMath::RInterpTo(Facing, Desired, DeltaSeconds, FMath::Max(0.0f, TurnInterpolationSpeed));
		// Presentation may smooth small turns, but must never slide sideways/backwards
		// for several frames after a sudden logical turn. No Mass state is changed.
		const float Lag = FMath::Clamp(FMath::FindDeltaAngleDegrees(Desired.Yaw, Facing.Yaw),
			-FMath::Clamp(MaxFacingLagDegrees, 0.0f, 45.0f), FMath::Clamp(MaxFacingLagDegrees, 0.0f, 45.0f));
		Facing = FRotator(0, FRotator::NormalizeAxis(Desired.Yaw + Lag), 0);
		DirectionDegrees = FMath::FindDeltaAngleDegrees(Facing.Yaw, Desired.Yaw);
	}
	const bool bContinuousTurn = !bSnap && State.bAlive && VisualState.bAlive
		&& Speed > IdleSpeed && VisualState.Velocity.Size2D() > IdleSpeed
		&& DeltaSeconds > SMALL_NUMBER && DeltaSeconds <= 0.5f;
	const float TurnTarget = bContinuousTurn ? FMath::Clamp(
		FMath::FindDeltaAngleDegrees(PreviousYaw, Facing.Yaw) / DeltaSeconds / FMath::Max(1.0f, FullTurnRateDegrees), -1.0f, 1.0f) : 0.0f;
	VisualTurnAmount = bContinuousTurn ? FMath::FInterpTo(VisualTurnAmount, TurnTarget, DeltaSeconds, 8.0f) : 0.0f;
	// Moves this passive visual Actor only. Never modifies a Mass fragment or evaluates behavior.
	SetActorLocationAndRotation(State.Position, Facing, false, nullptr, ETeleportType::TeleportPhysics);
	VisualState = State;
	PlaceholderBody->SetVisibility(CreatureMesh->GetSkeletalMeshAsset() == nullptr);
	VisualMotion = !State.bAlive ? EEcoCreatureVisualMotion::Dead
		: State.bEating && Speed <= FMath::Max(0.0f, IdleSpeed) ? EEcoCreatureVisualMotion::Eating
		: Speed <= FMath::Max(0.0f, IdleSpeed) ? EEcoCreatureVisualMotion::Idle
		: Speed >= FMath::Max(IdleSpeed + 1.0f, RunSpeed) ? EEcoCreatureVisualMotion::Run : EEcoCreatureVisualMotion::Walk;
	UpdateAnimation();
	if (Speed > IdleSpeed && CVarEcoDrawFacing.GetValueOnGameThread())
	{
		const FVector P = State.Position + FVector(0, 0, 140);
		DrawDebugDirectionalArrow(GetWorld(), P, P + State.Velocity.GetSafeNormal2D() * 220, 35, FColor::Green, false, 0, 0, 3);
		DrawDebugDirectionalArrow(GetWorld(), P + FVector(0, 0, 15), P + FVector(0, 0, 15) + GetVisualForwardDirection() * 220, 35, FColor::Cyan, false, 0, 0, 3);
	}
	if (Speed > IdleSpeed && CVarEcoFacingAudit.GetValueOnGameThread() && State.WorldTime - LastFacingAuditTime >= 1.0)
	{
		LastFacingAuditTime = State.WorldTime;
		UE_LOG(LogTemp, Log, TEXT("[Eco Facing] NetMode=%d Id=%lld Species=%s Speed=%.1f Error=%.2f Turn=%.3f"),
			int32(GetNetMode()), State.StableAgentId, *State.SpeciesId.ToString(), Speed,
			FMath::Abs(FMath::FindDeltaAngleDegrees(GetVisualForwardDirection().Rotation().Yaw, State.Velocity.Rotation().Yaw)), VisualTurnAmount);
	}
	OnVisualStateUpdated();
	return true;
}

void AEcoCreatureRepresentationActor::UpdateAnimation()
{
	if (!LocomotionBlendSpace || !CreatureMesh->GetSkeletalMeshAsset()) return;
	UAnimationAsset* Desired = VisualMotion == EEcoCreatureVisualMotion::Dead && DeathAnimation
		? static_cast<UAnimationAsset*>(DeathAnimation.Get()) : static_cast<UAnimationAsset*>(LocomotionBlendSpace.Get());
	if (!CreatureMesh->GetSingleNodeInstance() || CreatureMesh->GetSingleNodeInstance()->GetCurrentAsset() != Desired)
	{
		CreatureMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
		CreatureMesh->PlayAnimation(Desired, Desired == LocomotionBlendSpace);
		if (auto* Node = CreatureMesh->GetSingleNodeInstance()) Node->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
	}
	if (auto* Node = CreatureMesh->GetSingleNodeInstance())
		Node->SetBlendSpacePosition(FVector(VisualState.bAlive ? VisualState.Velocity.Size2D() : 0, VisualTurnAmount, 0));
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
