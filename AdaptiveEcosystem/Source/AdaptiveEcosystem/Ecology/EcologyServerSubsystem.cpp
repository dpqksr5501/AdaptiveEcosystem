// Copyright Epic Games, Inc. All Rights Reserved.

#include "Ecology/EcologyServerSubsystem.h"
#include "Engine/World.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "AdaptiveEcosystem.h"


bool UEcologyServerSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	if (!Super::ShouldCreateSubsystem(Outer))
	{
		return false;
	}

	const UWorld* World = Cast<UWorld>(Outer);
	if (!World)
	{
		return false;
	}

	// Never create this authoritative subsystem on pure clients (NM_Client).
	// Runs strictly on Standalone, Listen Server, or Dedicated Server.
	const ENetMode NetMode = World->GetNetMode();
	const bool bIsServerOrStandalone = (NetMode != NM_Client);

	if (!bIsServerOrStandalone)
	{
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyServerSubsystem: Skipped creation on NM_Client world."));
	}

	return bIsServerOrStandalone;
}

bool UEcologyServerSubsystem::HasServerAuthority() const
{
	if (const UWorld* World = GetWorld())
	{
		return World->GetNetMode() != NM_Client;
	}
	return false;
}

FName UEcologyServerSubsystem::MakeProfileKey(FName RegionId, FName SpeciesId)
{
	return FName(*FString::Printf(TEXT("%s_%s"), *RegionId.ToString(), *SpeciesId.ToString()));
}

FSpeciesEvolutionProfile UEcologyServerSubsystem::CreateDummyWolfProfile()
{
	FSpeciesEvolutionProfile Profile;
	Profile.RegionId = FName(TEXT("Forest_A"));
	Profile.SpeciesId = FName(TEXT("Wolf"));
	Profile.Generation = 1;
	Profile.ProfileRevision = 1;

	// Initial MVP traits requested by INITIAL_REPO_BOOTSTRAP.md:
	// BodyScale = 0.90
	// MoveSpeedMultiplier = 1.10
	// Fear = 0.80
	// Aggression = 0.20
	Profile.Phenotype.BodyScale = 0.90f;
	Profile.Gameplay.MoveSpeedMultiplier = 1.10f;
	Profile.Behavior.Fear = 0.80f;
	Profile.Behavior.Aggression = 0.20f;

	return Profile;
}

void UEcologyServerSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	AuthoritativeProfiles.Empty();
	AuthoritativeVegetationProfiles.Empty();
	RegionalGrazingPressure.Empty();
	RegionalHarvestPressure.Empty();
	RegionalPlayerPressure.Empty();

	// Pre-populate with initial dummy vertical slice profiles:
	// 1. Monster: Forest_A x Wolf
	FSpeciesEvolutionProfile DummyWolf = CreateDummyWolfProfile();
	SetSpeciesEvolutionProfile(DummyWolf);

	// 2. Vegetation: Forest_A x Grass_A
	FVegetationEvolutionProfile DummyGrass = CreateDummyGrassProfile();
	SetVegetationEvolutionProfile(DummyGrass);

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyServerSubsystem initialized with dummy vertical slice (Forest_A x Wolf, Forest_A x Grass_A)."));
}

void UEcologyServerSubsystem::Deinitialize()
{
	AuthoritativeProfiles.Empty();
	AuthoritativeVegetationProfiles.Empty();
	RegionalGrazingPressure.Empty();
	RegionalHarvestPressure.Empty();
	RegionalPlayerPressure.Empty();
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyServerSubsystem deinitialized."));
	Super::Deinitialize();
}


bool UEcologyServerSubsystem::GetSpeciesEvolutionProfile(FName RegionId, FName SpeciesId, FSpeciesEvolutionProfile& OutProfile) const
{
	const FName Key = MakeProfileKey(RegionId, SpeciesId);
	if (const FSpeciesEvolutionProfile* FoundProfile = AuthoritativeProfiles.Find(Key))
	{
		OutProfile = *FoundProfile;
		return true;
	}

	// Fallback for Forest_A x Wolf if key was missing
	if (RegionId == FName(TEXT("Forest_A")) && SpeciesId == FName(TEXT("Wolf")))
	{
		OutProfile = CreateDummyWolfProfile();
		return true;
	}

	UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyServerSubsystem: No profile found for Region [%s], Species [%s]"),
		*RegionId.ToString(), *SpeciesId.ToString());
	return false;
}

