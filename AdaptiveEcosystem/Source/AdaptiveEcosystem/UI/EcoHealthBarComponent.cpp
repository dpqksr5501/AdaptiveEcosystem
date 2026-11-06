#include "UI/EcoHealthBarComponent.h"
#include "UI/EcoHealthBarWidget.h"
#include "Engine/World.h"

UEcoHealthBarComponent::UEcoHealthBarComponent()
{
	SetWidgetSpace(EWidgetSpace::Screen);
	SetWidgetClass(UEcoHealthBarWidget::StaticClass());
	SetDrawSize(FVector2D(112, 18));
	SetPivot(FVector2D(.5f, 1.f));
	SetRelativeLocation(FVector(0, 0, 185));
	SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SetGenerateOverlapEvents(false);
	SetIsReplicatedByDefault(false);
	SetVisibility(false);
}

void UEcoHealthBarComponent::BeginPlay()
{
	Super::BeginPlay();
	if (GetNetMode() == NM_DedicatedServer)
	{
		SetVisibility(false);
		SetComponentTickEnabled(false);
	}
}

void UEcoHealthBarComponent::InitWidget()
{
	if (GetWorld() && GetNetMode() == NM_DedicatedServer) return;
	Super::InitWidget();
	if (auto* Bar = Cast<UEcoHealthBarWidget>(GetUserWidgetObject()))
	{
		Bar->SetVisibility(ESlateVisibility::HitTestInvisible);
		Bar->SetHealthFraction(HealthFraction);
	}
}

void UEcoHealthBarComponent::SetHealthNormalized(float Fraction, bool bAlive, bool bHasHealth)
{
	bHasHealthSample = bHasHealth && FMath::IsFinite(Fraction);
	HealthFraction = bHasHealthSample && bAlive ? FMath::Clamp(Fraction, 0.f, 1.f) : 0.f;
	SetVisibility(bHasHealthSample && GetNetMode() != NM_DedicatedServer);
	if (auto* Bar = Cast<UEcoHealthBarWidget>(GetUserWidgetObject())) Bar->SetHealthFraction(HealthFraction);
}

void UEcoHealthBarComponent::SetHealth(float CurrentHealth, float MaxHealth, bool bAlive)
{
	const bool bValid = FMath::IsFinite(CurrentHealth) && FMath::IsFinite(MaxHealth) && MaxHealth > 0.f;
	SetHealthNormalized(bValid ? CurrentHealth / MaxHealth : 0.f, bAlive, bValid);
}

void UEcoHealthBarComponent::ClearHealth()
{
	SetHealthNormalized(0.f, false, false);
}
