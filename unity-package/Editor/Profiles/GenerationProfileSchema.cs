using System;
using System.Collections.Generic;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Profiles
{
    public sealed class ValidationIssue
    {
        public string Path;
        public string Code;
        public string Message;
        public override string ToString() => string.IsNullOrEmpty(Path) ? Message : Path + ": " + Message;
    }

    public sealed class GenerationProfileParseResult
    {
        public GenerationProfile Profile;
        public List<ValidationIssue> Issues = new List<ValidationIssue>();
        public bool IsValid => Profile != null && Issues.Count == 0;
    }

    public static class GenerationProfileSchema
    {
        public static GenerationProfileParseResult Parse(JsonNode root, string sourcePath = null)
        {
            var result = new GenerationProfileParseResult();
            if (root == null || !root.IsObject)
            {
                result.Issues.Add(Issue("$", ProfileErrorCodes.SchemaInvalid, "Root must be an object."));
                return result;
            }
            var schema = root.Get("schema");
            var name = schema.Get("name").AsString();
            var version = schema.Get("version").AsString();
            if (name != ProfileSchemaVersions.GenerationProfileSchemaName)
                result.Issues.Add(Issue("schema.name", ProfileErrorCodes.SchemaInvalid, "Expected generation-profile."));
            if (Major(version) != Major(ProfileSchemaVersions.GenerationProfile))
                result.Issues.Add(Issue("schema.version", ProfileErrorCodes.SchemaUnsupported, "Unsupported schema major: " + version));

            var identity = root.Get("profile");
            var prompt = root.Get("prompt");
            var negative = root.Get("negative_prompt");
            var defaults = root.Get("generation_defaults");
            var unity = root.Get("unity");
            result.Profile = new GenerationProfile
            {
                SchemaName = name,
                SchemaVersion = version,
                Id = identity.Get("id").AsString(),
                Revision = identity.Get("revision").AsInt(),
                DisplayName = identity.Get("display_name").AsString(),
                Description = identity.Get("description").AsString(),
                AssetType = identity.Get("asset_type").AsString(),
                Builtin = identity.Get("builtin").AsBool(),
                Tags = identity.Get("tags").AsStringList(),
                Prompt = new GenerationPromptReference
                {
                    TemplateId = prompt.Get("template_id").AsString(),
                    TemplateRevision = prompt.Get("template_revision").AsInt(),
                    DefaultModifiers = prompt.Get("default_modifiers").AsStringList()
                },
                NegativePrompt = new GenerationNegativePromptReference
                {
                    ProfileId = negative.Get("profile_id").AsString(),
                    ProfileRevision = negative.Get("profile_revision").AsInt(),
                    AdditionalTerms = negative.Get("additional_terms").AsStringList()
                },
                Defaults = new GenerationDefaults
                {
                    Width = defaults.Get("width").AsInt(),
                    Height = defaults.Get("height").AsInt(),
                    Steps = defaults.Get("steps").AsInt(),
                    GuidanceScale = defaults.Get("guidance_scale").AsFloat(),
                    SeedStrategy = defaults.Get("seed_strategy").AsString(),
                    FixedSeed = defaults.Get("fixed_seed").IsNull ? (long?)null : defaults.Get("fixed_seed").AsLong()
                },
                Unity = new GenerationUnitySettings
                {
                    ImportProfileId = unity.Get("import_profile_id").AsString(),
                    SuggestedOutputDirectory = unity.Get("suggested_output_directory").AsString(),
                    CreateMaterial = unity.Get("create_material").AsBool()
                },
                SourcePath = sourcePath
            };
            result.Issues.AddRange(GenerationProfileValidator.ValidateStructure(result.Profile));
            return result;
        }

        static int Major(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) return -1;
            return int.TryParse(value.Split('.')[0], out var major) ? major : -1;
        }

        static ValidationIssue Issue(string path, string code, string message) =>
            new ValidationIssue { Path = path, Code = code, Message = message };
    }
}
