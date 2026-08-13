using System;
using System.Collections.Generic;
using UnityAiAssets.Editor.Versioning;

namespace UnityAiAssets.Editor.Api
{
    public sealed class ApiVersionInfo
    {
        public int Major;
        public int Minor;
    }

    public sealed class ApplicationInfo
    {
        public string Name;
        public string Version;
    }

    public sealed class SchemaVersionsInfo
    {
        public string Capabilities;
        public string GenerationManifest;
    }

    public sealed class RuntimeInfo
    {
        public string ConfiguredDevice;
        public string ResolvedDevice;
        public string ConfiguredPrecision;
        public string ResolvedPrecision;
        public bool ModelLoaded;
    }

    public sealed class ModelInfo
    {
        public string Id;
        public string Revision;
        public string Family;
        public string DisplayName;
    }

    public sealed class DimensionConstraints
    {
        public int MinimumWidth;
        public int MaximumWidth;
        public int MinimumHeight;
        public int MaximumHeight;
        public int WidthMultiple;
        public int HeightMultiple;
        public List<string> SupportedAspectRatios = new List<string>();
    }

    public sealed class IntRange
    {
        public int Minimum;
        public int Maximum;
        public int Default;
    }

    public sealed class FloatRange
    {
        public float Minimum;
        public float Maximum;
        public float Default;
    }

    public sealed class SeedConstraints
    {
        public long Minimum;
        public long Maximum;
        public bool RandomWhenOmitted;
    }

    public sealed class PromptConstraints
    {
        public int MaximumLength;
    }

    public sealed class NegativePromptConstraints
    {
        public bool Supported;
        public int MaximumLength;
    }

    public sealed class OutputNameConstraints
    {
        public int MaximumLength;
    }

    public sealed class SchedulerCapabilities
    {
        public bool SelectionSupported;
        public string Default;
        public List<string> Available = new List<string>();
    }

    public sealed class BackgroundRemovalCapabilities
    {
        public bool Available;
        public string Backend;
        public string Model;
        public bool ProducesNativeAlpha;
        public string UnavailableReason;
    }

    public sealed class AlphaCleanupCapabilities
    {
        public bool Available;
        public FloatRange AlphaThreshold;
        public FloatRange AlphaFeather;
        public bool RemoveNearTransparentDefault;
        public bool ZeroRgbWhenTransparentDefault;
    }

    public sealed class SpriteImportCapabilities
    {
        public bool Supported;
        public bool SingleSpriteOnly;
        public List<string> PivotModes = new List<string>();
    }

    public sealed class TileableProcessingCapabilities
    {
        public bool Available = true;
        public bool SeamAnalysis = true;
        public bool SeamCorrection = true;
        public bool PaletteReduction = true;
        public bool AiInpaintAvailable;
        public IntRange SeamBlendWidth;
        public IntRange PaletteColorCount;
        public int TargetSize = 512;
        public int CircularOffsetPx = 256;
        public int ProtectedBorderPx = 4;
    }

    public sealed class ProcessingCapabilities
    {
        public List<string> TransparencyStrategies = new List<string>();
        public BackgroundRemovalCapabilities BackgroundRemoval;
        public AlphaCleanupCapabilities AlphaCleanup;
        public SpriteImportCapabilities SpriteImport;
        public TileableProcessingCapabilities Tileable;
    }

    public sealed class TextToImageCapabilities
    {
        public bool Supported;
        public List<string> AssetTypes = new List<string>();
        public DimensionConstraints Dimensions;
        public IntRange Steps;
        public FloatRange GuidanceScale;
        public SeedConstraints Seed;
        public PromptConstraints Prompt;
        public NegativePromptConstraints NegativePrompt;
        public OutputNameConstraints OutputName;
        public SchedulerCapabilities Schedulers;
        public ProcessingCapabilities Processing;
    }

    public sealed class SourceImageConstraints
    {
        public List<string> SupportedFormats = new List<string>();
        public long MaximumByteSize;
        public DimensionConstraints Dimensions;
    }

