# 감각·인지 AI와 Social 연동

> 최초 구현 2026-10-02 · 인지 인계 계약 확장 2026-10-05 · 조연우 담당 · UE 5.8
>
> 범위: 시각·청각·개체별 위협 기억·정보 출처 구분. 후각은 제외한다.
> PPO V1 가중치/입출력, 자원/Vitals, 이동 writer, 네트워크 transport는 변경하지 않는다.

## 1. 구현 흐름

```text
Mass 포식자 Grid / Actor ThreatSource → 시야·Visibility 차폐 → 개인 Sight
서버 Gameplay Noise Event → 거리·차폐 감쇠 → 개인 Hearing
                   ↓
       마지막 감지 위치·신뢰도·불확실도 → 시간 기반 Memory
                   ↓ 새로 감지한 위험만
              기존 Herd Alarm → Social Response → Shelter Request
```

개인 기억은 Herd 입력으로 다시 방송하지 않는다. 구성원이 전달받은 경보는 개인의 직접 감지와
별도 필드에 보관하며, 청각은 소음 **발생 당시** 위치를 사용한다. 숨은 Actor의 현재 위치를 조회하지 않는다.
실제 Shelter 이동 소비자와 PPO가 새 인지 정보를 사용하는 연결은 후속 통합이다.

2026-10-05에는 아래 §7의 읽기 전용 인지 API와 §8의 행동 보정 진단을 추가했다.
감각/기억/경보를 제공하는 구현과 PPO가 그 정보를 실제 사용하는 통합은 구분한다.

## 2. 데이터 소유권과 연결 API

| 데이터 | 소유자 / 연결 지점 |
| --- | --- |
| 서버 소음 이벤트 | `UEcoNoiseSubsystem::ReportNoise(Position, Loudness, MaxRange, ThreatStrength, Instigator, Tag)` |
| 소음 발생 Actor 연결 | Blueprint에 `Eco Noise Emitter` 컴포넌트 추가, `EmitNoise` 호출 |
| 종별 감각 설정 | `Eco Social Trait.SocialConfig.Senses` |
| 개체별 감각 능력 | `FEcoSensoryProfileFragment` / Trait의 `SensoryProfile` 초기값 |
| 직접 감지 및 기억 | `FEcoSensoryStateFragment` |
| 무리에게 전달받은 정보 | 같은 Fragment의 `SharedThreatPosition`, `SharedAlarmStrength` (현재 수신 snapshot) |
| 다른 계층에 제공할 인지 정보 | `FEcoSensoryStateFragment::MakeReadSnapshot` → `FEcoSensoryReadSnapshot` |
| 행동 보정 진단 | `FEcoSocialBehaviorFragment.ActionAudit` / `eco.Social.ActionAudit 1` |
| 환경 입력 | 개체 `FEcoRegionFragment.CurrentRegionId` → World 환경, 실행 중 권위 Clock의 DayPhase |

프로필은 Vision/Hearing/Memory multiplier를 개체별로 보관한다. 출생 특성 생성은 Ecology/Mass 담당이며,
감각 계층은 그 결과를 소비할 수 있는 연결 지점만 제공한다. 기존 Shared PPO 모델을 개체마다 수정하지 않는다.
Region이 없으면 강우 입력은 0, 실행 중 Clock이 없으면 지역의 authored DayPhase를 사용한다.
Night/Rain multiplier의 기본값은 1이다. 팀 규칙이 확정되지 않은 상태에서 임의로 밤/비 페널티를 켜지 않는다.

## 3. 현재 감지 규칙

