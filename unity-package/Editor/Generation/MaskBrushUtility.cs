using UnityEngine;

namespace UnityAiAssets.Editor.Generation
{
    /// <summary>
    /// Editor-side inpainting mask helpers.
    /// Convention: white = regenerate, black = keep. Alpha is ignored.
    /// </summary>
    public static class MaskBrushUtility
    {
        public const string ConventionId = "white_inpaints";
        const byte InpaintThreshold = 8;

        public static Texture2D CreateKeepMask(int width, int height, string name = "InpaintMask")
        {
            var texture = new Texture2D(width, height, TextureFormat.RGBA32, false)
            {
                name = name,
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp
            };
            var pixels = new Color32[width * height];
            var keep = new Color32(0, 0, 0, 255);
            for (var i = 0; i < pixels.Length; i++)
                pixels[i] = keep;
            texture.SetPixels32(pixels);
            texture.Apply(false, false);
            return texture;
        }

        public static Texture2D ToLuminanceMask(Texture2D source, string name = "InpaintMask")
        {
            var readable = source.isReadable ? source : CopyReadable(source);
            try
            {
                var width = readable.width;
                var height = readable.height;
                var src = readable.GetPixels32();
                var dst = new Color32[src.Length];
                for (var i = 0; i < src.Length; i++)
                {
                    var luminance = Luminance(src[i]);
                    dst[i] = new Color32(luminance, luminance, luminance, 255);
                }

                var mask = new Texture2D(width, height, TextureFormat.RGBA32, false)
                {
                    name = name,
                    filterMode = FilterMode.Point,
                    wrapMode = TextureWrapMode.Clamp
                };
                mask.SetPixels32(dst);
                mask.Apply(false, false);
                return mask;
            }
            finally
            {
                if (readable != source)
                    Object.DestroyImmediate(readable);
            }
        }

        public static bool DimensionsMatch(Texture2D a, Texture2D b) =>
            a != null && b != null && a.width == b.width && a.height == b.height;

        public static bool HasInpaintRegion(Texture2D mask)
        {
            if (mask == null)
                return false;
            var readable = mask.isReadable ? mask : CopyReadable(mask);
            try
            {
                var pixels = readable.GetPixels32();
                for (var i = 0; i < pixels.Length; i++)
                {
                    if (Luminance(pixels[i]) >= InpaintThreshold)
                        return true;
                }

                return false;
            }
            finally
            {
                if (readable != mask)
                    Object.DestroyImmediate(readable);
            }
        }

        public static void ClearToKeep(Texture2D mask)
        {
            if (mask == null || !mask.isReadable)
                return;
            var pixels = new Color32[mask.width * mask.height];
            var keep = new Color32(0, 0, 0, 255);
            for (var i = 0; i < pixels.Length; i++)
                pixels[i] = keep;
            mask.SetPixels32(pixels);
            mask.Apply(false, false);
        }

        public static void PaintCircle(Texture2D mask, int centerX, int centerY, int radius, bool inpaint)
        {
            if (mask == null || !mask.isReadable || radius < 1)
                return;

            var width = mask.width;
            var height = mask.height;
            var color = inpaint ? new Color32(255, 255, 255, 255) : new Color32(0, 0, 0, 255);
            var radiusSq = radius * radius;
            var minX = Mathf.Max(0, centerX - radius);
            var maxX = Mathf.Min(width - 1, centerX + radius);
            var minY = Mathf.Max(0, centerY - radius);
            var maxY = Mathf.Min(height - 1, centerY + radius);
            for (var y = minY; y <= maxY; y++)
            {
                for (var x = minX; x <= maxX; x++)
                {
                    var dx = x - centerX;
                    var dy = y - centerY;
                    if (dx * dx + dy * dy <= radiusSq)
                        mask.SetPixel(x, y, color);
                }
            }

            mask.Apply(false, false);
        }

        public static Texture2D BuildOverlay(Texture2D source, Texture2D mask, Color tint, float opacity)
        {
            if (source == null || mask == null || !DimensionsMatch(source, mask))
                return null;

            var sourceReadable = source.isReadable ? source : CopyReadable(source);
            var maskReadable = mask.isReadable ? mask : CopyReadable(mask);
            try
            {
                var width = sourceReadable.width;
                var height = sourceReadable.height;
                var src = sourceReadable.GetPixels32();
                var msk = maskReadable.GetPixels32();
                var dst = new Color32[src.Length];
                var amount = Mathf.Clamp01(opacity);
                for (var i = 0; i < src.Length; i++)
                {
                    var strength = Luminance(msk[i]) / 255f * amount;
                    dst[i] = new Color32(
                        (byte)Mathf.RoundToInt(Mathf.Lerp(src[i].r, tint.r * 255f, strength)),
                        (byte)Mathf.RoundToInt(Mathf.Lerp(src[i].g, tint.g * 255f, strength)),
                        (byte)Mathf.RoundToInt(Mathf.Lerp(src[i].b, tint.b * 255f, strength)),
                        255);
                }

                var overlay = new Texture2D(width, height, TextureFormat.RGBA32, false)
                {
                    name = "InpaintOverlay",
                    filterMode = FilterMode.Bilinear,
                    wrapMode = TextureWrapMode.Clamp
                };
                overlay.SetPixels32(dst);
                overlay.Apply(false, false);
                return overlay;
            }
            finally
            {
                if (sourceReadable != source)
                    Object.DestroyImmediate(sourceReadable);
                if (maskReadable != mask)
                    Object.DestroyImmediate(maskReadable);
            }
        }

        public static Vector2Int GuiPointToTexturePixel(Rect rect, Vector2 guiPoint, int width, int height)
        {
            var u = Mathf.InverseLerp(rect.xMin, rect.xMax, guiPoint.x);
            var v = Mathf.InverseLerp(rect.yMin, rect.yMax, guiPoint.y);
            var x = Mathf.Clamp(Mathf.FloorToInt(u * width), 0, width - 1);
            // Editor GUI y grows downward; Texture2D y grows upward.
            var y = Mathf.Clamp(Mathf.FloorToInt((1f - v) * height), 0, height - 1);
            return new Vector2Int(x, y);
        }

        static byte Luminance(Color32 color)
        {
            return (byte)Mathf.Clamp(
                Mathf.RoundToInt(0.299f * color.r + 0.587f * color.g + 0.114f * color.b),
                0,
                255);
        }

        static Texture2D CopyReadable(Texture2D texture)
        {
            var rt = RenderTexture.GetTemporary(
                texture.width,
                texture.height,
                0,
                RenderTextureFormat.ARGB32,
                RenderTextureReadWrite.sRGB);
            var previous = RenderTexture.active;
            var readable = new Texture2D(texture.width, texture.height, TextureFormat.RGBA32, false);
            try
            {
                Graphics.Blit(texture, rt);
                RenderTexture.active = rt;
                readable.ReadPixels(new Rect(0, 0, texture.width, texture.height), 0, 0);
                readable.Apply(false, false);
                return readable;
            }
            finally
            {
                RenderTexture.active = previous;
                RenderTexture.ReleaseTemporary(rt);
            }
        }
    }
}
