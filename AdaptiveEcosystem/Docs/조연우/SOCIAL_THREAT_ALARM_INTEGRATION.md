# 실제 위협 → Social Alarm 연동

> 작업 브랜치: `codex/social-threat-integration` · 2026-09-30<br>
> 담당 범위: 조연우 — Herd / Alarm / Social Response / Shelter 의도와 예약<br>
> 이 문서는 작업 브랜치의 변경 사항이다. main 반영 여부와 에디터 검증 여부는 구분한다.

## 1. 이번에 구현한 것

기존에는 테스트 Harness가 경보를 직접 넣었다. 이제 Social 개체가 실제 위협을 발견하면 자신이 속한 Herd에 경보를 전달한다.

```text
Mass 포식자: 기존 Neighborhood Grid
플레이어 / 포식자 Actor: EcoThreatSourceComponent
                ↓
Social 구성원의 거리 · 시야각 · Visibility LOS 확인
                ↓
Herd마다 대표 위협 하나 선택 → 실제 감지 입력 갱신
                ↓
Alarm 수신 / 감쇠 → Social Response → Shelter 탐색 / 예약
```

Raw PPO Action, 관측 7개·행동 4개, Ecology 자원/개체군, Network 전송과 이동 writer는 변경하지 않았다. `ModulatedAction`과 Shelter `TargetPosition`은 아직 실제 Steering/Movement로 연결되지 않는다. 예약 성공을 도착 또는 `Occupied`로 해석하지 않는다.

## 2. 코드의 역할

| 파일 | 역할 |
|---|---|
| [EcoThreatDetectionProcessor.cpp](../../Source/AdaptiveEcosystem/AI/Social/Alarm/EcoThreatDetectionProcessor.cpp) | 기존 Mass 공간 그리드와 Actor 위협 스냅샷을 읽어 Herd별 위협 선택 |
| [EcoThreatSourceComponent.h](../../Source/AdaptiveEcosystem/AI/Social/Alarm/EcoThreatSourceComponent.h) | 실제 플레이어/Pawn 또는 포식자 Actor가 Social 위협임을 명시하는 컴포넌트 |
| [EcoHerdSubsystem.cpp](../../Source/AdaptiveEcosystem/AI/Social/Herd/EcoHerdSubsystem.cpp) | Actor 소스 등록, 수동 경보와 감지 경보 분리, 최종 Herd 경보 확정 |
| [EcoAlarmProcessors.cpp](../../Source/AdaptiveEcosystem/AI/Social/Alarm/EcoAlarmProcessors.cpp) | 경보를 구성원에 전달하고 움직이는 위협 위치 갱신; Raw를 보존한 Social 보정 |
| [EcoSocialTrait.cpp](../../Source/AdaptiveEcosystem/AI/Social/EcoSocialTrait.cpp) | Client 논리 Social 구성 제외; 소비하는 Fragment를 템플릿 요구사항으로 선언 |
| [EcoThreatAlarmTests.cpp](../../Source/AdaptiveEcosystem/AI/Social/Tests/EcoThreatAlarmTests.cpp) | 실제 Processor와 충돌 월드로 감지 → Alarm → Shelter 예약 회귀 검증 |

위협 컴포넌트에는 Tick, 이동, 공격 AI, RPC가 없다. BeginPlay에 권위 있는 World의 Herd Subsystem으로 등록하고 EndPlay에 해제한다. 약한 참조를 사용하며 비활성·삭제·무효 액터는 제외한다. 모든 Pawn을 자동으로 위협으로 취급하지 않는다.

## 3. 감지 계약

