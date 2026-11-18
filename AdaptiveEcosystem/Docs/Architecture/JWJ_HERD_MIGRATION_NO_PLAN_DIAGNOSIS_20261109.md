# 1102 가뭄 적용 후 이주 계획 없음 — 2026-11-09 진단

## 결론과 증거 수준

최신 사용자 Standalone에서는 가뭄 명령이 정상 적용됐다. 이전 PIE 맵 이름 거절과는 다른 현상이다. 현재 가장 유력한 원인은 **단독 Persistent Herd 구성과 이주의 최소2마리 조건 충돌**이다. 동일 맵·seed20000·사슴12/늑대4의 기존 관측에서 이를 확인했지만, 최신 사용자 실행 로그는 개체별 HerdId를 기록하지 않으므로 해당 실행의 전체 원인을 확정했다고 주장하지 않는다.

Source/에셋/기본값은 변경하지 않았다. 별도 재현은 실행 중 UnrealEditor/LiveCodingConsole 검사에서 시작 전에 거절됐으며 어떤 프로세스도 중단하지 않았다. 새 UBT/PIE/자동화 성공 기록이 아니다.

## 최신 사용자 로그에서 확정한 사실

파일: `AdaptiveEcosystem/Saved/Logs/AdaptiveEcosystem_2.log` (Git 제외).

| 근거 | 내용 |
|---|---|
| line483,1741 | `-game`, SessionName=`Play in Standalone Game`, 패키지 `/Game/JWJ/1102_Integration_JWJ` |
| line1761 | 4지역, 지역별 사슴12·늑대4, 시드20000 |
| line2033, 11:03:52 KST | `[HerdMigration][AuditFoodLoss] Region=JWJ_WildlifeTest Before=35.737011 After=0.000000 SuspendRegen=1` |
| line2086, 11:04:06 KST | `eco.HerdMigration = "1"` |
| 이후 Step124~149 | coordinator/Native 실행 계속 진행. 전체 시뮬레이션 정지가 아님 |
| 11:06:12 KST 종료까지 | 이 로그에 `[HerdMigration] Plan=...` 없음 |

로그는 UTC 시각을 쓰므로 표의 시각은 +9시간으로 환산했다. 가뭄 후 약2분간 실행됐으며 단순히8초 부족 유지 시간을 기다리지 않은 상황은 아니다. HUD 숨김만의 문제도 설명력이 낮다. 실제 계획 생성 시 Source가 Plan 로그를 남기기 때문이다.

## 가장 유력한 차단 조건

[이주 코드](../../Source/AdaptiveEcosystem/Mass/EcoHerdMigration.cpp)의 현재 신규 계획 루프는 동일 Persistent Herd 구성원 수가2보다 작으면 바로 건너뛴다.

```cpp
const auto& Members=Groups.FindChecked(Herd);
if(Members.Num()<2)continue;
```

이 검사는 부족 시간 측정·목적지/경로 평가보다 앞이다. 따라서 **먹이가0이어도, 에너지가 낮아져도, 경로가 있어도 단독 무리에는 계획을 만들지 않는다.** 이 early return에는 차단 사유 로그나 `migration_reason` 설정도 없다.

비교 자료는 `Saved/JWJFoodGrass_20261108/PIE_CameraRetry_Runtime.json`과 동일 폴더 `CameraRetry.log`다. 해당 실행도 동일 맵·시드20000·4지역·사슴12/늑대4였다. 2.016~52.032초의26개 표본에서 WildlifeTest 사슴12마리는 **12개의 서로 다른 HerdId**, 무리별 최대 인원은 계속1이었다. 마지막 표본도 각 개체 `migration_plan=0`, `migration_reason=None`이었다. 이 자료는 11-08의 관찰 실행이며 최신 사용자의 가뭄 실행을 새로 계측한 자료는 아니다.

[가입 처리](../../Source/AdaptiveEcosystem/AI/Social/Herd/EcoHerdProcessors.cpp)에서는 기존 유효 무리 소속이면 이탈 여부를 확인하고, 무리가 없는 개체만 가까운 무리를 찾아 가입한다. 이미 자기 자신으로 된 무리를 가진 개체들을 서로 병합하는 경로는 현재 여기 없다. 자기1마리 무리의 중심도 집계 때 자신을 따라가므로 단순 근접만으로2마리 무리가 되는 것을 기대할 수 없다. Persistent Herd와 화면상 flock/동족 응집 이동은 서로 다른 상태다.

## 아직 배제하지 못한 후속 조건

최신 실행에서2마리 이상 무리가 실제로 있었다면 다음 항목을 확인해야 한다. 현재 로그만으로 이 단계의 정확한 탈락 사유를 분리할 수는 없다.

- 동일 무리의 전원이 같은 출발 지역인지, 기존 계획/cooldown/stranded 상태인지.
- 유효한 route Actor가 실제 runtime에 로드돼 있는지, 출발/목적지와 양방향·인접성이 맞는지.
- life 세계에서 목적지의 유효한 habitat 보고가 있는지.
- 목적지1인당 예상 먹이가 출발지의1.2배 초과이고 최소0.5 이상인지.
- route 시작/끝이 각 Native stage 안에 있고 모든 terrain 이동 검사를 통과하는지.

목적지/경로 후보가 모두 탈락한 개체는 `migration_reason=NoViableKnownRoute`를 받지만, 그 경우에도 현재 코드가 후보별 탈락 로그를 출력하지는 않는다.

## 다음 수정/검증 지점

1. 먼저 최신 실행의 출발 지역별 StableAgentId→HerdId·무리 크기·부족 지속 시간·후보 탈락 사유를 읽기 전용으로 기록한다. 계획이 없을 때도 이유가 보여야 한다.
2. 제품 요구의 단독 개체 이주와 공동 Herd 이주를 구분해, 단독 개체 지원 또는 명시적 초기 무리 저작 중 적용 방식을 정한다. 최소 인원 검사를 조용히 삭제하거나 전역 반경을 크게 올려 통과시키는 방식으로 진단을 대체하지 않는다.
3. 그 다음 실제 계획→Native 이동→RegionId 인계→M4 MigrationIn/Out을 같은1102에서 검증한다. 기존 JYU 성공 기록으로 이 맵의 검증을 대체하지 않는다.

단독 개체 지원은 [1102 후속 개발 계획](JWJ_1102_FOOD_MIGRATION_SATIETY_PLAN_20261108.md)의 요구와 연결된다. `SocialControl=1` 전환은 이 최소 인원 조건을 해제하지 않으며 이번 진단 해결책으로 임의 적용하지 않는다.
