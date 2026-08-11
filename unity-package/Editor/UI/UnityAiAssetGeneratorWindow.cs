using System;
using System.Linq;
using UnityAiAssets.Editor.Capabilities;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Generation;
using UnityAiAssets.Editor.Importing;
using UnityAiAssets.Editor.Profiles;
using UnityAiAssets.Editor.Tileable;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.UI
{
    /// <summary>
    /// Texture generation editor window (Tools &gt; AI Asset Generator).
    /// </summary>
    public sealed class UnityAiAssetGeneratorWindow : EditorWindow
    {
        GenerationController _controller;
        TextureGenerationRequestModel _request;
        Vector2 _scroll;
        ProfileCatalog _catalog;
        GenerationProfileRegistry _profiles;
        GenerationProfileResolver _resolver;

        // Tileable inspect/correct workflow state (editor-only; preserves original asset).
        Texture2D _previewOriginal;
        Texture2D _previewOffset;
        Texture2D _previewTiled;
        Texture2D _previewMaterialSwatch;
        SeamAnalysisResult _seamDiagnostics;
        WrapDiscontinuityResult _wrapDiagnostics;
        string _workingTexturePath;
        Color32[] _workingPixels;
        int _workingWidth;
        int _workingHeight;
        bool _showOffsetPreview = true;
        int _materialTiling = 2;

        [MenuItem("Tools/AI Asset Generator")]
        public static void Open()
        {
            var window = GetWindow<UnityAiAssetGeneratorWindow>();
            window.titleContent = new GUIContent("AI Asset Generator");
            window.minSize = new Vector2(420, 620);
            window.Show();
        }

        void OnEnable()
        {
            EnsureInitialized();
        }

        void OnDisable()
        {
            DestroyPreviewTextures();
        }

        void DestroyPreviewTextures()
        {
            DestroyPreview(ref _previewOriginal);
            DestroyPreview(ref _previewOffset);
            DestroyPreview(ref _previewTiled);
            DestroyPreview(ref _previewMaterialSwatch);
        }

        static void DestroyPreview(ref Texture2D texture)
        {
            if (texture == null) return;
            DestroyImmediate(texture);
            texture = null;
        }

        void EnsureInitialized()
        {
            // EditorWindow serializes fields across domain reloads; plain C# objects
            // become null while a stale "_initialized" flag can remain true.
            if (_controller != null && _request != null && _catalog != null && _profiles != null && _resolver != null)
            {
                return;
            }

            var settings = UnityAiAssetSettings.instance;
            _catalog = new ProfileCatalog();
            _profiles = new GenerationProfileRegistry(
                userRoot: settings.UserProfileDirectoryAbsolute, catalog: _catalog);
            _resolver = new GenerationProfileResolver(_catalog);
            _controller = new GenerationController(
                profileRegistry: _profiles, profileResolver: _resolver, catalog: _catalog);
            _request = new TextureGenerationRequestModel
            {
                DestinationFolder = settings.DefaultTextureDirectory,
                AssetType = settings.DefaultAssetType,
                SelectedProfileId = _catalog.GetAssetType(settings.DefaultAssetType).DefaultGenerationProfileId,
                ImportProfileId = settings.DefaultImportProfileId,
                MaterialDestinationFolder = settings.DefaultMaterialDirectory,
                ImportProfile = settings.DefaultTextureImportProfile,
                CreateMaterial = settings.CreateMaterialByDefault,
                ShaderName = settings.DefaultShaderName
            };
        }

        void OnGUI()
        {
            EnsureInitialized();
            if (_controller == null || _request == null)
            {
                EditorGUILayout.HelpBox(
                    "Failed to initialize the generator window. Close it and open Tools > AI Asset Generator again.",
                    MessageType.Error);
                return;
            }

            var progress = _controller.Progress;
            var busy = _controller.IsBusy;

            _scroll = EditorGUILayout.BeginScrollView(_scroll);
            EditorGUILayout.LabelField("Local Texture Generation", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "Requires the Python FastAPI backend on the configured base URL.\n" +
                "Default model (SD 1.5) is trained at 512×512 — smaller sizes often look like broken grids.\n" +
                "Generation can take 1–3+ minutes on a laptop GPU; the status line shows wait time.\n" +
                "Cancel Wait only stops waiting in Unity; backend GPU work may continue.\n" +
                "If 512×512 times out, raise API Timeout in Project Settings > AI Asset Generator.",
                MessageType.Info);

            EditorGUILayout.Space();
            DrawCapabilitiesSection(progress, busy);

            EditorGUILayout.Space();
            using (new EditorGUI.DisabledScope(busy))
            {
                DrawRequestFields(progress);
            }

            EditorGUILayout.Space();
            DrawActions(progress, busy);
            EditorGUILayout.Space();
            DrawTileableWorkflowSection(progress);
            EditorGUILayout.Space();
            DrawStatus(progress);
            EditorGUILayout.EndScrollView();
        }

        void DrawCapabilitiesSection(GenerationProgress progress, bool busy)
        {
            EditorGUILayout.LabelField("Backend Capabilities", EditorStyles.boldLabel);

            EditorGUILayout.BeginHorizontal();
            using (new EditorGUI.DisabledScope(busy))
            {
                if (GUILayout.Button("Refresh Capabilities", GUILayout.Height(24)))
                {
                    RunSafe(() => _controller.RefreshCapabilitiesAsync());
                }
            }

            EditorGUILayout.LabelField("State", progress.CapabilityState.ToString(), GUILayout.Width(160));
            EditorGUILayout.EndHorizontal();

            if (progress.Capabilities != null)
            {
                EditorGUILayout.LabelField(
                    "Application",
                    $"{progress.ApplicationVersion ?? "unknown"}");
                EditorGUILayout.LabelField(
                    "Model",
                    $"{progress.ModelId ?? "unknown"} (family={progress.ModelFamily ?? "unknown"})");
                EditorGUILayout.LabelField(
                    "Runtime",
                    $"device={progress.ResolvedDevice ?? "unknown"}, " +
                    $"precision={progress.ResolvedPrecision ?? "unknown"}, " +
                    $"model_loaded={progress.ModelLoaded}");
            }
            else
            {
                EditorGUILayout.HelpBox(
                    "Capabilities have not been loaded yet. Click Refresh Capabilities before generating.",
                    MessageType.Info);
            }

            switch (progress.CapabilityState)
            {
                case CapabilityState.Incompatible:
                    EditorGUILayout.HelpBox(
                        "Backend capabilities are incompatible with this package version " +
                        $"({UnityAiAssets.Editor.Versioning.ClientCompatibility.PackageVersion}): " +
                        (progress.CapabilityError ?? "unknown reason."),
                        MessageType.Error);
                    break;
                case CapabilityState.Unavailable:
                    EditorGUILayout.HelpBox(
                        "Backend capabilities are unavailable: " + (progress.CapabilityError ?? "unknown error."),
                        MessageType.Error);
                    break;
                case CapabilityState.Stale:
                    EditorGUILayout.HelpBox(
                        "Showing the last known-good capabilities; the most recent refresh failed: " +
                        (progress.CapabilityError ?? "unknown error."),
                        MessageType.Warning);
                    break;
            }
        }

        void DrawRequestFields(GenerationProgress progress)
        {
            var t2i = progress.Capabilities?.Operations?.TextToImage;

            EditorGUILayout.LabelField("Profile", EditorStyles.boldLabel);
            var assetTypes = _catalog.GetAssetTypes().ToArray();
            var assetIndex = Math.Max(0, Array.FindIndex(assetTypes, item => item.Id == _request.AssetType));
            var selectedAsset = EditorGUILayout.Popup("Asset Type", assetIndex, assetTypes.Select(x => x.DisplayName).ToArray());
            if (selectedAsset != assetIndex)
            {
                if (!HasDirtyOverrides() || EditorUtility.DisplayDialog(
                    "Replace Overrides?", "Switching asset type resets profile override fields.", "Switch", "Cancel"))
                {
                    _request.AssetType = assetTypes[selectedAsset].Id;
                    _request.SelectedProfileId = assetTypes[selectedAsset].DefaultGenerationProfileId;
                    ResetToProfileDefaults();
                }
            }
            var profiles = _profiles.FilterByAssetType(_request.AssetType).ToArray();
            var profileIndex = Math.Max(0, Array.FindIndex(profiles, item => item.Id == _request.SelectedProfileId));
            if (profiles.Length > 0)
            {
                var labels = profiles.Select(profile =>
                {
                    var compatibility = GenerationProfileCompatibilityChecker.Check(profile, progress.Capabilities);
                    return $"{profile.DisplayName} ({profile.Origin}, {compatibility.State})";
                }).ToArray();
                var selectedProfile = EditorGUILayout.Popup("Generation Profile", profileIndex, labels);
                if (selectedProfile != profileIndex)
                {
                    if (!HasDirtyOverrides() || EditorUtility.DisplayDialog(
                        "Replace Overrides?", "Switching profiles resets override fields.", "Switch", "Cancel"))
                    {
                        _request.SelectedProfileId = profiles[selectedProfile].Id;
                        ResetToProfileDefaults();
                    }
                }
                var current = profiles[Math.Min(selectedProfile, profiles.Length - 1)];
                EditorGUILayout.HelpBox(current.Description + "\nTags: " + string.Join(", ", current.Tags) +
                    $"\nSchema {current.SchemaVersion}, revision {current.Revision}", MessageType.None);
            }

            _request.Subject = EditorGUILayout.TextField("Subject", _request.Subject);
            _request.AdditionalPrompt = EditorGUILayout.TextField("Additional Prompt", _request.AdditionalPrompt);
            _request.AdditionalNegative = EditorGUILayout.TextField("Additional Negative", _request.AdditionalNegative);
            UpdatePromptPreview(progress);
            EditorGUILayout.LabelField("Prompt Preview", EditorStyles.boldLabel);
            using (new EditorGUI.DisabledScope(true))
            {
                EditorGUILayout.TextArea(_request.PreviewPrompt, GUILayout.MinHeight(50));
                EditorGUILayout.TextArea(_request.PreviewNegative, GUILayout.MinHeight(40));
            }
            if (t2i != null)
            {
                EditorGUILayout.LabelField(
                    "Max prompt length",
                    t2i.Prompt.MaximumLength.ToString(),
                    EditorStyles.miniLabel);
            }

            if (t2i != null && !t2i.NegativePrompt.Supported && !string.IsNullOrEmpty(_request.NegativePrompt))
            {
                EditorGUILayout.HelpBox("The backend does not currently support a negative prompt.", MessageType.Warning);
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Generation", EditorStyles.boldLabel);

            if (t2i != null)
            {
                DrawConstrainedIntField(
                    "Width", ref _request.Width,
                    t2i.Dimensions.MinimumWidth, t2i.Dimensions.MaximumWidth, t2i.Dimensions.WidthMultiple);
                DrawConstrainedIntField(
                    "Height", ref _request.Height,
                    t2i.Dimensions.MinimumHeight, t2i.Dimensions.MaximumHeight, t2i.Dimensions.HeightMultiple);
                DrawConstrainedIntField("Steps", ref _request.Steps, t2i.Steps.Minimum, t2i.Steps.Maximum, 1);
                DrawConstrainedFloatField(
                    "Guidance Scale", ref _request.GuidanceScale,
                    t2i.GuidanceScale.Minimum, t2i.GuidanceScale.Maximum);
            }
            else
            {
                // Capabilities not loaded yet - accept input as-is; preflight validation
                // will run against capabilities once they are available.
                _request.Width = EditorGUILayout.IntField("Width", _request.Width);
                _request.Height = EditorGUILayout.IntField("Height", _request.Height);
                _request.Steps = EditorGUILayout.IntField("Steps", _request.Steps);
                _request.GuidanceScale = EditorGUILayout.FloatField("Guidance Scale", _request.GuidanceScale);
                EditorGUILayout.HelpBox(
                    "Refresh capabilities to see backend-enforced limits for these fields.",
                    MessageType.Info);
            }

            _request.UseExplicitSeed = EditorGUILayout.Toggle("Use Explicit Seed", _request.UseExplicitSeed);
            using (new EditorGUI.DisabledScope(!_request.UseExplicitSeed))
            {
                _request.Seed = EditorGUILayout.LongField("Seed", _request.Seed);
            }

            _request.OutputName = EditorGUILayout.TextField("Output Name", _request.OutputName);
            if (_request.AssetType == "sprite" || _request.AssetType == "icon")
            {
                EditorGUILayout.Space();
                EditorGUILayout.LabelField("Sprite Processing", EditorStyles.boldLabel);
                _request.TransparencyStrategy = EditorGUILayout.Popup(
                    "Transparency Strategy",
                    _request.TransparencyStrategy == "background_removal" ? 1 : 0,
                    new[] { "none", "background_removal" }) == 1 ? "background_removal" : "none";
                _request.AlphaThreshold = EditorGUILayout.IntSlider("Alpha Threshold", _request.AlphaThreshold, 0, 255);
                _request.AlphaFeather = EditorGUILayout.IntSlider("Alpha Feather", _request.AlphaFeather, 0, 64);
                _request.RemoveNearTransparent = EditorGUILayout.Toggle(
                    "Remove Near Transparent", _request.RemoveNearTransparent);
                _request.ZeroRgbWhenTransparent = EditorGUILayout.Toggle(
                    "Zero RGB When Transparent", _request.ZeroRgbWhenTransparent);
                _request.PixelsPerUnit = EditorGUILayout.FloatField("Pixels Per Unit", _request.PixelsPerUnit);
                var pivotChoices = new[] { "center", "bottom_center", "custom" };
                _request.PivotMode = pivotChoices[EditorGUILayout.Popup(
                    "Pivot Mode", System.Array.IndexOf(pivotChoices, _request.PivotMode) < 0 ? 0 :
                    System.Array.IndexOf(pivotChoices, _request.PivotMode), pivotChoices)];
                if (_request.PivotMode == "custom")
                {
                    _request.CustomPivotX = EditorGUILayout.FloatField("Custom Pivot X", _request.CustomPivotX);
                    _request.CustomPivotY = EditorGUILayout.FloatField("Custom Pivot Y", _request.CustomPivotY);
                }
                _request.AtlasHint = EditorGUILayout.TextField("Atlas Hint", _request.AtlasHint);
                if (_request.TransparencyStrategy == "background_removal" &&
                    t2i?.Processing?.BackgroundRemoval?.Available != true)
                    EditorGUILayout.HelpBox(
                        "Background removal is unavailable on the current backend; generation is disabled.",
                        MessageType.Error);
            }

            if (_request.AssetType == "texture" && IsTileableProfileSelected())
            {
                EditorGUILayout.Space();
                EditorGUILayout.LabelField("Tileable Texture", EditorStyles.boldLabel);
                EditorGUILayout.HelpBox(
                    "Generate at 512×512 → optional local AI seam repair (circular offset + center-cross inpaint) → " +
                    "3×3 tile preview → optional palette → Unity Repeat import.\n" +
                    "AI seam repair runs on the backend during generate. There is no soft-blend success path.",
                    MessageType.Info);
                _request.Tileable = EditorGUILayout.Toggle("Tileable Workflow", _request.Tileable);
                _request.ApplySeamCorrection = EditorGUILayout.Toggle(
                    "Apply AI Seam Repair (on generate)", _request.ApplySeamCorrection);
                var seamMin = SeamThresholds.MinSeamWidth;
                var seamMax = SeamThresholds.MaxSeamWidth;
                var tileableCaps = t2i?.Processing?.Tileable;
                if (tileableCaps?.SeamBlendWidth != null)
                {
                    if (tileableCaps.SeamBlendWidth.Minimum > 0)
                        seamMin = tileableCaps.SeamBlendWidth.Minimum;
                    if (tileableCaps.SeamBlendWidth.Maximum > 0)
                        seamMax = tileableCaps.SeamBlendWidth.Maximum;
                }
                _request.SeamBlendWidth = EditorGUILayout.IntSlider(
                    "Seam Mask Width", _request.SeamBlendWidth, seamMin, seamMax);
                _request.PaletteReductionEnabled = EditorGUILayout.Toggle(
                    "Palette Reduction (on generate)", _request.PaletteReductionEnabled);
                using (new EditorGUI.DisabledScope(!_request.PaletteReductionEnabled))
                {
                    _request.PaletteColorCount = EditorGUILayout.IntSlider(
                        "Palette Colors", _request.PaletteColorCount, 2, 256);
                }
                if (_request.ApplySeamCorrection)
                {
                    if (_request.Width != 512 || _request.Height != 512)
                        EditorGUILayout.HelpBox(
                            "AI seam repair requires exactly 512×512.",
                            MessageType.Error);
                    if (tileableCaps != null && !tileableCaps.AiInpaintAvailable)
                        EditorGUILayout.HelpBox(
                            "Local seam inpainting is unavailable on the current backend; disable AI seam repair or enable the inpaint model.",
                            MessageType.Error);
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Unity Import", EditorStyles.boldLabel);
            _request.DestinationFolder = EditorGUILayout.TextField("Destination Folder", _request.DestinationFolder);
            _request.ImportProfileId = EditorGUILayout.TextField(
                "Import Profile ID (Primary)", _request.ImportProfileId);
            var previousKind = _request.ImportProfile;
            _request.ImportProfile = (TextureImportProfileKind)EditorGUILayout.EnumPopup(
                "Legacy Import Kind (Secondary)",
                _request.ImportProfile);
            if (_request.ImportProfile != previousKind)
            {
                _request.ImportProfileId = TextureImportProfile.FromKind(_request.ImportProfile).Id;
            }
            _request.CreateMaterial = EditorGUILayout.Toggle("Create Material", _request.CreateMaterial);
            using (new EditorGUI.DisabledScope(!_request.CreateMaterial))
            {
                _request.MaterialDestinationFolder = EditorGUILayout.TextField(
                    "Material Destination",
                    _request.MaterialDestinationFolder);
                _request.ShaderName = EditorGUILayout.TextField("Shader", _request.ShaderName);
            }

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Reset to Profile Defaults")) ResetToProfileDefaults();
            if (GUILayout.Button("Duplicate Profile")) GenerationProfileManagerWindow.OpenWithProfile(_request.SelectedProfileId);
            if (GUILayout.Button("Manage Profiles")) GenerationProfileManagerWindow.Open();
            EditorGUILayout.EndHorizontal();
            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Create New Profile"))
                GenerationProfileEditorWindow.OpenNew(new UserProfileRepository(
                    UnityAiAssetSettings.instance.UserProfileDirectoryAbsolute));
            using (new EditorGUI.DisabledScope(
                !_profiles.TryGet(_request.SelectedProfileId, out var editable) || editable.Builtin))
            {
                if (GUILayout.Button("Edit User Profile"))
                    GenerationProfileEditorWindow.Open(editable, new UserProfileRepository(
                        UnityAiAssetSettings.instance.UserProfileDirectoryAbsolute));
            }
            EditorGUILayout.EndHorizontal();
        }

        void ResetToProfileDefaults()
        {
            if (!_profiles.TryGet(_request.SelectedProfileId, out var profile)) return;
            _request.Width = profile.Defaults.Width;
            _request.Height = profile.Defaults.Height;
            _request.Steps = profile.Defaults.Steps;
            _request.GuidanceScale = profile.Defaults.GuidanceScale;
            _request.UseExplicitSeed = profile.Defaults.SeedStrategy == "fixed";
            _request.Seed = profile.Defaults.FixedSeed ?? 0;
            _request.DestinationFolder = profile.Unity.SuggestedOutputDirectory;
            _request.ImportProfileId = profile.Unity.ImportProfileId;
            _request.CreateMaterial = profile.Unity.CreateMaterial;
            _request.TransparencyStrategy = profile.Processing.TransparencyStrategy;
            _request.AlphaThreshold = profile.Processing.AlphaThreshold;
            _request.AlphaFeather = profile.Processing.AlphaFeather;
            _request.RemoveNearTransparent = profile.Processing.RemoveNearTransparent;
            _request.ZeroRgbWhenTransparent = profile.Processing.ZeroRgbWhenTransparent;
            _request.PixelsPerUnit = profile.Unity.PixelsPerUnit;
            _request.PivotMode = profile.Unity.PivotMode;
            _request.CustomPivotX = profile.Unity.CustomPivotX;
            _request.CustomPivotY = profile.Unity.CustomPivotY;
            _request.AtlasHint = profile.Unity.AtlasHint;
            _request.Tileable = profile.Processing.Tileable;
            _request.ApplySeamCorrection = profile.Processing.ApplySeamCorrection;
            _request.SeamBlendWidth = profile.Processing.SeamBlendWidth;
            _request.PaletteReductionEnabled = profile.Processing.PaletteReductionEnabled;
            _request.PaletteColorCount = profile.Processing.PaletteColorCount;
        }

        bool IsTileableProfileSelected()
        {
            if (!_profiles.TryGet(_request.SelectedProfileId, out var profile)) return _request.Tileable;
            if (profile.Processing.Tileable) return true;
            return profile.Tags != null && profile.Tags.Exists(tag =>
                string.Equals(tag, "tileable", StringComparison.OrdinalIgnoreCase));
        }

        bool HasDirtyOverrides()
        {
            if (!_profiles.TryGet(_request.SelectedProfileId, out var profile)) return false;
            return _request.Width != profile.Defaults.Width ||
                   _request.Height != profile.Defaults.Height ||
                   _request.Steps != profile.Defaults.Steps ||
                   Math.Abs(_request.GuidanceScale - profile.Defaults.GuidanceScale) > 0.0001f ||
                   _request.DestinationFolder != profile.Unity.SuggestedOutputDirectory ||
                   _request.ImportProfileId != profile.Unity.ImportProfileId ||
                   _request.CreateMaterial != profile.Unity.CreateMaterial ||
                   _request.TransparencyStrategy != profile.Processing.TransparencyStrategy ||
                   _request.PixelsPerUnit != profile.Unity.PixelsPerUnit ||
                   _request.PivotMode != profile.Unity.PivotMode ||
                   _request.AtlasHint != profile.Unity.AtlasHint ||
                   _request.Tileable != profile.Processing.Tileable ||
                   _request.ApplySeamCorrection != profile.Processing.ApplySeamCorrection ||
                   _request.PaletteReductionEnabled != profile.Processing.PaletteReductionEnabled;
        }

        void UpdatePromptPreview(GenerationProgress progress)
        {
            try
            {
                var resolved = _resolver.Resolve(_profiles.Get(_request.SelectedProfileId), new UserProfileOverrides
                {
                    Subject = _request.Subject,
                    AdditionalPrompt = _request.AdditionalPrompt,
                    AdditionalNegative = _request.AdditionalNegative,
                    TransparencyStrategy = _request.TransparencyStrategy,
                    AlphaThreshold = _request.AlphaThreshold,
                    AlphaFeather = _request.AlphaFeather,
                    RemoveNearTransparent = _request.RemoveNearTransparent,
                    ZeroRgbWhenTransparent = _request.ZeroRgbWhenTransparent,
                    PixelsPerUnit = _request.PixelsPerUnit,
                    PivotMode = _request.PivotMode,
                    CustomPivotX = _request.CustomPivotX,
                    CustomPivotY = _request.CustomPivotY,
                    AtlasHint = _request.AtlasHint,
                    Tileable = _request.Tileable,
                    ApplySeamCorrection = _request.ApplySeamCorrection,
                    SeamBlendWidth = _request.SeamBlendWidth,
                    PaletteReductionEnabled = _request.PaletteReductionEnabled,
                    PaletteColorCount = _request.PaletteColorCount
                }, progress.Capabilities);
                var dto = GenerationRequestFactory.FromResolved(resolved, _request);
                _request.PreviewPrompt = _request.Prompt = dto.prompt;
                _request.PreviewNegative = _request.NegativePrompt = dto.negative_prompt;
            }
            catch (Exception exception)
            {
                _request.PreviewPrompt = "Invalid profile input: " + exception.Message;
                _request.PreviewNegative = string.Empty;
            }
        }

        void DrawTileableWorkflowSection(GenerationProgress progress)
        {
            if (_request.AssetType != "texture") return;

            EditorGUILayout.LabelField("Tileable Inspect / Preview", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(
                "Load an imported texture to inspect offset seams, wrap discontinuity, and 3×3 tiling. " +
                "AI seam repair is applied on generate only (local inpaint)—not via soft blending here.",
                MessageType.None);

            var importedPath = progress.ImportedTexturePath;
            using (new EditorGUI.DisabledScope(string.IsNullOrWhiteSpace(importedPath)))
            {
                if (GUILayout.Button("Load Imported Texture for Tileable Tools"))
                {
                    LoadWorkingTexture(importedPath);
                }
            }

            if (_workingPixels == null || string.IsNullOrEmpty(_workingTexturePath))
            {
                EditorGUILayout.LabelField("No working texture loaded.", EditorStyles.miniLabel);
                return;
            }

            EditorGUILayout.LabelField("Working", _workingTexturePath, EditorStyles.miniLabel);
            _showOffsetPreview = EditorGUILayout.Toggle("Show Offset Preview (50%)", _showOffsetPreview);

            if (_seamDiagnostics != null)
            {
                EditorGUILayout.LabelField(
                    "Edge RGB",
                    $"H={_seamDiagnostics.HorizontalScore:0.###}  V={_seamDiagnostics.VerticalScore:0.###}  " +
                    $"Combined={_seamDiagnostics.CombinedScore:0.###} ({_seamDiagnostics.QualityLabel})",
                    EditorStyles.miniLabel);
            }

            if (_wrapDiagnostics != null)
            {
                EditorGUILayout.LabelField(
                    "Wrap Δ",
                    $"H={_wrapDiagnostics.HorizontalRatio:0.00}x  V={_wrapDiagnostics.VerticalRatio:0.00}x normal gradient",
                    EditorStyles.miniLabel);
            }

            const float previewSize = 128f;
            EditorGUILayout.BeginHorizontal();
            DrawPreviewColumn("Original", _previewOriginal, previewSize);
            if (_showOffsetPreview)
                DrawPreviewColumn("Offset", _previewOffset, previewSize);
            DrawPreviewColumn("3×3 Tile", _previewTiled, previewSize);
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Re-Analyze Seams"))
                RefreshDiagnosticsAndPreviews();
            if (GUILayout.Button("Apply Palette Reduction"))
                ApplyPaletteToWorking();
            EditorGUILayout.EndHorizontal();

            _request.PaletteColorCount = EditorGUILayout.IntSlider(
                "Palette Colors", _request.PaletteColorCount, 2, 256);

            _materialTiling = EditorGUILayout.IntSlider("Material UV Tiling Preview", _materialTiling, 1, 8);
            if (_previewMaterialSwatch != null)
            {
                EditorGUILayout.LabelField("Unity Repeat Preview", EditorStyles.miniLabel);
                var rect = GUILayoutUtility.GetRect(previewSize, previewSize, GUILayout.ExpandWidth(false));
                EditorGUI.DrawPreviewTexture(rect, _previewMaterialSwatch, null, ScaleMode.ScaleToFit);
            }

            var wrapOk = false;
            var importer = AssetImporter.GetAtPath(_workingTexturePath) as TextureImporter;
            if (importer != null)
                wrapOk = importer.wrapMode == TextureWrapMode.Repeat;
            EditorGUILayout.HelpBox(
                wrapOk
                    ? "Import wrap mode is Repeat — suitable for tiling materials."
                    : "Import wrap mode is not Repeat. Prefer the ps1_tileable_texture import profile.",
                wrapOk ? MessageType.Info : MessageType.Warning);
        }

        static void DrawPreviewColumn(string label, Texture2D texture, float size)
        {
            EditorGUILayout.BeginVertical(GUILayout.Width(size + 8));
            EditorGUILayout.LabelField(label, EditorStyles.miniBoldLabel);
            var rect = GUILayoutUtility.GetRect(size, size, GUILayout.ExpandWidth(false));
            if (texture != null)
                EditorGUI.DrawPreviewTexture(rect, texture, null, ScaleMode.ScaleToFit);
            else
                EditorGUI.DrawRect(rect, new Color(0.15f, 0.15f, 0.15f));
            EditorGUILayout.EndVertical();
        }

        void LoadWorkingTexture(string assetPath)
        {
            var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(assetPath);
            if (texture == null) return;
            if (!TileableTextureWorkflow.TryReadPixels(texture, out var pixels, out var width, out var height, out var error))
            {
                EditorUtility.DisplayDialog("Tileable Tools", "Could not read texture pixels: " + error, "OK");
                return;
            }

            _workingTexturePath = assetPath;
            _workingPixels = pixels;
            _workingWidth = width;
            _workingHeight = height;
            RefreshDiagnosticsAndPreviews();
        }

        void RefreshDiagnosticsAndPreviews()
        {
            if (_workingPixels == null) return;
            _seamDiagnostics = SeamAnalysis.Analyze(_workingPixels, _workingWidth, _workingHeight);
            _wrapDiagnostics = WrapDiagnostics.Analyze(_workingPixels, _workingWidth, _workingHeight);
            DestroyPreviewTextures();
            _previewOriginal = TileableTextureWorkflow.CreatePreviewTexture(
                _workingPixels, _workingWidth, _workingHeight, FilterMode.Point);
            var offset = OffsetWrap.OffsetPreview(_workingPixels, _workingWidth, _workingHeight);
            _previewOffset = TileableTextureWorkflow.CreatePreviewTexture(
                offset, _workingWidth, _workingHeight, FilterMode.Point);
            var tiled = OffsetWrap.TiledPreview(_workingPixels, _workingWidth, _workingHeight, 3);
            _previewTiled = TileableTextureWorkflow.CreatePreviewTexture(
                tiled, _workingWidth * 3, _workingHeight * 3, FilterMode.Point);
            var materialTiles = OffsetWrap.TiledPreview(
                _workingPixels, _workingWidth, _workingHeight, Math.Max(1, _materialTiling));
            _previewMaterialSwatch = TileableTextureWorkflow.CreatePreviewTexture(
                materialTiles,
                _workingWidth * Math.Max(1, _materialTiling),
                _workingHeight * Math.Max(1, _materialTiling),
                FilterMode.Point);
            Repaint();
        }

        void ApplyPaletteToWorking()
        {
            if (_workingPixels == null) return;
            var reduced = PaletteReduction.Reduce(
                _workingPixels, _workingWidth, _workingHeight, _request.PaletteColorCount);
            var profile = _catalog.TryGetImportProfile(_request.ImportProfileId, out var importProfile)
                ? importProfile
                : TextureImportProfile.CreatePs1Tileable();
            var path = TileableTextureWorkflow.WriteSiblingPng(
                _workingTexturePath, reduced, _workingWidth, _workingHeight, ".palette", profile);
            _workingPixels = reduced;
            _workingTexturePath = path;
            _controller.Progress.ImportedTexturePath = path;
            RefreshDiagnosticsAndPreviews();
        }

        /// <summary>
        /// Draws a plain int field annotated with the backend-reported valid range/multiple.
        /// Deliberately uses IntField rather than IntSlider: Unity's slider controls clamp
        /// their displayed value to [minimum, maximum] on every repaint, which would silently
        /// rewrite an out-of-range value the user just typed. Out-of-range values are instead
        /// left as-is and flagged with a warning; preflight validation is the real gate.
        /// </summary>
        static void DrawConstrainedIntField(string label, ref int value, int minimum, int maximum, int multiple)
        {
            var hint = multiple > 1
                ? $"{minimum}–{maximum}, multiple of {multiple}"
                : $"{minimum}–{maximum}";
            value = EditorGUILayout.IntField($"{label} ({hint})", value);

            if (value < minimum || value > maximum || (multiple > 1 && value % multiple != 0))
            {
                EditorGUILayout.HelpBox(
                    $"{label} must be between {minimum} and {maximum}" +
                    (multiple > 1 ? $" and divisible by {multiple}" : string.Empty) +
                    $" (currently {value}).",
                    MessageType.Warning);
            }
        }

        static void DrawConstrainedFloatField(string label, ref float value, float minimum, float maximum)
        {
            value = EditorGUILayout.FloatField($"{label} ({minimum:0.#}–{maximum:0.#})", value);

            if (value < minimum || value > maximum)
            {
                EditorGUILayout.HelpBox(
                    $"{label} must be between {minimum} and {maximum} (currently {value}).",
                    MessageType.Warning);
            }
        }

        void DrawActions(GenerationProgress progress, bool busy)
        {
            var profileCompatibility = _profiles.TryGet(_request.SelectedProfileId, out var profile)
                ? GenerationProfileCompatibilityChecker.Check(profile, progress.Capabilities)
                : null;
            var canGenerate = progress.CanGenerate &&
                              profileCompatibility?.CanGenerate == true &&
                              !string.IsNullOrWhiteSpace(_request.Subject);
            if (canGenerate &&
                _request.ApplySeamCorrection &&
                (_request.Width != 512 || _request.Height != 512 ||
                 progress.Capabilities?.Operations?.TextToImage?.Processing?.Tileable?.AiInpaintAvailable == false))
            {
                canGenerate = false;
            }

            EditorGUILayout.BeginHorizontal();
            using (new EditorGUI.DisabledScope(busy))
            {
                if (GUILayout.Button("Check Backend Connection", GUILayout.Height(28)))
                {
                    RunSafe(() => _controller.CheckConnectionAsync());
                }

                using (new EditorGUI.DisabledScope(!canGenerate))
                {
                    if (GUILayout.Button("Generate And Import", GUILayout.Height(28)))
                    {
                        RunSafe(() => _controller.GenerateAndImportAsync(_request));
                    }
                }
            }

            using (new EditorGUI.DisabledScope(!busy))
            {
                if (GUILayout.Button("Cancel Wait", GUILayout.Height(28)))
                {
                    _controller.CancelLocalWait();
                }
            }

            EditorGUILayout.EndHorizontal();

            if (!canGenerate && !busy)
            {
                string reason;
                if (_request.ApplySeamCorrection && (_request.Width != 512 || _request.Height != 512))
                    reason = "Generate is disabled: AI seam repair requires exactly 512×512.";
                else if (_request.ApplySeamCorrection &&
                         progress.Capabilities?.Operations?.TextToImage?.Processing?.Tileable?.AiInpaintAvailable == false)
                    reason = "Generate is disabled: local seam inpainting is unavailable on the backend.";
                else if (profileCompatibility != null && !profileCompatibility.CanGenerate)
                    reason = string.Join("\n", profileCompatibility.Messages);
                else if (string.IsNullOrWhiteSpace(_request.Subject))
                    reason = "Generate is disabled: subject is required.";
                else
                    reason = GenerateUnavailableReason(progress);
                EditorGUILayout.HelpBox(reason, MessageType.Warning);
            }

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Open Generated Folder"))
            {
                OpenFolder(_request.DestinationFolder);
            }

            using (new EditorGUI.DisabledScope(string.IsNullOrWhiteSpace(_controller.Progress.ImportedTexturePath)))
            {
                if (GUILayout.Button("Select Imported Texture"))
                {
                    var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(_controller.Progress.ImportedTexturePath);
                    if (texture != null)
                    {
                        Selection.activeObject = texture;
                        EditorGUIUtility.PingObject(texture);
                    }
                }
            }

            EditorGUILayout.EndHorizontal();
        }

        static string GenerateUnavailableReason(GenerationProgress progress)
        {
            switch (progress.CapabilityState)
            {
                case CapabilityState.Unknown:
                    return "Generate is disabled: capabilities have not been loaded. Click Refresh Capabilities.";
                case CapabilityState.Loading:
                    return "Generate is disabled: capabilities are loading.";
                case CapabilityState.Unavailable:
                    return "Generate is disabled: backend capabilities are unavailable. " +
                           (progress.CapabilityError ?? string.Empty);
                case CapabilityState.Incompatible:
                    return "Generate is disabled: backend capabilities are incompatible with this package. " +
                           (progress.CapabilityError ?? string.Empty);
                default:
                    return "Generate is disabled: text_to_image is not currently supported by the backend.";
            }
        }

        void DrawStatus(GenerationProgress progress)
        {
            EditorGUILayout.LabelField("Status", EditorStyles.boldLabel);
            EditorGUILayout.LabelField("State", progress.State.ToString());
            EditorGUILayout.LabelField("Message", progress.StatusMessage ?? string.Empty);
            EditorGUILayout.LabelField(
                "Backend",
                progress.BackendReachable
                    ? $"Reachable (device={progress.ResolvedDevice}, model_loaded={progress.ModelLoaded})"
                    : "Not confirmed / unreachable");

            if (!string.IsNullOrWhiteSpace(progress.GenerationId))
            {
                EditorGUILayout.LabelField("Generation ID", progress.GenerationId);
            }

            if (progress.Seed.HasValue)
            {
                EditorGUILayout.LabelField("Seed", progress.Seed.Value.ToString());
            }

            if (progress.ElapsedSeconds.HasValue)
            {
                EditorGUILayout.LabelField("Backend Elapsed (s)", progress.ElapsedSeconds.Value.ToString("0.###"));
            }

            if (!string.IsNullOrWhiteSpace(progress.RequestId))
            {
                EditorGUILayout.LabelField("Last Request ID", progress.RequestId);
            }

            if (!string.IsNullOrWhiteSpace(progress.ImportedTexturePath))
            {
                EditorGUILayout.LabelField("Imported Texture", progress.ImportedTexturePath);
            }

            if (!string.IsNullOrWhiteSpace(progress.ImportedMaterialPath))
            {
                EditorGUILayout.LabelField("Imported Material", progress.ImportedMaterialPath);
            }

            if (!string.IsNullOrWhiteSpace(progress.MetadataAssetPath))
            {
                EditorGUILayout.LabelField("Metadata Asset", progress.MetadataAssetPath);
            }

            if (progress.ValidationIssues != null && progress.ValidationIssues.Count > 0)
            {
                foreach (var issue in progress.ValidationIssues)
                {
                    EditorGUILayout.HelpBox(issue.ToString(), MessageType.Warning);
                }
            }

            if (!string.IsNullOrWhiteSpace(progress.ErrorMessage))
            {
                EditorGUILayout.HelpBox(progress.ErrorMessage, MessageType.Error);
            }

            RepaintIfBusy(progress);
        }

        void RepaintIfBusy(GenerationProgress progress)
        {
            if (progress.State == GenerationState.CheckingConnection ||
                progress.State == GenerationState.Submitting ||
                progress.State == GenerationState.Generating ||
                progress.State == GenerationState.Downloading ||
                progress.State == GenerationState.Importing ||
                progress.State == GenerationState.RefreshingCapabilities)
            {
                Repaint();
            }
        }

        static void OpenFolder(string assetFolder)
        {
            try
            {
                var folder = AssetPathUtility.NormalizeAssetPath(assetFolder);
                AssetPathUtility.EnsureAssetFolderExists(folder);
                var obj = AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(folder);
                if (obj != null)
                {
                    Selection.activeObject = obj;
                    EditorGUIUtility.PingObject(obj);
                }
                else
                {
                    EditorUtility.RevealInFinder(AssetPathUtility.AssetPathToAbsolute(folder + "/."));
                }
            }
            catch (Exception ex)
            {
                EditorUtility.DisplayDialog("Open Folder Failed", ex.Message, "OK");
            }
        }

        static async void RunSafe(Func<System.Threading.Tasks.Task> action)
        {
            try
            {
                await action().ConfigureAwait(true);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                EditorUtility.DisplayDialog("AI Asset Generator", ex.Message, "OK");
            }
        }
    }
}
