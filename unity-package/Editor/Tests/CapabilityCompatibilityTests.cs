using NUnit.Framework;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Capabilities;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class CapabilityCompatibilityTests
    {
        static CapabilityDocument BuildDocument(int apiMajor, string capabilitiesSchema, string manifestSchema)
        {
            return new CapabilityDocument
            {
                Api = new ApiVersionInfo { Major = apiMajor, Minor = 0 },
                Application = new ApplicationInfo { Name = "unity-ai-asset-generator", Version = "0.3.0" },
                Schemas = new SchemaVersionsInfo
                {
                    Capabilities = capabilitiesSchema,
                    GenerationManifest = manifestSchema,
                },
                Runtime = new RuntimeInfo
                {
                    ConfiguredDevice = "auto",
                    ResolvedDevice = "cpu",
                    ConfiguredPrecision = "auto",
                    ResolvedPrecision = "float32",
                    ModelLoaded = false,
                },
                Model = new ModelInfo { Id = "model", Revision = null, Family = "sd15", DisplayName = null },
                Operations = new OperationsInfo
                {
                    TextToImage = new TextToImageCapabilities
                    {
                        Supported = true,
                        AssetTypes = new System.Collections.Generic.List<string> { "texture" },
                        Dimensions = new DimensionConstraints
                        {
                            MinimumWidth = 8, MaximumWidth = 1024, MinimumHeight = 8, MaximumHeight = 1024,
                            WidthMultiple = 8, HeightMultiple = 8,
                        },
                        Steps = new IntRange { Minimum = 1, Maximum = 150, Default = 25 },
                        GuidanceScale = new FloatRange { Minimum = 0f, Maximum = 30f, Default = 7f },
                        Seed = new SeedConstraints { Minimum = 0, Maximum = 4294967295L, RandomWhenOmitted = true },
                        Prompt = new PromptConstraints { MaximumLength = 2000 },
                        NegativePrompt = new NegativePromptConstraints { Supported = true, MaximumLength = 2000 },
                        OutputName = new OutputNameConstraints { MaximumLength = 100 },
                        Schedulers = new SchedulerCapabilities
                        {
                            SelectionSupported = false,
                            Default = "pndm",
                            Available = new System.Collections.Generic.List<string>(),
                        },
                    },
                    ImageToImage = new ImageToImageCapabilities { Supported = false },
                    Inpainting = new InpaintingCapabilities { Supported = false },
                },
                Precision = new PrecisionInfo
                {
                    Configured = "auto",
                    Resolved = "float32",
                    Available = new System.Collections.Generic.List<string> { "float32" },
                    UserSelectable = false,
                },
                Limits = new LimitsInfo { MaximumConcurrentGenerations = 1 },
            };
        }

        [Test]
        public void Check_AcceptsMatchingMajors()
        {
            var document = BuildDocument(1, "1.0", "1.0");
            var result = CapabilityCompatibilityChecker.Check(document);
            Assert.IsTrue(result.IsCompatible);
        }

        [Test]
        public void Check_AcceptsHigherMinor()
        {
            var document = BuildDocument(1, "1.7", "1.3");
            var result = CapabilityCompatibilityChecker.Check(document);
            Assert.IsTrue(result.IsCompatible, string.Join(",", result.Reasons));
        }

        [Test]
        public void Check_RejectsHigherApiMajor()
        {
            var document = BuildDocument(2, "1.0", "1.0");
            var result = CapabilityCompatibilityChecker.Check(document);
            Assert.IsFalse(result.IsCompatible);
            Assert.IsTrue(result.Reasons.Exists(r => r.Contains("API major")));
        }

        [Test]
        public void Check_RejectsHigherCapabilitiesSchemaMajor()
        {
            var document = BuildDocument(1, "2.0", "1.0");
            var result = CapabilityCompatibilityChecker.Check(document);
            Assert.IsFalse(result.IsCompatible);
            Assert.IsTrue(result.Reasons.Exists(r => r.Contains("capabilities")));
        }

        [Test]
        public void Check_RejectsHigherManifestSchemaMajor()
        {
            var document = BuildDocument(1, "1.0", "2.0");
            var result = CapabilityCompatibilityChecker.Check(document);
            Assert.IsFalse(result.IsCompatible);
            Assert.IsTrue(result.Reasons.Exists(r => r.Contains("generation_manifest")));
        }

        [Test]
        public void Check_RejectsNullDocument()
        {
            var result = CapabilityCompatibilityChecker.Check(null);
            Assert.IsFalse(result.IsCompatible);
        }

        [Test]
        public void Check_RejectsMalformedSchemaVersionString()
        {
            var document = BuildDocument(1, "not-a-version", "1.0");
            var result = CapabilityCompatibilityChecker.Check(document);
            Assert.IsFalse(result.IsCompatible);
        }
    }
}
