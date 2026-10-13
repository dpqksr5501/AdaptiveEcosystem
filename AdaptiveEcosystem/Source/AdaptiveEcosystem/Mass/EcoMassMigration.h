#pragma once

#include "Core/EcoMigrationTypes.h"
#include "Core/EcoResourceTypes.h"
#include "Core/EcoTimeTypes.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "EcoMassMigration.generated.h"

namespace EcoMassMigration
{
	/** Sequential Mass pass after resource completion. Never changes resources or entity identity. */
	bool Reconcile(FMassEntityManager& Manager, const FEcoServerTimeSnapshot& Time, double ActualTime,
		int64 StepId, TConstArrayView<FEcoResourceSnapshot> Resources,
		TConstArrayView<FEcoRegionSpatialSnapshot> Spaces, const FEcoMigrationSettings& Settings,
		bool bDecisionDue, double FeedInterval, bool bResetResidentVelocity = true);
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
