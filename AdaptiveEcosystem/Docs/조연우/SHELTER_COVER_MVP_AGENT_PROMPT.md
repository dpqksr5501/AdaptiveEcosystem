# AdaptiveEcosystem — Shelter / Cover Runtime MVP Agent Task

## 0. Repository / Branch

Repository:
`C:\Users\I\Documents\GitHub\AdaptiveEcosystem`

Unreal Project Root:
`C:\Users\I\Documents\GitHub\AdaptiveEcosystem\AdaptiveEcosystem`

User Docs:
`C:\Users\I\Documents\GitHub\AdaptiveEcosystem\AdaptiveEcosystem\Docs\조연우`

Before starting:

1. Make sure the verified `feat/social-alarm-mvp` work has been merged into `main`.
2. Pull the latest `main`.
3. Create and switch to:
   `feat/social-shelter-mvp`

Do not start from the old Shelter source without first reading the latest merged Social Runtime.

---

# 1. Project Context

The Social Behavior Runtime is intentionally separated from MassFlock / Movement.

Current responsibility boundaries:

- PPO / RL
  - decides high-level preferences
  - Action V1 remains exactly:
    `forage / cohesion / flee_dist / cover`

- Social Behavior Runtime
  - Dynamic Herd membership/state
  - Alarm communication/state
  - Shelter/Cover candidate selection and reservation

- MassFlock / Movement
  - another teammate owns actual movement/flocking/steering execution

Important:

**Do NOT implement or rewrite MassFlock.**

The Social Runtime should answer:

- Which herd does this agent belong to?
- What danger signal does it currently know?
- Does it want cover?
- Which shelter/slot should it use?
- What target position should later be handed to movement?

MassFlock should answer:

- How does the entity physically move there?

---

# 2. Current Verified State

The following MVPs are already editor-verified and should be treated as stable baselines:

## Dynamic Herd MVP
- Persistent Herd IDs
- Join / Leave
- Herd center
- Member count
- Average velocity
- Editor test harness

## Alarm Communication MVP
- Threat injection
- Herd-level alarm
- Distance attenuation
- Time decay
- Calm / Alert / Panic / Recovering / Regrouping
- Raw PPO output remains immutable
- `FEcoSocialBehaviorFragment::ModulatedAction` stores social-modulated action
- Editor test harness

Do not unnecessarily refactor either system.

---

# 3. First Task: Audit Existing Shelter Runtime

Before editing code, inspect the actual latest source and briefly report what is currently implemented and what is incomplete.

At minimum inspect:

- `AI/Social/Shelter/EcoShelterSubsystem.h/.cpp`
- `AI/Social/Shelter/EcoShelterProcessors.h/.cpp`
- `AI/Social/Shelter/EcoShelterAnchor.h/.cpp`
- `AI/Social/EcoSocialFragments.h`
- `AI/Social/EcoSocialTypes.h`
- `AI/Social/Alarm/EcoAlarmProcessors.*`
- `AI/Social/Herd/EcoHerdSubsystem.*`
- current Mass Entity traits/templates
- relevant processor ordering docs
- Root `AGENTS.md`
- `Docs/조연우/*.md`

Verify, do not assume, the following known concerns:

1. Shelter scoring currently uses a surface-normal orientation heuristic rather than true threat-relative world occlusion / LOS.
2. `FSlotProposal` exists in the reservation processor header but may not actually be used for deterministic reconciliation.
3. Reservation may currently be "first entity processed wins".
4. `UEcoShelterSubsystem` mutable reservation state may be modified from inside Mass entity loops.
5. Shelter query may still read raw `FEcoPolicyOutputFragment::Action.Cover` instead of the verified social-modulated action.
6. Shelter Query must execute after Alarm Propagation / Social Response if it consumes `FEcoSocialBehaviorFragment`.
7. No production movement implementation should be added here.
8. A reserved shelter slot currently may not expose a clean target position contract for later MassFlock integration.
9. `AEcoShelterAnchor` currently needs verification for runtime root component correctness.
10. `Radius` on `AEcoShelterAnchor` may currently be unused.
11. Shelter slot positions should be checked for correct even distribution around capacity.
12. Expired / abandoned reservations need a safe lifecycle.

