using NUnit.Framework;
using UnityAiAssets.Editor.Generation;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class GenerationRequestFactoryTests
    {
        [Test]
        public void FromResolved_UsesConstructedValuesAndProvenance()
        {
            var resolved = CreateResolved();
            var dto = GenerationRequestFactory.FromResolved(
                resolved, new TextureGenerationRequestModel { Prompt = "stale prompt" });

            Assert.AreEqual("constructed prompt", dto.prompt);
            Assert.AreEqual("constructed negative", dto.negative_prompt);
            Assert.AreEqual("profile", dto.generation_profile_id);
            Assert.AreEqual(3, dto.generation_profile_revision);
            Assert.AreEqual("user", dto.profile_origin);
            Assert.AreEqual("template", dto.prompt_template_id);
            Assert.AreEqual(2, dto.prompt_template_revision);
            Assert.AreEqual("negative", dto.negative_prompt_profile_id);
            Assert.AreEqual(4, dto.negative_prompt_profile_revision);
            Assert.AreEqual("ps1_environment_texture", dto.unity_import_profile_id);
        }

        [Test]
        public void FromResolved_OmitsSeedWhenResolvedSeedIsRandom()
        {
            var resolved = CreateResolved();
            resolved.Seed = null;
            var dto = GenerationRequestFactory.FromResolved(resolved, new TextureGenerationRequestModel());
            Assert.IsNull(dto.seed);
        }

        static ResolvedGenerationSettings CreateResolved() => new ResolvedGenerationSettings
        {
            ConstructedPrompt = " constructed prompt ",
            ConstructedNegativePrompt = "constructed negative",
            Width = 256,
            Height = 128,
            Steps = 20,
            GuidanceScale = 7f,
            Seed = 42,
            OutputName = "asset",
            AssetType = "texture",
            GenerationProfileId = "profile",
            GenerationProfileRevision = 3,
            ProfileOrigin = "user",
            PromptTemplateId = "template",
            PromptTemplateRevision = 2,
            NegativePromptProfileId = "negative",
            NegativePromptProfileRevision = 4,
            ImportProfileId = "ps1_environment_texture"
        };
    }
}
