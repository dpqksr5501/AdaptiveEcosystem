// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Mass/EntityHandle.h"
#include "EcoHerdTestHarnessActor.generated.h"

/**
 * Test harness actor for verifying the Dynamic Herd MVP.
 * Spawns 100 Mass entities distributed across spatial clusters and provides real-time 3D debug visualization of herd centroids and radii.
 */
UCLASS(BlueprintType, Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoHerdTestHarnessActor : public AActor
{
	GENERATED_BODY()

public:
	AEcoHerdTestHarnessActor();

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

public:
	virtual void Tick(float DeltaSeconds) override;

	/** Number of logical mass entities to spawn for the test */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug", meta = (ClampMin = "10", ClampMax = "1000"))
	int32 EntityCount = 100;

	/** Total area radius across which clusters are dispersed */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug", meta = (ClampMin = "500.0"))
	float AreaRadius = 3000.0f;

	/** Number of spatial origin clusters to seed initial entity groups */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug", meta = (ClampMin = "1", ClampMax = "10"))
	int32 ClusterCount = 3;

	/** If true, spawns entities automatically on BeginPlay */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug")
	bool bAutoSpawnOnBeginPlay = true;

	/** Enables in-world 3D wireframe debug rendering of herd centers, join/leave radii, and member counts */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug")
	bool bDrawDebugHerds = true;

	/** Spawns test mass entities configured with Eco social fragments */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Ecology|Debug")
	void SpawnTestHerds();

	/** Cleans up all spawned test mass entities */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Ecology|Debug")
	void ClearTestHerds();

private:
	TArray<FMassEntityHandle> SpawnedEntities;
};
