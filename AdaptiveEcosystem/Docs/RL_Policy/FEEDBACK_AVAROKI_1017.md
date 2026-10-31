# avaroki 님께 보낼 피드백 — 지역 비·눈 날씨와 나무 장애물 PR (초안, 10-17)

- 쓴 사람: 권신혁(RL·정책). 보내는 사람도 권신혁이다(PR 댓글이나 메시지에 아래 '보낼 글'을 그대로 붙인다).
- 대상: `origin/feat/ecosystem-integration-map` 의 `ff8c8f4` '지역별 비·눈 날씨 및 나무 장애물 배치'(우리 쪽 병합 `3e90177`).
- 근거(숫자 출처)는 맨 아래 '근거'에 모았다. 레벨·콘텐츠·설정은 읽기만 했고 저장하지 않았다.

---

## 보낼 글

avaroki 님, 지역 비·눈 날씨랑 나무 배치 PR(`ff8c8f4`) 잘 받았습니다! 제 브랜치에 합쳐서 맵을 하나씩 읽어 봤어요. 레벨은 열어서 읽기만 했고 아무것도 저장하지 않았습니다. 정리해서 드릴게요.

**잘 된 것**

- 합칠 때 충돌이 없었고, LFS 파일(나무·비·눈 이펙트·소리)도 모두 잘 받아졌어요. 빌드와 자동 시험도 그대로 통과했습니다.
- 나무 11그루 모두 충돌이 켜져 있어서(BlockAll) 우리 코드가 장애물로 읽는 조건(쿼리 충돌 + WorldStatic 막음)을 그대로 만족해요. 동물 무대 안에만 들어오면 바로 장애물로 읽힙니다.
- 비는 숲, 눈은 고지 트리거 상자를 따라 켜지는 구조라 지역마다 날씨를 다르게 보여 주기 좋아요.
- `BP_SkyManager` 의 SunSpeed 로 해·달을 돌리는 것도 블루프린트에서 확인했어요(지금은 두 맵 모두 0).

**확인하면서 걸린 것**

1. **나무가 동물 무대 밖에 있어요.** 사슴·늑대는 지역마다 먹이 자리 둘레 120 m 상자(동물 무대) 안에서만 움직여요. 11그루 모두 숲 지역이긴 한데 숲 무대 밖이에요. 가장 가까운 `Beech_Tree11` 도 무대 남쪽 끝에서 14.7 m 밖이고, 나머지는 38~360 m 떨어져 있어요. 그래서 지금은 사슴이 지나는 길에 나무가 0개예요.
2. **이 맵에는 동물이 안 나와요.** `LV_SHC_RegionalWeatherTest` 에 동물 조정자(`Eco_CreatureRuntime`, `AEcoCreatureIntegrationSpawner`)와 은신처가 없어서, 이 맵에서는 나무와 동물이 만나는 장면을 볼 수 없어요.
3. **충돌이 잎까지 감싼 덩어리 하나예요.** `Beech_Tree` 단순 충돌이 볼록 껍질 1개라서 크기 2배로 28 × 27 × 25 m 예요. 실제 줄기는 밑동 반경 0.8 m 정도인데, 동물 몸 높이(땅 위 60 cm)에서는 줄기에서 8~13 m 떨어진 허공에서 막혀요.
   - 동물 이동 제약과 플레이어(Pawn)도 같은 충돌을 써서 둘 다 보이지 않는 벽에 막힐 거예요(이 맵에 동물이 없어 직접 보지는 못했어요).
   - 우리 코드로 읽으면 나무 하나가 반경 13.8 m 원판, 무대 넓이의 4.2% 가 돼요.
