#include "AI/Social/Shelter/EcoRefugeHabitat.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "TimerManager.h"

AEcoRefugeHabitat::AEcoRefugeHabitat()
{
    Radius=1200;Capacity=4;Quality=.8f;SlotRadiusFraction=.55f;
    bProjectSlotsToGround=true;
    bReplicates=true;bAlwaysRelevant=true;SetReplicateMovement(false);
    NetDormancy=DORM_Awake;
    Brush=CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("RefugeBrush"));Brush->SetupAttachment(SceneRoot);
    Boulders=CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("RefugeBoulders"));Boulders->SetupAttachment(SceneRoot);
    for(auto* C:{Brush.Get(),Boulders.Get()}) {C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetCanEverAffectNavigation(false);C->SetCastShadow(true);}
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Grass(TEXT("/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassA"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Stone(TEXT("/Game/MWLandscapeAutoMaterial/Meshes/Cover/SM_MWAM_StoneA"));
    BrushMesh=Grass.Object;BoulderMesh=Stone.Object;
}

void AEcoRefugeHabitat::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME_CONDITION(AEcoRefugeHabitat,LayoutRadius,COND_InitialOnly);
    DOREPLIFETIME_CONDITION(AEcoRefugeHabitat,ReplicatedSeed,COND_InitialOnly);
    DOREPLIFETIME(AEcoRefugeHabitat,bRegistrationReady);
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
    if(GetNetMode()!=NM_Client){LayoutRadius=Radius;ReplicatedSeed=LayoutSeed;if(!IsNetStartupActor())NetDormancy=DORM_Awake;}
    Super::BeginPlay();
    if(HasAuthority()) {
        bRegistrationReady=ShelterRuntimeIndex>=0;
        if(!bRegistrationReady)GetWorldTimerManager().SetTimer(RegistrationTimer,this,&AEcoRefugeHabitat::TryRegisterGrounded,.25f,true);
        ForceNetUpdate();
    }
    OnRep_Ready();
    if(GetNetMode()!=NM_DedicatedServer&&Brush->GetInstanceCount()==0)RebuildHabitat();
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
}
void AEcoRefugeHabitat::EndPlay(const EEndPlayReason::Type Reason)
{
    GetWorldTimerManager().ClearTimer(RegistrationTimer);Super::EndPlay(Reason);
}
void AEcoRefugeHabitat::RebuildHabitat()
{
    if(!GetWorld()||GetNetMode()==NM_DedicatedServer||!BrushMesh||!BoulderMesh||!FMath::IsFinite(Radius)||Radius<50)return;
    Brush->ClearInstances();Boulders->ClearInstances();Brush->SetStaticMesh(BrushMesh);Boulders->SetStaticMesh(BoulderMesh);
    FRandomStream Random(LayoutSeed);
    const float R=FMath::Clamp(Radius,50.f,2500.f),Spacing=FMath::Clamp(BrushSpacing,80.f,250.f);
    auto Place=[&](UHierarchicalInstancedStaticMeshComponent* Component,float X,float Y,FVector Scale,FRotator Rotation){
        FVector P=GetActorLocation()+FVector(X,Y,0);
        FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoRefugeAuthorGround),true,this);
        if(GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,2000),P-FVector(0,0,4000),ECC_WorldStatic,Params))P.Z=Hit.ImpactPoint.Z;
        const auto Bounds=Component->GetStaticMesh()->GetBounds();
        P.Z-=(Bounds.Origin.Z-Bounds.BoxExtent.Z)*Scale.Z+5;
        Component->AddInstance(FTransform(Rotation,P,Scale),true);
    };
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
        const float Scale=Random.FRandRange(5.5f,8.f);
        Place(Boulders,FMath::Cos(Angle)*(R-65),FMath::Sin(Angle)*(R-65),{Scale,Scale*.8f,Scale*.95f},{0,Random.FRandRange(0,360),0});
    }
}
