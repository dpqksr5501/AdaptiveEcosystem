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
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "UI/EcoHealthBarComponent.h"

static TAutoConsoleVariable<int32> CVarEcoDrawFacing(TEXT("eco.Creature.DrawFacing"), 0,
	TEXT("Draw actual velocity (green) and calibrated mesh forward (cyan). Visual-only."));
static TAutoConsoleVariable<int32> CVarEcoIdentityLabels(TEXT("eco.Creature.Labels"),1,TEXT("Show representation identity labels. Visual-only; disable for scene captures."));
static TAutoConsoleVariable<int32> CVarEcoFacingAudit(TEXT("eco.Creature.FacingAudit"), 0,
	TEXT("Log moving representation facing error once per second, including client proxies."));

namespace
{
    float AdvanceVisualAngle(float Angle, float Error, bool bTrack, float Step, float MaxRate,
        float Acceleration, float Response, float& Rate)
    {
        if (Step <= 0.f) return Angle;
        const float BrakingRate = FMath::Sqrt(2.f * Acceleration * FMath::Abs(Error));
        const float Limit = FMath::Min(MaxRate, BrakingRate);
        const float TargetRate = bTrack ? FMath::Clamp(Error * Response, -Limit, Limit) : 0.f;
        const float PreviousRate = Rate;
        Rate = FMath::FInterpConstantTo(Rate, TargetRate, Step, bTrack ? Acceleration : 2.f * Acceleration);
        const float Change = (PreviousRate + Rate) * .5f * Step;
        if (bTrack && Error * Change >= 0.f && FMath::Abs(Change) >= FMath::Abs(Error))
        {
            Rate = 0.f;
            return FRotator::NormalizeAxis(Angle + Error);
        }
        return FRotator::NormalizeAxis(Angle + Change);
    }
}

bool FEcoCreatureVisualState::IsValid() const
{
	return StableAgentId > 0 && !SpeciesId.IsNone() && Sequence > 0 && FMath::IsFinite(WorldTime) && WorldTime >= 0.0
        &&FMath::IsFinite(BodyScale)&&BodyScale>=.65f&&BodyScale<=1.15f&&Appearance<=3
        &&FMath::IsFinite(Maturity)&&Maturity>=0&&Maturity<=1&&FMath::IsFinite(CoatTone)&&CoatTone>=0&&CoatTone<=1
		&& !Position.ContainsNaN() && !Velocity.ContainsNaN() && FMath::IsFinite(FocusYawDegrees)
        && (!bHasFacing || FMath::IsFinite(FacingYawDegrees))
        && uint8(SenseSource)<=uint8(EEcoSenseSource::Memory) && uint8(Activity)<=uint8(EEcoSpeciesActivity::ExitWater)
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
    if (GetNetMode() != NM_DedicatedServer)
    {
        MainPoseFinalized = CreatureMesh->RegisterOnBoneTransformsFinalizedDelegate(
            FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateUObject(this, &ThisClass::FitGroundSupport, CreatureMesh.Get()));
        ImmaturePoseFinalized = ImmatureMesh->RegisterOnBoneTransformsFinalizedDelegate(
            FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateUObject(this, &ThisClass::FitGroundSupport, ImmatureMesh.Get()));
    }
}

void AEcoCreatureRepresentationActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    CreatureMesh->UnregisterOnBoneTransformsFinalizedDelegate(MainPoseFinalized);
    ImmatureMesh->UnregisterOnBoneTransformsFinalizedDelegate(ImmaturePoseFinalized);
    Super::EndPlay(EndPlayReason);
}

void AEcoCreatureRepresentationActor::ResetGroundSupport()
{
    if (GroundSupportBlend > 0.f || MainGroundLift > 0.f || ImmatureGroundLift > 0.f)
    {
        GroundSupportRotation = FQuat::Identity;
        ApplyGroundSupport(*CreatureMesh, 0.f);
        ApplyGroundSupport(*ImmatureMesh, 0.f);
    }
    GroundSupportBlend = MainGroundLift = ImmatureGroundLift = 0.f;
    bGroundSupportEvidence = bGroundSupportSnap = false;
}

