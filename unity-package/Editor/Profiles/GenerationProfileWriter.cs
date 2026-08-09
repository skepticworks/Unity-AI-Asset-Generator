using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Profiles
{
    public static class GenerationProfileWriter
    {
        public static string Serialize(GenerationProfile profile) => JsonWriter.Serialize(ToObject(profile));

        public static void WriteAtomic(string path, GenerationProfile profile)
        {
            var directory = Path.GetDirectoryName(path);
            if (string.IsNullOrEmpty(directory)) throw new ArgumentException("Profile path needs a directory.", nameof(path));
            Directory.CreateDirectory(directory);
            var temporary = path + ".tmp";
            File.WriteAllText(temporary, Serialize(profile), new UTF8Encoding(false));
            if (File.Exists(path))
            {
                var backup = path + ".replace.bak";
                File.Replace(temporary, path, backup);
                if (File.Exists(backup)) File.Delete(backup);
            }
            else File.Move(temporary, path);
        }

        public static Dictionary<string, object> ToObject(GenerationProfile profile)
        {
            return new Dictionary<string, object>
            {
                ["schema"] = new Dictionary<string, object>
                {
                    ["name"] = profile.SchemaName,
                    ["version"] = profile.SchemaVersion
                },
                ["profile"] = new Dictionary<string, object>
                {
                    ["id"] = profile.Id, ["revision"] = profile.Revision,
                    ["display_name"] = profile.DisplayName, ["description"] = profile.Description,
                    ["asset_type"] = profile.AssetType, ["builtin"] = profile.Builtin, ["tags"] = profile.Tags
                },
                ["prompt"] = new Dictionary<string, object>
                {
                    ["template_id"] = profile.Prompt.TemplateId,
                    ["template_revision"] = profile.Prompt.TemplateRevision,
                    ["default_modifiers"] = profile.Prompt.DefaultModifiers
                },
                ["negative_prompt"] = new Dictionary<string, object>
                {
                    ["profile_id"] = profile.NegativePrompt.ProfileId,
                    ["profile_revision"] = profile.NegativePrompt.ProfileRevision,
                    ["additional_terms"] = profile.NegativePrompt.AdditionalTerms
                },
                ["generation_defaults"] = new Dictionary<string, object>
                {
                    ["width"] = profile.Defaults.Width, ["height"] = profile.Defaults.Height,
                    ["steps"] = profile.Defaults.Steps, ["guidance_scale"] = profile.Defaults.GuidanceScale,
                    ["seed_strategy"] = profile.Defaults.SeedStrategy, ["fixed_seed"] = profile.Defaults.FixedSeed
                },
                ["processing"] = new Dictionary<string, object>
                {
                    ["transparency_strategy"] = profile.Processing.TransparencyStrategy,
                    ["alpha_threshold"] = profile.Processing.AlphaThreshold,
                    ["alpha_feather"] = profile.Processing.AlphaFeather,
                    ["remove_near_transparent"] = profile.Processing.RemoveNearTransparent,
                    ["zero_rgb_when_transparent"] = profile.Processing.ZeroRgbWhenTransparent
                },
                ["unity"] = new Dictionary<string, object>
                {
                    ["import_profile_id"] = profile.Unity.ImportProfileId,
                    ["suggested_output_directory"] = profile.Unity.SuggestedOutputDirectory,
                    ["create_material"] = profile.Unity.CreateMaterial,
                    ["pixels_per_unit"] = profile.Unity.PixelsPerUnit,
                    ["pivot_mode"] = profile.Unity.PivotMode,
                    ["custom_pivot_x"] = profile.Unity.CustomPivotX,
                    ["custom_pivot_y"] = profile.Unity.CustomPivotY,
                    ["atlas_hint"] = profile.Unity.AtlasHint
                }
            };
        }
    }
}