4. **나무 높이가 모두 같아요.** 11그루 모두 z = −1310 이라 9그루는 땅에 1.8~4.6 m 묻혔고, 2그루는 떠 있어요(`Beech_Tree11` 3.2 m, `Beech_Tree2` 0.8 m). 우리 코드는 높이를 보지 않고 원판을 만들어서, 떠 있는 나무 밑으로 동물이 지나가면 화면과 어긋나요.
5. **나무가 듬성해요.** 11그루가 약 12 ha 에 퍼져 있어서 1 ha 에 1그루 정도예요. 실제 숲(줄기 단면적 1 ha 34 m²)이면 이 굵기(반경 0.8 m) 나무가 1 ha 에 17그루쯤이에요.
6. **다른 맵의 날씨 연결이 끊겼어요.** 날씨 블루프린트를 옮기면서 옛 경로 연결(리디렉터)이 사라졌어요.
   - `/Game/Actors/BP_WeatherManager_PlayerFollow` 가 없는 애셋을 가리켜서, `LV_JYU_V3Integration` 을 열면 'Failed to find redirected assets' 경고와 함께 날씨 액터가 빠져요. `LV_JYU_RefugeSafety`·`Integration_JwJ` 도 같은 액터를 써서 같을 거예요.
   - `/Game/Foliage/FT_GrassC`·`FT_GrassD` 도 연결 없이 옮겨져서 그 맵들의 풀 칠하기 연결이 끊겨요(이미 그려진 풀은 남아 있어요).
7. **날씨가 아직 화면과 소리에서만 바뀌어요.**
   - 지역 환경 값(`FRegionEnvironmentState.Rainfall`)은 0 그대로라, 게임 규칙(팀 시야·청각 계산, 먹이 재생, 우리 사슴)은 비·눈을 몰라요.
   - 비·눈이 카메라가 트리거 상자 안에 있는지로 켜져서, 카메라가 없는 서버·헤드리스 실행에서는 날씨가 없는 셈이에요.
   - 눈은 `EEcoWeatherState` 에 칸이 없어요(Clear·Rain·Storm·Drought 뿐).
8. **SunSpeed 는 동물 낮밤과 따로 돌아요.** 우리 v3 동물은 팀 시계(`UEcoWorldClockSubsystem`, 낮 60초 + 밤 60초)를 따르는데, SunSpeed 를 올리면 화면의 해·달과 동물의 낮밤이 어긋나요.

**부탁드릴 것**

1. **나무를 동물 무대 안에 놓아 주세요.** 맵은 `LV_Ecosystem_IntegrationTest`(공식 레벨이 따로 정해지면 그 맵)예요. 무대 상자는 월드 좌표(m)로 이래요.
   - 숲: x 282~402, y 405~525 (cm 로 X 28200~40200, Y 40500~52500)
   - 메마른 땅: x 280~400, y −50~70
   - 고지: x 280~400, y −550~−430
   - 숲 무대에 `Beech_Tree` 24그루 안팎이면 실제 숲과 비슷해요(줄기 반경 0.8 m 기준). 한쪽에 몰지 말고 퍼뜨리되, 나무 사이에 사슴이 빠져나갈 틈(3 m 이상)은 남겨 주세요.
   - 은신처 자리 4곳은 비워 주세요. 숲 무대 기준 (312, 435), (372, 435), (312, 495), (372, 495) m 둘레 반경 12 m 예요. 이 원 안 나무는 우리 코드가 은신처 덤불로 보고 빼서 화면과 어긋나요. 메마른 땅·고지도 무대 상자의 x·y 가 가장 작은 모서리에서 (30, 30)·(90, 30)·(30, 90)·(90, 90) m 떨어진 같은 자리예요.
   - 무대 상자 가장자리에서 2 m 이상 안쪽에 놓아 주세요. 무대 벽은 실제 땅에 없는 벽이라, 벽에 붙은 나무와 벽 사이에 사슴이 끼어요.
   - 메마른 땅·고지는 선택이에요. 바위를 놓는다면 무대마다 7개쯤(반경 0.5~1.5 m)이면 우리 파이썬 숲 설정과 같아요.
   - 폴리지 툴로 칠해도 괜찮아요(인스턴스도 읽어요). 충돌만 켜 주세요(쿼리 충돌 + WorldStatic 막음).