- Server/Standalone, GameThread, 기존 Detection Processor에서 0.2초마다 처리한다.
- 시각은 기존 거리·XY FOV·Simple/Complex Visibility LOS를 유지한다. 개인 감지는 Herd 가입 전에도 가능하다.
- 시각 거리 = Species ViewDistance × 개인 Vision × Night multiplier × 강우 보간 multiplier. 최종 상한 10000cm.
- 청각 거리 = min(설정 HearingRange × 개인 Hearing × 강우 보간 multiplier, 이벤트 MaxRange), 상한 10000cm.
- 청각 신뢰도 = HearingConfidence × Loudness × (1 - 거리/청각거리). 벽이 가리면 OccludedHearingMultiplier를 추가 곱한다.
- 청각은 FOV 밖에서도 가능하다. 소음 발생 위치는 추정의 중심이며 기본 불확실 반경 200cm를 함께 제공한다.
- 기본 청각 신뢰도 상한 0.65, 차폐 배율 0.35, 최소 유효 신뢰도 0.05다. 모두 튜닝용 게임 규칙이다.
- 위험 강도와 감지 신뢰도는 별도 값이다. `ThreatStrength=0`인 배경 소음은 이 첫 버전의 위협/경보 후보에서 제외한다.
- 시각 후보가 있으면 개인 기억에 시각을 기록한다. 시각이 없으면 기존 기억보다 위험 근거가 강한 새 청각 후보를 기록한다.
- 기존 기억의 위치는 고정되고 신뢰도는 선형 감소, 불확실 반경은 시간에 따라 증가한다. 기본 기억 수명 6초 × 개인 Memory 배율.
- 재발견은 위치·시간·신뢰도를 갱신한다. 만료/잘못된 설정/HP가 0인 관찰자는 개인 기억을 초기화한다.
- 소음은 0.6초간 보관하며 최대 128개다. 초과는 반환 ID 0으로 거절하고, 이미 수락한 이벤트는 삭제하지 않는다.
- 개체별 Noise ID watermark로 같은 이벤트를 한 번만 평가한다. 뒤늦게 범위 안으로 들어와 이미 평가한 소음을 다시 듣지 않는다.
- 한 번의 소음은 한 감지 패스에만 새 Herd 입력을 만든다. 이후에는 기존 Alarm 감쇠와 개인 Memory가 각각 유지된다.
- 개인 기억/무리 경보의 위치·강도를 PPO 입력으로 합치는 계약은 RL 담당과 별도로 정한다. V1 7개 입력에 몰래 추가하지 않는다.

기존 Social 템플릿에 새 감각 Fragment가 없으면 시각/Alarm 기존 경로가 유지되고 개인 청각·인지 기록은 사용하지 않는다.
Social Trait와 JYU Herd Harness는 새 Fragment를 생성한다. Client Trait에는 논리 감각 Fragment를 추가하지 않는다.
PendingDeath/ClientProxy/Alive 필터는 기존 Detection과 동일하다. 죽음 이후 state를 소비하는 새 코드는 이 자격 조건도 확인해야 한다.

## 4. SA와 소음 이벤트

SA가 Sound Attenuation을 의미한다면 **오디오 연출용**으로 사용한다.

- `NoiseSound`, `AudioAttenuation`에 Sound/SA 에셋을 지정하고 `PlayNoiseSound`를 해당 로컬 표현 경로에서 호출한다.
- `EmitNoise`는 서버 AI 이벤트만 만든다. 오디오 재생을 자동 호출하지 않으며 audio device/파일이 없어도 동작한다.
- `PlayNoiseSound`는 오디오만 재생하고 AI 이벤트/RPC를 만들지 않는다. Dedicated Server에서는 재생하지 않는다.
- 발소리 AnimNotify/이동 gameplay 사건 하나에서 **서버 EmitNoise**와 **로컬 오디오 재생**을 각각 연결한다.
- Client 소리를 Server가 들었다고 가정하지 않는다. Client→Server action 검증과 소리 복제는 기존 네트워킹 담당 경로에서 연결한다.
- 컴포넌트의 `EmitMovementNoise`를 켜면 서버 속도 기준 소음 대역을 사용할 수 있다. 기본 속도 250cm/s 이상, 0.4초 간격이다.
  이 대역은 소리 없는 테스트용이며, 정확한 발소리 시점은 AnimNotify/게임플레이에서 제공한다. 두 경로를 동시에 켜서 중복 발생시키지 않는다.
- 환경용 ATT_Environment_Loud 에셋은 저장소에 있으나 발소리 SA로 재사용하거나 수정하지 않았다. 실제 발소리/SA 선정과 청취 검증은 대기다.

AI 감지 반경과 플레이어가 듣는 SA 범위는 서로 다른 규칙이다. Audio mute/NullRHI에서도 AI 테스트 결과가 유지되어야 한다.
현재 벽 청각 감쇠는 Visibility line 기반 근사다. 음향 회절·재질별 전달·실내 전파를 구현했다고 주장하지 않는다.

## 5. JYU 수동 확인

