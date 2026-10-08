#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundConcurrency.h"

bool UEcoFootstepAudioSet::IsValidConfiguration() const
{
    return FMath::IsFinite(Volume) && Volume >= 0 && Volume <= 1 && FMath::IsFinite(WalkStride) && WalkStride > 0
        && FMath::IsFinite(RunStride) && RunStride > 0 && FMath::IsFinite(MinimumSpeed) && MinimumSpeed >= 0
        && FMath::IsFinite(NoiseRange) && NoiseRange > 0 && NoiseRange <= 10000
        && FMath::IsFinite(PredatorThreat) && PredatorThreat >= 0 && PredatorThreat <= 1;
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
    SC->Concurrency.MaxCount = 8;
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
