using NUnit.Framework;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class BatchStateAggregationTests
    {
        [Test]
        public void PartialSuccess_IsDistinctFromCompleteFailure()
        {
            var partial = Parse(@"{
                ""batch_id"": ""aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"",
                ""state"": ""partial_success"",
                ""created_at"": ""2026-01-01T00:00:00Z"",
                ""updated_at"": ""2026-01-01T00:00:05Z"",
                ""seed_mode"": ""fixed"",
                ""variation_count"": 1,
                ""prompts"": [""ok"", ""fail""],
                ""prompt_summary"": ""ok (+1 more)"",
                ""job_ids"": [],
                ""counts"": {
                    ""queued"": 0, ""running"": 0, ""cancelling"": 0,
                    ""completed"": 1, ""failed"": 1, ""cancelled"": 0, ""interrupted"": 0,
                    ""total"": 2, ""active"": 0, ""terminal"": 2
                },
                ""progress"": { ""finished_jobs"": 2, ""total_jobs"": 2, ""completed_jobs"": 1 },
                ""jobs"": [
                    {
                        ""job_id"": ""11111111-1111-1111-1111-111111111111"",
                        ""state"": ""completed"",
                        ""generation_type"": ""text_to_image"",
                        ""asset_type"": ""texture"",
                        ""prompt_summary"": ""ok"",
                        ""seed"": 1,
                        ""created_at"": ""2026-01-01T00:00:00Z"",
                        ""updated_at"": ""2026-01-01T00:00:03Z"",
                        ""progress"": { ""stage"": ""completed"", ""message"": ""done"" },
                        ""result"": {
                            ""generation_id"": ""bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"",
                            ""status"": ""completed"",
                            ""operation"": ""text_to_image"",
                            ""asset_type"": ""texture"",
                            ""seed"": 1, ""width"": 32, ""height"": 32, ""elapsed_seconds"": 0.2,
                            ""resources"": { ""image"": ""/i"", ""manifest"": ""/m"" },
                            ""schema_versions"": { ""generation_manifest"": ""1.5"" }
                        },
                        ""retry_count"": 0, ""max_retries"": 2, ""retry_history"": [],
                        ""cancel_requested"": false, ""request"": { ""output_name"": ""ok_p00_s1_v00"" }
                    },
                    {
                        ""job_id"": ""22222222-2222-2222-2222-222222222222"",
                        ""state"": ""failed"",
                        ""generation_type"": ""text_to_image"",
                        ""asset_type"": ""texture"",
                        ""prompt_summary"": ""fail"",
                        ""seed"": 1,
                        ""created_at"": ""2026-01-01T00:00:00Z"",
                        ""updated_at"": ""2026-01-01T00:00:04Z"",
                        ""progress"": { ""stage"": ""failed"", ""message"": ""inference failed"" },
                        ""error"": {
                            ""code"": ""INFERENCE_FAILED"",
                            ""message"": ""inference failed"",
                            ""retryable"": true,
                            ""occurred_at"": ""2026-01-01T00:00:04Z""
                        },
                        ""retry_count"": 0, ""max_retries"": 2, ""retry_history"": [],
                        ""cancel_requested"": false, ""request"": {}
                    }
                ]
            }");
            Assert.AreEqual("partial_success", partial.State);
            Assert.AreEqual(1, partial.Counts.Completed);
            Assert.AreEqual(1, partial.Counts.Failed);
            Assert.IsTrue(partial.HasImportableResults);
            Assert.IsTrue(partial.CanRetryFailed);
            Assert.IsFalse(partial.IsActive);
            Assert.IsTrue(partial.Jobs[0].CanImport);
            Assert.IsTrue(partial.Jobs[1].IsRetryable);
            Assert.AreEqual("INFERENCE_FAILED", partial.Jobs[1].Error.Code);
        }

        [Test]
        public void CancelledAndCompletedStates_ParseFromCounts()
        {
            var cancelled = Parse(@"{
                ""batch_id"": ""aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"",
                ""state"": ""cancelled"",
                ""created_at"": ""2026-01-01T00:00:00Z"",
                ""updated_at"": ""2026-01-01T00:00:01Z"",
                ""seed_mode"": ""random"",
                ""variation_count"": 1,
                ""prompts"": [""x""],
                ""prompt_summary"": ""x"",
                ""job_ids"": [],
                ""counts"": {
                    ""queued"": 0, ""running"": 0, ""cancelling"": 0,
                    ""completed"": 0, ""failed"": 0, ""cancelled"": 2, ""interrupted"": 0,
                    ""total"": 2, ""active"": 0, ""terminal"": 2
                },
                ""progress"": { ""finished_jobs"": 2, ""total_jobs"": 2, ""completed_jobs"": 0 },
                ""jobs"": []
            }");
            Assert.AreEqual("cancelled", cancelled.State);
            Assert.IsFalse(cancelled.HasImportableResults);
            Assert.IsTrue(cancelled.CanRetryFailed);
            Assert.IsFalse(cancelled.CanCancel);
        }

        static BatchDocument Parse(string json) => BatchDocument.Parse(json);
    }
}
