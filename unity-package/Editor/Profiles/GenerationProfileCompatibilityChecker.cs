using System.Collections.Generic;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Profiles
{
    public sealed class ProfileCompatibility
    {
        public ProfileCompatibilityState State;
        public List<string> ReasonCodes = new List<string>();
        public List<string> Messages = new List<string>();
        public bool CanGenerate => State == ProfileCompatibilityState.Compatible;
    }

    public static class GenerationProfileCompatibilityChecker
    {
        public static ProfileCompatibility Check(GenerationProfile profile, CapabilityDocument capabilities)
        {
            if (profile == null)
            {
                var missing = new ProfileCompatibility
                {
                    State = ProfileCompatibilityState.Incompatible
                };
                Add(missing, CompatibilityReasonCodes.CapabilitiesUnavailable, "A generation profile is required.");
                return missing;
            }

            return CheckValues(
                profile.AssetType,
                profile.Defaults.Width,
                profile.Defaults.Height,
                profile.Defaults.Steps,
                profile.Defaults.GuidanceScale,
                profile.Defaults.FixedSeed,
                capabilities);
        }

        /// <summary>
        /// Re-evaluate compatibility for effective settings after user overrides.
        /// Values are never silently clamped.
        /// </summary>
        public static ProfileCompatibility CheckEffective(
            string assetType,
            int width,
            int height,
            int steps,
            float guidanceScale,
            long? seed,
            CapabilityDocument capabilities)
        {
            return CheckValues(assetType, width, height, steps, guidanceScale, seed, capabilities);
        }

        static ProfileCompatibility CheckValues(
            string assetType,
            int width,
            int height,
            int steps,
            float guidanceScale,
            long? seed,
            CapabilityDocument capabilities)
        {
            var result = new ProfileCompatibility();
            if (capabilities?.Operations?.TextToImage == null)
            {
                Add(result, CompatibilityReasonCodes.CapabilitiesUnavailable, "Backend capabilities are unavailable.");
                result.State = ProfileCompatibilityState.Unknown;
                return result;
            }

            var operation = capabilities.Operations.TextToImage;
            if (!operation.Supported)
                Add(result, CompatibilityReasonCodes.OperationUnsupported, "text_to_image is unsupported.");
            if (operation.AssetTypes == null || !operation.AssetTypes.Contains(assetType))
                Add(result, CompatibilityReasonCodes.AssetTypeUnsupported, $"Asset type '{assetType}' is unsupported.");

            if (operation.Dimensions != null)
            {
                Range(width, operation.Dimensions.MinimumWidth, operation.Dimensions.MaximumWidth,
                    CompatibilityReasonCodes.WidthOutOfRange, "Width", result);
                Range(height, operation.Dimensions.MinimumHeight, operation.Dimensions.MaximumHeight,
                    CompatibilityReasonCodes.HeightOutOfRange, "Height", result);
                Multiple(width, operation.Dimensions.WidthMultiple,
                    CompatibilityReasonCodes.WidthMultipleInvalid, "Width", result);
                Multiple(height, operation.Dimensions.HeightMultiple,
                    CompatibilityReasonCodes.HeightMultipleInvalid, "Height", result);
            }

            if (operation.Steps != null)
                Range(steps, operation.Steps.Minimum, operation.Steps.Maximum,
                    CompatibilityReasonCodes.StepsOutOfRange, "Steps", result);

            if (operation.GuidanceScale != null &&
                (guidanceScale < operation.GuidanceScale.Minimum || guidanceScale > operation.GuidanceScale.Maximum))
                Add(result, CompatibilityReasonCodes.GuidanceOutOfRange, "Guidance is outside backend limits.");

            if (seed.HasValue && operation.Seed != null &&
                (seed.Value < operation.Seed.Minimum || seed.Value > operation.Seed.Maximum))
                Add(result, CompatibilityReasonCodes.SeedOutOfRange, "Seed is outside backend limits.");

            result.State = result.ReasonCodes.Count == 0
                ? ProfileCompatibilityState.Compatible
                : ProfileCompatibilityState.Incompatible;
            return result;
        }

        static void Range(int value, int minimum, int maximum, string code, string label, ProfileCompatibility result)
        {
            if (value < minimum || value > maximum) Add(result, code, label + " is outside backend limits.");
        }

        static void Multiple(int value, int multiple, string code, string label, ProfileCompatibility result)
        {
            if (multiple > 1 && value % multiple != 0) Add(result, code, label + " violates the backend multiple.");
        }

        static void Add(ProfileCompatibility result, string code, string message)
        {
            result.ReasonCodes.Add(code);
            result.Messages.Add(message);
        }
    }
}
