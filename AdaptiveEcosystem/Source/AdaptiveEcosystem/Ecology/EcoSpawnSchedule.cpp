#include "Ecology/EcoSpawnSchedule.h"
#include "World/EcoWorldClockSubsystem.h"

bool FEcoSpawnScheduleCursor::ConsumeDueWave(const FEcoServerTimeSnapshot& Time,
	const FEcoSpawnScheduleSettings& Settings, FEcoSpawnRequest& Out)
{
	if (!Settings.IsValid() || !EcoClock::IsValidPhase(Time.ServerTimeSeconds, Time.DayCycle)
		|| Time.ServerTimeSeconds < LastTime) return false;
	LastTime = Time.ServerTimeSeconds;
	if (CycleId != Time.DayCycle.CycleId || Phase != Time.DayCycle.Phase)
	{
		CycleId = Time.DayCycle.CycleId;
		Phase = Time.DayCycle.Phase;
		NextWaveIndex = 1;
	}
	const bool bDay = Phase == EEcoDayPhase::Day;
	const double Interval = bDay ? Settings.DayIntervalSeconds : Settings.NightIntervalSeconds;
	const double Due = Time.DayCycle.PhaseStartSeconds + NextWaveIndex * Interval;
	// Half-open phase: a wave at the phase end belongs to neither the previous phase nor its successor.
	if (Due >= Time.DayCycle.PhaseEndSeconds || Due > Time.ServerTimeSeconds) return false;
	Out = FEcoSpawnRequest();
	Out.WorldEpoch = Time.WorldEpoch;
	Out.CycleId = CycleId;
	Out.Phase = Phase;
	Out.WaveIndex = NextWaveIndex++;
	Out.ScheduledTime = Due;
	Out.Count = bDay ? Settings.DayCount : Settings.NightCount;
	return true;
}

int32 EcoSpawn::AllowedCount(int32 Requested, int32 RegionalAlive, int32 GlobalAlive,
	int32 RegionalReserved, int32 GlobalReserved, int32 RegionalLimit, int32 GlobalLimit, float Food, bool bInitial)
{
	if (Requested < 0 || RegionalAlive < 0 || GlobalAlive < 0 || RegionalReserved < 0 || GlobalReserved < 0
		|| RegionalLimit <= 0 || GlobalLimit <= 0 || !FMath::IsFinite(Food) || Food < 0.0f || (!bInitial && Food == 0.0f)) return 0;
	const int64 RegionalRoom = FMath::Max<int64>(0, static_cast<int64>(RegionalLimit) - RegionalAlive - RegionalReserved);
	const int64 GlobalRoom = FMath::Max<int64>(0, static_cast<int64>(GlobalLimit) - GlobalAlive - GlobalReserved);
	return static_cast<int32>(FMath::Min<int64>(Requested, FMath::Min(RegionalRoom, GlobalRoom)));
}
