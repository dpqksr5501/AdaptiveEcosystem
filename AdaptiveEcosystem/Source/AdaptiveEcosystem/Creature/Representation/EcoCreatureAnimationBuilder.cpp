#include "Creature/Representation/EcoCreatureAnimationBuilder.h"
#include "Creature/Representation/EcoCreatureAnimationProfile.h"
#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Representation/EcoForagePatchVisual.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Animation/AnimBlueprint.h"
#include "AI/Policy/EcoCreatureV3Trait.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoFaunaDecision.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "World/EcoNaturalHabitatProfile.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "MassSpawnerSubsystem.h"
#include "Mass/EntityFragments.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "Camera/CameraActor.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Creature/Debug/EcoCreatureInspection.h"
#include "Creature/Player/EcoPlayerEcologyComponent.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "Engine/SkeletalMesh.h"
#if WITH_EDITOR
#include "LandscapeProxy.h"
#include "LandscapeComponent.h"
#include "EngineUtils.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionEditorLoaderAdapter.h"
#include "WorldPartition/LoaderAdapter/LoaderAdapterShape.h"
#include "UObject/UnrealType.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "NiagaraSystem.h"
#include "NiagaraEmitter.h"
#include "NiagaraSpriteRendererProperties.h"
#include "NiagaraMeshRendererProperties.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshAttributes.h"
#include "MeshDescription.h"
#include "Misc/PackageName.h"
#endif

TArray<FName> UEcoCreatureAnimationBuilder::GetSkeletalBoneNames(USkeletalMesh* Mesh)
{
    TArray<FName> Out;if(Mesh)for(const auto& Bone:Mesh->GetRefSkeleton().GetRefBoneInfo())Out.Add(Bone.Name);return Out;
}
bool UEcoCreatureAnimationBuilder::ConfigureNaturalPrecipitation(UFXSystemAsset* Asset,UMaterialInterface* Material)
{
#if WITH_EDITOR
    auto* System=Cast<UNiagaraSystem>(Asset);
    if(!System||!Material||!System->GetPathName().StartsWith(TEXT("/Game/JYU/Ecosystem/Natural/")))return false;
    int32 Count=0;System->Modify();
    for(auto& Handle:System->GetEmitterHandles())if(auto* Data=Handle.GetInstance().GetEmitterData())for(auto* Renderer:Data->GetRenderers()){
        UE_LOG(LogTemp,Display,TEXT("[EcoNaturalPrecipitation] %s renderer=%s local=%d"),*System->GetName(),*Renderer->GetClass()->GetName(),Renderer->IsIn(System));
        if(auto* Sprite=Cast<UNiagaraSpriteRendererProperties>(Renderer)){
            if(!Sprite->IsIn(System))return false;
            Sprite->Modify();Sprite->Material=Material;Sprite->MaterialUserParamBinding.Parameter=FNiagaraVariable();++Count;
        }
        else if(auto* Mesh=Cast<UNiagaraMeshRendererProperties>(Renderer)){
            if(!Mesh->IsIn(System))return false;
            Mesh->Modify();Mesh->bOverrideMaterials=true;Mesh->OverrideMaterials.SetNum(1);Mesh->OverrideMaterials[0].ExplicitMat=Material;
            Mesh->OverrideMaterials[0].UserParamBinding.Parameter=FNiagaraVariable();++Count;
        }
    }
    System->PostEditChange();System->MarkPackageDirty();return Count>0;
#else
    return false;
#endif
}
UStaticMesh* UEcoCreatureAnimationBuilder::CreateNaturalPoolMesh(const FString& AssetPath,int32 Seed)
{
#if WITH_EDITOR
    if(!AssetPath.StartsWith(TEXT("/Game/JYU/Ecosystem/Natural/"))||FindObject<UPackage>(nullptr,*AssetPath))return nullptr;
    auto* Package=CreatePackage(*AssetPath);auto* Mesh=NewObject<UStaticMesh>(Package,*FPackageName::GetShortName(AssetPath),RF_Public|RF_Standalone);
    FMeshDescription Description;FStaticMeshAttributes Attributes(Description);Attributes.Register();
    auto Positions=Attributes.GetVertexPositions();auto UVs=Attributes.GetVertexInstanceUVs();UVs.SetNumChannels(1);
    auto Normals=Attributes.GetVertexInstanceNormals();auto Colors=Attributes.GetVertexInstanceColors();
    auto Tangents=Attributes.GetVertexInstanceTangents();auto Signs=Attributes.GetVertexInstanceBinormalSigns();
    const auto Group=Description.CreatePolygonGroup();Attributes.GetPolygonGroupMaterialSlotNames()[Group]=TEXT("Water");
    constexpr int32 Sides=48;TArray<FVertexID> Vertices;FRandomStream Random(Seed);TArray<float> Radii;
    for(int32 I=0;I<Sides;++I){const float A=2*PI*I/Sides;Radii.Add(44+4*FMath::Sin(A*3+.7f)+2*FMath::Cos(A*5+Random.FRand()*.25f));}
    auto AddVertex=[&](FVector3f P){const auto V=Description.CreateVertex();Positions[V]=P;Vertices.Add(V);};
    AddVertex({0,0,0});for(int32 Ring=0;Ring<2;++Ring)for(int32 I=0;I<Sides;++I){const float A=2*PI*I/Sides,R=Radii[I]*(Ring==0?.7f:1.f);AddVertex({FMath::Cos(A)*R,FMath::Sin(A)*R,0});}
    auto Triangle=[&](int32 A,int32 B,int32 C){TArray<FVertexInstanceID> Instances;
        for(const int32 Index:{A,B,C}){const auto V=Description.CreateVertexInstance(Vertices[Index]);const auto P=Positions[Vertices[Index]];
            UVs.Set(V,0,FVector2f(P.X/100+.5f,P.Y/100+.5f));Normals[V]=FVector3f(0,0,1);Tangents[V]=FVector3f(1,0,0);Signs[V]=1;
            Colors[V]=FVector4f(1,1,1,Index==0||Index<=Sides?1.f:0.f);Instances.Add(V);}
        Description.CreatePolygon(Group,Instances);
    };
    for(int32 I=0;I<Sides;++I){const int32 J=(I+1)%Sides;Triangle(0,1+I,1+J);Triangle(1+I,1+Sides+I,1+Sides+J);Triangle(1+I,1+Sides+J,1+J);}
    Mesh->GetStaticMaterials().Add(FStaticMaterial());UStaticMesh::FBuildMeshDescriptionsParams Params;Params.bBuildSimpleCollision=false;
    Mesh->BuildFromMeshDescriptions({&Description},Params);Mesh->MarkPackageDirty();return Mesh;
#else
    return nullptr;
#endif
}