void UEcologyServerSubsystem::SetSpeciesEvolutionProfile(const FSpeciesEvolutionProfile& InProfile)
{
	if (!HasServerAuthority())
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyServerSubsystem: Attempted to mutate authoritative profile on NM_Client! Rejected."));
		return;
	}

	const FName Key = MakeProfileKey(InProfile.RegionId, InProfile.SpeciesId);
	AuthoritativeProfiles.Add(Key, InProfile);

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyServerSubsystem: Committed profile for [%s] (Rev: %lld, Scale: %.2f, Speed: %.2f, Fear: %.2f, Aggression: %.2f)"),
		*Key.ToString(), InProfile.ProfileRevision, InProfile.Phenotype.BodyScale, InProfile.Gameplay.MoveSpeedMultiplier,
		InProfile.Behavior.Fear, InProfile.Behavior.Aggression);
}

bool UEcologyServerSubsystem::CommitEvolutionProposal(
	FName RegionId,
	FName SpeciesId,
	const FEvolutionProposal& Proposal,
	int32 ExpectedWorldEpoch,
	int32 ExpectedContextRevision,
	FSpeciesEvolutionProfile& OutCommittedProfile,
	FString& OutRejectReason)
{
	if (!HasServerAuthority())
	{
		OutRejectReason = TEXT("Must have server authority to commit evolution proposals.");
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyServerSubsystem: %s"), *OutRejectReason);
		return false;
	}

	FSpeciesEvolutionProfile CurrentProfile;
	if (!GetSpeciesEvolutionProfile(RegionId, SpeciesId, CurrentProfile))
	{
		OutRejectReason = FString::Printf(TEXT("Base profile not found for [%s x %s]"), *RegionId.ToString(), *SpeciesId.ToString());
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyServerSubsystem: %s"), *OutRejectReason);
		return false;
	}

	// Validate and apply proposal through the Evolution Validator
	const FEvolutionValidationResult ValidationResult = UEvolutionValidator::ValidateAndApplyProposal(
		CurrentProfile,
		Proposal,
		ExpectedWorldEpoch,
		ExpectedContextRevision);

	if (!ValidationResult.bAccepted)
	{
		OutRejectReason = ValidationResult.RejectReason;
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyServerSubsystem: Proposal rejected for [%s x %s]: %s"),
			*RegionId.ToString(), *SpeciesId.ToString(), *OutRejectReason);
		return false;
	}

	// Commit new authoritative profile
	SetSpeciesEvolutionProfile(ValidationResult.CommittedProfile);
	OutCommittedProfile = ValidationResult.CommittedProfile;
	return true;
}

FVegetationEvolutionProfile UEcologyServerSubsystem::CreateDummyGrassProfile()
{
	FVegetationEvolutionProfile Profile;
	Profile.RegionId = FName(TEXT("Forest_A"));
	Profile.VegetationSpeciesId = FName(TEXT("Grass_A"));
	Profile.Generation = 1;
	Profile.ProfileRevision = 1;

	// Initial MVP traits requested by 진화모델_확장.md:
	// GrowthRate = 1.00
	// RegenerationRate = 1.00
	// GrazingResistance = 0.50
	Profile.Traits.GrowthRate = 1.00f;
	Profile.Traits.RegenerationRate = 1.00f;
	Profile.Traits.GrazingResistance = 0.50f;

	return Profile;
}

bool UEcologyServerSubsystem::GetVegetationEvolutionProfile(FName RegionId, FName VegetationSpeciesId, FVegetationEvolutionProfile& OutProfile) const
{
	const FName Key = MakeProfileKey(RegionId, VegetationSpeciesId);
	if (const FVegetationEvolutionProfile* FoundProfile = AuthoritativeVegetationProfiles.Find(Key))
	{
		OutProfile = *FoundProfile;
		return true;
	}

	// Fallback for Forest_A x Grass_A if key was missing
	if (RegionId == FName(TEXT("Forest_A")) && VegetationSpeciesId == FName(TEXT("Grass_A")))
	{
		OutProfile = CreateDummyGrassProfile();
		return true;
	}

	UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyServerSubsystem: No vegetation profile found for Region [%s], VegetationSpecies [%s]"),
		*RegionId.ToString(), *VegetationSpeciesId.ToString());
	return false;
}

