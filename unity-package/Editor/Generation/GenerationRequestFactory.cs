using System;
using UnityAiAssets.Editor.Api;
using UnityAiAssets.Editor.Profiles;

namespace UnityAiAssets.Editor.Generation
{
    public static class GenerationRequestFactory
    {
        public static TextureGenerationRequestDto FromResolved(
            ResolvedGenerationSettings resolved,
            TextureGenerationRequestModel request)
        {
            if (resolved == null) throw new ArgumentNullException(nameof(resolved));
            if (request == null) throw new ArgumentNullException(nameof(request));

            var isSpriteOrIcon = string.Equals(resolved.AssetType, "sprite", StringComparison.OrdinalIgnoreCase)
                                 || string.Equals(resolved.AssetType, "icon", StringComparison.OrdinalIgnoreCase);

            var dto = new TextureGenerationRequestDto
            {
                prompt = (resolved.ConstructedPrompt ?? string.Empty).Trim(),
                negative_prompt = resolved.ConstructedNegativePrompt ?? string.Empty,
                width = resolved.Width,
                height = resolved.Height,
                steps = resolved.Steps,
                guidance_scale = resolved.GuidanceScale,
                seed = resolved.Seed,
                output_name = (resolved.OutputName ?? request.OutputName ?? string.Empty).Trim(),
                generation_profile_id = resolved.GenerationProfileId,
                generation_profile_revision = resolved.GenerationProfileRevision,
                profile_origin = resolved.ProfileOrigin,
                prompt_template_id = resolved.PromptTemplateId,
                prompt_template_revision = resolved.PromptTemplateRevision,
                negative_prompt_profile_id = resolved.NegativePromptProfileId,
                negative_prompt_profile_revision = resolved.NegativePromptProfileRevision,
                unity_import_profile_id = resolved.ImportProfileId,
                asset_type = resolved.AssetType,
                transparency_strategy = resolved.TransparencyStrategy,
                alpha_threshold = isSpriteOrIcon ? (int?)resolved.AlphaThreshold : null,
                alpha_feather = isSpriteOrIcon ? (int?)resolved.AlphaFeather : null,
                remove_near_transparent = isSpriteOrIcon ? (bool?)resolved.RemoveNearTransparent : null,
                zero_rgb_when_transparent = isSpriteOrIcon ? (bool?)resolved.ZeroRgbWhenTransparent : null,
                // Backend rejects sprite import fields on texture requests.
                pixels_per_unit = isSpriteOrIcon ? (float?)resolved.PixelsPerUnit : null,
                pivot_mode = isSpriteOrIcon ? resolved.PivotMode : null,
                custom_pivot_x = isSpriteOrIcon ? (float?)resolved.CustomPivotX : null,
                custom_pivot_y = isSpriteOrIcon ? (float?)resolved.CustomPivotY : null,
                atlas_hint = isSpriteOrIcon ? resolved.AtlasHint : null,
                tileable = resolved.Tileable,
                apply_seam_correction = resolved.ApplySeamCorrection,
                seam_blend_width = resolved.SeamBlendWidth,
                palette_reduction_enabled = resolved.PaletteReductionEnabled,
                palette_color_count = resolved.PaletteColorCount
            };

            if (request.UseInpainting)
            {
                dto.operation = "inpainting";
                dto.denoising_strength = request.DenoisingStrength;
                if (!SourceImageCodec.TryEncodePng(request.SourceTexture, out var sourcePng, out var sourceError))
                    throw new InvalidOperationException(sourceError);
                dto.source_image = new SourceImagePayloadDto
                {
                    content_base64 = Convert.ToBase64String(sourcePng),
                    media_type = "image/png"
                };
                if (!SourceImageCodec.TryEncodePng(request.MaskTexture, out var maskPng, out var maskError))
                    throw new InvalidOperationException(maskError);
                dto.mask_image = new SourceImagePayloadDto
                {
                    content_base64 = Convert.ToBase64String(maskPng),
                    media_type = "image/png"
                };
            }
            else if (request.UseImageToImage)
            {
                dto.operation = "image_to_image";
                dto.denoising_strength = request.DenoisingStrength;
                if (!SourceImageCodec.TryEncodePng(request.SourceTexture, out var png, out var encodeError))
                    throw new InvalidOperationException(encodeError);
                dto.source_image = new SourceImagePayloadDto
                {
                    content_base64 = Convert.ToBase64String(png),
                    media_type = "image/png"
                };
            }

            return dto;
        }
    }
}
