using NUnit.Framework;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Importing;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class TextureImportProfileTests
    {
        [Test]
        public void Ps1Pixel_HasExpectedDefaults()
        {
            var profile = TextureImportProfile.CreatePs1Pixel();
            Assert.AreEqual("PS1 Pixel Texture", profile.DisplayName);
            Assert.AreEqual(TextureImporterType.Default, profile.TextureType);
            Assert.IsTrue(profile.Srgb);
            Assert.IsFalse(profile.Mipmaps);
            Assert.AreEqual(FilterMode.Point, profile.FilterMode);
            Assert.AreEqual(TextureWrapMode.Repeat, profile.WrapMode);
            Assert.AreEqual(TextureImporterCompression.Uncompressed, profile.Compression);
            Assert.AreEqual(TextureImporterNPOTScale.None, profile.NpotScale);
            Assert.IsFalse(profile.IsReadable);
        }

        [Test]
        public void StandardEnvironment_HasExpectedDefaults()
        {
            var profile = TextureImportProfile.CreateStandardEnvironment();
            Assert.AreEqual("Standard Environment Texture", profile.DisplayName);
            Assert.IsTrue(profile.Mipmaps);
            Assert.AreEqual(FilterMode.Bilinear, profile.FilterMode);
            Assert.AreEqual(TextureImporterCompression.Compressed, profile.Compression);
            Assert.IsFalse(profile.IsReadable);
        }

        [Test]
        public void FromKind_MapsEnumValues()
        {
            Assert.AreEqual(
                "PS1 Pixel Texture",
                TextureImportProfile.FromKind(TextureImportProfileKind.Ps1Pixel).DisplayName);
            Assert.AreEqual(
                "Standard Environment Texture",
                TextureImportProfile.FromKind(TextureImportProfileKind.StandardEnvironment).DisplayName);
        }

        [Test]
        public void Ps1Sprite_HasSingleSpriteAlphaAndBottomCenterDefaults()
        {
            var profile = TextureImportProfile.CreatePs1Sprite();
            Assert.AreEqual(TextureImporterType.Sprite, profile.TextureType);
            Assert.AreEqual(SpriteImportMode.Single, profile.SpriteMode);
            Assert.IsTrue(profile.AlphaIsTransparency);
            Assert.AreEqual(TextureWrapMode.Clamp, profile.WrapMode);
            Assert.AreEqual(FilterMode.Point, profile.FilterMode);
            Assert.AreEqual(100f, profile.PixelsPerUnit);
            Assert.AreEqual("bottom_center", profile.PivotMode);
        }

        [Test]
        public void Ps1Icon_HasCenterPivotDefaults()
        {
            var profile = TextureImportProfile.CreatePs1Icon();
            Assert.AreEqual(TextureImporterType.Sprite, profile.TextureType);
            Assert.AreEqual(SpriteImportMode.Single, profile.SpriteMode);
            Assert.AreEqual("center", profile.PivotMode);
        }
    }
}
