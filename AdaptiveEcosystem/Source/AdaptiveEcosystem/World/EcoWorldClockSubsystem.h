#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Core/EcoTimeTypes.h"
#include "EcoWorldClockSubsystem.generated.h"

namespace EcoClock
{
	ADAPTIVEECOSYSTEM_API bool EvaluateFixedCycle(double Time, double DaySeconds, double NightSeconds, FEcoDayCycleState& Out);
	ADAPTIVEECOSYSTEM_API bool IsValidPhase(double Time, const FEcoDayCycleState& Phase);
}

/** Server-only elapsed clock facade. Advanced exactly once by the Mass lifecycle coordinator.
 * Consumers depend on snapshots, not the built-in day/night calculation.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoWorldClockSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()
public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Deinitialize() override;

	/** Same-world IEcoDayCycleProvider (e.g. a WorldSubsystem); bind before StartClock. */
	UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category="Ecology|Time")
	bool SetDayCycleProvider(UObject* Provider);
	bool StartClock(int32 WorldEpoch, double DaySeconds, double NightSeconds);
	bool AdvanceClock(double DeltaSeconds);
	bool GetSnapshotAt(double TimeSeconds, FEcoServerTimeSnapshot& Out) const;

	UFUNCTION(BlueprintPure, Category="Ecology|Time")
	FEcoServerTimeSnapshot GetServerTime() const { return Current; }
	UFUNCTION(BlueprintPure, Category="Ecology|Time")
	bool IsClockRunning() const { return bRunning; }
	UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category="Ecology|Time")
	void PrintServerTime(bool bPrintToScreen = true) const;
private:
	bool HasServerAuthority() const;
	UPROPERTY(Transient)
	TObjectPtr<UObject> DayCycleProvider;
	FEcoServerTimeSnapshot Current;
	double DayDuration = 60.0;
	double NightDuration = 60.0;
	bool bRunning = false;
};
