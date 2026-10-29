// 관찰 카메라 (10-27 '카메라가 느려 행동 관찰이 어렵다 → 늑대 시점·사슴 시점·탑·쿼터뷰 단축키') — 순수 함수와 논리 개체 찾기.
//
// 보는 것:
//   - 단축키 표: 설계 키(1~5·0·, .·- =·휠·G·H)가 맞고 팀·기본 입력 키(Tab·R·M·[ ]·마우스 가운데·F·Shift·Ctrl·WASD·Space·방향키)와 겹치지 않는다.
//   - 대상 고르기: 다음/이전(id 차례·감김·죽은 개체 빼기), 가장 가까운 개체(사건 먼저·같으면 id 작은 것),
//     자동 추적(쫓기는 사슴 > 사냥 늑대 > 도망 사슴, 방금 끝난 대상은 다른 후보가 없을 때만), 지역 고르기.
//   - 오른쪽 위 묶음 배치: 팀 HERD MIGRATION 판 밑·옆, 팀 ECO INSPECTOR 판 오른쪽, 1280×720~4K 화면 안.
//   - 부드러운 따라가기: 넘침 없음, 큰 프레임에도 안정, 앞보기를 더하면 9 m/s 대상도 뒤처지지 않음, 각도는 짧은 쪽.
//   - 논리 개체 찾기(Gather): 표현 액터 없이 600 m 떨어진 개체도 찾는다(촬영 감독 wolf·deer 가 대상을 못 찾던 원인),
//     클라이언트 표본이 없는 개체는 빼고 표본이 있으면 그 자리. 서브시스템 흐름(로컬 플레이어 없이): 1·1·, .·2·3·지역·5·0.
//   - 관찰 중 플레이어 이동 입력 막기(10-27 사용자 결정): 원래 카메라 = 안 막음, 1~5 = 막음(폰 이동 입력이 0), 다시 맞춰도 한 번만 더함,
//     엔진이 지우면(ResetIgnoreInputFlags) 다시 막음, eco.Cam.BlockMove 0 = 풀림, 0 = 풀림, 팀이 건 막기는 남김, 컨트롤러가 바뀌면 전 것을 풂.
//   - 자유 카메라(10-29 사용자 '0 을 누르면 그 자리에서 추적이 풀려 바로 직접 움직이게'): 키 입력(W A S D·방향키·Q E), 한 프레임 이동(보는 방향 앞뒤·가로 옆·
//     세계 위, 넘침 없음·부드럽게 섬), 마우스 시야(컨트롤러 방향이 바뀐 양), 화면 가운데 대상, 서브시스템 흐름(1 → 0 자유 카메라(막기 그대로) → 2 화면 가운데 사슴
//     → 0 → 0 원래 카메라(풀림) → 0 아무 일 없음 → eco.Cam.Free → 1 화면 가운데 늑대 → G 지역 → 2, 속도 - =).
// 문서: AdaptiveEcosystem/Docs/RL_Policy/OBSERVER_CAMERA.md

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoV3ObserverCamera.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "EcoTestWorld.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "InputCoreTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassPresentationFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"

namespace EcoV3ObserverCameraTestImpl
{
	using EcoV3Observe::EState;
	using EcoV3Observe::FSubject;

	// 순수 함수 장면의 id (지역 A·B·C)
	constexpr int64 kWolfA1 = 1;       // A 사냥 늑대 (0, 0)
	constexpr int64 kWolfA2 = 2;       // A 배회 늑대 (100 m, 0)
	constexpr int64 kDeerChased = 3;   // A 도망 사슴 — 사냥 늑대 10 m
	constexpr int64 kDeerFar = 4;      // A 도망 사슴 — 배회 늑대 10 m, 사냥 늑대 90 m
	constexpr int64 kDeerEat = 5;      // A 먹는 사슴 — 늑대 1 곁 7.07 m
	constexpr int64 kDeerB = 6;        // B 도망(트인 쪽) 사슴 — 사냥 늑대 5 m
	constexpr int64 kWolfB = 7;        // B 사냥 늑대
	constexpr int64 kDeerC = 8;        // C 도망 사슴 — 배회 늑대 8 m (사냥 늑대 없음)
	constexpr int64 kWolfC = 9;        // C 배회 늑대
	constexpr int64 kDeerHide = 10;    // A 숨으러 가는 사슴
	constexpr int64 kDeerDead = 11;    // A 죽은 사슴 — 늑대 1 곁 4 m (이웃·대상에서 빠져야 한다)

	FSubject MakeSubject(int64 Id, bool bWolf, FName RegionId, double X, double Y, EState State, bool bAlive = true)
	{
		FSubject S;
		S.Id = Id;
		S.bWolf = bWolf;
		S.Region = RegionId;
		S.Location = FVector(X, Y, 0.0);
		S.bAlive = bAlive;
		S.State = bAlive ? State : EState::Dead;
		return S;
	}

	/** 색인의 id (INDEX_NONE 이면 -1). */
	int64 IdAt(TConstArrayView<FSubject> List, int32 Index)
	{
		return List.IsValidIndex(Index) ? List[Index].Id : -1;
	}

	/** 순수 함수 장면. 일부러 id 차례가 아니게 넣는다 (고르기가 id 차례를 스스로 지키는지 본다). */
	TArray<FSubject> MakeScene()
	{
		const FName RegionA(TEXT("A")), RegionB(TEXT("B")), RegionC(TEXT("C"));
		TArray<FSubject> Out = {
			MakeSubject(kDeerHide, false, RegionA, 300.0, 9000.0, EState::Hide),
			MakeSubject(kWolfA2, true, RegionA, 10000.0, 0.0, EState::Roam),
			MakeSubject(kWolfB, true, RegionB, 100500.0, 0.0, EState::Hunt),
			MakeSubject(kWolfA1, true, RegionA, 0.0, 0.0, EState::Hunt),
			MakeSubject(kDeerEat, false, RegionA, 500.0, 500.0, EState::Eat),
			MakeSubject(kDeerChased, false, RegionA, 1000.0, 0.0, EState::Flee),
			MakeSubject(kDeerDead, false, RegionA, 400.0, 0.0, EState::Eat, false),
			MakeSubject(kWolfC, true, RegionC, 0.0, 50800.0, EState::Roam),
			MakeSubject(kDeerFar, false, RegionA, 9000.0, 0.0, EState::Flee),
			MakeSubject(kDeerB, false, RegionB, 100000.0, 0.0, EState::FleeOpen),
			MakeSubject(kDeerC, false, RegionC, 0.0, 50000.0, EState::Flee),
		};
		EcoV3Observe::FillNeighbors(Out);
		return Out;
	}

	EcoV3Observe::FRegionInfo MakeRegion(const TCHAR* Name, double X, double Y, double SizeCm, bool bStage)
	{
		EcoV3Observe::FRegionInfo R;
		R.Id = FName(Name);
		R.CenterCm = FVector(X, Y, 0.0);
		R.SizeCm = SizeCm;
		R.bStage = bStage;
		return R;
	}
}

// -----------------------------------------------------------------------------
// 단축키 표
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3ObserverCameraKeysTest, "AdaptiveEcosystem.Policy.V3.ObserverCamera.Keys",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ObserverCameraKeysTest::RunTest(const FString& Parameters)
{
	using EcoV3Observe::EAction;
	using EcoV3Observe::FKeyBind;
	const TConstArrayView<FKeyBind> Binds = EcoV3Observe::Keys();
	const TConstArrayView<FKey> Reserved = EcoV3Observe::TeamReservedKeys();
	TestTrue(TEXT("단축키 표가 있다"), Binds.Num() > 0);
	TestTrue(TEXT("팀 키 표가 있다"), Reserved.Num() > 0);

	// 1. 팀·기본 입력 키와 겹치지 않는다
	for (const FKeyBind& Bind : Binds)
	{
		TestFalse(FString::Printf(TEXT("%s 는 팀·기본 입력 키와 겹치지 않는다"), *Bind.Key.ToString()), Reserved.Contains(Bind.Key));
	}
	// 2. 한 키는 한 동작
	for (int32 i = 0; i < Binds.Num(); ++i)
	{
		for (int32 j = i + 1; j < Binds.Num(); ++j)
		{
			if (Binds[i].Key == Binds[j].Key)
			{
				AddError(FString::Printf(TEXT("키 %s 가 두 번 묶였다"), *Binds[i].Key.ToString()));
			}
		}
	}
	// 3. 모든 동작에 키가 있다
	for (uint8 Raw = 0; Raw <= static_cast<uint8>(EAction::Help); ++Raw)
	{
		const EAction Want = static_cast<EAction>(Raw);
		TestTrue(FString::Printf(TEXT("동작 %d 에 키가 있다"), static_cast<int32>(Raw)),
				 Binds.ContainsByPredicate([Want](const FKeyBind& Candidate) { return Candidate.Action == Want; }));
	}
	// 4. 설계 키 (헤더 머리말 · OBSERVER_CAMERA.md 키 표)
	auto ActionOf = [&Binds](const FKey& Key) -> int32
	{
		for (const FKeyBind& Candidate : Binds)
		{
			if (Candidate.Key == Key)
			{
				return static_cast<int32>(Candidate.Action);
			}
		}
		return -1;
	};
	struct FDesignKey
	{
		FKey Key;
		EAction Action;
		const TCHAR* Label;
	};
	const FDesignKey Design[] = {
		{EKeys::One, EAction::Wolf, TEXT("1 = 늑대 시점")},
		{EKeys::Two, EAction::Deer, TEXT("2 = 사슴 시점")},
		{EKeys::Three, EAction::Top, TEXT("3 = 탑뷰")},
		{EKeys::Four, EAction::Quarter, TEXT("4 = 쿼터뷰")},
		{EKeys::Five, EAction::Auto, TEXT("5 = 자동 추적")},
		{EKeys::Zero, EAction::Player, TEXT("0 = 원래 카메라")},
		{EKeys::Comma, EAction::Prev, TEXT(", = 이전 대상")},
		{EKeys::Period, EAction::Next, TEXT(". = 다음 대상")},
		{EKeys::Hyphen, EAction::ZoomOut, TEXT("- = 멀리")},
		{EKeys::Equals, EAction::ZoomIn, TEXT("= = 가까이")},
		{EKeys::MouseScrollDown, EAction::ZoomOut, TEXT("휠 아래 = 멀리")},
		{EKeys::MouseScrollUp, EAction::ZoomIn, TEXT("휠 위 = 가까이")},
		{EKeys::G, EAction::Region, TEXT("G = 지역 바꾸기")},
		{EKeys::H, EAction::Help, TEXT("H = 단축키 목록 숨기기/보이기")},
		{EKeys::NumPadOne, EAction::Wolf, TEXT("숫자패드 1 = 늑대 시점")},
	};
	for (const FDesignKey& Row : Design)
	{
		TestEqual(Row.Label, ActionOf(Row.Key), static_cast<int32>(Row.Action));
	}
	// 5. 화면 단축키 줄에 키가 모두 적혀 있다 (H 는 맨 윗줄 제목에 따로 있다)
	const FString Joined = FString::Join(EcoV3Observe::KeyHelpLines(), TEXT("\n"));
	for (const TCHAR* Token : {TEXT("1"), TEXT("2"), TEXT("3"), TEXT("4"), TEXT("5"), TEXT(","), TEXT("."), TEXT("-"), TEXT("="), TEXT("휠"), TEXT("G"),
							   TEXT("0")})
	{
		TestTrue(FString::Printf(TEXT("단축키 줄에 '%s' 가 있다"), Token), Joined.Contains(Token));
	}
	// 6. 콘솔 명령·변수가 있다
	for (const TCHAR* Name : {TEXT("eco.Cam.Wolf"), TEXT("eco.Cam.Deer"), TEXT("eco.Cam.Top"), TEXT("eco.Cam.Quarter"), TEXT("eco.Cam.Auto"),
							  TEXT("eco.Cam.Next"), TEXT("eco.Cam.Prev"), TEXT("eco.Cam.Zoom"), TEXT("eco.Cam.Region"), TEXT("eco.Cam.Player"),
							  TEXT("eco.Cam.Help"), TEXT("eco.Cam.Enable"), TEXT("eco.Cam.HudScale"), TEXT("eco.Cam.BlockMove"), TEXT("eco.Cam.Free"),
							  TEXT("eco.Cam.Speed"), TEXT("eco.Cam.Status")})
	{
		TestNotNull(*FString::Printf(TEXT("콘솔 %s"), Name), IConsoleManager::Get().FindConsoleObject(Name));
	}
	// 7. 자유 카메라 키 (10-29): 위아래 Q·E 는 팀·기본 입력 키도 단축키도 아니다 (Space = 점프·Ctrl = 살금살금은 팀 키라 쓰지 않았다).
	//    W A S D·방향키·Shift 는 팀 키지만 자유 카메라에서만 누른 채로 읽는다 (그때는 폰 이동 입력이 막혀 있다)
	for (const FKey& Key : {EKeys::Q, EKeys::E})
	{
		TestFalse(FString::Printf(TEXT("자유 카메라 %s 는 팀·기본 입력 키가 아니다"), *Key.ToString()), Reserved.Contains(Key));
		TestEqual(*FString::Printf(TEXT("자유 카메라 %s 는 단축키가 아니다"), *Key.ToString()), ActionOf(Key), -1);
	}
	auto FreeAxisOf = [](const FKey& Key) -> FVector
	{
		for (const EcoV3Observe::FFreeKey& K : EcoV3Observe::FreeMoveKeys())
		{
			if (K.Key == Key)
			{
				return K.Axis;
			}
		}
		return FVector(99.0);
	};
	TestEqual(TEXT("W = 앞"), FreeAxisOf(EKeys::W), FVector(1.0, 0.0, 0.0));
	TestEqual(TEXT("S = 뒤"), FreeAxisOf(EKeys::S), FVector(-1.0, 0.0, 0.0));
	TestEqual(TEXT("D = 오른쪽"), FreeAxisOf(EKeys::D), FVector(0.0, 1.0, 0.0));
	TestEqual(TEXT("A = 왼쪽"), FreeAxisOf(EKeys::A), FVector(0.0, -1.0, 0.0));
	TestEqual(TEXT("E = 위"), FreeAxisOf(EKeys::E), FVector(0.0, 0.0, 1.0));
	TestEqual(TEXT("Q = 아래"), FreeAxisOf(EKeys::Q), FVector(0.0, 0.0, -1.0));
	TestTrue(TEXT("Shift = 빠르게"), EcoV3Observe::FreeFastKeys().Contains(EKeys::LeftShift));
	for (const FKey& Key : {EKeys::SpaceBar, EKeys::LeftControl, EKeys::F})
	{
		TestEqual(*FString::Printf(TEXT("%s (팀 점프·살금살금·치기) 는 자유 카메라 이동 키가 아니다"), *Key.ToString()), FreeAxisOf(Key), FVector(99.0));
	}
	for (const TCHAR* Token : {TEXT("자유 카메라"), TEXT("W A S D"), TEXT("Q E"), TEXT("Shift"), TEXT("마우스"), TEXT("다시 0")})
	{
		TestTrue(FString::Printf(TEXT("단축키 줄에 '%s' 가 있다"), Token), Joined.Contains(Token));
	}
	return true;
}

