#include "World/EcoVegetationField.h"
#include "Components/StaticMeshComponent.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "Components/BoxComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Engine/World.h"
#include "Engine/GameInstance.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Misc/Crc.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Net/UnrealNetwork.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "MassEntitySubsystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "ProfilingDebugging/CsvProfiler.h"
#include "Engine/NetConnection.h"
#include "Serialization/ArchiveCountMem.h"

CSV_DEFINE_CATEGORY(EcoGrass, true);

namespace {
    TAutoConsoleVariable<int32> CVarVegetation(TEXT("eco.Vegetation"), 0,
        TEXT("Opt-in native soil/vegetation and ground visuals. Set before Play. -EcoVegetation also enables it."));
    TAutoConsoleVariable<int32> CVarFoodGrass(TEXT("eco.Grass.Enable"), 0,
        TEXT("Publish spatial food as grass without enabling soil. Set before Play."));
    TAutoConsoleVariable<int32> CVarShowFoodGrass(TEXT("eco.Grass.Visual"), 1,
        TEXT("Show food grass on this machine. Does not affect simulation."));
    TAutoConsoleVariable<int32> CVarPatchLayout(TEXT("eco.Grass.PatchLayout"), 0,
        TEXT("S1 opt-in shared patch layout/authority ground only. Set before Play. Consumption remains cell-based."));
#if !UE_BUILD_SHIPPING
    TAutoConsoleVariable<int32> CVarGrassNetAudit(TEXT("eco.Grass.NetAudit"), 0,
        TEXT("Log actual VisualGrid writer bits and newest base-state dynamic bytes per connection. QA only."));
#endif

    bool ValidHabitatBounds(const UBoxComponent* Bounds)
    {
        if (!IsValid(Bounds)) return false;
        const auto& Transform = Bounds->GetComponentTransform();
        const auto Extent = Bounds->GetUnscaledBoxExtent();
        return Transform.IsValid() && !Extent.ContainsNaN() && Extent.GetMin() > UE_SMALL_NUMBER
            && Transform.GetScale3D().GetAbs().GetMin() > UE_SMALL_NUMBER;
    }
}

bool FEcoVegetationVisualGrid::NetDeltaSerialize(FNetDeltaSerializeInfo& Params)
{
#if !UE_BUILD_SHIPPING
    const int64 Before = Params.Writer ? Params.Writer->GetNumBits() : 0;
#endif
    const bool bWrote = FastArrayDeltaSerialize<FEcoVegetationVisualCell, FEcoVegetationVisualGrid>(Cells, Params, *this);
#if !UE_BUILD_SHIPPING
    if (bWrote && Params.Writer && Params.Connection && !Params.bIsInitializingBaseFromDefault
        && IsInGameThread() && CVarGrassNetAudit.GetValueOnGameThread() != 0)
    {
        const auto* Field = Cast<AEcoVegetationField>(Params.CustomDeltaObject ? Params.CustomDeltaObject : Params.Object);
        if (Field && Field->HasAuthority())
        {
            FArchiveCountMem Counter(nullptr);
            if (Params.NewState && Params.NewState->IsValid()) (*Params.NewState)->CountBytes(Counter);
            UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoGrassNet] Conn=%s Region=%s Bits=%lld BaseDynamicBytes=%llu"),
                *Params.Connection->LowLevelGetRemoteAddress(true), *Field->RegionId.ToString(),
                Params.Writer->GetNumBits() - Before, uint64(Counter.GetMax()));
        }
    }
#endif
    return bWrote;
}

bool FEcoFoodPatchGroundCell::Matches(const FEcoFoodPatchLayout& Layout) const
{
    return Layout.IsValid() && MatchesValidatedLayout(Layout);
}

bool FEcoFoodPatchGroundCell::NetSerialize(FArchive& Ar, UPackageMap*, bool& bOutSuccess)
{
    uint32 WireCell = uint32(Cell), WireRevision = Revision;
    uint32 Count = uint32(RelativePositions.Num());
    Ar.SerializeIntPacked(WireCell); Ar.SerializeIntPacked(Epoch); Ar << SettingsHash;
    Ar.SerializeIntPacked(WireRevision); Ar.SerializeBits(&Count, 5);
    if (Ar.IsError() || WireCell >= 65536 || Count < 1 || Count > 25)
    { Ar.SetError(); bOutSuccess = false; return false; }
    Ar.SerializeBits(&ValidMask, Count);
    int32 Base = 0; uint32 DeltaBits = 0;
    if (Ar.IsSaving())
    {
        Base = MAX_int32; int32 Maximum = MIN_int32;
        for (const auto& Position : RelativePositions)
        {
            if (!FMath::IsFinite(Position.Z) || FMath::Abs(Position.Z) > 1000000)
            { Ar.SetError(); bOutSuccess = false; return false; }
            const int32 Z = FMath::RoundToInt(Position.Z); Base = FMath::Min(Base, Z); Maximum = FMath::Max(Maximum, Z);
        }
        DeltaBits = uint32(FMath::CeilLogTwo(uint32(Maximum - Base) + 1));
    }
    Ar << Base; Ar.SerializeBits(&DeltaBits, 5);
    if (Ar.IsError() || FMath::Abs(int64(Base)) > 1000000 || DeltaBits > 21)
    { Ar.SetError(); bOutSuccess = false; return false; }
    if (Ar.IsLoading()) { RelativePositions.SetNum(Count); Normals.Init(FVector_NetQuantizeNormal(FVector::ZeroVector), Count); }
    for (uint32 I = 0; I < Count; ++I)
    {
        uint32 Delta = Ar.IsSaving() ? uint32(FMath::RoundToInt(RelativePositions[I].Z) - Base) : 0;
        if (DeltaBits) Ar.SerializeBits(&Delta, DeltaBits);
        if (Ar.IsLoading()) RelativePositions[I] = FVector_NetQuantize10(FVector(0,0,double(Base) + Delta));
    }
    if (Ar.IsLoading()) { Cell = int32(WireCell); Revision = WireRevision; bHeightOnlyFromWire = true; }
    bOutSuccess = !Ar.IsError(); return bOutSuccess;
}

bool FEcoFoodPatchGroundCell::MatchesValidatedLayout(const FEcoFoodPatchLayout& Layout) const
{
    return Epoch == Layout.Epoch && SettingsHash == Layout.SettingsHash && Revision > 0
        && Cell >= 0 && Cell < Layout.GridWidth * Layout.GridWidth
        && RelativePositions.Num() == Layout.PatchCount && Normals.Num() == Layout.PatchCount
        && (ValidMask >> Layout.PatchCount) == 0;
}

