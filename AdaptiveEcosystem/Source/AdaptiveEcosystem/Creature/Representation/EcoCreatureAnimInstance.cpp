#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Representation/EcoCreatureAnimationProfile.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/PlayerController.h"

void UEcoCreatureAnimInstance::NativeInitializeAnimation()
{
	Super::NativeInitializeAnimation();
	AnimationIndex = 0; PoseAgeSeconds = 0; GroundIKAlpha = 0;
    AlertHeadAlpha=0;
    SensoryAlertSeconds=0;PreviousSense=EEcoSenseSource::None;
	GroundValid0=GroundValid1=GroundValid2=GroundValid3=0;
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
	Activity = bAlive ? Visual->VisualState.Activity : EEcoSpeciesActivity::Hold;
	VisualMotion = Visual && Visual->bBound ? Visual->VisualMotion : EEcoCreatureVisualMotion::Idle;
    int32 Desired = 0;
    const auto* Profile = Visual ? Visual->AnimationProfile.Get() : nullptr;
    const bool MovingAlert=bAlive&&Activity==EEcoSpeciesActivity::AlertGraze&&SpeedCmPerSecond>(Profile?Profile->StationarySpeed:40);
    AlertHeadAlpha=FMath::FInterpTo(AlertHeadAlpha,MovingAlert?1.f:0.f,DeltaSeconds,5.f);
    const EEcoSenseSource Sense=bAlive?Visual->VisualState.SenseSource:EEcoSenseSource::None;
    const bool FreshCue=Sense!=PreviousSense&&(Sense==EEcoSenseSource::Sight||Sense==EEcoSenseSource::Hearing);
    PreviousSense=Sense;
    SensoryAlertSeconds=FreshCue?.8f:FMath::Max(0.f,SensoryAlertSeconds-FMath::Max(0.f,DeltaSeconds));
    if (Visual && Visual->bBound && !bAlive) Desired = 8;
    else if (bAlive) {
        if(Activity==EEcoSpeciesActivity::Sleep) Desired=5;
        else if(Activity==EEcoSpeciesActivity::Freeze) Desired=4;
        else if(Activity==EEcoSpeciesActivity::Attack||Activity==EEcoSpeciesActivity::Pounce) Desired=6;
        else if(SpeedCmPerSecond<=(Profile?Profile->StationarySpeed:40)) {
            if(Activity==EEcoSpeciesActivity::ShelterHold)Desired=3;
            else if(Activity==EEcoSpeciesActivity::SatedRest)Desired=7;
            // A fresh cue briefly interrupts grazing; a persistent cue never pins the animal in alert forever.
            else if(SensoryAlertSeconds>0)Desired=2;
            else if(Activity==EEcoSpeciesActivity::AlertGraze)Desired=2;
            else if(Activity==EEcoSpeciesActivity::Graze||Activity==EEcoSpeciesActivity::Eat)Desired=1;
            else if(Activity==EEcoSpeciesActivity::Recover||Activity==EEcoSpeciesActivity::Exhaust||Activity==EEcoSpeciesActivity::Rest||Activity==EEcoSpeciesActivity::SatedRest)Desired=7;
            else if(Activity==EEcoSpeciesActivity::Search || Visual->VisualState.SenseSource==EEcoSenseSource::Hearing || Visual->VisualState.SenseSource==EEcoSenseSource::Memory)Desired=2;
        }
    }
    PoseAgeSeconds += FMath::Max(0.f,DeltaSeconds);
    if(Desired!=AnimationIndex && (Desired==8||(Desired==2&&FreshCue)||PoseAgeSeconds>=(Profile?Profile->MinimumPoseHoldSeconds:0))) {
        AnimationIndex=Desired;PoseAgeSeconds=0;
    }

    auto* Mesh=GetSkelMeshComponent();
    const auto* Viewer=UGameplayStatics::GetPlayerController(GetWorld(),0);
    const bool NearViewer=Viewer&&Visual&&FVector::DistSquared(Viewer->GetFocalLocation(),Visual->GetActorLocation())<FMath::Square(3000.f);
    const bool Standing=AnimationIndex==0||AnimationIndex==1||AnimationIndex==2||AnimationIndex==4;
    const bool IK=NearViewer&&Mesh&&bAlive&&Profile&&Profile->IsValidProfile()&&Profile->bEnableGroundIK&&Standing
        &&Desired!=3&&Desired!=5&&Desired!=6&&Desired!=7&&GetWorld()&&GetWorld()->GetNetMode()!=NM_DedicatedServer;
    float* Valid[]={&GroundValid0,&GroundValid1,&GroundValid2,&GroundValid3};
    FVector* Points[]={&GroundPoint0,&GroundPoint1,&GroundPoint2,&GroundPoint3};
    bool Any=false;
    for(int32 Index=0;Index<4;++Index) {
        *Valid[Index]=0;
        if(!IK||!Mesh->DoesSocketExist(Profile->FootBones[Index]))continue;
        const FVector Foot=Mesh->GetSocketLocation(Profile->FootBones[Index]);
        FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoVisualGroundEvidence),true,Visual);
        if(GetWorld()->LineTraceSingleByChannel(Hit,Foot+FVector(0,0,50),Foot-FVector(0,0,120),ECC_Visibility,Params)
            &&Hit.Normal.Z>=.65f&&!Hit.Location.ContainsNaN()) {
            const FTransform Component=Mesh->GetComponentTransform();
            GroundRootPoint=Component.InverseTransformPosition(Visual->GetActorLocation());
            *Points[Index]=Component.InverseTransformPosition(Hit.Location);*Valid[Index]=1;Any=true;
            GroundUp=Component.InverseTransformVectorNoScale(FVector::UpVector).GetSafeNormal();
            GroundWorldToComponent=Component.InverseTransformVector(FVector::UpVector).Size();
        }
    }
    GroundIKAlpha=FMath::FInterpTo(GroundIKAlpha,Any?1.f:0.f,DeltaSeconds,8.f);
}
