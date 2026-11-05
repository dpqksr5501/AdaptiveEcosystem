// 섬 무대 모드 (2026-11-05, Docs/RL_Policy/ISLAND_STAGE.md) — 팀 섬 맵 전체에서 사슴·늑대 시험.
//
// 켜는 곳: 맵 조정자 bV3IslandStage (복사 맵 /Game/EcoTest/Maps/LV_EcoV3_Island 만 참) 또는 콘솔 eco.IntegratedV3.Island 1 (명령줄 -EcoV3Island=1).
// 끄면(기본) 이 파일의 어떤 함수도 세계·조정자를 바꾸지 않는다 — 다른 맵은 지금 그대로다.
//
// 흐름 (서버·단독):
//   1. OnWorldBeginPlay → IslandResolve: 조정자 그룹이 섬 지역(eco.IntegratedV3.IslandRegion, 기본 Island) 하나이고 서식지 스트리밍을 쓰면 켠다.
//   2. ApplyToSpawner → IslandPlanHints: 지역 상자로 섬 정사각(한 변 = 상자 가로 반폭 큰 쪽 × 2, 4 m 단위)을 정하고, 조정자 스트리밍 원천이 섬 전체를
//      불러오도록 정사각을 덮는 격자 '힌트 자리'를 그룹 시작 자리로 쓴다 (조정자는 시작 자리 둘레를 불러온다 — EcoCreatureIntegrationSpawner.cpp).
//   3. 조정자 시작 직전 (섬 전체가 불린 프레임, HandlePreStartTick → ValidateSpawnPointsNow → IslandValidateNow):
//      땅/물 지도 훑기(ScanIslandMask) → 무리 자리 고르기(꼬리표 EcoV3IslandHerd TargetPoint 또는 자동 PickHerdSites) → 자리마다 PlanStage(지금 무대 규칙 그대로,
//      시작 자리는 땅 칸만) → 그룹 하나에 합쳐 쓴다. 실패하면 팀 값으로 되돌린다.
//   4. TryCreateContexts: 지역 세계 하나 = 섬 정사각 + FWorldConfig::Island(땅/물 지도), 은신처는 무리 자리마다 (원이 땅 칸 위).
//   5. 그리는 단독·리슨 호스트: 몸 액터가 없는 먼 개체를 인스턴스 표식으로 (IslandTickMarkers, 4 Hz).
//
// 거부: 그룹이 여럿·섬 지역 없음·스트리밍 끔(지금 모드로 돈다), 땅이 1 % 밑·무리 자리 0(팀 값으로 되돌림), 스냅숏·숲 자람·시험용 나무.

#include "EcoPolicyV3IntegratedSubsystem.h"

#include "AI/Social/Shelter/EcoShelterAnchor.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Engine/StaticMesh.h"
#include "Engine/TargetPoint.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "Landscape.h"
#include "LandscapeProxy.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/App.h"
#include "World/EcologyRegion.h"

#include "EcoV3ObserverCamera.h"

