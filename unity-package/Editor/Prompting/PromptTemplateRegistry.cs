using System;
using System.Collections.Generic;
using System.IO;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Prompting
{
    public sealed class PromptTemplateRegistry
    {
        readonly Dictionary<string, PromptTemplate> _items =
            new Dictionary<string, PromptTemplate>(StringComparer.Ordinal);

        public PromptTemplateRegistry(string builtinRoot = null)
        {
            var directory = Path.Combine(builtinRoot ?? ProfilePaths.ResolveBuiltinRoot(), "prompt_templates");
            foreach (var path in Directory.GetFiles(directory, "*.json"))
            {
                var node = JsonNode.Parse(File.ReadAllText(path)).Get("template");
                var template = new PromptTemplate
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
                if (string.IsNullOrWhiteSpace(template.Id) || _items.ContainsKey(template.Id))
                    throw new FormatException("Invalid or duplicate prompt template id in " + path);
                _items.Add(template.Id, template);
            }
        }

        public IReadOnlyCollection<PromptTemplate> GetAll() => _items.Values;
        public bool TryGet(string id, out PromptTemplate template) => _items.TryGetValue(id ?? string.Empty, out template);
        public PromptTemplate Get(string id)
        {
            if (!TryGet(id, out var value)) throw new KeyNotFoundException("Unknown prompt template: " + id);
            return value;
        }
    }
}
