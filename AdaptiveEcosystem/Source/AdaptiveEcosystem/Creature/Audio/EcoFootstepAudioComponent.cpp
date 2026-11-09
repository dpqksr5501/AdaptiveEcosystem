#include "Creature/Audio/EcoFootstepAudioComponent.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundAttenuation.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "DrawDebugHelpers.h"
#include "HAL/IConsoleManager.h"
#include "Engine/World.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicalMaterials/PhysicalMaterial.h"

static TAutoConsoleVariable<int32> CVarFootstepDebug(TEXT("eco.Footsteps.Debug"), 0, TEXT("Local audio SA spheres: blue inner, violet outer. No AI range inference."));
static TAutoConsoleVariable<int32> CVarFootstepLog(TEXT("eco.Footsteps.Log"), 0, TEXT("Log successfully started local footsteps; does not claim listener audibility."));

UEcoFootstepAudioComponent::UEcoFootstepAudioComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
    Random.Initialize(int32(FPlatformTime::Cycles()));
}

void UEcoFootstepAudioComponent::Consume(const FEcoCreatureVisualState& State, float Delta, bool bSnap, float GaitGain, bool bRun)
{
    UWorld* World = GetWorld();
    if (!World || World->GetNetMode() == NM_DedicatedServer || !AudioSet || !AudioSet->IsValidConfiguration()) { ResetCadence(); return; }
    const FVector Source = State.Position + FVector(0,0,20);
    const auto* Profile = AudioSet->FindProfile(State.SpeciesId);
    const float Speed = State.Velocity.Size2D();
    const auto Levels = Profile ? AudioSet->Evaluate(*Profile, EEcoFootstepSurface::Dry, Speed, State.BodyScale, GaitGain) : FEcoFootstepLevels{};
    const bool bGrounded = State.bAlive && EcoFootsteps::IsGroundActivity(uint8(State.Activity));
    const bool bTouchdown = Profile && !bSnap && bGrounded && CachedState.bAlive
        && CachedState.Activity == EEcoSpeciesActivity::Land;
    const float MinimumSpeed = Profile ? FMath::Min(AudioSet->MinimumSpeed, Profile->WalkSpeed * .35f) : AudioSet->MinimumSpeed;
    if (CVarFootstepDebug.GetValueOnGameThread() && AudioSet->Attenuation && State.bAlive)
    {
        const auto& SA = AudioSet->Attenuation->Attenuation;
        if (SA.AttenuationShape == EAttenuationShape::Sphere && SA.bAttenuate)
        {
            const float Inner = Profile ? Levels.PlaybackRange * .1f : SA.AttenuationShapeExtents.X;
            DrawDebugSphere(World, Source, Inner, 16, FColor::Blue, false, 0, 0, 1);
            DrawDebugSphere(World, Source, Profile ? Levels.PlaybackRange : Inner + SA.FalloffDistance, 24, FColor::Purple, false, 0, 0, 1);
        }
    }
    CachedState = State;
    CachedGaitGain = GaitGain;
    bCachedRun = bRun;
    if (bTouchdown) PlayContact(Source, TEXT("Touchdown"));
    if (bUseAnimationNotifies)
    {
        Cadence.Reset();
        NotifyGate.Observe(State.Position, Speed, bGrounded, Delta, World->GetTimeSeconds(), MinimumSpeed, bSnap);
        return;
    }
    NotifyGate.Reset();
    const float Spacing = Profile ? Levels.Spacing : AudioSet->GetStride(Speed)*State.BodyScale;
    if (!Cadence.Advance(State.Position, Speed, bGrounded, Delta, Spacing, MinimumSpeed, bSnap)) return;
    PlayContact(Source, TEXT("Distance"));
}

void UEcoFootstepAudioComponent::NotifyContact(USkeletalMeshComponent* Mesh, FName FootBone)
{
    UWorld* World = GetWorld();
    if (!bUseAnimationNotifies || !Mesh || Mesh->GetOwner() != GetOwner() || !World || !World->IsGameWorld()
        || World->GetNetMode() == NM_DedicatedServer || !AudioSet || !AudioSet->IsValidConfiguration()
        || !CachedState.bAlive || CachedState.StableAgentId <= 0 || !Mesh->DoesSocketExist(FootBone)) return;
    const auto* Profile = AudioSet->FindProfile(CachedState.SpeciesId);
    if (!NotifyGate.Contact(World->GetTimeSeconds(), Profile ? FMath::Clamp(Profile->WalkSpacing * .18f, 1.f, 10.f) : 10.f)) return;
    PlayContact(Mesh->GetSocketLocation(FootBone), TEXT("Notify"), FootBone);
}

