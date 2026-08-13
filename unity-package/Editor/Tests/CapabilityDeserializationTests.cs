using NUnit.Framework;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class CapabilityDeserializationTests
    {
        // Mirrors the shape produced by unity_ai_assets.api.schemas.capabilities.CapabilitiesResponse.
        const string FixtureJson = @"{
            ""api"": { ""major"": 1, ""minor"": 0 },
            ""application"": { ""name"": ""unity-ai-asset-generator"", ""version"": ""0.3.0"" },
            ""schemas"": { ""capabilities"": ""1.0"", ""generation_manifest"": ""1.0"" },
            ""runtime"": {
                ""configured_device"": ""auto"",
                ""resolved_device"": ""cuda"",
                ""configured_precision"": ""auto"",
                ""resolved_precision"": ""float16"",
                ""model_loaded"": false
            },
            ""model"": {
                ""id"": ""runwayml/stable-diffusion-v1-5"",
                ""revision"": null,
                ""family"": ""sd15"",
                ""display_name"": ""Stable Diffusion 1.5""
            },
            ""operations"": {
                ""text_to_image"": {
                    ""supported"": true,
                    ""asset_types"": [""texture""],
                    ""dimensions"": {
                        ""minimum_width"": 8, ""maximum_width"": 1024,
                        ""minimum_height"": 8, ""maximum_height"": 1024,
                        ""width_multiple"": 8, ""height_multiple"": 8
                    },
                    ""steps"": { ""minimum"": 1, ""maximum"": 150, ""default"": 25 },
                    ""guidance_scale"": { ""minimum"": 0.0, ""maximum"": 30.0, ""default"": 7.0 },
                    ""seed"": { ""minimum"": 0, ""maximum"": 4294967295, ""random_when_omitted"": true },
                    ""prompt"": { ""maximum_length"": 2000 },
                    ""negative_prompt"": { ""supported"": true, ""maximum_length"": 2000 },
                    ""output_name"": { ""maximum_length"": 100 },
                    ""schedulers"": { ""selection_supported"": false, ""default"": ""pndm"", ""available"": [] }
                },
                ""image_to_image"": { ""supported"": false },
                ""inpainting"": { ""supported"": false }
            },
            ""precision"": {
                ""configured"": ""auto"",
                ""resolved"": ""float16"",
                ""available"": [""float16"", ""float32""],
                ""user_selectable"": false
            },
            ""limits"": { ""maximum_concurrent_generations"": 1 }
        }";

        [Test]
        public void Parse_ReadsTopLevelVersionsAndIdentity()
        {
            var document = CapabilityDocument.Parse(FixtureJson);

            Assert.AreEqual(1, document.Api.Major);
            Assert.AreEqual(0, document.Api.Minor);
            Assert.AreEqual("unity-ai-asset-generator", document.Application.Name);
            Assert.AreEqual("0.3.0", document.Application.Version);
            Assert.AreEqual("1.0", document.Schemas.Capabilities);
            Assert.AreEqual("1.0", document.Schemas.GenerationManifest);
        }

        [Test]
        public void Parse_ReadsRuntimeAndModel()
        {
            var document = CapabilityDocument.Parse(FixtureJson);

            Assert.AreEqual("auto", document.Runtime.ConfiguredDevice);
            Assert.AreEqual("cuda", document.Runtime.ResolvedDevice);
            Assert.AreEqual("float16", document.Runtime.ResolvedPrecision);
            Assert.IsFalse(document.Runtime.ModelLoaded);

            Assert.AreEqual("runwayml/stable-diffusion-v1-5", document.Model.Id);
            Assert.IsNull(document.Model.Revision);
            Assert.AreEqual("sd15", document.Model.Family);
            Assert.AreEqual("Stable Diffusion 1.5", document.Model.DisplayName);
        }

        [Test]
        public void Parse_ReadsStringArraysInsideNestedObjects()
        {
            var document = CapabilityDocument.Parse(FixtureJson);

            CollectionAssert.AreEqual(new[] { "texture" }, document.Operations.TextToImage.AssetTypes);
            CollectionAssert.AreEqual(new[] { "float16", "float32" }, document.Precision.Available);
            CollectionAssert.IsEmpty(document.Operations.TextToImage.Schedulers.Available);
        }

        [Test]
        public void Parse_ReadsDimensionAndRangeConstraints()
        {
            var document = CapabilityDocument.Parse(FixtureJson);
            var t2i = document.Operations.TextToImage;

            Assert.IsTrue(t2i.Supported);
            Assert.AreEqual(8, t2i.Dimensions.MinimumWidth);
            Assert.AreEqual(1024, t2i.Dimensions.MaximumWidth);
            Assert.AreEqual(8, t2i.Dimensions.WidthMultiple);
            Assert.AreEqual(1, t2i.Steps.Minimum);
            Assert.AreEqual(150, t2i.Steps.Maximum);
            Assert.AreEqual(25, t2i.Steps.Default);
            Assert.AreEqual(0.0f, t2i.GuidanceScale.Minimum);
            Assert.AreEqual(30.0f, t2i.GuidanceScale.Maximum);
            Assert.AreEqual(0L, t2i.Seed.Minimum);
            Assert.AreEqual(4294967295L, t2i.Seed.Maximum);
            Assert.IsTrue(t2i.Seed.RandomWhenOmitted);
            Assert.AreEqual(2000, t2i.Prompt.MaximumLength);
            Assert.IsTrue(t2i.NegativePrompt.Supported);
            Assert.AreEqual(100, t2i.OutputName.MaximumLength);
        }

        [Test]
        public void Parse_ReadsUnsupportedOperations()
        {
            var document = CapabilityDocument.Parse(FixtureJson);
            Assert.IsFalse(document.Operations.ImageToImage.Supported);
            Assert.IsFalse(document.Operations.Inpainting.Supported);
        }

        [Test]
        public void Parse_ReadsImageToImageCapabilities()
        {
            const string json = @"{
                ""api"": { ""major"": 1, ""minor"": 1 },
                ""application"": { ""name"": ""unity-ai-asset-generator"", ""version"": ""0.7.0"" },
                ""schemas"": { ""capabilities"": ""1.3"", ""generation_manifest"": ""1.4"" },
                ""runtime"": {
                    ""configured_device"": ""auto"", ""resolved_device"": ""cpu"",
                    ""configured_precision"": ""auto"", ""resolved_precision"": ""float32"",
                    ""model_loaded"": false
                },
                ""model"": { ""id"": ""m"", ""revision"": null, ""family"": ""sd15"", ""display_name"": null },
                ""operations"": {
                    ""text_to_image"": {
                        ""supported"": true, ""asset_types"": [""texture""],
                        ""dimensions"": {
                            ""minimum_width"": 8, ""maximum_width"": 1024,
                            ""minimum_height"": 8, ""maximum_height"": 1024,
                            ""width_multiple"": 8, ""height_multiple"": 8
                        },
                        ""steps"": { ""minimum"": 1, ""maximum"": 150, ""default"": 25 },
                        ""guidance_scale"": { ""minimum"": 0.0, ""maximum"": 30.0, ""default"": 7.0 },
                        ""seed"": { ""minimum"": 0, ""maximum"": 4294967295, ""random_when_omitted"": true },
                        ""prompt"": { ""maximum_length"": 2000 },
                        ""negative_prompt"": { ""supported"": true, ""maximum_length"": 2000 },
                        ""output_name"": { ""maximum_length"": 100 },
                        ""schedulers"": { ""selection_supported"": false, ""default"": ""pndm"", ""available"": [] }
                    },
                    ""image_to_image"": {
                        ""supported"": true, ""asset_types"": [""texture"", ""sprite""],
                        ""dimensions"": {
                            ""minimum_width"": 8, ""maximum_width"": 1024,
                            ""minimum_height"": 8, ""maximum_height"": 1024,
                            ""width_multiple"": 8, ""height_multiple"": 8
                        },
                        ""steps"": { ""minimum"": 1, ""maximum"": 150, ""default"": 25 },
                        ""guidance_scale"": { ""minimum"": 0.0, ""maximum"": 30.0, ""default"": 7.0 },
                        ""seed"": { ""minimum"": 0, ""maximum"": 4294967295, ""random_when_omitted"": true },
                        ""prompt"": { ""maximum_length"": 2000 },
                        ""negative_prompt"": { ""supported"": true, ""maximum_length"": 2000 },
                        ""output_name"": { ""maximum_length"": 100 },
                        ""schedulers"": { ""selection_supported"": false, ""default"": ""pndm"", ""available"": [] },
                        ""denoising_strength"": { ""minimum"": 0.0, ""maximum"": 1.0, ""default"": 0.75 },
                        ""source_image"": {
                            ""supported_formats"": [""png"", ""jpeg"", ""webp""],
                            ""maximum_byte_size"": 10485760
                        }
                    },
                    ""inpainting"": { ""supported"": false }
                },
                ""precision"": { ""configured"": ""auto"", ""resolved"": ""float32"", ""available"": [""float32""], ""user_selectable"": false },
                ""limits"": { ""maximum_concurrent_generations"": 1 }
            }";
            var document = CapabilityDocument.Parse(json);
            Assert.IsTrue(document.Operations.ImageToImage.Supported);
            Assert.AreEqual(0.75f, document.Operations.ImageToImage.DenoisingStrength.Default);
            CollectionAssert.AreEqual(new[] { "png", "jpeg", "webp" }, document.Operations.ImageToImage.SourceImage.SupportedFormats);
            Assert.AreEqual(10485760L, document.Operations.ImageToImage.SourceImage.MaximumByteSize);
            CollectionAssert.Contains(document.Operations.ImageToImage.AssetTypes, "sprite");
        }

        [Test]
        public void Parse_ReadsInpaintingCapabilities()
        {
            const string json = @"{
                ""api"": { ""major"": 1, ""minor"": 2 },
                ""application"": { ""name"": ""unity-ai-asset-generator"", ""version"": ""0.8.0"" },
                ""schemas"": { ""capabilities"": ""1.4"", ""generation_manifest"": ""1.5"" },
                ""runtime"": {
                    ""configured_device"": ""auto"", ""resolved_device"": ""cpu"",
                    ""configured_precision"": ""auto"", ""resolved_precision"": ""float32"",
                    ""model_loaded"": false
                },
                ""model"": { ""id"": ""m"", ""revision"": null, ""family"": ""sd15"", ""display_name"": null },
                ""operations"": {
                    ""text_to_image"": {
                        ""supported"": true, ""asset_types"": [""texture""],
                        ""dimensions"": {
                            ""minimum_width"": 8, ""maximum_width"": 1024,
                            ""minimum_height"": 8, ""maximum_height"": 1024,
                            ""width_multiple"": 8, ""height_multiple"": 8
                        },
                        ""steps"": { ""minimum"": 1, ""maximum"": 150, ""default"": 25 },
                        ""guidance_scale"": { ""minimum"": 0.0, ""maximum"": 30.0, ""default"": 7.0 },
                        ""seed"": { ""minimum"": 0, ""maximum"": 4294967295, ""random_when_omitted"": true },
                        ""prompt"": { ""maximum_length"": 2000 },
                        ""negative_prompt"": { ""supported"": true, ""maximum_length"": 2000 },
                        ""output_name"": { ""maximum_length"": 100 },
                        ""schedulers"": { ""selection_supported"": false, ""default"": ""pndm"", ""available"": [] }
                    },
                    ""image_to_image"": { ""supported"": true },
                    ""inpainting"": {
                        ""supported"": true, ""asset_types"": [""texture"", ""sprite""],
                        ""dimensions"": {
                            ""minimum_width"": 8, ""maximum_width"": 1024,
                            ""minimum_height"": 8, ""maximum_height"": 1024,
                            ""width_multiple"": 8, ""height_multiple"": 8
                        },
                        ""steps"": { ""minimum"": 1, ""maximum"": 150, ""default"": 25 },
                        ""guidance_scale"": { ""minimum"": 0.0, ""maximum"": 30.0, ""default"": 7.0 },
                        ""seed"": { ""minimum"": 0, ""maximum"": 4294967295, ""random_when_omitted"": true },
                        ""prompt"": { ""maximum_length"": 2000 },
                        ""negative_prompt"": { ""supported"": true, ""maximum_length"": 2000 },
                        ""output_name"": { ""maximum_length"": 100 },
                        ""schedulers"": { ""selection_supported"": false, ""default"": ""pndm"", ""available"": [] },
                        ""denoising_strength"": { ""minimum"": 0.0, ""maximum"": 1.0, ""default"": 0.75 },
                        ""source_image"": {
                            ""supported_formats"": [""png"", ""jpeg"", ""webp""],
                            ""maximum_byte_size"": 10485760
                        },
                        ""mask_image"": {
                            ""supported_formats"": [""png"", ""jpeg"", ""webp""],
                            ""maximum_byte_size"": 10485760,
                            ""must_match_source_dimensions"": true,
                            ""convention"": ""white_inpaints"",
                            ""white_means"": ""regenerate"",
                            ""black_means"": ""keep"",
                            ""alpha_ignored"": true
                        }
                    }
                },
                ""precision"": { ""configured"": ""auto"", ""resolved"": ""float32"", ""available"": [""float32""], ""user_selectable"": false },
                ""limits"": { ""maximum_concurrent_generations"": 1 }
            }";
            var document = CapabilityDocument.Parse(json);
            Assert.IsTrue(document.Operations.Inpainting.Supported);
            Assert.AreEqual("white_inpaints", document.Operations.Inpainting.MaskImage.Convention);
            Assert.AreEqual("regenerate", document.Operations.Inpainting.MaskImage.WhiteMeans);
            Assert.AreEqual("keep", document.Operations.Inpainting.MaskImage.BlackMeans);
            Assert.IsTrue(document.Operations.Inpainting.MaskImage.MustMatchSourceDimensions);
            Assert.IsTrue(document.Operations.Inpainting.MaskImage.AlphaIgnored);
            CollectionAssert.AreEqual(
                new[] { "png", "jpeg", "webp" },
                document.Operations.Inpainting.MaskImage.SupportedFormats);
        }

        [Test]
        public void Parse_ReadsLimits()
        {
            var document = CapabilityDocument.Parse(FixtureJson);
            Assert.AreEqual(1, document.Limits.MaximumConcurrentGenerations);
        }

        [Test]
        public void TryParse_ReturnsFalseForMalformedJson()
        {
            Assert.IsFalse(CapabilityDocument.TryParse("{not valid json", out var document));
            Assert.IsNull(document);
        }

        [Test]
        public void TryParse_ReturnsFalseForNonObjectRoot()
        {
            Assert.IsFalse(CapabilityDocument.TryParse("[1,2,3]", out var document));
            Assert.IsNull(document);
        }
    }
}
