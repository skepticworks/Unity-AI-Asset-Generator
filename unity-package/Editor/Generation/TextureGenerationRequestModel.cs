using System;
using UnityAiAssets.Editor.Configuration;

namespace UnityAiAssets.Editor.Generation
{
    /// <summary>
    /// UI/editor request model (not the wire DTO).
    /// </summary>
    [Serializable]
    public sealed class TextureGenerationRequestModel
    {
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
        public bool CreateMaterial;
        public string MaterialDestinationFolder = "Assets/Generated/Materials";
        public string ShaderName = "Universal Render Pipeline/Lit";
    }
}