2. **나무 충돌을 줄기 캡슐로 바꿔 주세요.** `Beech_Tree` 메시의 단순 충돌을 지우고 줄기에 캡슐 하나(반경 약 0.8 m, 높이 2~3 m)만 두면 돼요. 잎·가지는 충돌 없이요. 우리 코드는 반경 25 cm·높이 50 cm 보다 작은 충돌은 빼니까, 그보다 크기만 하면 돼요.
3. **나무를 땅에 붙여 주세요.** End 키(바닥에 붙이기)로 줄기 밑이 땅에 살짝(0~30 cm) 묻히게요.
4. **끊긴 연결을 고쳐 주세요.** 옛 경로에 리디렉터를 다시 두거나, JYU·JWJ 맵의 날씨 액터를 새 `BP_WeatherManager_Region` 으로 바꿔 주세요. `FT_GrassC`·`FT_GrassD` 도 같이요. (에디터 안에서 옮기기·이름 바꾸기를 하면 리디렉터가 남아요.)
5. **공식 시연 레벨을 하나 정해 주세요.** 지금 통합 맵·JYU 맵·JWJ 맵·SHC 맵으로 나뉘어 있어요. SHC 맵을 공식으로 쓰려면 동물 조정자(`Eco_CreatureRuntime`)와 은신처가 들어가야 해요. 정해지면 나무·은신처·날씨를 그 맵에 모아요.
6. **날씨를 게임 값으로 내 주세요.** 우리가 읽을 곳은 이래요.
   - 서버에서 지역마다 `FRegionEnvironmentState` 에 쓰기: 맵에 `AEcoRegionEnvironmentAdapter` 를 지역마다 하나씩 놓고 `RegionIds` 에 그 지역 이름(`Forest`·`Highland`)을 넣은 뒤, 날씨 블루프린트가 `ApplyRainfall(강수 0~1, Rain 또는 Storm)` 을 부르면 돼요. `RegionIds` 를 비워 두면 모든 지역에 같은 비가 내려요.
   - 우리는 `UEcologyWorldSubsystem::GetEnvironmentState(지역 이름)` 로 `Rainfall`(0~1)과 `WeatherState` 를 읽어요. 팀 Social 시야·청각 코드도 이미 여기서 읽어요.
   - 눈은 지금 칸이 없어서, `EEcoWeatherState` 에 `Snow` 를 더하고 눈 세기 칸(`Snowfall`, 0~1)을 두면 좋겠어요. 쌓인 눈을 따로 쓸 거면 `SnowCover`(0~1)도요. Core 구조체라 팀이 같이 정해요.
   - 화면의 비·눈은 카메라 위치가 아니라 이 값을 따라 켜지게 해 주세요. 그래야 화면과 동물 규칙이 같고, 카메라 없는 서버에서도 날씨가 돌아요.
   - 언제 바뀌는지는 정해진 표나 시드로 정해 주세요. 예: 지역마다 (시작 초, 끝 초, 세기) 목록. 그래야 파이썬 학습 세계에서 똑같이 다시 만들 수 있어요. 한 번 바뀌면 30초 이상 가게 해 주세요.
7. **해·달은 팀 시계로 돌려 주세요.** SunSpeed 대신 `AEcoRegionEnvironmentAdapter` 의 `OnClockUpdated(Phase, PhaseProgress)`(팀 시계 `UEcoWorldClockSubsystem` 값)로 해 각도를 정하면 동물 낮밤과 맞아요.

나무를 놓으시면 알려 주세요. 제가 헤드리스로 돌려서 무대마다 읽힌 나무 수, 동물이 끼는지, 사냥·생존이 어떻게 바뀌는지 숫자로 바로 드릴게요. 맵 그림(무대·은신처·나무 자리)도 있어서 필요하면 같이 보내 드릴게요. 고맙습니다!

