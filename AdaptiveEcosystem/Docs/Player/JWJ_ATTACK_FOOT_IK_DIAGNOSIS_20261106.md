# 플레이어 공격 중 발 고정 진단

2026-11-06. 사용자 증상: 플레이어의 모든 공격에서 발이 바닥에 붙고 발차기 다리가 올라가지 않음. 분석만 수행했으며 게임 코드·Blueprint·Animation 에셋을 수정/저장하지 않았다. 별도 읽기 전용 Python commandlet에서 저장된 에셋을 추출했다. 사용자 에디터의 미저장 변경은 이 결과에 포함되지 않는다.

## 확인한 원인 경로

현재 `/Game/JWJ/Gameplay/BP_EcoPlayer_Common`의 Mesh는 `SKM_Quinn_Simple`, AnimClass는 **`/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed`**다.

저장된 AnimGraph의 연결은 다음과 같다.

```text
Locomotion StateMachine
    → DefaultSlot (AM_EcoUnarmedCombo가 출력되는 위치)
    → ControlRig: CR_Mannequin_FootIK
    → Output Pose
```

`AnimGraphNode_ControlRig_0`의 **Alpha는 연결 없이 상수 1.0**이다. `ShouldDoIKTrace`는 `NOT IsFalling`에만 연결되어 있으며 공격 여부를 검사하지 않는다. 따라서 지상에서 공격 Montage가 재생되어도 최종 포즈에 발 IK가 계속 적용된다.

Rig는 `IK_foot_L`/`IK_foot_R`의 global transform을 읽어 PBIK의 `foot_l`/`foot_r` effector 목표로 사용한다. 실제 공격 Sequence에서 FK 발은 움직이지만 IK 발의 높이는 계속 지면 부근에 남는다. 최종 IK가 공격의 발 포즈를 이 목표 쪽으로 되돌리는 경로다. 공격 전체에 공통 적용되므로 모든 공격에서 발이 붙는 증상과 일치한다.

## 원본 공격은 움직이는가

`MM_Attack_01`, `02`, `03`을 길이의 0/25/50/75/100%에서 AnimPose로 직접 평가했다.

| Sequence | EnableRootMotion | ForceRootLock | 실제 foot_r의 샘플 높이(cm, 원본 포즈 공간) |
|---|---|---|---|
| MM_Attack_01 | true | false | 8.2 / 16.2 / 8.2 / 8.2 / 8.2 |
| MM_Attack_02 | true | false | 8.1 / 7.9 / 14.6 / 22.0 / 8.1 |
| MM_Attack_03 | true | false | 14.6 / **150.2** / 6.2 / 11.1 / 6.2 |

각 Sequence의 `ik_foot_l/r` 높이는 약 8.2cm로 유지된다. 발차기 원본에서 오른발이 정상적으로 올라가는 것과 지면 부근에 남는 IK 목표 사이 차이가 크다. ForceRootLock은 세 에셋 모두 false다. EnableRootMotion=true 및 AnimInstance의 RootMotionFromMontagesOnly 설정은 별도 사항이며, Root Lock 옵션 자체는 root bone 고정에 관한 설정이다.

## 기존 전투 Blueprint와의 차이

`/Game/Variant_Combat/Anims/ABP_Manny_Combat`도 Slot 뒤에 같은 FootIK Rig가 있지만 Alpha 연결이 다르다.

```text
IsSlotActive(DefaultSlot)
    → SelectFloat(A=0, B=1)
    → ControlRig Alpha
```

공격 Slot이 활성화되면 Alpha0, 평상시에는 Alpha1이다. 현재 공통 플레이어는 이 전투용 IK 우회가 없는 ABP_Unarmed를 사용한다. 콤보를 연결할 때 이 차이를 반영하지 않은 것이 통합상의 빠진 부분이다.

## 권장 수정과 확인 방법

현재 플레이어용 owned AnimBlueprint에서 같은 공격 Slot 활성 여부에 따라 FootIK Alpha를 제어한다. 일반 이동의 지면 보정을 유지하고 공격 중에는 원본 발 포즈를 사용한다. 중단·종료 후 Alpha가 복원되는지, 필요하면 블렌딩을 부드럽게 적용할지 확인한다. 전체 공유 ABP_Unarmed를 바꾸거나 Root Lock을 일괄 변경하는 것은 이번 진단에 필요한 수정이 아니다.

빠른 원인 확인은 AnimGraph에서 해당 ControlRig Alpha를 임시 0으로 두고 같은 공격을 비교하는 것이다. 이때 발차기 다리가 올라오면 IK가 최종 포즈를 덮는 것을 실행으로 확인할 수 있다. 이 임시 우회 실행은 이번 분석에서 수행하지 않았다. 실제 수정 후에는 3단계 공격·단타·중단·걷기/경사·Client를 함께 검증해야 한다.

이전 `foot_r` 변경은 타격 Sphere의 부착 위치 수정이다. 시각 포즈의 FootIK 제어와 별개다. 이전 사냥 테스트는 접촉·피해·사망을 검증했으므로 발의 최종 시각 포즈가 정상이라는 증거로 사용할 수 없다.

추출 근거는 `Saved/PlayerHunting_20261105/AttackIK/AssetInspection.json`, `ABP_Unarmed.t3d`, `ABP_Manny_Combat.t3d`, `CR_Mannequin_FootIK.t3d`이며 Git 추적 대상이 아니다. 분석 commandlet 정상 종료(0), `AttackIK_Inspection.log`. C++/에셋 변경이 없어 새 UBT/PIE를 실행하지 않았다.
