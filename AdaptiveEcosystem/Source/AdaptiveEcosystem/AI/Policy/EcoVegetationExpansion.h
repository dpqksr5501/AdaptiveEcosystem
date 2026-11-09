#pragma once
#include "EcoWorldV3.h"
#include <array>

namespace EcoVegetationExpansion
{
    struct FSite { int32_t Cell=0;double BaseCapacity=0,Capacity=0; };
    // A habitat proposal only. The caller first commits capacity to M4, then
    // applies it. No biomass is added and no neighbor added this cycle can seed
    // another cell in the same cycle. Existing shelter/obstacle rules remain.
    inline std::vector<FSite> Plan(const EcoWorldV3::FFoodGrid& G,const EcoWorldV3::FWorldConfig& C,
        const std::vector<std::uint8_t>& Ground,std::int64_t Step)
    {
        std::vector<FSite> Out;
        if(!C.bEcosystemLife||!G.Vegetation.bEnabled||!G.HasValidVegetationLayout()||Ground.size()!=G.Food.size()
            ||(!G.Cap0.empty()&&G.Cap0.size()!=G.Food.size())
            ||G.VegetationWeather.Light<.2||G.VegetationWeather.Temperature<0)return Out;
        const auto& Base=G.Cap0.empty()?G.Cap:G.Cap0;
        const auto Count=int32_t(Base.size());if(!Count)return Out;
        const int32_t Start=int32_t((Step/225*67)%Count);
        for(int32_t N=0;N<Count&&Out.size()<64;++N){
            const int32_t K=(Start+N)%Count,X=K%G.Gw,Y=K/G.Gw;
            if(Base[K]>0||!Ground[K]||!G.Habitats[K].bGroundUsable||G.Regen[K]<=0||G.VegetationCells[K].Stress>.15)continue;
            const auto& H=G.Habitats[K];const double Moisture=G.VegetationCells[K].Moisture;
            const double Lo=H.bNatural?H.MoistureMin:H.Plant==EcoVegetationV3::EPlant::Riparian?.45:H.Plant==EcoVegetationV3::EPlant::Shrub?.18:.30;
            const double Hi=H.bNatural?H.MoistureMax:H.Plant==EcoVegetationV3::EPlant::Riparian?.95:H.Plant==EcoVegetationV3::EPlant::Shrub?.65:.75;
            if(Moisture<Lo||Moisture>Hi)continue;
            if(H.bNatural&&(H.SiteSuitability<.35||EcoNaturalHabitat::Triangle(G.VegetationWeather.Temperature,H.TemperatureMin,H.TemperatureOptimum,H.TemperatureMax)<=0))continue;
            if(C.Obstacles.bNoFood&&C.Obstacles.Active()&&EcoThreatV3::InsideAnyObstacle((X+.5)*G.Cell,(Y+.5)*G.Cell,
                C.Obstacles.Discs.data(),C.Obstacles.Num(),G.Cell*.7071067811865476))continue;
            double Seed=0;
            constexpr int32_t Offsets[4][2]={{-1,0},{1,0},{0,-1},{0,1}};
            for(const auto& D:Offsets){
                const int32_t A=X+D[0],B=Y+D[1];if(A<0||B<0||A>=G.Gw||B>=G.Gw)continue;
                const int32_t I=B*G.Gw+A;
                if(G.Food[I]>=.03&&G.Cap[I]>0&&G.Food[I]/G.Cap[I]>=.25)Seed=std::max(Seed,Base[I]);
            }
            const double Potential=std::min(.5,Seed*.5);if(Potential<.03)continue;
            const bool Cover=C.ShelterFood.bEnabled&&(G.CoverCell[K]||G.CellTouchesCover(X,Y,C.Covers));
            const double Capacity=Potential*(Cover?C.ShelterFood.CapFrac:1.);
            if(Capacity>0)Out.push_back({K,Potential,Capacity});
        }
        return Out;
    }
}
