#include "AI/Behavior/EcoSpeciesAIFragments.h"
void FEcoSpeciesAIMoveFragment::SetTarget(const FVector& Position, float InSpeed, float InRadius, double Now, const UEcoSpeciesAIProfile& P)
{
    if (Position.ContainsNaN()) { Hold(Now); return; }
    Speed=FMath::Clamp(InSpeed,0.f,P.RunSpeed); Radius=FMath::Max(1.f,InRadius);
    if (Status==EEcoAINavigationStatus::Following && Now<RetryAfter) return;
    if (Revision==0 || Status==EEcoAINavigationStatus::None || FVector::DistSquared(Position,Target)>FMath::Square(P.RetargetDistance)
        || (Status==EEcoAINavigationStatus::Failed && Now>=RetryAfter))
    {
        Target=Position; ++Revision; RequestedAt=Now; Deadline=Now+P.PathTimeout;
        Status=EEcoAINavigationStatus::Pending; BestDistance=MAX_flt; LastProgress=Now;
    }
}
void FEcoSpeciesAIMoveFragment::Hold(double Now)
{
    Speed=0;
    if (Status!=EEcoAINavigationStatus::None) { ++Revision; Status=EEcoAINavigationStatus::None; RequestedAt=Now; }
}
void FEcoSpeciesAIFeedingFragment::Add(double Start,double End,FName Region)
{
    if (!FMath::IsFinite(Start)||!FMath::IsFinite(End)||End<=Start) return;
    if (!Segments.IsEmpty() && Segments.Last().Region==Region && FMath::Abs(Segments.Last().End-Start)<.001)
        Segments.Last().End=End;
    else if (Segments.Num()<32) Segments.Add({Start,End,Region});
    else DroppedSeconds+=End-Start;
}
double FEcoSpeciesAIFeedingFragment::ConsumeThrough(double Time,FName Region)
{
    double Seconds=0;
    for (auto& Segment : Segments)
    {
        const double End=FMath::Min(Time,Segment.End);
        if (End>Segment.Start) { if (Segment.Region==Region) Seconds+=End-Segment.Start; else DroppedSeconds+=End-Segment.Start; Segment.Start=End; }
    }
    Segments.RemoveAll([](const auto& S){return S.Start>=S.End;});
    return Seconds;
}