void UEcologyServerSubsystem::SetVegetationEvolutionProfile(const FVegetationEvolutionProfile& InProfile)
{
	if (!HasServerAuthority())
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyServerSubsystem: Attempted to mutate authoritative vegetation profile on NM_Client! Rejected."));
		return;
	}

	const FName Key = MakeProfileKey(InProfile.RegionId, InProfile.VegetationSpeciesId);
	AuthoritativeVegetationProfiles.Add(Key, InProfile);

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyServerSubsystem: Committed vegetation profile for [%s] (Rev: %lld, Gen: %d, Growth: %.2f, Regen: %.2f, Resist: %.2f)"),
		*Key.ToString(), InProfile.ProfileRevision, InProfile.Generation,
		InProfile.Traits.GrowthRate, InProfile.Traits.RegenerationRate, InProfile.Traits.GrazingResistance);
}

bool UEcologyServerSubsystem::CommitVegetationEvolutionProposal(
	FName RegionId,
	FName VegetationSpeciesId,
	const FVegetationEvolutionProposal& Proposal,
	int32 ExpectedWorldEpoch,
	int32 ExpectedContextRevision,
	FVegetationEvolutionProfile& OutCommittedProfile,
	FString& OutRejectReason)
{
	if (!HasServerAuthority())
	{
		OutRejectReason = TEXT("Must have server authority to commit vegetation evolution proposals.");
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologyServerSubsystem: %s"), *OutRejectReason);
		return false;
	}

	FVegetationEvolutionProfile CurrentProfile;
	if (!GetVegetationEvolutionProfile(RegionId, VegetationSpeciesId, CurrentProfile))
	{
		OutRejectReason = FString::Printf(TEXT("Base vegetation profile not found for [%s x %s]"),
			*RegionId.ToString(), *VegetationSpeciesId.ToString());
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyServerSubsystem: %s"), *OutRejectReason);
		return false;
	}

	// Validate and apply proposal through the Evolution Validator
	const FVegetationValidationResult ValidationResult = UEvolutionValidator::ValidateAndApplyVegetationProposal(
		CurrentProfile,
		Proposal,
		ExpectedWorldEpoch,
		ExpectedContextRevision);

	if (!ValidationResult.bAccepted)
	{
		OutRejectReason = ValidationResult.RejectReason;
		UE_LOG(LogAdaptiveEcosystem, Warning, TEXT("EcologyServerSubsystem: Vegetation proposal rejected for [%s x %s]: %s"),
			*RegionId.ToString(), *VegetationSpeciesId.ToString(), *OutRejectReason);
		return false;
	}

	// Commit new authoritative vegetation profile
	SetVegetationEvolutionProfile(ValidationResult.CommittedProfile);
	OutCommittedProfile = ValidationResult.CommittedProfile;
	return true;
}

