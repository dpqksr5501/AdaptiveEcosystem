using UnrealBuildTool;
public class AdaptiveEcosystemEditor : ModuleRules {
    public AdaptiveEcosystemEditor(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage=PCHUsageMode.UseExplicitOrSharedPCHs;
        PrivateDependencyModuleNames.AddRange(new string[]{"Core","CoreUObject","Engine","AdaptiveEcosystem","UnrealEd","AnimGraph","AnimGraphRuntime","BlueprintGraph","KismetCompiler"});
    }
}
