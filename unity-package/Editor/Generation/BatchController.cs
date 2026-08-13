using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Capabilities;
using UnityAiAssets.Editor.Configuration;
using UnityAiAssets.Editor.Importing;
using UnityAiAssets.Editor.Integrity;
using UnityAiAssets.Editor.Metadata;
using UnityAiAssets.Editor.Profiles;
using UnityEngine;

namespace UnityAiAssets.Editor.Generation
{
    public sealed class BatchProgress
    {
        public GenerationState State = GenerationState.Idle;
        public string StatusMessage = "Idle";
        public string ErrorMessage;
        public CapabilityState CapabilityState = CapabilityState.Unknown;
        public CapabilityDocument Capabilities;
        public string CapabilityError;
        public string RequestId;
        public BatchDocument Current;
        public List<BatchDocument> History = new List<BatchDocument>();
        public List<string> ValidationIssues = new List<string>();
        public int LastImportedCount;
        public int LastSkippedCount;
        public string LastImportedPath;

        public bool CapabilitiesUsable =>
            CapabilityState == CapabilityState.Ready || CapabilityState == CapabilityState.Stale;
    }

    /// <summary>
    /// Orchestrates batch submit/monitor/import over the existing job API.
    /// Does not run generation itself.
    /// </summary>
    public sealed class BatchController
    {
        readonly Func<IGenerationApiClient> _clientFactory;
        readonly GeneratedAssetImporter _assetImporter;
        readonly GenerationMetadataImporter _metadataImporter;
        readonly MaterialFactory _materialFactory;
        readonly CapabilityCache _capabilityCache;
        readonly GenerationProfileRegistry _profileRegistry;
        readonly GenerationProfileResolver _profileResolver;
        readonly ProfileCatalog _catalog;
        readonly ImportedGenerationRegistry _imported;

        CancellationTokenSource _cts;
        CancellationTokenSource _pollCts;

        public BatchController(
            Func<IGenerationApiClient> clientFactory = null,
            GeneratedAssetImporter assetImporter = null,
            GenerationMetadataImporter metadataImporter = null,
            MaterialFactory materialFactory = null,
            CapabilityCache capabilityCache = null,
            GenerationProfileRegistry profileRegistry = null,
            GenerationProfileResolver profileResolver = null,
            ProfileCatalog catalog = null,
            ImportedGenerationRegistry imported = null)
        {
            _clientFactory = clientFactory ?? (() =>
            {
                var settings = UnityAiAssetSettings.instance;
                return new GenerationApiClient(settings.BackendBaseUrl, settings.ApiTimeoutSeconds);
            });
            _assetImporter = assetImporter ?? new GeneratedAssetImporter();
            _metadataImporter = metadataImporter ?? new GenerationMetadataImporter();
            _materialFactory = materialFactory ?? new MaterialFactory();
            _capabilityCache = capabilityCache ?? CapabilityCache.Shared;
            _catalog = catalog ?? new ProfileCatalog();
            _profileRegistry = profileRegistry ?? new GenerationProfileRegistry(
                userRoot: UnityAiAssetSettings.instance.UserProfileDirectoryAbsolute,
                catalog: _catalog);
            _profileResolver = profileResolver ?? new GenerationProfileResolver(_catalog);
            _imported = imported ?? new ImportedGenerationRegistry(DefaultRegistryPath());
            Progress = new BatchProgress();
        }

        public BatchProgress Progress { get; }

        public ImportedGenerationRegistry Imported => _imported;

        public bool IsBusy =>
            Progress.State == GenerationState.Submitting ||
            Progress.State == GenerationState.Downloading ||
            Progress.State == GenerationState.Importing ||
            Progress.State == GenerationState.RefreshingCapabilities;

        public static string DefaultRegistryPath()
        {
            var data = Application.dataPath;
            var library = Path.GetFullPath(Path.Combine(data, "..", "Library", "UnityAiAssets"));
            return Path.Combine(library, "imported-generations.json");
        }

