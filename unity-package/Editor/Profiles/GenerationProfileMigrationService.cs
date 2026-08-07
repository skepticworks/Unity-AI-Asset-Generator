using System;
using System.Collections.Generic;
using System.IO;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Profiles
{
    public sealed class MigrationResult
    {
        public bool Migrated;
        public string FromVersion;
        public string ToVersion;
        public GenerationProfile Profile;
        public List<ValidationIssue> Issues = new List<ValidationIssue>();
    }

    public static class GenerationProfileMigrationService
    {
        public static MigrationResult Migrate(JsonNode root)
        {
            var version = root.Get("schema").Get("version").AsString();
            if (version != "0.9")
            {
                var parsed = GenerationProfileSchema.Parse(root);
                return new MigrationResult
                {
                    Migrated = false, FromVersion = version, ToVersion = version,
                    Profile = parsed.Profile, Issues = parsed.Issues
                };
            }

            var profileNode = root.Get("profile");
            var defaults = root.Get("generation_defaults");
            var migrated = new GenerationProfile
            {
                SchemaName = ProfileSchemaVersions.GenerationProfileSchemaName,
                SchemaVersion = ProfileSchemaVersions.GenerationProfile,
                Id = profileNode.Get("id").AsString(),
                Revision = profileNode.Get("profile_version").AsInt(1),
                DisplayName = profileNode.Get("display_name").AsString(),
                Description = profileNode.Get("description").AsString(),
                AssetType = profileNode.Get("asset_type").AsString(),
                Builtin = false,
                Tags = profileNode.Get("tags").AsStringList(),
                Prompt = new GenerationPromptReference
                {
                    TemplateId = root.Get("prompt").Get("template_id").AsString(),
                    TemplateRevision = root.Get("prompt").Get("template_revision").AsInt(1),
                    DefaultModifiers = root.Get("prompt").Get("default_modifiers").AsStringList()
                },
                NegativePrompt = new GenerationNegativePromptReference
                {
                    ProfileId = root.Get("negative_prompt").Get("profile_id").AsString(),
                    ProfileRevision = root.Get("negative_prompt").Get("profile_revision").AsInt(1),
                    AdditionalTerms = root.Get("negative_prompt").Get("additional_terms").AsStringList()
                },
                Defaults = new GenerationDefaults
                {
                    Width = defaults.Get("width").AsInt(), Height = defaults.Get("height").AsInt(),
                    Steps = defaults.Get("steps").AsInt(), GuidanceScale = defaults.Get("guidance_scale").AsFloat(),
                    SeedStrategy = "random", FixedSeed = null
                },
                Unity = new GenerationUnitySettings
                {
                    ImportProfileId = root.Get("unity").Get("import_profile_id").AsString(),
                    SuggestedOutputDirectory = root.Get("unity").Get("suggested_output_directory").AsString(),
                    CreateMaterial = root.Get("unity").Get("create_material").AsBool()
                }
            };
            return new MigrationResult
            {
                Migrated = true, FromVersion = "0.9", ToVersion = "1.0", Profile = migrated,
                Issues = GenerationProfileValidator.ValidateStructure(migrated)
            };
        }

        public static MigrationResult MigrateAndPersist(string path)
        {
            var result = Migrate(JsonNode.Parse(File.ReadAllText(path)));
            if (result.Migrated && result.Issues.Count == 0)
            {
                File.Copy(path, path + ".bak", true);
                GenerationProfileWriter.WriteAtomic(path, result.Profile);
            }
            return result;
        }
    }
}
