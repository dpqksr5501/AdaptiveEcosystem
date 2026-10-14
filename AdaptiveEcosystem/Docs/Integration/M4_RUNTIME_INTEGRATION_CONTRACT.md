# M4 통합 실행 계약 — 이번 구현의 결정

기준 `3062180` 위 working tree / UE 5.8 / 2026-10-13. Source 구현 설명이며 자동화·렌더·성능 통과 증명은 아니다. [검증 상태](M4_IMPLEMENTATION_PROGRESS.md).

새 레벨에서의 조립은 [수동 배치 가이드](M4_NEW_LEVEL_MANUAL_SETUP.md)를 따른다. `ValidateEditorSetup`은 레벨을 수정하지 않는 기본 검사이며, runtime template 검사와 지면 검증이 이를 보완한다. Config 역할/필수 fragment/Client 금지 논리 요소를 확인한 뒤 Entity를 생성한다.

## 생명주기와 사건 순서

Box의 `UEcoMassLifecycleSubsystem`과 Creature의 `AEcoCreatureIntegrationSpawner`는 서로 배타적인 월드 coordinator다. 둘을 같은 맵에 배치하는 가드는 유지한다. 이동 writer는 Box의 엔진 Movement, Creature 초식의 Steering, 늑대의 기존 PredatorMovement로 구분한다. Social은 Request/Feedback과 예약을 소유한다.

Creature는 `OnWorldPostActorTick`에서 Mass 작업 종료 뒤 clock을 한 번 전진한다. 생존/자원은 최대 1초 간격, phase/wave/수동 사건/이주/개체 식사 예정 시각을 앞선 경계로 사용한다. 한 프레임의 catch-up은 설정 상한까지만 처리하고 남은 시간은 삭제하지 않는다. 실제 지형/충돌 이동은 과거 시간으로 다시 적분하지 않는다.

완료 step 순서:

1. 종별 생존 adapter → HP/Energy·기아·사망 후보 → 공통 Death commit, 태그/Travel/feeding/예약 정리.
2. Ecology Death receipt → 원인별 집계·피식 기록. 확인된 predator ID에만 opt-in 포획 보상.
3. 살아 있는 전체 인구 검증 → World 환경 snapshot → 자원 재생·감쇠·명시적 손실/공급.
4. opt-in wave 생성·인구 반영·spawn 예약 확정. 실제 birth 시각 이전의 catch-up 식사를 거부.
5. 행동/공간 조건으로 feeding 요청 → Ecology 배분 → 전체 결과 ID/epoch/step/지역/생존/중복 검증 → Energy 반영 → 자원 원장 완료.
6. 실제 도착 commit → 새 인구/압력 snapshot → 이주 의도 결정. Resident의 종별 속도를 이주 coordinator가 0으로 만들지 않는다.
7. 동일 완료 시각의 지역/종 요약 → GameState 단일 DTO. 종별 누적 Birth/Death/MigrationIn/MigrationOut과 현재 Population을 검증한다. 멸종 row는 0 population과 사망 회계를 유지한다. 표현·소음은 별도의 매 프레임 읽기 소비다.

Dead의 잔류/삭제는 프로필로 제공한다. Client relevance Remove/Actor 반환은 권위 Death/Population을 만들지 않는다. 살아 있는 Entity를 외부에서 직접 destroy하면 인구 보존 검사로 중단한다. 임의 despawn/언로드를 지원하는 저장 복원 API로 간주하지 않는다.

## 복제와 표시 시계

| 값 | 소유/의미 | 갱신 |
| --- | --- | --- |
| `SampleSequence`, `ServerSampleRealTimeSeconds` | 연결별 실제 movement 표본 | Transform/reset/identity 변경 시만 |
| `VisualRevision` | HP/Energy/life/속도/행동 payload revision | 표현 변경 시; 이동 serial과 별개 |
| `MovementDiscontinuityRevision` | 권위 teleport/reset | 위치 변화가 작아도 증가 |
| Actor의 로컬 `Sequence` | 렌더 호출의 순서 | 수신 stale 판정에 사용하지 않음 |
| Ecology clock / completed Step | 생존·자원·집계 시간 | 서버 coordinator가 전진 |

