#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoDebugCommandSubsystem.generated.h"

/** One handler per authoritative world. Command names are shared across PIE worlds,
 * while dispatch always uses the world supplied by the console.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoDebugCommandSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()
public:
	using FHandler = TFunction<void(UWorld&, const TArray<FString>&)>;

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Deinitialize() override;

	/** Register from a feature subsystem when its authoritative world is ready.
	 * Registration belongs to that world and is removed automatically at teardown.
	 */
	bool RegisterCommand(const FString& Name, const FString& Help, FHandler Handler);
	void Execute(FName Name, const TArray<FString>& Args);

private:
	TMap<FName, FHandler> Handlers;
};
