using System.IO;
using NUnit.Framework;
using UnityAiAssets.Editor.Importing;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class ImportedGenerationRegistryTests
    {
        [Test]
        public void MarkImported_PreventsDuplicateAndSurvivesReload()
        {
            var path = Path.Combine(Path.GetTempPath(), "UnityAiAssetsTests", "imported-" + Path.GetRandomFileName() + ".json");
            try
            {
                var registry = new ImportedGenerationRegistry(path);
                Assert.IsFalse(registry.IsImported("gen-1"));
                Assert.IsTrue(registry.MarkImported("gen-1"));
                Assert.IsFalse(registry.MarkImported("gen-1"));
                Assert.IsTrue(registry.IsImported("gen-1"));

                var reloaded = new ImportedGenerationRegistry(path);
                Assert.IsTrue(reloaded.IsImported("gen-1"));
                Assert.AreEqual(1, reloaded.Count);
            }
            finally
            {
                if (File.Exists(path))
                    File.Delete(path);
            }
        }

        [Test]
        public void FilterNew_SkipsAlreadyImportedIds()
        {
            var path = Path.Combine(Path.GetTempPath(), "UnityAiAssetsTests", "imported-" + Path.GetRandomFileName() + ".json");
            try
            {
                var registry = new ImportedGenerationRegistry(path);
                registry.MarkImported("keep");
                CollectionAssert.AreEqual(
                    new[] { "fresh" },
                    System.Linq.Enumerable.ToArray(registry.FilterNew(new[] { "keep", "fresh" })));
            }
            finally
            {
                if (File.Exists(path))
                    File.Delete(path);
            }
        }
    }
}