1. 새 빌드 완료 후 에디터를 재시작한다. 기존 수정 중인 JYU 맵은 코드 작업에서 변경하지 않는다.
2. Herd Harness를 사용하고 Alarm Harness의 연속 주입은 끈다. 시각 테스트 소스에는 `Eco Threat Source`를 붙인다.
3. 소음 발생 Pawn/Actor에는 `Eco Noise Emitter`를 추가한다. 우선 명시적 `EmitNoise(1, 2000, 1, Run)` 호출로 확인한다.
4. `eco.Senses.Debug 1`: 녹색 Sight, 노란색 Hearing, 청록색 Memory. 선의 끝은 마지막 감지 위치이며 구는 불확실 반경이다.
5. 개체 앞에서 발견 → Visibility 벽 뒤로 이동 → 마지막 위치/감소하는 Confidence 확인 → 새 소음 → 재발견을 확인한다.
6. 소음 하나가 memory 시간을 계속 갱신하지 않는지, 소리 발생 Actor를 이동해도 이전 소음 위치가 움직이지 않는지 확인한다.
7. 실제 Region/Clock 연동 테스트는 Region Fragment를 가진 production 개체로 진행한다. 기본 JYU Harness에는 Region이 없으므로 강우를 자동 적용했다고 해석하지 않는다.
8. 실제 은신 이동/Occupied와 Client 표현은 기존 이동·네트워킹 연결 후 별도로 검증한다.

## 6. 검증 및 다음 작업

2026-10-05 인지 인계 계약 / 보정 진단 검증:

- 직접 `UnrealBuildTool.exe AdaptiveEcosystemEditor Win64 Development`: **Succeeded** (124.02초).
  테스트 float 비교 허용 오차 수정 후 직접 재빌드도 **Succeeded** (48.84초).
- 최종 `/Engine/Maps/Entry`, `-nosound -NullRHI` Social 자동화: **17 성공 / 0 실패 / 테스트 경고 0 / 미실행 0**.
  Senses 7 + ActionAudit 1 + 기존 Threat 4 + ShelterLifecycle 5.
- 새 테스트 3개: 읽기 시각 만료·개인/공유 정보 분리·원본 불변, 경보 입력 나이·무리 slot 재사용,
  실제 Response의 모든 상태에서 Raw 보존·V1 수식 호환·반복 적용 시 비누적.
- 첫 실행은 16 성공 / 1 실패였다. 새 수식 비교 테스트의 기본 float 허용 오차가 너무 작아 실패했으며,
  명시적 `1e-6` 허용 오차와 상태별 오차 로그를 추가했다. 최종 최대 오차 `5.96046448e-8`이며 런타임 수식은 바꾸지 않았다.
- `eco.Social.ActionAudit 1`을 켠 자동화 로그에서 Calm의 Raw=Effective 및 Panic의 보정 차이를 확인했다.
- 로컬 산출물: `Saved/Logs/SocialReadContractBuild.log`, `SocialReadContractRebuild.log`,
  `SocialReadContractVerified.log`, `Saved/Automation/SocialReadContractVerified/index.json`.
- 수정 문서의 로컬 링크와 diff 확인. PPO/Core/Mass 소스 변경 없음.
  이 자동화는 실제 production EntityConfig·PPO 인지 소비·JYU 이동/도착·오디오 청취·Client PIE 검증을 대신하지 않는다.

2026-10-02 실행 결과:

- 직접 `UnrealBuildTool.exe AdaptiveEcosystemEditor Win64 Development`: **Succeeded** (120.19초).
  최초 sandbox 실행은 UBT 사용자 캐시 접근 거절로 컴파일 전 종료됐으며, 필요한 권한으로 재실행했다.
  재실행 전에 관련 프로세스 종료 상태와 Windows Application Event Log를 확인했다. 캐시/엔진/파일 삭제나 빌드 경로 변경은 하지 않았다.
- `/Engine/Maps/Entry`, `-nosound -NullRHI` UnrealEditor-Cmd 자동화: **14 성공 / 0 실패 / 테스트 경고 0**.
  Senses 5 + 기존 Threat 4 + ShelterLifecycle 5. 실행은 빌드 완료 후 시작하고 종료까지 기다렸다.
- 새 Senses 테스트: sight loss/reacquisition, hearing occlusion/once-only, 환경·개체 프로필,
  전달 정보 분리, 소음 수명·컴포넌트·queue bound. 기존 Social Threat/Lifecycle 회귀도 통과했다.