// -----------------------------------------------------------------------------
// 대상 고르기 (이웃·다음/이전·가장 가까운·자동 추적·지역)
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3ObserverCameraPickTest, "AdaptiveEcosystem.Policy.V3.ObserverCamera.Pick",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ObserverCameraPickTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3ObserverCameraTestImpl;
	const TArray<FSubject> Scene = MakeScene();
	const FName RegionA(TEXT("A")), RegionB(TEXT("B")), RegionC(TEXT("C")), RegionZ(TEXT("Z"));
	auto Get = [&Scene](int64 Id) -> const FSubject*
	{
		const int32 Index = EcoV3Observe::FindIndex(Scene, Id);
		return Scene.IsValidIndex(Index) ? &Scene[Index] : nullptr;
	};
	const FSubject* Wolf1 = Get(kWolfA1);
	const FSubject* Wolf2 = Get(kWolfA2);
	const FSubject* Chased = Get(kDeerChased);
	const FSubject* Far = Get(kDeerFar);
	const FSubject* DeerB = Get(kDeerB);
	const FSubject* Dead = Get(kDeerDead);
	const FSubject* Hiding = Get(kDeerHide);
	const FSubject* Eating = Get(kDeerEat);
	if (!TestNotNull(TEXT("늑대 1"), Wolf1) || !TestNotNull(TEXT("늑대 2"), Wolf2) || !TestNotNull(TEXT("쫓기는 사슴"), Chased)
		|| !TestNotNull(TEXT("먼 사슴"), Far) || !TestNotNull(TEXT("B 사슴"), DeerB) || !TestNotNull(TEXT("죽은 사슴"), Dead)
		|| !TestNotNull(TEXT("숨는 사슴"), Hiding) || !TestNotNull(TEXT("먹는 사슴"), Eating))
	{
		return false;
	}
	TestEqual(TEXT("FindIndex: 없는 id"), EcoV3Observe::FindIndex(Scene, 99), static_cast<int32>(INDEX_NONE));
	TestEqual(TEXT("FindIndex: 0 은 대상 없음"), EcoV3Observe::FindIndex(Scene, 0), static_cast<int32>(INDEX_NONE));

	// 이웃 (같은 지역·산 개체만)
	TestEqual(TEXT("쫓기는 사슴의 사냥 늑대"), Chased->NearestHuntWolfId, kWolfA1);
	TestEqual(TEXT("쫓기는 사슴의 사냥 늑대 거리"), Chased->NearestHuntWolfCm, 1000.0, 0.01);
	TestEqual(TEXT("먼 사슴의 가장 가까운 늑대 = 배회 늑대"), Far->NearestWolfId, kWolfA2);
	TestEqual(TEXT("먼 사슴의 사냥 늑대는 따로 (90 m)"), Far->NearestHuntWolfCm, 9000.0, 0.01);
	TestEqual(TEXT("늑대 1 의 가장 가까운 사슴 (죽은 사슴 4 m 는 빼고 7.07 m)"), Wolf1->NearestDeerId, kDeerEat);
	TestEqual(TEXT("다른 지역 늑대는 이웃이 아니다"), DeerB->NearestWolfId, kWolfB);
	TestEqual(TEXT("죽은 사슴은 이웃이 없다"), Dead->NearestWolfCm, -1.0, 0.0);

	// 다음·이전 (id 차례, 감김, 죽은 개체 빼기)
	TestEqual(TEXT("다음 늑대 1 → 2"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, true, RegionA, kWolfA1, +1)), kWolfA2);
	TestEqual(TEXT("다음 늑대 2 → 1 (감김)"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, true, RegionA, kWolfA2, +1)), kWolfA1);
	TestEqual(TEXT("이전 늑대 1 → 2 (감김)"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, true, RegionA, kWolfA1, -1)), kWolfA2);
	TestEqual(TEXT("목록에 없는 대상 + 다음 = 첫째"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, true, RegionA, 99, +1)), kWolfA1);
	TestEqual(TEXT("목록에 없는 대상 + 이전 = 마지막"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, true, RegionA, 99, -1)), kWolfA2);
	TestEqual(TEXT("모든 지역: 늑대 2 → 7"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, true, NAME_None, kWolfA2, +1)), kWolfB);
	TestEqual(TEXT("모든 지역: 늑대 9 → 1 (감김)"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, true, NAME_None, kWolfC, +1)), kWolfA1);
	TestEqual(TEXT("사슴 5 → 10"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, false, RegionA, kDeerEat, +1)), kDeerHide);
	TestEqual(TEXT("사슴 10 → 3 (죽은 11 은 건너뜀)"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, false, RegionA, kDeerHide, +1)), kDeerChased);
	TestEqual(TEXT("사슴 3 → 10 (이전, 감김)"), IdAt(Scene, EcoV3Observe::CycleSubject(Scene, false, RegionA, kDeerChased, -1)), kDeerHide);
	TestEqual(TEXT("없는 지역은 고를 것이 없다"), EcoV3Observe::CycleSubject(Scene, true, RegionZ, 0, +1), static_cast<int32>(INDEX_NONE));

	// 가장 가까운 개체
	TestEqual(TEXT("사건 먼저: 사냥 늑대가 멀어도 먼저"),
			  IdAt(Scene, EcoV3Observe::NearestSubject(Scene, true, RegionA, FVector(9500.0, 0.0, 0.0), true)), kWolfA1);
	TestEqual(TEXT("사건 무시: 가까운 배회 늑대"),
			  IdAt(Scene, EcoV3Observe::NearestSubject(Scene, true, RegionA, FVector(9500.0, 0.0, 0.0), false)), kWolfA2);
	TestEqual(TEXT("사건 먼저: 도망 사슴"), IdAt(Scene, EcoV3Observe::NearestSubject(Scene, false, RegionA, FVector::ZeroVector, true)), kDeerChased);
	TestEqual(TEXT("죽은 사슴(4 m)은 빼고 가장 가까운 사슴(7.07 m)"),
			  IdAt(Scene, EcoV3Observe::NearestSubject(Scene, false, RegionA, FVector::ZeroVector, false)), kDeerEat);
	TestEqual(TEXT("거리가 같으면 id 가 작은 것"),
			  IdAt(Scene, EcoV3Observe::NearestSubject(Scene, false, RegionA, FVector(750.0, 250.0, 0.0), false)), kDeerChased);
	TestEqual(TEXT("모든 지역: 가까운 사냥 늑대"),
			  IdAt(Scene, EcoV3Observe::NearestSubject(Scene, true, NAME_None, FVector(100000.0, 0.0, 0.0), true)), kWolfB);
	TestEqual(TEXT("없는 지역"), EcoV3Observe::NearestSubject(Scene, true, RegionZ, FVector::ZeroVector, true), static_cast<int32>(INDEX_NONE));

	// 사건·짝
	TestTrue(TEXT("숨으러 가는 사슴은 사건"), EcoV3Observe::IsEvent(*Hiding));
	TestFalse(TEXT("먹는 사슴은 사건이 아니다"), EcoV3Observe::IsEvent(*Eating));
	TestTrue(TEXT("사냥 늑대는 사건"), EcoV3Observe::IsEvent(*Wolf1));
	TestFalse(TEXT("배회 늑대는 사건이 아니다"), EcoV3Observe::IsEvent(*Wolf2));
	TestFalse(TEXT("죽은 개체는 사건이 아니다"), EcoV3Observe::IsEvent(*Dead));
	TestEqual(TEXT("늑대 짝 = 가장 가까운 사슴"), EcoV3Observe::PartnerOf(*Wolf1, EcoV3Observe::kAutoPairCm), kDeerEat);
	TestEqual(TEXT("짝 거리 밖이면 0"), EcoV3Observe::PartnerOf(*Wolf2, 500.0), static_cast<int64>(0));
	TestEqual(TEXT("사슴 짝: 사냥 늑대가 멀면 가까운 늑대"), EcoV3Observe::PartnerOf(*Far, EcoV3Observe::kAutoPairCm), kWolfA2);
	TestEqual(TEXT("사슴 짝: 사냥 늑대"), EcoV3Observe::PartnerOf(*Chased, EcoV3Observe::kAutoPairCm), kWolfA1);

	// 자동 추적
	struct FAutoCase
	{
		const TCHAR* Label;
		FName Region;
		bool bRegionOnly;
		int64 Exclude;
		int64 WantId;       // -1 = 없음
		int64 WantPartner;
	};
	const FAutoCase Cases[] = {
		{TEXT("A: 쫓기는 사슴 (사냥 늑대 10 m) 이 먼저"), RegionA, true, 0, kDeerChased, kWolfA1},
		{TEXT("A: 쫓기는 사슴이 방금 끝났으면 사냥 늑대 (짝 = 가까운 사슴)"), RegionA, true, kDeerChased, kWolfA1, kDeerEat},
		{TEXT("모든 지역: 쫓는 늑대가 가장 가까운 사슴 (B, 5 m)"), NAME_None, false, 0, kDeerB, kWolfB},
		{TEXT("A 를 먼저 본다"), RegionA, false, 0, kDeerChased, kWolfA1},
		{TEXT("B: 쫓기는 사슴이 끝났으면 그 늑대"), RegionB, true, kDeerB, kWolfB, kDeerB},
		{TEXT("C: 다른 후보가 없으면 방금 끝난 대상도 (도망 사슴, 짝 = 배회 늑대)"), RegionC, true, kDeerC, kDeerC, kWolfC},
		{TEXT("Z 만: 없음"), RegionZ, true, 0, -1, 0},
		{TEXT("Z 먼저, 없으면 모든 지역"), RegionZ, false, 0, kDeerB, kWolfB},
	};
	for (const FAutoCase& Case : Cases)
	{
		int64 Partner = -1;
		const int32 Index = EcoV3Observe::PickAuto(Scene, Case.Region, Case.bRegionOnly, Case.Exclude, Partner);
		TestEqual(*FString::Printf(TEXT("자동 추적 %s — 대상"), Case.Label), IdAt(Scene, Index), Case.WantId);
		TestEqual(*FString::Printf(TEXT("자동 추적 %s — 짝"), Case.Label), Partner, Case.WantPartner);
	}

	// 지역 고르기
	const TArray<EcoV3Observe::FRegionInfo> Regions = {
		MakeRegion(TEXT("A"), 0.0, 0.0, 10000.0, true),
		MakeRegion(TEXT("B"), 20000.0, 0.0, 10000.0, true),
		MakeRegion(TEXT("C"), 0.0, 50000.0, 6000.0, false),
	};
	TestEqual(TEXT("무대 A 안"), EcoV3Observe::RegionAt(Regions, FVector(4000.0, 4000.0, 0.0)), RegionA);
	TestEqual(TEXT("무대 B 안"), EcoV3Observe::RegionAt(Regions, FVector(16000.0, 0.0, 0.0)), RegionB);
	TestEqual(TEXT("무대 밖은 중심이 가장 가까운 지역"), EcoV3Observe::RegionAt(Regions, FVector(0.0, 40000.0, 0.0)), RegionC);
	TestEqual(TEXT("두 무대 사이는 가까운 중심"), EcoV3Observe::RegionAt(Regions, FVector(9000.0, 0.0, 0.0)), RegionA);
	TestEqual(TEXT("다음 지역 A → B"), EcoV3Observe::CycleRegion(Regions, RegionA, +1), RegionB);
	TestEqual(TEXT("다음 지역 C → A (감김)"), EcoV3Observe::CycleRegion(Regions, RegionC, +1), RegionA);
	TestEqual(TEXT("앞 지역 A → C (감김)"), EcoV3Observe::CycleRegion(Regions, RegionA, -1), RegionC);
	TestEqual(TEXT("모르는 지역이면 첫째"), EcoV3Observe::CycleRegion(Regions, RegionZ, +1), RegionA);
	TestEqual(TEXT("지역이 없으면 None"), EcoV3Observe::CycleRegion(TConstArrayView<EcoV3Observe::FRegionInfo>(), RegionA, +1), FName(NAME_None));
	return true;
}

