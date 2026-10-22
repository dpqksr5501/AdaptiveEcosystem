# 기존 작업 브랜치·폴더로 통합 — 2026-10-16

현재 브랜치: `codex/social-shelter-handoff`.
현재 프로젝트: `C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/AdaptiveEcosystem.uproject`.
실행 맵: `/Game/JYU/Maps/LV_JYU_V3Integration`.

## 통합과 보존

기존 HEAD `27d2105`는 통합 커밋 `8e2f34f`의 조상이므로 브랜치 이름을 유지하고 `git merge --ff-only codex/m4-v3-creature-integration`으로 반영했다. cherry-pick이나 파일 복사로 팀원의 이력을 분리하지 않았다. 통합 이전 상태는 로컬 `codex/backup-social-before-integration-20261016`에 보존했다. 원본 팀 맵은 이 반영에서 변경되지 않았으며, 독립 복사 맵과 JYU 에셋을 유지한다.

기존 폴더의 미추적 110개 파일을 SHA-256 manifest로 확인했다. 이 중 `Source` 아래의 `(1).cpp/.h` 복사본 6개는 중복 컴파일을 방지하기 위해 `AdaptiveEcosystem/Saved/IntegrationReturn_20261016/PreservedUntracked/`로 보관했다. 파일 내용은 바꾸거나 버리지 않았다. 여섯 파일은 모두 과거 커밋 `47faebce`의 해당 소스와 텍스트가 일치함을 확인했다. 현재 작업보다 오래된 복사본이며 별도 기능 수정이 누락된 것은 아니다. 비교 결과는 로컬 `DuplicateSourceComparison.json`에 남겼다. 기존 `Deliverables/`, `output/`, `tmp/`는 그대로 유지했다. manifest는 같은 보관 폴더의 `OriginalUntrackedManifest.json`과 `IntegrationReturnManifest.json`이다.

worktree의 `Saved/` 203개 파일(빌드·테스트 로그, 오디오, 화면, Inspector 기록, 자동 저장·설정·크래시 기록)을 `Saved/IntegrationReturn_20261016/WorktreeSaved/`로 복사하고 모두 해시를 대조했다. 이 보관 데이터는 로컬 ignored 파일이며 Git 커밋에는 포함되지 않는다. 재생성 가능한 Binaries/Intermediate/DerivedDataCache는 기존 폴더에서 다시 생성한다. LFS 1847개 파일이 원래 위치에서 실제 데이터로 존재하며 포인터 상태/누락이 없음을 확인했다.

## 기존 위치 검증

아래 검사는 모두 **원래 프로젝트 경로의 새 빌드**로 다시 실행했다.

- 직접 `UnrealBuildTool.exe AdaptiveEcosystemEditor Win64 Development` 빌드 성공, 종료 코드 0 (`BuildOriginal02.log`). 새 위치의 DLL/Editor 모듈을 생성했다.
- 전체 `Automation RunTests AdaptiveEcosystem`: **119개 수행, 실패 0/미실행 0**. 118 Success + missing-save 로드 검사의 예상 warning 1 (`AdaptiveEcosystem.Policy.Predation.SaveLoadGlobalEma`).
- 실제 D3D11 에디터 PIE에서 복사 맵을 로드하고 IK/시야/청각 반응 **12조건**을 촬영했다. `FINISHED`, 정상 종료 코드 0. 12도 IK 비교 화면도 직접 확인했다. 파일은 새 프로젝트의 `Saved/IntegrationV3/IKVisual/`에 생성됐다.
- Dedicated 서버 100초, Client 12초 및 동일 서버 재접속 12초 모두 정상 종료 코드 0, 종료 시 Ready=1. 서버 150개 초기 논리 개체/visual 0, Client/재접속 logical owned=0/step=0과 수신 visual 생성을 확인했다. 로그에 프로젝트/Mass/v3 런타임 오류·Fatal을 발견하지 않았다.
- 소스·설정과 JYU binary 에셋에서 삭제한 worktree 경로 참조를 발견하지 않았다. 소스/에셋/Config의 검증 후 추가 변경은 없다. 최초 통합 때의 D3D12 GPU 오류 등 기존 검증 한계는 그대로 유지한다.

[원래 위치 검증 요약](Evidence/JYU_V3/OriginalLocation_20261016.json). 전체 로그는 로컬 `Saved/IntegrationReturn_20261016/`에 남겼다.

최초 빌드는 에이전트가 권한이 제한된 실행 환경을 선택해 UBA cache `C:/ProgramData/Epic/UnrealBuildAccelerator/sessions` 생성 권한 오류를 반복했다. 소스/컴파일 오류로 간주하지 않았다. 사용자가 **이번 실행 1회에 한해 중단 후 재실행을 명시적으로 허용**한 뒤, 프로젝트 경로로 해당 UBT PID 22204를 확인해 중단했다. 관련 프로세스가 모두 끝난 뒤 직접 UBT를 캐시 쓰기 권한이 있는 환경에서 재실행했다. 기존 ‘실행 중 빌드 중단 금지’ 규칙은 이후에도 유지한다. `BuildOriginal01.log.gz`는 원본 내용을 해시 대조한 압축 실패 실행, `BuildOriginal02.log`는 재실행 기록이다.

## worktree 정리

기존 위치의 빌드·테스트·런타임 검증 및 보존 파일 대조 후 관리 도구의 **recoverable archive를 완료**했다. 이전 worktree 폴더가 없어졌고 `git worktree list`에는 원래 프로젝트 폴더만 남아 있음을 확인했다. Git 브랜치와 통합 이력은 보존했다. 이 기록을 작성한 뒤에도 기존 미추적 110개 파일의 내용 보존을 다시 확인했다.

앞으로 worktree 복원은 필요하지 않다. 원래 `AdaptiveEcosystem.uproject`를 열고 `/Game/JYU/Maps/LV_JYU_V3Integration`을 사용한다. 기존 팀 레벨과 복사 맵은 계속 분리한다. 이번 작업은 위치 통합이며, 미완료 기능을 새로 완료했다고 기록하지 않는다.
