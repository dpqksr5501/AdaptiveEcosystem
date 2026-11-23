# Unreal 체형 표현과 가상 본 기술 검토

2026-11-22 · UE 5.8 · 사전 설계와 기술 조사 · 2026-11-23 로컬 유전색 적용과 검증 반영

**첫 사슴·늑대 검증은 새 플러그인 없이 시작할 수 있다.** 유전·성장·실제 달리기 성능은 기존 C++ 권위 경로에서 비교하고, 몸 크기·성숙·털색·접지는 기존 표현을 재사용한다. 새 실루엣을 표현할 때 표면에는 Morph Targets, 관절 위치와 보폭에는 실제 본과 IK를 검토한다. 사용자가 언급한 ‘언리얼 가상 본’은 **Virtual Bones**로 해석했다. 가상 본은 애니메이션에서 다른 본을 기준 공간에 따라 추적하는 참조를 만들 때 쓴다. 구체적으로 필요한 곳은 기존 리그에서 발이나 접촉점이 흔들리는 장면을 재현한 뒤 고른다. [제품 설계와 연구 근거](MMORPG_ECOSYSTEM_ADAPTATION_DESIGN_20261122.md) · [Epic Virtual Bones](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-bones-in-unreal-engine)

## 1. 현재 에셋과 런타임에서 재사용할 것

| 현재 경로 | 보존할 책임과 다음 확인점 |
| --- | --- |
| 개체 생애와 반복 실행 | `FGenome`의 본래 값과 권위 성장·피로·체력으로 현재 크기·속도·유지비를 구한다. 기존 Native 또는 RuleFauna가 실제 이동과 대사·공격을 처리한다. [생애와 유전](../../Source/AdaptiveEcosystem/AI/Policy/EcoLifeHistoryV3.h) |
| 시각 상태와 Mesh | `BodyScale`, `Maturity`, `CoatTone`을 수신한다. `AEcoCreatureRepresentationActor`는 월드 스케일, 종·나이별 메시, 몸 비율·상태·털색을 표시한다. 현재 개체별 크기·색 차이에 사용할 수 있다. 별도의 다리뼈 길이 또는 발톱 외형 채널은 이 문서의 후보이다. [표현 상태](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureVisualState.h) · [표현 Actor](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.cpp) |
| 기존 리그와 발 접지 | 종별 Animation Profile에 `FootBones`, `IKEndBones`, `BodyBone`, `ContactHeights` 등 대응이 있다. `FAnimNode_EcoGroundFeet`이 기존 발 접지와 몸 보정을 처리한다. 새 체형에서는 발 기준과 보정 한도를 읽고 최솟값·최댓값의 보폭, 접지, 지면 관통을 비교한다. [종별 프로필](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureAnimationProfile.h) · [접지 노드](../../Source/AdaptiveEcosystem/Creature/Representation/EcoGroundFeetNode.cpp) |
| 공격 접촉과 피격 | 동물은 권위 실제 위치·거리·차폐·준비 상태를 확인한다. 플레이어에게 맞는 동물은 기존 권위 쿼리 프록시로 바인딩된다. 새 사거리나 제압 효과는 정확한 기존 전투 경계의 유효 접촉으로 증명한다. [전투·피격 프록시](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureCombat.cpp) |

### 소유 섬의 유전 비율과 실행 효과

`LV_JYU_IslandEcosystemRefreshed`의 생명주기에서 추진력·지구력·형태 세 축을 기존 전체 체격과 별도로 사용한다. 창시 개체는 축별 0.90–1.10에서 시작한다. 자연 출생은 같은 축의 부모 평균에 최대 ±0.03의 변이를 더해 0.82–1.18에 제한한다. 성장률은 현재의 발현 배율에 적용한다. 진단은 출생 유전값과 현재 발현값을 각각 기록한다. [부모 유전·성장 코드](../../Source/AdaptiveEcosystem/AI/Policy/EcoLifeHistoryV3.h)