namespace EcoV3IslandImpl
{
	static TAutoConsoleVariable<int32> CVarIsland(
		TEXT("eco.IntegratedV3.Island"), -1,
		TEXT("통합 v3 섬 무대 (11-05, ISLAND_STAGE.md). −1 = 맵 조정자 bV3IslandStage 를 따름 (기본 — 복사 맵 LV_EcoV3_Island 만 켬), 0 = 끔, 1 = 켬. ")
		TEXT("켜면 조정자 그룹 지역 하나가 섬 전체 정사각 세계가 되고, 시작 때 훑은 땅/물 지도(바다·호수·가파름·숲·큰 바위)가 벽 대신 못 가는 곳이다. ")
		TEXT("사슴·늑대는 무리 자리 여럿에서 시작해 섬 어디든 다닌다. Play 전에 바꾼다. 명령줄 -EcoV3Island= 은 시작값."),
		ECVF_Default);
	static TAutoConsoleVariable<FString> CVarIslandRegion(
		TEXT("eco.IntegratedV3.IslandRegion"), TEXT("Island"),
		TEXT("섬 무대가 될 지역 이름 (조정자 그룹이 이 지역 하나여야 한다). Play 전에 바꾼다."), ECVF_Default);
	static TAutoConsoleVariable<int32> CVarIslandHerds(
		TEXT("eco.IntegratedV3.IslandHerds"), 4, TEXT("섬 무대 무리 자리 수 (1~8). Play 전에 바꾼다."), ECVF_Default);
	static TAutoConsoleVariable<int32> CVarIslandDeerPerHerd(
		TEXT("eco.IntegratedV3.IslandDeerPerHerd"), 120,
		TEXT("섬 무대 무리마다 사슴 (1~128 — 무리 자리 120 m 안 밀도가 학습 범위). 합계가 조정자 상한 512 를 넘으면 무리마다 하나씩 줄인다. Play 전에 바꾼다."),
		ECVF_Default);
	static TAutoConsoleVariable<int32> CVarIslandWolvesPerHerd(
		TEXT("eco.IntegratedV3.IslandWolvesPerHerd"), 4, TEXT("섬 무대 무리마다 늑대 (0~12, 잠행·추격 번갈아). Play 전에 바꾼다."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarIslandHerdGapM(
		TEXT("eco.IntegratedV3.IslandHerdGapM"), 400.0f, TEXT("섬 무대 무리 자리 가운데끼리 가장 가까운 거리 (m). Play 전에 바꾼다."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarIslandHerdClearM(
		TEXT("eco.IntegratedV3.IslandHerdClearM"), 30.0f,
		TEXT("섬 무대 무리 자리 둘레 여유 (m — 자리 정사각이 해안·숲·호수에서 이만큼 더 떨어진다. 자리가 없으면 반씩 줄인다). Play 전에 바꾼다."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarIslandShoreM(
		TEXT("eco.IntegratedV3.IslandShoreM"), 0.5f, TEXT("섬 무대 땅 지도: 바다·호수 수면 위 이 높이(m)까지는 물. Play 전에 바꾼다."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarIslandSlopeZ(
		TEXT("eco.IntegratedV3.IslandSlopeZ"), 0.65f, TEXT("섬 무대 땅 지도: 가파름 문턱 (법선 Z — 팀 이동 제약과 같은 값). Play 전에 바꾼다."), ECVF_Default);
	static TAutoConsoleVariable<int32> CVarIslandForest(
		TEXT("eco.IntegratedV3.IslandForest"), 1,
		TEXT("섬 무대 땅 지도: 1 = 소나무 칸 막힘 (1단계, 기본), 0 = 숲을 무시 (나무 사이를 지나감 — 비교용). Play 전에 바꾼다."), ECVF_Default);
	static TAutoConsoleVariable<int32> CVarIslandMarkers(
		TEXT("eco.IntegratedV3.IslandMarkers"), 1,
		TEXT("섬 무대 먼 개체 표식 (1 = 켬 — 몸 액터가 없는 산 개체를 작은 공으로: 사슴 갈색·쫓기는 사슴 빨강·늑대 회색, 그리는 단독·리슨 호스트만). 언제든 바꿀 수 있다."),
		ECVF_Default);

	/** 무리 자리 꼬리표 (복사 맵에 사람이 놓은 TargetPoint — 이름 차례). */
	const FName kHerdTag(TEXT("EcoV3IslandHerd"));
	/** 큰 바위·나무로 보는 메시 이름 조각 (소문자). */
	const TCHAR* const kTreeWords[] = {TEXT("pine"), TEXT("tree"), TEXT("spruce"), TEXT("birch"), TEXT("beech"), TEXT("oak")};
	const TCHAR* const kRockWords[] = {TEXT("rock"), TEXT("cliff"), TEXT("boulder")};

	AEcologyRegion* FindRegion(UWorld* World, FName RegionId)
	{
		for (TActorIterator<AEcologyRegion> It(World); World && It; ++It)
		{
			if (It->RegionId == RegionId)
			{
				return *It;
			}
		}
		return nullptr;
	}

	/** 조정자와 같은 지면 검사 (두 번 검사해 1 cm 안 — 통합 서브시스템 ProjectLikeCoordinator 와 같다). */
	bool ProjectLikeCoordinator(UWorld& World, const FVector& Hint, FVector& Out)
	{
		FVector G;
		FVector G2;
		if (!EcoCreatureMovement::ProjectSpawnPoint(World, Hint, G) || !EcoCreatureMovement::ProjectSpawnPoint(World, G, G2) || !G2.Equals(G, 1.0))
		{
			return false;
		}
		Out = G2;
		return true;
	}

	void WritePlanToGroup(const FEcoV3StagePlan& Plan, FEcoCreatureSpawnGroup& G)
	{
		G.Herbivores = Plan.DeerPoints.Num();
		G.Wolves = Plan.WolfPoints.Num();
		G.HerbivoreSpawnPoints = Plan.DeerPoints;
		G.WolfSpawnPoints = Plan.WolfPoints;
		G.Schedule.RegionPopulationLimit = FMath::Max(G.Schedule.RegionPopulationLimit, G.Herbivores + G.Wolves);
	}

	bool AnyWord(const FString& Lower, TConstArrayView<const TCHAR*> Words)
	{
		for (const TCHAR* W : Words)
		{
			if (Lower.Contains(W))
			{
				return true;
			}
		}
		return false;
	}

	double Km2(int64 Cells, double CellUnits)
	{
		const double CellM = CellUnits * EcoRepertoireV3::kUnitCm / 100.0;
		return static_cast<double>(Cells) * CellM * CellM / 1.0e6;
	}
}

// -----------------------------------------------------------------------------
// 설정·켜기
// -----------------------------------------------------------------------------

FEcoV3IslandSettings FEcoV3IslandSettings::FromConsole()
{
	using namespace EcoV3IslandImpl;
	(void)UEcoPolicyV3IntegratedSubsystem::GetRequestedVersion();   // 명령줄 → 콘솔 시작값 (처음 한 번)
	auto Finite = [](float V, double Def, double Lo, double Hi) { return FMath::IsFinite(V) ? FMath::Clamp(static_cast<double>(V), Lo, Hi) : Def; };
	FEcoV3IslandSettings S;
	S.Mode = FMath::Clamp(CVarIsland.GetValueOnGameThread(), -1, 1);
	const FString Region = CVarIslandRegion.GetValueOnGameThread().TrimStartAndEnd();
	S.Region = Region.IsEmpty() ? FName(TEXT("Island")) : FName(*Region);
	S.Herds = FMath::Clamp(CVarIslandHerds.GetValueOnGameThread(), 1, 8);
	S.DeerPerHerd = FMath::Clamp(CVarIslandDeerPerHerd.GetValueOnGameThread(), 1, FEcoV3IntegratedSettings::kTrainDeer);
	S.WolvesPerHerd = FMath::Clamp(CVarIslandWolvesPerHerd.GetValueOnGameThread(), 0, 12);
	S.HerdGapM = Finite(CVarIslandHerdGapM.GetValueOnGameThread(), 400.0, 0.0, 5000.0);
	S.HerdClearM = Finite(CVarIslandHerdClearM.GetValueOnGameThread(), 30.0, 0.0, 200.0);
	S.ShoreM = Finite(CVarIslandShoreM.GetValueOnGameThread(), 0.5, 0.0, 10.0);
	S.SlopeZ = Finite(CVarIslandSlopeZ.GetValueOnGameThread(), 0.65, 0.0, 1.0);
	S.bForest = CVarIslandForest.GetValueOnGameThread() != 0;
	S.bMarkers = CVarIslandMarkers.GetValueOnGameThread() != 0;
	return S;
}

bool UEcoPolicyV3IntegratedSubsystem::IslandResolve(const AEcoCreatureIntegrationSpawner& S)
{
	using namespace EcoV3IslandImpl;
	const FEcoV3IslandSettings& Is = IslandSettings;
	const bool bWant = Is.Mode == 1 || (Is.Mode < 0 && S.bV3IslandStage);
	if (!bWant)
	{
		if (S.bV3IslandStage)
		{
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 섬 무대: 끔 — 맵 조정자는 섬 무대(bV3IslandStage)지만 eco.IntegratedV3.Island 0 이라 지금 통합 v3 무대(120 m 정사각)로 돈다"));
		}
		return false;
	}
	auto Refuse = [&Is](const FString& Why)
	{
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 섬 무대: 거부 — %s. 지금 통합 v3 무대로 돈다 (지역 %s)"), *Why, *Is.Region.ToString());
		return false;
	};
	if (S.Groups.Num() != 1 || S.Groups[0].RegionId != Is.Region)
	{
		FString Have;
		for (const FEcoCreatureSpawnGroup& G : S.Groups)
		{
			Have += (Have.IsEmpty() ? TEXT("") : TEXT("·")) + G.RegionId.ToString();
		}
		return Refuse(FString::Printf(TEXT("조정자 그룹이 섬 지역 하나여야 한다 (있는 그룹: %s — eco.IntegratedV3.IslandRegion)"), Have.IsEmpty() ? TEXT("없음") : *Have));
	}
	const AEcologyRegion* Region = FindRegion(GetWorld(), Is.Region);
	if (!Region || !Region->RegionBounds)
	{
		return Refuse(TEXT("섬 지역(AEcologyRegion)을 찾지 못했다"));
	}
	if (!S.bUseHabitatStreaming)
	{
		return Refuse(TEXT("조정자 서식지 스트리밍이 꺼져 있다 — 섬 전체를 불러온 뒤 땅/물 지도를 훑어야 한다"));
	}
	UE_LOG(LogEcoPolicyV3I, Log,
		   TEXT("[EcoV3I] 섬 무대: 켬 (%s) — 지역 %s 하나가 섬 전체 정사각 세계, 벽 대신 땅/물 지도 (바다·호수·가파름 %s·%s·큰 바위) | 무리 자리 %d × (사슴 %d·늑대 %d), ")
			   TEXT("자리끼리 %.0f m 이상·둘레 여유 %.0f m | 물 = 수면 + %.1f m 까지 | 먼 표식 %s | 스냅숏·적응 고리·숲 자람은 거부 (파이썬 거울 없음 — 언리얼 전용 시험 무대)"),
		   Is.Mode == 1 ? TEXT("eco.IntegratedV3.Island 1") : TEXT("맵 조정자 bV3IslandStage"), *Is.Region.ToString(),
		   *FString::Printf(TEXT("(법선 Z < %.2f)"), Is.SlopeZ), Is.bForest ? TEXT("소나무 숲") : TEXT("숲 무시 (eco.IntegratedV3.IslandForest 0)"), Is.Herds,
		   Is.DeerPerHerd, Is.WolvesPerHerd, Is.HerdGapM, Is.HerdClearM, Is.ShoreM, Is.bMarkers ? TEXT("켬") : TEXT("끔"));
	return true;
}

// -----------------------------------------------------------------------------
// 조정자 바꾸기 (BeginPlay): 섬 정사각 + 스트리밍 힌트 자리
// -----------------------------------------------------------------------------

bool UEcoPolicyV3IntegratedSubsystem::IslandPlanHints(AEcoCreatureIntegrationSpawner& S, TArray<FEcoV3StagePlan>& NewPlans,
													  TArray<FEcoCreatureSpawnGroup>& NewGroups, int64& OutTotal)
{
	using namespace EcoV3IslandImpl;
	using EcoRepertoireV3::kUnitCm;
	UWorld* World = GetWorld();
	if (!World || NewGroups.Num() != 1)
	{
		return false;
	}
	FEcoCreatureSpawnGroup& G = NewGroups[0];
	AEcologyRegion* Region = FindRegion(World, G.RegionId);
	if (!Region || !Region->RegionBounds)
	{
		UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 섬 무대: 지역 %s 를 찾지 못했다"), *G.RegionId.ToString());
		return false;
	}
	// 섬 정사각 = 지역 상자 (가로 반폭 큰 쪽) — 칸(4 m)의 배수로 올리고 120 m ~ 4 km 로 자른다
	const FVector Center = Region->RegionBounds->GetComponentLocation();
	const FVector Ext = Region->RegionBounds->GetScaledBoxExtent();
	const double CellCm = 2.0 * kUnitCm;
	double Side = 2.0 * FMath::Max(Ext.X, Ext.Y);
	Side = FMath::Clamp(FMath::CeilToDouble(Side / CellCm) * CellCm, 60.0 * kUnitCm, 2000.0 * kUnitCm);
	IslandSizeUnits = Side / kUnitCm;
	IslandOriginCm = FVector(Center.X - 0.5 * Side, Center.Y - 0.5 * Side, Center.Z);

	// 수: 무리 × (사슴 + 늑대) ≤ 조정자 상한 512 (넘으면 무리마다 사슴을 하나씩 줄인다)
	const int32 H = IslandSettings.Herds;
	int32 D = IslandSettings.DeerPerHerd;
	const int32 K = IslandSettings.WolvesPerHerd;
	while (H * (D + K) > 512 && D > 1)
	{
		--D;
	}
	if (H * (D + K) > 512)
	{
		UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 섬 무대: 무리 %d × 늑대 %d 만으로 조정자 상한 512 를 넘는다"), H, K);
		return false;
	}
	IslandSettings.DeerPerHerd = D;
	const int32 Total = H * (D + K);

	// 스트리밍 힌트 격자: 조정자 원천은 시작 자리마다 반지름 Rs 원 — 간격 ≤ Rs·√2 면 정사각을 다 덮는다 (1.4 배로 여유)
	const double Rs = FMath::Max(3000.0, static_cast<double>(S.HabitatStreamingRadius));
	int32 Nside = FMath::Max(1, FMath::CeilToInt32(Side / (1.4 * Rs)));
	if (Nside * Nside > Total)
	{
		const int32 Fit = FMath::Max(1, FMath::FloorToInt32(FMath::Sqrt(static_cast<double>(Total))));
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 섬 무대: 스트리밍 힌트 %d×%d 가 시작 자리 수 %d 를 넘는다 — %d×%d 만 쓴다 (서식지 반지름 %.0f m 가 작다, 섬 일부가 덜 불릴 수 있다)"),
			   Nside, Nside, Total, Fit, Fit, Rs / 100.0);
		Nside = Fit;
	}
	TArray<FVector> Grid;
	for (int32 j = 0; j < Nside; ++j)
	{
		for (int32 i = 0; i < Nside; ++i)
		{
			Grid.Add(FVector(IslandOriginCm.X + (i + 0.5) * Side / Nside, IslandOriginCm.Y + (j + 0.5) * Side / Nside, Center.Z));
		}
	}
	FEcoV3StagePlan Plan;
	Plan.RegionId = G.RegionId;
	Plan.GroupIndex = 0;
	Plan.CenterCm = FVector(IslandOriginCm.X + 0.5 * Side, IslandOriginCm.Y + 0.5 * Side, Center.Z);
	Plan.SizeUnits = IslandSizeUnits;
	Plan.WantDeer = H * D;
	Plan.WantWolves = H * K;
	for (int32 k = 0; k < Plan.WantDeer; ++k)
	{
		Plan.DeerPoints.Add(Grid[k % Grid.Num()]);
	}
	for (int32 k = 0; k < Plan.WantWolves; ++k)
	{
		Plan.WolfPoints.Add(Grid[(Plan.WantDeer + k) % Grid.Num()]);
	}
	Plan.bStageInside = true;
	Plan.bGrounded = false;
	Plan.bComplete = true;
	WritePlanToGroup(Plan, G);
	NewPlans.Add(Plan);
	OutTotal = Total;
	return true;
}

// -----------------------------------------------------------------------------
// 땅/물 지도 훑기
// -----------------------------------------------------------------------------

std::shared_ptr<EcoV3Island::FLandMask> UEcoPolicyV3IntegratedSubsystem::ScanIslandMask(UWorld& World, const FVector& OriginCm, double SizeUnits,
																						const FEcoV3IslandSettings& S, FString& OutLine)
{
	using namespace EcoV3IslandImpl;
	using namespace EcoV3Island;
	using EcoRepertoireV3::kUnitCm;
	const double T0 = FPlatformTime::Seconds();
	auto M = std::make_shared<FLandMask>();
	M->Cell = 2.0;
	M->Gw = FMath::Clamp(FMath::RoundToInt32(SizeUnits / M->Cell), 1, 4000);
	const int32 G = M->Gw;
	const double CellCm = M->Cell * kUnitCm;
	const size_t Cells = static_cast<size_t>(G) * static_cast<size_t>(G);
	M->Kind.assign(Cells, kLand);

	// 1. 지형 높이 (충돌 높이장 — 물리 쿼리가 아니다): 칸 모서리 (G+1)² 와 가운데 G²
	TArray<ALandscapeProxy*> Lands;
	for (TActorIterator<ALandscape> It(&World); It; ++It)
	{
		Lands.Add(*It);
	}
	if (Lands.IsEmpty())
	{
		for (TActorIterator<ALandscapeProxy> It(&World); It; ++It)
		{
			Lands.Add(*It);
		}
	}
	auto HeightAt = [&Lands](double X, double Y, float& Z)
	{
		for (const ALandscapeProxy* L : Lands)
		{
			if (const TOptional<float> H = L->GetHeightAtLocation(FVector(X, Y, 0.0)); H.IsSet())
			{
				Z = H.GetValue();
				return true;
			}
		}
		return false;
	};
	const float Nan = std::numeric_limits<float>::quiet_NaN();
	const int32 Gc = G + 1;
	TArray<float> Corner;
	Corner.Init(Nan, Gc * Gc);
	for (int32 y = 0; y <= G; ++y)
	{
		for (int32 x = 0; x <= G; ++x)
		{
			float Z = 0.0f;
			if (HeightAt(OriginCm.X + x * CellCm, OriginCm.Y + y * CellCm, Z))
			{
				Corner[y * Gc + x] = Z;
			}
		}
	}
	TArray<float> Mid;
	Mid.Init(Nan, G * G);
	for (int32 y = 0; y < G; ++y)
	{
		for (int32 x = 0; x < G; ++x)
		{
			float Z = 0.0f;
			if (HeightAt(OriginCm.X + (x + 0.5) * CellCm, OriginCm.Y + (y + 0.5) * CellCm, Z))
			{
				Mid[y * G + x] = Z;
			}
		}
	}
	const double TH = FPlatformTime::Seconds();

	// 2. 물 몸체 (클래스 이름 — 물 플러그인 모듈에 기대지 않는다): 바다 = 수면 높이, 호수·강 = 충돌 컴포넌트 선 검사 (그 컴포넌트만 — 장면 쿼리 아님)
	const double ShoreCm = S.ShoreM * 100.0;
	double OceanZ = -std::numeric_limits<double>::infinity();
	int32 Oceans = 0;
	TArray<uint8> Lake;
	Lake.Init(0, G * G);
	int32 WaterBodies = 0;
	int64 WaterTraces = 0;
	TArray<AActor*> Waters;
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		const FString Cls = It->GetClass()->GetName();
		if (!Cls.StartsWith(TEXT("WaterBody")))
		{
			continue;
		}
		if (Cls.Contains(TEXT("Ocean")))
		{
			OceanZ = FMath::Max(OceanZ, It->GetActorLocation().Z);
			++Oceans;
		}
		else
		{
			Waters.Add(*It);
		}
	}
	Waters.Sort([](const AActor& A, const AActor& B) { return A.GetFName().LexicalLess(B.GetFName()); });
	for (AActor* A : Waters)
	{
		TArray<UPrimitiveComponent*> Prims;
		A->GetComponents(Prims);
		TArray<UPrimitiveComponent*> Hits;
		FBox Box(ForceInit);
		for (UPrimitiveComponent* C : Prims)
		{
			if (C && C->IsRegistered() && C->IsQueryCollisionEnabled())
			{
				Hits.Add(C);
				Box += C->Bounds.GetBox();
			}
		}
		if (Hits.IsEmpty() || !Box.IsValid)
		{
			continue;
		}
		++WaterBodies;
		const int32 X0 = FMath::Max(0, FMath::FloorToInt32((Box.Min.X - OriginCm.X) / CellCm));
		const int32 Y0 = FMath::Max(0, FMath::FloorToInt32((Box.Min.Y - OriginCm.Y) / CellCm));
		const int32 X1 = FMath::Min(G - 1, FMath::FloorToInt32((Box.Max.X - OriginCm.X) / CellCm));
		const int32 Y1 = FMath::Min(G - 1, FMath::FloorToInt32((Box.Max.Y - OriginCm.Y) / CellCm));
		FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3IslandWater), true);
		for (int32 y = Y0; y <= Y1; ++y)
		{
			for (int32 x = X0; x <= X1; ++x)
			{
				const float Ground = Mid[y * G + x];
				if (FMath::IsNaN(Ground))
				{
					continue;
				}
				const double Px = OriginCm.X + (x + 0.5) * CellCm;
				const double Py = OriginCm.Y + (y + 0.5) * CellCm;
				const FVector Start(Px, Py, Box.Max.Z + 100.0);
				const FVector End(Px, Py, FMath::Min(Box.Min.Z, static_cast<double>(Ground)) - 100.0);
				double Surface = -std::numeric_limits<double>::infinity();
				for (UPrimitiveComponent* C : Hits)
				{
					FHitResult Hit;
					++WaterTraces;
					if (C->LineTraceComponent(Hit, Start, End, Params))
					{
						Surface = FMath::Max(Surface, Hit.ImpactPoint.Z);
					}
				}
				if (FMath::IsFinite(Surface) && Ground < Surface + ShoreCm)
				{
					Lake[y * G + x] = 1;
				}
			}
		}
	}

	// 3. 나무·큰 바위 (인스턴스 메시 — 메시 이름으로 가른다). 은신처 장식은 뺀다
	TArray<uint8> Forest;
	Forest.Init(0, G * G);
	TArray<uint8> Rock;
	Rock.Init(0, G * G);
	int64 Trees = 0, Rocks = 0;
	const double TreeR = S.ForestRadiusM * 100.0;
	const double RockPad = S.RockMarginM * 100.0;
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		if (It->IsA<AEcoShelterAnchor>())
		{
			continue;
		}
		TArray<UInstancedStaticMeshComponent*> Isms;
		It->GetComponents(Isms);
		for (const UInstancedStaticMeshComponent* Ism : Isms)
		{
			const UStaticMesh* Mesh = Ism ? Ism->GetStaticMesh() : nullptr;
			if (!Mesh)
			{
				continue;
			}
			const FString Name = Mesh->GetName().ToLower();
			const bool bTree = AnyWord(Name, kTreeWords);
			const bool bRock = !bTree && AnyWord(Name, kRockWords);
			if ((!bTree || !S.bForest) && !bRock)
			{
				continue;
			}
			const FBox MeshBox = Mesh->GetBoundingBox();
			const int32 N = Ism->GetInstanceCount();
			for (int32 i = 0; i < N; ++i)
			{
				FTransform T;
				if (!Ism->GetInstanceTransform(i, T, /*bWorldSpace*/ true))
				{
					continue;
				}
				FBox B(ForceInit);
				if (bTree)
				{
					++Trees;
					const FVector L = T.GetLocation();
					B = FBox(L - FVector(TreeR, TreeR, 0.0), L + FVector(TreeR, TreeR, 0.0));
				}
				else
				{
					++Rocks;
					B = MeshBox.TransformBy(T).ExpandBy(FVector(RockPad, RockPad, 0.0));
				}
				const int32 X0 = FMath::Max(0, FMath::FloorToInt32((B.Min.X - OriginCm.X) / CellCm));
				const int32 Y0 = FMath::Max(0, FMath::FloorToInt32((B.Min.Y - OriginCm.Y) / CellCm));
				const int32 X1 = FMath::Min(G - 1, FMath::FloorToInt32((B.Max.X - OriginCm.X) / CellCm));
				const int32 Y1 = FMath::Min(G - 1, FMath::FloorToInt32((B.Max.Y - OriginCm.Y) / CellCm));
				const FVector L = T.GetLocation();
				for (int32 y = Y0; y <= Y1; ++y)
				{
					for (int32 x = X0; x <= X1; ++x)
					{
						const double Px = OriginCm.X + (x + 0.5) * CellCm;
						const double Py = OriginCm.Y + (y + 0.5) * CellCm;
						if (bTree)
						{
							if (FMath::Square(Px - L.X) + FMath::Square(Py - L.Y) <= TreeR * TreeR)
							{
								Forest[y * G + x] = 1;
							}
						}
						else if (Px >= B.Min.X && Px <= B.Max.X && Py >= B.Min.Y && Py <= B.Max.Y)
						{
							Rock[y * G + x] = 1;
						}
					}
				}
			}
		}
	}

	// 4. 칸 종류 (위에서부터 먼저 맞는 것): 지형 없음 → 바다 → 호수·강 → 가파름 → 숲 → 바위 → 땅
	for (int32 y = 0; y < G; ++y)
	{
		for (int32 x = 0; x < G; ++x)
		{
			const int32 k = y * G + x;
			const float Zc = Mid[k];
			uint8 Kind = kLand;
			if (FMath::IsNaN(Zc))
			{
				Kind = kNoGround;
			}
			else if (Oceans > 0 && Zc <= OceanZ + ShoreCm)
			{
				Kind = kSea;
			}
			else if (Lake[k])
			{
				Kind = kLake;
			}
			else
			{
				const float H00 = Corner[y * Gc + x], H10 = Corner[y * Gc + x + 1], H01 = Corner[(y + 1) * Gc + x], H11 = Corner[(y + 1) * Gc + x + 1];
				bool bSteep = false;
				if (!FMath::IsNaN(H00) && !FMath::IsNaN(H10) && !FMath::IsNaN(H01) && !FMath::IsNaN(H11))
				{
					const double Dzdx = ((H10 + H11) - (H00 + H01)) / (2.0 * CellCm);
					const double Dzdy = ((H01 + H11) - (H00 + H10)) / (2.0 * CellCm);
					// 두 삼각형의 기울기도 본다 (한 칸 안의 꺾인 비탈)
					const double A1x = (H10 - H00) / CellCm, A1y = (H01 - H00) / CellCm;
					const double A2x = (H11 - H01) / CellCm, A2y = (H11 - H10) / CellCm;
					const double G2 = FMath::Max3(Dzdx * Dzdx + Dzdy * Dzdy, A1x * A1x + A1y * A1y, A2x * A2x + A2y * A2y);
					bSteep = 1.0 / FMath::Sqrt(1.0 + G2) < S.SlopeZ;
				}
				Kind = bSteep ? kSteep : Forest[k] ? kForest : Rock[k] ? kRock : kLand;
			}
			M->Kind[static_cast<size_t>(k)] = Kind;
		}
	}
	M->BuildDistance();
	{
		// 땅 칸 지형의 가장 높은 곳 (카메라 탑뷰 초점 — 초점이 땅 밑이면 가림 피하기가 카메라를 바닥으로 당긴다)
		double Top = -std::numeric_limits<double>::infinity();
		for (int32 k = 0; k < G * G; ++k)
		{
			if (M->Kind[static_cast<size_t>(k)] == kLand && !FMath::IsNaN(Mid[k]))
			{
				Top = FMath::Max(Top, static_cast<double>(Mid[k]));
			}
		}
		M->LandTopZ = FMath::IsFinite(Top) ? Top : OriginCm.Z;
	}
	const double T1 = FPlatformTime::Seconds();

	int64 Count[kNumKinds] = {};
	for (const uint8 V : M->Kind)
	{
		++Count[V < kNumKinds ? V : kNoGround];
	}
	double Bx0 = 0, By0 = 0, Bx1 = 0, By1 = 0;
	const bool bLand = M->LandBounds(Bx0, By0, Bx1, By1);
	const double MPerU = kUnitCm / 100.0;
	FString Kinds;
	for (int32 k = 0; k < kNumKinds; ++k)
	{
		Kinds += FString::Printf(TEXT("%s%s %lld"), k == 0 ? TEXT("") : TEXT("·"), UTF8_TO_TCHAR(KindNameKoUtf8(k)), static_cast<long long>(Count[k]));
	}
	OutLine = FString::Printf(
		TEXT("[EcoV3I] 섬 무대 | 땅 지도 %d×%d (%.0f m) | %s | 땅 %.3f km²%s | 바다 수면 %s · 호수·강 물 몸체 %d (선 검사 %lld) · 나무 인스턴스 %lld%s · 큰 바위 %lld | ")
			TEXT("지문 %016llx | 훑기 %.2f초 (높이 %.2f초)"),
		G, G, CellCm / 100.0, *Kinds, Km2(Count[kLand], M->Cell),
		bLand ? *FString::Printf(TEXT(" · 땅 경계 x %.0f ~ %.0f m, y %.0f ~ %.0f m"), (OriginCm.X + Bx0 * kUnitCm) / 100.0, (OriginCm.X + Bx1 * kUnitCm) / 100.0,
								 (OriginCm.Y + By0 * kUnitCm) / 100.0, (OriginCm.Y + By1 * kUnitCm) / 100.0)
			  : TEXT(" · 땅 없음"),
		Oceans > 0 ? *FString::Printf(TEXT("%.2f m"), OceanZ / 100.0) : TEXT("없음"), WaterBodies, static_cast<long long>(WaterTraces), static_cast<long long>(Trees),
		S.bForest ? TEXT("") : TEXT(" (숲 무시)"), static_cast<long long>(Rocks), static_cast<unsigned long long>(M->Fingerprint()), T1 - T0, TH - T0);
	(void)MPerU;
	return M;
}

// -----------------------------------------------------------------------------
// 시작 직전: 땅 지도 → 무리 자리 → 시작 자리
// -----------------------------------------------------------------------------

bool UEcoPolicyV3IntegratedSubsystem::IslandValidateNow()
{
	using namespace EcoV3IslandImpl;
	using EcoRepertoireV3::kUnitCm;
	AEcoCreatureIntegrationSpawner* S = Spawner.Get();
	UWorld* World = GetWorld();
	if (!S || !World || Plans.Num() != 1 || !S->Groups.IsValidIndex(Plans[0].GroupIndex))
	{
		RestoreTeamValues(TEXT("섬 무대: 계획·그룹을 찾지 못했다"));
		return false;
	}
	FEcoCreatureSpawnGroup& G = S->Groups[Plans[0].GroupIndex];
	AEcologyRegion* Region = FindRegion(World, G.RegionId);
	if (!Region)
	{
		RestoreTeamValues(TEXT("섬 무대: 지역을 찾지 못했다"));
		return false;
	}
	if (!IslandMask)
	{
		FString Line;
		IslandMask = ScanIslandMask(*World, IslandOriginCm, IslandSizeUnits, IslandSettings, Line);
		IslandScanLine = Line;
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("%s"), *Line);
	}
	const EcoV3Island::FLandMask& M = *IslandMask;
	const int64 Land = M.Count(EcoV3Island::kLand);
	if (!M.Valid() || Land * 100 < static_cast<int64>(M.Kind.size()))
	{
		UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 섬 무대: 땅 칸이 %lld/%d (1 %% 밑) — 지형이 덜 불렸거나 섬이 아니다"), static_cast<long long>(Land),
			   static_cast<int32>(M.Kind.size()));
		RestoreTeamValues(TEXT("섬 무대: 땅/물 지도에 땅이 너무 적다 (스트리밍 실패로 본다)"));
		return false;
	}

	// 무리 자리: 사람이 놓은 TargetPoint(꼬리표 EcoV3IslandHerd, 이름 차례) 또는 자동 (가장 먼 점 고르기)
	const double HerdUnits = FMath::Clamp(Settings.StageSizeUnits, 60.0, 110.0);
	TArray<FVector2D> Sites;   // 단위
	TArray<ATargetPoint*> Points;
	for (TActorIterator<ATargetPoint> It(World); It; ++It)
	{
		if (It->Tags.Contains(kHerdTag))
		{
			Points.Add(*It);
		}
	}
	Points.Sort([](const ATargetPoint& A, const ATargetPoint& B) { return A.GetFName().LexicalLess(B.GetFName()); });
	if (!Points.IsEmpty())
	{
		for (int32 i = 0; i < Points.Num() && Sites.Num() < IslandSettings.Herds; ++i)
		{
			const FVector P = Points[i]->GetActorLocation();
			Sites.Add(FVector2D((P.X - IslandOriginCm.X) / kUnitCm, (P.Y - IslandOriginCm.Y) / kUnitCm));
		}
		IslandSiteLine = FString::Printf(TEXT("사람이 놓은 TargetPoint (꼬리표 %s) %d 개 가운데 %d"), *kHerdTag.ToString(), Points.Num(), Sites.Num());
	}
	else
	{
		EcoV3Island::FSiteParams Sp;
		Sp.SizeUnits = HerdUnits;
		Sp.ClearUnits = IslandSettings.HerdClearM * 100.0 / kUnitCm;
		Sp.GapUnits = IslandSettings.HerdGapM * 100.0 / kUnitCm;
		Sp.Count = IslandSettings.Herds;
		M.LandCentroid(Sp.PrefX, Sp.PrefY);
		const EcoV3Island::FSiteResult R = EcoV3Island::PickHerdSites(M, Sp);
		for (size_t i = 0; i + 1 < R.Sites.size(); i += 2)
		{
			Sites.Add(FVector2D(R.Sites[i], R.Sites[i + 1]));
		}
		IslandSiteLine = FString::Printf(TEXT("자동 (후보 %lld — 자리 정사각 %.0f m 에 둘레 여유 %.0f m 가 모두 땅, 섬 땅 무게중심에서 가장 먼 점 고르기, 자리끼리 %.0f m 이상)"),
										 static_cast<long long>(R.Candidates), HerdUnits * kUnitCm / 100.0, R.ClearUsed * kUnitCm / 100.0, IslandSettings.HerdGapM);
	}
	if (Sites.IsEmpty())
	{
		RestoreTeamValues(TEXT("섬 무대: 무리 자리를 하나도 찾지 못했다"));
		return false;
	}
	if (Sites.Num() < IslandSettings.Herds)
	{
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 섬 무대: 무리 자리가 %d/%d 라 그 수로 시작한다 (%s)"), Sites.Num(), IslandSettings.Herds, *IslandSiteLine);
	}

	// 자리마다 지금 무대 규칙 그대로 (늑대 모서리 쪽·사슴 고르게·간격·지면 검사) + 시작 자리는 땅 칸, 해안에서 2 m 넘게
	const std::shared_ptr<EcoV3Island::FLandMask> MaskRef = IslandMask;
	const FVector Origin = IslandOriginCm;
	auto Contains = [Region, MaskRef, Origin](const FVector& P)
	{
		if (!Region->ContainsPosition(P))
		{
			return false;
		}
		const double Ux = (P.X - Origin.X) / EcoRepertoireV3::kUnitCm;
		const double Uy = (P.Y - Origin.Y) / EcoRepertoireV3::kUnitCm;
		return MaskRef->IsOpen(Ux, Uy) && MaskRef->ShoreDist(Ux, Uy) >= 1.0;
	};
	auto Project = [World](const FVector& Hint, FVector& Out) { return ProjectLikeCoordinator(*World, Hint, Out); };
	const double HintZ = Region->RegionBounds ? Region->RegionBounds->GetComponentLocation().Z : Origin.Z;
	IslandHerdPlans.Reset();
	FEcoV3StagePlan Merged = Plans[0];
	Merged.DeerPoints.Reset();
	Merged.WolfPoints.Reset();
	Merged.WantDeer = 0;
	Merged.WantWolves = 0;
	Merged.bComplete = true;
	FString Summary;
	for (int32 h = 0; h < Sites.Num(); ++h)
	{
		const FVector C(Origin.X + Sites[h].X * kUnitCm, Origin.Y + Sites[h].Y * kUnitCm, HintZ);
		FEcoV3StagePlan Hp;
		PlanStage(G.RegionId, h, C, C, Settings, IslandSettings.DeerPerHerd, IslandSettings.WolvesPerHerd, true, Contains, Project, Hp, nullptr);
		const bool bAccept = Hp.bComplete || (Hp.WolfPoints.Num() == Hp.WantWolves && Hp.DeerPoints.Num() >= FMath::Min(Hp.WantDeer, FMath::Max(4, Hp.WantDeer / 2)));
		Summary += FString::Printf(TEXT(" | 자리 %d (%.0f, %.0f) m 사슴 %d/%d 늑대 %d/%d%s"), h + 1, C.X / 100.0, C.Y / 100.0, Hp.DeerPoints.Num(), Hp.WantDeer,
								   Hp.WolfPoints.Num(), Hp.WantWolves, bAccept ? (Hp.bComplete ? TEXT("") : TEXT(" (사슴 일부만)")) : TEXT(" — 버림"));
		if (!bAccept)
		{
			continue;
		}
		double Zs = 0.0;
		for (const FVector& P : Hp.DeerPoints)
		{
			Zs += P.Z;
		}
		Hp.CenterCm.Z = Hp.DeerPoints.IsEmpty() ? HintZ : Zs / Hp.DeerPoints.Num();
		Hp.bGrounded = true;
		Merged.DeerPoints.Append(Hp.DeerPoints);
		Merged.WolfPoints.Append(Hp.WolfPoints);
		Merged.WantDeer += Hp.WantDeer;
		Merged.WantWolves += Hp.WantWolves;
		Merged.bComplete = Merged.bComplete && Hp.bComplete;
		IslandHerdPlans.Add(MoveTemp(Hp));
	}
	if (IslandHerdPlans.IsEmpty() || Merged.DeerPoints.IsEmpty())
	{
		UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 섬 무대: 지면 검사를 통과한 무리 자리가 없다%s"), *Summary);
		RestoreTeamValues(TEXT("섬 무대: 시작 자리를 채우지 못했다"));
		return false;
	}
	Merged.bGrounded = true;
	WritePlanToGroup(Merged, G);
	Plans[0] = MoveTemp(Merged);
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 섬 무대 | 무리 자리 %d — %s%s | 합계 사슴 %d·늑대 %d (조정자 시작 직전 %d 번째 검사, BeginPlay 뒤 %.2f 초)"),
		   IslandHerdPlans.Num(), *IslandSiteLine, *Summary, G.Herbivores, G.Wolves, ValidationPasses, World->GetTimeSeconds() - BeginPlaySeconds);
	return true;
}