- 감지는 **Server / Standalone, PrePhysics, GameThread**에서 0.2초마다 수행한다. 첫 실행은 즉시 감지한다. 큰 프레임 지연이 생겨도 한 프레임에 여러 감지 패스를 몰아서 실행하지 않는다.
- 관찰자는 `FEcoAliveTag`, Transform, Velocity, HerdMember와 Social/Species Shared가 있어야 한다. ClientProxy/PendingDeath 및 HP가 0 이하인 구성원은 감지하지 않는다.
- Mass 소스는 기존 Gather가 수집한 `FEcoPredatorTag` 항목을 재사용한다. 무효 Entity, ClientProxy, PendingDeath, HP가 0 이하인 포식자는 제외한다. Vitals가 없는 기존 포식자 대역도 지원한다.
- 포식자의 Vitals/Representation 읽기는 쿼리에 **간접 ReadOnly 접근**으로 선언한다. 관찰자와 다른 Archetype에 대한 읽기도 Mass 의존성 계산에 포함한다.
- Actor 소스는 `EcoThreatSourceComponent`를 명시적으로 추가한 Actor다. 활성 상태와 `bThreatEnabled`, 권위, RootComponent, 유효한 좌표/강도를 확인한다.
- 거리 판정은 3D, 시야각은 XY다. `FEcoSpeciesSharedFragment.ViewDistance` / `FOV`를 사용한다. 기본 1500cm / 120도다. 잘못된 설정으로 공간 그리드 셀 조회가 폭증하지 않도록 거리 상한은 10000cm다. PPO 시연의 `EcoBehaviorConfig.SeeRadiusCm/FovDeg`와는 별도 계약이다.
- 진행 방향은 Velocity XY, 정지 시 Transform의 X축, 둘 다 무효하면 World +X다.
- 기본 LOS는 필요하다. Social Shared의 `ThreatEyeHeight` 기본 60cm를 양쪽에 더해 Visibility Simple Line → Complex Line으로 확인한다. 소스 액터와 관찰자의 Mass Representation Actor는 무시한다.
- LOS는 위협을 **발견할 수 있는지** 확인한다. Shelter의 구체 스위프/오브젝트 fallback은 은신처의 **안전 점수**를 위한 별도 질의다. 감지에 구체 두께를 넣어 벽 모서리 밖 위협까지 숨기지 않는다.
- `(0,0,0)` 및 같은 위치도 유효한 위협이다. 위협 유무는 좌표가 아니라 강도와 소스 유효성으로 판단한다.
- Herd 중심에서 감지하지 않는다. 구성원 한 마리가 발견해도 같은 Herd에 전파된다. 다른 Herd로 자동 릴레이하지 않는다.

### 여러 위협 중 선택

관찰자 기준 `Strength × exp(-AlarmDistanceDecay × 거리)`가 큰 위협을 Herd 대표로 선택한다. 동점은 소스의 World 내 런타임 키로 정렬한다. Mass 키는 Entity Index/Serial, Actor 키는 컴포넌트 UniqueID다. 같은 World 내 순회 순서에 영향받지 않으며, 재실행·다른 서버 사이의 영속 재현성을 보장하는 ID는 아니다.

선택 우선순위에만 거리 감쇠를 적용한다. 실제 Herd 입력에는 소스의 원래 강도를 전달하므로, 구성원 수신 때 거리 감쇠가 중복 적용되지 않는다. 같은 Herd에 속한 구성원의 감지 횟수를 합산하지 않는다.

## 4. 경보 갱신과 종료

| 입력 | 갱신 방식 | 종료 방식 |
|---|---|---|
| 수동 / Harness | 기존 EmitHerdAlarm / EmitSpatialAlarm. 수동 입력 안에서 높은 강도 선택 | 시간 감쇠 또는 ClearHerdAlarms |
| 실제 감지 | 매 감지 패스의 결과로 이전 감지 입력을 교체. 이동·강도 저하도 반영 | 시야 밖 / 벽 차폐 / 죽음 / 소스 비활성·삭제 시 다음 패스에서 공급 종료 |

Herd 최종 출력은 두 입력 중 강한 것을 선택하며, 동일 강도이면 실제 감지가 우선이다. 감지 결과가 없어도 수동 경보를 지우지 않는다. 각 입력은 기존 Herd 감쇠율 0.2/초로 감소한다. 구성원은 자신의 `AlarmTimeDecay`로 경보 기억을 감소시킨다.

살아 있는 위협 입력이 있으면 구성원의 `LastThreatPosition`은 현재 대표 위협 위치로 갱신한다. 이전 강한 경보의 **강도 기억** 때문에 위치까지 과거에 고정되던 버그를 수정했다. 위협이 사라진 뒤에는 마지막 위치를 기억하다 강도 0 / Calm에서 위치도 초기화한다.

감지 커밋에는 `HerdRuntimeIndex`와 `PersistentHerdId`를 함께 확인한다. 해제된 Herd 슬롯이 재사용되어도 이전 감지 결과가 새 Herd로 들어가지 않는다. 할당/해제 시 입력도 초기화한다. NaN/무한 강도, 음수 반경·시간은 경보 API에서 거부한다.

`ClearHerdAlarms()`는 현재 두 입력을 지운다. **감지 기능이나 실제 위협 자체를 끄는 API는 아니다.** 실제 위협이 계속 보이면 다음 패스에 경보가 다시 들어온다. 종료 확인 시 Harness 연속 주입을 끄고 실제 소스를 비활성화하거나 시야 밖으로 이동시킨다.

