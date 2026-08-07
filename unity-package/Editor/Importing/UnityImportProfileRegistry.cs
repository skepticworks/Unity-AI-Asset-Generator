using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Profiles;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Importing
{
    public sealed class UnityImportProfileRegistry
    {
        readonly Dictionary<string, TextureImportProfile> _items =
            new Dictionary<string, TextureImportProfile>(StringComparer.Ordinal);

        public UnityImportProfileRegistry(string builtinRoot = null)
        {
            var path = Path.Combine(builtinRoot ?? ProfilePaths.ResolveBuiltinRoot(), "import_profiles.json");
            var root = JsonNode.Parse(File.ReadAllText(path));
            foreach (var node in root.Get("import_profiles").AsArray())
            {
                var settings = node.Get("settings");
                var profile = new TextureImportProfile
                {
                    Id = node.Get("id").AsString(),
                    DisplayName = node.Get("display_name").AsString(),
                    Description = node.Get("description").AsString(),
                    AssetTypes = node.Get("asset_types").AsStringList().ToArray(),
                    TextureType = Parse(settings, "texture_type", TextureImporterType.Default),
                    Srgb = settings.Get("srgb").AsBool(true),
                    AlphaSource = Parse(settings, "alpha_source", TextureImporterAlphaSource.FromInput),
                    AlphaIsTransparency = settings.Get("alpha_is_transparency").AsBool(),
                    Mipmaps = settings.Get("mipmaps").AsBool(),
                    FilterMode = Parse(settings, "filter_mode", FilterMode.Bilinear),
                    WrapMode = Parse(settings, "wrap_mode", TextureWrapMode.Repeat),
                    Compression = Parse(settings, "compression", TextureImporterCompression.Compressed),
                    NpotScale = Parse(settings, "npot_scale", TextureImporterNPOTScale.ToNearest),
                    IsReadable = settings.Get("is_readable").AsBool(),
                    SpriteMode = Parse(settings, "sprite_mode", SpriteImportMode.Single),
                    PixelsPerUnit = settings.Get("pixels_per_unit").AsFloat(100f),
                    MeshType = Parse(settings, "mesh_type", SpriteMeshType.FullRect)
                };
                if (string.IsNullOrWhiteSpace(profile.Id) || _items.ContainsKey(profile.Id))
                    throw new FormatException("Invalid or duplicate Unity import profile id in " + path);
                _items.Add(profile.Id, profile);
            }
        }

        public IReadOnlyCollection<string> KnownIds => _items.Keys;
        public IReadOnlyCollection<TextureImportProfile> GetAll() => _items.Values;
        public bool TryGet(string id, out TextureImportProfile profile) => _items.TryGetValue(id ?? string.Empty, out profile);
        public TextureImportProfile GetById(string id)
        {
            if (!TryGet(id, out var profile)) throw new KeyNotFoundException("Unknown Unity import profile: " + id);
            return profile;
        }
        public TextureImportProfile FromLegacyKind(TextureImportProfileKind kind) =>
            GetById(kind == TextureImportProfileKind.StandardEnvironment
                ? UnityImportProfileIds.StandardEnvironmentTexture
                : UnityImportProfileIds.Ps1EnvironmentTexture);

        static T Parse<T>(JsonNode node, string key, T fallback) where T : struct
        {
            var value = node.Get(key).AsString();
            return Enum.TryParse(value, true, out T parsed) ? parsed : fallback;
        }
    }
}
