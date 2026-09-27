#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"
#include "EcoMassTags.generated.h"

// -----------------------------------------------------------------------------
// Mass Tags (Minimal persistent categorical state)
// -----------------------------------------------------------------------------

/** Tag present on all living logical agents */
USTRUCT()
struct FEcoAliveTag : public FMassTag
{
	GENERATED_BODY()
};

/** Tag present on Pending Dead agents */
USTRUCT()
struct FEcoPendingDeathTag : public FMassTag
{
	GENERATED_BODY()
};

// Migration

/** Tag present when agent is actively performing cross-region migration */
USTRUCT()
struct FEcoMigratingTag : public FMassTag
{
	GENERATED_BODY()
};

// Initialization

/** Tag Needing StableAgentId & Initial Region assign agents */
USTRUCT()
struct FEcoNeedsInitializationTag : public FMassTag
{
	GENERATED_BODY()
};

// Network

/** Tag Authority logic agents owning by Server */
USTRUCT()
struct FEcoAuthorityTag : public FMassTag
{
	GENERATED_BODY()
};

/** Tag non-Authority proxy for Representation owning by Client */
USTRUCT()
struct FEcoClientProxyTag : public FMassTag
{
	GENERATED_BODY()
};