    public sealed class ImageToImageCapabilities
    {
        public bool Supported;
        public List<string> AssetTypes = new List<string>();
        public DimensionConstraints Dimensions;
        public IntRange Steps;
        public FloatRange GuidanceScale;
        public SeedConstraints Seed;
        public PromptConstraints Prompt;
        public NegativePromptConstraints NegativePrompt;
        public OutputNameConstraints OutputName;
        public SchedulerCapabilities Schedulers;
        public FloatRange DenoisingStrength;
        public SourceImageConstraints SourceImage;
        public ProcessingCapabilities Processing;
    }

    public sealed class MaskImageConstraints
    {
        public List<string> SupportedFormats = new List<string>();
        public long MaximumByteSize;
        public DimensionConstraints Dimensions;
        public bool MustMatchSourceDimensions = true;
        public string Convention = "white_inpaints";
        public string WhiteMeans = "regenerate";
        public string BlackMeans = "keep";
        public bool AlphaIgnored = true;
    }

    public sealed class InpaintingCapabilities
    {
        public bool Supported;
        public List<string> AssetTypes = new List<string>();
        public DimensionConstraints Dimensions;
        public IntRange Steps;
        public FloatRange GuidanceScale;
        public SeedConstraints Seed;
        public PromptConstraints Prompt;
        public NegativePromptConstraints NegativePrompt;
        public OutputNameConstraints OutputName;
        public SchedulerCapabilities Schedulers;
        public FloatRange DenoisingStrength;
        public SourceImageConstraints SourceImage;
        public MaskImageConstraints MaskImage;
        public ProcessingCapabilities Processing;
    }

    public sealed class UnsupportedOperationInfo
    {
        public bool Supported;
    }

    public sealed class OperationsInfo
    {
        public TextToImageCapabilities TextToImage;
        public ImageToImageCapabilities ImageToImage;
        public InpaintingCapabilities Inpainting;
    }

    public sealed class PrecisionInfo
    {
        public string Configured;
        public string Resolved;
        public List<string> Available = new List<string>();
        public bool UserSelectable;
    }

    public sealed class LimitsInfo
    {
        public int MaximumConcurrentGenerations;
    }

    public sealed class JobSystemInfo
    {
        public bool Supported;
        public string Persistence;
        public List<string> States = new List<string>();
        public int MaximumRetries;
        public int MaximumConcurrentJobs;
        public bool AutoRetry;
        public string Progress;
    }

    /// <summary>
    /// Typed, parsed form of GET /api/v1/capabilities. Built from <see cref="JsonNode"/>
    /// rather than JsonUtility because the payload contains string arrays nested inside
    /// objects, which JsonUtility does not deserialize reliably.
    /// </summary>
    public sealed class CapabilityDocument
    {
        public ApiVersionInfo Api;
        public ApplicationInfo Application;
        public SchemaVersionsInfo Schemas;
        public RuntimeInfo Runtime;
        public ModelInfo Model;
        public OperationsInfo Operations;
        public PrecisionInfo Precision;
        public LimitsInfo Limits;
        public JobSystemInfo Jobs;

        public SchemaVersion CapabilitiesSchemaVersion => SchemaVersion.Parse(Schemas.Capabilities);

        public SchemaVersion GenerationManifestSchemaVersion => SchemaVersion.Parse(Schemas.GenerationManifest);

        public static CapabilityDocument Parse(string json)
        {
            var root = JsonNode.Parse(json);
            return FromJsonNode(root);
        }

        public static bool TryParse(string json, out CapabilityDocument document)
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

