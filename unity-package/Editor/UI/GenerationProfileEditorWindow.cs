using System;
using System.Linq;
using UnityAiAssets.Editor.AssetTypes;
using UnityAiAssets.Editor.Profiles;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.UI
{
    public sealed class GenerationProfileEditorWindow : EditorWindow
    {
        GenerationProfile _profile;
        UserProfileRepository _repository;
        Vector2 _scroll;

        public static void Open(GenerationProfile profile, UserProfileRepository repository)
        {
            if (profile.Builtin) throw new InvalidOperationException("Built-in profiles must be duplicated before editing.");
            var window = GetWindow<GenerationProfileEditorWindow>();
            window.titleContent = new GUIContent("Edit Profile");
            window._profile = profile;
            window._repository = repository;
            window.Show();
        }

        public static void OpenNew(UserProfileRepository repository)
        {
            var profile = repository.Create(AssetTypeIds.Texture, "New Generation Profile");
            profile.Prompt.TemplateId = "ps1_environment_texture";
            profile.Prompt.TemplateRevision = 1;
            profile.NegativePrompt.ProfileId = "base_ps1_negative";
            profile.NegativePrompt.ProfileRevision = 1;
            profile.Defaults.Width = 512; profile.Defaults.Height = 512; profile.Defaults.Steps = 25;
            profile.Defaults.GuidanceScale = 7f;
            profile.Unity.ImportProfileId = "ps1_environment_texture";
            profile.Unity.SuggestedOutputDirectory = "Assets/Generated/Textures";
            Open(profile, repository);
        }

        void OnGUI()
        {
            if (_profile == null) { EditorGUILayout.HelpBox("No profile selected.", MessageType.Info); return; }
            _scroll = EditorGUILayout.BeginScrollView(_scroll);
            EditorGUILayout.LabelField("Identity", EditorStyles.boldLabel);
            EditorGUILayout.SelectableLabel(_profile.Id, EditorStyles.textField, GUILayout.Height(18));
            _profile.DisplayName = EditorGUILayout.TextField("Display Name", _profile.DisplayName);
            _profile.Description = EditorGUILayout.TextArea(_profile.Description, GUILayout.MinHeight(45));
            _profile.AssetType = EditorGUILayout.TextField("Asset Type", _profile.AssetType);
            var tags = EditorGUILayout.TextField("Tags (comma-separated)", string.Join(", ", _profile.Tags));
            _profile.Tags = tags.Split(',').Select(x => x.Trim()).Where(x => x.Length > 0).ToList();

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Prompt", EditorStyles.boldLabel);
            _profile.Prompt.TemplateId = EditorGUILayout.TextField("Template ID", _profile.Prompt.TemplateId);
            _profile.Prompt.TemplateRevision = EditorGUILayout.IntField("Template Revision", _profile.Prompt.TemplateRevision);
            var modifiers = EditorGUILayout.TextArea(string.Join("\n", _profile.Prompt.DefaultModifiers), GUILayout.MinHeight(40));
            _profile.Prompt.DefaultModifiers = Lines(modifiers);
            _profile.NegativePrompt.ProfileId = EditorGUILayout.TextField("Negative Profile ID", _profile.NegativePrompt.ProfileId);
            _profile.NegativePrompt.ProfileRevision = EditorGUILayout.IntField(
                "Negative Revision", _profile.NegativePrompt.ProfileRevision);
            var terms = EditorGUILayout.TextArea(string.Join("\n", _profile.NegativePrompt.AdditionalTerms), GUILayout.MinHeight(40));
            _profile.NegativePrompt.AdditionalTerms = Lines(terms);

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Generation Defaults", EditorStyles.boldLabel);
            _profile.Defaults.Width = EditorGUILayout.IntField("Width", _profile.Defaults.Width);
            _profile.Defaults.Height = EditorGUILayout.IntField("Height", _profile.Defaults.Height);
            _profile.Defaults.Steps = EditorGUILayout.IntField("Steps", _profile.Defaults.Steps);
            _profile.Defaults.GuidanceScale = EditorGUILayout.FloatField("Guidance", _profile.Defaults.GuidanceScale);
            _profile.Defaults.SeedStrategy = EditorGUILayout.TextField("Seed Strategy", _profile.Defaults.SeedStrategy);
            var fixedSeed = _profile.Defaults.FixedSeed ?? 0;
            fixedSeed = EditorGUILayout.LongField("Fixed Seed", fixedSeed);
            _profile.Defaults.FixedSeed = _profile.Defaults.SeedStrategy == "fixed" ? fixedSeed : (long?)null;

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Unity", EditorStyles.boldLabel);
            _profile.Unity.ImportProfileId = EditorGUILayout.TextField("Import Profile ID", _profile.Unity.ImportProfileId);
            _profile.Unity.SuggestedOutputDirectory = EditorGUILayout.TextField(
                "Output Directory", _profile.Unity.SuggestedOutputDirectory);
            _profile.Unity.CreateMaterial = EditorGUILayout.Toggle("Create Material", _profile.Unity.CreateMaterial);

            var issues = GenerationProfileValidator.ValidateStructure(_profile);
            foreach (var issue in issues) EditorGUILayout.HelpBox(issue.ToString(), MessageType.Error);
            using (new EditorGUI.DisabledScope(issues.Count > 0))
            {
                if (GUILayout.Button("Save Profile", GUILayout.Height(28)))
                {
                    _repository.Save(_profile);
                    EditorUtility.DisplayDialog("Generation Profile", "Profile saved.", "OK");
                }
            }
            EditorGUILayout.EndScrollView();
        }

        static System.Collections.Generic.List<string> Lines(string value) =>
            value.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(x => x.Trim()).Where(x => x.Length > 0).ToList();
    }
}
