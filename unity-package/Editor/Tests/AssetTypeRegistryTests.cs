using NUnit.Framework;
using UnityAiAssets.Editor.AssetTypes;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class AssetTypeRegistryTests
    {
        [Test] public void LoadsBuiltinCatalog()
        {
            var registry = new AssetTypeRegistry();
            Assert.AreEqual("ps1_environment_texture", registry.Get(AssetTypeIds.Texture).DefaultGenerationProfileId);
            Assert.AreEqual(4, registry.GetAll().Count);
        }
    }
}
