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
using UnityEngine;

namespace UnityAiAssets.Editor.Generation
{
    public sealed class TextureGenerationProgress
    {
        public GenerationState State = GenerationState.Idle;
        public string StatusMessage = "Idle";
        public string ErrorMessage;
        public bool BackendReachable;

        /// <summary>Deprecated: prefer <see cref="ResolvedDevice"/>.</summary>
        public string BackendDevice;

        public bool ModelLoaded;
        public string GenerationId;
        public long? Seed;
        public float? ElapsedSeconds;
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

        public bool CapabilitiesUsable =>
            CapabilityState == CapabilityState.Ready || CapabilityState == CapabilityState.Stale;

        public bool CanGenerate =>
            CapabilitiesUsable && Capabilities != null && Capabilities.Operations?.TextToImage?.Supported == true;
    }

    /// <summary>
    /// Orchestrates capability discovery, health checks, generation, download, integrity
    /// verification, import, metadata/manifest, and materials.
    /// </summary>
    public sealed class TextureGenerationController
    {
        readonly Func<IGenerationApiClient> _clientFactory;
        readonly GeneratedTextureImporter _textureImporter;
        readonly GenerationMetadataImporter _metadataImporter;
        readonly MaterialFactory _materialFactory;
        readonly CapabilityCache _capabilityCache;

        CancellationTokenSource _cts;
        string _lastKnownBackendBaseUrl;

        public TextureGenerationController(
            Func<IGenerationApiClient> clientFactory = null,
            GeneratedTextureImporter textureImporter = null,
            GenerationMetadataImporter metadataImporter = null,
            MaterialFactory materialFactory = null,
            CapabilityCache capabilityCache = null)
        {
            _clientFactory = clientFactory ?? (() =>
            {
                var settings = UnityAiAssetSettings.instance;
                return new GenerationApiClient(settings.BackendBaseUrl, settings.ApiTimeoutSeconds);
            });
            _textureImporter = textureImporter ?? new GeneratedTextureImporter();
            _metadataImporter = metadataImporter ?? new GenerationMetadataImporter();
            _materialFactory = materialFactory ?? new MaterialFactory();
            _capabilityCache = capabilityCache ?? CapabilityCache.Shared;
            Progress = new TextureGenerationProgress();
        }

        public TextureGenerationProgress Progress { get; }

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
                Progress.BackendDevice = health.resolved_device;
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
            Progress.Seed = null;
            Progress.ElapsedSeconds = null;
            Progress.ValidationIssues = new List<CapabilityValidationIssue>();

            try
            {
                using var client = CreateClient();

                var capabilities = await EnsureUsableCapabilitiesAsync(client, baseUrl, token).ConfigureAwait(true);
                if (capabilities == null)
                {
                    // EnsureUsableCapabilitiesAsync already set Progress.State/ErrorMessage.
                    return;
                }

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

                SetState(GenerationState.Submitting, "Submitting texture generation request…");
                var dto = new TextureGenerationRequestDto
                {
                    prompt = request.Prompt.Trim(),
                    negative_prompt = request.NegativePrompt ?? string.Empty,
                    width = request.Width,
                    height = request.Height,
                    steps = request.Steps,
                    guidance_scale = request.GuidanceScale,
                    seed = request.UseExplicitSeed ? request.Seed : (long?)null,
                    output_name = request.OutputName.Trim()
                };

                SetState(GenerationState.Generating, "Waiting for backend generation…");
                var generateTask = client.GenerateTextureAsync(dto, token);
                var startedUtc = DateTime.UtcNow;
                while (!generateTask.IsCompleted)
                {
                    var waited = (DateTime.UtcNow - startedUtc).TotalSeconds;
                    Progress.StatusMessage =
                        $"Waiting for backend generation… {waited:0}s elapsed " +
                        $"(timeout {settings.ApiTimeoutSeconds}s). Watch the Python console.";
                    try
                    {
                        await Task.WhenAny(generateTask, Task.Delay(500, token)).ConfigureAwait(true);
                    }
                    catch (OperationCanceledException)
                    {
                        throw;
                    }
                }

                var response = await generateTask.ConfigureAwait(true);
                Progress.GenerationId = response.generation_id;
                Progress.Seed = response.seed;
                Progress.ElapsedSeconds = response.elapsed_seconds;
                Progress.RequestId = client.LastRequestId ?? Progress.RequestId;

                SetState(GenerationState.Downloading, "Downloading generated PNG and manifest…");
                var png = await client.DownloadGenerationImageAsync(response.generation_id, token)
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
                    // Manifest download is best-effort against older backends; fall back below.
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

                SetState(GenerationState.Importing, "Importing texture into the Unity project…");
                var profile = TextureImportProfile.FromKind(request.ImportProfile);
                var import = _textureImporter.ImportPng(
                    png,
                    request.DestinationFolder,
                    request.OutputName,
                    profile);
                Progress.ImportedTexturePath = import.AssetPath;

                var imageUrl = FirstNonEmpty(response.resources?.image, response.image_url) ??
                               ApiEndpoints.GenerationImage(response.generation_id);
                var manifestUrl = FirstNonEmpty(response.resources?.manifest, response.metadata_url) ??
                               ApiEndpoints.GenerationManifest(response.generation_id);

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

                SetState(
                    GenerationState.Completed,
                    $"Imported texture at {import.AssetPath}");
            }
            catch (OperationCanceledException)
            {
                Progress.State = GenerationState.Cancelled;
                Progress.StatusMessage =
                    "Local wait cancelled. Backend generation may still complete; nothing was imported.";
                Progress.ErrorMessage = Progress.StatusMessage;
            }
            catch (Exception ex)
            {
                Fail(ex);
            }
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

        static string FirstNonEmpty(string a, string b) => !string.IsNullOrWhiteSpace(a) ? a : b;

        static void ValidateRequestStructure(TextureGenerationRequestModel request)
        {
            if (string.IsNullOrWhiteSpace(request.Prompt))
            {
                throw new ArgumentException("Prompt is required.");
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
