// R9 데모 플레이어 — 실시간 판 프레임 원천 (엔진 없음, 2026-11-12).
//
// 엔진 없는 R9 코어(EcoR9Core.h — 학습 세계 S′ 를 C++ 로 옮긴 것)를 한 스텝씩 돌려 FR9Frame(EcoR9DemoFrame.h)을 만든다.
// 화면 쪽은 코어를 직접 보지 않고 이 원천만 본다. 코어 API 가 바뀌면 EcoR9DemoLiveSource.cpp 한 파일만 맞춘다.
// 코어 헤더가 없는 빌드에서는 Available() 이 거짓이고 Init 이 '코어 없음' 으로 실패한다 (재생 판은 그대로 된다).

#pragma once

#include "EcoR9DemoFrame.h"

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace EcoR9Demo
{
	struct FR9LiveConfig
	{
		std::string ScenePath;      // 파이썬 장면 파일 (R9DUMP 1 의 @scene, py/dump_scene.py --decisions 0)
		std::string BrainDir;       // {deer,wolf,boar}.r9brain 이 있는 폴더 (export_brains.py)
		// 언리얼 쪽이 미리 읽어 넘기면 이것을 쓴다 (한글 경로도 되게). 비면 위 경로를 std::ifstream 으로 읽는다
		std::string SceneText;
		std::vector<std::uint8_t> BrainBytes[3];   // 사슴·늑대·멧돼지 차례
		std::uint64_t Seed = 1;     // 코어 난수 (물기 순서·다시 남·확률 뽑기)
		bool bSample = true;        // 참 = 확률대로 뽑기 (학습 때와 같음), 거짓 = 가장 높은 칸
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

		/** 장면·두뇌를 읽고 시작 장면 프레임까지 만든다. 실패하면 거짓과 까닭 (한국어 한 줄). */
		bool Init(const FR9LiveConfig& Config, FR9WorldInfo& OutInfo, FR9Frame& OutFirst, std::string& Err);

		/** 한 스텝(2/15 초) 진행하고 그 끝 상태를 Out 에 쓴다. 결정은 코어가 2 스텝마다 한다. */
		bool Next(FR9Frame& Out, std::string& Err);

		/** 지금까지 돈 스텝 수. */
		std::uint32_t Steps() const;

		struct FImpl;   // 코어를 감춘 속 (EcoR9DemoLiveSource.cpp)

	private:
		std::unique_ptr<FImpl> Impl;
	};
}
