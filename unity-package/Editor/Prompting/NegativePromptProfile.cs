using System.Collections.Generic;

namespace UnityAiAssets.Editor.Prompting
{
    public sealed class NegativePromptProfile
    {
        public string Id;
        public int Revision;
        public string DisplayName;
        public string Description;
        public List<string> Tags = new List<string>();
        public List<string> Terms = new List<string>();
    }
}