동일 identity에서 과거 이동 serial은 거부한다. 이동 serial이 같아도 새 VisualRevision은 수신하며 movement Previous/Current 시각을 바꾸지 않는다. 동일/과거 두 값은 거부한다. 첫 Add/reset은 snap, 정상 이동은 두 표본 사이에서 clamp 보간한다. 외삽·손실 보정·다수 표본 jitter buffer는 구현하지 않았다. 표본의 real-time과 Ecology clock을 혼합하지 않는다.

HP/Energy의 두 기존 전송 필드는 호환성을 위해 남겼지만 같은 `EcoRepresentation::QuantizeUnit` 반올림 규칙을 사용한다. 그 중복을 wire 최적화 완료로 주장하지 않는다. velocity-only는 연결 interval을 따르고 HP/life/flag/reset/region 변경은 우선 처리한다.

연결의 관련 항목/Add 상한은 한 Bubble에서 모든 Template을 합산한다. 현재 관련 항목은 유지하고 초과 신규 후보를 보류하며 엔진이 다음 callback에 재시도한다. 전 후보 거리순 eviction은 별도다. 로컬 Actor는 거리·binding 유지 bias·Stable ID로 선발한다. 풀 반환 시 identity/cadence/상태를 초기화하며 호환 클래스만 재사용하고 active+hidden 상한을 유지한다.

## 정책과 환경

V1 7→64→64→4와 기존 가중치를 유지한다. 기본 관측 5는 Ecology 지역 의미다. `eco.Policy.PredationSource 1`의 전역 EMA는 명시적인 실험이며 production 계약 전환이 아니다. 피식 EMA의 분모는 전체 alive prey snapshot의 cell별 수로 계산한다.

정책은 8/60초와 경과 dt를 사용한다. 한 프레임에 한 번 추론하고 긴 frame의 결정 debt를 보존한다. 초기 ID phase와 원거리 배수는 agent runtime에 저장한다. 죽은/pending/Client proxy를 배제한다. 모든 chunk의 due 입력을 모아 Native 수치 추론만 선택적으로 worker에 보내며 UObject/World 조회·새 fragment view의 output commit은 Game Thread다. 예외 관측/출력은 Utility fallback과 카운터로 드러낸다.

기존 `Perception → Predation → Steering` 관계를 보존했다. RL 브랜치의 포획 순서 변경을 같이 적용하지 않았다. 최종 Social/이주/지형/경계 속도 뒤 heading을 쓴다. FPS별 정책 주기가 같아도 모든 포획·물리 결과의 FPS 독립성이나 Python 전체 replay를 보장하는 것은 아니다.

World의 Rainfall은 완료 자원 경계에 snapshot된다. Ecology의 opt-in 재생 반응은 `Rate × lerp(Dry, Wet, Rainfall)`, 실제 증가는 capacity까지다. 기본 Rate=0, rainfall response=false라 기존 고갈 검증을 유지한다. 이 수치는 날씨 성장 학습/식물 Entity를 추가한 정책이 아니다. Client 하늘/날씨는 GameState 요약을 Adapter Blueprint 이벤트로 받아 표시하며 논리 상태를 수정하지 않는다.

비복제 level Actor의 ROLE_Authority와 World simulation authority는 다를 수 있다. 환경 Adapter는 World NetMode로 권위를 판단한다. `ApplyRainfall`은 biome의 기존 온도/습도를 유지하며 강수량/WeatherState만 갱신한다. `ApplyWeather`는 전체 환경 입력을 의도적으로 교체할 때 사용한다.

## 후속 범위

V3/M8/새 모델·마스크·Social 예외는 RL export와 명시적 새 계약 뒤 진행한다. 원 계획의 authored 식물·추가 종·두 대륙·지속성도 A~F 이후 추가 범위다. cook·GUI PIE·packet/CPU 측정·512 규모·soak는 마일스톤별 수동 문서에서 확인하고 실제 수행한 결과만 진행 기록에 남긴다.
