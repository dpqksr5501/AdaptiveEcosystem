#include "AI/Social/Shelter/EcoShelterDiagnostics.h"
#include "HAL/IConsoleManager.h"
#include "Engine/World.h"

DEFINE_LOG_CATEGORY(LogEcoSocialShelter);

namespace EcoShelterDiagnostics
{
	static TAutoConsoleVariable<int32> CVarShelterLog(
		TEXT("eco.Shelter.Log"), 0,
		TEXT("Shelter diagnostics: 0=off, 1=lease/state events + 5s summary, 2=also search attempts."), ECVF_Default);

	int32 GetLevel()
	{
#if UE_BUILD_SHIPPING
		return 0;
#else
		return FMath::Clamp(CVarShelterLog.GetValueOnGameThread(), 0, 2);
#endif
	}

	const TCHAR* StateName(EEcoShelterIntentState State)
	{
		switch (State)
		{
		case EEcoShelterIntentState::None: return TEXT("None");
		case EEcoShelterIntentState::Searching: return TEXT("Searching");
		case EEcoShelterIntentState::Reserved: return TEXT("Reserved");
		case EEcoShelterIntentState::Moving: return TEXT("Moving");
		case EEcoShelterIntentState::Occupied: return TEXT("Occupied");
		default: return TEXT("Unknown");
		}
	}

	void LogLeaseEvent(const UWorld* World, const TCHAR* Event, const FEcoShelterSlot& Slot, const TCHAR* Reason)
	{
		if (GetLevel() == 0) { return; }
		UE_LOG(LogEcoSocialShelter, Log,
			TEXT("[Shelter][%s] World=%s Time=%.2f Agent=%lld Reservation=%lld Shelter=%d Slot=%d Reason=%s Target=%s Expires=%.2f"),
			Event, *GetNameSafe(World), World ? double(World->GetTimeSeconds()) : 0.0,
			Slot.ReservedBy, Slot.ReservationId, Slot.ShelterRuntimeIndex, Slot.SlotIndex, Reason,
			*Slot.Position.ToCompactString(), Slot.ReservationExpireTime);
	}
}