bool UEcoPolicyV3IntegratedSubsystem::IslandCoverOnLand(const FVector& CenterCm, double RadiusCm) const
{
	if (!bIsland || !IslandMask)
	{
		return true;
	}
	using EcoRepertoireV3::kUnitCm;
	const EcoV3Island::FLandMask& M = *IslandMask;
	const double Cx = (CenterCm.X - IslandOriginCm.X) / kUnitCm;
	const double Cy = (CenterCm.Y - IslandOriginCm.Y) / kUnitCm;
	const double R = RadiusCm / kUnitCm + 0.5 * M.Cell;
	const int32 X0 = M.CellCoord(Cx - R), X1 = M.CellCoord(Cx + R);
	const int32 Y0 = M.CellCoord(Cy - R), Y1 = M.CellCoord(Cy + R);
	for (int32 y = Y0; y <= Y1; ++y)
	{
		for (int32 x = X0; x <= X1; ++x)
		{
			const double Px = (x + 0.5) * M.Cell;
			const double Py = (y + 0.5) * M.Cell;
			if (FMath::Square(Px - Cx) + FMath::Square(Py - Cy) <= R * R && !M.IsOpen(Px, Py))
			{
				return false;
			}
		}
	}
	return true;
}

bool UEcoPolicyV3IntegratedSubsystem::GetIslandLandBoxCm(FBox& Out) const
{
	double X0 = 0, Y0 = 0, X1 = 0, Y1 = 0;
	if (!bIsland || !IslandMask || !IslandMask->LandBounds(X0, Y0, X1, Y1))
	{
		return false;
	}
	using EcoRepertoireV3::kUnitCm;
	// 높이 = 섬 땅의 가장 높은 지형 + 30 m (탑뷰 초점이 언덕·큰 바위 밑으로 들어가지 않게 — 들어가면 가림 피하기가 카메라를 바닥으로 당긴다)
	const double Z = IslandMask->LandTopZ + 3000.0;
	Out = FBox(FVector(IslandOriginCm.X + X0 * kUnitCm, IslandOriginCm.Y + Y0 * kUnitCm, Z), FVector(IslandOriginCm.X + X1 * kUnitCm, IslandOriginCm.Y + Y1 * kUnitCm, Z));
	return true;
}

