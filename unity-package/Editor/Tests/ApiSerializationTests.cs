using NUnit.Framework;
using UnityAiAssets.Editor.Api;

namespace UnityAiAssets.Editor.Tests
{
    public sealed class ApiSerializationTests
    {
        [Test]
        public void TextureGenerationRequest_SerializesOptionalSeedWhenPresent()
        {
            var dto = new TextureGenerationRequestDto
            {
                prompt = "wall",
                negative_prompt = "photo",
                width = 512,
                height = 256,
                steps = 20,
                guidance_scale = 7.5f,
                seed = 99,
                output_name = "rusted_wall"
            };

            var json = dto.ToJson();
            StringAssert.Contains("\"prompt\":\"wall\"", json);
            StringAssert.Contains("\"negative_prompt\":\"photo\"", json);
            StringAssert.Contains("\"width\":512", json);
            StringAssert.Contains("\"height\":256", json);
            StringAssert.Contains("\"steps\":20", json);
            StringAssert.Contains("\"guidance_scale\":7.5", json);
            StringAssert.Contains("\"seed\":99", json);
            StringAssert.Contains("\"output_name\":\"rusted_wall\"", json);
        }

        [Test]
        public void TextureGenerationRequest_OmitsSeedWhenNull()
        {
            var dto = new TextureGenerationRequestDto
            {
                prompt = "floor",
                seed = null,
                output_name = "floor"
            };

            var json = dto.ToJson();
            Assert.That(json.Contains("\"seed\""), Is.False);
        }

        [Test]
        public void TextureGenerationRequest_EscapesQuotesInPrompt()
        {
            var dto = new TextureGenerationRequestDto
            {
                prompt = "say \"hello\"",
                output_name = "tex"
            };

            var json = dto.ToJson();
            StringAssert.Contains("say \\\"hello\\\"", json);
        }

        [Test]
        public void TextureGenerationRequest_SerializesOptionalProfileProvenance()
        {
            var json = new TextureGenerationRequestDto
            {
                prompt = "wall", output_name = "wall",
                generation_profile_id = "profile", generation_profile_revision = 2,
                profile_origin = "user", prompt_template_id = "template",
                prompt_template_revision = 1, negative_prompt_profile_id = "negative",
                negative_prompt_profile_revision = 3, unity_import_profile_id = "import",
                asset_type = "texture"
            }.ToJson();
            StringAssert.Contains("\"generation_profile_id\":\"profile\"", json);
            StringAssert.Contains("\"generation_profile_revision\":2", json);
            StringAssert.Contains("\"asset_type\":\"texture\"", json);
        }

        [Test]
        public void HealthResponse_DeserializesApplicationVersionAndResolvedDevice()
        {
            const string json =
                "{\"status\":\"ok\",\"application_version\":\"0.3.0\",\"model_loaded\":false," +
                "\"resolved_device\":\"cuda\",\"request_id\":\"req-1\"}";
            var dto = UnityEngine.JsonUtility.FromJson<HealthResponseDto>(json);
            Assert.AreEqual("ok", dto.status);
            Assert.AreEqual("0.3.0", dto.application_version);
            Assert.IsFalse(dto.model_loaded);
            Assert.AreEqual("cuda", dto.resolved_device);
            Assert.AreEqual("cuda", dto.Device);
            Assert.AreEqual("req-1", dto.request_id);
        }

        [Test]
        public void GenerationResponse_DeserializesResourcesAndSchemaVersions()
        {
            const string json =
                "{\"generation_id\":\"11111111-1111-1111-1111-111111111111\"," +
                "\"status\":\"completed\",\"operation\":\"text_to_image\",\"asset_type\":\"texture\"," +
                "\"seed\":123,\"width\":64,\"height\":64,\"elapsed_seconds\":1.5," +
                "\"resources\":{" +
                "\"image\":\"/api/v1/generations/11111111-1111-1111-1111-111111111111/image\"," +
                "\"manifest\":\"/api/v1/generations/11111111-1111-1111-1111-111111111111/manifest\"}," +
                "\"schema_versions\":{\"generation_manifest\":\"1.0\"}}";
            var dto = UnityEngine.JsonUtility.FromJson<TextureGenerationResponseDto>(json);
            Assert.AreEqual("11111111-1111-1111-1111-111111111111", dto.generation_id);
            Assert.AreEqual("text_to_image", dto.operation);
            Assert.AreEqual("texture", dto.asset_type);
            Assert.AreEqual(123, dto.seed);
            Assert.IsNotNull(dto.resources);
            StringAssert.Contains("/image", dto.resources.image);
            StringAssert.Contains("/manifest", dto.resources.manifest);
            Assert.IsNotNull(dto.schema_versions);
            Assert.AreEqual("1.0", dto.schema_versions.generation_manifest);
        }

