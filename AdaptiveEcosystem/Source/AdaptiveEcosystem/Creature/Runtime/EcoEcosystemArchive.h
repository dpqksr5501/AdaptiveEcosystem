#pragma once
// Native checkpoint codec. POD blobs are restricted to the exact runtime module
// hash; names and variable arrays have explicit lengths. Never serializes pointers.
#include "CoreMinimal.h"
#include "AI/Policy/EcoWorldV3.h"
#include <type_traits>

namespace EcoCheckpoint
{
    /** Saved policy cover indices retain their order; only live shelter bindings are rebuilt. */
    inline bool MapCoverGeometry(const std::vector<EcoObservationV3::FCoverInput>& Saved,const std::vector<EcoObservationV3::FCoverInput>& Live,TArray<int32>& Out)
    {
        if(Saved.size()>1024||Live.size()>1024)return false;
        Out.Init(INDEX_NONE,int32(Saved.size()));TArray<bool> Used;Used.Init(false,int32(Live.size()));
        auto Valid=[](const auto& C){return std::isfinite(C.X)&&std::isfinite(C.Y)&&std::isfinite(C.Radius)&&C.Radius>=0;};
        for(const auto& C:Live)if(!Valid(C))return false;
        for(int32 I=0;I<int32(Saved.size());++I){const auto& S=Saved[I];if(!Valid(S))return false;if(S.Radius==0)continue;
            for(int32 K=0;K<int32(Live.size());++K){const auto& C=Live[K];
                if(!Used[K]&&C.Radius>0&&FMath::Abs(S.X-C.X)<.005&&FMath::Abs(S.Y-C.Y)<.005&&FMath::Abs(S.Radius-C.Radius)<.005){Out[I]=K;Used[K]=true;break;}
            }
            if(Out[I]==INDEX_NONE)return false;
        }
        for(int32 K=0;K<int32(Live.size());++K)if(Live[K].Radius>0&&!Used[K])return false;
        return true;
    }
    template<class T> void Pod(FArchive& A,T& Value)
    { static_assert(std::is_trivially_copyable_v<T>,"Checkpoint POD must have no ownership/pointers");if(!A.IsError())A.Serialize(&Value,sizeof(T)); }
    template<class T> void Vector(FArchive& A,std::vector<T>& Values,int32 Limit=65536)
    {
        static_assert(std::is_trivially_copyable_v<T>);
        int32 Count=int32(Values.size());A<<Count;
        if(A.IsError()||Count<0||Count>Limit||(A.IsLoading()&&int64(Count)*int64(sizeof(T))>A.TotalSize()-A.Tell())){A.SetError();return;}
        if(A.IsLoading())Values.resize(Count);
        if(Count&&!A.IsError())A.Serialize(Values.data(),int64(Count)*sizeof(T));
    }
    template<class T> void Properties(FArchive& A,T& Value)
    { if(!A.IsError())T::StaticStruct()->SerializeItem(A,&Value,nullptr); }
    inline void Config(FArchive& A,EcoWorldV3::FWorldConfig& C)
    {
#define P(X) Pod(A,C.X)
        P(bEcosystemLife);P(Vegetation);P(WorldSize);P(Seed);P(NumHerbivores);P(NumStalkers);P(NumChasers);P(NumRanged);P(NumNocturnal);
        P(bPlayerProxy);P(bShelterSafe);P(ShelterWolfMargin);P(PredSpeedMult);P(DayPeriod);P(DayOffset);P(TwilightSteps);
        Vector(A,C.Covers,1024);P(bProtectedRefuges);P(PredatorRefugeMargin);P(FoodCell);P(FoodPatchBlur);P(FoodPatchThreshold);
        P(FoodGradBlur);P(FoodRegenBase);P(FoodRegenMult);P(FoodCoverRegenMult);P(RngStream);P(bRespawnDead);P(PredEmaDenominator);
        P(bRealismNight);P(PredEatCdOverride);P(bEatInPlace);P(WorldAllowed);P(WildFlight);P(WildReserve);P(WildSatiation);
        P(RealismVision);P(RealismHearing);P(ShelterFood);P(PackHunt);
        P(Obstacles.bEnabled);P(Obstacles.BodyR);P(Obstacles.bBlockSight);P(Obstacles.bNoFood);Vector(A,C.Obstacles.Discs,12288);
        P(Obstacles.Detour);P(Obstacles.Foliage.bEnabled);P(Obstacles.Foliage.R);P(Obstacles.Foliage.Block);Vector(A,C.Obstacles.Foliage.Trees,4096);
        P(Weather.bEnabled);P(Weather.Kind);P(Weather.Intensity);P(Weather.RainSight);P(Weather.RainHear);P(Weather.SnowSight);P(Weather.SnowHear);
        P(Weather.SnowDeerSpeed);P(Weather.SnowWolfSpeed);P(Weather.bObsVisibility);Vector(A,C.Weather.Schedule,4096);P(bSenseStats);P(bFlightStats);
#undef P
    }
    inline void Grid(FArchive& A,EcoWorldV3::FFoodGrid& G)
    {
#define P(X) Pod(A,G.X)
#define V(X) Vector(A,G.X)
        P(Vegetation);P(VegetationWeather);V(VegetationCells);V(Habitats);P(EnvironmentLost);P(VegetationGrown);
        P(Gw);P(Cell);P(GradBlur);V(Cap);V(Food);V(Regen);V(CoverCell);V(CoverFoodCell);V(Cap0);
        V(Blur);V(GradX);V(GradY);V(Sat);V(Tmp);V(Tmp2);V(Demand);
#undef V
#undef P
    }
    inline void World(FArchive& A,EcoWorldV3::FWorldState& W)
    {
        Config(A,W.Config);Grid(A,W.Food);
#define P(X) Pod(A,W.X)
        P(RepCfg);P(ObsCfg);P(ThreatCfg);P(Allowed);P(Rng.State);P(T);P(HuntWindow);P(HuntWindowCaptures);P(Dark);P(StepsToTransition);P(PredEma);
        P(WeatherKind);P(WeatherIntensity);P(Weather);P(ReserveCap);P(ObsDim);P(bObstacleObsProbe);P(ObstacleObsCfg);P(Stats);
#undef P
        // External observations and Step scratch contain live-frame data/pointers.
        // They are reconstructed before consumption, never deserialized as handles.
        if(A.IsLoading()){W.Rng.External=nullptr;W.Rng.ExternalUser=nullptr;}
    }
    inline bool ValidGrid(const EcoWorldV3::FFoodGrid& G)
    {
        const size_t N=G.Food.size();
        if(G.Gw<1||G.Gw>256||N!=size_t(G.Gw)*G.Gw||!std::isfinite(G.Cell)||G.Cell<=0||G.Cap.size()!=N||G.Regen.size()!=N
            ||G.CoverCell.size()!=N||G.Blur.size()!=N||G.GradX.size()!=N||G.GradY.size()!=N
            ||(!G.Demand.empty()&&G.Demand.size()!=N)||!G.HasValidVegetationLayout())return false;
        for(size_t I=0;I<N;++I){
            if(!std::isfinite(G.Food[I])||!std::isfinite(G.Cap[I])||!std::isfinite(G.Regen[I])||G.Cap[I]<0||G.Food[I]<0||G.Food[I]>G.Cap[I]+1e-9||G.Regen[I]<0)return false;
            if(G.Vegetation.bEnabled&&(!G.Habitats[I].IsValid()||!std::isfinite(G.VegetationCells[I].Moisture)||G.VegetationCells[I].Moisture<0
                ||G.VegetationCells[I].Moisture>1||!std::isfinite(G.VegetationCells[I].Stress)||G.VegetationCells[I].Stress<0||G.VegetationCells[I].Stress>1))return false;
        }
        return true;
    }
}
