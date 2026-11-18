#include "HAL/IConsoleManager.h"
#include "String/LexFromString.h"
#include "Engine/World.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "World/EcoVegetationField.h"
#include "EngineUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "MassEntitySubsystem.h"

#if !UE_BUILD_SHIPPING
namespace
{
	bool CanChangeGrassEnvironment(UWorld* World)
	{
		if (!IsInGameThread() || !World || !World->IsGameWorld() || World->GetNetMode() == NM_Client) return false;
		const auto* Mass = World->GetSubsystem<UMassEntitySubsystem>();
		return !Mass || !Mass->GetEntityManager().IsProcessing();
	}
}

static FAutoConsoleCommandWithWorldAndArgs GrassClimate(TEXT("eco.Grass.Climate"),
	TEXT("Authority: <RegionId> <Rainfall 0..1> <Temperature Celsius>. Override the effective regional climate."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		float Rain = 0, Temperature = 0;
		if (CanChangeGrassEnvironment(World) && Args.Num() == 3 &&
			LexTryParseString(Rain, *Args[1]) && LexTryParseString(Temperature, *Args[2]))
		{
			const auto* Regions = World->GetSubsystem<UEcologyWorldSubsystem>();
			auto* Region = Regions ? Regions->GetRegion(FName(*Args[0])) : nullptr;
			if (Region && Region->SetGrassTestClimate(Rain, Temperature))
			{
				UE_LOG(LogTemp, Display, TEXT("[EcoGrass] %s: rain=%.2f temperature=%.1f C"), *Args[0], Rain, Temperature);
				return;
			}
		}
		UE_LOG(LogTemp, Warning, TEXT("[EcoGrass] Climate rejected. Use an authority world and a registered region with valid rain and temperature."));
	}));

static FAutoConsoleCommandWithWorldAndArgs GrassAuto(TEXT("eco.Grass.Auto"),
	TEXT("Authority: <RegionId>. Restore normal regional environment inputs."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (!CanChangeGrassEnvironment(World) || Args.Num() != 1) return;
		const auto* Regions = World->GetSubsystem<UEcologyWorldSubsystem>();
		auto* Region = Regions ? Regions->GetRegion(FName(*Args[0])) : nullptr;
		if (!Region) return;
		Region->ClearGrassTestClimate();
		for (TActorIterator<AEcoVegetationHabitat> It(World); It; ++It)
			if (It->RegionId == Region->RegionId) It->DebugWaterConnection.Reset();
	}));

static FAutoConsoleCommandWithWorldAndArgs GrassWater(TEXT("eco.Grass.Water"),
	TEXT("Authority: <RegionId> [HabitatActorName] <0|1>. Override an authored water habitat's supply."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (!CanChangeGrassEnvironment(World) || (Args.Num() != 2 && Args.Num() != 3) ||
			(Args.Last() != TEXT("0") && Args.Last() != TEXT("1"))) return;
		int32 Changed = 0;
		for (TActorIterator<AEcoVegetationHabitat> It(World); It; ++It)
		{
			if (It->RegionId != FName(*Args[0]) || !It->bConnectedFreshWater || !It->IsValidHabitat() ||
				(Args.Num() == 3 && It->GetFName() != FName(*Args[1]))) continue;
			It->DebugWaterConnection = Args.Last() == TEXT("1");
			++Changed;
		}
		UE_LOG(LogTemp, Display, TEXT("[EcoGrass] Water: %d authored habitat(s) updated; soil applies on ground refresh."), Changed);
	}));

static FAutoConsoleCommandWithWorldAndArgs GrassExport(TEXT("eco.Grass.Export"),
	TEXT("Authority: <RegionId>. Save the food and soil audit to Saved/FoodGrass."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (!CanChangeGrassEnvironment(World) || Args.Num() != 1) return;
		for (TActorIterator<AEcoVegetationField> It(World); It; ++It)
		{
			if (It->RegionId != FName(*Args[0])) continue;
			const FString Directory = FPaths::ProjectSavedDir() / TEXT("FoodGrass");
			IFileManager::Get().MakeDirectory(*Directory, true);
			const FString Path = Directory / (FGuid::NewGuid().ToString() + TEXT(".json"));
			if (FFileHelper::SaveStringToFile(It->CaptureDiagnostics(true), *Path))
			{
				UE_LOG(LogTemp, Display, TEXT("[EcoGrass] Saved %s"), *Path);
			}
			else
			{
				UE_LOG(LogTemp, Error, TEXT("[EcoGrass] Failed to save %s"), *Path);
			}
			return;
		}
		UE_LOG(LogTemp, Warning, TEXT("[EcoGrass] No vegetation Field for %s."), *Args[0]);
	}));

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
