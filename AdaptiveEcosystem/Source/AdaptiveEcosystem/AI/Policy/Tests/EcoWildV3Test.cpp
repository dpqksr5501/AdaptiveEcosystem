// v3 야생 1단계 자동화 시험 — C++ 야생 규칙(EcoWorldV3.h)을 파이썬 야생 규칙(env_v2/world.py '야생 1단계', configs/v3_wild1_mirror.yaml)과
// 대조한다 (사람 결정 10-15 (7), 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md 5절 '골든 시험').
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Wild"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `WildGoldenVectorsV3.h` (herbivore_rl/export_golden_v3_wild.py — 파이썬 World._wild_reserve_step 을 난수 없는 장면으로 돌린 값)다.
// C++ 와 파이썬은 난수열이 달라 궤적은 대조하지 않는다.
//
// 묶음:
//   Wild.ReserveGolden   (w1) 계수 = 파이썬 블록, 용량 C, 비축 한 번 끝 사례, 굶음 열(죽는 스텝·표본), 섞음 열(스텝마다 E·R)
//   Wild.ReserveWorld    (w1) 기준 루프: 끄면(기본) 먹이 없는 세계에서 300 스텝 안에 굶음이 생기고, 켜면 아무도 굶지 않고 비축으로 살며 모두 약함(이동 ≤ 뛰기 × 0.75),
//                        굶어 죽는 사슴은 배·비축 모두 0. 낮 고정 세계는 켜도 꺼진다. 사슴 글자 (eco.V3Debug)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "../WildGoldenVectorsV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoWildV3Test
{
	namespace GW = EcoWorldV3::GoldenWild;

	// 같은 식을 같은 순서로 계산하므로 비트 단위로 같아야 한다. 허용은 표시용 여유다
	constexpr double kTol = 1.0e-15;

	/** 먹이 없는 세계 (위협 없음, 재생 0): 대사만으로 굶는다. 부활 없음 — 처음 굶은 스텝의 배·비축을 본다. */
	void InitStarveWorld(EcoWorldV3::FReferenceWorld& Ref, bool bReserve, std::int32_t DayPeriod)
	{
		EcoWorldV3::FWorldConfig C;
		C.Seed = 20000;
		C.NumHerbivores = 16;
		C.NumStalkers = 0;
		C.NumChasers = 0;
		C.NumRanged = 0;
		C.NumNocturnal = 0;
		C.DayPeriod = DayPeriod;
		C.bRespawnDead = false;
		C.WildReserve.bEnabled = bReserve;
		Ref.Init(C);
		for (size_t k = 0; k < Ref.World.Food.Food.size(); ++k)
		{
			Ref.World.Food.Food[k] = 0.0;
			Ref.World.Food.Regen[k] = 0.0;
		}
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWildV3ReserveGoldenTest,
	"AdaptiveEcosystem.Policy.V3.Wild.ReserveGolden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWildV3ReserveGoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	namespace GW = EcoWorldV3::GoldenWild;
	const FWildReserveConfig Cfg;
	const EcoRepertoireV3::FRepertoireConfig& RC = EcoRepertoireV3::kR1bConfig;
	TestFalse(TEXT("비축 기본은 끔 (R1b 학습 세계 그대로)"), Cfg.bEnabled);
	TestFalse(TEXT("세계 설정 기본도 끔"), FWorldConfig().WildReserve.bEnabled);
	TestEqual(TEXT("reserve_days"), Cfg.ReserveDays, GW::kReserveDays);
	TestEqual(TEXT("init"), Cfg.Init, GW::kReserveInit);
	TestEqual(TEXT("refill_e"), Cfg.RefillE, GW::kRefillE);
	TestEqual(TEXT("refill_frac"), Cfg.RefillFrac, GW::kRefillFrac);
	TestEqual(TEXT("weak_e"), Cfg.WeakE, GW::kWeakE);
	TestEqual(TEXT("weak_speed"), Cfg.WeakSpeed, GW::kWeakSpeed);
	TestEqual(TEXT("하루 = 통합 모드 900 스텝"), FWorldConfig().DayPeriod, GW::kDayPeriod);
	TestEqual(TEXT("energy_drain"), RC.EnergyDrain, GW::kEnergyDrain);
	TestEqual(TEXT("init_energy"), RC.InitEnergy, GW::kInitEnergy);
	TestEqual(TEXT("max_energy"), RC.MaxEnergy, GW::kMaxEnergy);
	const double Cap = WildReserveCapacity(Cfg, GW::kDayPeriod, RC.EnergyDrain);
	TestEqual(TEXT("용량 C = 3 × 900 × 0.002 (비트 단위)"), Cap, GW::kReserveCap);

	// 비축 한 번
	int32 Bad = 0;
	double MaxErr = 0.0;
	for (int32 c = 0; c < GW::kReserveCaseCount; ++c)
	{
		const double* Row = &GW::kReserveCases[c * 5];
		double E = Row[0];
		double R = Row[2];
		WildReserveStep(E, R, Row[1], Cap, Cfg);
		const double Err = FMath::Max(FMath::Abs(E - Row[3]), FMath::Abs(R - Row[4]));
		MaxErr = FMath::Max(MaxErr, Err);
		if (Err > EcoWildV3Test::kTol)
		{
			++Bad;
			AddError(FString::Printf(TEXT("비축 한 번 사례 %d: (E, R) = (%.17g, %.17g), 파이썬 (%.17g, %.17g)"), c, E, R, Row[3], Row[4]));
		}
	}
	AddInfo(FString::Printf(TEXT("비축 한 번: 사례 %d, 어긋남 %d, 최대 오차 %.3e"), GW::kReserveCaseCount, Bad, MaxErr));

	// 굶음 열 (걷기 대사만, 먹이 0)
	{
		double E = RC.InitEnergy;
		double R = Cfg.Init;
		int32 Sample = 1;
		int32 DeathStep = -1;
		int32 SampleBad = 0;
		for (int32 t = 1; t <= 100000; ++t)
		{
			double En = E - RC.EnergyDrain + 0.0;
			En = En < RC.MaxEnergy ? En : RC.MaxEnergy;
			WildReserveStep(En, R, 0.0, Cap, Cfg);
			E = En;
			while (Sample < GW::kStarveSampleCount && GW::kStarveSampleStep[Sample] == t)
			{
				if (FMath::Abs(E - GW::kStarveSampleE[Sample]) > EcoWildV3Test::kTol || FMath::Abs(R - GW::kStarveSampleR[Sample]) > EcoWildV3Test::kTol)
				{
					++SampleBad;
				}
				++Sample;
			}
			if (E <= 0.0 && R <= 0.0)
			{
				DeathStep = t;
				break;
			}
		}
		TestEqual(TEXT("굶음 열: 죽는 스텝 = 파이썬 (명세 약 2950)"), DeathStep, GW::kStarveDeathStep);
		TestEqual(TEXT("굶음 열: 표본 어긋남 0"), SampleBad, 0);
		TestEqual(TEXT("굶음 열: 표본을 모두 봤다"), Sample, GW::kStarveSampleCount);
	}

	// 섞음 열 (먹이 무늬, 채움·꺼냄이 번갈아)
	{
		double E = GW::kMixedStartE;
		double R = GW::kMixedStartR;
		int32 MixBad = 0;
		double MixErr = 0.0;
		for (int32 t = 0; t < GW::kMixedSteps; ++t)
		{
			const double G = ((t / 50) % 3 == 0) ? GW::kMixedGain : 0.0;
			double En = E - RC.EnergyDrain + G;
			En = En < RC.MaxEnergy ? En : RC.MaxEnergy;
			WildReserveStep(En, R, G, Cap, Cfg);
			E = En;
			const double Err = FMath::Max(FMath::Abs(E - GW::kMixedER[2 * t]), FMath::Abs(R - GW::kMixedER[2 * t + 1]));
			MixErr = FMath::Max(MixErr, Err);
			MixBad += Err > EcoWildV3Test::kTol ? 1 : 0;
		}
		TestEqual(TEXT("섞음 열: 어긋난 스텝 0"), MixBad, 0);
		AddInfo(FString::Printf(TEXT("섞음 열: 스텝 %d, 최대 오차 %.3e"), GW::kMixedSteps, MixErr));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWildV3ReserveWorldTest,
	"AdaptiveEcosystem.Policy.V3.Wild.ReserveWorld",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWildV3ReserveWorldTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	const EcoRepertoireV3::FRepertoireConfig& RC = EcoRepertoireV3::kR1bConfig;
	const double WeakMaxStep = RC.HerbSpeed * RC.GaitSpeed[EcoRepertoireV3::kGaitRun] * FWildReserveConfig().WeakSpeed;

	// 끔: 먹이가 없으면 E 0.5 가 대사로 바닥나 300 스텝 안에 모두 굶는다 (지금 규칙)
	{
		FReferenceWorld Off;
		EcoWildV3Test::InitStarveWorld(Off, false, 900);
		for (int32 t = 0; t < 300; ++t)
		{
			Off.StepOnce();
		}
		TestTrue(TEXT("끔: 300 스텝 안에 굶음이 있다"), Off.World.Stats.Starved > 0);
		TestEqual(TEXT("끔: 비축 칸은 늘 0"), Off.Bodies[0].Reserve, 0.0);
		TestEqual(TEXT("끔: 비축 기록 0"), Off.World.Stats.ReserveLiveSteps, static_cast<int64>(0));
	}
	// 낮 고정 세계는 켜도 꺼진다 (파이썬도 daynight 없이 켤 수 없다)
	{
		FReferenceWorld Day;
		EcoWildV3Test::InitStarveWorld(Day, true, 0);
		TestFalse(TEXT("낮 고정: 비축 꺼짐"), Day.World.Config.WildReserve.bEnabled);
		TestEqual(TEXT("낮 고정: 용량 0"), Day.World.ReserveCap, 0.0);
	}
	// 켬: 300 스텝에는 아무도 굶지 않고, 모두 배가 비어 비축으로 살며 약하다(느림). 그 뒤 굶는 사슴은 배·비축 모두 0
	FReferenceWorld On;
	EcoWildV3Test::InitStarveWorld(On, true, 900);
	TestTrue(TEXT("켬: 시작 비축 가득"), On.Bodies[0].Reserve == 1.0);
	TestEqual(TEXT("켬: 용량 5.4"), On.World.ReserveCap, EcoWorldV3::GoldenWild::kReserveCap);
	int32 FastWeak = 0;
	for (int32 t = 0; t < 300; ++t)
	{
		On.StepOnce();
		for (const FHerbBody& B : On.Bodies)
		{
			const double Dx = B.Pos.X - B.PrevPos.X;
			const double Dy = B.Pos.Y - B.PrevPos.Y;
			FastWeak += (B.bWeak && std::sqrt(Dx * Dx + Dy * Dy) > WeakMaxStep + 1.0e-9) ? 1 : 0;
		}
	}
	TestEqual(TEXT("켬: 300 스텝 굶음 0"), On.World.Stats.Starved, static_cast<int64>(0));
	TestEqual(TEXT("켬: 약한 사슴은 뛰기 × 0.75 보다 빨리 가지 않는다"), FastWeak, 0);
	int32 OnReserve = 0;
	int32 Empty = 0;
	int32 Weak = 0;
	for (const FHerbBody& B : On.Bodies)
	{
		OnReserve += (B.Energy <= 0.0 && B.Reserve > 0.0 && B.Reserve < 1.0) ? 1 : 0;
		Empty += (B.Energy <= 0.0 && B.Reserve <= 0.0) ? 1 : 0;
		Weak += B.bWeak ? 1 : 0;
	}
	TestTrue(TEXT("켬: 배가 비어 비축으로 사는 사슴이 있다"), OnReserve > 0);
	TestEqual(TEXT("켬: 배·비축 모두 빈 사슴은 없다"), Empty, 0);
	TestEqual(TEXT("켬: 모두 약함"), Weak, On.NumHerbivores());
	TestTrue(TEXT("켬: 비축 꺼내 씀 기록 > 0"), On.World.Stats.ReserveUsed > 0.0);
	TestTrue(TEXT("켬: 약한 개체·스텝 기록 > 0"), On.World.Stats.WeakSteps > 0);
	// 비축까지 바닥날 때까지 (걷기 대사면 약 2950 스텝. 서기·잠은 대사가 작아 더 버틴다 — 넉넉히 12000 스텝까지)
	TArray<bool> Dead;
	Dead.Init(false, On.NumHerbivores());
	int32 BadDeath = 0;
	int32 Deaths = 0;
	for (int32 t = 300; t < 12000 && Deaths < On.NumHerbivores(); ++t)
	{
		On.StepOnce();
		for (int32 i = 0; i < On.NumHerbivores(); ++i)
		{
			const FHerbBody& B = On.Bodies[static_cast<size_t>(i)];
			if (!Dead[i] && B.DeathCause == kDeathStarved)
			{
				Dead[i] = true;
				++Deaths;
				BadDeath += (B.Energy <= 0.0 && B.Reserve <= 0.0) ? 0 : 1;
			}
		}
	}
	TestTrue(TEXT("켬: 비축이 바닥나면 굶는다 (먹이 0)"), Deaths > 0);
	AddInfo(FString::Printf(TEXT("켬: 먹이 없는 세계 12000 스텝 안 굶음 %d/%d, 첫 굶음 전 비축 꺼내 씀 합 %.2f"), Deaths, On.NumHerbivores(),
							On.World.Stats.ReserveUsed));
	TestEqual(TEXT("켬: 굶어 죽는 사슴은 배·비축 모두 0"), BadDeath, 0);

	// 사슴 글자 (eco.V3Debug): 켠 세계는 배고픔 대신 비축·약함을 보인다. 끈 세계는 지금 그대로
	{
		EcoRepertoireV3::FRepState Rep;
		Rep.Behavior = EcoRepertoireV3::kGraze;
		FHerbBody Body;
		Body.Energy = 0.05;
		Body.Reserve = 0.63;
		Body.bWeak = true;
		FColor Color;
		TestEqual(TEXT("글자: 배고픔 비축 63% 약함(느림)"), EcoV3Integrated::DeerLabel(Rep, Body, false, Color, kKeepNone, true),
				  FString(TEXT("먹기 5% 배고픔 비축 63% 약함(느림)")));
		Body.Reserve = 0.0;
		TestEqual(TEXT("글자: 비축 바닥"), EcoV3Integrated::DeerLabel(Rep, Body, false, Color, kKeepNone, true),
				  FString(TEXT("먹기 5% 배고픔 비축 바닥 약함(느림)")));
		Body.Energy = 0.8;
		Body.Reserve = 0.2;
		Body.bWeak = false;
		TestEqual(TEXT("글자: 배는 괜찮고 비축 20%"), EcoV3Integrated::DeerLabel(Rep, Body, false, Color, kKeepNone, true),
				  FString(TEXT("먹기 80% 비축 20%")));
		Body.Energy = 0.05;
		TestEqual(TEXT("글자: 끈 세계는 지금 그대로"), EcoV3Integrated::DeerLabel(Rep, Body, false, Color), FString(TEXT("먹기 5% 굶주림")));
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
