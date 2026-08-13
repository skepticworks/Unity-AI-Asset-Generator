using NUnit.Framework;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class JobDeserializationTests
    {
        const string JobJson = @"{
            ""job_id"": ""aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"",
            ""state"": ""completed"",
            ""generation_type"": ""text_to_image"",
            ""asset_type"": ""texture"",
            ""prompt_summary"": ""rusted metal wall"",
            ""seed"": 42,
            ""created_at"": ""2026-01-01T00:00:00Z"",
            ""updated_at"": ""2026-01-01T00:00:05Z"",
            ""started_at"": ""2026-01-01T00:00:01Z"",
            ""completed_at"": ""2026-01-01T00:00:05Z"",
            ""progress"": { ""stage"": ""completed"", ""message"": ""Generation completed"" },
            ""result"": {
                ""generation_id"": ""bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"",
                ""status"": ""completed"",
                ""operation"": ""text_to_image"",
                ""asset_type"": ""texture"",
                ""seed"": 42,
                ""width"": 64,
                ""height"": 64,
                ""elapsed_seconds"": 1.25,
                ""resources"": {
                    ""image"": ""/api/v1/generations/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/image"",
                    ""manifest"": ""/api/v1/generations/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/manifest""
                },
                ""schema_versions"": { ""generation_manifest"": ""1.5"" }
            },
            ""error"": null,
            ""retry_count"": 1,
            ""max_retries"": 2,
            ""retry_history"": [
                {
                    ""code"": ""INFERENCE_FAILED"",
                    ""message"": ""temporary"",
                    ""retryable"": true,
                    ""occurred_at"": ""2026-01-01T00:00:02Z""
                }
            ],
            ""cancel_requested"": false,
            ""request"": { ""prompt"": ""rusted metal wall"", ""source_image"": { ""present"": true } }
        }";

        const string ListJson = @"{
            ""jobs"": [{
                ""job_id"": ""aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"",
                ""state"": ""failed"",
                ""generation_type"": ""inpainting"",
                ""asset_type"": ""sprite"",
                ""prompt_summary"": ""fix the plaque"",
                ""seed"": 9,
                ""created_at"": ""2026-01-01T00:00:00Z"",
                ""updated_at"": ""2026-01-01T00:00:03Z"",
                ""progress"": { ""stage"": ""failed"", ""message"": ""inference failed"" },
                ""error"": {
                    ""code"": ""INFERENCE_FAILED"",
                    ""message"": ""inference failed"",
                    ""retryable"": true,
                    ""occurred_at"": ""2026-01-01T00:00:03Z""
                },
                ""retry_count"": 0,
                ""max_retries"": 2,
                ""retry_history"": [],
                ""cancel_requested"": false,
                ""request"": {}
            }],
            ""total"": 1,
            ""limit"": 50,
            ""offset"": 0
        }";

        [Test]
        public void Parse_ReadsJobLifecycleAndResult()
        {
            var job = JobDocument.Parse(JobJson);
            Assert.AreEqual("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", job.JobId);
            Assert.AreEqual("completed", job.State);
            Assert.AreEqual("text_to_image", job.GenerationType);
            Assert.AreEqual("rusted metal wall", job.PromptSummary);
            Assert.AreEqual(42, job.Seed);
            Assert.IsTrue(job.CanImport);
            Assert.IsFalse(job.IsCancellable);
            Assert.IsNotNull(job.Result);
            Assert.AreEqual("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", job.Result.GenerationId);
            StringAssert.Contains("/image", job.Result.Resources.image);
            Assert.AreEqual(1, job.RetryHistory.Count);
            Assert.AreEqual("INFERENCE_FAILED", job.RetryHistory[0].Code);
        }

        [Test]
        public void Parse_ReadsHistoryListAndRetryEligibility()
        {
            var list = JobListDocument.Parse(ListJson);
            Assert.AreEqual(1, list.Total);
            Assert.AreEqual(1, list.Jobs.Count);
            var job = list.Jobs[0];
            Assert.AreEqual("failed", job.State);
            Assert.AreEqual("inpainting", job.GenerationType);
            Assert.IsTrue(job.IsRetryable);
            Assert.IsFalse(job.CanImport);
            Assert.AreEqual("INFERENCE_FAILED", job.Error.Code);
        }

        [Test]
        public void ApiEndpoints_IncludeJobRoutes()
        {
            Assert.AreEqual("/api/v1/jobs", ApiEndpoints.Jobs);
            Assert.AreEqual("/api/v1/jobs/abc", ApiEndpoints.Job("abc"));
            Assert.AreEqual("/api/v1/jobs/abc/result", ApiEndpoints.JobResult("abc"));
            Assert.AreEqual("/api/v1/jobs/abc/cancel", ApiEndpoints.JobCancel("abc"));
            Assert.AreEqual("/api/v1/jobs/abc/retry", ApiEndpoints.JobRetry("abc"));
            Assert.AreEqual("/api/v1/batches", ApiEndpoints.Batches);
        }
    }
}
