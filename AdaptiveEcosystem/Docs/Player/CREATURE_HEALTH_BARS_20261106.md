# 개체별 공통 체력 바

2026-11-06, 작업 브랜치 `jwj-1024`. 현재 변경은 로컬 작업이며 아래 검증 상태를 따른다.

## 동작과 재사용

`AEcoCreatureRepresentationActor`의 기본 `HealthBar` 컴포넌트를 모든 파생 종 Blueprint가 상속한다. 현재 생태계 사슴·늑대의 기본/Integrated/JYU 표현에 같은 경로가 적용된다. 맵이나 각 Blueprint를 다시 저장할 필요는 없다. 아직 구현하지 않은 종의 실행 backend를 추가하는 기능은 아니다.

`UEcoHealthBarComponent`는 수신 체력만 표시하는 screen-space WidgetComponent다. 머리 위 위치의 112×18 UI에 체력 비율과 %를 표시한다. 50% 초과는 초록, 25% 초과는 주황, 그 이하는 빨강이며 가득 찬 체력도 표시한다. 명시적 사망은 0%, 체력 미수신/풀 반환은 숨김이다. Actor 재바인딩 시 이전 체력을 지우고 새 표본을 기다린다. 개체 크기에 따라 부착 위치는 따라가고 UI의 화면 크기는 일정하다.

새 Actor에도 컴포넌트를 부착하고 기존 권위/복제 경로에서 `SetHealth(CurrentHealth, MaxHealth, bAlive)` 또는 `SetHealthNormalized(Fraction, bAlive, bHasHealth)`를 호출할 수 있다. 이 함수는 피해·회복·복제를 수행하지 않는다. 기본 widget은 C++로 생성하므로 별도 Widget Blueprint 에셋을 요구하지 않는다. 개별 종의 HealthBar relative location/draw size는 상속 컴포넌트에서 조정할 수 있다.

## 권위와 데이터 경로

기존 서버 공격 검증 → 완료 경계 `ApplyPlayerDamage` → `FEcoVitalsFragment` → presentation byte → 기존 Mass bubble → Client presentation → `ConsumeVisualState` → HealthBar를 사용한다. 새 RPC/체력 writer/이동 writer나 Client 논리 fragment를 추가하지 않는다. 피해는 관련 Client 모두에게 기존 중요 상태 delta로 전달되며 체력 바가 별도 polling RPC를 보내지 않는다.

표시는 기존 connection relevance와 representation 예산 안에서 실제 생성된 개체 전체에 적용한다. 관심 밖/표현 예산 밖의 모든 논리 개체를 별도 Actor로 생성하지 않는다. 네트워크 주기와 지연은 기존 transport를 따르므로 무지연 표시를 보장하지 않는다. 전송 값은 0–255 체력 비율이므로 정수 HP/MaxHP를 추정해 쓰지 않고 %로 표시한다. 낮은 양의 HP가 0으로 양자화되어도 사망 여부는 명시적 life 상태로 판단한다.

Dedicated server에서는 UI 생성과 tick을 실행하지 않는다. Client는 표시만 수행한다. 기존 V1/v3 정책·가중치·대사·피해 수치·관심 예산을 변경하지 않는다.

## 에디터 검증 입력

Unreal `AActor::GetFunctionCallspace`는 `GAllowActorScriptExecutionInEditor` 동안 RPC를 local로 취급한다. Python에서 `PressConfiguredAction`을 직접 호출하면 원격 combo가 local에서 거절되거나 LocalPredicted aim이 재귀 prediction 오류로 이어질 수 있다. 이 결과를 실제 사용자 입력의 네트워크 성공/실패 증거로 사용하지 않는다.

공통 action adapter는 에디터 스크립트가 실행 중인 game world 요청만 다음 게임 틱으로 미룬다. 약한 참조와 ASC/controller 일치·local possession을 재검사하고 유효한 authored action만 기존 GAS 경로로 전달한다. 일반 게임 입력은 기존 즉시 실행을 유지한다. 스크립트가 임의 피해나 서버 권위를 얻는 경로는 아니다.

## 검증