// -----------------------------------------------------------------------------
// 오른쪽 위 묶음 배치
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3ObserverCameraLayoutTest, "AdaptiveEcosystem.Policy.V3.ObserverCamera.PanelLayout",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ObserverCameraLayoutTest::RunTest(const FString& Parameters)
{
	using EcoV3Observe::FPanelLayout;
	using EcoV3Observe::LayoutPanel;
	using EcoV3Observe::TeamMigrationPanelRect;
	const double LeftLimit = EcoV3Observe::kTeamInspectorRightPx + EcoV3Observe::kPanelGap;   // 663

	// 팀 HERD MIGRATION 판 (EcoHerdMigrationDebug::Draw 와 같은 셈)
	const FBox2D Team1080 = TeamMigrationPanelRect(FVector2D(1920.0, 1080.0));
	TestEqual(TEXT("팀 판 1080p 왼쪽 (너비 430 상한)"), Team1080.Min.X, 1474.0, 0.01);
	TestEqual(TEXT("팀 판 1080p 위"), Team1080.Min.Y, 16.0, 0.01);
	TestEqual(TEXT("팀 판 1080p 오른쪽"), Team1080.Max.X, 1904.0, 0.01);
	TestEqual(TEXT("팀 판 1080p 아래 (높이 376)"), Team1080.Max.Y, 392.0, 0.01);
	TestEqual(TEXT("팀 판 800 너비 하한 300"), TeamMigrationPanelRect(FVector2D(800.0, 600.0)).Min.X, 484.0, 0.01);
	const FBox2D Team720 = TeamMigrationPanelRect(FVector2D(1280.0, 720.0));
	TestEqual(TEXT("팀 판 720p 왼쪽 (화면 32%)"), Team720.Min.X, 854.4, 0.01);

	// 1. 팀 판 없음: 오른쪽 위 16 px, 바라는 배율
	{
		const FPanelLayout L = LayoutPanel(FVector2D(1920.0, 1080.0), FVector2D(300.0, 250.0), 1.7f, nullptr);
		TestEqual(TEXT("1080p 배율"), L.Scale, 1.7f, 0.001f);
		TestEqual(TEXT("1080p 오른쪽 16 px"), L.X, 1394.0f, 0.01f);
		TestEqual(TEXT("1080p 위 16 px"), L.Y, 16.0f, 0.01f);
		TestFalse(TEXT("옆이 아니다"), L.bBeside);
	}
	// 2. 팀 판 있음: 그 밑
	{
		const FPanelLayout L = LayoutPanel(FVector2D(1920.0, 1080.0), FVector2D(300.0, 250.0), 1.7f, &Team1080);
		TestEqual(TEXT("팀 판 밑 (392 + 8)"), L.Y, 400.0f, 0.01f);
		TestEqual(TEXT("팀 판 밑 배율 그대로"), L.Scale, 1.7f, 0.001f);
		TestEqual(TEXT("팀 판 밑 오른쪽"), L.X, 1394.0f, 0.01f);
	}
	// 3. 720p 팀 판 밑: 남은 높이에 맞춰 줄인다
	{
		const FPanelLayout L = LayoutPanel(FVector2D(1280.0, 720.0), FVector2D(300.0, 400.0), 1.15f, &Team720);
		TestEqual(TEXT("720p 팀 판 밑 배율 = 304 / 400"), L.Scale, 0.76f, 0.001f);
		TestEqual(TEXT("720p 팀 판 밑 위"), L.Y, 400.0f, 0.01f);
		TestEqual(TEXT("720p 팀 판 밑 오른쪽"), L.X, 1036.0f, 0.05f);
	}
	// 4. 밑에 안 들면 팀 판 왼쪽 옆 (검사 판 오른쪽 안)
	{
		const FPanelLayout L = LayoutPanel(FVector2D(1280.0, 720.0), FVector2D(300.0, 700.0), 1.15f, &Team720);
		TestTrue(TEXT("팀 판 왼쪽 옆"), L.bBeside);
		TestEqual(TEXT("옆 위 16 px"), L.Y, 16.0f, 0.01f);
		TestEqual(TEXT("옆 배율 = 183.4 / 300"), L.Scale, 0.611333f, 0.001f);
		TestTrue(TEXT("옆 오른쪽 끝은 팀 판 앞 8 px"), L.X + 300.0f * L.Scale <= static_cast<float>(Team720.Min.X) - EcoV3Observe::kPanelGap + 0.05f);
		TestTrue(TEXT("옆 왼쪽 끝은 검사 판 오른쪽"), L.X >= static_cast<float>(LeftLimit) - 0.05f);
	}
	// 5. 그래도 안 들면 0.55 배로 화면 안
	{
		const FPanelLayout L = LayoutPanel(FVector2D(1280.0, 720.0), FVector2D(600.0, 900.0), 1.15f, &Team720);
		TestEqual(TEXT("가장 작은 배율"), L.Scale, EcoV3Observe::kPanelMinScale, 0.0001f);
		TestEqual(TEXT("화면 안 오른쪽"), L.X, 934.0f, 0.05f);
		TestEqual(TEXT("화면 안 아래 (720 − 16 − 495)"), L.Y, 209.0f, 0.05f);
	}
	// 6. 팀 판이 없어도 왼쪽 위 ECO INSPECTOR 판(x ~655)을 넘지 않는다
	{
		const FPanelLayout L = LayoutPanel(FVector2D(1280.0, 720.0), FVector2D(400.0, 200.0), 1.6f, nullptr);
		TestEqual(TEXT("검사 판 오른쪽으로 너비를 줄인다 (601 / 400)"), L.Scale, 1.5025f, 0.001f);
		TestTrue(TEXT("검사 판과 겹치지 않는다"), L.X >= static_cast<float>(LeftLimit) - 0.05f);
	}
	// 7. 묶음 크기가 없으면 기본값
	{
		const FPanelLayout L = LayoutPanel(FVector2D(1280.0, 720.0), FVector2D(0.0, 0.0), 1.0f, nullptr);
		TestEqual(TEXT("빈 묶음 배율 1"), L.Scale, 1.0f, 0.0f);
	}
	// 8. 흔한 화면·묶음 크기: 화면 안, 검사 판 오른쪽, 팀 판과 겹치지 않음 (DrawPanel 과 같은 바라는 배율 = 화면 높이 / 720 × 1.15, 1~2.4)
	const FVector2D Screens[] = {FVector2D(1280.0, 720.0),	FVector2D(1366.0, 768.0),	FVector2D(1600.0, 900.0),
								 FVector2D(1920.0, 1080.0), FVector2D(2560.0, 1440.0), FVector2D(3840.0, 2160.0)};
	const FVector2D Contents[] = {FVector2D(320.0, 260.0), FVector2D(380.0, 330.0), FVector2D(420.0, 380.0)};
	for (const FVector2D& Screen : Screens)
	{
		const float Base = FMath::Clamp(static_cast<float>(Screen.Y) / 720.0f * 1.15f, 1.0f, 2.4f);
		const FBox2D TeamRect = TeamMigrationPanelRect(Screen);
		for (const FVector2D& Content : Contents)
		{
			for (const bool bTeam : {false, true})
			{
				const FPanelLayout L = LayoutPanel(Screen, Content, Base, bTeam ? &TeamRect : nullptr);
				const double Left = L.X;
				const double Right = L.X + Content.X * L.Scale;
				const double TopY = L.Y;
				const double Bottom = L.Y + Content.Y * L.Scale;
				const FString Where = FString::Printf(TEXT("%.0fx%.0f 묶음 %.0fx%.0f 팀 판 %d"), Screen.X, Screen.Y, Content.X, Content.Y, bTeam ? 1 : 0);
				TestTrue(Where + TEXT(": 화면 안"), Left >= 0.0 && TopY >= 0.0 && Right <= Screen.X - EcoV3Observe::kPanelMargin + 0.5 && Bottom <= Screen.Y + 0.5);
				TestTrue(Where + TEXT(": 검사 판 오른쪽"), Left >= LeftLimit - 0.5);
				TestTrue(Where + TEXT(": 배율 0.55 이상"), L.Scale >= EcoV3Observe::kPanelMinScale - 0.0001f);
				if (bTeam)
				{
					const bool bOverlap = !(Right <= TeamRect.Min.X + 0.01 || Left >= TeamRect.Max.X - 0.01 || Bottom <= TeamRect.Min.Y + 0.01
											|| TopY >= TeamRect.Max.Y - 0.01);
					TestFalse(Where + TEXT(": 팀 판과 겹치지 않는다"), bOverlap);
				}
			}
		}
	}
	return true;
}