After the audit, proceed with implementation only within the MVP scope below.

---

# 4. Shelter / Cover MVP Goal

Implement this data flow:

```text
PPO Raw Action
        ↓
Alarm / Social Response
        ↓
FEcoSocialBehaviorFragment::ModulatedAction.Cover
        ↓
Shelter Search Request
        ↓
Nearby Shelter Candidates
        ↓
Threat-relative Occlusion / LOS Validation
        ↓
Cheap Score
  - cover validity
  - distance
  - quality
  - slot availability
        ↓
Reservation Proposal
        ↓
Deterministic Reconciliation
        ↓
Reserved Shelter Slot
        ↓
FEcoShelterIntentFragment
  - Shelter ID
  - Slot ID
  - Target Position
  - Score / State
        ↓
Future MassFlock adapter
```

This branch should stop before implementing actual MassFlock movement.

---

# 5. Required Implementation

## A. Use the correct Cover Intent

Shelter selection should be based on the **effective social behavior**, not by destructively rewriting PPO output.

Prefer:

`FEcoSocialBehaviorFragment::ModulatedAction.Cover`

The raw:

`FEcoPolicyOutputFragment::Action`

must remain immutable.

Verify existing processor ordering and ensure Shelter Query executes after the processor that writes `FEcoSocialBehaviorFragment`.

Target ordering should be explicit and deterministic:

```text
Herd Membership
→ Herd Aggregate
→ Alarm Propagation
→ Social Response
→ Shelter Query
→ Shelter Reservation/Reconciliation
→ future Movement/MassFlock
```

Do not rely only on being in the same Mass processor group.

---

## B. Real Threat-Relative Cover Validation

Replace "surface normal alone means cover" with an actual world-space occlusion test for the MVP.

Expected meaning:

A shelter candidate is useful when geometry blocks visibility from the current threat position toward the candidate shelter/slot.

Use Unreal Engine collision / line trace appropriately.

Requirements:

- threat-relative
- world geometry aware
- deterministic enough for the same world state
- debug-visible
- do not perform an unbounded number of traces every frame

Keep `SurfaceNormal` / `Quality` only as optional scoring inputs after actual cover validity.

Do not build a full EQS system.

---

## C. Deterministic Reservation

Implement the design already implied by the source comments:

```text
Query
→ Proposal
→ Reconciliation
→ Commit
```

Do not allow concurrent agents to mutate global shelter reservations directly in an arbitrary Mass iteration order.

For competing agents requesting the same slot:

1. higher candidate score wins
2. stable tie-break using `StableAgentId`

Global `UEcoShelterSubsystem` mutation must occur in a serialized/GameThread-safe stage.

If the processor is deliberately GameThread-only for this MVP, make that explicit.

The existing `FSlotProposal` can be reused/reworked if appropriate.

---

## D. Shelter Intent Contract

`FEcoShelterIntentFragment` should expose enough information for a future movement adapter without touching MassFlock.

At minimum the runtime must be able to resolve:

- target shelter index
- target slot index
- target world position
- candidate/reservation score
- state

State flow for this MVP may be:

```text
None
→ Searching
→ Reserved
```

`Moving / Occupied` should only be used if they can be semantically correct without pretending movement already exists.

Do not fake actual movement.

If `Occupied` cannot be editor-verified without MassFlock, explicitly defer it.

---

## E. Reservation Lifecycle

Handle at least:

- expired reservation
- failed reservation
- re-query after loss
- agent no longer wanting shelter
- hard/debug reset

Do not introduce complex death/despawn plumbing unless the current project already provides a clean hook.

Reservation timeout is acceptable as an MVP fallback for entities that disappear.

---

## F. Shelter Anchor Correctness

Audit and fix only what is necessary:

- ensure the actor has a valid runtime root component in packaged/runtime builds
- verify `Capacity`
- verify `Quality`
- decide whether `Radius` has a real MVP meaning
- distribute slots evenly if slots are generated around the anchor

For even slot placement use an angle based on capacity, not raw integer radians.

Example concept:

`Angle = 2π * SlotIdx / Capacity`

Do not add art assets or environment generation.

---

# 6. Debug / Editor Verification

Prefer a dedicated debug actor:

`AEcoShelterTestHarnessActor`

