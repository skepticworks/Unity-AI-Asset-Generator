using System;
using NUnit.Framework;
using UnityAiAssets.Editor.Importing;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class AssetPathUtilityTests
    {
        [Test]
        public void NormalizeAssetPath_AcceptsAssetsRelativePath()
        {
            var path = AssetPathUtility.NormalizeAssetPath(@"Assets\Generated\Textures");
            Assert.AreEqual("Assets/Generated/Textures", path);
        }

        [Test]
        public void NormalizeAssetPath_RejectsNonAssetsRoot()
        {
            Assert.Throws<ArgumentException>(() => AssetPathUtility.NormalizeAssetPath("Generated/Textures"));
        }

        [Test]
        public void NormalizeAssetPath_RejectsTraversal()
        {
            Assert.Throws<ArgumentException>(() => AssetPathUtility.NormalizeAssetPath("Assets/../Secrets"));
        }

        [Test]
        public void SanitizeFileName_RemovesInvalidCharacters()
        {
            var name = AssetPathUtility.SanitizeFileName("rusted wall!!!");
            Assert.AreEqual("rusted_wall", name);
        }

        [Test]
        public void SanitizeFileName_RejectsTraversalSegments()
        {
            Assert.Throws<ArgumentException>(() => AssetPathUtility.SanitizeFileName("../evil"));
        }

        [Test]
        public void CombineAssetPath_JoinsWithForwardSlashes()
        {
            var path = AssetPathUtility.CombineAssetPath("Assets/Generated/Textures", "wall.png");
            Assert.AreEqual("Assets/Generated/Textures/wall.png", path);
        }

        [Test]
        public void IsPng_DetectsSignature()
        {
            var bytes = new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A };
            Assert.IsTrue(AssetPathUtility.IsPng(bytes));
            Assert.IsFalse(AssetPathUtility.IsPng(new byte[] { 1, 2, 3 }));
        }

        [Test]
        public void EnsureUniqueAssetPath_ReturnsOriginalWhenMissing()
        {
            // Uses AssetDatabase; unique missing path should round-trip normalize.
            var path = AssetPathUtility.EnsureUniqueAssetPath(
                "Assets/Generated/Textures/__unity_ai_assets_missing_unique_probe__.png");
            Assert.AreEqual(
                "Assets/Generated/Textures/__unity_ai_assets_missing_unique_probe__.png",
                path);
        }
    }
}