// -----------------------------------------------------------------------------
// 부드러운 따라가기
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3ObserverCameraSmoothTest, "AdaptiveEcosystem.Policy.V3.ObserverCamera.SmoothFollow",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ObserverCameraSmoothTest::RunTest(const FString& Parameters)
{
	constexpr double FrameDt = 1.0 / 60.0;
	// 1. 계단 목표: 넘치지 않고 되돌지 않으며 3 초 안에 닿는다
	{
		double Value = 0.0, Vel = 0.0, Highest = 0.0, Prev = 0.0;
		bool bMonotone = true;
		for (int32 Frame = 0; Frame < 180; ++Frame)
		{
			EcoV3Observe::SmoothDamp(Value, Vel, 10.0, 0.3, FrameDt);
			Highest = FMath::Max(Highest, Value);
			bMonotone = bMonotone && Value >= Prev - 1e-12;
			Prev = Value;
		}
		TestTrue(TEXT("넘치지 않는다"), Highest <= 10.0 + 1e-9);
		TestTrue(TEXT("되돌지 않는다"), bMonotone);
		TestEqual(TEXT("3 초 뒤 목표"), Value, 10.0, 1e-3);
	}
	// 2. 큰 프레임 (1 초, 시간 상수 0.05 초 — 멈췄다 풀린 프레임 같은 것)에도 안정
	{
		double Value = 0.0, Vel = 0.0;
		bool bStable = true;
		for (int32 Frame = 0; Frame < 10; ++Frame)
		{
			EcoV3Observe::SmoothDamp(Value, Vel, 10.0, 0.05, 1.0);
			bStable = bStable && FMath::IsFinite(Value) && FMath::IsFinite(Vel) && Value <= 10.0 + 1e-9;
		}
		TestTrue(TEXT("큰 프레임에도 유한·넘침 없음"), bStable);
		TestEqual(TEXT("큰 프레임 끝"), Value, 10.0, 1e-6);
	}
	// 3. 0 프레임은 그대로 (멈춤 첫 프레임)
	{
		double Value = 3.0, Vel = 1.0;
		EcoV3Observe::SmoothDamp(Value, Vel, 10.0, 0.3, 0.0);
		TestEqual(TEXT("0 프레임 값"), Value, 3.0, 0.0);
		TestEqual(TEXT("0 프레임 속도"), Vel, 1.0, 0.0);
	}
	// 4. 9 m/s 로 달리는 대상: 앞보기(속도 × 시간 상수)를 더하면 정상 상태 뒤처짐이 거의 0 (관찰 카메라 초점)
	{
		constexpr double Speed = 900.0;   // cm/s
		constexpr double Tc = 0.18;       // 관찰 카메라 초점 시간 상수
		double WithLead = 0.0, WithLeadVel = 0.0, NoLead = 0.0, NoLeadVel = 0.0, Elapsed = 0.0;
		for (int32 Frame = 0; Frame < 300; ++Frame)
		{
			Elapsed += FrameDt;
			EcoV3Observe::SmoothDamp(WithLead, WithLeadVel, Speed * Elapsed + Speed * Tc, Tc, FrameDt);
			EcoV3Observe::SmoothDamp(NoLead, NoLeadVel, Speed * Elapsed, Tc, FrameDt);
		}
		TestTrue(*FString::Printf(TEXT("앞보기가 없으면 뒤처진다 (%.1f cm)"), Speed * Elapsed - NoLead), Speed * Elapsed - NoLead > 100.0);
		TestTrue(*FString::Printf(TEXT("앞보기가 있으면 15 cm 안 (%.1f cm)"), WithLead - Speed * Elapsed), FMath::Abs(WithLead - Speed * Elapsed) < 15.0);
	}
	// 5. 벡터판
	{
		FVector Value = FVector::ZeroVector, Vel = FVector::ZeroVector;
		const FVector Target(1000.0, -500.0, 200.0);
		for (int32 Frame = 0; Frame < 240; ++Frame)
		{
			EcoV3Observe::SmoothDampVector(Value, Vel, Target, 0.3, FrameDt);
		}
		TestEqual(TEXT("벡터판 목표"), Value, Target, 0.1f);
	}
	// 6. 각도: 170° → −170° 는 180° 쪽(짧은 쪽)으로 돈다 — 0° 쪽으로 가지 않는다
	{
		double Deg = 170.0, DegVel = 0.0, SmallestAbs = 180.0;
		bool bInRange = true;
		for (int32 Frame = 0; Frame < 240; ++Frame)
		{
			EcoV3Observe::SmoothDampAngle(Deg, DegVel, -170.0, 0.45, FrameDt);
			SmallestAbs = FMath::Min(SmallestAbs, FMath::Abs(Deg));
			bInRange = bInRange && Deg >= -180.0 - 1e-9 && Deg <= 180.0 + 1e-9;
		}
		TestTrue(TEXT("짧은 쪽으로 돈다"), SmallestAbs >= 169.99);
		TestTrue(TEXT("−180~180 안"), bInRange);
		TestEqual(TEXT("각도 목표"), Deg, -170.0, 0.01);
	}
	// 7. 가림 피하기 팔 (10-27): 처음은 바로 정하고, 가려지면 바로 당기고, 트이면 넘치지 않고 천천히 편다
	{
		double Arm = -1.0, ArmVel = 0.0;
		EcoV3Observe::ArmStep(Arm, ArmVel, 2400.0, 0.6, FrameDt);
		TestEqual(TEXT("처음은 바로"), Arm, 2400.0, 0.0);
		EcoV3Observe::ArmStep(Arm, ArmVel, 700.0, 0.6, FrameDt);
		TestEqual(TEXT("가려지면 바로 당긴다"), Arm, 700.0, 0.0);
		TestEqual(TEXT("당길 때 속도 0"), ArmVel, 0.0, 0.0);
		EcoV3Observe::ArmStep(Arm, ArmVel, 2400.0, 0.6, FrameDt);
		TestTrue(*FString::Printf(TEXT("트이면 한 프레임에 다 펴지 않는다 (%.1f cm)"), Arm), Arm > 700.0 && Arm < 900.0);
		double Highest = Arm, Prev = Arm;
		bool bMonotone = true;
		for (int32 Frame = 0; Frame < 360; ++Frame)
		{
			EcoV3Observe::ArmStep(Arm, ArmVel, 2400.0, 0.6, FrameDt);
			Highest = FMath::Max(Highest, Arm);
			bMonotone = bMonotone && Arm >= Prev - 1e-9;
			Prev = Arm;
		}
		TestTrue(TEXT("펴는 동안 넘치지 않는다"), Highest <= 2400.0 + 1e-9);
		TestTrue(TEXT("펴는 동안 되돌지 않는다"), bMonotone);
		TestEqual(TEXT("6 초 뒤 다 폈다"), Arm, 2400.0, 1.0);
	}
	// 8. 가리는 나무 고르기 (10-27): 나무 크기 상자만 후보, 선분이 지나거나 끝점이 안이면 가린다
	{
		const FBox Tree(FVector(-500.0, -500.0, 0.0), FVector(500.0, 500.0, 1600.0));     // 가로 10 m · 높이 16 m (Beech_Tree 어림)
		const FBox Bush(FVector(-150.0, -150.0, 0.0), FVector(150.0, 150.0, 120.0));      // 낮은 덤불
		const FBox Big(FVector(-2000.0, -2000.0, 0.0), FVector(2000.0, 2000.0, 2500.0));  // 가로 40 m (키운 너도밤나무)
		const FBox Hill(FVector(-5000.0, -5000.0, 0.0), FVector(5000.0, 5000.0, 2000.0)); // 가로 100 m (지형 덩어리)
		TestTrue(TEXT("나무 상자는 후보"), EcoV3Observe::IsOccluderBox(Tree));
		TestTrue(TEXT("키운 큰 나무도 후보"), EcoV3Observe::IsOccluderBox(Big));
		TestFalse(TEXT("낮은 덤불은 후보가 아니다"), EcoV3Observe::IsOccluderBox(Bush));
		TestFalse(TEXT("아주 넓은 것은 후보가 아니다"), EcoV3Observe::IsOccluderBox(Hill));
		TestFalse(TEXT("빈 상자는 후보가 아니다"), EcoV3Observe::IsOccluderBox(FBox(ForceInit)));
		TestTrue(TEXT("선분이 잎을 지난다"), EcoV3Observe::SegmentHitsBox(Tree, FVector(-1500.0, 0.0, 100.0), FVector(1500.0, 0.0, 1200.0)));
		TestTrue(TEXT("초점이 나무 아래(상자 안)"), EcoV3Observe::SegmentHitsBox(Tree, FVector(0.0, 200.0, 100.0), FVector(0.0, 3000.0, 1500.0)));
		TestFalse(TEXT("옆으로 비켜 지나면 가리지 않는다"), EcoV3Observe::SegmentHitsBox(Tree, FVector(-1500.0, 900.0, 100.0), FVector(1500.0, 900.0, 1200.0)));
		TestFalse(TEXT("위로 넘어가면 가리지 않는다"), EcoV3Observe::SegmentHitsBox(Tree, FVector(-3000.0, 0.0, 1800.0), FVector(3000.0, 0.0, 2500.0)));
	}
	return true;
}

// -----------------------------------------------------------------------------
// 상태 판정 (화면 글)
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3ObserverCameraStateTest, "AdaptiveEcosystem.Policy.V3.ObserverCamera.States",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ObserverCameraStateTest::RunTest(const FString& Parameters)
{
	using EcoV3Observe::EState;
	using EcoV3Integrated::EWolfState;
	// 사슴 (통합 v3): 도주 덮기가 먼저, 길에 따라 트인 쪽·은신처
	TestTrue(TEXT("도주 덮기 + RUN = 도망(트인 쪽)"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kGraze, false, EcoWorldV3::kKeepPanic, EcoWorldV3::kRouteRun) == EState::FleeOpen);
	TestTrue(TEXT("도주 덮기 + SHELTER = 도망(은신처)"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kGraze, false, EcoWorldV3::kKeepPanic, EcoWorldV3::kRouteShelter) == EState::FleeShelter);
	TestTrue(TEXT("도주 덮기 + 길 없음 = 도망"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kFlee, false, EcoWorldV3::kKeepPanic, EcoWorldV3::kRouteNone) == EState::Flee);
	TestTrue(TEXT("은신처 덮기 = 웅크림"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kGraze, false, EcoWorldV3::kKeepShelter, EcoWorldV3::kRouteNone) == EState::Crouch);
	TestTrue(TEXT("경계 덮기 + 먹기 = 경계"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kGraze, false, EcoWorldV3::kKeepAlert, EcoWorldV3::kRouteNone) == EState::Alert);
	TestTrue(TEXT("경계 덮기 + 얼기 = 얼기 (경계는 먹기일 때만)"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kFreeze, false, EcoWorldV3::kKeepAlert, EcoWorldV3::kRouteNone) == EState::Freeze);
	TestTrue(TEXT("거리 두기 덮기 + 먹기 = 거리 두기(쉬는 늑대) (10-27)"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kGraze, false, EcoWorldV3::kKeepRest, EcoWorldV3::kRouteNone) == EState::KeepAway);
	TestTrue(TEXT("거리 두기 덮기 + 잠 = 잠 (거리 두기는 먹기일 때만)"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kSleep, false, EcoWorldV3::kKeepRest, EcoWorldV3::kRouteNone) == EState::Sleep);
	TestTrue(TEXT("숨기 도착 = 웅크림"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kHide, true, EcoWorldV3::kKeepNone, EcoWorldV3::kRouteNone) == EState::Crouch);
	TestTrue(TEXT("숨기 가는 중 = 숨으러 감"),
			 EcoV3Observe::DeerStateV3(EcoRepertoireV3::kHide, false, EcoWorldV3::kKeepNone, EcoWorldV3::kRouteNone) == EState::Hide);
	TestTrue(TEXT("잠"), EcoV3Observe::DeerStateV3(EcoRepertoireV3::kSleep, false, EcoWorldV3::kKeepNone, EcoWorldV3::kRouteNone) == EState::Sleep);
	TestTrue(TEXT("먹기"), EcoV3Observe::DeerStateV3(EcoRepertoireV3::kGraze, false, EcoWorldV3::kKeepNone, EcoWorldV3::kRouteNone) == EState::Eat);

	// 늑대 (통합 v3)
	TestTrue(TEXT("추격 = 사냥"), EcoV3Observe::WolfStateV3(static_cast<int32>(EWolfState::Chase), false) == EState::Hunt);
	TestTrue(TEXT("잠행 = 사냥"), EcoV3Observe::WolfStateV3(static_cast<int32>(EWolfState::Stalk), false) == EState::Hunt);
	TestTrue(TEXT("돌진 = 사냥"), EcoV3Observe::WolfStateV3(static_cast<int32>(EWolfState::Pounce), false) == EState::Hunt);
	TestTrue(TEXT("식사 = 늑대 먹기"), EcoV3Observe::WolfStateV3(static_cast<int32>(EWolfState::Eat), false) == EState::WolfEat);
	TestTrue(TEXT("눕는 중 = 쉼"), EcoV3Observe::WolfStateV3(static_cast<int32>(EWolfState::Settle), false) == EState::Rest);
	TestTrue(TEXT("깨는 중 = 배회"), EcoV3Observe::WolfStateV3(static_cast<int32>(EWolfState::Waking), false) == EState::Roam);
	TestTrue(TEXT("배부름은 배회여도 쉼"), EcoV3Observe::WolfStateV3(static_cast<int32>(EWolfState::Roam), true) == EState::Rest);

	// 팀 표현 활동 값 (클라이언트·v1)
	TestTrue(TEXT("늑대 Pursue = 사냥"), EcoV3Observe::StateFromActivity(true, EEcoSpeciesActivity::Pursue) == EState::Hunt);
	TestTrue(TEXT("늑대 SatedRest = 쉼"), EcoV3Observe::StateFromActivity(true, EEcoSpeciesActivity::SatedRest) == EState::Rest);
	TestTrue(TEXT("늑대 Eat = 늑대 먹기"), EcoV3Observe::StateFromActivity(true, EEcoSpeciesActivity::Eat) == EState::WolfEat);
	TestTrue(TEXT("늑대 Wander = 배회"), EcoV3Observe::StateFromActivity(true, EEcoSpeciesActivity::Wander) == EState::Roam);
	TestTrue(TEXT("사슴 ShelterHold = 웅크림"), EcoV3Observe::StateFromActivity(false, EEcoSpeciesActivity::ShelterHold) == EState::Crouch);
	TestTrue(TEXT("사슴 ShelterTravel = 숨으러 감"), EcoV3Observe::StateFromActivity(false, EEcoSpeciesActivity::ShelterTravel) == EState::Hide);
	TestTrue(TEXT("사슴 AlertGraze = 경계"), EcoV3Observe::StateFromActivity(false, EEcoSpeciesActivity::AlertGraze) == EState::Alert);
	TestTrue(TEXT("사슴 Flee = 도망"), EcoV3Observe::StateFromActivity(false, EEcoSpeciesActivity::Flee) == EState::Flee);
	TestTrue(TEXT("사슴 Graze = 먹기"), EcoV3Observe::StateFromActivity(false, EEcoSpeciesActivity::Graze) == EState::Eat);
	TestTrue(TEXT("사슴 Travel = 이동"), EcoV3Observe::StateFromActivity(false, EEcoSpeciesActivity::Travel) == EState::Travel);

	// 쫓김·사냥·이름
	TestTrue(TEXT("도망(트인 쪽)은 쫓김"), EcoV3Observe::IsChased(EState::FleeOpen));
	TestTrue(TEXT("도망(은신처)은 쫓김"), EcoV3Observe::IsChased(EState::FleeShelter));
	TestFalse(TEXT("숨으러 감은 쫓김이 아니다"), EcoV3Observe::IsChased(EState::Hide));
	TestTrue(TEXT("사냥"), EcoV3Observe::IsHunting(EState::Hunt));
	for (uint8 Raw = static_cast<uint8>(EState::Eat); Raw < static_cast<uint8>(EState::Count); ++Raw)
	{
		TestNotEqual(*FString::Printf(TEXT("상태 %d 이름"), static_cast<int32>(Raw)), FString(EcoV3Observe::StateNameKo(static_cast<EState>(Raw))),
					 FString(TEXT("?")));
	}
	TestNotEqual(TEXT("모드 이름"), FString(UEcoV3ObserverCameraSubsystem::ModeNameKo(EEcoV3CamMode::Quarter)), FString(TEXT("원래 카메라")));
	return true;
}

