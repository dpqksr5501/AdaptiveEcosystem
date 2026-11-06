# 플레이어 총기와 플레이어별 표현 대상 계약

2026-11-06. 기준 브랜치 `jwj-1024`, 시작 HEAD `867d39ed`. 이번 구현의 기능·검증 기록이다.

## 플레이 규칙

각 플레이어는 자신에게 표현이 준비된 생태계 개체만 직접 공격할 수 있다. 다른 플레이어에게 표현된 개체, 아직 데이터만 도착한 개체, 논리 상태만 존재하는 개체는 자신의 공격 대상이 아니다. 잠깐 카메라 밖으로 나가거나 렌더 LOD가 바뀌는 것은 표현 해제가 아니다. 벽 차폐는 실제 Trace가 판정한다. 자연 포식·대사·사망은 기존 서버 생태계에서 계속 실행된다.

기존 공유 Proxy 예산(기본 256)·생성 거리(기본 1800cm)를 유지한다. 총기 기본 사거리는 1800cm이다. 더 긴 교전은 표현/복제/Proxy 범위를 함께 저작·검증해야 하며, 논리 개체 직접 ray 교차로 우회하지 않는다.

## 실행 구성

| 파일/구성 | 소유 책임 |
|---|---|
| EcoWeaponDefinition | 총 기본 대미지·사거리·발사 간격·Mesh·소켓·조준 프로필 |
| EcoWeaponActor / IEcoRangedWeapon | 무기 외형·총구 World Transform |
| EcoEquipmentComponent | 서버 장착/해제·소켓 검증·장착 Actor 복제 |
| EcoAimComponent / GA_AimWeapon | 우클릭 유지, 카메라 Offset/거리/FOV 보간, 회전·Bone 갱신 복구 |
| EcoWeaponFireComponent / GA_FireWeapon | 조준 중 좌클릭 1발, 서버 발사 간격·무기·시선 검증, 2단계 Trace |
| EcoCombatRelevanceComponent | 소유자별 대상 배정·표현 확인·유효기간 |
| IEcoDamageReceiver / EcoGASDamageReceiverComponent | 일반 Actor/GAS 대상의 피해 수신 계약 |
| 기존 Creature combat/lifecycle | 생태계 피해 큐·Native HP·기억·사망·장부, 이동 writer 추가 없음 |

컴포넌트는 기본 플레이어 Character에 구성된다. 무기 설정이 없으면 기존 플레이를 유지한다. 장착은 서버 `Equipment.Equip(Data)` 또는 `InitialWeapon`으로 지정한다. Client가 무기나 대미지를 임의 지정하지 않는다.

캐릭터 손 Bone 아래 `socket_Gun`, 총 Mesh에 `socket_Muzzle`을 저작한다. Static/Skeletal Mesh를 모두 지원한다. 명시적 대체 지점은 Weapon BP의 `bUseMuzzlePoint` + `MuzzlePoint`다. 잘못된 소켓은 장착을 거절한다. 서버 사격 중 Bone 갱신을 보장하고 종료 후 기존 설정을 복원한다. 왼손 IK·총 전용 Aim Offset 애니메이션은 가져올 실제 무기/애니메이션에 맞춰 저작해야 한다.

## 플레이어별 대상과 표현 확인

서버는 유효한 공유 Proxy 중 거리·시선 방향·기존 대상 유지 가산점으로 플레이어별 대상을 고른다. 상한은 Proxy 예산과 표현 Actor 예산 중 작은 값이다. 원격 플레이어는 해당 소유자의 실제 Mass bubble 입장 목록에도 포함되어야 한다. 배정은 owner-only replicated Offer(Coordinator, WorldEpoch, Revision, StableAgentIds)로 보낸다.

기존 SyncVisuals는 배정된 대상을 우선 배치하고, 실제로 바인딩되어 상태가 적용된 살아 있는 표현 Actor만 보고한다. 소유 Pawn의 컴포넌트가 배정과 표현 목록의 교집합을 서버에 확인한다. 서버는 배정 버전을 검증하고 0.75초 이내 확인만 사용한다. 준비 확인은 0.2초 간격과 표현 변경 시 갱신한다. Epoch/Coordinator 변경 시 이전 준비 목록을 지운다. 클라이언트 보고는 준비 확인이며 실제 렌더 픽셀의 증명이 아니다. HP와 명중 권위는 서버에 있다.

