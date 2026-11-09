# 생태계 플레이 흐름 수정 — 2026-10-29

[실제 점검](JYU_PLAYFLOW_AUDIT_20261029.md) 후 사용자의 전체 수정 요청으로 기존 `LV_JYU_Ecosystem`을 개선했다. 현재 작업 브랜치는 `codex/social-shelter-handoff`, 시작 HEAD는 `ecb898e`다. **작업 트리 변경이며 main 반영/push를 뜻하지 않는다.**

## 범위와 책임

새 세계 규칙은 **life rules version 2**다. 기존 `bEnableEcosystemLife` opt-in을 사용한다. 기존 V1/v3 모델·관측 차원·raw request·mask와 `SocialControl=0`을 보존한다. 생태 상태/자원/인구는 권위 서버가 소유하며 Native Step이 계속 유일한 위치·대사·섭식·포획 writer다. 새 전역 관리자나 별도 movement backend를 추가하지 않았다.

| 항목 | 실제 수정 | 분류 |
|---|---|---|
| 단독 무리 | life 세계는 1마리 Persistent Herd도 기존 계획/Travel/M4 인계 경로를 사용한다. 새 무리를 임의 생성하지 않는다. 지속적 부족 대기/경로 부재 사유를 남긴다. | 원인 수정 |
| 출발 시점 | 기존 부족 판단 외에 먹이 비율50% 미만·무리 절반 이상 energy40% 미만이면 life의 조기 부족으로 판단한다. 기존 지속 시간·목적지 가치·지식/TTL·도착/실패 계약을 거친다. | 장거리 이동의 구조적 보완 |
| 경계 정체 | 이동 직전에 outward 성분을 안쪽/접선 방향으로 보정한다. Native 경계 clamp는 유지한다. 이주·stranded에는 이 stage 경계 보정을 적용하지 않는다. | 구조적 이동 보완 |
| 개체 겹침 | 안정 ID 기반의 비영(非零) 분리 방향, 근거리 공간 bucket, C1 이동 구간의 swept 접촉 검사를 사용한다. 접촉 반경은 기존 지형 writer의 `30cm × body scale`과 같다. 기존 겹침은 더 깊어지지 않는 이탈만 허용한다. | 원인 수정/접촉 제약 확장 |
| 이주 교착 | 앞이 막히면 자기 진행 방향 기준 왼쪽으로 통과한다. authored 통로 폭에 따라 최대4개 목표 차선으로 분산한다. 실제 한 스텝의 지형/충돌 검사는 그대로 거친다. | 구조적 통행 보완 |
| 먹이 접근 | 배고프고 안전한 GRAZE 개체는 실제 먹이 .012 이상인 작은 패치에서 정지 섭식한다. 원래 .06 정지 기준은 작은 패치 전체 양보다 클 수 있었다. 가까운 실제 보이는 먹이 후보를 찾고 기존 단일 실행 경로로 접근한다. | 기존 정책에 대한 명시적 world-rule adapter |
| 식생 표시 | life의 900셀 세계는 먹이 셀 전체를 포함한다(상한1024). 셀당5개 풀 덩어리를 실제 지면 normal에 맞춰 표시하고 기존 food/moisture/stress custom data로 축소·숨김·회복한다. 기존 맵은256 표본·1덩어리를 유지한다. | 표현 개선 |
| 새 식생 영역 | 좋은 수분/온도·빛·낮은 스트레스·검증된 지면과 인접한 충분한 식생이 있어야 빈 셀의 서식 용량을 확장한다. 30 simulation seconds마다 최대64셀, 이웃 용량의 절반·최대.5이며 같은 주기에 연쇄 전파하지 않는다. | 새 세계 규칙 확장 |
| 낮밤 | 기존 날씨 presenter가 권위/수신 시계에서 Native와 같은 박명을 계산한다. 배치된 태양·달·하늘광을 사용하고 종료 시 원래 값을 복원한다. 비 연출 OFF와 낮밤 조명은 독립적이다. | 표현 연결의 원인 수정 |
| Highland | 실제 지면을 조사한 Highland↔Barren/Forest 통로와 인접 관계를 owned 맵에 추가했다. 각 경로의 물리 통과를 양방향·최대 지원 반경40cm로 검증했다. | 월드 authoring 보완 |

## 판단·이동 계약

`EcoLifeLocomotion.h`는 위치/에너지를 적분하지 않는 순수 의도/접촉 함수다. `EcoPolicyV3IntegratedProcessors.cpp`의 기존 life control hook과 terrain movement hook이 소비한다. 정책 raw request·관측을 덮어쓰지 않는다.

먹이 후보는 현재 시야 거리/FOV와 식생 차폐 안에서 제한한다. 실제 지면 통행 및 static LOS를 통과한 후보만 채택하며 한 번의 스캔에서 물리 후보 검사는 최대4회, 스캔은1 simulation second 간격이다. 원격 지역의 live food 정답을 개체에게 제공하지 않는다. 지역 origin이 달라지면 로컬 food cell cache를 무효화한다. 접촉은 현재 몸의 물리 제약이며 지각/기억에 위협 좌표를 추가하지 않는다.

