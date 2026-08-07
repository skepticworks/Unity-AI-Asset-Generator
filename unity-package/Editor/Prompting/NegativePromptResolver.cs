using System;
using System.Collections.Generic;

namespace UnityAiAssets.Editor.Prompting
{
    public static class NegativePromptResolver
    {
        public static string Resolve(
            NegativePromptProfile profile, IEnumerable<string> additionalTerms, string userNegative, int maximumLength)
        {
            if (profile == null) throw new ArgumentNullException(nameof(profile));
            var ordered = new List<string>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            Add(profile.Terms, ordered, seen);
            Add(additionalTerms, ordered, seen);
            if (!string.IsNullOrWhiteSpace(userNegative))
                Add(userNegative.Split(','), ordered, seen);
            var result = string.Join(", ", ordered);
            if (maximumLength > 0 && result.Length > maximumLength)
                throw new ArgumentException(
                    $"Negative prompt is {result.Length} characters; maximum is {maximumLength}. It was not truncated.");
            return result;
        }

        static void Add(IEnumerable<string> values, List<string> result, HashSet<string> seen)
        {
            if (values == null) return;
            foreach (var raw in values)
            {
                var value = raw?.Trim();
                if (!string.IsNullOrEmpty(value) && seen.Add(value)) result.Add(value);
            }
        }
    }
}
