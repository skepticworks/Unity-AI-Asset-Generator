using UnityEngine;

namespace UnityAiAssets.Editor.Metadata
{
    /// <summary>
    /// Editor-friendly provenance for an imported generated texture.
    /// </summary>
    public sealed class GenerationMetadataAsset : ScriptableObject
    {
        public string GenerationId;
        public string CreatedAtUtc;
        public string BackendBaseUrl;
        public string ModelId;
        public string ModelRevision;
        public string Prompt;
        public string NegativePrompt;
        public long Seed;
        public int Width;
        public int Height;
        public int Steps;
        public float GuidanceScale;
        public float BackendElapsedSeconds;
        public string ImportedTextureAssetPath;
        public string ImageRetrievalUrl;
        public string MetadataRetrievalUrl;
        public string PackageVersion;
        public Texture2D ImportedTexture;

        // --- Milestone 3: versioned manifest provenance (relative paths only; no absolute
        // backend filesystem paths are ever stored here) ---
        public string ManifestSchemaVersion;
        public string Operation;
        public string AssetType;
        public string Status;
        public string CompletedAtUtc;
        public string ApplicationName;
        public string ApplicationVersion;
        public int ApiMajor;
        public string ModelFamily;
        public string Device;
        public string Precision;
        public string Scheduler;
        public string OutputSha256;
        public long OutputByteSize;
        public string RequestId;
    }
}
