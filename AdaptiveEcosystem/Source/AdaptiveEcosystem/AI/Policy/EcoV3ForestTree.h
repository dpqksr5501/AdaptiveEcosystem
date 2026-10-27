// 통합 v3 숲 자람 모드의 나무 한 그루 (10-27, 설계 Docs/RL_Policy/FOREST_GROWTH_MODE.md 1.5·1.6) — 복제하는 실행 중 액터.
//
// 서버·단독이 숲 자리(EcoV3ForestGrowth.h)마다 묘목 때 놓고, 다 자라는 결정 스텝 경계에서 SetMature 로 줄기 막이 충돌을 켠다. 클라이언트는 복제된 계획 값으로
// 서버와 같은 정적 함수(UEcoPolicyV3IntegratedSubsystem::MakeLevelTree·LevelTreeTransform·LevelTrunkTransform, 같은 엔진 원기둥)를 불러 변환을 만든다 —
// 그래서 줄기 충돌 모양이 서버와 같다 (단독·리슨·데디케이티드 + 클라이언트 모두 같은 나무).
//   나무 메시   팀 Beech_Tree (EcoTreeLayoutV3::kMeshPath — 실행 중에 읽는다, 없으면 줄기 막이만), 충돌 없음, 그림자.
//               묘목 동안 크기 = 최종 × GrowFraction(서버 월드 시각 경과) — 기준점은 크기마다 MakeLevelTree 로 다시 셈해 줄기 중심이 움직이지 않는다 (그리기만).
//   줄기 막이   /Engine/BasicShapes/Cylinder, 게임에서 숨김, 묘목 동안 충돌 없음 → 꼬리표 EcoV3Trunk 도 없음 (GatherLevelTrunks 가 세지 않는다 — 아무것도 막지 않는다).
//               다 자라면 BlockAll·꼬리표 EcoV3Trunk — 레벨 나무 줄기 막이(EcoV3PlaceTreesCommandlet·SpawnLevelTreePair)와 같은 설정.
//   꼬리표       EcoV3Tree · EcoV3TreeId_<지역>_F<nn> (· 다 자라면 EcoV3Trunk).
//   액터 변환   늘 원점·단위 변환 (구성요소 세계 변환 = 상대 변환 — 합성 오차 없이 서버·클라이언트가 같은 값).
//   복제         bReplicates·bAlwaysRelevant(많아야 64 그루), 움직임 복제 안 함, 저장 안 함(RF_Transient — 놓는 쪽이 준다). 계획(Plan)은 처음 한 번,
//               다 자람(bMature)은 서버 값이 권위다 — 늦게 들어온 클라이언트도 함께 받아 곧바로 다 자란 나무·충돌을 갖는다. 휴면 대신 갱신 빈도 1 Hz + 바뀔 때 ForceNetUpdate.
//   데디케이티드 서버는 그리지 않으므로 Tick 을 끈다 (다 자람 때 최종 크기만 놓는다).
//   클라이언트 화면 줄 (덤): 색인 0 나무가 1 초마다 복제된 숲 나무를 세어 '숲이 자라는 중 — 메마른 땅 나무 n/목표' (eco.V3Brain.Notice, 키 732005).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"

#include "TreeLayoutV3.h"

#include "EcoV3ForestTree.generated.h"

class UStaticMeshComponent;
class USceneComponent;

/** 숲 나무 계획 (서버가 놓을 때 한 번 정하고 복제 — 실수는 double 그대로 보낸다). */
USTRUCT()
struct ADAPTIVEECOSYSTEM_API FEcoV3ForestPlan
{
	GENERATED_BODY()

