#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Creature/Audio/EcoFootstepCadence.h"
#include "Creature/Audio/EcoFootstepNotifyGate.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Core/EcoActivityTypes.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundConcurrency.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFootstepCadenceTest, "AdaptiveEcosystem.Creature.Audio.ActualDistanceAndDiscontinuities",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFootstepCadenceTest::RunTest(const FString& Parameters)
{
    FEcoFootstepCadence C;
    auto Step = [&](double X, bool bAlive = true, bool bSnap = false, float Delta = 0.1f, float Speed = 500.f)
        { return C.Advance(FVector(X, 0, 0), Speed, bAlive, Delta, 140.f, 40.f, bSnap); };
    TestFalse(TEXT("Binding does not emit"), Step(0));
    for (int32 I = 0; I < 10; ++I) TestFalse(TEXT("Blocked agents do not emit even with nonzero requested velocity"), Step(0));
    TestFalse(TEXT("Sub-stride travel accumulates"), Step(100));
    TestTrue(TEXT("Actual travel crosses stride"), Step(150));
    TestFalse(TEXT("Teleport emits no burst"), Step(5000));
    TestFalse(TEXT("Death resets accumulation"), Step(5100, false));
    TestFalse(TEXT("Stopped movement resets accumulation"), Step(5100, true, false, 0.1f, 0));
    TestFalse(TEXT("First short resumed step has no stale accumulation"), Step(5200));
    TestTrue(TEXT("Resumed real stride emits"), Step(5250));
    TestFalse(TEXT("A hitch resets rather than catching up"), Step(5600, true, false, 1.f));
    TestFalse(TEXT("Network snap resets cadence"), Step(6000, true, true));
    TestFalse(TEXT("No partial stride survives a snap"), Step(6100));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFootstepSettingsTest, "AdaptiveEcosystem.Creature.Audio.SurfaceAndPlaybackSettings",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFootstepSettingsTest::RunTest(const FString& Parameters)
{
    auto* Set = NewObject<UEcoFootstepAudioSet>();
    TestTrue(TEXT("Grass surface includes production Forest"), Set->IsGrass(TEXT("Forest")));
    TestFalse(TEXT("Barren and Highland select Dry"), Set->IsGrass(TEXT("Barren")) || Set->IsGrass(TEXT("Highland")));
    TestTrue(TEXT("Gameplay settings valid without any audio file"), Set->IsValidConfiguration());
#if WITH_EDITOR
    auto* SA = NewObject<USoundAttenuation>(); auto* SC = NewObject<USoundConcurrency>();
    TestTrue(TEXT("Configure shared playback"), Set->ConfigurePlayback(SA, SC));
    TestTrue(TEXT("Spatial audio fades between 3 and 40m with occlusion"), SA->Attenuation.bSpatialize
        && SA->Attenuation.bEnableOcclusion && SA->Attenuation.AttenuationShapeExtents.X == 300
        && SA->Attenuation.FalloffDistance == 3700);
    TestTrue(TEXT("Global concurrency bounded rather than eight voices per animal"), SC->Concurrency.MaxCount == 8
        && !SC->Concurrency.bLimitToOwner && SC->Concurrency.ResolutionRule == EMaxConcurrentResolutionRule::StopQuietest);
#endif
    Set->NoiseRange = -1;
    TestFalse(TEXT("Malformed gameplay settings cannot emit"), Set->IsValidConfiguration());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoNotifyContactGateTest, "AdaptiveEcosystem.Creature.Audio.NotifyTravelGate",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoNotifyContactGateTest::RunTest(const FString&)
{
    FEcoFootstepNotifyGate Gate;
    auto Move = [&](float X, double Now, bool Alive=true, bool Snap=false)
        { Gate.Observe(FVector(X,0,0), 500, Alive, .1f, Now, 40, Snap); };
    Move(0,1); TestFalse(TEXT("Spawn contact suppressed"), Gate.Contact(1));
    Move(100,1.1); TestTrue(TEXT("Moving foot contact accepted"), Gate.Contact(1.1));
    TestFalse(TEXT("Simultaneous blended notify cannot duplicate"), Gate.Contact(1.1));
    Move(120,1.12); TestFalse(TEXT("Adjacent sample transition bounded"), Gate.Contact(1.12));
    Move(120,1.2); TestFalse(TEXT("Blocked running animation stays silent"), Gate.Contact(1.2));
    Move(150,1.3); TestTrue(TEXT("Next real contact accepted"), Gate.Contact(1.3));
    Move(200,1.4,false); TestFalse(TEXT("Dead animal cannot notify"), Gate.Contact(1.4));
    Move(5000,1.5,true,true); TestFalse(TEXT("Replication snap cannot burst"), Gate.Contact(1.5));
    Move(5050,1.6); TestFalse(TEXT("Stale representation cannot play while stream is absent"), Gate.Contact(2));
    Gate.Reset(); TestFalse(TEXT("Pool/relevance reset clears pending contact"), Gate.Contact(2));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoPhysicalFootstepTest, "AdaptiveEcosystem.Creature.Audio.PhysicalSurfaceOverridesRegion",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoPhysicalFootstepTest::RunTest(const FString&)
{
    auto* Set = NewObject<UEcoFootstepAudioSet>();
    auto* Grass = NewObject<UPhysicalMaterial>(); auto* Dry = NewObject<UPhysicalMaterial>(); auto* Unknown = NewObject<UPhysicalMaterial>();
    Set->GrassMaterials.Add(Grass); Set->DryMaterials.Add(Dry);
    TestTrue(TEXT("Grass contact can override Barren region"), Set->IsGrassSurface(Grass, TEXT("Barren")));
    TestFalse(TEXT("Dry contact can override Forest region"), Set->IsGrassSurface(Dry, TEXT("Forest")));
    TestTrue(TEXT("Unknown/no streamed material falls back predictably"), Set->IsGrassSurface(Unknown, TEXT("Forest")));
    TestFalse(TEXT("Missing material retains Dry highland fallback"), Set->IsGrassSurface(nullptr, TEXT("Highland")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoProfiledFootstepsTest, "AdaptiveEcosystem.Creature.Audio.ProfiledFootstepAndHearing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoProfiledFootstepsTest::RunTest(const FString&)
{
    auto* Set = NewObject<UEcoFootstepAudioSet>();
    auto& Stone = Set->Surfaces.Add(EEcoFootstepSurface::Stone);
    auto* StoneMaterial = NewObject<UPhysicalMaterial>();
    Stone.Materials.Add(StoneMaterial);
    Stone.NoiseMultiplier = 1.3f;
    FEcoFootstepProfile Rat, Buffalo;
    Rat.Volume = .16f; Rat.PlaybackRange = 450.f; Rat.WalkSpacing = 7.f; Rat.NoiseRange = 320.f;
    Buffalo.Volume = .85f; Buffalo.PlaybackRange = 2500.f; Buffalo.NoiseRange = 2200.f;
    TestTrue(TEXT("Explicit stone overrides region fallback"), Set->GetSurface(StoneMaterial, TEXT("Forest")) == EEcoFootstepSurface::Stone);
    const auto Small = Set->Evaluate(Rat, EEcoFootstepSurface::Dry, 150.f, .75f);
    const auto Large = Set->Evaluate(Buffalo, EEcoFootstepSurface::Stone, 400.f, 1.f);
    TestTrue(TEXT("Large hooves carry further than a small paw"), Large.PlaybackRange > Small.PlaybackRange && Large.NoiseRange > Small.NoiseRange);
    TestTrue(TEXT("Small paws have shorter stride and quieter local mix"), Small.Spacing < Large.Spacing && Small.Volume < Large.Volume);
    const auto Dry = Set->Evaluate(Buffalo, EEcoFootstepSurface::Dry, 400.f, 1.f);
    TestTrue(TEXT("Hard ground changes source range"), Large.NoiseRange > Dry.NoiseRange);
    const auto Sneak = Set->Evaluate(Buffalo, EEcoFootstepSurface::Stone, 150.f, 1.f, .26f);
    TestTrue(TEXT("Sneak is quieter than running"), Sneak.Loudness < Large.Loudness && Sneak.PlaybackRange < Large.PlaybackRange);
    Rat.HearingRange = 2200.f;
    Buffalo.HearingRange = 900.f;
    TestTrue(TEXT("Only the sensitive listener hears a distant run"),
        EcoFootsteps::HearingStrength(Rat, 1000.f, Large.NoiseRange, Large.Loudness, 1.f, false) > 0.f
        && EcoFootsteps::HearingStrength(Buffalo, 1000.f, Large.NoiseRange, Large.Loudness, 1.f, false) == 0.f);
    TestTrue(TEXT("Near occluded run is still audible"), EcoFootsteps::HearingStrength(Rat, 150.f, Large.NoiseRange, Large.Loudness, 1.f, true) > 0.f);
    TestTrue(TEXT("Rain and cover can suppress a farther sound"),
        EcoFootsteps::HearingStrength(Rat, 400.f, Large.NoiseRange, Large.Loudness, .5f, true) == 0.f);
    TestFalse(TEXT("Airborne activity cannot emit a ground step"), EcoFootsteps::IsGroundActivity(uint8(EEcoSpeciesActivity::Fly)));
    return true;
}
#endif
