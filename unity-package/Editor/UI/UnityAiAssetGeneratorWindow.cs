using System;
using System.IO;
using System.Linq;
using UnityAiAssets.Editor.Api;
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
    /// Layout uses flexible EditorGUILayout patterns so docked/narrow windows remain usable.
    /// </summary>
    public sealed class UnityAiAssetGeneratorWindow : EditorWindow
    {
        GenerationController _controller;
        TextureGenerationRequestModel _request;
        Vector2 _scroll;
        ProfileCatalog _catalog;
        GenerationProfileRegistry _profiles;
        GenerationProfileResolver _resolver;

        bool _foldBackend = true;
        bool _foldProfile = true;
        bool _foldPrompt = true;
        bool _foldGeneration = true;
        bool _foldImg2Img = true;
        bool _foldInpaint = true;
        bool _foldProcessing = true;
        bool _foldImport = true;
        bool _foldTileable = true;
        bool _foldStatus = true;
        bool _foldHistory = true;

        Texture2D _previewOriginal;
        Texture2D _previewOffset;
        Texture2D _previewTiled;
        Texture2D _previewMaterialSwatch;
        Texture2D _inspectSource;
        Texture2D _compareSource;
        Texture2D _previewCompare;
        Texture2D _previewCompareTiled;
        bool _ownsSourceTexture;
        bool _ownsMaskTexture;
        Texture2D _maskOverlay;
        bool _maskOverlayDirty = true;
        SeamAnalysisResult _seamDiagnostics;
        WrapDiscontinuityResult _wrapDiagnostics;
        string _workingTexturePath;
        Color32[] _workingPixels;
        int _workingWidth;
        int _workingHeight;
        bool _showOffsetPreview = true;
        int _materialTiling = 2;
        string _autoLoadedImportPath;

        static GUIStyle _wrappedTextArea;
        static GUIStyle _sectionHelp;

        [MenuItem("Tools/AI Asset Generator")]
        public static void Open()
        {
            var window = GetWindow<UnityAiAssetGeneratorWindow>();
            window.titleContent = new GUIContent("AI Asset Generator");
            window.minSize = new Vector2(360, 480);
            window.Show();
        }

        void OnEnable()
        {
            EnsureInitialized();
        }

        void OnDisable()
        {
            DestroyPreviewTextures();
            DestroyOwnedSourceTexture();
            DestroyOwnedMaskTexture();
            DestroyPreview(ref _maskOverlay);
        }

        void DestroyPreviewTextures()
        {
            DestroyPreview(ref _previewOriginal);
            DestroyPreview(ref _previewOffset);
            DestroyPreview(ref _previewTiled);
            DestroyPreview(ref _previewMaterialSwatch);
            DestroyPreview(ref _previewCompare);
            DestroyPreview(ref _previewCompareTiled);
        }

        static void DestroyPreview(ref Texture2D texture)
        {
            if (texture == null) return;
            DestroyImmediate(texture);
            texture = null;
        }

        void EnsureInitialized()
        {
            if (_controller != null && _request != null && _catalog != null && _profiles != null && _resolver != null)
                return;

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

        static void EnsureStyles()
        {
            if (_wrappedTextArea == null)
            {
                _wrappedTextArea = new GUIStyle(EditorStyles.textArea)
                {
                    wordWrap = true,
                    richText = false
                };
            }

            if (_sectionHelp == null)
            {
                _sectionHelp = new GUIStyle(EditorStyles.miniLabel)
                {
                    wordWrap = true
                };
            }
        }

        void OnGUI()
        {
            EnsureInitialized();
            EnsureStyles();
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
            EditorGUILayout.LabelField("Local AI Asset Generation", EditorStyles.boldLabel);
            EditorGUILayout.LabelField(
                "Requires the Python FastAPI backend. Default SD 1.5 is trained at 512×512. " +
                "Generate submits a job and polls status; Cancel asks the backend to stop queued or running work.",
                _sectionHelp);

            EditorGUILayout.Space(4);
            using (new EditorGUI.DisabledScope(busy))
            {
                DrawBackendSection(progress, busy);
                DrawProfileSection(progress);
                DrawPromptSection(progress);
                DrawGenerationSection(progress);
                DrawImageToImageSection(progress);
                DrawInpaintingSection(progress);
                DrawProcessingSection(progress);
                DrawImportSection();
            }

            EditorGUILayout.Space(4);
            DrawActions(progress, busy);
            MaybeAutoLoadImportedTexture(progress);
            DrawTileableWorkflowSection(progress);
            DrawHistory(progress, busy);
            DrawStatus(progress);
            EditorGUILayout.EndScrollView();
        }

        void MaybeAutoLoadImportedTexture(GenerationProgress progress)
        {
            if (_request.AssetType != "texture")
                return;
            if (progress.State != GenerationState.Completed)
                return;
            if (string.IsNullOrWhiteSpace(progress.ImportedTexturePath))
                return;
            if (string.Equals(progress.ImportedTexturePath, _autoLoadedImportPath, StringComparison.Ordinal))
                return;

            _autoLoadedImportPath = progress.ImportedTexturePath;
            LoadWorkingTexture(progress.ImportedTexturePath);
        }

        static GUIContent Tip(string label, string tooltip) => new GUIContent(label, tooltip);

        void DrawBackendSection(GenerationProgress progress, bool busy)
        {
            _foldBackend = EditorGUILayout.BeginFoldoutHeaderGroup(_foldBackend, "Backend");
            if (_foldBackend)
            {
                EditorGUILayout.BeginHorizontal();
                using (new EditorGUI.DisabledScope(busy))
                {
                    if (GUILayout.Button(
                            Tip("Refresh Capabilities", "Fetch versioned capability document from the backend."),
                            GUILayout.Height(22)))
                        RunSafe(() => _controller.RefreshCapabilitiesAsync());
                }

                EditorGUILayout.LabelField(
                    Tip("State", "Capability cache state for the configured base URL."),
                    new GUIContent(progress.CapabilityState.ToString()),
                    EditorStyles.miniLabel);
                EditorGUILayout.EndHorizontal();

                if (progress.Capabilities != null)
                {
                    EditorGUILayout.LabelField("Application", progress.ApplicationVersion ?? "unknown", _sectionHelp);
                    EditorGUILayout.LabelField(
                        "Model",
                        $"{progress.ModelId ?? "unknown"} ({progress.ModelFamily ?? "unknown"})",
                        _sectionHelp);
                    EditorGUILayout.LabelField(
                        "Runtime",
                        $"device={progress.ResolvedDevice ?? "?"}, precision={progress.ResolvedPrecision ?? "?"}, loaded={progress.ModelLoaded}",
                        _sectionHelp);
                    var bg = progress.Capabilities.Operations?.TextToImage?.Processing?.BackgroundRemoval;
                    if (bg != null)
                    {
                        EditorGUILayout.LabelField(
                            "Background removal",
                            bg.Available
                                ? $"available ({bg.Backend}:{bg.Model})"
                                : "unavailable — " + (bg.UnavailableReason ?? "see backend logs"),
                            _sectionHelp);
                    }

                    var tile = progress.Capabilities.Operations?.TextToImage?.Processing?.Tileable;
                    if (tile != null)
                    {
                        EditorGUILayout.LabelField(
                            "AI seam inpaint",
                            tile.AiInpaintAvailable ? "available (local Diffusers)" : "unavailable",
                            _sectionHelp);
                    }
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
                            "Backend capabilities are incompatible with this package " +
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
                            "Showing last known-good capabilities; refresh failed: " +
                            (progress.CapabilityError ?? "unknown error."),
                            MessageType.Warning);
                        break;
                }
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawProfileSection(GenerationProgress progress)
        {
            _foldProfile = EditorGUILayout.BeginFoldoutHeaderGroup(_foldProfile, "Profile");
            if (_foldProfile)
            {
                var assetTypes = _catalog.GetAssetTypes().ToArray();
                var assetIndex = Math.Max(0, Array.FindIndex(assetTypes, item => item.Id == _request.AssetType));
                var selectedAsset = EditorGUILayout.Popup(
                    Tip("Asset Type", "Selects which generation profiles and processing options apply."),
                    assetIndex,
                    assetTypes.Select(x => x.DisplayName).ToArray());
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
                    var selectedProfile = EditorGUILayout.Popup(
                        Tip("Generation Profile", "Built-in or user profile driving prompts, defaults, and import hints."),
                        profileIndex,
                        labels);
                    if (selectedProfile != profileIndex)
                    {
                        if (!HasDirtyOverrides() || EditorUtility.DisplayDialog(
                                "Replace Overrides?", "Switching profiles resets override fields.", "Switch", "Cancel"))
                        {
                            _request.SelectedProfileId = profiles[selectedProfile].Id;
                            ResetToProfileDefaults();
                        }
                    }

                    var current = profiles[Math.Min(Math.Max(selectedProfile, 0), profiles.Length - 1)];
                    EditorGUILayout.LabelField(current.Description, _sectionHelp);
                    EditorGUILayout.LabelField(
                        $"Tags: {string.Join(", ", current.Tags)} · Schema {current.SchemaVersion}, rev {current.Revision}",
                        _sectionHelp);
                }

                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("Reset Defaults")) ResetToProfileDefaults();
                if (GUILayout.Button("Duplicate")) GenerationProfileManagerWindow.OpenWithProfile(_request.SelectedProfileId);
                if (GUILayout.Button("Manage")) GenerationProfileManagerWindow.Open();
                EditorGUILayout.EndHorizontal();
                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("Create New"))
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

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawPromptSection(GenerationProgress progress)
        {
            _foldPrompt = EditorGUILayout.BeginFoldoutHeaderGroup(_foldPrompt, "Prompt");
            if (_foldPrompt)
            {
                EditorGUILayout.LabelField(
                    Tip("Subject", "Primary subject inserted into the profile prompt template."),
                    EditorStyles.miniLabel);
                _request.Subject = EditorGUILayout.TextArea(_request.Subject ?? string.Empty, _wrappedTextArea, GUILayout.MinHeight(40));

                EditorGUILayout.LabelField(
                    Tip("Additional Prompt", "Extra positive terms appended after template modifiers."),
                    EditorStyles.miniLabel);
                _request.AdditionalPrompt = EditorGUILayout.TextArea(
                    _request.AdditionalPrompt ?? string.Empty, _wrappedTextArea, GUILayout.MinHeight(36));

                EditorGUILayout.LabelField(
                    Tip("Additional Negative", "Extra negative terms appended to the resolved negative prompt."),
                    EditorStyles.miniLabel);
                _request.AdditionalNegative = EditorGUILayout.TextArea(
                    _request.AdditionalNegative ?? string.Empty, _wrappedTextArea, GUILayout.MinHeight(36));

                UpdatePromptPreview(progress);
                EditorGUILayout.LabelField("Resolved Prompt Preview", EditorStyles.miniBoldLabel);
                using (new EditorGUI.DisabledScope(true))
                {
                    EditorGUILayout.TextArea(
                        _request.PreviewPrompt ?? string.Empty, _wrappedTextArea, GUILayout.MinHeight(56));
                    EditorGUILayout.TextArea(
                        _request.PreviewNegative ?? string.Empty, _wrappedTextArea, GUILayout.MinHeight(40));
                }

                var t2i = progress.Capabilities?.Operations?.TextToImage;
                if (t2i != null)
                {
                    EditorGUILayout.LabelField(
                        $"Max prompt length: {t2i.Prompt.MaximumLength}",
                        EditorStyles.miniLabel);
                }

                if (t2i != null && !t2i.NegativePrompt.Supported && !string.IsNullOrEmpty(_request.NegativePrompt))
                    EditorGUILayout.HelpBox("The backend does not currently support a negative prompt.", MessageType.Warning);
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawGenerationSection(GenerationProgress progress)
        {
            _foldGeneration = EditorGUILayout.BeginFoldoutHeaderGroup(_foldGeneration, "Generation Settings");
            if (_foldGeneration)
            {
                var t2i = progress.Capabilities?.Operations?.TextToImage;
                if (t2i != null)
                {
                    DrawConstrainedIntField(
                        Tip("Width", "Output width in pixels. Must satisfy backend min/max/multiple."),
                        ref _request.Width,
                        t2i.Dimensions.MinimumWidth, t2i.Dimensions.MaximumWidth, t2i.Dimensions.WidthMultiple);
                    DrawConstrainedIntField(
                        Tip("Height", "Output height in pixels. Must satisfy backend min/max/multiple."),
                        ref _request.Height,
                        t2i.Dimensions.MinimumHeight, t2i.Dimensions.MaximumHeight, t2i.Dimensions.HeightMultiple);
                    DrawConstrainedIntField(
                        Tip("Steps", "Diffusion inference steps."),
                        ref _request.Steps, t2i.Steps.Minimum, t2i.Steps.Maximum, 1);
                    DrawConstrainedFloatField(
                        Tip("Guidance Scale", "Classifier-free guidance scale."),
                        ref _request.GuidanceScale,
                        t2i.GuidanceScale.Minimum, t2i.GuidanceScale.Maximum);
                }
                else
                {
                    _request.Width = EditorGUILayout.IntField(Tip("Width", "Output width in pixels."), _request.Width);
                    _request.Height = EditorGUILayout.IntField(Tip("Height", "Output height in pixels."), _request.Height);
                    _request.Steps = EditorGUILayout.IntField(Tip("Steps", "Diffusion inference steps."), _request.Steps);
                    _request.GuidanceScale = EditorGUILayout.FloatField(
                        Tip("Guidance Scale", "Classifier-free guidance scale."), _request.GuidanceScale);
                    EditorGUILayout.HelpBox("Refresh capabilities to see backend-enforced limits.", MessageType.Info);
                }

                _request.UseExplicitSeed = EditorGUILayout.Toggle(
                    Tip("Use Explicit Seed", "When off, the backend picks a random seed within policy bounds."),
                    _request.UseExplicitSeed);
                using (new EditorGUI.DisabledScope(!_request.UseExplicitSeed))
                {
                    _request.Seed = EditorGUILayout.LongField(
                        Tip("Seed", "Fixed seed for reproducible generations."), _request.Seed);
                }

                _request.OutputName = EditorGUILayout.TextField(
                    Tip("Output Name", "Safe file stem for the imported PNG and metadata."),
                    _request.OutputName);
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawImageToImageSection(GenerationProgress progress)
        {
            _foldImg2Img = EditorGUILayout.BeginFoldoutHeaderGroup(_foldImg2Img, "Image-to-Image Variation");
            if (_foldImg2Img)
            {
                var i2i = progress.Capabilities?.Operations?.ImageToImage;
                var supported = i2i?.Supported == true;
                EditorGUILayout.LabelField(
                    "Uses the selected image as the generation init/latent image and modifies it " +
                    "according to denoising strength. This is not reference-image conditioning " +
                    "(IP-Adapter / style / identity). Reference conditioning is a separate future workflow.",
                    _sectionHelp);

                using (new EditorGUI.DisabledScope(!supported && progress.Capabilities != null))
                {
                    var nextImg2Img = EditorGUILayout.Toggle(
                        Tip(
                            "Enable Image-to-Image",
                            "When enabled, the source image is the starting latent. Denoising strength " +
                            "controls how much it changes. Not a style/identity reference and not masked inpainting."),
                        _request.UseImageToImage);
                    if (nextImg2Img && !_request.UseImageToImage)
                        _request.UseInpainting = false;
                    _request.UseImageToImage = nextImg2Img;

                    using (new EditorGUI.DisabledScope(!_request.UseImageToImage))
                    {
                        var previous = _request.SourceTexture;
                        var next = (Texture2D)EditorGUILayout.ObjectField(
                            Tip(
                                "Source Image",
                                "Init/source image used as the starting latent. PNG/JPEG/WebP on disk " +
                                "or a project Texture2D. Not a reference-conditioning image."),
                            _request.SourceTexture,
                            typeof(Texture2D),
                            false);
                        if (next != previous)
                        {
                            if (_ownsSourceTexture && previous != null)
                                DestroyImmediate(previous);
                            _ownsSourceTexture = false;
                            _request.SourceTexture = next;
                            EnsureMaskMatchesSource();
                        }

                        EditorGUILayout.BeginHorizontal();
                        if (GUILayout.Button(
                                Tip("Load From Disk…", "Open a PNG, JPEG, or WebP file as the img2img init image.")))
                        {
                            var path = EditorUtility.OpenFilePanel(
                                "Select source image (init image)", "", "png,jpg,jpeg,webp");
                            if (!string.IsNullOrEmpty(path))
                                LoadSourceImageFromDisk(path);
                        }

                        using (new EditorGUI.DisabledScope(_request.SourceTexture == null))
                        {
                            if (GUILayout.Button("Clear Source"))
                            {
                                DestroyOwnedSourceTexture();
                                _request.SourceTexture = null;
                            }
                        }

                        EditorGUILayout.EndHorizontal();

                        if (_request.SourceTexture != null)
                        {
                            var previewSize = Mathf.Min(160f, EditorGUIUtility.currentViewWidth - 48f);
                            var rect = GUILayoutUtility.GetRect(
                                previewSize, previewSize, GUILayout.ExpandWidth(false), GUILayout.ExpandHeight(false));
                            EditorGUI.DrawPreviewTexture(rect, _request.SourceTexture, null, ScaleMode.ScaleToFit);
                            EditorGUILayout.LabelField(
                                $"{_request.SourceTexture.width}×{_request.SourceTexture.height}  {_request.SourceTexture.name}",
                                _sectionHelp);
                        }

                        var minStrength = i2i?.DenoisingStrength != null ? i2i.DenoisingStrength.Minimum : 0f;
                        var maxStrength = i2i?.DenoisingStrength != null ? i2i.DenoisingStrength.Maximum : 1f;
                        if (maxStrength <= minStrength)
                        {
                            minStrength = 0f;
                            maxStrength = 1f;
                        }

                        _request.DenoisingStrength = EditorGUILayout.Slider(
                            Tip(
                                "Denoising Strength",
                                "How much the source init image is changed. 0 keeps it almost unchanged; " +
                                "1 allows maximum change. This applies only to img2img, not reference conditioning."),
                            _request.DenoisingStrength,
                            minStrength,
                            maxStrength);
                    }
                }

                if (progress.Capabilities != null && !supported)
                {
                    EditorGUILayout.HelpBox(
                        "The current model/backend does not support image_to_image. " +
                        "Img2img is not silently converted to text-to-image.",
                        MessageType.Warning);
                    _request.UseImageToImage = false;
                }
                else if (_request.UseImageToImage && _request.SourceTexture == null)
                {
                    EditorGUILayout.HelpBox(
                        "Select a source image (init image) before generating an image-to-image variation.",
                        MessageType.Warning);
                }
                else if (_request.UseImageToImage)
                {
                    EditorGUILayout.HelpBox(
                        "Generation will use image_to_image. Status and metadata will record the operation, " +
                        "denoising strength, and source-image dimensions/format.",
                        MessageType.Info);
                }
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawInpaintingSection(GenerationProgress progress)
        {
            _foldInpaint = EditorGUILayout.BeginFoldoutHeaderGroup(_foldInpaint, "Masked Inpainting");
            if (_foldInpaint)
            {
                var inpaint = progress.Capabilities?.Operations?.Inpainting;
                var supported = inpaint?.Supported == true;
                var convention = inpaint?.MaskImage?.Convention ?? MaskBrushUtility.ConventionId;
                EditorGUILayout.LabelField(
                    "Regenerates only the masked region of the source image. " +
                    "White = regenerate; black = keep original pixels. Mask alpha is ignored. " +
                    "This is not full-frame img2img and not reference-image conditioning.",
                    _sectionHelp);

                using (new EditorGUI.DisabledScope(!supported && progress.Capabilities != null))
                {
                    var nextInpaint = EditorGUILayout.Toggle(
                        Tip(
                            "Enable Inpainting",
                            "Masked regeneration of the source image. Mutually exclusive with image-to-image."),
                        _request.UseInpainting);
                    if (nextInpaint && !_request.UseInpainting)
                        _request.UseImageToImage = false;
                    _request.UseInpainting = nextInpaint;

                    using (new EditorGUI.DisabledScope(!_request.UseInpainting))
                    {
                        DrawSharedSourcePicker("Inpaint Source", "Image whose unmasked pixels are kept.");
                        DrawMaskPicker();
                        DrawMaskPreviews();
                        DrawMaskBrushControls();

                        var minStrength = inpaint?.DenoisingStrength != null ? inpaint.DenoisingStrength.Minimum : 0f;
                        var maxStrength = inpaint?.DenoisingStrength != null ? inpaint.DenoisingStrength.Maximum : 1f;
                        if (maxStrength <= minStrength)
                        {
                            minStrength = 0f;
                            maxStrength = 1f;
                        }

                        _request.DenoisingStrength = EditorGUILayout.Slider(
                            Tip(
                                "Denoising Strength",
                                "How strongly the masked region is regenerated. 0 keeps it closer to the source; " +
                                "1 allows maximum change inside the white mask."),
                            _request.DenoisingStrength,
                            minStrength,
                            maxStrength);
                    }
                }

                if (progress.Capabilities != null && !supported)
                {
                    EditorGUILayout.HelpBox(
                        "The current model/backend does not support inpainting. " +
                        "Inpainting is not silently converted to image-to-image or text-to-image.",
                        MessageType.Warning);
                    _request.UseInpainting = false;
                }
                else if (_request.UseInpainting && _request.SourceTexture == null)
                {
                    EditorGUILayout.HelpBox(
                        "Select a source image before painting or loading a mask.",
                        MessageType.Warning);
                }
                else if (_request.UseInpainting && _request.MaskTexture == null)
                {
                    EditorGUILayout.HelpBox(
                        "Load a mask from disk or paint one over the source. White regenerates; black is kept.",
                        MessageType.Warning);
                }
                else if (_request.UseInpainting &&
                         _request.SourceTexture != null &&
                         _request.MaskTexture != null &&
                         !MaskBrushUtility.DimensionsMatch(_request.SourceTexture, _request.MaskTexture))
                {
                    EditorGUILayout.HelpBox(
                        "Source and mask dimensions must match. Clear the mask and paint a new one, " +
                        "or load a mask with the same size as the source.",
                        MessageType.Error);
                }
                else if (_request.UseInpainting &&
                         _request.MaskTexture != null &&
                         !MaskBrushUtility.HasInpaintRegion(_request.MaskTexture))
                {
                    EditorGUILayout.HelpBox(
                        "The mask is entirely black (keep). Paint white over the region to regenerate.",
                        MessageType.Warning);
                }
                else if (_request.UseInpainting)
                {
                    EditorGUILayout.HelpBox(
                        $"Generation will use inpainting ({convention}: white regenerates, black is kept). " +
                        "Status and metadata record the operation, source, and mask.",
                        MessageType.Info);
                }
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawSharedSourcePicker(string label, string tooltip)
        {
            var previous = _request.SourceTexture;
            var next = (Texture2D)EditorGUILayout.ObjectField(
                Tip(label, tooltip),
                _request.SourceTexture,
                typeof(Texture2D),
                false);
            if (next != previous)
            {
                if (_ownsSourceTexture && previous != null)
                    DestroyImmediate(previous);
                _ownsSourceTexture = false;
                _request.SourceTexture = next;
                EnsureMaskMatchesSource();
            }

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button(Tip("Load Source From Disk…", "Open a PNG, JPEG, or WebP file as the inpaint source.")))
            {
                var path = EditorUtility.OpenFilePanel(
                    "Select source image", "", "png,jpg,jpeg,webp");
                if (!string.IsNullOrEmpty(path))
                    LoadSourceImageFromDisk(path);
            }

            using (new EditorGUI.DisabledScope(_request.SourceTexture == null))
            {
                if (GUILayout.Button("Clear Source"))
                {
                    DestroyOwnedSourceTexture();
                    DestroyOwnedMaskTexture();
                    DestroyPreview(ref _maskOverlay);
                }
            }

            EditorGUILayout.EndHorizontal();

            if (_request.SourceTexture != null)
            {
                EditorGUILayout.LabelField(
                    $"{_request.SourceTexture.width}×{_request.SourceTexture.height}  {_request.SourceTexture.name}",
                    _sectionHelp);
            }
        }

        void DrawMaskPicker()
        {
            var previous = _request.MaskTexture;
            var next = (Texture2D)EditorGUILayout.ObjectField(
                Tip(
                    "Mask Image",
                    "White regenerates; black is kept. RGB luminance is used; alpha is ignored."),
                _request.MaskTexture,
                typeof(Texture2D),
                false);
            if (next != previous)
            {
                if (_ownsMaskTexture && previous != null)
                    DestroyImmediate(previous);
                _ownsMaskTexture = false;
                _request.MaskTexture = next;
                _maskOverlayDirty = true;
            }

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button(Tip("Load Mask From Disk…", "Open a PNG, JPEG, or WebP mask. Dimensions must match the source.")))
            {
                var path = EditorUtility.OpenFilePanel(
                    "Select inpaint mask (white=regenerate)", "", "png,jpg,jpeg,webp");
                if (!string.IsNullOrEmpty(path))
                    LoadMaskImageFromDisk(path);
            }

            using (new EditorGUI.DisabledScope(_request.SourceTexture == null))
            {
                if (GUILayout.Button(Tip("New Mask", "Create a black (keep-all) mask matching the source, then paint white to inpaint.")))
                    ResetMaskToSource();
            }

            using (new EditorGUI.DisabledScope(_request.MaskTexture == null))
            {
                if (GUILayout.Button(Tip("Clear Mask", "Fill the mask with black (keep all).")))
                {
                    EnsureEditableMask();
                    MaskBrushUtility.ClearToKeep(_request.MaskTexture);
                    _maskOverlayDirty = true;
                }
            }

            EditorGUILayout.EndHorizontal();
        }

        void DrawMaskPreviews()
        {
            if (_request.SourceTexture == null && _request.MaskTexture == null)
                return;

            var previewSize = Mathf.Min(160f, (EditorGUIUtility.currentViewWidth - 64f) / 3f);
            EditorGUILayout.BeginHorizontal();
            DrawLabeledPreview("Source", _request.SourceTexture, previewSize);
            DrawLabeledPreview("Mask", _request.MaskTexture, previewSize);
            if (_request.SourceTexture != null && _request.MaskTexture != null &&
                MaskBrushUtility.DimensionsMatch(_request.SourceTexture, _request.MaskTexture))
            {
                if (_maskOverlayDirty || _maskOverlay == null)
                    RebuildMaskOverlay();
                DrawLabeledPreview("Overlay (white=inpaint)", _maskOverlay, previewSize);
            }

            EditorGUILayout.EndHorizontal();
        }

        void DrawLabeledPreview(string label, Texture2D texture, float previewSize)
        {
            EditorGUILayout.BeginVertical(GUILayout.Width(previewSize + 8f));
            EditorGUILayout.LabelField(label, _sectionHelp);
            var rect = GUILayoutUtility.GetRect(
                previewSize, previewSize, GUILayout.ExpandWidth(false), GUILayout.ExpandHeight(false));
            if (texture != null)
                EditorGUI.DrawPreviewTexture(rect, texture, null, ScaleMode.ScaleToFit);
            else
                EditorGUI.DrawRect(rect, new Color(0.15f, 0.15f, 0.15f));
            EditorGUILayout.EndVertical();
        }

        void DrawMaskBrushControls()
        {
            if (_request.SourceTexture == null)
                return;

            EditorGUILayout.LabelField(
                "Paint on the source: white regenerates, black keeps the original. " +
                "Click and drag on the paint canvas below.",
                _sectionHelp);
            _request.MaskBrushPaintsInpaint = EditorGUILayout.Toggle(
                Tip("Paint Inpaint (White)", "On: paint the region to regenerate. Off: erase back to keep (black)."),
                _request.MaskBrushPaintsInpaint);
            _request.MaskBrushSize = EditorGUILayout.IntSlider(
                Tip("Brush Size", "Radius in source pixels."),
                Mathf.Clamp(_request.MaskBrushSize, 1, 128),
                1,
                128);
            _request.MaskOverlayOpacity = EditorGUILayout.Slider(
                Tip("Overlay Opacity", "How strongly the red inpaint overlay is drawn over the source."),
                _request.MaskOverlayOpacity,
                0.1f,
                0.9f);

            EnsureEditableMask();
            if (_maskOverlayDirty || _maskOverlay == null)
                RebuildMaskOverlay();

            var canvasSize = Mathf.Min(280f, EditorGUIUtility.currentViewWidth - 48f);
            var canvas = _maskOverlay != null ? _maskOverlay : _request.SourceTexture;
            var rect = GUILayoutUtility.GetRect(
                canvasSize, canvasSize, GUILayout.ExpandWidth(false), GUILayout.ExpandHeight(false));
            if (canvas != null)
                EditorGUI.DrawPreviewTexture(rect, canvas, null, ScaleMode.ScaleToFit);

            var current = Event.current;
            if (rect.Contains(current.mousePosition) &&
                (current.type == EventType.MouseDown || current.type == EventType.MouseDrag) &&
                current.button == 0 &&
                _request.MaskTexture != null)
            {
                var fitted = FittedPreviewRect(rect, _request.MaskTexture.width, _request.MaskTexture.height);
                if (fitted.Contains(current.mousePosition))
                {
                    var pixel = MaskBrushUtility.GuiPointToTexturePixel(
                        fitted,
                        current.mousePosition,
                        _request.MaskTexture.width,
                        _request.MaskTexture.height);
                    MaskBrushUtility.PaintCircle(
                        _request.MaskTexture,
                        pixel.x,
                        pixel.y,
                        _request.MaskBrushSize,
                        _request.MaskBrushPaintsInpaint);
                    _maskOverlayDirty = true;
                    current.Use();
                    GUI.changed = true;
                    Repaint();
                }
            }
        }

        static Rect FittedPreviewRect(Rect outer, int imageWidth, int imageHeight)
        {
            if (imageWidth <= 0 || imageHeight <= 0)
                return outer;
            var imageAspect = imageWidth / (float)imageHeight;
            var rectAspect = outer.width / outer.height;
            if (imageAspect > rectAspect)
            {
                var height = outer.width / imageAspect;
                return new Rect(outer.x, outer.y + (outer.height - height) * 0.5f, outer.width, height);
            }

            var width = outer.height * imageAspect;
            return new Rect(outer.x + (outer.width - width) * 0.5f, outer.y, width, outer.height);
        }

        void LoadSourceImageFromDisk(string path)
        {
            try
            {
                var bytes = File.ReadAllBytes(path);
                var texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                if (!texture.LoadImage(bytes))
                {
                    DestroyImmediate(texture);
                    EditorUtility.DisplayDialog(
                        "Source Image",
                        "Could not decode the selected file. Use a valid PNG, JPEG, or WebP image.",
                        "OK");
                    return;
                }

                texture.name = Path.GetFileName(path);
                if (_ownsSourceTexture && _request.SourceTexture != null)
                    DestroyImmediate(_request.SourceTexture);
                _request.SourceTexture = texture;
                _ownsSourceTexture = true;
                EnsureMaskMatchesSource();
            }
            catch (Exception ex)
            {
                EditorUtility.DisplayDialog("Source Image", "Failed to load the file: " + ex.Message, "OK");
            }
        }

        void DestroyOwnedSourceTexture()
        {
            if (_ownsSourceTexture && _request != null && _request.SourceTexture != null)
            {
                DestroyImmediate(_request.SourceTexture);
                _request.SourceTexture = null;
            }

            _ownsSourceTexture = false;
            _maskOverlayDirty = true;
        }

        void DestroyOwnedMaskTexture()
        {
            if (_ownsMaskTexture && _request != null && _request.MaskTexture != null)
            {
                DestroyImmediate(_request.MaskTexture);
                _request.MaskTexture = null;
            }

            _ownsMaskTexture = false;
            _maskOverlayDirty = true;
        }

        void EnsureMaskMatchesSource()
        {
            _maskOverlayDirty = true;
            if (_request?.SourceTexture == null)
            {
                DestroyOwnedMaskTexture();
                DestroyPreview(ref _maskOverlay);
                return;
            }

            if (_request.MaskTexture != null &&
                MaskBrushUtility.DimensionsMatch(_request.SourceTexture, _request.MaskTexture))
                return;

            ResetMaskToSource();
        }

        void ResetMaskToSource()
        {
            if (_request?.SourceTexture == null)
                return;
            var created = MaskBrushUtility.CreateKeepMask(
                _request.SourceTexture.width, _request.SourceTexture.height);
            if (_ownsMaskTexture && _request.MaskTexture != null)
                DestroyImmediate(_request.MaskTexture);
            _request.MaskTexture = created;
            _ownsMaskTexture = true;
            _maskOverlayDirty = true;
        }

        void EnsureEditableMask()
        {
            if (_request?.SourceTexture == null)
                return;
            if (_request.MaskTexture == null)
            {
                ResetMaskToSource();
                return;
            }

            if (!_request.MaskTexture.isReadable ||
                !MaskBrushUtility.DimensionsMatch(_request.SourceTexture, _request.MaskTexture))
            {
                var converted = MaskBrushUtility.ToLuminanceMask(_request.MaskTexture);
                if (_ownsMaskTexture && _request.MaskTexture != null)
                    DestroyImmediate(_request.MaskTexture);
                _request.MaskTexture = converted;
                _ownsMaskTexture = true;
                _maskOverlayDirty = true;
            }
        }

        void LoadMaskImageFromDisk(string path)
        {
            try
            {
                var bytes = File.ReadAllBytes(path);
                var texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                if (!texture.LoadImage(bytes))
                {
                    DestroyImmediate(texture);
                    EditorUtility.DisplayDialog(
                        "Mask Image",
                        "Could not decode the selected file. Use a valid PNG, JPEG, or WebP image.",
                        "OK");
                    return;
                }

                if (_request.SourceTexture != null &&
                    (texture.width != _request.SourceTexture.width ||
                     texture.height != _request.SourceTexture.height))
                {
                    var message =
                        $"Mask is {texture.width}×{texture.height} but the source is " +
                        $"{_request.SourceTexture.width}×{_request.SourceTexture.height}. " +
                        "They must match exactly; the mask will not be stretched.";
                    DestroyImmediate(texture);
                    EditorUtility.DisplayDialog("Mask Image", message, "OK");
                    return;
                }

                var luminance = MaskBrushUtility.ToLuminanceMask(texture, Path.GetFileName(path));
                DestroyImmediate(texture);
                if (_ownsMaskTexture && _request.MaskTexture != null)
                    DestroyImmediate(_request.MaskTexture);
                _request.MaskTexture = luminance;
                _ownsMaskTexture = true;
                _maskOverlayDirty = true;
            }
            catch (Exception ex)
            {
                EditorUtility.DisplayDialog("Mask Image", "Failed to load the file: " + ex.Message, "OK");
            }
        }

        void RebuildMaskOverlay()
        {
            DestroyPreview(ref _maskOverlay);
            if (_request?.SourceTexture == null || _request.MaskTexture == null)
            {
                _maskOverlayDirty = false;
                return;
            }

            _maskOverlay = MaskBrushUtility.BuildOverlay(
                _request.SourceTexture,
                _request.MaskTexture,
                new Color(0.9f, 0.15f, 0.15f),
                _request.MaskOverlayOpacity);
            _maskOverlayDirty = false;
        }

        void DrawProcessingSection(GenerationProgress progress)
        {
            var isSpriteOrIcon = _request.AssetType == "sprite" || _request.AssetType == "icon";
            var isTileable = _request.AssetType == "texture" && IsTileableProfileSelected();
            if (!isSpriteOrIcon && !isTileable)
                return;

            _foldProcessing = EditorGUILayout.BeginFoldoutHeaderGroup(_foldProcessing, "Processing");
            if (_foldProcessing)
            {
                var t2i = progress.Capabilities?.Operations?.TextToImage;
                if (isSpriteOrIcon)
                    DrawSpriteProcessing(t2i);
                if (isTileable)
                    DrawTileableProcessing(t2i);
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawSpriteProcessing(TextToImageCapabilities t2i)
        {
            EditorGUILayout.LabelField("Transparent Background", EditorStyles.miniBoldLabel);
            EditorGUILayout.LabelField(
                "Diffusion models do not emit alpha. Transparency uses local rembg post-processing, " +
                "then alpha cleanup. Enabled only for sprite/icon asset types.",
                _sectionHelp);

            var bgAvailable = t2i?.Processing?.BackgroundRemoval?.Available == true;
            var strategyIndex = _request.TransparencyStrategy == "background_removal" ? 1 : 0;
            strategyIndex = EditorGUILayout.Popup(
                Tip(
                    "Transparency Strategy",
                    "none = opaque RGB. background_removal = local rembg alpha (not a cloud API)."),
                strategyIndex,
                new[] { "none (opaque)", "background_removal (local rembg)" });
            _request.TransparencyStrategy = strategyIndex == 1 ? "background_removal" : "none";

            using (new EditorGUI.DisabledScope(_request.TransparencyStrategy != "background_removal"))
            {
                _request.AlphaThreshold = EditorGUILayout.IntSlider(
                    Tip("Alpha Threshold", "Pixels at or below this alpha become fully transparent when cleanup runs."),
                    _request.AlphaThreshold, 0, 255);
                _request.AlphaFeather = EditorGUILayout.IntSlider(
                    Tip("Alpha Feather", "Softens the alpha edge after thresholding (0 = hard cut)."),
                    _request.AlphaFeather, 0, 64);
                _request.RemoveNearTransparent = EditorGUILayout.Toggle(
                    Tip("Remove Near Transparent", "Force near-zero alpha pixels to fully transparent."),
                    _request.RemoveNearTransparent);
                _request.ZeroRgbWhenTransparent = EditorGUILayout.Toggle(
                    Tip("Zero RGB When Transparent", "Clear RGB on fully transparent pixels to avoid fringe colors."),
                    _request.ZeroRgbWhenTransparent);
            }

            _request.PixelsPerUnit = EditorGUILayout.FloatField(
                Tip("Pixels Per Unit", "Unity sprite pixels-per-unit applied on import."),
                _request.PixelsPerUnit);
            var pivotChoices = new[] { "center", "bottom_center", "custom" };
            var pivotIndex = Array.IndexOf(pivotChoices, _request.PivotMode);
            if (pivotIndex < 0) pivotIndex = 0;
            _request.PivotMode = pivotChoices[EditorGUILayout.Popup(
                Tip("Pivot Mode", "Sprite pivot alignment written to the TextureImporter."),
                pivotIndex,
                pivotChoices)];
            if (_request.PivotMode == "custom")
            {
                _request.CustomPivotX = EditorGUILayout.Slider(
                    Tip("Custom Pivot X", "Normalized pivot X (0–1)."), _request.CustomPivotX, 0f, 1f);
                _request.CustomPivotY = EditorGUILayout.Slider(
                    Tip("Custom Pivot Y", "Normalized pivot Y (0–1)."), _request.CustomPivotY, 0f, 1f);
            }

            _request.AtlasHint = EditorGUILayout.TextField(
                Tip("Atlas Hint", "Optional metadata hint for future atlas grouping (not auto-atlased)."),
                _request.AtlasHint);

            if (_request.TransparencyStrategy == "background_removal" && !bgAvailable)
            {
                var reason = t2i?.Processing?.BackgroundRemoval?.UnavailableReason
                             ?? "Background removal is unavailable on the current backend.";
                EditorGUILayout.HelpBox(
                    reason + "\nSwitch strategy to none for opaque sprites, or install rembg and set " +
                    "BACKGROUND_REMOVAL_ENABLED=true, then refresh capabilities.",
                    MessageType.Error);
            }
            else if (_request.TransparencyStrategy == "none")
            {
                EditorGUILayout.HelpBox(
                    "Opaque output. Choose background_removal to produce alpha via local rembg.",
                    MessageType.Info);
            }
            else
            {
                EditorGUILayout.HelpBox(
                    "Transparent PNG will be written with alpha preserved through import " +
                    "(Alpha Is Transparency + FromInput).",
                    MessageType.Info);
            }
        }

        void DrawTileableProcessing(TextToImageCapabilities t2i)
        {
            EditorGUILayout.LabelField("Tileable / AI Seam Repair", EditorStyles.miniBoldLabel);
            EditorGUILayout.LabelField(
                "Generate at 512×512 → optional local AI seam repair (circular offset + center-cross inpaint) → " +
                "import with Repeat wrap. Repair runs on the backend during Generate only — not in the inspect tools below.",
                _sectionHelp);

            _request.Tileable = EditorGUILayout.Toggle(
                Tip("Tileable Workflow", "Marks the request for tileable provenance and diagnostics."),
                _request.Tileable);
            _request.ApplySeamCorrection = EditorGUILayout.Toggle(
                Tip(
                    "Apply AI Seam Repair",
                    "When enabled, the backend runs local Diffusers inpainting after txt2img. " +
                    "Requires 512×512 and an available inpaint model. Soft-blend is not used as a success path."),
                _request.ApplySeamCorrection);

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

            using (new EditorGUI.DisabledScope(!_request.ApplySeamCorrection))
            {
                _request.SeamBlendWidth = EditorGUILayout.IntSlider(
                    Tip("Seam Mask Width", "Width of the center-cross inpaint mask in offset space."),
                    _request.SeamBlendWidth, seamMin, seamMax);
            }

            _request.PaletteReductionEnabled = EditorGUILayout.Toggle(
                Tip("Palette Reduction", "Optional median-cut palette reduction after seam repair (alpha preserved)."),
                _request.PaletteReductionEnabled);
            using (new EditorGUI.DisabledScope(!_request.PaletteReductionEnabled))
            {
                _request.PaletteColorCount = EditorGUILayout.IntSlider(
                    Tip("Palette Colors", "Target color count when palette reduction is enabled."),
                    _request.PaletteColorCount, 2, 256);
            }

            if (_request.ApplySeamCorrection)
            {
                if (_request.Width != 512 || _request.Height != 512)
                    EditorGUILayout.HelpBox("AI seam repair requires exactly 512×512.", MessageType.Error);
                if (tileableCaps != null && !tileableCaps.AiInpaintAvailable)
                    EditorGUILayout.HelpBox(
                        "Local seam inpainting is unavailable. Enable SEAM_INPAINT_ENABLED and ensure the " +
                        "inpaint model can load, or disable AI seam repair.",
                        MessageType.Error);
                else
                    EditorGUILayout.HelpBox(
                        "On generate, Status will report whether seam repair was requested, applied, and which implementation ran.",
                        MessageType.Info);
            }
        }

        void DrawImportSection()
        {
            _foldImport = EditorGUILayout.BeginFoldoutHeaderGroup(_foldImport, "Unity Import");
            if (_foldImport)
            {
                _request.DestinationFolder = EditorGUILayout.TextField(
                    Tip("Destination Folder", "Project-relative Assets/ folder for the imported PNG."),
                    _request.DestinationFolder);
                _request.ImportProfileId = EditorGUILayout.TextField(
                    Tip("Import Profile ID", "Primary import profile id from the catalog."),
                    _request.ImportProfileId);
                var previousKind = _request.ImportProfile;
                _request.ImportProfile = (TextureImportProfileKind)EditorGUILayout.EnumPopup(
                    Tip("Legacy Import Kind", "Secondary fallback used only when the profile id is empty."),
                    _request.ImportProfile);
                if (_request.ImportProfile != previousKind)
                    _request.ImportProfileId = TextureImportProfile.FromKind(_request.ImportProfile).Id;

                _request.CreateMaterial = EditorGUILayout.Toggle(
                    Tip("Create Material", "Also create a material referencing the imported texture."),
                    _request.CreateMaterial);
                using (new EditorGUI.DisabledScope(!_request.CreateMaterial))
                {
                    _request.MaterialDestinationFolder = EditorGUILayout.TextField(
                        Tip("Material Destination", "Folder for the optional material asset."),
                        _request.MaterialDestinationFolder);
                    _request.ShaderName = EditorGUILayout.TextField(
                        Tip("Shader", "Shader name for the created material."),
                        _request.ShaderName);
                }
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
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

            _foldTileable = EditorGUILayout.BeginFoldoutHeaderGroup(_foldTileable, "Tileable Inspect / Preview");
            if (_foldTileable)
            {
                EditorGUILayout.LabelField(
                    "Pick any project texture to compare the single tile with a 3×3 tiled preview. " +
                    "AI seam repair runs on generate only — use Compare to load a second texture (e.g. pre-repair).",
                    _sectionHelp);

                DrawInspectTexturePicker(progress);

                if (_workingPixels == null || string.IsNullOrEmpty(_workingTexturePath))
                {
                    EditorGUILayout.HelpBox(
                        "No texture loaded yet. Assign a Texture2D above, use Project Selection, or generate/import first.",
                        MessageType.Info);
                    EditorGUILayout.EndFoldoutHeaderGroup();
                    return;
                }

                EditorGUILayout.LabelField("Working", _workingTexturePath, _sectionHelp);
                _showOffsetPreview = EditorGUILayout.Toggle(
                    Tip("Show Offset Preview (50%)", "Circular-shift preview highlighting wrap seams."),
                    _showOffsetPreview);

                if (_seamDiagnostics != null)
                {
                    EditorGUILayout.LabelField(
                        "Edge RGB",
                        $"H={_seamDiagnostics.HorizontalScore:0.###}  V={_seamDiagnostics.VerticalScore:0.###}  " +
                        $"Combined={_seamDiagnostics.CombinedScore:0.###} ({_seamDiagnostics.QualityLabel})",
                        _sectionHelp);
                }

                if (_wrapDiagnostics != null)
                {
                    EditorGUILayout.LabelField(
                        "Wrap Δ",
                        $"H={_wrapDiagnostics.HorizontalRatio:0.00}x  V={_wrapDiagnostics.VerticalRatio:0.00}x normal gradient",
                        _sectionHelp);
                }

                var previewSize = Mathf.Clamp(position.width / 3.5f, 72f, 140f);
                EditorGUILayout.LabelField("Primary (working texture)", EditorStyles.miniBoldLabel);
                EditorGUILayout.BeginHorizontal();
                DrawPreviewColumn("Single tile", _previewOriginal, previewSize);
                if (_showOffsetPreview)
                    DrawPreviewColumn("Offset 50%", _previewOffset, previewSize);
                DrawPreviewColumn("3×3 Tiled", _previewTiled, previewSize);
                EditorGUILayout.EndHorizontal();

                DrawCompareTexturePicker(previewSize);

                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("Re-Analyze Seams"))
                    RefreshDiagnosticsAndPreviews();
                if (GUILayout.Button(
                        Tip("Apply Palette Reduction", "Writes a sibling palette-reduced PNG; original preserved.")))
                    ApplyPaletteToWorking();
                EditorGUILayout.EndHorizontal();

                _request.PaletteColorCount = EditorGUILayout.IntSlider(
                    Tip("Palette Colors", "Color count for the editor-side palette tool."),
                    _request.PaletteColorCount, 2, 256);

                EditorGUI.BeginChangeCheck();
                _materialTiling = EditorGUILayout.IntSlider(
                    Tip("Material UV Tiling Preview", "How many repeats to show in the Unity Repeat preview."),
                    _materialTiling, 1, 8);
                if (EditorGUI.EndChangeCheck() && _workingPixels != null)
                    RefreshDiagnosticsAndPreviews();
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

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawInspectTexturePicker(GenerationProgress progress)
        {
            EditorGUI.BeginChangeCheck();
            var next = (Texture2D)EditorGUILayout.ObjectField(
                Tip("Inspect Texture", "Any Texture2D asset in the project. Used for single-tile vs 3×3 compare."),
                _inspectSource,
                typeof(Texture2D),
                false);
            if (EditorGUI.EndChangeCheck())
            {
                _inspectSource = next;
                if (_inspectSource != null)
                    LoadWorkingTexture(AssetDatabase.GetAssetPath(_inspectSource));
            }

            EditorGUILayout.BeginHorizontal();
            var importedPath = progress.ImportedTexturePath;
            using (new EditorGUI.DisabledScope(string.IsNullOrWhiteSpace(importedPath)))
            {
                if (GUILayout.Button(
                        Tip("Use Last Import", "Load the texture imported by the most recent Generate And Import in this window.")))
                {
                    LoadWorkingTexture(importedPath);
                    _inspectSource = AssetDatabase.LoadAssetAtPath<Texture2D>(importedPath);
                }
            }

            var selectionTex = Selection.activeObject as Texture2D;
            using (new EditorGUI.DisabledScope(selectionTex == null))
            {
                if (GUILayout.Button(
                        Tip("Use Project Selection", "Load the Texture2D currently selected in the Project window.")))
                {
                    _inspectSource = selectionTex;
                    LoadWorkingTexture(AssetDatabase.GetAssetPath(selectionTex));
                }
            }

            EditorGUILayout.EndHorizontal();
        }

        void DrawCompareTexturePicker(float previewSize)
        {
            EditorGUI.BeginChangeCheck();
            var next = (Texture2D)EditorGUILayout.ObjectField(
                Tip(
                    "Compare Texture (optional)",
                    "Second texture for side-by-side compare — e.g. unrepaired original vs repaired import."),
                _compareSource,
                typeof(Texture2D),
                false);
            if (EditorGUI.EndChangeCheck())
            {
                _compareSource = next;
                RefreshComparePreviews();
            }

            if (_compareSource == null || _previewCompare == null)
                return;

            EditorGUILayout.LabelField(
                "Compare: " + AssetDatabase.GetAssetPath(_compareSource),
                _sectionHelp);
            EditorGUILayout.BeginHorizontal();
            DrawPreviewColumn("Compare tile", _previewCompare, previewSize);
            DrawPreviewColumn("Compare 3×3", _previewCompareTiled, previewSize);
            EditorGUILayout.EndHorizontal();
        }

        static void DrawPreviewColumn(string label, Texture2D texture, float size)
        {
            EditorGUILayout.BeginVertical(GUILayout.MaxWidth(size + 8), GUILayout.ExpandWidth(true));
            EditorGUILayout.LabelField(label, EditorStyles.miniBoldLabel);
            var rect = GUILayoutUtility.GetRect(size, size, GUILayout.ExpandWidth(true), GUILayout.MaxWidth(size + 8));
            if (texture != null)
                EditorGUI.DrawPreviewTexture(rect, texture, null, ScaleMode.ScaleToFit);
            else
                EditorGUI.DrawRect(rect, new Color(0.15f, 0.15f, 0.15f));
            EditorGUILayout.EndVertical();
        }

        void LoadWorkingTexture(string assetPath)
        {
            if (string.IsNullOrWhiteSpace(assetPath))
                return;

            var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(assetPath);
            if (texture == null)
            {
                EditorUtility.DisplayDialog(
                    "Tileable Tools",
                    "No Texture2D found at:\n" + assetPath,
                    "OK");
                return;
            }

            if (!TileableTextureWorkflow.TryReadPixels(texture, out var pixels, out var width, out var height, out var error))
            {
                EditorUtility.DisplayDialog("Tileable Tools", "Could not read texture pixels: " + error, "OK");
                return;
            }

            _inspectSource = texture;
            _workingTexturePath = assetPath;
            _workingPixels = pixels;
            _workingWidth = width;
            _workingHeight = height;
            _foldTileable = true;
            RefreshDiagnosticsAndPreviews();
        }

        void RefreshDiagnosticsAndPreviews()
        {
            if (_workingPixels == null) return;
            _seamDiagnostics = SeamAnalysis.Analyze(_workingPixels, _workingWidth, _workingHeight);
            _wrapDiagnostics = WrapDiagnostics.Analyze(_workingPixels, _workingWidth, _workingHeight);
            DestroyPreview(ref _previewOriginal);
            DestroyPreview(ref _previewOffset);
            DestroyPreview(ref _previewTiled);
            DestroyPreview(ref _previewMaterialSwatch);
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
            RefreshComparePreviews();
            Repaint();
        }

        void RefreshComparePreviews()
        {
            DestroyPreview(ref _previewCompare);
            DestroyPreview(ref _previewCompareTiled);
            if (_compareSource == null)
                return;

            if (!TileableTextureWorkflow.TryReadPixels(
                    _compareSource, out var pixels, out var width, out var height, out var error))
            {
                EditorUtility.DisplayDialog("Tileable Tools", "Could not read compare texture: " + error, "OK");
                _compareSource = null;
                return;
            }

            _previewCompare = TileableTextureWorkflow.CreatePreviewTexture(
                pixels, width, height, FilterMode.Point);
            var tiled = OffsetWrap.TiledPreview(pixels, width, height, 3);
            _previewCompareTiled = TileableTextureWorkflow.CreatePreviewTexture(
                tiled, width * 3, height * 3, FilterMode.Point);
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

        static void DrawConstrainedIntField(GUIContent label, ref int value, int minimum, int maximum, int multiple)
        {
            var hint = multiple > 1
                ? $"{minimum}–{maximum}, ×{multiple}"
                : $"{minimum}–{maximum}";
            value = EditorGUILayout.IntField(new GUIContent($"{label.text} ({hint})", label.tooltip), value);

            if (value < minimum || value > maximum || (multiple > 1 && value % multiple != 0))
            {
                EditorGUILayout.HelpBox(
                    $"{label.text} must be between {minimum} and {maximum}" +
                    (multiple > 1 ? $" and divisible by {multiple}" : string.Empty) +
                    $" (currently {value}).",
                    MessageType.Warning);
            }
        }

        static void DrawConstrainedFloatField(GUIContent label, ref float value, float minimum, float maximum)
        {
            value = EditorGUILayout.FloatField(
                new GUIContent($"{label.text} ({minimum:0.#}–{maximum:0.#})", label.tooltip), value);

            if (value < minimum || value > maximum)
            {
                EditorGUILayout.HelpBox(
                    $"{label.text} must be between {minimum} and {maximum} (currently {value}).",
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

            if (canGenerate &&
                _request.TransparencyStrategy == "background_removal" &&
                progress.Capabilities?.Operations?.TextToImage?.Processing?.BackgroundRemoval?.Available != true)
            {
                canGenerate = false;
            }

            if (canGenerate &&
                _request.UseImageToImage &&
                progress.Capabilities?.Operations?.ImageToImage?.Supported != true)
            {
                canGenerate = false;
            }

            if (canGenerate && _request.UseImageToImage && _request.SourceTexture == null)
            {
                canGenerate = false;
            }

            if (canGenerate &&
                _request.UseInpainting &&
                progress.Capabilities?.Operations?.Inpainting?.Supported != true)
            {
                canGenerate = false;
            }

            if (canGenerate && _request.UseInpainting &&
                (_request.SourceTexture == null || _request.MaskTexture == null ||
                 !MaskBrushUtility.DimensionsMatch(_request.SourceTexture, _request.MaskTexture) ||
                 !MaskBrushUtility.HasInpaintRegion(_request.MaskTexture)))
            {
                canGenerate = false;
            }

            EditorGUILayout.BeginHorizontal();
            using (new EditorGUI.DisabledScope(busy))
            {
                if (GUILayout.Button(
                        Tip("Check Connection", "GET /health against the configured backend URL."),
                        GUILayout.Height(28)))
                    RunSafe(() => _controller.CheckConnectionAsync());

                using (new EditorGUI.DisabledScope(!canGenerate))
                {
                    if (GUILayout.Button(
                            Tip("Generate And Import", "Submit a job, poll until it finishes, then download and import."),
                            GUILayout.Height(28)))
                        RunSafe(() => _controller.GenerateAndImportAsync(_request));
                }
            }

            using (new EditorGUI.DisabledScope(!busy && string.IsNullOrWhiteSpace(progress.JobId)))
            {
                if (GUILayout.Button(
                        Tip("Cancel Job", "Cancel the active queued or running backend job and stop waiting in Unity."),
                        GUILayout.Height(28)))
                    RunSafe(() => _controller.CancelActiveJobAsync());
            }

            EditorGUILayout.EndHorizontal();

            if (GUILayout.Button(
                    Tip("Open Batch Generation", "Configure multiple prompts, seeds, and variations on the existing job queue."),
                    GUILayout.Height(22)))
                BatchGenerationWindow.Open();

            if (!canGenerate && !busy)
            {
                string reason;
                if (_request.ApplySeamCorrection && (_request.Width != 512 || _request.Height != 512))
                    reason = "Generate is disabled: AI seam repair requires exactly 512×512.";
                else if (_request.ApplySeamCorrection &&
                         progress.Capabilities?.Operations?.TextToImage?.Processing?.Tileable?.AiInpaintAvailable == false)
                    reason = "Generate is disabled: local seam inpainting is unavailable on the backend.";
                else if (_request.TransparencyStrategy == "background_removal" &&
                         progress.Capabilities?.Operations?.TextToImage?.Processing?.BackgroundRemoval?.Available != true)
                {
                    reason = progress.Capabilities?.Operations?.TextToImage?.Processing?.BackgroundRemoval?.UnavailableReason
                             ?? "Generate is disabled: background removal is unavailable.";
                }
                else if (_request.UseImageToImage && progress.Capabilities?.Operations?.ImageToImage?.Supported != true)
                    reason = "Generate is disabled: the current model/backend does not support image_to_image.";
                else if (_request.UseImageToImage && _request.SourceTexture == null)
                    reason = "Generate is disabled: image-to-image requires a source init image.";
                else if (_request.UseInpainting && progress.Capabilities?.Operations?.Inpainting?.Supported != true)
                    reason = "Generate is disabled: the current model/backend does not support inpainting.";
                else if (_request.UseInpainting && _request.SourceTexture == null)
                    reason = "Generate is disabled: inpainting requires a source image.";
                else if (_request.UseInpainting && _request.MaskTexture == null)
                    reason = "Generate is disabled: inpainting requires a mask (white=regenerate, black=keep).";
                else if (_request.UseInpainting &&
                         _request.SourceTexture != null &&
                         _request.MaskTexture != null &&
                         !MaskBrushUtility.DimensionsMatch(_request.SourceTexture, _request.MaskTexture))
                    reason = "Generate is disabled: source and mask dimensions must match.";
                else if (_request.UseInpainting &&
                         _request.MaskTexture != null &&
                         !MaskBrushUtility.HasInpaintRegion(_request.MaskTexture))
                    reason = "Generate is disabled: paint a white inpaint region on the mask.";
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
                OpenFolder(_request.DestinationFolder);

            var pingPath = !string.IsNullOrWhiteSpace(_controller.Progress.ImportedTexturePath)
                ? _controller.Progress.ImportedTexturePath
                : _workingTexturePath;
            using (new EditorGUI.DisabledScope(string.IsNullOrWhiteSpace(pingPath)))
            {
                if (GUILayout.Button(
                        Tip("Ping Texture", "Select and ping the last import, or the texture currently loaded for inspect.")))
                {
                    var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(pingPath);
                    if (texture != null)
                    {
                        Selection.activeObject = texture;
                        EditorGUIUtility.PingObject(texture);
                    }
                }
            }

            using (new EditorGUI.DisabledScope(string.IsNullOrWhiteSpace(_controller.Progress.ImportedTexturePath)))
            {
                if (GUILayout.Button(
                        Tip("Inspect Last Import", "Load the last Generate And Import result into Tileable Inspect / Preview.")))
                {
                    LoadWorkingTexture(_controller.Progress.ImportedTexturePath);
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
            _foldStatus = EditorGUILayout.BeginFoldoutHeaderGroup(_foldStatus, "Status");
            if (_foldStatus)
            {
                EditorGUILayout.LabelField("State", progress.State.ToString());
                EditorGUILayout.LabelField("Message", progress.StatusMessage ?? string.Empty, _sectionHelp);
                EditorGUILayout.LabelField(
                    "Backend",
                    progress.BackendReachable
                        ? $"Reachable (device={progress.ResolvedDevice}, model_loaded={progress.ModelLoaded})"
                        : "Not confirmed / unreachable",
                    _sectionHelp);

                if (!string.IsNullOrWhiteSpace(progress.Operation))
                    EditorGUILayout.LabelField("Operation", progress.Operation, _sectionHelp);
                if (progress.DenoisingStrength.HasValue)
                    EditorGUILayout.LabelField(
                        "Denoising Strength",
                        progress.DenoisingStrength.Value.ToString("0.###"),
                        _sectionHelp);

                if (!string.IsNullOrWhiteSpace(progress.ProcessingSummary))
                    EditorGUILayout.HelpBox(progress.ProcessingSummary, MessageType.Info);

                if (progress.SeamCorrectionRequested == true)
                {
                    var applied = progress.SeamCorrectionApplied == true;
                    EditorGUILayout.LabelField(
                        "AI seam repair",
                        applied
                            ? $"applied ({progress.SeamInpaintImplementation ?? "unknown"})"
                            : "requested but not applied",
                        _sectionHelp);
                }

                if (progress.BackgroundRemovalApplied == true)
                {
                    EditorGUILayout.LabelField(
                        "Background removal",
                        $"applied ({progress.BackgroundRemovalImplementation ?? "unknown"})",
                        _sectionHelp);
                }

                if (!string.IsNullOrWhiteSpace(progress.JobId))
                    EditorGUILayout.LabelField("Job ID", progress.JobId, _sectionHelp);
                if (!string.IsNullOrWhiteSpace(progress.JobState))
                    EditorGUILayout.LabelField(
                        "Job",
                        string.IsNullOrWhiteSpace(progress.JobStage)
                            ? progress.JobState
                            : $"{progress.JobState} / {progress.JobStage}",
                        _sectionHelp);
                if (!string.IsNullOrWhiteSpace(progress.GenerationId))
                    EditorGUILayout.LabelField("Generation ID", progress.GenerationId, _sectionHelp);
                if (progress.Seed.HasValue)
                    EditorGUILayout.LabelField("Seed", progress.Seed.Value.ToString());
                if (progress.ElapsedSeconds.HasValue)
                    EditorGUILayout.LabelField("Backend Elapsed (s)", progress.ElapsedSeconds.Value.ToString("0.###"));
                if (!string.IsNullOrWhiteSpace(progress.RequestId))
                    EditorGUILayout.LabelField("Last Request ID", progress.RequestId, _sectionHelp);
                if (!string.IsNullOrWhiteSpace(progress.ImportedTexturePath))
                    EditorGUILayout.LabelField("Imported Texture", progress.ImportedTexturePath, _sectionHelp);
                if (!string.IsNullOrWhiteSpace(progress.ImportedMaterialPath))
                    EditorGUILayout.LabelField("Imported Material", progress.ImportedMaterialPath, _sectionHelp);
                if (!string.IsNullOrWhiteSpace(progress.MetadataAssetPath))
                    EditorGUILayout.LabelField("Metadata Asset", progress.MetadataAssetPath, _sectionHelp);

                if (progress.ValidationIssues != null && progress.ValidationIssues.Count > 0)
                {
                    foreach (var issue in progress.ValidationIssues)
                        EditorGUILayout.HelpBox(issue.ToString(), MessageType.Warning);
                }

                if (!string.IsNullOrWhiteSpace(progress.ErrorMessage))
                    EditorGUILayout.HelpBox(progress.ErrorMessage, MessageType.Error);

                RepaintIfBusy(progress);
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawHistory(GenerationProgress progress, bool busy)
        {
            _foldHistory = EditorGUILayout.BeginFoldoutHeaderGroup(_foldHistory, "Generation History");
            if (_foldHistory)
            {
                EditorGUILayout.LabelField(
                    "Recent jobs from the local backend queue. Completed jobs can be re-imported; " +
                    "failed jobs can be retried; queued or running jobs can be cancelled.",
                    _sectionHelp);

                EditorGUILayout.BeginHorizontal();
                using (new EditorGUI.DisabledScope(busy))
                {
                    if (GUILayout.Button("Refresh History", GUILayout.Height(22)))
                        RunSafe(() => _controller.RefreshHistoryAsync());
                }
                EditorGUILayout.EndHorizontal();

                var jobs = progress.History;
                if (jobs == null || jobs.Count == 0)
                {
                    EditorGUILayout.HelpBox("No jobs loaded yet. Refresh history after the backend is running.", MessageType.Info);
                }
                else
                {
                    var shown = Math.Min(jobs.Count, 12);
                    for (var i = 0; i < shown; i++)
                    {
                        var job = jobs[i];
                        if (job == null)
                            continue;

                        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                        EditorGUILayout.LabelField(
                            $"{job.State} · {job.GenerationType} · {job.AssetType}",
                            EditorStyles.boldLabel);
                        if (!string.IsNullOrWhiteSpace(job.PromptSummary))
                            EditorGUILayout.LabelField("Prompt", job.PromptSummary, _sectionHelp);
                        var meta = job.CreatedAt ?? string.Empty;
                        if (job.Seed.HasValue)
                            meta += (string.IsNullOrEmpty(meta) ? string.Empty : " · ") + "seed " + job.Seed.Value;
                        if (job.Result != null)
                            meta += " · result " + job.Result.Status;
                        if (!string.IsNullOrEmpty(meta))
                            EditorGUILayout.LabelField(meta, _sectionHelp);
                        if (job.Error != null && !string.IsNullOrWhiteSpace(job.Error.Message))
                            EditorGUILayout.LabelField("Error", job.Error.Code + ": " + job.Error.Message, _sectionHelp);

                        EditorGUILayout.BeginHorizontal();
                        using (new EditorGUI.DisabledScope(busy || !job.CanImport))
                        {
                            if (GUILayout.Button(Tip("Import", "Download and import this completed result into the current destination folder.")))
                                RunSafe(() => _controller.ImportHistoryJobAsync(job.JobId, _request));
                        }

                        using (new EditorGUI.DisabledScope(busy || !job.IsRetryable))
                        {
                            if (GUILayout.Button(Tip("Retry", "Requeue this failed, interrupted, or cancelled job.")))
                                RunSafe(() => _controller.RetryHistoryJobAsync(job.JobId, _request));
                        }

                        using (new EditorGUI.DisabledScope(!job.IsCancellable))
                        {
                            if (GUILayout.Button(Tip("Cancel", "Cancel this queued or running job on the backend.")))
                                RunSafe(() => _controller.CancelHistoryJobAsync(job.JobId));
                        }

                        EditorGUILayout.EndHorizontal();
                        EditorGUILayout.EndVertical();
                    }
                }
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
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
