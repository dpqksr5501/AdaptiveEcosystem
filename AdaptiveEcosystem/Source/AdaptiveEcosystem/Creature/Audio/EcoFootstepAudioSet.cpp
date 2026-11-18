#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundConcurrency.h"
#include "Core/EcoActivityTypes.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Engine/World.h"
#include "Components/PrimitiveComponent.h"
#include "PhysicsEngine/BodyInstance.h"
#include "Network/EcoGameState.h"
#include "World/EcologyWorldSubsystem.h"

bool FEcoFootstepProfile::IsValid() const
{
    const auto In = [](float V, float Min, float Max) { return FMath::IsFinite(V) && V >= Min && V <= Max; };
    return In(WalkSpeed, 1.f, 3000.f) && In(RunSpeed, WalkSpeed + 1.f, 4000.f)
        && In(WalkSpacing, 1.f, 500.f) && In(RunSpacing, 1.f, 600.f)
        && In(Volume, 0.f, 1.f) && In(PlaybackRange, 50.f, 10000.f) && In(Pitch, .5f, 2.f)
        && In(NoiseRange, 50.f, 10000.f) && In(Threat, 0.f, 1.f) && In(HearingRange, 0.f, 10000.f)
        && In(OccludedHearing, 0.f, 1.f) && In(HearingThreshold, .01f, 1.f);
}

bool EcoFootsteps::IsGroundActivity(uint8 Activity)
{
    const auto Kind = EEcoSpeciesActivity(Activity);
    return Kind != EEcoSpeciesActivity::Fly && Kind != EEcoSpeciesActivity::Takeoff
        && Kind != EEcoSpeciesActivity::Land && Kind != EEcoSpeciesActivity::CorpseSettled
        && Kind != EEcoSpeciesActivity::Swim && Kind != EEcoSpeciesActivity::EnterWater && Kind != EEcoSpeciesActivity::ExitWater;
}

float EcoFootsteps::HearingStrength(const FEcoFootstepProfile& Listener, float Distance, float Range, float Loudness,
    float WeatherMultiplier, bool bOccluded)
{
    const float Reach = FMath::Min(Listener.HearingRange, Range) * FMath::Clamp(WeatherMultiplier, 0.f, 1.5f)
        * (bOccluded ? Listener.OccludedHearing : 1.f);
    const float Signal = Reach > Distance ? Loudness * (1.f - Distance / Reach) : 0.f;
    return Signal >= Listener.HearingThreshold ? Signal : 0.f;
}

FEcoFootstepLevels UEcoFootstepAudioSet::Evaluate(const FEcoFootstepProfile& Profile, EEcoFootstepSurface Surface,
    float Speed, float BodyScale, float GaitGain) const
{
    const float Scale = FMath::Clamp(BodyScale, .25f, 2.f);
    const float Effort = FMath::Clamp((Speed / Scale - Profile.WalkSpeed) / (Profile.RunSpeed - Profile.WalkSpeed), 0.f, 1.f);
    const auto* Ground = Surfaces.Find(Surface);
    const float Impact = FMath::Lerp(.48f, 1.f, Effort) * GaitGain;
    return {
        FMath::Lerp(Profile.WalkSpacing, Profile.RunSpacing, Effort) * Scale,
        FMath::Clamp(Profile.Volume * Impact * FMath::Sqrt(Scale) * (Ground ? Ground->VolumeMultiplier : 1.f), 0.f, 1.f),
        FMath::Clamp(Profile.PlaybackRange * FMath::Lerp(.7f, 1.f, Effort) * FMath::Sqrt(Scale) * FMath::Sqrt(GaitGain), 50.f, 10000.f),
        FMath::Clamp(Profile.Pitch / FMath::Sqrt(Scale), .5f, 2.f),
        FMath::Clamp(Profile.NoiseRange * FMath::Sqrt(Scale) * (Ground ? Ground->NoiseMultiplier : 1.f), 1.f, 10000.f),
        FMath::Clamp(Impact * FMath::Sqrt(Scale * (Ground ? Ground->NoiseMultiplier : 1.f)), .01f, 1.f)
    };
}

