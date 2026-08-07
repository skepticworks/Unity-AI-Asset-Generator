using System.Collections.Generic;

namespace UnityAiAssets.Editor.Prompting
{
    public sealed class PromptTemplate
    {
        public string Id;
        public int Revision;
        public string DisplayName;
        public string Description;
        public string AssetType;
        public string Pattern;
        public List<string> Placeholders = new List<string>();
        public List<string> RequiredPlaceholders = new List<string>();
    }
}
