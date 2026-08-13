using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace UnityAiAssets.Editor.Api
{
    public sealed class BatchJobCountsInfo
    {
        public int Queued;
        public int Running;
        public int Cancelling;
        public int Completed;
        public int Failed;
        public int Cancelled;
        public int Interrupted;
        public int Total;
        public int Active;
        public int Terminal;
    }

    public sealed class BatchProgressInfo
    {
        public int FinishedJobs;
        public int TotalJobs;
        public int CompletedJobs;
    }

    public sealed class BatchExpansionItemInfo
    {
        public int Index;
        public int PromptIndex;
        public int VariationIndex;
        public long Seed;
        public string Prompt;
        public string PromptSummary;
        public string OutputName;
    }

    public sealed class BatchPreviewDocument
    {
        public int JobCount;
        public int PromptCount;
        public int VariationCount;
        public string SeedMode;
        public List<long> BaseSeeds = new List<long>();
        public string SeedSummary;
        public List<string> Warnings = new List<string>();
        public List<BatchExpansionItemInfo> Items = new List<BatchExpansionItemInfo>();

        public static bool TryParse(string json, out BatchPreviewDocument document)
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

        public static BatchPreviewDocument Parse(string json)
        {
            var root = JsonNode.Parse(json);
            if (root == null || !root.IsObject)
                throw new FormatException("Batch preview root must be a JSON object.");
            var document = new BatchPreviewDocument
            {
                JobCount = root.Get("job_count").AsInt(),
                PromptCount = root.Get("prompt_count").AsInt(),
                VariationCount = root.Get("variation_count").AsInt(),
                SeedMode = root.Get("seed_mode").AsString() ?? string.Empty,
                SeedSummary = root.Get("seed_summary").AsString() ?? string.Empty,
            };
            foreach (var item in root.Get("base_seeds").AsArray())
            {
                if (item.Kind == JsonNodeKind.Number)
                    document.BaseSeeds.Add(item.AsLong());
            }

            document.Warnings = root.Get("warnings").AsStringList();
            var itemsNode = root.Get("items");
            if (itemsNode != null && itemsNode.IsArray)
            {
                foreach (var item in itemsNode.AsArray())
                {
                    if (item == null || !item.IsObject)
                        continue;
                    document.Items.Add(new BatchExpansionItemInfo
                    {
                        Index = item.Get("index").AsInt(),
                        PromptIndex = item.Get("prompt_index").AsInt(),
                        VariationIndex = item.Get("variation_index").AsInt(),
                        Seed = item.Get("seed").AsLong(),
                        Prompt = item.Get("prompt").AsString() ?? string.Empty,
                        PromptSummary = item.Get("prompt_summary").AsString() ?? string.Empty,
                        OutputName = item.Get("output_name").AsString() ?? string.Empty,
                    });
                }
            }

            return document;
        }
    }

    public sealed class BatchDocument
    {
        public string BatchId;
        public string State;
        public string CreatedAt;
        public string UpdatedAt;
        public string SeedMode;
        public int VariationCount;
        public List<string> Prompts = new List<string>();
        public string PromptSummary;
        public List<string> JobIds = new List<string>();
        public long? Seed;
        public long? SeedStart;
        public long? SeedEnd;
        public List<long> ResolvedBaseSeeds = new List<long>();
        public string SeedSummary;
        public bool CancelRequested;
        public string GenerationProfileId;
        public string AssetType;
        public string Operation;
        public string OutputName;
        public BatchJobCountsInfo Counts = new BatchJobCountsInfo();
        public BatchProgressInfo Progress = new BatchProgressInfo();
        public List<JobDocument> Jobs = new List<JobDocument>();

        public bool IsActive =>
            State == "queued" || State == "running" || State == "cancelling";

        public bool CanRetryFailed
        {
            get
            {
                if (Counts == null)
                    return false;
                return Counts.Failed + Counts.Interrupted + Counts.Cancelled > 0 && !IsActive;
            }
        }

        public bool CanCancel => Counts != null && (Counts.Queued > 0 || Counts.Running > 0);

        public bool HasImportableResults
        {
            get
            {
                foreach (var job in Jobs)
                {
                    if (job != null && job.CanImport)
                        return true;
                }

                return false;
            }
        }

        public static bool TryParse(string json, out BatchDocument document)
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

        public static BatchDocument Parse(string json)
        {
            return FromJsonNode(JsonNode.Parse(json));
        }

        public static BatchDocument FromJsonNode(JsonNode root)
        {
            if (root == null || !root.IsObject)
                throw new FormatException("Batch document root must be a JSON object.");

            var countsNode = root.Get("counts");
            var progressNode = root.Get("progress");
            var document = new BatchDocument
            {
                BatchId = root.Get("batch_id").AsString(),
                State = root.Get("state").AsString(),
                CreatedAt = root.Get("created_at").AsString(),
                UpdatedAt = root.Get("updated_at").AsString(),
                SeedMode = root.Get("seed_mode").AsString() ?? string.Empty,
                VariationCount = root.Get("variation_count").AsInt(),
                PromptSummary = root.Get("prompt_summary").AsString() ?? string.Empty,
                Seed = root.Get("seed").AsNullableLong(),
                SeedStart = root.Get("seed_start").AsNullableLong(),
                SeedEnd = root.Get("seed_end").AsNullableLong(),
                SeedSummary = root.Get("seed_summary").AsString() ?? string.Empty,
                CancelRequested = root.Get("cancel_requested").AsBool(),
                GenerationProfileId = root.Get("generation_profile_id").AsString(),
                AssetType = root.Get("asset_type").AsString(),
                Operation = root.Get("operation").AsString(),
                OutputName = root.Get("output_name").AsString(),
                Prompts = root.Get("prompts").AsStringList(),
                JobIds = root.Get("job_ids").AsStringList(),
                Counts = new BatchJobCountsInfo
                {
                    Queued = countsNode.Get("queued").AsInt(),
                    Running = countsNode.Get("running").AsInt(),
                    Cancelling = countsNode.Get("cancelling").AsInt(),
                    Completed = countsNode.Get("completed").AsInt(),
                    Failed = countsNode.Get("failed").AsInt(),
                    Cancelled = countsNode.Get("cancelled").AsInt(),
                    Interrupted = countsNode.Get("interrupted").AsInt(),
                    Total = countsNode.Get("total").AsInt(),
                    Active = countsNode.Get("active").AsInt(),
                    Terminal = countsNode.Get("terminal").AsInt(),
                },
                Progress = new BatchProgressInfo
                {
                    FinishedJobs = progressNode.Get("finished_jobs").AsInt(),
                    TotalJobs = progressNode.Get("total_jobs").AsInt(),
                    CompletedJobs = progressNode.Get("completed_jobs").AsInt(),
                },
            };
            foreach (var item in root.Get("resolved_base_seeds").AsArray())
            {
                if (item.Kind == JsonNodeKind.Number)
                    document.ResolvedBaseSeeds.Add(item.AsLong());
            }

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
    }

    public sealed class BatchListDocument
    {
        public List<BatchDocument> Batches = new List<BatchDocument>();
        public int Total;
        public int Limit;
        public int Offset;

        public static bool TryParse(string json, out BatchListDocument document)
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

        public static BatchListDocument Parse(string json)
        {
            var root = JsonNode.Parse(json);
            if (root == null || !root.IsObject)
                throw new FormatException("Batch list root must be a JSON object.");
            var document = new BatchListDocument
            {
                Total = root.Get("total").AsInt(),
                Limit = root.Get("limit").AsInt(),
                Offset = root.Get("offset").AsInt(),
            };
            var batchesNode = root.Get("batches");
            if (batchesNode != null && batchesNode.IsArray)
            {
                foreach (var item in batchesNode.AsArray())
                {
                    if (item != null && item.IsObject)
                        document.Batches.Add(BatchDocument.FromJsonNode(item));
                }
            }

            return document;
        }
    }

    public sealed class BatchSubmitRequestDto
    {
        public List<string> prompts = new List<string>();
        public int variation_count = 1;
        public string seed_mode = "random";
        public long? seed;
        public long? seed_start;
        public long? seed_end;
        public TextureGenerationRequestDto request;

        public string ToJson()
        {
            var sb = new StringBuilder(256);
            sb.Append("{\"prompts\":[");
            for (var i = 0; i < prompts.Count; i++)
            {
                if (i > 0)
                    sb.Append(',');
                sb.Append('"').Append(Escape(prompts[i] ?? string.Empty)).Append('"');
            }

            sb.Append("],\"variation_count\":");
            sb.Append(variation_count.ToString(CultureInfo.InvariantCulture));
            sb.Append(",\"seed_mode\":\"");
            sb.Append(Escape(seed_mode ?? "random"));
            sb.Append('"');
            if (seed.HasValue)
            {
                sb.Append(",\"seed\":");
                sb.Append(seed.Value.ToString(CultureInfo.InvariantCulture));
            }

            if (seed_start.HasValue)
            {
                sb.Append(",\"seed_start\":");
                sb.Append(seed_start.Value.ToString(CultureInfo.InvariantCulture));
            }

            if (seed_end.HasValue)
            {
                sb.Append(",\"seed_end\":");
                sb.Append(seed_end.Value.ToString(CultureInfo.InvariantCulture));
            }

            sb.Append(",\"request\":");
            sb.Append(request != null ? request.ToJson() : "{}");
            sb.Append('}');
            return sb.ToString();
        }

        static string Escape(string value)
        {
            if (string.IsNullOrEmpty(value))
                return string.Empty;
            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\n", "\\n")
                .Replace("\r", "\\r")
                .Replace("\t", "\\t");
        }
    }
}