bool FEcoFoodPatchGroundGrid::NetDeltaSerialize(FNetDeltaSerializeInfo& Params)
{
#if !UE_BUILD_SHIPPING
    const int64 Before = Params.Writer ? Params.Writer->GetNumBits() : 0;
#endif
    const bool bWrote = FastArrayDeltaSerialize<FEcoFoodPatchGroundCell, FEcoFoodPatchGroundGrid>(Cells, Params, *this);
#if !UE_BUILD_SHIPPING
    if (bWrote && Params.Writer && Params.Connection && !Params.bIsInitializingBaseFromDefault
        && IsInGameThread() && CVarGrassNetAudit.GetValueOnGameThread() != 0)
    {
        const auto* Field = Cast<AEcoVegetationField>(Params.CustomDeltaObject ? Params.CustomDeltaObject : Params.Object);
        if (Field && Field->HasAuthority())
            UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoPatchGroundNet] Conn=%s Region=%s Bits=%lld"),
                *Params.Connection->LowLevelGetRemoteAddress(true), *Field->RegionId.ToString(), Params.Writer->GetNumBits() - Before);
    }
#endif
    return bWrote;
}

uint16 FEcoVegetationVisualCell::EncodeAmount(double Amount)
{
    if (!FMath::IsFinite(Amount) || Amount <= 0) return 0;
    return uint16(FMath::Max(1, FMath::RoundToInt(FMath::Min(Amount, 1.) * 65535.)));
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
bool AEcoVegetationHabitat::HasWaterSupply() const
{
#if !UE_BUILD_SHIPPING
    if (DebugWaterConnection.IsSet()) return DebugWaterConnection.GetValue();
#endif
    return bConnectedFreshWater;
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
    PatchMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassD.SM_MWAM_GrassD")));
    RiparianMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassC.SM_MWAM_GrassC")));
    ShrubMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Plants/SM_MWAM_GrassB.SM_MWAM_GrassB")));
}
void AEcoVegetationField::BeginPlay()
{
    Super::BeginPlay();
    if (GetNetMode() != NM_DedicatedServer)
    {
        UStaticMesh* GrassMesh = PatchMesh.LoadSynchronous();
        if (!GrassMesh)
        {
            const auto* Defaults = GetDefault<AEcoVegetationField>();
            GrassMesh = Defaults->PatchMesh.LoadSynchronous();
        }
        Plants->SetStaticMesh(GrassMesh);
        if (!PatchMaterial.IsNull()) Plants->SetMaterial(0, PatchMaterial.LoadSynchronous());
        RiparianPlants->SetStaticMesh(RiparianMesh.LoadSynchronous());
        ShrubPlants->SetStaticMesh(ShrubMesh.LoadSynchronous());
        for(auto* Component:{RiparianPlants.Get(),ShrubPlants.Get()})if(!PatchMaterial.IsNull())Component->SetMaterial(0,PatchMaterial.LoadSynchronous());
        Tracks->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
        OnRep_MovementMarks();
    }
}
bool AEcoVegetationField::IsRequested()
{
    return CVarVegetation.GetValueOnGameThread() != 0 || FParse::Param(FCommandLine::Get(), TEXT("EcoVegetation"));
}
bool AEcoVegetationField::IsVisualRequested()
{
    return CVarFoodGrass.GetValueOnGameThread() != 0;
}

void AEcoVegetationField::ConfigureGrid(float InCellWidthCm, float InGridSizeCm, int32 InSeed)
{
    CellWidthCm = InCellWidthCm;
    GridSizeCm = InGridSizeCm;
    LayoutSeed = InSeed;
    bEnablePatchLayout = bEnablePatchLayout || CVarPatchLayout.GetValueOnGameThread() != 0;
    PatchLayoutMode = bEnablePatchLayout ? 1 : 0;
}

bool AEcoVegetationField::IsNetRelevantFor(const AActor* RealViewer, const AActor* ViewTarget, const FVector& SrcLocation) const
{
    if (GridSizeCm <= 0) return Super::IsNetRelevantFor(RealViewer, ViewTarget, SrcLocation);
    const FVector Local = SrcLocation - GetActorLocation();
    const double X = Local.X - FMath::Clamp(Local.X, 0., double(GridSizeCm));
    const double Y = Local.Y - FMath::Clamp(Local.Y, 0., double(GridSizeCm));
    return X * X + Y * Y <= GetNetCullDistanceSquared();
}

void AEcoVegetationField::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AEcoVegetationField, RegionId);
    DOREPLIFETIME(AEcoVegetationField, VisualGrid);
    DOREPLIFETIME(AEcoVegetationField, CellWidthCm);
    DOREPLIFETIME(AEcoVegetationField, GridSizeCm);
    DOREPLIFETIME(AEcoVegetationField, LayoutSeed);
    DOREPLIFETIME(AEcoVegetationField, MovementMarks);
    DOREPLIFETIME(AEcoVegetationField, PatchLayout);
    DOREPLIFETIME(AEcoVegetationField, PatchGround);
    DOREPLIFETIME(AEcoVegetationField, PatchLayoutMode);
}

bool AEcoVegetationField::EnsurePatchLayout()
{
    if (!bEnablePatchLayout || !IsInGameThread() || !HasAuthority() || GetNetMode() == NM_Client) return false;
    auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ctx = Sub && Sub->IsActive() ? Sub->GetContext(ContextIndex) : nullptr;
    if (!Ctx || Ctx->RegionId != RegionId) return false;
    auto& Cache = Ctx->FoodPatchCache;
    // Capture gameplay count once. Later render-detail edits cannot change IDs or redistribute resources.
    if (Cache.Layout.IsValid())
    {
        PatchLayout = Cache.Layout;
        return true;
    }
    FEcoFoodPatchLayout Descriptor;
    Descriptor.RegionId = RegionId; Descriptor.Seed = LayoutSeed; Descriptor.Epoch = 1;
    Descriptor.GridWidth = Ctx->Sim.Food.Gw; Descriptor.CellWidthCm = CellWidthCm;
    Descriptor.PatchCount = CandidatesPerCell; Descriptor.OriginCm = Ctx->OriginCm;
    if (Descriptor.PatchCount > 9)
    {
        UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoFoodPatch] S1 network layout supports 1..9 candidates; higher counts require S4 snapshot chunking"));
        Sub->RejectResourceContract(); return false;
    }
    Descriptor.SettingsHash = Descriptor.CalculateHash();
    if (!Cache.Initialize(Descriptor))
    {
        UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoFoodPatch] Invalid layout configuration in %s"), *RegionId.ToString());
        Sub->RejectResourceContract(); return false;
    }
    PatchLayout = Cache.Layout;
    UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoFoodPatch] Region=%s Epoch=%u Hash=%u Patches=%d StaticBytes=%llu (S1; cell consumption)"),
        *RegionId.ToString(), PatchLayout.Epoch, PatchLayout.SettingsHash, Cache.Patches.Num(), uint64(Cache.Patches.GetAllocatedSize()));
    return true;
}

