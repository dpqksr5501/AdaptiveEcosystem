#include "Ecology/EcologySimulationSubsystem.h"

bool UEcologySimulationSubsystem::AdjustSpatialFoodHabitat(FName Id, int64 Sequence, double Before, double Removed, double Capacity, double After)
{
	auto* Source = SpatialFood.Find(Id);
	if (!CanMutateAuthoritativeState(TEXT("AdjustSpatialFoodHabitat")) || bResourceStepOpen || !Source || Sequence <= Source->Sequence
		|| !FMath::IsFinite(Before) || !FMath::IsFinite(Removed) || !FMath::IsFinite(Capacity) || !FMath::IsFinite(After)
		|| Removed < 0 || Capacity <= 0 || Capacity > MAX_flt || After < 0 || After > Capacity + 1.e-8
		|| !FMath::IsNearlyEqual(Before, Source->Amount, 1.e-6)
		|| !FMath::IsNearlyEqual(Before - Removed, After, 1.e-6)) return false;
	Source->Capacity = Capacity; Source->Amount = After; Source->Sequence = Sequence;
	Source->HabitatRemoved += Removed;
	auto& Region = RegionalStates.FindChecked(Id);
	Region.FoodCapacity = float(Capacity); Region.FoodAmount = float(FMath::Clamp(After, 0.0, Capacity));
	return true;
}

bool UEcologySimulationSubsystem::RegisterSpatialFood(FName Id, double Capacity, double Amount)
{
	if (!CanMutateAuthoritativeState(TEXT("RegisterSpatialFood")) || bResourceStepOpen || SpatialFood.Contains(Id)
		|| (DayEvent.bEnabled&&DayEvent.RegionId==Id) || (NightEvent.bEnabled&&NightEvent.RegionId==Id)
        || PendingManualStarvation.Contains(Id) || PendingManualFoodSupply.Contains(Id)
        || !RegionalStates.Contains(Id) || !FMath::IsFinite(Capacity) || Capacity <= 0 || Capacity > MAX_flt
		|| !FMath::IsFinite(Amount) || Amount < 0 || Amount > Capacity) return false;
	auto& Source = SpatialFood.Add(Id); Source.Capacity = Capacity; Source.Amount = Amount;
	auto& Region = RegionalStates.FindChecked(Id);
	Region.FoodCapacity = float(Capacity); Region.FoodAmount = float(Amount);
	return true;
}

bool UEcologySimulationSubsystem::CommitSpatialFood(FName Id, int64 Sequence, double Before, double Consumed, double Regenerated, double After)
{
	auto* Source = SpatialFood.Find(Id);
	if (!CanMutateAuthoritativeState(TEXT("CommitSpatialFood")) || bResourceStepOpen || !Source || Sequence <= Source->Sequence
		|| !FMath::IsFinite(Before) || !FMath::IsFinite(Consumed) || !FMath::IsFinite(Regenerated) || !FMath::IsFinite(After)
		|| Consumed < 0 || Regenerated < -1.e-8 || After < 0 || After > Source->Capacity + 1.e-8
		|| !FMath::IsNearlyEqual(Before, Source->Amount, 1.e-6)
		|| !FMath::IsNearlyEqual(Before - Consumed + Regenerated, After, 1.e-6)) return false;
	Source->Amount = After; Source->Sequence = Sequence;
	Source->Consumed += Consumed; Source->Regenerated += FMath::Max(0.0, Regenerated);
	RegionalStates.FindChecked(Id).FoodAmount = float(FMath::Clamp(After, 0.0, Source->Capacity));
	return true;
}
