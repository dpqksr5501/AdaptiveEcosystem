#pragma once
#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "MassCommonTypes.h"
#include "EcoSpeciesAIProcessors.generated.h"

UCLASS() class ADAPTIVEECOSYSTEM_API UEcoSpeciesAIInputProcessor : public UMassProcessor
{
    GENERATED_BODY()
public: UEcoSpeciesAIInputProcessor();
protected:
    virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EM) override;
    virtual void Execute(FMassEntityManager& EM,FMassExecutionContext& Context) override;
    FMassEntityQuery Query;
};
UCLASS() class ADAPTIVEECOSYSTEM_API UEcoSpeciesAIActivityProcessor : public UMassProcessor
{
    GENERATED_BODY()
public: UEcoSpeciesAIActivityProcessor();
protected:
    virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EM) override;
    virtual void Execute(FMassEntityManager& EM,FMassExecutionContext& Context) override;
    FMassEntityQuery Query;
};
UCLASS() class ADAPTIVEECOSYSTEM_API UEcoSpeciesAINavigationProcessor : public UMassProcessor
{
    GENERATED_BODY()
public: UEcoSpeciesAINavigationProcessor();
protected:
    virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EM) override;
    virtual void Execute(FMassEntityManager& EM,FMassExecutionContext& Context) override;
    FMassEntityQuery Query;
};
UCLASS() class ADAPTIVEECOSYSTEM_API UEcoSpeciesAIMovementProcessor : public UMassProcessor
{
    GENERATED_BODY()
public: UEcoSpeciesAIMovementProcessor();
protected:
    virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EM) override;
    virtual void Execute(FMassEntityManager& EM,FMassExecutionContext& Context) override;
    FMassEntityQuery Query;
};
UCLASS() class ADAPTIVEECOSYSTEM_API UEcoSpeciesAIAttackProcessor : public UMassProcessor
{
    GENERATED_BODY()
public: UEcoSpeciesAIAttackProcessor();
protected:
    virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EM) override;
    virtual void Execute(FMassEntityManager& EM,FMassExecutionContext& Context) override;
    FMassEntityQuery Query;
    FMassEntityQuery TargetQuery;
};
