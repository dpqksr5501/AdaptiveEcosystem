# T10. 원격 플레이어 이동 입력·서버 논리 소음·로컬 오디오

상태: 기존 기능의 네트워크 회귀·필요 보완 명세 / 기준: `8836558` / 책임 제안: 원준 입력/권위, 조연우 감각·발소리, 권신혁 v3 위협 의미.

선행: [T01](01_RUNTIME_CONFIGURATION_AND_AUTHORITY.md), [T03](03_MULTICLIENT_AUTHORITY_VALIDATION.md). 확인: [F16](99_DECISIONS_AND_CONFIRMATIONS.md). 연계: T02/T04/T05.

## 1. 목적과 필요성

원격 Client의 걷기·잠행·달리기 의도가 서버 속도·실제 이동·소음과 일치해야 한다. 화면에서 듣는 발소리 수가 서버의 감지 사건 수를 결정하지 않게 한다. Host만 정상이고 원격 참가자는 다른 규칙을 적용받는 문제를 검증한다.

## 2. 현재 구현

UEcoPlayerEcologyComponent는 replicated Gait와 ServerSetGait를 사용한다. enum은 Walk/Sneak/Run이며 OnRep_Gait는 360/270/900 cm/s 속도를 설정한다. 현재 값과 enum 상한 검사가 있다.

서버가 CharacterMovement의 실제 위치·속도·접지 상태와 cadence를 읽어 Player.Footstep을 보고한다. 잠행/걷기/달리기 소음 크기는 현재 .12/.4/1, 기본 범위 입력은 2000 cm다. 이는 현재 사실이며 이번 문서에서 새 튜닝값으로 채택하는 것이 아니다.

Client/Listen의 LocalAudio는 수동 오디오를 재생한다. Dedicated는 로컬 오디오를 만들지 않는다. bThreatEnabled 기본은 true이고 v3에서 플레이어를 위협 관측으로 소비하는 경로와 Native 도주 반사의 대상은 동일하지 않을 수 있다.

## 3. 경계와 범위

포함: owning Client gait 요청·서버 검증·속도 교정·복제, 서버 소음 1회, 감각/경보 전달, 로컬 오디오·표면 회귀.

제외: 새 공격/총기/포획 규칙, Client 소음 위치·크기 주입 RPC, 매 발걸음 multicast, PPO 관측·도주 수치 임의 변경.

F16에서 플레이어를 관찰자/위협 중 무엇으로 볼지 결정한다. 관찰자 모드가 로컬 UI만 끄고 서버 ThreatSource는 남기는 상태가 되지 않게 한다. 실제 입력 binding은 현재 bUseKeyboardGait와 외부 SetGait 중 하나를 활성화한다.

## 4. 요청·결과 처리

```text
소유 Client의 gait 의도 → 기존 소유 component RPC
 → 서버 enum·소유·현재 pawn 상태 검증
 → 서버 gait/CharacterMovement 속도 확정 → replicated Gait
 → 서버 실제 이동 cadence → 논리 Noise
 → 서버 감각/정책/경보 → T02 표현 복제
```

1. Client는 enum 의도만 보낸다. 원하는 위치·소음 크기·위협 강도를 정하지 않는다.
2. 현재 서버 RPC 검사는 enum 범위가 중심이다. 사망·관전자·입력 잠금 같은 실제 pawn 모드가 있다면 허용 gait 조건을 추가한다.
3. 서버가 거부한 의도는 authoritative state로 교정한다. 현재 local 선적용 값이 서버 값과 다를 때 복원되는 경로를 확인한다.
4. 소유하지 않은 pawn 요청은 엔진 ownership과 프로젝트 검증으로 거부한다. 서버 역할을 local bIsLocallyControlled와 혼동하지 않는다.
5. keyboard polling과 Enhanced Input/BP binding이 동시에 요청을 덮어쓰지 않게 한다.
6. 요청 반복이 실측 문제라면 값 변경시에만 전송하고 필요한 최소 rate 제한을 적용한다. 프레임마다 Reliable RPC를 새로 추가하지 않는다.

## 5. 논리 소음과 오디오 계약

