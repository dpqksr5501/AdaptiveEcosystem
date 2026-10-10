#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"

void UEcoCreatureAnimInstance::NativeInitializeAnimation()
{
	Super::NativeInitializeAnimation();
	SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
}

void UEcoCreatureAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);
	const auto* Visual = Cast<AEcoCreatureRepresentationActor>(GetOwningActor());
	bAlive = Visual && Visual->bBound && Visual->VisualState.bAlive;
	SpeedCmPerSecond = bAlive ? Visual->VisualState.Velocity.Size2D() : 0.0f;
	DirectionDegrees = bAlive ? Visual->DirectionDegrees : 0.0f;
	TurnAmount = bAlive ? Visual->VisualTurnAmount : 0.0f;
	bEating = bAlive && Visual->VisualState.bEating;
	bPursuingPrey = bAlive && Visual->VisualState.bPursuingPrey;
	VisualMotion = Visual && Visual->bBound ? Visual->VisualMotion : EEcoCreatureVisualMotion::Idle;
}
