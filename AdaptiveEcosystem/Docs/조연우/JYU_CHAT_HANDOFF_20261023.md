# 조연우 최신 작업 인수인계 — 2026-10-23

**후속 구현 재개는 [팀 AI 공통 안내](../Team/ECOSYSTEM_AI_COLLABORATION_20261024.md)와 [life-v1 최신 인수인계](../Architecture/ECOSYSTEM_LIFE_HANDOFF_20261023.md)를 먼저 읽는다.** `ecfd82f` 이후 Source/owned `LV_JYU_Ecosystem`은2026-10-24에 **`d095948`**로 기록했다. 아래 공개 PR/이주 기준과 당시 push 상태는 그 작업 이전의 이력이다. 새 공유 상태는 현재 PR/Git에서 확인한다.

이 문서는 다른 채팅에서 재개할 때의 시작점이다. 구현 기준은 `581ce1d`(이주·신호·표현)와 `e22dbbd`(경로·목적지 시각화), 통합한 main은 `a74fcac`다. 이 문서 추가는 문서 감사이며 새 빌드·PIE 실행을 의미하지 않는다.

## 작업 위치와 공개 상태

- 원래 저장소의 `AdaptiveEcosystem/AdaptiveEcosystem.uproject`, UE 5.8을 사용한다. 별도 worktree에서 이어가지 않는다.
- 브랜치: `codex/social-shelter-handoff`.
- [PR #14 — 먹이 부족에 따른 무리 이주 기능 추가](https://github.com/dpqksr5501/AdaptiveEcosystem/pull/14)는 2026-10-23 확인 당시 OPEN·Ready for review·미병합이며, 기능/디버그 커밋까지 원격에 push했다. 이전 문서의 Draft·로컬 전용 설명은 과거 상태다. 재개 시 실제 원격 상태를 확인한다.
- GitHub Desktop의 과거 Push 81개는 main 병합으로 들어온 선행 이력 78개와 브랜치 후속 3개였다. 81개의 새 이주 기능 커밋을 만든 것이 아니다. push 후 HEAD/origin 차이는 0/0이었다. 이후 문서 커밋은 별도 이력이다.
- PR 설명은 사용자가 요청한 짧은 한글 설명을 유지한다. 개인 발표 파일은 push하지 않는다.

## 지금 연결된 기능

| 영역 | 현재 동작과 책임 | 근거 |
|---|---|---|
| Social 신호 | 직접 감지·개인 기억·같은 Herd의 유효한 공유 경보를 구분하는 버전 1 `ReadSignal`; 반복 수신으로 증거 수명 연장 금지 | [통합 계약](HERD_MIGRATION_AND_SIGNAL_CONTRACT.md), `AI/Social/EcoPolicyV3SocialBridge.*` |
| 행동 표현 | `AlertGraze`, `WeakTravel`, `SatedRest`; 경계 사슴의 이동+목 동작, 실제 저속 이동, 포만 늑대 휴식 | [통합 계약](HERD_MIGRATION_AND_SIGNAL_CONTRACT.md#애니메이션과-은신처) |
| 원인 진단 | 기존 Inspector에 최대 16건 원인 이력·신호·이주·Native 실제 위치; 사슴 v3 중심의 권위 진단 | `Creature/Debug/EcoCreatureInspection.cpp`, `Creature/Runtime/EcoCreatureLifecycle.cpp` |
| 무리 이주 | Persistent Herd 공동 계획 → 기존 Travel → Native 단일 이동 → 실제 지역 진입/context 인계 → M4 이주 영수증/유입·유출/인구 | `Mass/EcoHerdMigration.*`, [통합 계약](HERD_MIGRATION_AND_SIGNAL_CONTRACT.md) |
| 보호 은신처 | 실제 영역의 안전·등록/제거·지면 도착 검증·먹이 장부 거래, 바위 외형 bounds 정렬 | [은신처 계약](JYU_REFUGE_SAFETY_20261016.md), [main 통합](JYU_PR12_MAIN_INTEGRATION_20261022.md) |
| 이주 시각화 | 지도·방향 화살표·현재 목적지·실제 구성원/목표와 단계; 읽기 snapshot을 HUD가 4Hz로 소비 | [디버그 계약](HERD_MIGRATION_DEBUG_20261023.md), `Creature/Debug/EcoHerdMigrationDebug.*` |
| 멀티 | 기존 Bubble에 현재 지역·활동·위치를 전달; Client에 이주 논리/Subsystem을 만들지 않음 | [검증 JSON](Evidence/JYU_V3/HerdMigration_20261023.json) |

Source 상대 경로의 기준은 `AdaptiveEcosystem/Source/AdaptiveEcosystem/`다. Native `Step`만 이동·섭식·대사를 적분한다. Social·Herd·HUD에 두 번째 위치 writer나 복제 transport를 추가하지 않는다.

## 기본값과 혼동하기 쉬운 계약

| 설정 | 현재 기본값 | 의미 |
|---|---|---|
| `eco.IntegratedV3.SocialControl` | 0 | Social 처리는 유지하지만 기본 경보 신호가 v3 Raw Request/Control을 덮어쓰지 않는다. 1은 보존된 기존 행동 개입 opt-in |
| `eco.HerdMigration` | -1 | Spawner `bEnableHerdJourneys`를 따른다. 새 이주 맵 true, 기존 맵 false. 0은 신규 출발만 중지하고 진행 중 계획은 마무리 |
| `eco.HerdMigration.Debug` | -1 | authoring/계획에 따라 자동 표시. 0 숨김, 1 기본, 2 모든 활성 목표 |
| `eco.IntegratedV3.ShelterSafe` | 1 | Python `realism_shelter`와 맞춘 통합 Native 안전 규칙이 보호 담당 |
| `eco.IntegratedV3.ProtectedRefuges` | 1 | 실제 은신처 생명주기 담당. ShelterSafe=0일 때만 기존 JYU 안전 규칙이 보호 담당. 두 안전 규칙을 중첩하지 않음 |

CVar와 Native `FWorldConfig::bProtectedRefuges=false`의 기본값은 서로 다른 층이다. 위 통합 기본값을 전체 Native 기본값 OFF라고 설명하지 않는다. 기존 은신처 기준 세계의 파리티와 **새 무리 이주 ON 세계 전체 궤적 파리티 미검증**을 구분한다. V1 7관측/4출력과 v3 R1b 18관측/5행동·mask2, 기존 가중치를 유지하며 재학습은 하지 않았다.

## 에디터 확인과 화면 읽기

1. `/Game/JYU/Maps/LV_JYU_HerdMigration`을 열고 Play. JWJ 대형 레벨의 owned 복사본이며 원본 JWJ/Map/SHC는 보존했다. 3지역, 지역당 사슴 48·늑대 4, 수풀/바위 은신처 총 12곳이다.
2. 먹이가 충분하면 출발하지 않는다. 권위 Play 콘솔에서 `eco.HerdMigration.Test.Drought Barren`을 실행한다. 실제 먹이를 장부 거래로 제거하고 해당 세션의 재생을 중지하는 개발 fixture다. 다시 Play하면 원복한다.
3. `M`으로 지도 표시, `[`/`]`로 계획 선택. `Tab`/가운데 마우스로 개체 선택, `R`로 Inspector JSONL 기록. `eco.Creature.Labels 0`, `eco.Inspector.Visible 0`으로 화면을 정리할 수 있다.
4. 지속적인 부족 판정과 집결 뒤 실제 이동한다. 개인 위협 회피·저에너지 휴식·재집결이 우선할 수 있다. 명령은 즉시 이주/도착을 강제하지 않는다. `Blocked`는 무진행 진단이며 충돌 확정이 아니다. 가뭄 명령 반복으로 새 여정을 강제 생성하지 않는다.
5. 하늘색은 알려진 경로, 노란 영역/구는 **현재** 목적지와 끝점이다. 복귀 계획이면 목적지도 Barren, 화살표도 역방향이다. 지도 사각형은 전체 지역 지리가 아닌 Native habitat footprint다.
6. `In target` 실제 Region 진입과 `Finished` 경로 끝 도착을 구분한다. 종료 계획에는 복귀와 사망 정리가 포함된다. 모든 무리가 Forest에 성공한 숫자로 읽지 않는다.

현재 검증 경로는 Barren↔Forest다. Highland 개체는 시뮬레이션하지만 연결 corridor는 없다. 기존 `LV_JYU_RefugeSafety`와 `LV_JYU_V3Integration`에서 새 맵과 같은 이주가 자동 활성화되지 않는다. owned 맵 재생성 도구 `setup_jyu_herd_migration.py`는 수동 authoring을 교체하므로 확인 없이 재실행하지 않는다.

## 이전 실행의 검증 근거

| 실행 | 관찰 범위 | 근거 |
|---|---|---|
| 이주 기능 최종 | 직접 UBT Build13 성공, Automation07 203개(202 성공 + 예상 missing-save warning 1), 실패/미실행 0; engine-free evaluator 재컴파일 | [기능 검증](Evidence/JYU_V3/HerdMigration_20261023.json) |
| Dedicated + 순차 Client 2개 | 서버 165초 관찰, 실제 지역 이전 23건, 자원/인구 계약 실패 0. ClientA/B 논리 개체·로컬 이주 Subsystem 0, 은신처 12/12; B는 이전 개체 20마리 Forest 표현 수신 | 같은 JSON |
| 실제 Editor PIE | 120초 관찰, 지역 이전 22건. 집결·휴식·재집결·정체·복귀·정착 관찰 | 같은 JSON |
| 디버그 최종 | 직접 UBT Build04 성공, Automation03 203개(202 성공 + 예상 warning 1), 실패/미실행 0 | [시각화 검증](Evidence/JYU_V3/HerdVisualization_20261023.json) |
| 실제 발표 촬영 Story03 | Build03 PIE, Plan1/Herd30/개체57 Barren→Forest 동일 ID 이전 및 3/3 정착. 명시적 가뭄/관찰자 위협 OFF. 개체 teleport·정책 강제 없음 | 같은 JSON. 최종 Build04의 복귀 화살표 보완은 촬영 후 변경 |

짧은 제어 시나리오의 기능 증거다. 모든 무리 성공·자연 발생 빈도·장기 생태 균형·Shipping/cook·새 디버그의 별도 멀티 실행을 검증한 것으로 확대하지 않는다. uncooked Editor AnimGraph/HLOD import warning은 남아 있다. 원시 `Saved/` 로그는 추적하지 않으므로 다른 체크아웃에서는 체크인 JSON과 재현 도구를 먼저 읽는다.

## 다음 작업 후보와 완료 기준

아래는 아직 구현 완료로 표시하지 않는 후속 제안이다. 새 기능 작업 시 사용자 범위를 확인한다.

1. **장시간 생태 균형**: 가뭄 없는 대조군·장기 부족·목적지 동시 유입을 여러 seed로 관찰해 생존/자원 보존/왕복·실패율을 수치화한다. 성공 장면만으로 균형을 판정하지 않는다.
2. **막힘 원인 세분화**: Native 도주·지형 sweep·구성원 대기·저에너지의 실제 원인을 현재 무진행 진단과 구분한다. 새 이동 writer 없이 기존 단계의 근거를 기록한다.
3. **추가 지역 경로**: World 인접성·지면·수용량을 조사한 뒤 owned 맵에 Highland corridor를 추가하고 양방향 도착/복귀/인구 장부를 검증한다.
4. **RL 공동 계약**: 신호를 Native 반응·학습 관측에 사용할지는 RL 담당과 별도 결정한다. 이주 ON 세계 Python 파리티/재학습·출생/새끼 추종도 별도 작업이다.
5. **배포·멀티 시각화**: 실제 cook/패키징 확인. Client에 계획 지도가 필요하면 승인된 Summary DTO/기존 transport 설계를 먼저 정한다. 현재 권위 debug snapshot을 Client 논리로 복제하지 않는다.

무리 merge/split, multi-hop gossip, 계절 이주, 포식자 공동 이주, 자동 Cover 생성, ORCA/NavMesh는 여전히 미구현/Deferred다. 미연결 실험 코드의 일괄 활성화는 완료 기준이 아니다.

## 발표 자료 위치

사용자 요청으로 최종 PPT는 `C:/Users/I/Desktop/겜캡디_조연우_1023.pptx`에 있다. 원본 1016 PPT는 보존했다. 캡처·대본·대표 자료형 텍스트·렌더/제작 작업은 저장소 밖 `C:/Users/I/Desktop/AdaptiveEcosystem_발표자료/2026-10-23/`에 있다. 대표 자료형은 실제 `FEcoHerdJourney`이며 설명은 구현 나열보다 실제 부족→집결→이동→도착/정착 장면 중심이다. 개인 파일은 저장소에 추가하지 않는다.

문서 감사 범위와 확인 방법은 [문서 갱신 기록](JYU_DOCUMENTATION_AUDIT_20261023.md)을 따른다.
