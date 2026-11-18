"""Build R10 draft species cards from values already in the repo (read-only extraction, hand-transcribed with line refs)."""
import json, math, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "r10_cards")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- paths
ED = "AdaptiveEcosystem/Tools/Editor/"
SF, SE, HF, RF, IF, PG, FB, FS, IE = (ED + x for x in (
    "setup_jyu_fauna.py", "setup_jyu_expanded_fauna.py", "author_jyu_herbivore_forage.py", "author_jyu_reach_forage.py",
    "author_jyu_island_fauna.py", "author_jyu_pig.py", "author_jyu_fauna_balance.py", "author_jyu_fauna_footsteps.py",
    "apply_jyu_island_ecosystem.py"))
SRC = "AdaptiveEcosystem/Source/AdaptiveEcosystem/"
EH = SRC + "Creature/Runtime/EcoFauna.h"
FM = SRC + "Creature/Runtime/EcoFaunaMovement.cpp"
FW = SRC + "Creature/Runtime/EcoFaunaWaterMovement.cpp"
FC = SRC + "Creature/Runtime/EcoFauna.cpp"
NB = SRC + "Creature/Runtime/EcoCreatureNaturalBirth.cpp"
ES = SRC + "Ecology/EcologySimulationSubsystem.cpp"
NH = SRC + "World/EcoNaturalHabitatProfile.h"
P = SRC + "AI/Policy/"
RP, OB, WV, TM, IS, ISH, LH, IP = (P + x for x in (
    "EcoRepertoire.h", "EcoObservationV3.h", "EcoWorldV3.h", "EcoThreatModel.h", "EcoPolicyV3IntegratedSubsystem.cpp",
    "EcoPolicyV3IntegratedSubsystem.h", "EcoLifeHistoryV3.h", "EcoPolicyV3IntegratedProcessors.cpp"))
Y, YF, YM, RB = ("herbivore_rl/configs/v3_r9.yaml", "herbivore_rl/configs/v3_r9_fauna.yaml",
                 "herbivore_rl/configs/v3_r9_fauna_motion.yaml", "herbivore_rl/env_v2/r9_body.py")
DT = "AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md"
DC = "AdaptiveEcosystem/Docs/Architecture/FAUNA_HABITAT_CAPACITY_20261113.md"

US, UD, NA_, R9, DOC = "unreal-script", "unreal-default", "native", "r9-yaml", "doc-only"

# ---------------------------------------------------------------- unit helpers
def r(x, n=4):
    return None if x is None else round(float(x), n)
cm = lambda x: r(x / 100.0)                 # cm -> m, cm/s -> m/s, cm/s^2 -> m/s^2
U = lambda u: r(u * 2.0)                    # world unit (2 m) -> m
UPS = lambda u: r(u * 15.0)                 # unit/step (step = 2/15 s) -> m/s
UPS2 = lambda a: r(a * 112.5)               # unit/step^2 -> m/s^2
STEP_S = lambda n: r(n * 2.0 / 15.0, 3)     # steps -> s
PER_S = lambda x: r(x * 7.5, 6)             # per step -> per second
SLOPE = lambda n: r(math.degrees(math.acos(n)), 2)

def S(v, src, kind, note=None, cmp=True):
    d = {"v": v, "src": src, "kind": kind}
    if note:
        d["note"] = note
    if not cmp:
        d["cmp"] = False   # different quantity or unit system: kept for reference, excluded from CONFLICTS
    return d

def F(primary, *alts):
    d = dict(primary)
    a = [x for x in alts if x is not None]
    if a:
        d["alt"] = a
    return d

def NA(note):
    return {"v": None, "na": True, "note": note}

def NUL(note=None):
    d = {"v": None, "src": None, "kind": None}
    if note:
        d["note"] = note
    return d

# ---------------------------------------------------------------- EcoFauna.h defaults (field -> (value, line))
DEF = {
    "Diet": ("Herbivore", 77), "Locomotion": ("Ground", 78), "AdultMass": (40.0, 83), "AttackReach": (100.0, 84),
    "SightRange": (1500.0, 85), "SightHalfAngle": (99.0, 86), "WalkSpeed": (150.0, 87), "RunSpeed": (330.0, 88),
    "GroundAcceleration": (750.0, 89), "MinGroundNormalZ": (0.65, 90), "GroundTurnDegreesPerSecond": (0.0, 92),
    "SwimDepthFraction": (0.5, 93), "SpawningTemperatureC": ([0.0, 40.0], 94), "MaxNurseryCurrent": (120.0, 95),
    "bIndividualResponse": (False, 97), "StalkRange": (0.0, 98), "bFlankDefendedPrey": (False, 99),
    "HabitatCarrionRange": (0.0, 100), "CaregiverFollowRange": (0.0, 101), "RootingSeconds": (0.0, 102),
    "BodyRadius": (25.0, 103), "EyeHeight": (35.0, 104), "SweepHeight": (65.0, 105), "WadeDepth": (0.0, 106),
    "StepHeight": (20.0, 107), "SprintDrain": (0.10, 108), "FatigueRecovery": (0.13, 109), "Maintenance": (0.35, 110),
    "RestingMaintenanceFraction": (0.35, 112), "ScentRange": (0.0, 113), "DefenseDamage": (0.0, 114),
    "OffspringGuardRange": (0.0, 115), "bAllowSecondParentGuard": (False, 116), "DayActivity": (1.0, 117),
    "NightActivity": (1.0, 118), "NightVision": (1.0, 119), "AttackWindup": (0.35, 121), "AttackRecovery": (6.0, 122),
    "MaturitySeconds": (180.0, 123), "Gestation": (30.0, 124), "BirthRecovery": (300.0, 125), "FoodPerMeal": (0.2, 126),
    "CarrionEnergyPerMeal": (0.0, 128), "CarrionHungerFraction": (0.82, 130), "MealStartFraction": (0.0, 132),
    "MealStopFraction": (0.9, 133), "PostMealRestSeconds": (4.0, 134), "PursuitLimitSeconds": (12.0, 135),
    "ThreatSenseRange": (650.0, 136), "ThreatSightHalfAngle": (90.0, 137), "ThreatNearAwarenessRange": (280.0, 138),
    "RoutineHomeRadius": (520.0, 140), "SocialNeighborRadius": (0.0, 142), "AdultMaleSocialAffinity": (1.0, 144),
    "SocialSpacing": (180.0, 145), "HeatResponseC": ([0.0, 0.0], 147), "bAllowConspecificCarrion": (False, 150),
    "AdultCarrionEnergy": (0.0, 152), "DeathSettleSeconds": (0.9, 153), "CarrionLifetime": (20.0, 154),
    "FeedingPlaces": (2, 155), "RegionalLimit": (12, 156), "FlightCruiseHeight": (1200.0, 157),
    "FlightCeiling": (3000.0, 158), "FlightSpeed": (650.0, 159), "bCanDiveHunt": (False, 160), "NestlingSeconds": (0.0, 162),
    "PreyRules": ([], 82), "PlantPreferences": ({}, 80),
}

def base_profile():
    return {k: (v, f"{EH}:{ln}", UD) for k, (v, ln) in DEF.items()}

def apply(p, src, **kv):
    for k, v in kv.items():
        assert k in DEF, k
        p[k] = (v, src, US)

def prey(sp, ratio, pref=1.0, healthy=1.0, injured=1.0, guard=0.0, pursuit=0.0):
    d = {"prey": sp, "max_prey_mass_ratio": ratio, "preference": pref}
    if healthy != 1.0: d["max_healthy_maturity"] = healthy
    if injured != 1.0: d["max_injured_maturity"] = injured
    if guard: d["guard_radius_m"] = cm(guard)
    if pursuit: d["max_pursuit_start_m"] = cm(pursuit)
    return d

# ---------------------------------------------------------------- rule species profiles (island chain)
P_ = {}
# setup_jyu_fauna.py configure_species (LV_JYU_Fauna -> ExpandedFauna -> ... -> RiparianReach -> island donor)
ACT = {"Pig": (.72, .86, .75, 619), "Fox": (.53, .94, .85, 619), "Crow": (.94, .12, .42, 619),
       "Leopard": (.58, .90, .88, 620), "Buffalo": (.94, .62, .67, 620), "Rat": (.48, .97, .80, 620)}
TUN = {"Pig": (130., 315., 30., 75., 120., .27, 14, 610), "Fox": (130., 420., 23., 7., 135., .18, 8, 611),
       "Crow": (70., 145., 15., .55, 105., .16, 16, 612), "Leopard": (150., 530., 31., 60., 170., .2, 6, 613),
       "Buffalo": (100., 240., 65., 450., 220., .32, 12, 614), "Rat": (55., 220., 3.5, .25, 50., .08, 24, 615)}
ACC = {"Pig": 680., "Fox": 1100., "Crow": 430., "Leopard": 1250., "Buffalo": 420., "Rat": 850.}
for k, (w, rn, rad, m, mat, food, lim, ln) in TUN.items():
    p = base_profile()
    apply(p, f"{SF}:{ln}", WalkSpeed=w, RunSpeed=rn, BodyRadius=rad, AdultMass=m, MaturitySeconds=mat, FoodPerMeal=food, RegionalLimit=lim)
    apply(p, f"{SF}:617", GroundAcceleration=ACC[k])
    d, n, v, al = ACT[k]
    apply(p, f"{SF}:{al}", DayActivity=d, NightActivity=n, NightVision=v)
    apply(p, f"{SF}:646", Diet="Carnivore" if k in ("Fox", "Leopard") else ("Omnivore" if k in ("Pig", "Crow", "Rat") else "Herbivore"))
    apply(p, f"{SF}:661", AttackReach=75. if k == "Fox" else 125.)
    P_[k] = p
apply(P_["Pig"], f"{SF}:665", RootingSeconds=1.4, CarrionEnergyPerMeal=4., SprintDrain=.09, WadeDepth=10., DefenseDamage=18.,
      OffspringGuardRange=400., bAllowSecondParentGuard=True)
apply(P_["Fox"], f"{SF}:668", SightRange=1350., SightHalfAngle=100., CarrionEnergyPerMeal=7., CarrionHungerFraction=.86,
      SprintDrain=.095, Maintenance=.26, AttackWindup=.22, AttackRecovery=2.8, ScentRange=1000.)
apply(P_["Fox"], f"{SF}:650", PreyRules=[prey("Crow", .45), prey("Rat", .4, 1.9),
                                         prey("Jackrabbit", .7, .7, .65, 1.0)])
P_["Fox"]["PreyRules"] = (P_["Fox"]["PreyRules"][0], f"{SF}:650-651 + {SE}:500-504 (Jackrabbit rule added in ExpandedFauna)", US)
apply(P_["Leopard"], f"{SF}:671", SightRange=1750., SightHalfAngle=83., StalkRange=1250., SprintDrain=.16,
      CarrionEnergyPerMeal=9., CarrionHungerFraction=.78, AttackWindup=.42, ScentRange=750.)
