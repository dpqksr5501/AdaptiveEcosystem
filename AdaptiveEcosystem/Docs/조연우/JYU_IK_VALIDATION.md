# 사슴 IK 수정과 화면 검증 — 2026-10-15

검증 브랜치는 `codex/m4-v3-creature-integration`, 테스트 맵은 `/Game/JYU/Maps/LV_JYU_V3Integration`이다. 원본 팀 레벨과 원본 동물 애니메이션은 수정하지 않았다.

## 원인과 수정

발 접촉 마커와 두 관절 IK의 끝 관절을 혼동하면 실제 무릎 대신 짧은 발목 체인이 풀린다. 사슴·늑대의 뒷다리는 `Thigh → Calf → HorseLink → Foot`, 앞다리는 `UpperArm → Forearm → Hand → Finger0`이다. IK 끝은 `HorseLink`/`Hand`, 접촉 측정은 `Foot`/`Finger0`로 분리했다. 매 프레임 이미 IK를 적용한 소켓으로 무릎 방향을 재구성하던 피드백도 제거했다.

`FAnimNode_EcoGroundFeet`는 현재 프레임의 **IK 이전 입력 포즈**에서 다리 길이와 굽힘 평면을 계산한다. Game Thread의 네 지면 트레이스만 값으로 전달하고 AnyThread 포즈 계산은 World에 접근하지 않는다. 거의 곧은 체인은 원본 포즈를 유지하고, 다리 늘이기는 끄고, 발목 회전은 원본을 유지한다. 발 보정은 12cm, 몸통 하강은 6cm까지 제한하고 시간에 따라 보간한다. 프로필 검증은 접촉 마커의 부모·체인 중복·공통 몸통 조상을 확인한다.

걷기의 들린 발과 달리기의 공중 구간은 지면으로 강제 이동하지 않는다. 숨기·수면·공격·사망과 그 전환에서는 IK를 감쇠해 접힌 포즈를 보존한다. Actor 재사용 시 애니메이션과 접지 상태를 초기화한다. 이 노드는 Mesh 포즈만 바꾸며 Mass 위치/속도에는 쓰지 않는다.

## 실제 검증

UE 5.8.3, D3D11, 복사 맵 PIE에서 동일 BP·동일 클립의 IK ON/OFF를 나란히 배치했다. 임시 이동 가능한 발판의 pitch를 명시해 평지·4°·8°·12°와 먹기·걷기·달리기·숨기·수면·걷기 복귀 총 10개 조건을 촬영했다. `audit_jyu_ik_visual.py`가 각 조건의 소켓/관절 위치와 지면을 기록했다.

| 정지 경사 | IK OFF 평균 절대 잔차 | IK ON 평균 절대 잔차 |
|---|---:|---:|
| 4° | 2.886cm | 0.503cm |
| 8° | 5.847cm | 0.500cm |
| 12° | 8.864cm | 0.815cm |

잔차는 **접촉 마커 높이 − 지면 높이 − 클립별 중립 마커 높이**다. 발바닥 전체 메시의 충돌 측정과 같지 않다. 걷기/달리기 수치는 스윙 발과 원본 공중 동작까지 포함하므로 정지 접지 오차처럼 해석하지 않는다. 검사한 화면에서 다리 꼬임은 관찰하지 않았고, 뼈 길이는 ON/OFF에서 유지됐다. 숨기·수면의 IK alpha는 0이다.

![12도 경사 IK 비교](Evidence/JYU_V3/IdleSlope12.png)

앞쪽 개체는 IK OFF, 뒤쪽 개체는 IK ON이다. [4도 비교](Evidence/JYU_V3/IdleSlope.png), [8도 비교](Evidence/JYU_V3/IdleSlope8.png), [걷기](Evidence/JYU_V3/WalkSlope.png), [숨기 전환](Evidence/JYU_V3/HideTransition.png), [달리기](Evidence/JYU_V3/RunSlope.png), [측정 요약](Evidence/JYU_V3/IK_summary.json).

## 재현과 한계

복사 맵을 D3D11 에디터로 열고 `py <project>/Tools/Editor/run_jyu_ik_visual.py`를 실행한다. 결과는 `Saved/IntegrationV3/IKVisual/`에 생성되며 정상적으로 PIE와 에디터가 종료된다. 임시 표현 Actor·발판·카메라만 조작하고 저장 레벨이나 동물 Mass 상태는 바꾸지 않는다.

최종 Build24에서도 같은 10조건을 다시 촬영하고, 먹는 중 새 Hearing/Sight cue를 주는 2조건을 추가해 총 12조건을 확인했다. 각각 포즈 1(먹기) → 2(경계) → 1로 복귀했다. [청각 반응 화면](Evidence/JYU_V3/HearingWhileGraze.png), [시야 반응 화면](Evidence/JYU_V3/SightWhileGraze.png), [시간별 포즈 근거](Evidence/JYU_V3/Sensory_pose_summary.json).

급경사·낭떠러지·빠른 지면 변화·모든 카메라/LOD 조합의 무결함을 보장하는 검사는 아니다. 발목을 지면 노멀로 회전시키는 기능과 접촉 발 잠금은 추가하지 않았다. 보정 제한 밖에서는 원본 포즈를 우선하며, 기존 달리기 클립 자체의 공중 구간은 남는다. D3D12 실행에서 이 PC의 `DXGI_ERROR_DEVICE_HUNG`과 Windows LiveKernelEvent 141이 발생해 D3D11로 검증했다. 프로젝트 기본 렌더링 설정은 변경하지 않았다.


2026-10-16 구분 보강: 비교 사슴에는 `NO AI` 라벨과 HUD 안내가 표시되며, 비교 36초 후 PIE가 자동 종료된다. 일반 생태계를 보려면 Play를 다시 시작한다. `run_jyu_ik_visual.py`는 이후 에디터까지 정상 종료하는 자동 검증용 runner다. 늑대 반응을 확인할 때는 IK 도구를 실행하지 않고 [위협 감사](JYU_THREAT_AND_BACKEND_AUDIT_20261016.md)의 일반 Play 경로를 사용한다.
