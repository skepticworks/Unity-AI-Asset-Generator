using NUnit.Framework;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class TileableProfileSerializationTests
    {
        [Test]
        public void WriterRoundTrip_PreservesTileableSettings()
        {
            var profile = new GenerationProfile
            {
                SchemaName = ProfileSchemaVersions.GenerationProfileSchemaName,
                SchemaVersion = ProfileSchemaVersions.GenerationProfile,
                Id = "user_tileable",
                Revision = 2,
                DisplayName = "User Tileable",
                Description = "test",
                AssetType = "texture",
                Builtin = false,
                Prompt = new GenerationPromptReference
                {
                    TemplateId = "ps1_tileable_texture",
                    TemplateRevision = 1
                },
                NegativePrompt = new GenerationNegativePromptReference
                {
                    ProfileId = "tileable_texture_negative",
                    ProfileRevision = 1
                },
                Defaults = new GenerationDefaults
                {
                    Width = 256, Height = 256, Steps = 20, GuidanceScale = 7f, SeedStrategy = "random"
                },
                Processing = new GenerationProcessingSettings
                {
                    Tileable = true,
                    ApplySeamCorrection = true,
                    SeamBlendWidth = 12,
                    PaletteReductionEnabled = false,
                    PaletteColorCount = 32
                },
                Unity = new GenerationUnitySettings
                {
                    ImportProfileId = "ps1_tileable_texture",
                    SuggestedOutputDirectory = "Assets/Generated/Textures/Tileable",
                    CreateMaterial = true
                }
            };

            var json = GenerationProfileWriter.Serialize(profile);
            var parsed = GenerationProfileSchema.Parse(UnityAiAssets.Editor.Api.JsonNode.Parse(json));
            Assert.IsTrue(parsed.IsValid, string.Join("; ", parsed.Issues));
            Assert.AreEqual("1.2", parsed.Profile.SchemaVersion);
            Assert.IsTrue(parsed.Profile.Processing.Tileable);
            Assert.IsTrue(parsed.Profile.Processing.ApplySeamCorrection);
            Assert.AreEqual(12, parsed.Profile.Processing.SeamBlendWidth);
            Assert.IsFalse(parsed.Profile.Processing.PaletteReductionEnabled);
            Assert.AreEqual(32, parsed.Profile.Processing.PaletteColorCount);
        }

        [Test]
        public void SchemaParse_DefaultsMissingTileableFieldsSafely()
        {
            const string json =
                "{\"schema\":{\"name\":\"generation-profile\",\"version\":\"1.1\"}," +
                "\"profile\":{\"id\":\"legacy\",\"revision\":1,\"display_name\":\"L\",\"description\":\"d\"," +
                "\"asset_type\":\"texture\",\"builtin\":false,\"tags\":[]}," +
                "\"prompt\":{\"template_id\":\"ps1_environment_texture\",\"template_revision\":1,\"default_modifiers\":[]}," +
                "\"negative_prompt\":{\"profile_id\":\"base_ps1_negative\",\"profile_revision\":1,\"additional_terms\":[]}," +
                "\"generation_defaults\":{\"width\":64,\"height\":64,\"steps\":5,\"guidance_scale\":7,\"seed_strategy\":\"random\",\"fixed_seed\":null}," +
                "\"unity\":{\"import_profile_id\":\"ps1_environment_texture\",\"suggested_output_directory\":\"Assets/X\",\"create_material\":false}}";
            var parsed = GenerationProfileSchema.Parse(UnityAiAssets.Editor.Api.JsonNode.Parse(json));
            Assert.IsNotNull(parsed.Profile);
            Assert.IsFalse(parsed.Profile.Processing.Tileable);
            Assert.IsFalse(parsed.Profile.Processing.ApplySeamCorrection);
            Assert.IsFalse(parsed.Profile.Processing.PaletteReductionEnabled);
            Assert.AreEqual(16, parsed.Profile.Processing.PaletteColorCount);
        }
    }
}
