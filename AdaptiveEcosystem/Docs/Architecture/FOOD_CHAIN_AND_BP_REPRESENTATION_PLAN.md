# 실제 먹이사슬과 동물 Blueprint Representation 구현 계획

기준일: 2026-10-08. [두 대륙 계획](TWO_CONTINENT_ECOSYSTEM_PLAN.md)의 후속 요구를 구체화한다. 목표는 실제 식물 위치에 접근하는 초식 소비, 실제 초식 개체를 추격하는 육식 포식, 종별 BP 표현, 전 지역의 지속적인 생태계다. 아래 신규 클래스·Fragment 이름은 구현 제안이다.

## 1. 현재 코드와 목표의 차이

- `Mass/EcoMassFeeding.cpp::Collect`는 Resident 여부와 식사 시각을 확인하고 RegionId별 Food 요청을 만든다. 식물 ID·위치·거리·먹기 상태 검사가 없어 실제 근접 섭식으로 볼 수 없다.
- `AI/Policy/EcoBehaviorProcessors.cpp::UEcoPredationProcessor`에는 실제 거리 기반 포획이 있지만 HP=0과 별도 위치 격자 위험 기록을 반영한다. 정식 원인별 사망·포식자 Energy·Ecology 피드백을 연결해야 한다.
- `Creature/CreatureCharacter.h`는 Legacy EcoDataContracts/Evolution Profile에 의존한다. 신규 표현에는 Active Runtime 전용 base/adapter가 필요하다.
- `Core/EcoRepresentationTypes.h`에는 ID·종·위치·HP/Energy·Alive/Dead snapshot이 있다. 먹기·추격·공격 상태와 애니메이션 전달은 추가해야 한다.
- Build.cs에 MassRepresentation/MassActors 의존성이 있다. 설치 UE 5.8의 Movable Visualization Trait와 ActorClass 설정을 재사용할 수 있다. 현재 Box Blueprint/레벨 내부 설정은 이번 검토에서 확인하지 않았다.

## 2. 목표 구조와 상태 소유권

```text
Bootstrap → 종·역할 정의 → 서버 Mass 동물
실제 식물 자원 색인 → 탐색 → 접근 → 근접 소비 요청
실제 동물 이웃 색인 → 탐색 → 추격 → 공격/포식 요청
                                ↓
                     GameThread 권위 결과 확정
                                ↓
                식물 잔량 / Energy / 사망 / Population / 위험
                                ↓
                    다음 관측·행동·이주·재생/번식

동물 논리 결과 → Host 표현 / Client 프록시 → 등록 BP·AnimBP
식물 자원 결과 → 관련 범위의 식물 Actor/Entity/인스턴스 표현
```

| 대상 | 권위 저장소 | BP/Actor 역할 |
|---|---|---|
| 동물 ID·HP·Energy·행동·이동·생존 | 서버 Mass Entity | 메시·애니메이션·효과·읽기 상태·상호작용 진입점 |
| 식물 위치·잔량·재생·고갈 | Ecology 자원 레코드 | 배치 작성 또는 표현 |
| 지역 Food | Ecology의 식물 자원 합계 | 지역 요약 표시 |
| Population·PredationHistory | Ecology에 반영한 Mass 결과 | 요약 표시 |

첫 구현은 **식물 작성 Actor + Ecology 자원 레코드**, **Mass 동물 + 종별 BP 표현**을 권장한다. 이후 식물도 Mass/인스턴스로 확장하되 동일 ResourceId와 소비 API를 유지한다. 이 계획에서 식물 Entity는 ResourceId·위치·읽기 snapshot을 참조하고 권위 Biomass를 별도로 소유하지 않는다. Actor·Entity·Ecology에 중복 잔량을 두지 않는다.

## 3. 종별 BP 등록과 Representation

### 3.1 에디터에서 사용하는 구성

제안하는 `UEcoSpeciesDefinition` DataAsset에 다음을 등록한다.

| 설정 | 예시 |
|---|---|
| SpeciesId·식성·먹이 관계 | Deer/Plant, Wolf/허용 prey 종 |
| 논리 EntityConfig | EC_Deer / EC_Wolf |
| 표현 정의 | BP_Deer / BP_Wolf, 원거리 표현 에셋 |
| 종별 기본 규칙 | 크기·속도·섭식 거리/속도·대사·공격 피해/쿨다운 |