        public static CapabilityDocument FromJsonNode(JsonNode root)
        {
            if (root == null || !root.IsObject)
            {
                throw new FormatException("Capability document root must be a JSON object.");
            }

            var apiNode = root.Get("api");
            var applicationNode = root.Get("application");
            var schemasNode = root.Get("schemas");
            var runtimeNode = root.Get("runtime");
            var modelNode = root.Get("model");
            var operationsNode = root.Get("operations");
            var precisionNode = root.Get("precision");
            var limitsNode = root.Get("limits");
            var jobsNode = root.Get("jobs");

            return new CapabilityDocument
            {
                Api = new ApiVersionInfo
                {
                    Major = apiNode.Get("major").AsInt(),
                    Minor = apiNode.Get("minor").AsInt(),
                },
                Application = new ApplicationInfo
                {
                    Name = applicationNode.Get("name").AsString(),
                    Version = applicationNode.Get("version").AsString(),
                },
                Schemas = new SchemaVersionsInfo
                {
                    Capabilities = schemasNode.Get("capabilities").AsString(),
                    GenerationManifest = schemasNode.Get("generation_manifest").AsString(),
                },
                Runtime = new RuntimeInfo
                {
                    ConfiguredDevice = runtimeNode.Get("configured_device").AsString(),
                    ResolvedDevice = runtimeNode.Get("resolved_device").AsString(),
                    ConfiguredPrecision = runtimeNode.Get("configured_precision").AsString(),
                    ResolvedPrecision = runtimeNode.Get("resolved_precision").AsString(),
                    ModelLoaded = runtimeNode.Get("model_loaded").AsBool(),
                },
                Model = new ModelInfo
                {
                    Id = modelNode.Get("id").AsString(),
                    Revision = modelNode.Get("revision").AsString(),
                    Family = modelNode.Get("family").AsString(),
                    DisplayName = modelNode.Get("display_name").AsString(),
                },
                Operations = ParseOperations(operationsNode),
                Precision = new PrecisionInfo
                {
                    Configured = precisionNode.Get("configured").AsString(),
                    Resolved = precisionNode.Get("resolved").AsString(),
                    Available = precisionNode.Get("available").AsStringList(),
                    UserSelectable = precisionNode.Get("user_selectable").AsBool(),
                },
                Limits = new LimitsInfo
                {
                    MaximumConcurrentGenerations = limitsNode.Get("maximum_concurrent_generations").AsInt(),
                },
                Jobs = jobsNode != null && jobsNode.IsObject
                    ? new JobSystemInfo
                    {
                        Supported = jobsNode.Get("supported").AsBool(),
                        Persistence = jobsNode.Get("persistence").AsString(),
                        States = jobsNode.Get("states").AsStringList(),
                        MaximumRetries = jobsNode.Get("maximum_retries").AsInt(),
                        MaximumConcurrentJobs = jobsNode.Get("maximum_concurrent_jobs").AsInt(),
                        AutoRetry = jobsNode.Get("auto_retry").AsBool(),
                        Progress = jobsNode.Get("progress").AsString(),
                    }
                    : null,
            };
        }

