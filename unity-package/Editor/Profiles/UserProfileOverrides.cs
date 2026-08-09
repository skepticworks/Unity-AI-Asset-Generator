namespace UnityAiAssets.Editor.Profiles
{
    public sealed class UserProfileOverrides
    {
        public string Subject;
        public string AdditionalPrompt;
        public string AdditionalNegative;
        public int? Width;
        public int? Height;
        public int? Steps;
        public float? Guidance;
        public long? Seed;
        public string DestinationFolder;
        public string ImportProfileId;
        public bool? CreateMaterial;
        public string OutputName;
        public string TransparencyStrategy;
        public int? AlphaThreshold;
        public int? AlphaFeather;
        public bool? RemoveNearTransparent;
        public bool? ZeroRgbWhenTransparent;
        public float? PixelsPerUnit;
        public string PivotMode;
        public float? CustomPivotX;
        public float? CustomPivotY;
        public string AtlasHint;
    }
}
