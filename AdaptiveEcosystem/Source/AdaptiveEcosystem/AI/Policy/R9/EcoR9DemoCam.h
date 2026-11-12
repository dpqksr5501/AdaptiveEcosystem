// R9 데모 카메라 — 키·모드·거리 (2026-11-13 03:30 사용자 '0,1,2,3,4,5 번 키들로 시점 변경하는건 옛날 방식이 더 좋은데? … 우상단에 띄우고
// 0번 누르면 그냥 자유시점으로 보게 하고 시점 변경할때도 한번에 보여줘').
//
// 옛날 방식 = 관찰 카메라 (EcoV3ObserverCamera.h/.cpp, Docs/RL_Policy/OBSERVER_CAMERA.md 2·3·4절, ISLAND_STAGE.md I.2 '보기').
// 그 키 배치·뜻·거리·숙임을 R9 개체(사슴·늑대·멧돼지)에 그대로 맞춘다. 옛 코드는 고치지 않고, 공용 함수(EcoV3Observe — 부드러운 따라가기·자유 카메라·
// 오른쪽 위 글 묶음 자리)만 다시 쓴다.
//
//   1 늑대 시점 · 2 사슴 시점 · 3 탑뷰 · 4 쿼터뷰 · 5 자동 추적 · 0 자유 카메라          ← 옛 키 그대로 (숫자패드도)
//   6 멧돼지 시점 · 7 (= G) 다음 무리 자리 (끝에 섬 전체)                                 ← R9 만 (옛 키·옛 문서에 없는 숫자, G 는 옛 '지역 바꾸기')
//   8 물소 · 9 표범 · J 여우 시점 (동물 세계 2026-11-13 05:00)                            ← R9 만. 숫자가 모자라 여우는 J — 팀 입력 매핑(IMC_*)·플레이어/컨트롤러 BP·
//                                                                                        C++ 키 읽기 어디에도 Eight·Nine·J 이름이 없음을 확인 (fauna/UE_FAUNA.md)
//   , . 이전·다음 대상 · - = 휠 줌 (자유 카메라: 이동 속도) · H 단축키 목록 숨기기/보이기   ← 옛 키 그대로
//   자유 카메라: W A S D·방향키 이동 · Q E 아래·위 · 마우스 시야 · Shift 4 배           ← 옛 자유 카메라 그대로 (EcoV3Observe::FreeFlyStep·FreeLookStep)
// 옛 카메라와 다른 것 (사용자 11-13 요청):
//   - 0 은 늘 자유 카메라다 (옛: 자유 카메라에서 다시 0 = 원래 카메라(폰). R9 데모는 폰을 숨겨 두어 돌아갈 원래 카메라가 없다).
//   - 키로 시점을 바꾸면 그 프레임에 바로 그 자리로 간다 (옛: 150 m 안이면 0.18 초 시간 상수로 옮겨 감 — 자유 카메라에서 1~6 도 옮겨 감).
//     바꾼 뒤 움직이는 대상을 따라가는 것은 옛 부드러운 따라가기 그대로다.

#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"
#include "InputCoreTypes.h"

/** 카메라 모드 — 값 = 키 숫자 (콘솔 eco.R9Demo.Cam 도 같은 수). */
enum class EEcoR9DemoCam : uint8
{
	Free = 0,      // 0 자유 카메라 (그 자리에서 추적을 풀고 W A S D·Q E·마우스로 직접)
	Wolf = 1,      // 1 늑대 시점 (뒤에서 따라감)
	Deer = 2,      // 2 사슴 시점
	Top = 3,       // 3 탑뷰 (대상 위, 대상이 없으면 무리 자리·섬 전체 위)
	Quarter = 4,   // 4 쿼터뷰 (45° 사선)
	Auto = 5,      // 5 자동 추적 (사냥·물기·반격·사체 먹기 — 없으면 무리 자리 전체)
	Boar = 6,      // 6 멧돼지 시점 (R9 만)
	// 7 은 모드가 아니다 (다음 무리 자리)
	Buffalo = 8,   // 8 물소 시점 (동물 세계)
	Leopard = 9,   // 9 표범 시점
	Fox = 10       // J 여우 시점 (콘솔 eco.R9Demo.Cam 10)
};

