using System.IO;
using NUnit.Framework;
using UnityAiAssets.Editor.Profiles;
using UnityEngine;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class UserProfileRepositoryTests
    {
        string _root;
        [SetUp] public void SetUp() { _root = Path.Combine(Application.temporaryCachePath, "uai-profile-tests", System.Guid.NewGuid().ToString("N")); }
        [TearDown] public void TearDown() { if (Directory.Exists(_root)) Directory.Delete(_root, true); }

        [Test] public void DuplicateGetsNewIdentityAndSaveCreatesDirectory()
        {
            var repository = new UserProfileRepository(_root);
            var source = new GenerationProfile { Id = "builtin", DisplayName = "Built In", Builtin = true };
            var copy = repository.Duplicate(source);
            Assert.AreNotEqual(source.Id, copy.Id);
            Assert.AreEqual("Copy of Built In", copy.DisplayName);
            Assert.IsFalse(copy.Builtin);
            copy.AssetType = "texture";
            copy.Prompt.TemplateId = "ps1_environment_texture"; copy.Prompt.TemplateRevision = 1;
            copy.NegativePrompt.ProfileId = "base_ps1_negative"; copy.NegativePrompt.ProfileRevision = 1;
            copy.Defaults.Width = 64; copy.Defaults.Height = 64; copy.Defaults.Steps = 1;
            copy.Defaults.SeedStrategy = "random";
            copy.Unity.ImportProfileId = "ps1_environment_texture";
            copy.Unity.SuggestedOutputDirectory = "Assets/Test";
            var path = repository.Save(copy);
            Assert.IsTrue(File.Exists(path));
        }
    }
}