제어 우선순위는 기존 실제 위험/은신/이주와 Social의 유효 예약을 보존한다. 수면·Freeze·도착 은신 상태를 접촉 의도로 강제 이동시키지 않는다. 대신 움직이는 개체가 점유된 공간으로 새로 진입하는 것을 막는다. 이주 일시 정지와 stranded는 계속 기존 규칙을 따른다. 공간 bucket은 파생 scratch이고 swept 검사는 실제 현재 몸 위치를 읽는다. ORCA/전역 경로 탐색/임의 종 backend 지원을 뜻하지 않는다.

`life.local_forage_cell`, `life.motion_reason`, `life.motion_reason_name`, `life.contact_blocked_steps`, `life.world_rules_version`으로 정책 요청과 추가 보정을 구분한다. `Blocked`/`PathBlocked`는 여전히 무진행 진단이며 지형 충돌 확정이 아니다.

## 식생·장부·표현 계약

확장 계획은 기존 food/soil에서 계산하되, **M4 `AdjustSpatialFoodHabitat`의 capacity-only 거래가 승인된 뒤** native 용량에 적용한다. 확장 그 자체는 food를 생성하지 않는다. 새로운 먹이는 기존 Native `Regrow`의 `VegetationGrown`에만 기록된다. `Cap0`와 은신처의 용량 배수를 함께 보존하여 은신처 제거/재등록이 새 식생 용량을 되돌리거나 무상 food를 만들지 않는다.

지면 미확인·급경사·장애물과 겹치는 곳·기온0도 미만·부적절한 수분/빛/스트레스에서는 확장하지 않는다. 재생을0으로 중단한 가뭄 fixture도 그대로 유지한다. 따라서 모든 빈 땅이 언제나 녹색으로 변하는 규칙은 아니다. 확장 cadence/셀 수는 같은 빌드 checkpoint에 저장한다.

표시 개수는 새 잔고가 아니다. ground normal을 전송하고 셀 내부의5개 위치를 같은 지면 평면에 맞춘다. 이는 작은 지형 곡률의 모든 tuft를 별도로 trace한 것은 아니다. instance 수가 같으면 batch transform 갱신을 사용한다. 지면 준비/식생 종류/고갈로 수가 바뀔 때는 bounded rebuild를 한다. Client는 DTO만 소비하며 native 논리를 생성하지 않는다.

진단의 `capacity`, `ledger_capacity`, `colonized_cells`, `last_expansion_step`으로 용량 변화와 실제 biomass 증가를 구분한다. 큰 grid는1024셀 상한에 따라 표본화하므로 임의 규모의 전 셀 표현을 보장하지 않는다.

## owned 맵과 재현

`Tools/Editor/extend_jyu_ecosystem_playflow.py`는 기존 owned 맵만 갱신한다. A* 지면 조사와 **실제 runtime과 공통인 `ConstrainGroundStep`**을 사용하며, 새 actor label에 다른 소유자가 있으면 거절한다. 전체 경로가 유효해야 맵을 저장한다. 원본 팀 맵과 다른 JYU 맵을 재생성하지 않는다.

- `JYU_Ecosystem_Highland_Barren_GroundRoute`:57점.
- `JYU_Ecosystem_Highland_Forest_GroundRoute`:75점, 약740m.
- 지면 probe672개, 통과한 양방향 edge1119개. 최종 실제 이동은 별도 실행으로 검사한다.
- 현재 explicit authored report/30초 갱신·90초 TTL을 사용한다. 새 통로를 통해 목적지 정보를 알게 하는 authoring이며 무제한 원격 인지나 multi-hop gossip이 아니다.

Unreal 실행 전 기존 UBT/Editor/LiveCoding/dotnet/MSBuild/ShaderCompileWorker가 모두 정상 종료됐는지 확인한다. 검증 중인 프로세스를 중단하지 않는다. 원시 실행은 `Saved/PlayflowRelease_20261029/`, 멀티는 `Saved/PlayflowNetwork_20261029/`, 변경 전/중간 진단은 별도 `Playflow*` 폴더에 보존한다. 이전10-23 결과를 덮어쓰지 않았다.

## 검증과 남은 범위

최종 상세 수치는 [공유 evidence](../Architecture/Evidence/PlayflowFix_20261029.json)를 따른다. 첫 수정 중 접촉을 과도하게 제한해 이주 교착이 생긴 것을 반복 시험에서 발견했고, 실제 body 반경·측면 통과·차선 분산을 적용해 재검증했다. 초기 어두운 화면도 달빛을 보완한 최종 화면과 구분한다.

