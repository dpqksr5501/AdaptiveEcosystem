# 실제 보호 은신처와 지형·표현 연결

## 2026-10-23 main 통합 이후의 현재 계약

아래 10-16 구현·테스트는 이력이며 현재 통합 기본값은 `eco.IntegratedV3.ShelterSafe=1`, `eco.IntegratedV3.ProtectedRefuges=1`이다. ShelterSafe=1에서는 Python `realism_shelter`와 맞춘 Native 안전 규칙(영역 안 표적/포획 제외·늑대 진입 금지)이 보호를 맡고 ProtectedRefuges는 실제 등록/제거·도착 생명주기를 보완한다. ShelterSafe=0일 때만 기존 JYU swept/body-margin 안전을 사용한다. 두 보호 규칙과 몸 여유를 중복 적용하지 않는다. Native `FWorldConfig::bProtectedRefuges` 기본 false와 통합 CVar 기본값을 구분한다.

PR #12 통합에서는 늦은 은신처 등록으로 바뀐 먹이 용량/잔량을 `AdjustSpatialFoodHabitat` 거래로 M4 장부에 반영하고, 제거 시 용량만 복구하며 먹이를 생성하지 않는다. [main 장부 통합 근거](JYU_PR12_MAIN_INTEGRATION_20261022.md)를 따른다. 후속 이주 작업은 바위 mesh bounds/pivot 기준으로 외형 테두리를 계산해 늑대 보호 여유 안에 배치했다. 별도 물리 이동 writer를 만들지 않는다.

새 이주 맵에도 실제 수풀/바위 12곳을 배치했지만 기존 은신처 맵의 이주는 자동 활성화하지 않았다. 기존 안전 기준 세계의 Python 파리티와 새 이주 ON 세계 전체 궤적 미검증을 구분한다. [현재 실행·검증·한계](JYU_CHAT_HANDOFF_20261023.md)를 우선한다.

## 2026-10-16 최초 구현 기록

2026-10-16, `codex/social-shelter-handoff`, 원래 저장소. 직전 진단의 “은신처는 논리적 원일 뿐 실제로 안전하지 않음”을 수정했다. 기존 M4/v3 Social 인계 위에 추가한 **Unreal 세계 규칙**이다. PPO 재학습이나 새 모델 도입을 의미하지 않는다.

## 에디터에서 확인

`AdaptiveEcosystem.uproject`를 열고 **`/Game/JYU/Maps/LV_JYU_RefugeSafety`**를 연다. Content Browser의 `JYU/Maps/LV_JYU_RefugeSafety`이며, Outliner에서 `JYU_ProtectedRefuge_Forest_0`를 찾아 F로 이동한다. Forest/Barren/Highland에 각 4개, 총 12개다.

기존 `LV_JYU_V3Integration`을 World Partition 템플릿으로 복사해 별도 ExternalActors/ExternalObjects를 저장했다. 원본 팀 레벨과 기존 통합 맵은 수정하지 않았다. 기존 사용자 변경 68개(오디오 4개·기존 맵 ExternalActors 64개)는 작업 전 백업과 SHA-256을 대조한다.

PIE에서 볼 장면:

1. 바위 테두리와 높은 수풀, 안쪽의 사슴 자리와 출입 틈이 보인다.
2. 사슴은 기존 개인 감각·무리 경보·정책에 따라 피하거나 은신처로 이동한다. 실제 보호 구역 안에 도달해야 HIDE 도착·점유를 인정한다.
3. 보호 구역 안의 사슴은 웅크릴 수 있고, 늑대는 바깥으로 우회하거나 멈춘다. 은신처 안 사슴을 포획 대상으로 삼지 않는다.
4. 사슴이 밖으로 나오면 일반 피식 규칙이 다시 적용된다. 은신처가 제거되면 이전 자리에서 계속 숨어 있는 상태를 해제한다.

Inspector에서 `refuge_protected_here`, `native_in_cover`, `hide_arrived`, `shelter_state`, `request`/`executed`, `nearest_wolf_reason`을 함께 확인한다. 늑대의 `wolf_inside_refuge`는 false여야 한다. 서버 로그의 `[EcoRefuge]`는 보호 개체·스텝, 우회, 초기 위치 복구, 내부 늑대·스텝, 내부 포획 위반을 집계한다.

![실제 PIE 은신처와 사슴](Evidence/JYU_V3/RefugeSafety_20261016_PIE.png)

