#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Player/EcoCreatureHitProxy.h"
#include "Creature/Player/EcoPlayerEcologyComponent.h"
#include "Player/EcoMeleeHitComponent.h"
#include "Player/EcoPlayerState.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "World/EcoWorldClockSubsystem.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "EngineUtils.h"
#include "Engine/World.h"

namespace EcoCreatureCombat
{
    bool AlivePlayer(const APawn* Pawn)
    {
        const auto* State = Pawn ? Pawn->GetPlayerState<AEcoPlayerState>() : nullptr;
        return Pawn && Pawn->HasAuthority() && Pawn->IsPlayerControlled() && State && State->IsAlive();
    }
    bool ClearLine(UWorld& World, const FVector& A, const FVector& B)
    {
        return !World.LineTraceTestByObjectType(A, B, FCollisionObjectQueryParams(ECC_WorldStatic),
            FCollisionQueryParams(SCENE_QUERY_STAT(EcoCombatObstruction), false));
    }
    FVector NativePosition(FMassEntityManager& EM, FMassEntityHandle Entity, const UEcoPolicyV3IntegratedSubsystem& Native)
    {
        const auto& Link = EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Entity);
        const auto* Context = Native.GetContext(Link.ContextIndex);
        if (const auto* Body = EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(Entity))
            return Context->UnitsToCm(Body->Body.Pos.X, Body->Body.Pos.Y, Link.GroundZ);
        const auto& Wolf = EM.GetFragmentDataChecked<FEcoThreatStateFragment>(Entity).Agent.State;
        return Context->UnitsToCm(Wolf.PosX, Wolf.PosY, Link.GroundZ);
    }
}

FEcoCombatDiagnostics AEcoCreatureIntegrationSpawner::GetCombatDiagnostics() const
{
    auto Result = CombatDiagnostics;
    Result.ActiveProxies = HitProxies.Num(); Result.PooledProxies = HitProxyPool.Num(); Result.PendingDamage = ComboDamage.Num();
    return Result;
}

void AEcoCreatureIntegrationSpawner::ResetCombat()
{
    for (auto& Pair : HitProxies) if (IsValid(Pair.Value)) { Pair.Value->ClearBinding(); Pair.Value->Destroy(); }
    for (AEcoCreatureHitProxy* Proxy : HitProxyPool) if (IsValid(Proxy)) { Proxy->ClearBinding(); Proxy->Destroy(); }
    HitProxies.Reset(); HitProxyPool.Reset(); ComboDamage.Reset(); PendingHuntingDeaths.Reset(); ComboReceipts.Reset(); WolfCombat.Reset(); CombatEpoch = 0;
}

