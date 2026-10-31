#pragma once

#include "EcoObservationV3.h"
#include <algorithm>
#include <cmath>
#include <vector>

// Optional Unreal refuge rule. The training/golden world keeps this disabled.
// All positions remain native world units; this code never writes an Actor or a Mass transform.
namespace EcoRefugeV3
{
    using EcoRepertoireV3::FVec2;
    using EcoObservationV3::FCoverInput;
    inline constexpr double Epsilon = 1.e-4;

    inline bool Contains(const std::vector<FCoverInput>& Covers, const FVec2& P, double Margin=0)
    {
        for (const auto& C : Covers)
            if (C.Radius>0 && std::hypot(P.X-C.X,P.Y-C.Y)<=C.Radius+Margin) return true;
        return false;
    }

    struct FHit { int Index=-1; double Time=1; };
    inline FHit FirstHit(const std::vector<FCoverInput>& Covers,const FVec2& From,const FVec2& To,double Margin)
    {
        FHit Hit;
        const double X=To.X-From.X,Y=To.Y-From.Y,A=X*X+Y*Y;
        if(A<Epsilon*Epsilon)return Hit;
        for(int I=0;I<int(Covers.size());++I) {
            const auto& C=Covers[I];if(C.Radius<=0)continue;
            const double R=C.Radius+Margin,OX=From.X-C.X,OY=From.Y-C.Y;
            const double B=OX*X+OY*Y, D=B*B-A*(OX*OX+OY*OY-R*R);
            if(D<=0)continue; // A tangent segment stays outside.
            const double T=(-B-std::sqrt(D))/A;
            if(T>=-Epsilon&&T<=Hit.Time&&T<=1) {Hit.Index=I;Hit.Time=std::max(0.,T);}
        }
        return Hit;
    }

    struct FMoveResult { FVec2 Position; bool bConstrained=false; bool bRecovered=false; };
    inline FMoveResult Constrain(const std::vector<FCoverInput>& Covers,double WorldSize,
        const FVec2& From,const FVec2& Desired,double Margin)
    {
        FMoveResult R{Desired};
        auto InWorld=[&](const FVec2& P){return P.X>=0&&P.Y>=0&&P.X<=WorldSize&&P.Y<=WorldSize;};
        // A late-loaded refuge can contain a spawned predator. Recover to the nearest sampled
        // exterior of the union, rather than trapping it inside or granting a chance to kill first.
        if(Contains(Covers,From,Margin)) {
            double Best=1.e100;R.Position=From;R.bConstrained=R.bRecovered=true;
            for(const auto& C:Covers) {
                if(C.Radius<=0)continue;
                const double Base=std::atan2(From.Y-C.Y,From.X-C.X);
                for(int J=0;J<64;++J) {
                    const double Angle=Base+J*6.283185307179586/64.;
                    const double Radius=C.Radius+Margin+Epsilon;
                    const FVec2 P{C.X+std::cos(Angle)*Radius,C.Y+std::sin(Angle)*Radius};
                    const double Distance=std::hypot(P.X-From.X,P.Y-From.Y);
                    if(InWorld(P)&&!Contains(Covers,P,Margin)&&Distance<Best){R.Position=P;Best=Distance;}
                }
            }
            return R;
        }
        FVec2 Candidate=Desired;
        for(int Attempt=0;Attempt<8;++Attempt) {
            const auto Hit=FirstHit(Covers,From,Candidate,Margin);
            if(Hit.Index<0){R.Position=Candidate;return R;}
            R.bConstrained=true;
            const auto& C=Covers[Hit.Index];
            const double DX=Candidate.X-From.X,DY=Candidate.Y-From.Y;
            const FVec2 Contact{From.X+DX*Hit.Time,From.Y+DY*Hit.Time};
            const double Length=std::hypot(Contact.X-C.X,Contact.Y-C.Y);
            const FVec2 N{(Contact.X-C.X)/Length,(Contact.Y-C.Y)/Length};
            const double Side=N.X*DY-N.Y*DX>=0?1.:-1.;
            const double Remaining=std::hypot(DX,DY)*(1.-Hit.Time);
            // Tangential displacement lies in the exterior half-plane. Even the interpolated
            // straight segment cannot cut through this refuge, unlike a chord along its circle.
            Candidate={Contact.X-N.Y*Side*Remaining+N.X*Epsilon,
                       Contact.Y+N.X*Side*Remaining+N.Y*Epsilon};
            Candidate.X=std::clamp(Candidate.X,0.,WorldSize);
            Candidate.Y=std::clamp(Candidate.Y,0.,WorldSize);
        }
        R.Position=From; // Overlapping refuges / world edge: fail closed, no tunnelling.
        return R;
    }
}
