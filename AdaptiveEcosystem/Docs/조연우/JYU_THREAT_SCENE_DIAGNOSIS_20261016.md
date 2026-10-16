# 늑대 근접·앉은 사슴·무반응 장면 진단

> 후속 [보호 은신처 구현](JYU_REFUGE_SAFETY_20261016.md)에서 실제 안전 규칙과 새 복사 맵의 수풀·바위 배치를 추가했다. 아래 “미구현”과 원인 분석은 `22eb1b6` 당시 상태를 보존한 기록이다.

2026-10-16 KST, 기준 `22eb1b6`, 원래 프로젝트와 복사 맵에서 확인했다. 사용자의 08:14:17 / 08:14:31 스크린샷, 당시 보존된 에디터 로그, 현재 Source와 새 일반 PIE를 대조했다. 이 변경은 **원인 구분을 위한 읽기 전용 진단과 잘못된 목표 표시 수정**이다. PPO 가중치·시야각·청각 수치·도주/은신처 규칙·이동·복제 구조를 바꾸지 않았다.

## 사진에서 판단할 수 있는 것

1. **앉은 모습은 미감지와 동일하지 않다.** Native `UpdateWildFlight`는 원형 cover 안일 때, 사냥 중 늑대를 감지하면 FLEE보다 HIDE 도착/웅크림을 우선한다. HIDE 표현은 `GoToRest` 클립의 마지막 자세이고 Sleep 클립과는 별개다. 같은 지역의 당시 로그에는 숨기 개체가 있었으며 수면은 0이었다. 첫 사진은 개체 ID/검사 값이 없어 정확한 개인 상태를 확정할 수 없다.
2. **두 번째 사진은 시야각만의 문제라고 보기 어렵다.** 사진의 `Wolf #2`는 Forest의 두 번째 Native 늑대다. 기존 `Saved/Logs/AdaptiveEcosystem.log`의 UTC 23:14:30.527 / 23:14:40.316(한국 08:14:30.527 / 08:14:40.316) Forest 구간은 늑대·스텝 150개 중 포만 휴식 100%, 식사 0%, 추가 포획 0으로 기록됐다. 두 창이 08:14:31을 포함한다. 이는 당시 #2가 사냥하지 않던 근거이며, 사진 속 사슴 각각의 감지 여부까지 증명하는 자료는 아니다.

위협 시야는 **300°(뒤 60° 사각)**, 낮 기본 반경 40m다. 고개 숙여 먹을 때 시야 배수 0.6이면 24m이고 밤에는 줄어든다. 청각은 방향과 무관하지만 느린 걸음은 대체로 4m, 빠른 추격은 최대 40m다. 잠행/포만 걸음은 조용할 수 있다. 화면 카메라가 늑대를 보는 것과 사슴의 논리적 감지는 다르다.

**감지와 위급 경보도 다르다.** Native 관측은 깨어 있는 휴식 늑대도 볼 수 있지만, Social 직접 위협 채널은 사냥 중인 늑대만 발행한다. 따라서 `alarm_sense=None`인데 `nearest_wolf_reason=SeenRestingWolf`일 수 있다. 이를 “시야가 작동하지 않음”으로 판정하지 않는다. 쉬는 늑대는 Native 경계/걸으며 먹기에 영향을 줄 수 있어도 무조건 FLEE하지 않는다.

## 확인된 설계·구현 불일치

`RL_V3_WILD1_SPEC.md`에는 “늑대는 은신처에 못 들어간다 / 은신처는 안전하다”고 되어 있다. 현재 컴파일되는 Source에서는 다음과 같다.

- 통합 무대의 추가 cover는 지면에 생성한 `AEcoShelterAnchor`와 논리적 원이다. 덤불·암석 같은 시각적 엄폐물을 자동 생성하지 않는다. 기본 무대에서는 반경 12m 원 4개가 추가된다.
- Native HIDE는 cover 안에서 웅크리는 반응을 우선한다. Social의 유효 예약도 슬롯으로 이동한 뒤 유지한다.
- Native 늑대의 이동 hook은 지형/장애물을 검사하지만 cover 원 진입을 막는 검사는 없다.
- `EcoThreatV3::PreyCatchMult` / `Step`은 cover의 포획 거리에 배수(웅크림 4)를 적용한다. 무적/포획 제외가 아니며 늑대가 충분히 가까우면 잡힌다.
- 실제 사용자 로그 UTC 23:14:10.314 Forest에도 **웅크림 중 포획 1**이 기록됐다.

