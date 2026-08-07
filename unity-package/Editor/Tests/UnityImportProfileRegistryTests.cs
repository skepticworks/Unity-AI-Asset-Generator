using NUnit.Framework;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Importing;
using UnityEditor;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class UnityImportProfileRegistryTests
    {
        [Test] public void LoadsSpriteSettingsAndMapsLegacyKind()
        {
            var registry = new UnityImportProfileRegistry();
            Assert.AreEqual(TextureImporterType.Sprite, registry.GetById(UnityImportProfileIds.Ps1Sprite).TextureType);
            Assert.AreEqual(UnityImportProfileIds.Ps1EnvironmentTexture,
                registry.FromLegacyKind(TextureImportProfileKind.Ps1Pixel).Id);
        }
    }
}
