#include "EcoNeighborhoodSubsystem.h"

void UEcoNeighborhoodSubsystem::BeginFrame(float InCellSize)
{
	Entries.Reset();
	Cells.Reset();
	CellSize = FMath::Max(InCellSize, 1.0f);
	bBuilt = false;
}

int32 UEcoNeighborhoodSubsystem::Add(const FEcoNeighborEntry& Entry)
{
	return Entries.Add(Entry);
}

int64 UEcoNeighborhoodSubsystem::CellKey(const FVector& Location) const
{
	const int64 X = static_cast<int64>(FMath::FloorToInt(Location.X / CellSize));
	const int64 Y = static_cast<int64>(FMath::FloorToInt(Location.Y / CellSize));
	return (X << 32) ^ (Y & 0xFFFFFFFF);
}

void UEcoNeighborhoodSubsystem::Build()
{
	Cells.Reserve(Entries.Num());
	for (int32 i = 0; i < Entries.Num(); ++i)
	{
		Cells.FindOrAdd(CellKey(Entries[i].Location)).Add(i);
	}
	bBuilt = true;
}

void UEcoNeighborhoodSubsystem::QueryRadius(const FVector& Location, float Radius,
										   TArray<int32>& OutIndices) const
{
	OutIndices.Reset();
	if (!bBuilt)
	{
		return;
	}

	// 셀 크기를 반경 이상으로 잡았으므로 3x3 이면 충분하다. 반경이 더 크면 범위를 넓힌다.
	const int32 Span = FMath::Max(1, FMath::CeilToInt(Radius / CellSize));
	const int64 CX = static_cast<int64>(FMath::FloorToInt(Location.X / CellSize));
	const int64 CY = static_cast<int64>(FMath::FloorToInt(Location.Y / CellSize));
	const float RadiusSq = Radius * Radius;

	for (int32 dy = -Span; dy <= Span; ++dy)
	{
		for (int32 dx = -Span; dx <= Span; ++dx)
		{
			const int64 Key = ((CX + dx) << 32) ^ ((CY + dy) & 0xFFFFFFFF);
			if (const TArray<int32>* Bucket = Cells.Find(Key))
			{
				for (int32 Index : *Bucket)
				{
					if (FVector::DistSquared2D(Entries[Index].Location, Location) <= RadiusSq)
					{
						OutIndices.Add(Index);
					}
				}
			}
		}
	}
}
