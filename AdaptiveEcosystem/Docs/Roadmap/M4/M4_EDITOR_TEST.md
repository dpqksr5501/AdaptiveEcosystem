# M4.0~M4.2 수동 테스트

자동화 테스트는 작성·실행하지 않는다. 기존 M3 Box 테스트 레벨을 에디터에서 복제해 M4 전용 레벨로 저장한다. 기존 작업 레벨/에셋을 덮어쓰지 않는다. A/B Region과 Bootstrap의 동일 EntityConfig, 이동 설정을 유지한다. 실행한 테스트 결과는 M4_VALIDATION_REPORT.md에 기록한다.

1. **설정 확인:** 복제한 EntityConfig의 Eco Network Agent에서 M4 실험 프리셋을 적용하고 저장한다. Project Settings의 연결 예산도 확인한다. PIE를 재시작한다. Medium 거리를 High 이하로 또는 interval을 0으로 설정했을 때 오류와 스폰 거부를 확인하고 즉시 원복한다. 틀린 Bubble/Replicator 및 Actor>관련 개체 예산도 같은 방식으로 확인한다.
2. **Standalone:** 초기 Population/먹이/이주가 기존대로 동작하는지 확인한다. 콘솔 `eco.M4.Dump details`로 Authority 수, Alive 수, DuplicateIDs=0, InvalidIDs=0을 기록한다. Mass Debugger에서 Authority에는 reset Fragment가 있고 ClientPresentation Fragment가 없는지 확인한다.
3. **Listen Host + 1 Client:** 두 창에서 `eco.M4.Dump details`를 실행한다. Output Log의 World/NetMode로 로그를 구분한다. 관련 범위의 StableAgentId/Species/Region과 TemplateID가 대응하는지 확인한다. Client에는 ClientProxy + ClientPresentation이 있고 Authority/Vitals/Travel/Feeding이 없어야 한다. 이동 시 Client Sequence가 증가하고 서버 Bubble 표본 시각이 증가하는지 확인한다.
4. **이탈/재진입:** Client를 Off 거리 밖으로 이동하고 돌아온다. Client 프록시/Bubble 수는 줄었다가 회복하며 서버 Population과 StableAgentId는 이탈 때문에 바뀌지 않아야 한다. 새 Add의 Previous=Current 초기화를 확인한다. 범위 밖에서도 서버 이주는 계속돼야 한다.
5. **두 Client / Late Join:** Client를 서로 다른 지역과 겹치는 관심 영역에 둔다. Host의 각 Bubble 수와 Client별 프록시 수를 따로 기록한다. 실행 중 새 Client 접속, 접속 종료, PIE 재시작을 확인한다. 정상 로딩 후 PendingAdds=0이어야 한다. 템플릿을 늦게 로드하는 별도 스트리밍 테스트에서는 대기 중 변경이 최신 상태로 반영되고, 대기 중 Remove된 entry가 뒤늦게 생성되지 않아야 한다.
6. **상태/Reset:** 아래 M4.2의 SetVitals/Teleport 명령을 Host에서 실행한다. Client Current의 health/energy는 0~1이며 양자화 오차 약 0.002 이내여야 한다. Client reset revision과 Previous=Current를 확인한다. 플레이어 공격·피식은 M4.7~8에서 검증한다.
7. **baseline 캡처:** 같은 레벨/설정에서 Unreal Insights CPU 및 Networking Insights trace를 수집한다. N/C, 이동 비율/분포, 후보 검색·LOD·직렬화 비용, 연결별 bytes/s, Client CPU/GPU와 p50/p95/p99, 메모리를 기록한다. Actor/인스턴스 수는 Mass Debugger/Insights로 별도 측정한다. dump는 수동 snapshot이며 성능 구간 동안 반복 실행하지 않는다.

M4.2의 일반 위치 간격 gate는 구현했다. 보간·연결 전체 예산 집행은 후속 단계다. M4.0 baseline trace와 PIE 검증이 끝나기 전에는 M4.0/M4.1 전체 완료를 선언하지 않는다. M4.2도 아래 간격 실측·중요 변경·Remove·두 Client 확인을 완료 게이트로 남긴다.

## M4.2 준비

