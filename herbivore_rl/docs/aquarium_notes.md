# marl-aquarium 조사 노트 (§4.1)

- 조사 대상: `marl-aquarium` 0.1.10 (PyPI, MIT, LMU München)
- 저장소: https://github.com/michaelkoelle/marl-aquarium
- 조사 방법: `pip install --no-deps --target <scratch> marl-aquarium` 후 소스 전량 정독 (1,869 LOC)
- 조사 시점 환경: Windows 11 / Python 3.13.5 (Anaconda) / numpy 2.1.3
- **결론: 확장하지 않고 `env/world.py`를 자체 구현한다.** 근거는 §7.

---

## 1. 패키지 구성

| 파일 | LOC | 역할 |
|---|---|---|
| `env/aquarium.py` | 945 | `raw_env` (PettingZoo `ParallelEnv`). 물리·관측·보상·렌더 전부 |
| `env/utils.py` | 350 | `Torus` (거리/방향/FOV/충돌), 각도 변환, mp4 저장 |
| `aquarium_v0.py` | 184 | `env()` / `parallel_env()` 팩토리. 파라미터 재나열뿐 |
| `env/view.py` | 144 | pygame 렌더 |
| `env/animal.py` / `prey.py` / `predator.py` | 72 / 67 / 44 | `Entity` 기반 OO 개체 |
| `env/vector.py` | 63 | 스칼라 `Vector(x, y)` 클래스 |

## 2. 관측·행동 공간

### 관측 (prey 기준)
`observation_space = Box(0, 1, (5 + 3*6 + 1*6,))` = **(29,)** (기본값 `prey_observe_count=3`, `predator_observe_count=1`).

구성 (`prey_observe` → `get_prey_observations` → `prey_observer_observation` + `nearby_animal_observation`):

| 구간 | 내용 |
|---|---|
| 0–4 | 자기 자신: `[1, x/width, y/height, scale(orientation,-180..180), speed/max_speed]` |
| 5.. | 이웃 1마리당 6개: `[entity_type, x/width, y/height, dist/view_distance, dir, speed/max_speed]` |

→ **§3.1의 7개 스칼라(food_density, predator_count, predator_distance, kin_count, energy, recent_predation, cover_distance)와 공통 항목이 하나도 없다.** `predator_distance` 정도가 유사하지만 `nearby_animal_observation` 안에 섞여 있다.

### 행동
`action_space = Discrete(action_count)` (기본 16). `get_vector_from_action`이 action 인덱스를 **16방위 단위벡터**로 바꿔 desired velocity로 쓴다.

→ **§3.2는 `Box(-3,3,(4,))` 조향 가중치 4개.** 의미 자체가 다르다 (방향 선택 vs 가중치 출력). Aquarium의 핵심 설계 전제(정책이 방향을 고른다)와 본 프로젝트의 전제(정책은 방향을 고르지 않는다, §0)가 정반대다.

## 3. 시야(FOV)

- `prey_fov=120`, `predator_fov=150` (도). `prey_view_distance=100`, `predator_view_distance=200` (픽셀).
- `fov_enabled=True`면 `Torus.check_if_entity_is_in_view_in_torus()`가 **토러스 래핑 때문에 관측자마다 9개 시야원뿔 복사본**을 순회한다 (`utils.py` offsets 8개 + 원본).
- **채택**: FOV 각도 기본값 120도만 가져온다 (§3.1 "Aquarium 기본 FOV 사용"). 구현은 가져오지 않는다.
- 주의: `check_if_entity_is_in_view_in_torus`는 루프 안에서 `is_in_view`를 **덮어쓴다** (`is_in_view = ...`, 누적 `or`가 아님). 마지막 오프셋 결과만 남는 버그로 보인다.

## 4. 물리 조향 (§3.3과 대조)

