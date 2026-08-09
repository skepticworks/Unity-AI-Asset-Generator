using NUnit.Framework;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class GenerationProfileResolverTests
    {
        [Test] public void ResolvesBuiltinWithOverrides()
        {
            var registry = new GenerationProfileRegistry();
            var resolver = new GenerationProfileResolver(new ProfileCatalog());
            var result = resolver.Resolve(registry.Get("ps1_environment_texture"),
                new UserProfileOverrides { Subject = "rusted wall", Width = 256 });
            StringAssert.Contains("rusted wall", result.ConstructedPrompt);
            Assert.AreEqual(256, result.Width);
            Assert.AreEqual("ps1_environment_texture", result.GenerationProfileId);
        }

        [Test]
        public void ResolvesSpriteProcessingAndImportFields()
        {
            var registry = new GenerationProfileRegistry();
            var resolver = new GenerationProfileResolver(new ProfileCatalog());
            var result = resolver.Resolve(registry.Get("ps1_character_sprite"),
                new UserProfileOverrides { Subject = "robot", PixelsPerUnit = 64f });
            Assert.AreEqual("background_removal", result.TransparencyStrategy);
            Assert.AreEqual(64f, result.PixelsPerUnit);
            Assert.AreEqual("bottom_center", result.PivotMode);
            Assert.AreEqual("characters", result.AtlasHint);
        }
    }
}
