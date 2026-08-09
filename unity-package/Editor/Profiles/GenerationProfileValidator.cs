using System.Collections.Generic;
using UnityAiAssets.Editor.AssetTypes;
using System.Text.RegularExpressions;

namespace UnityAiAssets.Editor.Profiles
{
    public static class GenerationProfileValidator
    {
        static readonly Regex IdPattern = new Regex(@"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$");

        public static List<ValidationIssue> ValidateStructure(GenerationProfile profile)
        {
            var issues = new List<ValidationIssue>();
            Required(profile?.Id, "profile.id", issues);
            Required(profile?.DisplayName, "profile.display_name", issues);
            Required(profile?.AssetType, "profile.asset_type", issues);
            Required(profile?.Prompt?.TemplateId, "prompt.template_id", issues);
            Required(profile?.NegativePrompt?.ProfileId, "negative_prompt.profile_id", issues);
            Required(profile?.Unity?.ImportProfileId, "unity.import_profile_id", issues);
            if (profile == null) return issues;
            if (!string.IsNullOrWhiteSpace(profile.Id) && !IdPattern.IsMatch(profile.Id))
                issues.Add(new ValidationIssue { Path = "profile.id", Code = ProfileErrorCodes.ProfileIdInvalid, Message = "Profile id is invalid." });
            if (profile.Revision < 1) Invalid("profile.revision", "Revision must be at least 1.", issues);
            if (!AssetTypeIds.IsKnown(profile.AssetType)) Invalid("profile.asset_type", "Unknown asset type.", issues);
            if (profile.Defaults.Width <= 0) Invalid("generation_defaults.width", "Width must be positive.", issues);
            if (profile.Defaults.Height <= 0) Invalid("generation_defaults.height", "Height must be positive.", issues);
            if (profile.Defaults.Steps <= 0) Invalid("generation_defaults.steps", "Steps must be positive.", issues);
            if (profile.Defaults.GuidanceScale < 0) Invalid("generation_defaults.guidance_scale", "Guidance must not be negative.", issues);
            if (profile.Defaults.SeedStrategy != "random" && profile.Defaults.SeedStrategy != "fixed")
                Invalid("generation_defaults.seed_strategy", "Expected random or fixed.", issues);
            if (profile.Defaults.SeedStrategy == "fixed" && !profile.Defaults.FixedSeed.HasValue)
                Invalid("generation_defaults.fixed_seed", "A fixed seed is required for fixed strategy.", issues);
            if (profile.AssetType == "sprite" || profile.AssetType == "icon")
            {
                if (profile.Unity.PixelsPerUnit <= 0)
                    Invalid("unity.pixels_per_unit", "Pixels per unit must be positive.", issues);
                if (profile.Unity.PivotMode != "center" && profile.Unity.PivotMode != "bottom_center" &&
                    profile.Unity.PivotMode != "custom")
                    Invalid("unity.pivot_mode", "Expected center, bottom_center, or custom.", issues);
                if (profile.Unity.PivotMode == "custom" &&
                    (profile.Unity.CustomPivotX < 0 || profile.Unity.CustomPivotX > 1 ||
                     profile.Unity.CustomPivotY < 0 || profile.Unity.CustomPivotY > 1))
                    Invalid("unity.custom_pivot", "Custom pivot coordinates must be between zero and one.", issues);
            }
            return issues;
        }

        public static List<ValidationIssue> ValidateReferences(
            GenerationProfile profile, ProfileCatalog catalog)
        {
            var issues = new List<ValidationIssue>();
            if (!catalog.TryGetPromptTemplate(profile.Prompt.TemplateId, out var template))
                Missing("prompt.template_id", profile.Prompt.TemplateId, issues);
            else if (template.Revision != profile.Prompt.TemplateRevision)
                Invalid("prompt.template_revision", "Referenced template revision is unavailable.", issues);
            if (!catalog.TryGetNegativeProfile(profile.NegativePrompt.ProfileId, out var negative))
                Missing("negative_prompt.profile_id", profile.NegativePrompt.ProfileId, issues);
            else if (negative.Revision != profile.NegativePrompt.ProfileRevision)
                Invalid("negative_prompt.profile_revision", "Referenced negative profile revision is unavailable.", issues);
            if (!catalog.TryGetImportProfile(profile.Unity.ImportProfileId, out _))
                Missing("unity.import_profile_id", profile.Unity.ImportProfileId, issues);
            return issues;
        }

        static void Required(string value, string path, List<ValidationIssue> issues)
        {
            if (string.IsNullOrWhiteSpace(value))
                issues.Add(new ValidationIssue { Path = path, Code = ProfileErrorCodes.FieldRequired, Message = "Value is required." });
        }
        static void Invalid(string path, string message, List<ValidationIssue> issues) =>
            issues.Add(new ValidationIssue { Path = path, Code = ProfileErrorCodes.ValueInvalid, Message = message });
        static void Missing(string path, string value, List<ValidationIssue> issues) =>
            issues.Add(new ValidationIssue { Path = path, Code = ProfileErrorCodes.ReferenceMissing, Message = "Reference not found: " + value });
    }
}
