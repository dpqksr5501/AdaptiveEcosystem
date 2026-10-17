// 촬영 감독 단독 장면 읽기 (10-18 팀 날씨 확인용 -EcoV3FilmStandalone).
//
// 장면 = 이름,x,y,h,방위,숙임,시작초,길이초[,x1,y1,h1]. 8 칸이면 서 있는 장면, 11 칸이면 옮기는 장면, 그 밖은 건너뛴다.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoV3FilmDirector.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3FilmFreeShots, "AdaptiveEcosystem.Policy.V3.Film.StandaloneShots",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3FilmFreeShots::RunTest(const FString& Parameters)
{
	using FFree = UEcoV3FilmDirectorSubsystem::FFreeShot;
	AddExpectedMessage(TEXT("단독 장면"), EAutomationExpectedMessageFlags::Contains, 2);
	const TArray<FFree> S = UEcoV3FilmDirectorSubsystem::ParseFreeShots(
		TEXT("forest, 300, 420, 1.8, 180, 2, 8, 2;bad,1,2,3;cross,340,220,1.8,90,0,54,12,340,280,2.5;tilt,0,0,0,0,-120,1,0;short,1,2,3,4,5,6,7,8,9"));
	TestEqual(TEXT("좋은 장면 셋 (4 칸·10 칸 건너뜀)"), S.Num(), 3);
	if (S.Num() != 3)
	{
		return false;
	}
	TestEqual(TEXT("이름 앞뒤 빈칸 없앰"), S[0].Tag, FString(TEXT("forest")));
	TestEqual(TEXT("x m"), S[0].FromM.X, 300.0);
	TestEqual(TEXT("y m"), S[0].FromM.Y, 420.0);
	TestEqual(TEXT("땅 위 m"), S[0].FromH, 1.8);
	TestEqual(TEXT("방위"), S[0].YawDeg, 180.0);
	TestEqual(TEXT("숙임"), S[0].PitchDeg, 2.0);
	TestEqual(TEXT("시작"), S[0].StartSeconds, 8.0);
	TestEqual(TEXT("길이"), S[0].DurationSeconds, 2.0);
	TestFalse(TEXT("8 칸 = 서 있음"), S[0].bMove);
	TestTrue(TEXT("서 있으면 끝 = 시작"), S[0].ToM == S[0].FromM && S[0].ToH == S[0].FromH);
	TestTrue(TEXT("11 칸 = 옮김"), S[1].bMove);
	TestEqual(TEXT("끝 y"), S[1].ToM.Y, 280.0);
	TestEqual(TEXT("끝 높이"), S[1].ToH, 2.5);
	TestEqual(TEXT("숙임은 ±89.9 안"), S[2].PitchDeg, -89.9);
	TestEqual(TEXT("길이는 0.1 초 이상"), S[2].DurationSeconds, 0.1);
	return true;
}

#endif
