using NUnit.Framework;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class GenerationProfileRegistryTests
    {
        [Test] public void LoadsAndFiltersBuiltins()
        {
            var registry = new GenerationProfileRegistry();
            Assert.GreaterOrEqual(System.Linq.Enumerable.Count(registry.FilterByAssetType("texture")), 2);
            Assert.IsTrue(registry.Get("ps1_environment_texture").Builtin);
        }
    }
}
