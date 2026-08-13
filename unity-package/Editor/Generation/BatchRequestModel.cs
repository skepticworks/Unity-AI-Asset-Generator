using System;
using System.Collections.Generic;

namespace UnityAiAssets.Editor.Generation
{
    [Serializable]
    public sealed class BatchPromptEntry
    {
        public string Text = string.Empty;
    }

    /// <summary>Editor batch configuration. Shared generation fields live on <see cref="Shared"/>.</summary>
    [Serializable]
    public sealed class BatchRequestModel
    {
        public List<BatchPromptEntry> Prompts = new List<BatchPromptEntry>
        {
            new BatchPromptEntry { Text = "rusted metal plating" }
        };

        public int VariationCount = 1;
        public BatchSeedModeKind SeedMode = BatchSeedModeKind.Random;
        public long Seed = 12345;
        public long SeedStart = 1;
        public long SeedEnd = 4;
        public TextureGenerationRequestModel Shared = new TextureGenerationRequestModel();

        public List<string> PromptTexts()
        {
            var list = new List<string>(Prompts.Count);
            foreach (var entry in Prompts)
                list.Add(entry != null ? entry.Text : string.Empty);
            return list;
        }
    }
}
