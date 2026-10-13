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

void UEcoFootstepAudioComponent::Consume(const FEcoCreatureVisualState& State, float Delta, bool bSnap)
{
    UWorld* World = GetWorld();
    if (!World || World->GetNetMode() == NM_DedicatedServer || !AudioSet || !AudioSet->IsValidConfiguration()) { ResetCadence(); return; }
    const FVector Source = State.Position + FVector(0,0,20);
    if (CVarFootstepDebug.GetValueOnGameThread() && AudioSet->Attenuation && State.bAlive)
    {
        const auto& SA = AudioSet->Attenuation->Attenuation;
        if (SA.AttenuationShape == EAttenuationShape::Sphere && SA.bAttenuate)
        {
            DrawDebugSphere(World, Source, SA.AttenuationShapeExtents.X, 16, FColor::Blue, false, 0, 0, 1);
            DrawDebugSphere(World, Source, SA.AttenuationShapeExtents.X + SA.FalloffDistance, 24, FColor::Purple, false, 0, 0, 1);
        }
    }
    const float Speed = State.Velocity.Size2D();
    CachedState = State;
    if (bUseAnimationNotifies)
    {
        Cadence.Reset();
        NotifyGate.Observe(State.Position, Speed, State.bAlive, Delta, World->GetTimeSeconds(), AudioSet->MinimumSpeed, bSnap);
        return;
    }
    NotifyGate.Reset();
    if (!Cadence.Advance(State.Position, Speed, State.bAlive, Delta, AudioSet->GetStride(Speed), AudioSet->MinimumSpeed, bSnap)) return;
    PlayContact(Source, TEXT("Distance"));
}

void UEcoFootstepAudioComponent::NotifyContact(USkeletalMeshComponent* Mesh, FName FootBone)
{
    UWorld* World = GetWorld();
    if (!bUseAnimationNotifies || !Mesh || Mesh->GetOwner() != GetOwner() || !World || !World->IsGameWorld()
        || World->GetNetMode() == NM_DedicatedServer || !AudioSet || !AudioSet->IsValidConfiguration()
        || !CachedState.bAlive || CachedState.StableAgentId <= 0 || !Mesh->DoesSocketExist(FootBone)
        || !NotifyGate.Contact(World->GetTimeSeconds())) return;
    PlayContact(Mesh->GetSocketLocation(FootBone), TEXT("Notify"));
}

void UEcoFootstepAudioComponent::PlayContact(const FVector& Source, const TCHAR* Trigger)
{
    if (Source.ContainsNaN() || !GetWorld() || !AudioSet) return;
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoFootstepSurface), true, GetOwner());
    Params.bReturnPhysicalMaterial = true;
    LastMaterial = nullptr;
    if (GetWorld()->LineTraceSingleByChannel(Hit, Source + FVector(0,0,100), Source - FVector(0,0,300), ECC_Visibility, Params))
        LastMaterial = Hit.PhysMaterial.Get();
    const bool bGrass = AudioSet->IsGrassSurface(LastMaterial, CachedState.RegionId);
    const auto& Sounds = bGrass ? AudioSet->Grass : AudioSet->Dry;
    LastSurface = bGrass ? TEXT("Grass") : TEXT("Dry");
    if (Sounds.IsEmpty()) return; // Missing surface stays silent; never plays an unrelated fallback.
    int32 Pick = Random.RandRange(0, Sounds.Num()-1);
    if (Sounds.Num() > 1 && Pick == LastIndex) Pick = (Pick + 1) % Sounds.Num();
    LastIndex = Pick;
    USoundBase* Sound = Sounds[Pick];
    if (!Sound || !AudioSet->Attenuation || !AudioSet->Concurrency) return;
    LastSound = Sound;
    LastPlayback = UGameplayStatics::SpawnSoundAtLocation(this, Sound, Source, FRotator::ZeroRotator,
        AudioSet->Volume, Random.FRandRange(0.97f, 1.03f), 0, AudioSet->Attenuation, AudioSet->Concurrency, true);
    if (LastPlayback)
    {
        ++PlayedCount;
        if (bUseAnimationNotifies) ++NotifyPlayedCount; else ++DistancePlayedCount;
        if (CVarFootstepLog.GetValueOnGameThread()) UE_LOG(LogTemp, Log,
            TEXT("[Eco Footstep Audio] NetMode=%d Id=%lld Region=%s Surface=%s Material=%s Trigger=%s Sound=%s Count=%d Position=%s"),
            int32(GetWorld()->GetNetMode()), CachedState.StableAgentId, *CachedState.RegionId.ToString(), *LastSurface.ToString(),
            *GetNameSafe(LastMaterial), Trigger, *GetNameSafe(Sound), PlayedCount, *Source.ToCompactString());
    }
}
