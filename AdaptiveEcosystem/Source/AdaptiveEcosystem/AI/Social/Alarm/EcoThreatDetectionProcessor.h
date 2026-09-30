#pragma once

#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "AI/Social/Alarm/EcoThreatTypes.h"
#include "EcoThreatDetectionProcessor.generated.h"

/** Reads existing Mass predator grid and opt-in actor sources; writes only Social herd input. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoThreatDetectionProcessor : public UMassProcessor
{
	GENERATED_BODY()
public:
	UEcoThreatDetectionProcessor();
protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;
private:
	FMassEntityQuery EntityQuery;
	float TimeUntilScan = 0.0f;
	TArray<int32> CandidateIndices;
	TArray<FEcoActorThreatSnapshot> ActorThreats;
	TArray<FEcoObservedHerdThreat> BestThreats;
};
