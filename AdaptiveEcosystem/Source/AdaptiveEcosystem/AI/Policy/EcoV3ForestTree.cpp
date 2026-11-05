// 통합 v3 숲 자람 모드의 나무 한 그루 (EcoV3ForestTree.h 머리 주석).

#include "EcoV3ForestTree.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/GameStateBase.h"
#include "Misc/App.h"
#include "Net/UnrealNetwork.h"

#include "EcoPolicyV3IntegratedSubsystem.h"
#include "EcoV3BigChange.h"
#include "EcoV3Brain.h"
#include "EcoV3ForestGrowth.h"

namespace EcoV3ForestTreeImpl
{
	/** 숲 화면 줄 키 (EcoV3ForestGrowth.cpp 와 같다 — 732000~732004 는 두뇌 알림·상태 줄). */
	constexpr uint64 kNoticeKeyForest = 732005;

	/** FNV-1a 64 에 double 비트 하나를 넣는다. */
	void Mix(uint64& H, double V)
	{
		uint64 Bits = 0;
		FMemory::Memcpy(&Bits, &V, sizeof(Bits));
		for (int32 i = 0; i < 8; ++i)
		{
			H ^= (Bits >> (8 * i)) & 0xFFULL;
			H *= 1099511628211ULL;
		}
	}
}

AEcoV3ForestTree::AEcoV3ForestTree()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;
	PrimaryActorTick.TickInterval = 0.0f;
	bReplicates = true;
	bAlwaysRelevant = true;
	SetReplicateMovement(false);
	NetDormancy = DORM_Awake;
	SetNetUpdateFrequency(1.0f);
	SetMinNetUpdateFrequency(1.0f);
	SetCanBeDamaged(false);

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	RootComponent = Root;

	TreeMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TreeMesh"));
	TreeMesh->SetupAttachment(Root);
	TreeMesh->SetMobility(EComponentMobility::Movable);
	TreeMesh->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
	TreeMesh->SetCastShadow(true);
	TreeMesh->SetCanEverAffectNavigation(false);
	TreeMesh->SetGenerateOverlapEvents(false);

	TrunkMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TrunkBlocker"));
	TrunkMesh->SetupAttachment(Root);
	TrunkMesh->SetMobility(EComponentMobility::Movable);
	TrunkMesh->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);   // 묘목: 아무것도 막지 않는다
	TrunkMesh->SetCastShadow(false);
	TrunkMesh->SetHiddenInGame(true);
	TrunkMesh->SetCanEverAffectNavigation(false);   // 팀 내비 메시를 더럽히지 않는다 (명령과 같다)
	TrunkMesh->SetGenerateOverlapEvents(false);
	// 보이지 않는 막이: 그림자·거리장·반사·광선 추적에도 넣지 않는다 (SpawnLevelTreePair 와 같다)
	TrunkMesh->bAffectDistanceFieldLighting = false;
	TrunkMesh->bAffectDynamicIndirectLighting = false;
	TrunkMesh->bVisibleInReflectionCaptures = false;
	TrunkMesh->bVisibleInRealTimeSkyCaptures = false;
	TrunkMesh->bVisibleInRayTracing = false;

	Tags.Add(UEcoPolicyV3IntegratedSubsystem::LevelTreeTag());
}

void AEcoV3ForestTree::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(AEcoV3ForestTree, Plan);
	DOREPLIFETIME(AEcoV3ForestTree, bMature);
}

void AEcoV3ForestTree::BeginPlay()
{
	Super::BeginPlay();
	if (GetNetMode() == NM_DedicatedServer)
	{
		SetActorTickEnabled(false);   // 그리지 않는다 — 다 자람 때 최종 크기만 놓는다
	}
	// 클라이언트: 복제가 BeginPlay 앞에 왔으면 여기서 (OnRep 이 먼저 불렸어도 두 번 하지 않는다)
	if (Plan.bValid && !bPlanApplied)
	{
		ApplyPlan();
	}
	if (bMature && !bMatureApplied)
	{
		ApplyMature();
	}
}

