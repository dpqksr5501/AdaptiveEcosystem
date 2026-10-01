#include "EcoRegionPredationSubsystem.h"

#include "EcoBehaviorConfig.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

float UEcoRegionPredationSubsystem::GetRecentPredation() const
{
	// §3.1 "clip 1" — 관측은 항상 [0,1] 이어야 한다 (world.py: min(ema, 1)).
	return FMath::Clamp(Ema, 0.0f, 1.0f);
}

void UEcoRegionPredationSubsystem::ReportPredation(const FVector& /*Location*/)
{
	// 논리 상태는 서버/스탠드얼론에만 있다 (AGENTS.md §2.2).
	const UWorld* World = GetWorld();
	if (World && World->GetNetMode() == NM_Client)
	{
		return;
	}
	++PendingDeaths;
}

void UEcoRegionPredationSubsystem::ReportAlivePopulation(int32 AliveCount)
{
	StepPopulation = FMath::Max(StepPopulation, FMath::Max(AliveCount, 0));
}

void UEcoRegionPredationSubsystem::Tick()
{
	const float Decay = EcoBehaviorConfig::PredationEmaDecay;
	const float Gain = EcoBehaviorConfig::PredationEmaGain;
	// 정상 경로에서는 같은 프로세서가 포획 전에 세므로 PendingDeaths <= StepPopulation 이다.
	// 넘는 경우는 '산 초식이 없는데 사망이 보고됨'(전멸 뒤 플레이어 사냥 보고 등)뿐이고, 그때
	// 비율 상한을 1로 둔다. 파리티 경로가 아니다.
	const int32 Denom = FMath::Max3(StepPopulation, PendingDeaths, 1);
	const float Rate = static_cast<float>(PendingDeaths) / static_cast<float>(Denom);
	Ema = Decay * Ema + (1.0f - Decay) * Rate * Gain;
	PendingDeaths = 0;
	StepPopulation = 0;
}

bool UEcoRegionPredationSubsystem::SaveToSlot(const FString& SlotName, int32 UserIndex) const
{
	UEcoPredationSaveGame* Save = Cast<UEcoPredationSaveGame>(
		UGameplayStatics::CreateSaveGameObject(UEcoPredationSaveGame::StaticClass()));
	if (!Save)
	{
		return false;
	}
	Save->SchemaVersion = SaveSchemaVersion;
	Save->Ema = Ema;
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
	if (Save->SchemaVersion != SaveSchemaVersion)
	{
		// v1 은 지역별 저장이고 분모 버그로 값이 최대 128배 부풀어 있다. 일부러 버린다.
		UE_LOG(LogTemp, Warning,
			   TEXT("EcoRegionPredation: SchemaVersion %d(현재 %d) — v1 지역별 저장이라 무시한다"),
			   Save->SchemaVersion, SaveSchemaVersion);
		return false;
	}
	Ema = FMath::Max(Save->Ema, 0.0f);
	PendingDeaths = 0;
	StepPopulation = 0;
	return true;
}