FEcoBuildPoseGraph& EcoPoseGraphAuthoring(){static FEcoBuildPoseGraph Delegate;return Delegate;}
bool UEcoCreatureAnimationBuilder::BuildPoseGraph(UAnimBlueprint* BP,UEcoCreatureAnimationProfile* Profile)
{
    return EcoPoseGraphAuthoring().IsBound() && EcoPoseGraphAuthoring().Execute(BP,Profile);
}

bool UEcoCreatureAnimationBuilder::ConfigureBehaviorRepresentation(UBlueprint* BP,UEcoCreatureAnimationProfile* P,TSubclassOf<UEcoCreatureAnimInstance> Class)
{
#if WITH_EDITOR
    if(!BP||!BP->GeneratedClass||!P||!P->IsValidProfile()||!Class||!BP->GetPathName().StartsWith(TEXT("/Game/JYU/"))) return false;
    auto* CDO=Cast<AEcoCreatureRepresentationActor>(BP->GeneratedClass->GetDefaultObject());
    if(!CDO)return false;
    BP->Modify();CDO->Modify();CDO->AnimationProfile=P;CDO->BehaviorAnimationClass=Class;
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);
    CDO=Cast<AEcoCreatureRepresentationActor>(BP->GeneratedClass->GetDefaultObject());
    return CDO&&CDO->AnimationProfile==P&&CDO->BehaviorAnimationClass==Class;
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::AddPlayerEcologyComponent(UBlueprint* BP,UEcoFootstepAudioSet* AudioSet)
{
#if WITH_EDITOR
    if(!BP||!BP->SimpleConstructionScript||!AudioSet||!BP->GetPathName().StartsWith(TEXT("/Game/JYU/")))return false;
    BP->Modify();
    USCS_Node* Node=nullptr;
    for(auto* Existing:BP->SimpleConstructionScript->GetAllNodes())
        if(Existing->ComponentClass==UEcoPlayerEcologyComponent::StaticClass())Node=Existing;
    if(!Node){Node=BP->SimpleConstructionScript->CreateNode(UEcoPlayerEcologyComponent::StaticClass(),TEXT("EcoPlayerEcology"));BP->SimpleConstructionScript->AddNode(Node);}
    auto* C=Cast<UEcoPlayerEcologyComponent>(Node->ComponentTemplate);if(!C)return false;
    C->AudioSet=AudioSet;
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);
    return BP->Status!=BS_Error;
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::ConfigureV3EntityConfig(UMassEntityConfigAsset* Config,bool bPredator)
{
#if WITH_EDITOR
    if(!Config||!Config->GetPathName().StartsWith(TEXT("/Game/JYU/")))return false;
    for(const auto* Trait:Config->GetConfig().GetTraits())if(!Trait->IsA<UEcoCreatureV3Trait>())return false;
    Config->Modify();
    auto* Trait=Cast<UEcoCreatureV3Trait>(Config->AddTrait(UEcoCreatureV3Trait::StaticClass()));
    if(!Trait)return false;
    Trait->bPredator=bPredator;Config->MarkPackageDirty();return true;
#else
    return false;
#endif
}
bool UEcoCreatureAnimationBuilder::ProjectPlacementPoint(UObject* Context,FVector Point,FVector& Out)
{
    UWorld* World=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    return World&&EcoCreatureMovement::ProjectSpawnPoint(*World,Point,Out);
}

