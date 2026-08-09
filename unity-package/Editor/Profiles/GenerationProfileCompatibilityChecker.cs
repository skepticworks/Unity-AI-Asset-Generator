using System.Collections.Generic;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Capabilities;

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
                capabilities,
                profile.Processing.TransparencyStrategy,
                profile.Unity.PixelsPerUnit,
                profile.Unity.PivotMode,
                profile.Unity.CustomPivotX,
                profile.Unity.CustomPivotY);
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
            CapabilityDocument capabilities,
            string transparencyStrategy = "none",
            float pixelsPerUnit = 100f,
            string pivotMode = "center",
            float customPivotX = .5f,
            float customPivotY = .5f)
        {
            return CheckValues(assetType, width, height, steps, guidanceScale, seed, capabilities,
                transparencyStrategy, pixelsPerUnit, pivotMode, customPivotX, customPivotY);
        }

        static ProfileCompatibility CheckValues(
            string assetType,
            int width,
            int height,
            int steps,
            float guidanceScale,
            long? seed,
            CapabilityDocument capabilities,
            string transparencyStrategy,
            float pixelsPerUnit,
            string pivotMode,
            float customPivotX,
            float customPivotY)
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
                !CapabilityLimits.IsInRange(
                    guidanceScale, operation.GuidanceScale.Minimum, operation.GuidanceScale.Maximum))
                Add(result, CompatibilityReasonCodes.GuidanceOutOfRange, "Guidance is outside backend limits.");

            if (seed.HasValue && operation.Seed != null &&
                !CapabilityLimits.IsInRange(seed.Value, operation.Seed.Minimum, operation.Seed.Maximum))
                Add(result, CompatibilityReasonCodes.SeedOutOfRange, "Seed is outside backend limits.");
            if (transparencyStrategy == "background_removal" &&
                operation.Processing?.BackgroundRemoval?.Available != true)
                Add(result, CompatibilityReasonCodes.BackgroundRemovalUnavailable,
                    "The backend does not provide background removal.");
            if (assetType == "sprite" || assetType == "icon")
            {
                if (pixelsPerUnit <= 0)
                    Add(result, CompatibilityReasonCodes.PixelsPerUnitInvalid, "Pixels per unit must be greater than zero.");
                if (pivotMode != "center" && pivotMode != "bottom_center" && pivotMode != "custom")
                    Add(result, CompatibilityReasonCodes.PivotModeInvalid, "Pivot mode must be center, bottom_center, or custom.");
                if (pivotMode == "custom" &&
                    (!CapabilityLimits.IsInRange(customPivotX, 0f, 1f) ||
                     !CapabilityLimits.IsInRange(customPivotY, 0f, 1f)))
                    Add(result, CompatibilityReasonCodes.CustomPivotInvalid, "Custom pivot coordinates must be between zero and one.");
            }

            result.State = result.ReasonCodes.Count == 0
                ? ProfileCompatibilityState.Compatible
                : ProfileCompatibilityState.Incompatible;
            return result;
        }

        static void Range(int value, int minimum, int maximum, string code, string label, ProfileCompatibility result)
        {
            if (!CapabilityLimits.IsInRange(value, minimum, maximum))
                Add(result, code, label + " is outside backend limits.");
        }

        static void Multiple(int value, int multiple, string code, string label, ProfileCompatibility result)
        {
            if (!CapabilityLimits.IsMultiple(value, multiple))
                Add(result, code, label + " violates the backend multiple.");
        }

        static void Add(ProfileCompatibility result, string code, string message)
        {
            result.ReasonCodes.Add(code);
            result.Messages.Add(message);
        }
    }
}
