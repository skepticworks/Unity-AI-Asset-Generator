using NUnit.Framework;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class GenerationProfileMigrationTests
    {
        [Test] public void Migrates09RevisionAndSeedStrategy()
        {
            const string json = "{\"schema\":{\"version\":\"0.9\"},\"profile\":{\"id\":\"x\",\"profile_version\":3,\"display_name\":\"X\",\"asset_type\":\"texture\"},\"prompt\":{\"template_id\":\"t\",\"template_revision\":1},\"negative_prompt\":{\"profile_id\":\"n\",\"profile_revision\":1},\"generation_defaults\":{\"width\":64,\"height\":64,\"steps\":1,\"guidance_scale\":1},\"unity\":{\"import_profile_id\":\"i\",\"suggested_output_directory\":\"Assets/X\"}}";
            var result = GenerationProfileMigrationService.Migrate(JsonNode.Parse(json));
            Assert.IsTrue(result.Migrated);
            Assert.AreEqual(3, result.Profile.Revision);
            Assert.AreEqual("random", result.Profile.Defaults.SeedStrategy);
        }
    }
}
