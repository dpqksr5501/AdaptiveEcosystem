#include "World/EcoNaturalHabitatProfile.h"
#include "Misc/Crc.h"
#include "AI/Policy/EcoLifeHistoryV3.h"

bool FEcoPlantGuild::IsValid() const
{
    return FMath::IsFinite(MoistureMin)&&FMath::IsFinite(MoistureMax)&&MoistureMin>0&&MoistureMax<1&&MoistureMin<MoistureMax
        &&FMath::IsFinite(TemperatureMin)&&FMath::IsFinite(TemperatureOptimum)&&FMath::IsFinite(TemperatureMax)
        &&TemperatureMin>=-100&&TemperatureMax<=100&&TemperatureMin<TemperatureOptimum&&TemperatureOptimum<TemperatureMax
        &&FMath::IsFinite(ShadeTolerance)&&ShadeTolerance>=0&&ShadeTolerance<=1
        &&FMath::IsFinite(MaturationSeconds)&&MaturationSeconds>=10&&MaturationSeconds<=7200
        &&FMath::IsFinite(MaxSlopeDegrees)&&MaxSlopeDegrees>0&&MaxSlopeDegrees<=60
        &&FMath::IsFinite(WidthCm)&&WidthCm>=10&&WidthCm<=200&&FMath::IsFinite(HeightCm)&&HeightCm>=5&&HeightCm<=150
        &&FMath::IsFinite(Coverage)&&Coverage>=.1f&&Coverage<=1;
}
void FEcoPlantGuild::Apply(EcoVegetationV3::FHabitat& H) const
{
    H.bNatural=true;H.MaturationSeconds=MaturationSeconds;H.MoistureMin=MoistureMin;H.MoistureMax=MoistureMax;
    H.TemperatureMin=TemperatureMin;H.TemperatureOptimum=TemperatureOptimum;H.TemperatureMax=TemperatureMax;H.ShadeTolerance=ShadeTolerance;
}
UEcoNaturalHabitatProfile::UEcoNaturalHabitatProfile()
{
    Guilds.SetNum(3);
    Guilds[1].MaturationSeconds=120;Guilds[2].MaturationSeconds=300;
    Guilds[1].MoistureMin=.45f;Guilds[1].MoistureMax=.95f;Guilds[1].HeightCm=65;Guilds[1].WidthCm=90;Guilds[1].MaxSlopeDegrees=25;
    Guilds[2].MoistureMin=.18f;Guilds[2].MoistureMax=.65f;Guilds[2].ShadeTolerance=.8f;Guilds[2].HeightCm=85;Guilds[2].WidthCm=125;
}
bool UEcoNaturalHabitatProfile::IsValidProfile() const
{
    if(!EcoLifeV3::FPopulationProfile{MaturitySeconds,InitialJuvenileFraction,FemaleFraction,MaxFounderAgeSeconds}.IsValid())return false;
    if(!FMath::IsFinite(FounderBodyVariation)||FounderBodyVariation<0||FounderBodyVariation>.100001)return false;
    if(ProfileId.IsNone()||Guilds.Num()!=3||!FMath::IsFinite(ClusterScaleCm)||ClusterScaleCm<500||ClusterScaleCm>10000
        ||!FMath::IsFinite(ProbeAboveCm)||ProbeAboveCm<100||ProbeAboveCm>5000
        ||!FMath::IsFinite(ProbeBelowCm)||ProbeBelowCm<100||ProbeBelowCm>10000
        ||!FMath::IsFinite(GroundTintStrength)||GroundTintStrength<0||GroundTintStrength>1
        ||!FMath::IsFinite(MoonSunFraction)||MoonSunFraction<0||MoonSunFraction>.1
        ||!FMath::IsFinite(NightExposureBias)||NightExposureBias< -4||NightExposureBias>0
        ||!EcoNaturalHabitat::FGroundTraversal{WalkableSlopeDegrees,MaxStepUpCm,MaxStepDownCm,MaxWadingDepthCm}.IsValid())return false;
    for(const auto& Guild:Guilds)if(!Guild.IsValid())return false;
    return true;
}
uint32 UEcoNaturalHabitatProfile::Fingerprint() const
{
    uint32 Crc=FCrc::StrCrc32(*ProfileId.ToString());
    auto Add=[&](const auto& V){Crc=FCrc::MemCrc32(&V,sizeof(V),Crc);};
    Add(LayoutSeed);Add(ClusterScaleCm);Add(ProbeAboveCm);Add(ProbeBelowCm);Add(bRequireGroundTag);Add(bWildRefuges);
    Add(FounderBodyVariation);Add(MaturitySeconds);Add(InitialJuvenileFraction);Add(FemaleFraction);Add(MaxFounderAgeSeconds);
    Add(WalkableSlopeDegrees);Add(MaxStepUpCm);Add(MaxStepDownCm);Add(MaxWadingDepthCm);
    for(const auto& G:Guilds){
        Add(G.MaturationSeconds);Add(G.MoistureMin);Add(G.MoistureMax);Add(G.TemperatureMin);Add(G.TemperatureOptimum);Add(G.TemperatureMax);
        Add(G.ShadeTolerance);Add(G.MaxSlopeDegrees);Add(G.WidthCm);Add(G.HeightCm);Add(G.Coverage);
        Crc=FCrc::StrCrc32(*G.Mesh.ToSoftObjectPath().ToString(),Crc);
    }
    return Crc;
}
