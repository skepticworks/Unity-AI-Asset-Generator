using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace UnityAiAssets.Editor.Api
{
    public interface IGenerationApiClient : IDisposable
    {
        /// <summary>The X-Request-ID header from the most recently completed response, if any.</summary>
        string LastRequestId { get; }

        Task<HealthResponseDto> GetHealthAsync(CancellationToken cancellationToken);

        Task<CapabilityDocument> GetCapabilitiesAsync(CancellationToken cancellationToken);

        Task<TextureGenerationResponseDto> GenerateTextureAsync(
            TextureGenerationRequestDto request,
            CancellationToken cancellationToken);

        Task<JobDocument> SubmitJobAsync(
            TextureGenerationRequestDto request,
            CancellationToken cancellationToken);

        Task<JobDocument> GetJobAsync(string jobId, CancellationToken cancellationToken);

        Task<JobListDocument> ListJobsAsync(CancellationToken cancellationToken, int limit = 50);

        Task<JobDocument> CancelJobAsync(string jobId, CancellationToken cancellationToken);

        Task<JobDocument> RetryJobAsync(string jobId, CancellationToken cancellationToken);

        Task<BatchPreviewDocument> PreviewBatchAsync(
            BatchSubmitRequestDto request, CancellationToken cancellationToken);

        Task<BatchDocument> SubmitBatchAsync(
            BatchSubmitRequestDto request, CancellationToken cancellationToken);

        Task<BatchDocument> GetBatchAsync(string batchId, CancellationToken cancellationToken);

        Task<BatchListDocument> ListBatchesAsync(CancellationToken cancellationToken, int limit = 50);

        Task<BatchDocument> CancelBatchAsync(string batchId, CancellationToken cancellationToken);

        Task<BatchDocument> RetryFailedBatchAsync(string batchId, CancellationToken cancellationToken);

        Task<ModelListDocument> ListModelsAsync(CancellationToken cancellationToken);

        Task<InstalledModelDocument> GetModelAsync(string modelId, CancellationToken cancellationToken);

        Task<InstalledModelDocument> InstallModelAsync(string jsonBody, CancellationToken cancellationToken);

        Task<InstalledModelDocument> ValidateModelAsync(string modelId, CancellationToken cancellationToken);

        Task<InstalledModelDocument> ActivateModelAsync(string modelId, CancellationToken cancellationToken);

        Task DeleteModelAsync(string modelId, bool confirm, CancellationToken cancellationToken);

        Task<ModelStorageDocument> GetModelStorageAsync(CancellationToken cancellationToken);

        Task<ModelStorageDocument> UpdateModelStorageAsync(string directory, CancellationToken cancellationToken);

        Task<ModelDiskUsageDocument> RefreshModelDiskUsageAsync(CancellationToken cancellationToken);

        Task<bool> SetOfflineModeAsync(bool enabled, CancellationToken cancellationToken);

        Task<byte[]> DownloadGenerationImageAsync(string generationId, CancellationToken cancellationToken);

        /// <summary>
        /// Downloads the generation PNG, preferring an explicit resource path
        /// (typically <c>resources.image</c>) and falling back to the conventional image endpoint.
        /// </summary>
        Task<byte[]> DownloadGenerationImageAsync(
            string generationId,
            string imageResourcePath,
            CancellationToken cancellationToken);

        /// <summary>
        /// Downloads the versioned generation manifest, preferring an explicit resource path
        /// (typically <c>resources.manifest</c> from the generation response) and falling back
        /// to the conventional <c>/manifest</c> endpoint when none is supplied.
        /// </summary>
        Task<GenerationManifestDocument> DownloadGenerationManifestAsync(
            string generationId,
            string manifestResourcePath,
            CancellationToken cancellationToken);

        /// <summary>Deprecated: superseded by <see cref="DownloadGenerationManifestAsync"/>.</summary>
        Task<BackendMetadataDto> DownloadGenerationMetadataAsync(
            string generationId,
            CancellationToken cancellationToken);
    }

    /// <summary>
    /// Typed HTTP client for the local FastAPI backend.
    /// Uses HttpClient so long-running generation POSTs do not stall like UnityWebRequest can.
    /// </summary>
    public sealed class GenerationApiClient : IGenerationApiClient
    {
        const string RequestIdHeader = "X-Request-ID";

        readonly HttpClient _http;
        readonly int _timeoutSeconds;

        public GenerationApiClient(string baseUrl, int timeoutSeconds)
        {
            if (string.IsNullOrWhiteSpace(baseUrl))
            {
                throw new ArgumentException("Backend base URL is required.", nameof(baseUrl));
            }

            _timeoutSeconds = Math.Max(5, timeoutSeconds);
            var root = baseUrl.Trim().TrimEnd('/') + "/";
            _http = new HttpClient
            {
                BaseAddress = new Uri(root, UriKind.Absolute),
                Timeout = Timeout.InfiniteTimeSpan
            };
        }

        public string LastRequestId { get; private set; }

        public void Dispose()
        {
            _http.Dispose();
        }

        public async Task<HealthResponseDto> GetHealthAsync(CancellationToken cancellationToken)
        {
            var body = await GetStringAsync(
                ApiEndpoints.Health, Math.Min(30, _timeoutSeconds), cancellationToken).ConfigureAwait(true);
            return Deserialize<HealthResponseDto>(body);
        }

        public async Task<CapabilityDocument> GetCapabilitiesAsync(CancellationToken cancellationToken)
        {
            var body = await GetStringAsync(
                ApiEndpoints.Capabilities, Math.Min(30, _timeoutSeconds), cancellationToken).ConfigureAwait(true);
            if (!CapabilityDocument.TryParse(body, out var document))
            {
                throw new ApiException(
                    "Failed to parse the capabilities document returned by the backend.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<TextureGenerationResponseDto> GenerateTextureAsync(
            TextureGenerationRequestDto requestDto,
            CancellationToken cancellationToken)
        {
            if (requestDto == null)
            {
                throw new ArgumentNullException(nameof(requestDto));
            }

            var body = await PostJsonAsync(
                ApiEndpoints.GenerateTexture, requestDto.ToJson(), _timeoutSeconds, cancellationToken)
                .ConfigureAwait(true);
            return Deserialize<TextureGenerationResponseDto>(body);
        }

        public async Task<JobDocument> SubmitJobAsync(
            TextureGenerationRequestDto requestDto,
            CancellationToken cancellationToken)
        {
            if (requestDto == null)
            {
                throw new ArgumentNullException(nameof(requestDto));
            }

            var body = await PostJsonAsync(
                ApiEndpoints.Jobs, requestDto.ToJson(), Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            return ParseJob(body);
        }

        public async Task<JobDocument> GetJobAsync(string jobId, CancellationToken cancellationToken)
        {
            ValidateJobId(jobId);
            var body = await GetStringAsync(
                ApiEndpoints.Job(jobId), Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            return ParseJob(body);
        }

        public async Task<JobListDocument> ListJobsAsync(
            CancellationToken cancellationToken, int limit = 50)
        {
            var path = ApiEndpoints.Jobs + "?limit=" + Math.Max(1, Math.Min(200, limit));
            var body = await GetStringAsync(
                path, Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            if (!JobListDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse the job history returned by the backend.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<JobDocument> CancelJobAsync(string jobId, CancellationToken cancellationToken)
        {
            ValidateJobId(jobId);
            var body = await PostJsonAsync(
                ApiEndpoints.JobCancel(jobId), "{}", Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            return ParseJob(body);
        }

        public async Task<JobDocument> RetryJobAsync(string jobId, CancellationToken cancellationToken)
        {
            ValidateJobId(jobId);
            var body = await PostJsonAsync(
                ApiEndpoints.JobRetry(jobId), "{}", Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            return ParseJob(body);
        }

        public async Task<ModelListDocument> ListModelsAsync(CancellationToken cancellationToken)
        {
            var body = await GetStringAsync(
                ApiEndpoints.Models, Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            if (!ModelListDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse the model catalog returned by the backend.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<InstalledModelDocument> GetModelAsync(
            string modelId, CancellationToken cancellationToken)
        {
            ValidateModelId(modelId);
            var body = await GetStringAsync(
                ApiEndpoints.Model(modelId), Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            return ParseModel(body);
        }

        public async Task<InstalledModelDocument> InstallModelAsync(
            string jsonBody, CancellationToken cancellationToken)
        {
            var body = await PostJsonAsync(
                ApiEndpoints.ModelInstall, jsonBody, _timeoutSeconds, cancellationToken)
                .ConfigureAwait(true);
            return ParseModel(body);
        }

        public async Task<InstalledModelDocument> ValidateModelAsync(
            string modelId, CancellationToken cancellationToken)
        {
            ValidateModelId(modelId);
            var body = await PostJsonAsync(
                ApiEndpoints.ModelValidate(modelId), "{}", Math.Min(120, _timeoutSeconds),
                cancellationToken)
                .ConfigureAwait(true);
            return ParseModel(body);
        }

        public async Task<InstalledModelDocument> ActivateModelAsync(
            string modelId, CancellationToken cancellationToken)
        {
            ValidateModelId(modelId);
            var body = await PostJsonAsync(
                ApiEndpoints.ModelActivate(modelId), "{}", Math.Min(30, _timeoutSeconds),
                cancellationToken)
                .ConfigureAwait(true);
            return ParseModel(body);
        }

        public async Task DeleteModelAsync(
            string modelId, bool confirm, CancellationToken cancellationToken)
        {
            ValidateModelId(modelId);
            var path = ApiEndpoints.Model(modelId) + (confirm ? "?confirm=true" : "?confirm=false");
            await DeleteAsync(path, Math.Min(60, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
        }

        public async Task<ModelStorageDocument> GetModelStorageAsync(CancellationToken cancellationToken)
        {
            var body = await GetStringAsync(
                ApiEndpoints.ModelStorage, Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            if (!ModelStorageDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse model storage status.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<ModelStorageDocument> UpdateModelStorageAsync(
            string directory, CancellationToken cancellationToken)
        {
            var json = JsonWriter.Serialize(
                new Dictionary<string, object> { { "directory", directory ?? string.Empty } },
                indented: false);
            var body = await PutJsonAsync(
                ApiEndpoints.ModelStorage, json, Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            if (!ModelStorageDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse the updated model storage status.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<ModelDiskUsageDocument> RefreshModelDiskUsageAsync(
            CancellationToken cancellationToken)
        {
            var body = await PostJsonAsync(
                ApiEndpoints.ModelDiskUsageRefresh, "{}", Math.Min(120, _timeoutSeconds),
                cancellationToken)
                .ConfigureAwait(true);
            if (!ModelDiskUsageDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse model disk usage.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<bool> SetOfflineModeAsync(bool enabled, CancellationToken cancellationToken)
        {
            var json = JsonWriter.Serialize(
                new Dictionary<string, object> { { "enabled", enabled } },
                indented: false);
            var body = await PutJsonAsync(
                ApiEndpoints.ModelOffline, json, Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            if (!JsonNode.TryParse(body, out var node) || node == null)
            {
                throw new ApiException(
                    "Failed to parse the offline-mode response.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return node.Get("offline_mode").AsBool(enabled);
        }

        InstalledModelDocument ParseModel(string body)
        {
            if (!InstalledModelDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse the model record returned by the backend.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        JobDocument ParseJob(string body)
        {
            if (!JobDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse the job record returned by the backend.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<BatchPreviewDocument> PreviewBatchAsync(
            BatchSubmitRequestDto requestDto,
            CancellationToken cancellationToken)
        {
            if (requestDto == null)
                throw new ArgumentNullException(nameof(requestDto));
            var body = await PostJsonAsync(
                ApiEndpoints.BatchPreview, requestDto.ToJson(), Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            if (!BatchPreviewDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse the batch preview returned by the backend.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<BatchDocument> SubmitBatchAsync(
            BatchSubmitRequestDto requestDto,
            CancellationToken cancellationToken)
        {
            if (requestDto == null)
                throw new ArgumentNullException(nameof(requestDto));
            var body = await PostJsonAsync(
                ApiEndpoints.Batches, requestDto.ToJson(), Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            return ParseBatch(body);
        }

        public async Task<BatchDocument> GetBatchAsync(string batchId, CancellationToken cancellationToken)
        {
            ValidateBatchId(batchId);
            var body = await GetStringAsync(
                ApiEndpoints.Batch(batchId), Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            return ParseBatch(body);
        }

        public async Task<BatchListDocument> ListBatchesAsync(
            CancellationToken cancellationToken, int limit = 50)
        {
            var path = ApiEndpoints.Batches + "?limit=" + Math.Max(1, Math.Min(200, limit));
            var body = await GetStringAsync(
                path, Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            if (!BatchListDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse the batch history returned by the backend.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<BatchDocument> CancelBatchAsync(string batchId, CancellationToken cancellationToken)
        {
            ValidateBatchId(batchId);
            var body = await PostJsonAsync(
                ApiEndpoints.BatchCancel(batchId), "{}", Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            return ParseBatch(body);
        }

        public async Task<BatchDocument> RetryFailedBatchAsync(
            string batchId, CancellationToken cancellationToken)
        {
            ValidateBatchId(batchId);
            var body = await PostJsonAsync(
                ApiEndpoints.BatchRetryFailed(batchId), "{}", Math.Min(30, _timeoutSeconds), cancellationToken)
                .ConfigureAwait(true);
            return ParseBatch(body);
        }

        BatchDocument ParseBatch(string body)
        {
            if (!BatchDocument.TryParse(body, out var document) || document == null)
            {
                throw new ApiException(
                    "Failed to parse the batch record returned by the backend.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<byte[]> DownloadGenerationImageAsync(
            string generationId,
            CancellationToken cancellationToken) =>
            await DownloadGenerationImageAsync(generationId, null, cancellationToken).ConfigureAwait(true);

        public async Task<byte[]> DownloadGenerationImageAsync(
            string generationId,
            string imageResourcePath,
            CancellationToken cancellationToken)
        {
            ValidateGenerationId(generationId);
            var path = string.IsNullOrWhiteSpace(imageResourcePath)
                ? ApiEndpoints.GenerationImage(generationId)
                : imageResourcePath;
            var bytes = await GetBytesAsync(
                path, _timeoutSeconds, cancellationToken)
                .ConfigureAwait(true);
            if (bytes == null || bytes.Length == 0)
            {
                throw new ApiException(
                    "Image download returned empty content.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            if (bytes.Length < 8 ||
                bytes[0] != 0x89 || bytes[1] != 0x50 || bytes[2] != 0x4E || bytes[3] != 0x47)
            {
                throw new ApiException(
                    "Image download did not contain a PNG payload.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return bytes;
        }

        public async Task<GenerationManifestDocument> DownloadGenerationManifestAsync(
            string generationId,
            string manifestResourcePath,
            CancellationToken cancellationToken)
        {
            ValidateGenerationId(generationId);
            var path = string.IsNullOrWhiteSpace(manifestResourcePath)
                ? ApiEndpoints.GenerationManifest(generationId)
                : manifestResourcePath;
            var body = await GetStringAsync(path, _timeoutSeconds, cancellationToken).ConfigureAwait(true);
            if (!GenerationManifestDocument.TryParse(body, out var document))
            {
                throw new ApiException(
                    "Failed to parse the generation manifest returned by the backend.",
                    ApiFailureKind.Deserialization,
                    requestId: LastRequestId);
            }

            return document;
        }

        public async Task<BackendMetadataDto> DownloadGenerationMetadataAsync(
            string generationId,
            CancellationToken cancellationToken)
        {
            ValidateGenerationId(generationId);
            var body = await GetStringAsync(
                ApiEndpoints.GenerationMetadata(generationId), _timeoutSeconds, cancellationToken)
                .ConfigureAwait(true);
            return Deserialize<BackendMetadataDto>(body);
        }

        async Task<string> GetStringAsync(
            string path, int timeoutSeconds, CancellationToken cancellationToken)
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, TrimOrAbsolute(path));
            using var response = await SendWithTimeoutAsync(request, timeoutSeconds, cancellationToken)
                .ConfigureAwait(true);
            var body = await response.Content.ReadAsStringAsync().ConfigureAwait(true);
            EnsureSuccess(response, body);
            return body;
        }

        async Task<string> PostJsonAsync(
            string path, string json, int timeoutSeconds, CancellationToken cancellationToken)
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, TrimOrAbsolute(path))
            {
                Content = new StringContent(json, Encoding.UTF8, "application/json")
            };
            using var response = await SendWithTimeoutAsync(request, timeoutSeconds, cancellationToken)
                .ConfigureAwait(true);
            var body = await response.Content.ReadAsStringAsync().ConfigureAwait(true);
            EnsureSuccess(response, body);
            return body;
        }

        async Task<string> PutJsonAsync(
            string path, string json, int timeoutSeconds, CancellationToken cancellationToken)
        {
            using var request = new HttpRequestMessage(HttpMethod.Put, TrimOrAbsolute(path))
            {
                Content = new StringContent(json, Encoding.UTF8, "application/json")
            };
            using var response = await SendWithTimeoutAsync(request, timeoutSeconds, cancellationToken)
                .ConfigureAwait(true);
            var body = await response.Content.ReadAsStringAsync().ConfigureAwait(true);
            EnsureSuccess(response, body);
            return body;
        }

        async Task DeleteAsync(
            string path, int timeoutSeconds, CancellationToken cancellationToken)
        {
            using var request = new HttpRequestMessage(HttpMethod.Delete, TrimOrAbsolute(path));
            using var response = await SendWithTimeoutAsync(request, timeoutSeconds, cancellationToken)
                .ConfigureAwait(true);
            var body = await response.Content.ReadAsStringAsync().ConfigureAwait(true);
            EnsureSuccess(response, body);
        }

        async Task<byte[]> GetBytesAsync(
            string path, int timeoutSeconds, CancellationToken cancellationToken)
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, TrimOrAbsolute(path));
            using var response = await SendWithTimeoutAsync(request, timeoutSeconds, cancellationToken)
                .ConfigureAwait(true);
            if (!response.IsSuccessStatusCode)
            {
                var body = await response.Content.ReadAsStringAsync().ConfigureAwait(true);
                EnsureSuccess(response, body);
            }
            return await response.Content.ReadAsByteArrayAsync().ConfigureAwait(true);
        }

        async Task<HttpResponseMessage> SendWithTimeoutAsync(
            HttpRequestMessage request, int timeoutSeconds, CancellationToken cancellationToken)
        {
            using var timeoutCts = new CancellationTokenSource(TimeSpan.FromSeconds(timeoutSeconds));
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken, timeoutCts.Token);
            return await SendAsync(request, linked.Token, cancellationToken, timeoutSeconds)
                .ConfigureAwait(true);
        }

        async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken linkedToken,
            CancellationToken userToken,
            int timeoutSeconds)
        {
            try
            {
                var response = await _http.SendAsync(
                        request,
                        HttpCompletionOption.ResponseContentRead,
                        linkedToken)
                    .ConfigureAwait(true);
                CaptureRequestId(response);
                return response;
            }
            catch (OperationCanceledException) when (userToken.IsCancellationRequested)
            {
                throw new ApiException(
                    "Request cancelled locally. The backend may still be generating.",
                    ApiFailureKind.Cancelled);
            }
            catch (OperationCanceledException)
            {
                throw new ApiException(
                    $"Request timed out after {timeoutSeconds}s. " +
                    "Increase API Timeout in Project Settings, or lower width/height/steps. " +
                    "Check the Python backend console for activity.",
                    ApiFailureKind.Timeout);
            }
            catch (HttpRequestException ex)
            {
                throw new ApiException(
                    "Could not connect to the backend. Is uvicorn running on the configured URL? " +
                    ex.Message,
                    ApiFailureKind.Connection,
                    innerException: ex);
            }
        }

        void CaptureRequestId(HttpResponseMessage response)
        {
            if (response.Headers.TryGetValues(RequestIdHeader, out var values))
            {
                foreach (var value in values)
                {
                    if (!string.IsNullOrWhiteSpace(value))
                    {
                        LastRequestId = value;
                        return;
                    }
                }
            }
        }

        static string Trim(string endpoint) =>
            string.IsNullOrEmpty(endpoint) ? string.Empty : endpoint.TrimStart('/');

        static string TrimOrAbsolute(string endpoint)
        {
            if (string.IsNullOrEmpty(endpoint))
            {
                return string.Empty;
            }

            return Uri.IsWellFormedUriString(endpoint, UriKind.Absolute) ? endpoint : Trim(endpoint);
        }

        void EnsureSuccess(HttpResponseMessage response, string body)
        {
            if (response.IsSuccessStatusCode)
            {
                return;
            }

            var status = response.StatusCode;
            var kind = Classify(status);

            if (!string.IsNullOrWhiteSpace(body) && body.TrimStart().StartsWith("{", StringComparison.Ordinal))
            {
                if (ErrorEnvelope.TryParse(body, out var envelope))
                {
                    var requestId = !string.IsNullOrWhiteSpace(envelope.RequestId) ? envelope.RequestId : LastRequestId;
                    var message = !string.IsNullOrWhiteSpace(envelope.Message)
                        ? envelope.Message
                        : $"HTTP {(int)status} from backend.";
                    throw new ApiException(
                        message,
                        kind,
                        status,
                        envelope.Code,
                        envelope.Message,
                        requestId,
                        envelope.FieldIssues);
                }

                // Legacy fallback for older backends using {"error","code","message"}.
                try
                {
                    var legacy = JsonUtility.FromJson<ApiErrorDto>(body);
                    if (legacy != null && (!string.IsNullOrWhiteSpace(legacy.code) || !string.IsNullOrWhiteSpace(legacy.message)))
                    {
                        var message = !string.IsNullOrWhiteSpace(legacy.message)
                            ? legacy.message
                            : $"HTTP {(int)status} from backend.";
                        throw new ApiException(message, kind, status, legacy.code, legacy.message, LastRequestId);
                    }
                }
                catch (ApiException)
                {
                    throw;
                }
                catch
                {
                    // Fall through to the generic transport-level message below.
                }
            }

            throw new ApiException($"HTTP {(int)status} from backend.", kind, status, requestId: LastRequestId);
        }

        static ApiFailureKind Classify(HttpStatusCode status)
        {
            var code = (int)status;
            if (code == 408)
            {
                return ApiFailureKind.Timeout;
            }

            if (code == 409)
            {
                return ApiFailureKind.IncompatibleSchema;
            }

            if (code == 422)
            {
                return ApiFailureKind.Validation;
            }

            if (code >= 500 || code == 404 || code == 503)
            {
                return ApiFailureKind.Server;
            }

            return ApiFailureKind.Unexpected;
        }

        static T Deserialize<T>(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                throw new ApiException(
                    "Backend returned an empty JSON body.",
                    ApiFailureKind.Deserialization);
            }

            try
            {
                var value = JsonUtility.FromJson<T>(json);
                if (value == null)
                {
                    throw new ApiException(
                        "Failed to deserialize backend JSON.",
                        ApiFailureKind.Deserialization);
                }

                return value;
            }
            catch (ApiException)
            {
                throw;
            }
            catch (Exception ex)
            {
                throw new ApiException(
                    "Failed to deserialize backend JSON.",
                    ApiFailureKind.Deserialization,
                    innerException: ex);
            }
        }

        static void ValidateGenerationId(string generationId)
        {
            ValidateId(generationId, "generation_id");
        }

        static void ValidateJobId(string jobId)
        {
            ValidateId(jobId, "job_id");
        }

        static void ValidateBatchId(string batchId)
        {
            ValidateId(batchId, "batch_id");
        }

        static void ValidateModelId(string modelId)
        {
            ValidateId(modelId, "model_id");
        }

        static void ValidateId(string value, string fieldName)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                throw new ApiException(fieldName + " is required.", ApiFailureKind.Validation);
            }

            if (value.IndexOf("..", StringComparison.Ordinal) >= 0 ||
                value.IndexOf('/') >= 0 ||
                value.IndexOf('\\') >= 0)
            {
                throw new ApiException(fieldName + " is invalid.", ApiFailureKind.Validation);
            }
        }
    }
}
