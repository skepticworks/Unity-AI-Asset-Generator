namespace UnityAiAssets.Editor.Profiles
{
    public sealed class ResolvedGenerationSettings
    {
        public string AssetType;
        public string ConstructedPrompt;
        public string ConstructedNegativePrompt;
        public int Width;
        public int Height;
        public int Steps;
        public float GuidanceScale;
        public long? Seed;
        public string OutputName;
        public string DestinationFolder;
        public string ImportProfileId;
        public bool CreateMaterial;
        public string TransparencyStrategy;
        public int AlphaThreshold;
        public int AlphaFeather;
        public bool RemoveNearTransparent;
        public bool ZeroRgbWhenTransparent;
        public float PixelsPerUnit;
        public string PivotMode;
        public float CustomPivotX;
        public float CustomPivotY;
        public string AtlasHint;
        public bool Tileable;
        public bool ApplySeamCorrection;
        public int SeamBlendWidth = 64;
        public bool PaletteReductionEnabled;
        public int PaletteColorCount = 16;
        public ProfileCompatibility Compatibility;
        public string GenerationProfileId;
        public int GenerationProfileRevision;
        public string ProfileOrigin;
        public string PromptTemplateId;
        public int PromptTemplateRevision;
        public string NegativePromptProfileId;
        public int NegativePromptProfileRevision;
    }
}