- 지상 추진력은 가속·제동에 쓰인다. 형태가 큰 개체는 기존 접촉 판정의 도달 범위가 늘고, 회전 제한이 있는 개체는 민첩성이 낮아진다. 서버는 감지·기하·실접촉을 계속 확인한다.
- 공중 추진력은 순항에, 수륙·수중 추진력은 유영에 쓰인다. 수중 형태는 유영·부화·먹이 지급의 수층 여유에도 반영된다. 지구력은 활동 비용을 낮추고 평상시 소모를 높인다. 각 효과는 기존 움직임과 대사 처리에서 계산한다.
- 지상과 수중은 추진력·형태를 길이·폭의 비율로 표시하고, 공중은 추진력에 따른 가로 비율을 표시한다. 기존 메시의 수평 비율에 적용하고 높이와 접지 구조는 유지한다. 이 경로로 표현되는 변화는 몸의 비율이다. 턱이나 발톱의 개별 변형은 별도 에셋 작업이다. [실제 실행](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp) · [수층 검증](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaWaterMovement.cpp)

야생 포식자와 먹잇감의 가속·감속·회전 연구는 직선 속도와 기동성을 따로 다루는 근거로 삼았다. 핀치 장기 관찰은 같은 형질의 이점이 먹이 경쟁에 따라 달라지는 사례다. 구체적인 배율과 비용은 섬의 게임 계수다. [가속·감속·회전 연구](https://pubmed.ncbi.nlm.nih.gov/29364874/) · [핀치 부리와 먹이 경쟁](https://pubmed.ncbi.nlm.nih.gov/16840700/)

### 기존 골격 전체에 분포하는 유전 변화

세 축과 별도로 개체마다 몸 앞뒤·가로·높이에 적용되는 네 개의 공간 계수를 가진다. 계수 하나는 특정 이름의 뼈를 지정하지 않는다. 기존 리그의 기준 자세와 종별 정방향으로 뼈 위치를 읽고 몸의 서로 가까운 위치에 연속적인 변형을 적용한다. 출생 시에는 축마다 양쪽 부모가 25%와 75%씩 기여하며 작은 변이가 더해진다. 실제 값은 ±0.15 범위에서 제한하고 성숙 중에는 발현 강도만 바꾼다. 성장 공간 계수 (`Source/AdaptiveEcosystem/AI/Policy/EcoBodyDevelopment.h`) · [유전](../../Source/AdaptiveEcosystem/AI/Policy/EcoLifeHistoryV3.h)

기존 애니메이션과 발 IK가 계산된 뒤, 최종 포즈를 전달하기 전에 스킨에 연결된 뼈 위치를 이동시킨다. 보정 대상 발·IK 끝은 고정하며, 부모 관절에는 변형을 줄여 적용한다. 서버는 동일한 발현값으로 타격 도달·가속·대사와 몸의 폭·높이를 근사한다. 먹이 탐색, 지상 이동·통행·은신, 입수와 유영·부화는 같은 체형을 검사한다. 접촉 쿼리는 기존 권위 거리·차폐 검사와 캡슐을 사용한다. 새 사지 생성이나 렌더 메시와 같은 윤곽을 갖는 충돌체는 별도 범위다. 리그 표현 (`Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureShapeComponent.cpp`) · [물과 지상 이동](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp)

몸과 몸을 움직이는 정책의 계약은 각각 유지한다. 기존 규칙 실행기와 PPO 제어가 같은 체형을 사용하는 세계를 구성하며, 새로운 관측 입력이나 학습된 정책은 별도 인계가 필요하다. 공간에 연속적으로 퍼지는 변형은 형상 변형 연구를, 여러 부위 변화가 함께 발현되는 구조는 형태 발달 연구를 참고했다. [Sederberg와 Parry의 형상 변형](https://people.eecs.berkeley.edu/~sequin/CS285/PAPERS/Sederberg_Parry.pdf) · [형태의 발달과 진화](https://doi.org/10.1038/nrg2829) · [형태와 행동 공동 진화 연구](https://pmc.ncbi.nlm.nih.gov/articles/PMC8494941/)

동작은 개발 대조에서 `-EcoFunctionalTraits=0`으로 중립화할 수 있다. 체크포인트는 활성 규칙과 실행 이미지가 일치할 때 복원된다. 현재 빌드의 클라이언트 접속 프로토콜은 발현값 네 바이트를 포함한 `EcoProtocol=5`다. 지역마다 어느 형태가 누적되는지는 시드와 선택 압력을 둔 후손 대조로 판정한다.

### 소유 섬의 유전색과 시각 감지

소유 섬의 `DA_IslandCoatPalette`는 종별 바탕 명암과 지역별 배경 명암 추정값, 종별 외형이 참조하는 머티리얼 복제본을 고른다. 원래 머티리얼의 텍스처·마스크를 유지하면서 개체별 Custom Primitive Data로 색을 곱한다. 털 있는 11종은 밝기와 따뜻한 색조가 바뀌며, 새 2종과 어류 3종은 밝기만 소폭 달라진다. 색은 창시 개체의 분산과 부모 조합·변이로 결정한다. 팔레트는 목표 색이나 세대별 변화 방향을 담지 않는다. 팔레트 작성 도구 (`Tools/Editor/author_jyu_island_coats.py`) · [Unreal 개체별 머티리얼 공식 문서](https://dev.epicgames.com/documentation/unreal-engine/storing-custom-data-in-unreal-engine-materials-per-primitive)

권위 서버는 최초 탐지에서 개체 명암과 지역 배경 명암의 대비를 평가한다. 규칙 사냥의 지상·공중·수중 후보와 Native 늑대의 사슴 표적 탐색에 적용한다. 규칙 생물의 시각 위협 감지는 가까운 거리와 기존 경계 상태를 보존한다. 수층에서는 기존 수심과 수초 차폐를 사용하며 명암 효과를 줄인다. 포획·피격·소리에는 별도 배율을 추가하지 않는다. 배경은 지역 단위 추정값이며 관찰자 방향의 픽셀이나 실제 텍스처를 서버에서 샘플링하는 방식은 아니다. 선택을 켜고 끈 대조 실행은 창시 유전값과 외형을 공유한다. [쥐 모형 현장 실험](https://onlinelibrary.wiley.com/doi/10.1111/j.1558-5646.2010.00976.x) · [눈신토끼 배경 불일치 연구](https://onlinelibrary.wiley.com/doi/10.1111/ele.12568) · [담수어 명암 연구](https://onlinelibrary.wiley.com/doi/10.1111/bij.12451)

동일 창시 집단의 두 시드 눈밭 대조에서 상대 개체·시각·거리값이 일치하는 검사 231건 중 위장을 켰을 때만 13건이 감지에서 제외됐다. 조우 중 한 번 이상 감지된 비율은 밝기 그룹 간 차이가 작았다. 40게임분 동안 밝은 털의 생존·번식 이점과 세대별 누적은 확인되지 않았다. 외형은 자세·카메라·조명을 고정한 늑대·표범 렌더로 비교했다. 최초 감지는 Native 늑대의 권위 검사로 확인했고, 색의 유전은 자연 출생 계보에서 확인했다. [외형과 유전색 기록](MMORPG_ECOSYSTEM_TRAIT_EVIDENCE_20261122.md#16종-유전색-검증) · [눈밭 대조와 재현 명령](MMORPG_ECOSYSTEM_TRAIT_EVIDENCE_20261122.md#눈밭-사슴의-감지생존번식-대조)

## 2. 바꾸려는 모양에 맞는 Unreal 기능

| 해야 할 일 | 우선 선택 | 필요할 때 추가할 것 |
| --- | --- | --- |
| **개체의 전체 크기, 성숙도, 털색 차이** | 기존 스케일·성숙 표현·머티리얼 파라미터. 어린/성체 실루엣이 다르면 기존 메시 변형 또는 별도 성장 단계 에셋을 사용한다. | 새 레벨에 유전색 위장을 연결할 때 지역 배경 명암을 설정하고 실제 시각 감지와 후손 기록을 비교한다. [소유 섬 적용 범위](#소유-섬의-유전색과-시각-감지) |
| **몸통 두께, 근육·발톱·뿔의 표면 실루엣** | 같은 메시에서 작성한 **Morph Target**을 사용한다. Blender Shape Key 또는 기존 팀 DCC에서 베이스 메시와 버텍스 대응이 유지되는 변형을 만든다. 언리얼에서 0·중간·최대의 형태를 LOD마다 확인한다. | 토폴로지나 부착 위치 자체가 달라지는 뿔·발톱은 소켓 부착 메시 또는 단계별 메시가 적합할 수 있다. Morph만 변경하면 관절 위치와 권위 접촉 범위는 별도로 유지된다. [Epic FBX Morph Target Pipeline](https://dev.epicgames.com/documentation/unreal-engine/fbx-morph-target-pipeline-in-unreal-engine) · [Blender Shape Keys](https://docs.blender.org/manual/id/3.0/animation/shape_keys/introduction.html) |
| **다리·팔 비율이나 키 때문에 관절 위치가 변함** | 기존 **실제 변형 본**의 승인된 범위 내 로컬 translation 또는 제한된 스케일, 혹은 비율별로 작성한 변형 메시로 해결한다. 본 한 축만 늘릴 때 자식 본, 스킨 웨이트, 척추·발 절차를 같이 확인한다. | AnimGraph의 `Transform (Modify) Bone` 또는 기존 Skeletal Control을 비교한다. 발·손 위치가 달라지면 기존 GroundFeet, 좁은 체인 IK 또는 리타게팅으로 접지를 다시 맞춘다. [Epic Transform Bone](https://dev.epicgames.com/documentation/unreal-engine/animation-blueprint-transform-bone-in-unreal-engine) · [Epic IK Rig Retargeting](https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine) |
| **머리·척추의 덧씌운 동작 때문에 발이나 접촉점이 흔들림** | 레이어 전후의 실제 본과 기존 접지 노드를 먼저 대조한다. | 필요한 체인에만 **Virtual Bone + IK**를 검토한다. 예를 들어 리그 루트 기준에서 발이나 턱 끝을 추적하되 문제를 일으킨 additive 레이어에서 그 참조를 제외하고, IK가 그 위치를 사용하게 한다. 가상 본을 추가하는 일과 다리가 실제로 길어 보이게 하는 일은 서로 다른 작성 단계다. [Epic Virtual Bones](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-bones-in-unreal-engine) |
| **접촉점 배치, 맞는 크기, 래그돌** | **Socket**은 발톱 메시·이펙트·표현용 접촉점을 붙이거나 비교한다. 기존 권위 스윕·프록시가 몸과 공격에서 실제 유효한 범위를 처리한다. | 시각 메시의 Physics Asset은 물리 표현에 필요한 경우만 조정한다. 소켓 이동, Morph Target, 래그돌 바디 수정은 기존 권위 쿼리의 치수와 별도로 검증한다. [Epic Skeletal Mesh Sockets](https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-sockets-in-unreal-engine) · [Epic Physics Asset](https://dev.epicgames.com/documentation/en-us/unreal-engine/physics-asset-editor-in-unreal-engine---skeleton-tree) |
| **비율이 다른 리그 사이의 애니메이션 재사용** | 같은 리그에서 공유 가능한 애니메이션과 기존 리그별 프로필을 우선한다. | 체인 대응이 있는 경우 **IK Rig / IK Retargeter**로 에디터에서 애니메이션을 만들어 검증한다. 런타임 리타게팅은 에셋 복제를 피할 실익과 동시 개체 비용이 측정된 경우에 쓴다. [Epic Runtime IK Retargeting](https://dev.epicgames.com/documentation/en-us/unreal-engine/runtime-ik-retargeting-in-unreal-engine) |

가상 본은 Skeleton 에셋을 공유하는 여러 메시와 애니메이션에 영향을 줄 수 있다. 적용 전에 에셋의 참조 맵·AnimBP·리그와 Skeleton 공유 범위를 확인하고, 소유 시험 에셋에서만 첫 후보를 작성한다. 공중·수중 종에는 지상 사족의 본 이름이나 발 접지 가정을 일괄 적용하지 않는다.

## 3. 플러그인·도구 선택

설치된 UE 5.8의 descriptor에서 아래 엔진 플러그인의 존재를 확인했다. 저장소 `.uproject`에는 아래 항목의 명시적 활성화가 없다. 로컬 엔진에서 `ControlRig`·`IKRig` descriptor는 기본 활성화로 표시됐으며, 개별 플랫폼과 패키지 사용 여부는 적용 단계에서 확인한다. 새 종의 유전·형질 효과를 확인하는 첫 검증에는 기존 프로젝트 경로와 엔진 기본 에셋 기능이면 충분하다.

| 도구 | 사용을 검토할 조건 |
| --- | --- |
| **Control Rig / FullBodyIK** | 기존 접지로 해결하기 어려운 사족 전체 자세 보정, 여러 관절을 묶는 효과, 힘이 들어가는 전신 연출이 필요할 때. 먼저 오프라인 또는 근거리 한 종에서 비교한다. Epic의 Full-Body IK 사용법은 `FullBodyIK` 활성화를 요구한다. [Epic Full-Body IK](https://dev.epicgames.com/documentation/en-us/unreal-engine/control-rig-full-body-ik-in-unreal-engine) |
| **IKRig** | 실제로 다른 체인·비율인 애니메이션을 공유할 때. 오프라인 작업과 런타임 사용을 구분하고, 기존 사족 접지와 충돌 여부를 확인한다. [Epic IKRig 5.8](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/IKRig?application_version=5.8) |
| **AnimationWarping** | 현재 접지 이후에도 크기·속도별 보폭 오차가 커서 **Stride Warping**이 필요한 경우에 비교한다. Native가 정한 실제 변위를 애니메이션이 표현한다. Motion Warping을 비교할 때도 기존 이동 외에 별도 위치 갱신을 추가하지 않는다. [Epic Pose Warping](https://dev.epicgames.com/documentation/en-us/unreal-engine/pose-warping-in-unreal-engine) |
| **Animation Budget Allocator** | 실제 프로파일에서 많은 가까운 표현 개체의 Animation Tick이 병목인 경우. 화면 속 Mesh 평가 예산에만 사용한다. 권위 감각·이동·전투와 별도로 부하를 측정하고 LOD에서도 중요한 준비 동작이 유지되는지 본다. [Epic Animation Budget Allocator](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-budget-allocator-in-unreal-engine) |
| **Mutable** | 체형·외형의 조합 수가 크게 늘어 사전 제작한 소수의 메시·Morph만으로 관리하기 어려울 때. 로컬 5.8 descriptor는 beta, 기본 OFF다. 런타임 생성 지연, 캐시 키, 패키지 크기, 반복 리스폰·재사용과 폴백을 측정한 뒤 판단한다. [Epic UE 5.8 Mutable Sample](https://www.unrealengine.com/news/mutable-sample-for-runtime-character-customization-now-updated-for-ue-5-8) |
| **ML Deformer Framework** | 단순 Morph·스키닝으로 다루기 어려운 근육·피부 변형 품질이 실제 목표가 된 다음의 선택지다. 별도 메시·애니메이션과 학습용 변형 데이터가 필요하다. 렌더용 변형과 PPO 행동 모델·세대 유전은 각각 관리한다. [Epic ML Deformer 개요](https://dev.epicgames.com/documentation/unreal-engine/ml-deformer-framework-in-unreal-engine) · [Epic 5.8 API](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MLDeformerFrameworkEditor?application_version=5.8) |

공개 생체역학 도구가 필요한 경우 [OpenSim](https://github.com/opensim-org/opensim-core)은 관절·운동 질문을 오프라인에서 검토할 참고다. 프로젝트 리그의 실측 데이터와 대상 종 모델이 확보됐을 때 가치가 생긴다. 디자이너는 먼저 UE 내 조향·접촉 기록과 소유 리그의 발 접지에서 차이를 측정할 수 있다.

## 4. 제안하는 데이터와 제작 흐름

1. **종과 행동의 능력을 먼저 정한다.** 예를 들어 사슴의 초기 가속, 늑대의 추격 중 피로, 표범의 기존 접촉 안정성 중 한 축을 고른다. 유전 값의 허용 범위, 생애 중 물리 한계, 시각 변형 범위는 단위와 의미가 각각 다르므로 따로 둔다.
2. **권위 상태에서 현재 성능을 계산한다.** 생애 유전·성숙·영양·부상·피로에서 파생된 능력을 고정된 완료 경계에서 쓰고, 실제 이동·충돌·공격 판정은 각 backend 한 곳에서 수행한다. 본 길이를 읽기 위해 Dedicated Server가 Client와 같은 포즈 계산을 수행하는 조건을 만들지 않는다. 변화가 필요한 경우 종별 권위 단순 기하와 겹침·거리 검증 범위를 따로 정의한다.
3. **같은 특징을 읽을 수 있는 외형으로 번역한다.** 체형 값을 표현 데이터로 제한·양자화한다. Identity/revision에 따라 원본과 변형을 적용하고, 데이터가 없거나 LOD에서 표현이 단순화되면 기존 표현으로 재현 가능해야 한다. 룩에 맞춰 Root Motion이나 Mesh 스케일을 한 번 더 실제 이동에 적용하지 않는다.
4. **스케일과 접지의 적용 순서를 시험한다.** 기본 이동 포즈 생성, 필요할 때 변형 본·상태 적용, 발·몸 접지 보정, Mesh·Morph·머티리얼 표시를 같은 대표 동작에서 점검한다. 실제 AnimGraph와 에셋에 따라 보정 순서와 애니메이션 curve가 달라질 수 있으므로 실험 결과로 각 단계의 책임을 정한다.
5. **버전과 저장을 같은 단위로 관리한다.** 종/능력 규칙 버전, 표현 에셋·체형 축 버전, 모델 몸 해시를 구분한다. 저장에는 필요한 권위 값과 버전을 남기고, 네트워크는 위치·활동과 시각적으로 필요한 값만 전송한다. 이전 저장, 늦은 접속과 기존 모델을 대조한다. [서버·표현 인계](../Network/MORPHOLOGY_NETWORK_HANDOFF_20261105.md) · [RL 몸 계약 인계](../RL_Policy/MORPHOLOGY_RL_HANDOFF_20261105.md)

### 첫 리그 시험에서 제출할 근거

- **종별 본·메시 목록.** 베이스 Skeleton, 실제 변형 본과 접촉 본, 선택한 가상 본의 부모/추적 대상, Socket, 접지 프로필, 메시와 LOD별 지원 상태를 한 표로 적는다.
- **대표 자세에서의 시각 검증.** 중립·최소·최대, 새끼·성체, 서기·걷기·질주·가파른 회전·경사·멈춤·공격 준비·접촉·사망을 비교한다. 발 미끄러짐과 발·몸 관통, 좌우 차이, 소켓 배치, 어깨/척추 및 극단값 조합을 확인한다.
- **기능 검증.** 보폭과 실제 이동 속도, 공격이 보이는 범위와 권위 접촉, 좁은 통로와 실제 스윕, 대사와 성장·경험 장부를 함께 본다. 눈에 보이는 발톱·뿔만 길어지고 접촉 결과가 그대로인 경우 시각 변형으로 기록한다.
- **멀티·저장 검증.** Standalone과 Dedicated + Client 다수에서 같은 개체의 출생·이주·성장·사망, 근거리 전환과 늦은 접속, 저장 복원, 포즈 평가를 줄인 LOD와 표현 Actor 재사용을 확인한다. 풀 재사용 때 Mesh, 체형, Morph, Material, Socket 및 IK 상태가 이전 개체에서 이어지지 않는지 체크한다.
- **부하·권위 경계.** 실제 프레임 비용, 전송 필드, 리그 평가를 종별 표본으로 확인한다. 측정값은 검증한 동시 개체·플레이어·맵의 범위로 기록하고, 서버 권위의 하위 실행기와 클라이언트 표현을 분리한다.

첫 후보는 기존 사슴·늑대의 **전체 크기와 이동 지표**로 검증하고, 풋스텝·보폭·IK가 맞는지 기존 리그로 확인한다. 이 결과 이후에 표범 한 종의 앞다리나 발톱을 소유 에셋에서 시험하면, 실제 본 수정·Morph·가상 본이 각각 필요한 이유를 한 장면에서 판별할 수 있다.