`update_prey()` (aquarium.py:410):
```
steer_force = desired_velocity - velocity          # limit(prey_max_steer_force=0.6)
apply_force(steer_force)                           # acceleration += force / mass(=3)
acceleration.normalize(); acceleration *= max_acceleration(=1)
velocity += acceleration                           # 단, 동족과 충돌 중이면 반발 벡터로 대체
velocity.limit(max_velocity=4)
position += velocity
check_borders()                                    # 토러스 래핑
```
- 가속도/질량/조향력 상한이 있는 **관성 모델**. §3.3은 가중합을 정규화해 **속도를 직접 지정**하는 무관성 모델 (`normalize(v) * herb_speed`).
- separation/cohesion/forage/cover 항이 **없다**. 동족 회피는 "충돌하면 반발 벡터로 velocity를 통째로 대체"하는 한 줄뿐.
- §1.5(파이썬 조향 수식은 C++와 한 줄씩 대응)를 지키려면 이 레이어를 통째로 교체해야 한다.

## 5. 포식자 로직 / 번식 / 아사

| 항목 | Aquarium | §4.2 요구 |
|---|---|---|
| 포식자 유형 | 1종 | 근접형 + 원거리형 2종 |
| 포식 판정 | `Torus.get_colliding_animal` 반경 충돌 (`radius` 합) | 근접 1.0 결정적 / 원거리 3.0 확률적 |
| 포식자 정책 | 없음 — 포식자도 외부 에이전트 (`predator_N`이 agent) | 규칙 기반 추적 |
| 번식 | `procreate=True`일 때 **나이 기준** (`age == replication_age`) | 에너지 임계 + 쿨다운 (§3.4) |
| 에너지 | **개념 자체가 없음** | 관측 idx4 + 아사 + 번식 조건 |
| 아사 | 없음 (포식자만 `predator_max_age`로 죽음) | 필요 |
| 먹이 자원 | **없음** | 셀 격자 + 재생 (§4.2) |
| 은신처 | **없음** | 고정 배치 + 거리 2.5배 위장 |
| 지역 피식 EMA | 없음 | 필요 |
| 경계 | 토러스 고정 (`check_borders`가 좌표 래핑) | **벽** (토러스 끄기) |

## 6. 확장 지점

훅이 없다. 확장 포인트로 쓸 만한 것을 찾았지만 전부 막혀 있다:

- `raw_env`를 상속해 `update_prey` / `prey_observe` / `get_rewards`를 오버라이드하는 경로는 열려 있다. 그러나 오버라이드 대상이 **관측 7개 메서드 체인(aquarium.py:664–833) + 물리 2개 + 보상 3개**로, 사실상 `raw_env` 전체다.
- `Torus`가 거리/방향/FOV/충돌의 유일한 제공자라서, 벽 경계로 바꾸려면 모든 호출부를 교체해야 한다.
- `reset(seed=...)`가 **`seed`를 전혀 쓰지 않는다** (aquarium.py:156). 개체 생성은 모듈 전역 `random.randint`, ID는 클래스 변수 `Prey.identifier`. §3.5(시드 하나가 세계를 결정)를 만족시키려면 RNG를 전 계층에 다시 배선해야 한다.
- 에이전트 목록이 `prey_N` / `predator_N` 문자열 dict 기반이고 죽으면 `self.agents`에서 제거된다. §4.3(N=128 슬롯 고정 리스폰)과 규약이 어긋난다.

## 7. §11-A 판단 — 자체 World 채택

### 7.1 성능: §1.1과 구조적으로 충돌

Aquarium은 스칼라 OO다. `Vector`는 파이썬 float 두 개, 모든 연산이 파이썬 메서드 호출이다.

- `step()`은 `for entity in self.all_entities` 단일 루프 (aquarium.py:177).
- 그 안에서 `get_colliding_animal(prey, self.prey)`가 다시 `for a in animals` — **스텝당 O(N²) 파이썬 루프**.
- FOV는 쌍마다 오프셋 9개 순회 → 관측만 O(N·(N+M)·9).

