using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Importing
{
    public sealed class TextureImportResult
    {
        public string AssetPath;
        public Texture2D Texture;
    }

    /// <summary>
    /// Imports a downloaded PNG into Assets with a deterministic TextureImporter profile.
    /// </summary>
    public sealed class GeneratedTextureImporter
    {
        public TextureImportResult ImportPng(
            byte[] pngBytes,
            string destinationFolder,
            string desiredFileNameWithoutExtension,
            TextureImportProfile profile)
        {
            if (!AssetPathUtility.IsPng(pngBytes))
            {
                throw new InvalidOperationException("Downloaded bytes are not a valid PNG.");
            }

            if (profile == null)
            {
                throw new ArgumentNullException(nameof(profile));
            }

            var folder = AssetPathUtility.NormalizeAssetPath(destinationFolder);
            AssetPathUtility.EnsureAssetFolderExists(folder);

            var safeName = AssetPathUtility.SanitizeFileName(desiredFileNameWithoutExtension);
            var desiredPath = AssetPathUtility.CombineAssetPath(folder, safeName + ".png");
            var uniquePath = AssetPathUtility.EnsureUniqueAssetPath(desiredPath);
            var absolutePath = AssetPathUtility.AssetPathToAbsolute(uniquePath);

            var tempRoot = Path.Combine(Path.GetTempPath(), "UnityAiAssets");
            Directory.CreateDirectory(tempRoot);
            var tempFile = Path.Combine(tempRoot, Guid.NewGuid().ToString("N") + ".png");
            try
            {
                File.WriteAllBytes(tempFile, pngBytes);
                if (new FileInfo(tempFile).Length <= 0)
                {
                    throw new InvalidOperationException("Temporary PNG file is empty.");
                }

                File.Copy(tempFile, absolutePath, overwrite: false);
            }
            finally
            {
                if (File.Exists(tempFile))
                {
                    File.Delete(tempFile);
                }
            }

            AssetDatabase.ImportAsset(uniquePath, ImportAssetOptions.ForceUpdate);
            var importer = AssetImporter.GetAtPath(uniquePath) as TextureImporter;
            if (importer == null)
            {
                throw new InvalidOperationException($"TextureImporter missing for '{uniquePath}'.");
            }

            profile.Apply(importer);
            importer.SaveAndReimport();

            var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(uniquePath);
            if (texture == null)
            {
                throw new InvalidOperationException($"Failed to load imported texture at '{uniquePath}'.");
            }

            EditorGUIUtility.PingObject(texture);
            Selection.activeObject = texture;

            return new TextureImportResult
            {
                AssetPath = uniquePath,
                Texture = texture
            };
        }
    }
}
