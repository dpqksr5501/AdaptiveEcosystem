#pragma once
// Engine-free individual state. No model inputs, transport, UObject or movement ownership.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include "EcoMovementTracesV3.h"

namespace EcoLifeV3
{
    enum class EOrigin : std::uint8_t { Initial, NaturalBirth, Recovery, Fixture };
    enum class EEncounter : std::uint8_t { Harmless, Noise, Pursuit, Surprise, WitnessLoss, UnknownDamage, FastApproach };
    enum class EResponse : std::uint8_t { Policy, Curious, Vigilant, Retreat };
    inline std::uint64_t Mix(std::uint64_t V) { V+=0x9e3779b97f4a7c15ULL;V=(V^(V>>30))*0xbf58476d1ce4e5b9ULL;V=(V^(V>>27))*0x94d049bb133111ebULL;return V^(V>>31); }
    inline double Unit(std::uint64_t V) { return double(Mix(V)>>11)*(1.0/9007199254740992.0); }
    struct FGenome
    {
        // Bounded correlated tradeoff: faster/larger bodies require more food.
        double Speed=1, Size=1;
        bool IsValid() const { return std::isfinite(Speed)&&Speed>=.9&&Speed<=1.1&&std::isfinite(Size)&&Size>=.9&&Size<=1.1; }
    };
    inline FGenome Founder(std::uint64_t Seed,std::uint64_t Id)
    { return {.95+.1*Unit(Seed^Id),.95+.1*Unit(Seed+Id+17)}; }
    inline FGenome Inherit(const FGenome& A,const FGenome& B,std::uint64_t Seed)
    { return {std::clamp((A.Speed+B.Speed)*.5+(Unit(Seed)-.5)*.04,.9,1.1),
        std::clamp((A.Size+B.Size)*.5+(Unit(Seed+31)-.5)*.04,.9,1.1)}; }
    /** Recognized local harm only. Aggregate has no target location or rebroadcast path. */
    struct FRegionalDanger
    {
        double Human=0,Updated=0,NextExposure=0;
        std::array<std::uint64_t,32> Episodes{};
        std::uint32_t Cursor=0;
        double At(double Now) const
        { return std::isfinite(Now)&&Now>=Updated?Human*std::exp(-(Now-Updated)/300):0; }
        bool Record(std::uint64_t Episode,double Now)
        {
            if(!Episode||!std::isfinite(Now)||Now<Updated||Now<NextExposure
                ||std::find(Episodes.begin(),Episodes.end(),Episode)!=Episodes.end())return false;
            Human=std::min(1.,At(Now)+.12);Updated=Now;NextExposure=Now+5;Episodes[Cursor++%Episodes.size()]=Episode;return true;
        }
    };
    struct FMemory
    {
        double Familiarity=0,Curiosity=0,Fear=0,Hostility=0;
        double LastUpdate=0,NextExposure=0,LastDirect=-1,LastThreat=-1;
        double NextScan=0;
        double UnknownFear=0,LastDamage=-1;
        bool bLastDamageKnown=false;
        double PursuitExposure=0;
        double LastX=0,LastY=0; // observed position only, native units
        EEncounter LastKind=EEncounter::Harmless;
        EResponse Response=EResponse::Policy;
        std::array<std::uint64_t,16> Episodes{};
        std::uint32_t Cursor=0;
        void Age(double Now)
        {
            if(!std::isfinite(Now)||Now<LastUpdate)return;
            const double Dt=Now-LastUpdate;LastUpdate=Now;
            Familiarity*=std::exp(-Dt/600);Curiosity*=std::exp(-Dt/90);
            Fear*=std::exp(-Dt/180);Hostility*=std::exp(-Dt/300);
            UnknownFear*=std::exp(-Dt/120);
        }
        bool Observe(EEncounter Kind,std::uint64_t Episode,double EvidenceTime,double Now,double X,double Y,double Confidence=1)
        {
            if(!Episode||!std::isfinite(Now)||Now<LastUpdate||!std::isfinite(EvidenceTime)||Now<EvidenceTime||Now-EvidenceTime>15
                ||!std::isfinite(X)||!std::isfinite(Y)||!std::isfinite(Confidence)||Confidence<=0||Confidence>1
                ||std::find(Episodes.begin(),Episodes.end(),Episode)!=Episodes.end())return false;
            Age(Now);
            // Shared/repeated reports cannot bypass per-individual exposure limits.
            if(Now<NextExposure)return false;
            Episodes[Cursor++%Episodes.size()]=Episode;NextExposure=Now+5;
            LastDirect=EvidenceTime;LastX=X;LastY=Y;LastKind=Kind;
            if(Kind==EEncounter::Harmless){Familiarity=std::min(1.,Familiarity+.06*Confidence);
                Curiosity=std::min(1.,Curiosity+.12*Confidence*(1-Fear));}
            else {const double Weight=(Kind==EEncounter::Noise||Kind==EEncounter::FastApproach)?.04:Kind==EEncounter::Surprise?.3:.18;
                Fear=std::min(1.,Fear+Weight*Confidence);Curiosity*=.5;LastThreat=EvidenceTime;
                if(Kind!=EEncounter::Noise&&Kind!=EEncounter::FastApproach)Hostility=std::min(1.,Hostility+.08*Confidence);}
            return true;
        }
        EResponse Decide(double Now,double Distance,bool Safe,bool Traveling)
        {
            Age(Now);Response=EResponse::Policy;
            if(!Safe||Traveling)return Response;
            if(!bLastDamageKnown&&LastDamage>=0&&Now-LastDamage<8&&UnknownFear>.15){Response=EResponse::Vigilant;return Response;}
            if(LastDirect<0||Now-LastDirect>8)return Response;
            if(Fear>.35||(LastDamage>=0&&Now-LastDamage<8&&Fear>.15))Response=EResponse::Retreat;
            else if(Fear>.15||LastKind!=EEncounter::Harmless)Response=EResponse::Vigilant;
            else if(Familiarity>.12&&Curiosity>.2&&Distance>6&&Distance<18)Response=EResponse::Curious;
            return Response;
        }
        bool Suffer(std::uint64_t Episode,double Now,bool Known,double X,double Y,bool Pursuit)
        {
            if(!Episode||!std::isfinite(Now)||Now<LastUpdate||std::find(Episodes.begin(),Episodes.end(),Episode)!=Episodes.end())return false;
            Age(Now);LastDamage=Now;bLastDamageKnown=Known;
            if(!Known){Episodes[Cursor++%Episodes.size()]=Episode;UnknownFear=std::min(1.,UnknownFear+.3);LastKind=EEncounter::UnknownDamage;return true;}
            NextExposure=Now;
            return Observe(Pursuit?EEncounter::Pursuit:EEncounter::Surprise,Episode,Now,Now,X,Y);
        }
        bool ReceiveReport(std::uint64_t Episode,double Evidence,double Now,double Confidence)
        {
            if(!Episode||!std::isfinite(Now)||Now<LastUpdate||!std::isfinite(Evidence)||Now<Evidence||Now-Evidence>15||Now<NextExposure
                ||!std::isfinite(Confidence)||Confidence<=0||Confidence>1||std::find(Episodes.begin(),Episodes.end(),Episode)!=Episodes.end())return false;
            Age(Now);Episodes[Cursor++%Episodes.size()]=Episode;NextExposure=Now+5;
            Fear=std::min(1.,Fear+.12*Confidence);return true; // no direct position/time, no rebroadcast
        }
    };
    struct FIndividual
    {
        FGenome Genome;
        FMemory Memory;
        EcoTracesV3::FInvestigation Investigation;
        double NextTrace=0;
        // Predator-only nutrition. Plant-feeding bodies continue owning their native Energy/Reserve.
        double Nutrition=1,MealRemaining=0,MealExpires=0,MealX=0,MealY=0,MealZ=0;
        double MeatIssued=0,MeatConsumed=0,MeatWasted=0,BaseSpeed=0,BaseCatchRadius=0;
        double LastMeatIntake=0;
        bool bFeedingMeat=false;
        std::int64_t MealSource=0,LastHuntTarget=0;
        double LastHuntTime=-1;
        std::int64_t ParentA=0,ParentB=0;
        std::uint32_t Generation=0,Offspring=0;
        double Born=0,NextBirth=0;
        EOrigin Origin=EOrigin::Initial;
        bool bInitialized=false;
        double Growth(double Now) const { return std::clamp(.75+.25*std::max(0.,Now-Born)/180.,.75,1.); }
        double BodyScale(double Now) const { return Genome.Size*Growth(Now); }
        double SpeedScale(double Now) const { return Genome.Speed*(.8+.2*Growth(Now)); }
        double Maintenance() const { return Genome.Size*Genome.Size*Genome.Size*(1+std::max(0.,Genome.Speed-1)*2); }
        bool CanParent(double Now,double Energy,bool Resident) const
        { return bInitialized&&Resident&&Now-Born>=180&&Now>=NextBirth&&Energy>=.7&&Genome.IsValid(); }
        bool AssignMeat(std::int64_t Prey,double Amount,double Now,double X,double Y,double Z)
        {
            if(Prey<=0||Prey==MealSource||!std::isfinite(Amount)||Amount<=0||Amount>.6||!std::isfinite(Now)
                ||!std::isfinite(X)||!std::isfinite(Y)||!std::isfinite(Z))return false;
            MeatWasted+=MealRemaining;MealRemaining=Amount;MeatIssued+=Amount;MealSource=Prey;MealExpires=Now+20;bFeedingMeat=false;
            MealX=X;MealY=Y;MealZ=Z;return true;
        }
        bool PredatorStep(double Now,double X,double Y,bool Running,double Dt)
        {
            if(!std::isfinite(Dt)||Dt<=0||Dt>.25)return Nutrition>0;
            LastMeatIntake=0;
            Nutrition=std::max(0.,Nutrition-.00225*Maintenance()*(Running?2:1)*Dt);
            if(MealRemaining>0&&Now>=MealExpires){MeatWasted+=MealRemaining;MealRemaining=0;bFeedingMeat=false;}
            if(Nutrition<.9)bFeedingMeat=true;
            if(bFeedingMeat&&MealRemaining>0&&(MealX-X)*(MealX-X)+(MealY-Y)*(MealY-Y)<=6.25){
                const double Bite=std::min({MealRemaining,.12*Dt,1-Nutrition});
                MealRemaining-=Bite;MeatConsumed+=Bite;Nutrition+=Bite;LastMeatIntake=Bite;
                if(Nutrition>=.98||MealRemaining<=0)bFeedingMeat=false;
            }
            return Nutrition>0;
        }
        void AbandonMeat(){MeatWasted+=MealRemaining;MealRemaining=0;bFeedingMeat=false;}
    };
}