---

## 근거 (보낼 글에는 넣지 않는다)

- 맵 읽기: `herbivore_rl/results/v3/wild2/level_shc/README.md`(나무 11그루 자리·높이·충돌 모양, 날씨 블루프린트, SunSpeed, 리디렉터 경고), 그림 `stage_Forest.png`·`map_overview.png`·`forest_trees.png`·`beech_tree_collision.png`.
- 나무를 통합 레벨 무대에 겹친 결과(무대마다 원판 0): `herbivore_rl/results/v3/wild2/shc/README.md`.
- 무대 상자: 통합 v3 모드 내보내기 `level_shc/v3_export_integration_s20000.json` 의 `origin_cm`(숲 28200·40500, 메마른 땅 28000·−5000, 고지 28000·−55000)과 한 변 60 단위(120 m). 은신처 원은 같은 파일의 `covers`(단위 (15, 15)·(45, 15)·(15, 45)·(45, 45), 반지름 6 = 12 m).
  지금 통합 레벨에는 무대 안 은신처가 없어서 우리 코드가 이 네 자리에 임시 은신처를 만든다(팀 요청 문서 4절 2). 팀이 은신처를 놓으면 그 자리로 바뀐다.
- 우리 읽기 규칙: `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp` `ScanStageObstacles`
  (충돌 상자 중심이 무대 안 → 쿼리 충돌 + WorldStatic 막음 → 가로 반지름 25 cm 이상 → 높이 50 cm 이상 → 은신처 원 밖. 가로 반지름 = 충돌 상자 가로 반폭 평균. 높이·땅은 보지 않는다. 무대마다 원판 512 개까지).
- 밀도: 실제 온대 성숙림 가슴높이 단면적 34 m²/ha(ESA Ecological Archives E094-195, 명세 `RL_V3_WILD2_SPEC.md` 6-3). 반경 0.8 m 줄기 하나 = 2.01 m² → 1 ha 17그루, 숲 무대 1.44 ha 에 약 24그루.
  11그루의 퍼짐: x −78~344 m, y 321~616 m 상자(약 12 ha).
- 벽 곁 여유: 파이썬 배치 규칙(원판을 벽에서 r + 60 cm 띄움, 명세 6-2). 반경 0.8 m 줄기면 1.4 m 라 '2 m 이상'으로 적었다.
- 날씨 읽을 곳: `Core/EcoRegionTypes.h`(`FRegionEnvironmentState`, `EEcoWeatherState` = Clear·Rain·Storm·Drought), `World/EcoRegionEnvironmentAdapter.h`·`.cpp`(`ApplyRainfall` 은 `RegionIds` 가 비면 모든 지역에 쓴다),
  `World/EcologyWorldSubsystem.h` `GetEnvironmentState`, 팀이 이미 읽는 곳 `AI/Social/Senses/EcoPredatorPerception.cpp`·`AI/Social/Alarm/EcoThreatDetectionProcessor.cpp`(비 시야·청각 배수, 기본 1.0 = 효과 없음).
- 시계: 통합 v3 모드는 팀 시계가 돌면 그 시계에 맞춘다(`EcoPolicyV3IntegratedSubsystem.cpp` 전역 t 맞추기·`CheckClockDrift`).
- 확인하지 못한 것(추정): 동물·플레이어가 줄기에서 8~13 m 떨어진 허공에서 막힌다는 것(이 맵에 동물이 없다), `LV_JYU_RefugeSafety`·`Integration_JwJ` 의 날씨 액터가 빠진다는 것(`LV_JYU_V3Integration` 만 열어 봄).
- 학습 계획은 `RL_V3_R4_PLAN.md` 다. 나무가 무대 안에 들어와야 언리얼과 같은 판정 세계가 생긴다.
