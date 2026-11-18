# 로컬 검증 증거와 복원

`Saved/` 경로는 Unreal 프로젝트 폴더를 기준으로 한다. 이 기록은 실험한 PC에 저장된다. 다른 체크아웃에서는 문서의 맵 작성과 기록 도구로 다시 실행할 수 있다.

## 공통 로그 보관 폴더

이 PC에서는 `Saved/ValidationArchive/20261114/`에 완료된 섬 시험의 원시 JSON·로그·화면과 이전 Unreal 로그·프로파일링 CSV를 유형별 ZIP으로 보관한다. 묶음 안의 경로는 원래의 `Saved/` 상대 경로이며, `ValidationEvidenceManifest.json`에 파일별 원래 크기와 SHA-256이 있다. 현재 실행을 확인하는 최신 자동화·서버·장기 회귀 기록과 대표 화면은 기존 위치에서도 바로 열 수 있다. 팀에 공유하는 요약과 재현 스크립트는 Git에 두고 원시 ZIP은 로컬에서 보관한다.

2026-11-14에 원본 6,025개(24.99 GiB)를 ZIP 여섯 개(10.48 GiB)에 보관했다. ZIP에서 다시 읽은 해시를 대조한 뒤 원래 위치의 중복본을 제거해 14.51 GiB를 회수했다. `CleanupResult.json`에 각 묶음별 결과가 있다. 같은 정리에서 `Saved/R9Review/uv-cache`의 재다운로드 가능한 패키지 캐시를 정리했다. 다음 로컬 실행에서 패키지 다운로드가 필요할 수 있다. R9 `fauna_r2`의 22개 파일 해시와 6종 재개 ZIP의 무결성을 정리 후에 확인했다. 학습 결과, 체크포인트, 기존 Python 설치, Git·LFS 객체, 검증용 패키지와 증분 빌드 파일은 보존했다.

과거 기록 경로가 비어 있으면 해당 ZIP의 목록을 찾아 필요한 항목만 복원한다. 예를 들어 섬 보고서는 다음과 같이 읽는다. `-k`는 이미 있는 파일을 보존한다. 각 묶음의 목록과 정리 결과는 같은 폴더의 매니페스트와 정리 기록에 있다.

```powershell
$saved = (Resolve-Path -LiteralPath 'AdaptiveEcosystem/Saved').Path
$archive = Join-Path $saved 'ValidationArchive/20261114/IslandReports.zip'
tar.exe -tf $archive
tar.exe -x -k -f $archive -C $saved -- 'FaunaAudit/Island_20000_water_small20/IslandFaunaPIE.json'
```

## 바로 읽을 수 있는 최근 검증