## 실행 계약

- `FEcoV3IntegratedSettings::bProtectedRefuges=true`, CVar `eco.IntegratedV3.ProtectedRefuges=1`이 통합 경로의 기본값이다. Native `FWorldConfig` 기본값은 false로 유지해 기존 Python/Golden 기준 세계를 보존한다.
- `EcoRefugeSafetyV3.h`는 엔진 독립 원형 영역의 합집합 판정·swept segment 차단·접선 우회·초기 내부 늑대 복구만 수행한다. Native 적분기에서 호출하며 Actor나 별도 Mass writer가 위치를 다시 쓰지 않는다.
- 늑대 중심에는 반경 외곽 **100cm 여유**를 둔다. 양 끝이 원 밖이어도 중간에 원을 관통하는 이동을 차단하며, 보간 직선도 원 안을 가로지르지 않도록 처리한다. 겹친 원/무대 경계에서 우회가 해소되지 않으면 안전한 이전 위치에 머문다.
- 피식용 `FPreyView`에서 실제 보호 구역 안의 개체를 사냥·포획 후보에서 제외한다. 이 뷰의 `bAlive=false`는 후보 필터일 뿐 실제 Mass 생명·개체군·활력의 사망 값이 아니다. 굶주림·섭식·대사·자원 감소는 계속 실행된다.
- 공간 보호는 예약 여부와 별개다. 반경 안의 모든 사슴이 피식 보호를 받으며, **예약 슬롯은 도착·점유·자리 배분**의 계약이다. 4개 슬롯을 넘는 사슴도 영역에 들어오면 보호된다.
- Social lease/slot 검증과 기존 single Native movement를 유지한다. 슬롯은 기본 반경의 55% 안쪽이며 실제 지면 높이와 법선을 검사한다. 급경사/누락 지점이면 같은 방향의 더 안쪽을 탐색한다. 실제 위치의 거리와 보호 구역 포함 여부가 둘 다 맞아야 도착 feedback을 낸다.
- 지형이 늦게 준비되면 0.25초마다 최대 30초 등록을 재시도한다. 등록 전에는 런타임 외형을 숨겨 안전하지 않은 표식을 보이지 않는다. 성공 시 기존 context에 새 cover를 추가한다. 기존 index는 재활용하지 않는다.
- Shelter 등록마다 고유 `RegistrationId`를 갖는다. compact index가 재사용돼도 이전 cover가 부활하지 않는다. 삭제된 cover는 radius=0 tombstone으로 무효화하고, 관측/도주 목적지에서 제외한다. 먹이 잔량·capacity를 초기화하지 않고 cover 재생 배수만 갱신한다.

## 에셋과 클라이언트

`AEcoRefugeHabitat` → `/Game/JYU/Environment/BP_JYU_ProtectedRefuge`. 기존 프로젝트의 MWAM GrassA/StoneA mesh를 사용하고, 재질은 `MI_JYU_RefugeBrush`, `MI_JYU_RefugeStone`으로 복사했다. vendor 원본을 수정하지 않는다. 씨드 기반 HISM 배치는 은신처당 수풀 약 183~194개, 바위 20개이며 실제 지면에 맞춘다.

장식 HISM은 NoCollision이며 navigation에 영향을 주지 않는다. 사슴을 물리 충돌로 가두거나 두 이동 경로를 만들지 않고, 실제 늑대 접근 제한은 서버 Native 세계 규칙이 소유한다. 원형 보호 규칙과 자연물 배치를 같은 actor의 Radius에서 생성한다. Blueprint는 반경·밀도·높이·seed를 편집하고 RebuildHabitat로 다시 배치할 수 있다.

등록 판단/예약 Subsystem은 Server/Standalone 전용이다. 클라이언트에는 정적 Actor의 layout 반경·seed와 `bRegistrationReady`만 복제하며 실제 논리 시뮬레이션을 만들지 않는다. 복제된 동물 DTO/AnimBP 경로는 그대로다. Python 도구는 에디터 에셋 저작·관찰용이며 런타임 정책 추론에 사용하지 않는다.

## 검증