N=128에서 초당 500스텝(§4.6)을 내려면 물리·이웃탐색·FOV·충돌을 전부 numpy로 다시 써야 한다. 그러면 **남는 Aquarium 코드가 없다.**

### 7.2 계약 불일치 범위

§3 계약과 겹치는 부분이 사실상 없다 (§2, §4, §5 표 참조). 관측 7개, 행동 4개, 조향 수식, 보상 4종, 시드 규약, 슬롯 고정 리스폰 — 전부 신규 작성이다.
§4.2가 요구하는 먹이·은신처·피식 EMA·포식자 2종·벽 경계는 **어느 쪽을 골라도 100% 신규**다. 즉 Aquarium 채택으로 절약되는 작업량이 0에 수렴한다.

### 7.3 의존성이 이 머신에서 설치 불가

`METADATA`의 핀은 전부 `==` 고정이다:

```
numpy==1.22.4   gymnasium==0.28.1   pettingzoo==1.24.2   pygame==2.1.3   moviepy==1.0.3
```

- numpy 1.22.4는 **Python 3.13 휠이 없다** (1.22 계열은 ≤3.10 지원). 소스 빌드도 3.13에서 실패한다.
- 현재 환경은 Python 3.13.5 / numpy 2.1.3. 즉 Aquarium을 쓰려면 **Python 3.10 환경을 따로 세우고 거기에 torch·SB3까지 다시 설치**해야 한다.
- `env/utils.py`가 모듈 최상단에서 `moviepy`를 import하므로 moviepy 1.0.3 없이는 `import marl_aquarium` 자체가 실패한다.

### 7.4 비교

| | Aquarium 확장 | 자체 `env/world.py` |
|---|---|---|
| 재사용되는 코드 | FOV 각도 기본값(120도) 숫자 하나 | — |
| 새로 써야 하는 것 | 관측·행동·조향·보상·시드·리스폰 + §4.2 전부 | 동일 |
| 추가로 해야 하는 것 | 1,869 LOC를 벡터화 스타일로 개조, OO API와 numpy 사이 임피던스 상시 관리, **Python 3.10 별도 환경 구축** | 없음 |
| 예상 규모 | 위 전부 + 기존 코드 이해·우회 비용 | 순수 numpy 500–700 LOC |

§11-A 기준("3일 이상")을 넘는다고 판단한다. 절약분이 0인데 개조·환경 비용만 추가된다.

### 7.5 그래서 가져온 것 / 버린 것

- **가져옴**: 초식 FOV 기본값 **120도** (§3.1 "Aquarium 기본 FOV 사용" → `configs/default.yaml: fov_deg`). 포식자 FOV 150도.
- **버림**: 그 외 전부. `marl-aquarium`은 런타임 의존성이 아니다 (`requirements.txt`에 넣지 않는다).
- §3 계약은 §4.1 지시대로 **양쪽 동일**하게 유지한다. 자체 World를 쓴다는 사실이 §3을 바꾸지 않는다.

---

## 8. 부수 기록 — 기존 저장소 문서와의 차이

`AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V1.md`는 본 스펙보다 앞서 작성된 문서로, 다음이 다르다. **본 구현은 `herbivore_policy_spec.md` §3을 따른다.** Phase 6에서 저장소 문서를 갱신할 때 정리가 필요하다.

| 항목 | POLICY_CONTRACT_V1.md | herbivore_policy_spec §3 (채택) |
|---|---|---|
| `predator_count` 정규화 | `MaxPredatorCap = 5` | **÷ 8.0** |
| `kin_count` 이름 | `conspecific_count` | `kin_count` (자기 제외 명시) |
| `cover_distance` 정규화 | `÷ CoverSearchRadius` | **÷ 20.0 고정** |
| 조향 합성 | `flee_dist × F_flee`를 항상 더함 + `F_align` 항 있음 | `flee_dist`는 **도주 개시 거리 임계치**, 조건부로만 `×3.0` 가산. align 항 없음 |
| Utility 기준식 | 4식 모두 다름 | §5.1 |