void AEcoV3ForestTree::InitPlan(const FEcoV3ForestPlan& InPlan)
{
	Plan = InPlan;
	Plan.bValid = true;
	bPlanApplied = false;
	ApplyPlan();
	ForceNetUpdate();
}

void AEcoV3ForestTree::SetMature()
{
	if (bMature)
	{
		return;
	}
	bMature = true;
	ApplyMature();
	ForceNetUpdate();
}

void AEcoV3ForestTree::OnRep_Plan()
{
	bPlanApplied = false;
	ApplyPlan();
	if (bMature && !bMatureApplied)
	{
		ApplyMature();
	}
}

void AEcoV3ForestTree::OnRep_Mature()
{
	if (bMature && !bMatureApplied && bPlanApplied)
	{
		ApplyMature();
	}
}

EcoTreeLayoutV3::FTree AEcoV3ForestTree::FinalTree() const
{
	return UEcoPolicyV3IntegratedSubsystem::MakeLevelTree(Plan.X, Plan.Y, Plan.Scale, Plan.YawDeg);
}

FString AEcoV3ForestTree::PairId() const
{
	return FString::Printf(TEXT("%s_F%02d"), *Plan.RegionId.ToString(), Plan.Index);
}

void AEcoV3ForestTree::ApplyPlan()
{
	if (!Plan.bValid)
	{
		return;
	}
	bPlanApplied = true;
	// 메시는 실행 중에 읽는다 (생성자에서 읽으면 편집기를 켤 때마다 팀 나무 애셋을 불러온다). 나무 메시가 없으면 줄기 막이만 (패키지 빌드 굽기 — 설계 4절 위험 2)
	if (!TrunkMesh->GetStaticMesh())
	{
		TrunkMesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, UEcoPolicyV3IntegratedSubsystem::LevelTrunkMeshPath()));
	}
	if (!TreeMesh->GetStaticMesh() && GetNetMode() != NM_DedicatedServer)
	{
		if (UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, UTF8_TO_TCHAR(EcoTreeLayoutV3::kMeshPath)))
		{
			TreeMesh->SetStaticMesh(Mesh);
		}
	}
	// 액터는 늘 원점·단위 변환 — 구성요소의 세계 변환 = 상대 변환 (서버·클라이언트 합성 오차 없음)
	SetActorTransform(FTransform::Identity);
	const EcoTreeLayoutV3::FTree T = FinalTree();
	if (const UStaticMesh* Cylinder = TrunkMesh->GetStaticMesh())
	{
		FTransform TrunkXf;
		if (UEcoPolicyV3IntegratedSubsystem::LevelTrunkTransform(T, Plan.OriginCm(), Plan.GroundMinZ, *Cylinder, TrunkXf))
		{
			TrunkMesh->SetRelativeTransform(TrunkXf);
		}
	}
	SetTreeScaleFrac(bMature ? 1.0 : EcoV3Forest::GrowFraction(ServerTime() - Plan.GrowStartServerTime, Plan.GrowSeconds, Plan.SaplingFrac));
	Tags.AddUnique(UEcoPolicyV3IntegratedSubsystem::LevelTreeTag());
	Tags.AddUnique(FName(*(FString(TEXT("EcoV3TreeId_")) + PairId())));
}

void AEcoV3ForestTree::ApplyMature()
{
	if (!bPlanApplied)
	{
		return;
	}
	bMatureApplied = true;
	SetTreeScaleFrac(1.0);
	TrunkMesh->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);   // 명령·SpawnLevelTreePair 와 같은 프로파일
	Tags.AddUnique(UEcoPolicyV3IntegratedSubsystem::LevelTrunkTag());
	// 헤드리스 증거 (복제 확인 — 서버·클라이언트 같은 지문이어야 한다)
	const ENetMode Mode = GetNetMode();
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 숲 %s 다 자람 (%s) | 줄기 충돌 %s · 줄기 변환 지문 %016llx"), *PairId(),
		   Mode == NM_Client ? TEXT("클라이언트") : Mode == NM_Standalone ? TEXT("단독") : Mode == NM_DedicatedServer ? TEXT("데디케이티드 서버") : TEXT("리슨 서버"),
		   TrunkCollisionOn() ? TEXT("켬") : TEXT("끔"), static_cast<unsigned long long>(TrunkHash()));
	if (GetNetMode() != NM_Client)
	{
		SetActorTickEnabled(false);   // 다 자랐다 — 서버·단독은 더 그릴 것이 없다 (클라이언트는 화면 줄 때문에 둔다)
	}
}

