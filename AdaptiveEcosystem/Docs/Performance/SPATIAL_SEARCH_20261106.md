# Native v3 공간 탐색 최적화와 측정 기록

2026-11-06, 시작 branch `jwj-1024`, 기준 HEAD `395992ab`. 이 기록의 구현은 해당 HEAD 위 작업 트리 변경이다.

## 적용 순서와 상태

| 순서 | 방법 | 이번 적용 |
|---|---|---|
| 0 | 기준 전체 탐색과 수치 계측 | 완료. 같은 실행 파일에서 전체 탐색 선택 가능 |
| 1 | 사슴 동족 지각 공간 격자 | 완료. 시야/분리 반경의 합집합 후보 |
| 2 | 사슴 위협 지각 공간 격자 | 완료. 시각/청각 범위의 합집합, 외부 위협 포함 |
| 3 | 늑대 표적·포획 공간 격자 | 완료. 이동 후 사슴 snapshot, 늑대 이동 전 질의 |
| 보완 | 밀집 질의의 전체 탐색 전환 | 완료. 첫 측정에서 발견한 정렬 비용 회귀 완화 |
| 후속 | 후보 목록 캐시 | 미적용. 실제 맵 분포/변위/빌드 비용을 확인한 뒤 동일 기준으로 비교 |
| 후속 | 계층 격자·Quadtree | 미적용. 희소 지역/반경 차이가 실제 병목인지 확인 후 선택 |
| 후속 | 판단 주기·AI LOD | 미적용. 반응 지연과 세계 계약 변경 acceptance가 먼저 필요 |
| 후속 | 병렬화·SIMD | 미적용. 사슴별 차폐 scratch 분리와 결정적 합산 보존이 선행 |

후속 방법은 모두 켜야 하는 단계가 아니다. 측정 결과에 따라 선택한다. 늑대 PackGoals의 W², 감각/Flight 진단용 전체 쌍 탐색, 장애물·은신처 탐색과 실제 Unreal trace는 이번 공간 개체 탐색 변경의 밖이다. 전체 Step이 선형 복잡도가 됐다는 의미가 아니다.

## 구현 계약

- 엔진 비의존 `EcoSpatialIndexV3.h`의 XY 균일 해시 격자를 Native 단위로 구축한다. `1 Native 단위 = 200cm` 변환 경계는 기존 그대로다.
- 격자는 반경을 덮는 셀의 보수적인 후보만 반환한다. 반경 경계에 작은 여유를 둔다. 실제 거리/시야각/차폐/안전/포획 비교식은 기존 소비자에 남는다.
- 후보를 **기존 입력 row 인덱스 오름차순**으로 처리한다. 합산 순서, 동점 선택, 결과의 원본 인덱스를 보존한다. StableAgentId로 새 정렬하지 않는다.
- 동족 후보 반경은 `max(SeeR, SepRadius)`다. 위협은 현재 시야와 최대 위협 청각 반경을 함께 포함한다. 청각 시야 제한 옵션도 유지한다.
- 늑대는 snapshot의 탐지/포획 배수 최솟값으로 실제 거리 상한을 보수적으로 계산한다. 0 이하 배수·비정상/과대 질의는 전체 탐색한다. 플레이어 대역의 표적 탐색은 기존 전역 탐색이다.
- 사슴 이동 후 `Prey`와 최소 배수를 한 번 구성해 PackPeek, 실제 Threat Step, integration probe에서 재사용한다. 난수 생성 횟수와 원본 인덱스별 원거리 굴림을 유지한다.
- `BuildKinInputs`/`BuildThreatInputs` 때 관측용 격자를 갱신한다. 초기 입양/부분 관측/리스폰 후 동족 목록 갱신도 기존 경로를 따른다. 단계 간 위치를 섞지 않는다.
- 격자에 64개 미만이면 질의를 전체 탐색으로 전환한다. 모인 셀 후보가 전체의 25%를 초과하면 정렬 전에 전체 탐색한다. 매우 큰 빈 셀 영역/좌표 범위 오류도 fallback한다. 이는 측정으로 선택한 성능 기준이며 생태 수치가 아니다.
- 새 위치/자원 writer, 관측 차원, 가중치, Social 기본값, 맵 authoring 변경은 없다. 격자·계측은 파생 scratch이며 저장/복제 payload에 추가하지 않는다.

## 수치 기록과 재현

[원시 CSV](SPATIAL_SEARCH_20261106.csv), [중앙값·단계별 변화표](SPATIAL_SEARCH_20261106_RESULTS.md), [첫 구현의 회귀 측정](SPATIAL_SEARCH_20261106_PILOT.csv)을 보존한다.

실행 환경: Windows, AMD Ryzen 5 9600X, VS2022 MSVC 14.44 x64, `/O2 /std:c++20 /fp:precise`. 측정 중 UBT와 Unreal Editor는 실행하지 않았다.

조건: 사슴 128/1024, 늑대 9/65, seed 12345, Native 맵 한 변 spread=200(400m)/dense=60(120m), 청각 ON. 각 조건 10스텝 예열 후 100스텝을 세 번 실행한다. full→kin→threat→wolf의 누적 단계이며 같은 시드·설정이다. 기준 버전도 새 실행 파일의 full 경로이므로 서로 다른 실행 파일/컴파일러를 섞지 않는다. 맵 크기는 동작/자원 분포에도 영향을 주므로 서로 다른 배치의 시간을 직접 속도 비율로 비교하지 않는다.

