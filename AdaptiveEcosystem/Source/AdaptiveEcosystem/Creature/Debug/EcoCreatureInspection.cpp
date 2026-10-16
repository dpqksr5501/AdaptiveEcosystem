#include "Creature/Debug/EcoCreatureInspection.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/EcoPolicyV3SocialBridge.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "AI/Social/Senses/EcoSensoryTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntitySubsystem.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/Canvas.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

bool UEcoCreatureInspectionLibrary::CaptureAgent(UObject* Context,int64 AgentId,FString& Json)
{
    Json.Reset();UWorld* World=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!World||AgentId<=0||!IsInGameThread())return false;
    auto* Mass=World->GetSubsystem<UMassEntitySubsystem>();if(!Mass)return false;
    auto& Manager=Mass->GetMutableEntityManager();if(Manager.IsProcessing())return false;
    TSharedPtr<FJsonObject> Data;
    FMassEntityQuery Query(Manager.AsShared());
    Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
    auto Exec=Manager.CreateExecutionContext(0);
    Query.ForEachEntityChunk(Exec,[&](FMassExecutionContext& C){
        const auto Ids=C.GetFragmentView<FEcoIdentityFragment>();
        for(int32 I=0;I<C.GetNumEntities();++I)if(Ids[I].StableAgentId==AgentId){
            Data=MakeShared<FJsonObject>();const auto E=C.GetEntity(I);
            Data->SetNumberField(TEXT("schema"),1);Data->SetStringField(TEXT("stable_id"),LexToString(AgentId));
            Data->SetStringField(TEXT("species"),Ids[I].SpeciesId.ToString());
            Data->SetNumberField(TEXT("world_seconds"),World->GetTimeSeconds());
            Data->SetBoolField(TEXT("authority"),World->GetNetMode()!=NM_Client);
            Data->SetStringField(TEXT("position"),C.GetFragmentView<FTransformFragment>()[I].GetTransform().GetLocation().ToCompactString());
            if(const auto* View=Manager.GetFragmentDataPtr<FEcoCreaturePresentationFragment>(E)){
                Data->SetStringField(TEXT("activity"),UEnum::GetValueAsString(EEcoSpeciesActivity(View->Activity)));
                Data->SetStringField(TEXT("sense"),UEnum::GetValueAsString(EEcoSenseSource((View->Flags>>4)&3)));
                Data->SetNumberField(TEXT("energy_fraction"),View->Energy/255.0);
            }
            if(const auto* Cue=Manager.GetFragmentDataPtr<FEcoCreatureCueFragment>(E)){
                Data->SetStringField(TEXT("sense_source_key"),LexToString(Cue->Memory.SourceKey));
                Data->SetNumberField(TEXT("confidence"),Cue->Memory.Confidence);
                Data->SetStringField(TEXT("last_known"),Cue->Memory.LastKnownPosition.ToCompactString());
            }
            if(World->GetNetMode()==NM_Client)return;
            if(const auto* Link=Manager.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E))
                if(const auto* Sub=World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>())
                    if(const auto* Ctx=Sub->GetContext(Link->ContextIndex)) {
                        const auto& W=Ctx->Sim;
                        Data->SetBoolField(TEXT("refuge_safety_enabled"),W.Config.bProtectedRefuges);
                        Data->SetNumberField(TEXT("refuge_protected_prey_steps"),double(W.Stats.RefugeProtectedPreySteps));
                        Data->SetNumberField(TEXT("refuge_constrained_moves"),double(W.Stats.RefugeConstrainedMoves));
                        Data->SetNumberField(TEXT("refuge_capture_violations"),double(W.Stats.RefugeCaptureViolations));
                        Data->SetNumberField(TEXT("refuge_inside_predator_steps"),double(W.Stats.RefugeInsidePredatorSteps));
                        if(const auto* Body=Manager.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E))
                            Data->SetBoolField(TEXT("refuge_protected_here"),W.Config.bProtectedRefuges&&EcoRefugeV3::Contains(W.Config.Covers,Body->Body.Pos));
                        if(const auto* Wolf=Manager.GetFragmentDataPtr<FEcoThreatStateFragment>(E))
                            Data->SetBoolField(TEXT("wolf_inside_refuge"),EcoRefugeV3::Contains(W.Config.Covers,{Wolf->Agent.State.PosX,Wolf->Agent.State.PosY}));
                    }
            Data->SetBoolField(TEXT("social_runtime"),Manager.GetFragmentDataPtr<FEcoSocialBehaviorFragment>(E)!=nullptr);
            Data->SetBoolField(TEXT("species_ai_movement"),Manager.GetFragmentDataPtr<FEcoSpeciesAIMoveFragment>(E)!=nullptr);
            if(const auto* V=Manager.GetFragmentDataPtr<FEcoVitalsFragment>(E)){Data->SetNumberField(TEXT("hp"),V->HP);Data->SetNumberField(TEXT("energy"),V->Energy);}
            if(const auto* Alarm=Manager.GetFragmentDataPtr<FEcoAlarmStateFragment>(E)) {
                Data->SetNumberField(TEXT("social_state"),int32(Alarm->State));
                Data->SetNumberField(TEXT("alarm_strength"),Alarm->AlarmStrength);
                Data->SetStringField(TEXT("alarm_position"),Alarm->LastThreatPosition.ToCompactString());
            }
            if(const auto* Member=Manager.GetFragmentDataPtr<FEcoHerdMemberFragment>(E)) {
                FEcoHerdRuntimeData Herd;
                if(const auto* Herds=World->GetSubsystem<UEcoHerdSubsystem>();Herds&&Herds->GetHerdData(Member->HerdRuntimeIndex,Herd))
                    Data->SetStringField(TEXT("herd_id"),LexToString(Herd.PersistentHerdId));
            }
            if(const auto* Social=Manager.GetFragmentDataPtr<FEcoV3SocialBridgeFragment>(E)) {
                Data->SetNumberField(TEXT("social_override"),int32(Social->Applied));
                Data->SetNumberField(TEXT("native_behavior_before_social"),Social->NativeBehavior);
                Data->SetBoolField(TEXT("unsafe_shelter_yielded"),Social->bRejectedUnsafeShelter);
            }
            if(const auto* Intent=Manager.GetFragmentDataPtr<FEcoShelterIntentFragment>(E)) {
                Data->SetNumberField(TEXT("shelter_state"),int32(Intent->State));
                Data->SetStringField(TEXT("reservation_id"),LexToString(Intent->ReservationId));
            }
            if(const auto* Request=Manager.GetFragmentDataPtr<FEcoSocialMovementRequestFragment>(E)) {
                Data->SetNumberField(TEXT("social_forage"),Request->EffectiveAction.Forage);
                Data->SetNumberField(TEXT("social_cohesion"),Request->EffectiveAction.Cohesion);
            }
            if(const auto* P=Manager.GetFragmentDataPtr<FEcoBehaviorStateFragment>(E)){
                Data->SetStringField(TEXT("brain"),TEXT("PPO_V3_builtin"));
                Data->SetStringField(TEXT("movement"),TEXT("NativeV3_single_writer"));
                Data->SetNumberField(TEXT("policy_obs_dim"),EcoPolicyV3::kObsDim);
                Data->SetNumberField(TEXT("policy_mask_version"),EcoPolicyV3::kMaskVersion);
                Data->SetStringField(TEXT("policy_contract"),LexToString(EcoPolicyV3::kContractHash));
                Data->SetBoolField(TEXT("committed_policy_read"),P->Decision.bCommittedReads);
                Data->SetBoolField(TEXT("next_policy_read"),P->Decision.Prep.bReads);
                Data->SetNumberField(TEXT("next_request"),P->Decision.Request);
                Data->SetNumberField(TEXT("flight_override"),P->Decision.KeepActive);
                Data->SetNumberField(TEXT("see_mult"),P->Rep.SeeMult);
                TArray<TSharedPtr<FJsonValue>> Logits,Mask;
                for(int32 K=0;K<EcoRepertoireV3::kNumBehaviors;++K){
                    Logits.Add(MakeShared<FJsonValueNumber>(P->Decision.Logits[K]));
                    Mask.Add(MakeShared<FJsonValueNumber>(P->Decision.Mask[K]));
                }
                Data->SetArrayField(TEXT("next_logits"),Logits);Data->SetArrayField(TEXT("next_mask"),Mask);
                Data->SetNumberField(TEXT("policy_version"),3);Data->SetNumberField(TEXT("request"),P->Decision.CommittedRequest);
                Data->SetNumberField(TEXT("executed"),P->BehaviorId);Data->SetNumberField(TEXT("phase"),P->PhaseId);
                Data->SetNumberField(TEXT("mask"),P->PendingMaskBits);
                if(const auto* Link=Manager.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E))
                    if(const auto* Sub=World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>())
                        if(const auto* Ctx=Sub->GetContext(Link->ContextIndex)) {
                            Data->SetBoolField(TEXT("wild_flight_enabled"),Ctx->Sim.Config.WildFlight.bEnabled);
                            Data->SetBoolField(TEXT("realism_vision_enabled"),Ctx->Sim.Config.RealismVision.bEnabled);
                            Data->SetBoolField(TEXT("realism_hearing_enabled"),Ctx->Sim.Config.RealismHearing.bEnabled);
                            Data->SetNumberField(TEXT("native_vision_radius_cm"),EcoObservationV3::SeePredRadius(Ctx->Sim.Dark,Ctx->Sim.ObsCfg)*P->Rep.SeeMult*EcoRepertoireV3::kUnitCm);
                            Data->SetNumberField(TEXT("native_vision_angle_deg"),2*FMath::RadiansToDegrees(std::acos(Ctx->Sim.ObsCfg.ThreatFovCos)));
                            // Last native observation snapshot, including resting/sleeping wolves. This is
                            // read-only diagnosis, not a new omniscient input to policy or Social alarms.
                            if(const auto* Body=Manager.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E)) {
                                const int32 Count=int32(Ctx->Sim.ThreatIn.size()-Ctx->Sim.ExternalThreats.size());
                                int32 Nearest=INDEX_NONE;double Distance=0;
                                for(int32 J=0;J<Count;++J) {
                                    const auto& T=Ctx->Sim.ThreatIn[J];
                                    const double D=std::hypot(T.X-Body->Body.Pos.X,T.Y-Body->Body.Pos.Y);
                                    if(Nearest==INDEX_NONE||D<Distance){Nearest=J;Distance=D;}
                                }
                                if(Nearest!=INDEX_NONE) {
                                    const auto& T=Ctx->Sim.ThreatIn[Nearest];
                                    const auto Seen=EcoObservationV3::PerceiveThreats(Body->Body.Pos,Body->Body.Head,
                                        EcoObservationV3::SeePredRadius(Ctx->Sim.Dark,Ctx->Sim.ObsCfg),P->Rep.SeeMult,P->Rep.SeeMultLast,&T,1,Ctx->Sim.ObsCfg);
                                    const bool Hunting=T.bHunting&&!T.bAsleep;
                                    const TCHAR* Reason=T.bAsleep?TEXT("Asleep"):
                                        Seen.bNearestSight?(Hunting?TEXT("SeenHunter"):TEXT("SeenRestingWolf")):
                                        Seen.bNearestHeard?(Hunting?TEXT("HeardHunter"):TEXT("HeardRestingWolf")):TEXT("OutsideSightAndHearing");
                                    Data->SetNumberField(TEXT("nearest_wolf_snapshot_index"),Nearest);
                                    Data->SetNumberField(TEXT("nearest_wolf_distance_cm"),Distance*EcoRepertoireV3::kUnitCm);
                                    Data->SetNumberField(TEXT("nearest_wolf_hearing_radius_cm"),T.HearR*EcoRepertoireV3::kUnitCm);
                                    Data->SetBoolField(TEXT("nearest_wolf_sight_native"),Seen.bNearestSight);
                                    Data->SetBoolField(TEXT("nearest_wolf_heard_native"),Seen.bNearestHeard);
                                    Data->SetBoolField(TEXT("nearest_wolf_hunting"),Hunting);
                                    Data->SetBoolField(TEXT("nearest_wolf_asleep"),T.bAsleep);
                                    Data->SetStringField(TEXT("nearest_wolf_reason"),Reason);
                                }
                            }
                            if(const auto* Sense=Manager.GetFragmentDataPtr<FEcoPerceptionCacheFragment>(E)) {
                                const int32 Index=Sense->Perception.Threat.Nearest;
                                const int32 WolfCount=int32(Ctx->Sim.ThreatIn.size()-Ctx->Sim.ExternalThreats.size());
                                if(Index>=0&&Index<int32(Ctx->Sim.ThreatIn.size()))
                                    Data->SetStringField(TEXT("native_nearest_threat_kind"),Index<WolfCount?TEXT("NativeWolf"):TEXT("ExternalPlayer"));
                            }
                            const int32 K=P->Rep.HideTarget;
                            if(K>=0&&K<int32(Ctx->Sim.Config.Covers.size())) {
                                const auto& Cover=Ctx->Sim.Config.Covers[K];
                                Data->SetStringField(TEXT("target"),Ctx->UnitsToCm(Cover.X,Cover.Y,Link->GroundZ).ToCompactString());
                                Data->SetNumberField(TEXT("native_cover_radius_cm"),Cover.Radius*EcoRepertoireV3::kUnitCm);
                            }
                        }

            }else if(const auto* Raw=Manager.GetFragmentDataPtr<FEcoPolicyOutputFragment>(E)){
                Data->SetNumberField(TEXT("policy_version"),1);Data->SetNumberField(TEXT("forage_raw"),Raw->Action.Forage);
                Data->SetNumberField(TEXT("cover_raw"),Raw->Action.Cover);
            }
            if(const auto* P=Manager.GetFragmentDataPtr<FEcoPerceptionCacheFragment>(E)){
                Data->SetBoolField(TEXT("native_in_cover"),P->Perception.Cover.bInCover);
                if(const auto* State=Manager.GetFragmentDataPtr<FEcoBehaviorStateFragment>(E))
                    Data->SetBoolField(TEXT("hide_arrived"),State->Rep.bArrived&&State->Rep.Behavior==EcoRepertoireV3::kHide);
                Data->SetNumberField(TEXT("native_threat_count"),P->Perception.Threat.PredCount);
                if(P->Perception.Threat.Nearest>=0)
                    Data->SetNumberField(TEXT("native_threat_distance_cm"),P->Perception.Threat.DPredMin*EcoRepertoireV3::kUnitCm);
                Data->SetBoolField(TEXT("native_threat_sight"),P->Perception.Threat.bNearestSight);
                Data->SetBoolField(TEXT("native_threat_heard"),P->Perception.Threat.bNearestHeard);
                Data->SetNumberField(TEXT("native_nearest_threat_index"),P->Perception.Threat.Nearest);
                Data->SetNumberField(TEXT("native_kin_count"),P->Perception.Kin.KinCount);
                Data->SetNumberField(TEXT("native_kin_alarm"),P->Perception.Kin.KinAlarm);
                TArray<TSharedPtr<FJsonValue>> Obs;
                for(const float Value:P->Perception.Obs)Obs.Add(MakeShared<FJsonValueNumber>(Value));
                Data->SetArrayField(TEXT("observation"),Obs);
            }
            if(const auto* B=Manager.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E)){
                Data->SetNumberField(TEXT("last_intake"),B->Body.LastIntake);
                Data->SetNumberField(TEXT("reserve"),B->Body.Reserve);
                Data->SetNumberField(TEXT("native_head_x"),B->Body.Head.X);Data->SetNumberField(TEXT("native_head_y"),B->Body.Head.Y);
            }
            if(const auto* Wolf=Manager.GetFragmentDataPtr<FEcoThreatStateFragment>(E)) {
                Data->SetStringField(TEXT("brain"),TEXT("NativeV3_threat_FSM"));
                Data->SetStringField(TEXT("movement"),TEXT("NativeV3_single_writer"));
                Data->SetBoolField(TEXT("wolf_hunting"),Wolf->Agent.Last.bHunting);
                Data->SetBoolField(TEXT("wolf_has_target"),Wolf->Agent.Last.bHasTarget);
                Data->SetBoolField(TEXT("wolf_sated"),Wolf->Agent.Last.bSated);
                Data->SetBoolField(TEXT("wolf_asleep"),Wolf->Agent.State.bAsleep);
                Data->SetNumberField(TEXT("wolf_eat_steps"),Wolf->Agent.State.Cooldown);
                Data->SetNumberField(TEXT("wolf_sated_steps"),Wolf->Agent.State.SatLeft);
            }
            if(const auto* S=Manager.GetFragmentDataPtr<FEcoSocialMovementRequestFragment>(E); S&&S->bValid&&S->Mode!=EEcoSocialMovementMode::None&&S->ReservationId>0){
                Data->SetStringField(TEXT("target"),S->TargetPosition.ToCompactString());Data->SetNumberField(TEXT("reservation"),double(S->ReservationId));
            }
            if(const auto* S=Manager.GetFragmentDataPtr<FEcoSensoryStateFragment>(E)){
                // This channel intentionally excludes harmless resting wolves. Keep it distinguishable
                // from native_threat_sight / nearest_wolf_reason in the inspection output.
                Data->SetStringField(TEXT("alarm_sense"),UEnum::GetValueAsString(S->Source));
                Data->SetStringField(TEXT("sense"),UEnum::GetValueAsString(S->Source));Data->SetNumberField(TEXT("confidence"),S->Confidence);
                Data->SetStringField(TEXT("last_known"),S->LastKnownPosition.ToCompactString());
            }
        }
    });
    if(!Data)return false;
    return FJsonSerializer::Serialize(Data.ToSharedRef(),TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Json));
}
void AEcoCreatureInspectorHUD::DrawHUD()
{
    Super::DrawHUD();if(!Canvas||!PlayerOwner)return;
    TArray<AEcoCreatureRepresentationActor*> Actors;
    for(TActorIterator<AEcoCreatureRepresentationActor> It(GetWorld());It;++It)if(It->bBound&&!It->IsHidden())Actors.Add(*It);
    Actors.Sort([](const auto& A,const auto& B){return A.VisualState.StableAgentId<B.VisualState.StableAgentId;});
    if(!Selected.IsValid()||!Selected->bBound||Selected->VisualState.StableAgentId!=SelectedId){Selected=nullptr;SelectedId=0;}
    if(PlayerOwner->WasInputKeyJustPressed(EKeys::Tab)&&!Actors.IsEmpty()){
        int32 I=Actors.IndexOfByKey(Selected.Get());Selected=Actors[(I+1)%Actors.Num()];SelectedId=Selected->VisualState.StableAgentId;
    }
    if(PlayerOwner->WasInputKeyJustPressed(EKeys::MiddleMouseButton)){
        float Best=10000;FVector2D Mouse(Canvas->SizeX*.5f,Canvas->SizeY*.5f);PlayerOwner->GetMousePosition(Mouse.X,Mouse.Y);
        for(auto* Actor:Actors){FVector2D P;if(PlayerOwner->ProjectWorldLocationToScreen(Actor->GetActorLocation()+FVector(0,0,80),P)){
            const float D=FVector2D::DistSquared(P,Mouse);if(D<Best){Best=D;Selected=Actor;SelectedId=Actor->VisualState.StableAgentId;}
        }}
    }
    if(PlayerOwner->WasInputKeyJustPressed(EKeys::R)){
        bRecording=!bRecording;NextRecord=0;
        if(bRecording){RecordPath=FPaths::ProjectSavedDir()/TEXT("JYU")/FString::Printf(TEXT("Inspection_%s.jsonl"),*FDateTime::UtcNow().ToString(TEXT("%Y%m%d_%H%M%S")));IFileManager::Get().MakeDirectory(*FPaths::GetPath(RecordPath),true);}
    }
    const bool Preview=Actors.ContainsByPredicate([](const AEcoCreatureRepresentationActor* Actor){return Actor->ActorHasTag(TEXT("JYU.VisualAudit"));});
    if(Preview){
        const float PreviewY=Selected.IsValid()?480.f:410.f;
        DrawRect(FLinearColor(.25f,.1f,.01f,.95f),15,PreviewY,620,55);
        DrawText(TEXT("POSE / IK PREVIEW: comparison deer have NO AI."),FLinearColor::Yellow,25,PreviewY+10,nullptr,.9f);
        DrawText(TEXT("Play ends after the comparison. Start Play again for ecology."),FLinearColor::White,25,PreviewY+31,nullptr,.8f);
    }
    DrawRect(FLinearColor(.02f,.025f,.035f,.85f),15,15,600,Selected.IsValid()?450:65);
    DrawText(TEXT("ECO INSPECTOR | Tab: cycle  Middle mouse: pick  R: record"),FLinearColor::White,25,25,nullptr,.85f);
    if(!Selected.IsValid()){DrawText(TEXT("Select a visible creature. Shift: run  Ctrl: sneak"),FLinearColor(.6f,.8f,1),25,50,nullptr,.85f);return;}
    const auto& S=Selected->VisualState;
    const FString Text=FString::Printf(TEXT("%s #%lld  Region: %s\nActivity: %s\nSense: %s  Focus yaw: %.0f\nHealth: %.0f%%  Energy: %.0f%%  Speed: %.0f cm/s\n%s"),
        *S.SpeciesId.ToString(),SelectedId,*S.RegionId.ToString(),*UEnum::GetValueAsString(S.Activity),*UEnum::GetValueAsString(S.SenseSource),
        S.FocusYawDegrees,S.NormalizedHealth*100,S.NormalizedEnergy*100,S.Velocity.Size2D(),bRecording?TEXT("Recording 1 Hz JSONL"):TEXT("Read-only presentation"));
    DrawText(Text,FLinearColor(.75f,.9f,1),25,55,nullptr,1);
    if(GetWorld()->GetTimeSeconds()>=NextInspection) {
        NextInspection=GetWorld()->GetTimeSeconds()+.5;InspectionDetail.Reset();InspectionJson.Reset();
        if(UEcoCreatureInspectionLibrary::CaptureAgent(this,SelectedId,InspectionJson)) {
            TSharedPtr<FJsonObject> J;auto Reader=TJsonReaderFactory<>::Create(InspectionJson);
            if(FJsonSerializer::Deserialize(Reader,J)&&J.IsValid()) {
                for(const TCHAR* Key:{TEXT("request"),TEXT("executed"),TEXT("last_intake"),TEXT("flight_override"),TEXT("refuge_protected_here"),TEXT("native_in_cover"),TEXT("hide_arrived"),TEXT("nearest_wolf_reason"),TEXT("nearest_wolf_distance_cm"),TEXT("nearest_wolf_hearing_radius_cm"),TEXT("native_vision_radius_cm"),TEXT("alarm_sense"),TEXT("social_state"),TEXT("alarm_strength"),TEXT("social_override"),TEXT("shelter_state"),TEXT("target"),TEXT("wolf_inside_refuge"),TEXT("wolf_hunting"),TEXT("wolf_sated"),TEXT("wolf_asleep"),TEXT("wolf_eat_steps"),TEXT("wolf_sated_steps")}) {
                    const auto V=J->TryGetField(Key);if(!V.IsValid())continue;
                    const FString Value=V->Type==EJson::String?V->AsString():V->Type==EJson::Boolean?(V->AsBool()?TEXT("true"):TEXT("false")):LexToString(V->AsNumber());
                    InspectionDetail+=FString(Key)+TEXT(": ")+Value+TEXT("\n");
                }
                if(GetWorld()->GetNetMode()==NM_Client)InspectionDetail=TEXT("Client: presentation only. Policy details are available on authority.");
            }
        }
    }
    DrawText(InspectionDetail,FLinearColor(.7f,.85f,.7f),25,155,nullptr,.8f);

    if(bRecording&&GetWorld()->GetTimeSeconds()>=NextRecord){
        NextRecord=GetWorld()->GetTimeSeconds()+1;
        FString Json;
        if(UEcoCreatureInspectionLibrary::CaptureAgent(this,SelectedId,Json)){
            Json+=TEXT("\n");FFileHelper::SaveStringToFile(Json,*RecordPath,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
        }
    }
}
