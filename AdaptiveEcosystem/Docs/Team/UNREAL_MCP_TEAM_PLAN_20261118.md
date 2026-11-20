# Unreal MCP 팀 운영 안내

팀원마다 자기 PC에서 UE 5.8 에디터와 MCP를 실행한다. 팀 저장소는 조회 도구와 패키지 검사기를 공유한다. 개인 MCP 설정 파일은 각자의 체크아웃에 생성한다.

## 1. 개인 MCP 설정 적용

저장소 루트에서 PowerShell로 실행한다. 아래 명령은 UE 5.8에 포함된 Python 3.11을 사용한다. 엔진 설치 경로가 다르면 자신의 Python 3.11 이상 실행 파일을 지정한다.

```powershell
$mcpPython = 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe'
$mcpTools = 'AdaptiveEcosystem/Tools/UnrealMcp'
& $mcpPython "$mcpTools/configure_client.py" codex
& $mcpPython "$mcpTools/configure_client.py" codex --apply
```

- 실제로 연 폴더가 Unreal 프로젝트 폴더면 기본값을 사용한다. Git 저장소 루트를 열었다면 두 명령에 `--workspace repo`를 추가한다. Codex의 프로젝트별 설정은 신뢰된 프로젝트에서 적용된다. 적용 후 클라이언트 설정을 다시 읽고 도구 목록을 확인한다. [Codex MCP 설정](https://developers.openai.com/codex/mcp/)
- `codex` 자리에 `claude`, `cursor`, `gemini`, `vscode`도 사용할 수 있다. 적용기는 기존 서버와 개인 설정 값을 보존한다. UE 자동 생성 항목의 기존 포트를 이어받고, 필요하면 `--port 8001`처럼 지정한다. 같은 설정을 두 번 적용하면 두 번째에는 파일을 쓰지 않는다.
- 같은 이름에 개인 설정이 있거나 파일을 안전하게 해석할 수 없으면 적용을 중단한다. 주석이 들어간 JSONC 설정은 미리보기와 기존 설정을 보고 직접 병합한다. 다른 이름으로 같은 UE 주소가 등록돼 있으면 먼저 해당 항목을 검토한다. 이미 UE의 설정 생성 버튼을 다시 사용했다면 적용기를 다시 실행해 직접 연결이 돌아왔는지 확인한다.
- 두 작업 폴더의 MCP 설정 파일 5종은 파일 단위로 Git에서 제외한다. 현 체크아웃의 생성 파일 5개는 기존 포트 8001을 유지해 조회 전용으로 적용했다.

## 2. 조회 권한과 리스너

로컬 UE 플러그인의 Model Context Protocol 설정에서 **Tool Search**를 켠다. 자동 시작을 사용하지 않는 경우 에디터 콘솔의 `ModelContextProtocol.StartServer 8001`로 시작할 수 있다. 포트는 클라이언트 적용기에서 선택한 값과 맞춘다. 에디터에서 끌 때는 `ModelContextProtocol.StopServer`를 사용한다.

| 팀 MCP 도구 | 사용 범위 |
| --- | --- |
| `get_current_level` | 현재 레벨의 패키지 경로 |
| `is_pie_running` | PIE 또는 Simulate 실행 여부 |
| `find_actors_by_label` | 현재 월드의 액터 라벨 부분 검색 |

클라이언트는 표준 입출력으로 조회 전용 중계에 연결한다. 중계는 허용한 도구와 인자만 전달하며 범용 `call_tool`, 에셋·맵 변경, 일괄 저장, 스크립트 실행 요청을 거절한다. 중계에는 네트워크 수신 소켓이 없다. UE 쪽은 프로젝트의 8000·8001번 리스너 설정에서 루프백을 지정하며, 중계는 호출 전에 실제 수신 주소를 검사한다. 선택한 포트에 외부 인터페이스나 와일드카드 리스너가 있으면 호출을 중단한다.

UE 원본 MCP는 같은 PC에서 직접 연결할 수 있으므로 클라이언트에 직접 HTTP 프로필을 별도로 등록하면 조회 제한을 우회한다. 팀 프로필은 위 적용기로 생성한 항목을 사용한다. Experimental 플러그인 활성화는 로컬 `.uproject` 변경으로 관리 중이다. 팀 공유 커밋에 포함할 계획이 생기면 에디터 의존성과 패키징 타깃을 별도로 검증한다. [프로젝트 작업 지침](../../../AGENTS.md)

## 3. 맵과 에셋 패키지 충돌 검사

맵이나 블루프린트를 편집하기 전에 팀에서 그 패키지의 담당 브랜치를 정한다. 소유 복사 맵에서 작업하고, Git에서 비교할 브랜치를 먼저 fetch한다. 아래 `--against`는 예시이므로 실제 통합 대상과 같은 작업을 하는 팀원 브랜치로 바꾼다. 비교 대상이 여러 개면 옵션을 반복하고, 맵 외에 함께 편집할 소유 에셋이 있으면 `--asset /Game/…`으로 정확한 패키지를 지정한다.

```powershell
& $mcpPython "$mcpTools/review_packages.py" snapshot habitat-edit `
  --map /Game/JYU/Maps/LV_JYU_HabitatTransferFixture --against origin/jwj-1115

# 에디터에서 소유 복사 맵을 편집하고 작업한 패키지만 저장한다.
& $mcpPython "$mcpTools/review_packages.py" review habitat-edit
```

- `snapshot`은 기준 브랜치와 HEAD, 이미 변경된 패키지의 Git 상태·인덱스·파일 해시를 `Saved/UnrealMcp/`에 기록한다. 기존 작업과 비교 브랜치의 동일 패키지 변경이 겹치면 편집 전에 알려준다.
- `review`는 커밋 전에 실행한다. 선택한 `.umap`과 해당 `__ExternalActors__`·`__ExternalObjects__` 경로, 명시한 `.uasset` 범위를 검사한다. 범위를 벗어난 저장이나 같은 패키지 겹침이 있으면 종료 코드 1을 반환한다. 저장하지 않은 에디터 메모리 변경과 다른 팀원이 아직 커밋해 공유하지 않은 변경은 Git에서 확인할 수 없으므로 담당자 합의와 최신 fetch가 필요하다.
- 검사 실패 시 보고된 패키지의 담당자가 먼저 확인한다. 스크립트는 에셋을 저장하거나 되돌리거나 자동으로 stage하지 않는다.

## 확인 범위

- UE 5.8.3에서 `127.0.0.1:8001` 수신과 소유 맵 `/Game/JYU/Maps/LV_JYU_HabitatTransferFixture` 조회를 확인했다. PIE 상태 조회, 일치 항목이 없는 액터 검색, 범용 도구를 통한 맵 변경 요청 거절도 확인했다. 시험 로그는 로컬 `Saved/Logs/UnrealMcpReadOnlyLiveFinal.log`에 있다.
- 자동화는 5종 설정의 보존·재적용, 손상·개인 설정 보존, 조회 제한과 외부 리스너 거절, 소유 맵 저장 범위 및 브랜치 겹침을 검사한다. 실행 명령은 `& $mcpPython -m unittest discover -s $mcpTools -v`다.
- 실제 체크아웃에서 기존 미커밋 에셋을 기준점으로 기록하고 파일 변경 없이 재검사를 통과했다. 범위 이탈 및 브랜치 겹침 재현은 임시 Git 저장소에서 수행했다. 팀원 PC에서의 온보딩과 패키지 빌드는 별도 확인 항목이다.
