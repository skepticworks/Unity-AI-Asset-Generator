using System;
using System.Collections.Generic;

namespace UnityAiAssets.Editor.Generation
{
    public enum BatchSeedModeKind
    {
        Fixed = 0,
        Random = 1,
        Sequential = 2
    }

    public sealed class BatchExpansionItem
    {
        public int Index;
        public int PromptIndex;
        public int VariationIndex;
        public long Seed;
        public string Prompt;
        public string OutputName;
    }

    public sealed class BatchExpansionPlan
    {
        public readonly List<BatchExpansionItem> Items = new List<BatchExpansionItem>();
        public string SeedMode = "fixed";
        public readonly List<long> BaseSeeds = new List<long>();
        public int VariationCount = 1;
        public readonly List<string> Warnings = new List<string>();

        public int JobCount => Items.Count;

        public List<long> SeedsForPrompt(int promptIndex = 0)
        {
            var seeds = new List<long>();
            foreach (var item in Items)
            {
                if (item.PromptIndex == promptIndex)
                    seeds.Add(item.Seed);
            }

            return seeds;
        }

        public string SeedSummary()
        {
            var seeds = SeedsForPrompt(0);
            if (seeds.Count == 0)
                return "No seeds";
            if (seeds.Count <= 12)
                return string.Join(", ", seeds);
            return seeds[0] + "…" + seeds[seeds.Count - 1] + " (" + seeds.Count + " unique seeds per prompt)";
        }
    }

    /// <summary>
    /// Deterministic prompt × seed × variation expansion. Must match
    /// <c>unity_ai_assets.services.batch_expansion</c>.
    /// </summary>
    public static class BatchExpansion
    {
        public const int DefaultMaxJobs = 32;
        public const int DefaultMaxPrompts = 50;
        public const int DefaultMaxVariations = 16;
        public const int WarnJobCount = 16;

        public static string ToApiValue(BatchSeedModeKind mode)
        {
            switch (mode)
            {
                case BatchSeedModeKind.Fixed: return "fixed";
                case BatchSeedModeKind.Sequential: return "sequential";
                default: return "random";
            }
        }

        public static string BuildOutputName(
            string baseName, int promptIndex, long seed, int variationIndex, int maxLength)
        {
            var stem = string.IsNullOrWhiteSpace(baseName) ? "texture" : baseName.Trim();
            var suffix = "_p" + promptIndex.ToString("00") + "_s" + seed + "_v" + variationIndex.ToString("00");
            if (suffix.Length >= maxLength)
            {
                var start = suffix.Length - maxLength;
                return suffix.Substring(start);
            }

            var room = maxLength - suffix.Length;
            var trimmed = stem.Length <= room ? stem : stem.Substring(0, room);
            trimmed = trimmed.TrimEnd('_', '-', '.');
            if (string.IsNullOrEmpty(trimmed))
                trimmed = "tex";
            return trimmed + suffix;
        }