서버는 스스로 배정하지 않은 ID·오래된 배정 버전을 승인하지 않는다. 연결·Pawn 변경으로 컴포넌트가 교체되면 준비 상태도 사라진다. 준비되지 않은 대상에 대한 전역 논리 개체 fallback은 없다. 원격 클라이언트가 로드를 끝내지 못하면 해당 플레이어의 직접 공격은 허용하지 않는다.

무기 Trace는 사격자에게 허용되지 않은 생태계 Proxy를 Ignore한다. 보이지 않는 다른 플레이어용 Proxy가 총알을 막지 않는다. 월드 차단은 유지한다. 기존 콤보의 접촉 단계와 큐 입장, legacy strike의 대상 선택에도 동일한 제한을 적용한다. 이미 서버가 승인한 명중은 이후 표현 회수만을 이유로 취소하지 않는다.

현재 대상 유지 가산점·기존 거리 이탈 여유는 있으나 교전별 장기 예약/완전한 다중 플레이어 공정 배분은 별도 확장 지점이다. Proxy 예산 전체가 소진되면 새 논리 개체를 즉시 명중시키지 않는다.

## 발사와 대미지

카메라 중앙 Trace는 조준점을 구한다. 총구에서 조준점을 향해 사거리만큼 최종 Trace하고 가장 가까운 차단 결과로만 피해를 만든다. Eye→카메라/총구 차폐와 총구 겹침 검사도 한다. 기본 채널은 기존 맵에서 쓸 수 있는 Visibility이며 커스텀 채널로 교체 가능하다. Proxy는 Visibility를 Block하도록 변경했다. 표현 Actor 자체는 권위 충돌이 아니다.

서버는 살아 있는 소유 플레이어·장착 무기 일치·조준 상태·발사 간격·유한한 수치·허용 시선 방향·카메라/총구 거리와 차폐를 검증한다. 카메라 허용 위치는 Pawn으로부터 650cm, 총구는 300cm다. 현재는 서버 최신 위치 판정이며 과거 위치 되감기 지연 보상은 없다.

피해 스냅샷 = WeaponDefinition.BaseDamage + 서버의 AmmoDamage(현재 기본 0). 무기 교체 후 큐의 기존 공격 수치는 바뀌지 않는다. 탄약/발사체 Actor는 아직 생성하지 않는다. 향후 탄약 정의를 이 입력에 연결할 수 있다. 방어·부위·거리 보정은 현재 활성화하지 않는다.

일반 대상은 Actor 인터페이스 또는 첫 수신 컴포넌트 한 곳에만 전달한다. GAS Adapter는 기존 Health Attribute에 Instant GE를 적용하며 플레이어 무적/사망을 확인한다. 생태계 Proxy는 기존 FIFO 피해 큐로 들어가 동일 WorldEpoch·공격 실행·StableAgentId·Avatar 세대 검증을 거쳐 기존 ApplyPlayerDamage를 호출한다. Queued, Committed, DeathCommitted를 구분하며 확정 피해·사망은 owner 결과 RPC로 통지한다.

`OnShot(Execution,Muzzle,End)`는 서버 승인 발사의 multicast 연출 이벤트다. 총구 화염·발사음·반동·궤적은 실제 총 에셋에서 이 이벤트에 연결한다. 현재 시험 에셋은 큐브 외형이며 완성된 총 아트/애니메이션을 뜻하지 않는다.

## 기존 플레이어에서 사용

`Tools/Editor/setup_jwj_rifle.py`는 기존 `/Game/JWJ/Gameplay/BP_EcoPlayer_Common`, `BP_EcoPlayerController_Common`, `DA_EcoAbilityInputs_Common`에 직접 총기를 연결한다. 기존 `BP_EcoGameMode_Common`과 맵의 GameMode 설정을 사용한다. 별도 총기 Pawn/GameMode는 사용하지 않으며 최초 검증용 복사본은 삭제했다. 사용자 콤보 에셋과 원본 맵은 이 도구에서 저장하지 않는다.

