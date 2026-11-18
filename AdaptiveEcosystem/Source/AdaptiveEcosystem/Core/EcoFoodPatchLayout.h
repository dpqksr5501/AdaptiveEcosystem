#pragma once

#include "CoreMinimal.h"
#include "EcoFoodPatchLayout.generated.h"

/** V1 freezes the previous Field CRC/hash/FRandomStream draw order. All lengths are cm. */
USTRUCT()
struct ADAPTIVEECOSYSTEM_API FEcoFoodPatchLayout
{
    GENERATED_BODY()
    UPROPERTY() FName RegionId;
    UPROPERTY() int32 Seed = 0;
    UPROPERTY() int32 Version = 1;
    UPROPERTY() uint32 Epoch = 0; // zero means disabled/uninitialized
    UPROPERTY() int32 GridWidth = 0;
    UPROPERTY() int32 PatchCount = 9; // gameplay count, independent of render LOD
    UPROPERTY() float CellWidthCm = 0;
    UPROPERTY() FVector OriginCm = FVector::ZeroVector;
    UPROPERTY() uint32 SettingsHash = 0;

    uint32 CalculateHash() const;
    bool IsValid() const;
    bool Matches(const FEcoFoodPatchLayout& Other) const;
    uint32 RegionSeed() const;
    int32 NumPatches() const { return IsValid() ? GridWidth * GridWidth * PatchCount : 0; }
};

/** External identity. Array offsets and ISM indices are deliberately absent. */
struct FEcoFoodPatchId
{
    FName RegionId;
    uint32 Epoch = 0;
    int32 Cell = INDEX_NONE;
    int32 Candidate = INDEX_NONE;
    bool IsValidFor(const FEcoFoodPatchLayout& Layout) const;
};

struct FEcoFoodPatchSample
{
    float OffsetX = 0, OffsetY = 0, Yaw = 0;
};

/** Relative coordinates avoid per-patch UObject/FTransform ownership. Food is added in S2. */
struct FEcoFoodPatchStatic
{
    FVector3f RelativePosition = FVector3f::ZeroVector;
    FVector3f Normal = FVector3f::ZeroVector;
    float Yaw = 0;
    uint32 GroundRevision = 0;
    bool bGroundUsable = false;
};

struct ADAPTIVEECOSYSTEM_API FEcoFoodPatchCache
{
    FEcoFoodPatchLayout Layout;
    TArray<FEcoFoodPatchStatic> Patches;
    bool Initialize(const FEcoFoodPatchLayout& Descriptor);
    bool SetGround(const FEcoFoodPatchId& Id, const FVector& WorldPosition, const FVector& Normal, bool bUsable);
    void InvalidateGround();
};

/** Owned by the existing world subsystem; all Fields spend the same GT frame allowance. */
struct FEcoFoodPatchTraceBudget
{
    uint64 Frame = MAX_uint64;
    int32 Used = 0;
    int32 Take(uint64 CurrentFrame, int32 Requested)
    {
        if (Frame != CurrentFrame) { Frame = CurrentFrame; Used = 0; }
        const int32 Granted = FMath::Clamp(Requested, 0, 96 - Used);
        Used += Granted;
        return Granted;
    }
};

namespace EcoFoodPatchLayout
{
    /** Pure; no World, clock, camera, or global RNG. Does not modify Out on invalid inputs. */
    ADAPTIVEECOSYSTEM_API bool GenerateCell(uint32 RegionSeed, int32 Cell, float CellWidthCm,
        int32 Count, TArray<FEcoFoodPatchSample>& Out);
}
