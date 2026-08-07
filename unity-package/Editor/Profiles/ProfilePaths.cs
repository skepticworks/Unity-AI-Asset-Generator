using System;
using System.IO;
using UnityEditor.PackageManager;
using UnityEngine;

namespace UnityAiAssets.Editor.Profiles
{
    public static class ProfilePaths
    {
        public static string ResolveBuiltinRoot()
        {
            PackageInfo package = null;
            try { package = PackageInfo.FindForAssembly(typeof(ProfilePaths).Assembly); }
            catch (Exception) { package = null; }
            if (package != null)
            {
                var resolved = Path.Combine(package.resolvedPath, "Editor", "Profiles", "Builtin");
                if (IsRoot(resolved)) return resolved;
            }

            var assemblyLocation = typeof(ProfilePaths).Assembly.Location;
            var roots = new[]
            {
                string.IsNullOrEmpty(assemblyLocation) ? null : Path.GetDirectoryName(assemblyLocation),
                Directory.GetCurrentDirectory(),
                Application.dataPath
            };
            foreach (var root in roots)
            {
                var found = WalkParents(root);
                if (found != null) return found;
            }
            throw new DirectoryNotFoundException("Could not locate Editor/Profiles/Builtin/asset_types.json.");
        }

        static string WalkParents(string start)
        {
            if (string.IsNullOrWhiteSpace(start)) return null;
            var current = new DirectoryInfo(Path.GetFullPath(start));
            for (var depth = 0; current != null && depth < 12; depth++, current = current.Parent)
            {
                var candidates = new[]
                {
                    Path.Combine(current.FullName, "Editor", "Profiles", "Builtin"),
                    Path.Combine(current.FullName, "unity-package", "Editor", "Profiles", "Builtin"),
                    Path.Combine(current.FullName, "Packages", "com.skepticworks.unity-ai-assets", "Editor", "Profiles", "Builtin")
                };
                foreach (var candidate in candidates)
                    if (IsRoot(candidate)) return candidate;
            }
            return null;
        }

        static bool IsRoot(string path) =>
            !string.IsNullOrWhiteSpace(path) && File.Exists(Path.Combine(path, "asset_types.json"));
    }
}