void AEcoCreatureRepresentationActor::ApplyGroundSupport(USkeletalMeshComponent& Mesh, float Lift) const
{
    const FVector LocalLift = GetRootComponent()->GetComponentTransform().InverseTransformVector(FVector(0., 0., Lift));
    Mesh.SetRelativeLocationAndRotation(GroundSupportRotation.RotateVector(MeshOffset) + LocalLift,
        GroundSupportRotation * MeshRotation.Quaternion());
}

void AEcoCreatureRepresentationActor::UpdateGroundSupport(float DeltaSeconds, bool bSnap)
{
    const auto Activity = VisualState.Activity;
    const bool bRest = Activity == EEcoSpeciesActivity::Rest || Activity == EEcoSpeciesActivity::SatedRest
        || Activity == EEcoSpeciesActivity::Sleep || Activity == EEcoSpeciesActivity::ShelterHold;
    const bool bAirOrWater = (Activity >= EEcoSpeciesActivity::Takeoff && Activity <= EEcoSpeciesActivity::Land)
        || (Activity >= EEcoSpeciesActivity::Swim && Activity <= EEcoSpeciesActivity::ExitWater);
    const auto* Anim = Cast<UEcoCreatureAnimInstance>(CreatureMesh->GetAnimInstance());
    const bool bRestBlend = VisualState.bAlive && !bAirOrWater && GroundSupportBlend > .95f && Anim
        && (Anim->AnimationIndex == int32(EEcoPresentationPose::Hide)
            || Anim->AnimationIndex == int32(EEcoPresentationPose::Sleep)
            || Anim->AnimationIndex == int32(EEcoPresentationPose::Recover) || Anim->GetPoseAgeSeconds() < .22f);
    const bool bRequested = AnimationProfile && !bAlwaysSwimming
        && (!VisualState.bAlive || (bRest && VisualState.Velocity.SizeSquared2D() <= FMath::Square(AnimationProfile->StationarySpeed)));
    if (GetNetMode() == NM_DedicatedServer || (!bRequested && GroundSupportBlend <= 0.f)) return;

    const FVector Origin = GetActorLocation();
    FHitResult Hit;
    bGroundSupportEvidence = GetWorld()->LineTraceSingleByObjectType(Hit, Origin + FVector(0., 0., 10.),
        Origin - FVector(0., 0., 18.), FCollisionObjectQueryParams(ECC_WorldStatic),
        FCollisionQueryParams(SCENE_QUERY_STAT(EcoBodySupport), true, this)) && Hit.ImpactNormal.Z >= .75;
    if (bAirOrWater && VisualState.bAlive) bGroundSupportEvidence = false;
    // A floating amphibian carcass still has a floor underneath it in shallow water.
    if (bGroundSupportEvidence && !VisualState.bAlive && SwimPitchLimit > 0.f
        && !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Hit.ImpactPoint, 4.f))
        bGroundSupportEvidence = false;
    if (bGroundSupportEvidence)
    {
        GroundSupportPoint = Hit.ImpactPoint;
        GroundSupportNormal = Hit.ImpactNormal;
    }
    const bool bSupported = (bRequested || bRestBlend) && bGroundSupportEvidence;
    const float Alpha = bSnap ? 1.f : 1.f - FMath::Exp(-9.f * FMath::Min(DeltaSeconds, .05f));
    GroundSupportBlend = FMath::Lerp(GroundSupportBlend, bSupported ? 1.f : 0.f, Alpha);
    if (GroundSupportBlend < .005f) GroundSupportBlend = 0.f;
    const FQuat Target = bSupported ? FQuat::FindBetweenNormals(
        GetActorQuat().UnrotateVector(FVector::UpVector), GetActorQuat().UnrotateVector(GroundSupportNormal)) : FQuat::Identity;
    GroundSupportRotation = GroundSupportBlend > 0.f ? FQuat::Slerp(GroundSupportRotation, Target, Alpha).GetNormalized() : FQuat::Identity;
    bGroundSupportSnap = bSnap;
    if (GroundSupportBlend == 0.f)
        MainGroundLift = ImmatureGroundLift = 0.f;
    ApplyGroundSupport(*CreatureMesh, MainGroundLift);
    if (ImmatureMesh->IsVisible()) ApplyGroundSupport(*ImmatureMesh, ImmatureGroundLift);
}