지역 Bootstrap의 여러 SpawnGroup이 이 정의와 초기 수·생성 규칙을 참조한다. SpeciesDefinition에서 템플릿 생성 전에 Config/Trait를 검증·구성하며 SpeciesDefinition과 Config 양쪽에 서로 다른 ActorClass를 권위 설정으로 남기지 않는다. 초기에는 다음 PIE에 적용하는 사전 구성 방식으로 시작한다.

사용 흐름은 **표현 base에서 BP 제작 또는 adapter 연결 → 종 DataAsset에 BP 등록 → Bootstrap 그룹에 종/수 지정 → Mass 개체가 등록 BP로 표현**이다. 기존 AI Character BP를 그대로 지정한다고 AI/HP/CharacterMovement까지 자동 호환되는 것은 아니다.

### 3.2 엔진 기능과 프로젝트 연결

- UE 5.8의 `UMassMovableVisualizationTrait`와 Representation/ActorManagement를 재사용하여 HighResTemplateActor에 동물 BP를 연결한다. 정적 식물은 Stationary 표현 경로를 검토한다.
- 제안하는 `AEcoCreatureRepresentationActor` 또는 `UEcoRepresentationComponent`는 Bind(StableAgentId, SpeciesId), ApplySnapshot, Unbind를 제공한다. Actor 생성/재사용 시 ID를 연결하고 표현 Processor가 상태를 전달한다.
- 신규 BP는 Legacy Evolution에 의존하지 않고 자체 AI·권위 HP·별도 이동을 수행하지 않는다. Client 시각 Actor는 비복제이며 기존 Mass Bubble 상태를 소비한다.
- 속도, Idle/Moving/Grazing/Chasing/Attacking/Dead, 필요한 행동 시작 시각·ActionSequence를 읽기 snapshot에 추가한다. AnimBP가 걷기/먹기/공격/사망을 표현한다.
- 소비/피해는 서버 논리 시간으로 확정한다. 화면 Actor의 AnimNotify가 없으면 섭식이 중단되는 구조로 만들지 않는다. 짧은 행동이 네트워크 표본 사이에 누락되지 않도록 상태 지속 시간/sequence 규칙도 검증한다.
- Actor pool 재사용·지연 로딩 완료 때 binding generation과 ID를 확인하고 이전 애니메이션·사망·delegate·collision 상태를 초기화한다.
- 첫 시연은 소수 개체를 항상 동물 BP로 표현한다. 이후 가까운 BP/원거리 인스턴스/숨김을 적용한다. SkeletalMesh BP가 자동으로 StaticMesh 인스턴스로 바뀌지는 않으므로 원거리 에셋을 별도 준비한다. 설치 UE 5.8의 skinned instance 지원도 실제 에셋/성능을 검증한 뒤 선택한다.
- 플레이어 공격은 소유 Player Actor의 요청을 서버에서 ID·거리·차폐 등으로 검증한다. Client BP 충돌만을 권위 판정으로 쓰지 않는다. 화면 밖 개체에는 서버 단순 collision/공간 질의를 사용할 수 있다.

## 4. 실제 식물 자원과 초식 섭식

제안하는 `FEcoPlantResourceRecord`는 StableResourceId, RegionId/RuntimeIndex, PlantType, Transform, 먹을 수 있는 영역, Biomass, Capacity, 재생 설정, Revision을 가진다. 작성 식물 Actor는 위치·타입·초기량을 registry에 등록하고 실제 잔량은 Ecology만 변경한다. 동적 생성·네트워크·저장 ID는 Actor pointer/EntityHandle과 분리한다.

초식 동작은 **검색 → 도달 가능한 식물 선택 → 접근 → 섭식 범위 도착 → Grazing → 잔량 소비 → 실제 지급량에 따른 Energy 회복 → 고갈/위협 시 재탐색**이다.