| 최종 확인 | 결과 |
|---|---|
| 직접 UBT | `Milestone_Final_20261029_222835.log` Succeeded. 이후 runtime C++ 변경 없음. |
| 전체 자동화 | 228개 =227 Success+기존 예상 warning1, failed/notRun0. 기존 Native OFF/golden과 새 접촉·조명·확장 수지 회귀 포함. |
| 가뭄600 simulation seconds | Barren 초기48 stable ID 전원 Forest 실제 인계, Barren 기아0·BlockedRouteReturn0. 다른 Highland의 기아10건과 자연 출생6건을 포함해 최종140 living. |
| 실제 단독 개체 fixture | `-EcoIntegratedV3 -EcoV3DeerPerRegion=1`, 지역별1·전체3마리. Barren의1마리도 이주,600초 최종3 living·사망0. `SoloDrought`라는 앞선 실행은 명시적 통합 override 없이 authored48이 적용된 반복 시험이며 이 단독 증거로 사용하지 않는다. |
| 무가뭄·늑대0·seed23 600초 | 수정 전 Highland 기아21건 → 최종6건. 최종144 living/출생6. Highland→Barren12·Forest3명의 실제 인계. 동일 seed의 UE 월드 전체 궤적 동일성을 주장하지 않는다. |
| 무가뭄·늑대0·seed47 600초 | Highland48명 전원 실제 이주. 도착지/이동 비용에 따른 Barren14·Forest4 기아, 최종126 living. 기아0이나 전 지역 균형의 증거로 쓰지 않는다. |
| 자연1800 simulation seconds | 초기156→최종146 living, 자연 출생80, 포식60·기아30. 지역별 Forest64/Barren64/Highland18. 초기 cold/도착지 경쟁 문제의 장기 균형 완료를 뜻하지 않는다. |
| 일반 PIE125 wall seconds | 관찰 표본의 최소 초식 중심 간격 약63.19cm. body scale 기반 물리 반경 중첩 표본0. 모든 mesh/뿔/애니메이션의 시각적 교차0 보장은 아니다. Forest565/Barren540/Highland353 셀 표현, 각2810/2660/1485 instance. |
| 식생 장부 | 전체 headless 실행에서 food/grown/consumed/environment loss 장부 차이0. capacity 차이는 부동소수점 합산 수준인 최대약1.42e-13. PIE125초까지 Forest84/Barren106 셀의 실제 서식 용량 확장. Highland의 저온 확장0은 규칙대로다. |
| 플레이어55초×3 | 무해 접근 Curious8표본·familiarity최대.631, 추격 Retreat11표본·실제900cm/s, rear attack HP최소40·Unknown fear최대.567. 모두 FINISHED·정상 종료. |
| Dedicated160초/Client2 동시+late join | 세 지역 near-field 수신 누락0, 각 client 논리 개체0·local migration subsystem0·Native Step0. 동시 접속 관찰28.28초. 자연 출생 ID157의 late join/크기 수신 통과. |
| Client 관찰 frame | 3600표본 p95 A약3.04ms/B약6.78ms. 해당960×540/D3D11 관찰 구간의 dt이며 모든 해상도/하드웨어/전체 서버 성능 보장이 아니다. |
| 저장→새 프로세스 | 별도 슬롯 `PlayflowRelease23`,144개체 exact 복원. 추가 `LoadFull` 실행에서 실제2700셀 전체 food/용량/수분/스트레스/서식지·확장 cadence/셀 수·native step·seed/RNG·지역 origin을 저장 시점과 exact 비교했다. 잘못된 checksum/version/누락 파일과 live rollback을 거절하고 이전 상태 보존. |

확인 범위는 위 실행에 한정한다. simulation seconds와 wall seconds, Native CPU와 전체 rendered frame을 혼용하지 않는다. 새 cook/package와 streaming 제거/재진입 전체 lifecycle,500/1000개체는 이번에 다시 실행하지 않았다. 중간 구현의 교착/과도한 어둠과 그때의 테스트 수치는 최종 성공 근거로 쓰지 않는다. 최종 낮/밤 화면은 로컬 `Saved/PlayflowRelease_20261029/VegetationPIE_0.png`, `VegetationPIE_1.png`다.

수정은 모든 지역의 영구 균형/모든 seed에서의 기아0을 보장하지 않는다. 추운 서식지의 낮은 생산력, 이동 중 비용과 도착지 경쟁에 따른 사망은 실제 기록에 남는다. 이번 수정은 무상 에너지/food/teleport를 추가하지 않았다. 종별 계절 생태·임의 종·NavMesh·분산 서버·500/1000개체 acceptance는 별도다.

기존 V1/v3 가중치와 leaf soil 공식은 유지했다. **새 life-v2 전체 세계의 Python mirror/궤적 parity와 재학습은 완료되지 않았다.** snapshot은 `training_ready=false`, `learning_world_schema=ecosystem-life-v2`다. checkpoint는 기존처럼 정확히 같은 runtime image hash의 재시작용이며, 이전 빌드 저장 파일을 자동 변환하지 않는다. 사용자 기존 슬롯은 보존하고 이번 시험은 별도 `PlayflowRelease23`을 사용한다.
