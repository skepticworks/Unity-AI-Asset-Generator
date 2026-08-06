using System;
using System.IO;
using System.Text.RegularExpressions;
using UnityEngine;

namespace UnityAiAssets.Editor.Importing
{
    /// <summary>
    /// Validates and normalizes Unity asset paths and filenames.
    /// </summary>
    public static class AssetPathUtility
    {
        static readonly Regex InvalidFileChars = new Regex(@"[^\w\-.]+", RegexOptions.Compiled);
        static readonly Regex MultiUnderscore = new Regex(@"_+", RegexOptions.Compiled);

        public static string NormalizeAssetPath(string assetPath)
        {
            if (string.IsNullOrWhiteSpace(assetPath))
            {
                throw new ArgumentException("Asset path is required.", nameof(assetPath));
            }

            var normalized = assetPath.Replace('\\', '/').Trim();
            while (normalized.Contains("//"))
            {
                normalized = normalized.Replace("//", "/");
            }

            normalized = normalized.TrimEnd('/');
            if (!normalized.StartsWith("Assets/", StringComparison.Ordinal) &&
                !string.Equals(normalized, "Assets", StringComparison.Ordinal))
            {
                throw new ArgumentException(
                    "Unity asset paths must begin with 'Assets/'.",
                    nameof(assetPath));
            }

            if (normalized.Contains(".."))
            {
                throw new ArgumentException(
                    "Asset paths must not contain '..'.",
                    nameof(assetPath));
            }

            return normalized;
        }

        public static void EnsureAssetFolderExists(string assetFolderPath)
        {
            var folder = NormalizeAssetPath(assetFolderPath);
            if (string.Equals(folder, "Assets", StringComparison.Ordinal))
            {
                return;
            }

            if (AssetDatabaseFolderExists(folder))
            {
                return;
            }

            var parts = folder.Split('/');
            var current = parts[0];
            for (var i = 1; i < parts.Length; i++)
            {
                var next = current + "/" + parts[i];
                if (!AssetDatabaseFolderExists(next))
                {
                    UnityEditor.AssetDatabase.CreateFolder(current, parts[i]);
                }

                current = next;
            }
        }

        static bool AssetDatabaseFolderExists(string assetFolderPath)
        {
            return UnityEditor.AssetDatabase.IsValidFolder(assetFolderPath);
        }

        public static string SanitizeFileName(string rawName, string fallback = "texture")
        {
            if (string.IsNullOrWhiteSpace(rawName))
            {
                return fallback;
            }

            var trimmed = rawName.Trim();
            if (trimmed.IndexOf("..", StringComparison.Ordinal) >= 0)
            {
                throw new ArgumentException("Filename must not contain '..'.", nameof(rawName));
            }

            if (trimmed.IndexOf('/') >= 0 || trimmed.IndexOf('\\') >= 0)
            {
                throw new ArgumentException(
                    "Filename must not contain path separators.",
                    nameof(rawName));
            }

            var name = InvalidFileChars.Replace(trimmed, "_");
            name = MultiUnderscore.Replace(name, "_").Trim('_', '.', '-');
            if (string.IsNullOrWhiteSpace(name))
            {
                return fallback;
            }

            if (name.Length > 64)
            {
                name = name.Substring(0, 64).TrimEnd('_', '.', '-');
            }

            return name;
        }

        public static string EnsureUniqueAssetPath(string desiredAssetPath)
        {
            var path = NormalizeAssetPath(desiredAssetPath);
            if (!UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(path))
            {
                return path;
            }

            var directory = Path.GetDirectoryName(path)?.Replace('\\', '/') ?? "Assets";
            var fileName = Path.GetFileNameWithoutExtension(path);
            var extension = Path.GetExtension(path);
            for (var i = 1; i < 10000; i++)
            {
                var candidate = $"{directory}/{fileName}_{i}{extension}";
                if (!UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(candidate))
                {
                    return candidate;
                }
            }

            throw new InvalidOperationException("Could not resolve a unique asset path.");
        }

        public static string CombineAssetPath(string folder, string fileName)
        {
            var normalizedFolder = NormalizeAssetPath(folder);
            var safeFile = SanitizeFileName(fileName);
            return NormalizeAssetPath($"{normalizedFolder}/{safeFile}");
        }

        public static string AssetPathToAbsolute(string assetPath)
        {
            var normalized = NormalizeAssetPath(assetPath);
            var projectRoot = Path.GetDirectoryName(Application.dataPath);
            if (string.IsNullOrEmpty(projectRoot))
            {
                throw new InvalidOperationException("Unable to resolve Unity project root.");
            }

            var absolute = Path.GetFullPath(Path.Combine(projectRoot, normalized.Replace('/', Path.DirectorySeparatorChar)));
            var dataPath = Path.GetFullPath(Application.dataPath);
            if (!absolute.StartsWith(dataPath, StringComparison.OrdinalIgnoreCase) &&
                !absolute.StartsWith(Path.GetFullPath(projectRoot), StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Resolved path escapes the Unity project.");
            }

            if (!absolute.StartsWith(dataPath, StringComparison.OrdinalIgnoreCase) &&
                !normalized.Equals("Assets", StringComparison.Ordinal))
            {
                // Still under project root (e.g. for temp) — for Assets paths require under dataPath.
                if (normalized.StartsWith("Assets/", StringComparison.Ordinal) &&
                    !absolute.StartsWith(dataPath, StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException("Asset path escaped Assets/.");
                }
            }

            return absolute;
        }

        public static bool IsPng(byte[] bytes)
        {
            return bytes != null &&
                   bytes.Length >= 8 &&
                   bytes[0] == 0x89 &&
                   bytes[1] == 0x50 &&
                   bytes[2] == 0x4E &&
                   bytes[3] == 0x47;
        }
    }
}
