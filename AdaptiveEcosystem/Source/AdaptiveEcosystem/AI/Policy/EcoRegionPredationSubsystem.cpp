#include "EcoRegionPredationSubsystem.h"

#include "EcoBehaviorConfig.h"
#include "Kismet/GameplayStatics.h"

int64 UEcoRegionPredationSubsystem::RegionKey(const FVector& Location) const
{
	const float Size = FMath::Max(RegionSize, 1.0f);
	const int64 X = static_cast<int64>(FMath::FloorToInt(Location.X / Size));
	const int64 Y = static_cast<int64>(FMath::FloorToInt(Location.Y / Size));
	return (X << 32) ^ (Y & 0xFFFFFFFF);
}

float UEcoRegionPredationSubsystem::Get(const FVector& Location) const
{
	if (const FEcoRegionPredationState* State = Regions.Find(RegionKey(Location)))
	{
		// §3.1 "clip 1" — 관측은 항상 [0,1] 이어야 한다.
		return FMath::Clamp(State->Ema, 0.0f, 1.0f);
	}
	return 0.0f;
}

void UEcoRegionPredationSubsystem::ReportPredation(const FVector& Location)
{
	Regions.FindOrAdd(RegionKey(Location)).PendingDeaths += 1;
}

void UEcoRegionPredationSubsystem::ReportPopulation(const FVector& Location, int32 Count)
{
	FEcoRegionPredationState& State = Regions.FindOrAdd(RegionKey(Location));
	// 구간 안에서 본 최대값을 분모로 쓴다. 매 틱 덮어쓰면 마지막 틱 값만 남는다.
	State.Population = FMath::Max(State.Population, Count);
}

void UEcoRegionPredationSubsystem::Tick()
{
	// §3.1 / §9.6: ema = decay*ema + (1-decay)*(사망 수 / 개체 수)*gain
	const float Decay = EcoBehaviorConfig::PredationEmaDecay;
	const float Gain = EcoBehaviorConfig::PredationEmaGain;

	for (auto& Pair : Regions)
	{
		FEcoRegionPredationState& State = Pair.Value;
		const float Denom = static_cast<float>(FMath::Max(State.Population, 1));
		const float Rate = static_cast<float>(State.PendingDeaths) / Denom;
		State.Ema = Decay * State.Ema + (1.0f - Decay) * Rate * Gain;
		State.PendingDeaths = 0;
		State.Population = 0;
	}
}

bool UEcoRegionPredationSubsystem::SaveToSlot(const FString& SlotName, int32 UserIndex) const
{
	UEcoPredationSaveGame* Save = Cast<UEcoPredationSaveGame>(
		UGameplayStatics::CreateSaveGameObject(UEcoPredationSaveGame::StaticClass()));
	if (!Save)
	{
		return false;
	}
	Save->Regions = Regions;
	Save->RegionSize = RegionSize;
	return UGameplayStatics::SaveGameToSlot(Save, SlotName, UserIndex);
}

bool UEcoRegionPredationSubsystem::LoadFromSlot(const FString& SlotName, int32 UserIndex)
{
	UEcoPredationSaveGame* Save = Cast<UEcoPredationSaveGame>(
		UGameplayStatics::LoadGameFromSlot(SlotName, UserIndex));
	if (!Save)
	{
		return false;
	}
	// 지역 크기가 다르면 키가 다른 공간을 가리키므로 불러오지 않는다.
	if (!FMath::IsNearlyEqual(Save->RegionSize, RegionSize))
	{
		UE_LOG(LogTemp, Warning,
			   TEXT("EcoRegionPredation: 저장된 RegionSize(%.1f)가 현재(%.1f)와 달라 무시한다"),
			   Save->RegionSize, RegionSize);
		return false;
	}
	Regions = Save->Regions;
	return true;
}