        public bool IsImported(JobDocument job)
        {
            return job?.Result != null && _imported.IsImported(job.Result.GenerationId);
        }

        public void CancelLocalWait()
        {
            _cts?.Cancel();
        }

        public void StopPolling()
        {
            _pollCts?.Cancel();
        }

        public async Task RefreshCapabilitiesAsync()
        {
            if (IsBusy)
                return;
            var settings = UnityAiAssetSettings.instance;
            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;
            SetState(GenerationState.RefreshingCapabilities, "Refreshing backend capabilities…");
            _capabilityCache.SetLoading(settings.BackendBaseUrl);
            try
            {
                using var client = CreateClient();
                var document = await client.GetCapabilitiesAsync(token).ConfigureAwait(true);
                _capabilityCache.SetReady(settings.BackendBaseUrl, document);
                Progress.RequestId = client.LastRequestId ?? Progress.RequestId;
                MirrorCapabilities(settings.BackendBaseUrl);
                SetState(GenerationState.Idle, "Capabilities ready.");
            }
            catch (Exception ex)
            {
                var message = ex is ApiException api ? api.UserFacingMessage : ex.Message;
                _capabilityCache.SetUnavailable(settings.BackendBaseUrl, message);
                MirrorCapabilities(settings.BackendBaseUrl);
                Fail(ex);
            }
        }

        public bool TryBuildPlan(BatchRequestModel model, out BatchExpansionPlan plan, out List<string> errors)
        {
            plan = null;
            errors = new List<string>();
            if (model == null)
            {
                errors.Add("Batch request is required.");
                return false;
            }

            var maxJobs = Progress.Capabilities?.Batches?.MaximumJobs ?? BatchExpansion.DefaultMaxJobs;
            var maxPrompts = Progress.Capabilities?.Batches?.MaximumPrompts ?? BatchExpansion.DefaultMaxPrompts;
            var maxVariations = Progress.Capabilities?.Batches?.MaximumVariations ?? BatchExpansion.DefaultMaxVariations;
            return BatchExpansion.TryExpand(
                model.PromptTexts(),
                model.SeedMode,
                model.VariationCount,
                model.Seed,
                model.SeedStart,
                model.SeedEnd,
                model.Shared.OutputName,
                out plan,
                out errors,
                maxJobs: maxJobs,
                maxPrompts: maxPrompts,
                maxVariations: maxVariations);
        }