void AEcoV3ForestTree::SetTreeScaleFrac(double Frac)
{
	if (!Plan.bValid)
	{
		return;
	}
	// 크기마다 기준점을 다시 셈해 줄기 중심이 움직이지 않게 (메시 기준점 → 밑동 차 × 크기)
	const EcoTreeLayoutV3::FTree T = UEcoPolicyV3IntegratedSubsystem::MakeLevelTree(Plan.X, Plan.Y, Plan.Scale * FMath::Clamp(Frac, 0.01, 1.0), Plan.YawDeg);
	TreeMesh->SetRelativeTransform(UEcoPolicyV3IntegratedSubsystem::LevelTreeTransform(T, Plan.OriginCm(), Plan.GroundMinZ));
}

double AEcoV3ForestTree::ServerTime() const
{
	const UWorld* World = GetWorld();
	if (!World)
	{
		return 0.0;
	}
	const AGameStateBase* GS = World->GetGameState();
	return GS ? GS->GetServerWorldTimeSeconds() : World->GetTimeSeconds();
}

void AEcoV3ForestTree::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (Plan.bValid && !bMature && GetNetMode() != NM_DedicatedServer)
	{
		SetTreeScaleFrac(EcoV3Forest::GrowFraction(ServerTime() - Plan.GrowStartServerTime, Plan.GrowSeconds, Plan.SaplingFrac));   // 그리기만
	}
	if (GetNetMode() == NM_Client && Plan.bValid && Plan.Index == 0)
	{
		DrawClientNotice();
	}
}

void AEcoV3ForestTree::DrawClientNotice()
{
	const double Now = FPlatformTime::Seconds();
	if (Now < NextClientNotice || !GEngine || !FApp::CanEverRender() || !EcoV3Brain::NoticeEnabled())
	{
		return;
	}
	NextClientNotice = Now + 1.0;
	int32 Seen = 0;
	int32 Mature = 0;
	for (TActorIterator<AEcoV3ForestTree> It(GetWorld()); It; ++It)
	{
		if (It->GetPlan().bValid && It->GetPlan().RegionId == Plan.RegionId)
		{
			++Seen;
			Mature += It->IsMature() ? 1 : 0;
		}
	}
	const FString Region = EcoV3BigChange::RegionNameKo(Plan.RegionId);
	const FString Text = Mature >= Plan.Target ? FString::Printf(TEXT("숲이 다 자랐다 — %s 나무 %d/%d"), *Region, Mature, Plan.Target)
											   : FString::Printf(TEXT("숲이 자라는 중 — %s 나무 %d/%d (묘목 %d 그루 자라는 중)"), *Region, Mature, Plan.Target, Seen - Mature);
	GEngine->AddOnScreenDebugMessage(EcoV3ForestTreeImpl::kNoticeKeyForest, 1.5f, FColor(150, 230, 140), Text);
}

bool AEcoV3ForestTree::TrunkCollisionOn() const
{
	return TrunkMesh && CollisionEnabledHasQuery(TrunkMesh->GetCollisionEnabled()) && TrunkMesh->GetCollisionResponseToChannel(ECC_WorldStatic) == ECR_Block;
}

uint64 AEcoV3ForestTree::TrunkHash() const
{
	if (!Plan.bValid || !TrunkMesh)
	{
		return 0;
	}
	const FTransform Xf = TrunkMesh->GetComponentTransform();
	uint64 H = 14695981039346656037ULL;
	const FVector L = Xf.GetLocation();
	const FQuat Q = Xf.GetRotation();
	const FVector S = Xf.GetScale3D();
	for (const double V : {L.X, L.Y, L.Z, Q.X, Q.Y, Q.Z, Q.W, S.X, S.Y, S.Z})
	{
		EcoV3ForestTreeImpl::Mix(H, V);
	}
	return H;
}
