# T04. 이동 보간·불량망·Actor 풀 재사용

상태: 검증 및 실측 기반 보완 명세 / 기준: `8836558` / 책임 제안: 원준 수신·보간·풀, 조연우 AnimBP·IK·오디오.

선행: [T02](02_AGENT_PRESENTATION_REPLICATION.md), [T03](03_MULTICLIENT_AUTHORITY_VALIDATION.md) 최소 구성. 확인: [F05·F06·F15](99_DECISIONS_AND_CONFIRMATIONS.md).

## 1. 목적과 필요성

늦거나 끊겨 도착한 위치를 매끄럽게 보여주되, reset 이후 과거 위치로 되돌리거나 반환된 Actor가 이전 개체의 사망·소음을 이어받지 않도록 한다. Client 렌더링의 안정성과 서버 생태 결과를 분리한다.

## 2. 현재 구현

FEcoClientPresentationFragment는 Previous/Current 두 표본, 서버-Client 시계 offset, 이동/표현/reset/reject 카운터를 가진다. 두 서버 real-time 표본 사이를 clamp 보간하고 첫 표본·불연속은 snap한다. 다수 표본 jitter buffer·외삽·손실 예측은 현재 구현으로 주장하지 않는다.

SyncVisuals는 StableAgentId로 Actor를 바인딩하고 거리·기존 binding bias·ID로 선발한다. 호환 종/클래스만 재사용하며 active+hidden 상한을 지킨다. BindIdentity/ClearBinding에는 cadence·경보 타이머·상태·애니메이션 초기화가 있다. 먼저 이 경로를 검증한다.

## 3. 유지할 수신·표시 계약

| 사건 | 수신 버퍼 | Actor |
|---|---|---|
| 첫 Add/새 identity | Previous=Current, offset 초기화 | 즉시 위치 적용, cue 재생 억제 |
| 정상 이동 | 기존 Current를 Previous로 전진 | 정의된 지연으로 위치 보간 |
| 표현만 변경 | 위치 표본·시간축 보존 | 생사·행동·감각 즉시 갱신 |
| reset revision 변경 | 기존 이동 궤적 폐기 | 작은 위치 변화여도 snap |
| relevance 재진입 | 새 Bubble item 수명으로 시작 | 과거 binding·serial 이어받지 않음 |
| Pool 반환 | 바인딩 해제 | 타이머·오디오·IK·사망/전환 상태 정리 |
| World 교체 | 버퍼·pending Add·offset 폐기 | 이전 epoch Actor 재연결 금지 |

서버 생태 clock과 movement real-time을 섞지 않는다. 이 보간은 Client의 수동 표현이며 서버 Transform을 다시 적분하거나 Native Body에 값을 되쓰지 않는다. 프록시 위치 처리와 Actor 표시에서 같은 위치에 이중 smoothing을 추가하지 않는다.

## 4. 불량망 측정안

아래 수치는 **초기 시험 입력 제안**이며 제품 허용 기준이 아니다. F05에서 장비·실제 목표를 확정한다. 엔진의 현행 network emulation 수단으로 설정하고 명령·단위·실제 적용값을 결과에 기록한다.

| 프로필 | 편도 지연 제안 | 지연 변동 제안 | loss 제안 | 목적 |
|---|---:|---:|---:|---|
| N0 | 0 ms | 0 ms | 0% | 로컬 기준 |
| N1 | 50 ms | 10 ms | 0% | 일반 연결 |
| N2 | 100 ms | 30 ms | 1% | 느린 연결 |
| N3 | 150 ms | 50 ms | 3% | 스트레스, 출하 보장 아님 |

편도/RTT를 구분한다. packet reorder/duplicate로 FastArray callback이 반드시 역순 호출된다고 가정하지 않는다. wire 지연·손실 실행과 수신 함수에 대한 결정적 stale 표본 회귀를 각각 수행한다. 실행 후 emulation 설정을 원복한다.

## 5. 보완 구현 판단

1. F05의 전달 지연·위치 오차·정지 프레임 기준으로 현재 두 표본 보간의 비용과 끊김을 측정한다.
2. 정상 이동의 끊김이 허용 범위를 넘으면 원인을 interval·손실·수신 clock·Actor 예산으로 분리한다.
3. 단순 interval/delay 조정으로 해결할 수 있는지 먼저 확인한다. 숫자는 실측 없이 기본값으로 확정하지 않는다.
4. jitter buffer나 짧은 외삽이 필요하면 최대 지연·최대 외삽 시간·충돌을 무시하는 표시 범위·reset 규칙을 별도 작은 변경으로 정한다.
5. 죽음·teleport·identity 변경에는 예측을 이어가지 않는다. Client 표시 개선으로 서버 충돌·도착·포획을 판정하지 않는다.

## 6. 풀 수명·초기화 명세

반환은 logical death와 다르다. 거리/예산 때문에 살아 있는 개체의 Actor가 반환될 수 있다.

초기화 검토 대상은 StableAgentId/SpeciesId/RegionId, 로컬 Sequence, movement revision, VisualState, 속도·회전 smoothing, 사망·전환 montage, AnimInstance·IK, footstep cadence, 지연 alarm timer, 오디오 재생, label·debug 선택 상태다. 현재 존재하는 필드만 실제 수정하며, 추가 상태가 있으면 명시한다.

풀에 남는 UObject는 다른 world로 넘기지 않는다. 잘못된 클래스는 강제 재바인딩하지 않고 기존 호환성 규칙으로 제거/새 생성한다. 잠재 callback은 이전 ID와 generation을 검사하거나 반환 시 취소한다.

## 7. 검증 시나리오

| ID | 조건 | 기대 결과 |
|---|---|---|
| IP01 | N0~N3에서 직선·급회전·정지 | 오차·끊김 측정, 서버 위치 변경 없음 |
| IP02 | teleport 후 과거 serial 입력 | 과거 거부, 이전 위치로 이동 안 함 |
| IP03 | 위치 거의 동일한 reset | revision으로 보간 초기화 |
| IP04 | 동일 movement+새 visual | 이동 쌍 유지, 새 사망/행동 적용 |
| IP05 | 빠른 이동 중 Off→재진입 | 첫 표본 snap, 긴 궤적 가로지름 없음 |
| IP06 | 죽은 사슴 Actor를 산 사슴에 재사용 | 죽음·IK·발소리 잔류 없음 |
| IP07 | 경보 예약 직후 반환 | 다른 ID에서 과거 경보 안 울림 |
| IP08 | 사슴/늑대 비율 급변 | 호환 클래스만 재사용, active+pool 상한 |
| IP09 | serial wrap 부근·중복 표본 | T02의 순서 판정 유지 |
| IP10 | 20/30/60 FPS Client | 시각 차이는 계측, 논리 결과/권위 변화 없음 |

## 8. 완료 조건·산출물

현재 알고리즘으로 충족한 범위와 미충족 범위를 수치·영상으로 남긴다. pool 반환/생성/재사용/클래스 불일치 수, reset·stale 수, frame p95/p99, 관심 개체별 오차·수렴 시간을 기록한다. 불량망에서도 불변식·identity·생사 안전 조건은 모두 통과해야 한다. 부드러움의 제품 통과 여부는 F05 확정 후 판정한다.

## 9. Source 근거

- [수신·보간](../../../Source/AdaptiveEcosystem/Mass/EcoMassPresentationFragments.h)
- [시각 선발·풀](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePresentation.cpp)
- [Actor binding·오디오·애니메이션](../../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.cpp)
- [M4 표본 계약](../../Integration/M4_RUNTIME_INTEGRATION_CONTRACT.md)
