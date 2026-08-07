using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace UnityAiAssets.Editor.Prompting
{
    public static class PromptTemplateResolver
    {
        static readonly Regex Placeholder = new Regex(@"\{([A-Za-z_][A-Za-z0-9_]*)\}", RegexOptions.Compiled);
        static readonly Regex EmptySegments = new Regex(@"\s*,\s*(?=,|$)", RegexOptions.Compiled);
        static readonly HashSet<string> Known = new HashSet<string>(
            new[] { "subject", "style_modifiers", "asset_type" }, StringComparer.Ordinal);

        public static string Resolve(
            PromptTemplate template, string subject, IEnumerable<string> styleModifiers, string assetType,
            string additionalPrompt = null)
        {
            if (template == null) throw new ArgumentNullException(nameof(template));
            if (string.IsNullOrWhiteSpace(subject))
                throw new ArgumentException("Subject is required and must not be empty.", nameof(subject));

            var allowed = new HashSet<string>(template.Placeholders ?? new List<string>(), StringComparer.Ordinal);
            foreach (Match match in Placeholder.Matches(template.Pattern ?? string.Empty))
                if (!allowed.Contains(match.Groups[1].Value) || !Known.Contains(match.Groups[1].Value))
                    throw new FormatException("Unknown prompt placeholder: {" + match.Groups[1].Value + "}");

            var modifiers = string.Join(", ", (styleModifiers ?? Enumerable.Empty<string>())
                .Where(value => !string.IsNullOrWhiteSpace(value)).Select(value => value.Trim()));
            var prompt = (template.Pattern ?? string.Empty)
                .Replace("{subject}", subject.Trim())
                .Replace("{style_modifiers}", modifiers)
                .Replace("{asset_type}", assetType ?? string.Empty);
            prompt = EmptySegments.Replace(prompt, string.Empty).Trim(' ', ',');
            if (!string.IsNullOrWhiteSpace(additionalPrompt))
                prompt = string.IsNullOrEmpty(prompt) ? additionalPrompt.Trim() : prompt + ", " + additionalPrompt.Trim();
            return prompt;
        }
    }
}