// -----------------------------------------------------------------------------
// 논리 개체 찾기 (월드) + 서브시스템 흐름
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3ObserverCameraWorldTest, "AdaptiveEcosystem.Policy.V3.ObserverCamera.LogicalSubjects",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ObserverCameraWorldTest::RunTest(const FString& Parameters)
{
	using EcoV3Observe::EState;
	using EcoV3Observe::FSubject;
	EcoTest::FScopedTestWorld Scoped;
	if (!TestNotNull(TEXT("테스트 월드"), Scoped.World))
	{
		return false;
	}
	UWorld& World = *Scoped.World;
	UMassEntitySubsystem* MassSub = World.GetSubsystem<UMassEntitySubsystem>();
	if (!TestNotNull(TEXT("UMassEntitySubsystem"), MassSub))
	{
		return false;
	}
	FMassEntityManager& EM = MassSub->GetMutableEntityManager();
	// 팀 조정자가 만드는 통합 개체의 최소 구성 (꼬리표·id·지역·자리·표현). 클라이언트 판은 받는 표본 조각을 더한다
	const FMassArchetypeHandle HostArch = EM.CreateArchetype({
		FEcoIntegratedCreatureTag::StaticStruct(),
		FEcoIdentityFragment::StaticStruct(),
		FEcoRegionFragment::StaticStruct(),
		FTransformFragment::StaticStruct(),
		FEcoCreaturePresentationFragment::StaticStruct(),
	});
	const FMassArchetypeHandle ClientArch = EM.CreateArchetype({
		FEcoIntegratedCreatureTag::StaticStruct(),
		FEcoIdentityFragment::StaticStruct(),
		FEcoRegionFragment::StaticStruct(),
		FTransformFragment::StaticStruct(),
		FEcoCreaturePresentationFragment::StaticStruct(),
		FEcoClientPresentationFragment::StaticStruct(),
	});
	const FName WolfName(TEXT("Wolf")), DeerName(TEXT("Herbivore")), RegionA(TEXT("A")), RegionB(TEXT("B"));
	auto Spawn = [&EM](const FMassArchetypeHandle& Arch, int64 Id, FName Species, FName RegionId, const FVector& At, EEcoSpeciesActivity Activity,
					   bool bAlive, const FVector& Velocity) -> FMassEntityHandle
	{
		const FMassEntityHandle E = EM.CreateEntity(Arch);
		FEcoIdentityFragment& Ident = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
		Ident.StableAgentId = Id;
		Ident.SpeciesId = Species;
		EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId = RegionId;
		EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(At);
		FEcoCreaturePresentationFragment& Pres = EM.GetFragmentDataChecked<FEcoCreaturePresentationFragment>(E);
		Pres.Flags = static_cast<uint8>(bAlive ? 1 : 0);
		Pres.Activity = static_cast<uint8>(Activity);
		Pres.Velocity = Velocity;
		return E;
	};
	constexpr int64 kHuntWolf = 101;    // A, 월드 원점에서 600 m — 표현 액터 없음
	constexpr int64 kIdleWolf = 102;    // A
	constexpr int64 kFleeDeer = 201;    // A, 사냥 늑대 5.83 m
	constexpr int64 kDeadDeer = 202;    // A, 사냥 늑대 0.1 m 지만 죽음
	constexpr int64 kRegionBDeer = 203; // B, 월드 원점 반대쪽 800 m
	constexpr int64 kNoSampleDeer = 301;   // 클라이언트 표본 없음 — 빠져야 한다
	constexpr int64 kSampledDeer = 302;    // 클라이언트 표본 (602 m, −4 m) — 논리 변환은 원점
	Spawn(HostArch, kHuntWolf, WolfName, RegionA, FVector(60000.0, 0.0, 0.0), EEcoSpeciesActivity::Pursue, true, FVector(500.0, 0.0, 0.0));
	Spawn(HostArch, kIdleWolf, WolfName, RegionA, FVector(61000.0, 0.0, 0.0), EEcoSpeciesActivity::Hold, true, FVector::ZeroVector);
	Spawn(HostArch, kFleeDeer, DeerName, RegionA, FVector(60500.0, 300.0, 0.0), EEcoSpeciesActivity::Flee, true, FVector(0.0, 450.0, 0.0));
	Spawn(HostArch, kDeadDeer, DeerName, RegionA, FVector(60010.0, 0.0, 0.0), EEcoSpeciesActivity::Hold, false, FVector(100.0, 0.0, 0.0));
	Spawn(HostArch, kRegionBDeer, DeerName, RegionB, FVector(-80000.0, 0.0, 0.0), EEcoSpeciesActivity::Graze, true, FVector::ZeroVector);
	Spawn(ClientArch, kNoSampleDeer, DeerName, RegionA, FVector(60001.0, 1.0, 0.0), EEcoSpeciesActivity::Hold, true, FVector::ZeroVector);
	const FMassEntityHandle Sampled =
		Spawn(ClientArch, kSampledDeer, DeerName, RegionA, FVector::ZeroVector, EEcoSpeciesActivity::Hold, true, FVector::ZeroVector);
	FEcoClientPresentationFragment& Sample = EM.GetFragmentDataChecked<FEcoClientPresentationFragment>(Sampled);
	Sample.bHasSample = true;
	Sample.Current.Location = FVector(60200.0, -400.0, 0.0);

	// 1. Gather: 표현 액터 없이 논리 개체를 모두 (id 차례), 표본 없는 클라이언트 개체는 뺀다
	TArray<FSubject> Found;
	if (!TestTrue(TEXT("Gather 성공 (Mass 처리 중 아님)"), EcoV3Observe::Gather(World, Found)))
	{
		return false;
	}
	const int64 WantIds[] = {kHuntWolf, kIdleWolf, kFleeDeer, kDeadDeer, kRegionBDeer, kSampledDeer};
	if (!TestEqual(TEXT("논리 개체 6 (표본 없는 클라이언트 개체 하나는 뺀다)"), Found.Num(), 6))
	{
		return false;
	}
	for (int32 i = 0; i < Found.Num(); ++i)
	{
		TestEqual(*FString::Printf(TEXT("id 차례 %d"), i), Found[i].Id, WantIds[i]);
		TestFalse(*FString::Printf(TEXT("#%lld 표현 액터 없음"), Found[i].Id), Found[i].bHasActor);
	}
	TestNull(TEXT("표현 액터 찾기: 없음"), EcoV3Observe::FindActor(World, kHuntWolf));
	const FSubject& HuntWolf = Found[0];
	const FSubject& IdleWolf = Found[1];
	const FSubject& FleeDeer = Found[2];
	const FSubject& DeadDeer = Found[3];
	const FSubject& RegionBDeer = Found[4];
	const FSubject& SampledDeer = Found[5];
	TestTrue(TEXT("늑대 종"), HuntWolf.bWolf && IdleWolf.bWolf && !FleeDeer.bWolf);
	TestEqual(TEXT("논리 자리 (600 m — 액터 예산 밖)"), HuntWolf.Location, FVector(60000.0, 0.0, 0.0), 0.01f);
	TestEqual(TEXT("지역"), HuntWolf.Region, RegionA);
	TestTrue(TEXT("Pursue = 사냥"), HuntWolf.State == EState::Hunt);
	TestTrue(TEXT("5 m/s = 뛰기 동작"), HuntWolf.Motion == EEcoCreatureVisualMotion::Run);
	TestTrue(TEXT("Hold 늑대 = 배회"), IdleWolf.State == EState::Roam);
	TestTrue(TEXT("멈춘 늑대 = 서기 동작"), IdleWolf.Motion == EEcoCreatureVisualMotion::Idle);
	TestTrue(TEXT("Flee 사슴 = 도망"), FleeDeer.State == EState::Flee);
	TestEqual(TEXT("도망 사슴의 사냥 늑대"), FleeDeer.NearestHuntWolfId, kHuntWolf);
	TestEqual(TEXT("도망 사슴의 사냥 늑대 거리"), FleeDeer.NearestHuntWolfCm, FMath::Sqrt(500.0 * 500.0 + 300.0 * 300.0), 0.01);
	TestFalse(TEXT("죽음 깃발"), DeadDeer.bAlive);
	TestTrue(TEXT("죽은 상태"), DeadDeer.State == EState::Dead);
	TestEqual(TEXT("죽은 개체 속도 0"), DeadDeer.Velocity, FVector::ZeroVector, 0.0f);
	TestEqual(TEXT("B 사슴 지역"), RegionBDeer.Region, RegionB);
	TestTrue(TEXT("Graze 사슴 = 먹기"), RegionBDeer.State == EState::Eat);
	TestEqual(TEXT("B 에는 늑대가 없다"), RegionBDeer.NearestWolfCm, -1.0, 0.0);
	TestEqual(TEXT("클라이언트 표본 자리"), SampledDeer.Location, FVector(60200.0, -400.0, 0.0), 0.01f);
	TestEqual(TEXT("사냥 늑대의 가장 가까운 사슴 = 표본 자리 사슴 (죽은 사슴 빼고)"), HuntWolf.NearestDeerId, kSampledDeer);
	TestEqual(TEXT("배회 늑대의 가장 가까운 사슴"), IdleWolf.NearestDeerId, kFleeDeer);

	// 2. 지역 (무대가 없으면 개체 둘레 상자, 이름 차례)
	TArray<EcoV3Observe::FRegionInfo> Regions;
	EcoV3Observe::GatherRegions(World, Found, Regions);
	if (TestEqual(TEXT("지역 둘"), Regions.Num(), 2))
	{
		TestEqual(TEXT("이름 차례 A"), Regions[0].Id, RegionA);
		TestEqual(TEXT("이름 차례 B"), Regions[1].Id, RegionB);
		TestFalse(TEXT("통합 v3 무대가 아니다"), Regions[0].bStage);
		TestEqual(TEXT("A 둘레 상자 중심 x"), Regions[0].CenterCm.X, 60500.0, 0.01);
		TestEqual(TEXT("한 마리 지역도 60 m 상자"), Regions[1].SizeCm, 6000.0, 0.01);
	}

	// 3. 서브시스템 흐름 (로컬 플레이어가 없어 카메라 액터·보기 대상은 건드리지 않는다 — 고르기만 본다)
	UEcoV3ObserverCameraSubsystem* Cam = World.GetSubsystem<UEcoV3ObserverCameraSubsystem>();
	if (!TestNotNull(TEXT("관찰 카메라 서브시스템 (게임 월드에 만들어진다)"), Cam))
	{
		return false;
	}
	TestTrue(TEXT("처음은 원래 카메라"), Cam->GetMode() == EEcoV3CamMode::Player);
	TestTrue(TEXT("단축키 목록은 처음에 보인다"), Cam->IsKeyListShown());
	Cam->SetMode(EEcoV3CamMode::Wolf);
	TestTrue(TEXT("1 = 늑대 시점"), Cam->GetMode() == EEcoV3CamMode::Wolf);
	TestEqual(TEXT("1 = 사냥 중인 늑대를 먼저 (보는 자리에서 가까운 지역 A)"), Cam->GetSubjectId(), kHuntWolf);
	TestEqual(TEXT("대상 지역"), Cam->GetRegion(), RegionA);
	Cam->SetMode(EEcoV3CamMode::Wolf);
	TestEqual(TEXT("1 다시 = 다음 늑대"), Cam->GetSubjectId(), kIdleWolf);
	Cam->SetMode(EEcoV3CamMode::Wolf);
	TestEqual(TEXT("1 다시 = 감겨 첫 늑대"), Cam->GetSubjectId(), kHuntWolf);
	Cam->StepSubject(-1);
	TestEqual(TEXT(", = 이전 늑대"), Cam->GetSubjectId(), kIdleWolf);
	Cam->StepSubject(+1);
	TestEqual(TEXT(". = 다음 늑대"), Cam->GetSubjectId(), kHuntWolf);
	Cam->SetMode(EEcoV3CamMode::Deer);
	TestTrue(TEXT("2 = 사슴 시점"), Cam->GetMode() == EEcoV3CamMode::Deer);
	TestEqual(TEXT("2 = 보던 늑대 곁 사슴 (죽은 사슴 빼고, 클라이언트 표본 자리로 잰다)"), Cam->GetSubjectId(), kSampledDeer);
	Cam->SetMode(EEcoV3CamMode::Top);
	TestTrue(TEXT("3 = 탑뷰"), Cam->GetMode() == EEcoV3CamMode::Top);
	TestEqual(TEXT("3 = 보던 대상 위"), Cam->GetSubjectId(), kSampledDeer);
	TestTrue(TEXT("지역 B 로"), Cam->SetRegion(RegionB));
	TestEqual(TEXT("탑뷰 지역 바꿈 = 무대 전체 (대상 없음)"), Cam->GetSubjectId(), static_cast<int64>(0));
	TestEqual(TEXT("지역 B"), Cam->GetRegion(), RegionB);
	AddExpectedMessagePlain(TEXT("지역 'Nope' 없음"), EAutomationExpectedMessageFlags::Contains, 1);
	TestFalse(TEXT("없는 지역은 거짓"), Cam->SetRegion(FName(TEXT("Nope"))));
	TestEqual(TEXT("없는 지역이면 그대로"), Cam->GetRegion(), RegionB);
	Cam->SetMode(EEcoV3CamMode::Auto);
	TestTrue(TEXT("5 = 자동 추적"), Cam->GetMode() == EEcoV3CamMode::Auto);
	TestEqual(TEXT("고른 지역 B 에 사건이 없으면 기다린다"), Cam->GetSubjectId(), static_cast<int64>(0));
	TestTrue(TEXT("지역 A 로"), Cam->SetRegion(RegionA));
	TestEqual(TEXT("A 의 쫓기는 사슴을 고른다"), Cam->GetSubjectId(), kFleeDeer);
	TestTrue(TEXT("상태 줄"), Cam->DescribeStatus().Contains(TEXT("자동 추적")));
	Cam->ToggleKeyList();
	TestFalse(TEXT("H = 단축키 목록 숨김"), Cam->IsKeyListShown());
	Cam->ToggleKeyList();
	TestTrue(TEXT("H 다시 = 보임"), Cam->IsKeyListShown());
	Cam->SetMode(EEcoV3CamMode::Player);
	TestTrue(TEXT("0 = 원래 카메라"), Cam->GetMode() == EEcoV3CamMode::Player);
	TestEqual(TEXT("원래 카메라는 대상 없음"), Cam->GetSubjectId(), static_cast<int64>(0));
	return true;
}