| 구분 | 실행 장소 | 권위 영향 |
|---|---|---|
| CharacterMovement 확정 이동 | 서버 | 위치·속도·충돌 권위 |
| ServerCadence/ReportNoise | 서버 | AI가 듣는 위치·세기·사건 |
| Creature 서버 발소리 | 서버 거리 기반 | 애니메이션 LOD와 독립 |
| AnimNotify/LocalAudio | 각 렌더링 peer | 로컬 소리만, AI 입력 없음 |
| Herd alarm 표현 | 서버 결과 → Client cue | 들은 경보를 직접 관측으로 재발행 금지 |

서버 cadence와 애니메이션 접촉은 같은 프레임 사건이 아닐 수 있다. 논리/오디오를 프레임별로 1:1 강제하지 않고 실제 이동 거리·중복 유무·수명으로 검증한다. 물리 재질 분류는 표현 입력이며 Client가 Food/HP/경보 강도를 바꾸는 근거가 아니다.

## 6. 수명·특수 상황

teleport/reset·respawn·possession 변경은 cadence의 이전 위치를 초기화해 거대한 이동 발걸음을 만들지 않게 한다. 공중에서는 ground cadence를 멈추고 착지 소음은 별도 기존 규칙이 있는 경우만 검증한다.

종료·이탈·pawn 교체 시 ThreatSource/LocalAudio·대기 타이머 수명을 정리한다. Dedicated에 로컬 오디오가 생기지 않으며, 원격 pawn마다 여러 component가 중복 등록되지 않게 한다.

비·눈·물 표면의 소리 변화와 Native 청각 변화는 T05에서 같은 환경 의미를 공유하되 각 계층의 책임을 유지한다.

## 7. 검증 시나리오

| ID | 조건 | 기대 결과 |
|---|---|---|
| PN01 | 원격 A가 Walk/Sneak/Run 변경 | 서버·A·B gait 일치, 속도 허용 범위 |
| PN02 | enum 범위 밖·소유하지 않은 요청 | 서버 거부, 상태/소음 임의 변경 0 |
| PN03 | keyboard + BP binding 구성 | 선택된 입력 owner 하나, 왕복 진동 없음 |
| PN04 | 제자리·점프·공중 | 실제 ground cadence 기준, 중복 Noise 없음 |
| PN05 | teleport·respawn·재possession | 큰 거리 jump로 소음 폭발 없음 |
| PN06 | 원격 발걸음→사슴 감지 | 서버에서 1회 사건, Source/정책/표현 연결 |
| PN07 | Client A/B의 로컬 오디오 | 서버 Noise 수가 Client 수에 비례하지 않음 |
| PN08 | Dedicated no render | 논리 Noise 존재, mesh/로컬 오디오 0 |
| PN09 | F16 관찰자 모드 | 서버 threat 의미와 화면 설정 일치 |
| PN10 | 표면·날씨·저 FPS·LOD | 오디오 축소가 서버 감지를 줄이지 않음 |

## 8. 산출물·완료 조건

요청 gait·서버 수락/거부·실제 속도·접지·이동 거리·Noise ID·감지 출처를 RunId/agent/connection으로 연결한 기록을 남긴다. 서버에서 계산한 사건 1회와 Client별 표현 소비를 구분한다.

동시 Client에서 PN01~PN08을 통과하고 F16의 모드가 확정돼 있어야 한다. 기존 속도·세기 변경이 필요하면 gameplay tuning·Python parity 범위를 별도로 기록한다.

## 9. Source·계약 근거

- [플레이어 component](../../../Source/AdaptiveEcosystem/Creature/Player/EcoPlayerEcologyComponent.cpp), [입력·RPC 선언](../../../Source/AdaptiveEcosystem/Creature/Player/EcoPlayerEcologyComponent.h)
- [서버 Noise 서비스](../../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoNoiseSubsystem.cpp)
- [서버 개체 표현·소음](../../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp)
- [표현 Actor·로컬 cue](../../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.cpp)
- [감각 책임·검증 범위](../../조연우/README.md), [플레이어 위협 확인 요청](../../RL_Policy/TEAM_REQUESTS_V3.md)
