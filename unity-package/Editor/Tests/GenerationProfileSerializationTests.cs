using NUnit.Framework;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class GenerationProfileSerializationTests
    {
        [Test] public void RoundTripsSnakeCaseProfile()
        {
            var profile = new GenerationProfile
            {
                Id = "x", DisplayName = "X", AssetType = "texture",
                Prompt = new GenerationPromptReference { TemplateId = "t", TemplateRevision = 1 },
                NegativePrompt = new GenerationNegativePromptReference { ProfileId = "n", ProfileRevision = 1 },
                Defaults = new GenerationDefaults { Width = 64, Height = 64, Steps = 1, GuidanceScale = 1, SeedStrategy = "random" },
                Unity = new GenerationUnitySettings { ImportProfileId = "i", SuggestedOutputDirectory = "Assets/X" }
            };
            var json = GenerationProfileWriter.Serialize(profile);
            StringAssert.Contains("\"generation_defaults\"", json);
            Assert.AreEqual("x", GenerationProfileSchema.Parse(JsonNode.Parse(json)).Profile.Id);
        }
    }
}