// -----------------------------------------------------------------------------
// 관찰 중 플레이어 이동 입력 막기 (10-27 사용자 결정 — 안 보이는 폰이 걸어 발소리 Player.Footstep 를 사슴이 듣지 않게)
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3ObserverCameraMoveBlockTest, "AdaptiveEcosystem.Policy.V3.ObserverCamera.MoveInputBlock",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ObserverCameraMoveBlockTest::RunTest(const FString& Parameters)
{
	EcoTest::FScopedTestWorld Scoped;
	if (!TestNotNull(TEXT("테스트 월드"), Scoped.World))
	{
		return false;
	}
	UWorld& World = *Scoped.World;
	UMassEntitySubsystem* MassSub = World.GetSubsystem<UMassEntitySubsystem>();
	UEcoV3ObserverCameraSubsystem* Cam = World.GetSubsystem<UEcoV3ObserverCameraSubsystem>();
	IConsoleVariable* BlockVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Cam.BlockMove"));
	if (!TestNotNull(TEXT("UMassEntitySubsystem"), MassSub) || !TestNotNull(TEXT("관찰 카메라 서브시스템"), Cam)
		|| !TestNotNull(TEXT("eco.Cam.BlockMove"), BlockVar))
	{
		return false;
	}
	const int32 SavedBlock = BlockVar->GetInt();
	BlockVar->Set(1, ECVF_SetByCode);

	// 관찰 모드를 켜려면 통합 개체가 있어야 한다 (늑대 하나·사슴 하나)
	FMassEntityManager& EM = MassSub->GetMutableEntityManager();
	const FMassArchetypeHandle Arch = EM.CreateArchetype({
		FEcoIntegratedCreatureTag::StaticStruct(),
		FEcoIdentityFragment::StaticStruct(),
		FEcoRegionFragment::StaticStruct(),
		FTransformFragment::StaticStruct(),
		FEcoCreaturePresentationFragment::StaticStruct(),
	});
	auto Spawn = [&EM, &Arch](int64 Id, const TCHAR* Species, const FVector& At)
	{
		const FMassEntityHandle E = EM.CreateEntity(Arch);
		FEcoIdentityFragment& Ident = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
		Ident.StableAgentId = Id;
		Ident.SpeciesId = FName(Species);
		EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId = FName(TEXT("A"));
		EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(At);
		FEcoCreaturePresentationFragment& Pres = EM.GetFragmentDataChecked<FEcoCreaturePresentationFragment>(E);
		Pres.Flags = 1;   // 살아 있음
		Pres.Activity = static_cast<uint8>(EEcoSpeciesActivity::Hold);
	};
	Spawn(501, TEXT("Wolf"), FVector(1000.0, 0.0, 0.0));
	Spawn(502, TEXT("Herbivore"), FVector(2000.0, 0.0, 0.0));

	// 보는 플레이어 컨트롤러와 폰 (엔진 시험처럼 직접 만든다). 로컬 플레이어(ULocalPlayer)가 없어 서브시스템의 로컬 컨트롤러 찾기는 이것을 고르지 않는다
	// — 카메라 액터·보기 대상은 건드리지 않고, Tick 이 하는 막기 맞추기(SyncMoveInputBlock)를 직접 부른다
	APlayerController* PC = World.SpawnActor<APlayerController>();
	APawn* Pawn = World.SpawnActor<APawn>();
	if (!TestNotNull(TEXT("플레이어 컨트롤러"), PC) || !TestNotNull(TEXT("폰"), Pawn))
	{
		BlockVar->Set(SavedBlock, ECVF_SetByCode);
		return false;
	}
	PC->Possess(Pawn);
	TestTrue(TEXT("폰을 잡았다"), Pawn->GetController() == PC);
	// WASD 한 프레임 (프로젝트 캐릭터 Move 가 부르는 AddMovementInput) 뒤 폰에 남은 이동 입력
	auto MoveInputAfterW = [Pawn]() -> FVector
	{
		Pawn->ConsumeMovementInputVector();
		Pawn->AddMovementInput(FVector::ForwardVector, 1.0f);
		return Pawn->ConsumeMovementInputVector();
	};

	// 1. 원래 카메라: 막지 않는다
	Cam->SyncMoveInputBlock(PC);
	TestFalse(TEXT("원래 카메라 = 안 막음"), Cam->IsBlockingMoveInput());
	TestFalse(TEXT("원래 카메라 = 컨트롤러 이동 무시 아님"), PC->IsMoveInputIgnored());
	TestEqual(TEXT("원래 카메라 = W 가 폰에 들어간다"), MoveInputAfterW(), FVector::ForwardVector, 1.0e-4f);

	// 2. 관찰(1) = 막는다 — 폰 이동 입력이 0 (발소리가 나지 않는다)
	Cam->SetMode(EEcoV3CamMode::Wolf);
	if (!TestTrue(TEXT("1 = 늑대 시점"), Cam->GetMode() == EEcoV3CamMode::Wolf))
	{
		BlockVar->Set(SavedBlock, ECVF_SetByCode);
		return false;
	}
	Cam->SyncMoveInputBlock(PC);
	TestTrue(TEXT("관찰 중 = 막음"), Cam->IsBlockingMoveInput());
	TestTrue(TEXT("관찰 중 = 컨트롤러 이동 무시"), PC->IsMoveInputIgnored());
	TestTrue(TEXT("관찰 중 = 폰도 이동 무시"), Pawn->IsMoveInputIgnored());
	TestTrue(TEXT("관찰 중 = W 가 폰에 들어가지 않는다"), MoveInputAfterW().IsNearlyZero());
	TestTrue(TEXT("상태 줄에 이동 막음"), Cam->DescribeStatus().Contains(TEXT("이동 막음")));
	// 매 프레임 다시 맞춰도·다른 관찰 모드로 바꿔도 한 번만 더한다 (풀 때 한 번 빼면 0 — 아래 4에서 본다)
	Cam->SyncMoveInputBlock(PC);
	Cam->SetMode(EEcoV3CamMode::Deer);
	Cam->SyncMoveInputBlock(PC);
	Cam->SetMode(EEcoV3CamMode::Top);
	Cam->SyncMoveInputBlock(PC);
	TestTrue(TEXT("모드를 바꿔도 막음"), Cam->IsBlockingMoveInput() && PC->IsMoveInputIgnored());

	// 3. 엔진이 이동 무시 수를 지우면 (폰 다시 시작 — ClientRestart 의 ResetIgnoreInputFlags) 다음 맞추기에서 다시 막는다
	PC->ResetIgnoreInputFlags();
	TestFalse(TEXT("엔진이 지움"), PC->IsMoveInputIgnored());
	Cam->SyncMoveInputBlock(PC);
	TestTrue(TEXT("다시 막음"), PC->IsMoveInputIgnored());
	TestTrue(TEXT("다시 막은 뒤 W 가 폰에 들어가지 않는다"), MoveInputAfterW().IsNearlyZero());

	// 4. eco.Cam.BlockMove 0 = 풀림, 1 = 다시 막음
	BlockVar->Set(0, ECVF_SetByCode);
	Cam->SyncMoveInputBlock(PC);
	TestFalse(TEXT("BlockMove 0 = 풀림"), Cam->IsBlockingMoveInput());
	TestFalse(TEXT("BlockMove 0 = 수가 0 으로 (한 번만 더했다)"), PC->IsMoveInputIgnored());
	TestEqual(TEXT("BlockMove 0 = W 가 폰에 들어간다"), MoveInputAfterW(), FVector::ForwardVector, 1.0e-4f);
	BlockVar->Set(1, ECVF_SetByCode);
	Cam->SyncMoveInputBlock(PC);
	TestTrue(TEXT("BlockMove 1 = 다시 막음"), Cam->IsBlockingMoveInput() && PC->IsMoveInputIgnored());

	// 5. 0 (원래 카메라) = 풀림
	Cam->SetMode(EEcoV3CamMode::Player);
	TestTrue(TEXT("0 = 원래 카메라"), Cam->GetMode() == EEcoV3CamMode::Player);
	TestFalse(TEXT("0 = 풀림"), Cam->IsBlockingMoveInput());
	TestFalse(TEXT("0 = 컨트롤러 이동 무시 아님"), PC->IsMoveInputIgnored());
	TestEqual(TEXT("0 = W 가 다시 폰에 들어간다"), MoveInputAfterW(), FVector::ForwardVector, 1.0e-4f);

	// 6. 팀·엔진이 이미 건 막기는 남긴다 (우리가 더한 하나만 뺀다)
	PC->SetIgnoreMoveInput(true);   // 팀 막기 하나
	Cam->SetMode(EEcoV3CamMode::Auto);
	Cam->SyncMoveInputBlock(PC);
	TestTrue(TEXT("팀 막기 + 관찰 = 막음"), Cam->IsBlockingMoveInput() && PC->IsMoveInputIgnored());
	Cam->SetMode(EEcoV3CamMode::Player);
	TestFalse(TEXT("0 = 우리 막기는 풀림"), Cam->IsBlockingMoveInput());
	TestTrue(TEXT("0 뒤에도 팀 막기는 남는다"), PC->IsMoveInputIgnored());
	PC->SetIgnoreMoveInput(false);
	TestFalse(TEXT("팀이 풀면 이동 무시 아님"), PC->IsMoveInputIgnored());

	// 7. 컨트롤러가 바뀌면 전 컨트롤러를 풀고 새 것을 막는다. 로컬 컨트롤러가 없어지면(nullptr) 푼다
	APlayerController* PC2 = World.SpawnActor<APlayerController>();
	if (TestNotNull(TEXT("둘째 컨트롤러"), PC2))
	{
		Cam->SetMode(EEcoV3CamMode::Quarter);
		Cam->SyncMoveInputBlock(PC);
		Cam->SyncMoveInputBlock(PC2);
		TestFalse(TEXT("바뀌면 전 컨트롤러 풀림"), PC->IsMoveInputIgnored());
		TestTrue(TEXT("새 컨트롤러 막음"), PC2->IsMoveInputIgnored());
		Cam->SyncMoveInputBlock(nullptr);
		TestFalse(TEXT("컨트롤러 없음 = 풀림"), Cam->IsBlockingMoveInput());
		TestFalse(TEXT("컨트롤러 없음 = 새 컨트롤러도 풀림"), PC2->IsMoveInputIgnored());
		Cam->SetMode(EEcoV3CamMode::Player);
	}
	BlockVar->Set(SavedBlock, ECVF_SetByCode);
	return true;
}