void UEcologyServerSubsystem::IngestEcologyEvent(const FEcologyEvent& Event)
{
	if (!HasServerAuthority())
	{
		return;
	}

	switch (Event.Type)
	{
	case EEcologyEventType::CreatureGrazed:
	{
		const FName Key = MakeProfileKey(Event.RegionId, Event.SpeciesId);
		float& Pressure = RegionalGrazingPressure.FindOrAdd(Key);
		Pressure = FMath::Clamp(Pressure + Event.Magnitude * 0.1f, 0.0f, 1.0f);
		break;
	}
	case EEcologyEventType::VegetationHarvested:
	{
		const FName Key = MakeProfileKey(Event.RegionId, Event.SpeciesId);
		float& Pressure = RegionalHarvestPressure.FindOrAdd(Key);
		Pressure = FMath::Clamp(Pressure + Event.Magnitude * 0.1f, 0.0f, 1.0f);
		break;
	}
	case EEcologyEventType::CreatureKilled:
	{
		FPlayerPressureState& Pressure = RegionalPlayerPressure.FindOrAdd(Event.RegionId);
		Pressure.HuntingPressure = FMath::Clamp(Pressure.HuntingPressure + Event.Magnitude * 0.15f, 0.0f, 1.0f);
		break;
	}
	case EEcologyEventType::CreatureDamaged:
	{
		FPlayerPressureState& Pressure = RegionalPlayerPressure.FindOrAdd(Event.RegionId);
		Pressure.ThreatPressure = FMath::Clamp(Pressure.ThreatPressure + Event.Magnitude * 0.10f, 0.0f, 1.0f);
		break;
	}
	case EEcologyEventType::Encounter:
	{
		FPlayerPressureState& Pressure = RegionalPlayerPressure.FindOrAdd(Event.RegionId);
		Pressure.EncounterPressure = FMath::Clamp(Pressure.EncounterPressure + Event.Magnitude * 0.05f, 0.0f, 1.0f);
		break;
	}
	case EEcologyEventType::Pursuit:
	{
		FPlayerPressureState& Pressure = RegionalPlayerPressure.FindOrAdd(Event.RegionId);
		Pressure.PursuitPressure = FMath::Clamp(Pressure.PursuitPressure + Event.Magnitude * 0.10f, 0.0f, 1.0f);
		break;
	}
	default:
		break;
	}
}

void UEcologyServerSubsystem::RecordGrazing(FName RegionId, FName VegetationSpeciesId, float GrazingAmount, int64 InstigatorAgentId)
{
	if (!HasServerAuthority() || GrazingAmount <= 0.0f)
	{
		return;
	}

	const FName Key = MakeProfileKey(RegionId, VegetationSpeciesId);
	float& Pressure = RegionalGrazingPressure.FindOrAdd(Key);
	Pressure = FMath::Clamp(Pressure + GrazingAmount * 0.5f, 0.0f, 1.0f);

	// Ingest grazing event for auditing
	FEcologyEvent GrazingEvent;
	GrazingEvent.EventId = FPlatformTime::Cycles64();
	GrazingEvent.Type = EEcologyEventType::CreatureGrazed;
	GrazingEvent.RegionId = RegionId;
	GrazingEvent.SpeciesId = VegetationSpeciesId;
	GrazingEvent.StableAgentId = InstigatorAgentId;
	GrazingEvent.Magnitude = GrazingAmount;
	GrazingEvent.SimTimeSeconds = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	IngestEcologyEvent(GrazingEvent);

	// Deplete vegetation in the world region based on species grazing resistance
	if (const UWorld* World = GetWorld())
	{
		if (const UEcologyWorldSubsystem* WorldSubsystem = World->GetSubsystem<UEcologyWorldSubsystem>())
		{
			if (AEcologyRegion* Region = WorldSubsystem->GetRegion(RegionId))
			{
				FVegetationEvolutionProfile Profile;
				GetVegetationEvolutionProfile(RegionId, VegetationSpeciesId, Profile);
				Region->ApplyVegetationConsumption(GrazingAmount, Profile.Traits.GrazingResistance);
			}
		}
	}

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyServerSubsystem: Recorded grazing on [%s x %s] (Amount: %.2f, Accumulated GrazingPressure: %.2f)"),
		*RegionId.ToString(), *VegetationSpeciesId.ToString(), GrazingAmount, Pressure);
}

