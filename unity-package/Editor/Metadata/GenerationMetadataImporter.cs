using System;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Importing;
using UnityAiAssets.Editor.Versioning;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Metadata
{
    /// <summary>
    /// Persists generation provenance next to the imported texture.
    /// </summary>
    public sealed class GenerationMetadataImporter
    {
        public const string PackageVersion = ClientCompatibility.PackageVersion;

        /// <summary>
        /// Creates the metadata asset. Prefers the versioned <paramref name="manifest"/>;
        /// falls back to the deprecated flat <paramref name="legacyMetadata"/> shape when no
        /// manifest could be retrieved (older backend, or manifest download failed).
        /// Only ever stores relative resource paths, never absolute backend filesystem paths.
        /// </summary>
        public GenerationMetadataAsset Create(
            Texture2D texture,
            string textureAssetPath,
            string backendBaseUrl,
            TextureGenerationResponseDto generation,
            GenerationManifestDocument manifest,
            BackendMetadataDto legacyMetadata,
            string imageUrl,
            string metadataUrl,
            string requestId)
        {
            if (texture == null)
            {
                throw new ArgumentNullException(nameof(texture));
            }

            var texturePath = AssetPathUtility.NormalizeAssetPath(textureAssetPath);
            var directory = System.IO.Path.GetDirectoryName(texturePath)?.Replace('\\', '/') ?? "Assets";
            var metadataFolder = AssetPathUtility.NormalizeAssetPath(directory + "/Metadata");
            AssetPathUtility.EnsureAssetFolderExists(metadataFolder);

            var baseName = System.IO.Path.GetFileNameWithoutExtension(texturePath);
            var desired = AssetPathUtility.CombineAssetPath(metadataFolder, baseName + ".asset");
            var uniquePath = AssetPathUtility.EnsureUniqueAssetPath(desired);

            var asset = ScriptableObject.CreateInstance<GenerationMetadataAsset>();
            var imageOutput = manifest?.FindOutput("image");

            asset.GenerationId = generation?.generation_id ?? manifest?.Generation?.Id ?? legacyMetadata?.generation_id;
            asset.CreatedAtUtc = manifest?.Generation?.CreatedAtUtc ?? legacyMetadata?.created_at_utc ?? DateTime.UtcNow.ToString("o");
            asset.BackendBaseUrl = backendBaseUrl;
            asset.ModelId = manifest?.Model?.Id ?? legacyMetadata?.model_id;
            asset.ModelRevision = manifest?.Model?.Revision ?? legacyMetadata?.model_revision;
            asset.Prompt = manifest?.Request?.Prompt ?? legacyMetadata?.prompt;
            asset.NegativePrompt = manifest?.Request?.NegativePrompt ?? legacyMetadata?.negative_prompt;
            asset.Seed = generation?.seed ?? manifest?.Request?.Seed ?? legacyMetadata?.seed ?? 0;
            asset.Width = generation?.width ?? manifest?.Request?.Width ?? legacyMetadata?.width ?? 0;
            asset.Height = generation?.height ?? manifest?.Request?.Height ?? legacyMetadata?.height ?? 0;
            asset.Steps = manifest?.Request?.Steps ?? legacyMetadata?.steps ?? 0;
            asset.GuidanceScale = manifest?.Request?.GuidanceScale ?? legacyMetadata?.guidance_scale ?? 0f;
            asset.BackendElapsedSeconds = generation?.elapsed_seconds ?? manifest?.Generation?.ElapsedSeconds ?? legacyMetadata?.elapsed_seconds ?? 0f;
            asset.ImportedTextureAssetPath = texturePath;
            asset.ImageRetrievalUrl = imageUrl;
            asset.MetadataRetrievalUrl = metadataUrl;
            asset.PackageVersion = PackageVersion;
            asset.ImportedTexture = texture;

            asset.ManifestSchemaVersion = manifest?.Schema?.Version;
            asset.Operation = manifest?.Generation?.Operation ?? generation?.operation;
            asset.AssetType = manifest?.Generation?.AssetType ?? generation?.asset_type;
            asset.Status = manifest?.Generation?.Status ?? generation?.status;
            asset.CompletedAtUtc = manifest?.Generation?.CompletedAtUtc;
            asset.ApplicationName = manifest?.Application?.Name;
            asset.ApplicationVersion = manifest?.Application?.Version ?? legacyMetadata?.app_version;
            asset.ApiMajor = manifest?.Application?.ApiMajor ?? 0;
            asset.ModelFamily = manifest?.Model?.Family;
            asset.Device = manifest?.Runtime?.Device ?? legacyMetadata?.device;
            asset.Precision = manifest?.Runtime?.Precision ?? legacyMetadata?.torch_dtype;
            asset.Scheduler = manifest?.Runtime?.Scheduler;
            asset.OutputSha256 = imageOutput?.Sha256;
            asset.OutputByteSize = imageOutput?.ByteSize ?? 0;
            asset.RequestId = requestId;
            asset.GenerationProfileId = manifest?.Profile?.GenerationProfileId;
            asset.GenerationProfileRevision = manifest?.Profile?.GenerationProfileRevision ?? 0;
            asset.ProfileOrigin = manifest?.Profile?.ProfileOrigin;
            asset.PromptTemplateId = manifest?.Profile?.PromptTemplateId;
            asset.PromptTemplateRevision = manifest?.Profile?.PromptTemplateRevision ?? 0;
            asset.NegativePromptProfileId = manifest?.Profile?.NegativePromptProfileId;
            asset.NegativePromptProfileRevision = manifest?.Profile?.NegativePromptProfileRevision ?? 0;
            asset.UnityImportProfileId = manifest?.Profile?.UnityImportProfileId;
            asset.TransparencyStrategy = manifest?.Request?.TransparencyStrategy;
            asset.AlphaThreshold = manifest?.Processing?.AlphaThreshold ?? 0;
            asset.AlphaFeather = manifest?.Processing?.AlphaFeather ?? 0;
            asset.RemoveNearTransparent = manifest?.Processing?.RemoveNearTransparent ?? false;
            asset.ZeroRgbWhenTransparent = manifest?.Processing?.ZeroRgbWhenTransparent ?? false;
            asset.PixelsPerUnit = manifest?.Request?.PixelsPerUnit ?? 0f;
            asset.PivotMode = manifest?.Request?.PivotMode;
            asset.CustomPivotX = manifest?.Request?.CustomPivotX ?? 0f;
            asset.CustomPivotY = manifest?.Request?.CustomPivotY ?? 0f;
            asset.AtlasHint = manifest?.Request?.AtlasHint;
            asset.BackgroundRemovalBackend = manifest?.Processing?.BackgroundRemovalBackend;
            asset.BackgroundRemovalImplementation = manifest?.Processing?.BackgroundRemovalImplementation;
            asset.BackgroundRemovalModel = manifest?.Processing?.BackgroundRemovalModel;
            asset.ProducesNativeAlpha = manifest?.Processing?.ProducesNativeAlpha ?? false;
            asset.DenoisingStrength = manifest?.Request?.DenoisingStrength ?? 0f;
            asset.SourceImageFormat = manifest?.Request?.SourceImage?.Format;
            asset.SourceImageMediaType = manifest?.Request?.SourceImage?.MediaType;
            asset.SourceImageWidth = manifest?.Request?.SourceImage?.Width ?? 0;
            asset.SourceImageHeight = manifest?.Request?.SourceImage?.Height ?? 0;
            asset.SourceImageByteSize = manifest?.Request?.SourceImage?.ByteSize ?? 0;
            asset.SourceImageSha256 = manifest?.Request?.SourceImage?.Sha256;

            AssetDatabase.CreateAsset(asset, uniquePath);
            AssetDatabase.SaveAssets();
            return asset;
        }
    }
}