저장소 루트에서:

```powershell
powershell -ExecutionPolicy Bypass -File AdaptiveEcosystem/Tools/EcoSpatialBenchmark/build.ps1
New-Item -ItemType Directory -Force AdaptiveEcosystem/Saved/SpatialBenchmark | Out-Null
& AdaptiveEcosystem/Tools/EcoSpatialBenchmark/bin/EcoSpatialBenchmark.exe > AdaptiveEcosystem/Saved/SpatialBenchmark/run.csv 2> AdaptiveEcosystem/Saved/SpatialBenchmark/run.log
python AdaptiveEcosystem/Tools/EcoSpatialBenchmark/summarize.py AdaptiveEcosystem/Saved/SpatialBenchmark/run.csv
```

실행 종료 코드가 0인지 확인한 뒤 수치를 사용한다. 원시 CSV에는 전체 Step 시간, 격자 구축 시간, 동족/위협 지각 시간, 늑대 Step 시간, 각 단계의 전체 후보 슬롯 수와 실제 순회 슬롯 수를 기록한다. wolf 시간은 표적·포획만이 아닌 Threat Step 전체이며 PackPeek/integration probe가 같은 측정 객체를 받으면 그 호출도 포함된다. 후보 수는 정밀 순회 진입 수이며 실제 거리 비교 횟수나 격자 해시 조회 횟수와 동일하지 않다. 동족 자기 자신도 슬롯 수에는 포함한다.

`FWorldState::SearchDiagnostics.bEnabled=true`로 계측을 켜고 `Reset()`으로 새 구간을 시작한다. 기본은 OFF다. `bSpatialKin/bSpatialThreat/bSpatialWolf`로 방법별 A/B를 선택할 수 있다(기본 true). 상태 초기화는 기본값을 복구하므로 벤치마크는 Init 이후 선택한다. 게임 콘솔 명령이나 자동 CSV 저장은 추가하지 않았다.

세 번의 중앙값은 작은 차이의 유의성을 입증하지 않는다. 순서 무작위화·장시간 측정·여러 시드·메모리 사용량·실제 맵 Unreal Insights가 후속이다. 이 수치는 엔진과 같은 Native 헤더의 CPU 기준 루프이며 **렌더링/네트워크 포함 게임 프레임 측정이 아니다**.

## 측정에서 확인한 것

- spread 1024: 588.18 → 370.07 → 372.12 → 362.44ms/100스텝. 최종 전체 시간 **38.38% 감소**. 해당 단계 후보 감소율은 동족 92.13%, 위협 92.33%, 늑대 표적·포획 96.89%다.
- 위협 단계는 후보가 줄어도 전체 시간이 2.05ms 증가했다. 후보 감소를 자동으로 실행 시간 개선으로 설명하지 않는다.
- dense 1024: 836.38 → 847.84ms, 최종 **1.37% 증가**. dense 128도 30.20 → 31.47ms로 **4.21% 증가**했다. 밀집/소규모의 격자 비용이 남는다.
- 첫 구현은 dense 1024에서 약 842 → 1172ms로 악화됐다. 25% fallback을 추가해 이 회귀를 완화했다. 첫 CSV는 수정 전 알고리즘의 기록으로만 사용한다.

## 검증

- standalone `/O2` 빌드 성공.
- 음수 셀·중복 위치·반경 경계·시야 밖 청각·수면·거리 동점·과대 질의 fallback 검사 통과.
- 기준 전체 탐색 대 최종 격자, 4조건 × 900스텝 비교 통과. 조건별 seed, 밀집/분산, 원거리형, 플레이어 대역, 청각, 협동, 보호 은신처, 기본 리스폰 포함. 65개 이상 위협을 사용해 실제 격자 경로도 실행한다.
- 관측 float 배열/로짓은 바이트 비교, 위치·에너지·기하·선택·Arbiter 주요 필드·포획·먹이·세계 난수는 정확한 값 비교다. 모든 구조체의 padding까지 비트 비교했다는 뜻은 아니다.
- 직접 UBT `AdaptiveEcosystemEditor Win64 Development`: **Succeeded**, 47.61초. 로그 `Saved/SpatialBenchmark/UBT.log`. 기존 StructUtils deprecation/XGE 라이선스 경고가 있었다.
- UE `AdaptiveEcosystem.Policy.V3` 자동화: **128 Success, warning 0, failed 0**, 검사 소요 10.83초, 프로세스 종료 코드 0. 로그/리포트 `Saved/SpatialBenchmark/Automation.log`, `Saved/SpatialBenchmark/Automation/index.json`.
- 새 PIE/멀티플레이/패키징 성능 검증은 이번에 수행하지 않았다.

프로젝트의 [공통 맥락](../PROJECT_CONTEXT.md), [v3 계약](../RL_Policy/POLICY_CONTRACT_V3.md), [Mass 실행 순서](../Mass/MASS_PROCESSOR_ORDER.md)를 함께 따른다.