void UEcoPolicyV3IntegratedSubsystem::IslandLogStart(const FEcoV3RegionContext& Ctx) const
{
	using EcoRepertoireV3::kUnitCm;
	const EcoWorldV3::FFoodGrid& F = Ctx.Sim.Food;
	int64 FoodCells = 0;
	for (const double C : F.Cap)
	{
		FoodCells += C > 0.0 ? 1 : 0;
	}
	FString Herds;
	for (int32 h = 0; h < IslandHerdPlans.Num(); ++h)
	{
		const FEcoV3StagePlan& Hp = IslandHerdPlans[h];
		Herds += FString::Printf(TEXT("%s자리 %d (%.0f, %.0f, %.0f) m"), h == 0 ? TEXT("") : TEXT(" · "), h + 1, Hp.CenterCm.X / 100.0, Hp.CenterCm.Y / 100.0,
								 Hp.CenterCm.Z / 100.0);
	}
	UE_LOG(LogEcoPolicyV3I, Log,
		   TEXT("[EcoV3I] 섬 무대 시작 | 세계 %s 한 변 %.0f m (원점 %.0f, %.0f m) | 사슴 %d·늑대 %d · 은신처 %d (무리 자리마다 %d, 반경 %.0f m — 원이 땅 칸 위) | ")
			   TEXT("먹이 칸 %d×%d 가운데 먹이가 나는 칸 %lld (용량 합 %.0f) | 무리 자리: %s | 두뇌·세계 규칙은 통합 v3 그대로, 벽 대신 땅/물 지도 (지문 %016llx)"),
		   *Ctx.RegionId.ToString(), Ctx.SizeCm() / 100.0, Ctx.OriginCm.X / 100.0, Ctx.OriginCm.Y / 100.0, Ctx.PlannedDeer, Ctx.PlannedWolves,
		   static_cast<int32>(Ctx.Sim.Config.Covers.size()), Settings.ExtraCoverCount,
		   Settings.ExtraCoverRadiusUnits(FMath::Clamp(Settings.StageSizeUnits, 60.0, 110.0)) * kUnitCm / 100.0, F.Gw, F.Gw, static_cast<long long>(FoodCells), Ctx.StartFood,
		   *Herds, IslandMask ? static_cast<unsigned long long>(IslandMask->Fingerprint()) : 0ULL);
}

