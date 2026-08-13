using System.Linq;
using NUnit.Framework;
using UnityAiAssets.Editor.Generation;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class BatchExpansionTests
    {
        [Test]
        public void PromptAndVariationExpansion_IsOrderedAndDeterministic()
        {
            Assert.IsTrue(BatchExpansion.TryExpand(
                new[] { "rusty plate", "mossy brick" },
                BatchSeedModeKind.Fixed, 2, 10, 0, 0, "wall",
                out var first, out var errors));
            Assert.IsEmpty(errors);
            Assert.IsTrue(BatchExpansion.TryExpand(
                new[] { "rusty plate", "mossy brick" },
                BatchSeedModeKind.Fixed, 2, 10, 0, 0, "wall",
                out var second, out _));
            Assert.AreEqual(4, first.JobCount);
            CollectionAssert.AreEqual(
                new[] { 10L, 11L, 10L, 11L },
                first.Items.Select(item => item.Seed).ToArray());
            CollectionAssert.AreEqual(
                new[] { 0, 1, 0, 1 },
                first.Items.Select(item => item.VariationIndex).ToArray());
            CollectionAssert.AreEqual(
                new[] { 0, 0, 1, 1 },
                first.Items.Select(item => item.PromptIndex).ToArray());
            Assert.AreEqual("wall_p00_s10_v00", first.Items[0].OutputName);
            Assert.AreEqual(first.Items.Count, second.Items.Count);
            for (var i = 0; i < first.Items.Count; i++)
                Assert.AreEqual(first.Items[i].Seed, second.Items[i].Seed);
        }

        [Test]
        public void SequentialSeedRange_AvoidsDuplicateSeeds()
        {
            Assert.IsTrue(BatchExpansion.TryExpand(
                new[] { "metal" },
                BatchSeedModeKind.Sequential, 2, 0, 10, 12, "tex",
                out var plan, out var errors));
            Assert.IsEmpty(errors);
            CollectionAssert.AreEqual(
                new[] { 10L, 13L, 11L, 14L, 12L, 15L },
                plan.Items.Select(item => item.Seed).ToArray());
            Assert.AreEqual(plan.Items.Select(item => item.Seed).Distinct().Count(), plan.Items.Count);
            Assert.AreEqual("10, 13, 11, 14, 12, 15", plan.SeedSummary());
        }

        [Test]
        public void RandomMode_UsesProvidedSeedAsBase()
        {
            Assert.IsTrue(BatchExpansion.TryExpand(
                new[] { "a", "b" },
                BatchSeedModeKind.Random, 3, 42, 0, 0, "tex",
                out var plan, out _));
            CollectionAssert.AreEqual(new[] { 42L }, plan.BaseSeeds.ToArray());
            CollectionAssert.AreEqual(
                new[] { 42L, 43L, 44L, 42L, 43L, 44L },
                plan.Items.Select(item => item.Seed).ToArray());
        }

        [Test]
        public void InvalidAndExcessiveConfigurations_AreRejected()
        {
            Assert.IsFalse(BatchExpansion.TryExpand(
                new string[0], BatchSeedModeKind.Fixed, 1, 1, 0, 0, "tex",
                out _, out var empty));
            StringAssert.Contains("At least one prompt", empty[0]);

            Assert.IsFalse(BatchExpansion.TryExpand(
                new[] { "  " }, BatchSeedModeKind.Fixed, 1, 1, 0, 0, "tex",
                out _, out var blank));
            StringAssert.Contains("empty", blank[0]);

            Assert.IsFalse(BatchExpansion.TryExpand(
                new[] { "ok" }, BatchSeedModeKind.Sequential, 1, 0, 9, 3, "tex",
                out _, out var range));
            StringAssert.Contains("less than or equal", range[0]);

            Assert.IsFalse(BatchExpansion.TryExpand(
                new[] { "a", "b", "c" }, BatchSeedModeKind.Sequential, 2, 0, 1, 10, "tex",
                out _, out var tooLarge, maxJobs: 4));
            StringAssert.Contains("exceeds the maximum", tooLarge[0]);
        }

        [Test]
        public void OutputName_IsTruncated()
        {
            var name = BatchExpansion.BuildOutputName(
                "very_long_texture_name_that_should_be_clipped", 0, 123456, 0, 24);
            Assert.LessOrEqual(name.Length, 24);
            StringAssert.EndsWith("_s123456_v00", name);
        }

        [Test]
        public void ToApiValue_MatchesBackendSeedModes()
        {
            Assert.AreEqual("fixed", BatchExpansion.ToApiValue(BatchSeedModeKind.Fixed));
            Assert.AreEqual("random", BatchExpansion.ToApiValue(BatchSeedModeKind.Random));
            Assert.AreEqual("sequential", BatchExpansion.ToApiValue(BatchSeedModeKind.Sequential));
        }
    }
}
