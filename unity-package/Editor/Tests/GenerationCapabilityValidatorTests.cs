using NUnit.Framework;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Capabilities;
using UnityAiAssets.Editor.Generation;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class GenerationCapabilityValidatorTests
    {
        static CapabilityDocument BuildCapabilities()
        {
            return CapabilityDocument.Parse(@"{
                ""api"": { ""major"": 1, ""minor"": 0 },
                ""application"": { ""name"": ""unity-ai-asset-generator"", ""version"": ""0.3.0"" },
                ""schemas"": { ""capabilities"": ""1.0"", ""generation_manifest"": ""1.0"" },
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
                        ""prompt"": { ""maximum_length"": 20 },
                        ""negative_prompt"": { ""supported"": true, ""maximum_length"": 20 },
                        ""output_name"": { ""maximum_length"": 10 },
                        ""schedulers"": { ""selection_supported"": false, ""default"": ""pndm"", ""available"": [] }
                    },
                    ""image_to_image"": { ""supported"": false },
                    ""inpainting"": { ""supported"": false }
                },
                ""precision"": { ""configured"": ""auto"", ""resolved"": ""float32"", ""available"": [""float32""], ""user_selectable"": false },
                ""limits"": { ""maximum_concurrent_generations"": 1 }
            }");
        }

        static TextureGenerationRequestModel ValidRequest()
        {
            return new TextureGenerationRequestModel
            {
                Prompt = "a valid prompt",
                NegativePrompt = "",
                Width = 512,
                Height = 512,
                Steps = 25,
                GuidanceScale = 7f,
                UseExplicitSeed = false,
                Seed = 0,
                OutputName = "tex",
                DestinationFolder = "Assets/Generated/Textures",
                CreateMaterial = false,
            };
        }

        [Test]
        public void Validate_AcceptsWellFormedRequest()
        {
            var issues = GenerationCapabilityValidator.Validate(ValidRequest(), BuildCapabilities());
            Assert.IsEmpty(issues);
        }

        [Test]
        public void Validate_RejectsWidthNotMultiple()
        {
            var request = ValidRequest();
            request.Width = 513;
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "width" && i.Code == FieldIssueCode.ValueNotMultiple));
        }

        [Test]
        public void Validate_RejectsWidthBelowMinimum()
        {
            var request = ValidRequest();
            request.Width = 4;
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "width" && i.Code == FieldIssueCode.ValueBelowMinimum));
        }

        [Test]
        public void Validate_RejectsHeightAboveMaximum()
        {
            var request = ValidRequest();
            request.Height = 2048;
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "height" && i.Code == FieldIssueCode.ValueAboveMaximum));
        }

        [Test]
        public void Validate_RejectsStepsOutOfRange()
        {
            var request = ValidRequest();
            request.Steps = 0;
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "steps" && i.Code == FieldIssueCode.ValueBelowMinimum));
        }

        [Test]
        public void Validate_RejectsGuidanceScaleOutOfRange()
        {
            var request = ValidRequest();
            request.GuidanceScale = 31f;
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "guidance_scale" && i.Code == FieldIssueCode.ValueAboveMaximum));
        }

        [Test]
        public void Validate_RejectsSeedOutOfRangeOnlyWhenExplicit()
        {
            var request = ValidRequest();
            request.UseExplicitSeed = false;
            request.Seed = -1; // Would be invalid, but ignored while not using an explicit seed.
            var issuesImplicit = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsFalse(issuesImplicit.Exists(i => i.FieldName == "seed"));

            request.UseExplicitSeed = true;
            request.Seed = 5_000_000_000L; // Above uint32 max.
            var issuesExplicit = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issuesExplicit.Exists(i => i.FieldName == "seed" && i.Code == FieldIssueCode.ValueAboveMaximum));
        }

        [Test]
        public void Validate_RejectsEmptyPrompt()
        {
            var request = ValidRequest();
            request.Prompt = "   ";
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "prompt" && i.Code == FieldIssueCode.FieldRequired));
        }

        [Test]
        public void Validate_RejectsPromptTooLong()
        {
            var request = ValidRequest();
            request.Prompt = new string('a', 21);
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "prompt" && i.Code == FieldIssueCode.ValueTooLong));
        }

        [Test]
        public void Validate_RejectsNegativePromptTooLong()
        {
            var request = ValidRequest();
            request.NegativePrompt = new string('b', 21);
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "negative_prompt" && i.Code == FieldIssueCode.ValueTooLong));
        }

        [Test]
        public void Validate_RejectsOutputNameTooLong()
        {
            var request = ValidRequest();
            request.OutputName = "way_too_long_output_name";
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "output_name" && i.Code == FieldIssueCode.ValueTooLong));
        }

        [Test]
        public void Validate_RejectsEmptyOutputName()
        {
            var request = ValidRequest();
            request.OutputName = "  ";
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(i => i.FieldName == "output_name" && i.Code == FieldIssueCode.FieldRequired));
        }

        [Test]
        public void Validate_ReturnsSingleIssue_WhenOperationUnsupported()
        {
            var capabilities = BuildCapabilities();
            capabilities.Operations.TextToImage.Supported = false;
            var issues = GenerationCapabilityValidator.Validate(ValidRequest(), capabilities);
            Assert.AreEqual(1, issues.Count);
            Assert.AreEqual(AppErrorCode.OperationUnsupported, issues[0].Code);
        }

        [Test]
        public void Validate_RejectsWhenCapabilitiesMissing()
        {
            var issues = GenerationCapabilityValidator.Validate(ValidRequest(), null);
            Assert.IsNotEmpty(issues);
        }

        [Test]
        public void Validate_DoesNotCoerceRequestValues()
        {
            var request = ValidRequest();
            request.Width = 513;
            var originalWidth = request.Width;
            GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.AreEqual(originalWidth, request.Width);
        }

        [Test]
        public void Validate_UsesRequestedAssetType()
        {
            var request = ValidRequest();
            request.AssetType = "sprite";
            var issues = GenerationCapabilityValidator.Validate(request, BuildCapabilities());
            Assert.IsTrue(issues.Exists(issue => issue.FieldName == "asset_type"));
        }
    }
}
