#include "EcoPolicyTestSpawner.h"

#include "AI/Policy/EcoBehaviorConfig.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoWorldProviders.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "MassMovementFragments.h"
#include "Ecology/EcologySimulationSubsystem.h"

AEcoPolicyTestSpawner::AEcoPolicyTestSpawner()
{
	PrimaryActorTick.bCanEverTick = true;
	// 조향·포획 결과를 보려면 Mass 프로세서(PrePhysics)가 돈 뒤여야 한다.
	PrimaryActorTick.TickGroup = TG_PostPhysics;
}

namespace
{
	FMassEntityManager* GetEntityManager(const UWorld* World)
	{
		if (!World)
		{
			return nullptr;
		}
		UMassEntitySubsystem* Sub = World->GetSubsystem<UMassEntitySubsystem>();
		return Sub ? &Sub->GetMutableEntityManager() : nullptr;
	}

	/** Z축 회전. 배회 선회와 시야 부채꼴에 쓴다. */
	FVector Rotate2D(const FVector& V, float Angle)
	{
		const float C = FMath::Cos(Angle);
		const float S = FMath::Sin(Angle);
		return FVector(V.X * C - V.Y * S, V.X * S + V.Y * C, 0.0f);
	}

	/** 파이썬 시야 판정: dot(방향, heading) >= cos(fov/2). Heading 은 단위벡터. */
	bool InFov(const FVector& From, const FVector& Heading, const FVector& To, float CosHalfFov)
	{
		const FVector D(To.X - From.X, To.Y - From.Y, 0.0f);
		const float Len = D.Size2D();
		return Len > KINDA_SMALL_NUMBER && FVector::DotProduct(D / Len, Heading) >= CosHalfFov;
	}

	/** 부채꼴. 포식자 시야를 그린다 — 이 안에 들어온 초식만 쫓는다. */
	void DrawFan(const UWorld* World, const FVector& Center, const FVector& Heading, float Radius,
				 float HalfAngle, const FColor& Color, float Thickness)
	{
		constexpr int32 Segments = 16;
		FVector Prev = Center + Rotate2D(Heading, -HalfAngle) * Radius;
		DrawDebugLine(World, Center, Prev, Color, false, -1.0f, 0, Thickness);
		for (int32 s = 1; s <= Segments; ++s)
		{
			const float A = -HalfAngle + 2.0f * HalfAngle * static_cast<float>(s) / Segments;
			const FVector Next = Center + Rotate2D(Heading, A) * Radius;
			DrawDebugLine(World, Prev, Next, Color, false, -1.0f, 0, Thickness);
			Prev = Next;
		}
		DrawDebugLine(World, Center, Prev, Color, false, -1.0f, 0, Thickness);
	}

	/** 색 = cohesion (파이썬 replay.py 와 같은 규약). 파랑(0) → 빨강(1). */
	FColor CohesionColor(float Cohesion)
	{
		return FColor(FMath::Clamp(static_cast<int32>(Cohesion * 255.0f), 0, 255), 60,
					  FMath::Clamp(static_cast<int32>((1.0f - Cohesion) * 255.0f), 0, 255));
	}

	const FVector DrawLift(0.0f, 0.0f, 50.0f);
}

void AEcoPolicyTestSpawner::BeginPlay()
{
	Super::BeginPlay();
	if (!GetWorld() || GetWorld()->GetNetMode() == NM_Client) { return; }
	SpawnEntities();
}

void AEcoPolicyTestSpawner::EndPlay(const EEndPlayReason::Type Reason)
{
	if (FMassEntityManager* EM = GetEntityManager(GetWorld()))
	{
		for (const FMassEntityHandle& E : Herbivores)
		{
			if (EM->IsEntityValid(E)) { EM->DestroyEntity(E); }
		}
		for (const FMassEntityHandle& E : Predators)
		{
			if (EM->IsEntityValid(E)) { EM->DestroyEntity(E); }
		}
	}
	Herbivores.Reset();
	Predators.Reset();
	PredatorHeadings.Reset();
	PredatorTargets.Reset();
	CatchesSinceLog = 0;
	TotalCatches = 0;
	Super::EndPlay(Reason);
}

