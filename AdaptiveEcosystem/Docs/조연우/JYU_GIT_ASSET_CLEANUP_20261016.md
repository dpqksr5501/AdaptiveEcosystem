# 남아 있던 에셋 변경 정리

2026-10-16, `a88eac8` 이후 사용자의 Git 변경 정리 요청에 따라 확인했다. 이전 구현 커밋에서 바이트를 보존한 채 제외했던 **68개 에셋**이며, 이번 점검에서도 기존 백업 SHA-256과 일치했다. 파일을 초기화하거나 삭제하지 않고 별도 에셋 커밋으로 보존한다.

| 구분 | 개수 | 확인한 내용 | 처리 |
|---|---:|---|---|
| `LV_JYU_V3Integration`의 LandscapeStreamingProxy | 64 | 직전 HEAD의 LFS 원본과 비교해 `PM_EcoGrass`/`PM_EcoDry` 대신 `PM_JYU_Grass`/`PM_JYU_Dry`/`PM_JYU_Snow`/`PM_JYU_Water` 참조가 들어 있다. | 표면별 발소리 연결을 보존해 커밋 |
| JYU 경보·Snow·Water·Wet SoundWave | 4 | 기존 변경 저장본. 에디터에서 48kHz 모노, 압축 품질 80, 정상 로드를 확인했다. | 현재 바이트 그대로 커밋 |
| 10월 16일 발표 자료 | PPTX 1개 | 지난주 PDF 양식에 맞춘 편집 가능한 7장 발표 자료. | 별도 발표 커밋 |
| 발표 빌드·렌더·임시 검증 자료 | — | `Deliverables/WeeklyReport_20261016/.build/`에 모았고 해당 폴더의 `.gitignore`로 제외한다. | 최종 PPTX만 추적 |

Unreal 에디터에서 기존 통합 레벨의 64개 지형 Actor를 모두 로드하고 `MI_JYU_LandscapeSurface` 연결, 표면 PhysicalMaterial 4종과 SoundWave 4개를 확인했다. 에디터 검사에서 에셋을 저장하지 않았다. SoundWave 바이너리 크기 증가만으로 원음 변경이나 단순 캐시 변경을 단정하지 않는다. 현재 정상 로드되는 저장본을 보존했다.

검사 원본은 로컬 `Saved/GitCleanup_20261016/AssetAudit.json`, `EditorAssetAudit.json`, `EditorAudit02.log`다. `git lfs fsck --pointers HEAD`는 성공했다. 소스·설정·빌드 입력을 변경하지 않았으므로 이번 정리는 새 C++ 빌드나 PIE 검증을 의미하지 않는다. 이전 보호 은신처 구현의 빌드/147개 자동화/PIE·네트워크 검증 기록은 그대로 유지한다.

이전 문서에서 “사용자 에셋 68개를 커밋에서 제외했다”는 설명은 당시 커밋의 이력이다. 이번에는 명시적인 정리 요청에 따라 실제 변경 내용을 조사하고, 기능에 필요한 참조와 기존 오디오 저장본을 별도 커밋에 포함했다.
