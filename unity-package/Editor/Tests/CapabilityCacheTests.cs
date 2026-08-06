using NUnit.Framework;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Capabilities;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class CapabilityCacheTests
    {
        static CapabilityDocument CompatibleDocument()
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
                        ""prompt"": { ""maximum_length"": 2000 },
                        ""negative_prompt"": { ""supported"": true, ""maximum_length"": 2000 },
                        ""output_name"": { ""maximum_length"": 100 },
                        ""schedulers"": { ""selection_supported"": false, ""default"": ""pndm"", ""available"": [] }
                    },
                    ""image_to_image"": { ""supported"": false },
                    ""inpainting"": { ""supported"": false }
                },
                ""precision"": { ""configured"": ""auto"", ""resolved"": ""float32"", ""available"": [""float32""], ""user_selectable"": false },
                ""limits"": { ""maximum_concurrent_generations"": 1 }
            }");
        }

        static CapabilityDocument IncompatibleDocument()
        {
            var doc = CompatibleDocument();
            doc.Api.Major = 99;
            return doc;
        }

        [Test]
        public void NormalizeKey_TrimsTrailingSlashAndLowercases()
        {
            Assert.AreEqual("http://127.0.0.1:8000", CapabilityCache.NormalizeKey("HTTP://127.0.0.1:8000/"));
        }

        [Test]
        public void Get_ReturnsUnknownForNeverFetchedUrl()
        {
            var cache = new CapabilityCache();
            var entry = cache.Get("http://unused-url-for-test:9999");
            Assert.AreEqual(CapabilityState.Unknown, entry.State);
            Assert.IsNull(entry.Document);
        }

        [Test]
        public void SetReady_WithCompatibleDocument_MarksReady()
        {
            var cache = new CapabilityCache();
            const string url = "http://127.0.0.1:8001";
            cache.SetReady(url, CompatibleDocument());

            var entry = cache.Get(url);
            Assert.AreEqual(CapabilityState.Ready, entry.State);
            Assert.IsNotNull(entry.Document);
            Assert.IsNull(entry.ErrorMessage);
        }

        [Test]
        public void SetReady_WithIncompatibleDocument_MarksIncompatible()
        {
            var cache = new CapabilityCache();
            const string url = "http://127.0.0.1:8002";
            cache.SetReady(url, IncompatibleDocument());

            var entry = cache.Get(url);
            Assert.AreEqual(CapabilityState.Incompatible, entry.State);
            Assert.IsNotNull(entry.ErrorMessage);
        }

        [Test]
        public void SetUnavailable_WithNoPriorDocument_MarksUnavailable()
        {
            var cache = new CapabilityCache();
            const string url = "http://127.0.0.1:8003";
            cache.SetUnavailable(url, "connection refused");

            var entry = cache.Get(url);
            Assert.AreEqual(CapabilityState.Unavailable, entry.State);
            Assert.AreEqual("connection refused", entry.ErrorMessage);
        }

        [Test]
        public void SetUnavailable_AfterPriorReady_MarksStaleAndKeepsDocument()
        {
            var cache = new CapabilityCache();
            const string url = "http://127.0.0.1:8004";
            cache.SetReady(url, CompatibleDocument());
            cache.SetUnavailable(url, "timed out");

            var entry = cache.Get(url);
            Assert.AreEqual(CapabilityState.Stale, entry.State);
            Assert.IsNotNull(entry.Document);
            Assert.AreEqual("timed out", entry.ErrorMessage);
        }

        [Test]
        public void Invalidate_RemovesCachedEntry()
        {
            var cache = new CapabilityCache();
            const string url = "http://127.0.0.1:8005";
            cache.SetReady(url, CompatibleDocument());
            cache.Invalidate(url);

            var entry = cache.Get(url);
            Assert.AreEqual(CapabilityState.Unknown, entry.State);
            Assert.IsNull(entry.Document);
        }

        [Test]
        public void DifferentUrls_AreCachedIndependently()
        {
            var cache = new CapabilityCache();
            cache.SetReady("http://host-a:8000", CompatibleDocument());

            var entryA = cache.Get("http://host-a:8000");
            var entryB = cache.Get("http://host-b:8000");

            Assert.AreEqual(CapabilityState.Ready, entryA.State);
            Assert.AreEqual(CapabilityState.Unknown, entryB.State);
        }

        [Test]
        public void SetLoading_TransitionsToLoadingState()
        {
            var cache = new CapabilityCache();
            const string url = "http://127.0.0.1:8006";
            cache.SetLoading(url);

            var entry = cache.Get(url);
            Assert.AreEqual(CapabilityState.Loading, entry.State);
        }
    }
}
