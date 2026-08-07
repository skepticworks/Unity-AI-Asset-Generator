using System;
using System.Collections.Generic;
using System.IO;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.AssetTypes
{
    public sealed class AssetTypeRegistry
    {
        readonly Dictionary<string, AssetTypeDefinition> _items =
            new Dictionary<string, AssetTypeDefinition>(StringComparer.Ordinal);

        public AssetTypeRegistry(string builtinRoot = null)
        {
            var path = Path.Combine(builtinRoot ?? ProfilePaths.ResolveBuiltinRoot(), "asset_types.json");
            var root = JsonNode.Parse(File.ReadAllText(path));
            foreach (var item in root.Get("asset_types").AsArray())
            {
                var definition = new AssetTypeDefinition
                {
                    Id = item.Get("id").AsString(),
                    DisplayName = item.Get("display_name").AsString(),
                    Description = item.Get("description").AsString(),
                    DefaultGenerationProfileId = item.Get("default_generation_profile_id").AsString(),
                    DefaultImportProfileId = item.Get("default_import_profile_id").AsString(),
                    SuggestedOutputDirectory = item.Get("suggested_output_directory").AsString()
                };
                if (!AssetTypeIds.IsKnown(definition.Id))
                    throw new FormatException("Unknown asset type id: " + definition.Id);
                if (_items.ContainsKey(definition.Id))
                    throw new FormatException("Duplicate asset type id: " + definition.Id);
                _items.Add(definition.Id, definition);
            }
        }

        public IReadOnlyCollection<AssetTypeDefinition> GetAll() => _items.Values;

        public AssetTypeDefinition Get(string id)
        {
            if (!TryGet(id, out var value)) throw new KeyNotFoundException("Unknown asset type: " + id);
            return value;
        }

        public bool TryGet(string id, out AssetTypeDefinition value) => _items.TryGetValue(id ?? string.Empty, out value);
    }
}
