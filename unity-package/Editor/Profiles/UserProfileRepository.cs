using System;
using System.IO;
using UnityAiAssets.Editor.Api;
using UnityEditor;

namespace UnityAiAssets.Editor.Profiles
{
    public sealed class UserProfileRepository
    {
        public const string DefaultRelativeDirectory = "ProjectSettings/AIAssetGenerator/Profiles";
        readonly string _root;

        public UserProfileRepository(string root = null)
        {
            _root = Path.GetFullPath(root ?? DefaultRelativeDirectory);
        }

        public string Root => _root;

        public GenerationProfile Create(string assetType, string displayName)
        {
            return new GenerationProfile
            {
                Id = Guid.NewGuid().ToString("D"), Revision = 1, Builtin = false,
                DisplayName = displayName, Description = string.Empty, AssetType = assetType
            };
        }

        public GenerationProfile Duplicate(GenerationProfile original)
        {
            if (original == null) throw new ArgumentNullException(nameof(original));
            var copy = GenerationProfileSchema.Parse(JsonNode.Parse(GenerationProfileWriter.Serialize(original))).Profile;
            copy.Id = Guid.NewGuid().ToString("D");
            copy.Revision = 1;
            copy.Builtin = false;
            copy.DisplayName = "Copy of " + original.DisplayName;
            copy.SourcePath = null;
            return copy;
        }

        /// <summary>Increments revision only when material serialized fields changed.</summary>
        public string Save(GenerationProfile profile, bool overwrite = true)
        {
            if (profile == null) throw new ArgumentNullException(nameof(profile));
            if (profile.Builtin) throw new InvalidOperationException(ProfileErrorCodes.ReadOnly);
            var issues = GenerationProfileValidator.ValidateStructure(profile);
            if (issues.Count > 0) throw new InvalidOperationException(string.Join("\n", issues));
            Directory.CreateDirectory(_root);
            var path = Path.Combine(_root, profile.Id + ".json");
            if (File.Exists(path))
            {
                if (!overwrite) throw new IOException(ProfileErrorCodes.OverwriteRefused);
                var existing = GenerationProfileLoader.Load(path).Profile;
                if (existing != null)
                {
                    profile.Revision = existing.Revision;
                    var unchanged = GenerationProfileWriter.Serialize(existing) == GenerationProfileWriter.Serialize(profile);
                    profile.Revision = unchanged ? existing.Revision : existing.Revision + 1;
                }
            }
            else profile.Revision = Math.Max(1, profile.Revision);
            profile.Builtin = false;
            GenerationProfileWriter.WriteAtomic(path, profile);
            profile.SourcePath = path;
            return path;
        }

        public string Rename(GenerationProfile profile, string displayName)
        {
            if (string.IsNullOrWhiteSpace(displayName)) throw new ArgumentException("Display name is required.");
            profile.DisplayName = displayName.Trim();
            return Save(profile);
        }

        public void Delete(GenerationProfile profile)
        {
            if (profile == null || profile.Builtin) throw new InvalidOperationException(ProfileErrorCodes.ReadOnly);
            var path = Path.Combine(_root, profile.Id + ".json");
            if (File.Exists(path)) File.Delete(path);
        }

        public GenerationProfile Import(
            string sourcePath,
            bool overwrite = false,
            System.Collections.Generic.ISet<string> builtinIds = null)
        {
            var result = GenerationProfileLoader.Load(sourcePath);
            if (!result.IsValid) throw new FormatException(string.Join("\n", result.Issues));
            result.Profile.Builtin = false;
            if (builtinIds != null && builtinIds.Contains(result.Profile.Id))
            {
                Directory.CreateDirectory(Path.Combine(_root, "Quarantine"));
                File.Copy(sourcePath, Path.Combine(_root, "Quarantine", Path.GetFileName(sourcePath)), true);
                throw new IOException(ProfileErrorCodes.BuiltinCollision);
            }
            var destination = Path.Combine(_root, result.Profile.Id + ".json");
            if (File.Exists(destination) && !overwrite)
            {
                Directory.CreateDirectory(Path.Combine(_root, "Quarantine"));
                File.Copy(sourcePath, Path.Combine(_root, "Quarantine", Path.GetFileName(sourcePath)), true);
                throw new IOException(ProfileErrorCodes.DuplicateId);
            }
            Save(result.Profile, overwrite);
            return result.Profile;
        }

        public void Export(GenerationProfile profile, string path, bool overwrite = false)
        {
            if (File.Exists(path) && !overwrite) throw new IOException(ProfileErrorCodes.OverwriteRefused);
            GenerationProfileWriter.WriteAtomic(path, profile);
        }

        public void Reveal() { Directory.CreateDirectory(_root); EditorUtility.RevealInFinder(_root); }
    }
}
