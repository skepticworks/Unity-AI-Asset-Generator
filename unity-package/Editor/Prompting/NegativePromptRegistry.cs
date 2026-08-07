using System;
using System.Collections.Generic;
using System.IO;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Prompting
{
    public sealed class NegativePromptRegistry
    {
        readonly Dictionary<string, NegativePromptProfile> _items =
            new Dictionary<string, NegativePromptProfile>(StringComparer.Ordinal);

        public NegativePromptRegistry(string builtinRoot = null)
        {
            var directory = Path.Combine(builtinRoot ?? ProfilePaths.ResolveBuiltinRoot(), "negative_prompts");
            foreach (var path in Directory.GetFiles(directory, "*.json"))
            {
                var node = JsonNode.Parse(File.ReadAllText(path)).Get("profile");
                var profile = new NegativePromptProfile
                {
                    Id = node.Get("id").AsString(),
                    Revision = node.Get("revision").AsInt(),
                    DisplayName = node.Get("display_name").AsString(),
                    Description = node.Get("description").AsString(),
                    Tags = node.Get("tags").AsStringList(),
                    Terms = node.Get("terms").AsStringList()
                };
                if (string.IsNullOrWhiteSpace(profile.Id) || _items.ContainsKey(profile.Id))
                    throw new FormatException("Invalid or duplicate negative prompt profile id in " + path);
                _items.Add(profile.Id, profile);
            }
        }

        public IReadOnlyCollection<NegativePromptProfile> GetAll() => _items.Values;
        public bool TryGet(string id, out NegativePromptProfile profile) => _items.TryGetValue(id ?? string.Empty, out profile);
        public NegativePromptProfile Get(string id)
        {
            if (!TryGet(id, out var value)) throw new KeyNotFoundException("Unknown negative prompt profile: " + id);
            return value;
        }
    }
}
