#include "Debug/EcoDebugCommandSubsystem.h"
#include "AdaptiveEcosystem.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"

namespace
{
	struct FSharedCommand
	{
		IConsoleCommand* Console = nullptr;
		int32 Owners = 0;
	};
	TMap<FName, FSharedCommand> SharedCommands;
}

bool UEcoDebugCommandSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return !UE_BUILD_SHIPPING && Super::ShouldCreateSubsystem(Outer) && World
		&& World->IsGameWorld() && World->GetNetMode() != NM_Client;
}

bool UEcoDebugCommandSubsystem::RegisterCommand(const FString& Name, const FString& Help, FHandler Handler)
{
	if (!IsInGameThread() || !GetWorld() || GetWorld()->GetNetMode() == NM_Client
		|| Name.IsEmpty() || !Handler || Name.Contains(TEXT(" ")) || Name.Contains(TEXT("\t"))) return false;
	const FName Key(*Name);
	if (Handlers.Contains(Key)) return false;
	FSharedCommand* Shared = SharedCommands.Find(Key);
	if (!Shared)
	{
		IConsoleManager& ConsoleManager = IConsoleManager::Get();
		if (ConsoleManager.FindConsoleObject(*Name))
		{
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco Debug] Console name already owned: %s"), *Name);
			return false;
		}
		const FConsoleCommandWithWorldAndArgsDelegate Delegate = FConsoleCommandWithWorldAndArgsDelegate::CreateLambda(
			[Key](const TArray<FString>& Args, UWorld* World)
			{
				if (!World || !World->IsGameWorld() || World->GetNetMode() == NM_Client)
				{
					UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco Debug] %s requires a server or Standalone world."), *Key.ToString());
					return;
				}
				if (UEcoDebugCommandSubsystem* Registry = World->GetSubsystem<UEcoDebugCommandSubsystem>())
					Registry->Execute(Key, Args);
			});
		IConsoleCommand* Console = ConsoleManager.RegisterConsoleCommand(*Name, *Help, Delegate, ECVF_Cheat);
		if (!Console) return false;
		Shared = &SharedCommands.Add(Key, FSharedCommand{Console, 0});
	}
	Handlers.Add(Key, MoveTemp(Handler));
	++Shared->Owners;
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Debug] Registered %s in %s"), *Name, *GetWorld()->GetName());
	return true;
}

void UEcoDebugCommandSubsystem::Execute(FName Name, const TArray<FString>& Args)
{
	if (!IsInGameThread() || !GetWorld() || GetWorld()->GetNetMode() == NM_Client) return;
	if (FHandler* Handler = Handlers.Find(Name))
		(*Handler)(*GetWorld(), Args);
	else
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco Debug] %s is not registered in world %s."), *Name.ToString(), *GetWorld()->GetName());
}

void UEcoDebugCommandSubsystem::Deinitialize()
{
	for (const auto& Pair : Handlers)
	{
		FSharedCommand* Shared = SharedCommands.Find(Pair.Key);
		if (Shared && --Shared->Owners == 0)
		{
			IConsoleManager::Get().UnregisterConsoleObject(Shared->Console);
			SharedCommands.Remove(Pair.Key);
		}
	}
	Handlers.Reset();
	Super::Deinitialize();
}
