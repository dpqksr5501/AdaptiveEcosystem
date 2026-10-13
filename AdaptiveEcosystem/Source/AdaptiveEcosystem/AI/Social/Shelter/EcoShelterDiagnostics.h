#pragma once

#include "CoreMinimal.h"
#include "AI/Social/EcoSocialTypes.h"

class UWorld;

DECLARE_LOG_CATEGORY_EXTERN(LogEcoSocialShelter, Log, All);

namespace EcoShelterDiagnostics
{
	// 0=off, 1=lease/state events and five-second summary, 2=also search attempts.
	int32 GetLevel();
	const TCHAR* StateName(EEcoShelterIntentState State);
	void LogLeaseEvent(const UWorld* World, const TCHAR* Event, const FEcoShelterSlot& Slot, const TCHAR* Reason);
}