void AEcoCreatureIntegrationSpawner::UpdateHitProxies()
{
    if (!IsInGameThread() || GetNetMode() == NM_Client) return;
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    if (EM.IsProcessing()) return;
    const int32 Epoch = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().WorldEpoch;
    if (!bEnableEcosystemLife || !bEnablePlayerCombat) { ResetCombat(); return; }
    if (CombatEpoch != Epoch) { ResetCombat(); CombatEpoch = Epoch; }
    auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    if (!Native || !Native->IsActive()) return;
    TArray<APawn*> Players;
    for (auto It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
        if (auto* PC = It->Get(); PC && EcoCreatureCombat::AlivePlayer(PC->GetPawn())) Players.Add(PC->GetPawn());
    struct FCandidate { int64 Id; FVector Position; float Scale; bool bWolf; double Distance; };
    TArray<FCandidate> Candidates;
    const double AddDistance = FMath::Clamp(HitProxyDistance, 500.f, 5000.f);
    for (const auto Entity : Owned)
    {
        if (!EM.IsEntityValid(Entity) || EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP <= 0) continue;
        const auto* Link = EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
        if (!Link || !Link->bAdopted || Link->bDead || !Native->GetContext(Link->ContextIndex)) continue;
        const int64 Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).StableAgentId;
        const FVector Position = EcoCreatureCombat::NativePosition(EM, Entity, *Native);
        double Distance = MAX_dbl;
        for (const auto* Player : Players) Distance = FMath::Min(Distance, FVector::DistSquared(Position, Player->GetActorLocation()));
        if (Distance > FMath::Square(AddDistance + (HitProxies.Contains(Id) ? 400. : 0.))) continue;
        const auto* C = Native->GetContext(Link->ContextIndex);
        const float Scale = Link->Individual.bInitialized ? float(Link->Individual.BodyScale(C->Sim.T * EcoRepertoireV3::kStepSeconds)) : 1.f;
        Candidates.Add({Id, Position, Scale, EM.GetFragmentDataPtr<FEcoThreatStateFragment>(Entity) != nullptr, Distance});
    }
    Candidates.Sort([](const auto& A, const auto& B) { return A.Distance == B.Distance ? A.Id < B.Id : A.Distance < B.Distance; });
    if (Candidates.Num() > FMath::Clamp(MaxHitProxies, 1, 512)) Candidates.SetNum(FMath::Clamp(MaxHitProxies, 1, 512));
    TSet<int64> Needed;
    for (const auto& Candidate : Candidates) Needed.Add(Candidate.Id);
    for (auto It = HitProxies.CreateIterator(); It; ++It)
        if (!Needed.Contains(It.Key()) || !IsValid(It.Value()))
        {
            if (IsValid(It.Value())) { It.Value()->ClearBinding(); HitProxyPool.Add(It.Value()); }
            It.RemoveCurrent();
        }
    for (const auto& Candidate : Candidates)
    {
        auto* Proxy = HitProxies.FindRef(Candidate.Id).Get();
        if (!Proxy)
        {
            if (!HitProxyPool.IsEmpty()) Proxy = HitProxyPool.Pop();
            else Proxy = GetWorld()->SpawnActor<AEcoCreatureHitProxy>();
            if (!Proxy) continue;
            Proxy->Bind(this, Epoch, Candidate.Id); HitProxies.Add(Candidate.Id, Proxy);
        }
        Proxy->Sync(Candidate.Position, Candidate.Scale, Candidate.bWolf);
    }
    // All socket queries see the same completed logical-position snapshot, after native movement.
    for (auto* Player : Players) if (auto* Hit = Player->FindComponentByClass<UEcoMeleeHitComponent>()) Hit->EvaluateAtEcologyBoundary();
    for (auto It = WolfCombat.CreateIterator(); It; ++It)
    {
        const auto* Entity = AgentLookup.Find(It.Key());
        if (!Entity || !EM.IsEntityValid(*Entity) || EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Entity).HP <= 0) It.RemoveCurrent();
    }
}

