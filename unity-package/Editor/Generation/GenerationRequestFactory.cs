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

            return new TextureGenerationRequestDto
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
                asset_type = resolved.AssetType
            };
        }
    }
}
