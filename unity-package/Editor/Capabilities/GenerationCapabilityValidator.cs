using System.Collections.Generic;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Generation;

namespace UnityAiAssets.Editor.Capabilities
{
    /// <summary>
    /// A single preflight validation problem. Mirrors the backend's field issue codes so
    /// the same messaging vocabulary is used client- and server-side.
    /// </summary>
    public sealed class CapabilityValidationIssue
    {
        public string FieldName;
        public string Code;
        public string Message;

        public override string ToString() => string.IsNullOrEmpty(FieldName) ? Message : $"{FieldName}: {Message}";
    }

    /// <summary>
    /// Client-side preflight validation of a generation request against a fetched capability
    /// document. This never silently coerces values (e.g. clamping width to the maximum) -
    /// it only reports issues; the caller decides how/whether to surface them.
    /// </summary>
    public static class GenerationCapabilityValidator
    {
        public static List<CapabilityValidationIssue> Validate(
            TextureGenerationRequestModel request,
            CapabilityDocument capabilities)
        {
            var issues = new List<CapabilityValidationIssue>();
            if (request == null)
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = null,
                    Code = FieldIssueCode.FieldRequired,
                    Message = "A generation request is required.",
                });
                return issues;
            }

            if (capabilities == null)
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = null,
                    Code = FieldIssueCode.ValueInvalid,
                    Message = "Capabilities have not been loaded yet; refresh before generating.",
                });
                return issues;
            }

            var textToImage = capabilities.Operations?.TextToImage;
            if (textToImage == null || !textToImage.Supported)
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = "operation",
                    Code = AppErrorCode.OperationUnsupported,
                    Message = "The backend does not currently support text_to_image generation.",
                });
                return issues;
            }

            var assetType = string.IsNullOrWhiteSpace(request.AssetType) ? "texture" : request.AssetType;
            if (textToImage.AssetTypes == null || !textToImage.AssetTypes.Contains(assetType))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = "asset_type",
                    Code = AppErrorCode.AssetTypeUnsupported,
                    Message = $"The backend does not currently support the '{assetType}' asset type.",
                });
            }

            ValidateDimension(
                "width", request.Width,
                textToImage.Dimensions.MinimumWidth, textToImage.Dimensions.MaximumWidth,
                textToImage.Dimensions.WidthMultiple, issues);
            ValidateDimension(
                "height", request.Height,
                textToImage.Dimensions.MinimumHeight, textToImage.Dimensions.MaximumHeight,
                textToImage.Dimensions.HeightMultiple, issues);

            ValidateIntRange("steps", request.Steps, textToImage.Steps.Minimum, textToImage.Steps.Maximum, issues);
            ValidateFloatRange(
                "guidance_scale", request.GuidanceScale,
                textToImage.GuidanceScale.Minimum, textToImage.GuidanceScale.Maximum, issues);

            if (request.UseExplicitSeed)
            {
                ValidateLongRange("seed", request.Seed, textToImage.Seed.Minimum, textToImage.Seed.Maximum, issues);
            }

            var promptLength = request.Prompt?.Trim().Length ?? 0;
            if (promptLength == 0)
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = "prompt",
                    Code = FieldIssueCode.FieldRequired,
                    Message = "Prompt is required and must not be empty.",
                });
            }
            else if (promptLength > textToImage.Prompt.MaximumLength)
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = "prompt",
                    Code = FieldIssueCode.ValueTooLong,
                    Message = $"Prompt must be at most {textToImage.Prompt.MaximumLength} characters " +
                               $"(currently {promptLength}).",
                });
            }

            var negativePromptLength = request.NegativePrompt?.Length ?? 0;
            if (negativePromptLength > 0)
            {
                if (!textToImage.NegativePrompt.Supported)
                {
                    issues.Add(new CapabilityValidationIssue
                    {
                        FieldName = "negative_prompt",
                        Code = FieldIssueCode.ValueInvalid,
                        Message = "The backend does not currently support a negative prompt.",
                    });
                }
                else if (negativePromptLength > textToImage.NegativePrompt.MaximumLength)
                {
                    issues.Add(new CapabilityValidationIssue
                    {
                        FieldName = "negative_prompt",
                        Code = FieldIssueCode.ValueTooLong,
                        Message = $"Negative prompt must be at most " +
                                   $"{textToImage.NegativePrompt.MaximumLength} characters " +
                                   $"(currently {negativePromptLength}).",
                    });
                }
            }

            var outputNameLength = request.OutputName?.Trim().Length ?? 0;
            if (outputNameLength == 0)
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = "output_name",
                    Code = FieldIssueCode.FieldRequired,
                    Message = "Output name is required.",
                });
            }
            else if (outputNameLength > textToImage.OutputName.MaximumLength)
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = "output_name",
                    Code = FieldIssueCode.ValueTooLong,
                    Message = $"Output name must be at most {textToImage.OutputName.MaximumLength} characters " +
                               $"(currently {outputNameLength}).",
                });
            }

            return issues;
        }

        static void ValidateDimension(
            string fieldName, int value, int minimum, int maximum, int multiple,
            List<CapabilityValidationIssue> issues)
        {
            if (!CapabilityLimits.IsInRange(value, minimum, int.MaxValue))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = fieldName,
                    Code = FieldIssueCode.ValueBelowMinimum,
                    Message = $"{Capitalize(fieldName)} must be at least {minimum} (currently {value}).",
                });
            }

            if (!CapabilityLimits.IsInRange(value, int.MinValue, maximum))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = fieldName,
                    Code = FieldIssueCode.ValueAboveMaximum,
                    Message = $"{Capitalize(fieldName)} must be at most {maximum} (currently {value}).",
                });
            }

            if (!CapabilityLimits.IsMultiple(value, multiple))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = fieldName,
                    Code = FieldIssueCode.ValueNotMultiple,
                    Message = $"{Capitalize(fieldName)} must be divisible by {multiple} (currently {value}).",
                });
            }
        }

        static void ValidateIntRange(
            string fieldName, int value, int minimum, int maximum, List<CapabilityValidationIssue> issues)
        {
            if (!CapabilityLimits.IsInRange(value, minimum, int.MaxValue))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = fieldName,
                    Code = FieldIssueCode.ValueBelowMinimum,
                    Message = $"{Capitalize(fieldName)} must be at least {minimum} (currently {value}).",
                });
            }

            if (!CapabilityLimits.IsInRange(value, int.MinValue, maximum))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = fieldName,
                    Code = FieldIssueCode.ValueAboveMaximum,
                    Message = $"{Capitalize(fieldName)} must be at most {maximum} (currently {value}).",
                });
            }
        }

        static void ValidateFloatRange(
            string fieldName, float value, float minimum, float maximum, List<CapabilityValidationIssue> issues)
        {
            if (!CapabilityLimits.IsInRange(value, minimum, float.MaxValue))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = fieldName,
                    Code = FieldIssueCode.ValueBelowMinimum,
                    Message = $"{Capitalize(fieldName)} must be at least {minimum} (currently {value}).",
                });
            }

            if (!CapabilityLimits.IsInRange(value, float.MinValue, maximum))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = fieldName,
                    Code = FieldIssueCode.ValueAboveMaximum,
                    Message = $"{Capitalize(fieldName)} must be at most {maximum} (currently {value}).",
                });
            }
        }

        static void ValidateLongRange(
            string fieldName, long value, long minimum, long maximum, List<CapabilityValidationIssue> issues)
        {
            if (!CapabilityLimits.IsInRange(value, minimum, long.MaxValue))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = fieldName,
                    Code = FieldIssueCode.ValueBelowMinimum,
                    Message = $"{Capitalize(fieldName)} must be at least {minimum} (currently {value}).",
                });
            }

            if (!CapabilityLimits.IsInRange(value, long.MinValue, maximum))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = fieldName,
                    Code = FieldIssueCode.ValueAboveMaximum,
                    Message = $"{Capitalize(fieldName)} must be at most {maximum} (currently {value}).",
                });
            }
        }

        static string Capitalize(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return value;
            }

            return char.ToUpperInvariant(value[0]) + value.Substring(1);
        }
    }
}
