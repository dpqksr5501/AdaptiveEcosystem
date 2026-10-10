#include "AI/Social/Senses/EcoNoiseEmitterComponent.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundAttenuation.h"

UEcoNoiseEmitterComponent::UEcoNoiseEmitterComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.1f;
	bAutoActivate = true;
}

int64 UEcoNoiseEmitterComponent::EmitNoise(float Loudness, float MaxRange, float ThreatStrength, FName Tag)
{
	if (!IsActive() || !GetOwner() || !GetOwner()->HasAuthority() || !GetWorld()) { return 0; }
	UEcoNoiseSubsystem* Noise = GetWorld()->GetSubsystem<UEcoNoiseSubsystem>();
	return Noise ? Noise->ReportNoise(GetOwner()->GetActorLocation(), Loudness, MaxRange, ThreatStrength, GetOwner(), Tag) : 0;
}

bool UEcoNoiseEmitterComponent::PlayNoiseSound(float VolumeMultiplier)
{
	if (!IsActive() || !GetOwner() || !GetWorld() || GetWorld()->GetNetMode() == NM_DedicatedServer
		|| !NoiseSound || !FMath::IsFinite(VolumeMultiplier) || VolumeMultiplier < 0) { return false; }
	UGameplayStatics::PlaySoundAtLocation(this, NoiseSound, GetOwner()->GetActorLocation(), VolumeMultiplier,
		1.0f, 0.0f, AudioAttenuation);
	return true;
}

void UEcoNoiseEmitterComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (!bEmitMovementNoise || !GetOwner() || !GetOwner()->HasAuthority() || !FMath::IsFinite(DeltaTime)
		|| DeltaTime < 0 || !FMath::IsFinite(MinimumSpeed) || MinimumSpeed < 0
		|| !FMath::IsFinite(MovementNoiseInterval) || MovementNoiseInterval < 0.2f) { return; }
	TimeUntilNoise = FMath::Max(0.0f, TimeUntilNoise - DeltaTime);
	const float Speed = GetOwner()->GetVelocity().Size2D();
	if (!FMath::IsFinite(Speed) || Speed < MinimumSpeed) { return; }
	if (TimeUntilNoise > 0) { return; }
	EmitNoise(MovementLoudness, MovementNoiseRange, MovementThreatStrength, TEXT("Movement"));
	TimeUntilNoise = MovementNoiseInterval;
}
