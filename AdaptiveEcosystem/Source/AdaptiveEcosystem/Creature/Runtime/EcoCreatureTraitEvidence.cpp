#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"

#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "MassEntityManager.h"
#include "MassMovementFragments.h"
#include "MassSpawnerSubsystem.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"

namespace
{
    TSharedPtr<FJsonObject> BuildTraitRow(
        const FMassEntityManager& Manager, FMassEntityHandle Entity, double Now)
    {
        const auto* Identity = Manager.GetFragmentDataPtr<FEcoIdentityFragment>(Entity);
        const auto* Region = Manager.GetFragmentDataPtr<FEcoRegionFragment>(Entity);
        const auto* Fauna = Manager.GetFragmentDataPtr<FEcoFaunaFragment>(Entity);
        const auto* Native = Manager.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
        const auto* Life = Fauna ? &Fauna->Life : (Native ? &Native->Individual : nullptr);
        if (!Identity || Identity->StableAgentId <= 0 || !Region || !Life || !Life->bInitialized)
            return nullptr;

        auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("id"), LexToString(Identity->StableAgentId));
        Row->SetStringField(TEXT("species"), Identity->SpeciesId.ToString());
        Row->SetStringField(TEXT("region"), Region->CurrentRegionId.ToString());
        Row->SetStringField(TEXT("backend"), Fauna ? TEXT("rule") : TEXT("native_v3"));
        Row->SetStringField(TEXT("parent_a"), LexToString(Life->ParentA));
        Row->SetStringField(TEXT("parent_b"), LexToString(Life->ParentB));
        Row->SetNumberField(TEXT("generation"), Life->Generation);
        Row->SetNumberField(TEXT("origin"), uint8(Life->Origin));
        Row->SetNumberField(TEXT("offspring"), Life->Offspring);
        Row->SetNumberField(TEXT("sex"), uint8(Life->Sex));
        Row->SetNumberField(TEXT("born"), Life->Born);
        Row->SetNumberField(TEXT("sample_seconds"), Now);
        Row->SetNumberField(TEXT("maturity"), Life->AgeFraction(Now));
        Row->SetNumberField(TEXT("size_gene"), Life->Genome.Size);
        Row->SetNumberField(TEXT("speed_gene"), Life->Genome.Speed);
        Row->SetNumberField(TEXT("caution_gene"), Life->Genome.Caution);
        Row->SetNumberField(TEXT("sociability_gene"), Life->Genome.Sociability);
        Row->SetNumberField(TEXT("coat_gene"), Life->Genome.Coat);
        Row->SetNumberField(TEXT("propulsion_gene"), Life->Genome.Functional.Propulsion);
        Row->SetNumberField(TEXT("endurance_gene"), Life->Genome.Functional.Endurance);
        Row->SetNumberField(TEXT("form_gene"), Life->Genome.Functional.Form);
        const auto& Body = Life->Genome.Functional.Development;
        Row->SetNumberField(TEXT("shape_fore_gene"), Body.Fore);
        Row->SetNumberField(TEXT("shape_aft_gene"), Body.Aft);
        Row->SetNumberField(TEXT("shape_span_gene"), Body.Span);
        Row->SetNumberField(TEXT("shape_rise_gene"), Body.Rise);
        Row->SetNumberField(TEXT("body_scale"), Life->BodyScale(Now));
        Row->SetNumberField(TEXT("speed_scale"), Life->SpeedScale(Now));
        if (const auto* Vitals = Manager.GetFragmentDataPtr<FEcoVitalsFragment>(Entity))
        {
            Row->SetNumberField(TEXT("hp"), Vitals->HP);
            Row->SetNumberField(TEXT("energy"), Vitals->Energy);
        }
        if (const auto* Velocity = Manager.GetFragmentDataPtr<FMassVelocityFragment>(Entity))
            Row->SetNumberField(TEXT("horizontal_speed_cm_s"), Velocity->Value.Size2D());
        if (const auto* Visual = Manager.GetFragmentDataPtr<FEcoCreaturePresentationFragment>(Entity))
        {
            Row->SetNumberField(TEXT("visual_body_scale"), Visual->BodyScale / 128.);
            Row->SetNumberField(TEXT("visual_maturity"), Visual->Maturity / 255.);
            Row->SetNumberField(TEXT("visual_coat_tone"), Visual->CoatTone / 255.);
            Row->SetNumberField(TEXT("visual_body_condition"), Visual->BodyCondition / 128.);
            Row->SetNumberField(TEXT("visual_inherited_length"), double(Visual->InheritedProportions & 255u) / 128.);
            Row->SetNumberField(TEXT("visual_inherited_width"), double(Visual->InheritedProportions >> 8) / 128.);
            Row->SetNumberField(TEXT("visual_body_development"), Visual->InheritedBody);
            Row->SetNumberField(TEXT("visual_appearance"), EcoPresentationFlags::Appearance(Visual->Flags));
        }
        if (Fauna)
        {
            Row->SetBoolField(TEXT("swimming"), Fauna->bSwimming);
            Row->SetNumberField(TEXT("flight_phase"), uint8(Fauna->Flight));
            Row->SetNumberField(TEXT("stamina"), Fauna->Stamina);
            Row->SetNumberField(TEXT("threat_until"), Fauna->ThreatUntil);
        }
        else
        {
            Row->SetBoolField(TEXT("native_adopted"), Native->bAdopted);
            Row->SetNumberField(TEXT("native_maintenance"), Life->Maintenance());
            Row->SetNumberField(TEXT("native_last_damage"), Life->Memory.LastDamage);
            Row->SetBoolField(TEXT("native_last_damage_known"), Life->Memory.bLastDamageKnown);
            Row->SetNumberField(TEXT("native_fear"), Life->Memory.Fear);
            Row->SetNumberField(TEXT("native_unknown_fear"), Life->Memory.UnknownFear);
            Row->SetNumberField(TEXT("native_familiarity"), Life->Memory.Familiarity);
            Row->SetNumberField(TEXT("native_response"), uint8(Life->Memory.Response));
        }
        return Row;
    }

    FString WriteTraitJson(const TSharedRef<FJsonObject>& Object)
    {
        FString Result;
        FJsonSerializer::Serialize(Object, TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Result));
        return Result;
    }

    void SetTraitEventFields(FJsonObject& Row, const FEcoServerTimeSnapshot& Time, const TCHAR* Event)
    {
        Row.SetNumberField(TEXT("schema"), 1);
        Row.SetNumberField(TEXT("epoch"), Time.WorldEpoch);
        Row.SetStringField(TEXT("event"), Event);
    }
}