bool AEcoVegetationField::InvalidatePatchGround()
{
    if (!IsInGameThread() || GetNetMode() == NM_Client || !HasAuthority()) return false;
    const auto* Mass = GetWorld()->GetSubsystem<UMassEntitySubsystem>();
    if (Mass && Mass->GetEntityManager().IsProcessing()) return false;
    auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ctx = Sub ? Sub->GetContext(ContextIndex) : nullptr;
    if (!Ctx || Ctx->RegionId != RegionId || !Ctx->FoodPatchCache.Layout.Matches(PatchLayout)) return false;
    Ctx->FoodPatchCache.InvalidateGround();
    // Invalidate published anchors immediately; clients cannot keep displaying previously usable terrain.
    for (auto& Cell : PatchGround.Cells) { Cell.ValidMask = 0; ++Cell.Revision; PatchGround.MarkItemDirty(Cell); }
    NextPatchGround = 0; NextPatchGroundSweep = 0;
    return true;
}

void AEcoVegetationField::PublishPatchGroundCell(int32 Cell)
{
    auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const auto* Ctx = Sub->GetContext(ContextIndex);
    const auto& Cache = Ctx->FoodPatchCache;
    if (PublishedPatchCells.Num() != PatchLayout.GridWidth * PatchLayout.GridWidth)
        PublishedPatchCells.Init(INDEX_NONE, PatchLayout.GridWidth * PatchLayout.GridWidth);
    uint32 Mask = 0;
    for (int32 Candidate = 0; Candidate < PatchLayout.PatchCount; ++Candidate)
    {
        const auto& Patch = Cache.Patches[Cell * PatchLayout.PatchCount + Candidate];
        if (Patch.GroundRevision == 0) return; // stage the entire cell before publishing
        if (Patch.bGroundUsable) Mask |= 1u << Candidate;
    }
    int32& Index = PublishedPatchCells[Cell];
    if (Index == INDEX_NONE) Index = PatchGround.Cells.AddDefaulted();
    auto& Out = PatchGround.Cells[Index];
    Out.Cell = Cell; Out.Epoch = PatchLayout.Epoch; Out.SettingsHash = PatchLayout.SettingsHash;
    Out.ValidMask = Mask; ++Out.Revision;
    Out.RelativePositions.SetNum(PatchLayout.PatchCount); Out.Normals.SetNum(PatchLayout.PatchCount);
    for (int32 Candidate = 0; Candidate < PatchLayout.PatchCount; ++Candidate)
    {
        const auto& Patch = Cache.Patches[Cell * PatchLayout.PatchCount + Candidate];
        Out.RelativePositions[Candidate] = FVector_NetQuantize10(FVector(Patch.RelativePosition));
        Out.Normals[Candidate] = FVector_NetQuantizeNormal(FVector(Patch.Normal));
    }
    PatchGround.MarkItemDirty(Out);
}

void AEcoVegetationField::GatherPatchGround()
{
    CSV_SCOPED_TIMING_STAT(EcoGrass, GatherPatchGround);
    auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ctx = Sub->GetContext(ContextIndex);
    auto& Cache = Ctx->FoodPatchCache;
    const double Now = GetWorld()->GetTimeSeconds();
    if (Now < NextPatchGroundSweep) return;
    const int32 Budget = Sub->FoodPatchGroundBudget.Take(GFrameCounter, 12);
    int32 Traces = 0;
    TSet<int32> Changed;
    const FCollisionQueryParams Query(SCENE_QUERY_STAT(EcoFoodPatchGround), false, this);
    // Bound scanning too; confirmed static ground is not traced again until explicitly invalidated.
    for (int32 Inspected = 0; Inspected < 128 && Traces < Budget && NextPatchGround < Cache.Patches.Num(); ++Inspected)
    {
        const int32 Offset = NextPatchGround++;
        auto& Patch = Cache.Patches[Offset];
        if (Patch.bGroundUsable) continue;
        ++Traces;
        CSV_CUSTOM_STAT(EcoGrass, PatchGroundTraces, 1, ECsvCustomStatOp::Accumulate);
        const FVector Hint = PatchLayout.OriginCm + FVector(Patch.RelativePosition);
        FHitResult Hit;
        const bool bUsable = GetWorld()->LineTraceSingleByChannel(Hit, Hint + FVector(0,0,5000),
            Hint - FVector(0,0,20000), GroundTraceChannel, Query) && Hit.ImpactNormal.Z >= FMath::Max(.65f, MinimumGroundNormalZ);
        const FEcoFoodPatchId Id{RegionId, PatchLayout.Epoch, Offset / PatchLayout.PatchCount, Offset % PatchLayout.PatchCount};
        Cache.SetGround(Id, bUsable ? Hit.ImpactPoint : Hint, bUsable ? Hit.ImpactNormal : FVector::ZeroVector, bUsable);
        Changed.Add(Id.Cell);
    }
    for (const int32 Cell : Changed) PublishPatchGroundCell(Cell);
    if (NextPatchGround >= Cache.Patches.Num()) { NextPatchGround = 0; NextPatchGroundSweep = Now + 1; }
}
void AEcoVegetationField::GatherGround()
{
    CSV_SCOPED_TIMING_STAT(EcoGrass, GatherGround);
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
    if (Grid.Vegetation.bEnabled)
    {
        for (TActorIterator<AEcoVegetationHabitat> It(GetWorld()); It; ++It)
        {
            if (It->RegionId != RegionId) continue;
            if (!It->IsValidHabitat())
            { UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoVegetation] Unsupported authoring %s"), *It->GetPathName()); Sub->RejectResourceContract(); return; }
            Inputs.Add(*It);
        }
        Inputs.Sort([](const AEcoVegetationHabitat& A, const AEcoVegetationHabitat& B) { return A.GetPathName() < B.GetPathName(); });
    }
    const int32 CellBudget = PatchLayout.IsValid() ? Sub->FoodPatchGroundBudget.Take(GFrameCounter, 12) : 32;
    for (int32 Budget = 0; Budget < CellBudget && NextGroundCell < Count; ++Budget, ++NextGroundCell)
    {
        if (PatchLayout.IsValid()) CSV_CUSTOM_STAT(EcoGrass, PatchCellGroundTraces, 1, ECsvCustomStatOp::Accumulate);
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
            if (Input->HasWaterSupply() && FMath::IsFinite(Input->WaterSurfaceZ)
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
        if (Grid.Vegetation.bEnabled) Grid.Habitats[K] = H;
        if (H.bGroundUsable) Ground.Add(K, Hit.ImpactPoint);
        else Ground.Remove(K);
    }
    if (NextGroundCell >= Count) NextGroundRefresh = GetWorld()->GetTimeSeconds() + 5;
}
void AEcoVegetationField::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    const double Now = GetWorld()->GetTimeSeconds();
    if (GetNetMode() != NM_DedicatedServer && Now >= NextVisualRefresh)
    {
        NextVisualRefresh = Now + .25;
        RefreshVisuals();
    }
    if (GetNetMode() == NM_Client || !HasAuthority()) return;
    const auto* Mass = GetWorld()->GetSubsystem<UMassEntitySubsystem>();
    if (Mass && Mass->GetEntityManager().IsProcessing()) return;
    auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ctx = Sub && Sub->IsActive() ? Sub->GetContext(ContextIndex) : nullptr;
    if (!Ctx || Ctx->RegionId != RegionId) return;
    if (!Ctx->Sim.Food.HasValidVegetationLayout()) { Sub->RejectResourceContract(); return; }
    if (bEnablePatchLayout && !EnsurePatchLayout()) return;
    GatherGround();
    if (PatchLayout.IsValid()) GatherPatchGround();
    if (!Sub->IsActive()) return;
    if (Now < NextPublish) return;
    NextPublish = Now + 1;
    PublishCells();
}

