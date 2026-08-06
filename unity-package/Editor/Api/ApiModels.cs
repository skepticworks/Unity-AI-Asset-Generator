using System;
using System.Globalization;
using System.Text;

namespace UnityAiAssets.Editor.Api
{
    /// <summary>
    /// Wire models matching the FastAPI schemas. Kept separate from UI models.
    /// </summary>
    [Serializable]
    public sealed class HealthResponseDto
    {
        public string status;
        public string application_version;
        public bool model_loaded;
        public string resolved_device;
        public string request_id;

        /// <summary>Back-compat accessor for callers written against the pre-M3 "device" field.</summary>
        public string Device => resolved_device;
    }

    [Serializable]
    public sealed class TextureGenerationRequestDto
    {
        public string prompt;
        public string negative_prompt = "";
        public int width = 512;
        public int height = 512;
        public int steps = 25;
        public float guidance_scale = 7f;
        public long? seed;
        public string output_name = "texture";

        public string ToJson()
        {
            var sb = new StringBuilder(256);
            sb.Append('{');
            AppendString(sb, "prompt", prompt, first: true);
            AppendString(sb, "negative_prompt", negative_prompt ?? string.Empty, first: false);
            AppendNumber(sb, "width", width);
            AppendNumber(sb, "height", height);
            AppendNumber(sb, "steps", steps);
            AppendFloat(sb, "guidance_scale", guidance_scale);
            if (seed.HasValue)
            {
                AppendNumber(sb, "seed", seed.Value);
            }

            AppendString(sb, "output_name", output_name ?? "texture", first: false);
            sb.Append('}');
            return sb.ToString();
        }

        static void AppendString(StringBuilder sb, string key, string value, bool first)
        {
            if (!first)
            {
                sb.Append(',');
            }

            sb.Append('"').Append(key).Append("\":");
            sb.Append('"').Append(Escape(value)).Append('"');
        }

        static void AppendNumber(StringBuilder sb, string key, long value)
        {
            sb.Append(',');
            sb.Append('"').Append(key).Append("\":");
            sb.Append(value.ToString(CultureInfo.InvariantCulture));
        }

        static void AppendFloat(StringBuilder sb, string key, float value)
        {
            sb.Append(',');
            sb.Append('"').Append(key).Append("\":");
            sb.Append(value.ToString("0.###", CultureInfo.InvariantCulture));
        }

        static string Escape(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }

            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\n", "\\n")
                .Replace("\r", "\\r")
                .Replace("\t", "\\t");
        }
    }

    /// <summary>
    /// Retrieval links for a generation. Fields are relative or absolute URLs, never
    /// filesystem paths, so JsonUtility (which handles a flat nested class fine) is safe here.
    /// </summary>
    [Serializable]
    public sealed class ResourcesDto
    {
        public string image;
        public string manifest;
    }

    [Serializable]
    public sealed class SchemaVersionsDto
    {
        public string generation_manifest;
    }

    [Serializable]
    public sealed class TextureGenerationResponseDto
    {
        public string generation_id;
        public string status;
        public string operation;
        public string asset_type;
        public long seed;
        public int width;
        public int height;
        public float elapsed_seconds;
        public ResourcesDto resources;
        public SchemaVersionsDto schema_versions;

        // Deprecated: superseded by `resources`, kept for backward compatibility.
        public string image_path;
        public string metadata_path;
        public string image_url;
        public string metadata_url;
    }

    [Serializable]
    public sealed class ApiErrorDto
    {
        public string error;
        public string code;
        public string message;
    }

    [Serializable]
    public sealed class BackendMetadataDto
    {
        public string generation_id;
        public string created_at_utc;
        public string model_id;
        public string model_revision;
        public string prompt;
        public string negative_prompt;
        public long seed;
        public int width;
        public int height;
        public int steps;
        public float guidance_scale;
        public string device;
        public string torch_dtype;
        public string app_version;
        public float elapsed_seconds;
        public string output_filename;
    }

    public static class ApiEndpoints
    {
        public const string Health = "/health";
        public const string Capabilities = "/api/v1/capabilities";
        public const string GenerateTexture = "/api/v1/generations/textures";

        public static string GenerationImage(string generationId) =>
            $"/api/v1/generations/{generationId}/image";

        public static string GenerationManifest(string generationId) =>
            $"/api/v1/generations/{generationId}/manifest";

        /// <summary>Deprecated alias for <see cref="GenerationManifest"/>; kept for older backends.</summary>
        public static string GenerationMetadata(string generationId) =>
            $"/api/v1/generations/{generationId}/metadata";
    }
}
