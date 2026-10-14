#include "HAL/IConsoleManager.h"
#include "String/LexFromString.h"
#include "Engine/World.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Ecology/EcologySimulationSubsystem.h"

#if !UE_BUILD_SHIPPING
static FAutoConsoleCommandWithWorldAndArgs EcoEnvironmentRain(TEXT("eco.Environment.Rain"),
	TEXT("Manual authority World input: <RegionId> <Rainfall 0..1>. Changes no Food directly."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		float Rain = 0;
		if (!World || !IsInGameThread() || World->GetNetMode() == NM_Client || Args.Num() != 2
			|| !LexTryParseString(Rain, *Args[1]) || !FMath::IsFinite(Rain) || Rain < 0 || Rain > 1) return;
		const auto* Inputs = World->GetSubsystem<UEcologyWorldSubsystem>();
		auto* Region = Inputs ? Inputs->GetRegion(FName(*Args[0])) : nullptr; if (!Region) return;
		auto Environment = Region->GetEnvironmentState();
		Environment.Rainfall = Rain;
		Environment.WeatherState = Rain > 0 ? EEcoWeatherState::Rain : EEcoWeatherState::Clear;
		Region->SetEnvironmentState(Environment);
		UE_LOG(LogTemp, Log, TEXT("[Eco World Input] Region=%s Rain=%.3f"), *Args[0], Rain);
	}));

static FAutoConsoleCommandWithWorldAndArgs EcoEnvironmentRegeneration(TEXT("eco.Environment.Regeneration"),
	TEXT("Manual authority profile: <RegionId> <Rate/s> <RainfallResponse 0/1> <DryMultiplier 0..4> <WetMultiplier 0..4>."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		float Rate = 0, Dry = 0, Wet = 0; int32 Response = 0;
		if (!World || !IsInGameThread() || World->GetNetMode() == NM_Client || Args.Num() != 5
			|| !LexTryParseString(Rate, *Args[1]) || !LexTryParseString(Response, *Args[2])
			|| (Response != 0 && Response != 1) || !LexTryParseString(Dry, *Args[3]) || !LexTryParseString(Wet, *Args[4])) return;
		auto* Ecology = World->GetSubsystem<UEcologySimulationSubsystem>();
		const bool Accepted = Ecology && Ecology->ConfigureRegionRegeneration(FName(*Args[0]), Rate, Response != 0, Dry, Wet);
		UE_LOG(LogTemp, Log, TEXT("[Eco Growth Profile] Region=%s Rate=%.3f RainfallResponse=%d Dry=%.3f Wet=%.3f Accepted=%d"),
			*Args[0], Rate, Response, Dry, Wet, Accepted);
	}));
#endif