## 5. 실행 순서와 Entity 구성

```text
Herd Membership → Herd Aggregate ─┐
Neighborhood Gather ─────────────┴→ Threat Detection → Alarm Propagation ─┐
Gather → Perception → Policy ────────────────────────────────────────────┴→ Social Response
                                                                              ↓
                                                        Shelter Query → Reservation
```

Threat Detection은 Gather와 Herd Aggregate 이후, Alarm은 Detection 이후, Social Response는 Alarm과 Policy 이후에 실행하도록 명시했다. Steering은 여전히 Raw Action을 읽으므로 Response와 Steering 사이의 소비 계약은 다음 담당자 협업 과제다.

Social Trait가 다른 계층의 Alive/Authority/Species/Policy를 임의로 생성하지 않는다. Identity, Transform, Velocity, PolicyOutput은 `RequireFragment`로 누락을 알린다. Species Shared, Alive 및 production Authority 구성은 해당 Trait/스폰 구성에서 확인해야 한다. Social Trait는 Client 템플릿에 논리 Fragment를 추가하지 않는다(에디터 inspection 제외).

기존 JYU Herd Harness는 이미 Social 관찰자 구성을 갖췄다. M3 production EntityConfig에 Social Trait가 실제 포함되어 있는지는 에디터에서 별도로 확인한다. 이 작업에서는 `.uasset/.umap`을 변경하지 않았다. M3 Bootstrap의 Herbivore/이동 가드를 제거하거나 두 이동 경로를 같은 Entity에 섞지 않는다.

## 6. JYU에서 확인하기

1. `Lvl_JYU`를 연다. 기존 Herd/Shelter HUD와 Shelter Anchor를 유지한다.
2. Alarm Harness의 자동·연속 주입을 끈다. 기존 수동 경보를 Clear한다. Shelter HUD의 ThreatLocationOverride도 사용하지 않도록 끄고 좌표를 0으로 초기화한다.
3. 실제 플레이어 Pawn 또는 포식자 Blueprint에 **Eco Threat Source** 컴포넌트를 추가한다. `ThreatEnabled = true`, `ThreatStrength = 1`로 둔다. 기본 Root가 있는 Actor/Blueprint를 사용한다.
4. 관찰자 개체의 전방·시야 거리 안으로 이동한다. 정지 구성원은 Transform X축을 본다는 점을 확인한다.
5. 구성원의 Alert/Panic, Social Cover 상승, Shelter Searching/Reserved와 슬롯 소유자를 확인한다. 실제 은신 이동·Occupied는 이번 완료 기준이 아니다.
6. 위협을 이동시키면 현재 위협 위치에 따라 경보/Shelter 질의가 갱신되는지 확인한다. 이미 예약된 목적지는 기존 재탐색/예약 정책을 따르며 매 패스 강제 변경하지 않는다.
7. 위협과 관찰자 사이의 벽은 **Collision Enabled = Query Only 또는 Query and Physics, Visibility = Block**, 유효한 Simple 또는 Complex 충돌을 갖도록 설정한다. 벽을 사이에 두면 새 감지가 중단되며 기존 경보 기억은 남을 수 있다.
8. 컴포넌트를 비활성화하거나 액터를 삭제한다. 경보 공급 중단 → Recovering/Calm을 확인한다. Raw Cover가 0.25 이상이면 Calm에서도 Shelter 예약을 유지할 수 있다.

Mass 포식자는 기존 포식자 스폰 경로의 `FEcoPredatorTag`와 Gather 등록을 사용한다. 별도 복제 그리드를 만들지 않는다. 플레이어 이동/사냥 구현 및 포식자의 실제 공격·사망 판정은 각 담당 계층이 제공한다.

## 7. 검증 기록

2026-09-30, 로컬 UE **5.8.2**에서 실행했다.

- **직접 UBT**: `AdaptiveEcosystemEditor Win64 Development`, 최종 결과 **Succeeded**. 실행 중인 UBT/dotnet/Editor/LiveCoding/MSBuild/ShaderCompileWorker가 없는 상태에서 시작하고 완료까지 기다렸다.
- **자동화**: `AdaptiveEcosystem.Social.Threat`, 최종 **4 성공 / 0 실패 / 테스트 경고 0**. UnrealEditor-Cmd + NullRHI + Engine Entry 맵에서 실행했으며, 테스트가 자체 Game World와 Entity를 생성했다.
- **보고서**: [Saved/Automation/SocialThreat/index.json](../../Saved/Automation/SocialThreat/index.json), [로그](../../Saved/Logs/SocialThreatAutomation.log). Saved 파일은 로컬 실행 산출물이며 Git에 포함하지 않는다. 다른 PC에서는 테스트를 실행해야 생성된다.
- **문서/변경 검사**: `git diff --check` 통과. 변경 문서의 로컬 링크·코드 블록 검사 통과.

