#include "Ecology/EcoFoodAllocation.h"

bool EcoFood::Allocate(double Available, TConstArrayView<double> Requested, TArray<double>& Grants)
{
	Grants.Reset();
	if (!FMath::IsFinite(Available) || Available < 0.0) return false;
	double Total = 0.0;
	for (double Amount : Requested)
	{
		if (!FMath::IsFinite(Amount) || Amount < 0.0) return false;
		Total += Amount;
	}
	if (!FMath::IsFinite(Total)) return false;
	const double Ratio = Total > 0.0 ? FMath::Min(1.0, Available / Total) : 0.0;
	double Remaining = Available;
	for (double Amount : Requested)
	{
		// Only floating-point overshoot is clipped; resource shortages use the same ratio for everyone.
		const double Grant = FMath::Min(Remaining, Amount * Ratio);
		Grants.Add(Grant);
		Remaining = FMath::Max(0.0, Remaining - Grant);
	}
	return true;
}
