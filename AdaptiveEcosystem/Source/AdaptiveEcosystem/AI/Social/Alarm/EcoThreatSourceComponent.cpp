#include "AI/Social/Alarm/EcoThreatSourceComponent.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

UEcoThreatSourceComponent::UEcoThreatSourceComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	bAutoActivate = true;
}

void UEcoThreatSourceComponent::BeginPlay()
{
	Super::BeginPlay();
	if (GetOwner() && GetOwner()->HasAuthority())
	{
		if (UEcoHerdSubsystem* Herds = GetWorld()->GetSubsystem<UEcoHerdSubsystem>())
		{
			Herds->RegisterThreatSource(*this);
		}
	}
}

void UEcoThreatSourceComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UWorld* World = GetWorld())
	{
		if (UEcoHerdSubsystem* Herds = World->GetSubsystem<UEcoHerdSubsystem>())
		{
			Herds->UnregisterThreatSource(*this);
		}
	}
	Super::EndPlay(EndPlayReason);
}
