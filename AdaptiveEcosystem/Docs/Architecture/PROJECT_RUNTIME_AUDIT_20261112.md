# 프로젝트 전체 실행·구조 감사

`codex/social-shelter-handoff`, `051ef5f7`와 현재 로컬 소스를 기준으로 플레이어, 월드, 생태·학습, 표현·오디오, 네트워크·저장, 제작·배포 경로를 나눠 점검했다. 실행 검증은 기존 UE 5.8 바이너리로 했다. 바이너리의 테스트 결과와 현재 소스에서 확인한 조건을 구분한다. 팀 기본 맵과 소유 복사 맵에서 확인한 결과는 각각 해당 맵 범위에 적용된다.

## 이번에 실행한 검사

후속에는 원본 통합 레벨 기준선과 R7e·자연 출생을 적용한 두 복사본을 포함해 4배속 60분 실행 다섯 건을 완료했다. 네 Native 실행은 각 27,000 결정 스텝의 실제 사슴 섭취를 기록했고 행동 마스크·인구 장부 오류가 없었다. 복사본의 결과는 기존 바이너리와 해당 맵에 한정한다. [시드별 비교와 재현](FAUNA_POPULATION_BALANCE.md#integration_jwj-복사본의-r7e자연-출생과-다종-공존) · [로컬 증거와 복원](../Team/LOCAL_TEST_EVIDENCE.md)

| 검사 | 결과와 범위 |
| --- | --- |
| Unreal 전체 자동화 | `AdaptiveEcosystem` 299개. 성공 297, 경고 포함 성공 2, 실패·미실행 0. Policy 209, Creature 29, Social 20, Life 13, Vegetation 8, Combat·Review 각 6, NaturalHabitat·Playflow 각 3, CommonGameplay·Network 각 1이다. 경고는 없는 테스트 저장 파일 조회와 GAS GameplayCue 검색 경로가 없어 `/Game` 전체를 탐색하는 설정이다. |
| 설정으로 선택되는 기본 맵 | 맵 인자를 생략한 Standalone에서 `Integration_JwJ`가 열렸다. 실제 플레이어 Pawn, 통합 런타임 Ready, 권위 개체 19, Barren·Forest·Highland 세 지역 요약, 24번째 생태 스텝을 확인했다. 24초 NullRHI 기동 시험이다. |
| 여덟 종 시각 표현 | D3D11 PIE의 다종 소유 맵에서 경사 보행, 회전, 급반전, 정지, 달리기, 섭식, 이착륙, 사망·안착 등 12개 상황, 2,320프레임의 합성 표현 입력을 측정했다. 180° 반전에서 모든 리그의 최대 프레임당 yaw 변화는 6.29°였다. 25cm/s 초과 경사 보행 표본의 최저 발 마커 간격은 표범 +0.50cm, 물소 +0.91cm, 쥐 −1.54cm였다. 까마귀 비행 마지막 표본에서 IK와 유효 발 접점은 0이었다. 접촉 마커 측정은 메시 관통·발 미끄러짐의 전수 판정과 별개다. Rat 스켈레탈 메시의 material usage 누락 경고가 남았다. |
| 날씨·빗소리 | `LV_JYU_Ecosystem` D3D11 PIE에서 저장된 맵의 강우 0.65를 기다린 뒤 연출을 OFF→ON→OFF로 전환했다. 72개 표본에서 강우 입력은 유지되고 수분 평균은 0.490→0.599로 증가했다. 확인 구간에서 비 파티클과 AudioComponent 재생은 연출 옵션과 일치했다. 실제 청취 믹스와 Shipping 날씨는 별도다. |
| 월드 저장·프로세스 재시작 | 다종 맵에서 150초에 저장하고 별도 Standalone에서 복원했다. 생존 ID 95개, 여덟 종 인구·출생·사망 집계, 자원 단계 170이 일치했고 복원 실행은 단계 369까지 진행했다. 식생 공개 요약은 57.338→57.837로 달랐다. 이 기록기는 저장 직전 권위 공간 재고를 직접 비교하지 않으므로 원인이 발행 시차인지 자원 차이인지는 미확정이다. |
| 전용 서버 근접 사냥 | `1102_Integration_JWJ`에서 두 실제 클라이언트 접속을 확인했다. 기존 테스트가 UE Python의 `get_pawn()` 호출에서 중단했다. 로컬 복사본에서 컨트롤러 API와 서버 틱 연결을 조정한 실행은 표현을 받았으나 권위 사냥 사망과 결과 수신을 충족하지 못했다. 재시도 런처 중복으로 같은 서버에 4개 클라이언트가 붙고 종료 시 World 핸들이 무효화돼 이 실행은 전투 회귀 판정에서 제외한다. |
| 전용 서버 소총 | 기존 소총 스크립트의 별도 전용 서버·Client A/B. 서버는 권위 피해 7건과 사망 1건을 기록했다. A는 테스트가 기대한 소유자 피해 결과를 관측하지 못했다. B는 숨긴 상태의 발사 입력 자체가 발생하지 않아 가려진 표현의 피해 거절을 입증하지 못했다. 서버 통과와 두 클라이언트 실패를 구분했으며 RPC 전달과 테스트 이벤트 수집 중 어느 쪽이 원인인지는 미확정이다. |
| 렌더링 Client 체력바 | D3D11 클라이언트 두 개와 전용 서버에서 대상 체력이 100→70→40으로 감소했다. A는 1차 변화, B는 2차 변화와 소유자 결과 이벤트를 관측했다. A는 2차 구간 대상 표본이 한 개뿐이었고 B는 1차 구간 변화를 확인하지 못해 두 클라이언트의 동시 표시에 대한 검증이 실패했다. 기록된 표본에서 위젯과 수신 체력 불일치는 보고되지 않았다. 대상의 관심 범위 이탈·초기 표시 시각과 실제 복제 누락을 추가로 분리해야 한다. |
| 학습 산출물·Python | R7e 내장 데이터와 LF 정규화된 JSON 바이트가 일치했다. float32 누산으로 26개 fixture의 행동과 logits를 대조했고 최대 오차는 약 4.77e-6이었다. 번들 NumPy로 Python 월드의 날씨 경계 6개와 감각·속도 배율 6개도 통과했다. 로컬 Python에 pytest·gymnasium·torch가 없어 학습 전체 테스트는 실행하지 않았다. |
| 검증 도구 | 사냥·네트워크·패키지·발소리·날씨·서식지 검증 PowerShell과 Python 파일의 AST를 읽어 구문을 검사했다. 스크립트 구문 통과는 Unreal Python 바인딩 또는 실제 재현 성공과 별개다. |

원시 결과는 `Saved/ProjectAudit_20261112/Automation/index.json`, `DefaultMap.json`, `WeatherControls.json`, `CombatRetry/`, `Saved/RifleValidation/Network/`, `Saved/HealthBarValidation/Network/`, `Saved/FaunaAudit/ProjectAudit_20261112_MotionMetrics.json`, `Saved/FaunaAudit/ProjectAudit_20261112_Checkpoint_*.json`, `Saved/Logs/ProjectAudit_20261112_*.log`에 있다. 기본 맵과 테스트 맵의 역할은 [프로젝트 공통 맥락](../PROJECT_CONTEXT.md)을 따른다.

## 우선 확인하거나 수정할 항목

| 영역 | 현재 확인한 동작 | 다음 재현의 통과 기준 |
| --- | --- | --- |
| 전투 관심 범위 | 플레이어에게 제안한 대상 ID 집합에서 하나만 바뀌어도 이미 보이던 대상의 공격 준비 상태까지 초기화한다. 활성 전투 코디네이터가 둘이면 제안을 비운다. 새 확인이 오기 전 기존 대상의 공격이 거부될 수 있다. 소스 조건 확인. [전투 관심 범위](../../Source/AdaptiveEcosystem/Player/EcoCombatRelevanceComponent.cpp#L19) | A를 계속 보면서 B가 반복 진입·이탈할 때 A의 타격과 표시가 유지된다. 맵 작성 검증에서 중복 소유자를 찾아낸다. |
| 지역 언로드·날씨 | 환경 어댑터는 대상 지역 하나가 없으면 날씨 배치 전체를 건너뛴다. 강우로 자원을 계산하는 지역의 Actor가 빠지면 자원 경계가 실패하고 통합 런타임 Ready가 해제될 수 있다. 실제 기본 맵의 지역 언로드는 이번에 유도하지 않았다. [날씨 배치](../../Source/AdaptiveEcosystem/World/EcoRegionEnvironmentAdapter.cpp#L31) · [자원 경계](../../Source/AdaptiveEcosystem/Ecology/EcologyEnvironmentSimulation.cpp#L22) · [실행 실패](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp#L87) | 두 지역 중 하나를 내렸다 다시 올려도 남은 지역의 시계·식생·상호작용이 계속된다. 누락 원인과 복구가 로그에 남는다. |
| 이주와 막힘 | 왕복이 모두 실패해 지역 밖에 남은 개체는 `bStranded`가 켜진다. 기존 Native 경로는 이 개체를 정지시키고 섭식을 막으며, 같은 무리의 다음 이주 계획도 거부한다. 이 조건에서 길을 다시 열었을 때 자동 복구하는 경로를 찾지 못했다. [이주 상태](../../Source/AdaptiveEcosystem/Mass/EcoHerdMigration.cpp#L178) · [계획 거부](../../Source/AdaptiveEcosystem/Mass/EcoHerdMigration.cpp#L251) · [Native 정지](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp#L62) | 왕복 실패 뒤 한 개체의 고립을 해소하거나 격리하고, 길이 열리면 해당 무리의 이후 이동을 다시 평가한다. |
| 세션과 복구 | 세션 타임아웃은 표시와 데드라인을 갱신하지만 공급자 완료 콜백이 오지 않는 분기에서 작업 상태를 종료하지 않는다. UI는 Busy 동안 나가기까지 비활성화한다. 공급자 콜백 누락은 새 엔진 실행에서 주입하지 않았다. [타임아웃](../../Source/AdaptiveEcosystem/Network/Session/EcoSessionSubsystem.cpp#L397) · [메뉴 제어](../../Source/AdaptiveEcosystem/Network/Session/EcoSessionMenuWidget.cpp#L124) | Create·Join·Leave 콜백을 각각 지연·누락해도 취소나 재시도가 가능하고 늦게 온 콜백이 새 세션 상태를 덮지 않는다. |
| 보간·늦은 접속 | 복제 보간은 각 패킷의 수신 시간으로 오프셋을 바꾼다. 기존 수식을 100ms 간격·100cm 표본에 적용하고 지연을 80→20ms로 줄이면 예시 좌표가 140→200cm로 튄다. 정지 개체·안착 사체의 복제 yaw는 표현 Actor 초기 바인딩에 전달되지 않아 늦게 본 Client나 재사용 Actor에 다른 방향이 남을 수 있다. 전자는 수식 재현, 후자는 소스 확인이다. [보간 식](../../Source/AdaptiveEcosystem/Mass/EcoMassPresentationFragments.h#L32) · [표현 초기화](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePresentation.cpp#L95) · [정지 회전](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.cpp#L168) | 지터·재진입·늦은 접속에서 이동 궤적과 정지·사망 방향이 권위 표본과 일관된다. |
| 저장 경계 | 포맷 7의 저장은 본문 16MiB까지 허용하고 16바이트 헤더를 추가한다. 로드는 헤더 포함 전체 파일에 16MiB 상한을 적용한다. 그 경계 16바이트의 본문은 저장할 수 있어도 읽을 수 없다. 빌드 이미지 해시가 바뀐 복원도 명시적으로 거부한다. [저장과 로드 상한](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoEcosystemCheckpoint.cpp#L265) | 상한 전후에서 저장 허용과 로드 허용이 일치하고, 빌드 교체와 전투 중 저장의 지원 범위를 각각 확인한다. |
| 낮은 FPS와 생태 시간 | 규칙 종의 이동은 최신 프레임에서 한 번 처리하며 프레임당 0.1초를 넘는 이동량을 버린다. 자원 경계는 이전 경계까지 따라잡으며 갱신된 위치를 읽을 수 있다. 동일한 지연 구간에서 이동과 유지 대사의 시간 기준이 달라질 수 있다. 이번 감사에서 hitch를 주입하지 않았다. [이동 순서](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp#L51) · [자원 따라잡기](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp#L85) · [이동 시간 상한](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp#L374) | 10·20·60 FPS와 짧은 hitch에서 이동거리, 접촉 시각, 대사·섭식의 시간 차이를 분리한다. |

## 영역별 추가 점검

| 영역 | 발견과 확인 범위 |
| --- | --- |
| 조작·카메라 | 기본 보행 경로는 왼쪽 Ctrl·Shift를 매 프레임 읽는다. 해당 설정의 Pawn에서 재매핑·패드의 보행 모드 설정이 덮일 수 있다. 무기를 바꾼 뒤 이전 조준 블렌드가 0이 되기 전에 조준하면 이전 무기의 카메라 프로필이 남을 수 있다. 실제 기본 Pawn의 패드·재매핑 입력은 미실행이다. [보행 입력](../../Source/AdaptiveEcosystem/Creature/Player/EcoPlayerEcologyComponent.cpp#L75) · [조준 프로필](../../Source/AdaptiveEcosystem/Player/EcoAimComponent.cpp#L22) |
| HUD·읽기 쉬운 상태 | C++ 공통 체력바는 112×18 화면 위젯과 뿌리 기준 185cm 높이를 사용한다. 유효 체력이 남아 있으면 사망 표현에도 0%를 표시한다. 작은 동물·성장 단계·밀집 구역에서 위젯이 올바른 개체 위에 붙고 가려짐을 줄이는지 별도 화면 검증이 필요하다. [공통 위젯 설정](../../Source/AdaptiveEcosystem/UI/EcoHealthBarComponent.cpp#L5) · [표현 상태 연결](../../Source/AdaptiveEcosystem/Creature/Representation/EcoCreatureRepresentationActor.cpp#L227) |
| 플레이어의 월드 영향 | Native 피격은 경험·목격·무리·지역 위험에 전달된다. 규칙 종 피격은 살아 있는 피해자에 단기 위협을 주는 별도 경로다. C++ 총기 발사 경로에 빗나간 발사 자체를 권위 소리로 발행하는 호출이 없다. Blueprint 연결과 양쪽 backend의 반복 사냥 피드백은 추가 재현이 필요하다. [피격 영향](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePlayerOutcomes.cpp#L62) · [발사](../../Source/AdaptiveEcosystem/Player/EcoWeaponFireComponent.cpp#L61) |
| 지역 저작·배포 날씨 | 지역이 겹치면 통합 런타임은 정렬된 ID의 첫 지역을 고르고 플레이어 발소리는 Actor 순서의 첫 지역을 고른다. Shipping은 작성 날씨의 Native 인계·감시 일부가 제외되며 식생은 지역 강수·온도를 계속 읽는다. 같은 비가 식생과 청각에 다르게 반영될 수 있는 구성이다. [지역 선택](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureWorldProviders.cpp#L12) · [발소리 지역](../../Source/AdaptiveEcosystem/Creature/Player/EcoPlayerEcologyComponent.cpp#L92) · [날씨 감시](../../Source/AdaptiveEcosystem/AI/Policy/EcoV3EnvWatch.cpp#L402) · [식생 입력](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp#L1223) |
| 자원 처리 실패 | Native 스텝과 부수 상태 갱신 뒤 권위 식생 영수증을 확정한다. 지역의 영수증 하나가 거절되면 전체 Native 진행을 멈추는 경로가 있고, 앞서 실행한 지역까지 되감는 처리는 확인되지 않았다. 영수증 거절을 주입하지 않았다. [Native Step과 영수증](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp#L1281) · [실패 시 중단](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp#L5095) |
| 동물·양육·경쟁 | 규칙 육식 유체의 부모 에너지 이전은 같은 지역과 650cm 거리만 검사해 벽을 사이에 둔 전달이 가능하다. 공용 사체는 Native 늑대가 먼저, 늑대끼리는 ID 순서대로 자리 사용을 시도한다. 발견 순서·실제 접근이 같은 경우에도 backend와 ID가 경쟁 결과에 영향을 줄 수 있다. 종별 행동과 허기 감사 결과는 별도 보고서에 있다. [부모 에너지 이전](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.cpp#L449) · [사체 접근 순서](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureCarcass.cpp#L79) · [여덟 종 감사](ECOSYSTEM_BEHAVIOR_AUDIT_20261112.md) |
| 표현·오디오·에셋 | Notify 모드에서는 거리 발소리 대체 경로를 건너뛴다. 클립·LOD에서 Notify가 누락되면 서버 거리 기반 소리 증거는 남아도 플레이어가 듣는 소리는 끊길 수 있다. 이번 D3D11 실행의 음원은 비활성화했다. 임포트한 쥐 메시의 material usage 경고는 새로 확인했다. [접촉 발소리](../../Source/AdaptiveEcosystem/Creature/Audio/EcoFootstepAudioComponent.cpp#L45) · [서버 소리 증거](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp#L459) |
| 네트워크 규모 | 영구 미등록 템플릿은 5초 뒤 로그를 남긴 뒤에도 매 틱 버블을 다시 탐색한다. 일부 표현 경로에서 후보 전체를 정렬하고, 규칙 종의 감각은 소유 개체를 반복 순회한다. 코드상 비용이며 실제 대규모 동접·대역폭·프레임 예산은 측정하지 않았다. [템플릿 대기](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp#L143) · [표현 후보](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreaturePresentation.cpp#L30) · [감각 스캔](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp#L456) |
| 패키지·검증 배치 | 기본 게임과 명시적 cook은 `Integration_JwJ`, 사냥 검증은 `1102_Integration_JWJ`, 날씨와 여덟 종 표현은 별도 소유 맵이다. 기본 맵 Standalone 기동을 새로 확인했다. Shipping·cooked dedicated·다종 맵 조합은 실행하지 않았다. [기본 맵 설정](../../Config/DefaultEngine.ini) · [cook 설정](../../Config/DefaultGame.ini) · [사냥 네트워크 재현](../../Tools/Editor/run_player_hunting_network.ps1) |

## 후속 회귀 범위

전투 대상이 바뀌는 순간, 이주 중 길이 닫혔다 다시 열리는 순간, 한 지역이 내려가는 순간, 네트워크 완료 콜백이 사라지는 순간을 먼저 재현한다. 각 장면에서 플레이어 입력·보이는 상태·서버 판정·자원 장부를 같은 시각에 비교한다. 보상·접근성 UI·패드, 장시간 반복 사냥, 패키지와 업데이트 간 복원은 현재 실행 결과에 포함되지 않는다.

## 후속 소스 수정

| 영역 | 변경과 확인 범위 |
| --- | --- |
| 전투 관심 범위 | 같은 코디네이터와 월드 epoch에서 계속 제안되는 대상의 확인을 보존한다. 빠진 대상, 새 대상, epoch가 바뀐 대상은 다시 확인해야 한다. 기존 자동화에 다른 대상의 진입·이탈과 돌아온 대상의 재확인을 추가했다. |
| 근접 애니메이션 알림 | 수정한 테스트가 실제 Enhanced Input으로 서버 근접 피해 30과 공격자 결과 수신을 재현했다. 첫 타격 시 `EcoAttackNotifies.cpp`에서 콜백이 순회 중인 컴포넌트 집합을 변경해 Unreal ensure가 발생했다. 발행 전에 컴포넌트 목록을 복사하고 호출 직전 유효성을 확인하도록 고쳤다. 기존 바이너리의 전체 처치·사망 요약 검증은 실패했다. |
| 세션 | 타임아웃에서 로컬 완료 콜백을 해제한다. 검색은 공급자 취소 응답과 독립적으로 종료하며 생성·참가·이동 실패는 기존 정리 경로를 거친다. 정리 자체가 시간 초과되면 오류 상태로 돌아와 사용자가 다시 나갈 수 있다. 실제 공급자의 지연·늦은 완료·재시도는 별도다. |
| 날씨·스트리밍 | 사라진 지역 Actor의 마지막 완료 날씨를 자원 경계에 사용한다. 자동 날씨 갱신은 현재 로드된 지역에 계속 적용하며, Blueprint의 명시적 배치 호출은 전체 대상을 확인한 뒤 적용한다. 맵에서 쓰기 담당 날씨 어댑터가 둘인 경우와 다른 지역 계약 위반의 처리 방식은 후속 확인 사항이다. |
| 무리 이주 | 고립 개체를 새 계획의 참가자에서 제외해 나머지 개체의 출발 조건을 다시 평가한다. 고립 개체 자체는 기존 위치 보호를 유지하며 경로 재개방 뒤 복귀는 후속이다. |
| 표현·성능 | 최초 표시, 위치 불연속에서 정지한 개체, 안착 사체는 권위 yaw를 사용한다. 기존 움직임 방향 보간을 사용하고, 로컬 전투 관찰자 조회를 표현 갱신마다 한 번으로 줄였다. 풀에서 재사용한 사체의 방향을 기존 자동화에 추가했다. |
| 저장·상호작용 | 저장과 읽기에서 같은 본문 용량 상한을 쓰고 읽기 파일 상한에 헤더를 포함한다. 규칙 육식 유체의 부모 영양 전달은 벽이 가로막으면 건너뛴다. 이전 무기에서 조준이 풀리는 중 다시 조준하면 현재 무기 프로필로 보간한다. |

새 빌드 없이 작업했다. 추가한 C++ 회귀 항목은 다음 빌드에서 실행할 수 있으며, 위 299개 결과는 수정 이전 바이너리의 기준 결과다.

## 환경과 입력 변화에 대한 후속 점검

| 입력 또는 상황 | 확인한 구조와 수정 |
| --- | --- |
| 주변 단서가 바뀌거나 길이 막힘 | 규칙 종이 기억을 조사하는 동안 따라가던 목격·청각 단서가 막혀도 이전 코드는 냄새 기록만 지웠다. 이제 도착한 단서는 끝내고, 길이 막히면 실제 선택한 단서만 지운다. 따라갈 만한 목격이나 청각 단서가 있으면 새 냄새를 고르지 않고, 유효한 냄새 목표는 도착·차단·만료까지 이어간다. [감각에서 이동까지](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp) |
| 사체·패치 앞의 좁은 장애물 | 첫 직진 실패로 목표를 버리기 전에 측면 이동을 최대 네 번 검사한다. 기존 체형·경사·충돌·수심·지역 제한을 통과하고 목표와 가까워지는 발걸음만 채택한다. 모든 후보가 막히면 기존 목표 해제와 재시도 대기를 적용한다. [지상 이동](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp) |
| 종별 시야 설정 | 주간 위협 탐지 범위는 이제 생활 규칙 비트와 무관하게 종 프로필을 읽는다. 시야 반각과 가까운 거리의 방향 예외도 종 프로필에서 검증한다. 기존 값 650cm·90°·280cm는 기본값이고 야간 배율은 기존 옵션으로 적용한다. 새 에셋 값은 이번 변경에서 조정하지 않았다. [종 데이터](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h) · [탐지와 행동](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp) |
| 재매핑과 패드의 보행 입력 | 명시적인 `SetGait` 입력이 들어오면 해당 Pawn에서 고정 Ctrl/Shift의 보행 fallback을 양보한다. 걷기·은밀 이동·달리기 속도는 기존 기본값을 유지하며 캐릭터 설정에서 조정할 수 있다. [플레이어 보행](../../Source/AdaptiveEcosystem/Creature/Player/EcoPlayerEcologyComponent.cpp) |
| 네트워크 도착 간격 변화 | Client는 이동 표본 최대 네 개를 보존하며 새 패킷으로 보간 시각을 바로 교체하지 않는다. 표시 전용 업데이트는 이동 기록을 건드리지 않고 위치 불연속은 즉시 기록을 초기화한다. 100ms 이동 표본·80→20ms 수신 지연의 산술 검증은 수신 순간 60cm→2cm를 재현했다. 엔진 회귀에는 동일 조건, 표시 전용 업데이트, 순간이동을 추가했다. [보간 버퍼](../../Source/AdaptiveEcosystem/Mass/EcoMassPresentationFragments.h) · [Unreal 회귀](../../Source/AdaptiveEcosystem/Creature/Representation/Tests/EcoCreatureRepresentationTests.cpp) |

행동별 다음 검증은 [여덟 종 점검](ECOSYSTEM_BEHAVIOR_AUDIT_20261112.md)을 따른다. 원래 프로젝트 감사의 출시 환경, 전투·HUD 동시 표시, 콜백 누락, 대규모 접속, 장기 개체군은 앞 절의 미해결 조건을 적용한다. 이 후속에서는 소스와 산술만 검사했다. 새 Unreal 빌드나 쿠킹을 실행하지 않았다.

## 후속 구현과 동일 입력 비교

| 영역 | 변경 | 검증 범위 |
| --- | --- | --- |
| 사슴·Native 세계 | 다종 LIFE 단계에서 일반 채식, 경계 채식, 이동 휴식 등 모든 제어 훅 뒤에 포만 판정을 적용한다. 에너지 90% 이상이어도 비축이 20% 미만이면 허용 경로를 유지한다. PPO 요청이나 모델을 바꾸지 않았고 기본 65% 식사 재개 게이트를 강제 활성화하지 않았다. | 같은 R7e 시드 20017의 연속 입력 8,088개씩을 재판정했다. 90% 이상 실제 섭취 기록은 마스크 0에서 1,254개, 마스크 1에서 85개였다. 해당 기록은 모두 비축이 충분해 새 판정에 걸린다. 기록을 새 규칙으로 한 스텝씩 재판정한 결과이며 새 궤적이나 출생률을 예측하지 않는다. [기준 자료](ECOSYSTEM_BEHAVIOR_AUDIT_20261112.md#사슴의-포만-상태-섭취) |
| 규칙 종·자원·이주 | 명시적으로 공유되는 인접 통로에서 낮은 영양의 성체가 예상 식사량과 이동 시간으로 목적지를 비교한다. 식생·먹을 수 있는 사체·체급과 성숙 조건을 통과한 사냥 후보를 종의 능력에 따라 평가한다. 출산 예정 부모, 의존 새끼의 보호자, 경계·사냥·섭식 중인 개체는 출발을 보류한다. 목적지 수용량과 종 상한, 실제 지면·차폐·경사·수심을 확인하며 이전 영수증은 기존 권위 자원 경계에서 발행한다. | 단일 지역 소유 맵에서는 통로가 없어 기존 경로를 따른다. 옵션·인접성·목적지 포화·재고 만료·지면 제약을 확인할 별도 두 지역 맵이 필요하다. 이주 중 먹기와 신규 번식 예약을 건너뛴다. [공통 이동과 생태 장부](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp) |
| 비행·장애물·사체 | 직접 하강이 막히거나 아래 지면이 없으면 가까운 대체 지면을 찾는다. 수평 접근과 수직 하강을 각각 쓸어 검사하고 유효한 방향으로 조금씩 이동한다. 공중에서 죽으면 새 착지 탐색을 시작하며 기존 안착·개방 처리는 실제 지면 도달 뒤 이어진다. | 전방 차단, 지면 누락, 모든 후보 차단을 같은 입력의 분기 검사로 비교한다. 모든 방향이 막힌 상태에서 강제 이동이나 가짜 사체 개방은 하지 않는다. 실제 비행 애니메이션과 안전한 공간으로의 장거리 복귀는 미검증이다. [비행 이동](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp) |
| 복제·늦은 에셋 등록 | 누락된 템플릿에 대한 버블 전체 재검색을 처음에는 0.1초 간격, 5초 경고 뒤에는 1초 간격으로 제한한다. 새 항목의 등록 가능 여부는 수신 시 검사하고 제거 처리도 계속 수행한다. | 소스 확인. 60 FPS에서 영구 누락이면 해당 경고 이후 목표 재검색률은 초당 약 60회에서 최대 1회다. 실제 패키지, 늦은 등록, 클라이언트 비용은 미측정이다. [클라이언트 버블](../../Source/AdaptiveEcosystem/Network/Mass/EcoMassClientBubble.cpp) |
| 전투 검증 도구·프로세스 | 이번 실행의 서버 로그로 준비 여부를 확인하고, 한 클라이언트가 실패해도 나머지 결과를 모두 기다려 보고한다. | PowerShell 구문 확인. 전투·체력바의 기존 런타임 실패를 이 변경으로 해결했다고 기록하지 않는다. [전용 서버 검사 실행기](../../Tools/Editor/run_player_hunting_network.ps1) |

규칙 종 통로는 `EcoHerdMigrationRoute`의 `bAllowRuleFaunaPassage`를 켜고, 양쪽 지역이 인접해 있으며 지역 선택이 달라지는 짧은 연속 지면 좌표를 `Migration.ArrivalRadius` 안에 배치한다. 식량 보고 사용이 허용된 통로만 비교한다. 비행종은 땅에 있을 때 이 경로를 쓸 수 있다. 공중 지역 이동, Native 늑대의 독자 이동, 의존 가족 전체의 동시 이전은 별도 설계가 필요하다. 출생·식생·사체 공급, 사냥·음향·HUD·세션, 체크포인트·패키지는 위 감사의 남은 검증 조건을 유지한다.

이번 비교는 저장된 시드 입력 재판정, 분기 계산, 스크립트 구문 검사와 소스 확인이다. 새 C++ 바이너리와 쿠킹을 사용하지 않았으므로 실제 새 동작이나 장기 개체군의 변화를 확정할 수 없다.

## 지역 스트리밍·출시 날씨·공중 사체 후속

| 같은 조건 | 이전 경로 | 수정 후 소스와 검증 |
| --- | --- | --- |
| 작성된 지역 강우가 바뀜 | Shipping은 개발 환경 감시가 꺼져 지역 날씨를 Native 초기값과 이후 스텝에 전달하지 못했다. 식생의 지역 날씨 입력은 별도로 갱신됐다. | 출시 빌드에서 작성된 날씨 출처만 읽고 기존 결정 스텝 경계에 적용한다. 개발용 나무 스캔, 콘솔 덮기, 공지 및 변경 이력 누적을 사용하지 않는다. 기존 `WeatherControls.json`의 72개 관측 중 실제 강우 값을 사용해 전환·동일 값·건조 복귀·비활성·미등록·출처 없음 여섯 분기를 비교했다. Shipping 실행은 미검증이다. [날씨 입력과 적용](../../Source/AdaptiveEcosystem/AI/Policy/EcoV3EnvWatch.cpp) |
| 지역 Actor 한 개가 내려갔다 복귀함 | 날씨 값을 보존해도 이동용 공간 스냅숏 단계에서 전체 경계를 실패시켰다. | 초기 구성 검증은 필수 지형을 요구한다. 실행 중 누락된 지역은 장부 ID·인덱스를 유지하고 이동 후보에서 제외한다. Legacy는 현재 목적지가 누락되면 다음 자원 경계에서 예약을 해제한다. 지역이 복귀하면 새 스냅숏에서 인접성이 돌아온다. 스냅숏 입력 모델을 비교했고 엔진 회귀를 추가했다. Native 무리의 일시정지와 복귀는 아래 장기 운영 후속에 기록했다. [월드 스냅숏](../../Source/AdaptiveEcosystem/World/EcologyWorldSubsystem.cpp) · [이동 예약](../../Source/AdaptiveEcosystem/Mass/EcoMassMigration.cpp) |
| 두 지역 볼륨에 발 위치가 동시에 들어감 | 동물 쪽은 지역 ID 순, 플레이어 발소리의 재질·날씨 선택은 Actor 열거 순서였다. | 등록된 지역의 발소리 위치도 지역 ID 순으로 판정한다. 두 등록 순서를 바꾼 입력에서 같은 지역을 선택한다. 발소리의 청각 전파 범위는 기존 감각 규칙을 따른다. [플레이어 발소리](../../Source/AdaptiveEcosystem/Creature/Player/EcoPlayerEcologyComponent.cpp) |
| 공중 사망 후 최초 사체 만료를 넘겼지만 몸이 아직 남아 있음 | 착지보다 재고 만료가 먼저 처리되면, 나중에 몸이 땅에 닿아도 개방할 재고가 사라졌다. | 아직 비행 중인 사망 개체의 미개방 재고는 기존 몸 제거 기한까지 남긴다. 착지하면 기존 코드가 실제 착지 시각 기준으로 안착과 만료를 다시 설정한다. 고갈, 몸 제거 시한 도달, 기한 전 착지 조건을 같은 시각 입력으로 비교했다. [사체 정리](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.cpp) · [실제 착지](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp) |

소스 검사, 기록 입력의 분기 계산과 `git diff --check`를 실행했다. 새 Unreal 자동화는 추가했으며, 빌드·쿠킹 금지에 따라 그 실행과 새 바이너리 검증은 남아 있다. 다음 회귀에는 지역 스트리밍·기상 전환과 동물 반응을 함께 보는 장면, 사체 착지와 개방 시각, 여러 Client의 전투·HUD 일치, 저장 중 이동 상태를 포함한다.

## 장기 운영을 위한 구조 재점검

학습 모델이 연결된 실행 경로는 사슴의 Native PPO다. 늑대는 Native 위협 규칙, 멧돼지·여우·까마귀·표범·물소·쥐는 종별 규칙으로 움직인다. 종별 감각, 식성, 번식, 사체와 자원 장부는 학습 모델 적용 여부와 별개로 실제 실행 경로에서 쓰인다. 기본 R7e를 재사용하려면 관측과 행동 계약이 같아야 한다. 같은 장부를 사용해도 사냥 후보는 backend 경계를 통과하지 못해 규칙 종 표범의 살아 있는 먹이에서 Native 사슴이 빠진다. [시작 두뇌](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp) · [Native 늑대 실행](../../Source/AdaptiveEcosystem/AI/Policy/EcoWorldV3.h) · [규칙 종 포획](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp)

| 확인된 중복이나 누락 | 소스 수정 |
| --- | --- |
| 서식지 단계만 변경해도 포만 사슴의 섭식이 달라졌다. 사슴 생활 규칙과 단계별 포만 상한이 서로 다른 조건에서 동작해 실험 원인이 섞였다. | 포만 상한을 기존 `DeerMeal` 소유로 옮겼다. 생활 규칙 마스크는 생태 life가 켜진 월드에서 명시한 설정을 쓰며, 서식지 단계 0에서도 독립적으로 비교할 수 있다. 마스크 0은 사슴의 기존 Native 섭식 경로를 사용한다. [섭식 제어](../../Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp) · [규칙 설정](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureIntegrationSpawner.h) |
| Native 사슴의 저장된 Legacy 급식 시각으로 자원 경계를 잘랐다. 실제 급식 요청 단계는 Native 사슴을 이미 제외했다. | 자원 스케줄러도 실제 요청과 같은 backend 조건을 적용한다. 규칙 종의 공격 접촉, Legacy 급식, 이주와 일반 자원 경계는 각각 유효 시각에 처리된다. [자원 스케줄러와 급식 요청](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoCreatureLifecycle.cpp) |
| 규칙 종 이주는 지역 총 예약만 집계했다. 한 종에 자리가 하나 남아도 여러 개체가 먼저 출발할 수 있었다. | 지역별 종 집계에 상주 개체와 진행 중인 유입 예약을 함께 반영한다. 도착 검사는 자신의 예약을 빼고, 취소는 예약을 해제한다. 도착 시 목적지 예약은 상주 개체 한 자리로 이어진다. 통로 Actor의 허용 설정이 이 기능을 켜며, 다종 맵이 거부하는 Legacy 이동 설정과 독립이다. [통로·예약](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp) |
| Native 무리는 지역 Actor가 내려가도 남아 있는 계산용 context로 도착·인구 이전을 확정할 수 있었다. | 월드의 공간 스냅숏을 함께 읽는다. 출발지·목적지 또는 이동 중인 개체의 소속 지역에 지형이 빠지면 기존 계획에서 기다리고, 센싱과 유지 대사는 계속 계산한다. 재등록 후 중단 시간만 준비·경로 막힘 타이머에서 빼며, 기존 막힘 시간은 유지한다. 실제 레벨의 경로 중간 셀과 양끝 볼륨이 독립적으로 내려가는 경우는 별도 재현이 필요하다. [무리 이동](../../Source/AdaptiveEcosystem/Mass/EcoHerdMigration.cpp) |
| 규칙 종 체크포인트는 이동 조각을 읽고 쓰기 전에 종별 분기에서 빠져 진행 중인 이주를 잃었다. Native 무리 복원은 일부 존재하는 계획의 경유점만 검사했다. | 두 backend가 공통 이동 상태를 저장하고, 로드에서 목적지 ID를 현재 지역 인덱스로 연결한다. 활성 무리원과 계획의 연결, 경유점·시각·목적지를 새 개체 생성 전에 확인한다. 현재 저장기는 필수 지역 환경 제공자가 내려간 상태에서는 저장을 거절한다. [저장과 복원](../../Source/AdaptiveEcosystem/Creature/Runtime/EcoEcosystemCheckpoint.cpp) |

앞선 60분 비교에서 쥐는 세 시드 모두 기아 0으로 줄었으나 상한 24에 도달했고, 표범은 세 시드 모두 사라졌다. 120분 단일 시드와 식생 교란 비교에서도 다종 공존을 확인하지 못했다. 표범은 현지 영양 획득과 먹이 접근 범위를 함께 확인해야 한다. 사체 재고를 늘려 잠깐 생존 시간을 늘리는 효과와 실제 포획·재정착으로 회복하는 효과를 구분해야 한다. 규칙 종 이동의 프레임 지연과 자원 따라잡기, 포획 backend 경계, 다지역 출생·이주·플레이어 사냥의 결합은 남은 구조 검증 항목이다. [같은 시드 장시간 기록](FAUNA_POPULATION_BALANCE.md)

기존 기록을 다시 읽고 동일한 입력의 분기 모델, 코드 순서와 문서 링크를 검사했다. 새 엔진 빌드·쿠킹 없이 진행했으므로 이 수정의 개체군 효과, 실제 지역 재등록과 이주 중 프로세스 재시작은 미검증이다. 추가한 Native 이주 자동화는 지역 대기 후 기존 계획으로 두 개체가 각각 한 번만 도착하는 조건을 포함한다.

## 후속 단계별 실행 검증

UE 5.8에서 `AdaptiveEcosystemEditor Win64 Development`를 직접 빌드했다. 첫 빌드의 오류는 표현 경로에서 `GetPawn()` 결과를 `const auto*`로 추론한 부분이었다. `const APawn*`로 수정한 다음 빌드가 성공했다. 자동화 302개 중 300개가 성공했고 경고 동반 성공은 2개, 실패는 0개였다. 쿠킹은 실행하지 않았다.

### 행동 이유와 플레이어 사건

- 권위 Inspector에서 `eco.Inspection.GameplayReasons 1`을 켜면 개체별 `gameplay_reason_history`에 시각, 지역, 이유, 상대 ID, 양을 표시한다. 사냥 후보 획득·접촉 거절·포획, 사체 섭취, 총성 청취, 통로 도착, 출생 지연·확정을 기록한다. 최근 16건과 최대 512개 개체로 제한하며 복원 시 새 기록을 시작한다. 기존 `reason_history`는 Native Social의 판단 기록이다. 미감지 또는 후보 탐색에서 걸러진 모든 개체를 이 기록으로 역추적할 수는 없다.
- 서버의 승인된 총기 발사에만 생태계 컴포넌트가 `Player.Shot`을 발행한다. 탄착·피해 유무와 독립이며, 같은 발사 ID는 한 번만 처리한다. Native와 규칙 종은 각자의 감각 조건에서 반응한다. 기본 총성 반경은 6,500cm다. 원준 담당 발사·피해 판정과 플레이어 입력·팀 원본 레벨에는 수정이 없다.
- 전용 서버와 Client 2개에서 A의 승인된 발사 14건과 B의 의도적인 빗나감 7건을 확인했다. 서버 총성은 21건, Client 총성 기록은 0건이었다. A는 피해 확정 4건과 늑대 사망 확정 1건을 받았고 B는 피해를 주지 않았다. 발사·피해 로그는 `Saved/RifleValidation/QualityStep4`에 있다.
- 같은 팀 맵의 근접 사냥은 Client A에서 30 피해 확정 한 건을 받았다. 실행 내 늑대 사망·클라이언트 사망 요약·늑대의 원격 플레이어 피해까지 이어지지 않아 회귀 시험은 실패로 남았다. 원준 담당과는 네트워크 콤보 접촉을 재현할 때 각 공격의 활성 구간, 히트 프록시, 서버 접촉 결과를 동일 시각으로 기록해 비교한다.

### 1배속·4배속과 낮은 프레임률

규칙 종 이동을 한 틱에 최대 8회, 각 0.1초 이하로 나누고 남은 이동 시간을 다음 틱으로 넘긴다. 포획 접촉과 기존 권위 자원 거래는 처리한 이동 시각까지 진행한다. 이동 지연 중에는 체크포인트가 저장을 거절하며 지연이 해소되면 같은 저장 API로 재시도할 수 있다. `eco.Integration.Dump`의 `MotionDebt`가 남은 이동 시간을 초 단위로 보여 준다.

같은 시드 20000과 로컬 `LV_JYU_IntegrationR7eFauna`에서 각 120 게임초를 실행했다. `-benchmark -fps=`는 고정 프레임 시간으로 계산하며 실제 GPU 부하로 인한 프레임 급락 실험과 구분한다.

| 배속과 FPS | 사슴 섭취 | 사슴 | 멧돼지 | 쥐 | 쥐 사망 | 종료 이동 지연 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1× · 30 | 96.041 | 26 | 5 | 14 | 0 | 0.000초 |
| 1× · 60 | 96.045 | 26 | 5 | 14 | 0 | 0.000초 |
| 4× · 30 | 105.023 | 29 | 6 | 10 | 4 | 0.000초 |
| 4× · 60 | 96.041 | 26 | 5 | 14 | 1 | 0.000초 |

네 실행 모두 사슴 Native 결정 900스텝을 누락 없이 수집했다. 늑대 3, 물소 4, 까마귀 6, 여우 3, 표범 3은 네 실행에서 같았다. 4×·30 FPS의 쥐 사망 4건은 피식이었다. 이동 시간 유실은 보완했지만 4×·30 FPS의 포획과 섭식은 기준과 다르므로 개체군 실험을 비교할 때 배속과 프레임 설정을 함께 고정한다.

### 서식지 충격·통로·장기 개체군

무리 이주에서 되돌아가는 데 실패해 고립된 개체는 기존 계획의 경유점 중 가까운 곳을 지면 경로로 다시 검사한다. 길이 확인되면 기존 이동 경로를 사용하고, 지역 경계를 실제로 건넌 경우에만 `ReturnHome` 이전을 기록한다. 자동화에서 쿨다운 전 고립 상태, 이후 같은 계획 재개, 위치 보존과 허위 도착 0건을 확인했다. 실제 맵에서 막힌 경유점이 다시 열려 고립 개체가 복귀하는 장면은 추가 재현이 필요하다.

시드 20000, `LV_JYU_HerdMigration`, 4배속 150 게임초로 세 가지 자원 조건을 비교했다. 모두 같은 기존 Barren→Forest 통로를 사용했다.

| 자원 조건 | Barren 먹이량 6초 → 종료 | 계획 | Forest 도착 |
| --- | ---: | ---: | ---: |
| 대조군 | 29.29 → 44.00 | 0 | 0 |
| 일회성 손실 후 기존 재생 허용 | 10.26 → 43.65 | 0 | 0 |
| 손실 후 재생을 멈춘 지속 가뭄 실험 | 0 → 0 | 14 | 30 |

재생 억제는 테스트 입력이다. 지속 가뭄에서 30개체의 지역 이전과 도착을 함께 기록했다. 이 결과는 Native 무리 통로 검증이며 규칙 종 전용 경계나 복수 세대 정착을 입증하지 않는다.

별도 다종 복사본에서 시드 20000, 4×·60 FPS로 30분을 돌렸다. 실제 사슴 섭취량은 1,178.864, Native 결정은 누락 없이 13,500스텝이었다. 종료 개체수는 사슴 26, 늑대 1, 물소 5, 까마귀 4, 여우 0, 표범 0, 멧돼지 4, 쥐 24였다. 여우와 표범은 각각 새끼 한 마리를 낳았고 초기 두 마리와 새끼 모두 기아로 사망했다. 따라서 자원 거래와 자연 출생이 이어져도 다종 공존은 확인되지 않았다. 포식자의 현지 실제 섭취, backend 간 유효 먹이, 다른 지역 먹이 접근을 따로 재현해야 한다.

같은 설정의 6분 행동 표본에서 표범은 사냥 후보 획득 9건, 접촉 거리 미달 7건, 사체 섭취 4건을 남겼으며 포획 성공은 수집되지 않았다. 여우는 후보 획득 42건, 거리 미달 25건, 포획 2건, 사체 섭취 4건이었다. 기록기의 관측 간격은 1초이며 개체별 링을 읽으므로 수치는 모든 발생의 전수 집계가 아니다. 사슴 출생 지연에서도 전역 자리 상한 8건과 부모 에너지 6건이 각각 확인됐다. 재현 시 `-DeerAuditTrackReasons`를 사용한다.

### 표현과 음향

별도 소유 맵의 렌더링 PIE에서 여덟 종을 걷기, 급회전, 제동, 섭식, 사망과 정착 단계까지 재생했다. 까마귀 비행·착지와 쥐 사체 정착도 포함했다. 발소리 PIE의 여덟 종 발 이벤트는 각각 5~11회 재생됐고, 비행 중 까마귀와 거리 밖 쥐는 0회였다. 동일 거리의 물소는 6회 재생됐다. 플레이어는 일곱 표면과 비에 젖은 잔디의 재생 로그를 수집했다. 측정치, 스크린샷과 WAV는 각각 `Saved/FaunaAudit`, `Saved/FaunaFootsteps/QualityStep1_Footsteps`에 있다. 이 실험의 평면·경사 장면과 수집된 소리로 모든 통합 레벨 지형과 믹스를 보증할 수는 없다.

급반전의 몸통 회전은 프레임당 36.02° 이하였고 표범·물소 발 마커의 경사면 침투는 5cm 이하였다. 까마귀는 이륙·비행·착지 전환에서 지상 발 IK가 비활성화됐다. 판정 기준은 해당 PIE 스크립트에 있다. [동작·IK 검증](../../Tools/Editor/audit_jyu_fauna_motion.py) · [발소리 검증](../../Tools/Editor/audit_jyu_fauna_footsteps.py)

렌더링 Client 두 개에서 늑대 HP 100→70이 동일하게 보였고 늑대와 사슴 체력 위젯이 모두 초기화됐다. 두 번째 공격자가 18회 입력한 구간에서는 추가 피해가 서버에 확정되지 않아 양쪽 공격에 따른 연속 감소를 요구하는 전체 체력바 회귀는 실패했다. 두 Client의 위젯 값은 수신한 권위 HP 샘플과 일치했다. 이 장면은 두 번째 발사 요청에서 피해가 생기지 않은 원인까지 확정하지 않는다.

### 재현 입력

| 검증 | 기존 스크립트 | 실행 조건 |
| --- | --- | --- |
| 배속·개체군 | [통합 레벨 실행 기록기](../../Tools/Editor/audit_integration_r7e_runtime.py) | 다종 복사본에서 `-EcoV3Seed=20000 -EcoV3Wolves=1 -EcoV3Brain=default -DeerAuditMode=current -DeerAuditTrackIntake`. `-benchmark -fps=30` 또는 `60`, `-DeerAuditDilation=1` 또는 `4`. `-DeerAuditRun=<실행명> -DeerAuditSeconds=120`을 지정하고 30분은 `1800`을 사용한다. |
| 행동 이유 | [같은 기록기](../../Tools/Editor/audit_integration_r7e_runtime.py) | 위 조건의 4배속·60 FPS에 `-DeerAuditSeconds=360 -DeerAuditTrackReasons`를 사용한다. |
| 가뭄·회복 | [이주 기록기](../../Tools/Editor/audit_herd_migration_runtime.py) | 이주 맵에서 `-EcoV3Seed=20000 -benchmark -fps=60 -HerdAuditName=<실행명> -HerdAuditGameClock -HerdAuditDuration=150`. 대조군은 `-HerdAuditNoLoss`, 단발 손실은 `-HerdAuditRenewableLoss`, 지속 가뭄은 두 옵션 모두 생략한다. |
| 총기·체력바·근접 사냥 | [총기](../../Tools/Editor/run_jwj_rifle_network.ps1) · [체력바](../../Tools/Editor/run_health_bar_network.ps1) · [근접](../../Tools/Editor/run_player_hunting_network.ps1) | 실행기는 전용 서버와 Client 두 개를 기동한다. 총기의 결과 폴더는 `-EvidenceTag <실행명>`으로 구분하고 체력바는 `-RenderedClients`를 사용한다. |
