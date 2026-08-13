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
            var imageToImage = capabilities.Operations?.ImageToImage;
            if (request.UseImageToImage)
            {
                if (imageToImage == null || !imageToImage.Supported)
                {
                    issues.Add(new CapabilityValidationIssue
                    {
                        FieldName = "operation",
                        Code = AppErrorCode.OperationUnsupported,
                        Message =
                            "The backend does not currently support image_to_image. " +
                            "Img2img was not converted to text-to-image.",
                    });
                    return issues;
                }

                if (request.SourceTexture == null)
                {
                    issues.Add(new CapabilityValidationIssue
                    {
                        FieldName = "source_image",
                        Code = FieldIssueCode.FieldRequired,
                        Message =
                            "A source image is required for image-to-image generation. " +
                            "The source is the init/latent image, not a reference-conditioning input.",
                    });
                }
                else
                {
                    var sourceDims = imageToImage.SourceImage?.Dimensions ?? imageToImage.Dimensions;
                    if (sourceDims != null)
                    {
                        ValidateDimension(
                            "source_image.width", request.SourceTexture.width,
                            sourceDims.MinimumWidth, sourceDims.MaximumWidth,
                            sourceDims.WidthMultiple, issues);
                        ValidateDimension(
                            "source_image.height", request.SourceTexture.height,
                            sourceDims.MinimumHeight, sourceDims.MaximumHeight,
                            sourceDims.HeightMultiple, issues);
                    }

                    if (imageToImage.SourceImage != null && imageToImage.SourceImage.MaximumByteSize > 0)
                    {
                        if (SourceImageCodec.TryEncodePng(request.SourceTexture, out var png, out var encodeError))
                        {
                            if (png.Length > imageToImage.SourceImage.MaximumByteSize)
                            {
                                issues.Add(new CapabilityValidationIssue
                                {
                                    FieldName = "source_image",
                                    Code = FieldIssueCode.ValueAboveMaximum,
                                    Message =
                                        $"Source image is {png.Length} bytes; maximum is " +
                                        $"{imageToImage.SourceImage.MaximumByteSize} bytes.",
                                });
                            }
                        }
                        else
                        {
                            issues.Add(new CapabilityValidationIssue
                            {
                                FieldName = "source_image",
                                Code = FieldIssueCode.FormatInvalid,
                                Message = encodeError,
                            });
                        }
                    }
                }

                var strengthRange = imageToImage.DenoisingStrength;
                if (strengthRange != null)
                {
                    ValidateFloatRange(
                        "denoising_strength", request.DenoisingStrength,
                        strengthRange.Minimum, strengthRange.Maximum, issues);
                }
                else
                {
                    ValidateFloatRange("denoising_strength", request.DenoisingStrength, 0f, 1f, issues);
                }
            }
            else if (textToImage == null || !textToImage.Supported)
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = "operation",
                    Code = AppErrorCode.OperationUnsupported,
                    Message = "The backend does not currently support text_to_image generation.",
                });
                return issues;
            }

            if (textToImage == null)
            {
                return issues;
            }

            var assetType = string.IsNullOrWhiteSpace(request.AssetType) ? "texture" : request.AssetType;
            var assetTypes = request.UseImageToImage && imageToImage?.AssetTypes != null && imageToImage.AssetTypes.Count > 0
                ? imageToImage.AssetTypes
                : textToImage.AssetTypes;
            if (assetTypes == null || !assetTypes.Contains(assetType))
            {
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = "asset_type",
                    Code = AppErrorCode.AssetTypeUnsupported,
                    Message = $"The backend does not currently support the '{assetType}' asset type.",
                });
            }
            if (request.TransparencyStrategy == "background_removal" &&
                textToImage.Processing?.BackgroundRemoval?.Available != true)
            {
                var reason = textToImage.Processing?.BackgroundRemoval?.UnavailableReason;
                issues.Add(new CapabilityValidationIssue
                {
                    FieldName = "transparency_strategy",
                    Code = AppErrorCode.BackgroundRemovalUnavailable,
                    Message = string.IsNullOrWhiteSpace(reason)
                        ? "The backend does not currently provide background removal."
                        : reason,
                });
            }
            if (request.ApplySeamCorrection)
            {
                if (request.Width != 512 || request.Height != 512)
                {
                    issues.Add(new CapabilityValidationIssue
                    {
                        FieldName = "apply_seam_correction",
                        Code = FieldIssueCode.ValueInvalid,
                        Message = "AI seam repair requires exactly 512×512.",
                    });
                }
                if (textToImage.Processing?.Tileable?.AiInpaintAvailable != true)
                {
                    issues.Add(new CapabilityValidationIssue
                    {
                        FieldName = "apply_seam_correction",
                        Code = AppErrorCode.SeamInpaintUnavailable,
                        Message = "Local seam inpainting is unavailable on the current backend.",
                    });
                }
            }
            if (assetType == "sprite" || assetType == "icon")
            {
                if (request.PixelsPerUnit <= 0)
                    Invalid("pixels_per_unit", "Pixels per unit must be greater than zero.", issues);
                if (request.PivotMode != "center" && request.PivotMode != "bottom_center" && request.PivotMode != "custom")
                    Invalid("pivot_mode", "Pivot mode must be center, bottom_center, or custom.", issues);
                if (request.PivotMode == "custom" &&
                    (request.CustomPivotX < 0f || request.CustomPivotX > 1f ||
                     request.CustomPivotY < 0f || request.CustomPivotY > 1f))
                    Invalid("custom_pivot", "Custom pivot coordinates must be between zero and one.", issues);
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

        static void Invalid(string fieldName, string message, List<CapabilityValidationIssue> issues)
        {
            issues.Add(new CapabilityValidationIssue
            {
                FieldName = fieldName,
                Code = FieldIssueCode.ValueInvalid,
                Message = message,
            });
        }
    }
}
