#include "AI/Social/Shelter/EcoRefugeHabitat.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "TimerManager.h"
#include "AI/Policy/EcoNaturalHabitat.h"
#include "Creature/Runtime/EcoFaunaSightChannel.h"

AEcoRefugeHabitat::AEcoRefugeHabitat()
{
    Radius=1200;Capacity=4;Quality=.8f;SlotRadiusFraction=.55f;
    bProjectSlotsToGround=true;
    bReplicates=true;bAlwaysRelevant=true;SetReplicateMovement(false);
    NetDormancy=DORM_Awake;
    Brush=CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("RefugeBrush"));Brush->SetupAttachment(SceneRoot);
    Boulders=CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("RefugeBoulders"));Boulders->SetupAttachment(SceneRoot);
    for(auto* C:{Brush.Get(),Boulders.Get()}) {C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetCanEverAffectNavigation(false);C->SetCastShadow(true);}
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Grass(TEXT("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassA"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Stone(TEXT("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Cover/SM_MWAM_StoneA"));
    BrushMesh=Grass.Object;BoulderMesh=Stone.Object;
}

void AEcoRefugeHabitat::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME_CONDITION(AEcoRefugeHabitat,LayoutRadius,COND_InitialOnly);
    DOREPLIFETIME_CONDITION(AEcoRefugeHabitat,ReplicatedSeed,COND_InitialOnly);
    DOREPLIFETIME(AEcoRefugeHabitat,bRegistrationReady);
    DOREPLIFETIME(AEcoRefugeHabitat,bNaturalLayout);
    DOREPLIFETIME(AEcoRefugeHabitat,NaturalBrushLayout);
    DOREPLIFETIME(AEcoRefugeHabitat,NaturalStoneLayout);
}
void AEcoRefugeHabitat::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    Radius=FMath::Clamp(Radius,50.f,2500.f);
    if(HasAuthority()){LayoutRadius=Radius;ReplicatedSeed=LayoutSeed;}
    RebuildHabitat();
}
void AEcoRefugeHabitat::OnRep_Layout(){Radius=LayoutRadius;LayoutSeed=ReplicatedSeed;RebuildHabitat();}
void AEcoRefugeHabitat::BeginPlay()
{
    if(bNaturalLayout){bAlwaysRelevant=false;SetNetCullDistanceSquared(FMath::Square(50000.f));}
    if(GetNetMode()!=NM_Client){LayoutRadius=Radius;ReplicatedSeed=LayoutSeed;if(!IsNetStartupActor())NetDormancy=DORM_Awake;}
    Super::BeginPlay();
    if(HasAuthority()) {
        bRegistrationReady=ShelterRuntimeIndex>=0;
        if(!bRegistrationReady)GetWorldTimerManager().SetTimer(RegistrationTimer,this,&AEcoRefugeHabitat::TryRegisterGrounded,.25f,true);
        ForceNetUpdate();
    }
    OnRep_Ready();
    if(bNaturalLayout&&bRegistrationReady)RebuildHabitat();
    if(GetNetMode()!=NM_DedicatedServer&&Brush->GetInstanceCount()==0)RebuildHabitat();
    if (bFaunaBoulderOcclusion) SetFaunaBoulderOcclusion(true);
}