- [테스트 보고서](../../Saved/Automation/SocialSensory/index.json), [테스트 로그](../../Saved/Logs/SocialSensoryAutomation.log),
  [빌드 로그](../../Saved/Logs/EcoSensoryBuild.log). Saved 산출물은 로컬 파일이고 Git에 포함하지 않는다.
- UBT의 기존 StructUtils/MassEntityHandle deprecated 경고는 남아 있다. 테스트 경고 0과 빌드 경고를 구분한다.
- JYU 시각 PIE, 실제 Sound/SA 청취, production EntityConfig/Client, 전체 실제 이동은 **아직 검증하지 않았다**.

`EcoSensoryScan` CPU trace scope로 감지 패스 비용을 측정할 수 있다. 아직 100/300/1000 개체의 성능 수치를 측정하지 않았다.

다음 작업은 RL 인지 입력 계약, 실제 소음 gameplay/오디오 에셋 연결, 날씨·개체 특성 튜닝, 감지 trace budget/주기 분산과
대표 시연이다. 후각, 감각별 다중 타깃 장기 저장, 경로 이동, 식생 성장 계산, 출생 특성 생성은 이번 코드 범위 밖이다.

## 7. 인지 정보 인계 계약 — 2026-10-05 구현

Source: [인지 타입/API](../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoSensoryTypes.h),
[읽기 시각 감쇠/검증](../../Source/AdaptiveEcosystem/AI/Social/Senses/EcoSensoryTypes.cpp),
[경보 입력 시각 관리](../../Source/AdaptiveEcosystem/AI/Social/Herd/EcoHerdSubsystem.cpp),
[수신 처리](../../Source/AdaptiveEcosystem/AI/Social/Alarm/EcoAlarmProcessors.cpp).

`FEcoSensoryReadSnapshot::SchemaVersion=1`은 **Social 인지 데이터 버전**이다.
PPO PolicySchemaVersion이나 관측 차원을 변경하지 않는다. 새 Processor/Observation Fragment도 추가하지 않는다.

```cpp
// 다른 담당자의 미래 소비자 예시. 현재 Policy/Steering에 적용된 코드는 아니다.
// Authority / Alive / HP / PendingDeath / ClientProxy 자격을 먼저 확인한다.
// CurrentHerdId는 현재 회원 정보를 검증한 persistent ID; 미가입/유효하지 않으면 0.
const FEcoSensoryReadSnapshot Knowledge = Sense.MakeReadSnapshot(
    WorldGameTime, SocialConfig.Senses, SensoryProfile, CurrentHerdId);
```

| 필드 | 의미 / 소비 조건 |
| --- | --- |
| `bValid`, `WorldTime` | 읽기 인자의 유효성 및 이 값이 계산된 World 게임 시간. 생존/이동 자격을 뜻하지 않음 |
| `bHasPersonalThreat` | 유효한 개인 위협 단서가 있음. 현재는 가장 우선한 단서 하나이며 포식자 수가 아님 |
| `PersonalSource`, `LastDirectSense` | 지금 제공되는 Sight/Hearing/Memory와 마지막 직접 감지 종류 |
| `LastKnownPosition` | 마지막 직접 감지 위치, cm 월드 좌표. 숨은 Actor의 현재 위치를 조회하지 않음 |
| `Confidence`, `ThreatStrength` | 감지 확실성과 위험 강도. 서로 다른 값이며 한 값을 두 번 곱해 감쇠하지 않음 |
| `UncertaintyRadiusCm`, `PersonalAgeSeconds` | 위치 불확실 반경과 마지막 감지 후 경과 시간 |
| `bFreshDirectEvidence` | 같은 World 시각에 새 Sight/Hearing을 기록한 경우만 true. 다음 프레임의 기억을 새 방송 근거로 사용하지 않음 |
| `bHasSharedThreat` | 현재 persistent Herd와 일치하고 아직 만료되지 않은 무리 보고가 있음 |
| `SharedReportedPosition`, `SharedAlarmStrength` | 무리 보고 위치 및 감쇠된 경보 강도. 직접 시각 정보나 보정된 Confidence로 해석하지 않음 |
| `SourcePersistentHerdId` | 보고를 수신한 무리. 개별 발신자 ID나 원래 감지 종류는 현재 제공하지 않음 |
| `SharedEvidenceAgeSeconds`, `SharedReceptionAgeSeconds` | 선택된 경보 입력의 나이와 개체 수신 후 나이. 재수신은 입력의 나이를 갱신하지 않음 |

