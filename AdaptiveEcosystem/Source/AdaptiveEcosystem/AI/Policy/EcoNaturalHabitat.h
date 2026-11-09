#pragma once
// Engine-independent spatial proposals. Distances here are cm unless stated.
// Noise is an art-directed surrogate for unresolved microsites, not new food.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <array>

namespace EcoNaturalHabitat
{
    struct FBite { int Cell=-1;double X=0,Y=0,Time=0,Amount=0; };
    struct FBrowseEvidence
    {
        std::array<FBite,192> Events{};
        std::uint64_t Sequence=0;
        void Add(int Cell,double X,double Y,double Time,double Amount)
        {
            if(Amount<=0||!std::isfinite(Amount)||!std::isfinite(Time)||!std::isfinite(X)||!std::isfinite(Y))return;
            for(auto& E:Events)if(E.Cell==Cell&&Time>=E.Time&&Time-E.Time<20&&(E.X-X)*(E.X-X)+(E.Y-Y)*(E.Y-Y)<.5){
                const double Old=E.Amount*(1-(Time-E.Time)/20),Total=Old+Amount;
                E.X=(E.X*Old+X*Amount)/Total;E.Y=(E.Y*Old+Y*Amount)/Total;E.Amount=Total;E.Time=Time;++Sequence;return;
            }
            for(auto& E:Events)if(E.Cell<0||Time-E.Time>=20){E={Cell,X,Y,Time,Amount};++Sequence;return;}
            Events[Sequence++%Events.size()]={Cell,X,Y,Time,Amount};
        }
    };
    inline std::uint32_t Hash(std::uint32_t V)
    { V^=V>>16;V*=0x7feb352du;V^=V>>15;V*=0x846ca68bu;return V^(V>>16); }
    inline double Random(std::uint32_t Seed,std::uint32_t Key)
    { return (Hash(Seed^Hash(Key))>>8)/16777216.; }
    inline double Smooth(double V) { V=std::clamp(V,0.,1.);return V*V*(3-2*V); }
    inline double Noise(double X,double Y,std::uint32_t Seed)
    {
        const auto IX=std::int32_t(std::floor(X)),IY=std::int32_t(std::floor(Y));
        const double U=Smooth(X-IX),V=Smooth(Y-IY);
        auto Sample=[&](std::int32_t A,std::int32_t B){return Random(Seed,std::uint32_t(A)*73856093u^std::uint32_t(B)*19349663u);};
        const double A=Sample(IX,IY)*(1-U)+Sample(IX+1,IY)*U;
        const double B=Sample(IX,IY+1)*(1-U)+Sample(IX+1,IY+1)*U;
        return A*(1-V)+B*V;
    }
    struct FSite { double X=0,Y=0,Yaw=0,Scale=1; };
    inline FSite Candidate(std::uint32_t Seed,std::uint32_t Cell,int Ordinal,double CellSize)
    {
        const auto Key=Cell*37u+std::uint32_t(Ordinal)*131u;
        // Stratified jitter bounds adjacent sites; no repeated centre/cross pattern.
        return {((Ordinal%3-1)*.29+(Random(Seed,Key)-.5)*.20)*CellSize,
                ((Ordinal/3-1)*.29+(Random(Seed,Key+1)-.5)*.20)*CellSize,
                Random(Seed,Key+2)*360,.70+Random(Seed,Key+3)*.6};
    }
    inline double PatchDensity(double X,double Y,double Scale,std::uint32_t Seed)
    { return .22+.78*Smooth(Noise(X/Scale,Y/Scale,Seed)*1.65-.25); }
    inline double Triangle(double Value,double Minimum,double Optimum,double Maximum)
    {
        if(Value<=Minimum||Value>=Maximum)return 0;
        return Value<Optimum?(Value-Minimum)/(Optimum-Minimum):(Maximum-Value)/(Maximum-Optimum);
    }
    struct FGroundTraversal
    {
        double MaxSlopeDegrees=40,StepUpCm=35,DropCm=60,WadingDepthCm=40;
        bool IsValid() const {return std::isfinite(MaxSlopeDegrees)&&MaxSlopeDegrees>0&&MaxSlopeDegrees<=49
            &&std::isfinite(StepUpCm)&&StepUpCm>=0&&StepUpCm<=100&&std::isfinite(DropCm)&&DropCm>=0&&DropCm<=150
            &&std::isfinite(WadingDepthCm)&&WadingDepthCm>=0&&WadingDepthCm<=100;}
        bool AllowsHeight(double From,double To,double Distance) const
        {
            if(!IsValid()||!std::isfinite(From)||!std::isfinite(To)||!std::isfinite(Distance)||Distance<0)return false;
            const double Slope=Distance*std::tan(MaxSlopeDegrees*.017453292519943295);
            return To-From<=std::max(StepUpCm,Slope)&&From-To<=std::max(DropCm,Slope);
        }
    };
    struct FSettlementBudget
    {
        double FoodPerHead=0,RequiredPerHead=0;
        bool bAdmissible=false;
    };
    // Destination knowledge remains a dated report. Committed population is an
    // admission-ledger floor, not a new per-agent observation of remote animals.
    inline FSettlementBudget SettlementBudget(double Food,double Recovery30,int ReportedPopulation,int CommittedPopulation,
        int Incoming,int Members,double FoodPerSecond,double Horizon=60)
    {
        FSettlementBudget Out;
        if(!std::isfinite(Food)||Food<0||!std::isfinite(Recovery30)||Recovery30<0||!std::isfinite(FoodPerSecond)||FoodPerSecond<=0
            ||!std::isfinite(Horizon)||Horizon<30||Horizon>300||ReportedPopulation<0||CommittedPopulation<0||Incoming<0||Members<1)return Out;
        const double Population=double(std::max(ReportedPopulation,CommittedPopulation))+Incoming+Members;
        // Current light/rain is not guaranteed to persist. Discount extrapolated
        // recovery, including the known alternating day/night growth window.
        Out.FoodPerHead=(Food+Recovery30*(Horizon/30)*.5)/Population;
        Out.RequiredPerHead=FoodPerSecond*Horizon*1.1;
        Out.bAdmissible=Out.FoodPerHead>=Out.RequiredPerHead;return Out;
    }
    struct FResidence
    {
        std::int32_t Cover=-1;
        std::int32_t RequestedCover=-1;
        std::int64_t Registration=0;
        double X=0,Y=0,OriginX=0,OriginY=0,SettledSince=-1,NextSearch=0,LastProgress=0,LastDistance=1.e9;
        std::uint8_t Phase=0; // 0 none, 1 entering, 2 vigilant, 3 resting, 4 escaping, 5 no place
        std::uint64_t EdgeRestSteps=0,InteriorRestSteps=0,SearchFailures=0;
    };
    // Native units in this helper. Body must fit completely inside the cover.
    inline FSite Interior(std::uint32_t Seed,double X,double Y,double Radius,double Body,int CandidateIndex)
    {
        const double Angle=(Random(Seed,std::uint32_t(CandidateIndex)*17u)+CandidateIndex*.61803398875)*6.283185307179586;
        const double R=std::max(0.,Radius-Body*2)*(.20+.48*Random(Seed,std::uint32_t(CandidateIndex)*17u+1));
        return {X+std::cos(Angle)*R,Y+std::sin(Angle)*R,0,1};
    }
    inline bool CanRest(double Distance,double Depth,double Body,bool ThreatVisible,double ThreatAge,double Dwell,double Required)
    { return Distance<=std::max(.25,Body)&&Depth>=Body*2&&!ThreatVisible&&ThreatAge>=8&&Dwell>=Required; }
}