void UEcologyServerSubsystem::TickEcologySimulation(float DeltaTime)
{
	if (!HasServerAuthority() || DeltaTime <= 0.0f)
	{
		return;
	}

	const UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	const UEcologyWorldSubsystem* WorldSubsystem = World->GetSubsystem<UEcologyWorldSubsystem>();
	if (!WorldSubsystem)
	{
		return;
	}

	// 1. Natural vegetation regrowth driven by authoritative species traits
	for (const auto& Pair : AuthoritativeVegetationProfiles)
	{
		const FVegetationEvolutionProfile& Profile = Pair.Value;
		if (AEcologyRegion* Region = WorldSubsystem->GetRegion(Profile.RegionId))
		{
			Region->ApplyVegetationRegrowth(DeltaTime, Profile.Traits.GrowthRate, Profile.Traits.RegenerationRate);
		}
	}

	// 2. Slow pressure decay over time (approx 2% per second)
	const float DecayAmount = 0.02f * DeltaTime;
	for (auto& Pair : RegionalGrazingPressure)
	{
		Pair.Value = FMath::Max(0.0f, Pair.Value - DecayAmount);
	}
	for (auto& Pair : RegionalHarvestPressure)
	{
		Pair.Value = FMath::Max(0.0f, Pair.Value - DecayAmount);
	}
	for (auto& Pair : RegionalPlayerPressure)
	{
		FPlayerPressureState& P = Pair.Value;
		P.HuntingPressure = FMath::Max(0.0f, P.HuntingPressure - DecayAmount);
		P.EncounterPressure = FMath::Max(0.0f, P.EncounterPressure - DecayAmount);
		P.PursuitPressure = FMath::Max(0.0f, P.PursuitPressure - DecayAmount);
		P.ThreatPressure = FMath::Max(0.0f, P.ThreatPressure - DecayAmount);
	}
}

float UEcologyServerSubsystem::GetGrazingPressure(FName RegionId, FName VegetationSpeciesId) const
{
	return RegionalGrazingPressure.FindRef(MakeProfileKey(RegionId, VegetationSpeciesId));
}

float UEcologyServerSubsystem::GetHarvestPressure(FName RegionId, FName VegetationSpeciesId) const
{
	return RegionalHarvestPressure.FindRef(MakeProfileKey(RegionId, VegetationSpeciesId));
}

FPlayerPressureState UEcologyServerSubsystem::GetPlayerPressure(FName RegionId) const
{
	return RegionalPlayerPressure.FindRef(RegionId);
}

bool UEcologyServerSubsystem::BuildMonsterEvolutionContext(FName RegionId, FName SpeciesId, int32 WorldEpoch, int32 ContextRevision, FEvolutionContext& OutContext) const
{
	OutContext = FEvolutionContext();
	OutContext.RegionId = RegionId;
	OutContext.SpeciesId = SpeciesId;
	OutContext.WorldEpoch = WorldEpoch;
	OutContext.ContextRevision = ContextRevision;

	if (!GetSpeciesEvolutionProfile(RegionId, SpeciesId, OutContext.CurrentProfile))
	{
		return false;
	}

	OutContext.Generation = OutContext.CurrentProfile.Generation;

	if (const UWorld* World = GetWorld())
	{
		if (const UEcologyWorldSubsystem* WorldSubsystem = World->GetSubsystem<UEcologyWorldSubsystem>())
		{
			WorldSubsystem->GetEnvironmentState(RegionId, OutContext.Environment);
		}
	}

	OutContext.Pressure = GetPlayerPressure(RegionId);
	return true;
}

bool UEcologyServerSubsystem::BuildVegetationEvolutionContext(FName RegionId, FName VegetationSpeciesId, int32 WorldEpoch, int32 ContextRevision, FVegetationEvolutionContext& OutContext) const
{
	OutContext = FVegetationEvolutionContext();
	OutContext.RegionId = RegionId;
	OutContext.VegetationSpeciesId = VegetationSpeciesId;
	OutContext.WorldEpoch = WorldEpoch;
	OutContext.ContextRevision = ContextRevision;

	if (!GetVegetationEvolutionProfile(RegionId, VegetationSpeciesId, OutContext.CurrentProfile))
	{
		return false;
	}

	OutContext.Generation = OutContext.CurrentProfile.Generation;

	if (const UWorld* World = GetWorld())
	{
		if (const UEcologyWorldSubsystem* WorldSubsystem = World->GetSubsystem<UEcologyWorldSubsystem>())
		{
			WorldSubsystem->GetEnvironmentState(RegionId, OutContext.Environment);
		}
	}

	OutContext.GrazingPressure = GetGrazingPressure(RegionId, VegetationSpeciesId);
	OutContext.HarvestPressure = GetHarvestPressure(RegionId, VegetationSpeciesId);
	return true;
}