apply(P_["Leopard"], f"{SF}:653-657", PreyRules=[prey("Pig", 1.6), prey("Rat", .1, .14, pursuit=320.),
                                                 prey("Buffalo", 1.8, .45, .35, .55, guard=400.)])
apply(P_["Leopard"], f"{FB}:57-58", bFlankDefendedPrey=True, HabitatCarrionRange=3000.)
apply(P_["Buffalo"], f"{SF}:674", CaregiverFollowRange=850., EyeHeight=120., SweepHeight=90., WadeDepth=35., SprintDrain=.14,
      FeedingPlaces=4, CarrionLifetime=36., DefenseDamage=32., OffspringGuardRange=650.)
apply(P_["Rat"], f"{SF}:677", EyeHeight=5., SweepHeight=5., StepHeight=4., SightRange=800., WadeDepth=1., SprintDrain=.17,
      FatigueRecovery=.21, Maintenance=.14, AdultCarrionEnergy=13., DeathSettleSeconds=.85, CarrionLifetime=12., FeedingPlaces=1,
      Gestation=15., BirthRecovery=55.)
apply(P_["Crow"], f"{SF}:682", Locomotion="Flight", SightRange=2000., CarrionEnergyPerMeal=3.5, CarrionHungerFraction=.9,
      FlightCruiseHeight=1200., FlightCeiling=3000., FlightSpeed=650., SprintDrain=.08, EyeHeight=23., AdultCarrionEnergy=19., FeedingPlaces=1)

# setup_jyu_expanded_fauna.py
ETUN = {"Bighorn": (29., 70., 135., 570., 25), "Jackrabbit": (10., 3., 90., 430., 26), "Horse": (42., 400., 150., 700., 27),
        "Mink": (9., 1., 75., 280., 28), "GoldenEagle": (24., 5., 55., 145., 29), "AriakeCatfish": (4., .14, 42., 95., 30),
        "CommonCarp": (7., .9, 52., 125., 31), "UnidentifiedFish": (4., .05, 36., 82., 32)}
for k, (rad, m, w, rn, ln) in ETUN.items():
    p = base_profile()
    apply(p, f"{SE}:{ln}", BodyRadius=rad, AdultMass=m, WalkSpeed=w, RunSpeed=rn)
    apply(p, f"{SE}:325-328", RegionalLimit=10, bIndividualResponse=True)
    P_[k] = p
for k in ("AriakeCatfish", "CommonCarp"):
    cat = k == "AriakeCatfish"
    apply(P_[k], f"{SE}:331-338", Locomotion="Swimming", Diet="Carnivore" if cat else "Omnivore",
          CarrionEnergyPerMeal=1.5 if cat else 0., SpawningTemperatureC=[0., 40.] if cat else [17., 23.],
          MaxNurseryCurrent=18. if cat else 12., SwimDepthFraction=.82 if cat else .56, DayActivity=.26 if cat else .8,
          NightActivity=.93 if cat else .85, SightRange=450., RoutineHomeRadius=275., MaturitySeconds=180., Gestation=35.,
          BirthRecovery=105., Maintenance=.12)
apply(P_["UnidentifiedFish"], f"{SE}:341-345", Locomotion="Swimming", Diet="Omnivore", SwimDepthFraction=.21, DayActivity=.88,
      NightActivity=.52, SightRange=325., RoutineHomeRadius=230., RegionalLimit=8, MaxNurseryCurrent=10., MaturitySeconds=125.,
      Gestation=24., BirthRecovery=100., Maintenance=.10)
apply(P_["GoldenEagle"], f"{SE}:351-355", Locomotion="Flight", Diet="Carnivore", bCanDiveHunt=True, AttackReach=95., AttackWindup=.10,
      CarrionEnergyPerMeal=5., FlightSpeed=900., FlightCruiseHeight=2300., FlightCeiling=5500., DayActivity=1., NightActivity=.16,
      SightRange=3200., NestlingSeconds=90.)
apply(P_["GoldenEagle"], f"{SE}:347-350", PreyRules=[prey("Jackrabbit", .7, 1.), prey("Rat", .35, .55)])
apply(P_["Mink"], f"{SE}:365-369", Diet="Carnivore", Locomotion="Amphibious", AttackReach=27., AttackWindup=.13,
      CarrionEnergyPerMeal=4., HabitatCarrionRange=520., SightRange=850., ScentRange=700., EyeHeight=15., SweepHeight=23.,
      StepHeight=12., DayActivity=.45, NightActivity=.9, GroundTurnDegreesPerSecond=340.)
apply(P_["Mink"], f"{SE}:357-364", PreyRules=[prey("Rat", .5), prey("Jackrabbit", .65, .55, .28, .42),
                                             prey("UnidentifiedFish", .12, 1.05), prey("AriakeCatfish", .2, .85),
                                             prey("CommonCarp", .3, .75, .4, .5)])
apply(P_["Jackrabbit"], f"{SE}:371-373", GroundTurnDegreesPerSecond=425., GroundAcceleration=1100., EyeHeight=23., SweepHeight=24.,
      StepHeight=13., MaturitySeconds=105., Gestation=23., BirthRecovery=85., DayActivity=.35, NightActivity=.95)
apply(P_["Bighorn"], f"{SE}:375-378", GroundTurnDegreesPerSecond=200., GroundAcceleration=700., StepHeight=34., SweepHeight=80.,
      EyeHeight=102., DefenseDamage=20., SocialNeighborRadius=640., SocialSpacing=125., OffspringGuardRange=420.,
      CaregiverFollowRange=520., DayActivity=.9, NightActivity=.48)
apply(P_["Horse"], f"{SE}:379-382", GroundTurnDegreesPerSecond=120., MinGroundNormalZ=.86, GroundAcceleration=380., StepHeight=25.,
      SweepHeight=120., EyeHeight=154., DefenseDamage=31., SocialNeighborRadius=850., SocialSpacing=220., OffspringGuardRange=510.,
      CaregiverFollowRange=740., DayActivity=.9, NightActivity=.68)
# plant guild preferences (grass, forbs, browse, wet_meadow) — author_jyu_herbivore_forage.py, re-applied on the island donor by author_jyu_reach_forage.py:135-141
PREF = {"Horse": ((1.45, .88, .68, 1.16), 25), "Bighorn": ((1.15, 1.40, 1.06, .91), 26),
        "Jackrabbit": ((.91, 1.29, 1.45, .88), 27), "Buffalo": ((1.18, 1.08, .79, 1.40), 28)}
for k, (vals, ln) in PREF.items():
    apply(P_[k], f"{HF}:{ln} (applied to island donor by {RF}:135-141)",
          PlantPreferences=dict(zip(("grass", "forbs", "browse", "wet_meadow"), vals)))

# pig-only fixture (not the island) — author_jyu_pig.py:32-44
PIGMAP = dict(AdultMass=75., BodyRadius=30., bIndividualResponse=True, WalkSpeed=130., RunSpeed=315., GroundAcceleration=680.,
              GroundTurnDegreesPerSecond=225., EyeHeight=56., SweepHeight=73., SightRange=1150., ThreatSenseRange=850.,
              RootingSeconds=1.4, CarrionEnergyPerMeal=4., CarrionHungerFraction=.83, ScentRange=800., WadeDepth=10., StepHeight=20.,
              DayActivity=.72, NightActivity=.86, NightVision=.75, SprintDrain=.09, DefenseDamage=18., OffspringGuardRange=400.,
              CaregiverFollowRange=480., SocialNeighborRadius=640., SocialSpacing=138., AdultMaleSocialAffinity=.18,
              HeatResponseC=[25., 36.], MaturitySeconds=120., Gestation=32., BirthRecovery=140., FoodPerMeal=.27, RegionalLimit=14)
PIGSRC = f"{PG}:32-44"
PIGNOTE = "LV_JYU_Pig pig-only fixture; NOT the island value (island Pig comes from setup_jyu_fauna.py via the RiparianReach donor)"

# footstep listener / emitter profiles (DA_FaunaFootsteps; Expanded copies templates with own walk/run)
FOOT = {"Herbivore": (2250, 33), "Wolf": (2600, 34), "Pig": (1540, 35), "Fox": (2350, 36), "Crow": (1400, 37),
        "Leopard": (1950, 38), "Buffalo": (1230, 39), "Rat": (1700, 40)}
FOOT_TEMPLATE = {"Bighorn": "Herbivore", "Jackrabbit": "Rat", "Horse": "Buffalo", "Mink": "Fox", "GoldenEagle": "Crow"}

# island roster (author_jyu_island_fauna.py)
ISLAND = {"AriakeCatfish": ("LowerRiver", 3, "537"), "CommonCarp": ("LowerRiver", 6, "538"), "UnidentifiedFish": ("LowerRiver", 7, "539"),
          "Mink": ("LowerRiver", 2, "540"), "Horse": ("Grassland", 5, "541-542"), "Bighorn": ("Highland", 5, "543-544"),
          "GoldenEagle": ("Highland", 2, "545"), "Jackrabbit": ("Riverbank", 4, "546-547"),
          "Pig": ("Grassland", 4, "552"), "Buffalo": ("Grassland", 4, "552"), "Crow": ("Grassland", 3, "552"),
          "Fox": ("Riverbank", 2, "553"), "Rat": ("Riverbank", 6, "553"), "Leopard": ("Riverbank", 1, "553")}
REGION_TEMP = {"Snowfield": (-4, 103), "Grassland": (18, 104), "Riverbank": (14, 105), "Highland": (7, 106)}
AQUATIC = {  # island submerged patches: id -> (consumers, nursery)
    "IslandRiverInletPlants": (["CommonCarp"], True), "IslandRiverQuietMargin": (["CommonCarp", "UnidentifiedFish"], True),
    "IslandRiverGravelInsects": (["AriakeCatfish"], False), "IslandRiverRoots": (["AriakeCatfish", "Mink"], True),
    "IslandRiverDrift": (["UnidentifiedFish", "CommonCarp"], False), "IslandRiverSlowShelf": (["CommonCarp", "UnidentifiedFish"], True),
    "IslandRiverRootsShore": (["AriakeCatfish", "Mink"], False)}
# LV_JYU_Fauna fixture patches (replaced on the island)
FIXTURE = {"GroundInsects": ["Fox", "Crow", "Pig"], "FallenFruit": ["Fox", "Crow", "Pig", "Rat"], "Burrow": ["Rat"]}

