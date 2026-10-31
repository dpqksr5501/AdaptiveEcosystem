// 레벨 나무 놓기 명령 (10-18 사용자 '일단 플레이시 장애물이 생성되게 하지 말고 그냥 우리 통합레벨에 배치를 해 테스트하는 레벨에').
//
// 무대 나무 배치 표(TreeLayoutV3.h, 파이썬 herbivore_rl/results/v3/wild2/trees/make_tree_layout.py — 숲 24·고지 9·메마른 땅 0 그루)를 통합 레벨
// /Game/Map/LV_Ecosystem_IntegrationTest 에 진짜 액터로 놓는다. 예전(10-17)에는 통합 v3 모드가 Play 때마다 같은 표로 나무를 놓았다
// (EcoPolicyV3IntegratedSubsystem 'StageTrees' — 이제 기본 꺼짐, 예비).
//
// 나무마다 두 액터 (폴더 EcoV3_Trees, 늘 불림 — 공간 스트리밍을 하지 않는다):
//   - 나무: AStaticMeshActor, 팀 메시 /Game/SHC/Fab/Realistic_Beech_Tree_3D_Vegetation/Beech_Tree, 이 액터만 충돌 없음(메시 애셋은 그대로 —
//     메시 충돌은 잎까지 덮는 큰 볼록 하나라 그대로 쓰면 잎 아래가 막힌다), 그림자 켬, 꼬리표 EcoV3Tree. 자리 = 실행 중 나무와 같다
//     (기준점·방위·크기 = 표, Z = 줄기 중심·둘레 6 곳의 가장 낮은 땅 − 10 cm).
//   - 줄기 막이: AStaticMeshActor, 엔진 /Engine/BasicShapes/Cylinder, BlockAll, 게임에서 숨김·그림자 없음, 꼬리표 EcoV3Trunk, 나무 액터에 붙음
//     (나무를 옮기면 함께 움직인다). 충돌 상자 가로 반폭 평균 = 줄기 원판 반지름(밑동 꼭짓점 반경 40.45 cm × 크기), 땅 − 30 cm ~ 땅 + 4 m.
//     통합 v3 모드의 레벨 읽기가 이 막이를 줄기 원판으로 읽는다 (표 자리와 1 cm 안이면 표 값 — 파이썬 거울과 비트 단위로 같다).
//   두 액터 모두 꼬리표 EcoV3TreeId_<지역>_<번호> 로 짝을 찾는다.
//
// 실행 (편집기를 닫고, 한 번에 하나):
//   UnrealEditor-Cmd.exe <uproject> -run=EcoV3PlaceTrees -unattended -nopause -nosplash
//       [-Map=/Game/Map/LV_Ecosystem_IntegrationTest] [-DryRun] [-Remove] [-Force]
//   - 기본: 맵과 모든 액터를 불러 무대 자리(통합 모드와 같은 규칙 — 조정자 그룹의 먹이 자리, 지역 상자 안)를 찾고 나무를 놓거나 고친다.
//     다시 돌려도 우리 꼬리표 액터만 바꾼다 — 이미 같으면 저장하지 않는다(-Force 면 다시 저장). 표에 없는 우리 액터는 지운다.
//   - -DryRun: 계산과 확인만 하고 저장하지 않는다.  -Remove: 우리 액터(꼬리표 EcoV3Tree·EcoV3Trunk)를 모두 지운다.
//   새 액터는 외부 액터 파일(Content/__ExternalActors__/Map/LV_Ecosystem_IntegrationTest/...)로, 폴더는 외부 개체 파일로 저장된다. 맵 파일은 바꾸지 않는다.
//   끝에 레벨 읽기(ScanStageObstacles)로 원판이 표와 같은지 확인해 적는다.
#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"

#include "EcoV3PlaceTreesCommandlet.generated.h"

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoV3PlaceTreesCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UEcoV3PlaceTreesCommandlet();
	virtual int32 Main(const FString& Params) override;
};
