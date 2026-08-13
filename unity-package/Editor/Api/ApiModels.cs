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

    public sealed class SourceImagePayloadDto
    {
        public string content_base64;
        public string media_type;
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
        public string generation_profile_id;
        public int? generation_profile_revision;
        public string profile_origin;
        public string prompt_template_id;
        public int? prompt_template_revision;
        public string negative_prompt_profile_id;
        public int? negative_prompt_profile_revision;
        public string unity_import_profile_id;
        public string asset_type;
        public string transparency_strategy;
        public int? alpha_threshold;
        public int? alpha_feather;
        public bool? remove_near_transparent;
        public bool? zero_rgb_when_transparent;
        public float? pixels_per_unit;
        public string pivot_mode;
        public float? custom_pivot_x;
        public float? custom_pivot_y;
        public string atlas_hint;
        public bool? tileable;
        public bool? apply_seam_correction;
        public int? seam_blend_width;
        public bool? palette_reduction_enabled;
        public int? palette_color_count;
        public string operation;
        public SourceImagePayloadDto source_image;
        public SourceImagePayloadDto mask_image;
        public float? denoising_strength;

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
            AppendOptionalString(sb, "generation_profile_id", generation_profile_id);
            if (generation_profile_revision.HasValue) AppendNumber(sb, "generation_profile_revision", generation_profile_revision.Value);
            AppendOptionalString(sb, "profile_origin", profile_origin);
            AppendOptionalString(sb, "prompt_template_id", prompt_template_id);
            if (prompt_template_revision.HasValue) AppendNumber(sb, "prompt_template_revision", prompt_template_revision.Value);
            AppendOptionalString(sb, "negative_prompt_profile_id", negative_prompt_profile_id);
            if (negative_prompt_profile_revision.HasValue) AppendNumber(sb, "negative_prompt_profile_revision", negative_prompt_profile_revision.Value);
            AppendOptionalString(sb, "unity_import_profile_id", unity_import_profile_id);
            AppendOptionalString(sb, "asset_type", asset_type);
            AppendOptionalString(sb, "transparency_strategy", transparency_strategy);
            if (alpha_threshold.HasValue) AppendNumber(sb, "alpha_threshold", alpha_threshold.Value);
            if (alpha_feather.HasValue) AppendNumber(sb, "alpha_feather", alpha_feather.Value);
            if (remove_near_transparent.HasValue) AppendBool(sb, "remove_near_transparent", remove_near_transparent.Value);
            if (zero_rgb_when_transparent.HasValue) AppendBool(sb, "zero_rgb_when_transparent", zero_rgb_when_transparent.Value);
            if (pixels_per_unit.HasValue) AppendFloat(sb, "pixels_per_unit", pixels_per_unit.Value);
            AppendOptionalString(sb, "pivot_mode", pivot_mode);
            if (custom_pivot_x.HasValue) AppendFloat(sb, "custom_pivot_x", custom_pivot_x.Value);
            if (custom_pivot_y.HasValue) AppendFloat(sb, "custom_pivot_y", custom_pivot_y.Value);
            AppendOptionalString(sb, "atlas_hint", atlas_hint);
            if (tileable.HasValue) AppendBool(sb, "tileable", tileable.Value);
            if (apply_seam_correction.HasValue) AppendBool(sb, "apply_seam_correction", apply_seam_correction.Value);
            if (seam_blend_width.HasValue) AppendNumber(sb, "seam_blend_width", seam_blend_width.Value);
            if (palette_reduction_enabled.HasValue) AppendBool(sb, "palette_reduction_enabled", palette_reduction_enabled.Value);
            if (palette_color_count.HasValue) AppendNumber(sb, "palette_color_count", palette_color_count.Value);
            if (!string.IsNullOrWhiteSpace(operation))
                AppendString(sb, "operation", operation, first: false);
            if (denoising_strength.HasValue)
                AppendFloat(sb, "denoising_strength", denoising_strength.Value);
            if (source_image != null && !string.IsNullOrEmpty(source_image.content_base64))
            {
                sb.Append(",\"source_image\":{");
                AppendString(sb, "content_base64", source_image.content_base64, first: true);
                if (!string.IsNullOrWhiteSpace(source_image.media_type))
                    AppendString(sb, "media_type", source_image.media_type, first: false);
                sb.Append('}');
            }
            if (mask_image != null && !string.IsNullOrEmpty(mask_image.content_base64))
            {
                sb.Append(",\"mask_image\":{");
                AppendString(sb, "content_base64", mask_image.content_base64, first: true);
                if (!string.IsNullOrWhiteSpace(mask_image.media_type))
                    AppendString(sb, "media_type", mask_image.media_type, first: false);
                sb.Append('}');
            }
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

        static void AppendOptionalString(StringBuilder sb, string key, string value)
        {
            if (!string.IsNullOrWhiteSpace(value)) AppendString(sb, key, value, false);
        }

        static void AppendFloat(StringBuilder sb, string key, float value)
        {
            sb.Append(',');
            sb.Append('"').Append(key).Append("\":");
            sb.Append(value.ToString("0.###", CultureInfo.InvariantCulture));
        }

        static void AppendBool(StringBuilder sb, string key, bool value)
        {
            sb.Append(',').Append('"').Append(key).Append("\":").Append(value ? "true" : "false");
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
        public const string Jobs = "/api/v1/jobs";

        public static string Job(string jobId) => $"/api/v1/jobs/{jobId}";

        public static string JobResult(string jobId) => $"/api/v1/jobs/{jobId}/result";

        public static string JobCancel(string jobId) => $"/api/v1/jobs/{jobId}/cancel";

        public static string JobRetry(string jobId) => $"/api/v1/jobs/{jobId}/retry";

        public static string GenerationImage(string generationId) =>
            $"/api/v1/generations/{generationId}/image";

        public static string GenerationManifest(string generationId) =>
            $"/api/v1/generations/{generationId}/manifest";

        /// <summary>Deprecated alias for <see cref="GenerationManifest"/>; kept for older backends.</summary>
        public static string GenerationMetadata(string generationId) =>
            $"/api/v1/generations/{generationId}/metadata";
    }
}
