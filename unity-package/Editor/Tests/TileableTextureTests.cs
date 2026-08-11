using NUnit.Framework;
using UnityAiAssets.Editor.Importing;
using UnityAiAssets.Editor.Tileable;
using UnityEngine;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class TileableTextureTests
    {
        [Test]
        public void CircularShift_WrapsWithoutEmptyBorders()
        {
            var pixels = new Color32[16];
            for (var i = 0; i < 16; i++)
                pixels[i] = new Color32((byte)(i * 10), 0, 100, 255);

            var shifted = OffsetWrap.CircularShift(pixels, 4, 4, 1, 0);
            Assert.AreEqual(pixels[0], shifted[1]);
            Assert.AreEqual(pixels[3], shifted[0]);
            // Source buffer remains unchanged.
            Assert.AreEqual(new Color32(0, 0, 100, 255), pixels[0]);
        }

        [Test]
        public void CircularShift_Exactly256On512()
        {
            var pixels = new Color32[512 * 512];
            for (var y = 0; y < 512; y++)
            for (var x = 0; x < 512; x++)
                pixels[y * 512 + x] = new Color32((byte)(x % 256), (byte)(y % 256), 7, 255);

            var shifted = OffsetWrap.CircularShift(pixels, 512, 512, 256, 256);
            Assert.AreEqual(pixels[0], shifted[256 * 512 + 256]);
            Assert.AreEqual(pixels[255 * 512 + 255], shifted[511 * 512 + 511]);
        }

        [Test]
        public void TiledPreview_Is3x3WithoutGaps()
        {
            var pixels = new Color32[4];
            for (var i = 0; i < 4; i++)
                pixels[i] = new Color32(5, 6, 7, 255);
            var tiled = OffsetWrap.TiledPreview(pixels, 2, 2, 3);
            Assert.AreEqual(36, tiled.Length);
            Assert.AreEqual(pixels[0], tiled[0]);
            Assert.AreEqual(pixels[0], tiled[2 + 2 * 6]); // tile (1,1) origin in 6-wide canvas
        }

        [Test]
        public void WrapDiagnostics_SolidNearOne()
        {
            var pixels = new Color32[64];
            for (var i = 0; i < pixels.Length; i++)
                pixels[i] = new Color32(40, 50, 60, 255);
            pixels[10] = new Color32(41, 50, 60, 255);
            var result = WrapDiagnostics.Analyze(pixels, 8, 8);
            Assert.Less(result.HorizontalRatio, 2f);
            Assert.Less(result.VerticalRatio, 2f);
            StringAssert.Contains("Horizontal wrap discontinuity", result.FormatReport());
        }

        [Test]
        public void SeamAnalysis_SolidTextureHasZeroScores()
        {
            var pixels = new Color32[64];
            for (var i = 0; i < pixels.Length; i++)
                pixels[i] = new Color32(40, 50, 60, 255);

            var result = SeamAnalysis.Analyze(pixels, 8, 8);
            Assert.AreEqual(0f, result.HorizontalScore);
            Assert.AreEqual(0f, result.VerticalScore);
            Assert.AreEqual(0f, result.CombinedScore);
            Assert.AreEqual("excellent", result.QualityLabel);
        }

        [Test]
        public void SeamCorrection_DoesNotMutateSourceBuffer()
        {
            var pixels = new Color32[64];
            for (var y = 0; y < 8; y++)
            for (var x = 0; x < 8; x++)
                pixels[y * 8 + x] = new Color32((byte)(x < 4 ? 10 : 200), 10, 10, 255);

            var clone = (Color32[])pixels.Clone();
            var corrected = SeamCorrection.Correct(pixels, 8, 8, 2);
            CollectionAssert.AreEqual(clone, pixels);
            Assert.AreNotEqual(pixels[0], corrected[0]);
        }

        [Test]
        public void PaletteReduction_PreservesDimensionsAndAlpha()
        {
            var pixels = new Color32[48];
            for (var i = 0; i < pixels.Length; i++)
                pixels[i] = new Color32((byte)(i * 5), 20, 30, (byte)(i < 4 ? 0 : 200));

            var reduced = PaletteReduction.Reduce(pixels, 8, 6, 8);
            Assert.AreEqual(48, reduced.Length);
            Assert.AreEqual(0, reduced[0].a);
            Assert.AreEqual(200, reduced[10].a);
        }

        [Test]
        public void Ps1TileableImportProfile_UsesRepeatWrap()
        {
            var profile = TextureImportProfile.CreatePs1Tileable();
            Assert.AreEqual(UnityImportProfileIds.Ps1TileableTexture, profile.Id);
            Assert.AreEqual(TextureWrapMode.Repeat, profile.WrapMode);
            Assert.AreEqual(FilterMode.Point, profile.FilterMode);
            Assert.IsFalse(profile.Mipmaps);
        }
    }
}
