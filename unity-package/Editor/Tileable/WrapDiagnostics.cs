using System;
using UnityEngine;

namespace UnityAiAssets.Editor.Tileable
{
    /// <summary>
    /// Wrap discontinuity: cross-boundary gradient vs typical internal adjacent gradient.
    /// Values near 1.0 mean the wrap edge is about as continuous as a normal pixel step.
    /// </summary>
    public sealed class WrapDiscontinuityResult
    {
        public float HorizontalRatio;
        public float VerticalRatio;
        public float InternalMeanGradient;
        public float HorizontalWrapGradient;
        public float VerticalWrapGradient;

        public string FormatReport()
        {
            return
                $"Horizontal wrap discontinuity: {HorizontalRatio:0.00}x normal gradient\n" +
                $"Vertical wrap discontinuity:   {VerticalRatio:0.00}x normal gradient";
        }
    }

    public static class WrapDiagnostics
    {
        public static WrapDiscontinuityResult Analyze(Color32[] pixels, int width, int height)
        {
            if (pixels == null) throw new ArgumentNullException(nameof(pixels));
            if (width < 2 || height < 2) throw new ArgumentException("Texture must be at least 2x2.");
            if (pixels.Length != width * height) throw new ArgumentException("Pixel buffer size mismatch.");

            var internalMean = MeanInternalGradient(pixels, width, height);

            var horizontalWrap = 0f;
            for (var y = 0; y < height; y++)
                horizontalWrap += RgbDistance(pixels[y * width + (width - 1)], pixels[y * width]);
            horizontalWrap /= height;

            var verticalWrap = 0f;
            for (var x = 0; x < width; x++)
                verticalWrap += RgbDistance(pixels[(height - 1) * width + x], pixels[x]);
            verticalWrap /= width;

            var baseline = internalMean > 1e-6f ? internalMean : 1f;
            return new WrapDiscontinuityResult
            {
                HorizontalRatio = horizontalWrap / baseline,
                VerticalRatio = verticalWrap / baseline,
                InternalMeanGradient = internalMean,
                HorizontalWrapGradient = horizontalWrap,
                VerticalWrapGradient = verticalWrap
            };
        }

        static float MeanInternalGradient(Color32[] pixels, int width, int height)
        {
            var total = 0f;
            var count = 0;
            for (var y = 0; y < height; y++)
            {
                var row = y * width;
                for (var x = 0; x < width - 1; x++)
                {
                    total += RgbDistance(pixels[row + x], pixels[row + x + 1]);
                    count++;
                }
            }

            for (var y = 0; y < height - 1; y++)
            {
                for (var x = 0; x < width; x++)
                {
                    total += RgbDistance(pixels[y * width + x], pixels[(y + 1) * width + x]);
                    count++;
                }
            }

            return count == 0 ? 0f : total / count;
        }

        static float RgbDistance(Color32 a, Color32 b)
        {
            return (Mathf.Abs(a.r - b.r) + Mathf.Abs(a.g - b.g) + Mathf.Abs(a.b - b.b)) / 3f;
        }
    }
}