float AEcoPolicyTestSpawner::GetWorldExtent() const
{
	const UWorld* World = GetWorld();
	const UEcoDummyWorldProviderSubsystem* Dummy =
		World ? World->GetSubsystem<UEcoDummyWorldProviderSubsystem>() : nullptr;
	return (Dummy && Dummy->WorldExtent > 0.0f) ? Dummy->WorldExtent : SpawnRadius;
}

void AEcoPolicyTestSpawner::SpawnEntities()
{
	FMassEntityManager* EM = GetEntityManager(GetWorld());
	if (!EM)
	{
		UE_LOG(LogTemp, Error, TEXT("EcoPolicyTestSpawner: MassEntitySubsystem 이 없다"));
		return;
	}

	// §9.4/§9.5 쿼리가 요구하는 프래그먼트·태그의 합집합.
	TArray<const UScriptStruct*> HerbComposition = {
		FTransformFragment::StaticStruct(),
		FMassVelocityFragment::StaticStruct(),
		FEcoSteeringGeometryFragment::StaticStruct(),
		FEcoObservationFragment::StaticStruct(),
		FEcoPolicyOutputFragment::StaticStruct(),
		FEcoPolicyRuntimeFragment::StaticStruct(),
		FEcoVitalsFragment::StaticStruct(),
		FEcoHerbivoreTag::StaticStruct(),
		// 트레잇과 같은 구성. 이동은 조향 프로세서 몫이라 엔진 이동 프로세서를 막아 둔다.
		FMassCustomMovementTag::StaticStruct(),
	};
	// FEcoPredatorStateFragment 가 없으면 UEcoPredationProcessor 가 이 포식자를 못 본다.
	TArray<const UScriptStruct*> PredComposition = {
		FTransformFragment::StaticStruct(),
		FMassVelocityFragment::StaticStruct(),
		FEcoPredatorStateFragment::StaticStruct(),
		FEcoPredatorTag::StaticStruct(),
	};
	UEcologySimulationSubsystem* IdentityOwner = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	if (bAssignStableAgentIds)
	{
		if (!IdentityOwner || !IdentityOwner->IsAuthoritativeWorld()) { return; }
		HerbComposition.Add(FEcoIdentityFragment::StaticStruct());
		PredComposition.Add(FEcoIdentityFragment::StaticStruct());
	}

	const FMassArchetypeHandle HerbArch = EM->CreateArchetype(HerbComposition);
	const FMassArchetypeHandle PredArch = EM->CreateArchetype(PredComposition);

	const FVector Origin = GetActorLocation();
	FRandomStream Rand(1337);   // 결정적으로 — 같은 배치를 다시 보고 싶을 때가 있다
	SimRand.Initialize(4242);

	auto Spawn = [&](const FMassArchetypeHandle& Arch, int32 Count, float Radius,
					 TArray<FMassEntityHandle>& Out)
	{
		for (int32 i = 0; i < Count; ++i)
		{
			const FMassEntityHandle E = EM->CreateEntity(Arch);
			const float Angle = Rand.FRandRange(0.0f, 2.0f * PI);
			const float R = Radius * FMath::Sqrt(Rand.FRand());   // 면적 균등
			const FVector Loc = Origin + FVector(R * FMath::Cos(Angle), R * FMath::Sin(Angle), 0.0f);

			EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(Loc);
			// 정지 상태면 시야 판정이 전방 축에 고정되므로 초기 속도를 준다.
			const float A2 = Rand.FRandRange(0.0f, 2.0f * PI);
			EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value =
				FVector(FMath::Cos(A2), FMath::Sin(A2), 0.0f) * 10.0f;
			Out.Add(E);
		}
	};

	Spawn(HerbArch, HerbivoreCount, SpawnRadius, Herbivores);
	Spawn(PredArch, PredatorCount, SpawnRadius * 0.7f, Predators);
	if (bAssignStableAgentIds)
	{
		for (const auto E : Herbivores)
		{
			auto& Identity = EM->GetFragmentDataChecked<FEcoIdentityFragment>(E);
			Identity.StableAgentId = IdentityOwner->AllocateStableAgentId();
			Identity.SpeciesId = TEXT("Herbivore");
		}
		for (const auto E : Predators)
		{
			auto& Identity = EM->GetFragmentDataChecked<FEcoIdentityFragment>(E);
			Identity.StableAgentId = IdentityOwner->AllocateStableAgentId();
			Identity.SpeciesId = TEXT("Wolf");
		}
	}

	// §9.2 "스폰 시 0~PolicyInterval 랜덤" — 정책 부하를 틱마다 고르게 흩는다.
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	for (int32 i = 0; i < Herbivores.Num(); ++i)
	{
		FEcoVitalsFragment& Vitals = EM->GetFragmentDataChecked<FEcoVitalsFragment>(Herbivores[i]);
		Vitals.MaxEnergy = 100.0f;
		Vitals.Energy = Rand.FRandRange(20.0f, 100.0f);
		EM->GetFragmentDataChecked<FEcoPolicyRuntimeFragment>(Herbivores[i]).LastPolicyStep =
			Rand.RandRange(0, Interval - 1);
	}

	PredatorHeadings.SetNum(Predators.Num());
	PredatorTargets.Init(INDEX_NONE, Predators.Num());
	for (int32 i = 0; i < Predators.Num(); ++i)
	{
		const float A = Rand.FRandRange(0.0f, 2.0f * PI);
		PredatorHeadings[i] = FVector(FMath::Cos(A), FMath::Sin(A), 0.0f);
	}

	bSpawned = true;
	UE_LOG(LogTemp, Log, TEXT("EcoPolicyTestSpawner: 초식 %d, 포식자 %d 스폰. "
							  "eco.UseLearnedPolicy 로 정책을 바꾼다."),
		   Herbivores.Num(), Predators.Num());
}

