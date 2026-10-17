# 과밀·기아 기반 코드 검증 기록

2026-10-06, UE 5.8. 자동화 테스트는 작성·실행하지 않았다. 에셋과 기존 사용자의 레벨 변경은 저장/수정하지 않았다.

## 수행한 검증

- AdaptiveEcosystemEditor Win64 Development UBT 빌드 통과. 기존 StructUtils 및 MassEntityHandle include deprecation 경고 유지.
- 기존 `/Game/JWJ/Jang_lv`를 UnrealEditor-Cmd의 Standalone/NullRHI로 실행. 기존 레벨/프로젝트 설정 사용, benchmark 고정 30 FPS. 네트워크/렌더 테스트는 아니다.
- 150초 실행에서 FoodShortage 원인의 분산 출발과 동일 ID의 A→B 도착 확인.
- 300초 실행에서 실제 성공 Spawn=64, Starvation Death=64, 고유 Death ID=64, 마지막 일일 Alive=0. 200초 요약에서는 Alive=53, 220초부터 0. Dead 잔류 후 제거 로그 확인. 생태계 Error/Assertion/Fatal=0.
- 순수 과밀 전용 레벨, 수동 공급 회복, Host/Client, Late Join, 저 FPS/긴 frame, 대규모 성능은 아직 미검증. 에디터 테스트 문서에 분리된 설정/시나리오 제공.

실행 로그:

- `AdaptiveEcosystem/Saved/Logs/EcoSurvival_Standalone.log`
- `AdaptiveEcosystem/Saved/Logs/EcoSurvival_Death.log`

Saved 로그는 로컬 실행 산출물이다. 테스트 진행 후 필요한 기록만 따로 보관한다.

## 최종 빌드와 재실행

- 최종 UBT 빌드 성공 (`AdaptiveEcosystemEditor Win64 Development`, Result: Succeeded).
- 최종 변경으로 Jang_lv Standalone을 300초 실행. 시작 시 `Debug.FoodSupply Forest_A 5` 및 `eco.M4.Dump details`를 실행했다.
- 공급 요청 5가 다음 자원 단계에서 실제 5로 적용되고, 자원 보존 오류 없이 진행했다.
- 이번 실행은 추가 공급으로 정규 Spawn 결과도 달라져 성공 Births=65, Starvation Death=65, 고유 Death ID=65, 최종 Alive=0이었다. 200초 Alive=54, 220초부터 0. 공급으로 인구를 직접 증가시킨 것이 아니라 정상 웨이브가 추가 개체를 생성했다.
- 서로 다른 Region으로 완료된 이주 로그 15건을 확인했다. 완료 이주 원인이 FoodShortage로 보존되며, 초기 Region 요약/개체 Vitals 진단도 정상 출력됐다.
- 생태계 Error/Assertion/Fatal=0, `git diff --check` 통과. 최종 로그는 `AdaptiveEcosystem/Saved/Logs/EcoSurvival_Final.log`.
- 죽기 직전의 공급 회복, 순수 과밀만 발생시키는 전용 프리셋, Host/Client 사망 전달 및 성능은 별도 수동 확인이 필요하다. 앞선 Standalone 기록을 이 항목들의 통과로 해석하지 않는다.

## 구현 범위와 한계

현재 M3 Box 경로에서 섭취 회복, 시각 기반 대사, 기아 피해, 단일 사망 commit, 예정 유출/유입을 고려한 과밀·식량 전망 이주, Spawn 억제, 요약/진단을 연결했다. Server/Standalone만 논리 상태를 계산한다.

HP=0인 외부 피해는 공통 commit 경로에서 ExternalDamage로 처리하지만, 기존 별도 PPO/Social 포식 경로와 플레이어 RPC 진입점을 이 Box 구성에 통합한 것은 아니다. 원인 미확정 외부 피해를 포식으로 추정하여 위협을 올리지 않는다. PPO V1 입력/행동 차원과 Legacy Evolution은 변경하지 않았다.

Food 재생이 없으므로 이번 300초 실행의 전멸은 음식 고갈 후 기대 가능한 결과다. 장기 평형이나 성능 달성을 의미하지 않는다. Dead 표본은 잔류 시간 동안 최선 노력 전송하며 ACK가 없다. 최종 사망 애니메이션은 아직 없다.
