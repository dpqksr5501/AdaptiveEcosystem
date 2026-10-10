#pragma once

#include "Core/EcoMigrationTypes.h"
#include "Core/EcoResourceTypes.h"
#include "Core/EcoTimeTypes.h"
#include "Core/EcoSurvivalTypes.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "EcoMassMigration.generated.h"

namespace EcoMassMigration
{
	/** Sequential Mass pass after resource completion. Never changes resources or entity identity. */
	bool Reconcile(FMassEntityManager& Manager, const FEcoServerTimeSnapshot& Time, double ActualTime,
		int64 StepId, TConstArrayView<FEcoResourceSnapshot> Resources,
		TConstArrayView<FEcoRegionSpatialSnapshot> Spaces, const FEcoMigrationSettings& Settings,
		bool bDecisionDue, double FeedInterval, const FEcoOvercrowdingSettings* PressureSettings = nullptr,
		const FEcoSurvivalSettings* SurvivalSettings = nullptr,
		TConstArrayView<FEcoMigrationPressureSnapshot> Pressure = {}, double ConsumptionRate = 0.0,
		TArray<FEcoMigrationOutcome>* OutArrivals = nullptr);
}

/** Writes movement intent only. The engine UMassApplyMovementProcessor owns position integration. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoMigrationSteeringProcessor : public UMassProcessor
{
	GENERATED_BODY()
public:

	UEcoMigrationSteeringProcessor();
protected:

	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;
private:
	FMassEntityQuery EntityQuery;
};
