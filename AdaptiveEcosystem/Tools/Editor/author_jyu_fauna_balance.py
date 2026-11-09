"""Author the staged habitat and food experiment in the owned fauna map."""

import unreal


MAP = "/Game/JYU/Maps/LV_JYU_Fauna"
OWNER = "JYU.Fauna.20261108"


def configure(world, runtime):
    groups = runtime.get_editor_property("groups")
    patches = []
    for group_index, group in enumerate(groups):
        if str(group.get_editor_property("region_id")) != "FaunaMeadow":
            continue
        region = group.get_editor_property("region_id")
        rat_sites = ((-850., -550.), (480., -350.), (-1750., 1550.))

        def patch(name, xy, stage, consumers, capacity, rate, meal, shelter=0.):
            item = unreal.EcoFaunaHabitatPatch()
            values = dict(id=name, region_id=region, center=unreal.Vector(*xy, 0.), stage=stage,
                          consumers=consumers, capacity=capacity, regrowth_per_second=rate, energy_per_meal=meal)
            if shelter:
                values.update(sheltered_species="Rat", shelter_radius=shelter, entrance_radius=7.)
            for key, value in values.items():
                item.set_editor_property(key, value)
            patches.append(item)

        for index, site in enumerate(rat_sites):
            patch(f"Burrow_{index}", site, 1, ["Rat"], 27., .32, 2.8, 82.)
        for index, site in enumerate(((-540., -1120.), (840., -1010.), (-2600., 440.), (970., 800.))):
            patch(f"GroundInsects_{index}", site, 2, ["Fox", "Crow", "Pig"], 26., .53, 4.5)
        for index, site in enumerate(((-550., 60.), (0., -1450.), (-1380., 900.))):
            patch(f"FallenFruit_{index}", site, 2, ["Fox", "Crow", "Pig", "Rat"], 24., .44, 4.)

        placements = group.get_editor_property("fauna")
        for index, placement in enumerate(placements):
            kind = str(placement.get_editor_property("species_id"))
            if kind == "Rat":
                sites = [unreal.Vector(x + dx, y + dy, 0.) for x, y in rat_sites
                         for dx, dy in ((-46., 12.), (42., 15.), (-138., -76.), (130., 94.))]
                placement.set_editor_property("habitat_spawn_points", sites)
                placement.set_editor_property("habitat_spawn_stage", 1)
            if kind == "Leopard":
                placement.set_editor_property("habitat_spawn_points",
                                              [unreal.Vector(-4080., 3660., 0.), unreal.Vector(-2030., 820., 0.)])
                placement.set_editor_property("habitat_spawn_stage", 3)
            placements[index] = placement
        group.set_editor_property("fauna", placements)
        groups[group_index] = group
    if not patches:
        raise RuntimeError("FaunaMeadow is missing")
    runtime.set_editor_property("groups", groups)
    profiles = runtime.get_editor_property("fauna_species")
    for index, profile in enumerate(profiles):
        if str(profile.get_editor_property("species_id")) == "Leopard":
            profile.set_editor_property("flank_defended_prey", True)
            profile.set_editor_property("habitat_carrion_range", 3000.)
            profiles[index] = profile
    runtime.set_editor_property("fauna_species", profiles)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    runtime.set_editor_property("fauna_habitat_stage", 3)


if __name__ == "__main__":
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.load_level(MAP):
        raise RuntimeError(f"Could not open {MAP}")
    world = editor.get_editor_world()
    if unreal.EditorAssetLibrary.get_metadata_tag(world, "JYUOwner") != OWNER:
        raise RuntimeError("Expected the owned fauna map")
    runtime, = [actor for actor in actors.get_all_level_actors()
                if isinstance(actor, unreal.EcoCreatureIntegrationSpawner)]
    configure(world, runtime)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError(f"Could not save {MAP}")
    unreal.log("FAUNA_BALANCE_AUTHORED")