- 최초 직접 UBT `AdaptiveEcosystemEditor Win64 Development` 성공.
- 최초 Creature 자동화 26개 중 25 Success, 1 Fail. 새 `AdaptiveEcosystem.Creature.Visual.HealthBarReplicationAndPooling` 성공. 실패는 기존 `Creature.JYU.RefugeVisualComposition`의 누락된 MWLandscapeAutoMaterial 수풀/바위 mesh 검사이며 이번 변경에서 에셋을 대체하지 않았다.
- 렌더 Client에서 체력 바의 화면 표시와 수신 표본/컴포넌트 값 일치를 확인했다. 최초 두 Client 공격 검증은 에디터 스크립트 RPC 실행 문제로 실패했으며 성공으로 기록하지 않는다.
- 입력 adapter 보완 후 직접 UBT 성공(`Saved/IntegrationBuilds/Milestone_Final_20261106_114131.log`). 관련 Visual+Combat 자동화 **11개 성공/실패 0**이며 1개는 기존 GameplayCueNotifyPaths 미지정 warning을 포함한다(`Saved/HealthBarValidation/Regression/index.json`).
- 렌더링한 Dedicated server+실제 두 Client에서 **Server/A/B 모두 PASS**. A·B가 같은 StableAgentId=1 개체를 각각 1발씩 공격했고 서버 HP **100→70→40**, 두 Client의 바 비율 **1.0→0.70196→0.4**를 확인했다. 양자화 오차는 기존 byte/255 계약이다. 두 Client 모두 수신한 사슴·늑대 전체에 공통 바가 있고 수신 표본과 값이 일치하며 권위 개체 0이었다. 개체 relevance 범위 밖 전수 표시나 WAN 지연/대규모 UI 성능 검증은 아니다.
- 빈 체력 영역을 어두운 색으로 바꿔 % 글자 대비를 개선하고 최종 직접 UBT 성공(`Saved/IntegrationBuilds/Milestone_Final_20261106_114958.log`)과 화면을 확인했다. 최종 렌더 네트워크 재검증도 **Server/A/B 모두 PASS**, 각 Client 1발, 서버 최종 HP40/두 Client 최종 비율0.4였다. 관련 결과는 `Saved/HealthBarValidation/Network/{Server,A,B}.json`이다.
- 반복 실행 중 자동 조준의 빗나감과 fixture의 로컬 Actor 이름 충돌을 관찰했다. 최신 fixture는 복제된 PlayerId로 사격자를 식별하고 공격 중인 플레이어를 늑대의 이동 방향에 두며 나머지 관찰자는 뒤에 배치한다. 서버 위치 표본을 이용하는 시험 장치이므로 실제 사용자의 수동 조준 적중률·지연 보상 검증으로 설명하지 않는다.

검증 중 근접 콤보의 기존 `EcoAttackNotifies.cpp::Send`에서 수신 컴포넌트가 새 hit component를 생성하면 ranged-for container 변경 ensure가 발생하는 것도 관찰했다. 이 파일/콤보 동작은 이번 체력 바 변경에서 수정하지 않았다. 최종 네트워크 acceptance는 기존 장착 총기 경로를 사용한다. Owner damage outcome callback의 완전 전달도 이번 바 검증의 완료 범위로 확대하지 않는다.

재현 도구: `Tools/Editor/run_health_bar_network.ps1 -RenderedClients`. 기존 `/Game/JWJ/1102_Integration_JWJ`와 common player를 사용한다. fixture는 서버 플레이어 위치/무적을 제어하고 테스트 전용 파일로 서버 대상 위치를 공유해 Client 조준에 사용한다. 이는 움직이는 대상의 보간 지연에 따른 빗나감을 줄이기 위한 UI 시험 장치이며 일반 플레이어에게 권위 위치를 보내는 기능은 아니다. 기존 소유자 입력→GAS→총기 RPC→서버 무기/시선/거리/차폐/표현 준비 검증→실제 Trace→피해 큐를 통과한다. 체력 감소를 수신하면 해당 Client는 재발사를 멈춘다. 양쪽 공격 구간의 서버 HP와 각 Client 수신 바, 모든 수신 사슴·늑대의 바 일치, Client 논리 권위 0을 검사한다. 개체 HP·위치·체력 바 값을 fixture가 직접 쓰지 않는다. 결과는 `Saved/HealthBarValidation/`에 남고 Git에 넣지 않는다. 렌더 캡처는 `Saved/Screenshots/WindowsEditor/`에 남는다.
