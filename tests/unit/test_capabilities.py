"""Unit tests for capability assembly and fake backend reporting."""

from __future__ import annotations

from unity_ai_assets.api.schemas.capabilities import CapabilitiesResponse
from unity_ai_assets.core.config import Settings
from unity_ai_assets.domain.generation_policy import GenerationPolicy
from unity_ai_assets.inference.fake_backend import FakeImageGenerationBackend
from unity_ai_assets.services.capability_service import CapabilityService


def test_capability_document_construction() -> None:
    settings = Settings(
        model_id="fake/model",
        model_family="sd15",
        model_display_name="Fake",
        device="cpu",
        torch_dtype="float32",
        app_version="0.3.0-test",
    )
    backend = FakeImageGenerationBackend(device_name="cpu", model_loaded=False)
    service = CapabilityService(settings, GenerationPolicy.from_settings(settings), backend)
    document = service.get_capabilities()
    assert document.model.id == "fake/model"
    assert document.model.family == "sd15"
    assert document.runtime.model_loaded is False
    assert document.runtime.configured_device == "cpu"
    assert document.runtime.resolved_device == "cpu"
    assert document.operations.text_to_image.supported is True
    assert document.operations.image_to_image.supported is True
    assert document.operations.image_to_image.denoising_strength.default == 0.75
    assert "png" in document.operations.image_to_image.source_image.supported_formats
    assert document.operations.inpainting.supported is True
    assert document.operations.inpainting.mask_image.convention == "white_inpaints"
    assert document.operations.inpainting.mask_image.white_means == "regenerate"
    assert document.operations.inpainting.mask_image.black_means == "keep"
    assert document.operations.inpainting.mask_image.alpha_ignored is True
    assert document.operations.inpainting.mask_image.must_match_source_dimensions is True
    assert document.operations.text_to_image.schedulers.selection_supported is False
    assert document.precision.user_selectable is False
    assert document.jobs.supported is True
    assert document.jobs.persistence == "local_filesystem"
    assert "queued" in document.jobs.states
    assert document.jobs.progress == "stage"
    assert document.batches.supported is True
    assert document.batches.maximum_jobs == 32
    assert "sequential" in document.batches.seed_modes
    assert backend.calls == []


def test_capability_serialization() -> None:
    settings = Settings(model_id="fake/model", device="cpu", torch_dtype="float32")
    backend = FakeImageGenerationBackend()
    service = CapabilityService(settings, GenerationPolicy.from_settings(settings), backend)
    response = CapabilitiesResponse.from_domain(service.get_capabilities())
    payload = response.model_dump()
    assert payload["operations"]["text_to_image"]["dimensions"]["width_multiple"] == 8
    i2i = payload["operations"]["image_to_image"]
    assert i2i["supported"] is True
    assert i2i["denoising_strength"]["default"] == 0.75
    assert i2i["source_image"]["maximum_byte_size"] == 10 * 1024 * 1024
    assert "png" in i2i["source_image"]["supported_formats"]
    inpaint = payload["operations"]["inpainting"]
    assert inpaint["supported"] is True
    assert inpaint["mask_image"]["convention"] == "white_inpaints"
    assert inpaint["mask_image"]["white_means"] == "regenerate"
    assert inpaint["mask_image"]["black_means"] == "keep"
    assert "png" in inpaint["mask_image"]["supported_formats"]
    jobs = payload["jobs"]
    assert jobs["supported"] is True
    assert jobs["persistence"] == "local_filesystem"
    assert jobs["progress"] == "stage"
    assert "queued" in jobs["states"]
    batches = payload["batches"]
    assert batches["supported"] is True
    assert batches["maximum_jobs"] == 32
    assert "fixed" in batches["seed_modes"]
    assert "diffusers" not in str(payload).lower()
    assert "C:\\" not in str(payload)
    assert "huggingface" not in str(payload).lower() or "model" in str(payload).lower()


def test_fake_backend_capabilities_deterministic() -> None:
    backend = FakeImageGenerationBackend(default_scheduler="pndm")
    caps = backend.describe_capabilities()
    assert caps.text_to_image_supported is True
    assert caps.default_scheduler == "pndm"
    assert caps.available_schedulers == []
