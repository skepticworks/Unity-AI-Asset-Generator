using NUnit.Framework;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class ModelDeserializationTests
    {
        const string ListJson = @"{
            ""models"": [
                {
                    ""id"": ""acme__sd15"",
                    ""name"": ""Acme SD 1.5"",
                    ""version"": null,
                    ""revision"": ""abc123"",
                    ""source"": ""local_directory"",
                    ""source_identifier"": ""acme/sd15"",
                    ""source_url"": null,
                    ""license"": {
                        ""known"": false,
                        ""name"": null,
                        ""url"": null,
                        ""file"": ""LICENSE"",
                        ""identifier"": null
                    },
                    ""model_type"": ""diffusers_pipeline"",
                    ""pipeline_class"": ""StableDiffusionPipeline"",
                    ""family"": ""sd15"",
                    ""installed_at"": ""2026-08-17T14:00:00+00:00"",
                    ""status"": ""installed"",
                    ""usable"": true,
                    ""active"": true,
                    ""size_bytes"": 2048,
                    ""validation"": {
                        ""state"": ""valid"",
                        ""checked_at"": ""2026-08-17T14:00:00+00:00"",
                        ""issues"": []
                    },
                    ""compatibility"": {
                        ""schema_name"": ""model-compatibility"",
                        ""schema_version"": ""1.0"",
                        ""schema_status"": ""supported"",
                        ""architecture"": ""sd15"",
                        ""pipeline_type"": ""stable_diffusion"",
                        ""pipeline_class"": ""StableDiffusionPipeline"",
                        ""model_family"": ""sd15"",
                        ""supported_operations"": [""text_to_image"", ""image_to_image"", ""inpainting""],
                        ""required_components"": [""unet"", ""vae""],
                        ""backend_engine"": ""diffusers"",
                        ""generation_modes"": [""text_to_image""]
                    },
                    ""hash_algorithm"": ""sha256"",
                    ""files"": [
                        { ""path"": ""model_index.json"", ""sha256"": ""aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"", ""byte_size"": 12 }
                    ]
                }
            ],
            ""storage"": {
                ""directory"": ""C:/tmp/models"",
                ""exists"": true,
                ""accessible"": true,
                ""writable"": true,
                ""created"": false,
                ""issue"": null,
                ""search_paths"": [""C:/tmp/old-models""],
                ""free_bytes"": 1000,
                ""total_volume_bytes"": 2000
            },
            ""offline_mode"": false,
            ""active_model_id"": ""acme__sd15""
        }";

        [Test]
        public void Parse_ListReadsModelsStorageAndOffline()
        {
            Assert.IsTrue(ModelListDocument.TryParse(ListJson, out var document));
            Assert.AreEqual(1, document.Models.Count);
            Assert.IsFalse(document.OfflineMode);
            Assert.AreEqual("acme__sd15", document.ActiveModelId);
            Assert.AreEqual("C:/tmp/models", document.Storage.Directory);
            Assert.IsTrue(document.Storage.Accessible);
            CollectionAssert.AreEqual(new[] { "C:/tmp/old-models" }, document.Storage.SearchPaths);
        }

        [Test]
        public void Parse_ModelReadsLicenseAsUnknownWhenNotKnown()
        {
            ModelListDocument.TryParse(ListJson, out var document);
            var model = document.Models[0];
            Assert.IsFalse(model.License.Known);
            Assert.AreEqual("See LICENSE (identifier unknown)", model.License.Display);
            Assert.IsTrue(model.Usable);
            Assert.IsTrue(model.Active);
            Assert.AreEqual(2048, model.SizeBytes);
            Assert.AreEqual("valid", model.Validation.State);
        }

        [Test]
        public void Parse_CompatibilityManifestAndOperations()
        {
            ModelListDocument.TryParse(ListJson, out var document);
            var compat = document.Models[0].Compatibility;
            Assert.IsTrue(compat.SchemaSupported);
            CollectionAssert.Contains(compat.SupportedOperations, "text_to_image");
            CollectionAssert.Contains(compat.RequiredComponents, "unet");
        }

        [Test]
        public void Parse_UnknownCompatibilityMajor()
        {
            const string json = @"{
                ""id"": ""x"",
                ""name"": ""X"",
                ""source"": ""huggingface"",
                ""source_identifier"": ""x/y"",
                ""license"": { ""known"": false },
                ""model_type"": ""diffusers_pipeline"",
                ""family"": ""unknown"",
                ""status"": ""installed"",
                ""usable"": true,
                ""validation"": { ""state"": ""valid"", ""issues"": [] },
                ""compatibility"": {
                    ""schema_version"": ""2.0"",
                    ""schema_status"": ""unsupported_major"",
                    ""supported_operations"": []
                }
            }";
            Assert.IsTrue(InstalledModelDocument.TryParse(json, out var model));
            Assert.AreEqual("unsupported_major", model.Compatibility.SchemaStatus);
            Assert.IsFalse(model.Compatibility.SchemaSupported);
        }

        [Test]
        public void DiskUsage_ParsesPerModelSizes()
        {
            const string json = @"{
                ""total_bytes"": 4096,
                ""models"": [ { ""id"": ""acme__sd15"", ""size_bytes"": 4096 } ],
                ""free_bytes"": 10,
                ""volume_total_bytes"": 100,
                ""calculated_at"": ""2026-08-17T14:00:00+00:00"",
                ""stale"": false
            }";
            Assert.IsTrue(ModelDiskUsageDocument.TryParse(json, out var usage));
            Assert.AreEqual(4096, usage.TotalBytes);
            Assert.AreEqual("acme__sd15", usage.Models[0].Key);
            Assert.AreEqual(4096, usage.Models[0].Value);
        }

        [Test]
        public void ApiEndpoints_IncludeModelRoutes()
        {
            Assert.AreEqual("/api/v1/models", ApiEndpoints.Models);
            Assert.AreEqual("/api/v1/models/storage", ApiEndpoints.ModelStorage);
            Assert.AreEqual("/api/v1/models/acme__sd15", ApiEndpoints.Model("acme__sd15"));
            Assert.AreEqual("/api/v1/models/acme__sd15/validate", ApiEndpoints.ModelValidate("acme__sd15"));
            Assert.AreEqual("/api/v1/models/acme__sd15/activate", ApiEndpoints.ModelActivate("acme__sd15"));
            Assert.AreEqual("/api/v1/models/install", ApiEndpoints.ModelInstall);
            Assert.AreEqual("/api/v1/models/offline", ApiEndpoints.ModelOffline);
        }

        [Test]
        public void InstallJson_UsesLocalDirectorySource()
        {
            var json = ModelInstallRequestJson.LocalDirectory(@"C:\models\sd15", "local/sd15", "SD15");
            Assert.IsTrue(json.Contains("\"source\":\"local_directory\"") || json.Contains("\"source\": \"local_directory\""));
            Assert.IsTrue(json.Contains("local_directory"));
        }
    }
}
