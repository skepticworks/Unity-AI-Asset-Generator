using System.Collections.Generic;

namespace UnityAiAssets.Editor.Api
{
    /// <summary>
    /// Top-level error codes. Must match unity_ai_assets.core.error_codes.AppErrorCode exactly.
    /// </summary>
    public static class AppErrorCode
    {
        public const string RequestBodyInvalid = "REQUEST_BODY_INVALID";
        public const string GenerationRequestInvalid = "GENERATION_REQUEST_INVALID";
        public const string OperationUnsupported = "OPERATION_UNSUPPORTED";
        public const string AssetTypeUnsupported = "ASSET_TYPE_UNSUPPORTED";
        public const string SchedulerUnsupported = "SCHEDULER_UNSUPPORTED";
        public const string ModelUnavailable = "MODEL_UNAVAILABLE";
        public const string ModelLoadingFailed = "MODEL_LOADING_FAILED";
        public const string InferenceFailed = "INFERENCE_FAILED";
        public const string OutputPersistenceFailed = "OUTPUT_PERSISTENCE_FAILED";
        public const string GenerationNotFound = "GENERATION_NOT_FOUND";
        public const string ManifestNotFound = "MANIFEST_NOT_FOUND";
        public const string CapabilitySchemaUnsupported = "CAPABILITY_SCHEMA_UNSUPPORTED";
        public const string ManifestSchemaUnsupported = "MANIFEST_SCHEMA_UNSUPPORTED";
        public const string BackgroundRemovalUnavailable = "BACKGROUND_REMOVAL_UNAVAILABLE";
        public const string InternalServerError = "INTERNAL_SERVER_ERROR";
    }

    /// <summary>
    /// Field-level validation issue codes. Must match unity_ai_assets.core.error_codes.FieldIssueCode exactly.
    /// </summary>
    public static class FieldIssueCode
    {
        public const string FieldRequired = "FIELD_REQUIRED";
        public const string ValueTooShort = "VALUE_TOO_SHORT";
        public const string ValueTooLong = "VALUE_TOO_LONG";
        public const string ValueBelowMinimum = "VALUE_BELOW_MINIMUM";
        public const string ValueAboveMaximum = "VALUE_ABOVE_MAXIMUM";
        public const string ValueNotMultiple = "VALUE_NOT_MULTIPLE";
        public const string ValueInvalid = "VALUE_INVALID";
        public const string FormatInvalid = "FORMAT_INVALID";
    }

    /// <summary>
    /// A single field-level validation problem, mirroring the backend's FieldIssue.to_dict() shape.
    /// </summary>
    public sealed class FieldIssue
    {
        public string FieldName;
        public string Code;
        public string Message;
        public JsonNode Actual;
        public JsonNode Minimum;
        public JsonNode Maximum;
        public int? ExpectedMultiple;

        public static FieldIssue FromJsonNode(string fieldName, JsonNode node)
        {
            var issue = new FieldIssue
            {
                FieldName = fieldName,
                Code = node.Get("code").AsString(),
                Message = node.Get("message").AsString(),
                Actual = node.HasKey("actual") ? node.Get("actual") : null,
                Minimum = node.HasKey("minimum") ? node.Get("minimum") : null,
                Maximum = node.HasKey("maximum") ? node.Get("maximum") : null,
            };

            if (node.HasKey("expected_multiple"))
            {
                issue.ExpectedMultiple = node.Get("expected_multiple").AsInt();
            }

            return issue;
        }

        public override string ToString()
        {
            return string.IsNullOrEmpty(FieldName) ? Message : $"{FieldName}: {Message}";
        }
    }

    /// <summary>
    /// Typed parse of the stable error envelope:
    /// { "error": { "code", "message", "request_id", "details": { "fields": { name: [issue,...] } } } }
    /// </summary>
    public sealed class ErrorEnvelope
    {
        public string Code;
        public string Message;
        public string RequestId;
        public List<FieldIssue> FieldIssues = new List<FieldIssue>();

        public static bool TryParse(string json, out ErrorEnvelope envelope)
        {
            envelope = null;
            if (!JsonNode.TryParse(json, out var root) || !root.IsObject)
            {
                return false;
            }

            var errorNode = root.Get("error");
            if (!errorNode.IsObject)
            {
                return false;
            }

            var code = errorNode.Get("code").AsString();
            var message = errorNode.Get("message").AsString();
            if (string.IsNullOrEmpty(code) && string.IsNullOrEmpty(message))
            {
                return false;
            }

            envelope = new ErrorEnvelope
            {
                Code = code,
                Message = message,
                RequestId = errorNode.Get("request_id").AsString(),
            };

            var fieldsNode = errorNode.Get("details").Get("fields");
            if (fieldsNode.IsObject)
            {
                foreach (var pair in fieldsNode.AsObject())
                {
                    if (!pair.Value.IsArray)
                    {
                        continue;
                    }

                    foreach (var issueNode in pair.Value.AsArray())
                    {
                        envelope.FieldIssues.Add(FieldIssue.FromJsonNode(pair.Key, issueNode));
                    }
                }
            }

            return true;
        }
    }
}
