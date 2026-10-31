#pragma once
#include "CoreMinimal.h"
struct FMassEntityTemplateBuildContext;
class UEcoSpeciesAIProfile;
namespace EcoSpeciesAI { void BuildEngineTemplate(FMassEntityTemplateBuildContext& Context,const UWorld& World,UEcoSpeciesAIProfile& Profile); }
