# Source conflicts (SI units)

Primary = what the team island executes (Unreal rule profile, or Native v3 for deer/wolf). `pig-map` rows are LV_JYU_Pig values that the island does not use. R9 rows are the Python body table. Numbers differing by more than 1% are listed; stamina compares seconds from full to lock and lock to unlock.

| species | field | primary (kind) | other source (kind) | Unreal island executes | primary src | other src |
|---|---|---|---|---|---|---|
| deer | body.accel_mps2 | unlimited (native) | 13.5 (r9-yaml) | unlimited | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoRepertoire.h:161-166` | `herbivore_rl/configs/v3_r9.yaml:123` |
| deer | body.turn_dps | unlimited (native) | 130 (r9-yaml) | unlimited | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoRepertoire.h:161-166` | `herbivore_rl/configs/v3_r9_fauna_motion.yaml:16` |
| deer | body.stamina | none (native) | run 12.0 s / recover 8.0 s (r9-yaml) | none | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoRepertoire.h:161-191` | `herbivore_rl/configs/v3_r9.yaml:124-125` |
| deer | senses.smell_m | none (native) | 6 (r9-yaml) | none | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoObservationV3.h:68-86` | `herbivore_rl/configs/v3_r9.yaml:129` |
| deer | diet.grass | {"eat_units_per_s": 0.45, "energy_per_unit": 0.5, "walk_eat_mult": 0.5} (native) | {"eat_units_per_s": 0.09, "energy_per_unit": 0.5} (r9-yaml) | {"eat_units_per_s": 0.45, "energy_per_unit": 0.5, "walk_eat_mult": 0.5} | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoRepertoire.h:163,187-188` | `herbivore_rl/configs/v3_r9.yaml:137-138` |
| wolf | body.run_mps | 7.2 (native) | {"base_mps": 9.0, "world_mult": [0.9, 1.05], "range_mps": [8.1, 9.45]} (r9-yaml) | 7.2 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.h:335; AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h:1104` | `herbivore_rl/configs/v3_r9.yaml:166-167` |
| wolf | body.accel_mps2 | unlimited (native) | 11.25 (r9-yaml) | unlimited | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h:1420-1495` | `herbivore_rl/configs/v3_r9.yaml:168` |
| wolf | body.turn_dps | unlimited (native) | 140 (r9-yaml) | unlimited | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h:1420-1495` | `herbivore_rl/configs/v3_r9_fauna_motion.yaml:19` |
| wolf | body.stamina | none (stalker exhausts 4 s after a 1.6 s pounce) (native) | run 40.0 s / recover 8.0 s (r9-yaml) | none (stalker exhausts 4 s after a 1.6 s pounce) | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h:205-208` | `herbivore_rl/configs/v3_r9.yaml:169-170` |
| wolf | senses.sight_m | 28 (native) | 40 (r9-yaml) | 28 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h:182` | `herbivore_rl/configs/v3_r9.yaml:171` |
| wolf | senses.fov_deg | 150 (native) | 250 (r9-yaml) | 150 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h:183` | `herbivore_rl/configs/v3_r9.yaml:172` |
| wolf | senses.smell_m | none (native) | 10 (r9-yaml) | none | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h:178-260` | `herbivore_rl/configs/v3_r9.yaml:174` |
| wolf | combat.hunts | deer (native) | deer, boar, buffalo, leopard, fox (r9-yaml) | deer | `AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedProcessors.cpp:1206; AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoThreatModel.h:1098-1115` | `herbivore_rl/configs/v3_r9_fauna.yaml:47 (S' herbivore_rl/configs/v3_r9.yaml:187 = deer, boar)` |
| boar | body.mass_kg | 75 (unreal-script) | 80 (r9-yaml) | 75 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:610` | `herbivore_rl/configs/v3_r9.yaml:206` |
| boar | body.sweep_height_m | 0.65 (unreal-default) | 0.73 (unreal-script pig-map) | 0.65 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:105` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | body.run_mps | 3.15 (unreal-script) | 6.3 (r9-yaml) | 3.15 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:610` | `herbivore_rl/configs/v3_r9.yaml:211` |
| boar | body.turn_dps | 0 (unreal-default) | 125 (r9-yaml) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:92` | `herbivore_rl/configs/v3_r9_fauna_motion.yaml:22` |
| boar | body.turn_dps | 0 (unreal-default) | 225 (unreal-script pig-map) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:92` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | senses.sight_m | 15 (unreal-default) | 16 (r9-yaml) | 15 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:85` | `herbivore_rl/configs/v3_r9.yaml:216` |
| boar | senses.sight_m | 15 (unreal-default) | 11.5 (unreal-script pig-map) | 15 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:85` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | senses.fov_deg | 198 (unreal-default) | 300 (r9-yaml) | 198 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:86` | `herbivore_rl/configs/v3_r9.yaml:217` |
| boar | senses.eye_height_m | 0.35 (unreal-default) | 0.56 (unreal-script pig-map) | 0.35 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:104` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | senses.smell_m | 0 (unreal-default) | 12 (r9-yaml) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:113` | `herbivore_rl/configs/v3_r9.yaml:219` |
| boar | senses.smell_m | 0 (unreal-default) | 8 (unreal-script pig-map) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:113` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | senses.threat_sense_m | 6.5 (unreal-default) | 8.5 (unreal-script pig-map) | 6.5 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:136` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | diet.insects | False (unreal-script) | True (unreal-script fixture) | False | `AdaptiveEcosystem/Tools/Editor/author_jyu_island_fauna.py:571-612` | `AdaptiveEcosystem/Tools/Editor/author_jyu_fauna_balance.py:32` |
| boar | diet.fruit_mast | False (unreal-script) | True (unreal-script fixture) | False | `AdaptiveEcosystem/Tools/Editor/author_jyu_island_fauna.py:571-612` | `AdaptiveEcosystem/Tools/Editor/author_jyu_fauna_balance.py:34` |
| boar | diet.fruit_mast | False (unreal-script) | True (unreal-script pig-map) | False | `AdaptiveEcosystem/Tools/Editor/author_jyu_island_fauna.py:571-612` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:120` |
| boar | life.gestation_s | 30 (unreal-default) | 32 (unreal-script pig-map) | 30 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:124` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | life.birth_recovery_s | 300 (unreal-default) | 140 (unreal-script pig-map) | 300 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:125` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | social.social_neighbor_m | 0 (unreal-default) | 6.4 (unreal-script pig-map) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:142` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | social.social_spacing_m | 1.8 (unreal-default) | 1.38 (unreal-script pig-map) | 1.8 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:145` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | social.adult_male_social_affinity | 1 (unreal-default) | 0.18 (unreal-script pig-map) | 1 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:144` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | social.caregiver_follow_m | 0 (unreal-default) | 4.8 (unreal-script pig-map) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:101` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| boar | habitat.heat_response_c | 0, 0 (unreal-default) | 25, 36 (unreal-script pig-map) | 0, 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:147` | `AdaptiveEcosystem/Tools/Editor/author_jyu_pig.py:32-44` |
| buffalo | body.walk_mps | 1 (unreal-script) | 1.5 (r9-yaml) | 1 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:614` | `herbivore_rl/configs/v3_r9_fauna.yaml:68` |
| buffalo | body.run_mps | 2.4 (unreal-script) | 7.2 (r9-yaml) | 2.4 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:614` | `herbivore_rl/configs/v3_r9_fauna.yaml:69` |
| buffalo | body.accel_mps2 | 4.2 (unreal-script) | 6.75 (r9-yaml) | 4.2 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:617` | `herbivore_rl/configs/v3_r9_fauna.yaml:71` |
| buffalo | body.turn_dps | 0 (unreal-default) | 90 (r9-yaml) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:92` | `herbivore_rl/configs/v3_r9_fauna_motion.yaml:25` |
| buffalo | body.stamina | run 6.07 s / recover 3.08 s (unreal-script) | run 8.0 s / recover 8.0 s (r9-yaml) | run 6.07 s / recover 3.08 s | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:674; AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:109; lock/unlock AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp:1522-1524` | `herbivore_rl/configs/v3_r9_fauna.yaml:72-73` |
| buffalo | senses.sight_m | 15 (unreal-default) | 20 (r9-yaml) | 15 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:85` | `herbivore_rl/configs/v3_r9_fauna.yaml:74` |
| buffalo | senses.fov_deg | 198 (unreal-default) | 300 (r9-yaml) | 198 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:86` | `herbivore_rl/configs/v3_r9_fauna.yaml:75` |
| buffalo | senses.smell_m | 0 (unreal-default) | 12 (r9-yaml) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:113` | `herbivore_rl/configs/v3_r9_fauna.yaml:77` |
| buffalo | combat.counterattack_damage_hp | 32 (unreal-script) | 56.9 (r9-yaml) | 32 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:674` | `herbivore_rl/configs/v3_r9_fauna.yaml:92; herbivore_rl/configs/v3_r9_fauna.yaml:110; AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:154-155` |
| buffalo | life.maturity_s | 220 (unreal-script) | 450 (r9-yaml) | 220 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:614` | `herbivore_rl/configs/v3_r9_fauna.yaml:93` |
| buffalo | life.birth_recovery_s | 300 (unreal-default) | 450 (r9-yaml) | 300 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:125` | `herbivore_rl/configs/v3_r9_fauna.yaml:114` |
| buffalo | life.mate_radius_m | 10 (unreal-default) | 20 (r9-yaml) | 10 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.cpp:1301` | `herbivore_rl/configs/v3_r9_fauna.yaml:99` |
| leopard | body.mass_kg | 60 (unreal-script) | 50 (r9-yaml) | 60 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:613` | `herbivore_rl/configs/v3_r9_fauna.yaml:116` |
| leopard | body.walk_mps | 1.5 (unreal-script) | 2.25 (r9-yaml) | 1.5 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:613` | `herbivore_rl/configs/v3_r9_fauna.yaml:120` |
| leopard | body.run_mps | 5.3 (unreal-script) | 8.55 (r9-yaml) | 5.3 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:613` | `herbivore_rl/configs/v3_r9_fauna.yaml:121` |
| leopard | body.accel_mps2 | 12.5 (unreal-script) | 16.875 (r9-yaml) | 12.5 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:617` | `herbivore_rl/configs/v3_r9_fauna.yaml:123` |
| leopard | body.turn_dps | 0 (unreal-default) | 135 (r9-yaml) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:92` | `herbivore_rl/configs/v3_r9_fauna_motion.yaml:28` |
| leopard | body.stamina | run 5.31 s / recover 3.08 s (unreal-script) | run 4.0 s / recover 12.0 s (r9-yaml) | run 5.31 s / recover 3.08 s | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:671; AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:109; lock/unlock AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp:1522-1524` | `herbivore_rl/configs/v3_r9_fauna.yaml:124-125` |
| leopard | senses.sight_m | 17.5 (unreal-script) | 40 (r9-yaml) | 17.5 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:671` | `herbivore_rl/configs/v3_r9_fauna.yaml:126` |
| leopard | senses.fov_deg | 166 (unreal-script) | 200 (r9-yaml) | 166 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:671` | `herbivore_rl/configs/v3_r9_fauna.yaml:127` |
| leopard | senses.smell_m | 7.5 (unreal-script) | 6 (r9-yaml) | 7.5 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:671` | `herbivore_rl/configs/v3_r9_fauna.yaml:129` |
| leopard | combat.hunts | Pig, Rat, Buffalo (unreal-script) | deer, wolf, boar, buffalo, fox (r9-yaml) | Pig, Rat, Buffalo | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:653-657` | `herbivore_rl/configs/v3_r9_fauna.yaml:142` |
| leopard | combat.attack_reach_m | 1.25 (unreal-script) | 2 (r9-yaml) | 1.25 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:661` | `herbivore_rl/configs/v3_r9_fauna.yaml:143` |
| leopard | life.maturity_s | 170 (unreal-script) | 386.667 (r9-yaml) | 170 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:613` | `herbivore_rl/configs/v3_r9_fauna.yaml:145` |
| leopard | life.birth_recovery_s | 300 (unreal-default) | 486.667 (r9-yaml) | 300 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:125` | `herbivore_rl/configs/v3_r9_fauna.yaml:166` |
| leopard | life.mate_radius_m | 10 (unreal-default) | 20 (r9-yaml) | 10 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.cpp:1301` | `herbivore_rl/configs/v3_r9_fauna.yaml:151` |
| fox | body.walk_mps | 1.3 (unreal-script) | 2.25 (r9-yaml) | 1.3 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:611` | `herbivore_rl/configs/v3_r9_fauna.yaml:172` |
| fox | body.run_mps | 4.2 (unreal-script) | 7.05 (r9-yaml) | 4.2 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:611` | `herbivore_rl/configs/v3_r9_fauna.yaml:173` |
| fox | body.accel_mps2 | 11 (unreal-script) | 13.5 (r9-yaml) | 11 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:617` | `herbivore_rl/configs/v3_r9_fauna.yaml:175` |
| fox | body.turn_dps | 0 (unreal-default) | 185 (r9-yaml) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:92` | `herbivore_rl/configs/v3_r9_fauna_motion.yaml:31` |
| fox | body.stamina | run 8.95 s / recover 3.08 s (unreal-script) | run 8.0 s / recover 8.0 s (r9-yaml) | run 8.95 s / recover 3.08 s | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:668; AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:109; lock/unlock AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFaunaMovement.cpp:1522-1524` | `herbivore_rl/configs/v3_r9_fauna.yaml:176-177` |
| fox | senses.sight_m | 13.5 (unreal-script) | 24 (r9-yaml) | 13.5 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:668` | `herbivore_rl/configs/v3_r9_fauna.yaml:178` |
| fox | senses.fov_deg | 200 (unreal-script) | 260 (r9-yaml) | 200 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:668` | `herbivore_rl/configs/v3_r9_fauna.yaml:179` |
| fox | diet.insects | False (unreal-script) | True (unreal-script fixture) | False | `AdaptiveEcosystem/Tools/Editor/author_jyu_island_fauna.py:571-612` | `AdaptiveEcosystem/Tools/Editor/author_jyu_fauna_balance.py:32` |
| fox | diet.fruit_mast | False (unreal-script) | True (unreal-script fixture) | False | `AdaptiveEcosystem/Tools/Editor/author_jyu_island_fauna.py:571-612` | `AdaptiveEcosystem/Tools/Editor/author_jyu_fauna_balance.py:34` |
| fox | combat.hunts | Crow, Rat, Jackrabbit (unreal-script) | deer, wolf, boar, buffalo, leopard (r9-yaml) | Crow, Rat, Jackrabbit | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:650-651 + AdaptiveEcosystem/Tools/Editor/setup_jyu_expanded_fauna.py:500-504 (Jackrabbit rule added in ExpandedFauna)` | `herbivore_rl/configs/v3_r9_fauna.yaml:194` |
| fox | combat.attack_reach_m | 0.75 (unreal-script) | 1.1 (r9-yaml) | 0.75 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:661` | `herbivore_rl/configs/v3_r9_fauna.yaml:195` |
| fox | life.maturity_s | 135 (unreal-script) | 144 (r9-yaml) | 135 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:611` | `herbivore_rl/configs/v3_r9_fauna.yaml:197` |
| fox | life.mate_radius_m | 10 (unreal-default) | 20 (r9-yaml) | 10 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.cpp:1301` | `herbivore_rl/configs/v3_r9_fauna.yaml:203` |
| rat | body.mass_kg | 0.25 (unreal-script) | 0.3 (doc-only) | 0.25 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:615` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:115` |
| rat | body.walk_mps | 0.55 (unreal-script) | 0.6 (doc-only) | 0.55 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:615` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:117` |
| rat | body.run_mps | 2.2 (unreal-script) | 1.41 (doc-only) | 2.2 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:615` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:117` |
| rat | body.accel_mps2 | 8.5 (unreal-script) | 5.625 (doc-only) | 8.5 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:617` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:118` |
| rat | senses.sight_m | 8 (unreal-script) | 6 (doc-only) | 8 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:677` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:131` |
| rat | senses.fov_deg | 198 (unreal-default) | 320 (doc-only) | 198 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:86` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:131` |
| rat | senses.smell_m | 0 (unreal-default) | 8 (doc-only) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:113` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:131` |
| rat | diet.fruit_mast | False (unreal-script) | True (unreal-script fixture) | False | `AdaptiveEcosystem/Tools/Editor/author_jyu_island_fauna.py:571-612` | `AdaptiveEcosystem/Tools/Editor/author_jyu_fauna_balance.py:34` |
| rat | life.maturity_s | 50 (unreal-script) | 45.333 (doc-only) | 50 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:615` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:134` |
| rat | life.birth_recovery_s | 55 (unreal-script) | 50 (doc-only) | 55 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:677` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:134` |
| crow | body.mass_kg | 0.55 (unreal-script) | 0.6 (doc-only) | 0.55 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:612` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:115` |
| crow | body.walk_mps | 0.7 (unreal-script) | 0.75 (doc-only) | 0.7 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:612` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:117` |
| crow | body.fly_mps | 6.5 (unreal-script) | 6.3 (doc-only) | 6.5 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:682` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:117` |
| crow | body.accel_mps2 | 4.3 (unreal-script) | 9 (doc-only) | 4.3 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:617` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:118` |
| crow | senses.sight_m | 20 (unreal-script) | 60 (doc-only) | 20 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:682` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:131` |
| crow | senses.fov_deg | 198 (unreal-default) | 300 (doc-only) | 198 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:86` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:131` |
| crow | senses.smell_m | 0 (unreal-default) | 1 (doc-only) | 0 | `AdaptiveEcosystem/Source/AdaptiveEcosystem/Creature/Runtime/EcoFauna.h:113` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:131` |
| crow | diet.insects | False (unreal-script) | True (unreal-script fixture) | False | `AdaptiveEcosystem/Tools/Editor/author_jyu_island_fauna.py:571-612` | `AdaptiveEcosystem/Tools/Editor/author_jyu_fauna_balance.py:32` |
| crow | diet.fruit_mast | False (unreal-script) | True (unreal-script fixture) | False | `AdaptiveEcosystem/Tools/Editor/author_jyu_island_fauna.py:571-612` | `AdaptiveEcosystem/Tools/Editor/author_jyu_fauna_balance.py:34` |
| crow | life.maturity_s | 105 (unreal-script) | 540 (doc-only) | 105 | `AdaptiveEcosystem/Tools/Editor/setup_jyu_fauna.py:612` | `AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md:134` |