bool AEcoCreatureIntegrationSpawner::QueueComboContact(UEcoMeleeHitComponent& Source, AEcoCreatureHitProxy& Target, const FHitResult& Hit)
{
    FEcoCombatDamageOutcome Outcome;
    Outcome.WorldEpoch = CombatEpoch; Outcome.AttackExecutionId = Source.AttackExecutionId;
    Outcome.StepId = Source.ActiveStep; Outcome.TargetStableAgentId = Target.StableAgentId;
    auto Reject = [&](EEcoDamageResult Reason) { Outcome.Result = Reason; ++CombatDiagnostics.DamageRejected; Source.PublishDamageOutcome(Outcome); return false; };
    auto* Player = Cast<APawn>(Source.GetOwner());
    if (!IsInGameThread() || GetNetMode() == NM_Client || !bReady || !bEnableEcosystemLife || !bEnablePlayerCombat
        || !EcoCreatureCombat::AlivePlayer(Player) || Source.GetWorld() != GetWorld() || !Source.HasAuthoritativeWindow()) return Reject(EEcoDamageResult::InvalidAttack);
    const auto* State = Player->GetPlayerState<AEcoPlayerState>();
    if (CombatEpoch <= 0 || Target.WorldEpoch != CombatEpoch || Target.Coordinator.Get() != this
        || Target.StableAgentId <= 0 || HitProxies.FindRef(Target.StableAgentId) != &Target || Hit.GetActor() != &Target) return Reject(EEcoDamageResult::InvalidTarget);
    if (!Source.AttackData || !Source.AttackData->Steps.IsValidIndex(Source.ActiveStep)) return Reject(EEcoDamageResult::InvalidAttack);
    const auto& Profile = Source.AttackData->Steps[Source.ActiveStep];
    if (!FMath::IsFinite(Profile.Damage) || Profile.Damage <= 0 || Profile.Damage > 10000
        || !FMath::IsFinite(Source.AttackData->MaxReachCm) || Source.AttackData->MaxReachCm < 100 || Source.AttackData->MaxReachCm > 800
        || Hit.ImpactPoint.ContainsNaN() || FVector::DistSquared(Player->GetActorLocation(), Hit.ImpactPoint) > FMath::Square(Source.AttackData->MaxReachCm)) return Reject(EEcoDamageResult::InvalidAttack);
    const double RealNow = GetWorld()->GetTimeSeconds();
    for (auto It = ComboReceipts.CreateIterator(); It; ++It) if (It.Value() < RealNow) It.RemoveCurrent();
    const FString Key = FString::Printf(TEXT("%u:%lld:%d:%lld"), Source.GetUniqueID(), Source.AttackExecutionId, Source.ActiveStep, Target.StableAgentId);
    if (ComboReceipts.Contains(Key)) return Reject(EEcoDamageResult::Duplicate);
    if (ComboDamage.Num() >= 128 || ComboReceipts.Num() >= 4096) return Reject(EEcoDamageResult::QueueFull);
    ComboReceipts.Add(Key, RealNow + 6);
    FComboDamage Request;
    Request.Player = Player; Request.Controller = Player->GetController(); Request.Source = &Source;
    Request.Epoch = CombatEpoch; Request.Stage = Source.ActiveStep; Request.Avatar = State->AvatarGeneration;
    Request.Execution = Source.AttackExecutionId; Request.Target = Target.StableAgentId; Request.Damage = Profile.Damage;
    Request.Issued = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
    Request.Sequence=++CombatContactSequence;
    Request.RealIssued = RealNow; ComboDamage.Add(Request); ++CombatDiagnostics.ContactsQueued;
    Outcome.Result = EEcoDamageResult::Queued; Source.PublishDamageOutcome(Outcome);
    return true;
}

void AEcoCreatureIntegrationSpawner::ProcessComboDamage(const FEcoServerTimeSnapshot& Time, uint64 ThroughSequence)
{
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    // FIFO preserves server contact order. A later combo stage may already be running when consumed.
    for (int32 I = 0; I < ComboDamage.Num();)
    {
        if (ComboDamage[I].Sequence > ThroughSequence || ComboDamage[I].Issued > Time.ServerTimeSeconds + 1.e-6) { ++I; continue; }
        const auto Request = ComboDamage[I]; ComboDamage.RemoveAt(I);
        FEcoCombatDamageOutcome Outcome;
        Outcome.WorldEpoch = Request.Epoch; Outcome.AttackExecutionId = Request.Execution; Outcome.StepId = Request.Stage; Outcome.TargetStableAgentId = Request.Target;
        Outcome.QueueSeconds = GetWorld()->GetTimeSeconds() - Request.RealIssued;
        CombatDiagnostics.MaximumQueueSeconds = FMath::Max(CombatDiagnostics.MaximumQueueSeconds, Outcome.QueueSeconds);
        auto* Player = Request.Player.Get();
        const auto* State = Player ? Player->GetPlayerState<AEcoPlayerState>() : nullptr;
        const auto* Entity = AgentLookup.Find(Request.Target);
        Outcome.Result = EEcoDamageResult::InvalidTarget;
        if (Request.Epoch != Time.WorldEpoch || Time.ServerTimeSeconds - Request.Issued > 3 || Outcome.QueueSeconds > 3) Outcome.Result = EEcoDamageResult::Expired;
        else if (!EcoCreatureCombat::AlivePlayer(Player) || Player->GetController() != Request.Controller.Get() || State->AvatarGeneration != Request.Avatar) Outcome.Result = EEcoDamageResult::InvalidAvatar;
        else if (Entity && EM.IsEntityValid(*Entity))
        {
            const float Before = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Entity).HP;
            if (Before <= 0) Outcome.Result = EEcoDamageResult::AlreadyDead;
            else
            {
                ApplyPlayerDamage(*Player, *Entity, Request.Damage);
                Outcome.RemainingHP = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Entity).HP;
                Outcome.AppliedDamage = Before - Outcome.RemainingHP;
                Outcome.Result = EEcoDamageResult::Committed; ++CombatDiagnostics.DamageCommitted;
                if (Outcome.RemainingHP <= 0) PendingHuntingDeaths.Add(Request.Target, {Request.Source, Outcome});
                if (Outcome.RemainingHP <= 0) if (auto* Proxy = HitProxies.FindRef(Request.Target).Get()) Proxy->ClearBinding();
            }
        }
        if (Outcome.Result != EEcoDamageResult::Committed) ++CombatDiagnostics.DamageRejected;
        if (auto* Source = Request.Source.Get()) Source->PublishDamageOutcome(Outcome);
        UE_LOG(LogTemp, Log, TEXT("[EcoCombat][Outcome] Epoch=%d Execution=%lld Stage=%d Target=%lld Result=%d Applied=%.2f HP=%.2f Queue=%.3f"),
            Outcome.WorldEpoch, Outcome.AttackExecutionId, Outcome.StepId, Outcome.TargetStableAgentId, int32(Outcome.Result), Outcome.AppliedDamage, Outcome.RemainingHP, Outcome.QueueSeconds);
    }
}

