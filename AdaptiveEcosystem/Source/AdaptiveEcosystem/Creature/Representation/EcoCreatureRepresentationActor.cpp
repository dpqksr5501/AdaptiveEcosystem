#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Representation/EcoCreatureAnimationProfile.h"
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
#include "TimerManager.h"
#include "Kismet/GameplayStatics.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Creature/Audio/EcoFootstepAudioComponent.h"
#include "UI/EcoHealthBarComponent.h"

static TAutoConsoleVariable<int32> CVarEcoDrawFacing(TEXT("eco.Creature.DrawFacing"), 0,
	TEXT("Draw actual velocity (green) and calibrated mesh forward (cyan). Visual-only."));
static TAutoConsoleVariable<int32> CVarEcoIdentityLabels(TEXT("eco.Creature.Labels"),1,TEXT("Show representation identity labels. Visual-only; disable for scene captures."));
static TAutoConsoleVariable<int32> CVarEcoFacingAudit(TEXT("eco.Creature.FacingAudit"), 0,
	TEXT("Log moving representation facing error once per second, including client proxies."));

bool FEcoCreatureVisualState::IsValid() const
{
	return StableAgentId > 0 && !SpeciesId.IsNone() && Sequence > 0 && FMath::IsFinite(WorldTime) && WorldTime >= 0.0
        &&FMath::IsFinite(BodyScale)&&BodyScale>=.65f&&BodyScale<=1.15f&&Appearance<=3
        &&FMath::IsFinite(Maturity)&&Maturity>=0&&Maturity<=1&&FMath::IsFinite(CoatTone)&&CoatTone>=0&&CoatTone<=1
		&& !Position.ContainsNaN() && !Velocity.ContainsNaN() && FMath::IsFinite(FocusYawDegrees)
        && uint8(SenseSource)<=uint8(EEcoSenseSource::Memory) && uint8(Activity)<=uint8(EEcoSpeciesActivity::Investigate)
		&& FMath::IsFinite(NormalizedHealth) && NormalizedHealth >= 0.0f && NormalizedHealth <= 1.0f
		&& FMath::IsFinite(NormalizedEnergy) && NormalizedEnergy >= 0.0f && NormalizedEnergy <= 1.0f;
}

AEcoCreatureRepresentationActor::AEcoCreatureRepresentationActor()
{
	PrimaryActorTick.bCanEverTick = false;
	bReplicates = false; // The eventual production transport remains the existing Mass network path.
	SetReplicateMovement(false);
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("VisualRoot")));
	HealthBar = CreateDefaultSubobject<UEcoHealthBarComponent>(TEXT("HealthBar"));
	HealthBar->SetupAttachment(RootComponent);
	Footsteps = CreateDefaultSubobject<UEcoFootstepAudioComponent>(TEXT("Footsteps"));
	CreatureMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("CreatureMesh"));
	CreatureMesh->SetupAttachment(RootComponent);
	CreatureMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	CreatureMesh->SetGenerateOverlapEvents(false);
    ImmatureMesh=CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("ImmatureMesh"));
    ImmatureMesh->SetupAttachment(RootComponent);ImmatureMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ImmatureMesh->SetGenerateOverlapEvents(false);ImmatureMesh->SetVisibility(false);ImmatureMesh->bCastDynamicShadow=true;
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
    Footsteps->bUseAnimationNotifies = bUseFootstepNotifies;
	if (VisualMesh) { CreatureMesh->SetSkeletalMesh(VisualMesh); }
    AppliedAppearance=255;ApplyAppearance(VisualState.Appearance);
	CreatureMesh->SetRelativeRotation(MeshRotation);
    ImmatureMesh->SetRelativeRotation(MeshRotation);
	UpdateAnimation();
	PlaceholderBody->SetVisibility(CreatureMesh->GetSkeletalMeshAsset() == nullptr);
	IdentityLabel->SetText(FText::FromString(bBound ? FString::Printf(TEXT("%s #%lld"), *VisualSpeciesId.ToString(), VisualState.StableAgentId)
		: VisualSpeciesId.ToString() + TEXT(" (unbound)")));
}
void AEcoCreatureRepresentationActor::ApplyAppearance(uint8 Variant)
{
    if(AppliedAppearance==Variant||!AppearanceVariants.IsValidIndex(Variant))return;
    const auto& V=AppearanceVariants[Variant];
    if(!V.Mesh||!V.Profile||!V.Profile->IsValidProfile()||!V.AnimationClass||V.MeshScale.ContainsNaN())return;
    CreatureMesh->SetSkeletalMesh(V.Mesh);CreatureMesh->SetRelativeScale3D(V.MeshScale);
    AnimationProfile=V.Profile;LocomotionBlendSpace=V.Profile->Locomotion;BehaviorAnimationClass=V.AnimationClass;
    CreatureMesh->SetAnimInstanceClass(V.AnimationClass);AppliedAppearance=Variant;
    CreatureMesh->EmptyOverrideMaterials();
    if(bContinuousGrowthAppearance){
        for(int32 I=0;I<V.GrowthMaterials.Num();++I)CreatureMesh->SetMaterial(I,V.GrowthMaterials[I]);
        if(AppearanceVariants.IsValidIndex(2)){
            const auto& Young=AppearanceVariants[2];
            ImmatureMesh->SetSkeletalMesh(Young.Mesh);ImmatureMesh->SetAnimInstanceClass(Young.AnimationClass);
            ImmatureMesh->EmptyOverrideMaterials();
            for(int32 I=0;I<Young.GrowthMaterials.Num();++I)ImmatureMesh->SetMaterial(I,Young.GrowthMaterials[I]);
        }
    }
}