        public async Task SubmitAsync(BatchRequestModel model)
        {
            if (model == null)
                throw new ArgumentNullException(nameof(model));
            if (IsBusy)
                return;

            Progress.ValidationIssues = new List<string>();
            Progress.ErrorMessage = null;
            if (!TryBuildPlan(model, out var plan, out var errors))
            {
                Progress.ValidationIssues = errors;
                Progress.State = GenerationState.Failed;
                Progress.ErrorMessage = string.Join("\n", errors);
                Progress.StatusMessage = "Batch configuration is invalid.";
                return;
            }

            var request = model.Shared;
            if (request.UseImageToImage && request.SourceTexture == null)
            {
                FailMessage("Image-to-image batches require a source image.");
                return;
            }

            if (request.UseInpainting && (request.SourceTexture == null || request.MaskTexture == null))
            {
                FailMessage("Inpainting batches require both a source image and a mask.");
                return;
            }

            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;
            try
            {
                using var client = CreateClient();
                var settings = UnityAiAssetSettings.instance;
                var capabilities = await EnsureCapabilitiesAsync(client, settings.BackendBaseUrl, token)
                    .ConfigureAwait(true);
                if (capabilities == null)
                    return;

                SetState(GenerationState.Submitting, "Resolving preset and submitting batch…");
                var dto = BuildSubmitDto(model, capabilities);
                var batch = await client.SubmitBatchAsync(dto, token).ConfigureAwait(true);
                Progress.Current = batch;
                Progress.RequestId = client.LastRequestId ?? Progress.RequestId;
                SetState(
                    GenerationState.Idle,
                    "Submitted " + batch.JobIds.Count + " jobs. The existing queue will run them one at a time.");
                StartPolling(batch.BatchId);
            }
            catch (OperationCanceledException)
            {
                Progress.State = GenerationState.Cancelled;
                Progress.StatusMessage = "Batch submit cancelled locally.";
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task RefreshHistoryAsync()
        {
            if (IsBusy)
                return;
            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            try
            {
                using var client = CreateClient();
                SetState(GenerationState.Downloading, "Loading batches…");
                var list = await client.ListBatchesAsync(_cts.Token).ConfigureAwait(true);
                Progress.History = list.Batches ?? new List<BatchDocument>();
                if (Progress.Current != null)
                {
                    var current = await client.GetBatchAsync(Progress.Current.BatchId, _cts.Token)
                        .ConfigureAwait(true);
                    Progress.Current = current;
                    if (current.IsActive)
                        StartPolling(current.BatchId);
                }
                else if (Progress.History.Count > 0)
                {
                    var latest = Progress.History[0];
                    Progress.Current = await client.GetBatchAsync(latest.BatchId, _cts.Token)
                        .ConfigureAwait(true);
                    if (Progress.Current.IsActive)
                        StartPolling(Progress.Current.BatchId);
                }

                SetState(GenerationState.Idle, "Loaded " + Progress.History.Count + " batches.");
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task SelectBatchAsync(string batchId)
        {
            if (string.IsNullOrWhiteSpace(batchId) || IsBusy)
                return;
            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            try
            {
                using var client = CreateClient();
                SetState(GenerationState.Downloading, "Loading batch…");
                Progress.Current = await client.GetBatchAsync(batchId, _cts.Token).ConfigureAwait(true);
                SetState(GenerationState.Idle, FormatBatchStatus(Progress.Current));
                if (Progress.Current.IsActive)
                    StartPolling(batchId);
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task CancelCurrentAsync()
        {
            var batch = Progress.Current;
            if (batch == null || string.IsNullOrWhiteSpace(batch.BatchId))
                return;
            try
            {
                using var client = CreateClient();
                Progress.Current = await client.CancelBatchAsync(batch.BatchId, CancellationToken.None)
                    .ConfigureAwait(true);
                SetState(GenerationState.Idle, FormatBatchStatus(Progress.Current));
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task RetryFailedAsync()
        {
            var batch = Progress.Current;
            if (batch == null || string.IsNullOrWhiteSpace(batch.BatchId) || IsBusy)
                return;
            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            try
            {
                using var client = CreateClient();
                SetState(GenerationState.Submitting, "Retrying failed batch jobs…");
                Progress.Current = await client.RetryFailedBatchAsync(batch.BatchId, _cts.Token)
                    .ConfigureAwait(true);
                SetState(GenerationState.Idle, FormatBatchStatus(Progress.Current));
                if (Progress.Current.IsActive)
                    StartPolling(Progress.Current.BatchId);
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task CancelJobAsync(string jobId)
        {
            if (string.IsNullOrWhiteSpace(jobId))
                return;
            try
            {
                using var client = CreateClient();
                await client.CancelJobAsync(jobId, CancellationToken.None).ConfigureAwait(true);
                if (Progress.Current != null)
                {
                    Progress.Current = await client.GetBatchAsync(Progress.Current.BatchId, CancellationToken.None)
                        .ConfigureAwait(true);
                    SetState(GenerationState.Idle, FormatBatchStatus(Progress.Current));
                }
            }
            catch (Exception ex)
            {
                if (!IsBusy)
                    Fail(ex);
            }
        }

        public async Task RetryJobAsync(string jobId)
        {
            if (string.IsNullOrWhiteSpace(jobId) || IsBusy)
                return;
            try
            {
                using var client = CreateClient();
                await client.RetryJobAsync(jobId, CancellationToken.None).ConfigureAwait(true);
                if (Progress.Current != null)
                {
                    Progress.Current = await client.GetBatchAsync(Progress.Current.BatchId, CancellationToken.None)
                        .ConfigureAwait(true);
                    SetState(GenerationState.Idle, FormatBatchStatus(Progress.Current));
                    if (Progress.Current.IsActive)
                        StartPolling(Progress.Current.BatchId);
                }
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task ImportJobsAsync(IEnumerable<JobDocument> jobs, TextureGenerationRequestModel request)
        {
            if (request == null)
                throw new ArgumentNullException(nameof(request));
            if (IsBusy)
                return;

            var targets = (jobs ?? Enumerable.Empty<JobDocument>())
                .Where(job => job != null && job.CanImport)
                .ToList();
            if (targets.Count == 0)
            {
                SetState(GenerationState.Idle, "No successful outputs selected for import.");
                return;
            }

            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;
            Progress.LastImportedCount = 0;
            Progress.LastSkippedCount = 0;
            Progress.LastImportedPath = null;
            try
            {
                using var client = CreateClient();
                foreach (var job in targets)
                {
                    token.ThrowIfCancellationRequested();
                    if (IsImported(job))
                    {
                        Progress.LastSkippedCount++;
                        continue;
                    }

                    SetState(
                        GenerationState.Importing,
                        "Importing " + (Progress.LastImportedCount + 1) + " of " + targets.Count + "…");
                    await ImportOneAsync(client, job, request, token).ConfigureAwait(true);
                    _imported.MarkImported(job.Result.GenerationId);
                    Progress.LastImportedCount++;
                }

                var skipped = Progress.LastSkippedCount;
                SetState(
                    GenerationState.Completed,
                    "Imported " + Progress.LastImportedCount + " asset(s)" +
                    (skipped > 0 ? ", skipped " + skipped + " already imported." : "."));
            }
            catch (OperationCanceledException)
            {
                Progress.State = GenerationState.Cancelled;
                Progress.StatusMessage = "Import cancelled.";
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task<Texture2D> LoadThumbnailAsync(JobDocument job, int maxSize, CancellationToken token)
        {
            if (job == null || !job.CanImport)
                return null;
            using var client = CreateClient();
            var png = await client.DownloadGenerationImageAsync(
                job.Result.GenerationId, job.Result.Resources?.image, token).ConfigureAwait(true);
            return CreateThumbnail(png, maxSize);
        }

        void StartPolling(string batchId)
        {
            _pollCts?.Cancel();
            _pollCts = new CancellationTokenSource();
            var token = _pollCts.Token;
            PollLoop(batchId, token);
        }

        async void PollLoop(string batchId, CancellationToken token)
        {
            try
            {
                while (!token.IsCancellationRequested)
                {
                    await Task.Delay(800, token).ConfigureAwait(true);
                    if (IsBusy)
                        continue;
                    using var client = CreateClient();
                    var batch = await client.GetBatchAsync(batchId, token).ConfigureAwait(true);
                    Progress.Current = batch;
                    Progress.StatusMessage = FormatBatchStatus(batch);
                    if (!batch.IsActive)
                        return;
                }
            }
            catch (OperationCanceledException)
            {
            }
            catch (Exception ex)
            {
                if (!IsBusy)
                    Progress.StatusMessage = "Batch poll failed: " + ex.Message;
            }
        }

        BatchSubmitRequestDto BuildSubmitDto(
            BatchRequestModel model, CapabilityDocument capabilities)
        {
            var request = model.Shared;
            var selectedProfile = _profileRegistry.Get(request.SelectedProfileId);
            var constructed = new List<string>();
            ResolvedGenerationSettings lastResolved = null;
            foreach (var entry in model.Prompts)
            {
                var subject = entry != null ? entry.Text : string.Empty;
                var resolved = _profileResolver.Resolve(selectedProfile, BuildOverrides(request, subject), capabilities);
                if (!resolved.Compatibility.CanGenerate)
                    throw new InvalidOperationException(string.Join("\n", resolved.Compatibility.Messages));
                constructed.Add(resolved.ConstructedPrompt);
                lastResolved = resolved;
            }

            if (lastResolved == null)
                throw new InvalidOperationException("Batch has no prompts to resolve.");

            ApplyResolved(request, lastResolved);
            var issues = GenerationCapabilityValidator.Validate(request, capabilities);
            if (issues.Count > 0)
                throw new InvalidOperationException(string.Join("\n", issues.Select(i => i.ToString())));

            var dto = new BatchSubmitRequestDto
            {
                prompts = constructed,
                variation_count = model.VariationCount,
                seed_mode = BatchExpansion.ToApiValue(model.SeedMode),
                seed = model.SeedMode == BatchSeedModeKind.Sequential ? (long?)null : model.Seed,
                seed_start = model.SeedMode == BatchSeedModeKind.Sequential ? model.SeedStart : (long?)null,
                seed_end = model.SeedMode == BatchSeedModeKind.Sequential ? model.SeedEnd : (long?)null,
                request = GenerationRequestFactory.FromResolved(lastResolved, request)
            };
            dto.request.seed = null;
            return dto;
        }

        static UserProfileOverrides BuildOverrides(TextureGenerationRequestModel request, string subject)
        {
            return new UserProfileOverrides
            {
                Subject = subject,
                AdditionalPrompt = request.AdditionalPrompt,
                AdditionalNegative = request.AdditionalNegative,
                Width = request.Width,
                Height = request.Height,
                Steps = request.Steps,
                Guidance = request.GuidanceScale,
                DestinationFolder = request.DestinationFolder,
                ImportProfileId = request.ImportProfileId,
                CreateMaterial = request.CreateMaterial,
                OutputName = request.OutputName,
                TransparencyStrategy = request.TransparencyStrategy,
                AlphaThreshold = request.AlphaThreshold,
                AlphaFeather = request.AlphaFeather,
                RemoveNearTransparent = request.RemoveNearTransparent,
                ZeroRgbWhenTransparent = request.ZeroRgbWhenTransparent,
                PixelsPerUnit = request.PixelsPerUnit,
                PivotMode = request.PivotMode,
                CustomPivotX = request.CustomPivotX,
                CustomPivotY = request.CustomPivotY,
                AtlasHint = request.AtlasHint,
                Tileable = request.Tileable,
                ApplySeamCorrection = request.ApplySeamCorrection,
                SeamBlendWidth = request.SeamBlendWidth,
                PaletteReductionEnabled = request.PaletteReductionEnabled,
                PaletteColorCount = request.PaletteColorCount
            };
        }

        static void ApplyResolved(TextureGenerationRequestModel request, ResolvedGenerationSettings resolved)
        {
            request.AssetType = resolved.AssetType;
            request.Prompt = request.PreviewPrompt = resolved.ConstructedPrompt;
            request.NegativePrompt = request.PreviewNegative = resolved.ConstructedNegativePrompt;
            request.ImportProfileId = resolved.ImportProfileId;
            request.Width = resolved.Width;
            request.Height = resolved.Height;
            request.Steps = resolved.Steps;
            request.GuidanceScale = resolved.GuidanceScale;
            request.OutputName = resolved.OutputName;
            request.DestinationFolder = resolved.DestinationFolder;
            request.CreateMaterial = resolved.CreateMaterial;
            request.TransparencyStrategy = resolved.TransparencyStrategy;
            request.AlphaThreshold = resolved.AlphaThreshold;
            request.AlphaFeather = resolved.AlphaFeather;
            request.RemoveNearTransparent = resolved.RemoveNearTransparent;
            request.ZeroRgbWhenTransparent = resolved.ZeroRgbWhenTransparent;
            request.PixelsPerUnit = resolved.PixelsPerUnit;
            request.PivotMode = resolved.PivotMode;
            request.CustomPivotX = resolved.CustomPivotX;
            request.CustomPivotY = resolved.CustomPivotY;
            request.AtlasHint = resolved.AtlasHint;
            request.Tileable = resolved.Tileable;
            request.ApplySeamCorrection = resolved.ApplySeamCorrection;
            request.SeamBlendWidth = resolved.SeamBlendWidth;
            request.PaletteReductionEnabled = resolved.PaletteReductionEnabled;
            request.PaletteColorCount = resolved.PaletteColorCount;
        }

        async Task ImportOneAsync(
            IGenerationApiClient client,
            JobDocument job,
            TextureGenerationRequestModel request,
            CancellationToken token)
        {
            var png = await client
                .DownloadGenerationImageAsync(job.Result.GenerationId, job.Result.Resources?.image, token)
                .ConfigureAwait(true);
            GenerationManifestDocument manifest = null;
            try
            {
                manifest = await client
                    .DownloadGenerationManifestAsync(job.Result.GenerationId, job.Result.Resources?.manifest, token)
                    .ConfigureAwait(true);
            }
            catch (ApiException)
            {
            }

            token.ThrowIfCancellationRequested();
            var imageOutput = manifest?.FindOutput("image");
            if (imageOutput != null)
            {
                var expectedSize = imageOutput.ByteSize > 0 ? (long?)imageOutput.ByteSize : null;
                var integrity = ImageIntegrityVerifier.Verify(png, imageOutput.Sha256, expectedSize);
                if (!integrity.IsValid)
                {
                    throw new ApiException(
                        "Downloaded image failed integrity verification: " + integrity.FailureReason,
                        ApiFailureKind.Integrity,
                        requestId: Progress.RequestId);
                }
            }

            var profile = !string.IsNullOrWhiteSpace(request.ImportProfileId)
                ? _catalog.GetImportProfile(request.ImportProfileId)
                : _catalog.FromLegacyKind(request.ImportProfile);
            profile = profile.Copy();
            if (request.AssetType == "sprite" || request.AssetType == "icon")
            {
                profile.PixelsPerUnit = request.PixelsPerUnit;
                profile.PivotMode = request.PivotMode;
                profile.CustomPivotX = request.CustomPivotX;
                profile.CustomPivotY = request.CustomPivotY;
            }

            var outputName = !string.IsNullOrWhiteSpace(job.RequestOutputName)
                ? job.RequestOutputName
                : request.OutputName;
            var import = _assetImporter.ImportPng(png, request.DestinationFolder, outputName, profile);
            Progress.LastImportedPath = import.AssetPath;

            var response = new TextureGenerationResponseDto
            {
                generation_id = job.Result.GenerationId,
                status = job.Result.Status,
                operation = job.Result.Operation,
                asset_type = job.Result.AssetType,
                seed = job.Result.Seed,
                width = job.Result.Width,
                height = job.Result.Height,
                elapsed_seconds = job.Result.ElapsedSeconds,
                resources = job.Result.Resources,
                schema_versions = job.Result.SchemaVersions,
            };
            var imageUrl = job.Result.Resources?.image ?? ApiEndpoints.GenerationImage(job.Result.GenerationId);
            var manifestUrl = job.Result.Resources?.manifest ?? ApiEndpoints.GenerationManifest(job.Result.GenerationId);
            _metadataImporter.Create(
                import.Texture,
                import.AssetPath,
                UnityAiAssetSettings.instance.BackendBaseUrl,
                response,
                manifest,
                null,
                imageUrl,
                manifestUrl,
                Progress.RequestId);
            if (request.CreateMaterial)
            {
                _materialFactory.CreateMaterial(
                    import.Texture,
                    request.MaterialDestinationFolder,
                    outputName,
                    request.ShaderName);
            }
        }

        async Task<CapabilityDocument> EnsureCapabilitiesAsync(
            IGenerationApiClient client, string baseUrl, CancellationToken token)
        {
            var entry = _capabilityCache.Get(baseUrl);
            if (entry.State == CapabilityState.Unknown)
            {
                SetState(GenerationState.RefreshingCapabilities, "Fetching backend capabilities…");
                try
                {
                    var document = await client.GetCapabilitiesAsync(token).ConfigureAwait(true);
                    _capabilityCache.SetReady(baseUrl, document);
                }
                catch (Exception ex)
                {
                    var message = ex is ApiException api ? api.UserFacingMessage : ex.Message;
                    _capabilityCache.SetUnavailable(baseUrl, message);
                }

                entry = _capabilityCache.Get(baseUrl);
            }

            MirrorCapabilities(baseUrl);
            if (entry.State == CapabilityState.Unavailable || entry.State == CapabilityState.Incompatible)
            {
                FailMessage("Backend capabilities are not usable: " + (entry.ErrorMessage ?? "unknown."));
                return null;
            }

            return entry.Document;
        }

        void MirrorCapabilities(string baseUrl)
        {
            var entry = _capabilityCache.Get(baseUrl);
            Progress.CapabilityState = entry.State;
            Progress.Capabilities = entry.Document;
            Progress.CapabilityError = entry.ErrorMessage;
        }

        IGenerationApiClient CreateClient()
        {
            var client = _clientFactory();
            if (client == null)
                throw new InvalidOperationException("API client factory returned null.");
            return client;
        }

        void SetState(GenerationState state, string message)
        {
            Progress.State = state;
            Progress.StatusMessage = message;
            if (state != GenerationState.Failed)
                Progress.ErrorMessage = null;
        }

        void FailMessage(string message)
        {
            Progress.State = GenerationState.Failed;
            Progress.ErrorMessage = message;
            Progress.StatusMessage = "Failed: " + message;
        }

        void Fail(Exception ex)
        {
            if (ex is ApiException api)
            {
                Progress.ErrorMessage = api.UserFacingMessage;
                Progress.StatusMessage = "Failed (" + api.Kind + "): " + api.UserFacingMessage;
                if (!string.IsNullOrWhiteSpace(api.RequestId))
                    Progress.RequestId = api.RequestId;
            }
            else
            {
                Progress.ErrorMessage = ex.Message;
                Progress.StatusMessage = "Failed: " + ex.Message;
            }

            Progress.State = GenerationState.Failed;
        }

        public static string FormatBatchStatus(BatchDocument batch)
        {
            if (batch == null)
                return "No batch selected.";
            var counts = batch.Counts;
            var progress = batch.Progress;
            var ratio = progress != null
                ? progress.FinishedJobs + "/" + progress.TotalJobs + " finished, " +
                  progress.CompletedJobs + " completed"
                : "no progress";
            return batch.State + " · " + ratio +
                   (counts != null
                       ? " · queued " + counts.Queued + ", running " + counts.Running +
                         ", failed " + counts.Failed + ", cancelled " + counts.Cancelled
                       : string.Empty);
        }

        public static Texture2D CreateThumbnail(byte[] png, int maxSize)
        {
            if (png == null || png.Length == 0)
                return null;
            var source = new Texture2D(2, 2, TextureFormat.RGBA32, false);
            if (!source.LoadImage(png))
            {
                UnityEngine.Object.DestroyImmediate(source);
                return null;
            }

            var max = Math.Max(1, maxSize);
            if (source.width <= max && source.height <= max)
                return source;

            var scale = max / (float)Math.Max(source.width, source.height);
            var width = Math.Max(1, Mathf.RoundToInt(source.width * scale));
            var height = Math.Max(1, Mathf.RoundToInt(source.height * scale));
            var rt = RenderTexture.GetTemporary(width, height, 0, RenderTextureFormat.ARGB32);
            var previous = RenderTexture.active;
            try
            {
                Graphics.Blit(source, rt);
                RenderTexture.active = rt;
                var thumb = new Texture2D(width, height, TextureFormat.RGBA32, false);
                thumb.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                thumb.Apply();
                UnityEngine.Object.DestroyImmediate(source);
                return thumb;
            }
            finally
            {
                RenderTexture.active = previous;
                RenderTexture.ReleaseTemporary(rt);
            }
        }
    }
}
