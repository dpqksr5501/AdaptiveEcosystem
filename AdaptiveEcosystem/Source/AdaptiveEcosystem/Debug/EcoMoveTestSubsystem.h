#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "AI/Policy/EcoV3StaticMeshMovement.h"
#include "EcoMoveTestSubsystem.generated.h"

class AEcoCreatureRepresentationActor;
class FJsonObject;

#if !UE_BUILD_SHIPPING
namespace EcoMoveBaseline { struct FRun; }
namespace EcoMoveAvoidance { struct FRun; enum class EScenario : uint8; }

struct FEcoMoveTestSample
{
	int64 Step = 0;
	int64 Seed = 0;
	double WorldSeconds = 0;
	FName Region;
	FString Brain;
	int32 Deer = 0, Wolves = 0;
	int32 Request = 0, Executed = 0, FlightOverride = 0, Route = 0, Gait = 0, Mask = 0;
	bool bPolicyRead = false, bArrived = false;
	FName GoalKind;
	int64 GoalId = 0;
	FVector2D GoalXYCm = FVector2D::ZeroVector;
	FVector2D FleeDirection = FVector2D::ZeroVector;
	FVector2D Base = FVector2D::ZeroVector, BeforeAdapter = FVector2D::ZeroVector;
	FVector2D BeforeDetour = FVector2D::ZeroVector, Final = FVector2D::ZeroVector;
	FVector StartCm = FVector::ZeroVector, EndCm = FVector::ZeroVector;
	FVector2D SeparationDelta = FVector2D::ZeroVector;
	int32 LifeMotion = 0, SocialControl = 0;
	bool bBoundarySteer = false, bDetour = false, bDetourFailed = false, bObstacleHit = false;
	bool bIslandSteer = false, bMoveRejected = false, bAlternativeAccepted = false;
	int32 IslandSlide = 0, GroundRejections = 0, ContactRejections = 0;
	int32 DeathCause = 0;
	double Intake = 0;
	float BodyRadiusCm = 0.f;
	bool bStaticMeshHit = false;
	int32 StaticMoveBlock = 0, StaticFinalBlock = 0, StaticHitItem = INDEX_NONE;
	FVector StaticHitPoint = FVector::ZeroVector, StaticHitNormal = FVector::ZeroVector;
	FString StaticHitComponent;

	void SetGoal(FName Kind, int64 Id, double WorldX, double WorldY);
};

struct FEcoMoveTestVisualSample
{
	double WorldSeconds = 0, StateSeconds = 0;
	int32 NativeSamples = 0;
	int64 Sequence = 0;
	FName Region;
	FVector ActorCm = FVector::ZeroVector, StateCm = FVector::ZeroVector, StateVelocity = FVector::ZeroVector;
	double ActorYaw = 0, FocusYaw = 0;
	bool bAlive = false, bDiscontinuity = false;
};
#endif

/** World-local, read-only recorder. File writes run outside Mass processing. */
UCLASS()
class UEcoMoveTestSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void OnWorldEndPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

#if !UE_BUILD_SHIPPING
	void Execute(const TArray<FString>& Args);
	int64 NativeTarget() const;
	void RecordNative(FEcoMoveTestSample&& Sample);
	bool IsRecordingStaticMesh() const { return bActive && bStaticMesh; }
	void RecordStaticMesh(int32 Steps, FEcoV3StaticMeshMetrics&& Metrics);
	FString ScreenStatus() const;

private:
	bool PrepareRun(int32 Steps);
	bool PrepareFixture(int32 Steps);
	void StartObserve(int64 Id, int32 Steps);
	void StartBaseline(int32 Steps, int64 Seed);
	void StartStaticMesh(int32 Frames);
	void StartAvoidance(EcoMoveAvoidance::EScenario Scenario, int32 Steps, int64 Seed, bool bCompareApplied);
	void PostActorTick(UWorld* InWorld, ELevelTick TickType, float DeltaSeconds);
	void StartWorldTick(UWorld* InWorld, ELevelTick TickType, float DeltaSeconds);
	void RecordVisual(double Now);
	AEcoCreatureRepresentationActor* FindVisual(int64 Id) const;
	void Finish(const TCHAR* Result, const TCHAR* Reason);
	bool WriteReport(const TCHAR* Result, const TCHAR* Reason) const;
	bool WriteBaseline(const TCHAR* Result, const TCHAR* Reason) const;
	bool WriteAvoidance(const TCHAR* Result, const TCHAR* Reason) const;
	bool WriteAppliedAvoidance(const TCHAR* Result, const TCHAR* Reason) const;
	bool WriteStaticMesh(const TCHAR* Result, const TCHAR* Reason) const;
	void PrintStatus() const;

	FDelegateHandle PostTickHandle, StartTickHandle;
	TWeakObjectPtr<AEcoCreatureRepresentationActor> Visual;
	TArray<FEcoMoveTestSample> Samples;
	TArray<FEcoMoveTestVisualSample> VisualSamples;
	TSharedPtr<EcoMoveBaseline::FRun> Baseline;
	TSharedPtr<EcoMoveAvoidance::FRun> Avoidance;
	struct FStaticMeshFrame
	{
		uint64 Frame;
		int32 Steps;
		double WorldSeconds, DeltaSeconds, WorldTickSeconds;
		FEcoV3StaticMeshMetrics Metrics;
	};
	TArray<FStaticMeshFrame> StaticMeshFrames;
	TSharedPtr<FJsonObject> StaticMeshSetup;
	double WorldTickStarted = 0.;
	int32 StaticMeshMode = 0;
	bool bStaticMesh = false;
	FString RunId, Directory, LastResult, LastReason;
	int64 AgentId = 0;
	int32 RequestedSteps = 0;
	double StartedAt = 0, LastNativeAt = 0, NextVisualAt = 0, ShowResultUntil = 0;
	bool bActive = false, bClient = false;
#endif
};
