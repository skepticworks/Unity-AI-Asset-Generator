using System;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Importing
{
    public static class UnityImportProfileIds
    {
        public const string Ps1EnvironmentTexture = "ps1_environment_texture";
        public const string StandardEnvironmentTexture = "standard_environment_texture";
        public const string Ps1Sprite = "ps1_sprite";
        public const string Ps1Icon = "ps1_icon";
        public const string Ps1Ui = "ps1_ui";
    }

    /// <summary>
    /// Controlled TextureImporter settings. Extensible for future sprite profiles.
    /// </summary>
    [Serializable]
    public sealed class TextureImportProfile
    {
        public string Id;
        public string DisplayName;
        public string Description;
        public string[] AssetTypes = Array.Empty<string>();
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
        public SpriteImportMode SpriteMode = SpriteImportMode.Single;
        public float PixelsPerUnit = 100f;
        public SpriteMeshType MeshType = SpriteMeshType.FullRect;

        public static TextureImportProfile CreatePs1Pixel()
        {
            return new TextureImportProfile
            {
                Id = UnityImportProfileIds.Ps1EnvironmentTexture,
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
                Id = UnityImportProfileIds.StandardEnvironmentTexture,
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

        public static TextureImportProfile CreatePs1Sprite() => CreateSprite(
            UnityImportProfileIds.Ps1Sprite, "PS1 Sprite", FilterMode.Point);

        public static TextureImportProfile CreatePs1Icon() => CreateSprite(
            UnityImportProfileIds.Ps1Icon, "PS1 Icon", FilterMode.Point);

        public static TextureImportProfile CreatePs1Ui() => CreateSprite(
            UnityImportProfileIds.Ps1Ui, "PS1 UI", FilterMode.Bilinear);

        static TextureImportProfile CreateSprite(string id, string displayName, FilterMode filterMode)
        {
            return new TextureImportProfile
            {
                Id = id,
                DisplayName = displayName,
                TextureType = TextureImporterType.Sprite,
                Srgb = true,
                AlphaSource = TextureImporterAlphaSource.FromInput,
                AlphaIsTransparency = true,
                Mipmaps = false,
                FilterMode = filterMode,
                WrapMode = TextureWrapMode.Clamp,
                Compression = TextureImporterCompression.Uncompressed,
                NpotScale = TextureImporterNPOTScale.None,
                IsReadable = false,
                SpriteMode = SpriteImportMode.Single,
                PixelsPerUnit = 100f,
                MeshType = SpriteMeshType.FullRect
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
            if (TextureType == TextureImporterType.Sprite)
            {
                importer.spriteImportMode = SpriteMode;
                importer.spritePixelsPerUnit = PixelsPerUnit;
                var settings = new TextureImporterSettings();
                importer.ReadTextureSettings(settings);
                settings.spriteMeshType = MeshType;
                importer.SetTextureSettings(settings);
            }
        }
    }
}
