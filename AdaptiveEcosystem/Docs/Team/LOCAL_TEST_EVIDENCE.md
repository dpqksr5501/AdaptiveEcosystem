# 로컬 검증 증거와 복원

`Saved/` 경로는 Unreal 프로젝트 폴더를 기준으로 한다. 이 기록은 실험한 PC에 저장된다. 다른 체크아웃에서는 문서의 맵 작성과 기록 도구로 다시 실행할 수 있다.

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
