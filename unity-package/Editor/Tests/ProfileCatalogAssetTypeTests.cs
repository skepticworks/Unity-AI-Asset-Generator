using NUnit.Framework;
using UnityAiAssets.Editor.AssetTypes;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class ProfileCatalogAssetTypeTests
    {
        [Test] public void LoadsBuiltinCatalog()
        {
            var catalog = new ProfileCatalog();
            Assert.AreEqual(
                "ps1_environment_texture",
                catalog.GetAssetType(AssetTypeIds.Texture).DefaultGenerationProfileId);
            Assert.AreEqual(4, catalog.GetAssetTypes().Count);
        }
    }
}
