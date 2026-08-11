using System;
using System.IO;
using UnityAiAssets.Editor.Importing;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Tileable
{
    /// <summary>
    /// Editor-side tileable workflow: read pixels, analyze, correct, palette, export variants.
    /// Preserves the original imported asset; writes corrected/palette siblings.
    /// </summary>
    public static class TileableTextureWorkflow
    {
        public static bool TryReadPixels(Texture2D texture, out Color32[] pixels, out int width, out int height, out string error)
        {
            pixels = null;
            width = height = 0;
            error = null;
            if (texture == null)
            {
                error = "Texture is null.";
                return false;
            }

            width = texture.width;
            height = texture.height;
            var path = AssetDatabase.GetAssetPath(texture);
            if (string.IsNullOrEmpty(path))
            {
                error = "Texture is not an asset.";
                return false;
            }

            try
            {
                var importer = AssetImporter.GetAtPath(path) as TextureImporter;
                var wasReadable = false;
                if (importer != null)
                {
                    wasReadable = importer.isReadable;
                    if (!wasReadable)
                    {
                        importer.isReadable = true;
                        importer.SaveAndReimport();
                        texture = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
                    }
                }

                pixels = texture.GetPixels32();
                if (importer != null && !wasReadable)
                {
                    importer.isReadable = false;
                    importer.SaveAndReimport();
                }

                return true;
            }
            catch (Exception exception)
            {
                error = exception.Message;
                return false;
            }
        }

        public static Texture2D CreatePreviewTexture(Color32[] pixels, int width, int height, FilterMode filterMode)
        {
            var tex = new Texture2D(width, height, TextureFormat.RGBA32, false)
            {
                filterMode = filterMode,
                wrapMode = TextureWrapMode.Repeat,
                hideFlags = HideFlags.HideAndDontSave
            };
            tex.SetPixels32(pixels);
            tex.Apply(false, false);
            return tex;
        }

        public static string WriteSiblingPng(
            string sourceAssetPath,
            Color32[] pixels,
            int width,
            int height,
            string suffix,
            TextureImportProfile importProfile)
        {
            if (string.IsNullOrWhiteSpace(sourceAssetPath))
                throw new ArgumentException("Source asset path is required.", nameof(sourceAssetPath));

            var directory = Path.GetDirectoryName(sourceAssetPath)?.Replace('\\', '/');
            var baseName = Path.GetFileNameWithoutExtension(sourceAssetPath);
            var desired = AssetPathUtility.CombineAssetPath(directory, baseName + suffix + ".png");
            var unique = AssetPathUtility.EnsureUniqueAssetPath(desired);

            var tex = new Texture2D(width, height, TextureFormat.RGBA32, false);
            tex.SetPixels32(pixels);
            tex.Apply(false, false);
            var bytes = tex.EncodeToPNG();
            UnityEngine.Object.DestroyImmediate(tex);

            var absolute = Path.GetFullPath(unique);
            Directory.CreateDirectory(Path.GetDirectoryName(absolute) ?? ".");
            File.WriteAllBytes(absolute, bytes);
            AssetDatabase.ImportAsset(unique);

            var profile = importProfile ?? TextureImportProfile.CreatePs1Tileable();
            var importer = AssetImporter.GetAtPath(unique) as TextureImporter;
            if (importer != null)
            {
                profile.Apply(importer);
                importer.SaveAndReimport();
            }

            return unique;
        }
    }
}
