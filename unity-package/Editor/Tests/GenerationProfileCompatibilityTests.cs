using NUnit.Framework;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class GenerationProfileCompatibilityTests
    {
        static CapabilityDocument TextureCapabilities(
            int minWidth = 8,
            int maxWidth = 1024,
            int multiple = 8,
            int minSteps = 1,
            int maxSteps = 150)
        {
            return new CapabilityDocument
            {
                Operations = new OperationsInfo
                {
                    TextToImage = new TextToImageCapabilities
                    {
                        Supported = true,
                        AssetTypes = { "texture" },
                        Dimensions = new DimensionConstraints
                        {
                            MinimumWidth = minWidth,
                            MaximumWidth = maxWidth,
                            MinimumHeight = minWidth,
                            MaximumHeight = maxWidth,
                            WidthMultiple = multiple,
                            HeightMultiple = multiple
                        },
                        Steps = new IntRange { Minimum = minSteps, Maximum = maxSteps },
                        GuidanceScale = new FloatRange { Minimum = 0, Maximum = 30 },
                        Seed = new SeedConstraints { Minimum = 0, Maximum = 1000 },
                        NegativePrompt = new NegativePromptConstraints { Supported = true, MaximumLength = 2000 },
                        Prompt = new PromptConstraints { MaximumLength = 2000 }
                    }
                }
            };
        }

        [Test]
        public void AcceptsCompatibleTextureProfile()
        {
            var profile = new GenerationProfile
            {
                AssetType = "texture",
                Defaults = new GenerationDefaults
                {
                    Width = 512, Height = 512, Steps = 25, GuidanceScale = 7f
                }
            };
            var result = GenerationProfileCompatibilityChecker.Check(profile, TextureCapabilities());
            Assert.AreEqual(ProfileCompatibilityState.Compatible, result.State);
            Assert.IsTrue(result.CanGenerate);
        }

        [Test]
        public void RejectsUnsupportedAssetType()
        {
            var profile = new GenerationProfile
            {
                AssetType = "sprite",
                Defaults = new GenerationDefaults
                {
                    Width = 512, Height = 512, Steps = 10, GuidanceScale = 7
                }
            };
            var result = GenerationProfileCompatibilityChecker.Check(profile, TextureCapabilities());
            CollectionAssert.Contains(result.ReasonCodes, CompatibilityReasonCodes.AssetTypeUnsupported);
            Assert.IsFalse(result.CanGenerate);
        }

        [Test]
        public void RejectsIconAndUiWhenUnsupported()
        {
            var caps = TextureCapabilities();
            foreach (var assetType in new[] { "icon", "ui" })
            {
                var profile = new GenerationProfile
                {
                    AssetType = assetType,
                    Defaults = new GenerationDefaults
                    {
                        Width = 512, Height = 512, Steps = 25, GuidanceScale = 7
                    }
                };
                var result = GenerationProfileCompatibilityChecker.Check(profile, caps);
                CollectionAssert.Contains(result.ReasonCodes, CompatibilityReasonCodes.AssetTypeUnsupported);
            }
        }

        [Test]
        public void ReevaluatesAfterUserOverride()
        {
            var caps = TextureCapabilities(maxWidth: 512);
            var result = GenerationProfileCompatibilityChecker.CheckEffective(
                "texture", 768, 512, 25, 7f, null, caps);
            CollectionAssert.Contains(result.ReasonCodes, CompatibilityReasonCodes.WidthOutOfRange);
            Assert.IsFalse(result.CanGenerate);
        }

        [Test]
        public void RejectsInvalidMultipleWithoutClamping()
        {
            var result = GenerationProfileCompatibilityChecker.CheckEffective(
                "texture", 510, 512, 25, 7f, null, TextureCapabilities());
            CollectionAssert.Contains(result.ReasonCodes, CompatibilityReasonCodes.WidthMultipleInvalid);
        }
    }
}
