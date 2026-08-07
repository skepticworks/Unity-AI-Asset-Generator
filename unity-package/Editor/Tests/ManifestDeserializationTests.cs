using NUnit.Framework;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class ManifestDeserializationTests
    {
        // Mirrors unity_ai_assets.domain.generation_manifest.GenerationManifest.to_dict().
        const string FixtureJson = @"{
            ""schema"": { ""name"": ""generation-manifest"", ""version"": ""1.0"" },
            ""generation"": {
                ""id"": ""11111111-1111-1111-1111-111111111111"",
                ""operation"": ""text_to_image"",
                ""asset_type"": ""texture"",
                ""status"": ""completed"",
                ""created_at_utc"": ""2026-08-06T12:00:00Z"",
                ""completed_at_utc"": ""2026-08-06T12:01:30Z"",
                ""elapsed_seconds"": 90.5
            },
            ""application"": { ""name"": ""unity-ai-asset-generator"", ""version"": ""0.3.0"", ""api_major"": 1 },
            ""model"": { ""id"": ""runwayml/stable-diffusion-v1-5"", ""revision"": null, ""family"": ""sd15"" },
            ""runtime"": { ""device"": ""cuda"", ""precision"": ""float16"", ""scheduler"": ""pndm"" },
            ""request"": {
                ""prompt"": ""rusted wall"",
                ""negative_prompt"": ""text, watermark"",
                ""width"": 512,
                ""height"": 512,
                ""steps"": 25,
                ""guidance_scale"": 7.0,
                ""seed"": 12345,
                ""output_name"": ""wall""
            },
            ""outputs"": [
                {
                    ""kind"": ""image"",
                    ""format"": ""png"",
                    ""relative_path"": ""wall.png"",
                    ""width"": 512,
                    ""height"": 512,
                    ""sha256"": ""abc123"",
                    ""byte_size"": 4096
                }
            ]
        }";

        [Test]
        public void Parse_ReadsSchemaBlock()
        {
            var manifest = GenerationManifestDocument.Parse(FixtureJson);
            Assert.AreEqual("generation-manifest", manifest.Schema.Name);
            Assert.AreEqual("1.0", manifest.Schema.Version);
        }

        [Test]
        public void Parse_ReadsGenerationBlock()
        {
            var manifest = GenerationManifestDocument.Parse(FixtureJson);
            Assert.AreEqual("11111111-1111-1111-1111-111111111111", manifest.Generation.Id);
            Assert.AreEqual("text_to_image", manifest.Generation.Operation);
            Assert.AreEqual("texture", manifest.Generation.AssetType);
            Assert.AreEqual("completed", manifest.Generation.Status);
            Assert.AreEqual(90.5f, manifest.Generation.ElapsedSeconds, 0.001f);
        }

        [Test]
        public void Parse_ReadsApplicationModelAndRuntime()
        {
            var manifest = GenerationManifestDocument.Parse(FixtureJson);
            Assert.AreEqual("unity-ai-asset-generator", manifest.Application.Name);
            Assert.AreEqual("0.3.0", manifest.Application.Version);
            Assert.AreEqual(1, manifest.Application.ApiMajor);

            Assert.AreEqual("runwayml/stable-diffusion-v1-5", manifest.Model.Id);
            Assert.IsNull(manifest.Model.Revision);
            Assert.AreEqual("sd15", manifest.Model.Family);

            Assert.AreEqual("cuda", manifest.Runtime.Device);
            Assert.AreEqual("float16", manifest.Runtime.Precision);
            Assert.AreEqual("pndm", manifest.Runtime.Scheduler);
        }

        [Test]
        public void Parse_ReadsRequestEcho()
        {
            var manifest = GenerationManifestDocument.Parse(FixtureJson);
            Assert.AreEqual("rusted wall", manifest.Request.Prompt);
            Assert.AreEqual("text, watermark", manifest.Request.NegativePrompt);
            Assert.AreEqual(512, manifest.Request.Width);
            Assert.AreEqual(512, manifest.Request.Height);
            Assert.AreEqual(25, manifest.Request.Steps);
            Assert.AreEqual(7.0f, manifest.Request.GuidanceScale);
            Assert.AreEqual(12345L, manifest.Request.Seed);
            Assert.AreEqual("wall", manifest.Request.OutputName);
        }

        [Test]
        public void Parse_ReadsOutputsArray()
        {
            var manifest = GenerationManifestDocument.Parse(FixtureJson);
            Assert.AreEqual(1, manifest.Outputs.Count);
            var output = manifest.Outputs[0];
            Assert.AreEqual("image", output.Kind);
            Assert.AreEqual("png", output.Format);
            Assert.AreEqual("wall.png", output.RelativePath);
            Assert.AreEqual("abc123", output.Sha256);
            Assert.AreEqual(4096L, output.ByteSize);
        }

        [Test]
        public void FindOutput_IsCaseInsensitiveAndReturnsNullWhenMissing()
        {
            var manifest = GenerationManifestDocument.Parse(FixtureJson);
            Assert.IsNotNull(manifest.FindOutput("IMAGE"));
            Assert.IsNull(manifest.FindOutput("thumbnail"));
        }

        [Test]
        public void SchemaVersionValue_ParsesToStructuredVersion()
        {
            var manifest = GenerationManifestDocument.Parse(FixtureJson);
            var version = manifest.SchemaVersionValue;
            Assert.AreEqual(1, version.Major);
            Assert.AreEqual(0, version.Minor);
        }

        [Test]
        public void TryParse_ReturnsFalseForMalformedJson()
        {
            Assert.IsFalse(GenerationManifestDocument.TryParse("{broken", out var manifest));
            Assert.IsNull(manifest);
        }

        [Test]
        public void Parse_HandlesEmptyOutputsArray()
        {
            const string json = @"{
                ""schema"": { ""name"": ""generation-manifest"", ""version"": ""1.0"" },
                ""generation"": {
                    ""id"": ""x"", ""operation"": ""text_to_image"", ""asset_type"": ""texture"",
                    ""status"": ""completed"", ""created_at_utc"": ""2026-01-01T00:00:00Z"",
                    ""completed_at_utc"": ""2026-01-01T00:00:01Z"", ""elapsed_seconds"": 1.0
                },
                ""application"": { ""name"": ""a"", ""version"": ""0.3.0"", ""api_major"": 1 },
                ""model"": { ""id"": ""m"", ""revision"": null, ""family"": ""sd15"" },
                ""runtime"": { ""device"": ""cpu"", ""precision"": ""float32"", ""scheduler"": ""pndm"" },
                ""request"": {
                    ""prompt"": ""p"", ""negative_prompt"": """", ""width"": 8, ""height"": 8,
                    ""steps"": 1, ""guidance_scale"": 0.0, ""seed"": 0, ""output_name"": ""o""
                },
                ""outputs"": []
            }";

            var manifest = GenerationManifestDocument.Parse(json);
            Assert.IsEmpty(manifest.Outputs);
            Assert.IsNull(manifest.FindOutput("image"));
        }

        [Test]
        public void Parse_ReadsOptionalProfileBlockFromManifest11()
        {
            var json = FixtureJson.Replace(
                @"""version"": ""1.0""",
                @"""version"": ""1.1""").Replace(
                @"""outputs"": [",
                @"""profile"": { ""generation_profile_id"": ""p"", ""generation_profile_revision"": 2,
                    ""profile_origin"": ""builtin"", ""prompt_template_id"": ""t"",
                    ""prompt_template_revision"": 1, ""negative_prompt_profile_id"": ""n"",
                    ""negative_prompt_profile_revision"": 3, ""unity_import_profile_id"": ""i"" },
                  ""outputs"": [");
            var manifest = GenerationManifestDocument.Parse(json);
            Assert.AreEqual("p", manifest.Profile.GenerationProfileId);
            Assert.AreEqual("i", manifest.Profile.UnityImportProfileId);
            Assert.AreEqual(1, manifest.SchemaVersionValue.Major);
        }
    }
}