void AEcoPolicyTestSpawner::RespawnCaught()
{
	// 파이썬 §4.3 — 잡힌 슬롯을 즉시 월드 전체 균일 랜덤 위치로 되살린다. 개체 수는 고정.
	//
	// 실제 게임에서는 Lifecycle 계층의 몫이고 UEcoPredationProcessor 는 HP=0 으로 표시만 한다.
	// 테스트 레벨에는 그 계층이 없어서, 이게 없으면 잡힌 개체가 HP 0 인 채로 계속 달리고
	// 포식자는 그 "시체"를 최근접 표적으로 영원히 쫓는다.
	FMassEntityManager* EM = GetEntityManager(GetWorld());
	if (!EM)
	{
		return;
	}
	const float Extent = GetWorldExtent();

	for (const FMassEntityHandle& E : Herbivores)
	{
		if (!EM->IsEntityValid(E)) { continue; }
		FEcoVitalsFragment& Vitals = EM->GetFragmentDataChecked<FEcoVitalsFragment>(E);
		if (Vitals.HP > 0.0f) { continue; }

		FTransform& T = EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform();
		const FVector Death = T.GetLocation();
		if (bDrawDebug)
		{
			// 포획 지점 — 1.5초 남는다.
			DrawDebugSphere(GetWorld(), Death + DrawLift, 350.0f, 12, FColor::Orange,
							false, 1.5f, 0, 8.0f);
			DrawDebugPoint(GetWorld(), Death + DrawLift, HerbivorePointSize * 2.5f, FColor::Orange,
						   false, 1.5f);
		}
		++CatchesSinceLog;
		++TotalCatches;

		T.SetLocation(FVector(SimRand.FRandRange(-Extent, Extent),
							  SimRand.FRandRange(-Extent, Extent), Death.Z));
		const float A = SimRand.FRandRange(0.0f, 2.0f * PI);
		EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value =
			FVector(FMath::Cos(A), FMath::Sin(A), 0.0f) * 10.0f;
		Vitals.HP = Vitals.MaxHP;
		Vitals.Energy = Vitals.MaxEnergy * EcoBehaviorConfig::InitEnergyFrac;
		OnTestEntityReset(E);
	}
}

