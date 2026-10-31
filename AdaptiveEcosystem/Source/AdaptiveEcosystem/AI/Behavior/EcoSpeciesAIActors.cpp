#include "AI/Behavior/EcoSpeciesAIActors.h"
#include "Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h"
#include "SmartObjectComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"
AEcoSpeciesAIActivitySite::AEcoSpeciesAIActivitySite()
{ SmartObject=CreateDefaultSubobject<USmartObjectComponent>(TEXT("SmartObject"));SetRootComponent(SmartObject); }
void AEcoSpeciesAIActivitySite::BeginPlay()
{Super::BeginPlay();if(auto* S=GetWorld()->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>())S->RegisterSite(*this);}
void AEcoSpeciesAIActivitySite::EndPlay(EEndPlayReason::Type R)
{if(auto* S=GetWorld()->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>())S->UnregisterSite(*this);Super::EndPlay(R);}
AEcoSpeciesAIFixture::AEcoSpeciesAIFixture()
{SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));PrimaryActorTick.bCanEverTick=true;}
void AEcoSpeciesAIFixture::BeginPlay()
{
    Super::BeginPlay();Origin=GetActorLocation();StartTime=GetWorld()->GetTimeSeconds();
    if(auto* S=GetWorld()->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>())FixtureId=S->RegisterFixture(*this);
}
void AEcoSpeciesAIFixture::Tick(float Delta)
{
    Super::Tick(Delta);
    if(GetNetMode()==NM_Client||!FMath::IsFinite(PeriodSeconds)||PeriodSeconds<=0||!FMath::IsFinite(MotionRadius))return;
    const double A=(GetWorld()->GetTimeSeconds()-StartTime)*2*PI/PeriodSeconds;
    SetActorLocation(Origin+FVector(FMath::Cos(A)-1,FMath::Sin(A),0)*FMath::Max(0.f,MotionRadius));
}
bool AEcoSpeciesAIFixture::TryCapture(double Now)
{
    if(!IsAvailable(Now)||!bPrey||!FMath::IsFinite(RespawnSeconds)||RespawnSeconds<=0)return false;
    CapturedUntil=Now+RespawnSeconds;return true;
}
void AEcoSpeciesAIFixture::EndPlay(EEndPlayReason::Type R)
{if(auto* S=GetWorld()->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>())S->UnregisterFixture(*this);Super::EndPlay(R);}