따라서 앉은 사슴을 모두 “정상적인 안전한 은신”이라고 설명할 수 없다. **시각적 cover 부족과 안전 계약 미충족이 남아 있다.** 이번 진단 커밋에서 학습 세계의 규칙을 조용히 바꾸거나 늑대의 전역 위치를 PPO 입력에 주입하지 않았다. 물리적 진입 금지/포획 면역 또는 노출 시 은신 중단을 구현할 때는 해당 명세·Python 세계와의 차이·Social lease 해제·경계 밖 이동을 함께 검증해야 한다.

## Inspector에서 바로 구분하기

일반 Play 중 Tab 또는 가운데 마우스로 실제 사슴/늑대를 선택한다.

| 항목 | 의미 |
| --- | --- |
| `executed=2`, `native_in_cover=true`, `hide_arrived=true` | Native cover 안의 숨기. Sleep은 executed=4 |
| `nearest_wolf_reason=SeenHunter / HeardHunter` | 가장 가까운 Native 늑대를 시야/청각으로 인지했고 위협 메타데이터상 사냥 중 |
| `SeenRestingWolf / HeardRestingWolf` | 감지했지만 식사·포만 등으로 사냥 중이 아님 |
| `OutsideSightAndHearing` | 가장 가까운 늑대가 현재 Native 감지 밖. 다른 늑대나 공유 경보까지 없다는 의미는 아님 |
| `Asleep` | 가장 가까운 늑대가 잠들어 Native 감지에서 제외됨 |
| `nearest_wolf_distance_cm`, `nearest_wolf_hearing_radius_cm` | Native snapshot의 평면 거리와 소리 반경 |
| `native_vision_radius_cm`, `native_vision_angle_deg` | 현재 밤/행동 배수를 반영한 시야 반경과 시야각(각도는 JSON) |
| `wolf_hunting`, `wolf_sated`, `wolf_asleep`, `wolf_eat_steps`, `wolf_sated_steps` | 늑대를 선택하면 보이는 실제 위협 상태/남은 시간의 스텝 값 |

새 항목은 authority의 읽기 전용 진단이다. Client에는 기존 표현만 있고 숨은 서버 정책/위협 위치를 새로 복제하지 않는다. `nearest_wolf_*`는 가장 가까운 **Native 늑대**의 마지막 논리 snapshot을 분석한다. Unreal LOS를 포함한 Social 감각과는 구분하며 AI가 소비하는 새 지각이 아니다. Native 이산 스텝과 화면 보간 사이에는 약 0.13초 차이가 있을 수 있다.

Social Request가 유효하더라도 Mode=None이면 Native cover 목표를 `(0,0,0)`으로 덮어 표시하던 오류를 고쳤다. 실제 이동 좌표를 바꾼 것이 아니다. HUD는 불리언을 true/false로 표시하고 늑대 선택 시 상태도 보여준다.

## 이번 검증

- 직접 UBT `AdaptiveEcosystemEditor Win64 Development` 성공(`Build03.log`).
- 전체 자동화 **141개: 140 Success + 1 예상 없는 저장 파일 warning, 실패 0·미실행 0**. 새 검사는 실제 v3 템플릿/지역 snapshot으로 뒤쪽 느린 늑대의 4m 청각, 들리지 않는 사각 구역, 빠른 늑대 청각, 보이는 휴식 늑대, 수면 제외, cover 목표 보존을 확인한다.
- 복사 맵 D3D11 일반 PIE 35초 관찰·정상 종료. 최종 70표본/3,273개 사슴 기록 중 실제 숨기 도착+cover 117건, 보이는 휴식 늑대 옆 GRAZE 262건. 임시 IK 개체는 0이다. 숨기 자세(Anim pose 3)에서 사냥 중 늑대를 본 표본 59건, 들은 표본 40건도 있어 “앉음=못 봄” 가정은 성립하지 않았다.
- [실제 화면](Evidence/JYU_V3/ThreatScenes_20261016.png), [새 진단·사례·회귀 결과](Evidence/JYU_V3/ThreatScenes_20261016.json), [사용자 촬영 시각 Forest 로그 발췌](Evidence/JYU_V3/ThreatScenes_user_log_20261016.txt). 개별 사진 속 개체를 새 PIE의 개체와 동일 개체로 단정하지 않는다.
- 전체 원시 로그/관찰은 `Saved/SceneAudit_20261016/`. 사용자 에셋 변경 68개 SHA256을 대조해 보존했다. 이번 변경은 transport/이동 변경이 없어 네트워크 실행은 반복하지 않았으며 이전 `22eb1b6`의 서버/Client 검증을 새 실행처럼 기재하지 않는다. 기존 에디터 시작 전 LowLevelTestAdapter 진단 15개도 그대로이며 이번 수정으로 해결했다고 주장하지 않는다.