- 직접 `UnrealBuildTool.exe AdaptiveEcosystemEditor Win64 Development` 성공 (`Build06.log`). 실행 중인 엔진/빌드를 중단하거나 중복 빌드하지 않았다.
- 전체 자동화 **147개: Success 146, SuccessWithWarnings 1, Fail 0** (`Automation05/index.json`). 경고 1개는 기존 missing-save fixture의 예상 경고다.
- 새 회귀 6개: swept 이동/겹친 영역/초기 내부 복구, 실제 Mass 보호·밖으로 나간 뒤 포획, 삭제·index 재사용·먹이 보존·노출 상태 해제, 실제 mesh/HISM, 경사 지면 슬롯, 여러 엔진 프레임에 걸친 늦은 지면 등록.
- 실제 에디터/일반 PIE 40초: 은신처 **12/12 준비 완료**, 관찰 80회, 사슴 기록 3,801개 중 보호 662·보호 구역 안 앉은 자세 210·점유 147, 늑대 기록 160개 중 내부 0. 이는 반복 관찰 건수이며 고유 개체 수가 아니다.
- 300 native steps 시 Forest/Barren/Highland 우회 22/34/38회, 세 지역 모두 `InsidePredatorSteps=0`, `CaptureViolations=0`, 초기 복구 0. 지역 집계는 실제 로그 전체에서 확인했고, Actor 샘플은 카메라 주변 Forest가 중심이다.
- 실제 editor viewport, PIE 전체 장면과 근접 장면을 저장하고 육안으로 수풀·바위·사슴 접지와 웅크림 위치를 확인했다. 첫 관찰에서 Highland 2곳이 초기 지면 등록에 실패해 안쪽 슬롯 fallback과 늦은 등록 처리를 추가했고, 재관찰에서 12곳 모두 정상화했다.
- 실제 Dedicated 110초 + 같은 서버에 Client A/B 순차 접속: 세 프로세스 exit 0. 두 클라이언트 모두 은신처 count=ready=visible=12, 수풀/바위 인스턴스와 준비 상태를 확인했다. 클라이언트 논리 개체/Native step은 모두 0, 실제 수신 동물 Actor는 존재하며 Dedicated의 시각 Actor는 0이다.
- Dedicated 750 native steps: Forest/Barren/Highland 우회 13/65/22회, 보호 개체·스텝 14,275/7,713/8,025, 세 지역 모두 내부 늑대·스텝/내부 포획 위반 0. 첫 네트워크 관찰 도구가 `-game`에서 없는 에디터 전용 Subsystem을 조회해 실패했다. ObjectIterator로 실제 게임 월드만 읽도록 고친 뒤 두 접속을 다시 실행했고 Python 오류 없이 보고서를 얻었다. 마지막 Build06은 이동 중 은신처 제거 처리와 기존 Inspector 목표 표시 복원이며, 일반 PIE/네트워크 화면·수치는 직전 동일 보호/이동 코드의 Build05 실행 결과다. 제거 중 이동 취소는 최종 자동화 회귀로 추가 검증했다.

도구: `Tools/Editor/setup_jyu_refuge_safety.py`(백업 manifest가 있는 저작 세션), `run_jyu_refuge_audit.py`(관찰/스크린샷), `test_jyu_refuge_network.ps1` + `audit_jyu_refuge_client.py`(서버와 두 번의 실제 접속). 원본 raw 결과는 `Saved/RefugeSafety_20261016/`, 공유 가능한 요약과 화면은 `Evidence/JYU_V3/RefugeSafety_20261016*`이다.

## 범위와 남은 설계

이는 **Unreal 세계 확장 규칙**이다. R1b 가중치·18관측/5행동·mask2·V1 계약은 바꾸지 않았다. 확장 ON일 때 이동/피식 전이가 Python 기준 세계와 달라지므로 ON 상태까지 sim-to-sim 파리티가 성립한다고 주장하지 않는다. 같은 세계로 재학습하려면 RL 담당자가 Python mirror에 동일 원형 경계·보호 후보 필터와 검증 벡터를 반영해야 한다. 기존 OFF Golden Vector 회귀는 이번 전체 테스트에 포함됐다.

완전한 NavMesh/ORCA 경로 탐색, 매 프레임 움직이는 은신처, 동적으로 넓히는 보호 반경, 임의의 복잡한 mesh 내부 체적은 이번 범위가 아니다. 배치한 원형 보호 영역과 최대 무대 크기의 정상적인 authoring 조건에서 동작한다. 지형 미준비 시 보호 표식을 감추며, 30초 후에도 등록할 수 없으면 명시적으로 경고한다. 원 밖에서 쉬는 포만 늑대 때문에 모든 사슴이 항상 달아나도록 감각·정책 수치를 바꾸지 않았다.