- 검색은 실제 자원 위치/잔량 snapshot을 사용한다. 선택에 거리·도달성·위험·경합을 반영한다.
- 개체 Fragment에는 TargetResourceId, 목적지, 상태, 다음 섭식 시각을 둔다. 기존 단일 이동 의도 경로를 사용한다.
- 소비 요청에는 AgentId/ResourceId/Epoch/Step/RequestId/요청량을 넣는다. commit에서 Alive·식성·타깃 존재·잔량·실제 위치/상호작용 범위·필요한 차폐/도달성을 재확인한다.
- 단순 중심 거리 대신 동물 크기와 식물의 섭식 영역을 반영한다. 장애물 너머 식물을 먹거나 접근 전에 Food를 지급하지 않는다.
- 여러 동물이 같은 식물을 먹어도 원자적 배분·공정 규칙으로 합계 소비가 잔량을 넘지 않는다. 지급량만 Energy로 변환한다.
- 고갈 식물은 검색에서 제외하고 크기/재질/숨김 등을 갱신한다. 재생 규칙이 있으면 다시 먹을 수 있게 된다.
- 기존 지역 주기 배분은 Box 검증 모드로 격리한다. 실게임 개체에는 근접 섭식만 적용해 원거리 자동 식사와 중복 지급되지 않게 한다.

지역 FoodAmount는 **해당 지역의 먹을 수 있는 식물 Biomass 합계**로 전환한다. 식물 잔량 감소와 지역 소비를 두 번 차감하지 않는다. 기존 InitialFoodAmount/FoodCapacity/Supply/Starvation은 실제 식물 배치·증가·손실로 전환하거나 명시적 별도 저장고 계약이 필요하다. 첫 MVP에서는 별도 저장고를 만들지 않는다.

재생은 식물 자원 레코드에서만 수행하고 Region 자동 재생과 중복 실행하지 않는다. FoodDensity/gradient도 같은 식물 데이터에서 산출한다. 실제 접근 시간·공간 패치가 기존 학습 환경과 다르면 Python 환경·정규화 계약·정책 평가를 함께 갱신한다.

식물 Actor unload는 논리 자원 제거가 아니다. persistent descriptor로 기존 레코드를 재연결하고, Late Join/재진입 때 초기값이 아닌 최신 Revision/잔량을 전달한다. 자원 DTO는 관련 범위의 복제 Actor/Component 등 전송 계층에 두고 Subsystem에 RPC를 만들지 않는다.

## 5. 실제 육식 포식과 생명주기

육식 동작은 **허용 먹잇감 탐색 → Alive/도달성 확인 → 추격 → 공격/포획 범위 → 결과 확정 → 실제 섭취량에 따른 Energy 회복**이다. 초식 개체는 같은 위치 검색으로 위협을 감지하고 도주/은신한다.

- 초기 MVP는 기존 포획 규칙으로 **성공 때 사망과 즉시 섭취를 함께 확정**한다. prey의 섭취 가능한 biomass/전환 효율과 포식자 cooldown을 적용한다. HP가 일부 감소했다고 전체 먹이 보상을 지급하지 않는다.
- 여러 번 공격하는 전투가 필요하면 피해·쿨다운 규칙을 추가한다. HP=0만 기록하고 원인 없는 ExternalDamage로 넘기지 않는다.
- Predation/PlayerHunt/Starvation 원인을 구분한다. 포식 결과는 Alive 제거, 이동·예약·소비 정리, Population 감소, 실제 사건 지역 위험, 포식자 보상을 연결하며 피해자 receipt로 한 번만 확정한다.
- carnivore는 식생 식사 쿼리에서 제외한다. 먹잇감 분포와 자기 Energy를 이용하는 역할별 탐색·이주 평가가 필요하다.
- 후속 시체 섭식은 CarcassResource와 잔량을 추가한다. 사망으로 Population을 감소시키고, 시체 소비로 잔량과 포식자 Energy를 변경한다. 동물 DeadRetention 종료와 시체 먹이 소멸을 분리한다.

## 6. 생태계 전역 적용과 구현 순서

공통 서버 Mass/자원 색인에 모든 활성 논리 대상이 등록된다. 실제 반경·지역 연결·관계표로 후보를 제한한다. 카메라·Representation LOD·BP Actor의 존재가 서버 상호작용을 중단시키지 않는다. 처음에는 모든 테스트 지역을 서버에 로드하고 동일 규칙을 적용한다.

