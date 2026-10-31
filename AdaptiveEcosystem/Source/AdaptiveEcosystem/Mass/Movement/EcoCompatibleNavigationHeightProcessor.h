#pragma once
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "EcoCompatibleNavigationHeightProcessor.generated.h"
/** Engine height smoothing compatibility path; grounded SpeciesAI has its own sole writer. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoCompatibleNavigationHeightProcessor : public UMassProcessor
{
    GENERATED_BODY()
public: UEcoCompatibleNavigationHeightProcessor();
protected:
    virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EM) override;
    virtual void Execute(FMassEntityManager& EM,FMassExecutionContext& Context) override;
private: FMassEntityQuery Query;
};
