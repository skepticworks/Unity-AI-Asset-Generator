using System;
using UnityEngine;

namespace UnityAiAssets.Editor.Tileable
{
    /// <summary>
    /// Circular offset / wrap helpers shared by previews and correction.
    /// </summary>
    public static class OffsetWrap
    {
        public static int WrapCoordinate(int value, int size)
        {
            if (size <= 0) throw new ArgumentOutOfRangeException(nameof(size));
            var wrapped = value % size;
            return wrapped < 0 ? wrapped + size : wrapped;
        }

        public static void OffsetShiftAmounts(int width, int height, out int dx, out int dy,
            float fraction = SeamThresholds.OffsetPreviewFraction)
        {
            if (width <= 0 || height <= 0) throw new ArgumentOutOfRangeException();
            dx = Mathf.RoundToInt(width * fraction) % width;
            dy = Mathf.RoundToInt(height * fraction) % height;
        }

        public static Color32[] CircularShift(Color32[] source, int width, int height, int dx, int dy)
        {
            if (source == null) throw new ArgumentNullException(nameof(source));
            if (source.Length != width * height) throw new ArgumentException("Pixel buffer size mismatch.");
            dx = WrapCoordinate(dx, width);
            dy = WrapCoordinate(dy, height);
            var result = new Color32[source.Length];
            for (var y = 0; y < height; y++)
            {
                for (var x = 0; x < width; x++)
                {
                    var sx = WrapCoordinate(x - dx, width);
                    var sy = WrapCoordinate(y - dy, height);
                    result[y * width + x] = source[sy * width + sx];
                }
            }

            return result;
        }

        public static Color32[] OffsetPreview(Color32[] source, int width, int height)
        {
            OffsetShiftAmounts(width, height, out var dx, out var dy);
            return CircularShift(source, width, height, dx, dy);
        }

        public static Color32[] TiledPreview(Color32[] source, int width, int height,
            int repeats = SeamThresholds.DefaultTilePreviewRepeat)
        {
            if (repeats < 1) throw new ArgumentOutOfRangeException(nameof(repeats));
            var outW = width * repeats;
            var outH = height * repeats;
            var result = new Color32[outW * outH];
            for (var ty = 0; ty < repeats; ty++)
            {
                for (var tx = 0; tx < repeats; tx++)
                {
                    for (var y = 0; y < height; y++)
                    {
                        for (var x = 0; x < width; x++)
                        {
                            result[(ty * height + y) * outW + (tx * width + x)] = source[y * width + x];
                        }
                    }
                }
            }

            return result;
        }
    }
}
