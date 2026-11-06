# JWJ 무기 없는 콤보 공격

2026-11-05 최초 구현. 기존 GAS 입력 설정을 사용한다. **후속으로 동물 피해·플레이어 HP를 연결했다.** 현재 동작과 수동 검증은 [사냥·생태계 구현 및 테스트](../Architecture/PLAYER_HUNTING_IMPLEMENTATION_AND_TEST_20261106.md)를 따른다. 아래 최초 검증의 미연결 설명은 당시 범위다.

## 에디터 설정

- 공통 Pawn `/Game/JWJ/Gameplay/BP_EcoPlayer_Common`의 `MeleeHit.AttackData`는 `/Game/JWJ/Gameplay/DA_EcoUnarmedCombo`다.
- `/Game/JWJ/Gameplay/DA_EcoAbilityInputs_Common`에서 기존 `IA_ComboAttack`을 `EcoGameplayAbility_ComboAttack`에 연결했다. 활성화는 Started다.
- 키는 `/Game/JWJ/Gameplay/IMC_EcoAbilities_Common`에서 바꾼다. 현재 F를 재사용한다.
- `/Game/JWJ/Gameplay/AM_EcoUnarmedCombo`는 MM_Attack_01/02/03을 각각 LeftPunch/RightPunch/Kick Section으로 사용한다. 각 Section은 기본적으로 다음 Section에 자동 연결하지 않는다.
- 공유 SK_Mannequin Skeleton에 Attack_Hand_L(hand_l), Attack_Hand_R(hand_r), Attack_Foot(foot_l) 소켓을 추가했다. Skeleton Editor에서 위치/회전을 조정할 수 있다.
- 2026-11-06 실제 공격 손 순서 정정: 1단계 MM_Attack_01은 오른손 `Attack_Hand_R`, 2단계 MM_Attack_02는 왼손 `Attack_Hand_L`, 3단계는 오른발 `foot_r`다. 기존 Montage Section 이름 `LeftPunch`/`RightPunch`는 호환용 식별자로 유지하므로 이름 대신 단계별 Socket을 기준으로 본다. 공격 타이밍·반경·피해는 유지한다. 기존 두 저작 도구도 이 매핑을 사용한다.
- 단계별 Section·Socket·Radius·Damage는 DA에서 편집한다. TargetObjectTypes와 ObstructionChannel도 DA에 있다. 후속 구현은 서버 피격 Proxy를 통해 실제 생태계 HP에 피해를 확정한다. 발차기는 실제 모션에 맞춰 오른발 `foot_r` bone을 사용한다.
- DrawDebug를 켜면 활성 Window 동안 Sphere와 Sweep 경로가 표시된다.

## 애니메이션 타이밍

초기 저작값은 각 애니메이션 길이의 22~48%에 HitWindow, 첫 두 공격의 32~73%에 ComboInputWindow, 80%에 ComboBranch다. 이는 모션에 맞춰 에디터에서 조정할 시작값이다. Montage Notify 트랙에서 직접 길이와 위치를 변경한다. 원본 Sequence에는 Notify를 추가하지 않았다.

ComboBranch는 입력 Window와 타격 Window가 닫힌 뒤에 놓는다. 이 Notify는 Branching Point다. 발차기에는 다음 단계 입력/분기가 없다. 재입력이 없으면 현재 공격에서 종료한다. 누른 상태 유지와 Window 밖 입력은 다음 공격을 예약하지 않는다. Window당 다음 단계 하나만 예약한다.

## 책임과 확장

- EcoGameplayAbility_ComboAttack: 서버가 콤보 상태와 전환을 결정. ServerInitiated Montage와 엔진 기본 입력 직접 복제를 사용한다. 로컬 예측/지연 보정은 구현 범위 밖이다.
- EcoMeleeHitComponent: 서버에서만 소켓 부착 Query Sphere와 이전→현재 소켓 위치 Sphere Sweep을 실행. 자기 자신/부착 Actor를 제외하고 World Visibility로 차폐를 검사한다. 단계당 Actor 한 번으로 중복 제거한다.
- EcoAttackWindowReceiver: Notify와 실행 컴포넌트 사이 인터페이스. Notify에는 플레이어별 런타임 데이터를 저장하지 않는다.
- EcoAttackNotifies: 입력/타격 Window 시작·종료, 콤보 분기 전달.
- OnContact(Target,Hit,Step,Damage): 서버의 충돌 후보 이벤트. 후속 구현에서 실제 Proxy 접촉은 별도로 QueueComboContact에 전달한다. OnContact와 최종 피해 확정은 서로 다르며, 최종 결과는 OnDamageOutcome으로 받는다.
- 공격 중 AlwaysTickPoseAndRefreshBones로 소켓 위치 갱신을 보장하고 종료 시 기존 Tick 설정으로 복원한다. 모든 종료/중단은 타격과 입력 상태를 정리한다.

후속 ECS 경로는 WorldEpoch·StableAgentId·공격 실행 ID·단계 ID를 검증하며 개체 단위 중복 제거를 수행한다.

## 실행과 검증

직접 UBT AdaptiveEcosystemEditor Win64 Development 최종 빌드 성공(Saved/JWJCreatureSetup/combo_build.log). 실제 JWJ 맵의 Standalone PIE에 임시 Sphere 대상을 배치하고 Enhanced Input을 주입했다. 단타 1회, 유효한 재입력 3연속 3회, 길게 누르기 1회, Window 밖 조기 입력 1회, Montage 중단 1회의 접촉을 확인했고 모든 경우 종료 후 ActiveStep=-1이었다. Pawn 이동량을 제외한 실제 손 소켓 변위도 33~95cm로 확인했다. 임시 대상과 테스트 중 Pawn 위치 변경은 맵에 저장하지 않았다.

검증 스크립트는 Tools/Editor/verify_jwj_combo_attack.py다. 별도 테스트 에디터의 Python에서 실행한다. PIE와 임시 fixture를 정리하며 저장하지 않는다. Saved/JWJCreatureSetup/combo_final_pie.log에 다섯 Case와 PASS가 있다. 물리 키 입력, Dedicated+Client, 지연/패킷 손실, 낮은 FPS와 별도 벽 fixture는 아직 검증하지 않았다. 기존 프로젝트의 MWLandscapeAutoMaterial 누락 에셋 경고/오류는 이 검증 로그에도 나타난다.

수동 확인: 현재 1102 맵에서 F 한 번, 길게 누르기, 왼손/오른손 회수 전 각각 다시 누르기를 비교한다. 콤보 데이터의 DrawDebug를 켜고 동물에 대한 접촉을 확인한다. Output Log의 [EcoCombo] Started/Queued/Advance/HitOpen/Contact/End와 [EcoCombat][Outcome]을 구분한다. 구체적인 사냥·피격·이주 확인 순서는 후속 테스트 문서를 따른다.

Tools/Editor/setup_jwj_combo_attack.py는 신규 owned Montage·DA를 생성하고 기존 공통 Pawn/입력 DA를 연결한다. 이미 있는 Montage/DA의 타이밍과 단계 설정은 재실행으로 덮어쓰지 않는다. 공유 Skeleton에 필요한 소켓을 추가하는 최초 저작만 수행한다.
