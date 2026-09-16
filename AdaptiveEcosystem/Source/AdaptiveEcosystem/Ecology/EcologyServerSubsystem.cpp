// Copyright Epic Games, Inc. All Rights Reserved.

#include "Ecology/EcologyServerSubsystem.h"
#include "Engine/World.h"
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

	// Pre-populate with the initial dummy vertical slice profile: Forest_A x Wolf
	FSpeciesEvolutionProfile DummyWolf = CreateDummyWolfProfile();
	SetSpeciesEvolutionProfile(DummyWolf);

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("EcologyServerSubsystem initialized with dummy vertical slice (Forest_A x Wolf)."));
}

void UEcologyServerSubsystem::Deinitialize()
{
	AuthoritativeProfiles.Empty();
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
