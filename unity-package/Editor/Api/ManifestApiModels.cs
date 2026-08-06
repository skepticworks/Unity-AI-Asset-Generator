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
                },
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
