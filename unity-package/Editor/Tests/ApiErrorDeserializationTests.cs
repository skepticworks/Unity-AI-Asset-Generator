using NUnit.Framework;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class ApiErrorDeserializationTests
    {
        [Test]
        public void TryParse_ReadsCodeMessageAndRequestId()
        {
            const string json = @"{
                ""error"": {
                    ""code"": ""GENERATION_REQUEST_INVALID"",
                    ""message"": ""The generation request is invalid."",
                    ""request_id"": ""11111111-1111-1111-1111-111111111111""
                }
            }";

            Assert.IsTrue(ErrorEnvelope.TryParse(json, out var envelope));
            Assert.AreEqual(AppErrorCode.GenerationRequestInvalid, envelope.Code);
            Assert.AreEqual("The generation request is invalid.", envelope.Message);
            Assert.AreEqual("11111111-1111-1111-1111-111111111111", envelope.RequestId);
            Assert.IsEmpty(envelope.FieldIssues);
        }

        [Test]
        public void TryParse_ReadsFieldIssuesWithNumericConstraints()
        {
            const string json = @"{
                ""error"": {
                    ""code"": ""GENERATION_REQUEST_INVALID"",
                    ""message"": ""The generation request is invalid."",
                    ""request_id"": ""req-1"",
                    ""details"": {
                        ""fields"": {
                            ""width"": [
                                {
                                    ""code"": ""VALUE_NOT_MULTIPLE"",
                                    ""message"": ""Width must be divisible by 8."",
                                    ""actual"": 513,
                                    ""expected_multiple"": 8
                                },
                                {
                                    ""code"": ""VALUE_ABOVE_MAXIMUM"",
                                    ""message"": ""Width must be at most 1024."",
                                    ""actual"": 2048,
                                    ""maximum"": 1024
                                }
                            ]
                        }
                    }
                }
            }";

            Assert.IsTrue(ErrorEnvelope.TryParse(json, out var envelope));
            Assert.AreEqual(2, envelope.FieldIssues.Count);

            var multipleIssue = envelope.FieldIssues[0];
            Assert.AreEqual("width", multipleIssue.FieldName);
            Assert.AreEqual(FieldIssueCode.ValueNotMultiple, multipleIssue.Code);
            Assert.AreEqual(513, multipleIssue.Actual.AsInt());
            Assert.AreEqual(8, multipleIssue.ExpectedMultiple);

            var maximumIssue = envelope.FieldIssues[1];
            Assert.AreEqual(FieldIssueCode.ValueAboveMaximum, maximumIssue.Code);
            Assert.AreEqual(1024, maximumIssue.Maximum.AsInt());
        }

        [Test]
        public void TryParse_ReadsMultipleFieldsIndependently()
        {
            const string json = @"{
                ""error"": {
                    ""code"": ""GENERATION_REQUEST_INVALID"",
                    ""message"": ""invalid"",
                    ""request_id"": ""req-2"",
                    ""details"": {
                        ""fields"": {
                            ""width"": [ { ""code"": ""VALUE_BELOW_MINIMUM"", ""message"": ""too small"", ""minimum"": 8 } ],
                            ""prompt"": [ { ""code"": ""FIELD_REQUIRED"", ""message"": ""required"" } ]
                        }
                    }
                }
            }";

            Assert.IsTrue(ErrorEnvelope.TryParse(json, out var envelope));
            Assert.AreEqual(2, envelope.FieldIssues.Count);
            CollectionAssert.Contains(new[] { "width", "prompt" }, envelope.FieldIssues[0].FieldName);
            CollectionAssert.Contains(new[] { "width", "prompt" }, envelope.FieldIssues[1].FieldName);
        }

        [Test]
        public void TryParse_ReturnsFalseForMissingErrorObject()
        {
            Assert.IsFalse(ErrorEnvelope.TryParse(@"{ ""status"": ""ok"" }", out var envelope));
            Assert.IsNull(envelope);
        }

        [Test]
        public void TryParse_ReturnsFalseForMalformedJson()
        {
            Assert.IsFalse(ErrorEnvelope.TryParse("not json at all", out var envelope));
            Assert.IsNull(envelope);
        }

        [Test]
        public void ErrorCodeConstants_MatchBackendSpelling()
        {
            Assert.AreEqual("REQUEST_BODY_INVALID", AppErrorCode.RequestBodyInvalid);
            Assert.AreEqual("GENERATION_REQUEST_INVALID", AppErrorCode.GenerationRequestInvalid);
            Assert.AreEqual("OPERATION_UNSUPPORTED", AppErrorCode.OperationUnsupported);
            Assert.AreEqual("ASSET_TYPE_UNSUPPORTED", AppErrorCode.AssetTypeUnsupported);
            Assert.AreEqual("SCHEDULER_UNSUPPORTED", AppErrorCode.SchedulerUnsupported);
            Assert.AreEqual("MODEL_UNAVAILABLE", AppErrorCode.ModelUnavailable);
            Assert.AreEqual("MODEL_LOADING_FAILED", AppErrorCode.ModelLoadingFailed);
            Assert.AreEqual("INFERENCE_FAILED", AppErrorCode.InferenceFailed);
            Assert.AreEqual("OUTPUT_PERSISTENCE_FAILED", AppErrorCode.OutputPersistenceFailed);
            Assert.AreEqual("GENERATION_NOT_FOUND", AppErrorCode.GenerationNotFound);
            Assert.AreEqual("MANIFEST_NOT_FOUND", AppErrorCode.ManifestNotFound);
            Assert.AreEqual("CAPABILITY_SCHEMA_UNSUPPORTED", AppErrorCode.CapabilitySchemaUnsupported);
            Assert.AreEqual("MANIFEST_SCHEMA_UNSUPPORTED", AppErrorCode.ManifestSchemaUnsupported);
            Assert.AreEqual("INTERNAL_SERVER_ERROR", AppErrorCode.InternalServerError);
        }

        [Test]
        public void FieldIssueCodeConstants_MatchBackendSpelling()
        {
            Assert.AreEqual("FIELD_REQUIRED", FieldIssueCode.FieldRequired);
            Assert.AreEqual("VALUE_TOO_SHORT", FieldIssueCode.ValueTooShort);
            Assert.AreEqual("VALUE_TOO_LONG", FieldIssueCode.ValueTooLong);
            Assert.AreEqual("VALUE_BELOW_MINIMUM", FieldIssueCode.ValueBelowMinimum);
            Assert.AreEqual("VALUE_ABOVE_MAXIMUM", FieldIssueCode.ValueAboveMaximum);
            Assert.AreEqual("VALUE_NOT_MULTIPLE", FieldIssueCode.ValueNotMultiple);
            Assert.AreEqual("VALUE_INVALID", FieldIssueCode.ValueInvalid);
            Assert.AreEqual("FORMAT_INVALID", FieldIssueCode.FormatInvalid);
        }
    }
}