void UEcoFootstepAudioComponent::PlayContact(const FVector& Source, const TCHAR* Trigger, FName FootBone)
{
    if (Source.ContainsNaN() || !GetWorld() || !AudioSet) return;
    const auto* Profile = AudioSet->FindProfile(CachedState.SpeciesId);
    LastMaterial = nullptr;
    FEcoFootstepContact Contact;
    if (Profile)
    {
        if (!AudioSet->ResolveContact(*GetWorld(), Source, CachedState.RegionId, GetOwner(), Contact)) return;
        LastMaterial = Contact.Material;
    }
    else
    {
        FHitResult Hit;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoFootstepSurface), true, GetOwner());
        Params.bReturnPhysicalMaterial = true;
        if (GetWorld()->LineTraceSingleByChannel(Hit, Source + FVector(0,0,100), Source - FVector(0,0,300), ECC_Visibility, Params))
            LastMaterial = Hit.PhysMaterial.Get();
        Contact.Surface = AudioSet->GetSurface(LastMaterial, CachedState.RegionId);
        Contact.Position = Source;
    }
    const EEcoFootstepSurface Surface = Contact.Surface;
    const auto& Sounds = Profile ? AudioSet->SelectSounds(Surface, CachedState.SpeciesId == EcoFootsteps::Player, bCachedRun, Profile->bHoof) : AudioSet->GetSounds(Surface);
    const FName Names[] = {TEXT("Grass"),TEXT("Dry"),TEXT("Snow"),TEXT("Water"),TEXT("Wet"),TEXT("Stone"),TEXT("Wood")};
    LastSurface = Names[uint8(Surface)];
    if (Sounds.IsEmpty()) return; // Missing surface stays silent; never plays an unrelated fallback.
    int32 Pick = Random.RandRange(0, Sounds.Num()-1);
    if (Sounds.Num() > 1 && Pick == LastIndex) Pick = (Pick + 1) % Sounds.Num();
    LastIndex = Pick;
    USoundBase* Sound = Sounds[Pick];
    if (!Sound || !AudioSet->Attenuation || !AudioSet->Concurrency) return;
    LastSound = Sound;
    const float Variation = Random.FRandRange(.96f, 1.04f);
    LastVolume = AudioSet->Volume;
    LastPlaybackRange = AudioSet->Attenuation->Attenuation.AttenuationShapeExtents.X + AudioSet->Attenuation->Attenuation.FalloffDistance;
    if (Profile)
    {
        const auto Levels = AudioSet->Evaluate(*Profile, Surface, CachedState.Velocity.Size2D(), CachedState.BodyScale, CachedGaitGain);
        auto Settings = AudioSet->Attenuation->Attenuation;
        Settings.AttenuationShapeExtents.X = Levels.PlaybackRange * .1f;
        Settings.FalloffDistance = Levels.PlaybackRange * .9f;
        LastVolume = Levels.Volume;
        LastPlaybackRange = Levels.PlaybackRange;
        if (LastVolume <= 0.f || !UGameplayStatics::AreAnyListenersWithinRange(this, Contact.Position, LastPlaybackRange)) return;
        auto* Playback = NewObject<UAudioComponent>(GetWorld());
        Playback->bAutoDestroy = true;
        Playback->bAutoActivate = false;
        Playback->ConcurrencySet.Add(AudioSet->Concurrency);
        Playback->SetSound(Sound);
        Playback->SetVolumeMultiplier(LastVolume);
        Playback->SetPitchMultiplier(Levels.Pitch * Variation);
        Playback->SetAttenuationOverrides(Settings);
        Playback->SetWorldLocation(Contact.Position + FVector(0, 0, 4));
        Playback->RegisterComponentWithWorld(GetWorld());
        Playback->Play();
        LastPlayback = Playback->IsPlaying() ? Playback : nullptr;
        if (!LastPlayback) Playback->DestroyComponent();
    }
    else LastPlayback = UGameplayStatics::SpawnSoundAtLocation(this, Sound, Contact.Position, FRotator::ZeroRotator,
        LastVolume, Variation, 0, AudioSet->Attenuation, AudioSet->Concurrency, true);
    if (LastPlayback)
    {
        ++PlayedCount;
        if (bUseAnimationNotifies) ++NotifyPlayedCount; else ++DistancePlayedCount;
        if (CVarFootstepLog.GetValueOnGameThread()) UE_LOG(LogTemp, Log,
            TEXT("[Eco Footstep Audio] NetMode=%d Id=%lld Region=%s Surface=%s Material=%s Trigger=%s Sound=%s Count=%d Position=%s Species=%s Volume=%.3f Range=%.0f Foot=%s"),
            int32(GetWorld()->GetNetMode()), CachedState.StableAgentId, *CachedState.RegionId.ToString(), *LastSurface.ToString(),
            *GetNameSafe(LastMaterial), Trigger, *GetNameSafe(Sound), PlayedCount, *Contact.Position.ToCompactString(),
            *CachedState.SpeciesId.ToString(), LastVolume, LastPlaybackRange, *FootBone.ToString());
    }
}