# ---------------------------------------------------------------- R9 tables (6 species)
R9T = {
 "deer": dict(mass=(60., f"{Y}:116"), walk=(.24, f"{Y}:120"), run=(.60, f"{Y}:121"), accel=(.12, f"{Y}:123"),
              stam=(90, 60, f"{Y}:124-125"), see=(20., f"{Y}:126"), fov=(300., f"{Y}:127"), smell=(3., f"{Y}:129"),
              drain=(.002, f"{Y}:130"), reserve=(3., f"{Y}:131"), diet=(["grass"], f"{Y}:136"), eat=({"grass": .012}, f"{Y}:137"),
              epu=({"grass": .5}, f"{Y}:138"), hp=(True, f"{YF}:37 (overrides {Y}:139 false)"), shelter=(True, f"{Y}:141"),
              bites=([], f"{Y}:142"), bite_r=(0., f"{Y}:143"), counter=(False, f"{Y}:144"), maturity=(2700, f"{Y}:145"),
              female=(.6, f"{Y}:147"), mate=(10., f"{Y}:151"), birth=(15., f"{Y}:152"), recover=(2250, f"{YF}:45"),
              hide=(1.0, f"{YF}:40"), bite_k=(0., f"{YF}:39"), strike_k=(0., f"{YF}:41"), gore=(False, 0., f"{YF}:42-43"),
              camo=(1.0, f"{YF}:44"), turn=(130., f"{YM}:16"), lat=(9., f"{YM}:17")),
 "wolf": dict(mass=(40., f"{Y}:161"), walk=(.18, f"{Y}:165"), run=(.60, f"{Y}:166"), run_mult=([.90, 1.05], f"{Y}:167"),
              accel=(.10, f"{Y}:168"), stam=(300, 60, f"{Y}:169-170"), see=(20., f"{Y}:171"), fov=(250., f"{Y}:172"),
              smell=(5., f"{Y}:174"), drain=(.0003, f"{Y}:175"), reserve=(3., f"{Y}:176"), diet=(["meat"], f"{Y}:181"),
              eat=({"meat": .016}, f"{Y}:182"), epu=({"meat": 1.0}, f"{Y}:183"), hp=(True, f"{Y}:184"), shelter=(False, f"{Y}:186"),
              bites=(["deer", "boar", "buffalo", "leopard", "fox"], f"{YF}:47 (S' {Y}:187 = deer, boar)"), bite_r=(1.0, f"{Y}:188"),
              counter=(False, f"{Y}:189"), maturity=(1350, f"{Y}:190"), female=(0.0, f"{Y}:192 (sex none {Y}:191)"),
              mate=(10., f"{Y}:196"), birth=(15., f"{Y}:197"), recover=(2250, f"{YF}:54"), hide=(2.5, f"{YF}:49"),
              bite_k=(1.5000939941099485, f"{YF}:48"), strike_k=(0., f"{YF}:50"), gore=(False, 0., f"{YF}:51-52"),
              camo=(1.0, f"{YF}:53"), turn=(140., f"{YM}:19"), lat=(7., f"{YM}:20")),
 "boar": dict(mass=(80., f"{Y}:206"), walk=(.0866667, f"{Y}:210"), run=(.42, f"{Y}:211"), accel=(.06, f"{Y}:213"),
              stam=(70.8333333, 23.0769231, f"{Y}:214-215"), see=(8., f"{Y}:216"), fov=(300., f"{Y}:217"), smell=(6., f"{Y}:219"),
              drain=(.000466667, f"{Y}:220"), reserve=(3., f"{Y}:221"), diet=(["root", "meat", "grass"], f"{Y}:226"),
              eat=({"root": .018, "meat": .0059259259, "grass": .036}, f"{Y}:227"), epu=({"root": .15, "meat": .9, "grass": .05}, f"{Y}:228"),
              hp=(True, f"{Y}:229"), shelter=(True, f"{Y}:231"), bites=([], f"{Y}:232"), bite_r=(0., f"{Y}:233"),
              counter=(True, f"{Y}:234"), maturity=(900, f"{Y}:235"), female=(.5, f"{Y}:237"), mate=(5., f"{Y}:241"),
              birth=(7.5, f"{Y}:242"), recover=(2250, f"{YF}:62"), hide=(2.1, f"{YF}:57"), bite_k=(0., f"{YF}:56"),
              strike_k=(0.28348223622634644, f"{YF}:58"), gore=(False, 0., f"{YF}:59-60"), camo=(1.0, f"{YF}:61"),
              turn=(125., f"{YM}:22"), lat=(7., f"{YM}:23")),
 "buffalo": dict(mass=(450., f"{YF}:64"), walk=(.10, f"{YF}:68"), run=(.48, f"{YF}:69"), accel=(.06, f"{YF}:71"),
              stam=(60, 60, f"{YF}:72-73"), see=(10., f"{YF}:74"), fov=(300., f"{YF}:75"), smell=(6., f"{YF}:77"),
              drain=(.00121, f"{YF}:78"), reserve=(7.3, f"{YF}:79"), diet=(["grass"], f"{YF}:84"), eat=({"grass": .0544}, f"{YF}:85"),
              epu=({"grass": .0667}, f"{YF}:86"), hp=(True, f"{YF}:87"), shelter=(False, f"{YF}:89"), bites=([], f"{YF}:90"),
              bite_r=(0., f"{YF}:91"), counter=(True, f"{YF}:92"), maturity=(3375, f"{YF}:93"), female=(.5, f"{YF}:95"),
              mate=(10., f"{YF}:99"), birth=(15., f"{YF}:100"), recover=(3375, f"{YF}:114"), hide=(2.1, f"{YF}:109"),
              bite_k=(0., f"{YF}:108"), strike_k=(0.28348223622634644, f"{YF}:110"), gore=(True, 1.2, f"{YF}:111-112"),
              camo=(1.0, f"{YF}:113"), turn=(90., f"{YM}:25"), lat=(5., f"{YM}:26")),
 "leopard": dict(mass=(50., f"{YF}:116"), walk=(.15, f"{YF}:120"), run=(.57, f"{YF}:121"), accel=(.15, f"{YF}:123"),
              stam=(30, 90, f"{YF}:124-125"), see=(20., f"{YF}:126"), fov=(200., f"{YF}:127"), smell=(3., f"{YF}:129"),
              drain=(.000284, f"{YF}:130"), reserve=(3.3, f"{YF}:131"), diet=(["meat"], f"{YF}:136"), eat=({"meat": .0189}, f"{YF}:137"),
              epu=({"meat": .8}, f"{YF}:138"), hp=(True, f"{YF}:139"), shelter=(True, f"{YF}:141"),
              bites=(["deer", "wolf", "boar", "buffalo", "fox"], f"{YF}:142"), bite_r=(1.0, f"{YF}:143"), counter=(False, f"{YF}:144"),
              maturity=(2900, f"{YF}:145"), female=(.5, f"{YF}:147"), mate=(10., f"{YF}:151"), birth=(15., f"{YF}:152"),
              recover=(3650, f"{YF}:166"), hide=(2.5, f"{YF}:161"), bite_k=(1.5000939941099485, f"{YF}:160"), strike_k=(0., f"{YF}:162"),
              gore=(False, 0., f"{YF}:163-164"), camo=(.4, f"{YF}:165"), turn=(135., f"{YM}:28"), lat=(11., f"{YM}:29")),
 "fox": dict(mass=(7., f"{YF}:168"), walk=(.15, f"{YF}:172"), run=(.47, f"{YF}:173"), accel=(.12, f"{YF}:175"),
              stam=(60, 60, f"{YF}:176-177"), see=(12., f"{YF}:178"), fov=(260., f"{YF}:179"), smell=(5., f"{YF}:181"),
              drain=(.000464, f"{YF}:182"), reserve=(1.4, f"{YF}:183"), diet=(["meat", "root"], f"{YF}:188"),
              eat=({"meat": .00433, "root": .0029}, f"{YF}:189"), epu=({"meat": 5.714, "root": 1.714}, f"{YF}:190"),
              hp=(True, f"{YF}:191"), shelter=(True, f"{YF}:193"), bites=(["deer", "wolf", "boar", "buffalo", "leopard"], f"{YF}:194"),
              bite_r=(.55, f"{YF}:195"), counter=(False, f"{YF}:196"), maturity=(1080, f"{YF}:197"), female=(.5, f"{YF}:199"),
              mate=(10., f"{YF}:203"), birth=(15., f"{YF}:204"), recover=(2250, f"{YF}:218"), hide=(1.0, f"{YF}:213"),
              bite_k=(.2, f"{YF}:212"), strike_k=(0., f"{YF}:214"), gore=(False, 0., f"{YF}:215-216"), camo=(1.0, f"{YF}:217"),
              turn=(185., f"{YM}:31"), lat=(10., f"{YM}:32")),
}
R9_OF = {"Pig": "boar", "Buffalo": "buffalo", "Leopard": "leopard", "Fox": "fox", "deer": "deer", "wolf": "wolf"}
R9_ID = {"deer": "deer", "wolf": "wolf", "boar": "boar", "buffalo": "buffalo", "leopard": "leopard", "fox": "fox",
         "rat": "rat", "crow": "crow", "bighorn": "bighorn", "jackrabbit": "jackrabbit", "horse": "horse", "golden_eagle": "golden_eagle",
         "mink": "mink", "ariake_catfish": "ariake_catfish", "common_carp": "common_carp", "small_fish": "small_fish"}
# doc-only shoulder heights (RL_R9_SPECIES_TRAITS.md:135) and rat/crow body rows (:115-134)
SHOULDER = {"deer": "0.9", "wolf": "0.80-0.85", "boar": "0.70-0.80", "buffalo": "1.20-1.33", "leopard": "0.57-0.70",
            "fox": "0.35-0.40", "rat": "0.08"}
R9COUNTER = {"boar": 18.0, "buffalo": 56.9}   # RL_R9_SPECIES_TRAITS.md:154-155 (boar->wolf 0.18, buffalo->wolf 0.569)
R9MAP_UNREAL = {"boar": "Pig", "buffalo": "Buffalo", "leopard": "Leopard", "fox": "Fox"}

def r9(sp, key):
    return R9T[sp][key]

# ---------------------------------------------------------------- card assembly: rule species
def ue(p, key):
    return p[key]

def ueS(p, key, conv=lambda x: x, note=None):
    v, src, kind = p[key]
    return S(conv(v) if v is not None else None, src, kind, note)

def r9S(sp, key, conv=lambda x: x, note=None, idx=0):
    t = R9T[sp][key]
    return S(conv(t[idx]), t[-1], R9, note)

def stamina_obj_ue(p):
    dv, dsrc, dk = p["SprintDrain"]
    rv, rsrc, rk = p["FatigueRecovery"]
    kind = US if US in (dk, rk) else UD
    v = {"model": "stamina 0..1; drains SprintDrain/s while running; locks <=0.15, unlocks >=0.55",
         "sprint_drain_per_s": dv, "recovery_per_s": rv,
         "run_s_full_to_lock": r((1 - .15) / dv, 2), "recover_s_lock_to_unlock": r((.55 - .15) / rv, 2)}
    return S(v, f"{dsrc}; {rsrc}; lock/unlock {FM}:1522-1524", kind)