        static OperationsInfo ParseOperations(JsonNode operationsNode)
        {
            var textToImageNode = operationsNode.Get("text_to_image");
            var dimensionsNode = textToImageNode.Get("dimensions");
            var stepsNode = textToImageNode.Get("steps");
            var guidanceNode = textToImageNode.Get("guidance_scale");
            var seedNode = textToImageNode.Get("seed");
            var promptNode = textToImageNode.Get("prompt");
            var negativePromptNode = textToImageNode.Get("negative_prompt");
            var outputNameNode = textToImageNode.Get("output_name");
            var schedulersNode = textToImageNode.Get("schedulers");
            var processingNode = textToImageNode.Get("processing");

            var textToImage = new TextToImageCapabilities
            {
                Supported = textToImageNode.Get("supported").AsBool(),
                AssetTypes = textToImageNode.Get("asset_types").AsStringList(),
                Dimensions = new DimensionConstraints
                {
                    MinimumWidth = dimensionsNode.Get("minimum_width").AsInt(),
                    MaximumWidth = dimensionsNode.Get("maximum_width").AsInt(),
                    MinimumHeight = dimensionsNode.Get("minimum_height").AsInt(),
                    MaximumHeight = dimensionsNode.Get("maximum_height").AsInt(),
                    WidthMultiple = dimensionsNode.Get("width_multiple").AsInt(1),
                    HeightMultiple = dimensionsNode.Get("height_multiple").AsInt(1),
                    SupportedAspectRatios = dimensionsNode.Get("supported_aspect_ratios").AsStringList(),
                },
                Steps = new IntRange
                {
                    Minimum = stepsNode.Get("minimum").AsInt(),
                    Maximum = stepsNode.Get("maximum").AsInt(),
                    Default = stepsNode.Get("default").AsInt(),
                },
                GuidanceScale = new FloatRange
                {
                    Minimum = guidanceNode.Get("minimum").AsFloat(),
                    Maximum = guidanceNode.Get("maximum").AsFloat(),
                    Default = guidanceNode.Get("default").AsFloat(),
                },
                Seed = new SeedConstraints
                {
                    Minimum = seedNode.Get("minimum").AsLong(),
                    Maximum = seedNode.Get("maximum").AsLong(),
                    RandomWhenOmitted = seedNode.Get("random_when_omitted").AsBool(true),
                },
                Prompt = new PromptConstraints
                {
                    MaximumLength = promptNode.Get("maximum_length").AsInt(),
                },
                NegativePrompt = new NegativePromptConstraints
                {
                    Supported = negativePromptNode.Get("supported").AsBool(),
                    MaximumLength = negativePromptNode.Get("maximum_length").AsInt(),
                },
                OutputName = new OutputNameConstraints
                {
                    MaximumLength = outputNameNode.Get("maximum_length").AsInt(),
                },
                Schedulers = new SchedulerCapabilities
                {
                    SelectionSupported = schedulersNode.Get("selection_supported").AsBool(),
                    Default = schedulersNode.Get("default").AsString(),
                    Available = schedulersNode.Get("available").AsStringList(),
                },
                Processing = processingNode.IsObject ? new ProcessingCapabilities
                {
                    TransparencyStrategies = processingNode.Get("transparency_strategies").AsStringList(),
                    BackgroundRemoval = new BackgroundRemovalCapabilities
                    {
                        Available = processingNode.Get("background_removal").Get("available").AsBool(),
                        Backend = processingNode.Get("background_removal").Get("backend").AsString(),
                        Model = processingNode.Get("background_removal").Get("model").AsString(),
                        ProducesNativeAlpha = processingNode.Get("background_removal").Get("produces_native_alpha").AsBool(),
                        UnavailableReason = processingNode.Get("background_removal").Get("unavailable_reason").AsString()
                    },
                    AlphaCleanup = new AlphaCleanupCapabilities
                    {
                        Available = processingNode.Get("alpha_cleanup").Get("available").AsBool(),
                        AlphaThreshold = ParseFloatRange(processingNode.Get("alpha_cleanup").Get("alpha_threshold")),
                        AlphaFeather = ParseFloatRange(processingNode.Get("alpha_cleanup").Get("alpha_feather")),
                        RemoveNearTransparentDefault = processingNode.Get("alpha_cleanup").Get("remove_near_transparent_default").AsBool(),
                        ZeroRgbWhenTransparentDefault = processingNode.Get("alpha_cleanup").Get("zero_rgb_when_transparent_default").AsBool()
                    },
                    SpriteImport = new SpriteImportCapabilities
                    {
                        Supported = processingNode.Get("sprite_import").Get("supported").AsBool(),
                        SingleSpriteOnly = processingNode.Get("sprite_import").Get("single_sprite_only").AsBool(),
                        PivotModes = processingNode.Get("sprite_import").Get("pivot_modes").AsStringList()
                    },
                    Tileable = processingNode.Get("tileable").IsObject
                        ? new TileableProcessingCapabilities
                        {
                            Available = processingNode.Get("tileable").Get("available").AsBool(true),
                            SeamAnalysis = processingNode.Get("tileable").Get("seam_analysis").AsBool(true),
                            SeamCorrection = processingNode.Get("tileable").Get("seam_correction").AsBool(true),
                            PaletteReduction = processingNode.Get("tileable").Get("palette_reduction").AsBool(true),
                            AiInpaintAvailable = processingNode.Get("tileable").Get("ai_inpaint_available").AsBool(),
                            SeamBlendWidth = ParseIntRange(processingNode.Get("tileable").Get("seam_blend_width")),
                            PaletteColorCount = ParseIntRange(processingNode.Get("tileable").Get("palette_color_count")),
                            TargetSize = processingNode.Get("tileable").Get("target_size").AsInt(512),
                            CircularOffsetPx = processingNode.Get("tileable").Get("circular_offset_px").AsInt(256),
                            ProtectedBorderPx = processingNode.Get("tileable").Get("protected_border_px").AsInt(4)
                        }
                        : new TileableProcessingCapabilities()
                } : null,
            };

            return new OperationsInfo
            {
                TextToImage = textToImage,
                ImageToImage = ParseImageToImage(operationsNode.Get("image_to_image")),
                Inpainting = ParseInpainting(operationsNode.Get("inpainting")),
            };
        }