Do not make production Shelter code depend on this actor.

It may visualize:

- registered Shelter anchors
- shelter runtime index
- available/reserved capacity
- individual slot positions
- reservation owner StableAgentId
- candidate score
- agent → target slot line
- LOS / occlusion result
- target position

Reuse existing Herd/Alarm harnesses rather than duplicating their responsibilities.

Recommended editor setup:

```text
AEcoHerdTestHarnessActor
+
AEcoAlarmTestHarnessActor
+
multiple AEcoShelterAnchor actors
+
AEcoShelterTestHarnessActor (debug only)
```

Place shelters so that:

- one candidate is behind blocking geometry relative to threat
- one candidate is exposed
- shelters have different distance / quality / capacity

Expected observable result:

```text
Threat
   ↓
Agent becomes Alert/Panic
   ↓
Modulated Cover rises
   ↓
Occluded Shelter preferred
   ↓
Slot reserved
   ↓
Another agent competing for same slot
   ↓
Deterministic winner
```

---

# 7. MVP Success Criteria

The Shelter / Cover MVP is complete only if all of these are verified:

1. Existing Herd MVP still works.
2. Existing Alarm MVP still works.
3. Raw PPO Action is unchanged.
4. Shelter Query consumes the intended effective Cover value.
5. A threat-relative world occlusion / LOS check is actually executed.
6. An exposed shelter can be rejected or scored below a truly occluded shelter.
7. Nearby viable shelters can be selected.
8. Capacity / slot availability is respected.
9. Two agents competing for the same slot produce a deterministic winner.
10. No arbitrary first-iteration-wins reservation behavior remains.
11. `FEcoShelterIntentFragment` contains a usable future movement target.
12. Clearing/decaying danger can release or eventually expire unnecessary reservations.
13. No Mass worker-thread unsafe mutation of ShelterSubsystem remains.
14. No MassFlock source is rewritten.
15. `AdaptiveEcosystemEditor Win64 Development` build succeeds.
16. Editor PIE runs without assertions/crashes.

---

# 8. Explicit Non-Goals

Do NOT implement in this branch:

- MassFlock movement
- direct velocity control
- ORCA / RVO2 / DetourCrowd
- multi-hop Alarm gossip
- Herd Merge/Split
- full spatial hash/grid rewrite
- EQS-based cover system
- navmesh path planning overhaul
- actual Player/Predator production integration
- PPO schema changes
- new Action dimensions
- networking redesign
- new third-party dependency

Current PPO contract remains exactly:

```text
Observation V1 = 7
Action V1 = 4
forage / cohesion / flee_dist / cover
```

---

# 9. Performance Boundaries

This is an MVP, but avoid obvious per-frame scaling traps.

Allowed for now:

- simple linear shelter registry
- periodic shelter query cooldown
- small candidate count
- limited LOS checks

Avoid:

- every agent tracing against every shelter every frame
- repeated full slot scans where a cheap cached/indexed lookup is easy
- Tick-driven UObject/Actor AI per creature
- global mutable state writes from parallel Mass loops

Do not add a full spatial acceleration structure in this branch unless the current source proves it is necessary to make the MVP function.

---

# 10. Required Report After Implementation

After implementation, report exactly:

## Audit Findings
What was wrong in the original Shelter implementation.

## Changed Files
Every modified/added file and why.

## Final Runtime Data Flow
From `ModulatedAction.Cover` to reserved slot.

## Processor Order
Exact final execution order.

## Thread-Safety Model
Which stage reads snapshots/proposals and which stage mutates `UEcoShelterSubsystem`.

## Shelter Score
Exact formula and the meaning of each term.

## LOS / Occlusion
What is traced, on which collision channel, and what counts as covered.

## Reservation Arbitration
How conflicts are resolved and tie-broken.

## Editor Test Procedure
Exact actors to place, Details values, buttons/actions, and expected visualization.

## Build Result
Exact build target and whether it succeeded.

## Deferred Work
What intentionally remains for future MassFlock / production integration.

---

# 11. Final Constraint

Do not treat this as a general refactor.

The goal is:

**"A small, testable, thread-safe Shelter/Cover MVP that consumes the already-verified Social Runtime and produces a deterministic movement target contract without implementing movement itself."**