bool AEcoCreatureRepresentationActor::BindIdentity(int64 AgentId, FName SpeciesId)
{
	if (AgentId <= 0 || SpeciesId != VisualSpeciesId || bBound) { return false; }
	VisualState = {};
	HealthBar->ClearHealth();
	VisualTurnAmount = DirectionDegrees = 0.0f;
	LastFacingAuditTime = -1.0;
	VisualState.StableAgentId = AgentId;
	VisualState.SpeciesId = SpeciesId;
	bBound = true;
	Footsteps->ResetCadence();
	SetActorHiddenInGame(false);
	RefreshAppearance();
    // A pooled visual must not inherit death/IK state from its previous logical identity.
    if(auto* Animation=CreatureMesh->GetAnimInstance())Animation->InitializeAnimation();
	return true;
}

void AEcoCreatureRepresentationActor::ClearBinding()
{
	bBound = false;
	HealthBar->ClearHealth();
	if(GetWorld())GetWorld()->GetTimerManager().ClearTimer(AlarmTimer);
	LastAlarmTime=-10;
	Footsteps->ResetCadence();
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
    IdentityLabel->SetVisibility(CVarEcoIdentityLabels.GetValueOnGameThread()!=0);
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
	if(Speed<=IdleSpeed && State.SenseSource!=EEcoSenseSource::None)
        Facing=FRotator(0,FMath::FixedTurn(Facing.Yaw,State.FocusYawDegrees,90.f*DeltaSeconds),0);
    const bool NewDirectCue=State.SenseSource!=VisualState.SenseSource&&(State.SenseSource==EEcoSenseSource::Sight||State.SenseSource==EEcoSenseSource::Hearing);
    const bool NewFlee=State.Activity!=VisualState.Activity&&State.Activity==EEcoSpeciesActivity::Flee;
    if(!bSnap&&VisualSpeciesId==TEXT("Herbivore")&&State.bAlive&&(NewDirectCue||NewFlee)&&State.WorldTime-LastAlarmTime>=3&&GetWorld()->GetNetMode()!=NM_DedicatedServer)
    {
        LastAlarmTime=State.WorldTime;
        GetWorld()->GetTimerManager().SetTimer(AlarmTimer,this,&AEcoCreatureRepresentationActor::PlayAlarmCue,.05f+float(State.StableAgentId%7)*.05f,false);
    }
    const bool bContinuousTurn = !bSnap && State.bAlive && VisualState.bAlive
		&& Speed > IdleSpeed && VisualState.Velocity.Size2D() > IdleSpeed
		&& DeltaSeconds > SMALL_NUMBER && DeltaSeconds <= 0.5f;
	const float TurnTarget = bContinuousTurn ? FMath::Clamp(
		FMath::FindDeltaAngleDegrees(PreviousYaw, Facing.Yaw) / DeltaSeconds / FMath::Max(1.0f, FullTurnRateDegrees), -1.0f, 1.0f) : 0.0f;
	VisualTurnAmount = bContinuousTurn ? FMath::FInterpTo(VisualTurnAmount, TurnTarget, DeltaSeconds, 8.0f) : 0.0f;
	// Moves this passive visual Actor only. Never modifies a Mass fragment or evaluates behavior.
	SetActorLocationAndRotation(State.Position, Facing, false, nullptr, ETeleportType::TeleportPhysics);
    SetActorScale3D(FVector(State.BodyScale));
	VisualState = State;
    ApplyAppearance(State.Appearance);
    if(bContinuousGrowthAppearance&&State.Appearance>0){
        // Both rigs retain one logical identity. Complementary masked fades only render
        // two meshes during maturation; no gameplay, age extrapolation or actor spawning.
        const float T=FMath::Clamp((State.Maturity-.60f)/.40f,0.f,1.f);
        const float Adult=State.Appearance==1?T*T*(3-2*T):1.f;
        CreatureMesh->SetVisibility(Adult>0);CreatureMesh->SetCustomPrimitiveDataFloat(3,Adult);CreatureMesh->SetCustomPrimitiveDataFloat(4,0);
        ImmatureMesh->SetVisibility(Adult<1);ImmatureMesh->SetCustomPrimitiveDataFloat(3,Adult);ImmatureMesh->SetCustomPrimitiveDataFloat(4,1);
        const float Tone=.85f+.3f*State.CoatTone;
        CreatureMesh->SetCustomPrimitiveDataFloat(5,Tone);ImmatureMesh->SetCustomPrimitiveDataFloat(5,Tone);
        // Nutrition/health alter condition without rewriting genes, growing bones or giving speed.
        const float Condition=FMath::Clamp(.75f*State.NormalizedEnergy+.25f*State.NormalizedHealth,0.f,1.f);
        const FVector ConditionShape(.97f+.03f*Condition,.94f+.06f*Condition,1);
        const FVector Proportions=ConditionShape*FMath::Lerp(FVector(.90,.90,1.04),FVector::OneVector,State.Maturity);
        if(AppearanceVariants.IsValidIndex(State.Appearance))CreatureMesh->SetRelativeScale3D(AppearanceVariants[State.Appearance].MeshScale*Proportions);
        ImmatureMesh->SetRelativeScale3D(Proportions);
    }else{CreatureMesh->SetVisibility(true);ImmatureMesh->SetVisibility(false);}
	HealthBar->SetHealthNormalized(State.NormalizedHealth, State.bAlive, State.bHasVitals);
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
	Footsteps->Consume(State, DeltaSeconds, bSnap);
	return true;
}

void AEcoCreatureRepresentationActor::UpdateAnimation()
{
	if (!CreatureMesh->GetSkeletalMeshAsset()) return;
    if (BehaviorAnimationClass && AnimationProfile && AnimationProfile->IsValidProfile())
    {
        if (!CreatureMesh->GetAnimInstance() || !CreatureMesh->GetAnimInstance()->IsA(BehaviorAnimationClass))
        { CreatureMesh->SetAnimationMode(EAnimationMode::AnimationBlueprint); CreatureMesh->SetAnimInstanceClass(BehaviorAnimationClass); }
        return;
    }
    if (!LocomotionBlendSpace) return;
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

void AEcoCreatureRepresentationActor::PlayAlarmCue()
{
    if(!bBound||!VisualState.bAlive||!AnimationProfile||!AnimationProfile->AlarmSound||!GetWorld()||GetWorld()->GetNetMode()==NM_DedicatedServer)return;
    UGameplayStatics::SpawnSoundAtLocation(this,AnimationProfile->AlarmSound,GetActorLocation(),FRotator::ZeroRotator,.4f,1,0,
        Footsteps&&Footsteps->AudioSet?Footsteps->AudioSet->Attenuation.Get():nullptr);
}
