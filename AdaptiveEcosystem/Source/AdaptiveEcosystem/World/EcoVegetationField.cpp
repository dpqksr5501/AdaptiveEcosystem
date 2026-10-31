#include "World/EcoVegetationField.h"
#include "Components/StaticMeshComponent.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "Components/BoxComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Net/UnrealNetwork.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "MassEntitySubsystem.h"
#include "Ecology/EcologySimulationSubsystem.h"

namespace {
    TAutoConsoleVariable<int32> CVarVegetation(TEXT("eco.Vegetation"), 0,
        TEXT("Opt-in native soil/vegetation and sampled ground visuals. Set before Play. -EcoVegetation also enables it."));
    bool ValidHabitatBounds(const UBoxComponent* Bounds)
    {
        if (!IsValid(Bounds)) return false;
        const auto& Transform = Bounds->GetComponentTransform();
        const auto Extent = Bounds->GetUnscaledBoxExtent();
        return Transform.IsValid() && !Extent.ContainsNaN() && Extent.GetMin() > UE_SMALL_NUMBER
            && Transform.GetScale3D().GetAbs().GetMin() > UE_SMALL_NUMBER;
    }
}

AEcoVegetationHabitat::AEcoVegetationHabitat()
{
    Bounds = CreateDefaultSubobject<UBoxComponent>(TEXT("HabitatBounds"));
    SetRootComponent(Bounds); Bounds->SetBoxExtent(FVector(1000)); Bounds->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    WaterSurface=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("AuthoredShallowWater"));WaterSurface->SetupAttachment(Bounds);
    WaterSurface->SetCollisionEnabled(ECollisionEnabled::NoCollision);WaterSurface->SetCanEverAffectNavigation(false);WaterSurface->SetVisibility(false);
    WaterMaterial=TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/JYU/Materials/M_JYU_Surface_Water.M_JYU_Surface_Water")));
}
void AEcoVegetationHabitat::OnConstruction(const FTransform& Transform)
{Super::OnConstruction(Transform);RefreshWaterVisual();}
void AEcoVegetationHabitat::BeginPlay()
{Super::BeginPlay();RefreshWaterVisual();}
void AEcoVegetationHabitat::RefreshWaterVisual()
{
    if(!WaterSurface)return;
    const bool Visible=bConnectedFreshWater&&FMath::IsFinite(WaterSurfaceZ)&&FMath::IsFinite(WaterSurfaceSizeCm.X)&&FMath::IsFinite(WaterSurfaceSizeCm.Y)
        &&WaterSurfaceSizeCm.X>=100&&WaterSurfaceSizeCm.X<=4000&&WaterSurfaceSizeCm.Y>=100&&WaterSurfaceSizeCm.Y<=4000;
    WaterSurface->SetVisibility(Visible&&GetNetMode()!=NM_DedicatedServer);
    if(!Visible||GetNetMode()==NM_DedicatedServer)return;
    WaterSurface->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Plane.Plane")));
    if(!WaterMaterial.IsNull())WaterSurface->SetMaterial(0,WaterMaterial.LoadSynchronous());
    WaterSurface->SetWorldLocation(FVector(GetActorLocation().X,GetActorLocation().Y,WaterSurfaceZ));
    WaterSurface->SetWorldScale3D(FVector(WaterSurfaceSizeCm.X/100.,WaterSurfaceSizeCm.Y/100.,1));
}
bool AEcoVegetationHabitat::IsValidHabitat() const
{
    return ValidHabitatBounds(Bounds) && Plant >= 0 && Plant <= 2 && FMath::IsFinite(Drainage) && Drainage >= 0 && Drainage <= 1
        && FMath::IsFinite(Shade) && Shade >= 0 && Shade <= 1
        && (!bConnectedFreshWater || (FMath::IsFinite(WaterSurfaceZ) && FMath::IsFinite(MaxSupplyRiseCm)
            && MaxSupplyRiseCm > 0 && MaxSupplyRiseCm <= 200
            &&FMath::IsFinite(WaterSurfaceSizeCm.X)&&FMath::IsFinite(WaterSurfaceSizeCm.Y)
            &&WaterSurfaceSizeCm.X>=100&&WaterSurfaceSizeCm.X<=4000&&WaterSurfaceSizeCm.Y>=100&&WaterSurfaceSizeCm.Y<=4000));
}
bool AEcoVegetationHabitat::ContainsGround(const FVector& Point) const
{
    if (Point.ContainsNaN() || !ValidHabitatBounds(Bounds)) return false;
    const FVector Extent = Bounds->GetUnscaledBoxExtent();
    return FBox(-Extent, Extent).IsInsideOrOn(Bounds->GetComponentTransform().InverseTransformPosition(Point));
}
AEcoVegetationField::AEcoVegetationField()
{
    bReplicates = true;
    // Spatial actor relevance, independent of whether native ecology continues off screen.
    SetNetCullDistanceSquared(FMath::Square(50000.f));
    SetNetUpdateFrequency(1);
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    Plants = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Plants"));
    SetRootComponent(Plants);
    Plants->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Plants->SetCanEverAffectNavigation(false);
    Plants->NumCustomDataFloats = 3;
    RiparianPlants=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("RiparianPlants"));
    ShrubPlants=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ShrubPlants"));
    Tracks=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("MovementMarks"));
    for(auto* Component:{RiparianPlants.Get(),ShrubPlants.Get(),Tracks.Get()}){
        Component->SetupAttachment(Plants);Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Component->SetCanEverAffectNavigation(false);Component->NumCustomDataFloats=3;
    }
    PatchMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassD.SM_MWAM_GrassD")));
}
void AEcoVegetationField::BeginPlay()
{
    Super::BeginPlay();
    if (GetNetMode() != NM_DedicatedServer)
    {
        Plants->SetStaticMesh(PatchMesh.LoadSynchronous());
        if (!PatchMaterial.IsNull()) Plants->SetMaterial(0, PatchMaterial.LoadSynchronous());
        RiparianPlants->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassC.SM_MWAM_GrassC")));
        ShrubPlants->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Game/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassB.SM_MWAM_GrassB")));
        for(auto* Component:{RiparianPlants.Get(),ShrubPlants.Get()})if(!PatchMaterial.IsNull())Component->SetMaterial(0,PatchMaterial.LoadSynchronous());
        Tracks->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
        OnRep_Cells();
    }
}
bool AEcoVegetationField::IsRequested()
{
    return CVarVegetation.GetValueOnGameThread() != 0 || FParse::Param(FCommandLine::Get(), TEXT("EcoVegetation"));
}
void AEcoVegetationField::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AEcoVegetationField, RegionId);
    DOREPLIFETIME(AEcoVegetationField, Cells);
    DOREPLIFETIME(AEcoVegetationField, MovementMarks);
}
void AEcoVegetationField::GatherGround()
{
    auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ctx = Sub && Sub->IsActive() ? Sub->GetContext(ContextIndex) : nullptr;
    if (!Ctx || Ctx->RegionId != RegionId) return;
    auto& Grid = Ctx->Sim.Food;
    const int32 Count = int32(Grid.Food.size());
    // Refresh ground in bounded slices, including previously failed/streamed cells.
    if (NextGroundCell >= Count)
    {
        if (GetWorld()->GetTimeSeconds() < NextGroundRefresh) return;
        NextGroundCell = 0;
    }
    TArray<AEcoVegetationHabitat*> Inputs;
    for (TActorIterator<AEcoVegetationHabitat> It(GetWorld()); It; ++It)
        if (It->RegionId == RegionId)
        {
            if (!It->IsValidHabitat())
            { UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoVegetation] Unsupported authoring %s"), *It->GetPathName()); Sub->RejectResourceContract(); return; }
            Inputs.Add(*It);
        }
    Inputs.Sort([](const AEcoVegetationHabitat& A, const AEcoVegetationHabitat& B) { return A.GetPathName() < B.GetPathName(); });
    for (int32 Budget = 0; Budget < 32 && NextGroundCell < Count; ++Budget, ++NextGroundCell)
    {
        const int32 K = NextGroundCell;
        const FVector Hint = Ctx->UnitsToCm((K % Grid.Gw + 0.5) * Grid.Cell, (K / Grid.Gw + 0.5) * Grid.Cell, Ctx->OriginCm.Z);
        FHitResult Hit; FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoVegetationGround), false, this);
        if (!GetWorld()->LineTraceSingleByChannel(Hit, Hint + FVector(0,0,5000), Hint - FVector(0,0,20000), ECC_WorldStatic, Params))
        { Ground.Remove(K); continue; } // terrain unavailable: hidden, retry next cycle
        EcoVegetationV3::FHabitat H;
        H.bGroundUsable = Hit.ImpactNormal.Z >= 0.65;
        H.Drainage = FMath::Clamp(1.0 - double(Hit.ImpactNormal.Z) * 0.5, 0.0, 1.0);
        for (const auto* Input : Inputs)
        {
            if (!Input->ContainsGround(Hit.ImpactPoint)) continue;
            if (!Input->IsValidHabitat())
            { UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoVegetation] Unsupported authoring %s"), *Input->GetPathName()); Sub->RejectResourceContract(); return; }
            H.Plant = static_cast<EcoVegetationV3::EPlant>(Input->Plant);
            H.Drainage = Input->Drainage; H.Shade = Input->Shade;
            if (Input->bConnectedFreshWater && FMath::IsFinite(Input->WaterSurfaceZ)
                && FMath::IsFinite(Input->MaxSupplyRiseCm) && Input->MaxSupplyRiseCm > 0 && Input->MaxSupplyRiseCm <= 200)
            {
                const double Rise = Hit.ImpactPoint.Z - Input->WaterSurfaceZ;
                H.WaterSupply = EcoVegetationV3::Unit(1 - FMath::Max(0.0, Rise) / Input->MaxSupplyRiseCm);
                H.Flood = EcoVegetationV3::Unit(-Rise / 100.0);
            }
            break; // stable precedence for overlaps, no additive water creation
        }
        if (!H.IsValid())
        { UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoVegetation] Invalid habitat %s cell %d"), *RegionId.ToString(), K); Sub->RejectResourceContract(); return; }
        Grid.Habitats[K] = H;
        if (H.bGroundUsable) Ground.Add(K, Hit.ImpactPoint);
        else Ground.Remove(K);
    }
    if (NextGroundCell >= Count) NextGroundRefresh = GetWorld()->GetTimeSeconds() + 5;
}
void AEcoVegetationField::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (GetNetMode() == NM_Client || !HasAuthority()) { SetActorTickEnabled(false); return; }
    const auto* Mass = GetWorld()->GetSubsystem<UMassEntitySubsystem>();
    if (Mass && Mass->GetEntityManager().IsProcessing()) return;
    auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ctx = Sub && Sub->IsActive() ? Sub->GetContext(ContextIndex) : nullptr;
    if (!Ctx || Ctx->RegionId != RegionId || !Ctx->Sim.Food.Vegetation.bEnabled) return;
    if (!Ctx->Sim.Food.HasValidVegetationLayout()) { Sub->RejectResourceContract(); return; }
    GatherGround();
    if (!Sub->IsActive()) return;
    if (GetWorld()->GetTimeSeconds() < NextPublish) return;
    NextPublish = GetWorld()->GetTimeSeconds() + 1;
    const auto& Grid = Ctx->Sim.Food;
    Cells.Reset();
    // Up to 256 representative logical cells per region. These are samples, not
    // separate patches or an estimate to write back into the food grid.
    const int32 Stride = FMath::Max(1, FMath::DivideAndRoundUp(int32(Grid.Food.size()), 256));
    for (int32 K = 0; K < int32(Grid.Food.size()); K += Stride)
    {
        const FVector* Anchor = Ground.Find(K); if (!Anchor || Grid.Cap[K] <= 0) continue;
        auto& V = Cells.AddDefaulted_GetRef(); V.Cell = K; V.Position = *Anchor;
        V.Food = uint8(FMath::RoundToInt(EcoVegetationV3::Unit(Grid.Food[K] / Grid.Cap[K]) * 255));
        V.Moisture = uint8(FMath::RoundToInt(Grid.VegetationCells[K].Moisture * 255));
        V.Stress = uint8(FMath::RoundToInt(Grid.VegetationCells[K].Stress * 255));
        V.Plant=uint8(Grid.Habitats[K].Plant);
    }
    MovementMarks.Reset();const double Now=Ctx->Sim.T*EcoRepertoireV3::kStepSeconds;
    for(const auto& T:Ctx->MovementTraces.Events)if(T.Id&&Now>=T.Time&&Now-T.Time<20){
        if(MovementMarks.Num()>=64)break;
        auto& Mark=MovementMarks.AddDefaulted_GetRef();Mark.Position=Ctx->UnitsToCm(T.X,T.Y,T.Z+2);Mark.Age=uint8((Now-T.Time)*255/20);
    }
    if (GetNetMode() != NM_DedicatedServer) OnRep_Cells();
}
void AEcoVegetationField::OnRep_Cells()
{
    Plants->ClearInstances();RiparianPlants->ClearInstances();ShrubPlants->ClearInstances();Tracks->ClearInstances();
    if (!Plants->GetStaticMesh()) return;
    for (const auto& V : Cells)
    {
        auto* Component=V.Plant==1?RiparianPlants.Get():V.Plant==2?ShrubPlants.Get():Plants.Get();
        if(!Component->GetStaticMesh())continue;
        const FBox Box=Component->GetStaticMesh()->GetBoundingBox();
        const float Amount = V.Food / 255.f;
        if (Amount <= 0.01f) continue;
        // A grass mesh is often authored in centimetres as one tiny tuft. Give
        // this logical cell a bounded 1.2m patch footprint, independently of its
        // <=45cm height, so its food change can be read beside the animals.
        const FVector MeshSize = Box.GetSize();
        const double Width = FMath::Clamp(double(PatchWidthCm), 10.0, 400.0) * FMath::Sqrt(Amount) / FMath::Max(1.0, FMath::Max(MeshSize.X, MeshSize.Y));
        const double TargetHeight=V.Plant==2?80:V.Plant==1?65:double(PatchHeightCm);
        const double Height = FMath::Clamp(TargetHeight, 5.0, 100.0) / FMath::Max(1.0, MeshSize.Z) * (0.2 + 0.8 * Amount);
        FVector P = V.Position; P.Z -= Box.Min.Z * Height;
        const FTransform T(FRotator(0, (V.Cell * 137) % 360, 0), P, FVector(Width, Width, Height));
        const int32 Instance = Component->AddInstance(T, true);
        Component->SetCustomDataValue(Instance, 0, Amount, false);
        Component->SetCustomDataValue(Instance, 1, V.Moisture / 255.f, false);
        Component->SetCustomDataValue(Instance, 2, V.Stress / 255.f, false);
    }
    for(auto* C:{Plants.Get(),RiparianPlants.Get(),ShrubPlants.Get()})C->MarkRenderStateDirty();
    if(Tracks->GetStaticMesh())for(const auto& Mark:MovementMarks){
        const double Scale=1-Mark.Age/255.;Tracks->AddInstance(FTransform(FRotator::ZeroRotator,Mark.Position,FVector(.25*Scale,.12*Scale,.015)),true);
    }
}
FString AEcoVegetationField::CaptureDiagnostics(bool bIncludeLearningCells) const
{
    if(!IsInGameThread())return TEXT("{\"rejected\":\"GameThreadRequired\"}");
    const bool bAuthority = GetNetMode() != NM_Client && HasAuthority();
    auto J = MakeShared<FJsonObject>(); J->SetStringField(TEXT("region"), RegionId.ToString());
    J->SetBoolField(TEXT("authority"), bAuthority); J->SetNumberField(TEXT("visual_cells"), Cells.Num());
    J->SetNumberField(TEXT("instances"), Plants->GetInstanceCount()+RiparianPlants->GetInstanceCount()+ShrubPlants->GetInstanceCount());
    J->SetNumberField(TEXT("riparian_instances"),RiparianPlants->GetInstanceCount());J->SetNumberField(TEXT("shrub_instances"),ShrubPlants->GetInstanceCount());
    J->SetNumberField(TEXT("movement_marks"),MovementMarks.Num());
    J->SetStringField(TEXT("visual_class"), GetClass()->GetPathName());
    J->SetStringField(TEXT("visual_mesh"), PatchMesh.ToSoftObjectPath().ToString());
    J->SetStringField(TEXT("visual_material"), PatchMaterial.ToSoftObjectPath().ToString());
    if (bAuthority)
    {
        const auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
        if (const auto* Ctx = Sub ? Sub->GetContext(ContextIndex) : nullptr)
        {
            if(bIncludeLearningCells){
                const auto* Mass=GetWorld()->GetSubsystem<UMassEntitySubsystem>();
                if(Mass&&Mass->GetEntityManager().IsProcessing())return TEXT("{\"rejected\":\"MassProcessing\"}");
                const auto& F=Ctx->Sim.Food;
                J->SetStringField(TEXT("learning_world_schema"),TEXT("ecosystem-life-v1"));J->SetBoolField(TEXT("training_ready"),false);
                J->SetStringField(TEXT("seed"),LexToString(Ctx->Sim.Config.Seed));J->SetStringField(TEXT("rng_state"),LexToString(Ctx->Sim.Rng.State));
                J->SetNumberField(TEXT("native_unit_cm"),EcoRepertoireV3::kUnitCm);J->SetNumberField(TEXT("step_seconds"),EcoRepertoireV3::kStepSeconds);
                J->SetNumberField(TEXT("cell_size_units"),F.Cell);J->SetNumberField(TEXT("grid_width"),F.Gw);
                J->SetNumberField(TEXT("temperature"),F.VegetationWeather.Temperature);J->SetNumberField(TEXT("light"),F.VegetationWeather.Light);
                J->SetArrayField(TEXT("native_origin_cm"),{MakeShared<FJsonValueNumber>(Ctx->OriginCm.X),MakeShared<FJsonValueNumber>(Ctx->OriginCm.Y),MakeShared<FJsonValueNumber>(Ctx->OriginCm.Z)});
                auto Rates=MakeShared<FJsonObject>();Rates->SetNumberField(TEXT("infiltration"),F.Vegetation.Infiltration);Rates->SetNumberField(TEXT("evaporation"),F.Vegetation.Evaporation);
                Rates->SetNumberField(TEXT("drainage"),F.Vegetation.Drainage);Rates->SetNumberField(TEXT("uptake"),F.Vegetation.Uptake);Rates->SetNumberField(TEXT("stress_loss"),F.Vegetation.StressLoss);J->SetObjectField(TEXT("soil_parameters"),Rates);
                TArray<TSharedPtr<FJsonValue>> Samples;
                if(F.HasValidVegetationLayout()&&F.Vegetation.bEnabled)for(size_t K=0;K<F.Food.size();++K){
                    auto Row=MakeShared<FJsonObject>();const auto& H=F.Habitats[K];const auto& S=F.VegetationCells[K];
                    Row->SetNumberField(TEXT("cell"),double(K));Row->SetNumberField(TEXT("food"),F.Food[K]);Row->SetNumberField(TEXT("capacity"),F.Cap[K]);Row->SetNumberField(TEXT("regen_per_step"),F.Regen[K]);
                    Row->SetNumberField(TEXT("moisture"),S.Moisture);Row->SetNumberField(TEXT("stress"),S.Stress);Row->SetNumberField(TEXT("plant"),int32(H.Plant));
                    Row->SetNumberField(TEXT("drainage"),H.Drainage);Row->SetNumberField(TEXT("shade"),H.Shade);Row->SetNumberField(TEXT("water_supply"),H.WaterSupply);Row->SetNumberField(TEXT("flood"),H.Flood);Row->SetBoolField(TEXT("ground_usable"),H.bGroundUsable);
                    Samples.Add(MakeShared<FJsonValueObject>(Row));
                }
                J->SetArrayField(TEXT("logical_cells"),Samples);
            }
            const auto& G = Ctx->Sim.Food; double Moisture = 0;
            for (const auto& S : G.VegetationCells) Moisture += S.Moisture;
            J->SetNumberField(TEXT("food"), G.Total()); J->SetNumberField(TEXT("grown"), G.VegetationGrown);
            J->SetNumberField(TEXT("environment_lost"), G.EnvironmentLost);
            J->SetNumberField(TEXT("consumed"), Ctx->Sim.Stats.FoodEaten);
            J->SetNumberField(TEXT("mean_moisture"), G.VegetationCells.empty() ? 0 : Moisture / G.VegetationCells.size());
            J->SetNumberField(TEXT("rain"), G.VegetationWeather.Rain);
            J->SetNumberField(TEXT("ground_cells"), Ground.Num());
            int32 Counts[3] = {}; int32 Connected = 0;
            for (const auto& H : G.Habitats)
            {
                const int32 Plant = int32(H.Plant); if (Plant >= 0 && Plant < 3) ++Counts[Plant];
                if (H.WaterSupply > 0 || H.Flood > 0) ++Connected;
            }
            J->SetNumberField(TEXT("grass_cells"), Counts[0]);
            J->SetNumberField(TEXT("riparian_cells"), Counts[1]);
            J->SetNumberField(TEXT("shrub_cells"), Counts[2]);
            J->SetNumberField(TEXT("connected_water_cells"), Connected);
            J->SetNumberField(TEXT("native_step"), double(Ctx->Sim.T));
            FEcoSpatialFoodAudit Audit;
            if (const auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>(); Ecology && Ecology->GetSpatialFoodAudit(RegionId, Audit))
            {
                J->SetNumberField(TEXT("ledger_amount"), Audit.Amount);
                J->SetNumberField(TEXT("ledger_consumed"), Audit.Consumed);
                J->SetNumberField(TEXT("ledger_grown"), Audit.Regenerated);
                J->SetNumberField(TEXT("ledger_environment_lost"), Audit.EnvironmentLost);
                J->SetNumberField(TEXT("ledger_habitat_removed"), Audit.HabitatRemoved);
                J->SetNumberField(TEXT("receipt_sequence"), double(Audit.Sequence));
            }
        }
    }
    FString Text; const auto Writer = TJsonWriterFactory<>::Create(&Text); FJsonSerializer::Serialize(J, Writer); return Text;
}