def stamina_obj_r9(sp):
    run_steps, rec_steps, src = R9T[sp]["stam"]
    v = {"model": "R9 stamina 0..1; lock 0.15 / unlock 0.55 (v3_r9.yaml:77-78)", "run_steps": run_steps, "recover_steps": rec_steps,
         "run_s_full_to_lock": STEP_S(run_steps), "recover_s_lock_to_unlock": STEP_S(rec_steps)}
    return S(v, src, R9)

def foot_hearing(name):
    tpl = FOOT_TEMPLATE.get(name, name)
    if tpl not in FOOT:
        return None
    val, ln = FOOT[tpl]
    src = f"{FS}:{ln}" + (f" (copied as template '{tpl}' by {SE}:596-600)" if name in FOOT_TEMPLATE else "")
    return S(cm(val), src, US, "footstep listener HearingRange (EcoFootstepAudioSet.h:28); heard footsteps cue prey/threat (EcoFaunaMovement.cpp:1572-1645)")

def rule_card(cid, name):
    p = P_[name]
    loc = p["Locomotion"][0]
    aquatic = loc == "Swimming"; flight = loc == "Flight"; amph = loc == "Amphibious"
    r9sp = R9_OF.get(name)
    c = {"id": cid, "unreal_id": name, "executor": "Unreal rule fauna backend (EcoFauna profile on LV_JYU_IslandEcosystemRefreshed)",
         "island_chain": "setup_jyu_fauna.py/setup_jyu_expanded_fauna.py profile -> LV_JYU_Fauna -> LV_JYU_ExpandedFauna -> SeasonalWaterFood -> RiparianHabitat -> RiparianProjectJ -> RiparianReach (donor) -> island (author_jyu_island_fauna.py:549,612)"}
    if r9sp:
        c["r9_id"] = r9sp
    # medium
    med = {}
    med["ground"] = S(not aquatic, p["Locomotion"][1], p["Locomotion"][2], f"Locomotion={loc}" + ("; walks/hops when grounded" if flight else ""))
    med["wade_depth_m"] = F(ueS(p, "WadeDepth", cm, "0 = cannot wade" if p["WadeDepth"][0] == 0 else None),
                            S(cm(PIGMAP["WadeDepth"]), PIGSRC, US, PIGNOTE) if name == "Pig" else None) if not aquatic else NA("aquatic")
    med["swim"] = S(aquatic or amph, p["Locomotion"][1], p["Locomotion"][2], f"CanSwim() {EH}:165")
    med["swim_depth_frac"] = ueS(p, "SwimDepthFraction", note="fraction of local water column height the swimmer holds (EcoFaunaWaterMovement.cpp:589)") if (aquatic or amph) else NA("not a swimmer")
    if aquatic:
        med["needs_water"] = S(True, p["Locomotion"][1], p["Locomotion"][2], f"IsAquatic() {EH}:164 — Swimming locomotion never leaves water")
    else:
        med["needs_water"] = NA("terrestrial/aerial; no drinking or thirst mechanic in the fauna backend")
    med["fly"] = S(flight, p["Locomotion"][1], p["Locomotion"][2])
    if flight:
        med["cruise_height_m"] = ueS(p, "FlightCruiseHeight", cm, "above ground")
        med["ceiling_m"] = ueS(p, "FlightCeiling", cm, "above ground")
        med["takeoff_s"] = S(0.65, f"{FM}:1791-1792", UD, "hard-coded Takeoff phase length")
    else:
        for k in ("cruise_height_m", "ceiling_m", "takeoff_s"):
            med[k] = NA("does not fly")
    if name == "CommonCarp":
        med["min_swim_depth_m"] = S({"hatchling": 0.06825, "adult": 0.091}, f"{DC}:1045", DOC, "game minimum swim water column measured at the island carp nurseries")
    c["medium"] = med
    # body
    b = {}
    b["mass_kg"] = F(ueS(p, "AdultMass"), r9S(r9sp, "mass") if r9sp else None,
                     S(cm(0) if False else 75.0, PIGSRC, US, PIGNOTE) if name == "Pig" else None,
                     S(0.3, f"{DT}:115", DOC) if name == "Rat" else None, S(0.6, f"{DT}:115", DOC) if name == "Crow" else None)
    b["radius_m"] = ueS(p, "BodyRadius", cm)
    b["sweep_height_m"] = F(ueS(p, "SweepHeight", cm, "collision sweep height"),
                            S(cm(PIGMAP["SweepHeight"]), PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    if name in ("deer", "wolf") or (r9sp and r9sp in SHOULDER) or name == "Rat":
        key = r9sp or "rat"
        b["shoulder_height_m"] = S(SHOULDER[key], f"{DT}:135", DOC, "range string, metres")
    walk_note = "swim speed in water (EcoFaunaWaterMovement.cpp:199 uses WalkSpeed)" if aquatic else None
    b["walk_mps"] = F(ueS(p, "WalkSpeed", cm, walk_note), r9S(r9sp, "walk", UPS) if r9sp else None,
                      S(.6, f"{DT}:117", DOC, "R9 stage-3 draft 0.04 u/step") if name == "Rat" else None,
                      S(.75, f"{DT}:117", DOC, "R9 stage-3 draft ground 0.05 u/step") if name == "Crow" else None)
    run_note = "not used by water movement (EcoFaunaWaterMovement.cpp:199); drives animation/footstep scale only" if aquatic else None
    b["run_mps"] = F(ueS(p, "RunSpeed", cm, run_note),
                     r9S(r9sp, "run", UPS) if r9sp else None,
                     S(1.41, f"{DT}:117", DOC, "R9 stage-3 draft 0.094 u/step") if name == "Rat" else None)
    if aquatic or amph:
        b["swim_mps"] = S(cm(p["WalkSpeed"][0]), f"{p['WalkSpeed'][1]}; {FW}:199",
                          p["WalkSpeed"][2], "swim = WalkSpeed x SpeedScale x Lerp(0.45,1,activity); " + ("amphibious swim stamina -0.025/s (EcoFaunaWaterMovement.cpp:201,628)" if amph else "no faster swim gait"))
    else:
        b["swim_mps"] = NA("not a swimmer")
    if flight:
        b["fly_mps"] = F(ueS(p, "FlightSpeed", cm, "horizontal cruise speed; climb/descent = 0.65 x FlightSpeed (EcoFaunaMovement.cpp:516)"),
                         S(6.3, f"{DT}:117", DOC, "R9 stage-3 draft fly 0.42 u/step") if name == "Crow" else None)
        b["cruise_mps"] = ueS(p, "FlightSpeed", cm)
        b["dive_mps"] = S(cm(p["FlightSpeed"][0]) if p["bCanDiveHunt"][0] else None, f"{FM}:1449-1451" if p["bCanDiveHunt"][0] else None,
                          (US if p["bCanDiveHunt"][0] else None), "dive moves at FlightSpeed toward prey" if p["bCanDiveHunt"][0] else "no dive hunting (bCanDiveHunt=false)") if p["bCanDiveHunt"][0] else NA("bCanDiveHunt=false")
    else:
        for k in ("fly_mps", "cruise_mps", "dive_mps"):
            b[k] = NA("does not fly")
    b["accel_mps2"] = F(ueS(p, "GroundAcceleration", cm), r9S(r9sp, "accel", UPS2) if r9sp else None,
                        S(5.625, f"{DT}:118", DOC, "R9 stage-3 draft 0.05 u/step^2") if name == "Rat" else None,
                        S(9.0, f"{DT}:118", DOC, "R9 stage-3 draft 0.08 u/step^2") if name == "Crow" else None)
    tv = p["GroundTurnDegreesPerSecond"]
    b["turn_dps"] = F(S(tv[0], tv[1], tv[2], "0 = unrestricted heading" if tv[0] == 0 else None),
                      r9S(r9sp, "turn") if r9sp else None,
                      S(225., PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    b["lat_accel_mps2"] = F(r9S(r9sp, "lat", note="no Unreal equivalent")) if r9sp else NUL("no lateral-acceleration limit in Unreal fauna; not in R9")
    b["max_slope_deg"] = ueS(p, "MinGroundNormalZ", SLOPE, f"acos(MinGroundNormalZ={p['MinGroundNormalZ'][0]})") if not aquatic else NA("aquatic")
    b["step_m"] = F(ueS(p, "StepHeight", cm), S(.20, PIGSRC, US, PIGNOTE) if name == "Pig" else None) if not aquatic else NA("aquatic")
    b["stamina"] = F(stamina_obj_ue(p), stamina_obj_r9(r9sp) if r9sp else None,
                     S({"run_steps": 45, "recover_steps": 30}, f"{DT}:119", DOC) if name == "Rat" else None,
                     S({"fly_steps": 600, "recover_steps": 60}, f"{DT}:119", DOC) if name == "Crow" else None)
    b["maintenance_energy_per_s"] = F(ueS(p, "Maintenance", note="vitals energy units/s at full activity; plant energy 5/unit (EcoFauna.h:15)"),
                                      S({"drain_E_per_step": R9T[r9sp]["drain"][0], "drain_E_per_s": PER_S(R9T[r9sp]["drain"][0]),
                                         "reserve_days": R9T[r9sp]["reserve"][0]}, f"{R9T[r9sp]['drain'][1]}; {R9T[r9sp]['reserve'][1]}", R9,
                                        "R9 E units (stomach 0..1), not Unreal vitals units", cmp=False) if r9sp else None)
    c["body"] = b
    # senses
    se = {}
    se["sight_m"] = F(ueS(p, "SightRange", cm, "food/prey/carrion sight (EcoFaunaMovement.cpp:255-266,844)"),
                      r9S(r9sp, "see", U) if r9sp else None, S(cm(PIGMAP["SightRange"]), PIGSRC, US, PIGNOTE) if name == "Pig" else None,
                      S(6.0, f"{DT}:131", DOC, "R9 stage-3 draft eye 3 u") if name == "Rat" else None,
                      S(60.0, f"{DT}:131", DOC, "R9 stage-3 draft eye 30 u") if name == "Crow" else None)
    se["fov_deg"] = F(ueS(p, "SightHalfAngle", lambda h: r(2 * h, 1), "full angle = 2 x SightHalfAngle (prey sight)"),
                      r9S(r9sp, "fov") if r9sp else None,
                      S(320.0, f"{DT}:131", DOC) if name == "Rat" else None, S(300.0, f"{DT}:131", DOC) if name == "Crow" else None)
    se["eye_height_m"] = F(ueS(p, "EyeHeight", cm), S(cm(PIGMAP["EyeHeight"]), PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    sv = p["ScentRange"]
    se["smell_m"] = F(S(cm(sv[0]), sv[1], sv[2], "0 = no scent sensing" if sv[0] == 0 else "scales with sqrt(stock/20) for carrion (EcoFaunaMovement.cpp:841-843)"),
                      r9S(r9sp, "smell", U) if r9sp else None, S(cm(PIGMAP["ScentRange"]), PIGSRC, US, PIGNOTE) if name == "Pig" else None,
                      S(8.0, f"{DT}:131", DOC, "R9 stage-3 draft nose 4 u") if name == "Rat" else None,
                      S(1.0, f"{DT}:131", DOC, "R9 stage-3 draft nose 0.5 u") if name == "Crow" else None)
    if p["HabitatCarrionRange"][0]:
        se["habitat_carrion_m"] = ueS(p, "HabitatCarrionRange", cm, "caps scent search for carrion")
    fh = foot_hearing(name)
    r9hear = S({"min_m": 4.0, "max_m": 40.0}, f"{RB}:225-230", R9, "R9: radius set by the EMITTER's speed (species-independent), 2-20 u", cmp=False) if r9sp else None
    se["hearing_m"] = F(fh, r9hear) if fh else NUL("no footstep listener profile for this species -> no footstep hearing (EcoFaunaMovement.cpp:1572)")
    se["threat_sense_m"] = F(ueS(p, "ThreatSenseRange", cm, "visual threat range; x Lerp(1,NightVision,darkness) (EcoFaunaMovement.cpp:1527-1528)"),
                             S(cm(PIGMAP["ThreatSenseRange"]), PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    se["threat_fov_deg"] = ueS(p, "ThreatSightHalfAngle", lambda h: r(2 * h, 1), "full angle = 2 x ThreatSightHalfAngle")
    se["threat_near_awareness_m"] = ueS(p, "ThreatNearAwarenessRange", cm, "omnidirectional near awareness")
    se["night_vision"] = ueS(p, "NightVision", note="sight multiplier at full darkness")
    se["day_activity"] = ueS(p, "DayActivity")
    se["night_activity"] = ueS(p, "NightActivity")
    if r9sp:
        se["camo"] = S(R9T[r9sp]["camo"][0], R9T[r9sp]["camo"][1], R9, "R9 R3: how far others see this body (1 = plain)")
        se["head_down_mult"] = S(.6, {"boar": f"{Y}:218", "buffalo": f"{YF}:76", "leopard": f"{YF}:128", "fox": f"{YF}:180"}[r9sp], R9, "eyes x0.6 while eating")
    c["senses"] = se
    # diet
    d = {}
    diet = p["Diet"][0]
    d["diet_class"] = F(S(diet, p["Diet"][1], p["Diet"][2]),
                        S(R9T[r9sp]["diet"][0], R9T[r9sp]["diet"][1], R9, "R9 diet order") if r9sp else None,
                        S(["root", "meat"], f"{DT}:122", DOC, "stage-3 draft") if name == "Rat" else None,
                        S(["meat", "root"], f"{DT}:122", DOC, "stage-3 draft") if name == "Crow" else None)
    plant = (not aquatic) and diet != "Carnivore"
    d["plant_native_grid"] = S(plant, f"{EH}:166 UsesPlantFood(); {FM}:1950-1952; {FC}:972", US if p["Diet"][2] == US or p["Locomotion"][2] == US else UD,
                               "eats the Native vegetation grid (no guild distinction)" if plant else "does not eat land plants")
    prefs = p["PlantPreferences"][0]
    for g in ("grass", "forbs", "browse", "wet_meadow"):
        if prefs:
            d[g] = S(prefs[g], p["PlantPreferences"][1], US, "relative preference at island land-forage patches (consumers Horse/Bighorn/Jackrabbit/Buffalo, {}:587-609)".format(IF))
        elif plant:
            d[g] = S(1.0, f"{EH}:79-80,170", UD, "omitted guild = ordinary food (1.0); but no island guild patch lists this species as consumer")
        else:
            d[g] = NA("not a land-plant eater")
    if r9sp == "buffalo":
        d["grass"] = F(d["grass"], S({"eat_units_per_s": PER_S(.0544), "energy_per_unit": .0667}, f"{YF}:85-86", R9, "R9 grass eating (R9 food units)", cmp=False))
    # roots
    if r9sp and "root" in R9T[r9sp]["diet"][0]:
        d["roots"] = S({"eat_units_per_s": PER_S(R9T[r9sp]["eat"][0]["root"]), "energy_per_unit": R9T[r9sp]["epu"][0]["root"]},
                       f"{R9T[r9sp]['eat'][1]}; {R9T[r9sp]['epu'][1]}", R9,
                       "no root resource in Unreal island" + ("; Unreal RootingSeconds=1.4 s is a rooting pause while eating grid plants (EcoFaunaMovement.cpp:2117-2120); pig-only map has a HerbaceousRoots patch (author_jyu_pig.py:122)" if name == "Pig" else ""))
    elif name == "Rat":
        d["roots"] = S(True, f"{DT}:122", DOC, "stage-3 draft diet root->meat; no root resource in Unreal")
    elif name == "Crow":
        d["roots"] = S(True, f"{DT}:122", DOC, "stage-3 draft diet meat->root; no root resource in Unreal")
    elif aquatic:
        d["roots"] = NA("aquatic; see aquatic_plants_drift (IslandRiverRoots is a submerged root-margin patch)")
    else:
        d["roots"] = S(False, p["Diet"][1], p["Diet"][2], f"Diet={diet}; no root resource on the island")
    if name in ("Fox", "Crow", "Pig"):
        d["insects"] = F(S(False, f"{IF}:571-612", US, "island patch list has no land insect patch"),
                         S(True, f"{FB}:32", US, "LV_JYU_Fauna fixture GroundInsects patch (energy 4.5/meal); replaced on island"))
    elif name == "AriakeCatfish":
        d["insects"] = S(True, f"{IF}:573", US, "IslandRiverGravelInsects benthic patch, 2.8 energy/meal")
    elif name == "Rat":
        d["insects"] = S(False, f"{IF}:571-612", US, "no land insect patch on the island (fixture GroundInsects never listed Rat, author_jyu_fauna_balance.py:32)")
    elif aquatic:
        d["insects"] = NA("see aquatic_plants_drift")
    else:
        d["insects"] = S(False, p["Diet"][1], p["Diet"][2], f"Diet={diet}; no insect resource")
    if name in ("Fox", "Crow", "Pig", "Rat"):
        d["fruit_mast"] = F(S(False, f"{IF}:571-612", US, "no fruit patch on island"),
                            S(True, f"{FB}:34", US, "LV_JYU_Fauna FallenFruit fixture (4.0/meal); replaced on island"),
                            S(True, f"{PG}:120", US, PIGNOTE + " (FallenMast patch)") if name == "Pig" else None)
    aq = [pid for pid, (cons, _) in AQUATIC.items() if name in cons]
    d["aquatic_plants_drift"] = S(aq, f"{IF}:571-584 (+RootsShore split {IF}:162-191)", US,
                                   "island submerged patches; 2.8 energy/meal, capacity 16 nursery / 11 other") if aq else (NA("not aquatic") if not (aquatic or amph) else NUL())
    rules = p["PreyRules"][0]
    d["meat_live_prey"] = S(bool(rules), p["PreyRules"][1], p["PreyRules"][2],
                            f"PredationEnergyPerMeal = {p['CarrionEnergyPerMeal'][0] or 6.0} ({EH}:129)" if rules else ("carnivore without prey rules: eats patches/carrion only" if diet == "Carnivore" else None))
    if r9sp:
        d["meat_live_prey"] = F(d["meat_live_prey"], S(bool(R9T[r9sp]["bites"][0]), R9T[r9sp]["bites"][1], R9))
    ce = p["CarrionEnergyPerMeal"]
    d["carrion"] = S({"eats": ce[0] > 0, "energy_per_meal": ce[0], "hunger_start_frac": p["CarrionHungerFraction"][0]} if ce[0] > 0 else {"eats": False},
                     ce[1], ce[2], None)
    if r9sp and "meat" in R9T[r9sp]["diet"][0]:
        d["carrion"] = F(d["carrion"], S({"eat_units_per_s": PER_S(R9T[r9sp]["eat"][0]["meat"]), "energy_per_unit": R9T[r9sp]["epu"][0]["meat"]},
                                          f"{R9T[r9sp]['eat'][1]}; {R9T[r9sp]['epu'][1]}", R9, "R9 meat = carcass meat (kg/9 per unit)", cmp=False))
    d["food_per_meal_units"] = ueS(p, "FoodPerMeal", note="Native grid food units per plant meal; energy = units x 5")
    d["meal_stop_frac"] = ueS(p, "MealStopFraction")
    d["post_meal_rest_s"] = ueS(p, "PostMealRestSeconds")
    if p["RootingSeconds"][0]:
        d["rooting_s"] = ueS(p, "RootingSeconds")
    d["feeding_places_on_own_carcass"] = ueS(p, "FeedingPlaces")
    d["adult_carcass_energy"] = ueS(p, "AdultCarrionEnergy", note="0 = estimated from body mass")
    c["diet"] = d
    # combat
    cb = {}
    cb["hunts"] = F(S(rules, p["PreyRules"][1], p["PreyRules"][2], "MaxPreyMassRatio: prey mass <= ratio x hunter mass (both x size^3 x Lerp(0.12,1,age)); maturity limits by prey HP<60% (EcoFaunaWaterMovement.cpp:24-30); fauna backend can only target fauna residents (EcoFauna.h:81)"),
                    S(R9T[r9sp]["bites"][0], R9T[r9sp]["bites"][1], R9) if r9sp else None)
    if rules or diet == "Carnivore":
        cb["attack_reach_m"] = F(ueS(p, "AttackReach", cm), S(U(R9T[r9sp]["bite_r"][0]), R9T[r9sp]["bite_r"][1], R9, "x genetic size x growth") if r9sp and R9T[r9sp]["bite_r"][0] else None)
        cb["attack_windup_s"] = ueS(p, "AttackWindup")
        cb["attack_recovery_s"] = ueS(p, "AttackRecovery")
        cb["pursuit_limit_s"] = ueS(p, "PursuitLimitSeconds")
        cb["stalk_range_m"] = ueS(p, "StalkRange", cm, "0 = no stalking")
        cb["flank_defended_prey"] = ueS(p, "bFlankDefendedPrey")
        cb["bite_damage"] = F(S("prey HP - 100% MaxHP if prey DefenseDamage==0, else -45% MaxHP", f"{FM}:398", UD, "same for every hunter"),
                              S({"bite_k": R9T[r9sp]["bite_k"][0]}, R9T[r9sp]["bite_k"][1], R9, "R9 R1 wound = min(1, bite_k x (Ma/Mb)^(2/3) / hide_b)") if r9sp else None)
        if p["bCanDiveHunt"][0]:
            cb["dive_hunt"] = ueS(p, "bCanDiveHunt")
    else:
        for k in ("attack_reach_m", "attack_windup_s", "attack_recovery_s", "pursuit_limit_s", "stalk_range_m", "bite_damage"):
            cb[k] = NA("does not hunt")
    dd = p["DefenseDamage"]
    cb["counterattack_damage_hp"] = F(S(dd[0], dd[1], dd[2], "hunter HP points (0-100) x size x Lerp(0.2,1,age); needs own HP>=35% and facing within +-75.5 deg (EcoFaunaMovement.cpp:383-388)" if dd[0] else "0 = no counterattack"),
                                      S(18., PIGSRC, US, PIGNOTE) if name == "Pig" else None,
                                      S(R9COUNTER.get(r9sp, 0.0), f"{R9T[r9sp]['counter'][1]}; {R9T[r9sp]['strike_k'][1]}; {DT}:154-155", R9,
                                        "R9 counter/gore damage to an adult wolf in HP points (x100): strike_k x (M_self/M_wolf)^(2/3) / hide_wolf; 0 = no counter") if r9sp else None)
    cb["offspring_guard_m"] = ueS(p, "OffspringGuardRange", cm, "0 = no parental guarding")
    cb["second_parent_guard"] = ueS(p, "bAllowSecondParentGuard")
    if r9sp:
        cb["gore"] = F(S(False, f"{FM}:324-410", UD, "no gore/charge attack in Unreal fauna"),
                       S({"gore": R9T[r9sp]["gore"][0], "gore_r_m": U(R9T[r9sp]["gore"][1])}, R9T[r9sp]["gore"][2], R9))
        cb["hide"] = S(R9T[r9sp]["hide"][0], R9T[r9sp]["hide"][1], R9, "R9 wound divisor")
    else:
        cb["gore"] = S(False, f"{FM}:324-410", UD, "no gore/charge attack in Unreal fauna")
    c["combat"] = cb
    # life
    lf = {}
    lf["maturity_s"] = F(ueS(p, "MaturitySeconds"), r9S(r9sp, "maturity", STEP_S) if r9sp else None,
                         S(STEP_S(340), f"{DT}:134", DOC, "stage-3 draft 340 steps") if name == "Rat" else None,
                         S(STEP_S(4050), f"{DT}:134", DOC, "stage-3 draft 4050 steps") if name == "Crow" else None)
    lf["gestation_s"] = F(ueS(p, "Gestation"), S(STEP_S(225), f"{Y}:103", R9, "body_common.breed.gestation (all species)") if r9sp else None,
                          S(32., PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    lf["birth_recovery_s"] = F(ueS(p, "BirthRecovery"), r9S(r9sp, "recover", STEP_S) if r9sp else None,
                               S(140., PIGSRC, US, PIGNOTE) if name == "Pig" else None,
                               S(STEP_S(375), f"{DT}:134", DOC) if name == "Rat" else None, S(STEP_S(2250), f"{DT}:134", DOC) if name == "Crow" else None)
    lf["litter"] = F(S(1, f"{ES}:400", UD, "one young per natural-birth reservation"), S(1, f"{DT}:139", DOC, "R9: litter 1 for all species") if r9sp else None)
    lf["mate_radius_m"] = F(S(10.0, f"{FC}:1301", UD, "parents within 1000 cm"), r9S(r9sp, "mate", U) if r9sp else None)
    if r9sp:
        lf["birth_radius_m"] = r9S(r9sp, "birth", U)
        lf["female_frac"] = r9S(r9sp, "female")
    lf["nestling_s"] = ueS(p, "NestlingSeconds", note="positive => needs a nest perch (FEcoFaunaPerch NestId) for natural hatches (EcoFauna.cpp:1126-1128)") if flight else NA("not a nester")
    if name == "GoldenEagle":
        lf["nest_site"] = S("Highland perch at (51314, 49330, 3137) cm, no NestId on island", f"{IF}:226-235", US,
                            "island adds a plain perch (no NestId) — fixture LV_JYU_ExpandedFauna had NestId ExpandedEagleWestNest (setup_jyu_expanded_fauna.py:553-554)")
    if aquatic:
        st = p["SpawningTemperatureC"]
        lf["spawning_temp_c"] = S(st[0], st[1], st[2], "water temperature window for nursery spawning (EcoFauna.cpp:1021)")
        lf["max_nursery_current_mps"] = ueS(p, "MaxNurseryCurrent", cm, "EcoFauna.cpp:1022")
        lf["nursery_patches"] = S([pid for pid, (cons, nur) in AQUATIC.items() if name in cons and nur], f"{IF}:571-581", US, "aquatic_nursery patches")
    else:
        lf["spawning_temp_c"] = NA("not a spawner")
        lf["max_nursery_current_mps"] = NA("not a spawner")
    lf["lifespan_s"] = NUL("no ageing death in Unreal fauna; R9 has none either")
    lf["regional_limit"] = ueS(p, "RegionalLimit")
    c["life"] = lf
    # social
    so = {}
    so["social_neighbor_m"] = F(ueS(p, "SocialNeighborRadius", cm, "0 = independent routine"), S(6.4, PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    so["social_spacing_m"] = F(ueS(p, "SocialSpacing", cm), S(1.38, PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    so["adult_male_social_affinity"] = F(ueS(p, "AdultMaleSocialAffinity"), S(.18, PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    so["caregiver_follow_m"] = F(ueS(p, "CaregiverFollowRange", cm, "0 = young do not follow"), S(4.8, PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    so["guard_radius_m"] = ueS(p, "OffspringGuardRange", cm)
    so["routine_home_radius_m"] = ueS(p, "RoutineHomeRadius", cm)
    so["individual_response"] = ueS(p, "bIndividualResponse")
    c["social"] = so
    # habitat
    h = {}
    reg, n, ln = ISLAND[name]
    h["island_region"] = S(reg, f"{IF}:{ln}", US)
    h["island_founders"] = S(n, f"{IF}:{ln}", US)
    if reg in REGION_TEMP:
        t, tl = REGION_TEMP[reg]
        h["region_air_temp_c"] = S(t, f"{IE}:{tl}", US)
    else:
        h["region_air_temp_c"] = S(16, f"{IF}:500", US, "LowerRiver rules-only region environment")
    if aquatic or amph:
        h["water_temp_c"] = S(18.5, f"{IF}:138", US, "fauna_water_temperature_c of every IslandLowerRiver habitat")
        h["water_current_mps"] = S([.03, .14], f"{IF}:511", US, "per-section river current 3-14 cm/s")
    hr = p["HeatResponseC"]
    h["heat_response_c"] = F(S(hr[0], hr[1], hr[2], "both 0 = disabled"), S([25., 36.], PIGSRC, US, PIGNOTE) if name == "Pig" else None)
    c["habitat"] = h
    return c

# ---------------------------------------------------------------- native deer / wolf
def deer_card():
    c = {"id": "deer", "unreal_id": "Herbivore (Native v3 deer)", "r9_id": "deer",
         "executor": "Unreal Native v3 (EcoWorldV3 / R7e brain) — conversion: 1 unit = 200 cm (EcoRepertoire.h:75), 1 step = 8/60 s (EcoRepertoire.h:76); u/step x 15 = m/s"}
    med = {"ground": S(True, f"{RP}:161", NA_),
           "wade_depth_m": S(0.40, f"{NH}:59", UD, "UEcoNaturalHabitatProfile.MaxWadingDepthCm default (Native terrestrial backend)"),
           "swim": S(False, f"{NH}:55", UD, "'not swimming/flying support'"), "swim_depth_frac": NA("not a swimmer"),
           "needs_water": NA("no drinking mechanic"), "fly": S(False, f"{NH}:55", UD),
           "cruise_height_m": NA("does not fly"), "ceiling_m": NA("does not fly"), "takeoff_s": NA("does not fly")}
    c["medium"] = med
    R = "deer"
    b = {}
    b["mass_kg"] = F(r9S(R, "mass", note="Native has no mass; R9 only"))
    b["radius_m"] = S(0.30, f"{WV}:445", NA_, "obstacle sweep body radius 0.15 u (only with eco.IntegratedV3.Obstacles)")
    b["shoulder_height_m"] = S(SHOULDER["deer"], f"{DT}:135", DOC)
    b["walk_mps"] = F(S(UPS(.6 * .4), f"{RP}:161-162", NA_, "HerbSpeed 0.6 u/step x GaitSpeed[walk] 0.4 = 0.24 u/step; x genome SpeedScale 0.92-1.08"), r9S(R, "walk", UPS))
    b["run_mps"] = F(S(UPS(.6), f"{RP}:161-162", NA_, "0.6 u/step; snow x0.6 (EcoWorldV3.h:505); weak x0.75 (EcoWorldV3.h:355)"), r9S(R, "run", UPS))
    for k in ("swim_mps", "fly_mps", "cruise_mps", "dive_mps"):
        b[k] = NA("n/a")
    b["accel_mps2"] = F(S("unlimited", f"{RP}:161-166", NA_, "velocity set directly each step"), r9S(R, "accel", UPS2))
    b["turn_dps"] = F(S("unlimited", f"{RP}:161-166", NA_, "heading set directly each step"), r9S(R, "turn"))
    b["lat_accel_mps2"] = F(r9S(R, "lat", note="no Native equivalent"))
    b["max_slope_deg"] = S(40.0, f"{NH}:56", UD, "WalkableSlopeDegrees default")
    b["step_m"] = S(0.35, f"{NH}:57", UD, "MaxStepUpCm; step down 0.60 m (line 58)")
    b["stamina"] = F(S("none", f"{RP}:161-191", NA_, "Native deer have no stamina; run costs 2.5x drain (GaitDrain)"), stamina_obj_r9(R))
    b["maintenance_energy_per_s"] = F(S({"drain_E_per_step": .002, "drain_E_per_s": PER_S(.002), "gait_drain": [0.714, 1.0, 2.5], "reserve_days": 3.0},
                                        f"{RP}:166,184; {WV}:350", NA_, "E 0..1; fat reserve on (eco.IntegratedV3.WildReserve=1, EcoPolicyV3IntegratedSubsystem.cpp:146)"),
                                      S({"drain_E_per_step": .002, "drain_E_per_s": PER_S(.002), "reserve_days": 3.0}, f"{Y}:130-131", R9))
    c["body"] = b
    se = {}
    se["sight_m"] = F(S(U(20.), f"{OB}:70", NA_, "SeeR 20 u (kin, food and threat); threat radius x(1-0.5 dark) x0.6 grazing x0.3 sleeping"), r9S(R, "see", U))
    se["fov_deg"] = F(S(300.0, f"{WV}:1397; {IS}:322-324", NA_, "threat FOV with eco.IntegratedV3.RealismVision=1 (default); kin/food FOV 120 deg (EcoObservationV3.h:71)"),
                      r9S(R, "fov"))
    se["eye_height_m"] = S(0.75, f"{IP}:166", NA_, "player-sight ray start height")
    se["smell_m"] = F(S("none", f"{OB}:68-86", NA_, "no smell in Native"), r9S(R, "smell", U))
    se["hearing_m"] = F(S({"min_m": U(2.), "max_m": U(20.)}, f"{OB}:171-172; {IS}:329-331", NA_, "RealismHearing=1: wolf footstep radius 4 m (roaming) to 40 m (running); rain x0.5 (EcoWorldV3.h:502)"),
                        S({"min_m": 4.0, "max_m": 40.0}, f"{RB}:225-230", R9, "emitter-speed based (same model)"),
                        S(cm(2250), f"{FS}:33", US, "'Herbivore' footstep listener profile (player/creature footsteps)", cmp=False))
    se["threat_sense_m"] = S(U(20.), f"{OB}:70,76", NA_, "same SeeR; x(1 - 0.5 x darkness)")
    se["flight_distances_m"] = S({"alert": 30.0, "flight": 15.0, "safe": 40.0}, f"{IS}:127-145; {WV}:192-194", NA_, "WildFlight=1 default world rule")
    se["night_vision"] = S(0.5, f"{OB}:76", NA_, "detect radius x(1 - 0.5 d): 0.5 at full dark")
    se["day_activity"] = NUL("Native deer have no activity curve; brain decides (SLEEP action)")
    se["night_activity"] = NUL("Native deer have no activity curve; brain decides (SLEEP action)")
    se["camo"] = S(1.0, f"{YF}:44", R9)
    se["head_down_mult"] = F(S(.6, f"{RP}:152", NA_, "GrazeHeadDown"), S(.6, f"{Y}:128", R9))
    c["senses"] = se
    d = {"diet_class": F(S("Herbivore (grass grid)", f"{RP}:187-188", NA_), S(["grass"], f"{Y}:136", R9)),
         "plant_native_grid": S(True, f"{RP}:187", NA_),
         "grass": F(S({"eat_units_per_s": PER_S(.06), "energy_per_unit": .5, "walk_eat_mult": .5}, f"{RP}:163,187-188", NA_, "FoodEatRate 0.06 u/step"),
                    S({"eat_units_per_s": PER_S(.012), "energy_per_unit": .5}, f"{Y}:137-138", R9, "eat_rate 0.012 u/step; stand-only eating")),
         "forbs": NUL("Native grid has no guild split (natural habitat guilds grass/riparian/shrub exist in EcoNaturalHabitatProfile.h:40)"),
         "browse": NUL(), "wet_meadow": NUL(), "roots": NA("not eaten"), "insects": NA("not eaten"),
         "aquatic_plants_drift": NA("not eaten"), "meat_live_prey": S(False, f"{Y}:142", R9), "carrion": S({"eats": False}, f"{Y}:136", R9)}
    c["diet"] = d
    cb = {"hunts": S([], f"{Y}:142", R9, "deer never bite"), "attack_reach_m": NA("does not hunt"),
          "counterattack_damage_hp": S("none", f"{Y}:144", R9), "offspring_guard_m": NUL(), "gore": S(False, f"{YF}:42", R9),
          "hide": S(1.0, f"{YF}:40", R9),
          "hp": F(S("no HP vs wolves: a catch kills", f"{TM}:184", NA_), S({"has_hp": True, "regen_per_day": .25}, f"{YF}:37-38", R9))}
    c["combat"] = cb
    lf = {"maturity_s": F(S(360.0, f"{NH}:44; {LH}:22", UD, "natural-population profile default"), r9S(R, "maturity", STEP_S)),
          "gestation_s": F(S(30.0, f"{NB}:155", NA_), S(STEP_S(225), f"{Y}:103", R9)),
          "birth_recovery_s": F(S(300.0, f"{NB}:125", NA_), r9S(R, "recover", STEP_S)),
          "litter": F(S(1, f"{ES}:400", UD), S(1, f"{DT}:139", DOC)),
          "mate_radius_m": F(S(U(10.), f"{NB}:154", NA_, "100 = 10^2 u^2"), r9S(R, "mate", U)),
          "birth_radius_m": F(S(U(15.), f"{NB}:73", NA_), r9S(R, "birth", U)),
          "female_frac": F(S(.6, f"{NH}:46", UD), r9S(R, "female")),
          "parent_energy_min": F(S(.7, f"{LH}:228", NA_), S(.7, f"{Y}:101", R9)),
          "nestling_s": NA("n/a"), "spawning_temp_c": NA("n/a"), "max_nursery_current_mps": NA("n/a"),
          "lifespan_s": NUL("no ageing death"),
          "max_founder_age_s": F(S(1800.0, f"{LH}:22", UD), S(STEP_S(13500), f"{Y}:149", R9))}
    c["life"] = lf
    so = {"kin_separation_m": S(U(5.), f"{OB}:79", NA_, "SepRadius 5 u"), "social_neighbor_m": NUL(), "caregiver_follow_m": NUL("family follow exists (EcoLifeHistoryV3.h:213-217) but no radius constant found"),
          "guard_radius_m": NUL()}
    c["social"] = so
    h = {"island_region": S(["Snowfield", "Grassland", "Riverbank", "Highland"], f"{IE}:103-106", US),
         "island_founders": S(48, f"{IE}:128", US, "12 per region"),
         "region_air_temp_c": S({"Snowfield": -4, "Grassland": 18, "Riverbank": 14, "Highland": 7}, f"{IE}:103-106", US),
         "heat_response_c": NUL()}
    c["habitat"] = h
    return c

def wolf_card():
    c = {"id": "wolf", "unreal_id": "Wolf (Native v3 threat)", "r9_id": "wolf",
         "executor": "Unreal Native v3 threat model (EcoThreatModel.h) — 1 unit = 200 cm, 1 step = 8/60 s"}
    med = {"ground": S(True, f"{TM}:181", NA_), "wade_depth_m": S(0.40, f"{NH}:59", UD, "Native terrestrial backend default"),
           "swim": S(False, f"{NH}:55", UD), "swim_depth_frac": NA("n/a"), "needs_water": NA("n/a"), "fly": S(False, f"{NH}:55", UD),
           "cruise_height_m": NA("n/a"), "ceiling_m": NA("n/a"), "takeoff_s": NA("n/a")}
    c["medium"] = med
    R = "wolf"
    b = {}
    b["mass_kg"] = F(r9S(R, "mass", note="Native has no mass"))
    b["radius_m"] = S(0.30, f"{WV}:445", NA_, "obstacle sweep radius; shelter body margin +1 m (eco.IntegratedV3.WolfBodyMargin, EcoPolicyV3IntegratedSubsystem.cpp:203-204)")
    b["shoulder_height_m"] = S(SHOULDER["wolf"], f"{DT}:135", DOC)
    b["walk_mps"] = F(S(UPS(.3 * .6), f"{TM}:204", NA_, "no walk gait; slowest modes: stalk 0.18 u/step = 2.7 m/s, sated roam x0.3 = 2.16 m/s (EcoThreatModel.h:258)"),
                      r9S(R, "walk", UPS))
    b["run_mps"] = F(S(UPS(.6 * .8), f"{ISH}:335; {TM}:1104", NA_, "base speed HerbSpeed 0.6 x PredSpeedMult 0.8 = 0.48 u/step (also roam speed); pounce 13.5 m/s for 1.6 s (EcoThreatModel.h:205-206); hungry x0.7 (EcoPolicyV3IntegratedProcessors.cpp:619)"),
                     S({"base_mps": 9.0, "world_mult": [0.9, 1.05], "range_mps": [8.1, 9.45]}, f"{Y}:166-167", R9))
    b["pounce_mps"] = S(UPS(1.5 * .6), f"{TM}:205-207", NA_, "stalker pounce 12 steps (1.6 s), then exhaust 1.8 m/s for 30 steps (4 s)")
    for k in ("swim_mps", "fly_mps", "cruise_mps", "dive_mps"):
        b[k] = NA("n/a")
    b["accel_mps2"] = F(S("unlimited", f"{TM}:1420-1495", NA_), r9S(R, "accel", UPS2))
    b["turn_dps"] = F(S("unlimited", f"{TM}:1420-1495", NA_), r9S(R, "turn"))
    b["lat_accel_mps2"] = F(r9S(R, "lat"))
    b["max_slope_deg"] = S(40.0, f"{NH}:56", UD)
    b["step_m"] = S(0.35, f"{NH}:57", UD)
    b["stamina"] = F(S("none (stalker exhausts 4 s after a 1.6 s pounce)", f"{TM}:205-208", NA_), stamina_obj_r9(R))
    b["maintenance_energy_per_s"] = F(S({"drain_E_per_s": .00225, "running_mult": 2}, f"{LH}:246", NA_, "predator Nutrition 0..1 drain x genome maintenance"),
                                      S({"drain_E_per_step": .0003, "drain_E_per_s": PER_S(.0003)}, f"{Y}:175", R9))
    c["body"] = b
    se = {"sight_m": F(S(U(14.), f"{TM}:182", NA_, "PredViewR 14 u; weather x0.9 rain / x0.7 snow"), r9S(R, "see", U)),
          "fov_deg": F(S(150.0, f"{TM}:183", NA_, "pred_fov_deg 150"), r9S(R, "fov")),
          "eye_height_m": NUL(), "smell_m": F(S("none", f"{TM}:178-260", NA_), r9S(R, "smell", U)),
          "hearing_m": F(S("none (Native wolf targeting is sight-only)", f"{TM}:178-260", NA_),
                         S(cm(2600), f"{FS}:34", US, "'Wolf' footstep listener profile in DA_FaunaFootsteps (not used by the Native threat step)", cmp=False),
                         S({"min_m": 4.0, "max_m": 40.0}, f"{RB}:225-230", R9, "R9 emitter-speed based hearing", cmp=False)),
          "threat_sense_m": NUL("wolves have no threat sensing in Native"),
          "night_vision": S("diurnal: sleeps at darkness >= 0.5; awake twilight speed x(1-d), floor 0.5", f"{TM}:199-200,241-246", NA_),
          "day_activity": S(1.0, f"{TM}:199", NA_), "night_activity": S(0.0, f"{TM}:199", NA_, "asleep (nocturnal wolf slot exists: NumNocturnal EcoWorldV3.h:1420)"),
          "camo": S(1.0, f"{YF}:53", R9), "head_down_mult": S(.6, f"{Y}:173", R9)}
    c["senses"] = se
    d = {"diet_class": F(S("Carnivore (deer only)", f"{TM}:181-189", NA_), S(["meat"], f"{Y}:181", R9)),
         "plant_native_grid": S(False, f"{TM}:181", NA_),
         "grass": NA("n/a"), "forbs": NA("n/a"), "browse": NA("n/a"), "wet_meadow": NA("n/a"), "roots": NA("n/a"),
         "insects": NA("n/a"), "aquatic_plants_drift": NA("n/a"),
         "meat_live_prey": S(True, f"{TM}:184", NA_),
         "carrion": F(S({"meal_max_nutrition": .6, "bite_per_s": .12, "eat_within_m": U(2.5), "meal_expires_s": 20, "eat_in_place_s": 5.0},
                        f"{LH}:234-250; {IS}:110-111", NA_, "own kill only"),
                      S({"eat_units_per_s": PER_S(.016), "energy_per_unit": 1.0}, f"{Y}:182-183", R9, "consistent with Native 0.12/s", cmp=False))}
    c["diet"] = d
    cb = {"hunts": F(S(["deer"], f"{IP}:1206; {TM}:1098-1115", NA_, "Native wolves target Native deer only (alternating stalker/chaser)"),
                     S(R9T[R]["bites"][0], R9T[R]["bites"][1], R9)),
          "attack_reach_m": F(S(U(1.), f"{TM}:184", NA_, "melee catch radius 1 u"), S(U(1.), f"{Y}:188", R9, "x size x growth")),
          "bite_damage": F(S("catch = deer dies", f"{TM}:184", NA_), S({"bite_k": R9T[R]["bite_k"][0]}, f"{YF}:48", R9)),
          "stalk_range_m": S(U(6.), f"{TM}:203", NA_, "stalk_dist: pounce starts at perceived 12 m"),
          "attack_recovery_s": S(5.0, f"{IS}:110-111", NA_, "WolfEatSeconds after a kill (eat in place)"),
          "bite_cooldown_s": S(STEP_S(8), f"{Y}:82", R9, "R9 bite cooldown 8 steps (all biters)"),
          "counterattack_damage_hp": S(False, f"{Y}:189", R9), "offspring_guard_m": NUL(),
          "gore": S(False, f"{YF}:51", R9), "hide": S(2.5, f"{YF}:49", R9)}
    c["combat"] = cb
    lf = {"maturity_s": F(S(180.0, f"{LH}:211", NA_, "FIndividual default (wolves are not natural-population)"), r9S(R, "maturity", STEP_S)),
          "gestation_s": F(S(30.0, f"{NB}:155", NA_), S(STEP_S(225), f"{Y}:103", R9)),
          "birth_recovery_s": F(S(300.0, f"{NB}:125", NA_), r9S(R, "recover", STEP_S)),
          "litter": F(S(1, f"{ES}:400", UD), S(1, f"{DT}:139", DOC)),
          "mate_radius_m": F(S(U(10.), f"{NB}:154", NA_), r9S(R, "mate", U)),
          "birth_radius_m": F(S(U(15.), f"{NB}:73", NA_), r9S(R, "birth", U)),
          "parent_nutrition_min": S(.7, f"{LH}:228", NA_), "child_not_in_shelter": S(True, f"{NB}:81", NA_),
          "nestling_s": NA("n/a"), "spawning_temp_c": NA("n/a"), "max_nursery_current_mps": NA("n/a"), "lifespan_s": NUL()}
    c["life"] = lf
    c["social"] = {"pack_hunt": S("PackHunt config (eco.IntegratedV3.PackHunt)", f"{WV}:1483-1484", NA_, "lead 12 m, door 30 m (EcoThreatModel.h:170-173)"),
                   "social_neighbor_m": NUL(), "guard_radius_m": NUL(), "caregiver_follow_m": NUL()}
    c["habitat"] = {"island_region": S(["Snowfield", "Grassland", "Riverbank", "Highland"], f"{IE}:103-106", US),
                    "island_founders": S(16, f"{IE}:128", US, "4 per region"),
                    "region_air_temp_c": S({"Snowfield": -4, "Grassland": 18, "Riverbank": 14, "Highland": 7}, f"{IE}:103-106", US),
                    "heat_response_c": NUL()}
    return c

# ---------------------------------------------------------------- build all
CARDS = {}
CARDS["deer"] = deer_card()
CARDS["wolf"] = wolf_card()
for cid, name in (("boar", "Pig"), ("buffalo", "Buffalo"), ("leopard", "Leopard"), ("fox", "Fox"), ("rat", "Rat"), ("crow", "Crow"),
                  ("bighorn", "Bighorn"), ("jackrabbit", "Jackrabbit"), ("horse", "Horse"), ("golden_eagle", "GoldenEagle"),
                  ("mink", "Mink"), ("ariake_catfish", "AriakeCatfish"), ("common_carp", "CommonCarp"), ("small_fish", "UnidentifiedFish")):
    CARDS[cid] = rule_card(cid, name)
CARDS["boar"]["note"] = "Unreal 'Pig'. Island value = setup_jyu_fauna.py; author_jyu_pig.py values (pig-only map) recorded as alt."
CARDS["small_fish"]["note"] = "Unreal 'UnidentifiedFish' — provisional freshwater gameplay guild (setup_jyu_expanded_fauna.py:340)."
for cid in ("rat", "crow"):
    CARDS[cid]["note"] = "R9 has no body for this species yet (stage 3); doc-only draft numbers from RL_R9_SPECIES_TRAITS.md:112-135 recorded as alt."

GROUPS = ("medium", "body", "senses", "diet", "combat", "life", "social", "habitat")
for cid, card in CARDS.items():
    with open(os.path.join(OUT, f"{cid}.json"), "w", encoding="utf-8") as fh:
        json.dump(card, fh, ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- conflicts & gaps
def entries(field):
    if not isinstance(field, dict) or field.get("na") or "v" not in field:
        return []
    out = [] if field.get("v") is None else [field]
    for a in field.get("alt", []):
        if a.get("v") is not None:
            out.append(a)
    return out

def norm(v):
    if isinstance(v, bool): return ("b", v)
    if isinstance(v, (int, float)): return ("n", float(v))
    if isinstance(v, list): return ("l", tuple(sorted(str(x if not isinstance(x, dict) else x.get("prey")).lower() for x in v)))
    if isinstance(v, dict):
        if "run_s_full_to_lock" in v: return ("st", (v["run_s_full_to_lock"], v["recover_s_lock_to_unlock"]))
        if "eats" in v: return ("b", v["eats"])
        if "drain_E_per_s" in v: return ("n", float(v["drain_E_per_s"]))
        return ("d", json.dumps(v, sort_keys=True))
    return ("s", str(v))

ALIAS = {"pig": "boar", "buffalo": "buffalo", "leopard": "leopard", "fox": "fox", "crow": "crow", "rat": "rat", "jackrabbit": "jackrabbit",
         "unidentifiedfish": "small_fish", "ariakecatfish": "ariake_catfish", "commoncarp": "common_carp"}

def differ(a, b):
    if a.get("cmp") is False or b.get("cmp") is False:
        return False
    ka, va = norm(a["v"]); kb, vb = norm(b["v"])
    if ka == "n" and kb == "n":
        return abs(va - vb) > 1e-6 * max(1.0, abs(va), abs(vb)) and abs(va - vb) / max(abs(va), abs(vb), 1e-12) > 0.01
    if ka == "l" and kb == "l":
        ma = {ALIAS.get(x, x) for x in va}; mb = {ALIAS.get(x, x) for x in vb}
        return ma != mb
    if ka == "st" and kb == "st":
        return any(abs(x - y) > .05 * max(abs(x), abs(y), 1e-9) for x, y in zip(va, vb))
    if ka != kb:
        # numeric vs dict/string such as 'unlimited' / 'none' or a range: a real model difference
        if {ka, kb} <= {"n", "s"} or {ka, kb} <= {"st", "s"} or ("d" in (ka, kb) and "n" in (ka, kb)):
            return True
        return False
    return va != vb

def fmt(v):
    if isinstance(v, float): return f"{v:g}"
    if isinstance(v, dict):
        if "run_s_full_to_lock" in v: return f"run {v['run_s_full_to_lock']} s / recover {v['recover_s_lock_to_unlock']} s"
        return json.dumps(v, ensure_ascii=False).replace("|", "/")
    if isinstance(v, list): return ", ".join(x.get("prey") if isinstance(x, dict) else f"{x:g}" if isinstance(x, float) else str(x) for x in v)
    return str(v).replace("|", "/")

UNREAL = (US, UD, NA_)
MODEL_DIFFS = """
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
"""
rows, gaps = [], {}
for cid, card in CARDS.items():
    gaps[cid] = []
    for g in GROUPS:
        for fname, field in card.get(g, {}).items():
            if isinstance(field, dict) and field.get("v") is None and not field.get("na") and not field.get("alt"):
                gaps[cid].append((f"{g}.{fname}", field.get("note", "")))
            es = entries(field)
            if len(es) < 2:
                continue
            base = es[0]
            for other in es[1:]:
                if differ(base, other):
                    runs = fmt(base["v"]) if base["kind"] in UNREAL and "NOT the island" not in base.get("note", "") else "not executed on the island"
                    rows.append((cid, f"{g}.{fname}", base, other, runs))

with open(os.path.join(OUT, "CONFLICTS.md"), "w", encoding="utf-8") as fh:
    fh.write("# Source conflicts (SI units)\n\n")
    fh.write("Primary = what the team island executes (Unreal rule profile, or Native v3 for deer/wolf). "
             "`pig-map` rows are LV_JYU_Pig values that the island does not use. R9 rows are the Python body table. "
             "Numbers differing by more than 1% are listed; stamina compares seconds from full to lock and lock to unlock.\n\n")
    fh.write("| species | field | primary (kind) | other source (kind) | Unreal island executes | primary src | other src |\n|---|---|---|---|---|---|---|\n")
    for cid, f, a, b, runs in rows:
        okind = b["kind"] + (" pig-map" if "NOT the island" in b.get("note", "") else " fixture" if "replaced on island" in b.get("note", "") else "")
        fh.write(f"| {cid} | {f} | {fmt(a['v'])} ({a['kind']}) | {fmt(b['v'])} ({okind}) | {runs} | `{a['src']}` | `{b['src']}` |\n")
    fh.write(f"\n{len(rows)} conflicting pairs.\n")
    fh.write(MODEL_DIFFS)

with open(os.path.join(OUT, "GAPS.md"), "w", encoding="utf-8") as fh:
    fh.write("# Gaps — applicable fields with no source anywhere in the repo\n\n"
             "Fields marked not-applicable (e.g. flight fields for walkers) are excluded. These are the values R10 has to choose.\n\n")
    for cid, items in gaps.items():
        fh.write(f"## {cid} ({len(items)})\n\n")
        for f, note in items:
            fh.write(f"- `{f}`" + (f" — {note}" if note else "") + "\n")
        fh.write("\n")

# ---------------------------------------------------------------- summary counts
summary = {}
for cid, card in CARDS.items():
    filled = nulls = na = 0
    for g in GROUPS:
        for fname, field in card.get(g, {}).items():
            if not isinstance(field, dict):
                continue
            if field.get("na"):
                na += 1
            elif field.get("v") is None and not field.get("alt"):
                nulls += 1
            else:
                filled += 1
    summary[cid] = (filled, nulls, na)
with open(os.path.join(OUT, "_counts.json"), "w") as fh:
    json.dump(summary, fh, indent=1)
print(json.dumps(summary))
print("conflicts", len(rows))
