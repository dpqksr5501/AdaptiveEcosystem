#include "AI/Behavior/EcoSpeciesAIProfile.h"
#include "StateTree.h"
#include "MassStateTreeSchema.h"
bool UEcoSpeciesAIProfile::Validate(FString& Error) const
{
    const float Values[] = {DecisionInterval,HungryEnter,SatiatedExit,MinimumDwell,CalmSeconds,WalkSpeed,RunSpeed,
        BodyRadius,BodyHeight,WanderRadius,ArrivalRadius,RepathInterval,RetargetDistance,CorridorWidth,PathTimeout,
        SlotLease,FoodUnitsPerSecond,GrazeMaxSpeed,PursuitSeconds,SearchSeconds,AttackCooldown,AttackRadius,MediumDistance,FarDistance};
    for (float V : Values) if (!FMath::IsFinite(V) || V < 0) { Error=TEXT("Nonfinite/negative Species AI profile value"); return false; }
    if (Version<1 || (bPolicyOnly&&bPredator) || DecisionInterval<.05f || HungryEnter>=SatiatedExit || SatiatedExit>1 || WalkSpeed<=0 || RunSpeed<WalkSpeed
        || BodyRadius<=0 || BodyHeight<BodyRadius*2 || ArrivalRadius<=0 || RepathInterval<.1f || RetargetDistance<=0
        || CorridorWidth<BodyRadius*2 || PathTimeout<=0 || SlotLease<=DecisionInterval || PursuitSeconds<=0
        || SearchSeconds<=0 || AttackCooldown<=0 || AttackRadius<BodyRadius || MediumDistance<=0 || FarDistance<=MediumDistance)
    { Error=TEXT("Invalid Species AI profile ranges/ordering"); return false; }
    if (!StateTree || !StateTree->IsReadyToRun() || !StateTree->GetSchema() || !StateTree->GetSchema()->IsA<UMassStateTreeSchema>())
    { Error=TEXT("Assign a compiled Mass Behavior StateTree"); return false; }
    return true;
}