// -----------------------------------------------------------------------------
// 먼 개체 표식 (그리는 단독·리슨 호스트 — 몸 액터가 없는 산 개체)
// -----------------------------------------------------------------------------

void UEcoPolicyV3IntegratedSubsystem::IslandTickMarkers()
{
	using namespace EcoV3IslandImpl;
	UWorld* World = GetWorld();
	if (!bIsland || !bContextsCreated || !World || !FApp::CanEverRender() || World->GetNetMode() == NM_Client || World->GetNetMode() == NM_DedicatedServer)
	{
		return;
	}
	const bool bOn = CVarIslandMarkers.GetValueOnGameThread() != 0;
	if (!bOn)
	{
		if (IsValid(IslandMarkerActor))
		{
			IslandMarkerActor->SetActorHiddenInGame(true);
		}
		return;
	}
	const double Now = FPlatformTime::Seconds();
	if (Now < NextIslandMarker)
	{
		return;
	}
	NextIslandMarker = Now + 0.25;
	// 표식 액터: 인스턴스 메시 셋 (사슴 갈색·쫓기는 사슴 빨강·늑대 회색). 충돌·그림자·복제 없음
	if (!IsValid(IslandMarkerActor))
	{
		UStaticMesh* Sphere = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
		UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
		if (!Sphere)
		{
			return;
		}
		FActorSpawnParameters Params;
		Params.Name = MakeUniqueObjectName(World->PersistentLevel, AActor::StaticClass(), TEXT("EcoV3_IslandMarkers"));
		Params.ObjectFlags |= RF_Transient;
		AActor* A = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Params);
		if (!A)
		{
			return;
		}
		A->SetReplicates(false);
		USceneComponent* Root = NewObject<USceneComponent>(A, TEXT("Root"));
		A->SetRootComponent(Root);
		Root->RegisterComponent();
		const FLinearColor Colors[3] = {FLinearColor(0.45f, 0.26f, 0.10f), FLinearColor(0.95f, 0.08f, 0.05f), FLinearColor(0.35f, 0.35f, 0.38f)};
		const TCHAR* Names[3] = {TEXT("Deer"), TEXT("Chased"), TEXT("Wolf")};
		for (int32 k = 0; k < 3; ++k)
		{
			UInstancedStaticMeshComponent* Ism = NewObject<UInstancedStaticMeshComponent>(A, Names[k]);
			Ism->SetMobility(EComponentMobility::Movable);
			Ism->SetStaticMesh(Sphere);
			if (Base)
			{
				UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Base, A);
				Mid->SetVectorParameterValue(TEXT("Color"), Colors[k]);
				Ism->SetMaterial(0, Mid);
			}
			Ism->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Ism->SetCastShadow(false);
			Ism->SetupAttachment(Root);
			Ism->RegisterComponent();
			A->AddInstanceComponent(Ism);
		}
		IslandMarkerActor = A;
	}
	IslandMarkerActor->SetActorHiddenInGame(false);
	TArray<EcoV3Observe::FSubject> Subs;
	if (!EcoV3Observe::Gather(*World, Subs))
	{
		return;
	}
	FVector Eye = FVector::ZeroVector;
	bool bEye = false;
	if (const APlayerController* PC = World->GetFirstPlayerController(); PC && PC->PlayerCameraManager)
	{
		Eye = PC->PlayerCameraManager->GetCameraLocation();
		bEye = true;
	}
	TArray<FTransform> Ts[3];
	for (const EcoV3Observe::FSubject& Sb : Subs)
	{
		if (!Sb.bAlive || Sb.bHasActor)
		{
			continue;
		}
		const double Dist = bEye ? FVector::Dist(Eye, Sb.Location) : 10000.0;
		const double SizeCm = FMath::Max(150.0, 0.012 * Dist);
		const int32 Kind = Sb.bWolf ? 2 : (EcoV3Observe::IsChased(Sb.State) ? 1 : 0);
		Ts[Kind].Add(FTransform(FRotator::ZeroRotator, Sb.Location + FVector(0.0, 0.0, 0.5 * SizeCm + 60.0), FVector(SizeCm / 100.0)));
	}
	TArray<UInstancedStaticMeshComponent*> Isms;
	IslandMarkerActor->GetComponents(Isms);
	for (UInstancedStaticMeshComponent* Ism : Isms)
	{
		const int32 Kind = Ism->GetFName() == FName(TEXT("Chased")) ? 1 : Ism->GetFName() == FName(TEXT("Wolf")) ? 2 : 0;
		Ism->ClearInstances();
		if (!Ts[Kind].IsEmpty())
		{
			Ism->AddInstances(Ts[Kind], false, /*bWorldSpace*/ true, /*bUpdateNavigation*/ false);
		}
	}
}

