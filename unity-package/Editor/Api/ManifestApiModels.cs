using System;
using System.Collections.Generic;
using UnityAiAssets.Editor.Versioning;

namespace UnityAiAssets.Editor.Api
{
    public sealed class ManifestSchemaInfo
    {
        public string Name;
        public string Version;
    }

    public sealed class ManifestGenerationInfo
    {
        public string Id;
        public string Operation;
        public string AssetType;
        public string Status;
        public string CreatedAtUtc;
        public string CompletedAtUtc;
        public float ElapsedSeconds;
    }

    public sealed class ManifestApplicationInfo
    {
        public string Name;
        public string Version;
        public int ApiMajor;
    }

    public sealed class ManifestModelInfo
    {
        public string Id;
        public string Revision;
        public string Family;
    }

    public sealed class ManifestRuntimeInfo
    {
        public string Device;
        public string Precision;
        public string Scheduler;
    }

    public sealed class ManifestRequestInfo
    {
        public string Prompt;
        public string NegativePrompt;
        public int Width;
        public int Height;
        public int Steps;
        public float GuidanceScale;
        public long Seed;
        public string OutputName;
        public string TransparencyStrategy;
        public float PixelsPerUnit;
        public string PivotMode;
        public float CustomPivotX;
        public float CustomPivotY;
        public string AtlasHint;
        public bool Tileable;
        public bool ApplySeamCorrection;
        public int SeamBlendWidth;
        public bool PaletteReductionEnabled;
        public int PaletteColorCount;
    }

    public sealed class ManifestProcessingInfo
    {
        public string TransparencyStrategy;
        public bool BackgroundRemovalApplied;
        public string BackgroundRemovalImplementation;
        public string BackgroundRemovalBackend;
        public string BackgroundRemovalModel;
        public bool ProducesNativeAlpha;
        public bool AlphaCleanupApplied;
        public int AlphaThreshold;
        public int AlphaFeather;
        public bool RemoveNearTransparent;
        public bool ZeroRgbWhenTransparent;
        public float PixelsPerUnit;
        public string PivotMode;
        public float CustomPivotX;
        public float CustomPivotY;
        public string AtlasHint;
        public string OriginalRelativePath;
        public string FinalRelativePath;
        public bool Tileable;
        public bool SeamCorrectionApplied;
        public bool PaletteReductionApplied;
        public int SeamBlendWidth;
        public int PaletteColorCount;
        public float? SeamScoreBefore;
        public float? SeamScoreAfter;
        public float? HorizontalSeamScore;
        public float? VerticalSeamScore;
        public float? HorizontalWrapDiscontinuity;
        public float? VerticalWrapDiscontinuity;
        public string SeamInpaintImplementation;
    }

    public sealed class ManifestOutputInfo
    {
        public string Kind;
        public string Format;
        public string RelativePath;
        public int Width;
        public int Height;
        public string Sha256;
        public long ByteSize;
    }

    public sealed class ManifestProfileInfo
    {
        public string GenerationProfileId;
        public int GenerationProfileRevision;
        public string ProfileOrigin;
        public string PromptTemplateId;
        public int PromptTemplateRevision;
        public string NegativePromptProfileId;
        public int NegativePromptProfileRevision;
        public string UnityImportProfileId;
    }

    /// <summary>
    /// Typed, parsed form of a generation manifest document
    /// (GET /api/v1/generations/{id}/manifest, or the deprecated /metadata alias).
    /// Built from <see cref="JsonNode"/> because "outputs" is an array of objects that
    /// JsonUtility cannot deserialize reliably as a field.
    /// </summary>
    public sealed class GenerationManifestDocument
    {
        public ManifestSchemaInfo Schema;
        public ManifestGenerationInfo Generation;
        public ManifestApplicationInfo Application;
        public ManifestModelInfo Model;
        public ManifestRuntimeInfo Runtime;
        public ManifestRequestInfo Request;
        public ManifestProfileInfo Profile;
        public ManifestProcessingInfo Processing;
        public List<ManifestOutputInfo> Outputs = new List<ManifestOutputInfo>();

        public SchemaVersion SchemaVersionValue => SchemaVersion.Parse(Schema.Version);

