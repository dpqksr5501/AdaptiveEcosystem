#include "Core/EcoFoodPatchLayout.h"
#include "Misc/Crc.h"

uint32 FEcoFoodPatchLayout::RegionSeed() const
{
    return FCrc::StrCrc32(*RegionId.ToString(), uint32(Seed));
}

uint32 FEcoFoodPatchLayout::CalculateHash() const
{
    uint32 Hash = HashCombineFast(RegionSeed(), uint32(Version));
    Hash = HashCombineFast(Hash, uint32(GridWidth));
    Hash = HashCombineFast(Hash, uint32(PatchCount));
    Hash = HashCombineFast(Hash, GetTypeHash(CellWidthCm));
    // Epoch and origin are checked separately, rather than hashing platform-sized FVector bytes.
    return Hash;
}

bool FEcoFoodPatchLayout::IsValid() const
{
    return !RegionId.IsNone() && Version == 1 && Epoch != 0 && GridWidth >= 1 && GridWidth <= 256
        && PatchCount >= 1 && PatchCount <= 25 && FMath::IsFinite(CellWidthCm) && CellWidthCm > 0
        && CellWidthCm <= 100000 && !OriginCm.ContainsNaN() && SettingsHash == CalculateHash();
}

bool FEcoFoodPatchLayout::Matches(const FEcoFoodPatchLayout& Other) const
{
    return IsValid() && Other.IsValid() && RegionId == Other.RegionId && Seed == Other.Seed
        && Version == Other.Version && Epoch == Other.Epoch && GridWidth == Other.GridWidth
        && PatchCount == Other.PatchCount && CellWidthCm == Other.CellWidthCm
        && OriginCm == Other.OriginCm && SettingsHash == Other.SettingsHash;
}

bool FEcoFoodPatchId::IsValidFor(const FEcoFoodPatchLayout& Layout) const
{
    return Layout.IsValid() && RegionId == Layout.RegionId && Epoch == Layout.Epoch
        && Cell >= 0 && Cell < Layout.GridWidth * Layout.GridWidth && Candidate >= 0 && Candidate < Layout.PatchCount;
}

bool EcoFoodPatchLayout::GenerateCell(uint32 Seed, int32 Cell, float Width, int32 Count, TArray<FEcoFoodPatchSample>& Out)
{
    if (Cell < 0 || !FMath::IsFinite(Width) || Width <= 0 || Width > 100000 || Count < 1 || Count > 25) return false;
    FRandomStream Random(int32(HashCombineFast(Seed, uint32(Cell))));
    Out.SetNumUninitialized(Count);
    for (auto& Sample : Out)
    {
        // Keep float assignment and X, Y, yaw sequence exactly as the old RefreshPlants implementation.
        Sample.OffsetX = Random.FRandRange(-.42f, .42f) * Width;
        Sample.OffsetY = Random.FRandRange(-.42f, .42f) * Width;
        Sample.Yaw = Random.FRandRange(0.f, 360.f);
    }
    return true;
}

bool FEcoFoodPatchCache::Initialize(const FEcoFoodPatchLayout& Descriptor)
{
    if (!Descriptor.IsValid()) return false;
    if (Layout.Matches(Descriptor)) return true; // no regeneration, including valid ground
    // A changed layout must use a new epoch; delayed consumers must never address a replacement by an old ID.
    if (Layout.IsValid() && Descriptor.Epoch <= Layout.Epoch) return false;
    TArray<FEcoFoodPatchStatic> Staged;
    Staged.SetNum(Descriptor.NumPatches());
    TArray<FEcoFoodPatchSample> Samples;
    for (int32 Cell = 0; Cell < Descriptor.GridWidth * Descriptor.GridWidth; ++Cell)
    {
        EcoFoodPatchLayout::GenerateCell(Descriptor.RegionSeed(), Cell, Descriptor.CellWidthCm, Descriptor.PatchCount, Samples);
        for (int32 Candidate = 0; Candidate < Descriptor.PatchCount; ++Candidate)
        {
            auto& Patch = Staged[Cell * Descriptor.PatchCount + Candidate];
            const auto& Sample = Samples[Candidate];
            Patch.RelativePosition = FVector3f((Cell % Descriptor.GridWidth + .5f) * Descriptor.CellWidthCm + Sample.OffsetX,
                (Cell / Descriptor.GridWidth + .5f) * Descriptor.CellWidthCm + Sample.OffsetY, 0);
            Patch.Yaw = Sample.Yaw;
        }
    }
    Layout = Descriptor;
    Patches = MoveTemp(Staged);
    return true;
}

bool FEcoFoodPatchCache::SetGround(const FEcoFoodPatchId& Id, const FVector& Position, const FVector& Normal, bool bUsable)
{
    if (!Id.IsValidFor(Layout) || Patches.Num() != Layout.NumPatches() || Position.ContainsNaN() || Normal.ContainsNaN()) return false;
    auto& Patch = Patches[Id.Cell * Layout.PatchCount + Id.Candidate];
    const FVector Relative = Position - Layout.OriginCm;
    // Projection corrects height only: terrain/streaming cannot silently move a logical patch in XY.
    if (FMath::Abs(Relative.X - Patch.RelativePosition.X) > .1 || FMath::Abs(Relative.Y - Patch.RelativePosition.Y) > .1
        || (bUsable && (!Normal.IsNormalized() || Normal.Z < .65))) return false;
    Patch.RelativePosition.Z = float(Relative.Z);
    Patch.Normal = FVector3f(Normal);
    Patch.bGroundUsable = bUsable;
    ++Patch.GroundRevision;
    return true;
}

void FEcoFoodPatchCache::InvalidateGround()
{
    for (auto& Patch : Patches) { Patch.bGroundUsable = false; ++Patch.GroundRevision; }
}
