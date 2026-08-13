using System;
using System.Collections.Generic;

namespace UnityAiAssets.Editor.Api
{
    public sealed class JobProgressInfo
    {
        public string Stage;
        public string Message;
        public int? CurrentStep;
        public int? TotalSteps;
    }

    public sealed class JobErrorInfo
    {
        public string Code;
        public string Message;
        public bool Retryable;
        public string OccurredAt;
    }

    public sealed class JobResultInfo
    {
        public string GenerationId;
        public string Status;
        public string Operation;
        public string AssetType;
        public long Seed;
        public int Width;
        public int Height;
        public float ElapsedSeconds;
        public ResourcesDto Resources;
        public SchemaVersionsDto SchemaVersions;
    }

    /// <summary>
    /// Public job record from <c>/api/v1/jobs</c>. Parsed with <see cref="JsonNode"/>
    /// because history listings contain arrays JsonUtility cannot round-trip.
    /// </summary>
    public sealed class JobDocument
    {
        public string JobId;
        public string State;
        public string GenerationType;
        public string AssetType;
        public string PromptSummary;
        public long? Seed;
        public string BatchId;
        public int? BatchIndex;
        public int? PromptIndex;
        public int? VariationIndex;
        public string RequestOutputName;
        public string RequestProfileId;
        public string CreatedAt;
        public string UpdatedAt;
        public string StartedAt;
        public string CompletedAt;
        public JobProgressInfo Progress = new JobProgressInfo();
        public JobResultInfo Result;
        public JobErrorInfo Error;
        public int RetryCount;
        public int MaxRetries;
        public List<JobErrorInfo> RetryHistory = new List<JobErrorInfo>();
        public bool CancelRequested;

        public bool IsTerminal =>
            State == "completed" || State == "failed" || State == "cancelled" || State == "interrupted";

        public bool IsCancellable => State == "queued" || State == "running";

        public bool IsRetryable
        {
            get
            {
                if (State != "failed" && State != "interrupted" && State != "cancelled")
                    return false;
                if (RetryCount >= MaxRetries)
                    return false;
                if (Error != null && !Error.Retryable)
                    return false;
                return true;
            }
        }

        public bool CanImport =>
            State == "completed" && Result != null && !string.IsNullOrWhiteSpace(Result.GenerationId);

        public static JobDocument Parse(string json)
        {
            return FromJsonNode(JsonNode.Parse(json));
        }

        public static bool TryParse(string json, out JobDocument document)
        {
            try
            {
                document = Parse(json);
                return true;
            }
            catch (Exception)
            {
                document = null;
                return false;
            }
        }