FString AEcoCreatureIntegrationSpawner::CapturePopulationTraits() const
{
    if (!IsInGameThread() || !HasAuthority() || !bReady || !bEnableEcosystemLife || CompletedTime.WorldEpoch <= 0)
        return {};
    UWorld* World = GetWorld();
    if (!World || World->GetNetMode() == NM_Client) return {};
    auto* Mass = World->GetSubsystem<UMassSpawnerSubsystem>();
    if (!Mass) return {};
    const auto& Manager = Mass->GetEntityManagerChecked();
    if (Manager.IsProcessing()) return {};

    const auto* Native = World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const double CompletedSeconds = CompletedTime.ServerTimeSeconds;
    TArray<int64> Ids;
    AgentLookup.GenerateKeyArray(Ids);
    Ids.Sort();
    TArray<TSharedPtr<FJsonValue>> Agents;
    Agents.Reserve(Ids.Num());
    for (const int64 Id : Ids)
    {
        const FMassEntityHandle Entity = AgentLookup.FindChecked(Id);
        if (!Manager.IsEntityValid(Entity)) continue;
        const auto* Vitals = Manager.GetFragmentDataPtr<FEcoVitalsFragment>(Entity);
        if (!Vitals || Vitals->HP <= 0.f) continue;
        const auto* Fauna = Manager.GetFragmentDataPtr<FEcoFaunaFragment>(Entity);
        double Now = Fauna ? FMath::Max(CompletedSeconds, FaunaMotionTime) : CompletedSeconds;
        if (Native && !Fauna)
        {
            const auto* Link = Manager.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
            if (const auto* Context = Link ? Native->GetContext(Link->ContextIndex) : nullptr)
                Now = Context->Sim.T * EcoRepertoireV3::kStepSeconds;
        }
        const auto Row = BuildTraitRow(Manager, Entity, Now);
        if (!Row) continue;
        const auto& Individual = Fauna ? Fauna->Life : Manager.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Entity).Individual;
        const auto Traits = Individual.FunctionalTraits(Now, UsesFunctionalTraits());
        Row->SetNumberField(TEXT("propulsion_multiplier"), Traits.DriveScale());
        Row->SetNumberField(TEXT("activity_cost_multiplier"), Traits.ActiveCost());
        Row->SetNumberField(TEXT("rest_cost_multiplier"), Traits.RestCost());
        Row->SetNumberField(TEXT("form_reach_multiplier"), Traits.ReachScale());
        Row->SetNumberField(TEXT("body_width_multiplier"), Traits.WidthScale());
        Row->SetNumberField(TEXT("body_height_multiplier"), Traits.HeightScale());
        Row->SetNumberField(TEXT("swim_clearance_multiplier"), Traits.SwimClearanceScale());
        if (Fauna)
        {
            const FName SpeciesId = Manager.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).SpeciesId;
            if (const auto* Survival = Manager.GetFragmentDataPtr<FEcoCreatureSurvivalFragment>(Entity))
                Row->SetNumberField(TEXT("maintenance_energy_per_second"), Fauna->ScaleMaintenance(
                    Survival->Settings.BaseMetabolism * double(Fauna->MaintenanceScale), UsesHeritableFaunaMaintenance(),
                    Now, UsesFunctionalTraits()));
            if (const auto* Profile = FindFauna(SpeciesId); Profile && Profile->Locomotion == EEcoFaunaLocomotion::Flight)
            {
                Row->SetNumberField(TEXT("cruise_cap_cm_s"), FaunaCruiseSpeed(*Profile, *Fauna, Now));
                const auto* Velocity = Manager.GetFragmentDataPtr<FMassVelocityFragment>(Entity);
                Row->SetNumberField(TEXT("flight_stamina_drain_per_second"),
                    FaunaFlightStaminaDrain(*Profile, *Fauna, Velocity ? Velocity->Value.Size2D() : 0.));
            }
        }
        Agents.Add(MakeShared<FJsonValueObject>(Row));
    }
    auto Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("schema"), 1);
    Result->SetNumberField(TEXT("epoch"), CompletedTime.WorldEpoch);
    Result->SetNumberField(TEXT("completed_seconds"), CompletedSeconds);
    Result->SetBoolField(TEXT("heritable_flight"), UsesHeritableFlightSpeed());
    Result->SetBoolField(TEXT("functional_traits"), UsesFunctionalTraits());
    Result->SetBoolField(TEXT("coat_palette"), CoatPalette != nullptr);
    Result->SetBoolField(TEXT("coat_selection"), UsesCoatSelection());
    Result->SetBoolField(TEXT("heritable_fauna_maintenance"), UsesHeritableFaunaMaintenance());
    Result->SetBoolField(TEXT("aquatic_nursery_approach"), UsesAquaticNurseryApproach());
    Result->SetBoolField(TEXT("fauna_breeding_opportunity"), UsesFaunaBreedingOpportunity());
    Result->SetBoolField(TEXT("predator_continuity"), UsesPredatorContinuity());
    Result->SetBoolField(TEXT("covered_refuge_forage"), UsesCoveredRefugeForage());
    Result->SetBoolField(TEXT("covered_refuge_meal_rotation"), UsesCoveredRefugeMealRotation());
    Result->SetBoolField(TEXT("aquatic_patch_meal_rotation"), UsesAquaticPatchMealRotation());
    Result->SetBoolField(TEXT("land_plant_meal_rotation"), UsesLandPlantMealRotation());
    TArray<TSharedPtr<FJsonValue>> Nurseries;
    for (const auto& Birth : FaunaBirths)
    {
        if (Birth.NurseryId.IsNone()) continue;
        const auto Site = MakeShared<FJsonObject>();
        Site->SetStringField(TEXT("region"), Birth.Region.ToString());
        Site->SetStringField(TEXT("species"), Birth.Species.ToString());
        Site->SetStringField(TEXT("site"), Birth.NurseryId.ToString());
        Site->SetStringField(TEXT("parent_a"), LexToString(Birth.ParentA));
        Site->SetStringField(TEXT("parent_b"), LexToString(Birth.ParentB));
        Site->SetNumberField(TEXT("due"), Birth.Due);
        Nurseries.Add(MakeShared<FJsonValueObject>(Site));
    }
    Result->SetArrayField(TEXT("nurseries"), MoveTemp(Nurseries));
    Result->SetArrayField(TEXT("agents"), MoveTemp(Agents));
    return WriteTraitJson(Result);
}