| 자동화 테스트 | 확인한 동작 |
|---|---|
| MassToShelter | 실제 Gather의 포식자 → 감지 → Panic → Social Response → Shelter Reserved. Raw Action 보존, 약해지는 이동 위협 위치 갱신, HP=0/삭제 소스 종료, 기억 감쇠, 정지 FOV, 범위 밖, 원점 좌표, ClientProxy 소스/PendingDeath 관찰자 제외 |
| ActorLOSAndLifecycle | 실제 컴포넌트 BeginPlay 등록, 소스 자체 충돌 제외, Visibility 벽 차폐와 Ignore 응답, 비활성화, 이동/강도 변경, EndPlay 해제 |
| ChannelAndSlotSafety | 수동/실제 경보의 독립성, 오래된 PersistentHerdId 거부, 슬롯 초기화, 음수 반경/시간 방어, 두 입력 Clear |
| ProcessorOrder | 실제 Mass Dependency Solver에서 Gather/Aggregate → Detection → Alarm과 Policy/Alarm → Response → Query → Reservation 순서 확인 |

초기 Actor 테스트 실패는 자체 테스트 월드가 `InitializeActorsForPlay`를 거치지 않아 컴포넌트 자동 활성화가 수행되지 않은 조건이었다. 테스트 준비 단계에서 정상 Actor 초기화의 활성 상태를 명시하고 BeginPlay 등록까지 검증했다. 기능 코드를 우회해 직접 경보를 주입하는 방식으로 테스트를 바꾸지 않았다.

### 사용자 PIE 확인 — 캐릭터 접근 → Alert

2026-09-30 사용자가 캐릭터에 `EcoThreatSourceComponent`를 추가한 뒤, 핑크색으로 표시된 개체에 접근하면 `Alert`로 바뀐다고 보고했다. 첨부 화면에서도 주황색 `[Alert]` 개체와 핑크색 `[Regroup]` 개체를 확인했다. 이는 캐릭터 위협 입력에 따른 경보 반응의 사용자 수동 확인 기록이다. 화면만으로 수동 Harness 비활성 여부와 개별 감지/전파 경로를 분리해 확정하지 않는다.

추가 수동 확인 항목은 가까운 거리의 Panic, 위협 이동에 따른 위치 갱신, 벽 LOS 차폐, 소스 비활성/이탈 뒤 경보 감쇠, 실제 위협에 따른 Shelter 예약이다. 기존 JYU 차폐/예약 표시 검증은 보존한다. production EntityConfig 및 Listen Server/Client 검증은 대기 중이다. 이 결과를 실제 이동/Occupied 또는 전체 생태계 폐루프 검증으로 확대하지 않는다.

재실행은 UBT 빌드 완료 후 에디터 Session Frontend의 Automation에서 `AdaptiveEcosystem.Social.Threat`를 선택하거나 아래 명령을 사용한다. 에디터·빌드가 실행 중이면 추가 빌드를 시작하지 않는다.

```powershell
& 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' `
  'C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/AdaptiveEcosystem.uproject' `
  /Engine/Maps/Entry -unattended -nop4 -nosplash -nosound -NullRHI `
  '-ExecCmds=Automation RunTests AdaptiveEcosystem.Social.Threat' `
  '-TestExit=Automation Test Queue Empty' `
  '-ReportExportPath=C:/Users/I/Documents/GitHub/AdaptiveEcosystem/AdaptiveEcosystem/Saved/Automation/SocialThreat'
```

## 8. 다음 단계

이번 단계 이후 Social 담당의 다음 작업은 **보정 행동과 예약 목적지의 이동 계층 인계 계약**이다. 이동 담당자와 최종 writer, Migration/Shelter/Flee 우선순위, 도착 판정과 예약 연장 주체를 확정한다. 그 뒤 Social 내부의 Moving/Occupied 및 Death/Despawn/Migration 해제를 연결한다. PPO 차원 변경·Bootstrap 가드 삭제·이동 전체 재작성은 선행 작업으로 잡지 않는다.
