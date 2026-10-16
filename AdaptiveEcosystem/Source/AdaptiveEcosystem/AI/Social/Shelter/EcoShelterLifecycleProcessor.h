#pragma once

#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "EcoShelterLifecycleProcessor.generated.h"

/** Consumes movement feedback, maintains leases and publishes Social intent; never integrates movement. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoShelterLifecycleProcessor : public UMassProcessor
{
	GENERATED_BODY()
public:
	UEcoShelterLifecycleProcessor();
protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;
private:
	FMassEntityQuery EntityQuery;
	TSet<int64> ConfirmedReservations;
	// Per-processor/world diagnostics; never store debug state in shared agent config.
	double NextDiagnosticsSummaryTime = 0.0;
	int32 DiagnosticsFeedbackAccepted = 0;
	int32 DiagnosticsArrivalRejected = 0;
};