void AEcoVegetationField::PublishCells()
{
    CSV_SCOPED_TIMING_STAT(EcoGrass, PublishCells);
    const auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const auto* Ctx = Sub->GetContext(ContextIndex);
    const auto& Grid = Ctx->Sim.Food;
    auto& Cells = VisualGrid.Cells;
    bool bRemoved = false;
    for (int32 Index = Cells.Num() - 1; Index >= 0; --Index)
    {
        const int32 Cell = Cells[Index].Cell;
        if (!Ground.Contains(Cell) || Grid.Cap[Cell] <= 0)
        {
            Cells.RemoveAtSwap(Index, 1, EAllowShrinking::No);
            bRemoved = true;
        }
    }
    if (bRemoved) VisualGrid.MarkArrayDirty();

    TArray<int32> Published;
    Published.Init(INDEX_NONE, int32(Grid.Food.size()));
    for (int32 Index = 0; Index < Cells.Num(); ++Index) Published[Cells[Index].Cell] = Index;
    for (int32 K = 0; K < Published.Num(); ++K)
    {
        const FVector* Anchor = Ground.Find(K); if (!Anchor || Grid.Cap[K] <= 0) continue;
        const uint16 Food = FEcoVegetationVisualCell::EncodeAmount(Grid.Food[K]);
        const uint16 Capacity = FEcoVegetationVisualCell::EncodeAmount(Grid.Cap[K]);
        const uint8 Moisture = Grid.Vegetation.bEnabled ? uint8(FMath::RoundToInt(Grid.VegetationCells[K].Moisture * 255)) : 0;
        const uint8 Stress = Grid.Vegetation.bEnabled ? uint8(FMath::RoundToInt(Grid.VegetationCells[K].Stress * 255)) : 0;
        const uint8 Plant = Grid.Vegetation.bEnabled ? uint8(Grid.Habitats[K].Plant) : 0;
        const bool bNew = Published[K] == INDEX_NONE;
        auto& V = bNew ? Cells.AddDefaulted_GetRef() : Cells[Published[K]];
        if (!bNew && V.Food == Food && V.Capacity == Capacity && V.Plant == Plant &&
            V.Moisture == Moisture && V.Stress == Stress && V.Position.Equals(*Anchor, .1)) continue;
        V.Cell = K;
        V.Position = FVector_NetQuantize10(*Anchor);
        V.Food = Food;
        V.Capacity = Capacity;
        V.Moisture = Moisture;
        V.Stress = Stress;
        V.Plant = Plant;
        VisualGrid.MarkItemDirty(V);
    }
    PublishedNativeStep = int64(Ctx->Sim.T);
    MovementMarks.Reset();const double Now=Ctx->Sim.T*EcoRepertoireV3::kStepSeconds;
    for(const auto& T:Ctx->MovementTraces.Events)if(T.Id&&Now>=T.Time&&Now-T.Time<20){
        if(MovementMarks.Num()>=64)break;
        auto& Mark=MovementMarks.AddDefaulted_GetRef();Mark.Position=Ctx->UnitsToCm(T.X,T.Y,T.Z+2);Mark.Age=uint8((Now-T.Time)*255/20);
    }
    if (GetNetMode() != NM_DedicatedServer) OnRep_MovementMarks();
}
void AEcoVegetationField::OnRep_MovementMarks()
{
    Tracks->ClearInstances();
    if(Tracks->GetStaticMesh())for(const auto& Mark:MovementMarks){
        const double Scale=1-Mark.Age/255.;Tracks->AddInstance(FTransform(FRotator::ZeroRotator,Mark.Position,FVector(.25*Scale,.12*Scale,.015)),true);
    }
}

TArray<int64> AEcoVegetationField::GetDueGroundCandidates(double Now, int32 Budget) const
{
    TArray<int64> Due;
    if (!FMath::IsFinite(Now) || Budget <= 0) return Due;
    for (const auto& Entry : RenderedPlants)
    {
        if (Entry.Value.NextGroundCheck <= Now) Due.Add(Entry.Key);
    }
    Due.Sort([this](int64 Left, int64 Right)
    {
        const double LeftTime = RenderedPlants.FindChecked(Left).NextGroundCheck;
        const double RightTime = RenderedPlants.FindChecked(Right).NextGroundCheck;
        return LeftTime == RightTime ? Left < Right : LeftTime < RightTime;
    });
    Due.SetNum(FMath::Min(Due.Num(), Budget), EAllowShrinking::No);
    return Due;
}

void AEcoVegetationField::RefreshVisuals()
{
    CSV_SCOPED_TIMING_STAT(EcoGrass, RefreshVisuals);
    const bool bVisible = CVarShowFoodGrass.GetValueOnGameThread() != 0;
    const auto* GameInstance = GetWorld()->GetGameInstance();
    const auto* Viewer = GameInstance ? GameInstance->GetFirstLocalPlayerController(GetWorld()) : nullptr;
    if (!bVisible || !Viewer || CellWidthCm <= 0)
    {
        if (!RenderedPlants.IsEmpty())
        {
            for (auto* Component : {Plants.Get(), RiparianPlants.Get(), ShrubPlants.Get()}) Component->ClearInstances();
            RenderedPlants.Reset();
        }
        return;
    }

    FVector Eye;
    FRotator ViewRotation;
    Viewer->GetPlayerViewPoint(Eye, ViewRotation);
    RefreshPlants(Eye, GetWorld()->GetTimeSeconds());
}

