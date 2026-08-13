using System;
using System.Collections.Generic;
using System.Linq;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Generation;
using UnityAiAssets.Editor.Importing;
using UnityAiAssets.Editor.Profiles;
using UnityEditor;
using UnityEngine;

namespace UnityAiAssets.Editor.UI
{
    /// <summary>
    /// Batch generation over the existing job queue. Does not run inference itself.
    /// </summary>
    public sealed class BatchGenerationWindow : EditorWindow
    {
        BatchController _controller;
        BatchRequestModel _model;
        ProfileCatalog _catalog;
        GenerationProfileRegistry _profiles;
        Vector2 _scroll;
        Vector2 _jobScroll;
        readonly HashSet<string> _selectedJobIds = new HashSet<string>();
        readonly Dictionary<string, Texture2D> _thumbnails = new Dictionary<string, Texture2D>();
        string _thumbnailJobId;
        bool _foldProfile = true;
        bool _foldPrompts = true;
        bool _foldSeeds = true;
        bool _foldOperation = true;
        bool _foldImport = true;
        bool _foldQueue = true;
        bool _ownsSource;
        bool _ownsMask;
        static GUIStyle _help;
        static GUIStyle _wrap;

        [MenuItem("Tools/AI Asset Generator/Batch Generation")]
        public static void Open()
        {
            var window = GetWindow<BatchGenerationWindow>();
            window.titleContent = new GUIContent("AI Batch Generation");
            window.minSize = new Vector2(380, 520);
            window.Show();
        }

        void OnEnable()
        {
            EnsureInitialized();
            EditorApplication.update += OnEditorUpdate;
            RunSafe(() => _controller.RefreshHistoryAsync());
        }

        void OnDisable()
        {
            EditorApplication.update -= OnEditorUpdate;
            _controller?.StopPolling();
            DestroyThumbnails();
            if (_model?.Shared != null)
            {
                DestroyOwned(ref _ownsSource, ref _model.Shared.SourceTexture);
                DestroyOwned(ref _ownsMask, ref _model.Shared.MaskTexture);
            }
        }

        void OnEditorUpdate()
        {
            if (_controller?.Progress?.Current != null && _controller.Progress.Current.IsActive)
                Repaint();
        }

        void EnsureInitialized()
        {
            if (_controller != null && _model != null)
                return;
            var settings = UnityAiAssetSettings.instance;
            _catalog = new ProfileCatalog();
            _profiles = new GenerationProfileRegistry(
                userRoot: settings.UserProfileDirectoryAbsolute, catalog: _catalog);
            _controller = new BatchController(profileRegistry: _profiles, catalog: _catalog);
            _model = new BatchRequestModel
            {
                Shared =
                {
                    DestinationFolder = settings.DefaultTextureDirectory,
                    AssetType = settings.DefaultAssetType,
                    SelectedProfileId = _catalog.GetAssetType(settings.DefaultAssetType).DefaultGenerationProfileId,
                    ImportProfileId = settings.DefaultImportProfileId,
                    MaterialDestinationFolder = settings.DefaultMaterialDirectory,
                    CreateMaterial = settings.CreateMaterialByDefault,
                    ShaderName = settings.DefaultShaderName
                }
            };
        }

        static void EnsureStyles()
        {
            _help ??= new GUIStyle(EditorStyles.miniLabel) { wordWrap = true };
            _wrap ??= new GUIStyle(EditorStyles.textArea) { wordWrap = true };
        }

        void OnGUI()
        {
            EnsureInitialized();
            EnsureStyles();
            var progress = _controller.Progress;
            var busy = _controller.IsBusy;

            _scroll = EditorGUILayout.BeginScrollView(_scroll);
            EditorGUILayout.LabelField("Batch Generation", EditorStyles.boldLabel);
            EditorGUILayout.LabelField(
                "Expands prompts, seeds, and variations into the existing local job queue. " +
                "One failed job does not fail the batch. Closing this window does not stop queued work.",
                _help);

            DrawProfile(progress);
            DrawPrompts(busy);
            DrawSeeds(progress, busy);
            DrawOperation(progress, busy);
            DrawImport(busy);
            DrawSubmit(progress, busy);
            DrawQueue(progress, busy);
            DrawStatus(progress);
            EditorGUILayout.EndScrollView();
        }

