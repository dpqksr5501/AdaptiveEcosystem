# Social Behavior & Shelter Runtime — Architecture Context

> **Project:** AdaptiveEcosystem  
> **Engine:** Unreal Engine 5.8  
> **Repository:** `dpqksr5501/AdaptiveEcosystem`  
> **Status:** Active extension architecture  
> **Purpose:** AI coding agents and team members should read this document before implementing Social Behavior features.
>
> This document supplements, but does not replace:
>
> - `/AGENTS.md`
> - `Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md`
> - `Docs/RL_Policy/POLICY_CONTRACT_V1.md`
> - `Docs/Mass/MASS_PROCESSOR_ORDER.md`
>
> Detailed implementation rules live in:
>
> - `Docs/SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md`

---

# 1. Why this runtime exists

AdaptiveEcosystem is not only a PPO movement demo.

Its core loop is:

```text
World / Region
→ Mass logical creature state
→ Observation
→ PPO behavior policy
→ Runtime behavior execution
→ Movement / Interaction
→ Resource / Population changes
→ Region state
→ next Observation
```

The PPO decides high-level behavior tendencies:

```text
forage
cohesion
flee_dist
cover
```

However, these four numbers do not define:

```text
which creatures belong to the same persistent herd
how a threat is communicated socially
which physical shelter is valid
which shelter slot is available
how a herd recovers after scattering
```

The Social Behavior & Shelter Runtime owns those runtime responsibilities.

---

# 2. Ownership boundaries

## RL / Behavior Policy team owns

```text
Aquarium
Observation
Action
Reward
PPO training
Policy export
Policy schema
Utility baseline
```

Social Runtime must not silently change:

```text
ObservationDimension = 7
ActionDimension = 4
feature order
normalization
action meaning
network layout
```

---

## Mass / Ecology team owns

```text
Stable logical creature lifecycle
HP
Energy
Region
Travel
Population
Migration
Representation / Simulation LOD
Ecology feedback
```

Social Runtime reads these states when necessary but does not become their source of truth.

---

## World / Region team owns

```text
Region
Weather
Day / Night
Food resource
environment state
```

Social Runtime must not move these responsibilities into its own Subsystem.

---

## MassFlock / Movement owner owns

```text
local flock steering
cohesion / alignment / separation execution
movement integration
MassFlock adaptation
```

**MassFlock is not part of the Social Runtime ownership.**

---

## Social Behavior & Shelter Runtime owns

```text
Dynamic Herd
Alarm Communication
Shelter Resolution
Social Response State

Optional:
Local Avoidance execution layer
```

---

# 3. Final runtime boundary

```text
PPO Policy
forage / cohesion / flee_dist / cover
                │
                ▼
       Runtime Behavior Intent
                │
      ┌─────────┴──────────┐
      ▼                    ▼
Dynamic Herd          Threat / Alarm
      │                    │
      └─────────┬──────────┘
                ▼
          Social Response
                │
      ┌─────────┴──────────┐
      ▼                    ▼
 Group Context        Shelter Intent
                           │
                           ▼
                 Shelter Query / Score
                           │
                           ▼
                     Reservation
                           │
                           ▼
              Movement / MassFlock layer
                           │
                           ▼
                 Preferred Velocity
                           │
                           ▼
           Local Avoidance [Optional]
                           │
                           ▼
                     Safe Velocity
```

---

# 4. Dynamic Herd

A Herd is not the same thing as flock steering.

```text
Herd
= persistent logical group identity

Flock
= local movement behavior
```

Social Runtime owns:

```text
Persistent Herd ID
Membership
Join / Leave
Merge / Split
Herd Center
Average Velocity
Representative
Threat State
Recovery / Regroup
```

MassFlock owns the actual local flock movement.

Example:

```text
Creature 12
Creature 19
Creature 31
      ↓
Persistent Herd #4
      ↓
group state / group target
      ↓
MassFlock / movement
```

The initial Herd MVP does not require a behavioral leader.

A Representative may be used for:

```text
group-level query
debugging
future shelter query reduction
future alarm aggregation
```

---

# 5. Alarm Communication

Alarm is an explicit runtime social signal.

```text
Creature detects threat
→ Alarm signal
→ Herd threat state
→ nearby members / nearby herd
→ social response
```

Initial implementation must not add a new PPO observation.

Instead:

```text
PPO Output
+
Social Modifier
→ Runtime Behavior
```

Alarm can influence:

```text
cohesion multiplier
forage suppression
flee sensitivity
shelter intent
scatter / recovery state
```

but should not become an unrelated second high-level AI policy.

Preferred priority:

```text
1. amplify / attenuate existing PPO intent
2. resolve runtime targets
3. emergency override only for extreme threat
```

---

# 6. Cover / Shelter

Internally, prefer the term:

```text
Shelter
```

because this system represents refuge from a threat rather than only FPS tactical cover.

Policy V1 still keeps the existing names:

```text
cover
cover_distance
```

Runtime shelter responsibilities:

```text
Shelter Registry
Candidate Query
LOS / threat-relative validity
Safety scoring
Capacity
Slot
Reservation
Release
```

Important distinction:

```text
Policy:
"cover preference is 0.8"

Runtime:
"which shelter is valid right now?"
"which slot is free?"
"which shelter blocks this threat?"
"which agent wins the reservation?"
```

---

# 7. Local Avoidance

Local Avoidance is optional.

It is only valid as an execution layer:

```text
Preferred Velocity
→ collision-safe correction
→ Safe Velocity
```

It must not choose a new high-level goal.

Before custom ORCA:

```text
1. inspect UE 5.8 Mass avoidance
2. inspect current MassFlock avoidance
3. determine whether a gap actually exists
4. only then consider RVO2 / ORCA
```

---

# 8. Current repository contracts already available

Current `main` already defines:

```text
FEcoIdentityFragment
FEcoVitalsFragment
FEcoRegionFragment
FEcoTravelFragment
FEcoObservationFragment
FEcoPolicyOutputFragment
FEcoPolicyRuntimeFragment
FEcoSpeciesSharedFragment
FEcoAliveTag
FEcoMigratingTag
```

Do not duplicate:

```text
StableAgentId
SpeciesId
SpeciesRuntimeIndex
HP
Energy
Region
ViewDistance
FOV
CoverSearchRadius
Policy Observation
Policy Action
```

Current `FEcoSpeciesSharedFragment` already contains:

```text
BaseMoveSpeed
EnergyDecayRate
FoodConsumptionRate
FoodEnergyGain
ViewDistance
FOV
CoverSearchRadius
MigrationThreshold
```

---

# 9. Expected new Social Runtime data

Candidate per-agent state:

```text
Herd membership
Alarm state
Shelter intent
```

Candidate global runtime state:

```text
Herd runtime table
Alarm event buffer
Shelter registry
Shelter reservation table
```

Do not copy the full herd state into every Entity Fragment.

Use:

```text
compact runtime index
+
central dense runtime data
```

where practical.

---

# 10. Performance model

The target is MassEntity-style data-oriented processing.

Avoid:

```text
per-agent UObject AI
per-agent EQS
all-pairs O(N^2) searches
per-frame global map mutation
per-frame shelter LOS for all agents
per-agent dynamic allocation in hot loops
```

Prefer:

```text
shared spatial lookup
bounded neighbors
dense arrays
batch processing
two-pass reduction
proposal → reconciliation
different update frequencies
Simulation LOD
```

---

# 11. Shared spatial lookup

Herd, Alarm and optional Avoidance all require nearby entities.

Do not create:

```text
HerdGrid
AlarmGrid
AvoidanceGrid
```

independently.

First inspect:

```text
current project movement code
MassFlock integration
UE 5.8 MassNavigation
MassMovement
MassCrowd / avoidance facilities
```

Reuse existing neighbor infrastructure when possible.

Create a new Social spatial index only when reuse is not possible.

---

# 12. Third-party / OSS relationship

## Dynamic Herd

Implementation:

```text
project-native
```

References:

```text
Reynolds Boids
OpenSteer
```

These help with steering concepts, not persistent Herd lifecycle.

---

## Alarm

Implementation:

```text
project-native local broadcast / herd aggregation
```

References:

```text
ARGoS3
gossip / local broadcast concepts
```

ARGoS3 is a design reference, not a runtime dependency.

---

## Shelter

Implementation:

```text
Mass-native registry / query / reservation
```

Reference:

```text
Deams51/CoverGenerator-UE4
```

Use its cover-generation ideas where useful; do not assume the old UE4 plugin can be dropped directly into UE 5.8.

---

## Local Avoidance

First choice:

```text
UE 5.8 built-in Mass functionality
```

Optional advanced reference:

```text
RVO2 / ORCA
DetourCrowd
HRVO
```

Only port algorithmic core if there is a demonstrated gap.

---

# 13. MVP sequence

```text
0. Source Audit
1. Social data foundation
2. Herd MVP
3. Alarm MVP
4. Shelter MVP
5. Integration
6. Merge / Split / Regroup
7. Performance / LOD
8. Optional Local Avoidance
```

Do not begin with:

```text
automatic cover generation
custom ORCA
advanced fission-fusion
```

---

# 14. MVP behavior scenario

A successful early integrated demo:

```text
100 logical creatures
→ form multiple persistent herds
→ one member detects a threat
→ alarm spreads through its herd
→ social state changes
→ high shelter intent agents query valid shelters
→ slots are reserved deterministically
→ agents move using the existing movement layer
→ threat clears
→ alarm decays
→ agents recover / regroup
```

---

# 15. Non-goals

This feature does not own:

```text
PPO training redesign
new observation/action dimensions
food simulation
population source of truth
weather system
new predator RL policy
MassFlock rewrite
full multiplayer replication
save/load architecture
automatic cover generation in MVP
custom ORCA in MVP
```

---

# 16. Document priority for Social work

When implementing this feature, read in this order:

```text
1. /AGENTS.md
2. current Source
3. Docs/RL_Policy/POLICY_CONTRACT_V1.md
4. Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md
5. Docs/Mass/MASS_PROCESSOR_ORDER.md
6. Docs/SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_ARCHITECTURE.md
7. Docs/SocialBehavior/SOCIAL_BEHAVIOR_RUNTIME_IMPLEMENTATION_GUIDE.md
8. technical research documents
9. legacy Evolution documents
```

If current Source and an Active Contract conflict, report the conflict instead of silently choosing one.

---

# 17. Important documentation warning

`Docs/Architecture/아키텍처_설명.md` contains useful historical design rationale, but it also retains substantial material from the old LLM / Evolution architecture.

Therefore:

```text
Do not use that file as the current runtime source of truth
for Social Behavior implementation.
```

For current implementation use:

```text
PPO_MASS_ECOSYSTEM_ARCHITECTURE.md
POLICY_CONTRACT_V1.md
MASS_PROCESSOR_ORDER.md
this Social Behavior architecture document
current Source
```

---

# 18. One-sentence definition

> **Social Behavior & Shelter Runtime is the MassEntity-oriented runtime layer that adds persistent herd identity, local threat communication, and shelter selection/reservation without changing the PPO policy contract or taking ownership of MassFlock movement.**