void AEcoVegetationField::RefreshPlants(const FVector& Eye, double Now)
{
    if ((GetNetMode() == NM_Client && PatchLayoutMode < 0) || (PatchLayoutMode == 1 && !PatchLayout.IsValid()))
    {
        for (auto* Component : {Plants.Get(), RiparianPlants.Get(), ShrubPlants.Get()}) Component->ClearInstances();
        RenderedPlants.Reset(); LocalLayoutSamples.Reset(); return;
    }
    const bool bAuthorityAnchors = PatchLayout.IsValid();
    const int32 MaxCandidates = bAuthorityAnchors ? PatchLayout.PatchCount : FMath::Clamp(CandidatesPerCell, 1, 25);
    const double NearDistance = FMath::Max(1000.f, DetailRadiusCm);
    const double CullDistance = FMath::Max(NearDistance, FMath::Sqrt(GetNetCullDistanceSquared()));
    const uint32 Seed = bAuthorityAnchors ? PatchLayout.RegionSeed() : FCrc::StrCrc32(*RegionId.ToString(), uint32(LayoutSeed));
    if (CachedRegionSeed != Seed || CachedCellWidth != CellWidthCm || CachedPatchCount != MaxCandidates
        || CachedLayoutEpoch != PatchLayout.Epoch)
    {
        LocalLayoutSamples.Reset();
        CachedRegionSeed = Seed; CachedCellWidth = CellWidthCm; CachedPatchCount = MaxCandidates;
        CachedLayoutEpoch = PatchLayout.Epoch;
    }
    TMap<int32, const FEcoFoodPatchGroundCell*> AuthorityGround;
    if (bAuthorityAnchors) for (const auto& Cell : PatchGround.Cells)
        if (Cell.MatchesValidatedLayout(PatchLayout)) AuthorityGround.Add(Cell.Cell, &Cell);
    const int32 TraceBudget = FMath::Clamp(CandidateTracesPerUpdate, 2, 1000);
    // Reserve space for new candidates when existing terrain samples need rechecks.
    int32 RefreshBudget = FMath::Max(1, TraceBudget / 4);
    int32 NewBudget = TraceBudget - RefreshBudget;
    // Earliest deadlines get the bounded refresh budget, including failed streaming samples.
    const TArray<int64> RefreshCandidates = GetDueGroundCandidates(Now, RefreshBudget);
    const FCollisionQueryParams Query(SCENE_QUERY_STAT(EcoGrassCandidate), false, this);
    TSet<int64> Retained;
    const auto ComponentFor = [this](uint8 Plant)
    {
        return Plant == 1 ? RiparianPlants.Get() : Plant == 2 ? ShrubPlants.Get() : Plants.Get();
    };

    for (const auto& Cell : VisualGrid.Cells)
    {
        if (!Cell.HasRenderableFood()) continue;
        const double DistanceSquared = FVector::DistSquared2D(Eye, Cell.Position);
        if (DistanceSquared > FMath::Square(CullDistance)) continue;
        auto* Component = ComponentFor(Cell.Plant);
        if (!Component->GetStaticMesh()) continue;

        const float Remaining = float(Cell.Food) / Cell.Capacity;
        const float Density = FMath::Clamp(Cell.Food / (65535.f * FMath::Max(.01f, FoodAtFullDensity)), 0.f, 1.f);
        const bool bNear = DistanceSquared <= FMath::Square(NearDistance);
        const int32 Count = bNear ? FMath::Max(1, FMath::CeilToInt(MaxCandidates * Density)) : 1;
        const float Detail = bNear ? 1.f : FMath::Sqrt(float(MaxCandidates));
        const FEcoFoodPatchGroundCell* GroundCell = AuthorityGround.FindRef(Cell.Cell);
        if (bAuthorityAnchors && !GroundCell) continue; // wait for complete matching authority cell; no local trace fallback
        auto& Samples = LocalLayoutSamples.FindOrAdd(Cell.Cell);
        if (Samples.Num() != MaxCandidates)
            EcoFoodPatchLayout::GenerateCell(Seed, Cell.Cell, CellWidthCm, MaxCandidates, Samples);
        const FBox Bounds = Component->GetStaticMesh()->GetBoundingBox();
        const FVector MeshSize = Bounds.GetSize();
        for (int32 Candidate = 0; Candidate < Count; ++Candidate)
        {
            const int64 Key = (int64(Cell.Cell) << 32) | uint32(Candidate);
            const auto& Sample = Samples[Candidate];
            const float Yaw = Sample.Yaw;
            const FVector Hint = FVector(Cell.Position) + FVector(Sample.OffsetX, Sample.OffsetY, 0);
            const FVector Local = Hint - GetActorLocation();
            if (Local.X < 0 || Local.Y < 0 || Local.X > GridSizeCm || Local.Y > GridSizeCm) continue;
            auto* Existing = RenderedPlants.Find(Key);
            if (bAuthorityAnchors)
            {
                if (!(GroundCell->ValidMask & (1u << Candidate))) continue;
                auto& Rendered = RenderedPlants.FindOrAdd(Key);
                FVector Relative = GroundCell->RelativePositions[Candidate];
                if (GroundCell->bHeightOnlyFromWire)
                {
                    Relative.X = (Cell.Cell % PatchLayout.GridWidth + .5) * PatchLayout.CellWidthCm + Sample.OffsetX;
                    Relative.Y = (Cell.Cell / PatchLayout.GridWidth + .5) * PatchLayout.CellWidthCm + Sample.OffsetY;
                }
                const FVector Position = PatchLayout.OriginCm + Relative;
                if (!Rendered.GroundPosition.Equals(Position, .01)) Rendered.Food = 0;
                Rendered.Anchor = Cell.Position;
                Rendered.GroundPosition = Position;
                Rendered.bGroundReady = true;
                Rendered.NextGroundCheck = TNumericLimits<double>::Max();
                Existing = &Rendered;
            }
            if (Existing && !Existing->Anchor.Equals(Cell.Position, .1))
            {
                if (Existing->Instance.IsValid())
                {
                    ComponentFor(Existing->Plant)->RemoveInstanceById(Existing->Instance);
                    Existing->Instance = {};
                }
                Existing->bGroundReady = false;
                Existing->NextGroundCheck = 0;
            }
            int32& RemainingTraces = Existing ? RefreshBudget : NewBudget;
            const bool bCanTrace = Existing ? RefreshCandidates.Contains(Key) : NewBudget > 0;
            if (!bAuthorityAnchors && bCanTrace && RemainingTraces > 0)
            {
                --RemainingTraces;
                CSV_CUSTOM_STAT(EcoGrass, CandidateTraces, 1, ECsvCustomStatOp::Accumulate);
                auto& Rendered = RenderedPlants.FindOrAdd(Key);
                FHitResult Hit;
                const double Reach = FMath::Max(100., double(CellWidthCm));
                const bool bGround = GetWorld()->LineTraceSingleByChannel(Hit, Hint + FVector(0, 0, Reach),
                    Hint - FVector(0, 0, Reach), GroundTraceChannel, Query) && Hit.ImpactNormal.Z >= MinimumGroundNormalZ;
                if (!bGround && Rendered.Instance.IsValid())
                {
                    ComponentFor(Rendered.Plant)->RemoveInstanceById(Rendered.Instance);
                    Rendered.Instance = {};
                }
                Rendered.Anchor = Cell.Position;
                Rendered.GroundPosition = bGround ? Hit.ImpactPoint : FVector::ZeroVector;
                Rendered.NextGroundCheck = Now + (bGround ? 5. : 1.);
                Rendered.Food = 0; // refresh transform even if only ground moved
                Rendered.bGroundReady = bGround;
                Existing = &Rendered;
            }
            if (!Existing) continue;
            Retained.Add(Key);
            if (!Existing->bGroundReady || !Existing->Anchor.Equals(Cell.Position, .1)) continue;
            if (Existing->Instance.IsValid() && Existing->Plant != Cell.Plant)
            {
                ComponentFor(Existing->Plant)->RemoveInstanceById(Existing->Instance);
                Existing->Instance = {};
            }
            if (Existing->Instance.IsValid() && Existing->Food == Cell.Food && Existing->Capacity == Cell.Capacity &&
                Existing->Moisture == Cell.Moisture && Existing->Stress == Cell.Stress && Existing->Detail == Detail) continue;

            const double Width = FMath::Min(double(CellWidthCm), PatchWidthCm * Detail * FMath::Sqrt(double(Density))) /
                FMath::Max(1., FMath::Max(MeshSize.X, MeshSize.Y));
            const double Height = PatchHeightCm * (.2 + .8 * Remaining) / FMath::Max(1., MeshSize.Z);
            const FVector Base = Existing->GroundPosition - FVector(0, 0, Bounds.Min.Z * Height);
            const FTransform Transform(FRotator(0, Yaw, 0), Base, FVector(Width, Width, Height));
            if (Existing->Instance.IsValid()) Component->UpdateInstanceTransformById(Existing->Instance, Transform, true);
            else Existing->Instance = Component->AddInstanceById(Transform, true);
            if (!Existing->Instance.IsValid()) continue;
            Component->SetCustomDataValueById(Existing->Instance, 0, Remaining);
            Component->SetCustomDataValueById(Existing->Instance, 1, Cell.Moisture / 255.f);
            Component->SetCustomDataValueById(Existing->Instance, 2, Cell.Stress / 255.f);
            Existing->Food = Cell.Food;
            Existing->Capacity = Cell.Capacity;
            Existing->Moisture = Cell.Moisture;
            Existing->Stress = Cell.Stress;
            Existing->Plant = Cell.Plant;
            Existing->Detail = Detail;
        }
    }
    for (auto It = RenderedPlants.CreateIterator(); It; ++It)
    {
        if (Retained.Contains(It.Key())) continue;
        if (It.Value().Instance.IsValid()) ComponentFor(It.Value().Plant)->RemoveInstanceById(It.Value().Instance);
        It.RemoveCurrent();
    }
    // A camera leaving a region may evict render samples; Native layout/amounts are unaffected.
    TSet<int32> RenderedCells;
    for (const auto& Entry : RenderedPlants) RenderedCells.Add(int32(Entry.Key >> 32));
    for (auto It = LocalLayoutSamples.CreateIterator(); It; ++It)
        if (!RenderedCells.Contains(It.Key())) It.RemoveCurrent();
}