개인 정보는 **복사본**을 읽기 시각까지 감쇠한다. 감지 패스가 늦어져도 이미 만료된 단서가 노출되지 않는다.
감지 상태 원본, 정책 출력, Transform/Velocity는 이 함수에서 쓰지 않는다.
같은 감지 시각 이후에는 개인 단서를 Memory로 제공하고 마지막 감지 종류를 별도로 보존한다.
보관한 반환값을 미래 프레임에 계속 재사용하지 말고 각 판단 시각에 다시 읽는다.
현재 Herd ID 조회는 GameThread 또는 담당 계층이 제공한 불변 membership snapshot에서 검증한다.
worker에서 가변 Herd Subsystem을 직접 조회/수정하도록 실행 플래그만 바꾸지 않는다.

무리 입력 시각은 `FEcoHerdRuntimeData.LastThreatEvidenceTime`으로 추적한다.
manual 입력은 실제 선택된 주입 시각, detected 입력은 새 감지 패스가 선택한 시각이다.
물리적 소음 발생 시각/개별 발신자 감지 이력까지 복원한 값은 아니다.
감쇠/수신/더 약해서 무시된 manual 입력은 이 시각을 갱신하지 않는다.
기존 입력 선택·강도 감쇠 수식은 유지한다.

`SharedInformationMaxAge` 기본값은 6초이며 개인 Memory multiplier와 독립적인 수신 정보 수명이다.
입력 시각부터 이 시간이 지나면 읽기 결과에서 제외한다. 반복 수신으로 만료를 연장하지 않는다.
무리 이탈 또는 runtime slot 재사용 시 현재 persistent ID가 다르면 과거 보고를 제외한다.
잘못된 설정은 `bValid=false`, 만료/미인지 단서는 해당 `bHas...=false`와 기본값으로 제공한다.
false를 위험이 없다는 확정 정보로 해석하지 않는다.

현재 shared 보고에는 신뢰도/불확실 반경/개별 발신자/원래 감지 종류가 없다.
따라서 임의로 `Confidence=1`, `Uncertainty=0`, `Sight`로 변환하지 않는다.
청각 위치도 정확한 타깃 좌표로 쓰지 않고 불확실 반경을 함께 다루는 방식은 RL/Steering 담당이 계약으로 정한다.

## 8. PPO와 Social 보정 중복 진단 — 2026-10-05 구현

Source: [ActionAudit 타입](../../Source/AdaptiveEcosystem/AI/Social/EcoSocialActionAudit.h),
[진단 계산](../../Source/AdaptiveEcosystem/AI/Social/EcoSocialActionAudit.cpp),
[Social Response](../../Source/AdaptiveEcosystem/AI/Social/Alarm/EcoAlarmProcessors.cpp).

Social Response는 기존 V1 수식으로 `ModulatedAction`을 만든 뒤 `ActionAudit`에 같은 시각의 원본 Action,
적용 상태 및 네 항목의 최대 절대 차이를 기록한다. Policy Fragment는 ReadOnly다.
Audit은 최종 이동 명령/학습 보상/두 번째 정책 출력이 아니며 실제 이동 소비 여부를 보증하지 않는다.

`eco.Social.ActionAudit 1`을 켜면 Server/Standalone에서 5 게임 초마다 요약을 기록한다.
`Matched / Adjusted / Invalid`, 표본 `Agent / State / Raw / Effective / MaxDelta`를 확인한다.
Action 순서는 `[Forage, Cohesion, FleeDist, Cover]`다. Identity가 없는 대역은 Agent=0으로 표시한다.
매 프레임 로그는 하지 않고, 진단을 꺼도 현재 적용된 보정 비교값은 Fragment에서 읽을 수 있다.
진단 throttle과 World 시각 접근을 직렬화하기 위해 Response는 GameThread 실행을 명시한다.
Alarm/Response는 Server/Standalone 플래그와 Client World guard를 명시한다.

현재 Panic 강제 은신 요구와 경보별 보정은 기존 활성 계약이므로 유지한다.
향후 위험 반응을 PPO가 학습할 때의 보정 유지/축소/제거는 **RL과 Social의 공동 계약 변경**이다.
진단 로그를 근거로 변경 범위를 정하고, 유지하는 보정·제약은 Python 학습 환경에서도 재현한다.

