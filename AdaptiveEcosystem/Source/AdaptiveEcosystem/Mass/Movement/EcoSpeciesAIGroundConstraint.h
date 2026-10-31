#pragma once
#include "CoreMinimal.h"
class UEcoSpeciesAIProfile;
namespace EcoSpeciesAI { bool ConstrainGroundStep(UWorld& World,FName Region,bool Traveling,const FVector& Start,FVector& End,const UEcoSpeciesAIProfile& Profile); }
