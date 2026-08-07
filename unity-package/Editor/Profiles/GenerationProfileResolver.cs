using System;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Profiles
{
    public sealed class GenerationProfileResolver
    {
        readonly ProfileCatalog _catalog;

        public GenerationProfileResolver(ProfileCatalog catalog)
        {
            _catalog = catalog ?? throw new ArgumentNullException(nameof(catalog));
        }

        public ResolvedGenerationSettings Resolve(
            GenerationProfile profile, UserProfileOverrides overrides, CapabilityDocument capabilities = null)
        {
            if (profile == null) throw new ArgumentNullException(nameof(profile));
            overrides = overrides ?? new UserProfileOverrides();
            var template = _catalog.GetPromptTemplate(profile.Prompt.TemplateId);
            var negative = _catalog.GetNegativeProfile(profile.NegativePrompt.ProfileId);
            var maximumNegative = capabilities?.Operations?.TextToImage?.NegativePrompt?.MaximumLength ?? 0;
            var seed = overrides.Seed ??
                (profile.Defaults.SeedStrategy == "fixed" ? profile.Defaults.FixedSeed : null);
            var constructedPrompt = PromptTemplateResolver.Resolve(
                template, overrides.Subject, profile.Prompt.DefaultModifiers, profile.AssetType, overrides.AdditionalPrompt);
            var maximumPrompt = capabilities?.Operations?.TextToImage?.Prompt?.MaximumLength ?? 0;
            var constructedNegative = NegativePromptResolver.Resolve(
                negative, profile.NegativePrompt.AdditionalTerms, overrides.AdditionalNegative, maximumNegative);
            var width = overrides.Width ?? profile.Defaults.Width;
            var height = overrides.Height ?? profile.Defaults.Height;
            var steps = overrides.Steps ?? profile.Defaults.Steps;
            var guidance = overrides.Guidance ?? profile.Defaults.GuidanceScale;
            var compatibility = GenerationProfileCompatibilityChecker.CheckEffective(
                profile.AssetType, width, height, steps, guidance, seed, capabilities);
            if (!string.IsNullOrEmpty(constructedNegative) &&
                capabilities?.Operations?.TextToImage?.NegativePrompt?.Supported == false)
            {
                compatibility.ReasonCodes.Add(CompatibilityReasonCodes.NegativePromptUnsupported);
                compatibility.Messages.Add("The backend does not support negative prompts.");
                compatibility.State = ProfileCompatibilityState.Incompatible;
            }
            if (maximumPrompt > 0 && constructedPrompt.Length > maximumPrompt)
            {
                compatibility.ReasonCodes.Add(CompatibilityReasonCodes.PromptTooLong);
                compatibility.Messages.Add(
                    $"Resolved prompt is {constructedPrompt.Length} characters; maximum is {maximumPrompt}.");
                compatibility.State = ProfileCompatibilityState.Incompatible;
            }
            return new ResolvedGenerationSettings
            {
                AssetType = profile.AssetType,
                ConstructedPrompt = constructedPrompt,
                ConstructedNegativePrompt = constructedNegative,
                Width = width,
                Height = height,
                Steps = steps,
                GuidanceScale = guidance,
                Seed = seed,
                OutputName = string.IsNullOrWhiteSpace(overrides.OutputName) ? "texture" : overrides.OutputName.Trim(),
                DestinationFolder = string.IsNullOrWhiteSpace(overrides.DestinationFolder)
                    ? profile.Unity.SuggestedOutputDirectory : overrides.DestinationFolder.Trim(),
                ImportProfileId = string.IsNullOrWhiteSpace(overrides.ImportProfileId)
                    ? profile.Unity.ImportProfileId : overrides.ImportProfileId,
                CreateMaterial = overrides.CreateMaterial ?? profile.Unity.CreateMaterial,
                Compatibility = compatibility,
                GenerationProfileId = profile.Id,
                GenerationProfileRevision = profile.Revision,
                ProfileOrigin = profile.Origin,
                PromptTemplateId = template.Id,
                PromptTemplateRevision = template.Revision,
                NegativePromptProfileId = negative.Id,
                NegativePromptProfileRevision = negative.Revision
            };
        }
    }
}