        public ManifestOutputInfo FindOutput(string kind)
        {
            foreach (var output in Outputs)
            {
                if (string.Equals(output.Kind, kind, StringComparison.OrdinalIgnoreCase))
                {
                    return output;
                }
            }

            return null;
        }

        public static GenerationManifestDocument Parse(string json)
        {
            var root = JsonNode.Parse(json);
            return FromJsonNode(root);
        }

        public static bool TryParse(string json, out GenerationManifestDocument document)
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

        public static GenerationManifestDocument FromJsonNode(JsonNode root)
        {
            if (root == null || !root.IsObject)
            {
                throw new FormatException("Manifest document root must be a JSON object.");
            }

            var schemaNode = root.Get("schema");
            var generationNode = root.Get("generation");
            var applicationNode = root.Get("application");
            var modelNode = root.Get("model");
            var runtimeNode = root.Get("runtime");
            var requestNode = root.Get("request");
            var outputsNode = root.Get("outputs");
            var profileNode = root.Get("profile");
            var processingNode = root.Get("processing");

            var document = new GenerationManifestDocument
            {
                Schema = new ManifestSchemaInfo
                {
                    Name = schemaNode.Get("name").AsString(),
                    Version = schemaNode.Get("version").AsString(),
                },
                Generation = new ManifestGenerationInfo
                {
                    Id = generationNode.Get("id").AsString(),
                    Operation = generationNode.Get("operation").AsString(),
                    AssetType = generationNode.Get("asset_type").AsString(),
                    Status = generationNode.Get("status").AsString(),
                    CreatedAtUtc = generationNode.Get("created_at_utc").AsString(),
                    CompletedAtUtc = generationNode.Get("completed_at_utc").AsString(),
                    ElapsedSeconds = generationNode.Get("elapsed_seconds").AsFloat(),
                },
                Application = new ManifestApplicationInfo
                {
                    Name = applicationNode.Get("name").AsString(),
                    Version = applicationNode.Get("version").AsString(),
                    ApiMajor = applicationNode.Get("api_major").AsInt(),
                },
                Model = new ManifestModelInfo
                {
                    Id = modelNode.Get("id").AsString(),
                    Revision = modelNode.Get("revision").AsString(),
                    Family = modelNode.Get("family").AsString(),
                },
                Runtime = new ManifestRuntimeInfo
                {
                    Device = runtimeNode.Get("device").AsString(),
                    Precision = runtimeNode.Get("precision").AsString(),
                    Scheduler = runtimeNode.Get("scheduler").AsString(),
                },
                Request = new ManifestRequestInfo
                {
                    Prompt = requestNode.Get("prompt").AsString(),
                    NegativePrompt = requestNode.Get("negative_prompt").AsString(string.Empty),
                    Width = requestNode.Get("width").AsInt(),
                    Height = requestNode.Get("height").AsInt(),
                    Steps = requestNode.Get("steps").AsInt(),
                    GuidanceScale = requestNode.Get("guidance_scale").AsFloat(),
                    Seed = requestNode.Get("seed").AsLong(),
                    OutputName = requestNode.Get("output_name").AsString(),
                    TransparencyStrategy = requestNode.Get("transparency_strategy").AsString("none"),
                    PixelsPerUnit = requestNode.Get("pixels_per_unit").AsFloat(100f),
                    PivotMode = requestNode.Get("pivot_mode").AsString("center"),
                    CustomPivotX = requestNode.Get("custom_pivot_x").AsFloat(.5f),
                    CustomPivotY = requestNode.Get("custom_pivot_y").AsFloat(.5f),
                    AtlasHint = requestNode.Get("atlas_hint").AsString(),
                    Tileable = requestNode.Get("tileable").AsBool(),
                    ApplySeamCorrection = requestNode.Get("apply_seam_correction").AsBool(),
                    SeamBlendWidth = requestNode.Get("seam_blend_width").AsInt(64),
                    PaletteReductionEnabled = requestNode.Get("palette_reduction_enabled").AsBool(),
                    PaletteColorCount = requestNode.Get("palette_color_count").AsInt(16)
                },
                Processing = processingNode.IsObject ? new ManifestProcessingInfo
                {
                    TransparencyStrategy = processingNode.Get("transparency_strategy").AsString("none"),
                    BackgroundRemovalApplied = processingNode.Get("background_removal_applied").AsBool(),
                    BackgroundRemovalImplementation = processingNode.Get("background_removal_implementation").AsString(),
                    BackgroundRemovalBackend = processingNode.Get("background_removal_backend").AsString(),
                    BackgroundRemovalModel = processingNode.Get("background_removal_model").AsString(),
                    ProducesNativeAlpha = processingNode.Get("produces_native_alpha").AsBool(),
                    AlphaCleanupApplied = processingNode.Get("alpha_cleanup_applied").AsBool(),
                    AlphaThreshold = processingNode.Get("alpha_threshold").AsInt(),
                    AlphaFeather = processingNode.Get("alpha_feather").AsInt(),
                    RemoveNearTransparent = processingNode.Get("remove_near_transparent").AsBool(),
                    ZeroRgbWhenTransparent = processingNode.Get("zero_rgb_when_transparent").AsBool(),
                    PixelsPerUnit = processingNode.Get("pixels_per_unit").AsFloat(),
                    PivotMode = processingNode.Get("pivot_mode").AsString(),
                    CustomPivotX = processingNode.Get("custom_pivot_x").AsFloat(.5f),
                    CustomPivotY = processingNode.Get("custom_pivot_y").AsFloat(.5f),
                    AtlasHint = processingNode.Get("atlas_hint").AsString(),
                    OriginalRelativePath = processingNode.Get("original_relative_path").AsString(),
                    FinalRelativePath = processingNode.Get("final_relative_path").AsString(),
                    Tileable = processingNode.Get("tileable").AsBool(),
                    SeamCorrectionApplied = processingNode.Get("seam_correction_applied").AsBool(),
                    PaletteReductionApplied = processingNode.Get("palette_reduction_applied").AsBool(),
                    SeamBlendWidth = processingNode.Get("seam_blend_width").AsInt(64),
                    PaletteColorCount = processingNode.Get("palette_color_count").AsInt(16),
                    SeamScoreBefore = processingNode.Get("seam_score_before").AsNullableFloat(),
                    SeamScoreAfter = processingNode.Get("seam_score_after").AsNullableFloat(),
                    HorizontalSeamScore = processingNode.Get("horizontal_seam_score").AsNullableFloat(),
                    VerticalSeamScore = processingNode.Get("vertical_seam_score").AsNullableFloat(),
                    HorizontalWrapDiscontinuity = processingNode.Get("horizontal_wrap_discontinuity").AsNullableFloat(),
                    VerticalWrapDiscontinuity = processingNode.Get("vertical_wrap_discontinuity").AsNullableFloat(),
                    SeamInpaintImplementation = processingNode.Get("seam_inpaint_implementation").AsString()
                } : null,
                Profile = profileNode.IsObject ? new ManifestProfileInfo
                {
                    GenerationProfileId = profileNode.Get("generation_profile_id").AsString(),
                    GenerationProfileRevision = profileNode.Get("generation_profile_revision").AsInt(),
                    ProfileOrigin = profileNode.Get("profile_origin").AsString(),
                    PromptTemplateId = profileNode.Get("prompt_template_id").AsString(),
                    PromptTemplateRevision = profileNode.Get("prompt_template_revision").AsInt(),
                    NegativePromptProfileId = profileNode.Get("negative_prompt_profile_id").AsString(),
                    NegativePromptProfileRevision = profileNode.Get("negative_prompt_profile_revision").AsInt(),
                    UnityImportProfileId = profileNode.Get("unity_import_profile_id").AsString()
                } : null,
            };

            if (outputsNode.IsArray)
            {
                foreach (var outputNode in outputsNode.AsArray())
                {
                    document.Outputs.Add(new ManifestOutputInfo
                    {
                        Kind = outputNode.Get("kind").AsString(),
                        Format = outputNode.Get("format").AsString(),
                        RelativePath = outputNode.Get("relative_path").AsString(),
                        Width = outputNode.Get("width").AsInt(),
                        Height = outputNode.Get("height").AsInt(),
                        Sha256 = outputNode.Get("sha256").AsString(),
                        ByteSize = outputNode.Get("byte_size").AsLong(),
                    });
                }
            }

            return document;
        }
    }
}
