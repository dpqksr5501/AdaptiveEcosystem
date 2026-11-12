// R9 데모 플레이어 — 실시간 판 프레임 원천 (엔진 없음, 2026-11-12).
//
// 엔진 없는 R9 코어(EcoR9Core.h — 학습 세계 S′ 를 C++ 로 옮긴 것)를 한 스텝씩 돌려 FR9Frame(EcoR9DemoFrame.h)을 만든다.
// 화면 쪽은 코어를 직접 보지 않고 이 원천만 본다. 코어 API 가 바뀌면 EcoR9DemoLiveSource.cpp 한 파일만 맞춘다.
// 코어 헤더가 없는 빌드에서는 Available() 이 거짓이고 Init 이 '코어 없음' 으로 실패한다 (재생 판은 그대로 된다).
//
// 맵 전체 땅 모드 (2026-11-13, CORE_API.md): Config.Whole 이 있으면 장면 파일(scene.txt)은 몸 표·상수만 쓰고(LoadParams), 언리얼이 훑은 땅 지도 위에
// 코어 큰 세계 장면 생성기(EcoR9Scene.h BuildBigScene)로 무리 자리·은신처·먹이·시작 개체를 만든다. 생성기가 없는 코어면 WholeAvailable() 거짓 →
// Init 이 까닭과 함께 실패하고, 화면 쪽은 예전 한 무대(120 m)로 돈다. 큰 세계는 먹이 격자가 커서 프레임에 격자를 싣지 않는다 — ReadFood 로 창만 읽는다.

#pragma once

#include "EcoR9DemoFrame.h"
#include "EcoR9DemoWhole.h"

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace EcoR9Demo
{
	/** 맵 전체 땅 모드 입력 (언리얼 훑기 → 코어 LandMap·BigSpec, CORE_API.md 1·2 절). 좌표는 모두 코어 단위·코어 칸 차례. */
	struct FR9WholeSpec
	{
		std::int32_t G = 0;                        // 땅 지도 한 변 칸 수 (코어 칸 = 2 단위 = 4 m)
		double CellUnits = 2.0;
		std::vector<std::uint8_t> Kind;            // G×G, iy·G + ix (ER9Land: 0 열림 · 1 물·땅 없음 · 2 가파름 · 3 나무·바위·건물)
		std::vector<double> Anchor;                // 은신처 곁 후보점 (x0, y0, x1, y1, …) — 나무 덩어리·큰 바위 가운데. 비면 코어가 장애물 칸을 씀
		std::vector<double> Sites;                 // 사람이 놓은 무리 자리 (x0, y0, …). 비면 코어가 고른다
		std::int32_t Herds = 6;                    // eco.R9Demo.Herds
		std::int32_t PerHerd[3] = {24, 2, 8};      // 자리마다 사슴·늑대·멧돼지 (eco.R9Demo.PerHerd)
		std::int32_t MaxAnimals = 400;             // 총수 상한
		double PrefX = -1.0;                       // 첫 무리 자리를 이 점 가까이 (플레이어 시작점, 코어 단위 — 음수 = 코어가 가장 트인 곳)
		double PrefY = -1.0;
	};

	struct FR9LiveConfig
	{
		std::string ScenePath;      // 파이썬 장면 파일 (R9DUMP 1 의 @scene, py/dump_scene.py --decisions 0)
		std::string BrainDir;       // {deer,wolf,boar}.r9brain 이 있는 폴더 (export_brains.py)
		// 언리얼 쪽이 미리 읽어 넘기면 이것을 쓴다 (한글 경로도 되게). 비면 위 경로를 std::ifstream 으로 읽는다
		std::string SceneText;
		std::vector<std::uint8_t> BrainBytes[3];   // 사슴·늑대·멧돼지 차례
		std::uint64_t Seed = 1;     // 코어 난수 (물기 순서·다시 남·확률 뽑기)
		bool bSample = true;        // 참 = 확률대로 뽑기 (학습 때와 같음), 거짓 = 가장 높은 칸
		std::shared_ptr<const FR9WholeSpec> Whole;   // 있으면 맵 전체 땅 모드 (큰 세계 장면 생성기)
	};

	class FR9LiveSource
	{
	public:
		FR9LiveSource();
		~FR9LiveSource();
		FR9LiveSource(const FR9LiveSource&) = delete;
		FR9LiveSource& operator=(const FR9LiveSource&) = delete;

		/** 이 빌드에 코어가 들어 있나. */
		static bool Available();
		/** 이 빌드의 코어에 큰 세계 장면 생성기(EcoR9Scene.h)가 있나 (맵 전체 땅 모드). */
		static bool WholeAvailable();

		/** 장면·두뇌를 읽고 시작 장면 프레임까지 만든다. 실패하면 거짓과 까닭 (한국어 한 줄). */
		bool Init(const FR9LiveConfig& Config, FR9WorldInfo& OutInfo, FR9Frame& OutFirst, std::string& Err);

		/** 한 스텝(2/15 초) 진행하고 그 끝 상태를 Out 에 쓴다. 결정은 코어가 2 스텝마다 한다. */
		bool Next(FR9Frame& Out, std::string& Err);

		/** 지금까지 돈 스텝 수. */
		std::uint32_t Steps() const;

		/**
		 * 먹이 창 읽기 (코어 칸 창 W — 지금 상태). Grass·Root 는 W.Nx × W.Ny (창 안 행 우선). 큰 세계는 프레임에 격자를 싣지 않으므로 이것으로 읽는다.
		 * 창이 격자 밖이면 그 칸은 0.
		 */
		bool ReadFood(const FR9FoodWindow& W, std::vector<float>& Grass, std::vector<float>& Root) const;
		/** 땅 칸 (코어 칸) 이 막혔나 — 큰 세계 땅 지도 (작은 세계·격자 밖 = 거짓). */
		bool IsBlockedCell(std::int32_t Ix, std::int32_t Iy) const;
		/** 마지막 결정 계산 비용 한 줄 (관측·두뇌·스텝 ms, 이웃 비교 수 — 코어 LastCost). 모르면 빈 글. */
		std::string CostLine() const;
		/**
		 * 확인용 (11-13 빌드·확인): 지금까지 스텝 끝마다 센 '막힌 칸 위에 선 산 개체' 수와 센 산 개체-스텝 수 (코어 World::IsBlockedAt — double 좌표).
		 * 큰 세계(막힌 칸 있음)에서만 센다. 읽기만 — 규칙·난수에 손대지 않는다.
		 */
		void OnBlockedStats(std::int64_t& OutOnBlocked, std::int64_t& OutAgentSteps) const;

		struct FImpl;   // 코어를 감춘 속 (EcoR9DemoLiveSource.cpp)

	private:
		std::unique_ptr<FImpl> Impl;
	};
}
