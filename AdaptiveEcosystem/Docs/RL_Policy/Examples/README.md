# soil/life 실제 관찰 예제

작성일: **2026-10-24**. `d095948`의 구현을 검증한 **2026-10-23 실제 QA snapshot**에서 필요한 행을 그대로 골랐다. 전체 원본은 로컬 `Saved/EcosystemLife_20261023`에 있으며 Git에 포함하지 않는다. 이 작은 파일은 clone한 팀원이 데이터 모양·관찰/정답 차이를 먼저 확인하기 위한 자료다.

## 제공하는 두 사례

| 파일 | 실제 포함한 값 | 읽을 때의 조건 |
|---|---|---|
| [부모·자식](ecosystem_life_family_actual_20261024.json) | 부모58/78과 자연 자식157의 실제 진단,3지역의 실제 metadata와 각4개 cell | 출생 후 관찰이다. 출생 순간 Energy/Reserve Golden이 아니며 이미 성장·이동·섭식했을 수 있다. |
| [Unknown 피해](ecosystem_life_unknown_damage_actual_20261024.json) | 실제 ambush fixture의 피해 개체17, 비영 Unknown fear·인식 여부·실제 observation/request/executed·지역 표본 | 테스트 Pawn을 재배치하고 실제 TryStrike를 호출한 명시적 fixture다. 자연 플레이의 급습 확률/분포가 아니다. |

각 파일의 metadata에는 원본 snapshot sha256, source 파일/보고서 이름, 실제 전체 agent 수, 선택한 cell index가 있다. `agents` 행과 선택된 cell 값은 원본에서 수정하지 않았다. metadata와 부분 표본 표시만 덧붙였다. 인위적으로 기대값을 만든 fixture/Golden이 아니다.

## 이 파일로 하면 안 되는 것

- `partial=true`, `training_ready=false`, `golden_vector=false`, `restorable_world=false`다. 전체 학습 환경·기존 native snapshot schema·binary checkpoint와 호환된다고 가정하지 않는다.
- region metadata의 총 food/인구는 전체 세계 기준이다. 제공한4개 cell 합계와 맞추거나 나머지896개를0으로 채우지 않는다. 전체900셀은 새 capture로 얻는다.
- 전체 current position·HP·부모·RNG·장부는 진단 정답일 수 있다. 이 JSON 전체를 observation vector로 넣지 않는다. policy 입력은 계약된 `observation`/판/시점만 사용한다.
- ID와 seed/RNG의 문자열을 JavaScript number로 강제 변환하지 않는다. 중요한 int64 정밀도를 잃을 수 있다.
- `energy`는 M4 Vitals 단위, `energy_fraction`은 표현에서 읽은 양자화 값이다. Native 정규화 Energy와 같은 정밀도/단위라고 가정하지 않는다. 정확한 Native body 값이 필요한 mirror에는 별도 capture 계약을 정한다.
- `life.nutrition`은 현재 늑대 영양에 사용하는 상태다. 초식 개체에서 기본값1로 보인다고 실제 초식 Energy/Reserve=1인 것은 아니다. 초식의 비축·섭식과 자기 에너지를 따로 읽는다.
- `last_damage_attacker_known=false`만으로 Unknown 피해를 받았다고 판정하지 않는다. 피해가 전혀 없을 때도 기본 false다. 제공 사례는 실제 피해 시험 보고서와 비영 Unknown fear를 함께 검증했다.
- snapshot의 현재 body·committed policy read·next read/request를 같은 시점으로 섞지 않는다. 저주기 표본은 전체 step 입력/난수/생명주기 순서를 담지 않는다.

## 재생성

먼저 실제 프로젝트 폴더 `AdaptiveEcosystem/`에서, engine/build가 모두 종료된 상태로 QA를 실행한다. C++를 바꿨다면 먼저 루트 규칙대로 직접 UBT 검증을 한다.

```powershell
./Tools/Editor/run_ecosystem_validation.ps1 -Check ambush
./Tools/Editor/run_ecosystem_life.ps1 -Mode save -Name FinalSave -Slot LifeRestart -Seed 23 -Duration 115 -SaveAt 95
```

이 명령은 해당 이름의 Saved 결과를 새로 만든다. 이전 원시 근거가 필요하면 먼저 별도로 보존한다. 기존 수동 맵을 setup 스크립트로 재생성하지 않는다. 다음은 일반 Python으로 실행하는 **읽기/문서 추출 도구**다. Unreal이나 학습을 시작하지 않는다.

```powershell
# 같은 프로젝트 폴더에서
python ./Tools/Editor/export_ecosystem_documentation_examples.py --source-implementation-commit d095948 --capture-date 2026-10-23 --release-date 2026-10-24
```

실제 FINISHED 보고서·snapshot이 없거나 부모/자식·Unknown 근거가 없으면 도구가 거절한다. 새 실행의 ID/값은 달라질 수 있으므로 새 기준 SHA·날짜·선택 결과와 본 README의 사례 설명을 함께 갱신한다. provenance 인자는 필수이며 commit 존재/날짜 형식을 검사하지만, 입력 snapshot이 정말 그 빌드에서 만들어졌는지는 실행 기록으로 확인해야 한다. 현재 예시의 `d095948`/2026-10-23을 다른 실행에 그대로 재사용하지 않는다.

정확한 `.eco` 복원이나 per-step trajectory/모델 Golden이 필요하면 [학습 가이드](../ECOSYSTEM_RL_AGENT_GUIDE_20261024.md)와 [실제 codec 계약](../../Architecture/ECOSYSTEM_LIFE_IMPLEMENTATION_20261023.md)을 따른다. 원본 snapshot은 모델 학습 완료 증거나 배포 가능한 저장 파일이 아니다.