        public static JobDocument FromJsonNode(JsonNode root)
        {
            if (root == null || !root.IsObject)
                throw new FormatException("Job document root must be a JSON object.");

            var progressNode = root.Get("progress");
            var resultNode = root.Get("result");
            var errorNode = root.Get("error");
            var historyNode = root.Get("retry_history");

            var document = new JobDocument
            {
                JobId = root.Get("job_id").AsString(),
                State = root.Get("state").AsString(),
                GenerationType = root.Get("generation_type").AsString(),
                AssetType = root.Get("asset_type").AsString(),
                PromptSummary = root.Get("prompt_summary").AsString() ?? string.Empty,
                Seed = root.Get("seed").AsNullableLong(),
                BatchId = root.Get("batch_id").AsString(),
                BatchIndex = root.Get("batch_index").Kind == JsonNodeKind.Number
                    ? root.Get("batch_index").AsInt()
                    : (int?)null,
                PromptIndex = root.Get("prompt_index").Kind == JsonNodeKind.Number
                    ? root.Get("prompt_index").AsInt()
                    : (int?)null,
                VariationIndex = root.Get("variation_index").Kind == JsonNodeKind.Number
                    ? root.Get("variation_index").AsInt()
                    : (int?)null,
                CreatedAt = root.Get("created_at").AsString(),
                UpdatedAt = root.Get("updated_at").AsString(),
                StartedAt = root.Get("started_at").AsString(),
                CompletedAt = root.Get("completed_at").AsString(),
                RetryCount = root.Get("retry_count").AsInt(),
                MaxRetries = root.Get("max_retries").AsInt(),
                CancelRequested = root.Get("cancel_requested").AsBool(),
                Progress = new JobProgressInfo
                {
                    Stage = progressNode.Get("stage").AsString(),
                    Message = progressNode.Get("message").AsString(),
                    CurrentStep = progressNode.Get("current_step").Kind == JsonNodeKind.Number
                        ? progressNode.Get("current_step").AsInt()
                        : (int?)null,
                    TotalSteps = progressNode.Get("total_steps").Kind == JsonNodeKind.Number
                        ? progressNode.Get("total_steps").AsInt()
                        : (int?)null,
                },
            };

            if (resultNode != null && resultNode.IsObject)
            {
                var resourcesNode = resultNode.Get("resources");
                var schemaNode = resultNode.Get("schema_versions");
                document.Result = new JobResultInfo
                {
                    GenerationId = resultNode.Get("generation_id").AsString(),
                    Status = resultNode.Get("status").AsString(),
                    Operation = resultNode.Get("operation").AsString(),
                    AssetType = resultNode.Get("asset_type").AsString(),
                    Seed = resultNode.Get("seed").AsLong(),
                    Width = resultNode.Get("width").AsInt(),
                    Height = resultNode.Get("height").AsInt(),
                    ElapsedSeconds = resultNode.Get("elapsed_seconds").AsFloat(),
                    Resources = new ResourcesDto
                    {
                        image = resourcesNode.Get("image").AsString(),
                        manifest = resourcesNode.Get("manifest").AsString(),
                    },
                    SchemaVersions = new SchemaVersionsDto
                    {
                        generation_manifest = schemaNode.Get("generation_manifest").AsString(),
                    },
                };
            }

            if (errorNode != null && errorNode.IsObject)
                document.Error = ParseError(errorNode);

            if (historyNode != null && historyNode.IsArray)
            {
                foreach (var item in historyNode.AsArray())
                {
                    if (item != null && item.IsObject)
                        document.RetryHistory.Add(ParseError(item));
                }
            }

            var requestNode = root.Get("request");
            if (requestNode != null && requestNode.IsObject)
            {
                document.RequestOutputName = requestNode.Get("output_name").AsString();
                document.RequestProfileId = requestNode.Get("generation_profile_id").AsString();
            }

            return document;
        }

        static JobErrorInfo ParseError(JsonNode node)
        {
            return new JobErrorInfo
            {
                Code = node.Get("code").AsString(),
                Message = node.Get("message").AsString(),
                Retryable = node.Get("retryable").AsBool(),
                OccurredAt = node.Get("occurred_at").AsString(),
            };
        }
    }

    public sealed class JobListDocument
    {
        public List<JobDocument> Jobs = new List<JobDocument>();
        public int Total;
        public int Limit;
        public int Offset;

        public static JobListDocument Parse(string json)
        {
            var root = JsonNode.Parse(json);
            if (root == null || !root.IsObject)
                throw new FormatException("Job list root must be a JSON object.");

            var document = new JobListDocument
            {
                Total = root.Get("total").AsInt(),
                Limit = root.Get("limit").AsInt(),
                Offset = root.Get("offset").AsInt(),
            };
            var jobsNode = root.Get("jobs");
            if (jobsNode != null && jobsNode.IsArray)
            {
                foreach (var item in jobsNode.AsArray())
                {
                    if (item != null && item.IsObject)
                        document.Jobs.Add(JobDocument.FromJsonNode(item));
                }
            }

            return document;
        }

        public static bool TryParse(string json, out JobListDocument document)
        {
            try
            {
                document = Parse(json);
                return true;
            }
            catch (Exception)
            {
                document = null;
                return false;
            }
        }
    }
}
