using System;
using System.Collections.Generic;
using UnityEngine;

namespace UnityAiAssets.Editor.Tileable
{
    public sealed class SeamAnalysisResult
    {
        public float HorizontalMean;
        public float HorizontalMax;
        public float HorizontalPercentile;
        public float HorizontalScore;
        public float VerticalMean;
        public float VerticalMax;
        public float VerticalPercentile;
        public float VerticalScore;
        public float CombinedScore;

        public string QualityLabel
        {
            get
            {
                if (CombinedScore <= SeamThresholds.ExcellentMax) return "excellent";
                if (CombinedScore <= SeamThresholds.AcceptableMax) return "acceptable";
                return "poor";
            }
        }
    }

    /// <summary>
    /// Deterministic left/right and top/bottom edge mismatch diagnostics.
    /// </summary>
    public static class SeamAnalysis
    {
        public static SeamAnalysisResult Analyze(Color32[] pixels, int width, int height)
        {
            if (pixels == null) throw new ArgumentNullException(nameof(pixels));
            if (width < 2 || height < 2) throw new ArgumentException("Texture must be at least 2x2.");
            if (pixels.Length != width * height) throw new ArgumentException("Pixel buffer size mismatch.");

            var horizontal = new List<float>(height);
            for (var y = 0; y < height; y++)
                horizontal.Add(RgbDistance(pixels[y * width], pixels[y * width + (width - 1)]));

            var vertical = new List<float>(width);
            for (var x = 0; x < width; x++)
                vertical.Add(RgbDistance(pixels[x], pixels[(height - 1) * width + x]));

            EdgeStats(horizontal, out var hMean, out var hMax, out var hPct, out var hScore);
            EdgeStats(vertical, out var vMean, out var vMax, out var vPct, out var vScore);

            return new SeamAnalysisResult
            {
                HorizontalMean = hMean,
                HorizontalMax = hMax,
                HorizontalPercentile = hPct,
                HorizontalScore = hScore,
                VerticalMean = vMean,
                VerticalMax = vMax,
                VerticalPercentile = vPct,
                VerticalScore = vScore,
                CombinedScore = (hScore + vScore) * 0.5f
            };
        }

        static float RgbDistance(Color32 a, Color32 b)
        {
            if (a.a < 8 && b.a < 8) return 0f;
            return (Mathf.Abs(a.r - b.r) + Mathf.Abs(a.g - b.g) + Mathf.Abs(a.b - b.b)) / 3f;
        }

        static void EdgeStats(List<float> distances, out float mean, out float max, out float percentile, out float score)
        {
            if (distances.Count == 0)
            {
                mean = max = percentile = score = 0f;
                return;
            }

            var sum = 0f;
            max = 0f;
            for (var i = 0; i < distances.Count; i++)
            {
                sum += distances[i];
                if (distances[i] > max) max = distances[i];
            }

            mean = sum / distances.Count;
            var ordered = new List<float>(distances);
            ordered.Sort();
            percentile = Percentile(ordered, SeamThresholds.EdgePercentile);
            score = Mathf.Min(1f, mean / SeamThresholds.RgbNormalizer);
        }

        static float Percentile(List<float> sorted, float percentile)
        {
            if (sorted.Count == 0) return 0f;
            if (sorted.Count == 1) return sorted[0];
            var rank = (percentile / 100f) * (sorted.Count - 1);
            var low = (int)rank;
            var high = Mathf.Min(low + 1, sorted.Count - 1);
            var frac = rank - low;
            return sorted[low] * (1f - frac) + sorted[high] * frac;
        }
    }
}