## 9. 담당별 다음 연결 작업과 완료 기준

권장 목표 흐름은 `World → 개인 인지/무리 정보 → PPO → Social 협력/예약 → 단일 이동 실행 → 결과`다.
이 구조는 목표이며 현재 Policy가 새 API를 소비하거나 이동이 연결됐다는 뜻은 아니다.

| 담당 | 다음 작업 | 완료 기준 |
| --- | --- | --- |
| 조연우 | 인지 read API, 경보 시각/출처, Raw/Effective 진단, 예약 결과 처리 제공 | 본 문서의 Source와 자동화 검증, 기존 계약 보존 |
| 권신혁 / RL | 인지 데이터의 V2 관측 의미·정규화·결측 처리와 행동 결정권 확정, Python/C++ 연결 | 같은 입력의 파리티, 학습 환경에 감각/기억/Social 조건 재현 |
| 이동 담당 | 인지 정보와 일치하는 위협 방향, EffectiveAction/예약 목적지 소비, 단일 writer | 실제 이동/도착/실패/양보 Feedback 및 중복 적분 없음 |
| 장원준 / Ecology·Mass | 최종 EntityConfig, 생존/자원/이주 실행과 이동 담당 연결 | 자원 소비·상태 변화가 실제 생태계로 되돌아가는 검증 |
| 송해찬 / World·레벨 | 실제 Region 환경, 차폐 충돌과 은신처 배치 | 감각/은신 차폐 확인, 지형 도달 가능성은 이동 담당 검증 |
| 표현·네트워크 담당 | 서버 gameplay 소음과 로컬 SA/애니메이션 연결 | 권위 이벤트 중복 없음, Client 논리 재계산 없음 |

**연결 전에 해결할 현재 공백:** 기존 `UEcoPerceptionProcessor`는 별도로 Grid 위치/FOV로 포식자 기하를 만들고
`UEcoPolicyProcessor`와 `UEcoSteeringProcessor`가 이를 소비한다.
새 LOS/환경/청각/기억은 이 경로를 아직 차단하지 않는다.
관측만 제한하고 Steering이 실제 숨은 포식자 위치를 사용하면 정보 누출이 남으므로 두 소비자를 함께 검토한다.
현재 단일 위협 단서를 V1 predator_count로 바꾸거나 heard/shared를 직접 관측한 개체 수로 세지 않는다.

연결 순서는 인지/행동 계약 확정 → RL 관측과 Steering 위협 정보 일치 → 기존 이동 writer 하나의 Request 소비 →
다음 Lifecycle 패스 Feedback → 실제 자원/Vitals 결과 검증이다.
인지 소비자는 Detection/Alarm 이후, Social Response는 Policy 이후, 이동은 Lifecycle 이후에 배치하는 것이 목표다.
현재 Policy에는 Alarm 이후 prerequisite가 없다. 연결 담당자가 Mass 그룹 의존성까지 확인해 명시한다.
Feedback을 같은 pass에 되돌리려는 순환 의존성을 만들지 않는다.

팀 통합 시나리오:

- 시야 상실 후 포식자가 이동해도 개인 기억 위치 고정, 나이/불확실도 증가, 이후 만료.
- 같은 무리 보고를 계속 받아도 원 입력 나이가 증가하고, 개인 Sight로 바뀌거나 재방송되지 않음.
- 무리 이탈/slot 재사용/죽음/Client에서는 이전 보고와 이동 요청을 소비하지 않음.
- 동일한 인지 상태로 PPO 원본·Social 보정·최종 이동 결과를 비교하고 이중 보정 여부 확인.
- 은신처 만석/경로 실패/행동 중단/이주 시 예약 해제와 다음 판단이 일치.
- 밤/비/식생 조건이 인지와 자원에 영향을 주는 경로를 각각 확인하고 중복 감쇠를 피함.
- 같은 환경에서 정책 비교군/입력 ablation과 실제 결과를 비교. 이것은 기존 Social 단위 테스트와 별도 검증.

Shared Model은 유지하며 개체 특성을 모델이 행동 차이로 반영해야 한다면 관측 계약에 포함한다.
멈춤/걷기/달리기·음수·이주 선택과 행동 전환 hysteresis는 V2/RL·이동 담당의 후속 계약이다.
이번 작업에서 새로운 행동 선택기·속도 작성자·PPO schema·Bootstrap 가드 변경은 추가하지 않았다.
