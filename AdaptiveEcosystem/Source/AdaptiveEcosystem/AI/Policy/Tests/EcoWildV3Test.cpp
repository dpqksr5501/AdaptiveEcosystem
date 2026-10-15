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
//   Wild.PerceptionGolden R3 감지: 시야 300° cos·발소리 계수, 장면 12개의 소리 반경·사슴 × 늑대 알아챔·보이는 수·가장 가까운 거리
//   Wild.FlightGolden    (w3) 계수, 도주 장면 28개(test_wild1 반사 장면 12 + 난수 16)의 다음 덮기·방향·풀림 잠금 = 파이썬 _wf_update
//   Wild.FlightRun       (w3) 끈 세계는 계수와 무관하게 비트 단위로 같고 덮기 0, 켠 세계는 경계·도주가 돌고 경계 중 먹기 = 걷기·섭식 0.5·고개 듦
//   Wild.SatiationGolden (w2) 계수·하루 → 스텝, 포만 열(막 잡은 늑대 둘: 쿨다운·남은 배부름·쉼 정확히, 속력 = 파이썬 변위), 잡으면 배부름, 늑대 글자

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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWildV3SatiationGoldenTest,
	"AdaptiveEcosystem.Policy.V3.Wild.SatiationGolden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWildV3SatiationGoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoThreatV3;
	namespace GW = EcoWorldV3::GoldenWild;
	// 계수: 하루 단위 → 스텝, 세계 설정이 위협 설정으로 옮긴다
	const EcoWorldV3::FWildSatiationConfig Ws;
	TestFalse(TEXT("포만 기본은 끔"), Ws.bEnabled || FThreatConfig().bWildSatiation);
	TestEqual(TEXT("sat_days"), Ws.SatDays, GW::kSatDays);
	TestEqual(TEXT("rest_speed"), Ws.RestSpeed, GW::kRestSpeed);
	TestEqual(TEXT("sat 스텝 = 반올림(0.5 × 900)"), EcoWorldV3::WildDaysToSteps(Ws.SatDays, GW::kDayPeriod), GW::kSatSteps);
	{
		EcoWorldV3::FWorldConfig C;
		C.WildSatiation.bEnabled = true;
		EcoWorldV3::FWorldState W;
		EcoWorldV3::InitWorld(W, C);
		TestTrue(TEXT("세계 → 위협 설정: 켬"), W.ThreatCfg.bWildSatiation);
		TestEqual(TEXT("세계 → 위협 설정: 450 스텝"), W.ThreatCfg.SatSteps, GW::kSatSteps);
		C.DayPeriod = 0;
		EcoWorldV3::InitWorld(W, C);
		TestFalse(TEXT("낮 고정 세계는 켜도 꺼진다"), W.ThreatCfg.bWildSatiation);
	}

	// 포만 열: 막 잡은 늑대 (쿨다운 38·배부름 450), 낮·깨어 있음, 사슴 없음 → 37 스텝 먹기(제자리), 450 스텝 배부름(0.3 배), 그다음 사냥
	FThreatConfig Cfg;
	Cfg.PredEatCd = GW::kPredEatCd;
	Cfg.bEatInPlace = true;
	Cfg.bWildSatiation = true;
	Cfg.SatSteps = GW::kSatSteps;
	Cfg.RestSpeed = GW::kRestSpeed;
	int32 IntBad = 0;
	int32 VelBad = 0;
	int32 VelExact = 0;
	int32 HuntBad = 0;
	for (int32 m = 0; m < GW::kSatWolves; ++m)
	{
		const FThreatSpec Spec = GW::kSatWolfType[m] == 1 ? MakeStalkerSpec(0.8, false, Cfg) : MakeChaserSpec(0.8, false, false, Cfg);
		TestEqual(TEXT("늑대 기본 속력"), Spec.BaseSpeed, GW::kPredBaseSpeed);
		FThreatState T;
		T.PosX = 30.0;
		T.PosY = 30.0;
		T.Cooldown = GW::kPredEatCd;
		T.SatLeft = GW::kSatSteps;
		FThreatStepInput In;
		In.Prey = nullptr;
		In.NumPrey = 0;
		In.Dark = 0.0;
		In.WorldSize = 60.0;
		for (int32 t = 0; t < GW::kSatChainSteps; ++t)
		{
			In.WanderTurn = 0.05 * ((t % 7) - 3);   // 선회는 속력에 영향이 없다 (난수열은 다르다)
			const FThreatStepResult R = Step(Spec, T, In, Cfg);
			const std::int32_t* Row = &GW::kSatChainInt[(t * GW::kSatWolves + m) * 3];
			if (T.Cooldown != Row[0] || T.SatLeft != Row[1] || (R.bSated ? 1 : 0) != Row[2])
			{
				if (IntBad == 0)
				{
					AddError(FString::Printf(TEXT("포만 열 늑대 %d 스텝 %d: (쿨다운 %d, 배부름 %d, 쉼 %d), 파이썬 (%d, %d, %d)"), m, t, T.Cooldown,
											 T.SatLeft, R.bSated ? 1 : 0, Row[0], Row[1], Row[2]));
				}
				++IntBad;
			}
			// 사냥 = 쿨다운 0 ∧ 배부르지 않음 (깨어 있음)
			HuntBad += R.bHunting != (T.Cooldown == 0 && !R.bSated) ? 1 : 0;
			// 변위 크기: 벽에 닿은 스텝만 속력보다 작다 (파이썬 위치·선회가 달라 벽 스텝은 다를 수 있다)
			const double V = GW::kSatChainVel[t * GW::kSatWolves + m];
			if (FMath::Abs(R.Speed - V) <= 1.0e-9)
			{
				++VelExact;
			}
			else if (V > R.Speed + 1.0e-9)
			{
				++VelBad;
			}
		}
	}
	TestEqual(TEXT("포만 열: 쿨다운·남은 배부름·쉼이 파이썬과 같다"), IntBad, 0);
	TestEqual(TEXT("포만 열: 사냥 판정 = 먹기도 쉼도 아님"), HuntBad, 0);
	TestEqual(TEXT("포만 열: 파이썬 변위가 C++ 속력보다 큰 스텝 없음"), VelBad, 0);
	const int32 Total = GW::kSatChainSteps * GW::kSatWolves;
	TestTrue(TEXT("포만 열: 변위 크기 = 속력 (벽 스텝 빼고 거의 모두)"), VelExact * 10 >= Total * 9);
	AddInfo(FString::Printf(TEXT("포만 열: 늑대 %d × 스텝 %d, 변위 = 속력 %d/%d"), GW::kSatWolves, GW::kSatChainSteps, VelExact, Total));

	// 잡으면 배부름이 걸린다 (플레이어형은 아님)
	{
		FThreatState T;
		T.PosX = 10.0;
		T.PosY = 10.0;
		FPreyView P;
		P.X = 10.3;
		P.Y = 10.0;
		FThreatStepInput In;
		In.Prey = &P;
		In.NumPrey = 1;
		In.WorldSize = 60.0;
		const FThreatSpec Chaser = MakeChaserSpec(0.8, false, false, Cfg);
		const FThreatStepResult R = Step(Chaser, T, In, Cfg);
		TestEqual(TEXT("잡음"), R.Caught, 0);
		TestEqual(TEXT("잡으면 배부름 450"), T.SatLeft, GW::kSatSteps);
		TestEqual(TEXT("잡으면 먹기 38"), T.Cooldown, GW::kPredEatCd);
	}
	// 늑대 글자 (eco.V3Debug)
	{
		EcoWorldV3::FThreatAgent A;
		A.Spec = MakeChaserSpec(0.8, false, false, Cfg);
		A.State.SatLeft = 315;
		A.Last.bSated = true;
		FColor Color;
		TestEqual(TEXT("글자: 배부름·쉼 42초"), EcoV3Integrated::WolfLabel(A, Cfg, 0.0, Color), FString(TEXT("늑대 배부름·쉼 42초 (추격형)")));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWildV3PerceptionGoldenTest,
	"AdaptiveEcosystem.Policy.V3.Wild.PerceptionGolden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWildV3PerceptionGoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoObservationV3;
	namespace GW = EcoWorldV3::GoldenWild;
	// 계수 = 거울 세계, 끈 세계는 R1b 그대로
	const EcoWorldV3::FRealismVisionConfig Vc;
	const FHearingConfig Hc;
	TestFalse(TEXT("시야·발소리 기본은 끔"), Vc.bEnabled || Hc.bEnabled);
	TestEqual(TEXT("threat_fov_deg"), Vc.ThreatFovDeg, GW::kThreatFovDeg);
	TestEqual(TEXT("kin_fov_deg 는 기본 120° 그대로 (옮기지 않은 칸)"), EcoWorldV3::kBaseFovDeg, GW::kKinFovDeg);
	TestEqual(TEXT("s_silent"), Hc.SSilent, GW::kHearSSilent);
	TestEqual(TEXT("s_quiet"), Hc.SQuiet, GW::kHearSQuiet);
	TestEqual(TEXT("s_loud"), Hc.SLoud, GW::kHearSLoud);
	TestEqual(TEXT("r_quiet"), Hc.RQuiet, GW::kHearRQuiet);
	TestEqual(TEXT("r_loud"), Hc.RLoud, GW::kHearRLoud);
	TestEqual(TEXT("roam_quiet"), Hc.bRoamQuiet, GW::kHearRoamQuiet);
	TestEqual(TEXT("cap_to_sight"), Hc.bCapToSight, GW::kHearCapToSight);
	TestEqual(TEXT("see_r"), kR1bObsConfig.SeeR, GW::kSeeR);
	const double Cos300 = FovCosOf(Vc.ThreatFovDeg, EcoWorldV3::kBaseFovDeg, kR1bObsConfig.FovCos);
	TestEqual(TEXT("위협 시야 cos(150°) 비트 단위"), Cos300, GW::kThreatFovCos);
	TestEqual(TEXT("기본 시야각이면 기본 cos 그대로"), FovCosOf(120.0, 120.0, kR1bObsConfig.FovCos), kR1bObsConfig.FovCos);
	{
		EcoWorldV3::FWorldConfig C;
		EcoWorldV3::FWorldState W;
		EcoWorldV3::InitWorld(W, C);
		TestEqual(TEXT("끈 세계: 위협 시야 = 기본 120°"), W.ObsCfg.ThreatFovCos, kR1bObsConfig.FovCos);
		C.RealismVision.bEnabled = true;
		EcoWorldV3::InitWorld(W, C);
		TestEqual(TEXT("켠 세계: 위협 시야 300°"), W.ObsCfg.ThreatFovCos, GW::kThreatFovCos);
	}

	FObservationConfig Oc = kR1bObsConfig;
	Oc.ThreatFovCos = Cos300;
	Oc.bHearCapToSight = Hc.bCapToSight;
	FHearingConfig H = Hc;
	H.bEnabled = true;
	int32 HearBad = 0;
	int32 PairBad = 0;
	int32 RowBad = 0;
	int32 Pairs = 0;
	int32 Seen = 0;
	int32 HeardOnly = 0;
	for (int32 k = 0; k < GW::kPercScenes; ++k)
	{
		FThreatInput Th[GW::kPercM];
		for (int32 m = 0; m < GW::kPercM; ++m)
		{
			const double* Wv = &GW::kPercWolf[(k * GW::kPercM + m) * 6];
			Th[m].X = Wv[0];
			Th[m].Y = Wv[1];
			Th[m].VelX = Wv[2];
			Th[m].VelY = Wv[3];
			Th[m].HearR = HearingRadius(H, std::sqrt(Wv[2] * Wv[2] + Wv[3] * Wv[3]) / Oc.HerbSpeed, Wv[4] != 0.0);
			HearBad += FMath::Abs(Th[m].HearR - Wv[5]) > 1.0e-12 ? 1 : 0;
		}
		for (int32 i = 0; i < GW::kPercN; ++i)
		{
			const double* Dv = &GW::kPercDeer[(k * GW::kPercN + i) * 5];
			const EcoRepertoireV3::FVec2 Pos{Dv[0], Dv[1]};
			const EcoRepertoireV3::FVec2 Head{Dv[2], Dv[3]};
			const double SeePred = SeePredRadius(0.0, Oc);
			const FThreatPerception All = PerceiveThreats(Pos, Head, SeePred, Dv[4], Dv[4], Th, GW::kPercM, Oc);
			const int32 Row = k * GW::kPercN + i;
			const double DMin = GW::kPercDMin[Row];
			if (All.PredCount != GW::kPercCount[Row] || (DMin >= 0.0 ? FMath::Abs(All.DPredMin - DMin) > 1.0e-12 : All.Nearest >= 0))
			{
				++RowBad;
			}
			for (int32 m = 0; m < GW::kPercM; ++m)
			{
				const FThreatPerception One = PerceiveThreats(Pos, Head, SeePred, Dv[4], Dv[4], &Th[m], 1, Oc);
				const int32 Want = GW::kPercVis[Row * GW::kPercM + m];
				PairBad += (One.PredCount == 1 ? 1 : 0) != Want ? 1 : 0;
				++Pairs;
				Seen += Want;
				// 들어서만 안 쌍 (시야각·반경 밖인데 보임) — 발소리 판정이 실제로 쓰였는지 센다
				FThreatInput Mute = Th[m];
				Mute.HearR = 0.0;
				HeardOnly += (Want == 1 && PerceiveThreats(Pos, Head, SeePred, Dv[4], Dv[4], &Mute, 1, Oc).PredCount == 0) ? 1 : 0;
			}
		}
	}
	TestEqual(TEXT("소리 반경 = 파이썬 hearing_radius"), HearBad, 0);
	TestEqual(TEXT("사슴 × 늑대 알아챔 = 파이썬 wf_pvis"), PairBad, 0);
	TestEqual(TEXT("사슴마다 보이는 수·가장 가까운 거리 = 파이썬"), RowBad, 0);
	TestTrue(TEXT("장면에 보이는 쌍과 들어서만 안 쌍이 있다"), Seen > 0 && HeardOnly > 0);
	AddInfo(FString::Printf(TEXT("지각 장면 %d: 쌍 %d, 알아챔 %d, 그중 들어서만 %d"), GW::kPercScenes, Pairs, Seen, HeardOnly));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWildV3FlightGoldenTest,
	"AdaptiveEcosystem.Policy.V3.Wild.FlightGolden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWildV3FlightGoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	namespace GW = EcoWorldV3::GoldenWild;
	const FWildFlightConfig Fc;
	TestFalse(TEXT("도주 반사 기본은 끔"), Fc.bEnabled || FWorldConfig().WildFlight.bEnabled);
	TestEqual(TEXT("alert_r"), Fc.AlertR, GW::kFlightAlertR);
	TestEqual(TEXT("flight_r"), Fc.FlightR, GW::kFlightFlightR);
	TestEqual(TEXT("safe_r"), Fc.SafeR, GW::kFlightSafeR);
	TestEqual(TEXT("approach"), Fc.Approach, GW::kFlightApproach);
	TestEqual(TEXT("alert_w"), Fc.AlertW, GW::kFlightAlertW);
	TestEqual(TEXT("rest_alert"), Fc.bRestAlert, GW::kFlightRestAlert);
	TestEqual(TEXT("shelter_cos"), Fc.ShelterCos, GW::kFlightShelterCos);
	TestEqual(TEXT("shelter_r"), Fc.ShelterR, GW::kFlightShelterR);
	TestEqual(TEXT("crouch"), Fc.bCrouch, GW::kFlightCrouch);
	TestEqual(TEXT("wall_margin"), Fc.WallMargin, GW::kFlightWallMargin);

	// 거울 세계와 같은 감지·포만을 켠 기준 루프 (늑대 둘 = 추격형. 종류는 사냥 판정·알아챔에 들지 않는다)
	FWorldConfig C;
	C.WorldSize = GW::kFlightWorldSize;
	C.NumHerbivores = GW::kFlightN;
	C.NumStalkers = 0;
	C.NumChasers = GW::kFlightM;
	C.NumRanged = 0;
	C.NumNocturnal = 0;
	C.bRespawnDead = false;
	C.WildSatiation.bEnabled = true;
	C.RealismVision.bEnabled = true;
	C.RealismHearing.bEnabled = true;
	C.WildFlight.bEnabled = true;
	FReferenceWorld Ref;
	Ref.Init(C);
	int32 ModeBad = 0;
	int32 DirBad = 0;
	int32 LockBad = 0;
	int32 HandBad = 0;
	double MaxErr = 0.0;
	int32 Counts[kNumKeepModes] = {};
	for (int32 k = 0; k < GW::kFlightScenes; ++k)
	{
		FWorldState& W = Ref.World;
		W.Config.Covers.clear();
		for (int32 c = 0; c < GW::kFlightCovers; ++c)
		{
			const double* Cv = &GW::kFlightCover[(k * GW::kFlightCovers + c) * 3];
			if (Cv[2] >= 0.0)
			{
				W.Config.Covers.push_back({Cv[0], Cv[1], Cv[2]});
			}
		}
		W.Dark = 0.0;
		for (int32 m = 0; m < GW::kFlightM; ++m)
		{
			const double* Wv = &GW::kFlightWolf[(k * GW::kFlightM + m) * 8];
			FThreatAgent& A = Ref.Threats[static_cast<size_t>(m)];
			A.State.PosX = Wv[0];
			A.State.PosY = Wv[1];
			A.State.VelX = Wv[2];
			A.State.VelY = Wv[3];
			A.Last.bRunning = Wv[4] != 0.0;
			A.State.Cooldown = static_cast<int32>(Wv[5]);
			A.State.SatLeft = static_cast<int32>(Wv[6]);
			A.Last.Target = static_cast<int32>(Wv[7]);
			A.Last.bHasTarget = A.Last.Target >= 0;
			A.State.bAsleep = false;
		}
		for (int32 i = 0; i < GW::kFlightN; ++i)
		{
			const double* Dv = &GW::kFlightDeerIn[(k * GW::kFlightN + i) * 7];
			FHerbBody& B = Ref.Bodies[static_cast<size_t>(i)];
			B.Pos = {Dv[0], Dv[1]};
			B.Head = {Dv[2], Dv[3]};
			B.DeathCause = kDeathNone;
			EcoRepertoireV3::FRepState& S = Ref.Reps[static_cast<size_t>(i)];
			S.SeeMult = Dv[4];
			S.SeeMultLast = Dv[4];
			S.LockLeft = static_cast<int32>(Dv[6]);
			Ref.Decisions[static_cast<size_t>(i)].KeepActive = static_cast<int32>(Dv[5]);
		}
		ObserveAll(W, Ref.Views.data(), Ref.NumHerbivores(), Ref.ThreatPtrs.data(), Ref.NumThreats());
		Detail::UpdateWildFlight(W, Ref.Views.data(), Ref.NumHerbivores(), Ref.ThreatPtrs.data(), Ref.NumThreats());
		for (int32 i = 0; i < GW::kFlightN; ++i)
		{
			const double* O = &GW::kFlightDeerOut[(k * GW::kFlightN + i) * 4];
			const FHerbDecision& D = Ref.Decisions[static_cast<size_t>(i)];
			const int32 Want = static_cast<int32>(O[0]);
			const double Err = FMath::Max(FMath::Abs(D.KeepDir.X - O[1]), FMath::Abs(D.KeepDir.Y - O[2]));
			MaxErr = FMath::Max(MaxErr, Err);
			const bool bBad = D.KeepMode != Want || Err > 1.0e-12 || Ref.Reps[static_cast<size_t>(i)].LockLeft != static_cast<int32>(O[3]);
			ModeBad += D.KeepMode != Want ? 1 : 0;
			DirBad += Err > 1.0e-12 ? 1 : 0;
			LockBad += Ref.Reps[static_cast<size_t>(i)].LockLeft != static_cast<int32>(O[3]) ? 1 : 0;
			HandBad += (bBad && k < GW::kFlightHandScenes) ? 1 : 0;
			if (bBad && ModeBad + DirBad + LockBad <= 3)
			{
				AddError(FString::Printf(TEXT("도주 장면 %d 사슴 %d: 덮기 %d 방향 (%.17g, %.17g) 잠금 %d, 파이썬 %d (%.17g, %.17g) %d"), k, i, D.KeepMode,
										 D.KeepDir.X, D.KeepDir.Y, Ref.Reps[static_cast<size_t>(i)].LockLeft, Want, O[1], O[2], static_cast<int32>(O[3])));
			}
			++Counts[Want >= 0 && Want < kNumKeepModes ? Want : 0];
		}
	}
	TestEqual(TEXT("도주 장면: 다음 덮기 = 파이썬 _wf_update"), ModeBad, 0);
	TestEqual(TEXT("도주 장면: 방향 = 파이썬 (|Δ| ≤ 1e-12)"), DirBad, 0);
	TestEqual(TEXT("도주 장면: 풀리면 잠금 0 = 파이썬"), LockBad, 0);
	TestEqual(TEXT("tests/test_wild1.py 반사 장면 12 개 모두 같다"), HandBad, 0);
	TestTrue(TEXT("장면에 덮기 넷이 모두 나온다"), Counts[0] > 0 && Counts[1] > 0 && Counts[2] > 0 && Counts[3] > 0);
	AddInfo(FString::Printf(TEXT("도주 장면 %d (사슴 %d): 두뇌 %d · 경계 %d · 도주 %d · 웅크림 %d, 방향 최대 오차 %.3e"), GW::kFlightScenes,
							GW::kFlightScenes * GW::kFlightN, Counts[0], Counts[1], Counts[2], Counts[3], MaxErr));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoWildV3FlightRunTest,
	"AdaptiveEcosystem.Policy.V3.Wild.FlightRun",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoWildV3FlightRunTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	// 끔: 계수만 다른 끈 세계 둘은 600 스텝 비트 단위로 같고 덮기·기록이 0. 켬: 규칙이 돌고 마스크 위반 0, 경계 중 걷기 섭식 배수
	auto Make = [](bool bOn, double AlertR)
	{
		FWorldConfig C;
		C.Seed = 20001;
		C.WorldSize = 60.0;
		C.NumHerbivores = 32;
		C.Covers = QuadCovers(60.0, 6.0);
		C.WildFlight.bEnabled = bOn;
		C.WildFlight.AlertR = AlertR;
		C.WildSatiation.bEnabled = bOn;
		C.RealismVision.bEnabled = bOn;
		C.RealismHearing.bEnabled = bOn;
		return C;
	};
	FReferenceWorld A, B, On;
	A.Init(Make(false, 15.0));
	B.Init(Make(false, 3.0));
	On.Init(Make(true, 15.0));
	int32 Diff = 0;
	int32 KeepSet = 0;
	int32 AlertWalk = 0;
	int32 AlertBad = 0;
	for (int32 t = 0; t < 600; ++t)
	{
		A.StepOnce();
		B.StepOnce();
		On.StepOnce();
		for (int32 i = 0; i < A.NumHerbivores(); ++i)
		{
			const FHerbBody& Ba = A.Bodies[static_cast<size_t>(i)];
			const FHerbBody& Bb = B.Bodies[static_cast<size_t>(i)];
			Diff += (Ba.Pos.X != Bb.Pos.X || Ba.Pos.Y != Bb.Pos.Y || Ba.Energy != Bb.Energy) ? 1 : 0;
			KeepSet += A.Decisions[static_cast<size_t>(i)].KeepActive != kKeepNone ? 1 : 0;
			const FHerbDecision& D = On.Decisions[static_cast<size_t>(i)];
			if (D.KeepActive == kKeepAlert && On.Reps[static_cast<size_t>(i)].Behavior == EcoRepertoireV3::kGraze
				&& (D.KeepDir.X != 0.0 || D.KeepDir.Y != 0.0))
			{
				const EcoRepertoireV3::FControlOutput& O = On.Controls[static_cast<size_t>(i)];
				++AlertWalk;
				AlertBad += (O.Gait != EcoRepertoireV3::kGaitWalk || O.EatMult != EcoRepertoireV3::kR1bConfig.GaitEat[EcoRepertoireV3::kGaitWalk]
							 || O.SeeMult != 1.0) ? 1 : 0;
			}
		}
	}
	const FWorldStats& Sa = A.World.Stats;
	const FWorldStats& So = On.World.Stats;
	TestEqual(TEXT("끈 세계 둘 (계수만 다름)은 600 스텝 비트 단위로 같다"), Diff, 0);
	TestEqual(TEXT("끄면 덮기 칸이 늘 0"), KeepSet, 0);
	TestEqual(TEXT("끄면 도주 기록 0"), Sa.KeepAlertStarts + Sa.KeepPanicStarts + Sa.KeepShelterStarts + Sa.KeepPanicEnds, static_cast<int64>(0));
	TestTrue(TEXT("켜면 규칙이 돈다 (경계·도주 덮기 > 0)"), So.KeepSteps[kKeepAlert] > 0 && So.KeepSteps[kKeepPanic] > 0);
	TestTrue(TEXT("켬: 경계 중 먹기 사슴이 있다"), AlertWalk > 0);
	TestEqual(TEXT("켬: 경계 중 먹기 = 걷기·섭식 0.5·고개 듦"), AlertBad, 0);
	TestEqual(TEXT("켬: 마스크 위반 0"), So.MaskViolations, static_cast<int64>(0));
	AddInfo(FString::Printf(TEXT("켬 600 스텝: 경계 시작 %lld · 도주 시작 %lld · 웅크림 시작 %lld · 끝난 도주 %lld (은신처 %lld) · 경계 중 먹기 %d · 포획 %lld"),
							So.KeepAlertStarts, So.KeepPanicStarts, So.KeepShelterStarts, So.KeepPanicEnds, So.KeepPanicEndShelter, AlertWalk,
							So.Caught));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