        public static bool TryExpand(
            IList<string> prompts,
            BatchSeedModeKind seedMode,
            int variationCount,
            long seed,
            long seedStart,
            long seedEnd,
            string outputName,
            out BatchExpansionPlan plan,
            out List<string> errors,
            int maxJobs = DefaultMaxJobs,
            int maxPrompts = DefaultMaxPrompts,
            int maxVariations = DefaultMaxVariations,
            int maxPromptLength = 2000,
            int maxOutputNameLength = 100,
            long minSeed = 0,
            long maxSeed = 4294967295)
        {
            errors = new List<string>();
            plan = new BatchExpansionPlan { VariationCount = variationCount, SeedMode = ToApiValue(seedMode) };
            if (prompts == null || prompts.Count == 0)
            {
                errors.Add("At least one prompt is required.");
                return false;
            }

            if (prompts.Count > maxPrompts)
            {
                errors.Add("A batch may include at most " + maxPrompts + " prompts.");
                return false;
            }

            var normalized = new List<string>();
            for (var i = 0; i < prompts.Count; i++)
            {
                var text = NormalizePrompt(prompts[i]);
                if (string.IsNullOrEmpty(text))
                {
                    errors.Add("Prompt " + (i + 1) + " is empty.");
                    continue;
                }

                if (text.Length > maxPromptLength)
                {
                    errors.Add("Prompt " + (i + 1) + " exceeds the maximum length of " + maxPromptLength + ".");
                    continue;
                }

                normalized.Add(text);
            }

            if (errors.Count > 0)
                return false;

            if (variationCount < 1)
            {
                errors.Add("Variation count must be at least 1.");
                return false;
            }

            if (variationCount > maxVariations)
            {
                errors.Add("Variation count may be at most " + maxVariations + ".");
                return false;
            }

            if (!TryResolveBaseSeeds(
                    seedMode, seed, seedStart, seedEnd, minSeed, maxSeed,
                    plan.BaseSeeds, errors))
                return false;

            var stride = plan.BaseSeeds.Count;
            var jobCount = normalized.Count * stride * variationCount;
            if (jobCount > maxJobs)
            {
                errors.Add(
                    "This batch would create " + jobCount + " jobs, which exceeds the maximum of " +
                    maxJobs + ". Reduce prompts, seed range, or variations.");
                return false;
            }

            var seenPrompts = new HashSet<string>();
            for (var promptIndex = 0; promptIndex < normalized.Count; promptIndex++)
            {
                var prompt = normalized[promptIndex];
                if (!seenPrompts.Add(prompt))
                    plan.Warnings.Add(
                        "Prompt " + (promptIndex + 1) +
                        " duplicates an earlier entry and will reuse the same seed set.");

                var usedSeeds = new HashSet<long>();
                foreach (var baseSeed in plan.BaseSeeds)
                {
                    for (var variationIndex = 0; variationIndex < variationCount; variationIndex++)
                    {
                        var actual = baseSeed + variationIndex * (long)stride;
                        if (actual > maxSeed)
                        {
                            errors.Add(
                                "Expanded seed exceeds the allowed maximum. Reduce the sequential range or variation count.");
                            return false;
                        }

                        if (!usedSeeds.Add(actual))
                        {
                            errors.Add("Sequential seed expansion produced a duplicate seed for the same prompt.");
                            return false;
                        }

                        plan.Items.Add(new BatchExpansionItem
                        {
                            Index = plan.Items.Count,
                            PromptIndex = promptIndex,
                            VariationIndex = variationIndex,
                            Seed = actual,
                            Prompt = prompt,
                            OutputName = BuildOutputName(
                                outputName, promptIndex, actual, variationIndex, maxOutputNameLength)
                        });
                    }
                }
            }

            return true;
        }

        static bool TryResolveBaseSeeds(
            BatchSeedModeKind seedMode,
            long seed,
            long seedStart,
            long seedEnd,
            long minSeed,
            long maxSeed,
            List<long> baseSeeds,
            List<string> errors)
        {
            if (seedMode == BatchSeedModeKind.Sequential)
            {
                if (seedStart < minSeed || seedStart > maxSeed || seedEnd < minSeed || seedEnd > maxSeed)
                {
                    errors.Add("Sequential seed range must stay within " + minSeed + "…" + maxSeed + ".");
                    return false;
                }

                if (seedStart > seedEnd)
                {
                    errors.Add("Seed start must be less than or equal to seed end.");
                    return false;
                }

                for (var value = seedStart; value <= seedEnd; value++)
                    baseSeeds.Add(value);
                return true;
            }

            if (seed < minSeed || seed > maxSeed)
            {
                errors.Add("Seed must be between " + minSeed + " and " + maxSeed + ".");
                return false;
            }

            if (seedMode == BatchSeedModeKind.Fixed || seedMode == BatchSeedModeKind.Random)
            {
                baseSeeds.Add(seed);
                return true;
            }

            errors.Add("Unknown seed mode.");
            return false;
        }

        static string NormalizePrompt(string raw)
        {
            if (string.IsNullOrWhiteSpace(raw))
                return string.Empty;
            return string.Join(" ", raw.Split((char[])null, StringSplitOptions.RemoveEmptyEntries));
        }
    }
}