bool AEcoCreatureIntegrationSpawner::GuideWolfPlayerCombat(int64 Id, FEcoV3RegionContext& Context, const FVector& Position,
    const FVector& Heading, double Now, bool bAvailable, bool bProvoked, EcoThreatV3::FThreatStepInput& Input)
{
    if (!bEnablePlayerCombat || !bEnableEcosystemLife || !bReady || !bAvailable) { WolfCombat.Remove(Id); return false; }
    auto& Attack = WolfCombat.FindOrAdd(Id);
    APawn* Best = nullptr; double BestDistance = FMath::Min(2400., EcoWorldV3::WolfViewNow(Context.Sim) * EcoRepertoireV3::kUnitCm);
    for (auto It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
    {
        const auto* PC = It->Get(); APawn* Pawn = PC ? PC->GetPawn() : nullptr;
        const auto* Bridge = Pawn ? Pawn->FindComponentByClass<UEcoPlayerEcologyComponent>() : nullptr;
        if (!EcoCreatureCombat::AlivePlayer(Pawn) || !Bridge || !Bridge->bThreatEnabled) continue;
        const FVector Delta = Pawn->GetActorLocation() - Position;
        const double Distance = Delta.Size2D();
        if (Distance > BestDistance || FMath::Abs(Delta.Z) > 220 || (Distance > 1 && FVector::DotProduct(Heading, Delta.GetSafeNormal2D()) < Context.Sim.ThreatCfg.PredFovCos)) continue;
        const auto From = Context.CmToUnits(Position), To = Context.CmToUnits(Pawn->GetActorLocation());
        FVector Eye; FRotator Rotation; Pawn->GetActorEyesViewPoint(Eye, Rotation);
        if (Context.Sim.Food.BlocksSight(From.X, From.Y, To.X, To.Y) || !EcoCreatureCombat::ClearLine(*GetWorld(), Position + FVector(0,0,65), Eye)) continue;
        // A hurt wolf retaliates only with identified, recent evidence. Unprovoked approach uses a small territory radius.
        if (!bProvoked && Distance > 900) continue;
        Best = Pawn; BestDistance = Distance;
    }
    if (!Best) { Attack.Target.Reset(); Attack.Due = -1; Attack.bPending = false; return false; }
    const uint32 Avatar = Best->GetPlayerState<AEcoPlayerState>()->AvatarGeneration;
    if (Attack.Target.Get() != Best || Attack.Avatar != Avatar) { Attack.Target = Best; Attack.Avatar = Avatar; Attack.Due = -1; Attack.bPending = false; }
    Attack.LastSeen = Now;
    if (BestDistance < 190 && Now >= Attack.Cooldown && Attack.Due < 0 && !Attack.bPending)
    {
        Attack.Due = Now + .5; ++CombatDiagnostics.WolfAttacks;
        UE_LOG(LogTemp, Log, TEXT("[EcoCombat][WolfWindup] Wolf=%lld Player=%s Due=%.3f"), Id, *Best->GetName(), Attack.Due);
    }
    if (Attack.Due >= 0 && Now >= Attack.Due) { Attack.bPending = true; Attack.Sequence=++CombatContactSequence; Attack.ContactTime=Now; Attack.Cooldown = Now + 1.5; Attack.Due = -1; }
    Input.bHuntingAllowed = false; Input.bPackHelp = false; Input.bResourceApproach = true;
    Input.bResourceWait = BestDistance < 150 || Attack.bPending || Attack.Due >= 0 || Now < Attack.Cooldown;
    const FVector Direction = (Best->GetActorLocation() - Position).GetSafeNormal2D();
    Input.ResourceDirX = Direction.X; Input.ResourceDirY = Direction.Y;
    return true;
}

void AEcoCreatureIntegrationSpawner::ProcessWolfAttacks(const FEcoServerTimeSnapshot& Time, uint64 ThroughSequence)
{
    if (!bEnablePlayerCombat || !bEnableEcosystemLife) return;
    auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>(); if (!Native) return;
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    TArray<int64> Order; WolfCombat.GetKeys(Order); Order.Sort();
    for (const int64 Id : Order)
    {
        auto& Attack = WolfCombat.FindChecked(Id);
        if (!Attack.bPending || Attack.Sequence>ThroughSequence || Attack.ContactTime>Time.ServerTimeSeconds+1.e-6) continue;
        Attack.bPending = false;
        const auto* Entity = AgentLookup.Find(Id); auto* Player = Attack.Target.Get();
        if (!Entity || !EM.IsEntityValid(*Entity) || EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Entity).HP <= 0 || !EcoCreatureCombat::AlivePlayer(Player)) continue;
        auto* State = Player->GetPlayerState<AEcoPlayerState>();
        const auto& Link = EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(*Entity);
        const auto* C = Native->GetContext(Link.ContextIndex); if (!C || Link.bDead || State->AvatarGeneration != Attack.Avatar) continue;
        const double Now = C->Sim.T * EcoRepertoireV3::kStepSeconds;
        if (Now < Attack.LastSeen || Now - Attack.LastSeen > .3) continue;
        const FVector Position = EcoCreatureCombat::NativePosition(EM, *Entity, *Native);
        const FVector Delta = Player->GetActorLocation() - Position;
        const auto& Wolf = EM.GetFragmentDataChecked<FEcoThreatStateFragment>(*Entity).Agent.State;
        const FVector Heading(Wolf.HeadX, Wolf.HeadY, 0);
        if (Delta.Size2D() > 210 || FMath::Abs(Delta.Z) > 220 || FVector::DotProduct(Heading, Delta.GetSafeNormal2D()) < .3
            || !EcoCreatureCombat::ClearLine(*GetWorld(), Position + FVector(0,0,65), Player->GetActorLocation())) continue;
        if (State->ApplyCreatureDamage(Player, WolfPlayerDamage, Id) > 0) ++CombatDiagnostics.PlayerHits;
    }
}

void AEcoCreatureIntegrationSpawner::ProcessCombatDamage(const FEcoServerTimeSnapshot& Time)
{
    for (int32 Pass=0;Pass<640;++Pass)
    {
        uint64 Next=MAX_uint64;
        for(const auto& R:ComboDamage) if(R.Issued<=Time.ServerTimeSeconds+1.e-6) Next=FMath::Min(Next,R.Sequence);
        for(const auto& Pair:WolfCombat) if(Pair.Value.bPending&&Pair.Value.ContactTime<=Time.ServerTimeSeconds+1.e-6) Next=FMath::Min(Next,Pair.Value.Sequence);
        if(Next==MAX_uint64)break;
        ProcessComboDamage(Time,Next);ProcessWolfAttacks(Time,Next);
    }
}
