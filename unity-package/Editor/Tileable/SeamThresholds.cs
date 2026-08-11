namespace UnityAiAssets.Editor.Tileable
{
    /// <summary>
    /// Central thresholds for tileable offset, AI seam mask width, and diagnostics.
    /// </summary>
    public static class SeamThresholds
    {
        public const float ExcellentMax = 0.05f;
        public const float AcceptableMax = 0.15f;
        public const float RgbNormalizer = 255f;
        public const float EdgePercentile = 95f;

        public const int TileableTargetSize = 512;
        public const int CircularOffsetPx = 256;
        public const int ProtectedBorderPx = 4;

        /// <summary>Center-cross mask width for AI seam repair (not soft-blend).</summary>
        public const int DefaultSeamWidth = 64;
        public const int MinSeamWidth = 8;
        public const int MaxSeamWidth = 128;

        /// <summary>Legacy soft-blend width caps (editor unit tests / offline helpers only).</summary>
        public const int DefaultSeamBlendWidth = 8;
        public const int MinSeamBlendWidth = 1;
        public const int MaxSeamBlendWidth = 64;

        public const int DefaultPaletteColorCount = 16;
        public const int MinPaletteColorCount = 2;
        public const int MaxPaletteColorCount = 256;
        public const float OffsetPreviewFraction = 0.5f;
        public const int DefaultTilePreviewRepeat = 3;
    }
}
