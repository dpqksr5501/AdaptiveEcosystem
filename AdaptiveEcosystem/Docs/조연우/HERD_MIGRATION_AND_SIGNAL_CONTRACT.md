# 무리 이주와 v3 신호 통합 계약

> 화면에서 변화를 확인하려면 [이주 경로·목적지 디버그](HERD_MIGRATION_DEBUG_20261023.md)를 따른다. 새 맵에서는 자동 지도, `M` 표시 토글, `[`/`]` 무리 선택을 지원한다. 시각화는 아래 행동 계약을 변경하지 않는다.

2026-10-22 시작, 2026-10-23 갱신. 작업 기준 `3cc772e` (PR #12 main 통합 이후). PR #14는 사용자 요청으로 **Draft** 전환했으며 이번 기능을 자동 병합하지 않는다. 실행 증거와 마지막 인계는 아래 검증 절을 따른다.

이번 구현·검증·맵은 현재 브랜치의 **로컬 커밋**으로 보존하고 원격 push는 하지 않는다. 최종 확인한 PR #14의 원격 head는 `5e270f4`, Draft=true·merged=false다. 따라서 원격 PR에는 아직 이번 로컬 작업이 들어 있지 않다. 이어서 작업할 때 로컬 HEAD와 원격 상태를 다시 확인한다.

- v3 경보는 개인 직접 감지/기억/전달받은 경보를 구분한 읽기 신호다. 기본 경로는 Raw Request·Control을 경보로 덮어쓰지 않는다. 기존 V1과 opt-in SocialControl은 호환 경로로 유지한다.
- Herd는 공동 계획과 구성원 정체성을 소유한다. 공통 Travel/지역/생명주기와 Ecology 원장을 사용하며 새 복제 transport를 만들지 않는다.
- Native의 동일 결정 스텝에서만 이동·섭식·에너지를 계산한다. 이주 제어 훅은 목적 방향을 제공하고, 경계 개방은 이주 구성원에게만 적용한다. 위협 회피가 우선이며 슬롯 부족으로 이미 보호 영역 안의 개체를 내보내지 않는다.
- 계획은 등록된 인접 지역 경로만 대상으로 한다. 출발 준비·식량 부족 지속·도착 예정 수요·재이주 대기·진행 정체/실패·휴식·재집결을 기록한다. 공간 검사에 실패한 경로를 순간이동으로 보정하지 않는다.
- 실제 도착 때만 같은 ID의 지역과 Native context 좌표를 인계하고 공통 Migration receipt/종별 유입·유출을 기록한다. Herd ID는 지역 경계를 넘어 유지한다. 사망한 구성원은 계획 집계에서 제외한다.
- 이주는 별도 opt-in Unreal 세계 규칙 확장이다. 기존 가중치와 V1/18차원 관측을 변경하지 않는다. 기본 OFF 세계의 Golden 기준을 보존한다. 새 규칙 ON의 Python 전체 궤적 파리티/재학습을 완료로 주장하지 않는다. 엔진 없는 평가기는 헤더 변경 후 다시 빌드한다.
- 팀 레벨은 읽기 감사 후 owned 복사 레벨에서 authoring한다. 원본 팀 레벨 변경과 개인 브랜치의 미병합 정책 변경은 자동 적용하지 않는다.

## 실제 연결과 소유권

| 입력/결과 | 연결된 기존 시스템 | 이번 연결 |
|---|---|---|
| 개인 감지·기억·무리 경보 | 신혁 Native perception, 조연우 Sensory/Herd/Alarm | `EcoV3Social::ReadSignal` 버전 1 읽기 계약 |
| 지속적인 먹이 부족 | Native 실제 Food grid → M4 Ecology resource ledger | 완료된 자원 단계에서 부족 지속 시간·예상 유입 수요 판단 |
| 무리의 공동 목적지 | Persistent Herd → `UEcoHerdMigrationSubsystem` | roster 고정, 준비/이동/재집결/휴식/정착/막힘 기록 |
| 목적지까지 실제 이동 | `IntegratedControlHook` → Native `Step` → 기존 terrain sweep | 방향·속도 의도만 공급. Native 개인 위협 회피가 우선 |
| 실제 지역 진입 | 공통 Region/Travel + Native context | 좌표계만 rebase, 동일 StableAgentId·에너지·비축·Herd 유지 |
| 유입·유출/개체군 | 원준 M4 `RecordMigrations`/종별 합계/GameState | 기존 migration receipt 한 번, 기존 집계/요약/복제 사용 |
| 시각화/디버그 | 기존 Mass Bubble/수동적 Actor/Inspector | 활동 상태, 실제 위치·계획·원인 이력 표시 |

`EcoHerdMigration.*`는 새로운 movement processor가 아니다. `EcoCreatureLifecycle.cpp`의 `CompleteResourceStep` 이후, 기존 이주 영수증·재집계 이전에 실행한다. Mass processing 외 GameThread 경계에서 fragment를 갱신한다. 이주 판단이 같은 프레임에 여러 번 실행돼도 실제 위치 적분을 반복하지 않는다. 레거시 개별 이주와 v3 무리 이주를 같은 개체에 중복 적용하지 않는다. 기존 wave/spawn 정책과 생명주기는 보존한다.

클라이언트에는 이주 Subsystem/계획/논리 Entity를 생성하지 않는다. 기존 transport로 받은 RegionId·활동·위치만 표시한다. `OnRuntimeSample`은 완료된 런타임을 진단 도구가 읽는 2초 간격 로컬 이벤트다. RPC나 복제 transport가 아니며, 리스너가 없으면 호출하지 않는다. Dedicated Server에는 Slate 틱이 없으므로 검증 Python은 이 이벤트를 사용한다. 게임 추론에 Python을 사용하지 않는다.

## 신호 계약과 원인 기록

`ReadSignal(Sense, Alarm, CurrentHerdId, Now, Settings)`는 기존 감각 snapshot의 TTL/신뢰도/무리 일치 검증을 그대로 사용한다. 유효한 개인 증거를 우선하고, 없으면 같은 현재 Herd의 유효한 shared report를 반환한다. 직접 관측, 개인 기억, 공유 경보의 시각과 종류를 구분한다. shared report의 반복 수신이 원래 증거 시각을 새로 만들지 않는다. 공유 채널에 원 관측자의 SourceKey가 없으면 0을 유지하며 식별자를 추정하지 않는다.

기본 `eco.IntegratedV3.SocialControl=0`은 신호만 제공한다. 이 신호 자체를 v3의 새 관측 차원이나 학습 완료된 flee 입력으로 설명하지 않는다. 기존 opt-in SocialControl/V1 handoff는 보존하며, 보호 은신처 안에서 lease 부족만으로 개체를 외부로 밀어내지 않는다.

Inspector는 `decision_reason`, `reason_history` 최대 16건, `social_signal_*`, `migration_*`, `native_world_position`을 기록한다. 원인 또는 지역이 바뀔 때만 추가한다. 사망/Native panic/Native shelter/이주/기존 Social 개입/유효한 공유 신호를 구분한다. 만료된 경보의 저장된 strength만 보고 현재 원인으로 표시하지 않는다. `Tab` 순환, 가운데 마우스 선택, `R` JSONL 기록은 기존 조작을 유지한다. Client는 서버 원인 이력을 직접 생성하거나 복제받지 않는다.

## 무리 이주 규칙

- `eco.HerdMigration=-1` 기본값은 Spawner의 `bEnableHerdJourneys`를 따른다. 기존 맵은 false, 새 복사 맵만 true다. 0은 신규 출발을 멈추며 진행 중 계획은 안전하게 마무리한다. 1은 활성화한다.
- 현재 herbivore Native v3에 적용한다. 구성원 2 이상, 같은 출발 지역, 실제 먹이 비율 25% 미만 8초 지속, 배고픈 구성원 또는 5% 미만의 심한 부족이 필요하다. 순간적인 감소 후 자원이 회복되면 출발하지 않는다.
- `AEcoHerdMigrationRoute`는 두 지역을 잇는 명시적인 경로 지식이다. 실제 World `AdjacentRegionIds`, 양 끝 Native stage 포함, terrain sweep을 모두 확인한다. 경로를 모르면 `NoViableKnownRoute`를 기록하고 3초 뒤 재평가한다. 전 세계 먹이 위치를 전지적으로 탐색하지 않는다.
- 후보는 목적지의 기존 Food/Population과 진행 중 유입 인원을 함께 평가한다. 최소 0.5 자원/예상 개체, 현재 지역보다 개선된 공급, 경로 길이 비용을 사용한다. 이것은 초기 정책이며 수용량을 학습한 결과는 아니다.
- 최대 6초 출발 집결, 70% 집결 기준, corridor 안 분산 목표, 220cm 근접 분리, 3500cm 이상 벌어질 때 선두의 제한된 대기, 저에너지 짧은 공동 휴식을 적용한다. 죽은 구성원은 생존 roster에서 제외한다. 이주 중과 도착 직후 잠깐은 기존 Herd 가입/이탈 거리 규칙이 공동 정체성을 깨지 않는다.
- 25초 무진행은 막힘을 기록한다. 50초 정체 또는 목적지 고갈은 알려진 경로를 역으로 돌아가려 한다. 돌아갈 수 없는 지형을 teleport로 해결하지 않는다. 위협 회피와 지형에 따라 여정이 끝나지 않거나 굶을 수 있다. 성공한 실제 도착 뒤 최소 45초 정착해 왕복 진동을 줄인다.
- 목적지 Native stage에 실제로 들어올 때만 지역 이전 영수증을 발행한다. 경로 끝 도착은 별도의 여행 완료 조건이다. 도착 중인 구성원과 이미 도착한 구성원이 일시적으로 다른 지역에 있을 수 있다. context 이전 때 다음 관측을 새 지역에서 다시 만들고 body를 재입양/재생성하지 않는다.
- 이동 중 stage 밖에서 source grid 가장자리 먹이를 잘못 먹지 않는다. 대사·비축·날씨·지형·피식·보호 은신처 검사는 기존 Native Step에서 계속 실행한다. 지역 환경은 실제 지역 commit 전까지 마지막 지역 기준이다.

## 애니메이션과 은신처

기존 enum 번호를 유지한 채 `AlertGraze`, `WeakTravel`, `SatedRest`를 추가했다. 네트워크 수신/표현의 활동 범위 검증도 함께 갱신했다. 움직이는 경계 사슴은 locomotion 다리 위에 실제 목 뼈(`STAG_-Neck`)의 look clip을 layered blend한다. 늑대 포만 휴식은 새 감각 cue 때문에 일어나는 대신 휴식 pose를 유지한다. 저에너지 이동은 Native의 실제 느린 속도를 기존 locomotion이 소비한다. 사망·수면·공격과 기존 IK 우선순위는 보존한다.

JYU 사슴/늑대 AnimationProfile·AnimBP 네 에셋을 재저장했다. 새 복사 맵에 실제 수풀/바위 은신처 12곳을 배치했다. 바위의 mesh 원점이 중앙이라는 가정을 없애고 실제 bounds로 ring을 계산해 보이는 바깥 경계가 Native 늑대 swept body 보호 여유 안에 있게 했다. 외형에 별도 충돌/이동 writer를 만들지 않는다. 보호 은신처의 기존 ON 세계 규칙과 Python 기본 세계의 차이는 [기존 보호 은신처 계약](JYU_REFUGE_SAFETY_20261016.md)을 유지한다.

## 실행 레벨과 재현

읽기 감사에서 기존 `JWJ/Integration_JwJ`, `Map/LV_Ecosystem_IntegrationTest`, OpenWorld의 실제 로드 구성을 비교했다. 팀원의 3지역 대형 통합 맵 `/Game/JWJ/Integration_JwJ`를 기반으로 **`/Game/JYU/Maps/LV_JYU_HerdMigration`**을 만들었다. 원본 JWJ/Map/SHC 레벨에 저장하지 않는다. `setup_jyu_herd_migration.py`는 owned 맵만 재생성하며 같은 맵에서 수동 수정한 내용은 재authoring 때 교체되므로 실행 전 diff를 확인한다.

새 맵은 지역당 사슴 48, 기존 늑대·3지역 환경·생태계 루프를 사용한다. 실제 지면 334곳을 조사한 경로 29점을 Barren↔Forest 사이에 배치했고, 경로와 개체 주변 지형은 기존 WorldPartition streaming source가 유지한다. Highland는 시뮬레이션하지만 이번 맵에는 그곳으로 통하는 검증된 이주 corridor를 authoring하지 않았다.

1. UE 5.8로 위 맵을 열고 Play한다. 원본 팀 맵과 기존 RefugeSafety는 별도로 남아 있다.
2. 평상시 자원이 충분하면 강제 이주하지 않는다. 시연하려면 Play 콘솔에서 `eco.HerdMigration.Test.Drought Barren`을 실행한다. **개발용 JYU 맵·권위 world 전용**으로 기존 자원 영수증을 발행해 먹이를 0으로 만들고 해당 세션의 재생을 멈춘다. Play 재시작으로 원복한다. 기본 생태계 규칙이나 학습 수치를 바꾸는 명령이 아니다.
3. Inspector에서 `Preparing → Traveling/Regrouping/Resting → Settled`와 개체별 이유, 실제 RegionId를 확인한다. 위협 회피 중에는 Native 원인이 우선 표시된다.
4. `Tools/Editor/test_jyu_herd_network.ps1`은 dedicated server와 순차 접속 ClientA/ClientB를 실행한다. 정상 종료 타이머를 기다리며 프로세스를 강제 중단하지 않는다. 관찰자만 이동해 기존 Bubble relevance를 확인하고 위협 컴포넌트는 테스트에서 비활성화한다.
5. `audit_herd_migration_runtime.py`의 `-HerdAuditPIE` 모드는 실제 PIE를 시작하고 관찰 카메라/스크린샷/Inspector snapshot을 저장한 뒤 정상 EndPlay한다. `Saved/HerdMigration_20261022`는 원시 로그·임시 보고서 위치이며 Git에 추적하지 않는다.

## 검증과 한계

최종 근거: [실행 결과 JSON](Evidence/JYU_V3/HerdMigration_20261023.json). 직접 UBT `Build13` 성공, 최종 전체 자동화 `Automation07` **202 Success + 예상 missing-save warning 1 = 203개, 실패/미실행 0**. 엔진 없는 evaluator 재컴파일 성공. Dedicated Server와 ClientA/ClientB, 실제 Editor PIE가 모두 정상 종료했다. 실행 도중 빌드/엔진을 강제 중단하지 않았다.

| 검증 | 실제 결과 |
|---|---|
| Dedicated Server, 48 사슴/지역 | 165초 관찰, 실제 Barren→Forest 지역 이전 23건, 자원/개체군 계약 실패 0 |
| 첫 ClientA | 최대 표현 개체 17, 논리 개체 0, 로컬 이주 Subsystem 0, 은신처 ready/visible 12/12 |
| 후속 ClientB 재접속 | 최대 표현 개체 32, 동일 권위 분리/은신처 조건 통과. 서버에서 이전한 개체 20마리의 Forest 표현 수신 확인 |
| 실제 Editor PIE | 120초 관찰, 지역 이전 22건. 집결·이동·휴식·재집결·막힘·정착 및 정체 후 복귀 기록 |
| 원인 이력 | 실제 runtime snapshot의 최대 16건, 단계별 이유/지역/Native step 기록 |
| 원본 보존 | JWJ/Map/SHC 원본 콘텐츠 diff 없음. JYU 애니메이션 4개와 새 owned 맵/외부 Actor만 authoring |

아래 화면은 실제 PIE에서 저장한 것이다. 첫 화면은 이동 무리와 기존 생태계, 두 번째는 실제 보호 수풀/바위 외형이다. Inspector의 세부 원인 이력은 JSON의 `arrival_example.reason_history`와 원시 runtime 기록에 있다.

![무리 이주 PIE](Evidence/JYU_V3/HerdMigration_PIE_20261023.png)

![보호 은신처 실제 외형](Evidence/JYU_V3/HerdMigration_Refuge_20261023.png)

Uncooked `-game` 실행에는 기존 Editor AnimGraph/HLOD 패키지 import warning이 남는다. 이번 실행에서 실제 Client mesh/활동/은신처 수신과 정상 종료는 확인했지만 Shipping cook/패키징을 검증한 것은 아니다. 시나리오 시간은 관찰 wall time이며 원시 snapshot의 `world_seconds`/`native_step`은 별도로 기록된다. 처음 dedicated 검증은 Slate 관찰기 미호출과 기존 지역 순환 관찰자의 새 맵 좌표 불일치로 재현기를 수정했으며, 위 표는 완료 경계 relay·서버 관찰 위치를 사용한 최종 실행 결과다.

최종 실행 결과는 함께 저장하는 Evidence 보고서를 따른다. 자동화는 Native 경계 밖 이동·동일 ID/Herd 유지·실제 도착 영수증·context 인계, TTL/중복 수신·고정 크기 원인 이력, 실제 저장된 animation profile과 활동 유효 범위·사망 초기화·바위 bounds를 검증한다. 엔진 없는 `EcoV3Eval`도 변경한 native 헤더로 재컴파일했다.

24마리/지역 초기 Standalone 검증에서는 단발성 먹이 감소 후 재생이 회복되면 이주 0, 재생을 중단한 명시적 가뭄에서는 계획 6개·실제 Barren→Forest 이전 12건을 관찰했다. 이는 제어된 부족 시나리오의 기능 증거이며 자연 발생 빈도나 장시간 균형을 증명하지 않는다.

계절성 장거리 이동, 출산/새끼 추종, 무리 merge/split, 지도 탐색·학습 기억, 포식자 공동 이주, ORCA/NavMesh, 새 RL 관측·재학습·Python ON 세계 파리티는 이번 구현 범위가 아니다. 기존 구조에 연결되지 않은 모든 실험 코드를 무조건 활성화하지 않는다. 이번 연결의 기준은 팀의 현재 권위·자원·이동·복제 계약이며 미병합 개인 정책 변경은 분리했다.