#if !UE_BUILD_SHIPPING
FString AEcoVegetationField::DescribeGrassCell(const FVector& Position) const
{
    const FVector Local = Position - GetActorLocation();
    if (CellWidthCm <= 0 || Local.X < 0 || Local.Y < 0 || Local.X >= GridSizeCm || Local.Y >= GridSizeCm)
        return TEXT("Aim at ground in the selected region");
    const int32 Width = FMath::CeilToInt(double(GridSizeCm) / CellWidthCm);
    const int32 Cell = FMath::FloorToInt(Local.Y / CellWidthCm) * Width + FMath::FloorToInt(Local.X / CellWidthCm);
    if (GetNetMode() != NM_Client)
    {
        const auto* Mass = GetWorld()->GetSubsystem<UMassEntitySubsystem>();
        if (Mass && Mass->GetEntityManager().IsProcessing()) return TEXT("Waiting for completed step");
        const auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
        const auto* Ctx = Sub && Sub->IsActive() ? Sub->GetContext(ContextIndex) : nullptr;
        if (Ctx && Ctx->RegionId == RegionId)
        {
            const auto& Grid = Ctx->Sim.Food;
            const int32 NativeCell = Grid.CellOf(Ctx->CmToUnits(Position));
            if (Grid.Vegetation.bEnabled)
            {
                const auto& Soil = Grid.VegetationCells[NativeCell];
                return FString::Printf(TEXT("Cell %d | Food %.4f / %.4f | Moisture %.2f | Stress %.2f"),
                    NativeCell, Grid.Food[NativeCell], Grid.Cap[NativeCell], Soil.Moisture, Soil.Stress);
            }
            return FString::Printf(TEXT("Cell %d | Food %.4f / %.4f"), NativeCell, Grid.Food[NativeCell], Grid.Cap[NativeCell]);
        }
    }
    const auto* State = VisualGrid.Cells.FindByPredicate([Cell](const auto& Row) { return Row.Cell == Cell; });
    if (!State) return FString::Printf(TEXT("Cell %d | No display sample"), Cell);
    return FString::Printf(TEXT("Cell %d | Received food %.4f / %.4f"), Cell, State->Food / 65535., State->Capacity / 65535.);
}
#endif