NavMesh/경로 탐색/지형 제약을 연결하고 실패 타깃은 재선정한다. 직선 조향만으로 복잡한 지형에서 실제 접근을 보장하지 않는다. 대규모 원거리 집계/주기 감소는 후속 최적화이며 먹이 접근과 자원·시간 보존을 별도 검증한다.

| 단계 | 작업 | 완료 조건 |
|---|---|---|
| 1 | SpeciesDefinition·Active 표현 base·ActorClass mapping | 소수 Mass 개체가 등록 BP로 표시되고 ID 유지 |
| 2 | 식물 Actor registry·자원 색인·표현 갱신 | 식물 ID/위치/잔량/고갈을 서버·Client에서 확인 |
| 3 | 초식 타깃·접근·Grazing·근접 소비 | 도착 이후에만 잔량 감소/Energy 증가, 고갈 시 재탐색 |
| 4 | Bootstrap 복수 그룹·육식 추격/포획/보상/사망 | 한 지역에서 식물–초식–육식이 같은 폐루프로 동작 |
| 5 | 지역 Food 전환·실제 Provider/Social/이주 | 자원·관측·집계 정합, 이중 위치 적분 없음 |
| 6 | 두 대륙·다지역·네트워크·표현 전환 | 화면 밖에서도 생태 진행, 재진입/전환은 출생·죽음과 무관 |
| 7 | 재생/번식·Utility/PPO 평가·스트리밍/성능 | 장시간 조건별 생태 변화, 자원/Population 불변식 유지 |

장기 지속에는 식물 재생·종별 번식/유입이 필요하다. 스폰 웨이브는 번식과 구분한다. 목표는 항상 일정 인구를 보장하는 것이 아니라 환경 압력에 따른 변화와 그 원인을 관측하는 것이다.

## 7. 첫 시연과 인수 기준

작은 전용 레벨의 예시: 식물 10개, 초식 6개, 육식 2개. 실제 식물/초식/육식 BP를 처음부터 사용한다. 이 수치는 성능이나 생태 균형의 보장값이 아니다.

1. 접근 전에는 먹지 않고, 도달 가능한 식물에 도착한 뒤 먹기 상태가 된다. 장애물 너머 자원은 원거리 소비되지 않는다.
2. 합계 식물 소비가 잔량을 넘지 않고 실제 지급량만 Energy로 전환된다. 지역 Food = 식물 Biomass 합이다.
3. 육식이 실제 초식을 추격·포획하면 Population이 하나 줄고 보상이 한 번만 지급된다. 동시 공격도 중복 사망/보상이 없다.
4. 이동/먹기/공격/사망 애니메이션이 논리 결과를 표현한다. 표현 생성/제거는 논리 출생/죽음을 만들지 않는다.
5. 기아는 피식 위험을 올리지 않는다. 실제 식물 고갈/피식 위험이 다음 관측에 반영된다.
6. 전체 Alive = 최초 생성 + 실제 후속 생성/번식 − 확정 사망. 식물·시체·Client 프록시는 동물 Population에 포함하지 않는다.
7. 화면 밖 지역·두 Client·Late Join/재진입·30/60 FPS·긴 프레임에서도 권위 결과가 일치한다. 과거 위치 snapshot만으로 현재 소비 거리를 소급 승인하지 않는다.

## 8. 근거와 검증 범위

- 설치 UE 5.8의 MassMovableVisualizationTrait.h, MassVisualizationTrait.h, MassRepresentationActorManagement.h를 확인했다. ActorClass/spawn hook은 엔진 기능이고 ID/snapshot/애니메이션 연결은 프로젝트가 구현한다.
- [Epic UE 5.8 Visualization Trait API](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassRepresentation/UMassVisualizationTrait?lang=en-US): ActorClass/인스턴스 표현 설정. 신규 동물에는 설치 소스의 Movable 파생 Trait를 사용한다.
- [M4 구현 계획](../Roadmap/M4/M4_IMPLEMENTATION_PLAN.md)의 보간·Representation·권위 상호작용 기반을 재사용한다.
- 이번 변경은 계획 문서 작성이다. C++·BP·레벨을 편집하거나 PIE 동작을 검증한 결과가 아니다.
