// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class AdaptiveEcosystem : ModuleRules
{
	public AdaptiveEcosystem(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			"StateTreeModule",
			"GameplayStateTreeModule",
			"UMG",
			"Slate"
		});

		PrivateDependencyModuleNames.AddRange(new string[] { });

		PublicIncludePaths.AddRange(new string[] {
			"AdaptiveEcosystem",
			"AdaptiveEcosystem/Core",
			"AdaptiveEcosystem/World",
			"AdaptiveEcosystem/Ecology",
			"AdaptiveEcosystem/Creature",
			"AdaptiveEcosystem/Evolution",
			"AdaptiveEcosystem/Network",
			"AdaptiveEcosystem/Debug",
			"AdaptiveEcosystem/Variant_Platforming",
			"AdaptiveEcosystem/Variant_Platforming/Animation",
			"AdaptiveEcosystem/Variant_Combat",
			"AdaptiveEcosystem/Variant_Combat/AI",
			"AdaptiveEcosystem/Variant_Combat/Animation",
			"AdaptiveEcosystem/Variant_Combat/Gameplay",
			"AdaptiveEcosystem/Variant_Combat/Interfaces",
			"AdaptiveEcosystem/Variant_Combat/UI",
			"AdaptiveEcosystem/Variant_SideScrolling",
			"AdaptiveEcosystem/Variant_SideScrolling/AI",
			"AdaptiveEcosystem/Variant_SideScrolling/Gameplay",
			"AdaptiveEcosystem/Variant_SideScrolling/Interfaces",
			"AdaptiveEcosystem/Variant_SideScrolling/UI"
		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
