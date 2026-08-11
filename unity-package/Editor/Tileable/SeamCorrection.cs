using System;
using UnityEngine;

namespace UnityAiAssets.Editor.Tileable
{
    /// <summary>
    /// Soft edge-blend seam correction (legacy offline helper / unit tests only).
    /// Production tileable repair uses local AI inpainting on generate — do not treat
    /// soft-blend as a successful seamless path.
    /// </summary>
    public static class SeamCorrection
    {
        public static Color32[] Correct(
            Color32[] source,
            int width,
            int height,
            int blendWidth = SeamThresholds.DefaultSeamBlendWidth,
            bool correctHorizontal = true,
            bool correctVertical = true)
        {
            if (source == null) throw new ArgumentNullException(nameof(source));
            if (source.Length != width * height) throw new ArgumentException("Pixel buffer size mismatch.");

            var working = (Color32[])source.Clone();
            if (correctHorizontal)
                working = BlendHorizontal(working, width, height, blendWidth);
            if (correctVertical)
                working = BlendVertical(working, width, height, blendWidth);
            return working;
        }

        static int ClampBlend(int value, int size)
        {
            var width = Mathf.Clamp(value, SeamThresholds.MinSeamBlendWidth, SeamThresholds.MaxSeamBlendWidth);
            return Mathf.Max(1, Mathf.Min(width, Mathf.Max(1, size / 2)));
        }

        static Color32 Blend(Color32 a, Color32 b, float t)
        {
            return new Color32(
                (byte)Mathf.RoundToInt(a.r * (1f - t) + b.r * t),
                (byte)Mathf.RoundToInt(a.g * (1f - t) + b.g * t),
                (byte)Mathf.RoundToInt(a.b * (1f - t) + b.b * t),
                (byte)Mathf.RoundToInt(a.a * (1f - t) + b.a * t));
        }

        static Color32[] BlendHorizontal(Color32[] pixels, int width, int height, int blendWidth)
        {
            var strip = ClampBlend(blendWidth, width);
            var source = (Color32[])pixels.Clone();
            var result = (Color32[])pixels.Clone();
            for (var y = 0; y < height; y++)
            {
                for (var i = 0; i < strip; i++)
                {
                    var t = (i + 1f) / (strip + 1f) * 0.5f;
                    var leftIdx = y * width + i;
                    var rightIdx = y * width + (width - 1 - i);
                    result[leftIdx] = Blend(source[leftIdx], source[rightIdx], t);
                    result[rightIdx] = Blend(source[rightIdx], source[leftIdx], t);
                }
            }

            return result;
        }

        static Color32[] BlendVertical(Color32[] pixels, int width, int height, int blendWidth)
        {
            var strip = ClampBlend(blendWidth, height);
            var source = (Color32[])pixels.Clone();
            var result = (Color32[])pixels.Clone();
            for (var x = 0; x < width; x++)
            {
                for (var i = 0; i < strip; i++)
                {
                    var t = (i + 1f) / (strip + 1f) * 0.5f;
                    var topIdx = i * width + x;
                    var bottomIdx = (height - 1 - i) * width + x;
                    result[topIdx] = Blend(source[topIdx], source[bottomIdx], t);
                    result[bottomIdx] = Blend(source[bottomIdx], source[topIdx], t);
                }
            }

            return result;
        }
    }
}
