#include "Debug/EcoStarvationDebugSubsystem.h"
#include "Debug/EcoDebugCommandSubsystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "World/EcologyRegion.h"
#include "World/EcoWorldClockSubsystem.h"
#include "AdaptiveEcosystem.h"
#include "Engine/World.h"
#include "EngineUtils.h"

bool UEcoStarvationDebugSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return !UE_BUILD_SHIPPING && Super::ShouldCreateSubsystem(Outer) && World
		&& World->IsGameWorld() && World->GetNetMode() != NM_Client;
}

void UEcoStarvationDebugSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	Collection.InitializeDependency<UEcoDebugCommandSubsystem>();
}

void UEcoStarvationDebugSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	UEcoDebugCommandSubsystem* Commands = InWorld.GetSubsystem<UEcoDebugCommandSubsystem>();
	if (!Commands) return;

	const auto QueueStarvation = [](UWorld& World, FName RegionId)
	{
		UEcologySimulationSubsystem* Ecology = World.GetSubsystem<UEcologySimulationSubsystem>();
		UEcoWorldClockSubsystem* Clock = World.GetSubsystem<UEcoWorldClockSubsystem>();
		if (!Ecology || !Clock || !Clock->IsClockRunning() || !Ecology->QueueManualStarvation(RegionId, Clock->GetServerTime()))
		{
			UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco Debug] Starvation rejected: World=%s Region=%s (check authority, region and readiness)."),
				*World.GetName(), *RegionId.ToString());
			return;
		}
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Debug] Starvation queued: World=%s Region=%s Due=%.3f; Food will reach zero at this server time."),
			*World.GetName(), *RegionId.ToString(), Clock->GetServerTime().ServerTimeSeconds);
	};

	Commands->RegisterCommand(TEXT("Debug.Starvation"), TEXT("Debug.Starvation <RegionId>: queue immediate food depletion on this server world."),
		[QueueStarvation](UWorld& World, const TArray<FString>& Args)
		{
			if (Args.Num() != 1 || Args[0].IsEmpty())
			{
				UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco Debug] Usage: Debug.Starvation <RegionId>"));
				return;
			}
			QueueStarvation(World, FName(*Args[0]));
		});
	for (TActorIterator<AEcologyRegion> It(&InWorld); It; ++It)
	{
		const FName RegionId = It->RegionId;
		if (RegionId.IsNone()) continue;
		const FString Name = FString::Printf(TEXT("Debug.Starvation.%s"), *RegionId.ToString());
		Commands->RegisterCommand(Name, TEXT("Queue immediate food depletion for this region on the server."),
			[QueueStarvation, RegionId](UWorld& World, const TArray<FString>& Args)
			{
				if (!Args.IsEmpty())
				{
					UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("[Eco Debug] This command takes no arguments."));
					return;
				}
				QueueStarvation(World, RegionId);
			});
	}
}