void AEcoRefugeHabitat::SetFaunaBoulderOcclusion(bool bEnabled)
{
    if (!GetWorld() || GetNetMode() == NM_Client) return;
    Boulders->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Boulders->SetCollisionObjectType(bEnabled ? EcoFaunaDecision::SightCoverChannel : ECC_WorldStatic);
    Boulders->SetCollisionResponseToAllChannels(ECR_Ignore);
    if (bEnabled) Boulders->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
}
void AEcoRefugeHabitat::OnRep_Ready()
{
    Brush->SetVisibility(bRegistrationReady,true);Boulders->SetVisibility(bRegistrationReady,true);
}
void AEcoRefugeHabitat::TryRegisterGrounded()
{
    if(!HasAuthority())return;
    if(auto* Shelters=GetWorld()->GetSubsystem<UEcoShelterSubsystem>())
        ShelterRuntimeIndex=Shelters->RegisterShelter(GetActorLocation(),GetActorForwardVector(),Quality,Capacity,Radius,SlotRadiusFraction,true);
    bRegistrationReady=ShelterRuntimeIndex>=0;
    if(bRegistrationReady||++RegistrationAttempts>=120) {
        GetWorldTimerManager().ClearTimer(RegistrationTimer);
        if(!bRegistrationReady)UE_LOG(LogTemp,Warning,TEXT("[EcoRefuge] Ground registration unavailable: %s"),*GetName());
    }
    OnRep_Ready();ForceNetUpdate();
    if(bRegistrationReady&&bNaturalLayout)RebuildHabitat();
}
void AEcoRefugeHabitat::EndPlay(const EEndPlayReason::Type Reason)
{
    GetWorldTimerManager().ClearTimer(RegistrationTimer);Super::EndPlay(Reason);
}
void AEcoRefugeHabitat::RebuildHabitat()
{
    if(!GetWorld()||(!bNaturalLayout&&GetNetMode()==NM_DedicatedServer)||!BrushMesh||!BoulderMesh||!FMath::IsFinite(Radius)||Radius<50)return;
    if(bNaturalLayout&&HasActorBegunPlay()&&GetNetMode()==NM_Client){OnRep_NaturalLayout();return;}
    Brush->ClearInstances();Boulders->ClearInstances();Brush->SetStaticMesh(BrushMesh);Boulders->SetStaticMesh(BoulderMesh);
    NaturalBrushLayout.Reset();NaturalStoneLayout.Reset();
    FRandomStream Random(LayoutSeed);
    const float R=FMath::Clamp(Radius,50.f,2500.f),Spacing=FMath::Clamp(BrushSpacing,80.f,250.f);
    auto Place=[&](UHierarchicalInstancedStaticMeshComponent* Component,float X,float Y,FVector Scale,FRotator Rotation){
        FVector P=GetActorLocation()+FVector(X,Y,0);
        FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoRefugeAuthorGround),true,this);
        const bool Grounded=GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,bNaturalLayout?600:2000),P-FVector(0,0,bNaturalLayout?1200:4000),ECC_WorldStatic,Params);
        if(bNaturalLayout&&(!Grounded||Hit.ImpactNormal.Z<.75||FMath::Abs(Hit.ImpactPoint.Z-GetActorLocation().Z)>400))return;
        if(Grounded)P.Z=Hit.ImpactPoint.Z;
        const auto Bounds=Component->GetStaticMesh()->GetBounds();
        P.Z-=(Bounds.Origin.Z-Bounds.BoxExtent.Z)*Scale.Z+5;
        const FTransform T(Rotation,P,Scale);
        if(bNaturalLayout)(Component==Brush.Get()?NaturalBrushLayout:NaturalStoneLayout).Add(T);
        if(GetNetMode()!=NM_DedicatedServer)Component->AddInstance(T,true);
    };
    if(bNaturalLayout){
        // Bounded irregular clumps with soft edges; no stone ring or cardinal garden paths.
        for(int32 I=0;I<240&&NaturalBrushLayout.Num()<160;++I){
            const float Angle=Random.FRand()*2*PI,Length=FMath::Sqrt(Random.FRand())*R;
            const float X=FMath::Cos(Angle)*Length,Y=FMath::Sin(Angle)*Length;
            const double Density=EcoNaturalHabitat::PatchDensity(X,Y,R*.65,uint32(LayoutSeed));
            if(Random.FRand()>Density*(.25+.75*EcoNaturalHabitat::Smooth((R-Length)/(R*.35))))continue;
            bool Close=false;for(const auto& T:NaturalBrushLayout)if(FVector::DistSquared2D(T.GetLocation(),GetActorLocation()+FVector(X,Y,0))<Spacing*Spacing*.35){Close=true;break;}
            if(Close)continue;
            const float Height=FMath::Clamp(BrushHeight,60.f,200.f)*Random.FRandRange(.65f,1.2f);
            const FVector Size=BrushMesh->GetBoundingBox().GetSize();
            const float Width=Random.FRandRange(150,240)/FMath::Max(1.,FMath::Max(Size.X,Size.Y));
            Place(Brush,X,Y,{Width,Width,Height/FMath::Max(1.,Size.Z)},{0,Random.FRandRange(0,360),0});
        }
        for(int32 I=0;I<FMath::Clamp(NaturalBoulderCount,0,8);++I){
            const float Angle=Random.FRand()*2*PI,Length=Random.FRandRange(.25f,.9f)*R;
            const FVector Size=BoulderMesh->GetBoundingBox().GetSize();
            const float Scale=Random.FRandRange(120,260)/FMath::Max(1.,FMath::Max(Size.X,Size.Y));
            Place(Boulders,FMath::Cos(Angle)*Length,FMath::Sin(Angle)*Length,{Scale,Scale*.8f,Scale*.65f},{0,Random.FRandRange(0,360),0});
        }
        if(HasAuthority())ForceNetUpdate();
        return;
    }
    // Cardinal passages stay legible; occupants stand in clear pockets surrounded by tall brush.
    for(float Y=-R;Y<=R;Y+=Spacing)for(float X=-R;X<=R;X+=Spacing) {
        const float PX=X+Random.FRandRange(-Spacing*.22f,Spacing*.22f),PY=Y+Random.FRandRange(-Spacing*.22f,Spacing*.22f);
        if(PX*PX+PY*PY>R*R)continue;
        if((FMath::Abs(PX)<100&&FMath::Abs(PY)>R*.45f)||(FMath::Abs(PY)<100&&FMath::Abs(PX)>R*.45f))continue;
        bool Slot=false;
        for(int I=0;I<Capacity;++I) {
            const float Angle=2*PI*I/FMath::Max(1,Capacity);
            Slot|=FVector2D::Distance({PX,PY},{FMath::Cos(Angle)*R*SlotRadiusFraction,FMath::Sin(Angle)*R*SlotRadiusFraction})<130;
        }
        if(Slot)continue;
        const float Height=FMath::Clamp(BrushHeight,60.f,200.f)*Random.FRandRange(.85f,1.15f);
        const float Z=Height/(BrushMesh->GetBounds().BoxExtent.Z*2);
        Place(Brush,PX,PY,{Random.FRandRange(1.25f,1.8f),Random.FRandRange(1.25f,1.8f),Z},{0,Random.FRandRange(0,360),0});
    }
    for(int I=0;I<28;++I) {
        const float Angle=2*PI*(I+.5f)/28;
        if(FMath::Abs(FMath::Sin(Angle))<.20f||FMath::Abs(FMath::Cos(Angle))<.20f)continue;
        const auto Bounds=BoulderMesh->GetBounds();
        const float MeshRadius=FMath::Max(1.f,FVector2D(Bounds.BoxExtent.X,Bounds.BoxExtent.Y*.8f).Size());
        const float Scale=FMath::Min(Random.FRandRange(5.5f,8.f),R*.4f/MeshRadius);
        const FRotator Rotation(0,Random.FRandRange(0,360),0);
        const FVector Offset=Rotation.RotateVector(Bounds.Origin*FVector(Scale,Scale*.8f,Scale*.95f));
        // Actual mesh bounds stay within the native wolf body margin (100cm); pivots need not be centered.
        const float Ring=FMath::Max(0.f,R+50.f-MeshRadius*Scale);
        Place(Boulders,FMath::Cos(Angle)*Ring-Offset.X,FMath::Sin(Angle)*Ring-Offset.Y,{Scale,Scale*.8f,Scale*.95f},Rotation);
    }
}
void AEcoRefugeHabitat::OnRep_NaturalLayout()
{
    if(!bNaturalLayout||GetNetMode()==NM_DedicatedServer||!BrushMesh||!BoulderMesh)return;
    Brush->ClearInstances();Boulders->ClearInstances();Brush->SetStaticMesh(BrushMesh);Boulders->SetStaticMesh(BoulderMesh);
    Brush->AddInstances(NaturalBrushLayout,false,true,false);Boulders->AddInstances(NaturalStoneLayout,false,true,false);
    OnRep_Ready();
}
