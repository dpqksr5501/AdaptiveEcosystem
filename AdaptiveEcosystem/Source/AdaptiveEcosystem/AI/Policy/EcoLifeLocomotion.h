#pragma once
// Life-world intent helpers. No position/energy integration and no policy writes.
#include "EcoRepertoire.h"
#include <algorithm>
#include <cstdint>

namespace EcoLifeMotion
{
    using EcoRepertoireV3::FVec2;
    inline FVec2 PassingAvoidance(FVec2 Repulsion,FVec2 Forward)
    {
        const double Dot=Repulsion.X*Forward.X+Repulsion.Y*Forward.Y;
        if(Dot<0){
            Repulsion=EcoRepertoireV3::Sub(Repulsion,EcoRepertoireV3::Scale(Forward,Dot));
            // Every moving body passes on its own left. Head-on bodies then
            // choose opposite world-space sides, instead of both stopping.
            Repulsion=EcoRepertoireV3::Add(Repulsion,EcoRepertoireV3::Scale({-Forward.Y,Forward.X},-Dot));
        }
        return Repulsion;
    }
    inline bool AllowsMotion(FVec2 From,FVec2 To,FVec2 Other,double Clearance)
    {
        const auto Delta=EcoRepertoireV3::Sub(To,From),Away=EcoRepertoireV3::Sub(From,Other);
        const double Initial=EcoRepertoireV3::SizeSquared(Away),Limit=Clearance*Clearance;
        if(Initial<Limit-1.e-9)
            return Delta.X*Away.X+Delta.Y*Away.Y>=-1.e-9
                &&EcoRepertoireV3::SizeSquared(EcoRepertoireV3::Sub(To,Other))>Initial+1.e-9;
        const double Length=EcoRepertoireV3::SizeSquared(Delta);
        const double T=Length>1.e-12?std::clamp(-(Away.X*Delta.X+Away.Y*Delta.Y)/Length,0.,1.):0.;
        return EcoRepertoireV3::SizeSquared(EcoRepertoireV3::Add(Away,EcoRepertoireV3::Scale(Delta,T)))>=Limit-1.e-9;
    }

    // Physical contact also applies to grazing/stationary animals. Exact
    // coincidence needs a stable antisymmetric direction, not normalize(0).
    inline FVec2 Separation(FVec2 P,FVec2 Q,double Clearance,std::uint64_t Id,std::uint64_t Other)
    {
        const double X=P.X-Q.X,Y=P.Y-Q.Y,D=std::hypot(X,Y);
        if(D>=Clearance||Clearance<=0||Id==Other)return {};
        if(D<1.e-6){
            const auto Pair=std::min(Id,Other)*0x9e3779b97f4a7c15ULL+std::max(Id,Other);
            const double Angle=double(Pair%1024)*6.283185307179586/1024;
            const double Sign=Id<Other?-1.:1.;return {Sign*std::cos(Angle),Sign*std::sin(Angle)};
        }
        const double Weight=(Clearance-D)/Clearance;
        return {X/D*Weight,Y/D*Weight};
    }

    // Change only the outward part of an intended velocity. Keep tangential
    // escape, and point inward at a corner rather than repeatedly clipping it.
    inline FVec2 BoundaryVelocity(FVec2 P,FVec2 V,double Size,double Margin)
    {
        if(P.X>=Margin&&P.X<=Size-Margin&&P.Y>=Margin&&P.Y<=Size-Margin)return V;
        const double Speed=std::hypot(V.X,V.Y);
        if(Speed<1.e-9||Size<=2*Margin)return V;
        const double Push=Speed*.6;
        if(P.X<Margin&&V.X<Push)V.X=std::max(V.X,Push*(1-P.X/Margin));
        if(P.X>Size-Margin&&V.X>-Push)V.X=std::min(V.X,-Push*(1-(Size-P.X)/Margin));
        if(P.Y<Margin&&V.Y<Push)V.Y=std::max(V.Y,Push*(1-P.Y/Margin));
        if(P.Y>Size-Margin&&V.Y>-Push)V.Y=std::min(V.Y,-Push*(1-(Size-P.Y)/Margin));
        const double N=std::hypot(V.X,V.Y);
        return N>1.e-9?FVec2{V.X/N*Speed,V.Y/N*Speed}:V;
    }
}
