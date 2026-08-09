using System;
using UnityAiAssets.Editor.AssetTypes;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Importing;

namespace UnityAiAssets.Editor.Generation
{
    /// <summary>
    /// UI/editor request model (not the wire DTO).
    /// </summary>
    [Serializable]
    public sealed class TextureGenerationRequestModel
    {
        public string AssetType = AssetTypeIds.Texture;
        public string SelectedProfileId = "ps1_environment_texture";
        public string Subject = "rusted industrial wall";
        public string AdditionalPrompt = string.Empty;
        public string AdditionalNegative = string.Empty;
        public string PreviewPrompt = string.Empty;
        public string PreviewNegative = string.Empty;
        public string Prompt = "low-resolution rusted industrial wall texture, PS1 game aesthetic";
        public string NegativePrompt = "text, logo, watermark, photorealistic scene";
        public int Width = 512;
        public int Height = 512;
        public int Steps = 20;
        public float GuidanceScale = 7f;
        public bool UseExplicitSeed;
        public long Seed = 12345;
        public string OutputName = "texture";
        public string DestinationFolder = "Assets/Generated/Textures";
        public TextureImportProfileKind ImportProfile = TextureImportProfileKind.Ps1Pixel;
        public string ImportProfileId = UnityImportProfileIds.Ps1EnvironmentTexture;
        public bool CreateMaterial;
        public string TransparencyStrategy = "none";
        public int AlphaThreshold = 16;
        public int AlphaFeather;
        public bool RemoveNearTransparent = true;
        public bool ZeroRgbWhenTransparent = true;
        public float PixelsPerUnit = 100f;
        public string PivotMode = "center";
        public float CustomPivotX = .5f;
        public float CustomPivotY = .5f;
        public string AtlasHint;
        public string MaterialDestinationFolder = "Assets/Generated/Materials";
        public string ShaderName = "Universal Render Pipeline/Lit";
    }
}
