# Gaps — applicable fields with no source anywhere in the repo

Fields marked not-applicable (e.g. flight fields for walkers) are excluded. These are the values R10 has to choose.

## deer (11)

- `senses.day_activity` — Native deer have no activity curve; brain decides (SLEEP action)
- `senses.night_activity` — Native deer have no activity curve; brain decides (SLEEP action)
- `diet.forbs` — Native grid has no guild split (natural habitat guilds grass/riparian/shrub exist in EcoNaturalHabitatProfile.h:40)
- `diet.browse`
- `diet.wet_meadow`
- `combat.offspring_guard_m`
- `life.lifespan_s` — no ageing death
- `social.social_neighbor_m`
- `social.caregiver_follow_m` — family follow exists (EcoLifeHistoryV3.h:213-217) but no radius constant found
- `social.guard_radius_m`
- `habitat.heat_response_c`

## wolf (8)

- `senses.eye_height_m`
- `senses.threat_sense_m` — wolves have no threat sensing in Native
- `combat.offspring_guard_m`
- `life.lifespan_s`
- `social.social_neighbor_m`
- `social.guard_radius_m`
- `social.caregiver_follow_m`
- `habitat.heat_response_c`

## boar (1)

- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## buffalo (1)

- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## leopard (1)

- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## fox (1)

- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## rat (2)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## crow (2)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## bighorn (2)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## jackrabbit (2)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## horse (2)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## golden_eagle (2)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## mink (2)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## ariake_catfish (3)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `senses.hearing_m` — no footstep listener profile for this species -> no footstep hearing (EcoFaunaMovement.cpp:1572)
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## common_carp (3)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `senses.hearing_m` — no footstep listener profile for this species -> no footstep hearing (EcoFaunaMovement.cpp:1572)
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

## small_fish (3)

- `body.lat_accel_mps2` — no lateral-acceleration limit in Unreal fauna; not in R9
- `senses.hearing_m` — no footstep listener profile for this species -> no footstep hearing (EcoFaunaMovement.cpp:1572)
- `life.lifespan_s` — no ageing death in Unreal fauna; R9 has none either

