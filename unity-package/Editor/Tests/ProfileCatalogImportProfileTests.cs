using NUnit.Framework;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Importing;
using UnityAiAssets.Editor.Profiles;
using UnityEditor;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class ProfileCatalogImportProfileTests
    {
        [Test] public void LoadsSpriteSettingsAndMapsLegacyKind()
        {
            var catalog = new ProfileCatalog();
            Assert.AreEqual(TextureImporterType.Sprite, catalog.GetImportProfile(UnityImportProfileIds.Ps1Sprite).TextureType);
            Assert.AreEqual(UnityImportProfileIds.Ps1EnvironmentTexture,
                catalog.FromLegacyKind(TextureImportProfileKind.Ps1Pixel).Id);
        }
    }
}
