# Asset Audit Report — AdaptiveEcosystem Content Directory

**작성일**: 2026-09-16  
**작성 목적**: 템플릿 프로젝트(Unreal Engine Third Person / Variants)로부터 유입된 에셋들을 분류하고, 동적 생태계 캡스톤 프로젝트에 필요한 에셋과 삭제 후보를 안전하게 구분함.  
**원칙**: 본 단계에서는 에셋을 **임의로 자동 삭제하지 않으며**, 팀원들의 검토를 거쳐 안전한 단계에서 정리함.

---

## 1. 종합 분류 요약

```text
┌─────────────────────────────────────────────────────────────┐
│                          Content/                           │
├───────────────────┬───────────────────┬─────────────────────┤
│       KEEP        │ REMOVE CANDIDATE  │    UNKNOWN/CHECK    │
│  (프로젝트 필수)    │   (삭제 검토 대상)  │   (참조 관계 확인)    │
├───────────────────┼───────────────────┼─────────────────────┤
│ Characters/       │ Variant_Combat/   │ __ExternalActors__/ │
│ Input/            │ Variant_Platform/ │ __ExternalObjects__/│
│ LevelPrototyping/ │ Variant_SideScroll│ Collections/        │
│ ThirdPerson/      │                   │ Developers/         │
└───────────────────┴───────────────────┴─────────────────────┘
```

---

## 2. 세부 분류 상세

### A. KEEP (보존 필수)

| 경로 | 주요 내용 | 보존 사유 |
|---|---|---|
| `Content/Characters/Mannequins/` | `SK_Mannequin`, `SKM_Manny_Simple`, `SKM_Quinn_Simple`, 기본 애니메이션(Unarmed, Death 등), Control Rig, Physics Asset | 크리처 및 캐릭터 런타임의 기본 스켈레탈 메시, 애니메이션 리타게팅, 본 스케일 변형 프로토타이핑에 필수적인 베이스라인 에셋 |
| `Content/Input/` | `IMC_Default`, `IA_Move`, `IA_Look`, `IA_Jump` 등 Enhanced Input | 플레이어 기본 조작 체계의 필수 입력 구성 |
| `Content/LevelPrototyping/` | `SM_Cube`, `SM_Ramp`, `M_Grid` 등 기본 블록아웃 메시 및 머티리얼 | World/Level 담당 팀원이 생태계 테스트 맵(`TestMap_Ecology`), 서식지(`Forest_A`), NavMesh 영역을 프로토타이핑하는 데 필수 |
| `Content/ThirdPerson/` | `BP_ThirdPersonCharacter`, `BP_ThirdPersonGameMode` | 기본 관찰자/플레이어 캐릭터 베이스라인 |

### B. REMOVE CANDIDATE (삭제 검토 대상)

> [!WARNING]
> 아래 에셋들은 C++ 모듈(`Source/AdaptiveEcosystem/Variant_*`)과 상호 참조되어 있을 수 있으므로, C++ 소스 정리와 함께 단계적으로 제거해야 합니다.

| 경로 | 주요 내용 | 삭제 검토 사유 |
|---|---|---|
| `Content/Variant_Combat/` | `ABP_Manny_Combat`, `AM_ComboAttack`, `AM_ChargedAttack`, `BP_Combat*`, `Lvl_Combat.umap`, `UI_LifeBar` 등 40여 개 에셋 | Third Person 템플릿의 격투(Combat) 예제 에셋으로, 동적 생태계 캡스톤 프로젝트의 핵심 시스템(Ecology/Mass/Evolution)과 무관함 |
| `Content/Variant_Platforming/` | `BP_PlatformingCharacter`, 대시(Dash) 애니메이션 몽타주 등 | 플랫포머 점프/대시 템플릿 에셋으로 불필요 |
| `Content/Variant_SideScrolling/` | `BP_SideScrolling*`, 점프패드, 이동 플랫폼, 사이드뷰 카메라 매니저 등 | 2.5D 사이드스크롤링 예제 에셋으로 3D 생태계 프로젝트와 무관 |

### C. UNKNOWN / REFERENCE CHECK NEEDED (의존성 확인 필요)

| 경로 | 주요 내용 | 확인 필요 사항 |
|---|---|---|
| `Content/__ExternalActors__/` | World Partition 외부 액터 레코드 | `Lvl_Combat` 또는 다른 레벨에서 분할 저장된 액터 파일. 해당 맵 삭제 시 함께 정리되어야 함 |
| `Content/__ExternalObjects__/` | World Partition 외부 오브젝트 데이터 | 상동 |
| `Content/Collections/` | 에디터 로컬 컬렉션 정의 | 프로젝트 공용 컬렉션인지 개인 설정인지 확인 필요 |
| `Content/Developers/` | 개발자 개인 작업 폴더 | 팀원 로컬 작업물이 포함되어 있는지 확인 |

---

## 3. 권장 정리 절차 (Safe Deletion Workflow)

1. **Phase 1 (현재)**: 에셋 보존 및 감사 목록 작성 (완료)
2. **Phase 2 (팀 검토)**: Variant C++ 코드 의존성 정리
   - `AdaptiveEcosystem.Build.cs`에서 `Variant_*` 폴더 제외 검토
   - `AdaptiveEcosystem/Source/AdaptiveEcosystem/Variant_*` 소스 코드 정리
3. **Phase 3 (에디터 내 정리)**:
   - Unreal Editor의 *Reference Viewer*를 통해 `Variant_*` 에셋이 `Characters/`나 `LevelPrototyping/`의 에셋을 오염시키지 않았는지 확인
   - 에디터 내에서 `Variant_Combat`, `Variant_Platforming`, `Variant_SideScrolling` 폴더를 안전하게 일괄 삭제(Delete)
