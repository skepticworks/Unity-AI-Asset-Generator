using System;
using System.Collections.Generic;
using UnityEngine;

namespace UnityAiAssets.Editor.Tileable
{
    /// <summary>
    /// Optional median-cut style palette reduction preserving alpha.
    /// </summary>
    public static class PaletteReduction
    {
        public static Color32[] Reduce(Color32[] source, int width, int height, int colorCount)
        {
            if (source == null) throw new ArgumentNullException(nameof(source));
            if (source.Length != width * height) throw new ArgumentException("Pixel buffer size mismatch.");
            colorCount = Mathf.Clamp(colorCount, SeamThresholds.MinPaletteColorCount, SeamThresholds.MaxPaletteColorCount);

            var opaque = new List<Color32>();
            for (var i = 0; i < source.Length; i++)
            {
                if (source[i].a > 0) opaque.Add(new Color32(source[i].r, source[i].g, source[i].b, 255));
            }

            if (opaque.Count == 0)
                return (Color32[])source.Clone();

            var palette = BuildPalette(opaque, colorCount);
            var result = new Color32[source.Length];
            for (var i = 0; i < source.Length; i++)
            {
                var px = source[i];
                if (px.a == 0)
                {
                    result[i] = new Color32(0, 0, 0, 0);
                    continue;
                }

                var nearest = Nearest(palette, px);
                result[i] = new Color32(nearest.r, nearest.g, nearest.b, px.a);
            }

            return result;
        }

        static List<Color32> BuildPalette(List<Color32> colors, int colorCount)
        {
            // Simple uniform bucket quantization for deterministic Editor use.
            var buckets = new Dictionary<int, ColorAccum>();
            var step = Mathf.Max(1, 256 / Mathf.Max(2, (int)Mathf.Ceil(Mathf.Pow(colorCount, 1f / 3f))));
            foreach (var c in colors)
            {
                var key = ((c.r / step) << 16) | ((c.g / step) << 8) | (c.b / step);
                if (!buckets.TryGetValue(key, out var accum))
                    accum = new ColorAccum();
                accum.R += c.r;
                accum.G += c.g;
                accum.B += c.b;
                accum.Count++;
                buckets[key] = accum;
            }

            var list = new List<Color32>();
            foreach (var pair in buckets)
            {
                var a = pair.Value;
                list.Add(new Color32(
                    (byte)(a.R / a.Count),
                    (byte)(a.G / a.Count),
                    (byte)(a.B / a.Count),
                    255));
            }

            list.Sort((a, b) => (a.r + a.g + a.b).CompareTo(b.r + b.g + b.b));
            if (list.Count <= colorCount) return list;
            return list.GetRange(0, colorCount);
        }

        static Color32 Nearest(List<Color32> palette, Color32 color)
        {
            var best = palette[0];
            var bestDist = int.MaxValue;
            for (var i = 0; i < palette.Count; i++)
            {
                var p = palette[i];
                var d = (p.r - color.r) * (p.r - color.r)
                      + (p.g - color.g) * (p.g - color.g)
                      + (p.b - color.b) * (p.b - color.b);
                if (d < bestDist)
                {
                    bestDist = d;
                    best = p;
                }
            }

            return best;
        }

        struct ColorAccum
        {
            public long R;
            public long G;
            public long B;
            public int Count;
        }
    }
}
