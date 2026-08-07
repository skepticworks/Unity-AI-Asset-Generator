using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityAiAssets.Editor.Importing;
using UnityAiAssets.Editor.Prompting;

namespace UnityAiAssets.Editor.Profiles
{
    public sealed class ProfileLoadError
    {
        public string Path;
        public string Code;
        public string Message;
    }

    public sealed class GenerationProfileRegistry
    {
        readonly Dictionary<string, GenerationProfile> _items =
            new Dictionary<string, GenerationProfile>(StringComparer.Ordinal);

        public List<ProfileLoadError> LoadErrors { get; } = new List<ProfileLoadError>();
        public HashSet<string> ConflictedIds { get; } = new HashSet<string>(StringComparer.Ordinal);
        public string BuiltinRoot { get; }
        public string UserRoot { get; }

        public GenerationProfileRegistry(string builtinRoot = null, string userRoot = null)
        {
            BuiltinRoot = builtinRoot ?? ProfilePaths.ResolveBuiltinRoot();
            UserRoot = userRoot;
            LoadDirectory(Path.Combine(BuiltinRoot, "generation"), true);
            if (!string.IsNullOrWhiteSpace(UserRoot) && Directory.Exists(UserRoot))
                LoadDirectory(UserRoot, false);
            var templates = new PromptTemplateRegistry(BuiltinRoot);
            var negatives = new NegativePromptRegistry(BuiltinRoot);
            var imports = new UnityImportProfileRegistry(BuiltinRoot);
            foreach (var profile in _items.Values.ToArray())
            {
                foreach (var issue in GenerationProfileValidator.ValidateReferences(profile, templates, negatives, imports))
                    LoadErrors.Add(new ProfileLoadError
                    {
                        Path = profile.SourcePath, Code = issue.Code, Message = issue.ToString()
                    });
            }
        }

        public IReadOnlyCollection<GenerationProfile> GetAll() => _items.Values;
        public IEnumerable<GenerationProfile> FilterByAssetType(string assetType) =>
            _items.Values.Where(value => string.Equals(value.AssetType, assetType, StringComparison.Ordinal));
        public bool TryGet(string id, out GenerationProfile profile) => _items.TryGetValue(id ?? string.Empty, out profile);
        public GenerationProfile Get(string id)
        {
            if (!TryGet(id, out var profile)) throw new KeyNotFoundException("Unknown generation profile: " + id);
            return profile;
        }

        void LoadDirectory(string directory, bool builtin)
        {
            if (!Directory.Exists(directory)) return;
            foreach (var path in Directory.GetFiles(directory).Where(GenerationProfileLoader.IsCandidate).OrderBy(x => x))
            {
                var result = GenerationProfileLoader.Load(path);
                if (!result.IsValid)
                {
                    foreach (var issue in result.Issues)
                        LoadErrors.Add(new ProfileLoadError { Path = path, Code = issue.Code, Message = issue.ToString() });
                    continue;
                }
                var profile = result.Profile;
                profile.Builtin = builtin;
                profile.SourcePath = path;
                if (_items.TryGetValue(profile.Id, out var existing))
                {
                    if (existing.Builtin && !builtin)
                    {
                        LoadErrors.Add(new ProfileLoadError
                        {
                            Path = path,
                            Code = ProfileErrorCodes.BuiltinCollision,
                            Message = "User profile id collides with built-in " + existing.SourcePath
                        });
                        continue;
                    }

                    var code = ProfileErrorCodes.Conflict;
                    LoadErrors.Add(new ProfileLoadError
                    {
                        Path = path,
                        Code = code,
                        Message = "Profile id conflicts with " + existing.SourcePath
                    });
                    LoadErrors.Add(new ProfileLoadError
                    {
                        Path = existing.SourcePath,
                        Code = code,
                        Message = "Profile id conflicts with " + path
                    });
                    // Quarantine both conflicted user profiles from selection.
                    _items.Remove(profile.Id);
                    ConflictedIds.Add(profile.Id);
                    continue;
                }
                if (ConflictedIds.Contains(profile.Id))
                {
                    LoadErrors.Add(new ProfileLoadError
                    {
                        Path = path,
                        Code = ProfileErrorCodes.Conflict,
                        Message = "Profile id is already marked conflicted."
                    });
                    continue;
                }
                _items.Add(profile.Id, profile);
            }
        }
    }
}