void AEcoPolicyTestSpawner::MovePredators(float DeltaSeconds)
{
	// 파이썬 env/world.py 의 포식자 스텝 (§4.2):
	//   - 식사 중(쿨다운)이 아니면 시야 안 최근접을 **체감 거리**로 고른다
	//       시야 = 반경 pred_view_r × 각도 pred_fov, 체감 거리 = 거리 × (은신처면 cover_hide_mult)
	//   - 목표가 있으면 직선 추격, 없으면 스텝마다 ±pred_wander_turn 만큼 틀며 배회
	//   - 벽에 닿으면 그 축 방향을 뒤집고 좌표를 clamp
	// 포획 자체는 UEcoPredationProcessor 가 한다. 여기서는 움직임만.
	UWorld* World = GetWorld();
	FMassEntityManager* EM = GetEntityManager(World);
	if (!EM || Predators.Num() == 0)
	{
		return;
	}
	const UEcoWorldProviderRegistry* Registry = World->GetSubsystem<UEcoWorldProviderRegistry>();
	const IEcoWorldCoverProvider* Cover = Registry ? Registry->GetCoverProvider() : nullptr;

	const float Speed = EcoBehaviorConfig::HerbSpeedCmS * PredatorSpeedRatio;
	const float ViewRadius = EcoBehaviorConfig::PredViewRadiusCm;
	const float HideMult = EcoBehaviorConfig::CoverHideMult;
	const float CosHalfFov =
		FMath::Cos(FMath::DegreesToRadians(EcoBehaviorConfig::PredFovDeg) * 0.5f);
	const float Turn = EcoBehaviorConfig::PredWanderTurnRad;
	const float Extent = GetWorldExtent();

	// 파이썬 선회는 "스텝당 ±Turn" 이다. 틱마다 잘게 나눠 돌리면 무작위 걸음의 분산이
	// 달라져 훨씬 곧게 걷는다. 그래서 스텝 경계에서만 한 번 돈다.
	WanderAccumulator += DeltaSeconds;
	const bool bStepBoundary = WanderAccumulator >= EcoBehaviorConfig::StepSeconds;
	if (bStepBoundary)
	{
		WanderAccumulator = FMath::Fmod(WanderAccumulator, EcoBehaviorConfig::StepSeconds);
	}

	// 초식 위치와 은신 여부 — 포식자마다 다시 구하지 않는다.
	TArray<FVector> HerbPos;
	TArray<float> HerbHide;   // 체감 거리 배수. 0 이면 표적이 될 수 없다
	HerbPos.SetNum(Herbivores.Num());
	HerbHide.SetNum(Herbivores.Num());
	for (int32 j = 0; j < Herbivores.Num(); ++j)
	{
		const FMassEntityHandle& H = Herbivores[j];
		if (!EM->IsEntityValid(H) || EM->GetFragmentDataChecked<FEcoVitalsFragment>(H).HP <= 0.0f)
		{
			HerbHide[j] = 0.0f;
			continue;
		}
		HerbPos[j] = EM->GetFragmentDataChecked<FTransformFragment>(H).GetTransform().GetLocation();
		HerbHide[j] = (Cover && Cover->IsInCover(HerbPos[j])) ? HideMult : 1.0f;
	}

	for (int32 i = 0; i < Predators.Num(); ++i)
	{
		PredatorTargets[i] = INDEX_NONE;
		if (!EM->IsEntityValid(Predators[i])) { continue; }

		FTransform& T = EM->GetFragmentDataChecked<FTransformFragment>(Predators[i]).GetMutableTransform();
		const FEcoPredatorStateFragment& State =
			EM->GetFragmentDataChecked<FEcoPredatorStateFragment>(Predators[i]);
		const FVector Pos = T.GetLocation();
		const FVector Heading = PredatorHeadings[i];

		int32 Target = INDEX_NONE;
		if (State.EatCooldown <= 0.0f)
		{
			float Best = TNumericLimits<float>::Max();
			for (int32 j = 0; j < Herbivores.Num(); ++j)
			{
				if (HerbHide[j] <= 0.0f) { continue; }
				const float Perceived = FVector::Dist2D(Pos, HerbPos[j]) * HerbHide[j];
				if (Perceived > ViewRadius || Perceived >= Best) { continue; }
				if (!InFov(Pos, Heading, HerbPos[j], CosHalfFov)) { continue; }
				Best = Perceived;
				Target = j;
			}
		}

		FVector Dir = Target != INDEX_NONE
						  ? (HerbPos[Target] - Pos).GetSafeNormal2D()
						  : (bStepBoundary ? Rotate2D(Heading, SimRand.FRandRange(-Turn, Turn))
										   : Heading);
		// 표적과 정확히 겹치면 방향이 0 이 된다. 그대로 두면 시야 판정이 영영 실패해 멈춘다.
		if (Dir.IsNearlyZero())
		{
			Dir = Heading;
		}

		FVector NewPos = Pos + Dir * Speed * DeltaSeconds;
		for (int32 Axis = 0; Axis < 2; ++Axis)
		{
			if (NewPos[Axis] < -Extent || NewPos[Axis] > Extent)
			{
				Dir[Axis] = -Dir[Axis];
				NewPos[Axis] = FMath::Clamp(NewPos[Axis], -Extent, Extent);
			}
		}

		T.SetLocation(NewPos);
		EM->GetFragmentDataChecked<FMassVelocityFragment>(Predators[i]).Value = Dir * Speed;
		PredatorHeadings[i] = Dir.GetSafeNormal2D();
		PredatorTargets[i] = Target;
	}
}

