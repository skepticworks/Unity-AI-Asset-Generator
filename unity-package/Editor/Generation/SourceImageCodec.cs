using System;
using UnityEngine;

namespace UnityAiAssets.Editor.Generation
{
    /// <summary>
    /// Encodes a Unity texture as PNG bytes for the img2img init/source image.
    /// This is not a reference-conditioning (IP-Adapter) encoder.
    /// </summary>
    public static class SourceImageCodec
    {
        public static bool TryEncodePng(Texture2D texture, out byte[] png, out string error)
        {
            png = null;
            error = null;
            if (texture == null)
            {
                error = "A source image is required for image-to-image generation.";
                return false;
            }

            try
            {
                png = texture.isReadable ? texture.EncodeToPNG() : EncodeUnreadable(texture);
            }
            catch (Exception ex)
            {
                error = "Failed to encode the source image as PNG: " + ex.Message;
                return false;
            }

            if (png == null || png.Length == 0)
            {
                error = "Source image encoding produced an empty PNG.";
                return false;
            }

            return true;
        }

        static byte[] EncodeUnreadable(Texture2D texture)
        {
            var rt = RenderTexture.GetTemporary(
                texture.width,
                texture.height,
                0,
                RenderTextureFormat.ARGB32,
                RenderTextureReadWrite.sRGB);
            var previous = RenderTexture.active;
            Texture2D readable = null;
            try
            {
                Graphics.Blit(texture, rt);
                RenderTexture.active = rt;
                readable = new Texture2D(texture.width, texture.height, TextureFormat.RGBA32, false);
                readable.ReadPixels(new Rect(0, 0, texture.width, texture.height), 0, 0);
                readable.Apply();
                return readable.EncodeToPNG();
            }
            finally
            {
                RenderTexture.active = previous;
                RenderTexture.ReleaseTemporary(rt);
                if (readable != null)
                    UnityEngine.Object.DestroyImmediate(readable);
            }
        }
    }
}