        [Test]
        public void GenerationResponse_StillDeserializesDeprecatedFieldsWhenPresent()
        {
            const string json =
                "{\"generation_id\":\"abc\",\"status\":\"completed\"," +
                "\"seed\":1,\"width\":8,\"height\":8,\"elapsed_seconds\":0.1," +
                "\"resources\":{\"image\":\"/x/image\",\"manifest\":\"/x/manifest\"}," +
                "\"image_path\":\"generated/x/a.png\",\"metadata_path\":\"generated/x/a.json\"," +
                "\"image_url\":\"/api/v1/generations/abc/image\"," +
                "\"metadata_url\":\"/api/v1/generations/abc/metadata\"}";
            var dto = UnityEngine.JsonUtility.FromJson<TextureGenerationResponseDto>(json);
            StringAssert.Contains("/image", dto.image_url);
            StringAssert.Contains("/metadata", dto.metadata_url);
        }

        [Test]
        public void ApiEndpoints_AreStable()
        {
            Assert.AreEqual("/health", ApiEndpoints.Health);
            Assert.AreEqual("/api/v1/capabilities", ApiEndpoints.Capabilities);
            Assert.AreEqual("/api/v1/generations/textures", ApiEndpoints.GenerateTexture);
            Assert.AreEqual(
                "/api/v1/generations/abc/image",
                ApiEndpoints.GenerationImage("abc"));
            Assert.AreEqual(
                "/api/v1/generations/abc/manifest",
                ApiEndpoints.GenerationManifest("abc"));
            Assert.AreEqual(
                "/api/v1/generations/abc/metadata",
                ApiEndpoints.GenerationMetadata("abc"));
        }

        [Test]
        public void TextureGenerationRequest_SerializesImg2ImgFields()
        {
            var dto = new TextureGenerationRequestDto
            {
                prompt = "variation",
                output_name = "var",
                operation = "image_to_image",
                denoising_strength = 0.4f,
                source_image = new SourceImagePayloadDto
                {
                    content_base64 = "QUJD",
                    media_type = "image/png"
                }
            };

            var json = dto.ToJson();
            StringAssert.Contains("\"operation\":\"image_to_image\"", json);
            StringAssert.Contains("\"denoising_strength\":0.4", json);
            StringAssert.Contains("\"source_image\":{", json);
            StringAssert.Contains("\"content_base64\":\"QUJD\"", json);
            StringAssert.Contains("\"media_type\":\"image/png\"", json);
        }

        [Test]
        public void TextureGenerationRequest_OmitsImg2ImgFieldsForTxt2Img()
        {
            var json = new TextureGenerationRequestDto
            {
                prompt = "wall",
                output_name = "wall"
            }.ToJson();
            Assert.That(json.Contains("\"operation\""), Is.False);
            Assert.That(json.Contains("\"source_image\""), Is.False);
            Assert.That(json.Contains("\"denoising_strength\""), Is.False);
            Assert.That(json.Contains("\"mask_image\""), Is.False);
        }

        [Test]
        public void TextureGenerationRequest_SerializesInpaintingFields()
        {
            var dto = new TextureGenerationRequestDto
            {
                prompt = "inpaint",
                output_name = "patch",
                operation = "inpainting",
                denoising_strength = 0.5f,
                source_image = new SourceImagePayloadDto
                {
                    content_base64 = "QUJD",
                    media_type = "image/png"
                },
                mask_image = new SourceImagePayloadDto
                {
                    content_base64 = "TUFTSw==",
                    media_type = "image/png"
                }
            };

            var json = dto.ToJson();
            StringAssert.Contains("\"operation\":\"inpainting\"", json);
            StringAssert.Contains("\"mask_image\":{", json);
            StringAssert.Contains("\"content_base64\":\"TUFTSw==\"", json);
        }
    }
}
