#include "Creature/Runtime/EcoFaunaExperience.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaExperienceEstimateTest, "AdaptiveEcosystem.Fauna.Experience.Estimate",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoFaunaExperienceEstimateTest::RunTest(const FString&)
{
	using enum EEcoExperienceOutcome;
	const FEcoExperienceKey First{EEcoExperienceActivity::Patch, TEXT("Meadow"), TEXT("Shared"), FIntVector(0, 0, 0)};
	const FEcoExperienceKey Second{EEcoExperienceActivity::Patch, TEXT("Meadow"), TEXT("Shared"), FIntVector(1, 0, 0)};
	FEcoFaunaExperience Memory;
	TestEqual(TEXT("No evidence is neutral"), Memory.Preference(First, 0.), 1.);
	TestTrue(TEXT("First failure is accepted"), Memory.Observe(First, 10., RouteBlocked));
	TestFalse(TEXT("Repeat contact within the sample interval is ignored"), Memory.Observe(First, 10.5, RouteBlocked));
	TestFalse(TEXT("Older receipt is ignored"), Memory.Observe(First, 9., Completed));
	TestTrue(TEXT("Failed access is less preferred"), Memory.Preference(First, 10.) < 1.);
	TestEqual(TEXT("Other access to the same stock remains neutral"), Memory.Preference(Second, 10.), 1.);
	TestTrue(TEXT("Old failure moves toward neutral with server time"),
		Memory.Preference(First, 130.) > Memory.Preference(First, 10.) && Memory.Preference(First, 130.) < 1.);
	TestTrue(TEXT("A later success can reverse the preference"), Memory.Observe(First, 130., Completed) &&
		Memory.Preference(First, 130.) > 1.);
	for (int32 Index = 1; Index <= 64; ++Index)
		Memory.Observe(First, 130. + 2. * Index, Completed);
	TestTrue(TEXT("Accumulation is bounded"), Memory.Sites[0].IsValid(258.) && Memory.Preference(First, 258.) < 1.25);
	for (int32 Index = 1; Index <= 32; ++Index)
		Memory.Observe({EEcoExperienceActivity::Perch, TEXT("Meadow"), NAME_None, FIntVector(Index, 0, 0)}, 300. + Index, Completed);
	TestEqual(TEXT("Fixed per-agent memory bound"), Memory.Sites.Num(), FEcoFaunaExperience::MaxSites);
	TestTrue(TEXT("Frequent perch observations preserve the uncommon food history"), Memory.Preference(First, 332.) > 1.);
	TestEqual(TEXT("The oldest perch is replaced within its activity"),
		Memory.Preference({EEcoExperienceActivity::Perch, TEXT("Meadow"), NAME_None, FIntVector(1, 0, 0)}, 332.), 1.);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaExperienceOutcomeTest, "AdaptiveEcosystem.Fauna.Experience.OutcomeAttribution",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoFaunaExperienceOutcomeTest::RunTest(const FString&)
{
	using enum EEcoExperienceOutcome;
	const FEcoExperienceKey Site{EEcoExperienceActivity::Patch, TEXT("Meadow"), TEXT("Food")};
	FEcoFaunaExperience Memory;
	TestTrue(TEXT("Arrival and meal establish baseline"), Memory.Observe(Site, 10., Completed));
	TestTrue(TEXT("A threat right after eating is still counted"), Memory.Observe(Site, 10.1, ThreatInterrupted));
	TestFalse(TEXT("Repeated threat samples within two seconds do not stack"), Memory.Observe(Site, 10.2, ThreatInterrupted));
	TestEqual(TEXT("Interrupted feeding keeps learned physical access"), Memory.Sites[0].Success, 1.);
	TestEqual(TEXT("Interrupted feeding is no route failure"), Memory.Sites[0].Failure, 0.);
	TestTrue(TEXT("Danger affects preference immediately"), Memory.Preference(Site, 10.1) < 1.);
	TestTrue(TEXT("Temporary danger fades sooner than successful access"), Memory.Preference(Site, 100.1) > 1.);
	TestTrue(TEXT("Loss of habitat is its own observation"), Memory.Observe(Site, 101., HabitatUnavailable));
	TestEqual(TEXT("Habitat change also keeps access evidence"), Memory.Sites[0].Failure, 0.);
	TestTrue(TEXT("Habitat unavailability does not refresh danger"), Memory.Sites[0].DangerAt == 10.1);
	TestTrue(TEXT("Restored sample is valid"), Memory.Sites[0].IsValid(101.));
	TestFalse(TEXT("Archived sample cannot be from the future"), Memory.Sites[0].IsValid(100.));

	const FEcoExperienceKey Detour{EEcoExperienceActivity::Passage, TEXT("Meadow"), TEXT("Forest")};
	Memory.Observe(Detour, 10., TimedOut);
	TestEqual(TEXT("Timeout has less weight than observed obstruction"), Memory.Sites.Last().Failure, .5);
	for (int32 Index = 1; Index <= 48; ++Index)
	{
		const double At = 10. + 3. * Index;
		Memory.Observe(Detour, At, RouteBlocked);
		Memory.Observe(Detour, At, ThreatInterrupted);
		Memory.Observe(Detour, At, HabitatUnavailable);
	}
	TestEqual(TEXT("Compounding evidence is still bounded"), Memory.Preference(Detour, 154.), FEcoExperienceEstimate::MinPreference);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaDevelopmentTest, "AdaptiveEcosystem.Fauna.Experience.LongTermDevelopment",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoFaunaDevelopmentTest::RunTest(const FString&)
{
	FEcoFaunaExperience WellFed, Deprived;
	auto& Development = WellFed.LongTerm;
	Development.SampleCondition(0., 1.);
	Development.SampleCondition(1., 1.);
	TestEqual(TEXT("A single meal cannot change shape"), Development.BodyConditionByte(), uint8(128));
	for (double At = 0.; At <= 180.; At += 10.)
	{
		Development.SampleCondition(At, 1.);
		Deprived.LongTerm.SampleCondition(At, .05);
	}
	const uint8 FedShape = Development.BodyConditionByte();
	TestTrue(TEXT("Identical ages and genes can have different condition shapes"),
		FedShape > 128 && Deprived.LongTerm.BodyConditionByte() < 128);
	Development.ObserveExploration(20., EEcoExperienceOutcome::Completed);
	Development.ObserveExploration(21., EEcoExperienceOutcome::RouteBlocked);
	Development.ObserveExploration(50., EEcoExperienceOutcome::ThreatInterrupted);
	TestEqual(TEXT("Route learning is debounced and ignores threat events"), Development.ExplorationAt, 20.);
	TestTrue(TEXT("Exploration is still elevated after a minute"), Development.ExplorationFactor(80.) > 1.01);
	TestTrue(TEXT("Exploration later returns toward baseline"), Development.ExplorationFactor(620.) < Development.ExplorationFactor(80.));
	Development.ObservePartner(2, 30., false);
	Development.ObservePartner(2, 32., false);
	TestEqual(TEXT("Contact in adjacent decisions cannot farm familiarity"), Development.Partners[0].At, 30.);
	Development.ObservePartner(2, 60., true);
	TestTrue(TEXT("Committed care strengthens an individual relationship"), Development.FamiliarityWith(2, 70.) > .35);
	TestEqual(TEXT("No familiarity transfers to a different agent"), Development.FamiliarityWith(3, 70.), 0.);
	for (int64 Id = 3; Id <= 12; ++Id) Development.ObservePartner(Id, 70. + Id, false);
	TestEqual(TEXT("Relationships use bounded capacity"), Development.Partners.Num(), FEcoFaunaLongTermExperience::MaxPartners);
	TestTrue(TEXT("Checkpoint state validates"), Development.IsValid(1, 180.));
	TestFalse(TEXT("A relationship to self is invalid"), Development.IsValid(12, 180.));
	WellFed.RetainBodyCondition();
	TestEqual(TEXT("Corpse keeps its final body shape"), WellFed.LongTerm.BodyConditionByte(), FedShape);
	TestTrue(TEXT("Corpse discards its interaction memory"), WellFed.LongTerm.Partners.IsEmpty() && WellFed.LongTerm.ExplorationAt < 0.);
	return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoEncounterEstimatorTest, "AdaptiveEcosystem.Fauna.Experience.InterspeciesEstimate",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoEncounterEstimatorTest::RunTest(const FString&)
{
	const FEcoEncounterKey Hunt{EEcoEncounterKind::Hunt, EEcoEncounterMedium::Ground, TEXT("Bank"), TEXT("Rabbit")};
	FEcoFaunaExperience Memory;
	Memory.ObserveEncounter(Hunt, 10., 0.);
	const double Discouraged = Memory.Encounters[0].Factor(10.);
	TestTrue(TEXT("A resolved setback makes this prey less attractive"), Discouraged < 1.);
	Memory.ObserveEncounter(Hunt, 10., 1.);
	TestEqual(TEXT("Duplicate boundary receipts cannot change the estimate"), Memory.Encounters[0].Factor(10.), Discouraged);
	TestTrue(TEXT("Old evidence relaxes toward the prior"), Memory.Encounters[0].Factor(160.) > Discouraged);
	Memory.ObserveEncounter(Hunt, 160., 1.);
	TestTrue(TEXT("Later outcomes can reverse the preference"), Memory.Encounters[0].Factor(160.) > 1.);
	auto OtherContext = Hunt;
	OtherContext.Medium = EEcoEncounterMedium::Water;
	TestNull(TEXT("A ground result is not carried into water"), Memory.FindEncounter(OtherContext));
	OtherContext = Hunt;
	OtherContext.Kind = EEcoEncounterKind::Risk;
	TestNull(TEXT("Hunt outcomes are not copied to avoidance"), Memory.FindEncounter(OtherContext));
	for (int32 Index = 1; Index <= 256; ++Index)
		Memory.ObserveEncounter(Hunt, 160. + Index, 1.);
	TestTrue(TEXT("The estimate caps evidence and choice influence"), Memory.Encounters[0].IsValid(416.)
		&& Memory.Encounters[0].Factor(416.) <= FEcoEncounterEstimate::MaxFactor);
	for (int32 Index = 0; Index <= FEcoFaunaExperience::MaxEncounters; ++Index)
		Memory.ObserveEncounter({EEcoEncounterKind::Plants, EEcoEncounterMedium::Ground,
			TEXT("Bank"), TEXT("Rabbit"), NAME_None, FIntVector(Index, 0, 0)}, 450. + Index, .25);
	TestEqual(TEXT("Sparse per-individual memory stays bounded"), Memory.Encounters.Num(), FEcoFaunaExperience::MaxEncounters);
	const auto OldMeal = Memory.Encounters[0].Key;
	for (int32 Index = 0; Index <= FEcoFaunaExperience::MaxInteractionEncounters; ++Index)
		Memory.ObserveEncounter({EEcoEncounterKind::Alarm, EEcoEncounterMedium::Ground,
			TEXT("Bank"), TEXT("Crow"), NAME_None, FIntVector(Index, 0, 0)}, 500. + Index, 1.);
	TestNotNull(TEXT("Recording warnings cannot evict food and threat observations"), Memory.FindEncounter(OldMeal));
	TestEqual(TEXT("Warnings have their own bounded budget"), Memory.Encounters.Num(),
		FEcoFaunaExperience::MaxEncounters + FEcoFaunaExperience::MaxInteractionEncounters);
	Memory.RetainBodyCondition();
	TestTrue(TEXT("Death discards encounter estimation"), Memory.Encounters.IsEmpty());
	return true;
}
#endif
