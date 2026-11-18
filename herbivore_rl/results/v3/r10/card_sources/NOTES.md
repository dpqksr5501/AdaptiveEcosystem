# Notes — units and surprises

**Conversions.** Unreal rule fauna: cm, cm/s, cm/s² ÷ 100; full FOV = 2 × half-angle; max slope = acos(MinGroundNormalZ) (0.65 → 49.5°, horse 0.86 → 30.7°); stamina run time = 0.85 / SprintDrain s, recovery = 0.40 / FatigueRecovery s (lock 0.15, unlock 0.55). Native v3 and R9 share 1 unit = 2 m and 1 step = 2/15 s (EcoRepertoire.h:75-76, r9_body.py:67-68): u/step × 15 = m/s, u/step² × 112.5 = m/s², steps × 2/15 = s, per-step × 7.5 = per-s.

**Which value is "Unreal".** The island (`LV_JYU_IslandEcosystemRefreshed`) copies its 14 rule profiles from the `LV_JYU_RiparianReach` donor, whose chain starts at `setup_jyu_fauna.py` / `setup_jyu_expanded_fauna.py`. `author_jyu_pig.py` values (pig-only map) are recorded as alts only. Fields the scripts never set are C++ defaults (kind `unreal-default`) — e.g. Pig, Buffalo, Bighorn, Jackrabbit, Horse keep SightRange 15 m; all but Fox (200°) and Leopard (166°) keep FOV 198°; no island script sets ThreatSenseRange (6.5 m for everyone).

**Surprises.**
- Unreal speeds are far below R9/real: buffalo run 2.4 vs 7.2 m/s, boar 3.15 vs 6.3, leopard 5.3 vs 8.55, fox 4.2 vs 7.05. Horse runs 7 m/s, faster than the Unreal leopard.
- Fish `RunSpeed` is never used for swimming (water movement uses WalkSpeed only).
- Only Jackrabbit, Bighorn, Horse, Mink have a turn limit; Native deer/wolf have none, nor acceleration limits.
- Island Pig loses the pig-map senses: smell 0, sight 15 m, no heat response, no social spacing.
- Rule species mate within 10 m (hard-coded); Native and R9 use 20 m.
- Golden eagle has NestlingSeconds 90 (needs a NestId perch to hatch) but the island perch has no NestId — likely no natural eagle births (not run-verified).
- Native wolves cannot hunt rule species and rule predators cannot hunt Native deer.
- Deer grass eat rate: Native 0.06 vs R9 0.012 units/step (5×).