새 무기·입력 리소스만 `/Game/JWJ/Weapons/`에 둔다. 기존 캐릭터 Mesh에 누락된 mesh socket_Gun을 hand_r 아래 추가한다. 이미 있는 소켓의 Transform은 덮어쓰지 않는다. 공통 Pawn의 InitialWeapon은 DA_PlaceholderRifle, WeaponClass는 BP_PlaceholderRifle이다. 실제 총 Mesh가 아직 없으므로 큐브 모양의 임시 외형을 사용한다.

- 기존 플레이 맵에서 Play하면 기존 플레이어가 무기를 장착한다.
- 우클릭 유지로 조준, 좌클릭 한 번에 1발, 우클릭 해제로 카메라 복귀. 기존 F 콤보 입력은 유지한다.
- 실제 총: WeaponDefinition에서 Mesh/소켓/GripOffset을 저작하고 기존 Pawn의 Equipment에 지정한다. 총구 소켓을 사용할 때 기본 AEcoWeaponActor 또는 MuzzlePoint fallback을 끈 BP를 사용한다.
- 재실행은 기존 무기 수치를 보존하고 누락된 입력만 추가한다.

## 검증

검증 산출물은 `Saved/RifleValidation/`에 기록한다. 실행 결과는 아래 최종 기록을 따른다. 이전 실패 로그를 성공 근거로 사용하지 않는다.


최종 실행 결과:

- 직접 UBT `AdaptiveEcosystemEditor Win64 Development` 성공. `Saved/RifleValidation/BuildFinal.log`.
- 전체 자동화 233개: Success 230, SuccessWithWarnings 2, Fail 1, NotRun 0. `Saved/RifleValidation/AllFinal/index.json`. 실패는 `RefugeVisualComposition`: 기존 수풀/바위 프로젝트 Mesh가 없어 외형 구성 검증 실패. 이번 변경은 해당 은신처/누락 에셋을 수정하지 않았다. 새 총기·표현 대상·벽 차폐 테스트는 성공했다.
- 기존 공통 Pawn/GameMode의 실제 PIE PASS: 장착, 조준 없이 발사 거절, 우클릭 조준과 카메라 보간, 좌클릭 1발, 발사 간격 제한, 해제 후 카메라 복원, Unequip 시 조준 종료. `Saved/RifleValidation/PIECommon.log`, `PIE.json`. 맵 설정·위치 fixture는 저장하지 않았다.
- Dedicated + 실제 Client A/B PASS. B의 로컬 표현을 숨긴 동안 대상 HP 100 유지·B 피해 결과 0. A는 30+30+30+10으로 서버 피해 4회·사망 장부 1회, owner의 Committed/DeathCommitted 결과 수신. Client 논리 개체 0 확인. `Saved/RifleValidation/Network/{Server,A,B}.json`과 로그.
- 네트워크 검증은 실제 Enhanced Input 주입으로 수행했다. Python에서 GA 입력을 직접 호출하면 Editor script execution guard가 RPC를 로컬 실행시킬 수 있어 검증에 사용하지 않는다. 첫 능력 목록 복제가 끝난 뒤 입력을 시작한다. 이 fixture의 서버 플레이어 배치는 자연 생태 균형 검증이 아니다.
- 가져올 실제 총 Mesh·발사음·총구 화염·총 전용 애니메이션은 미제공 상태다. 현재 큐브 무기는 기능 확인용이다. `OnShot`에 해당 연출을 연결하고 실제 무기 소켓/GripOffset을 조정한다. 과거 위치 되감기, 실제 탄약 재고·재장전, 부위별 피격은 이번 구현에 포함하지 않는다.

개발 중 생성했던 별도 총기 Pawn/Controller/GameMode/복사 Mesh/복사 입력 DA는 최종 산출물에서 제거했다. 기존 사용자 수정 콤보 DA·설정 도구·문서는 덮어쓰지 않았다. 최초 구현 종료 시점에는 커밋·push를 수행하지 않았다.

2026-11-06 기능별 커밋 정리 시 직접 UBT `AdaptiveEcosystemEditor Win64 Development`를 다시 실행해 `Target is up to date`, `Result: Succeeded`를 확인했다(`Saved/RifleValidation/BuildCommitReview.log`). 위 자동화·PIE·네트워크 결과 파일을 대조했으며 해당 실행을 새로 반복한 것은 아니다. 콤보 손 소켓 보정과 공간 탐색 최적화 계획은 별도 커밋 범위다.
