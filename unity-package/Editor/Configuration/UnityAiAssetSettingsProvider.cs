using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.Configuration
{
    /// <summary>
    /// Exposes AI Asset Generator settings under Edit &gt; Project Settings.
    /// </summary>
    public sealed class UnityAiAssetSettingsProvider : SettingsProvider
    {
        public UnityAiAssetSettingsProvider()
            : base("Project/AI Asset Generator", SettingsScope.Project)
        {
            label = "AI Asset Generator";
        }

        public override void OnGUI(string searchContext)
        {
            var settings = UnityAiAssetSettings.instance;
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Backend", EditorStyles.boldLabel);
            settings.BackendBaseUrl = EditorGUILayout.TextField("Backend Base URL", settings.BackendBaseUrl);
            settings.ApiTimeoutSeconds = EditorGUILayout.IntField("API Timeout (seconds)", settings.ApiTimeoutSeconds);
            EditorGUILayout.HelpBox(
                "Generation waits until the backend finishes. Laptop GPUs often need 120–600+ seconds for 512×512. " +
                "Default timeout is 1800s (30 minutes).",
                MessageType.None);

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Defaults", EditorStyles.boldLabel);
            settings.DefaultTextureDirectory = EditorGUILayout.TextField(
                "Texture Directory",
                settings.DefaultTextureDirectory);
            settings.DefaultMaterialDirectory = EditorGUILayout.TextField(
                "Material Directory",
                settings.DefaultMaterialDirectory);
            settings.DefaultTextureImportProfile = (TextureImportProfileKind)EditorGUILayout.EnumPopup(
                "Texture Import Profile",
                settings.DefaultTextureImportProfile);
            settings.DefaultImportProfileId = EditorGUILayout.TextField(
                "Default Import Profile ID", settings.DefaultImportProfileId);
            settings.DefaultAssetType = EditorGUILayout.TextField("Default Asset Type", settings.DefaultAssetType);
            settings.UserProfileDirectory = EditorGUILayout.TextField(
                "User Profile Directory", settings.UserProfileDirectory);
            settings.ShowPromptPreviewByDefault = EditorGUILayout.Toggle(
                "Show Prompt Preview", settings.ShowPromptPreviewByDefault);
            settings.RefreshCompatibilityOnReconnect = EditorGUILayout.Toggle(
                "Refresh On Reconnect", settings.RefreshCompatibilityOnReconnect);
            settings.CreateMaterialByDefault = EditorGUILayout.Toggle(
                "Create Material By Default",
                settings.CreateMaterialByDefault);
            using (new EditorGUI.DisabledScope(!settings.CreateMaterialByDefault))
            {
                settings.DefaultShaderName = EditorGUILayout.TextField(
                    "Default Shader",
                    settings.DefaultShaderName);
            }

            EditorGUILayout.HelpBox(
                "Do not store Hugging Face tokens or backend secrets here. " +
                "Model storage, offline mode, install, and deletion are configured in " +
                "Tools > AI Asset Generator > Models (and backend env vars).",
                MessageType.Info);

            if (GUI.changed)
            {
                settings.SaveSettings();
            }
        }

        [SettingsProvider]
        public static SettingsProvider CreateProvider() => new UnityAiAssetSettingsProvider();
    }
}
