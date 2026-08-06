using System;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Importing
{
    /// <summary>
    /// Controlled TextureImporter settings. Extensible for future sprite profiles.
    /// </summary>
    [Serializable]
    public sealed class TextureImportProfile
    {
        public string DisplayName;
        public TextureImporterType TextureType = TextureImporterType.Default;
        public bool Srgb = true;
        public TextureImporterAlphaSource AlphaSource = TextureImporterAlphaSource.FromInput;
        public bool AlphaIsTransparency;
        public bool Mipmaps;
        public FilterMode FilterMode = FilterMode.Bilinear;
        public TextureWrapMode WrapMode = TextureWrapMode.Repeat;
        public TextureImporterCompression Compression = TextureImporterCompression.Compressed;
        public TextureImporterNPOTScale NpotScale = TextureImporterNPOTScale.ToNearest;
        public bool IsReadable;

        public static TextureImportProfile CreatePs1Pixel()
        {
            return new TextureImportProfile
            {
                DisplayName = "PS1 Pixel Texture",
                TextureType = TextureImporterType.Default,
                Srgb = true,
                AlphaSource = TextureImporterAlphaSource.FromInput,
                AlphaIsTransparency = false,
                Mipmaps = false,
                FilterMode = FilterMode.Point,
                WrapMode = TextureWrapMode.Repeat,
                Compression = TextureImporterCompression.Uncompressed,
                NpotScale = TextureImporterNPOTScale.None,
                IsReadable = false
            };
        }

        public static TextureImportProfile CreateStandardEnvironment()
        {
            return new TextureImportProfile
            {
                DisplayName = "Standard Environment Texture",
                TextureType = TextureImporterType.Default,
                Srgb = true,
                AlphaSource = TextureImporterAlphaSource.FromInput,
                AlphaIsTransparency = false,
                Mipmaps = true,
                FilterMode = FilterMode.Bilinear,
                WrapMode = TextureWrapMode.Repeat,
                Compression = TextureImporterCompression.Compressed,
                NpotScale = TextureImporterNPOTScale.ToNearest,
                IsReadable = false
            };
        }

        public static TextureImportProfile FromKind(Configuration.TextureImportProfileKind kind)
        {
            switch (kind)
            {
                case Configuration.TextureImportProfileKind.Ps1Pixel:
                    return CreatePs1Pixel();
                case Configuration.TextureImportProfileKind.StandardEnvironment:
                    return CreateStandardEnvironment();
                default:
                    return CreatePs1Pixel();
            }
        }

        public void Apply(TextureImporter importer)
        {
            if (importer == null)
            {
                throw new ArgumentNullException(nameof(importer));
            }

            importer.textureType = TextureType;
            importer.sRGBTexture = Srgb;
            importer.alphaSource = AlphaSource;
            importer.alphaIsTransparency = AlphaIsTransparency;
            importer.mipmapEnabled = Mipmaps;
            importer.filterMode = FilterMode;
            importer.wrapMode = WrapMode;
            importer.textureCompression = Compression;
            importer.npotScale = NpotScale;
            importer.isReadable = IsReadable;
        }
    }
}
