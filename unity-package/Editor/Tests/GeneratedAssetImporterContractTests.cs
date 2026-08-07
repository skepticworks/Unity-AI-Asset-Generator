using System;
using NUnit.Framework;
using UnityAiAssets.Editor.Importing;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class GeneratedAssetImporterContractTests
    {
        [Test]
        public void Ps1ImportProfile_PreservesPointFilteringWithoutMipmaps()
        {
            const string folder = "Assets/GeneratedAssetImporterContractTests";
            try
            {
                var png = Convert.FromBase64String(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAFgAI/1J5ZAAAAAElFTkSuQmCC");
                var result = new GeneratedAssetImporter().ImportPng(
                    png, folder, "ps1_contract", TextureImportProfile.CreatePs1Pixel());
                var importer = AssetImporter.GetAtPath(result.AssetPath) as TextureImporter;
                Assert.IsNotNull(importer);
                Assert.AreEqual(FilterMode.Point, importer.filterMode);
                Assert.IsFalse(importer.mipmapEnabled);
            }
            finally
            {
                AssetDatabase.DeleteAsset(folder);
                AssetDatabase.Refresh();
            }
        }
    }
}