1. 에디터를 재시작하여 빌드된 모듈을 로드한다. 기존 Box 레벨과 EntityConfig를 복제한 테스트 사본에서 작업한다. 각 Bootstrap의 EntityConfig를 **같은 사본**으로 지정한다. Host/Client는 같은 Config GUID와 코드를 사용해야 한다.
2. Config → Eco Network Agent → `Apply M4 Experimental Preset` 적용·저장. Params에서 High/Medium/Low 간격 0.1/0.2/0.5초, 거리 시작 0/2000/8000cm, Off 시작 20000cm를 확인한다. 이 단계는 Actor 수 제한을 적용하지 않는다.
3. Play 옵션 → Number of Players=2, Net Mode=`Play As Listen Server`, 창 분리(`New Editor Window`). 이 설정은 Host+1 Client다. Host+2 Client는 Number of Players=3으로 실행한다. 서로 다른 컴퓨터라면 모든 실행 환경에 같은 빌드/Config를 적용한다.
4. **순수 이동 간격 측정 동안만:** Project Settings → Adaptive Ecosystem → Survival의 BaseMetabolism=0, TravelMetabolism=0, FoodEnergyGain=0, Feeding의 bEnabled=false로 설정하고 PIE를 다시 시작한다. Survival.bEnabled는 true로 유지한다. 필요하면 Spawn Waves도 끄고 소수의 Box로 시작한다. HP/Energy 우선 갱신이 섞이는 것을 줄이기 위한 실험 설정이다. 실제 생태 테스트 전에는 저장해 둔 원래 값을 복원하고 PIE를 재시작한다.
5. Host 창의 콘솔에서 `eco.M4.Dump details` 실행. 대상 ID, Position, Region, 각 Bubble의 Sequence/LOD/Interval을 찾는다. 아래 명령의 `<ID>`는 실제 양수 StableAgentId로 바꾼다. 콘솔은 선택한 PIE World에서 실행되므로 Output Log의 World/NetMode도 확인한다.

| 명령 | 사용 |
| --- | --- |
| `eco.M4.Dump` / `eco.M4.Dump details` | 현재 수/ID와 서버 Bubble별 LOD·누적 counters; details는 위치와 표본 시각도 표시 |
| `eco.M4.TraceSamples 1` | 실제 dirty 표본, Add, Remove 로그 |
| `eco.M4.TraceSamples 2` | 정지 상태를 포함한 Transform 검사 로그 |
| `eco.M4.TraceSamples 0` | 로그 종료; 성능 캡처 전 실행 |
| `eco.M4.SetVitals <ID> 0.75 0.5` | 살아있는 서버 개체 HP/Energy 비율 변경 |
| `eco.M4.Teleport <ID> <X> <Y> <Z>` | 서버 위치(cm) 변경 + reset revision 증가 |

SetVitals/Teleport는 non-Shipping 수동 디버그 명령이며 Client에서는 거부된다. 죽은 개체를 되살리지 않는다. Region/Population을 직접 변경하지 않으며 Teleport의 Region은 기존 이주 commit 규칙으로만 바뀐다. 같은 ID가 여러 개면 편집을 거부한다. TraceSamples는 프로세스 전체 설정이므로 단일 프로세스 PIE의 여러 창에 함께 적용된다.

## M4.2 확인 순서와 기대 결과

### 1. 정지 개체 — 검사 주기와 불필요 전송

Client 플레이어를 대상에서 약 10m, 50m, 120m에 각각 두고 Host에서 `eco.M4.TraceSamples 2`를 켠다. 거리는 화면에 보이는 Host 카메라가 아닌 해당 **연결의 Viewer** 기준이다. 히스테리시스 경계에서 충분히 떨어진 위치를 사용한다. 개수 제한도 등급에 영향을 줄 수 있으므로 최종 등급은 서버 dump의 LOD로 확인한다.

각 위치에서 5~10초 관찰한다. 같은 World/Bubble/ID의 `Reason=Interval`에서 CheckDelta가 High 약 0.1초, Medium 약 0.2초, Low 약 0.5초 이상이어야 한다. interval 도달 이후 첫 replication pass의 프레임 오차는 허용한다. 정지·상태 불변 구간에서는 Dirty=0이고 Sequence/SampleTime은 그대로다. dump의 Checks/Gated는 늘고 Dirty는 그대로여야 한다. High 승격의 첫 검사와 Add/Visual/Reset은 일반 간격 비교에서 제외한다.

### 2. 이동 개체 — 실제 dirty 표본 간격

기존 A/B Region 이주를 사용한다. 예를 들어 Host에서 `Debug.Starvation Forest_A`를 실행하여 Food=0을 만들고, Forest_B에 Food와 공간이 있는지 확인한다. 필요하면 `Debug.FoodSupply Forest_B 100`으로 자원을 공급한다. migration/pressure/최소 거주 시간 설정에 따라 출발을 기다린다. 대상 State=Traveling과 Position 변화가 실제로 있는지 dump로 확인한다. 이 구간의 체력/에너지는 준비 단계 설정으로 고정한다.

`eco.M4.TraceSamples 1`로 같은 Bubble/ID/LOD의 연속 `Reason=Interval` SampleTime 차이를 측정한다. 충분한 속도로 tolerance를 넘는 이동에서는 0.1/0.2/0.5초 근처의 간격이어야 한다. 아주 느린 이동이나 정지에서는 dirty 간격이 더 길 수 있다. LOD 전환·Region commit·Visual/Reset을 포함한 구간으로 일반 주기 실패를 판정하지 않는다.

### 3. 두 Client의 독립 시계 / High 승격

