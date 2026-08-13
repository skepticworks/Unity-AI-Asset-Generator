using NUnit.Framework;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Generation;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class BatchDeserializationTests
    {
        [Test]
        public void Parse_ReadsBatchAndMemberJobAssociation()
        {
            const string json = @"{
                ""batch_id"": ""aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"",
                ""state"": ""running"",
                ""created_at"": ""2026-01-01T00:00:00Z"",
                ""updated_at"": ""2026-01-01T00:00:02Z"",
                ""seed_mode"": ""sequential"",
                ""variation_count"": 2,
                ""prompts"": [""rusted metal"", ""mossy brick""],
                ""prompt_summary"": ""rusted metal (+1 more)"",
                ""job_ids"": [""11111111-1111-1111-1111-111111111111""],
                ""seed_start"": 10,
                ""seed_end"": 12,
                ""resolved_base_seeds"": [10, 11, 12],
                ""seed_summary"": ""10, 13, 11, 14, 12, 15"",
                ""cancel_requested"": false,
                ""generation_profile_id"": ""ps1_environment_texture"",
                ""asset_type"": ""texture"",
                ""operation"": ""text_to_image"",
                ""output_name"": ""batch"",
                ""counts"": {
                    ""queued"": 3, ""running"": 1, ""cancelling"": 0,
                    ""completed"": 0, ""failed"": 0, ""cancelled"": 0, ""interrupted"": 0,
                    ""total"": 4, ""active"": 4, ""terminal"": 0
                },
                ""progress"": { ""finished_jobs"": 0, ""total_jobs"": 4, ""completed_jobs"": 0 },
                ""jobs"": [{
                    ""job_id"": ""11111111-1111-1111-1111-111111111111"",
                    ""state"": ""running"",
                    ""generation_type"": ""text_to_image"",
                    ""asset_type"": ""texture"",
                    ""prompt_summary"": ""rusted metal"",
                    ""seed"": 10,
                    ""batch_id"": ""aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"",
                    ""batch_index"": 0,
                    ""prompt_index"": 0,
                    ""variation_index"": 0,
                    ""created_at"": ""2026-01-01T00:00:00Z"",
                    ""updated_at"": ""2026-01-01T00:00:02Z"",
                    ""progress"": { ""stage"": ""generating"", ""message"": ""Running generation"" },
                    ""retry_count"": 0, ""max_retries"": 2, ""retry_history"": [],
                    ""cancel_requested"": false,
                    ""request"": { ""output_name"": ""batch_p00_s10_v00"", ""generation_profile_id"": ""ps1_environment_texture"" }
                }]
            }";
            var batch = BatchDocument.Parse(json);
            Assert.AreEqual("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", batch.BatchId);
            Assert.IsTrue(batch.IsActive);
            Assert.AreEqual(2, batch.Prompts.Count);
            Assert.AreEqual(4, batch.Progress.TotalJobs);
            Assert.AreEqual(1, batch.Jobs.Count);
            var job = batch.Jobs[0];
            Assert.AreEqual(batch.BatchId, job.BatchId);
            Assert.AreEqual(0, job.BatchIndex);
            Assert.AreEqual(0, job.VariationIndex);
            Assert.AreEqual("batch_p00_s10_v00", job.RequestOutputName);
            Assert.AreEqual("ps1_environment_texture", job.RequestProfileId);
            Assert.IsTrue(job.IsCancellable);
        }

        [Test]
        public void BatchSubmitRequest_SerializesNestedGenerationRequest()
        {
            var dto = new BatchSubmitRequestDto
            {
                prompts = { "one", "two" },
                variation_count = 2,
                seed_mode = "fixed",
                seed = 9,
                request = new TextureGenerationRequestDto
                {
                    prompt = "placeholder",
                    width = 32,
                    height = 32,
                    output_name = "batch"
                }
            };
            var json = dto.ToJson();
            StringAssert.Contains("\"prompts\":[\"one\",\"two\"]", json);
            StringAssert.Contains("\"seed_mode\":\"fixed\"", json);
            StringAssert.Contains("\"variation_count\":2", json);
            StringAssert.Contains("\"request\":{", json);
            StringAssert.Contains("\"output_name\":\"batch\"", json);
        }

        [Test]
        public void ApiEndpoints_IncludeBatchRoutes()
        {
            Assert.AreEqual("/api/v1/batches", ApiEndpoints.Batches);
            Assert.AreEqual("/api/v1/batches/preview", ApiEndpoints.BatchPreview);
            Assert.AreEqual("/api/v1/batches/abc", ApiEndpoints.Batch("abc"));
            Assert.AreEqual("/api/v1/batches/abc/cancel", ApiEndpoints.BatchCancel("abc"));
            Assert.AreEqual("/api/v1/batches/abc/retry-failed", ApiEndpoints.BatchRetryFailed("abc"));
        }

        [Test]
        public void PreviewParse_ReadsSeedSummary()
        {
            const string json = @"{
                ""job_count"": 2,
                ""prompt_count"": 1,
                ""variation_count"": 2,
                ""seed_mode"": ""fixed"",
                ""base_seeds"": [5],
                ""seed_summary"": ""5, 6"",
                ""warnings"": [],
                ""items"": [
                    { ""index"": 0, ""prompt_index"": 0, ""variation_index"": 0, ""seed"": 5,
                      ""prompt"": ""metal"", ""prompt_summary"": ""metal"", ""output_name"": ""t_p00_s5_v00"" },
                    { ""index"": 1, ""prompt_index"": 0, ""variation_index"": 1, ""seed"": 6,
                      ""prompt"": ""metal"", ""prompt_summary"": ""metal"", ""output_name"": ""t_p00_s6_v01"" }
                ]
            }";
            var preview = BatchPreviewDocument.Parse(json);
            Assert.AreEqual(2, preview.JobCount);
            Assert.AreEqual("5, 6", preview.SeedSummary);
            Assert.AreEqual(5, preview.Items[0].Seed);
            Assert.AreEqual("fixed", BatchExpansion.ToApiValue(BatchSeedModeKind.Fixed));
        }
    }
}
