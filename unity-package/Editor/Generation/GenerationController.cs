using System;
using System.Collections.Generic;
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
    public sealed class GenerationProgress
    {
        public GenerationState State = GenerationState.Idle;
        public string StatusMessage = "Idle";
        public string ErrorMessage;
        public bool BackendReachable;

        public bool ModelLoaded;
        public string GenerationId;
        public string JobId;
        public string JobState;
        public string JobStage;
        public long? Seed;
        public float? ElapsedSeconds;
        public List<JobDocument> History = new List<JobDocument>();
        public string ImportedTexturePath;
        public string ImportedMaterialPath;
        public string MetadataAssetPath;

        // --- Milestone 3: capability/version-aware fields ---
        public CapabilityState CapabilityState = CapabilityState.Unknown;
        public CapabilityDocument Capabilities;
        public string CapabilityError;
        public string ApplicationVersion;
        public string ModelId;
        public string ModelFamily;
        public string ResolvedDevice;
        public string ResolvedPrecision;
        public string RequestId;
        public List<CapabilityValidationIssue> ValidationIssues = new List<CapabilityValidationIssue>();

        // Last generation processing provenance (from manifest; explicit, never implied).
        public bool? SeamCorrectionRequested;
        public bool? SeamCorrectionApplied;
        public string SeamInpaintImplementation;
        public float? SeamScoreBefore;
        public float? SeamScoreAfter;
        public bool? BackgroundRemovalApplied;
        public string BackgroundRemovalImplementation;
        public string TransparencyStrategy;
        public string ProcessingSummary;
        public string Operation;
        public float? DenoisingStrength;

        public bool CapabilitiesUsable =>
            CapabilityState == CapabilityState.Ready || CapabilityState == CapabilityState.Stale;

        public bool CanGenerate =>
            CapabilitiesUsable && Capabilities != null &&
            (Capabilities.Operations?.TextToImage?.Supported == true ||
             Capabilities.Operations?.ImageToImage?.Supported == true ||
             Capabilities.Operations?.Inpainting?.Supported == true);
    }

    /// <summary>
    /// Orchestrates capability discovery, health checks, generation, download, integrity
    /// verification, import, metadata/manifest, and materials.
    /// </summary>
    public sealed class GenerationController
    {
        readonly Func<IGenerationApiClient> _clientFactory;
        readonly GeneratedAssetImporter _assetImporter;
        readonly GenerationMetadataImporter _metadataImporter;
        readonly MaterialFactory _materialFactory;
        readonly CapabilityCache _capabilityCache;
        readonly GenerationProfileRegistry _profileRegistry;
        readonly GenerationProfileResolver _profileResolver;
        readonly ProfileCatalog _catalog;

        CancellationTokenSource _cts;
        string _lastKnownBackendBaseUrl;

        public GenerationController(
            Func<IGenerationApiClient> clientFactory = null,
            GeneratedAssetImporter assetImporter = null,
            GenerationMetadataImporter metadataImporter = null,
            MaterialFactory materialFactory = null,
            CapabilityCache capabilityCache = null,
            GenerationProfileRegistry profileRegistry = null,
            GenerationProfileResolver profileResolver = null,
            ProfileCatalog catalog = null)
        {
            _clientFactory = clientFactory ?? (() =>
            {
                return UnityAiAssetSettings.CreateApiClient();
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
            Progress = new GenerationProgress();
        }

        public GenerationProgress Progress { get; }

        public bool IsBusy =>
            Progress.State == GenerationState.CheckingConnection ||
            Progress.State == GenerationState.Submitting ||
            Progress.State == GenerationState.Generating ||
            Progress.State == GenerationState.Downloading ||
            Progress.State == GenerationState.Importing ||
            Progress.State == GenerationState.RefreshingCapabilities;

        public void CancelLocalWait()
        {
            _cts?.Cancel();
        }

        public async Task CancelActiveJobAsync()
        {
            var jobId = Progress.JobId;
            _cts?.Cancel();
            if (string.IsNullOrWhiteSpace(jobId))
            {
                return;
            }

            try
            {
                using var client = CreateClient();
                await client.CancelJobAsync(jobId, CancellationToken.None).ConfigureAwait(true);
            }
            catch (Exception)
            {
                // Local wait is already cancelled; backend cancel is best-effort.
            }
        }

        /// <summary>
        /// Loads (or reloads) the current backend's capability document into the shared
        /// session cache and mirrors its state onto <see cref="Progress"/>. Never touches
        /// caller-owned request/UI state, so entered values survive a failed refresh.
        /// </summary>
        public async Task RefreshCapabilitiesAsync()
        {
            if (IsBusy)
            {
                return;
            }

            var settings = UnityAiAssetSettings.instance;
            var baseUrl = settings.BackendBaseUrl;
            InvalidateCacheOnUrlChange(baseUrl);

            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;

            SetState(GenerationState.RefreshingCapabilities, "Refreshing backend capabilities…");
            _capabilityCache.SetLoading(baseUrl);
            MirrorCapabilityState(baseUrl);

            try
            {
                using var client = CreateClient();
                var document = await client.GetCapabilitiesAsync(token).ConfigureAwait(true);
                _capabilityCache.SetReady(baseUrl, document);
                Progress.RequestId = client.LastRequestId ?? Progress.RequestId;
                MirrorCapabilityState(baseUrl);

                if (Progress.CapabilityState == CapabilityState.Incompatible)
                {
                    SetState(
                        GenerationState.Idle,
                        $"Backend capabilities are incompatible: {Progress.CapabilityError}");
                }
                else
                {
                    SetState(
                        GenerationState.Idle,
                        $"Capabilities ready (app={Progress.ApplicationVersion}, model={Progress.ModelId}, " +
                        $"device={Progress.ResolvedDevice}, precision={Progress.ResolvedPrecision}, " +
                        $"model_loaded={Progress.ModelLoaded}).");
                }
            }
            catch (Exception ex)
            {
                var message = ex is ApiException api ? api.UserFacingMessage : ex.Message;
                _capabilityCache.SetUnavailable(baseUrl, message);
                MirrorCapabilityState(baseUrl);
                Fail(ex);
            }
        }

        public async Task CheckConnectionAsync()
        {
            if (IsBusy)
            {
                return;
            }

            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            SetState(GenerationState.CheckingConnection, "Checking backend connection…");
            try
            {
                using var client = CreateClient();
                var health = await client.GetHealthAsync(_cts.Token).ConfigureAwait(true);
                Progress.BackendReachable = string.Equals(health.status, "ok", StringComparison.OrdinalIgnoreCase);
                Progress.ResolvedDevice = health.resolved_device;
                Progress.ModelLoaded = health.model_loaded;
                Progress.ApplicationVersion = health.application_version;
                Progress.RequestId = health.request_id ?? client.LastRequestId ?? Progress.RequestId;
                SetState(
                    GenerationState.Idle,
                    Progress.BackendReachable
                        ? $"Backend OK (app={health.application_version}, device={health.resolved_device}, " +
                          $"model_loaded={health.model_loaded})"
                        : "Backend responded with unexpected status.");
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task GenerateAndImportAsync(TextureGenerationRequestModel request)
        {
            if (request == null)
            {
                throw new ArgumentNullException(nameof(request));
            }

            if (IsBusy)
            {
                return;
            }

            ValidateRequestStructure(request);

            var settings = UnityAiAssetSettings.instance;
            var baseUrl = settings.BackendBaseUrl;
            InvalidateCacheOnUrlChange(baseUrl);

            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;
            Progress.ErrorMessage = null;
            Progress.ImportedTexturePath = null;
            Progress.ImportedMaterialPath = null;
            Progress.MetadataAssetPath = null;
            Progress.GenerationId = null;
            Progress.JobId = null;
            Progress.JobState = null;
            Progress.JobStage = null;
            Progress.Seed = null;
            Progress.ElapsedSeconds = null;
            Progress.ValidationIssues = new List<CapabilityValidationIssue>();
            Progress.SeamCorrectionRequested = null;
            Progress.SeamCorrectionApplied = null;
            Progress.SeamInpaintImplementation = null;
            Progress.SeamScoreBefore = null;
            Progress.SeamScoreAfter = null;
            Progress.BackgroundRemovalApplied = null;
            Progress.BackgroundRemovalImplementation = null;
            Progress.TransparencyStrategy = null;
            Progress.ProcessingSummary = null;
            Progress.Operation = null;
            Progress.DenoisingStrength = null;

            try
            {
                using var client = CreateClient();

                var capabilities = await EnsureUsableCapabilitiesAsync(client, baseUrl, token).ConfigureAwait(true);
                if (capabilities == null)
                {
                    // EnsureUsableCapabilitiesAsync already set Progress.State/ErrorMessage.
                    return;
                }

                var selectedProfile = _profileRegistry.Get(request.SelectedProfileId);
                var resolved = _profileResolver.Resolve(selectedProfile, new UserProfileOverrides
                {
                    Subject = request.Subject,
                    AdditionalPrompt = request.AdditionalPrompt,
                    AdditionalNegative = request.AdditionalNegative,
                    Width = request.Width,
                    Height = request.Height,
                    Steps = request.Steps,
                    Guidance = request.GuidanceScale,
                    Seed = request.UseExplicitSeed ? request.Seed : (long?)null,
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
                }, capabilities);
                if (!resolved.Compatibility.CanGenerate)
                    throw new InvalidOperationException(string.Join("\n", resolved.Compatibility.Messages));
                request.AssetType = resolved.AssetType;
                request.Prompt = request.PreviewPrompt = resolved.ConstructedPrompt;
                request.NegativePrompt = request.PreviewNegative = resolved.ConstructedNegativePrompt;
                request.ImportProfileId = resolved.ImportProfileId;
                request.Width = resolved.Width;
                request.Height = resolved.Height;
                request.Steps = resolved.Steps;
                request.GuidanceScale = resolved.GuidanceScale;
                request.UseExplicitSeed = resolved.Seed.HasValue;
                request.Seed = resolved.Seed ?? 0;
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

                var issues = GenerationCapabilityValidator.Validate(request, capabilities);
                if (issues.Count > 0)
                {
                    Progress.ValidationIssues = issues;
                    Progress.State = GenerationState.Failed;
                    Progress.ErrorMessage =
                        "Request does not satisfy backend capabilities:\n" +
                        string.Join("\n", issues.Select(i => " - " + i));
                    Progress.StatusMessage = "Failed: request violates backend capability constraints.";
                    return;
                }

                SetState(GenerationState.Submitting, "Submitting generation job…");
                var dto = GenerationRequestFactory.FromResolved(resolved, request);
                var job = await client.SubmitJobAsync(dto, token).ConfigureAwait(true);
                ApplyJobProgress(job);
                Progress.RequestId = client.LastRequestId ?? Progress.RequestId;

                SetState(GenerationState.Generating, FormatJobStatus(job));
                job = await WaitForJobAsync(client, job.JobId, token).ConfigureAwait(true);
                if (job.State == "cancelled")
                {
                    Progress.State = GenerationState.Cancelled;
                    Progress.StatusMessage = "Job cancelled. Nothing was imported.";
                    Progress.ErrorMessage = Progress.StatusMessage;
                    await RefreshHistorySilentAsync(client, token).ConfigureAwait(true);
                    return;
                }

                if (job.State != "completed" || job.Result == null)
                {
                    Progress.State = GenerationState.Failed;
                    Progress.ErrorMessage = job.Error != null
                        ? $"{job.Error.Code}: {job.Error.Message}"
                        : $"Job ended in state {job.State}.";
                    Progress.StatusMessage = "Failed: " + Progress.ErrorMessage;
                    await RefreshHistorySilentAsync(client, token).ConfigureAwait(true);
                    return;
                }

                var response = ToGenerationResponse(job);
                Progress.GenerationId = response.generation_id;
                Progress.Seed = response.seed;
                Progress.ElapsedSeconds = response.elapsed_seconds;
                Progress.Operation = !string.IsNullOrWhiteSpace(response.operation)
                    ? response.operation
                    : (request.UseInpainting
                        ? "inpainting"
                        : (request.UseImageToImage ? "image_to_image" : "text_to_image"));
                Progress.DenoisingStrength = request.UseInpainting || request.UseImageToImage
                    ? request.DenoisingStrength
                    : (float?)null;
                Progress.RequestId = client.LastRequestId ?? Progress.RequestId;

                SetState(GenerationState.Downloading, "Downloading generated PNG and manifest…");
                var png = await client
                    .DownloadGenerationImageAsync(response.generation_id, response.resources?.image, token)
                    .ConfigureAwait(true);

                GenerationManifestDocument manifest = null;
                BackendMetadataDto legacyMetadata = null;
                try
                {
                    manifest = await client
                        .DownloadGenerationManifestAsync(response.generation_id, response.resources?.manifest, token)
                        .ConfigureAwait(true);
                }
                catch (ApiException)
                {
                    // Compatibility-only fallback for older backends without manifests.
                    try
                    {
                        legacyMetadata = await client
                            .DownloadGenerationMetadataAsync(response.generation_id, token)
                            .ConfigureAwait(true);
                    }
                    catch (ApiException)
                    {
                        // Both manifest and legacy metadata are best-effort; import can continue.
                    }
                }

                token.ThrowIfCancellationRequested();

                VerifyImageIntegrityOrThrow(png, manifest);

                ApplyProcessingProvenance(request, manifest);

                SetState(GenerationState.Importing, "Importing texture into the Unity project…");
                var profile = !string.IsNullOrWhiteSpace(request.ImportProfileId)
                    ? _catalog.GetImportProfile(request.ImportProfileId)
                    : _catalog.FromLegacyKind(request.ImportProfile);
                profile = profile.Copy();
                if (request.AssetType == "sprite" || request.AssetType == "icon")
                {
                    profile.PixelsPerUnit = resolved.PixelsPerUnit;
                    profile.PivotMode = resolved.PivotMode;
                    profile.CustomPivotX = resolved.CustomPivotX;
                    profile.CustomPivotY = resolved.CustomPivotY;
                }
                var import = _assetImporter.ImportPng(
                    png,
                    request.DestinationFolder,
                    request.OutputName,
                    profile);
                Progress.ImportedTexturePath = import.AssetPath;

                var imageUrl = !string.IsNullOrWhiteSpace(response.resources?.image)
                    ? response.resources.image
                    : ApiEndpoints.GenerationImage(response.generation_id);
                var manifestUrl = !string.IsNullOrWhiteSpace(response.resources?.manifest)
                    ? response.resources.manifest
                    : ApiEndpoints.GenerationManifest(response.generation_id);

                var metadataAsset = _metadataImporter.Create(
                    import.Texture,
                    import.AssetPath,
                    settings.BackendBaseUrl,
                    response,
                    manifest,
                    legacyMetadata,
                    imageUrl,
                    manifestUrl,
                    Progress.RequestId);
                Progress.MetadataAssetPath = UnityEditor.AssetDatabase.GetAssetPath(metadataAsset);

                if (request.CreateMaterial)
                {
                    var material = _materialFactory.CreateMaterial(
                        import.Texture,
                        request.MaterialDestinationFolder,
                        request.OutputName,
                        request.ShaderName);
                    Progress.ImportedMaterialPath = UnityEditor.AssetDatabase.GetAssetPath(material);
                }

                await RefreshHistorySilentAsync(client, token).ConfigureAwait(true);
                SetState(
                    GenerationState.Completed,
                    BuildCompletionStatus(import.AssetPath));
            }
            catch (OperationCanceledException)
            {
                Progress.State = GenerationState.Cancelled;
                Progress.StatusMessage =
                    "Cancelled. If the job was still queued or running, the backend was asked to stop.";
                Progress.ErrorMessage = Progress.StatusMessage;
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        void ApplyProcessingProvenance(TextureGenerationRequestModel request, GenerationManifestDocument manifest)
        {
            Progress.SeamCorrectionRequested = request.ApplySeamCorrection;
            Progress.TransparencyStrategy = request.TransparencyStrategy;

            var processing = manifest?.Processing;
            if (processing == null)
            {
                Progress.SeamCorrectionApplied = false;
                Progress.BackgroundRemovalApplied = false;
                Progress.ProcessingSummary = request.ApplySeamCorrection
                    ? "Seam repair was requested but the manifest has no processing block — cannot verify application."
                    : "No processing provenance in manifest.";
                return;
            }

            Progress.SeamCorrectionApplied = processing.SeamCorrectionApplied;
            Progress.SeamInpaintImplementation = processing.SeamInpaintImplementation;
            Progress.SeamScoreBefore = processing.SeamScoreBefore;
            Progress.SeamScoreAfter = processing.SeamScoreAfter;
            Progress.BackgroundRemovalApplied = processing.BackgroundRemovalApplied;
            Progress.BackgroundRemovalImplementation = processing.BackgroundRemovalImplementation;

            var parts = new List<string>();
            if (request.UseInpainting)
            {
                var operation = manifest?.Generation?.Operation ?? "inpainting";
                var strength = request.DenoisingStrength.ToString("0.###");
                var sourceMeta = manifest?.Request?.SourceImage;
                var maskMeta = manifest?.Request?.MaskImage;
                var convention = manifest?.Request?.MaskConvention ?? MaskBrushUtility.ConventionId;
                var sourceDetail = sourceMeta == null
                    ? string.Empty
                    : $" Source {sourceMeta.Width}×{sourceMeta.Height} {sourceMeta.Format}.";
                var maskDetail = maskMeta == null
                    ? string.Empty
                    : $" Mask {maskMeta.Width}×{maskMeta.Height} {maskMeta.Format}" +
                      (string.IsNullOrEmpty(maskMeta.Sha256)
                          ? "."
                          : $", sha256={maskMeta.Sha256.Substring(0, Math.Min(8, maskMeta.Sha256.Length))}….");
                parts.Add(
                    $"Operation: {operation} (masked inpainting, not img2img or reference conditioning). " +
                    $"Convention: {convention} (white regenerates, black is kept). " +
                    $"Denoising strength: {strength}.{sourceDetail}{maskDetail}");
            }
            else if (request.UseImageToImage)
            {
                var operation = manifest?.Generation?.Operation ?? "image_to_image";
                var strength = request.DenoisingStrength.ToString("0.###");
                var sourceMeta = manifest?.Request?.SourceImage;
                var sourceDetail = sourceMeta == null
                    ? string.Empty
                    : $" Source {sourceMeta.Width}×{sourceMeta.Height} {sourceMeta.Format}" +
                      (string.IsNullOrEmpty(sourceMeta.Sha256) ? "." : $", sha256={sourceMeta.Sha256.Substring(0, Math.Min(8, sourceMeta.Sha256.Length))}….");
                parts.Add(
                    $"Operation: {operation} (source used as init/latent image, not reference conditioning). " +
                    $"Denoising strength: {strength}.{sourceDetail}");
            }
            if (request.ApplySeamCorrection)
            {
                if (processing.SeamCorrectionApplied)
                {
                    parts.Add(
                        "AI seam repair: requested and applied" +
                        (string.IsNullOrEmpty(processing.SeamInpaintImplementation)
                            ? string.Empty
                            : $" ({processing.SeamInpaintImplementation})") +
                        (processing.SeamScoreBefore.HasValue && processing.SeamScoreAfter.HasValue
                            ? $"; seam score {processing.SeamScoreBefore.Value:0.###} → {processing.SeamScoreAfter.Value:0.###}"
                            : string.Empty) +
                        ". Final imported PNG is the repaired tile.");
                }
                else
                {
                    parts.Add(
                        "AI seam repair: requested but NOT applied (manifest seam_correction_applied=false). " +
                        "Final texture is unrepaired.");
                }
            }
            else if (processing.SeamCorrectionApplied)
            {
                parts.Add("AI seam repair: applied unexpectedly without a UI request — check backend logs.");
            }
            else
            {
                parts.Add("AI seam repair: not requested.");
            }

            if (string.Equals(request.TransparencyStrategy, "background_removal", StringComparison.OrdinalIgnoreCase))
            {
                parts.Add(processing.BackgroundRemovalApplied
                    ? "Transparent background: background_removal applied" +
                      (string.IsNullOrEmpty(processing.BackgroundRemovalImplementation)
                          ? "."
                          : $" ({processing.BackgroundRemovalImplementation}).")
                    : "Transparent background: requested but NOT applied.");
            }
            else if (request.AssetType == "sprite" || request.AssetType == "icon")
            {
                parts.Add("Transparent background: strategy=none (opaque RGB).");
            }

            Progress.ProcessingSummary = string.Join(" ", parts);
        }

        string BuildCompletionStatus(string assetPath)
        {
            if (!string.IsNullOrWhiteSpace(Progress.ProcessingSummary))
                return $"Imported {assetPath}. {Progress.ProcessingSummary}";
            return $"Imported texture at {assetPath}";
        }

        /// <summary>
        /// Ensures a usable (Ready or Stale) capability document is available, refreshing
        /// once if necessary. Returns null (with Progress already set to Failed) when
        /// capabilities are missing or incompatible, per the "disable generate" contract.
        /// </summary>
        async Task<CapabilityDocument> EnsureUsableCapabilitiesAsync(
            IGenerationApiClient client, string baseUrl, CancellationToken token)
        {
            var entry = _capabilityCache.Get(baseUrl);
            if (entry.State == CapabilityState.Unknown)
            {
                SetState(GenerationState.RefreshingCapabilities, "Fetching backend capabilities…");
                _capabilityCache.SetLoading(baseUrl);
                try
                {
                    var document = await client.GetCapabilitiesAsync(token).ConfigureAwait(true);
                    _capabilityCache.SetReady(baseUrl, document);
                    Progress.RequestId = client.LastRequestId ?? Progress.RequestId;
                }
                catch (Exception ex)
                {
                    var message = ex is ApiException api ? api.UserFacingMessage : ex.Message;
                    _capabilityCache.SetUnavailable(baseUrl, message);
                }

                entry = _capabilityCache.Get(baseUrl);
            }

            MirrorCapabilityState(baseUrl);

            if (entry.State == CapabilityState.Unavailable)
            {
                Progress.State = GenerationState.Failed;
                Progress.ErrorMessage = "Backend capabilities are unavailable: " + (entry.ErrorMessage ?? "unknown error.");
                Progress.StatusMessage = "Failed: could not load backend capabilities.";
                return null;
            }

            if (entry.State == CapabilityState.Incompatible)
            {
                Progress.State = GenerationState.Failed;
                Progress.ErrorMessage = "Backend capabilities are incompatible: " + (entry.ErrorMessage ?? "unknown reason.");
                Progress.StatusMessage = "Failed: backend capabilities are incompatible with this package.";
                return null;
            }

            return entry.Document;
        }

        void VerifyImageIntegrityOrThrow(byte[] png, GenerationManifestDocument manifest)
        {
            var imageOutput = manifest?.FindOutput("image");
            if (imageOutput == null)
            {
                // No manifest (older backend, or best-effort download failed) - nothing to verify against.
                return;
            }

            var expectedSize = imageOutput.ByteSize > 0 ? (long?)imageOutput.ByteSize : null;
            var result = ImageIntegrityVerifier.Verify(png, imageOutput.Sha256, expectedSize);
            if (!result.IsValid)
            {
                throw new ApiException(
                    $"Downloaded image failed integrity verification and was rejected before import: " +
                    $"{result.FailureReason}",
                    ApiFailureKind.Integrity,
                    requestId: Progress.RequestId);
            }
        }

        void MirrorCapabilityState(string baseUrl)
        {
            var entry = _capabilityCache.Get(baseUrl);
            Progress.CapabilityState = entry.State;
            Progress.Capabilities = entry.Document;
            Progress.CapabilityError = entry.ErrorMessage;

            if (entry.Document != null)
            {
                Progress.ApplicationVersion = entry.Document.Application?.Version;
                Progress.ModelId = entry.Document.Model?.Id;
                Progress.ModelFamily = entry.Document.Model?.Family;
                Progress.ResolvedDevice = entry.Document.Runtime?.ResolvedDevice;
                Progress.ResolvedPrecision = entry.Document.Runtime?.ResolvedPrecision;
                Progress.ModelLoaded = entry.Document.Runtime?.ModelLoaded ?? Progress.ModelLoaded;
            }
        }

        void InvalidateCacheOnUrlChange(string currentBaseUrl)
        {
            if (_lastKnownBackendBaseUrl != null &&
                !string.Equals(
                    CapabilityCache.NormalizeKey(_lastKnownBackendBaseUrl),
                    CapabilityCache.NormalizeKey(currentBaseUrl),
                    StringComparison.Ordinal))
            {
                // Do not delete the old entry outright (it may still be relevant if the user
                // switches back); simply stop treating it as "current" so a stale progress
                // mirror from a previous URL is not shown against the new one.
                Progress.CapabilityState = CapabilityState.Unknown;
                Progress.Capabilities = null;
                Progress.CapabilityError = null;
            }

            _lastKnownBackendBaseUrl = currentBaseUrl;
        }

        IGenerationApiClient CreateClient()
        {
            var client = _clientFactory();
            if (client == null)
            {
                throw new InvalidOperationException("API client factory returned null.");
            }

            return client;
        }

        void SetState(GenerationState state, string message)
        {
            Progress.State = state;
            Progress.StatusMessage = message;
            Progress.ErrorMessage = state == GenerationState.Failed ? Progress.ErrorMessage : null;
        }

        void Fail(Exception ex)
        {
            Progress.State = GenerationState.Failed;
            if (ex is ApiException api)
            {
                Progress.ErrorMessage = api.UserFacingMessage;
                Progress.StatusMessage = $"Failed ({api.Kind}): {api.UserFacingMessage}";
                if (!string.IsNullOrWhiteSpace(api.RequestId))
                {
                    Progress.RequestId = api.RequestId;
                }

                if (api.Kind == ApiFailureKind.Connection)
                {
                    Progress.BackendReachable = false;
                }
            }
            else
            {
                Progress.ErrorMessage = ex.Message;
                Progress.StatusMessage = "Failed: " + ex.Message;
            }
        }

        public async Task RefreshHistoryAsync()
        {
            if (IsBusy)
            {
                return;
            }

            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            try
            {
                using var client = CreateClient();
                SetState(GenerationState.CheckingConnection, "Loading generation history…");
                await RefreshHistorySilentAsync(client, _cts.Token).ConfigureAwait(true);
                SetState(GenerationState.Idle, $"Loaded {Progress.History.Count} recent jobs.");
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task ImportHistoryJobAsync(string jobId, TextureGenerationRequestModel request)
        {
            if (request == null)
            {
                throw new ArgumentNullException(nameof(request));
            }

            if (IsBusy || string.IsNullOrWhiteSpace(jobId))
            {
                return;
            }

            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;
            try
            {
                using var client = CreateClient();
                SetState(GenerationState.Downloading, "Loading completed job…");
                var job = await client.GetJobAsync(jobId, token).ConfigureAwait(true);
                ApplyJobProgress(job);
                if (!job.CanImport)
                {
                    Progress.State = GenerationState.Failed;
                    Progress.ErrorMessage = "That job has no completed result to import.";
                    Progress.StatusMessage = Progress.ErrorMessage;
                    return;
                }

                await ImportCompletedJobAsync(client, job, request, token).ConfigureAwait(true);
            }
            catch (OperationCanceledException)
            {
                Progress.State = GenerationState.Cancelled;
                Progress.StatusMessage = "Import cancelled.";
                Progress.ErrorMessage = Progress.StatusMessage;
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task RetryHistoryJobAsync(string jobId, TextureGenerationRequestModel request)
        {
            if (request == null)
            {
                throw new ArgumentNullException(nameof(request));
            }

            if (IsBusy || string.IsNullOrWhiteSpace(jobId))
            {
                return;
            }

            _cts?.Cancel();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;
            try
            {
                using var client = CreateClient();
                SetState(GenerationState.Submitting, "Retrying failed job…");
                var job = await client.RetryJobAsync(jobId, token).ConfigureAwait(true);
                ApplyJobProgress(job);
                SetState(GenerationState.Generating, FormatJobStatus(job));
                job = await WaitForJobAsync(client, job.JobId, token).ConfigureAwait(true);
                if (job.State != "completed" || job.Result == null)
                {
                    Progress.State = job.State == "cancelled" ? GenerationState.Cancelled : GenerationState.Failed;
                    Progress.ErrorMessage = job.Error != null
                        ? $"{job.Error.Code}: {job.Error.Message}"
                        : $"Retry ended in state {job.State}.";
                    Progress.StatusMessage = Progress.ErrorMessage;
                    await RefreshHistorySilentAsync(client, token).ConfigureAwait(true);
                    return;
                }

                await ImportCompletedJobAsync(client, job, request, token).ConfigureAwait(true);
            }
            catch (OperationCanceledException)
            {
                Progress.State = GenerationState.Cancelled;
                Progress.StatusMessage = "Retry cancelled.";
                Progress.ErrorMessage = Progress.StatusMessage;
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
        }

        public async Task CancelHistoryJobAsync(string jobId)
        {
            if (string.IsNullOrWhiteSpace(jobId))
            {
                return;
            }

            try
            {
                using var client = CreateClient();
                var job = await client.CancelJobAsync(jobId, CancellationToken.None).ConfigureAwait(true);
                ApplyJobProgress(job);
                await RefreshHistorySilentAsync(client, CancellationToken.None).ConfigureAwait(true);
                if (!IsBusy)
                {
                    SetState(GenerationState.Idle, $"Job {job.State}: {job.PromptSummary}");
                }
            }
            catch (Exception ex)
            {
                if (!IsBusy)
                {
                    Fail(ex);
                }
            }
        }

        async Task ImportCompletedJobAsync(
            IGenerationApiClient client,
            JobDocument job,
            TextureGenerationRequestModel request,
            CancellationToken token)
        {
            var response = ToGenerationResponse(job);
            Progress.GenerationId = response.generation_id;
            Progress.Seed = response.seed;
            Progress.ElapsedSeconds = response.elapsed_seconds;
            Progress.Operation = response.operation;
            SetState(GenerationState.Downloading, "Downloading generated PNG and manifest…");
            var png = await client
                .DownloadGenerationImageAsync(response.generation_id, response.resources?.image, token)
                .ConfigureAwait(true);

            GenerationManifestDocument manifest = null;
            BackendMetadataDto legacyMetadata = null;
            try
            {
                manifest = await client
                    .DownloadGenerationManifestAsync(response.generation_id, response.resources?.manifest, token)
                    .ConfigureAwait(true);
            }
            catch (ApiException)
            {
                try
                {
                    legacyMetadata = await client
                        .DownloadGenerationMetadataAsync(response.generation_id, token)
                        .ConfigureAwait(true);
                }
                catch (ApiException)
                {
                }
            }

            token.ThrowIfCancellationRequested();
            VerifyImageIntegrityOrThrow(png, manifest);
            ApplyProcessingProvenance(request, manifest);

            SetState(GenerationState.Importing, "Importing texture into the Unity project…");
            var settings = UnityAiAssetSettings.instance;
            var selectedProfile = _profileRegistry.Get(request.SelectedProfileId);
            var capabilities = Progress.Capabilities;
            ResolvedGenerationSettings resolved = null;
            try
            {
                if (capabilities != null)
                {
                    resolved = _profileResolver.Resolve(selectedProfile, new UserProfileOverrides
                    {
                        Subject = request.Subject,
                        DestinationFolder = request.DestinationFolder,
                        ImportProfileId = request.ImportProfileId,
                        OutputName = request.OutputName,
                        CreateMaterial = request.CreateMaterial,
                    }, capabilities);
                }
            }
            catch (Exception)
            {
                resolved = null;
            }

            var profile = !string.IsNullOrWhiteSpace(request.ImportProfileId)
                ? _catalog.GetImportProfile(request.ImportProfileId)
                : _catalog.FromLegacyKind(request.ImportProfile);
            profile = profile.Copy();
            if (resolved != null && (request.AssetType == "sprite" || request.AssetType == "icon"))
            {
                profile.PixelsPerUnit = resolved.PixelsPerUnit;
                profile.PivotMode = resolved.PivotMode;
                profile.CustomPivotX = resolved.CustomPivotX;
                profile.CustomPivotY = resolved.CustomPivotY;
            }

            var import = _assetImporter.ImportPng(
                png,
                request.DestinationFolder,
                request.OutputName,
                profile);
            Progress.ImportedTexturePath = import.AssetPath;

            var imageUrl = !string.IsNullOrWhiteSpace(response.resources?.image)
                ? response.resources.image
                : ApiEndpoints.GenerationImage(response.generation_id);
            var manifestUrl = !string.IsNullOrWhiteSpace(response.resources?.manifest)
                ? response.resources.manifest
                : ApiEndpoints.GenerationManifest(response.generation_id);

            var metadataAsset = _metadataImporter.Create(
                import.Texture,
                import.AssetPath,
                settings.BackendBaseUrl,
                response,
                manifest,
                legacyMetadata,
                imageUrl,
                manifestUrl,
                Progress.RequestId);
            Progress.MetadataAssetPath = UnityEditor.AssetDatabase.GetAssetPath(metadataAsset);

            if (request.CreateMaterial)
            {
                var material = _materialFactory.CreateMaterial(
                    import.Texture,
                    request.MaterialDestinationFolder,
                    request.OutputName,
                    request.ShaderName);
                Progress.ImportedMaterialPath = UnityEditor.AssetDatabase.GetAssetPath(material);
            }

            await RefreshHistorySilentAsync(client, token).ConfigureAwait(true);
            SetState(GenerationState.Completed, BuildCompletionStatus(import.AssetPath));
        }

        async Task<JobDocument> WaitForJobAsync(
            IGenerationApiClient client, string jobId, CancellationToken token)
        {
            var startedUtc = DateTime.UtcNow;
            while (true)
            {
                token.ThrowIfCancellationRequested();
                var job = await client.GetJobAsync(jobId, token).ConfigureAwait(true);
                ApplyJobProgress(job);
                if (job.IsTerminal)
                {
                    return job;
                }

                var waited = (DateTime.UtcNow - startedUtc).TotalSeconds;
                Progress.StatusMessage = FormatJobStatus(job) + $" ({waited:0}s)";
                await Task.Delay(400, token).ConfigureAwait(true);
            }
        }

        async Task RefreshHistorySilentAsync(IGenerationApiClient client, CancellationToken token)
        {
            try
            {
                var list = await client.ListJobsAsync(token).ConfigureAwait(true);
                Progress.History = list.Jobs ?? new List<JobDocument>();
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception)
            {
                // History is best-effort and must not fail generation/import.
            }
        }

        void ApplyJobProgress(JobDocument job)
        {
            if (job == null)
            {
                return;
            }

            Progress.JobId = job.JobId;
            Progress.JobState = job.State;
            Progress.JobStage = job.Progress != null ? job.Progress.Stage : job.State;
            if (job.Seed.HasValue)
            {
                Progress.Seed = job.Seed;
            }

            if (job.Result != null)
            {
                Progress.GenerationId = job.Result.GenerationId;
                Progress.ElapsedSeconds = job.Result.ElapsedSeconds;
                Progress.Operation = job.Result.Operation;
            }
        }

        static string FormatJobStatus(JobDocument job)
        {
            var stage = job.Progress != null && !string.IsNullOrWhiteSpace(job.Progress.Message)
                ? job.Progress.Message
                : job.State;
            if (job.Progress != null && job.Progress.CurrentStep.HasValue && job.Progress.TotalSteps.HasValue)
            {
                return $"{stage} ({job.Progress.CurrentStep}/{job.Progress.TotalSteps})";
            }

            return stage;
        }

        static TextureGenerationResponseDto ToGenerationResponse(JobDocument job)
        {
            var result = job.Result;
            return new TextureGenerationResponseDto
            {
                generation_id = result.GenerationId,
                status = result.Status,
                operation = result.Operation,
                asset_type = result.AssetType,
                seed = result.Seed,
                width = result.Width,
                height = result.Height,
                elapsed_seconds = result.ElapsedSeconds,
                resources = result.Resources,
                schema_versions = result.SchemaVersions,
            };
        }

        static void ValidateRequestStructure(TextureGenerationRequestModel request)
        {
            if (string.IsNullOrWhiteSpace(request.Subject) && string.IsNullOrWhiteSpace(request.Prompt))
            {
                throw new ArgumentException("Subject is required.");
            }

            AssetPathUtility.NormalizeAssetPath(request.DestinationFolder);
            if (request.CreateMaterial)
            {
                AssetPathUtility.NormalizeAssetPath(request.MaterialDestinationFolder);
                if (string.IsNullOrWhiteSpace(request.ShaderName))
                {
                    throw new ArgumentException("Shader name is required when creating a material.");
                }
            }
        }
    }
}