bool UEcoFootstepAudioSet::ResolveContact(UWorld& World, const FVector& Source, FName RegionId, const AActor* Ignore,
    FEcoFootstepContact& Out) const
{
    Out = {};
    if (Source.ContainsNaN()) return false;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoFootstepSurface), true, Ignore);
    Params.bReturnPhysicalMaterial = true;
    FHitResult Hit;
    if (!World.LineTraceSingleByObjectType(Hit, Source + FVector(0, 0, 35), Source - FVector(0, 0, 75),
        FCollisionObjectQueryParams(ECC_WorldStatic), Params) || Hit.ImpactNormal.Z < .55f) return false;
    Out.Position = Hit.ImpactPoint;
    Out.Material = Hit.PhysMaterial.Get();
    if (const auto* Component = Hit.GetComponent())
        if (const auto* Body = Component->GetBodyInstance())
            if (auto* Override = Body->GetPhysMaterialOverride()) Out.Material = Override;
    Out.Surface = GetSurface(Out.Material, RegionId);
    if (!EcoCreatureMovement::IsWadeableGround(World, Out.Position, 1.f)) Out.Surface = EEcoFootstepSurface::Water;
    else if (Out.Surface == EEcoFootstepSurface::Dry || Out.Surface == EEcoFootstepSurface::Grass)
    {
        float Rainfall = 0.f;
        if (World.GetNetMode() == NM_Client)
        {
            const auto* State = World.GetGameState<AEcoGameState>();
            if (const auto* Row = State ? State->FindCompletedRegion(RegionId) : nullptr) Rainfall = Row->Environment.Rainfall;
        }
        else
        {
            FRegionEnvironmentState Environment;
            const auto* Regions = World.GetSubsystem<UEcologyWorldSubsystem>();
            if (Regions && Regions->GetEnvironmentState(RegionId, Environment)) Rainfall = Environment.Rainfall;
        }
        if (Rainfall >= RainWetThreshold) Out.Surface = EEcoFootstepSurface::Wet;
    }
    return true;
}

const TArray<TObjectPtr<USoundBase>>& UEcoFootstepAudioSet::SelectSounds(EEcoFootstepSurface S, bool bPlayer, bool bRun, bool bHoof) const
{
    if (const auto* Ground = Surfaces.Find(S))
    {
        if (bPlayer && bRun && !Ground->PlayerRun.IsEmpty()) return Ground->PlayerRun;
        if (bPlayer && !Ground->PlayerWalk.IsEmpty()) return Ground->PlayerWalk;
        if (bHoof && !Ground->Hoof.IsEmpty()) return Ground->Hoof;
        if (!Ground->Animal.IsEmpty()) return Ground->Animal;
    }
    return GetSounds(S);
}

bool UEcoFootstepAudioSet::IsValidConfiguration() const
{
    for (const auto& Pair : Profiles) if (Pair.Key.IsNone() || !Pair.Value.IsValid()) return false;
    for (const auto& Pair : Surfaces)
        if (!FMath::IsFinite(Pair.Value.NoiseMultiplier) || Pair.Value.NoiseMultiplier <= 0.f || Pair.Value.NoiseMultiplier > 2.f
            || !FMath::IsFinite(Pair.Value.VolumeMultiplier) || Pair.Value.VolumeMultiplier <= 0.f || Pair.Value.VolumeMultiplier > 2.f) return false;
    return FMath::IsFinite(Volume) && Volume >= 0 && Volume <= 1 && FMath::IsFinite(WalkStride) && WalkStride > 0
        && FMath::IsFinite(RunStride) && RunStride > 0 && FMath::IsFinite(MinimumSpeed) && MinimumSpeed >= 0
        && FMath::IsFinite(NoiseRange) && NoiseRange > 0 && NoiseRange <= 10000
        && FMath::IsFinite(PredatorThreat) && PredatorThreat >= 0 && PredatorThreat <= 1
        && FMath::IsFinite(RainWetThreshold) && RainWetThreshold >= 0.f && RainWetThreshold <= 1.f;
}

bool UEcoFootstepAudioSet::ConfigurePlayback(USoundAttenuation* SA, USoundConcurrency* SC)
{
#if WITH_EDITOR
    if (!SA || !SC) return false;
    Modify(); SA->Modify(); SC->Modify();
    auto& Settings = SA->Attenuation;
    Settings.bAttenuate = true;
    Settings.bSpatialize = true;
    Settings.AttenuationShape = EAttenuationShape::Sphere;
    Settings.DistanceAlgorithm = EAttenuationDistanceModel::Linear;
    Settings.AttenuationShapeExtents = FVector(300, 0, 0);
    Settings.FalloffDistance = 3700; // 3m full volume; linear fade to silence at 40m.
    Settings.bEnableOcclusion = true;
    Settings.OcclusionTraceChannel = ECC_Visibility;
    Settings.OcclusionVolumeAttenuation = 0.35f;
    Settings.OcclusionLowPassFilterFrequency = 2500;
    Settings.OcclusionInterpolationTime = 0.15f;
    SC->Concurrency.SetEnableMaxCountPlatformScaling(false);
    SC->Concurrency.MaxCount = Profiles.IsEmpty() ? 8 : 16;
    SC->Concurrency.bLimitToOwner = false;
    SC->Concurrency.ResolutionRule = EMaxConcurrentResolutionRule::StopQuietest;
    Attenuation = SA; Concurrency = SC;
    SA->PostEditChange(); SC->PostEditChange();
    SA->MarkPackageDirty(); SC->MarkPackageDirty(); MarkPackageDirty();
    return true;
#else
    return false;
#endif
}
