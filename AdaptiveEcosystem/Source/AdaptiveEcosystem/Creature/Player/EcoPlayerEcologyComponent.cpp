#include "Creature/Player/EcoPlayerEcologyComponent.h"
#include "AI/Social/Alarm/EcoThreatSourceComponent.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "Creature/Audio/EcoFootstepAudioComponent.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Net/UnrealNetwork.h"
#include "Engine/World.h"
#include "InputCoreTypes.h"
#include "World/EcologyRegion.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
static TAutoConsoleVariable<int32> CVarPlayerGaitLog(TEXT("eco.Player.GaitLog"),0,TEXT("Log accepted player gait changes and server movement speed."));
UEcoPlayerEcologyComponent::UEcoPlayerEcologyComponent()
{
    PrimaryComponentTick.bCanEverTick=true;PrimaryComponentTick.TickGroup=TG_PostPhysics;
    SetIsReplicatedByDefault(true);
}
void UEcoPlayerEcologyComponent::BeginPlay()
{
    Super::BeginPlay();OnRep_Gait();
    if(GetOwner()->HasAuthority()) {
        ThreatSource=NewObject<UEcoThreatSourceComponent>(GetOwner());
        GetOwner()->AddInstanceComponent(ThreatSource);ThreatSource->bThreatEnabled=bThreatEnabled;ThreatSource->RegisterComponent();
    }
    if(GetNetMode()!=NM_DedicatedServer) {
        LocalAudio=NewObject<UEcoFootstepAudioComponent>(GetOwner());
        GetOwner()->AddInstanceComponent(LocalAudio);LocalAudio->AudioSet=AudioSet;LocalAudio->RegisterComponent();
    }
}
void UEcoPlayerEcologyComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{Super::GetLifetimeReplicatedProps(OutLifetimeProps);DOREPLIFETIME(UEcoPlayerEcologyComponent,Gait);}
void UEcoPlayerEcologyComponent::OnRep_Gait()
{
    if(auto* C=Cast<ACharacter>(GetOwner())) C->GetCharacterMovement()->MaxWalkSpeed=
        Gait==EEcoPlayerGait::Sneak?270.f:Gait==EEcoPlayerGait::Run?900.f:360.f;
}
void UEcoPlayerEcologyComponent::SetGait(EEcoPlayerGait NewGait)
{
    if(CVarPlayerGaitLog.GetValueOnGameThread()&&NewGait!=Gait)UE_LOG(LogTemp,Log,TEXT("[Eco Player Gait Request] Owner=%s New=%d Current=%d"),*GetNameSafe(GetOwner()),uint8(NewGait),uint8(Gait));
    if(uint8(NewGait)>uint8(EEcoPlayerGait::Run)||NewGait==Gait)return;
    Gait=NewGait;OnRep_Gait();
    if(CVarPlayerGaitLog.GetValueOnGameThread())UE_LOG(LogTemp,Log,TEXT("[Eco Player Gait] Owner=%s Authority=%d Gait=%d"),*GetNameSafe(GetOwner()),GetOwner()->HasAuthority(),uint8(Gait));
    if(!GetOwner()->HasAuthority())ServerSetGait(NewGait);
}
void UEcoPlayerEcologyComponent::ServerSetGait_Implementation(EEcoPlayerGait NewGait)
{if(uint8(NewGait)<=uint8(EEcoPlayerGait::Run)){Gait=NewGait;OnRep_Gait();}}
void UEcoPlayerEcologyComponent::TickComponent(float Dt,ELevelTick Type,FActorComponentTickFunction* Function)
{
    Super::TickComponent(Dt,Type,Function);
    auto* Pawn=Cast<ACharacter>(GetOwner());if(!Pawn||!Pawn->IsPlayerControlled())return;
    if(bUseKeyboardGait&&Pawn->IsLocallyControlled()) if(auto* PC=Cast<APlayerController>(Pawn->GetController()))
        SetGait(PC->IsInputKeyDown(EKeys::LeftControl)?EEcoPlayerGait::Sneak:PC->IsInputKeyDown(EKeys::LeftShift)?EEcoPlayerGait::Run:EEcoPlayerGait::Walk);
    const float Speed=Pawn->GetVelocity().Size2D();
    const FVector Pos=Pawn->GetActorLocation()-FVector(0,0,90);
    const bool Grounded=Pawn->GetCharacterMovement()->IsMovingOnGround();
    if(Pawn->HasAuthority()) {
        if(ThreatSource)ThreatSource->bThreatEnabled=bThreatEnabled;
        if(ServerCadence.Advance(Pos,Speed,Grounded,Dt,Gait==EEcoPlayerGait::Run?220.f:140.f,40.f))
            if(auto* Noise=GetWorld()->GetSubsystem<UEcoNoiseSubsystem>())
                Noise->ReportNoise(Pos,Gait==EEcoPlayerGait::Sneak?.12f:Gait==EEcoPlayerGait::Run?1.f:.4f,2000.f,1.f,Pawn,TEXT("Player.Footstep"));
    }
    if(LocalAudio) {
        FEcoCreatureVisualState S;S.bAlive=Grounded;S.Position=Pos;S.Velocity=Pawn->GetVelocity();S.WorldTime=GetWorld()->GetTimeSeconds();
        for(TActorIterator<AEcologyRegion> It(GetWorld());It;++It)if(It->ContainsPosition(Pos)){S.RegionId=It->RegionId;break;}
        LocalAudio->Consume(S,Dt,false);
    }
}