void AEcoCreatureRepresentationActor::FitGroundSupport(USkeletalMeshComponent* Mesh)
{
    if (!bBound || GroundSupportBlend <= 0.f || !AnimationProfile || !Mesh->IsVisible()) return;
    float& Lift = Mesh == CreatureMesh ? MainGroundLift : ImmatureGroundLift;
    float Target = 0.f;
    if (bGroundSupportEvidence)
    {
        const UEcoCreatureAnimationProfile* Profile = AnimationProfile.Get();
        if (Mesh == ImmatureMesh && AppearanceVariants.IsValidIndex(2) && AppearanceVariants[2].Profile)
            Profile = AppearanceVariants[2].Profile.Get();
        for (const FName Foot : Profile->FootBones)
        {
            if (!Mesh->DoesSocketExist(Foot)) continue;
            const FVector Contact = Mesh->GetSocketLocation(Foot) - FVector(0., 0., Lift);
            const double Gap = FVector::DotProduct(Contact - GroundSupportPoint, GroundSupportNormal) / GroundSupportNormal.Z;
            Target = FMath::Max(Target, float(.25 - Gap));
        }
        Target = FMath::Min(Target, 2.f * Profile->MaxFootCorrectionCm * VisualState.BodyScale);
    }
    // Correct only buried contacts. The underlying clip keeps its lifted legs and body pose.
    const float Dt = FMath::Min(GetWorld()->GetDeltaSeconds(), .05f);
    const float Next = bGroundSupportSnap ? Target : FMath::FInterpConstantTo(Lift, Target, Dt, Target > Lift ? 420.f : 120.f);
    if (!FMath::IsNearlyEqual(Next, Lift, .01f))
    {
        Lift = Next;
        ApplyGroundSupport(*Mesh, Lift);
    }
}