FString AEcoVegetationField::CaptureDiagnostics(bool bIncludeLearningCells) const
{
    if(!IsInGameThread())return TEXT("{\"rejected\":\"GameThreadRequired\"}");
    const bool bAuthority = GetNetMode() != NM_Client && HasAuthority();
    auto J = MakeShared<FJsonObject>(); J->SetStringField(TEXT("region"), RegionId.ToString());
    J->SetBoolField(TEXT("authority"), bAuthority); J->SetNumberField(TEXT("visual_cells"), VisualGrid.Cells.Num());
    J->SetNumberField(TEXT("instances"), Plants->GetInstanceCount()+RiparianPlants->GetInstanceCount()+ShrubPlants->GetInstanceCount());
    J->SetNumberField(TEXT("riparian_instances"),RiparianPlants->GetInstanceCount());J->SetNumberField(TEXT("shrub_instances"),ShrubPlants->GetInstanceCount());
    J->SetNumberField(TEXT("movement_marks"),MovementMarks.Num());
    // Container allocations only: excludes shared meshes/materials, ISM render buffers and GPU memory.
    J->SetNumberField(TEXT("visual_grid_allocated_bytes"), double(VisualGrid.Cells.GetAllocatedSize()));
    J->SetNumberField(TEXT("candidate_cache_allocated_bytes"), double(RenderedPlants.GetAllocatedSize()));
    J->SetNumberField(TEXT("ground_cache_allocated_bytes"), double(Ground.GetAllocatedSize()));
    uint64 LayoutBytes = LocalLayoutSamples.GetAllocatedSize();
    for (const auto& Entry : LocalLayoutSamples) LayoutBytes += Entry.Value.GetAllocatedSize();
    uint64 GroundDtoBytes = PatchGround.Cells.GetAllocatedSize();
    for (const auto& Cell : PatchGround.Cells) GroundDtoBytes += Cell.RelativePositions.GetAllocatedSize() + Cell.Normals.GetAllocatedSize();
    J->SetNumberField(TEXT("layout_sample_cache_allocated_bytes"), double(LayoutBytes));
    J->SetNumberField(TEXT("patch_ground_dto_allocated_bytes"), double(GroundDtoBytes));
    J->SetNumberField(TEXT("patch_layout_epoch"), PatchLayout.Epoch);
    J->SetNumberField(TEXT("patch_layout_mode"), PatchLayoutMode);
    J->SetNumberField(TEXT("patch_layout_hash"), PatchLayout.SettingsHash);
    J->SetNumberField(TEXT("patch_layout_count"), PatchLayout.NumPatches());
    J->SetStringField(TEXT("grazing_backend"), TEXT("LegacyCellConsumption_S1AnchorsOnly"));
    int32 PublishedAnchors = 0;
    const bool bValidLayout = PatchLayout.IsValid();
    for (const auto& Cell : PatchGround.Cells) if (bValidLayout && Cell.MatchesValidatedLayout(PatchLayout))
        for (int32 Candidate = 0; Candidate < PatchLayout.PatchCount; ++Candidate)
            PublishedAnchors += (Cell.ValidMask & (1u << Candidate)) ? 1 : 0;
    J->SetNumberField(TEXT("published_patch_anchors"), PublishedAnchors);
    TArray<const FEcoFoodPatchGroundCell*> OrderedGround;
    for (const auto& Cell : PatchGround.Cells) if (bValidLayout && Cell.MatchesValidatedLayout(PatchLayout)) OrderedGround.Add(&Cell);
    OrderedGround.Sort([](const FEcoFoodPatchGroundCell& A, const FEcoFoodPatchGroundCell& B) { return A.Cell < B.Cell; });
    uint32 AnchorChecksum = 0;
    for (const auto* Cell : OrderedGround)
    {
        AnchorChecksum = FCrc::MemCrc32(&Cell->Cell, sizeof(Cell->Cell), AnchorChecksum);
        AnchorChecksum = FCrc::MemCrc32(&Cell->ValidMask, sizeof(Cell->ValidMask), AnchorChecksum);
        TArray<FEcoFoodPatchSample> Samples;
        EcoFoodPatchLayout::GenerateCell(PatchLayout.RegionSeed(), Cell->Cell, PatchLayout.CellWidthCm, PatchLayout.PatchCount, Samples);
        for (int32 I = 0; I < Cell->RelativePositions.Num(); ++I)
        {
            // Compare reconstructed XY and the same 1cm wire height; raw server wrappers retain full precision.
            const int64 Codes[] = {
                FMath::RoundToInt64(((Cell->Cell % PatchLayout.GridWidth + .5) * PatchLayout.CellWidthCm + Samples[I].OffsetX) * 10),
                FMath::RoundToInt64(((Cell->Cell / PatchLayout.GridWidth + .5) * PatchLayout.CellWidthCm + Samples[I].OffsetY) * 10),
                FMath::RoundToInt64(Cell->RelativePositions[I].Z)};
            AnchorChecksum = FCrc::MemCrc32(Codes, sizeof(Codes), AnchorChecksum);
        }
    }
    J->SetNumberField(TEXT("patch_anchor_checksum"), AnchorChecksum);
    double AnchorError = 0;
    TMap<int32, const FEcoFoodPatchGroundCell*> GroundByCell;
    for (const auto* Cell : OrderedGround) GroundByCell.Add(Cell->Cell, Cell);
    for (const auto& Entry : RenderedPlants)
    {
        const auto* Cell = GroundByCell.FindRef(int32(Entry.Key >> 32)); const int32 Candidate = int32(uint32(Entry.Key));
        if (Cell && Cell->RelativePositions.IsValidIndex(Candidate) && Entry.Value.Instance.IsValid())
        {
            const auto& Sample = LocalLayoutSamples.FindChecked(Cell->Cell)[Candidate];
            const FVector Relative((Cell->Cell % PatchLayout.GridWidth + .5) * PatchLayout.CellWidthCm + Sample.OffsetX,
                (Cell->Cell / PatchLayout.GridWidth + .5) * PatchLayout.CellWidthCm + Sample.OffsetY, Cell->RelativePositions[Candidate].Z);
            AnchorError = FMath::Max(AnchorError, FVector::Distance(Entry.Value.GroundPosition, PatchLayout.OriginCm + Relative));
        }
    }
    J->SetNumberField(TEXT("rendered_authority_anchor_error_cm"), AnchorError);
    if (bIncludeLearningCells)
    {
        TArray<TSharedPtr<FJsonValue>> Anchors;
        for (const auto& Entry : RenderedPlants) if (Entry.Value.Instance.IsValid())
        {
            auto Row = MakeShared<FJsonObject>(); const FVector& Position = Entry.Value.GroundPosition;
            Row->SetNumberField(TEXT("cell"), int32(Entry.Key >> 32)); Row->SetNumberField(TEXT("candidate"), uint32(Entry.Key));
            Row->SetArrayField(TEXT("ground_cm"), {MakeShared<FJsonValueNumber>(Position.X),MakeShared<FJsonValueNumber>(Position.Y),MakeShared<FJsonValueNumber>(Position.Z)});
            Anchors.Add(MakeShared<FJsonValueObject>(Row));
        }
        J->SetArrayField(TEXT("rendered_patch_anchors"), Anchors);
    }
    J->SetNumberField(TEXT("movement_marks_allocated_bytes"), double(MovementMarks.GetAllocatedSize()));
    J->SetNumberField(TEXT("cached_candidates"), RenderedPlants.Num());
    int32 NearInstances = 0, CoarseInstances = 0, PendingGround = 0;
    for (const auto& Entry : RenderedPlants)
    {
        if (!Entry.Value.bGroundReady) ++PendingGround;
        if (!Entry.Value.Instance.IsValid()) continue;
        if (Entry.Value.Detail > 1.f) ++CoarseInstances;
        else ++NearInstances;
    }
    J->SetNumberField(TEXT("near_instances"), NearInstances);
    J->SetNumberField(TEXT("coarse_instances"), CoarseInstances);
    J->SetNumberField(TEXT("pending_ground_candidates"), PendingGround);
    J->SetNumberField(TEXT("grid_size_cm"), GridSizeCm);
    J->SetNumberField(TEXT("local_candidate_limit"), double(VisualGrid.Cells.Num()) * FMath::Clamp(CandidatesPerCell, 1, 25));
    J->SetNumberField(TEXT("candidate_trace_limit_per_refresh"), FMath::Clamp(CandidateTracesPerUpdate, 2, 1000));
    J->SetStringField(TEXT("visual_class"), GetClass()->GetPathName());
    J->SetStringField(TEXT("visual_mesh"), PatchMesh.ToSoftObjectPath().ToString());
    J->SetStringField(TEXT("visual_material"), PatchMaterial.ToSoftObjectPath().ToString());
    if (bAuthority)
    {
        const auto* Sub = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
        if (const auto* Ctx = Sub ? Sub->GetContext(ContextIndex) : nullptr)
        {
            J->SetNumberField(TEXT("native_patch_static_allocated_bytes"), double(Ctx->FoodPatchCache.Patches.GetAllocatedSize()));
            J->SetNumberField(TEXT("patch_static_record_bytes"), sizeof(FEcoFoodPatchStatic));
            J->SetNumberField(TEXT("patch_world_ground_traces_this_frame"), Sub->FoodPatchGroundBudget.Used);
            if(bIncludeLearningCells){
                const auto* Mass=GetWorld()->GetSubsystem<UMassEntitySubsystem>();
                if(Mass&&Mass->GetEntityManager().IsProcessing())return TEXT("{\"rejected\":\"MassProcessing\"}");
                const auto& F=Ctx->Sim.Food;
                // Compare current Native source, last published DTO and actual local render cache.
                // Source comparison is synchronous only when native_step == published_native_step.
                J->SetNumberField(TEXT("published_native_step"), double(PublishedNativeStep));
                TMap<int32, int32> Instances, MatchingInstances;
                TMap<int32, const FEcoVegetationVisualCell*> VisualByCell;
                for (const auto& V : VisualGrid.Cells) VisualByCell.Add(V.Cell, &V);
                for (const auto& Entry : RenderedPlants)
                {
                    if (!Entry.Value.Instance.IsValid()) continue;
                    const int32 Cell = int32(Entry.Key >> 32);
                    ++Instances.FindOrAdd(Cell);
                    const auto* const* Found = VisualByCell.Find(Cell);
                    const auto* Visual = Found ? *Found : nullptr;
                    if (Visual && Entry.Value.Food == Visual->Food && Entry.Value.Capacity == Visual->Capacity)
                        ++MatchingInstances.FindOrAdd(Cell);
                }
                TArray<TSharedPtr<FJsonValue>> VisualSamples;
                for (const auto& V : VisualGrid.Cells)
                {
                    if (V.Cell < 0 || size_t(V.Cell) >= F.Food.size()) continue;
                    auto Row = MakeShared<FJsonObject>();
                    Row->SetNumberField(TEXT("cell"), V.Cell);
                    Row->SetNumberField(TEXT("food_code"), V.Food);
                    Row->SetNumberField(TEXT("capacity_code"), V.Capacity);
                    Row->SetNumberField(TEXT("source_food_code"), FEcoVegetationVisualCell::EncodeAmount(F.Food[V.Cell]));
                    Row->SetNumberField(TEXT("source_capacity_code"), FEcoVegetationVisualCell::EncodeAmount(F.Cap[V.Cell]));
                    Row->SetNumberField(TEXT("source_food"), F.Food[V.Cell]);
                    Row->SetNumberField(TEXT("instances"), Instances.FindRef(V.Cell));
                    Row->SetNumberField(TEXT("matching_instances"), MatchingInstances.FindRef(V.Cell));
                    VisualSamples.Add(MakeShared<FJsonValueObject>(Row));
                }
                J->SetArrayField(TEXT("visual_samples"), VisualSamples);
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
            const size_t DoubleCapacity = G.Cap.capacity() + G.Food.capacity() + G.Regen.capacity() + G.Cap0.capacity()
                + G.Blur.capacity() + G.GradX.capacity() + G.GradY.capacity() + G.Sat.capacity()
                + G.Tmp.capacity() + G.Tmp2.capacity() + G.Demand.capacity();
            const size_t GridBytes = DoubleCapacity * sizeof(double) + G.CoverCell.capacity() + G.CoverFoodCell.capacity()
                + G.VegetationCells.capacity() * sizeof(EcoVegetationV3::FCell)
                + G.Habitats.capacity() * sizeof(EcoVegetationV3::FHabitat);
            J->SetNumberField(TEXT("native_food_grid_buffer_bytes"), double(GridBytes));
            J->SetBoolField(TEXT("soil"), G.Vegetation.bEnabled);
            J->SetNumberField(TEXT("temperature"), G.VegetationWeather.Temperature);
#if !UE_BUILD_SHIPPING
            const auto* Regions = GetWorld()->GetSubsystem<UEcologyWorldSubsystem>();
            const auto* Region = Regions ? Regions->GetRegion(RegionId) : nullptr;
            J->SetBoolField(TEXT("manual_climate"), Region && Region->HasGrassTestClimate());
#endif
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
                J->SetNumberField(TEXT("ledger_capacity"), Audit.Capacity);
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