// -----------------------------------------------------------------------------
// 자유 카메라 (10-29 사용자 — 관찰 중 0: 그 자리에서 추적 풀기, 자유 카메라에서 다시 0: 플레이어로)
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3ObserverCameraFreeTest, "AdaptiveEcosystem.Policy.V3.ObserverCamera.FreeCamera",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3ObserverCameraFreeTest::RunTest(const FString& Parameters)
{
	using EcoV3Observe::EAction;
	using EcoV3Observe::EState;
	using EcoV3Observe::FSubject;
	using EcoV3ObserverCameraTestImpl::MakeSubject;
	constexpr double Dt = 1.0 / 30.0;
	constexpr double Speed = EcoV3Observe::kFreeDefaultSpeedCm;

	// 1. 키 입력 (앞, 오른쪽, 위)
	auto InputOf = [](std::initializer_list<FKey> Down) -> FVector
	{
		TArray<FKey> Held(Down);
		return EcoV3Observe::FreeMoveInput([&Held](const FKey& K) { return Held.Contains(K); });
	};
	TestEqual(TEXT("아무 키도 없음 = 0"), InputOf({}), FVector::ZeroVector);
	TestEqual(TEXT("W = 앞"), InputOf({EKeys::W}), FVector(1.0, 0.0, 0.0));
	TestEqual(TEXT("W + S = 0"), InputOf({EKeys::W, EKeys::S}), FVector::ZeroVector);
	TestEqual(TEXT("W + 위 방향키 = 앞 1"), InputOf({EKeys::W, EKeys::Up}), FVector(1.0, 0.0, 0.0));
	TestEqual(TEXT("D + E = 오른쪽 위"), InputOf({EKeys::D, EKeys::E}), FVector(0.0, 1.0, 1.0));
	TestEqual(TEXT("A + Q = 왼쪽 아래"), InputOf({EKeys::A, EKeys::Q}), FVector(0.0, -1.0, -1.0));
	TestEqual(TEXT("Space·Ctrl 은 움직이지 않는다"), InputOf({EKeys::SpaceBar, EKeys::LeftControl}), FVector::ZeroVector);

	// 2. 한 프레임 이동: 앞 = 보는 방향(숙임 포함), 바라는 속도에 넘침 없이 다가가고, 떼면 부드럽게 선다
	{
		const FRotator View(-30.0, 90.0, 0.0);
		FVector Loc = FVector::ZeroVector, Vel = FVector::ZeroVector;
		double MaxSpeed = 0.0;
		for (int32 i = 0; i < 60; ++i)   // 2 초
		{
			EcoV3Observe::FreeFlyStep(Loc, Vel, View, FVector(1.0, 0.0, 0.0), Speed, Dt);
			MaxSpeed = FMath::Max(MaxSpeed, Vel.Size());
		}
		TestTrue(TEXT("넘침 없음 (속도 ≤ 바라는 속도)"), MaxSpeed <= Speed + 1.0e-6);
		TestEqual(TEXT("2 초 뒤 바라는 속도"), Vel.Size(), Speed, Speed * 0.01);
		TestTrue(TEXT("보는 방향(숙임 포함)으로 간다"), FVector::DotProduct(Loc.GetSafeNormal(), View.Vector()) > 0.9999);
		// 지수 다가가기: 간 거리 ≈ 속도 × (2 − 시간 상수)
		TestEqual(TEXT("2 초에 간 거리"), Loc.Size(), Speed * (2.0 - EcoV3Observe::kFreeAccelSmooth), Speed * 0.05);
		const FVector Before = Loc;
		bool bNoBack = true;
		for (int32 i = 0; i < 30; ++i)   // 1 초 떼기
		{
			const FVector Prev = Loc;
			EcoV3Observe::FreeFlyStep(Loc, Vel, View, FVector::ZeroVector, Speed, Dt);
			bNoBack = bNoBack && FVector::DotProduct(Loc - Prev, View.Vector()) >= -1.0e-9;
		}
		TestTrue(TEXT("떼면 뒤로 가지 않는다"), bNoBack);
		TestTrue(TEXT("1 초 뒤 선다 (속도 0)"), Vel.IsZero());
		TestEqual(TEXT("서는 동안 간 거리 ≈ 속도 × 시간 상수"), (Loc - Before).Size(), Speed * EcoV3Observe::kFreeAccelSmooth, Speed * 0.02);
	}
	{
		// 옆 = 보는 방향의 가로 오른쪽 (숙여도 땅과 나란히), 위 = 세계 위, 사선도 같은 속도, 0 프레임 그대로, 1 초 프레임에도 넘치지 않음
		FVector Loc = FVector::ZeroVector, Vel = FVector::ZeroVector;
		const FRotator Down(-60.0, 0.0, 0.0);
		for (int32 i = 0; i < 60; ++i)
		{
			EcoV3Observe::FreeFlyStep(Loc, Vel, Down, FVector(0.0, 1.0, 0.0), Speed, Dt);
		}
		TestTrue(TEXT("D = 가로 오른쪽 (+Y, 높이 그대로)"), Vel.GetSafeNormal().Equals(FVector(0.0, 1.0, 0.0), 1.0e-6) && FMath::Abs(Loc.Z) < 1.0e-6);
		Loc = Vel = FVector::ZeroVector;
		for (int32 i = 0; i < 60; ++i)
		{
			EcoV3Observe::FreeFlyStep(Loc, Vel, Down, FVector(0.0, 0.0, 1.0), Speed, Dt);
		}
		TestTrue(TEXT("E = 세계 위"), Vel.GetSafeNormal().Equals(FVector::UpVector, 1.0e-6));
		Loc = Vel = FVector::ZeroVector;
		for (int32 i = 0; i < 60; ++i)
		{
			EcoV3Observe::FreeFlyStep(Loc, Vel, FRotator(-30.0, 0.0, 0.0), FVector(1.0, 1.0, 1.0), Speed, Dt);
		}
		TestTrue(TEXT("세 키를 같이 눌러도 바라는 속도를 넘지 않는다"), Vel.Size() <= Speed + 1.0e-6);
		const FVector Held = Loc;
		EcoV3Observe::FreeFlyStep(Loc, Vel, Down, FVector(1.0, 0.0, 0.0), Speed, 0.0);
		TestEqual(TEXT("0 프레임 = 그대로"), Loc, Held);
		Vel = FVector::ZeroVector;
		EcoV3Observe::FreeFlyStep(Loc, Vel, Down, FVector(1.0, 0.0, 0.0), Speed, 1.0);
		TestTrue(TEXT("1 초 프레임에도 넘치지 않는다"), Vel.Size() <= Speed + 1.0e-6);
	}

	// 3. 마우스 시야: 컨트롤러 방향이 바뀐 양만 (짧은 쪽), 숙임은 ±89°
	{
		double Yaw = 10.0, Pitch = -20.0;
		EcoV3Observe::FreeLookStep(Yaw, Pitch, FRotator(0.0, 359.0, 0.0), FRotator(0.0, 1.0, 0.0));
		TestEqual(TEXT("방위 359 → 1 = +2°"), Yaw, 12.0, 1.0e-9);
		EcoV3Observe::FreeLookStep(Yaw, Pitch, FRotator(350.0, 0.0, 0.0), FRotator(340.0, 0.0, 0.0));
		TestEqual(TEXT("숙임 350(−10) → 340(−20) = −10°"), Pitch, -30.0, 1.0e-9);
		Pitch = 85.0;
		EcoV3Observe::FreeLookStep(Yaw, Pitch, FRotator(0.0, 0.0, 0.0), FRotator(10.0, 0.0, 0.0));
		TestEqual(TEXT("숙임은 89° 까지"), Pitch, EcoV3Observe::kFreePitchLimit, 1.0e-9);
		EcoV3Observe::FreeLookStep(Yaw, Pitch, FRotator(10.0, 30.0, 0.0), FRotator(10.0, 30.0, 0.0));
		TestEqual(TEXT("컨트롤러가 그대로면 시야도 그대로"), Yaw, 12.0, 1.0e-9);
		EcoV3Observe::FreeLookStep(Yaw, Pitch, FRotator(0.0, 0.0, 0.0), FRotator(0.0, 170.0, 0.0));
		TestEqual(TEXT("한 프레임에 90° 넘게 바뀌면 (폰 다시 잡기) 돌리지 않는다"), Yaw, 12.0, 1.0e-9);
	}

	// 4. 화면 가운데 대상: 원뿔(20°·300 m) 안에서 각이 가장 작은 것, 같으면 가까운 것. 죽은 개체·뒤·밖은 뺀다
	{
		const FName A(TEXT("A"));
		const TArray<FSubject> List = {
			MakeSubject(11, false, A, 10000.0, 300.0, EState::Eat),     // 사슴 1.7°
			MakeSubject(12, false, A, 5000.0, 1000.0, EState::Eat),     // 사슴 11.3°
			MakeSubject(13, true, A, 3000.0, 0.0, EState::Roam),        // 늑대 0°
			MakeSubject(14, false, A, -5000.0, 0.0, EState::Eat),       // 뒤
			MakeSubject(15, false, A, 8000.0, 0.0, EState::Eat, false), // 죽음 (0°)
			MakeSubject(16, false, A, 40000.0, 0.0, EState::Eat),       // 400 m — 밖
			MakeSubject(17, false, A, 2000.0, 2000.0, EState::Eat),     // 45° — 밖
			MakeSubject(18, false, A, 20000.0, 600.0, EState::Eat),     // 사슴 1.7° — 11 과 같은 쪽, 더 멂
		};
		// 눈 높이 = 개체 몸 가운데 높이 (Location + 1 m)
		const FVector Eye(0.0, 0.0, 100.0);
		using EcoV3ObserverCameraTestImpl::IdAt;
		TestEqual(TEXT("사슴 = 가운데에 가장 가까운 산 사슴 (같은 쪽이면 가까운 것)"),
				  IdAt(List, EcoV3Observe::CenterSubject(List, 0, Eye, FVector::ForwardVector, 20.0, 30000.0)), static_cast<int64>(11));
		TestEqual(TEXT("늑대"), IdAt(List, EcoV3Observe::CenterSubject(List, 1, Eye, FVector::ForwardVector, 20.0, 30000.0)), static_cast<int64>(13));
		TestEqual(TEXT("아무 종"), IdAt(List, EcoV3Observe::CenterSubject(List, -1, Eye, FVector::ForwardVector, 20.0, 30000.0)), static_cast<int64>(13));
		TestEqual(TEXT("원뿔 밖이면 없음"), EcoV3Observe::CenterSubject(List, 0, Eye, FVector(0.0, -1.0, 0.0), 20.0, 30000.0), static_cast<int32>(INDEX_NONE));
		TestEqual(TEXT("방향 0 이면 없음"), EcoV3Observe::CenterSubject(List, 0, Eye, FVector::ZeroVector, 20.0, 30000.0), static_cast<int32>(INDEX_NONE));
	}

	// 5. 서브시스템 흐름 (로컬 플레이어가 없어 카메라 액터·보기 대상은 건드리지 않는다 — 모드·대상·막기만 본다)
	EcoTest::FScopedTestWorld Scoped;
	if (!TestNotNull(TEXT("테스트 월드"), Scoped.World))
	{
		return false;
	}
	UWorld& World = *Scoped.World;
	UMassEntitySubsystem* MassSub = World.GetSubsystem<UMassEntitySubsystem>();
	UEcoV3ObserverCameraSubsystem* Cam = World.GetSubsystem<UEcoV3ObserverCameraSubsystem>();
	IConsoleVariable* BlockVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Cam.BlockMove"));
	if (!TestNotNull(TEXT("UMassEntitySubsystem"), MassSub) || !TestNotNull(TEXT("관찰 카메라 서브시스템"), Cam)
		|| !TestNotNull(TEXT("eco.Cam.BlockMove"), BlockVar))
	{
		return false;
	}
	const int32 SavedBlock = BlockVar->GetInt();
	BlockVar->Set(1, ECVF_SetByCode);
	FMassEntityManager& EM = MassSub->GetMutableEntityManager();
	const FMassArchetypeHandle Arch = EM.CreateArchetype({
		FEcoIntegratedCreatureTag::StaticStruct(),
		FEcoIdentityFragment::StaticStruct(),
		FEcoRegionFragment::StaticStruct(),
		FTransformFragment::StaticStruct(),
		FEcoCreaturePresentationFragment::StaticStruct(),
	});
	auto Spawn = [&EM, &Arch](int64 Id, const TCHAR* Species, const TCHAR* RegionId, const FVector& At)
	{
		const FMassEntityHandle E = EM.CreateEntity(Arch);
		FEcoIdentityFragment& Ident = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
		Ident.StableAgentId = Id;
		Ident.SpeciesId = FName(Species);
		EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId = FName(RegionId);
		EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(At);
		FEcoCreaturePresentationFragment& Pres = EM.GetFragmentDataChecked<FEcoCreaturePresentationFragment>(E);
		Pres.Flags = 1;   // 살아 있음
		Pres.Activity = static_cast<uint8>(EEcoSpeciesActivity::Hold);
	};
	constexpr int64 kWolf1 = 601, kWolf2 = 602, kDeer1 = 701, kDeer2 = 702, kDeerB = 703;
	Spawn(kWolf1, TEXT("Wolf"), TEXT("A"), FVector(1000.0, 0.0, 0.0));
	Spawn(kWolf2, TEXT("Wolf"), TEXT("A"), FVector(3000.0, 2000.0, 0.0));
	Spawn(kDeer1, TEXT("Herbivore"), TEXT("A"), FVector(2000.0, 0.0, 0.0));
	Spawn(kDeer2, TEXT("Herbivore"), TEXT("A"), FVector(2000.0, 3000.0, 0.0));
	Spawn(kDeerB, TEXT("Herbivore"), TEXT("B"), FVector(-80000.0, 0.0, 0.0));
	APlayerController* PC = World.SpawnActor<APlayerController>();
	APawn* Pawn = World.SpawnActor<APawn>();
	if (!TestNotNull(TEXT("플레이어 컨트롤러"), PC) || !TestNotNull(TEXT("폰"), Pawn))
	{
		BlockVar->Set(SavedBlock, ECVF_SetByCode);
		return false;
	}
	PC->Possess(Pawn);
	auto MoveInputAfterW = [Pawn]() -> FVector
	{
		Pawn->ConsumeMovementInputVector();
		Pawn->AddMovementInput(FVector::ForwardVector, 1.0f);
		return Pawn->ConsumeMovementInputVector();
	};
	auto Blocked = [&]() -> bool
	{
		Cam->SyncMoveInputBlock(PC);   // Tick 이 매 프레임 하는 막기 맞추기
		return Cam->IsBlockingMoveInput() && PC->IsMoveInputIgnored() && MoveInputAfterW().IsNearlyZero();
	};

	// 5-1. 1 → 0 = 자유 카메라 (대상 없음, 폰 이동 막기 그대로)
	Cam->DoAction(EAction::Wolf);
	TestTrue(TEXT("1 = 늑대 시점"), Cam->GetMode() == EEcoV3CamMode::Wolf && Cam->GetSubjectId() != 0);
	TestTrue(TEXT("늑대 시점 = 막음"), Blocked());
	Cam->DoAction(EAction::Player);
	TestTrue(TEXT("관찰 중 0 = 자유 카메라"), Cam->GetMode() == EEcoV3CamMode::Free);
	TestEqual(TEXT("자유 카메라는 대상 없음"), Cam->GetSubjectId(), static_cast<int64>(0));
	TestTrue(TEXT("자유 카메라 = 폰 이동 막기 그대로 (W 가 폰에 들어가지 않는다)"), Blocked());
	TestTrue(TEXT("상태 줄 자유 카메라"), Cam->DescribeStatus().Contains(TEXT("자유 카메라")));
	TestTrue(TEXT("자유 카메라 자리·방향이 유한하다"), !Cam->GetFreeLocation().ContainsNaN() && !Cam->GetFreeRotation().ContainsNaN());
	Cam->DoAction(EAction::Next);
	Cam->DoAction(EAction::Prev);
	TestTrue(TEXT("자유 카메라에서 , . 는 아무 일 없음"), Cam->GetMode() == EEcoV3CamMode::Free && Cam->GetSubjectId() == 0);
	// 속도: = 휠 위 = 빠르게, - 휠 아래 = 느리게, 1~150 m/s
	Cam->DoAction(EAction::ZoomIn);
	TestEqual(TEXT("= = 1.2 배 빠르게"), Cam->GetFreeSpeedCm(), Speed * EcoV3Observe::kFreeSpeedStep, 1.0e-6);
	Cam->DoAction(EAction::ZoomOut);
	TestEqual(TEXT("- = 다시 12 m/s"), Cam->GetFreeSpeedCm(), Speed, 1.0e-6);
	Cam->SetFreeSpeed(1000.0);
	TestEqual(TEXT("150 m/s 까지"), Cam->GetFreeSpeedCm(), EcoV3Observe::kFreeMaxSpeedCm, 1.0e-6);
	Cam->SetFreeSpeed(0.01);
	TestEqual(TEXT("1 m/s 밑으로 가지 않는다"), Cam->GetFreeSpeedCm(), EcoV3Observe::kFreeMinSpeedCm, 1.0e-6);
	Cam->SetFreeSpeed(Speed / 100.0);

	// 5-2. 자유 카메라에서 2 = 화면 가운데 사슴 (먼 사슴 702 도 같은 쪽이지만 가까운 701)
	Cam->SetFreePose(FVector(2000.0, -1500.0, 100.0), FRotator(0.0, 90.0, 0.0));
	TestEqual(TEXT("자유 카메라 자리"), Cam->GetFreeLocation(), FVector(2000.0, -1500.0, 100.0));
	Cam->DoAction(EAction::Deer);
	TestTrue(TEXT("자유 카메라에서 2 = 사슴 시점"), Cam->GetMode() == EEcoV3CamMode::Deer);
	TestEqual(TEXT("2 = 화면 가운데 사슴"), Cam->GetSubjectId(), kDeer1);
	TestTrue(TEXT("사슴 시점 = 막음"), Blocked());

	// 5-3. 0 을 빠르게 두 번 = 자유 카메라 → 원래 카메라 (막기 풀림), 원래 카메라에서 0 = 아무 일 없음
	Cam->DoAction(EAction::Player);
	TestTrue(TEXT("0 = 자유 카메라"), Cam->GetMode() == EEcoV3CamMode::Free);
	Cam->DoAction(EAction::Player);
	TestTrue(TEXT("자유 카메라에서 다시 0 = 원래 카메라"), Cam->GetMode() == EEcoV3CamMode::Player);
	Cam->SyncMoveInputBlock(PC);
	TestFalse(TEXT("원래 카메라 = 풀림"), Cam->IsBlockingMoveInput() || PC->IsMoveInputIgnored());
	TestEqual(TEXT("원래 카메라 = W 가 다시 폰에 들어간다"), MoveInputAfterW(), FVector::ForwardVector, 1.0e-4f);
	Cam->DoAction(EAction::Player);
	Cam->SyncMoveInputBlock(PC);
	TestTrue(TEXT("원래 카메라에서 0 = 아무 일 없음"), Cam->GetMode() == EEcoV3CamMode::Player && !Cam->IsBlockingMoveInput());

	// 5-4. eco.Cam.Free (원래 카메라에서도) → 1 = 화면 가운데 늑대 (지금 규칙(보는 자리 곁·같으면 id 작은 것)이면 601 — 가운데 602 를 고른다)
	Cam->SetMode(EEcoV3CamMode::Free);
	TestTrue(TEXT("eco.Cam.Free = 자유 카메라"), Cam->GetMode() == EEcoV3CamMode::Free);
	TestTrue(TEXT("eco.Cam.Free = 막음"), Blocked());
	Cam->EnterFree(TEXT("시험 — 두 번"));
	TestTrue(TEXT("이미 자유 카메라면 그대로"), Cam->GetMode() == EEcoV3CamMode::Free);
	Cam->SetFreePose(FVector(3000.0, 0.0, 100.0), FRotator(0.0, 90.0, 0.0));
	Cam->DoAction(EAction::Wolf);
	TestEqual(TEXT("1 = 화면 가운데 늑대"), Cam->GetSubjectId(), kWolf2);
	// 가운데에 아무도 없으면 지금 규칙 (보는 자리 곁 — 같은 거리면 id 작은 것)
	Cam->DoAction(EAction::Player);
	Cam->SetFreePose(FVector(3000.0, 0.0, 100.0), FRotator(0.0, -90.0, 0.0));
	Cam->DoAction(EAction::Wolf);
	TestEqual(TEXT("가운데에 없으면 보는 자리 곁 늑대"), Cam->GetSubjectId(), kWolf1);
	TestTrue(TEXT("늑대 시점 = 막음"), Blocked());

	// 5-5. 자유 카메라에서 G = 자유 카메라 그대로 다음 지역 무대가 보이는 자리로, 거기서 2 = 그 지역 사슴
	Cam->DoAction(EAction::Player);
	const FVector BeforeG = Cam->GetFreeLocation();
	Cam->DoAction(EAction::Region);
	TestTrue(TEXT("G 뒤에도 자유 카메라"), Cam->GetMode() == EEcoV3CamMode::Free);
	TestEqual(TEXT("G = 다음 지역 B"), Cam->GetRegion(), FName(TEXT("B")));
	TestTrue(TEXT("G = 카메라가 B 로 옮겼다"), FVector::Dist2D(Cam->GetFreeLocation(), FVector(-80000.0, 0.0, 0.0)) < 10000.0
		&& FVector::Dist(BeforeG, Cam->GetFreeLocation()) > 50000.0);
	TestTrue(TEXT("G 뒤에도 막음"), Blocked());
	Cam->DoAction(EAction::Deer);
	TestEqual(TEXT("B 에서 2 = 화면 가운데 B 사슴"), Cam->GetSubjectId(), kDeerB);
	TestEqual(TEXT("지역 B"), Cam->GetRegion(), FName(TEXT("B")));

	// 5-6. 끄기 (eco.Cam.Player = 바로 폰으로)
	Cam->DoAction(EAction::Player);
	Cam->SetMode(EEcoV3CamMode::Player);
	TestTrue(TEXT("eco.Cam.Player = 원래 카메라"), Cam->GetMode() == EEcoV3CamMode::Player);
	Cam->SyncMoveInputBlock(PC);
	TestFalse(TEXT("끝 = 풀림"), PC->IsMoveInputIgnored());
	BlockVar->Set(SavedBlock, ECVF_SetByCode);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