bool UEcoCreatureAnimationBuilder::ValidateCopiedGroundSegment(UObject* Context,FVector From,FVector To)
{
#if WITH_EDITOR
    auto* World=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!World||!World->GetName().Contains(TEXT("LV_JYU_Ecosystem")))return false;
    return ValidateHabitatGroundSegment(Context,From,To);
#else
    return false;
#endif
}
bool UEcoCreatureAnimationBuilder::ValidateFaunaGroundSegment(UObject* Context,FName RegionId,FName SpeciesId,
    FVector From,FVector To,float BodyScale)
{
#if WITH_EDITOR
    auto* World = GEngine ? GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull) : nullptr;
    const double Distance = FVector::Dist2D(From,To);
    if (!World || From.ContainsNaN() || To.ContainsNaN() || Distance > 600. || !FMath::IsFinite(BodyScale)
        || BodyScale <= 0.f) return false;
    const auto* Regions = World->GetSubsystem<UEcologyWorldSubsystem>();
    const auto* Region = Regions ? Regions->GetRegion(RegionId) : nullptr;
    if (!RegionId.IsNone() && (!Region || !Region->ContainsPosition(From) || !Region->ContainsPosition(To))) return false;
    const FEcoFaunaSpecies* Species = nullptr;
    for (TActorIterator<AEcoCreatureIntegrationSpawner> It(World); It; ++It)
    {
        Species = It->FaunaSpecies.FindByPredicate([&](const auto& Profile) { return Profile.SpeciesId == SpeciesId; });
        if (Species) break;
    }
    if (!Species || Species->IsAquatic() || !EcoCreatureMovement::IsWadeableGround(*World,From,Species->WadeDepth)) return false;
    const int32 Steps = FMath::Max(1,FMath::CeilToInt(Distance / 10.));
    const float Radius = FMath::Clamp(Species->BodyRadius * BodyScale,1.f,120.f);
    FVector Current = From;
    for (int32 Index = 1; Index <= Steps; ++Index)
    {
        FVector Next = FMath::Lerp(From,To,double(Index) / Steps);
        Next.Z = Current.Z;
        if (!EcoCreatureMovement::ConstrainGroundStep(*World,Current,Next,Radius,Species->MinGroundNormalZ,
            Species->SweepHeight * BodyScale,Species->StepHeight) || (Region && !Region->ContainsPosition(Next))
            || FMath::Abs(Next.Z - Current.Z) > Species->StepHeight
            || !EcoCreatureMovement::IsWadeableGround(*World,Next,Species->WadeDepth)) return false;
        Current = Next;
    }
    return FMath::Abs(Current.Z - To.Z) <= 1.;
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::HasFaunaAuditSight(UObject* Context,FVector From,FVector To)
{
#if WITH_EDITOR
    const auto* World = GEngine ? GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull) : nullptr;
    return World && !From.ContainsNaN() && !To.ContainsNaN()
        && EcoFaunaDecision::HasClearSight(*World,From,To,0.f,0.f);
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::SetIslandAuditFounderPlacement(AEcoCreatureIntegrationSpawner* Spawner,int64 StableId,
    FName RegionId,FVector Location)
{
#if WITH_EDITOR
    auto* World = Spawner ? Spawner->GetWorld() : nullptr;
    if (!World || World->WorldType != EWorldType::PIE || World->GetNetMode() != NM_Standalone
        || !World->GetName().EndsWith(TEXT("LV_JYU_IslandEcosystemRefreshed"))
        || !Spawner->bReady || Spawner->Step != 0) return false;
    auto& Manager = World->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Entity = Spawner->AgentLookup.Find(StableId);
    if (Manager.IsProcessing() || !Entity || !Manager.IsEntityValid(*Entity)) return false;
    auto* Fauna = Manager.GetFragmentDataPtr<FEcoFaunaFragment>(*Entity);
    const auto& Identity = Manager.GetFragmentDataChecked<FEcoIdentityFragment>(*Entity);
    if (!Fauna || Fauna->Life.Origin != EcoLifeV3::EOrigin::Initial || Fauna->DecisionCount != 0) return false;
    FEcoFaunaPlacement Placement;
    Placement.SpeciesId = Identity.SpeciesId;
    Placement.SpawnPoints.Add(Location);
    TArray<FVector> Positions;
    if (!Spawner->BuildFaunaPositions(RegionId,Placement,Positions)) return false;
    auto& Region = Manager.GetFragmentDataChecked<FEcoRegionFragment>(*Entity);
    auto* Ecology = World->GetSubsystem<UEcologySimulationSubsystem>();
    const int32 RegionIndex = Ecology->GetRegionRuntimeIndex(RegionId);
    if (RegionIndex == INDEX_NONE) return false;
    auto& OldTotal = Spawner->SpeciesTotals.FindChecked(Region.CurrentRegionId).FindChecked(Identity.SpeciesId);
    if (OldTotal.Births <= 0) return false;
    --OldTotal.Births;
    ++Spawner->SpeciesTotals.FindOrAdd(RegionId).FindOrAdd(Identity.SpeciesId).Births;
    Region.CurrentRegionId = RegionId;
    Region.CurrentRegionIndex = RegionIndex;
    Fauna->Home = Fauna->Goal = Positions[0];
    Manager.GetFragmentDataChecked<FTransformFragment>(*Entity).GetMutableTransform().SetLocation(Positions[0]);
    return Spawner->ReconcilePopulation();
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::SplitIslandAuditForage(AEcoCreatureIntegrationSpawner* Spawner,FName PatchId,FName NewId,
    FVector Location,const TArray<FTransform>& OriginalPlants,const TArray<FTransform>& NewPlants)
{
#if WITH_EDITOR
    auto* World = Spawner ? Spawner->GetWorld() : nullptr;
    if (!World || World->WorldType != EWorldType::PIE || World->GetNetMode() != NM_Standalone
        || !World->GetName().EndsWith(TEXT("LV_JYU_IslandEcosystemRefreshed"))
        || !Spawner->bReady || Spawner->Step != 0 || NewId.IsNone() || Location.ContainsNaN()
        || Spawner->FaunaHabitatPatches.Num() >= 64) return false;
    auto& Patches = Spawner->FaunaHabitatPatches;
    auto& Stocks = Spawner->FaunaPatchStock;
    auto& Visuals = Spawner->FaunaForageVisuals;
    if (Stocks.Num() != Patches.Num() || Visuals.Num() != Patches.Num()
        || Patches.ContainsByPredicate([NewId](const auto& Patch) { return Patch.Id == NewId; })) return false;
    const int32 Index = Patches.IndexOfByPredicate([PatchId](const auto& Patch) { return Patch.Id == PatchId; });
    if (Index == INDEX_NONE) return false;
    auto* Visual = Visuals[Index].Get();
    auto& Source = Patches[Index];
    FVector Ground;
    if (!Source.IsPlantForage() || Source.Stage > Spawner->FaunaHabitatStage || Source.ShelterRadius > 0.f
        || !Visual || OriginalPlants.IsEmpty() || NewPlants.IsEmpty()
        || OriginalPlants.Num() + NewPlants.Num() != Visual->FullPlantTransforms.Num()
        || !EcoCreatureMovement::ProjectSpawnPoint(*World,Location,Ground)
        || !EcoCreatureMovement::IsWadeableGround(*World,Ground,0.f)) return false;
    const auto* Region = Spawner->FindRegion(Ground);
    if (!Region || Region->RegionId != Source.RegionId) return false;

    FActorSpawnParameters Params;
    Params.Template = Visual;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    auto* NewVisual = World->SpawnActor<AEcoForagePatchVisual>(Visual->GetClass(),FTransform(Ground),Params);
    if (!NewVisual) return false;
    NewVisual->SetActorLocation(Ground,false,nullptr,ETeleportType::TeleportPhysics);
    if (!NewVisual->GetActorLocation().Equals(Ground,1.))
    {
        NewVisual->Destroy();
        return false;
    }

    Source.Capacity *= .5f;
    Source.RegrowthPerSecond *= .5f;
    Source.PlantDryLossPerSecond *= .5f;
    Stocks[Index] *= .5f;
    FEcoFaunaHabitatPatch NewPatch = Source;
    NewPatch.Id = NewId;
    NewPatch.Center = Ground;
    const float SplitStock = Stocks[Index];
    Patches.Add(MoveTemp(NewPatch));
    Stocks.Add(SplitStock);
    Visual->FullPlantTransforms = OriginalPlants;
    NewVisual->PatchId = NewId;
    NewVisual->FullPlantTransforms = NewPlants;
    Visuals.Add(NewVisual);
    Visual->RebuildForagePreview();
    NewVisual->RebuildForagePreview();
    Spawner->PublishForageVisuals();
    return true;
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::ValidateHabitatGroundSegment(UObject* Context,FVector From,FVector To)
{
#if WITH_EDITOR
    auto* World=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    const double Distance=FVector::Dist2D(From,To);
    if(!World||From.ContainsNaN()||To.ContainsNaN()||!FMath::IsFinite(Distance)||Distance>20000)return false;
    const UEcoNaturalHabitatProfile* Profile=nullptr;
    for(TActorIterator<AEcoCreatureIntegrationSpawner> It(World);It;++It){Profile=It->NaturalHabitatProfile;break;}
    EcoNaturalHabitat::FGroundTraversal Rules;
    if(Profile){if(!Profile->IsValidProfile())return false;Rules={Profile->WalkableSlopeDegrees,Profile->MaxStepUpCm,Profile->MaxStepDownCm,Profile->MaxWadingDepthCm};}
    const int32 Pieces=FMath::Max(1,FMath::CeilToInt(Distance/30));FVector Current=From;
    for(int32 I=1;I<=Pieces;++I){
        const double Alpha=double(I)/Pieces;
        FVector Next(FMath::Lerp(From.X,To.X,Alpha),FMath::Lerp(From.Y,To.Y,Alpha),Current.Z);
        if(!EcoCreatureMovement::ConstrainGroundStep(*World,Current,Next,40,Profile?float(FMath::Cos(FMath::DegreesToRadians(Rules.MaxSlopeDegrees))):.65f))return false;
        if(Profile&&(!Rules.AllowsHeight(Current.Z,Next.Z,FVector::Dist2D(Current,Next))||!EcoCreatureMovement::IsWadeableGround(*World,Next,float(Rules.WadingDepthCm))))return false;
        Current=Next;
    }
    return FMath::Abs(Current.Z-To.Z)<=50;
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::ConfigureIntegrationGameMode(UBlueprint* BP,TSubclassOf<APawn> Pawn,TSubclassOf<APlayerController> Controller)
{
#if WITH_EDITOR
    if(!BP||!BP->GeneratedClass||!Pawn||!Controller||!BP->GetPathName().StartsWith(TEXT("/Game/JYU/")))return false;
    auto* Mode=Cast<AGameModeBase>(BP->GeneratedClass->GetDefaultObject());if(!Mode)return false;
    BP->Modify();Mode->Modify();Mode->DefaultPawnClass=Pawn;Mode->PlayerControllerClass=Controller;Mode->HUDClass=AEcoCreatureInspectorHUD::StaticClass();
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);
    Mode=Cast<AGameModeBase>(BP->GeneratedClass->GetDefaultObject());
    return Mode&&Mode->DefaultPawnClass==Pawn&&Mode->PlayerControllerClass==Controller&&Mode->HUDClass==AEcoCreatureInspectorHUD::StaticClass();
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::PrepareCopiedWorld(UObject* Context)
{
#if WITH_EDITOR
    UWorld* W=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!W||W->WorldType!=EWorldType::Editor||
        (!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/")) && W->GetPathName()!=TEXT("/Game/JWJ/1102_Integration_JWJ.1102_Integration_JWJ")))return false;
    if(auto* WP=W->GetWorldPartition()) {
        auto* Loader=WP->CreateEditorLoaderAdapter<FLoaderAdapterShape>(W,FBox(FVector(-1000000),FVector(1000000)),TEXT("JYU copied world authoring"));
        Loader->GetLoaderAdapter()->Load();
    }
    return true;
#else
    return false;
#endif
}
bool UEcoCreatureAnimationBuilder::SetCopiedLandscapeMaterial(UObject* Context,UMaterialInterface* Material)
{
#if WITH_EDITOR
    UWorld* W=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!W||W->WorldType!=EWorldType::Editor||!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/"))||!Material||!Material->GetPathName().StartsWith(TEXT("/Game/JYU/")))return false;
    int32 Count=0;
    for(TActorIterator<ALandscapeProxy> It(W);It;++It) {
        It->Modify();It->LandscapeMaterial=Material;It->UpdateAllComponentMaterialInstances(true);
        for(const auto& Component:It->LandscapeComponents) {Component->Modify();Component->MarkPackageDirty();}
        It->MarkPackageDirty();++Count;
    }
    return Count>0;
#else
    return false;
#endif
}

AActor* UEcoCreatureAnimationBuilder::SpawnVisualAuditActor(UObject* Context,TSubclassOf<AActor> ActorClass,FTransform Transform)
{
#if WITH_EDITOR
    UWorld* W=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!W||W->WorldType!=EWorldType::PIE||W->GetNetMode()!=NM_Standalone||!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/"))||!ActorClass)return nullptr;
    if(!ActorClass->IsChildOf(AEcoCreatureRepresentationActor::StaticClass())&&!ActorClass->IsChildOf(AStaticMeshActor::StaticClass())&&!ActorClass->IsChildOf(ACameraActor::StaticClass()))return nullptr;
    FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    return W->SpawnActor<AActor>(ActorClass,Transform,Params);
#else
    return nullptr;
#endif
}

bool UEcoCreatureAnimationBuilder::UpdateVisualAuditActor(AEcoCreatureRepresentationActor* Actor,UEcoCreatureAnimationProfile* Profile,FEcoCreatureVisualState State,float DeltaSeconds)
{
#if WITH_EDITOR
    UWorld* W=Actor?Actor->GetWorld():nullptr;
    if(!W||W->WorldType!=EWorldType::PIE||W->GetNetMode()!=NM_Standalone||!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/"))||!Profile||!Profile->IsValidProfile())return false;
    if(!Actor->bBound&&!Actor->BindIdentity(State.StableAgentId,State.SpeciesId))return false;
    Actor->Tags.AddUnique(TEXT("JYU.VisualAudit"));
    Actor->AnimationProfile=Profile;State.Sequence=Actor->VisualState.Sequence+1;State.WorldTime=W->GetTimeSeconds();
    State.bHasVitals=true;State.NormalizedHealth=State.NormalizedEnergy=1;
    return Actor->ConsumeVisualState(State,DeltaSeconds);
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::SetAuditPlayerGait(APawn* Player,int32 GaitIndex)
{
#if WITH_EDITOR
    UWorld* W=Player?Player->GetWorld():nullptr;
    if(!W||W->WorldType!=EWorldType::PIE||W->GetNetMode()!=NM_Standalone||!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/"))||!Player->IsPlayerControlled()||GaitIndex<0||GaitIndex>2)return false;
    auto* Bridge=Player->FindComponentByClass<UEcoPlayerEcologyComponent>();if(!Bridge)return false;
    Bridge->SetGait(EEcoPlayerGait(GaitIndex));return Bridge->Gait==EEcoPlayerGait(GaitIndex);
#else
    return false;
#endif
}
