#include "EcoVegetationV3.h"
#include <iostream>
#include <iomanip>
int main()
{
    double V[21];std::cout<<std::setprecision(17);
    while(std::cin>>V[0]){
        for(int I=1;I<21;++I)if(!(std::cin>>V[I]))return 2;
        EcoVegetationV3::FConfig C;C.bEnabled=V[0]!=0;C.Infiltration=V[1];C.Evaporation=V[2];C.Drainage=V[3];C.Uptake=V[4];C.StressLoss=V[5];
        EcoVegetationV3::FWeather W{V[6],V[7],V[8]};
        EcoVegetationV3::FHabitat H;H.Plant=static_cast<EcoVegetationV3::EPlant>(int(V[9]));H.Drainage=V[10];H.Shade=V[11];H.WaterSupply=V[12];H.Flood=V[13];H.bGroundUsable=V[14]!=0;
        EcoVegetationV3::FCell S{V[15],V[16]};
        const auto O=EcoVegetationV3::Advance(C,W,H,S,V[17],V[18],V[19],V[20]);
        std::cout<<O.Food<<' '<<O.Growth<<' '<<O.Loss<<' '<<S.Moisture<<' '<<S.Stress<<'\n';
    }
    return 0;
}
