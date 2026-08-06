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
    }

    public sealed class UnsupportedOperationInfo
    {
        public bool Supported;
    }

    public sealed class OperationsInfo
    {
        public TextToImageCapabilities TextToImage;
        public UnsupportedOperationInfo ImageToImage;
        public UnsupportedOperationInfo Inpainting;
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
            };

            return new OperationsInfo
            {
                TextToImage = textToImage,
                ImageToImage = new UnsupportedOperationInfo
                {
                    Supported = operationsNode.Get("image_to_image").Get("supported").AsBool(),
                },
                Inpainting = new UnsupportedOperationInfo
                {
                    Supported = operationsNode.Get("inpainting").Get("supported").AsBool(),
                },
            };
        }
    }
}
