using NUnit.Framework;
using UnityAiAssets.Editor.Prompting;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class NegativePromptResolverTests
    {
        [Test] public void DeduplicatesExactlyAndPreservesOrder()
        {
            var profile = new NegativePromptProfile { Terms = { "text", "logo" } };
            Assert.AreEqual("text, logo, Text", NegativePromptResolver.Resolve(profile, new[] { "logo", "Text" }, "text", 100));
        }
        [Test] public void FailsRatherThanTruncating()
        {
            var profile = new NegativePromptProfile { Terms = { "one", "two" } };
            Assert.Throws<System.ArgumentException>(() => NegativePromptResolver.Resolve(profile, null, null, 3));
        }
    }
}