94 conflicting pairs.

## Model-level differences (not listed row by row; such alts carry `"cmp": false` in the cards)

| topic | Unreal (what runs) | R9 Python | consequence for R10 |
|---|---|---|---|
| hearing | per-listener `HearingRange` in the footstep profile (rule species 12.3-26 m; fish have no profile); Native deer hear wolves 4-40 m by wolf speed | species-independent, set by the emitter's speed: 4 m quiet to 40 m running (`r9_body.py:225-230`) | pick one hearing model |
| energy units | rule fauna vitals energy: maintenance 0.35/s default, plant food 5 energy/unit (`EcoFauna.h:13-16`) | E 0..1 stomach, drain per step (deer 0.002/step = 0.015/s) | maintenance numbers are not comparable across the two |
| food units | island patches give 2.8 energy/meal; plant meal = FoodPerMeal grid units | eat_rate units/step x e_per_unit per food kind | eat-rate fields need one unit system |
| bite damage | 100% MaxHP to undefended prey, 45% to prey with DefenseDamage > 0 (`EcoFaunaMovement.cpp:398`) | wound = min(1, bite_k x (Ma/Mb)^(2/3) / hide) | Unreal has no hide/bite_k; R9 has no flat 45% rule |
| counter / gore | DefenseDamage HP points when facing within +-75.5 deg and HP >= 35%; no gore | counter + running gore scaled by momentum (`v3_r9_fauna.yaml:31`) | buffalo gore exists only in R9 |
| acceleration / turning | Native deer & wolf: unlimited (velocity set per step); rule fauna: GroundAcceleration, turn cap only if GroundTurnDegreesPerSecond > 0 | accel cap and M1 turn limit min(turn_dps, asin(lat_accel / speed)) | most island species turn instantly in Unreal |
| stamina | rule fauna: SprintDrain / FatigueRecovery per s, lock 0.15 / unlock 0.55; Native deer & wolf: none | run / recover steps with the same 0.15 / 0.55 lock | deer stamina exists only in R9 |
| day / night | NightVision, DayActivity, NightActivity per species; Native deer detect x(1-0.5 d), diurnal wolves sleep at d >= 0.5 | no day/night (`RL_R9_SPECIES_TRAITS.md:138`) | R9 has no night values |
| prey selection | fauna backend targets fauna residents only (`EcoFauna.h:81`); Native wolves target Native deer only | any listed species | wolf->boar/buffalo, leopard/fox->deer do not exist in Unreal |
| mate radius | rule fauna 10 m hard-coded (`EcoFauna.cpp:1301`); Native 20 m | 20 m (boar 10 m) | |