| 범위 | 로컬 기록 |
| --- | --- |
| 통합 레벨 원본과 복사본 60분 실행 | `Saved/ProjectAudit_20261112/IntegrationR7eSummary.json`과 완료된 `IntegrationR7e_*.json`. 원시 로그는 `Saved/Logs/IntegrationR7e_*.log`에 있다. |
| 복사본 작성·월드 파티션 | `Saved/ProjectAudit_20261112/IntegrationR7eAuthoring.json`, `Saved/Logs/IntegrationR7eAuthoring.log` |
| 사슴 단독·기존 다종 참조 | `Saved/ProjectAudit_20261112/DeerLong_Summary.json`과 완료된 `DeerLong_*.json`, 대응하는 `Saved/Logs/`의 로그 |
| 기존 바이너리 정책 회귀 | `Saved/ProjectAudit_20261112/PolicyV3Baseline/index.json` |
| 다종 공통 시계, 시드 두 개와 4배속 30·60 FPS | `Saved/ProjectAudit_20261112/SharedBoundaryLong_*.json`, 대응하는 `Saved/Logs/` 권위 로그 |
| 통로 경유점·지면 도착·목적지 섭취 | `Saved/ProjectAudit_20261112/SharedBoundaryApproachPIE.json`, `Saved/Logs/SharedBoundaryApproachPIE.log` |
| 공통 시계 빌드의 자동화 | `Saved/SharedBoundary/Automation/index.json`, `Saved/Logs/SharedBoundary_Automation.log` |
| 전용 서버 근접 사냥과 늦은 접속 | `Saved/PlayerHunting_20261105/SharedBoundaryMeleeIsolated/`의 서버 및 두 Client 결과 |
| 같은 두뇌에서 서식지 단계 비교 | `Saved/ProjectAudit_20261112/HabitatCause_20000_Stage*.json`와 `HabitatCause_20017_Stage*.json`, 대응하는 `Saved/Logs/` 권위 로그 |
| 통합 맵에서 대체 먹이 구역만 바꾼 비교 | `Saved/ProjectAudit_20261112/HabitatCause_Integration_*.json`, 대응하는 `Saved/Logs/` 권위 로그 |
| 서식지 스트리밍·먹이 이주 회귀 | `Saved/HabitatCauseFinal/Automation/index.json`, `Saved/Logs/HabitatCauseFinal_Automation.log` |
| 여우의 지면 통과와 목적지 대체 먹이 섭취 | `Saved/ProjectAudit_20261112/HabitatCause_PassageFoodPIE.json`, 대응하는 `Saved/Logs/` 권위 로그 |
| 멧돼지 배치와 표범 공격 접촉 비교 | `Saved/ProjectAudit_20261112/PreyAccess_*.json`와 `PreyWindup_*.json`, 대응하는 `Saved/Logs/` 권위 로그 |
| 공격 준비 첫 이동과 유효 접촉 회귀 | `Saved/PreyWindupFinal/Automation/index.json`, `Saved/Logs/PreyWindupFinal_Automation.log` |
| 공격 준비 수정 후 저FPS·멀티 근접 회귀 | `Saved/ProjectAudit_20261112/PreyWindupParity_*.json`, `Saved/PlayerHunting_20261105/PreyWindupMelee/`의 세 프로세스 결과 |
| 공용 사체 영양 예약과 두 시드 30분 비교 | `Saved/ProjectAudit_20261112/EssentialCarcass_*.json`, 대응하는 권위 로그와 `Saved/EssentialCarcass/Automation/index.json` |
| 신규 종 사냥 설정과 실행 경계 자동화 | `Saved/NewFaunaEssential/Automation/index.json`, `Saved/Logs/NewFaunaEssential_Automation.log` |
| 16종의 별도 30·60분 비교 | `Saved/ExpandedFaunaImport/ExpandedFinal{Baseline,Full}20000_summary.json` |
| 15개 군락 재고·외형, 실제 섭취와 건조·강우 비교 | `Saved/ExpandedFaunaImport/HerbivoreForage{Natural,Choice,Depleted,WeatherCycle}20000_status.json` 및 같은 이름의 로그 |
| 식생 저장·복원과 실시간 전용 서버 PIE | `Saved/ExpandedFaunaImport/HerbivoreForage{Save,Load,Network}20000_status.json`, `HerbivoreForageCheckpointState.json` |
| 식생과 관목 재질 렌더, 전체 자동화 318건 | `Saved/ExpandedFaunaImport/ForageGrowthVisualFinal.png`, `Saved/Automation/ForageGrowth/index.json` |
| 돼지 전용 개체차·양육자 추종·열 반응과 경사 애니메이션 | `Saved/ExpandedFaunaImport/PigFollowupCurrent20000_status.json`, `PigThermal{Cool,Dry,Wet}20000_status.json`, `Saved/FaunaAudit/PigPoseFinalMetrics.json` |
| 돼지 도주·저장·전용 서버 PIE와 공유 사체 | `Saved/ExpandedFaunaImport/PigFollowup{Threat,Save,Load,Network}20000_status.json`, `Saved/Automation/PigFinal/index.json` |
| 다종 휴식·사망 지면 보정과 보행 회귀 | `Saved/FaunaAudit/PigSupport{Before,Final}{Flat,Uphill,CrossSlope}Metrics.json`, `FaunaSupport{Existing,Expanded}{Grounded,Walk}Metrics.json`, `Saved/Automation/FaunaGroundSupport/index.json` |
| 지면 보정 후 재질·발소리·생태 실행 | `Saved/FaunaAudit/BoundMaterials.json`, `Saved/FaunaFootsteps/GroundSupportFootsteps{Existing,Expanded}/PlaybackAudit.json`, `Saved/ExpandedFaunaImport/GroundSupport{Ecology180,CarpRoute}_status.json` |
| 반전·저속 자세 전환, 경사 이동과 돼지 사체 안착 | `Saved/FaunaAudit/FaunaContinuity{Before,Final}*Metrics.json`, `FaunaTurnSlope{Existing,Expanded}{30,60}Metrics.json`, `FaunaTurnPigUphillMetrics.json`, `Saved/Automation/FaunaTurnContinuity/index.json` |
| 회전 수정 후 발소리 재생과 경사 직선 제동의 기존 관통 재현 | `Saved/FaunaFootsteps/TurnContinuityFootsteps{Existing,Expanded}/PlaybackAudit.json`, `Saved/FaunaAudit/FaunaTurnSlopeStraight60Metrics.json` |
| 지상 이주 후 정착지 자연 출생, 16종 180초와 잉어 수로 회귀 | `Saved/Logs/FaunaSettlersTarget.log`, `Saved/Automation/FaunaSettlers/index.json`, `Saved/ExpandedFaunaImport/FaunaSettlersEcology{30,60}.jsonl`, `FaunaSettlersCarp{Open,Closed}_status.json` |
| 수변 하상·수위 주기, 범람원 재고, 밍크 섭취와 고수위 수중 렌더 | `Saved/ExpandedFaunaImport/RiparianReach{Audit,HighView}.json`, `RiparianReach{Low,High,Underwater,Receded}.png`, `Saved/Logs/RiparianReachAudit.log` |
| 수변 장식 인스턴싱 전후, 근·원거리 나무 렌더와 수위·섭취 회귀 | `Saved/ExpandedFaunaImport/ReachFoliage{Before,Performance}.json`, `ReachFoliage{Near,Far}.png`, `Saved/Profiling/CSV/ReachFoliageNear*.csv`, `Saved/Logs/ReachFoliageEcologyRegression.log` |
| 수변 17개 군락의 재고·외형, 건조·강우·침수·섭취, 직접 UBT 뒤 전체 자동화 320건 | `Saved/Logs/ReachPlantGrowthFinal.log`, `Saved/ExpandedFaunaImport/RiparianReachAudit.json`, `Saved/Automation/ReachPlantGrowth/index.json`, `Saved/Logs/ReachGrowthAutomation.log` |
| 저·고수위의 충돌 바닥 표본, 깊이를 만족한 연결 면적과 근거리 먹이 고갈 | `Saved/ExpandedFaunaImport/ReachHabitatArea.json`, `Saved/Logs/ReachHabitatArea.log`, 군락 재고는 `Saved/Logs/ReachPlantGrowthFinal.log` |

