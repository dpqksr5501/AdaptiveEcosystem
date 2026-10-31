#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

namespace EcoTracesV3
{
    struct FTrace { std::uint64_t Id=0;std::int64_t Source=0;double X=0,Y=0,Z=0,Time=0; };
    /** 256 events, 64 spatial buckets, <=16 returned nearby cues. No live target queries. */
    struct FField
    {
        std::array<FTrace,256> Events{};
        std::array<std::vector<int>,64> Buckets;
        std::uint64_t Serial=0;
        unsigned Cursor=0;
        static unsigned Hash(double X,double Y)
        { return (unsigned(int(std::floor(X/8)))*73856093u ^ unsigned(int(std::floor(Y/8)))*19349663u)%64; }
        void Rebuild()
        { for(auto& B:Buckets)B.clear();for(unsigned I=0;I<Events.size();++I)if(Events[I].Id)Buckets[Hash(Events[I].X,Events[I].Y)].push_back(I); }
        void Add(std::int64_t Source,double X,double Y,double Z,double Now)
        {
            if(Source<=0||!std::isfinite(X)||!std::isfinite(Y)||!std::isfinite(Z)||!std::isfinite(Now)||Now<0
                ||std::abs(X)>100000||std::abs(Y)>100000||Serial==UINT64_MAX)return;
            const unsigned Slot=Cursor++%Events.size();const auto Old=Events[Slot];
            if(Old.Id){auto& B=Buckets[Hash(Old.X,Old.Y)];B.erase(std::remove(B.begin(),B.end(),int(Slot)),B.end());}
            Events[Slot]={++Serial,Source,X,Y,Z,Now};Buckets[Hash(X,Y)].push_back(Slot);
        }
        template<class F> void Query(double X,double Y,double Now,F Visit) const
        {
            if(!std::isfinite(X)||!std::isfinite(Y)||!std::isfinite(Now)||std::abs(X)>100000||std::abs(Y)>100000)return;
            std::array<bool,64> Seen{};unsigned Count=0;
            for(int DY=-2;DY<=2;++DY)for(int DX=-2;DX<=2;++DX){
                const auto H=Hash(X+DX*8,Y+DY*8);if(Seen[H])continue;Seen[H]=true;
                for(int I:Buckets[H]){const auto& T=Events[I];
                    if(!T.Id||Now<T.Time||Now-T.Time>20||(T.X-X)*(T.X-X)+(T.Y-Y)*(T.Y-Y)>144)continue;
                    Visit(T);if(++Count>=16)return;
                }
            }
        }
    };
    enum class ERole:std::uint8_t { None, Lead, Intercept, Investigate };
    struct FInvestigation
    {
        std::uint64_t Trace=0,LastUsed=0;
        std::int64_t Target=0;
        double X=0,Y=0,Started=0,Until=0,NextQuery=0,Cooldown=0,LastProgress=0,BestDistance=1e30;
        ERole Role=ERole::None;
        void Cancel(double Now){Trace=0;Target=0;Role=ERole::None;Cooldown=Now+8;Until=0;}
    };
}