        static ImageToImageCapabilities ParseImageToImage(JsonNode node)
        {
            var parsed = new ImageToImageCapabilities
            {
                Supported = node.Get("supported").AsBool(),
                AssetTypes = node.Get("asset_types").AsStringList(),
            };
            if (node.Get("dimensions").IsObject)
            {
                var dimensionsNode = node.Get("dimensions");
                parsed.Dimensions = new DimensionConstraints
                {
                    MinimumWidth = dimensionsNode.Get("minimum_width").AsInt(),
                    MaximumWidth = dimensionsNode.Get("maximum_width").AsInt(),
                    MinimumHeight = dimensionsNode.Get("minimum_height").AsInt(),
                    MaximumHeight = dimensionsNode.Get("maximum_height").AsInt(),
                    WidthMultiple = dimensionsNode.Get("width_multiple").AsInt(1),
                    HeightMultiple = dimensionsNode.Get("height_multiple").AsInt(1),
                    SupportedAspectRatios = dimensionsNode.Get("supported_aspect_ratios").AsStringList(),
                };
            }

            if (node.Get("steps").IsObject)
                parsed.Steps = ParseIntRange(node.Get("steps"));
            if (node.Get("guidance_scale").IsObject)
                parsed.GuidanceScale = ParseFloatRange(node.Get("guidance_scale"));
            if (node.Get("seed").IsObject)
            {
                var seedNode = node.Get("seed");
                parsed.Seed = new SeedConstraints
                {
                    Minimum = seedNode.Get("minimum").AsLong(),
                    Maximum = seedNode.Get("maximum").AsLong(),
                    RandomWhenOmitted = seedNode.Get("random_when_omitted").AsBool(true),
                };
            }

            if (node.Get("prompt").IsObject)
            {
                parsed.Prompt = new PromptConstraints
                {
                    MaximumLength = node.Get("prompt").Get("maximum_length").AsInt(),
                };
            }

            if (node.Get("negative_prompt").IsObject)
            {
                parsed.NegativePrompt = new NegativePromptConstraints
                {
                    Supported = node.Get("negative_prompt").Get("supported").AsBool(),
                    MaximumLength = node.Get("negative_prompt").Get("maximum_length").AsInt(),
                };
            }

            if (node.Get("output_name").IsObject)
            {
                parsed.OutputName = new OutputNameConstraints
                {
                    MaximumLength = node.Get("output_name").Get("maximum_length").AsInt(),
                };
            }

            if (node.Get("schedulers").IsObject)
            {
                var schedulersNode = node.Get("schedulers");
                parsed.Schedulers = new SchedulerCapabilities
                {
                    SelectionSupported = schedulersNode.Get("selection_supported").AsBool(),
                    Default = schedulersNode.Get("default").AsString(),
                    Available = schedulersNode.Get("available").AsStringList(),
                };
            }

            if (node.Get("denoising_strength").IsObject)
                parsed.DenoisingStrength = ParseFloatRange(node.Get("denoising_strength"));

            if (node.Get("source_image").IsObject)
            {
                var sourceNode = node.Get("source_image");
                parsed.SourceImage = new SourceImageConstraints
                {
                    SupportedFormats = sourceNode.Get("supported_formats").AsStringList(),
                    MaximumByteSize = sourceNode.Get("maximum_byte_size").AsLong(),
                    Dimensions = sourceNode.Get("dimensions").IsObject
                        ? new DimensionConstraints
                        {
                            MinimumWidth = sourceNode.Get("dimensions").Get("minimum_width").AsInt(),
                            MaximumWidth = sourceNode.Get("dimensions").Get("maximum_width").AsInt(),
                            MinimumHeight = sourceNode.Get("dimensions").Get("minimum_height").AsInt(),
                            MaximumHeight = sourceNode.Get("dimensions").Get("maximum_height").AsInt(),
                            WidthMultiple = sourceNode.Get("dimensions").Get("width_multiple").AsInt(1),
                            HeightMultiple = sourceNode.Get("dimensions").Get("height_multiple").AsInt(1),
                            SupportedAspectRatios = sourceNode.Get("dimensions").Get("supported_aspect_ratios").AsStringList(),
                        }
                        : null,
                };
            }

            return parsed;
        }

