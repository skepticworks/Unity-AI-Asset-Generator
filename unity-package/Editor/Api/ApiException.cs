using System;
using System.Collections.Generic;
using System.Net;

namespace UnityAiAssets.Editor.Api
{
    /// <summary>
    /// Typed failure from the local generation API client.
    /// </summary>
    public sealed class ApiException : Exception
    {
        public ApiException(
            string message,
            ApiFailureKind kind,
            HttpStatusCode? statusCode = null,
            string serverCode = null,
            string serverMessage = null,
            string requestId = null,
            List<FieldIssue> fieldIssues = null,
            Exception innerException = null)
            : base(message, innerException)
        {
            Kind = kind;
            StatusCode = statusCode;
            ServerCode = serverCode;
            ServerMessage = serverMessage;
            RequestId = requestId;
            FieldIssues = fieldIssues ?? new List<FieldIssue>();
        }

        public ApiFailureKind Kind { get; }

        public HttpStatusCode? StatusCode { get; }

        /// <summary>Legacy alias for <see cref="AppErrorCode"/>; retained for existing call sites.</summary>
        public string ServerCode { get; }

        public string ServerMessage { get; }

        /// <summary>Stable top-level error code from the error envelope (e.g. "GENERATION_REQUEST_INVALID").</summary>
        public string AppErrorCode => ServerCode;

        /// <summary>The X-Request-ID associated with the failed request, when known.</summary>
        public string RequestId { get; }

        /// <summary>Field-level validation issues from the error envelope's details.fields, if any.</summary>
        public List<FieldIssue> FieldIssues { get; }

        public bool HasFieldIssues => FieldIssues != null && FieldIssues.Count > 0;

        public string UserFacingMessage
        {
            get
            {
                if (!string.IsNullOrWhiteSpace(ServerMessage))
                {
                    return ServerMessage;
                }

                return Message;
            }
        }
    }

    public enum ApiFailureKind
    {
        Connection,
        Timeout,
        Validation,
        Server,
        Deserialization,
        Cancelled,
        Unexpected,

        /// <summary>Downloaded artifact failed a SHA256/byte-size integrity check.</summary>
        Integrity,

        /// <summary>The backend's public API major version is not supported by this package.</summary>
        IncompatibleApi,

        /// <summary>A capability or manifest schema major version is not supported by this package.</summary>
        IncompatibleSchema
    }
}