// -----------------------------------------------------------------------------
// 섬 기록 줄 (10 초마다 — 막힌 칸 위 개체는 늘 0 이어야 한다)
// -----------------------------------------------------------------------------

void UEcoPolicyV3IntegratedSubsystem::IslandTickStats()
{
	using EcoRepertoireV3::kUnitCm;
	UWorld* World = GetWorld();
	if (!bIsland || !bContextsCreated || !IslandMask || !World || Contexts.IsEmpty())
	{
		return;
	}
	const double Now = World->GetTimeSeconds() - BeginPlaySeconds;
	if (NextIslandStats <= 0.0)
	{
		NextIslandStats = Now + 10.0;
		return;
	}
	if (Now < NextIslandStats)
	{
		return;
	}
	TArray<EcoV3Observe::FSubject> Subs;
	if (!EcoV3Observe::Gather(*World, Subs))
	{
		return;   // Mass 처리 중 — 다음 프레임
	}
	NextIslandStats = Now + 10.0;
	const EcoV3Island::FLandMask& M = *IslandMask;
	const int32 H = IslandHerdPlans.Num();
	TArray<int32> HerdDeer, HerdChased, HerdHunt;
	HerdDeer.Init(0, H);
	HerdChased.Init(0, H);
	HerdHunt.Init(0, H);
	int32 Deer = 0, Wolves = 0, DeerBlocked = 0, WolfBlocked = 0, Away = 0, Chased = 0, Hunting = 0;
	for (const EcoV3Observe::FSubject& Sb : Subs)
	{
		if (!Sb.bAlive)
		{
			continue;
		}
		const double Ux = (Sb.Location.X - IslandOriginCm.X) / kUnitCm;
		const double Uy = (Sb.Location.Y - IslandOriginCm.Y) / kUnitCm;
		const bool bBlocked = !M.IsOpen(Ux, Uy);
		const bool bChased = !Sb.bWolf && EcoV3Observe::IsChased(Sb.State);
		const bool bHunt = Sb.bWolf && EcoV3Observe::IsHunting(Sb.State);
		(Sb.bWolf ? Wolves : Deer) += 1;
		(Sb.bWolf ? WolfBlocked : DeerBlocked) += bBlocked ? 1 : 0;
		Chased += bChased ? 1 : 0;
		Hunting += bHunt ? 1 : 0;
		// 가장 가까운 무리 자리 (300 m 밖이면 '자리 밖')
		int32 Best = INDEX_NONE;
		double BestD = 300.0 * 100.0;
		for (int32 h = 0; h < H; ++h)
		{
			const double D = FVector::Dist2D(Sb.Location, IslandHerdPlans[h].CenterCm);
			if (D < BestD)
			{
				BestD = D;
				Best = h;
			}
		}
		if (Best == INDEX_NONE)
		{
			Away += Sb.bWolf ? 0 : 1;
			continue;
		}
		HerdDeer[Best] += Sb.bWolf ? 0 : 1;
		HerdChased[Best] += bChased ? 1 : 0;
		HerdHunt[Best] += bHunt ? 1 : 0;
	}
	const EcoWorldV3::FWorldStats& St = Contexts[0]->Sim.Stats;
	const int64 Now4[4] = {St.IslandDeerSteers, St.IslandDeerSlides, St.IslandDeerStops, St.IslandWolfReflects};
	FString Herds;
	for (int32 h = 0; h < H; ++h)
	{
		Herds += FString::Printf(TEXT("%s%d: 사슴 %d (쫓김 %d)·사냥 늑대 %d"), h == 0 ? TEXT("") : TEXT(" · "), h + 1, HerdDeer[h], HerdChased[h], HerdHunt[h]);
	}
	UE_LOG(LogEcoPolicyV3I, Log,
		   TEXT("[EcoV3I] 섬 무대 | %.0f초 | 산 사슴 %d·늑대 %d | 막힌 칸 위: 사슴 %d·늑대 %d | 무리 자리 300 m 안 — %s | 자리 밖 사슴 %d | 지금 쫓김 사슴 %d·사냥 늑대 %d | ")
			   TEXT("구간 해안 굽힘 %lld · 미끄러짐 %lld · 제자리 %lld · 늑대 반사 %lld | 누적 포획 %lld"),
		   Now, Deer, Wolves, DeerBlocked, WolfBlocked, *Herds, Away, Chased, Hunting, static_cast<long long>(Now4[0] - IslandStatsPrev[0]),
		   static_cast<long long>(Now4[1] - IslandStatsPrev[1]), static_cast<long long>(Now4[2] - IslandStatsPrev[2]), static_cast<long long>(Now4[3] - IslandStatsPrev[3]),
		   static_cast<long long>(St.Caught));
	for (int32 k = 0; k < 4; ++k)
	{
		IslandStatsPrev[k] = Now4[k];
	}
}
