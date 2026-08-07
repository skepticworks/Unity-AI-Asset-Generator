using System.Collections.Generic;

namespace UnityAiAssets.Editor.Profiles
{
    public sealed class GenerationDefaults
    {
        public int Width;
        public int Height;
        public int Steps;
        public float GuidanceScale;
        public string SeedStrategy = "random";
        public long? FixedSeed;
    }

    public sealed class GenerationPromptReference
    {
        public string TemplateId;
        public int TemplateRevision;
        public List<string> DefaultModifiers = new List<string>();
    }

    public sealed class GenerationNegativePromptReference
    {
        public string ProfileId;
        public int ProfileRevision;
        public List<string> AdditionalTerms = new List<string>();
    }

    public sealed class GenerationUnitySettings
    {
        public string ImportProfileId;
        public string SuggestedOutputDirectory;
        public bool CreateMaterial;
    }

    public sealed class GenerationProfile
    {
        public string SchemaName = ProfileSchemaVersions.GenerationProfileSchemaName;
        public string SchemaVersion = ProfileSchemaVersions.GenerationProfile;
        public string Id;
        public int Revision = 1;
        public string DisplayName;
        public string Description;
        public string AssetType;
        public bool Builtin;
        public List<string> Tags = new List<string>();
        public GenerationPromptReference Prompt = new GenerationPromptReference();
        public GenerationNegativePromptReference NegativePrompt = new GenerationNegativePromptReference();
        public GenerationDefaults Defaults = new GenerationDefaults();
        public GenerationUnitySettings Unity = new GenerationUnitySettings();
        public string SourcePath;
        public string Origin => Builtin ? "builtin" : "user";
    }
}
