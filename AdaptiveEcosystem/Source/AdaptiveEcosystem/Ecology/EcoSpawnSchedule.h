#pragma once
#include "Core/EcoSpawnTypes.h"

/** Consumes due wave keys even when food/caps reject a spawn. Never builds a backlog of rejected waves. */
struct ADAPTIVEECOSYSTEM_API FEcoSpawnScheduleCursor
{
	bool ConsumeDueWave(const FEcoServerTimeSnapshot& Time, const FEcoSpawnScheduleSettings& Settings, FEcoSpawnRequest& Out);
private:
	int64 CycleId = -1;
	EEcoDayPhase Phase = EEcoDayPhase::Day;
	int64 NextWaveIndex = 1;
	double LastTime = -1.0;
};

namespace EcoSpawn
{
	ADAPTIVEECOSYSTEM_API int32 AllowedCount(int32 Requested, int32 RegionalAlive, int32 GlobalAlive,
		int32 RegionalReserved, int32 GlobalReserved, int32 RegionalLimit, int32 GlobalLimit, float Food, bool bInitial);
}
