#pragma once
#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "EcoCreaturePredatorProcessor.generated.h"

/** The only position writer for integrated wolves; existing demo wolves are excluded. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoCreaturePredatorProcessor : public UMassProcessor
{
    GENERATED_BODY()
public:
    UEcoCreaturePredatorProcessor();
protected:
    virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
    virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;
private:
    FMassEntityQuery Query;
};