        void DrawProfile(BatchProgress progress)
        {
            _foldProfile = EditorGUILayout.BeginFoldoutHeaderGroup(_foldProfile, "Preset / Profile");
            if (_foldProfile)
            {
                EditorGUILayout.HelpBox(
                    "The selected generation profile supplies prompt templates, negatives, default size, " +
                    "asset type, and import settings. Batch overrides: prompt list, seed mode, variation count, " +
                    "and any generation fields you change below.",
                    MessageType.Info);
                var request = _model.Shared;
                var assetTypes = _catalog.GetAssetTypes().ToArray();
                var assetIndex = Math.Max(0, Array.FindIndex(assetTypes, item => item.Id == request.AssetType));
                var selectedAsset = EditorGUILayout.Popup(
                    Tip("Asset Type", "Applies the asset type's default generation and import profiles to the whole batch."),
                    assetIndex,
                    assetTypes.Select(x => x.DisplayName).ToArray());
                if (selectedAsset != assetIndex)
                {
                    request.AssetType = assetTypes[selectedAsset].Id;
                    request.SelectedProfileId = assetTypes[selectedAsset].DefaultGenerationProfileId;
                }

                var profiles = _profiles.FilterByAssetType(request.AssetType).ToArray();
                if (profiles.Length > 0)
                {
                    var profileIndex = Math.Max(0, Array.FindIndex(profiles, item => item.Id == request.SelectedProfileId));
                    var labels = profiles.Select(profile => profile.DisplayName + " (" + profile.Origin + ")").ToArray();
                    var next = EditorGUILayout.Popup(
                        Tip("Generation Profile", "Applied to every prompt in the batch."),
                        profileIndex,
                        labels);
                    if (next != profileIndex)
                        request.SelectedProfileId = profiles[next].Id;
                    var current = profiles[Math.Min(Math.Max(next, 0), profiles.Length - 1)];
                    EditorGUILayout.LabelField(current.Description, _help);
                    EditorGUILayout.LabelField(
                        "From preset: template, negative, default size/import. Batch overrides: prompts, seeds, variations.",
                        _help);
                }

                request.AdditionalPrompt = EditorGUILayout.TextField(
                    Tip("Additional Prompt", "Appended to every resolved prompt. Override of the preset."),
                    request.AdditionalPrompt ?? string.Empty);
                request.AdditionalNegative = EditorGUILayout.TextField(
                    Tip("Additional Negative", "Appended to the preset negative prompt for the whole batch."),
                    request.AdditionalNegative ?? string.Empty);
                request.Width = EditorGUILayout.IntField(
                    Tip("Width", "Batch-level size override. Leave as the preset default unless you need a different size."),
                    request.Width);
                request.Height = EditorGUILayout.IntField(
                    Tip("Height", "Batch-level size override."), request.Height);
                request.Steps = EditorGUILayout.IntField(Tip("Steps", "Batch-level steps override."), request.Steps);
                request.GuidanceScale = EditorGUILayout.FloatField(
                    Tip("Guidance", "Batch-level guidance override."), request.GuidanceScale);
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawPrompts(bool busy)
        {
            _foldPrompts = EditorGUILayout.BeginFoldoutHeaderGroup(
                _foldPrompts, "Prompts (" + _model.Prompts.Count + ")");
            if (_foldPrompts)
            {
                EditorGUILayout.LabelField(
                    "Each entry is the subject inserted into the selected profile template. Order is preserved.",
                    _help);
                using (new EditorGUI.DisabledScope(busy))
                {
                    for (var i = 0; i < _model.Prompts.Count; i++)
                    {
                        EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                        EditorGUILayout.LabelField("Prompt " + (i + 1), EditorStyles.miniBoldLabel);
                        _model.Prompts[i].Text = EditorGUILayout.TextArea(
                            _model.Prompts[i].Text ?? string.Empty, _wrap, GUILayout.MinHeight(40));
                        EditorGUILayout.BeginHorizontal();
                        if (GUILayout.Button(Tip("Duplicate", "Insert a copy of this prompt after it.")))
                            _model.Prompts.Insert(i + 1, new BatchPromptEntry { Text = _model.Prompts[i].Text });
                        using (new EditorGUI.DisabledScope(_model.Prompts.Count <= 1))
                        {
                            if (GUILayout.Button(Tip("Remove", "Remove this prompt entry.")))
                            {
                                _model.Prompts.RemoveAt(i);
                                EditorGUILayout.EndHorizontal();
                                EditorGUILayout.EndVertical();
                                break;
                            }
                        }

                        EditorGUILayout.EndHorizontal();
                        EditorGUILayout.EndVertical();
                    }

                    if (GUILayout.Button(Tip("Add Prompt", "Append an empty prompt entry.")))
                        _model.Prompts.Add(new BatchPromptEntry());
                }
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawSeeds(BatchProgress progress, bool busy)
        {
            _foldSeeds = EditorGUILayout.BeginFoldoutHeaderGroup(_foldSeeds, "Seeds and Variations");
            if (_foldSeeds)
            {
                using (new EditorGUI.DisabledScope(busy))
                {
                    _model.SeedMode = (BatchSeedModeKind)EditorGUILayout.EnumPopup(
                        Tip("Seed Mode", "Fixed uses one base seed. Random picks a base seed you can reroll. Sequential uses an inclusive range."),
                        _model.SeedMode);
                    if (_model.SeedMode == BatchSeedModeKind.Sequential)
                    {
                        _model.SeedStart = EditorGUILayout.LongField(
                            Tip("Seed Start", "First seed in the inclusive sequential range."), _model.SeedStart);
                        _model.SeedEnd = EditorGUILayout.LongField(
                            Tip("Seed End", "Last seed in the inclusive sequential range. Variations offset by the range size to avoid duplicates."),
                            _model.SeedEnd);
                    }
                    else
                    {
                        EditorGUILayout.BeginHorizontal();
                        _model.Seed = EditorGUILayout.LongField(
                            Tip("Seed", _model.SeedMode == BatchSeedModeKind.Random
                                ? "Random base seed used for preview and submit. Reroll to pick another."
                                : "Fixed base seed. Variations use seed, seed+1, …"),
                            _model.Seed);
                        if (_model.SeedMode == BatchSeedModeKind.Random &&
                            GUILayout.Button(Tip("Reroll", "Pick a new random base seed."), GUILayout.Width(70)))
                            _model.Seed = (uint)UnityEngine.Random.Range(0, int.MaxValue);
                        EditorGUILayout.EndHorizontal();
                    }

                    _model.VariationCount = EditorGUILayout.IntSlider(
                        Tip("Variations", "Extra outputs per prompt/seed. Sequential variations use a stride so seeds do not collide with the requested range."),
                        Math.Max(1, _model.VariationCount), 1,
                        progress.Capabilities?.Batches?.MaximumVariations ?? BatchExpansion.DefaultMaxVariations);
                }

                if (_controller.TryBuildPlan(_model, out var plan, out var errors))
                {
                    EditorGUILayout.HelpBox(
                        plan.JobCount + " jobs will be created.\nSeeds per prompt: " + plan.SeedSummary(),
                        plan.JobCount >= BatchExpansion.WarnJobCount ? MessageType.Warning : MessageType.Info);
                    foreach (var warning in plan.Warnings)
                        EditorGUILayout.HelpBox(warning, MessageType.Warning);
                }
                else
                {
                    EditorGUILayout.HelpBox(string.Join("\n", errors), MessageType.Error);
                }
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawOperation(BatchProgress progress, bool busy)
        {
            _foldOperation = EditorGUILayout.BeginFoldoutHeaderGroup(_foldOperation, "Generation Mode");
            if (_foldOperation)
            {
                var request = _model.Shared;
                using (new EditorGUI.DisabledScope(busy))
                {
                    var img2 = EditorGUILayout.Toggle(
                        Tip("Image-to-Image", "Requires a source image. Applied to every job in the batch."),
                        request.UseImageToImage);
                    if (img2 && !request.UseImageToImage)
                        request.UseInpainting = false;
                    request.UseImageToImage = img2;
                    var inpaint = EditorGUILayout.Toggle(
                        Tip("Inpainting", "Requires source and mask. White regenerates, black is kept."),
                        request.UseInpainting);
                    if (inpaint && !request.UseInpainting)
                        request.UseImageToImage = false;
                    request.UseInpainting = inpaint;

                    if (request.UseImageToImage || request.UseInpainting)
                    {
                        request.SourceTexture = TextureField("Source Image", request.SourceTexture, ref _ownsSource);
                        request.DenoisingStrength = EditorGUILayout.Slider(
                            Tip("Denoising Strength", "How far each job may move from the source."),
                            request.DenoisingStrength, 0f, 1f);
                    }

                    if (request.UseInpainting)
                        request.MaskTexture = TextureField("Mask Image", request.MaskTexture, ref _ownsMask);
                }

                if (request.UseImageToImage && progress.Capabilities?.Operations?.ImageToImage?.Supported != true)
                    EditorGUILayout.HelpBox("Backend does not support image-to-image.", MessageType.Warning);
                if (request.UseInpainting && progress.Capabilities?.Operations?.Inpainting?.Supported != true)
                    EditorGUILayout.HelpBox("Backend does not support inpainting.", MessageType.Warning);
                if (request.UseImageToImage && request.SourceTexture == null)
                    EditorGUILayout.HelpBox("Select a source image before submitting an img2img batch.", MessageType.Warning);
                if (request.UseInpainting && (request.SourceTexture == null || request.MaskTexture == null))
                    EditorGUILayout.HelpBox("Select a source and mask before submitting an inpainting batch.", MessageType.Warning);
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        Texture2D TextureField(string label, Texture2D current, ref bool owns)
        {
            var next = (Texture2D)EditorGUILayout.ObjectField(
                Tip(label, "Shared across every job in the batch."), current, typeof(Texture2D), false);
            if (next != current && owns && current != null)
                DestroyImmediate(current);
            if (next != current)
                owns = false;
            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("Load From Disk…"))
            {
                var path = EditorUtility.OpenFilePanel("Select image", "", "png,jpg,jpeg,webp");
                if (!string.IsNullOrEmpty(path))
                {
                    var bytes = System.IO.File.ReadAllBytes(path);
                    var loaded = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                    if (loaded.LoadImage(bytes))
                    {
                        if (owns && current != null)
                            DestroyImmediate(current);
                        owns = true;
                        next = loaded;
                    }
                    else
                    {
                        DestroyImmediate(loaded);
                    }
                }
            }

            EditorGUILayout.EndHorizontal();
            return next;
        }

        void DrawImport(bool busy)
        {
            _foldImport = EditorGUILayout.BeginFoldoutHeaderGroup(_foldImport, "Import");
            if (_foldImport)
            {
                using (new EditorGUI.DisabledScope(busy))
                {
                    _model.Shared.DestinationFolder = EditorGUILayout.TextField(
                        Tip("Destination", "Unity Assets/ folder for imported PNGs."),
                        _model.Shared.DestinationFolder);
                    _model.Shared.OutputName = EditorGUILayout.TextField(
                        Tip("Output Name", "Base stem. Each job appends _p00_s{seed}_v00 so names stay predictable."),
                        _model.Shared.OutputName);
                    _model.Shared.CreateMaterial = EditorGUILayout.Toggle(
                        Tip("Create Material", "Optional material beside each imported texture."),
                        _model.Shared.CreateMaterial);
                }
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawSubmit(BatchProgress progress, bool busy)
        {
            _controller.TryBuildPlan(_model, out var plan, out _);
            var canSubmit = progress.CapabilitiesUsable &&
                            (progress.Capabilities?.Batches == null || progress.Capabilities.Batches.Supported) &&
                            plan != null && plan.JobCount > 0 &&
                            !(_model.Shared.UseImageToImage && _model.Shared.SourceTexture == null) &&
                            !(_model.Shared.UseInpainting &&
                              (_model.Shared.SourceTexture == null || _model.Shared.MaskTexture == null));
            if (plan != null && plan.JobCount >= BatchExpansion.WarnJobCount)
                EditorGUILayout.HelpBox(
                    "Large batch (" + plan.JobCount + " jobs). The editor stays responsive; jobs still run one at a time on the backend.",
                    MessageType.Warning);

            EditorGUILayout.BeginHorizontal();
            using (new EditorGUI.DisabledScope(busy))
            {
                if (GUILayout.Button("Refresh Capabilities", GUILayout.Height(24)))
                    RunSafe(() => _controller.RefreshCapabilitiesAsync());
            }

            using (new EditorGUI.DisabledScope(busy || !canSubmit))
            {
                if (GUILayout.Button(
                        Tip("Submit Batch", "Expand configuration into normal jobs and enqueue them."),
                        GUILayout.Height(24)))
                {
                    if (plan != null && plan.JobCount >= BatchExpansion.WarnJobCount &&
                        !EditorUtility.DisplayDialog(
                            "Submit Large Batch?",
                            "This will queue " + plan.JobCount + " generation jobs.",
                            "Submit", "Cancel"))
                    {
                        EditorGUILayout.EndHorizontal();
                        return;
                    }

                    RunSafe(() => _controller.SubmitAsync(_model));
                }
            }

            EditorGUILayout.EndHorizontal();
        }

        void DrawQueue(BatchProgress progress, bool busy)
        {
            _foldQueue = EditorGUILayout.BeginFoldoutHeaderGroup(_foldQueue, "Queue");
            if (_foldQueue)
            {
                EditorGUILayout.BeginHorizontal();
                using (new EditorGUI.DisabledScope(busy))
                {
                    if (GUILayout.Button("Refresh Batches"))
                        RunSafe(() => _controller.RefreshHistoryAsync());
                }

                EditorGUILayout.EndHorizontal();
                if (progress.History != null && progress.History.Count > 0)
                {
                    var labels = progress.History.Select(item =>
                        (item.State ?? "?") + " · " + (item.PromptSummary ?? item.BatchId)).ToArray();
                    var currentId = progress.Current?.BatchId;
                    var index = Math.Max(0, Array.FindIndex(progress.History, item => item.BatchId == currentId));
                    var next = EditorGUILayout.Popup("Recent Batches", index, labels);
                    if (next != index && next >= 0 && next < progress.History.Count)
                        RunSafe(() => _controller.SelectBatchAsync(progress.History[next].BatchId));
                }

                var batch = progress.Current;
                if (batch == null)
                {
                    EditorGUILayout.HelpBox(
                        "No batch loaded. Submit one or refresh to reconstruct state from the backend.",
                        MessageType.Info);
                }
                else
                {
                    DrawBatchSummary(batch, busy);
                    DrawJobList(batch, busy);
                }
            }

            EditorGUILayout.EndFoldoutHeaderGroup();
        }

        void DrawBatchSummary(BatchDocument batch, bool busy)
        {
            var counts = batch.Counts ?? new BatchJobCountsInfo();
            EditorGUILayout.LabelField("Batch " + batch.State, EditorStyles.boldLabel);
            EditorGUILayout.LabelField(BatchController.FormatBatchStatus(batch), _help);
            EditorGUILayout.LabelField(
                "Preset: " + (batch.GenerationProfileId ?? "none") +
                " · " + (batch.Operation ?? "text_to_image") +
                " · " + (batch.AssetType ?? "texture"),
                _help);
            if (batch.Progress != null && batch.Progress.TotalJobs > 0)
            {
                var fraction = batch.Progress.FinishedJobs / (float)batch.Progress.TotalJobs;
                EditorGUI.ProgressBar(
                    EditorGUILayout.GetControlRect(GUILayout.Height(18)),
                    fraction,
                    batch.Progress.FinishedJobs + " / " + batch.Progress.TotalJobs + " jobs finished");
            }

            EditorGUILayout.LabelField(
                "Queued " + counts.Queued + " · Running " + counts.Running +
                " · Completed " + counts.Completed + " · Failed " + counts.Failed +
                " · Cancelled " + counts.Cancelled,
                _help);

            EditorGUILayout.BeginHorizontal();
            using (new EditorGUI.DisabledScope(!batch.CanCancel))
            {
                if (GUILayout.Button(Tip("Cancel Batch", "Cancels queued/running jobs. Completed results stay available.")))
                    RunSafe(() => _controller.CancelCurrentAsync());
            }

            using (new EditorGUI.DisabledScope(busy || !batch.CanRetryFailed))
            {
                if (GUILayout.Button(Tip("Retry Failed", "Requeue eligible failed, interrupted, or cancelled jobs.")))
                    RunSafe(() => _controller.RetryFailedAsync());
            }

            using (new EditorGUI.DisabledScope(busy || !batch.HasImportableResults))
            {
                if (GUILayout.Button(Tip("Import All Successful", "Import completed outputs that have not already been imported.")))
                    RunSafe(() => _controller.ImportJobsAsync(batch.Jobs, _model.Shared));
                if (GUILayout.Button(Tip("Import Selected", "Import only the checked successful jobs.")))
                {
                    var selected = batch.Jobs.Where(job => job != null && _selectedJobIds.Contains(job.JobId));
                    RunSafe(() => _controller.ImportJobsAsync(selected, _model.Shared));
                }
            }

            EditorGUILayout.EndHorizontal();
        }

        void DrawJobList(BatchDocument batch, bool busy)
        {
            EditorGUILayout.Space(4);
            EditorGUILayout.LabelField("Jobs", EditorStyles.miniBoldLabel);
            _jobScroll = EditorGUILayout.BeginScrollView(_jobScroll, GUILayout.MinHeight(180), GUILayout.MaxHeight(360));
            foreach (var job in batch.Jobs)
            {
                if (job == null)
                    continue;
                EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                EditorGUILayout.BeginHorizontal();
                var selected = _selectedJobIds.Contains(job.JobId);
                var nextSelected = EditorGUILayout.Toggle(selected, GUILayout.Width(18));
                if (nextSelected != selected)
                {
                    if (nextSelected)
                        _selectedJobIds.Add(job.JobId);
                    else
                        _selectedJobIds.Remove(job.JobId);
                }

                EditorGUILayout.LabelField(
                    job.State + " · seed " + (job.Seed.HasValue ? job.Seed.Value.ToString() : "?") +
                    (job.VariationIndex.HasValue ? " · v" + job.VariationIndex.Value : string.Empty),
                    EditorStyles.boldLabel);
                EditorGUILayout.EndHorizontal();
                EditorGUILayout.LabelField(job.PromptSummary ?? string.Empty, _help);
                var profile = job.RequestProfileId ?? batch.GenerationProfileId ?? "—";
                var stage = job.Progress != null && !string.IsNullOrWhiteSpace(job.Progress.Message)
                    ? job.Progress.Message
                    : job.State;
                EditorGUILayout.LabelField("Profile " + profile + " · " + stage, _help);
                if (job.Error != null)
                    EditorGUILayout.HelpBox(job.Error.Code + ": " + job.Error.Message, MessageType.Error);
                if (_controller.IsImported(job))
                    EditorGUILayout.LabelField("Already imported", EditorStyles.miniLabel);
                if (job.CanImport)
                {
                    if (_thumbnails.TryGetValue(job.JobId, out var thumb) && thumb != null)
                    {
                        var rect = GUILayoutUtility.GetRect(64, 64, GUILayout.Width(64), GUILayout.Height(64));
                        EditorGUI.DrawPreviewTexture(rect, thumb, null, ScaleMode.ScaleToFit);
                    }
                    else if (_thumbnailJobId != job.JobId && GUILayout.Button("Load Preview", GUILayout.Width(110)))
                    {
                        _thumbnailJobId = job.JobId;
                        var captured = job;
                        RunSafe(async () =>
                        {
                            var texture = await _controller.LoadThumbnailAsync(
                                captured, 64, System.Threading.CancellationToken.None);
                            if (texture != null)
                            {
                                if (_thumbnails.TryGetValue(captured.JobId, out var previous) && previous != null)
                                    DestroyImmediate(previous);
                                _thumbnails[captured.JobId] = texture;
                            }

                            _thumbnailJobId = null;
                            Repaint();
                        });
                    }
                }

                EditorGUILayout.BeginHorizontal();
                using (new EditorGUI.DisabledScope(!job.IsCancellable))
                {
                    if (GUILayout.Button("Cancel", GUILayout.Width(70)))
                        RunSafe(() => _controller.CancelJobAsync(job.JobId));
                }

                using (new EditorGUI.DisabledScope(busy || !job.IsRetryable))
                {
                    if (GUILayout.Button("Retry", GUILayout.Width(70)))
                        RunSafe(() => _controller.RetryJobAsync(job.JobId));
                }

                using (new EditorGUI.DisabledScope(busy || !job.CanImport || _controller.IsImported(job)))
                {
                    if (GUILayout.Button("Import", GUILayout.Width(70)))
                        RunSafe(() => _controller.ImportJobsAsync(new[] { job }, _model.Shared));
                }

                EditorGUILayout.EndHorizontal();
                EditorGUILayout.EndVertical();
            }

            EditorGUILayout.EndScrollView();
        }

        void DrawStatus(BatchProgress progress)
        {
            EditorGUILayout.Space(6);
            EditorGUILayout.LabelField("Status", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(progress.StatusMessage ?? "Idle", MessageType.None);
            if (!string.IsNullOrWhiteSpace(progress.ErrorMessage))
                EditorGUILayout.HelpBox(progress.ErrorMessage, MessageType.Error);
            if (progress.LastImportedCount > 0)
                EditorGUILayout.LabelField(
                    "Last import: " + progress.LastImportedCount + " imported, " +
                    progress.LastSkippedCount + " skipped",
                    _help);
        }

        void DestroyThumbnails()
        {
            foreach (var pair in _thumbnails)
            {
                if (pair.Value != null)
                    DestroyImmediate(pair.Value);
            }

            _thumbnails.Clear();
        }

        static void DestroyOwned(ref bool owns, ref Texture2D texture)
        {
            if (owns && texture != null)
                DestroyImmediate(texture);
            owns = false;
            texture = null;
        }

        static GUIContent Tip(string label, string tooltip) => new GUIContent(label, tooltip);

        static async void RunSafe(Func<System.Threading.Tasks.Task> action)
        {
            try
            {
                await action().ConfigureAwait(true);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                EditorUtility.DisplayDialog("Batch Generation", ex.Message, "OK");
            }
        }
    }
}