namespace EcoR9DemoCam
{
	/** 키 동작. */
	enum class EAction : uint8
	{
		Free,       // 0
		Wolf,       // 1
		Deer,       // 2
		Top,        // 3
		Quarter,    // 4
		Auto,       // 5
		Boar,       // 6
		NextSite,   // 7 · G
		Prev,       // ,
		Next,       // .
		ZoomOut,    // - · 휠 아래 · 숫자패드 -
		ZoomIn,     // = · 휠 위 · 숫자패드 +
		Help,       // H
		Buffalo,    // 8 (동물 세계 — 뒤에 붙여 옛 동작 번호는 그대로)
		Leopard,    // 9
		Fox,        // J
		Count
	};

	struct FKeyBind
	{
		FKey Key;
		EAction Action;
	};

	/** 단축키 표 (숫자패드·휠 같은 별칭 포함). 옛 관찰 카메라 키(EcoV3Observe::Keys)와 겹치는 키는 같은 뜻이다 (시험 CamKeys). */
	TConstArrayView<FKeyBind> Keys();
	/** 키 → 동작 (카메라 키가 아니면 거짓). */
	bool ActionOf(const FKey& Key, EAction& Out);
	/** 모드를 고르는 동작이면 그 모드 (0~6 · 8 · 9 · 10). */
	bool ModeOf(EAction Action, EEcoR9DemoCam& Out);
	/** 0~6 · 8~10 → 모드 (밖·7 이면 거짓). */
	bool ModeFromInt(int32 Value, EEcoR9DemoCam& Out);
	const TCHAR* ModeNameKo(EEcoR9DemoCam Mode);
	/** 오른쪽 위 단축키 줄 (위에서 아래로). bSites = 무리 자리가 있는 맵 전체 땅 (7 · G 줄), bFauna = 동물 세계 판 (8 · 9 · J 줄). */
	TArray<FString> KeyHelpLines(bool bSites, bool bFauna = false);

	// 따라가기 거리·숙임·방위 — 옛 관찰 카메라 그대로 (EcoV3ObserverCamera.cpp:77-82, OBSERVER_CAMERA.md 4절 표). 멧돼지는 사슴 값을 쓴다
	inline constexpr float kFov = 70.0f;
	inline constexpr double kWolfDistCm = 1400.0, kWolfPitch = -20.0;
	inline constexpr double kDeerDistCm = 1100.0, kDeerPitch = -18.0;
	inline constexpr double kBoarDistCm = 1100.0, kBoarPitch = -18.0;
	inline constexpr double kTopDistCm = 4500.0, kTopPitch = -89.0;
	inline constexpr double kQuarterDistCm = 3000.0, kQuarterPitch = -45.0, kQuarterYaw = 45.0;
	inline constexpr double kAutoDistCm = 2400.0, kAutoPitch = -35.0, kAutoMaxCm = 12000.0;
	inline constexpr double kOverviewPitch = -40.0;
	inline constexpr double kMinZoom = 0.15, kMaxZoom = 8.0, kZoomStep = 1.2;

	/** 탑뷰 전체 높이: 한 변의 1.1 배가 세로 화면(16:9)에 드는 거리 (옛 FitTopCm). */
	double FitTopCm(double SizeCm);
	/** 섬 전체 보기 한 변 (옛 섬 무대 GatherRegions — 탑뷰가 세로로 맞추므로 가로는 16:9 몫으로 줄여 견준다). */
	double IslandViewSizeCm(double SizeXCm, double SizeYCm);

	/**
	 * 화면 가운데 대상 (자유 카메라에서 1~6 — 옛 EcoV3Observe::CenterSubject 와 같은 규칙): Eye 에서 Forward 쪽 MaxAngleDeg 안·MaxRangeCm 안 점 가운데
	 * 보는 방향과의 각이 가장 작은 것 (같으면 가까운 것, 그다음 Ids 가 작은 것). Points·Ids 는 같은 길이. 없으면 INDEX_NONE.
	 */
	int32 CenterPick(TConstArrayView<FVector> Points, TConstArrayView<uint32> Ids, const FVector& Eye, const FVector& Forward, double MaxAngleDeg, double MaxRangeCm);
}
