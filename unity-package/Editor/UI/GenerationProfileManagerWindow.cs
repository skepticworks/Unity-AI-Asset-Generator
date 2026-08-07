using System;
using System.Linq;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Profiles;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.UI
{
    public sealed class GenerationProfileManagerWindow : EditorWindow
    {
        GenerationProfileRegistry _registry;
        UserProfileRepository _repository;
        Vector2 _scroll;
        string _selectedId;

        [MenuItem("Tools/AI Asset Generator/Profiles")]
        public static void Open()
        {
            var window = GetWindow<GenerationProfileManagerWindow>();
            window.titleContent = new GUIContent("Generation Profiles");
            window.minSize = new Vector2(700, 400);
            window.Show();
        }

        public static void OpenWithProfile(string id)
        {
            Open();
            var window = GetWindow<GenerationProfileManagerWindow>();
            window._selectedId = id;
        }

        void OnEnable() => Refresh();

        void Refresh()
        {
            _repository = new UserProfileRepository(UnityAiAssetSettings.instance.UserProfileDirectoryAbsolute);
            _registry = new GenerationProfileRegistry(userRoot: _repository.Root);
            Repaint();
        }

        void OnGUI()
        {
            if (_registry == null) Refresh();
            EditorGUILayout.BeginHorizontal(EditorStyles.toolbar);
            if (GUILayout.Button("New", EditorStyles.toolbarButton)) GenerationProfileEditorWindow.OpenNew(_repository);
            if (GUILayout.Button("Duplicate", EditorStyles.toolbarButton)) DuplicateSelected();
            if (GUILayout.Button("Edit", EditorStyles.toolbarButton)) EditSelected();
            if (GUILayout.Button("Rename", EditorStyles.toolbarButton)) RenameSelected();
            if (GUILayout.Button("Delete", EditorStyles.toolbarButton)) DeleteSelected();
            if (GUILayout.Button("Import", EditorStyles.toolbarButton)) ImportProfile();
            if (GUILayout.Button("Export", EditorStyles.toolbarButton)) ExportSelected();
            if (GUILayout.Button("Reveal", EditorStyles.toolbarButton)) _repository.Reveal();
            if (GUILayout.Button("Refresh", EditorStyles.toolbarButton)) Refresh();
            if (GUILayout.Button("Validate", EditorStyles.toolbarButton)) ValidateAll();
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            EditorGUILayout.LabelField("Name", EditorStyles.boldLabel, GUILayout.Width(220));
            EditorGUILayout.LabelField("Asset Type", EditorStyles.boldLabel, GUILayout.Width(90));
            EditorGUILayout.LabelField("Origin", EditorStyles.boldLabel, GUILayout.Width(70));
            EditorGUILayout.LabelField("Schema", EditorStyles.boldLabel, GUILayout.Width(70));
            EditorGUILayout.LabelField("Revision", EditorStyles.boldLabel);
            EditorGUILayout.EndHorizontal();
            _scroll = EditorGUILayout.BeginScrollView(_scroll);
            foreach (var profile in _registry.GetAll().OrderBy(x => x.DisplayName))
            {
                var selected = profile.Id == _selectedId;
                var style = selected ? "SelectionRect" : "Label";
                EditorGUILayout.BeginHorizontal(style);
                if (GUILayout.Button(profile.DisplayName, EditorStyles.label, GUILayout.Width(220))) _selectedId = profile.Id;
                EditorGUILayout.LabelField(profile.AssetType, GUILayout.Width(90));
                EditorGUILayout.LabelField(profile.Origin, GUILayout.Width(70));
                EditorGUILayout.LabelField(profile.SchemaVersion, GUILayout.Width(70));
                EditorGUILayout.LabelField(profile.Revision.ToString());
                EditorGUILayout.EndHorizontal();
            }
            EditorGUILayout.EndScrollView();
            foreach (var error in _registry.LoadErrors)
                EditorGUILayout.HelpBox(error.Code + ": " + error.Message, MessageType.Warning);
        }

        GenerationProfile Selected() => _registry.TryGet(_selectedId, out var profile) ? profile : null;
        void DuplicateSelected()
        {
            var selected = Selected(); if (selected == null) return;
            var copy = _repository.Duplicate(selected); _repository.Save(copy); Refresh(); _selectedId = copy.Id;
        }
        void EditSelected()
        {
            var selected = Selected(); if (selected == null) return;
            if (selected.Builtin) { DuplicateSelected(); selected = Selected(); }
            GenerationProfileEditorWindow.Open(selected, _repository);
        }
        void RenameSelected()
        {
            var selected = Selected(); if (selected == null || selected.Builtin) return;
            GenerationProfileEditorWindow.Open(selected, _repository);
        }
        void DeleteSelected()
        {
            var selected = Selected(); if (selected == null || selected.Builtin) return;
            if (EditorUtility.DisplayDialog("Delete Profile", "Delete " + selected.DisplayName + "?", "Delete", "Cancel"))
            { _repository.Delete(selected); _selectedId = null; Refresh(); }
        }
        void ImportProfile()
        {
            var path = EditorUtility.OpenFilePanel("Import Generation Profile", "", "json");
            if (!string.IsNullOrEmpty(path)) { _repository.Import(path); Refresh(); }
        }
        void ExportSelected()
        {
            var selected = Selected(); if (selected == null) return;
            var path = EditorUtility.SaveFilePanel("Export Generation Profile", "", selected.Id + ".json", "json");
            if (!string.IsNullOrEmpty(path)) _repository.Export(selected, path, true);
        }
        void ValidateAll()
        {
            EditorUtility.DisplayDialog("Profile Validation",
                _registry.LoadErrors.Count == 0 ? "All loaded profiles are schema-valid." :
                string.Join("\n", _registry.LoadErrors.Select(x => x.Message)), "OK");
        }
    }
}