void AEcoCreatureRepresentationActor::RefreshAppearance()
{
    Footsteps->bUseAnimationNotifies = bUseFootstepNotifies;
	if (VisualMesh) { CreatureMesh->SetSkeletalMesh(VisualMesh); }
    if (!FMath::IsNearlyEqual(VisualMeshScale, 1.f))
        CreatureMesh->SetRelativeScale3D(FVector(VisualMeshScale));
    AppliedAppearance=255;ApplyAppearance(VisualState.Appearance);
	CreatureMesh->SetRelativeRotation(MeshRotation);
    ImmatureMesh->SetRelativeRotation(MeshRotation);
    if (!MeshOffset.IsNearlyZero())
    {
        CreatureMesh->SetRelativeLocation(MeshOffset);
        ImmatureMesh->SetRelativeLocation(MeshOffset);
    }
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
	VisualYawRateDegrees = 0.f;
	VisualPitchRateDegrees = VisualRollRateDegrees = ReversalDirection = 0.f;
	bHasMotionHeading = false;
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
    ResetGroundSupport();
	bBound = false;
	HealthBar->ClearHealth();
	if(GetWorld())GetWorld()->GetTimerManager().ClearTimer(AlarmTimer);
	LastAlarmTime=-10;
	Footsteps->ResetCadence();
	VisualState = {};
	VisualTurnAmount = DirectionDegrees = 0.0f;
	VisualYawRateDegrees = 0.f;
	VisualPitchRateDegrees = VisualRollRateDegrees = ReversalDirection = 0.f;
	bHasMotionHeading = false;
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
    const float PreviousPitch = Facing.Pitch;
    const float PreviousRoll = Facing.Roll;
	const float PreviousYaw = Facing.Yaw;
	const float HeadingThreshold = FMath::Max(0.f, IdleSpeed) * (bHasMotionHeading && !bSnap ? .75f : 1.25f);
	bHasMotionHeading = State.bAlive && Speed > HeadingThreshold;
	const bool bMoving = bSoftenAbruptFacing ? bHasMotionHeading : Speed > FMath::Max(0.f, IdleSpeed);
    const float AngularStep = FMath::Min(DeltaSeconds, .05f);
	const auto Activity = State.Activity;
	const bool bFlight = State.bAlive && FlightPitchLimit > 0.f
		&& (Activity == EEcoSpeciesActivity::Takeoff || Activity == EEcoSpeciesActivity::Fly
			|| Activity == EEcoSpeciesActivity::Land || Activity == EEcoSpeciesActivity::Attack);
	const bool bWater = State.bAlive && SwimPitchLimit > 0.f
		&& (bAlwaysSwimming || Activity == EEcoSpeciesActivity::EnterWater || Activity == EEcoSpeciesActivity::Swim
			|| Activity == EEcoSpeciesActivity::ExitWater);
	const bool bFocus = !bMoving && State.bAlive && State.SenseSource != EEcoSenseSource::None;
	DirectionDegrees = 0.0f;
	if (bSoftenAbruptFacing)
	{
		if (bSnap)
		{
			VisualYawRateDegrees = ReversalDirection = 0.f;
			if (bMoving || State.bHasFacing)
				Facing.Yaw = bMoving ? State.Velocity.Rotation().Yaw : State.FacingYawDegrees;
		}
		else if (State.bAlive)
		{
            const bool bTrack = bMoving || bFocus;
			const float DesiredYaw = bMoving ? State.Velocity.Rotation().Yaw : State.FocusYawDegrees;
			float Error = bTrack ? FMath::FindDeltaAngleDegrees(PreviousYaw, DesiredYaw) : 0.f;
			// Hold the chosen side of an about-face across the angle seam and small input changes.
			if (!bTrack || FMath::Abs(Error) < 160.f) ReversalDirection = 0.f;
			else if (ReversalDirection == 0.f && FMath::Abs(Error) >= 175.f)
				ReversalDirection = FMath::Sign(FMath::Abs(VisualYawRateDegrees) > 1.f ? VisualYawRateDegrees : Error);
			if (Error * ReversalDirection < 0.f) Error -= FMath::Sign(Error) * 360.f;
			const float MaxRate = bFocus ? 90.f : bFlight ? 300.f : bWater ? 360.f : 540.f;
			const float Acceleration = bFlight || bWater ? 1440.f : 2160.f;
			Facing.Yaw = AdvanceVisualAngle(PreviousYaw, Error, bTrack, AngularStep, MaxRate, Acceleration,
				FMath::Max(0.f, TurnInterpolationSpeed), VisualYawRateDegrees);
		}
		else
		{
			VisualYawRateDegrees = ReversalDirection = 0.f;
		}
		if (bMoving) DirectionDegrees = FMath::FindDeltaAngleDegrees(Facing.Yaw, State.Velocity.Rotation().Yaw);
	}
	else if (bMoving)
	{
		const FRotator Desired(0, State.Velocity.Rotation().Yaw, 0);
		Facing = bSnap ? Desired : FMath::RInterpTo(Facing, Desired, DeltaSeconds, FMath::Max(0.0f, TurnInterpolationSpeed));
		const float Limit = FMath::Clamp(MaxFacingLagDegrees, 0.0f, 45.0f);
		const float Lag = FMath::Clamp(FMath::FindDeltaAngleDegrees(Desired.Yaw, Facing.Yaw), -Limit, Limit);
		Facing = FRotator(0, FRotator::NormalizeAxis(Desired.Yaw + Lag), 0);
		DirectionDegrees = FMath::FindDeltaAngleDegrees(Facing.Yaw, Desired.Yaw);
	}
	if (!bSoftenAbruptFacing && !bMoving && State.bHasFacing && (bSnap || !State.bAlive))
        Facing=FRotator(0,State.FacingYawDegrees,0);
	if (!bSoftenAbruptFacing && bFocus)
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
	if (bSoftenAbruptFacing && !bSnap && State.bAlive && VisualState.bAlive)
		VisualTurnAmount = FMath::Lerp(VisualTurnAmount, TurnTarget, 1.f - FMath::Exp(-8.f * FMath::Min(DeltaSeconds, .05f)));
	else
		VisualTurnAmount = bContinuousTurn ? FMath::FInterpTo(VisualTurnAmount, TurnTarget, DeltaSeconds, 8.0f) : 0.0f;
    if (FlightPitchLimit > 0.f || SwimPitchLimit > 0.f)
    {
        const float Limit = bFlight ? FlightPitchLimit : bWater ? SwimPitchLimit : 0.f;
        const float Pitch = State.Velocity.SizeSquared() > FMath::Square(IdleSpeed)
            ? FMath::Clamp(float(State.Velocity.Rotation().Pitch), -Limit, Limit) : 0.f;
        const float Roll = bFlight ? -VisualTurnAmount * FlightBankLimit : 0.f;
        if (bSnap)
        {
            Facing.Pitch = Pitch;
            Facing.Roll = Roll;
            VisualPitchRateDegrees = VisualRollRateDegrees = 0.f;
        }
        else
        {
            Facing.Pitch = AdvanceVisualAngle(PreviousPitch, Pitch - PreviousPitch, true, AngularStep, 160.f, 720.f, 9.f, VisualPitchRateDegrees);
            Facing.Roll = AdvanceVisualAngle(PreviousRoll, Roll - PreviousRoll, true, AngularStep, 200.f, 900.f, 9.f, VisualRollRateDegrees);
        }
    }
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
    UpdateGroundSupport(DeltaSeconds, bSnap);
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
    if (!VisualState.bAlive && VisualState.Activity == EEcoSpeciesActivity::CorpseSettled)
    {
        const auto* Pose = AnimationProfile && AnimationProfile->Poses.IsValidIndex(int32(EEcoPresentationPose::Dead))
            ? &AnimationProfile->Poses[int32(EEcoPresentationPose::Dead)] : nullptr;
        auto* Clip = Pose && Pose->Clip ? Pose->Clip.Get() : DeathAnimation.Get();
        if (Clip)
        {
            // A corpse already seen falling can finish its local blend before freezing.
            // A newly visible settled corpse has no falling pose to finish.
            const auto* Anim = Cast<UEcoCreatureAnimInstance>(CreatureMesh->GetAnimInstance());
            if (!VisualState.bDiscontinuity && Anim && Pose && Anim->AnimationIndex == int32(EEcoPresentationPose::Dead)
                && Anim->GetPoseAgeSeconds() < Clip->GetPlayLength() / FMath::Max(.1f, Pose->PlayRate) + Pose->BlendSeconds)
                return;
            auto* Current = CreatureMesh->GetSingleNodeInstance();
            if (!Current || Current->GetCurrentAsset() != Clip || Current->IsPlaying())
            {
                CreatureMesh->PlayAnimation(Clip, false);
                if (auto* Node = CreatureMesh->GetSingleNodeInstance())
                {
                    Node->SetPosition(Clip->GetPlayLength(), false);
                    Node->SetPlaying(false);
                }
            }
            return;
        }
    }
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
