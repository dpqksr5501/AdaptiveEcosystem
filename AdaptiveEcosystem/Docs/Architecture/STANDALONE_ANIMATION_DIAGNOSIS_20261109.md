# Standalone 사슴·늑대 고정 포즈 진단

2026-11-09. 사용자 관측: 기아·이주는 작동하지만 발 움직임과 섭식 동작이 사라지고 고정 Mesh가 이동한다. 이번 작업은 로그·Source·설치된 UE 5.8 소스 분석이다. 설정/코드/에셋 수정 및 새 실행 검증은 하지 않았다.

## 확인 사실

- `Saved/Logs/AdaptiveEcosystem_2.log:483`: 13:33 Standalone 세션은 `-game -PIEVIACONSOLE`로 실행됐다.
- 같은 로그 1686: `ABP_JYU_Deer`가 `/Script/AdaptiveEcosystemEditor` import를 찾지 못한다.
- 같은 로그 1824–1825: 사슴·늑대 양쪽 `AnimGraphNode_EcoGroundFeet_1`의 `AnimGraphNodeBinding_Base_0` outer 로딩 실패가 있다.
- 편집기 로그 `AdaptiveEcosystem.log:1378`에는 해당 Editor DLL의 정상 로딩 기록이 있다.
- 이주 변경 전 11:03 Standalone 로그 `AdaptiveEcosystem_2-backup-2026.11.09-02.06.12.log:1687,1860,1861`에도 같은 경고가 있다. 이번 지역 이주 수정이 처음 만든 로딩 오류로 설명할 수 없다.
- 최신 로그에는 Plan 1~9 순차 승인, Approved=9/9 이후 RetentionFloor, 여러 계획의 Arrived=1/1이 확인된다. 논리 이동 경로와 포즈 출력 경로는 독립적이다. Settled Arrived=0/1 사례도 있으므로 모든 개체 생존 도착으로 확대하지 않는다.

## 원래 애니메이션 구조

[표현 Actor](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.cpp)의 `ConsumeVisualState`가 실제 속도/활동을 받으면서 Actor 위치를 갱신한다. [AnimInstance](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureAnimInstance.cpp)는 그 상태에서 `SpeedCmPerSecond`, `AnimationIndex` 등을 계산한다.

[Graph 작성 코드](../../Source/AdaptiveEcosystemEditor/AdaptiveEcosystemEditorModule.cpp)는 이동 BlendSpace와 먹기/경계/수면 등의 SequencePlayer를 BlendListByInt에 연결하고, 발 IK를 거쳐 최종 포즈를 출력한다. 이 경로는 Montage 재생을 호출하지 않는다. Actor 위치만 정상 갱신되고 최종 AnimGraph가 무효라면 고정 포즈의 Mesh가 이동하는 증상이 가능하다.

## 가장 유력한 원인

[uproject](../../AdaptiveEcosystem.uproject)의 `AdaptiveEcosystemEditor`는 Type=`Editor`다. 해당 모듈에 편집용 `UAnimGraphNode_EcoGroundFeet`가 있다. 실제 평가용 `FAnimNode_EcoGroundFeet`는 이미 Runtime 모듈에 있다.

설치된 `Engine/Source/Runtime/Projects/Private/ModuleDescriptor.cpp`에서 `Editor` 모듈은 GIsEditor일 때 로드되고 `UncookedOnly`는 cooked data가 필요하지 않을 때 로드된다. 편집기와 uncooked Standalone의 차이 때문에 후자의 ABP 로드에 필요한 그래프 클래스가 누락되는 것으로 판단한다. [Epic EHostType 문서](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Projects/EHostType__Type)도 이 모듈 종류를 구분한다.

**모듈/그래프 import 실패는 확인 사실이다. 그것이 실제 최종 포즈 정지의 직접 원인인지는 수정 전후 ABP 및 본 포즈 관측으로 확정해야 한다.** 경고만으로 AnimInstance 자체가 없다고 단정하지 않는다. 현재 로그에 포즈 시간/본 변환 표본은 없다.

## 권장 수정 순서

1. 해당 모듈의 현재 책임을 대조한 후 Type을 `UncookedOnly`로 바꾸는 최소 변경부터 검증한다. 현재 클래스 패키지 이름을 유지하면 저장된 `/Script/AdaptiveEcosystemEditor` 참조도 유지된다. LoadingPhase를 무작정 바꾸는 것으로는 Editor 실행 조건을 해결하지 못한다.
2. 향후 실제 Editor UI 모듈과 분리가 필요하면 그래프 클래스만 UncookedOnly 모듈로 옮기되, 클래스 경로 redirect와 기존 ABP 참조 이전을 함께 처리한다. 런타임 빌드에 UnrealEd/AnimGraph 편집 코드를 넣지 않는다.
3. 편집기에서 사슴·늑대 ABP의 컴파일 상태·최종 Output Pose 연결을 확인한다. 자동 Graph 재생성/에셋 일괄 저장은 첫 해결책으로 사용하지 않는다. 필요한 경우 해당 ABP만 수정한다.
4. 같은 맵의 PIE와 별도 Standalone에서 import 오류 소멸과 실제 애니메이션 평가를 비교한다. 문제 지속 시 실제 AnimClass/AnimationMode, SkeletalMesh tick, PauseAnims, 재생속도, 속도/활동 입력, 출력 포즈 순으로 좁힌다.
5. cooked Development 실행에서도 Runtime 포즈 노드만으로 정상 동작하는지 확인한다. uncooked Standalone 성공을 packaged 성공으로 간주하지 않는다.

## 검증 항목

- 사슴과 늑대 모두: 유효한 BehaviorAnimationClass/AnimationProfile 및 실제 AnimInstance 클래스 확인.
- 걷는 개체: 이동 속도 > 0, 이동 AnimationIndex=0, 애니메이션 시간이 진행하고 다리 본의 **local/component 공간 상대 변환**이 프레임 사이 변하는지 확인. World 좌표 변화는 Actor 이동만으로도 발생하므로 증거로 부족하다.
- 정지 섭식: 해당 Activity와 AnimationIndex=1, 섭식 시퀀스 시간 및 목/머리 본 포즈 변화 확인.
- 이동 중 이주/일반 이동, 근거리/원거리, 풀에서 재바인딩된 Actor를 비교한다.
- 기존 `EcoJYUIntegrationTests`의 NativeUpdateAnimation 직접 호출/AnimationIndex 검사만으로 uncooked Standalone의 완성된 Graph 평가를 검증할 수 없다. 별도 실행 표본이 필요하다.

이주를 끄거나 Montage로 전환하는 것은 현재 증거가 가리키는 첫 수정점이 아니다. 이번 테스트를 Standalone으로 안내하면서 이 애니메이션 로딩 차이를 검증하지 못했던 부분을 후속 acceptance에 추가한다.
