using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.AssetTypes;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Importing;
using UnityAiAssets.Editor.Prompting;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Profiles
{
    /// <summary>Read-only catalog of all built-in profile contracts.</summary>
    public sealed class ProfileCatalog
    {
        readonly Dictionary<string, AssetTypeDefinition> _assetTypes =
            new Dictionary<string, AssetTypeDefinition>(StringComparer.Ordinal);
        readonly Dictionary<string, PromptTemplate> _templates =
            new Dictionary<string, PromptTemplate>(StringComparer.Ordinal);
        readonly Dictionary<string, NegativePromptProfile> _negatives =
            new Dictionary<string, NegativePromptProfile>(StringComparer.Ordinal);
        readonly Dictionary<string, TextureImportProfile> _imports =
            new Dictionary<string, TextureImportProfile>(StringComparer.Ordinal);

        public ProfileCatalog(string builtinRoot = null)
        {
            BuiltinRoot = builtinRoot ?? ProfilePaths.ResolveBuiltinRoot();
            LoadAssetTypes();
            LoadPromptTemplates();
            LoadNegativeProfiles();
            LoadImportProfiles();
        }

        public string BuiltinRoot { get; }

        public IReadOnlyCollection<AssetTypeDefinition> GetAssetTypes() => _assetTypes.Values;
        public bool TryGetAssetType(string id, out AssetTypeDefinition value) =>
            _assetTypes.TryGetValue(id ?? string.Empty, out value);
        public AssetTypeDefinition GetAssetType(string id) =>
            Get(_assetTypes, id, "asset type");

        public IReadOnlyCollection<PromptTemplate> GetPromptTemplates() => _templates.Values;
        public bool TryGetPromptTemplate(string id, out PromptTemplate value) =>
            _templates.TryGetValue(id ?? string.Empty, out value);
        public PromptTemplate GetPromptTemplate(string id) =>
            Get(_templates, id, "prompt template");

        public IReadOnlyCollection<NegativePromptProfile> GetNegativeProfiles() => _negatives.Values;
        public bool TryGetNegativeProfile(string id, out NegativePromptProfile value) =>
            _negatives.TryGetValue(id ?? string.Empty, out value);
        public NegativePromptProfile GetNegativeProfile(string id) =>
            Get(_negatives, id, "negative prompt profile");

        public IReadOnlyCollection<TextureImportProfile> GetImportProfiles() => _imports.Values;
        public bool TryGetImportProfile(string id, out TextureImportProfile value) =>
            _imports.TryGetValue(id ?? string.Empty, out value);
        public TextureImportProfile GetImportProfile(string id) =>
            Get(_imports, id, "Unity import profile");
        public TextureImportProfile FromLegacyKind(TextureImportProfileKind kind) =>
            GetImportProfile(kind == TextureImportProfileKind.StandardEnvironment
                ? UnityImportProfileIds.StandardEnvironmentTexture
                : UnityImportProfileIds.Ps1EnvironmentTexture);

        void LoadAssetTypes()
        {
            var path = Path.Combine(BuiltinRoot, "asset_types.json");
            foreach (var item in JsonNode.Parse(File.ReadAllText(path)).Get("asset_types").AsArray())
            {
                var value = new AssetTypeDefinition
                {
                    Id = item.Get("id").AsString(),
                    DisplayName = item.Get("display_name").AsString(),
                    Description = item.Get("description").AsString(),
                    DefaultGenerationProfileId = item.Get("default_generation_profile_id").AsString(),
                    DefaultImportProfileId = item.Get("default_import_profile_id").AsString(),
                    SuggestedOutputDirectory = item.Get("suggested_output_directory").AsString()
                };
                if (!AssetTypeIds.IsKnown(value.Id)) throw new FormatException("Unknown asset type id: " + value.Id);
                Add(_assetTypes, value.Id, value, path);
            }
        }

        void LoadPromptTemplates()
        {
            foreach (var path in Directory.GetFiles(Path.Combine(BuiltinRoot, "prompt_templates"), "*.json"))
            {
                var node = JsonNode.Parse(File.ReadAllText(path)).Get("template");
                var value = new PromptTemplate
                {
                    Id = node.Get("id").AsString(),
                    Revision = node.Get("revision").AsInt(),
                    DisplayName = node.Get("display_name").AsString(),
                    Description = node.Get("description").AsString(),
                    AssetType = node.Get("asset_type").AsString(),
                    Pattern = node.Get("pattern").AsString(),
                    Placeholders = node.Get("placeholders").AsStringList(),
                    RequiredPlaceholders = node.Get("required_placeholders").AsStringList()
                };
                Add(_templates, value.Id, value, path);
            }
        }

        void LoadNegativeProfiles()
        {
            foreach (var path in Directory.GetFiles(Path.Combine(BuiltinRoot, "negative_prompts"), "*.json"))
            {
                var node = JsonNode.Parse(File.ReadAllText(path)).Get("profile");
                var value = new NegativePromptProfile
                {
                    Id = node.Get("id").AsString(),
                    Revision = node.Get("revision").AsInt(),
                    DisplayName = node.Get("display_name").AsString(),
                    Description = node.Get("description").AsString(),
                    Tags = node.Get("tags").AsStringList(),
                    Terms = node.Get("terms").AsStringList()
                };
                Add(_negatives, value.Id, value, path);
            }
        }

        void LoadImportProfiles()
        {
            var path = Path.Combine(BuiltinRoot, "import_profiles.json");
            foreach (var node in JsonNode.Parse(File.ReadAllText(path)).Get("import_profiles").AsArray())
            {
                var settings = node.Get("settings");
                var value = new TextureImportProfile
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
                Add(_imports, value.Id, value, path);
            }
        }

        static T Get<T>(Dictionary<string, T> items, string id, string label)
        {
            if (!items.TryGetValue(id ?? string.Empty, out var value))
                throw new KeyNotFoundException("Unknown " + label + ": " + id);
            return value;
        }

        static void Add<T>(Dictionary<string, T> items, string id, T value, string path)
        {
            if (string.IsNullOrWhiteSpace(id) || items.ContainsKey(id))
                throw new FormatException("Invalid or duplicate profile id in " + path);
            items.Add(id, value);
        }

        static T Parse<T>(JsonNode node, string key, T fallback) where T : struct
        {
            var value = node.Get(key).AsString();
            return Enum.TryParse(value, true, out T parsed) ? parsed : fallback;
        }
    }
}
