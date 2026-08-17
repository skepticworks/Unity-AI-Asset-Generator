"""Minimal Diffusers-like trees for model-management tests."""

from __future__ import annotations

import json
from pathlib import Path


def write_fake_diffusers_model(
    root: Path,
    *,
    class_name: str = "StableDiffusionPipeline",
    components: tuple[str, ...] = (
        "unet",
        "vae",
        "text_encoder",
        "tokenizer",
        "scheduler",
    ),
    weight_bytes: bytes = b"fake-weights",
) -> Path:
    """Create a tiny directory that passes structural/hash validation."""
    root.mkdir(parents=True, exist_ok=True)
    index = {
        "_class_name": class_name,
        "_diffusers_version": "0.30.0",
    }
    for name in components:
        index[name] = ["diffusers", "FakeComponent"]
        component_dir = root / name
        component_dir.mkdir(parents=True, exist_ok=True)
        (component_dir / "config.json").write_text("{}", encoding="utf-8")
        (component_dir / "diffusion_pytorch_model.safetensors").write_bytes(weight_bytes)
    (root / "model_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return root