	UPROPERTY() double OriginX = 0.0;   // 무대 원점 (cm)
	UPROPERTY() double OriginY = 0.0;
	UPROPERTY() double OriginZ = 0.0;
	UPROPERTY() double X = 0.0;         // 줄기 중심 (무대 단위)
	UPROPERTY() double Y = 0.0;
	UPROPERTY() double R = 0.0;         // 줄기 반지름 (무대 단위 — 기록·보기. 변환은 MakeLevelTree 가 크기에서 다시 셈)
	UPROPERTY() double YawDeg = 0.0;
	UPROPERTY() double Scale = 2.0;     // 최종 크기
	UPROPERTY() double GroundMinZ = 0.0;   // 서버가 잰 줄기 아래 가장 낮은 땅 (cm — 클라이언트는 다시 재지 않는다)
	UPROPERTY() double GrowStartServerTime = 0.0;   // 묘목이 돋은 서버 월드 시각 (그리기)
	UPROPERTY() float GrowSeconds = 20.0f;
	UPROPERTY() float SaplingFrac = 0.15f;
	UPROPERTY() FName RegionId;
	UPROPERTY() int32 Index = -1;       // 숲 자리 순번 (F<nn>)
	UPROPERTY() int32 Target = 0;       // 숲 목표 (놓은 수 — 클라이언트 화면 줄)
	UPROPERTY() bool bValid = false;

	FVector OriginCm() const { return FVector(OriginX, OriginY, OriginZ); }
};

UCLASS(NotBlueprintable, NotPlaceable)
class ADAPTIVEECOSYSTEM_API AEcoV3ForestTree : public AActor
{
	GENERATED_BODY()

public:
	AEcoV3ForestTree();

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
	virtual void Tick(float DeltaSeconds) override;

	/** 서버: 계획을 정한다 (놓은 직후 한 번 — 메시·변환·꼬리표). */
	void InitPlan(const FEcoV3ForestPlan& InPlan);
	/** 서버: 다 자람 — 최종 크기, 줄기 막이 BlockAll, 꼬리표 EcoV3Trunk, bMature 복제. */
	void SetMature();

	const FEcoV3ForestPlan& GetPlan() const { return Plan; }
	bool IsMature() const { return bMature; }
	/** 최종 나무 (MakeLevelTree(X, Y, 크기, 방위) — 서버·클라이언트 같은 셈). */
	EcoTreeLayoutV3::FTree FinalTree() const;
	/** 줄기 막이 충돌이 켜졌나 (쿼리 충돌 ∧ WorldStatic 막음). */
	bool TrunkCollisionOn() const;
	/** 줄기 막이 세계 변환 지문 (FNV-1a 64 — 위치·회전·크기 double 비트, 서버·클라이언트 견줌 — eco.IntegratedV3.ForestInfo). 계획 전이면 0. */
	uint64 TrunkHash() const;
	UStaticMeshComponent* GetTrunkComponent() const { return TrunkMesh; }
	UStaticMeshComponent* GetTreeComponent() const { return TreeMesh; }
	/** 짝 꼬리표 이름 <지역>_F<nn>. */
	FString PairId() const;

protected:
	virtual void BeginPlay() override;

private:
	UPROPERTY(VisibleAnywhere, Category = "Ecology|V3")
	TObjectPtr<USceneComponent> Root;
	UPROPERTY(VisibleAnywhere, Category = "Ecology|V3")
	TObjectPtr<UStaticMeshComponent> TreeMesh;
	UPROPERTY(VisibleAnywhere, Category = "Ecology|V3")
	TObjectPtr<UStaticMeshComponent> TrunkMesh;

	UPROPERTY(ReplicatedUsing = OnRep_Plan)
	FEcoV3ForestPlan Plan;
	UPROPERTY(ReplicatedUsing = OnRep_Mature)
	bool bMature = false;

	UFUNCTION()
	void OnRep_Plan();
	UFUNCTION()
	void OnRep_Mature();

	/** 계획 → 메시·줄기 막이 변환·꼬리표 (서버·클라이언트 같은 길). */
	void ApplyPlan();
	/** 다 자람 → 최종 크기·충돌·꼬리표. */
	void ApplyMature();
	/** 나무 메시 크기 몫 (최종 × Frac) 변환. */
	void SetTreeScaleFrac(double Frac);
	/** 서버 월드 시각 (GameState 가 있으면 그 값 — 클라이언트도 같은 눈금). */
	double ServerTime() const;
	/** 클라이언트 화면 줄 (색인 0 나무만). */
	void DrawClientNotice();

	bool bPlanApplied = false;
	bool bMatureApplied = false;
	double NextClientNotice = 0.0;
};