        static InpaintingCapabilities ParseInpainting(JsonNode node)
        {
            var parsed = new InpaintingCapabilities
            {
                Supported = node.Get("supported").AsBool(),
                AssetTypes = node.Get("asset_types").AsStringList(),
            };
            if (node.Get("dimensions").IsObject)
            {
                var dimensionsNode = node.Get("dimensions");
                parsed.Dimensions = new DimensionConstraints
                {
                    MinimumWidth = dimensionsNode.Get("minimum_width").AsInt(),
                    MaximumWidth = dimensionsNode.Get("maximum_width").AsInt(),
                    MinimumHeight = dimensionsNode.Get("minimum_height").AsInt(),
                    MaximumHeight = dimensionsNode.Get("maximum_height").AsInt(),
                    WidthMultiple = dimensionsNode.Get("width_multiple").AsInt(1),
                    HeightMultiple = dimensionsNode.Get("height_multiple").AsInt(1),
                    SupportedAspectRatios = dimensionsNode.Get("supported_aspect_ratios").AsStringList(),
                };
            }

            if (node.Get("steps").IsObject)
                parsed.Steps = ParseIntRange(node.Get("steps"));
            if (node.Get("guidance_scale").IsObject)
                parsed.GuidanceScale = ParseFloatRange(node.Get("guidance_scale"));
            if (node.Get("seed").IsObject)
            {
                var seedNode = node.Get("seed");
                parsed.Seed = new SeedConstraints
                {
                    Minimum = seedNode.Get("minimum").AsLong(),
                    Maximum = seedNode.Get("maximum").AsLong(),
                    RandomWhenOmitted = seedNode.Get("random_when_omitted").AsBool(true),
                };
            }

            if (node.Get("prompt").IsObject)
            {
                parsed.Prompt = new PromptConstraints
                {
                    MaximumLength = node.Get("prompt").Get("maximum_length").AsInt(),
                };
            }

            if (node.Get("negative_prompt").IsObject)
            {
                parsed.NegativePrompt = new NegativePromptConstraints
                {
                    Supported = node.Get("negative_prompt").Get("supported").AsBool(),
                    MaximumLength = node.Get("negative_prompt").Get("maximum_length").AsInt(),
                };
            }

            if (node.Get("output_name").IsObject)
            {
                parsed.OutputName = new OutputNameConstraints
                {
                    MaximumLength = node.Get("output_name").Get("maximum_length").AsInt(),
                };
            }

            if (node.Get("schedulers").IsObject)
            {
                var schedulersNode = node.Get("schedulers");
                parsed.Schedulers = new SchedulerCapabilities
                {
                    SelectionSupported = schedulersNode.Get("selection_supported").AsBool(),
                    Default = schedulersNode.Get("default").AsString(),
                    Available = schedulersNode.Get("available").AsStringList(),
                };
            }

            if (node.Get("denoising_strength").IsObject)
                parsed.DenoisingStrength = ParseFloatRange(node.Get("denoising_strength"));

            if (node.Get("source_image").IsObject)
            {
                var sourceNode = node.Get("source_image");
                parsed.SourceImage = new SourceImageConstraints
                {
                    SupportedFormats = sourceNode.Get("supported_formats").AsStringList(),
                    MaximumByteSize = sourceNode.Get("maximum_byte_size").AsLong(),
                    Dimensions = sourceNode.Get("dimensions").IsObject
                        ? new DimensionConstraints
                        {
                            MinimumWidth = sourceNode.Get("dimensions").Get("minimum_width").AsInt(),
                            MaximumWidth = sourceNode.Get("dimensions").Get("maximum_width").AsInt(),
                            MinimumHeight = sourceNode.Get("dimensions").Get("minimum_height").AsInt(),
                            MaximumHeight = sourceNode.Get("dimensions").Get("maximum_height").AsInt(),
                            WidthMultiple = sourceNode.Get("dimensions").Get("width_multiple").AsInt(1),
                            HeightMultiple = sourceNode.Get("dimensions").Get("height_multiple").AsInt(1),
                            SupportedAspectRatios = sourceNode.Get("dimensions").Get("supported_aspect_ratios").AsStringList(),
                        }
                        : null,
                };
            }

            if (node.Get("mask_image").IsObject)
            {
                var maskNode = node.Get("mask_image");
                parsed.MaskImage = new MaskImageConstraints
                {
                    SupportedFormats = maskNode.Get("supported_formats").AsStringList(),
                    MaximumByteSize = maskNode.Get("maximum_byte_size").AsLong(),
                    MustMatchSourceDimensions = maskNode.Get("must_match_source_dimensions").AsBool(true),
                    Convention = maskNode.Get("convention").AsString("white_inpaints"),
                    WhiteMeans = maskNode.Get("white_means").AsString("regenerate"),
                    BlackMeans = maskNode.Get("black_means").AsString("keep"),
                    AlphaIgnored = maskNode.Get("alpha_ignored").AsBool(true),
                    Dimensions = maskNode.Get("dimensions").IsObject
                        ? new DimensionConstraints
                        {
                            MinimumWidth = maskNode.Get("dimensions").Get("minimum_width").AsInt(),
                            MaximumWidth = maskNode.Get("dimensions").Get("maximum_width").AsInt(),
                            MinimumHeight = maskNode.Get("dimensions").Get("minimum_height").AsInt(),
                            MaximumHeight = maskNode.Get("dimensions").Get("maximum_height").AsInt(),
                            WidthMultiple = maskNode.Get("dimensions").Get("width_multiple").AsInt(1),
                            HeightMultiple = maskNode.Get("dimensions").Get("height_multiple").AsInt(1),
                            SupportedAspectRatios = maskNode.Get("dimensions").Get("supported_aspect_ratios").AsStringList(),
                        }
                        : null,
                };
            }

            return parsed;
        }

        static FloatRange ParseFloatRange(JsonNode node) => new FloatRange
        {
            Minimum = node.Get("minimum").IsNull ? node.Get("min").AsFloat() : node.Get("minimum").AsFloat(),
            Maximum = node.Get("maximum").IsNull ? node.Get("max").AsFloat() : node.Get("maximum").AsFloat(),
            Default = node.Get("default").AsFloat()
        };

        static IntRange ParseIntRange(JsonNode node) => new IntRange
        {
            Minimum = node.Get("minimum").IsNull ? node.Get("min").AsInt() : node.Get("minimum").AsInt(),
            Maximum = node.Get("maximum").IsNull ? node.Get("max").AsInt() : node.Get("maximum").AsInt(),
            Default = node.Get("default").AsInt()
        };
    }
}
