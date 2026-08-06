using System;
using UnityAiAssets.Editor.Capabilities;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Generation;
using UnityAiAssets.Editor.Importing;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.UI
{
    /// <summary>
    /// Texture generation editor window (Tools &gt; AI Asset Generator).
    /// </summary>
    public sealed class UnityAiAssetGeneratorWindow : EditorWindow
    {
        TextureGenerationController _controller;
        TextureGenerationRequestModel _request;
        Vector2 _scroll;

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

        void EnsureInitialized()
        {
            // EditorWindow serializes fields across domain reloads; plain C# objects
            // become null while a stale "_initialized" flag can remain true.
            if (_controller != null && _request != null)
            {
                return;
            }

            var settings = UnityAiAssetSettings.instance;
            _controller = new TextureGenerationController();
            _request = new TextureGenerationRequestModel
            {
                DestinationFolder = settings.DefaultTextureDirectory,
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
            DrawStatus(progress);
            EditorGUILayout.EndScrollView();
        }

        void DrawCapabilitiesSection(TextureGenerationProgress progress, bool busy)
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

        void DrawRequestFields(TextureGenerationProgress progress)
        {
            var t2i = progress.Capabilities?.Operations?.TextToImage;

            EditorGUILayout.LabelField("Prompt", EditorStyles.boldLabel);
            _request.Prompt = EditorGUILayout.TextArea(_request.Prompt, GUILayout.MinHeight(60));
            if (t2i != null)
            {
                EditorGUILayout.LabelField(
                    "Max prompt length",
                    t2i.Prompt.MaximumLength.ToString(),
                    EditorStyles.miniLabel);
            }

            _request.NegativePrompt = EditorGUILayout.TextField("Negative Prompt", _request.NegativePrompt);
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

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Unity Import", EditorStyles.boldLabel);
            _request.DestinationFolder = EditorGUILayout.TextField("Destination Folder", _request.DestinationFolder);
            _request.ImportProfile = (TextureImportProfileKind)EditorGUILayout.EnumPopup(
                "Texture Import Profile",
                _request.ImportProfile);
            _request.CreateMaterial = EditorGUILayout.Toggle("Create Material", _request.CreateMaterial);
            using (new EditorGUI.DisabledScope(!_request.CreateMaterial))
            {
                _request.MaterialDestinationFolder = EditorGUILayout.TextField(
                    "Material Destination",
                    _request.MaterialDestinationFolder);
                _request.ShaderName = EditorGUILayout.TextField("Shader", _request.ShaderName);
            }
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

        void DrawActions(TextureGenerationProgress progress, bool busy)
        {
            var canGenerate = progress.CanGenerate;

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
                EditorGUILayout.HelpBox(GenerateUnavailableReason(progress), MessageType.Warning);
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

        static string GenerateUnavailableReason(TextureGenerationProgress progress)
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

        void DrawStatus(TextureGenerationProgress progress)
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

        void RepaintIfBusy(TextureGenerationProgress progress)
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
