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
    }
}
