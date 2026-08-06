using System;
using UnityAiAssets.Editor.Importing;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Configuration
{
    public enum TextureImportProfileKind
    {
        Ps1Pixel = 0,
        StandardEnvironment = 1
    }

    /// <summary>
    /// Project-level settings for the AI Asset Generator editor tools.
    /// </summary>
    [FilePath("ProjectSettings/UnityAiAssetSettings.asset", FilePathAttribute.Location.ProjectFolder)]
    public sealed class UnityAiAssetSettings : ScriptableSingleton<UnityAiAssetSettings>
    {
        const string DefaultBackendUrl = "http://127.0.0.1:8000";
        const string DefaultTextureFolder = "Assets/Generated/Textures";
        const string DefaultMaterialFolder = "Assets/Generated/Materials";

        [SerializeField] string backendBaseUrl = DefaultBackendUrl;
        [SerializeField] int apiTimeoutSeconds = 1800;
        [SerializeField] string defaultTextureDirectory = DefaultTextureFolder;
        [SerializeField] string defaultMaterialDirectory = DefaultMaterialFolder;
        [SerializeField] TextureImportProfileKind defaultTextureImportProfile = TextureImportProfileKind.Ps1Pixel;
        [SerializeField] bool createMaterialByDefault;
        [SerializeField] string defaultShaderName = "Universal Render Pipeline/Lit";

        public string BackendBaseUrl
        {
            get => string.IsNullOrWhiteSpace(backendBaseUrl) ? DefaultBackendUrl : backendBaseUrl.Trim().TrimEnd('/');
            set
            {
                backendBaseUrl = string.IsNullOrWhiteSpace(value) ? DefaultBackendUrl : value.Trim().TrimEnd('/');
                Save(true);
            }
        }

        public int ApiTimeoutSeconds
        {
            get => Math.Max(5, apiTimeoutSeconds);
            set
            {
                apiTimeoutSeconds = Math.Max(5, value);
                Save(true);
            }
        }

        public string DefaultTextureDirectory
        {
            get => AssetPathUtility.NormalizeAssetPath(
                string.IsNullOrWhiteSpace(defaultTextureDirectory)
                    ? DefaultTextureFolder
                    : defaultTextureDirectory);
            set
            {
                defaultTextureDirectory = AssetPathUtility.NormalizeAssetPath(value);
                Save(true);
            }
        }

        public string DefaultMaterialDirectory
        {
            get => AssetPathUtility.NormalizeAssetPath(
                string.IsNullOrWhiteSpace(defaultMaterialDirectory)
                    ? DefaultMaterialFolder
                    : defaultMaterialDirectory);
            set
            {
                defaultMaterialDirectory = AssetPathUtility.NormalizeAssetPath(value);
                Save(true);
            }
        }

        public TextureImportProfileKind DefaultTextureImportProfile
        {
            get => defaultTextureImportProfile;
            set
            {
                defaultTextureImportProfile = value;
                Save(true);
            }
        }

        public bool CreateMaterialByDefault
        {
            get => createMaterialByDefault;
            set
            {
                createMaterialByDefault = value;
                Save(true);
            }
        }

        public string DefaultShaderName
        {
            get => string.IsNullOrWhiteSpace(defaultShaderName)
                ? "Universal Render Pipeline/Lit"
                : defaultShaderName.Trim();
            set
            {
                defaultShaderName = string.IsNullOrWhiteSpace(value)
                    ? "Universal Render Pipeline/Lit"
                    : value.Trim();
                Save(true);
            }
        }

        public void SaveSettings() => Save(true);
    }
}
