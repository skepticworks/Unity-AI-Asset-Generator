using System.IO;
using NUnit.Framework;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class GenerationProfileLoadTests
    {
        [Test] public void LoadsBuiltinProfile()
        {
            var path = Path.Combine(ProfilePaths.ResolveBuiltinRoot(), "generation", "ps1_environment_texture.json");
            var result = GenerationProfileLoader.Load(path);
            Assert.IsTrue(result.IsValid, string.Join("\n", result.Issues));
            Assert.AreEqual("texture", result.Profile.AssetType);
        }
    }
}