void AEcoCreatureIntegrationSpawner::RecordTraitOutcome(const FMassEntityManager& Manager,
    FMassEntityHandle Entity, const FEcoServerTimeSnapshot& Time, const TCHAR* Event, int64 RelatedAgent,
    int32 DeathCause, bool bPlayerHunt, FName PreviousRegion) const
{
    if (!bAuditTraitOutcomes || !Manager.IsEntityValid(Entity)) return;
    const auto Row = BuildTraitRow(Manager, Entity, Time.ServerTimeSeconds);
    if (!Row) return;
    SetTraitEventFields(*Row, Time, Event);
    if (DeathCause != INDEX_NONE)
    {
        Row->SetNumberField(TEXT("death_cause"), DeathCause);
        Row->SetBoolField(TEXT("player_hunt_receipt"), bPlayerHunt);
    }
    if (RelatedAgent > 0)
        Row->SetStringField(TEXT("related_agent"), LexToString(RelatedAgent));
    if (!PreviousRegion.IsNone())
        Row->SetStringField(TEXT("previous_region"), PreviousRegion.ToString());
    UE_LOG(LogTemp, Log, TEXT("[EcoTrait] %s"), *WriteTraitJson(Row.ToSharedRef()));
}

void AEcoCreatureIntegrationSpawner::RecordTraitHit(const FMassEntityManager& Manager, FMassEntityHandle Entity,
    const FEcoServerTimeSnapshot& Time, const FEcoCombatDamageOutcome& Outcome) const
{
    if (!bAuditTraitOutcomes || Outcome.AppliedDamage <= 0.f) return;
    const auto Row = BuildTraitRow(Manager, Entity, Time.ServerTimeSeconds);
    if (!Row) return;
    SetTraitEventFields(*Row, Time, TEXT("player_hit"));
    Row->SetStringField(TEXT("execution"), LexToString(Outcome.AttackExecutionId));
    Row->SetNumberField(TEXT("step"), Outcome.StepId);
    Row->SetNumberField(TEXT("damage"), Outcome.AppliedDamage);
    UE_LOG(LogTemp, Log, TEXT("[EcoTrait] %s"), *WriteTraitJson(Row.ToSharedRef()));
}