먹이 군락 재현은 [다종 검증 스크립트](../../Tools/Editor/run_jyu_expanded_fauna_validation.ps1)의 `HerbivoreForage`, `ForageWeather`, `ForagePersistence`, `ForageNetwork` 모드를 사용한다. 면적·통로·두뇌의 대조군은 [공간 비교 계획](../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md)에 있다.

수변 재현은 저장된 `LV_JYU_RiparianReach`에서 [수변 검사 스크립트](../../Tools/Editor/author_jyu_riparian_reach.py)의 `-EcoRiparianReachAudit`를 사용한다. 깊이 격자만 추가하려면 `-EcoRiparianReachArea`, 고수위 수중 렌더에는 별도 실행에서 `-EcoRiparianReachHighView`를 쓴다. 기존 결과가 같은 이름으로 저장되므로 비교 전에 원본을 보관한다. 맵을 처음 작성할 때의 하상과 군락 적용 순서 및 렌더 비교는 [수변 실측 기록](../Architecture/FAUNA_HABITAT_CAPACITY_20261113.md)과 [식생 렌더 검사 도구](../../Tools/Editor/audit_jyu_reach_foliage.py)를 따른다. 위 자동화와 PIE 기록은 문서 갱신 전에 완료한 실행이다.

맵별 결과, 모델·시드·배속, 섭취 단위와 미검증 범위는 [개체군 비교와 재현](../Architecture/FAUNA_POPULATION_BALANCE.md#integration_jwj-복사본의-r7e자연-출생과-다종-공존)에 있다. 재현용 복사 맵 두 개와 각각의 World Partition 외부 액터는 에셋과 함께 사용한다. 원본 에셋, 저장 슬롯, Git·LFS 데이터는 원시 로그와 용도가 다르다.

## 이전 실행 기록 복원

2026-11-12에 용량 증가가 확인된 항목은 시드·재실행별로 저장한 원시 생태 시계열과 반복 빌드 진단이었다. 이전 대용량 생태 JSON 75개, 빌드 진단 로그 1개, 중단된 기록기 실행의 로그·JSON 8개를 `Saved/ProjectAudit_20261112/HistoricalTestEvidence_20261112.zip`으로 보존했다. 원본 6.12 GiB와 압축본 0.80 GiB를 대조해 5.32 GiB를 회수했다. 각 파일은 사용 중인지 확인하고, 압축에서 다시 읽은 SHA-256이 원본과 일치할 때만 기존 위치에서 정리했다.

ZIP 내부 경로는 `Saved/` 상대 경로다. 아카이브의 `HistoricalTestEvidenceManifest.json`에 각 파일의 바이트 수와 SHA-256이 있고, ZIP 옆 `HistoricalTestEvidence_20261112.json`에서 정리 결과를 확인할 수 있다. 최근 완료 실행의 로그·집계, 테스트 맵, 패키지 실행물, 가져온 에셋, 저장 슬롯과 Git·LFS 데이터는 보존했다.

예를 들어 이전 세대 분석 도구가 `Saved/NaturalHabitatRelease_20261030/Natural23_Life.json`을 필요로 하면, 저장소 루트의 PowerShell에서 그 항목만 복원한다. 이미 같은 경로에 파일이 있으면 `-k`가 해당 파일을 보존한다.

```powershell
$saved = (Resolve-Path -LiteralPath 'AdaptiveEcosystem/Saved').Path
$archive = Join-Path $saved 'ProjectAudit_20261112/HistoricalTestEvidence_20261112.zip'
tar.exe -tf $archive
tar.exe -x -k -f $archive -C $saved -- 'NaturalHabitatRelease_20261030/Natural23_Life.json'
```
