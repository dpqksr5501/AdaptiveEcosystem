#include "EcoWorldProviders.h"

#include "Engine/World.h"

// -----------------------------------------------------------------------------
// UEcoDummyWorldProviderSubsystem
// -----------------------------------------------------------------------------

void UEcoDummyWorldProviderSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	// §9.4 "평면 + 고정 패턴". 맵 중앙을 비우고 사방에 은신처를 둔다.
	const float R = WorldExtent * 0.45f;
	CoverPoints.Reset();
	CoverPoints.Add(FVector(+R, +R, 0.0f));
	CoverPoints.Add(FVector(-R, +R, 0.0f));
	CoverPoints.Add(FVector(+R, -R, 0.0f));
	CoverPoints.Add(FVector(-R, -R, 0.0f));
}

float UEcoDummyWorldProviderSubsystem::RawFoodAt(const FVector& Location) const
{
	// 저주파 사인 격자를 문턱값으로 잘라 패치를 만든다. 결과는 [0,1].
	const float K = 2.0f * PI / FMath::Max(FoodWavelength, KINDA_SMALL_NUMBER);
	const float Raw = 0.5f * (FMath::Sin(Location.X * K) * FMath::Cos(Location.Y * K) + 1.0f);
	const float T = FMath::Clamp(FoodThreshold, 0.0f, 0.99f);
	return FMath::Clamp((Raw - T) / (1.0f - T), 0.0f, 1.0f);
}

int64 UEcoDummyWorldProviderSubsystem::CellKey(const FVector& Location) const
{
	const int64 X = static_cast<int64>(FMath::FloorToInt(Location.X / FoodCellCm));
	const int64 Y = static_cast<int64>(FMath::FloorToInt(Location.Y / FoodCellCm));
	return (X << 32) ^ (Y & 0xFFFFFFFF);
}

float UEcoDummyWorldProviderSubsystem::GetFoodDensity(const FVector& Location, float Radius) const
{
	// §3.1 관측 0번은 "시야 내 먹이 밀도 평균"이다. 해석적 적분 대신 십자 표본으로
	// 근사한다 — 더미의 목적은 정확도가 아니라 파이프라인을 돌리는 것이다.
	const float R = FMath::Max(Radius, KINDA_SMALL_NUMBER);
	float Sum = RawFoodAt(Location);
	int32 N = 1;
	for (const FVector& Offset : {FVector(R, 0, 0), FVector(-R, 0, 0),
								  FVector(0, R, 0), FVector(0, -R, 0),
								  FVector(R * 0.5f, R * 0.5f, 0),
								  FVector(-R * 0.5f, -R * 0.5f, 0)})
	{
		Sum += RawFoodAt(Location + Offset);
		++N;
	}
	const float Consumed = ConsumedGrid.FindRef(CellKey(Location));
	return FMath::Clamp(Sum / N - Consumed, 0.0f, 1.0f);
}

FVector UEcoDummyWorldProviderSubsystem::GetFoodGradient(const FVector& Location, float Radius) const
{
	// 조향용이라 관측보다 **좁은 반경**으로 잡는다. 넓게 잡으면 국소 고갈이 반영되지
	// 않아 개체가 전부 같은 지점으로 몰린다 (파이썬에서 측정된 문제).
	const float H = FMath::Max(Radius * 0.2f, FoodCellCm);
	const float Dx = GetFoodDensity(Location + FVector(H, 0, 0), H)
				   - GetFoodDensity(Location - FVector(H, 0, 0), H);
	const float Dy = GetFoodDensity(Location + FVector(0, H, 0), H)
				   - GetFoodDensity(Location - FVector(0, H, 0), H);
	return FVector(Dx, Dy, 0.0f).GetSafeNormal();
}

float UEcoDummyWorldProviderSubsystem::ConsumeFood(const FVector& Location, float Amount)
{
	const int64 Key = CellKey(Location);
	float& Consumed = ConsumedGrid.FindOrAdd(Key, 0.0f);
	const float Available = FMath::Max(RawFoodAt(Location) - Consumed, 0.0f);
	const float Taken = FMath::Min(Amount, Available);
	Consumed += Taken;
	return Taken;
}

void UEcoDummyWorldProviderSubsystem::RegenerateConsumed(float DeltaSeconds)
{
	const float Recover = ConsumeRegenPerSecond * DeltaSeconds;
	for (auto It = ConsumedGrid.CreateIterator(); It; ++It)
	{
		It.Value() -= Recover;
		if (It.Value() <= 0.0f)
		{
			It.RemoveCurrent();
		}
	}
}

float UEcoDummyWorldProviderSubsystem::GetCoverDistance(const FVector& Location) const
{
	float Best = TNumericLimits<float>::Max();
	for (const FVector& C : CoverPoints)
	{
		Best = FMath::Min(Best, FVector::Dist2D(Location, C) - CoverRadius);
	}
	return FMath::Max(Best, 0.0f);
}

FVector UEcoDummyWorldProviderSubsystem::GetCoverDirection(const FVector& Location) const
{
	float Best = TNumericLimits<float>::Max();
	FVector BestDir = FVector::ZeroVector;
	for (const FVector& C : CoverPoints)
	{
		const float Edge = FVector::Dist2D(Location, C) - CoverRadius;
		if (Edge < Best)
		{
			Best = Edge;
			BestDir = FVector(C.X - Location.X, C.Y - Location.Y, 0.0f);
		}
	}
	// 이미 안에 있으면 영벡터 — §3.3 to_cover 규약.
	return Best <= 0.0f ? FVector::ZeroVector : BestDir.GetSafeNormal();
}

bool UEcoDummyWorldProviderSubsystem::IsInCover(const FVector& Location) const
{
	for (const FVector& C : CoverPoints)
	{
		if (FVector::Dist2D(Location, C) <= CoverRadius)
		{
			return true;
		}
	}
	return false;
}

// -----------------------------------------------------------------------------
// UEcoWorldProviderRegistry
// -----------------------------------------------------------------------------

void UEcoWorldProviderRegistry::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	// 더미를 기본값으로 걸어 둔다. 월드팀 구현이 생기면 Set*Provider 로 덮어쓴다.
	if (UWorld* World = GetWorld())
	{
		if (UEcoDummyWorldProviderSubsystem* Dummy =
				World->GetSubsystem<UEcoDummyWorldProviderSubsystem>())
		{
			FoodProvider = Dummy;
			CoverProvider = Dummy;
		}
	}
}