Host+2 Client에서 같은 대상에 Client A는 약 10m, B는 약 120m 떨어져 둔다. Host Bubble별 ID와 최종 LOD가 High/Low인지 확인하고 10초간 표본을 기록한다. 해당 ID의 일반 위치 표본은 A 약 0.1초, B 약 0.5초여야 한다. B의 LastCheck가 A의 마지막 검사 때마다 갱신되면 실패다.

B를 대상 가까이 옮겨 High로 승격시킨다. 첫 High callback의 `HighPromotions`가 증가하고 간격을 기다리지 않고 검사해야 한다. 변한 위치가 있으면 즉시 dirty, 정지라면 TraceSamples=2에서 Dirty=0의 검사만 기록할 수 있다. 많은 개체를 동시에 승격시킬 때 HighPromotions/Dirty 증가와 trace 비용을 기록한다. 승격/Add 폭주 제한은 M4.6의 후속 범위다.

### 4. Low 간격 도중 중요한 상태 / 작은 reset

대상을 Low에 두고, 필요하면 테스트 사본의 Low UpdateInterval을 5초로 늘려 PIE를 재시작한다. Host에서 `eco.M4.SetVitals <ID> 0.75 0.5`를 실행한다. 다음 replication pass에서 `Reason=Visual` 표본과 VisualRev 증가가 나와야 하며 5초 간격을 기다리면 실패다. Client의 Health/Energy도 네트워크 전송 후 0.75/0.5 근처여야 한다.

Host dump의 현재 Position을 사용하여 `eco.M4.Teleport <ID> <X+0.5cm> <Y> <Z>`를 실행한다. 좌표는 수식을 계산한 숫자로 입력한다. 기존과 **동일 좌표**로 실행해도 된다. 일반 tolerance보다 작은/없는 변위라도 ResetRev와 Sequence가 늘고 `Reason=Reset`이 기록되어야 한다. Client의 reset revision 증가와 수신 Fragment Previous=Current를 확인한다. 엔진 PositionYaw payload의 FVector 위치를 수신 Transform과 비교한다.

Region 우선 변경은 실제 이주 도착에서 확인한다. 목적지 도착 시 서버 CurrentRegionId가 바뀌고 다음 replication pass에 `IdentityOrRegion`이 나와야 한다. Client Region도 최신 commit 값이어야 한다. 조작 명령으로 Region만 바꿔 생태 장부와 어긋나게 만들지 않는다.

### 5. 지속 Dead 상태 / 파괴 Remove

Survival.bEnabled=true, DeadRetentionSeconds를 기본 2초 또는 긴 관찰 시간으로 둔다. Low interval을 5초로 설정한 세션에서 살아있는 대상에 `eco.M4.SetVitals <ID> 0 0.5`를 실행한다. HP=0은 기존 Survival/Lifecycle이 다음 생태 경계에서 ExternalDamage 사망으로 commit한다. 그 이후 Alive Tag에서 읽은 Dead 상태가 `Visual` 우선 표본으로 생성되고 Population은 한 번 감소해야 한다. 잔류 기한 후 `Remove`와 Removes 증가를 확인한다. 플레이어 포식에 의한 PredationHistory 증가는 이 명령의 기대 결과가 아니다.

서버 dirty와 실제 Client 수신은 따로 기록한다. packet이 병합·유실되면 Dead와 Remove 사이의 연출을 반드시 관찰한다는 보장은 아직 없다. 이 단계에서 검증하는 것은 interval gate가 Dead/파괴 Remove를 막지 않는지다.

### 6. Off 이탈 / 재진입 / Late Join

이동 중 Client를 Off 경계와 히스테리시스 밖(예: 250m 이상)으로 옮긴다. Low interval이 남아 있어도 서버의 relevance 변경 pass에서 `Remove`가 기록되어야 한다. Client proxy 제거는 네트워크 도착 뒤 확인한다. 서버 Population/Alive/StableAgentId는 relevance 이탈 때문에 변하면 안 된다.

돌아오면 같은 논리 ID에 새 Add가 생성되고 Sequence=1, Client Previous=Current로 초기화한다. 원거리에서 계속 진행된 이주가 최신 snapshot에 포함되어야 한다. 새 Client 접속과 접속 종료도 확인하고 정상 로딩 후 PendingAdds=0, InvalidIDs=0, DuplicateIDs=0인지 기록한다.

## 결과 기록

[검증 기록](M4_VALIDATION_REPORT.md)에 사용한 레벨/Config, 실제 Params/실험 설정, N/C, World/Bubble/ID, LOD별 SampleTime 차이, Checks/Gated/Dirty/HighPromotions의 시작·종료 차이, 중요 변경과 Remove 관찰 결과를 적는다. 로그는 프로젝트 `Saved/Logs`에서 보관한다. 실험 후 Params·대사·식사·Spawn 설정을 복원하고 TraceSamples=0으로 종료한다.