void AEcoPolicyTestSpawner::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bSpawned)
	{
		return;
	}
	// 이번 틱 PrePhysics 에서 UEcoPredationProcessor 가 잡은 개체부터 되살린다.
	RespawnCaught();
	MovePredators(DeltaSeconds);

	if (bDrawDebug)
	{
		DrawDebug();
	}
	if (LogInterval > 0.0f)
	{
		LogAccumulator += DeltaSeconds;
		if (LogAccumulator >= LogInterval)
		{
			LogAccumulator = 0.0f;
			LogSummary();
			CatchesSinceLog = 0;
		}
	}
}

void AEcoPolicyTestSpawner::DrawDebug() const
{
	const UWorld* World = GetWorld();
	FMassEntityManager* EM = GetEntityManager(World);
	if (!EM) { return; }

	// --- 초식: 점(화면 픽셀, 색 = cohesion) + 진행 방향 선 + 도주 중이면 노란 선 ---
	for (const FMassEntityHandle& E : Herbivores)
	{
		if (!EM->IsEntityValid(E)) { continue; }
		const FVector Top =
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation() + DrawLift;
		const FEcoPolicyActionV1& A = EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action;
		const FEcoSteeringGeometryFragment& G =
			EM->GetFragmentDataChecked<FEcoSteeringGeometryFragment>(E);
		const FVector V = EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value;
		const FColor Color = CohesionColor(A.Cohesion);

		if (HerbivorePointSize > 0.0f)
		{
			DrawDebugPoint(World, Top, HerbivorePointSize, Color, false, -1.0f, 0);
		}
		if (HeadingLineLength > 0.0f && !V.IsNearlyZero())
		{
			DrawDebugLine(World, Top, Top + V.GetSafeNormal2D() * HeadingLineLength, Color,
						  false, -1.0f, 0, 3.0f);
		}
		// §3.3 도주 분기가 켜진 개체 — 포식자 반대쪽으로 굵게.
		if (G.DistPredMin < A.FleeDist * EcoBehaviorConfig::SeeRadiusCm)
		{
			DrawDebugLine(World, Top, Top + G.AwayFromPred * HeadingLineLength * 1.5f,
						  FColor::Yellow, false, -1.0f, 0, 8.0f);
		}
	}

	// --- 포식자: X(빨강 = 사냥 중, 회색 = 식사 중) + 시야 부채꼴 + 추격선 ---
	const float HalfFov = FMath::DegreesToRadians(EcoBehaviorConfig::PredFovDeg) * 0.5f;
	for (int32 i = 0; i < Predators.Num(); ++i)
	{
		const FMassEntityHandle& E = Predators[i];
		if (!EM->IsEntityValid(E)) { continue; }
		const FVector Pos =
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation() + DrawLift;
		const bool bHunting = EM->GetFragmentDataChecked<FEcoPredatorStateFragment>(E).EatCooldown <= 0.0f;
		const FColor Mark = bHunting ? FColor::Red : FColor(150, 150, 150);

		const float S = PredatorMarkSize;
		DrawDebugLine(World, Pos + FVector(-S, -S, 0), Pos + FVector(S, S, 0), Mark, false, -1.0f, 0, 12.0f);
		DrawDebugLine(World, Pos + FVector(-S, S, 0), Pos + FVector(S, -S, 0), Mark, false, -1.0f, 0, 12.0f);

		if (!bDrawPredatorView) { continue; }
		DrawFan(World, Pos, PredatorHeadings[i], EcoBehaviorConfig::PredViewRadiusCm, HalfFov,
				bHunting ? FColor(170, 40, 40) : FColor(110, 110, 110), 3.0f);

		const int32 T = PredatorTargets.IsValidIndex(i) ? PredatorTargets[i] : INDEX_NONE;
		if (T != INDEX_NONE && EM->IsEntityValid(Herbivores[T]))
		{
			const FVector TargetPos =
				EM->GetFragmentDataChecked<FTransformFragment>(Herbivores[T]).GetTransform().GetLocation()
				+ DrawLift;
			DrawDebugLine(World, Pos, TargetPos, FColor::Red, false, -1.0f, 0, 5.0f);
		}
	}

	// --- 은신처: 파란 두 겹 원 (파이썬 replay.py 의 은신처 테두리색과 같다) ---
	// 판정은 IsInCover() 가 하고 여기서는 보이게만 한다. 더미가 지금 쓰이는 은신처 제공자일
	// 때만 그린다 — 월드팀 구현으로 바뀌면 더미의 위치는 판정과 무관해지기 때문이다.
	const UEcoWorldProviderRegistry* Registry = World->GetSubsystem<UEcoWorldProviderRegistry>();
	const UEcoDummyWorldProviderSubsystem* Dummy = World->GetSubsystem<UEcoDummyWorldProviderSubsystem>();
	if (Registry && Dummy
		&& Registry->GetCoverProvider() == static_cast<const IEcoWorldCoverProvider*>(Dummy))
	{
		const FColor CoverColor(85, 102, 170);
		const float R = Dummy->GetCoverRadius();
		for (const FVector& C : Dummy->GetCoverPoints())
		{
			const FVector P(C.X, C.Y, DrawLift.Z);
			DrawDebugCircle(World, P, R, 48, CoverColor, false, -1.0f, 0, 10.0f,
							FVector(1, 0, 0), FVector(0, 1, 0), false);
			DrawDebugCircle(World, P, R * 0.55f, 32, CoverColor, false, -1.0f, 0, 4.0f,
							FVector(1, 0, 0), FVector(0, 1, 0), false);
		}
	}

	// --- 경계: 스폰 반경(회색 원) + 시뮬레이션 경계(검은 사각형, 초식이 여기서 clamp 된다) ---
	DrawDebugCircle(World, GetActorLocation() + DrawLift, SpawnRadius, 64, FColor(90, 90, 90),
					false, -1.0f, 0, 5.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
	const float Extent = GetWorldExtent();
	DrawDebugBox(World, DrawLift, FVector(Extent, Extent, 0.0f), FColor(30, 30, 30),
				 false, -1.0f, 0, 10.0f);
}

void AEcoPolicyTestSpawner::LogSummary() const
{
	FMassEntityManager* EM = GetEntityManager(GetWorld());
	if (!EM) { return; }

	int32 Moving = 0, Fleeing = 0, SawPredator = 0;
	float SumCohesion = 0.0f, SumFlee = 0.0f, SumForage = 0.0f, SumCover = 0.0f;
	int32 N = 0;

	for (const FMassEntityHandle& E : Herbivores)
	{
		if (!EM->IsEntityValid(E)) { continue; }
		++N;
		const FEcoPolicyActionV1& A = EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action;
		const FEcoSteeringGeometryFragment& G =
			EM->GetFragmentDataChecked<FEcoSteeringGeometryFragment>(E);
		SumForage += A.Forage; SumCohesion += A.Cohesion; SumFlee += A.FleeDist; SumCover += A.Cover;
		if (!EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value.IsNearlyZero()) { ++Moving; }
		if (G.PredatorCount > 0) { ++SawPredator; }
		if (G.DistPredMin < A.FleeDist * EcoBehaviorConfig::SeeRadiusCm) { ++Fleeing; }
	}
	if (N == 0) { return; }

	static IConsoleVariable* CVar =
		IConsoleManager::Get().FindConsoleVariable(TEXT("eco.UseLearnedPolicy"));
	const int32 Mode = CVar ? CVar->GetInt() : -1;

	UE_LOG(LogTemp, Log,
		   TEXT("[Eco] 정책=%s | 개체 %d, 이동 %d, 포식자 본 개체 %d, 도주 %d | 포획 %d (누적 %d) | "
				"forage %.2f cohesion %.2f flee %.2f cover %.2f"),
		   Mode == 1 ? TEXT("학습") : (Mode == 0 ? TEXT("Utility") : TEXT("?")),
		   N, Moving, SawPredator, Fleeing, CatchesSinceLog, TotalCatches,
		   SumForage / N, SumCohesion / N, SumFlee / N, SumCover / N);
}
