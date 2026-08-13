# Unity AI Asset Generator

Local, AI-assisted generation of Unity-ready **2D game assets** using pretrained generative models (Hugging Face Diffusers) plus an **editor-only Unity package**. No ComfyUI.

## Current milestone scope (Milestone 7)

1. Versioned capability reporting (`GET /api/v1/capabilities`) including processing, tileable, and **image-to-image**
2. Authoritative generation policy (single source of truth for limits, including denoising strength and source-image uploads)
3. Stable machine-readable API error envelope + request IDs
4. Versioned generation manifests with integrity hashes, processing provenance, and img2img source-image metadata
5. Unity capability cache, compatibility checks, and preflight validation
6. Unity download integrity verification before import
7. Texture, sprite, icon, tileable texture, and **img2img variation** generation through one shared pipeline
8. Explicit transparency strategies with optional local background removal + alpha cleanup
9. Tileable workflow: offset inspect, seam diagnostics, modular correction, tile preview, optional palette reduction
10. Single-sprite Unity import with pixels-per-unit, pivot modes, and atlas-hint metadata
11. Versioned built-in/user generation profiles with migration and profile provenance
12. Image-to-image: source/init image upload, validation, denoising strength, capability gating (no silent txt2img fallback)

Automated Python tests use a **fake inference backend** (and fake background remover when needed).
They do **not** download diffusion or rembg weights.

## Explicit non-goals (this milestone)

- ComfyUI, ComfyUI APIs, workflows, or custom nodes
- Sprite sheets, animation frame extraction, automatic SpriteAtlas creation, Addressables
- ControlNet, IP-Adapter / reference-image conditioning, inpainting (except local tileable seam repair), masking, batching
- Guaranteed perfectly seamless textures (correction is best-effort diagnostics + soft blending)
- Database, Redis, Celery, Docker, auth, cloud storage
- Model installation UI, distributed job system
- Full material editor / per-request precision or scheduler selection

## System requirements

- **Python 3.11** (project targets `>=3.11,<3.13`)
- **Unity 2022.3 LTS** or newer (package `unity: 2022.3`)
- Windows, Linux, or macOS
- Optional **NVIDIA GPU** with a CUDA-capable PyTorch build (recommended)
- Disk space for model weights (Stable Diffusion 1.5 is several GB)
- Optional rembg/ONNX Runtime for local background removal (sprites/icons)

## Environment setup

```powershell
cd C:\Users\tyler\UnityAssetGenerator
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
Copy-Item .env.example .env
```

## Dependency installation

```powershell
pip install -e ".[dev]"
```

Optional local background removal (sprites/icons):

```powershell
pip install -e ".[background-removal]"
```

Keep `BACKGROUND_REMOVAL_ENABLED=true` in `.env` (the example default). Capabilities report `background_removal.available` and an `unavailable_reason` when rembg is missing or disabled. Diffusion models do not emit native alpha — transparency is local rembg post-processing with alpha preserved in PNG + Unity sprite import.

## Starting the API

```powershell
uvicorn unity_ai_assets.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Bind defaults to **loopback**. Use a **single worker**.

`GET /` returns a small service-identity JSON (health/capabilities/docs links). IDE and browser tooling often probe localhost ports with Chrome DevTools discovery (`GET /json/version`); those probes are not part of this API and are filtered from uvicorn access logs so they do not look like application failures.

On low-VRAM GPUs, keep `ENABLE_CPU_OFFLOAD=false` and `EXCLUSIVE_MODEL_VRAM=true` (defaults): txt2img and seam-inpaint pipelines are not kept in VRAM together. The inactive pipeline is unloaded between stages. CPU offload is an alternative that pages modules continuously and is often slower per step.

## Versioning policy

| Concern | Source | Notes |
|---------|--------|-------|
| Application semver | `pyproject.toml` / `core.version` | Currently `0.7.0` |
| API major/minor | `core.version` | Independent of app semver; currently `1.1` |
| Capabilities schema | `1.3` | Img2img operation block is additive |
| Generation manifest schema | `1.4` | Img2img source-image metadata is additive |
| Generation profile schema | `1.2` | Tileable defaults are additive |

## Tileable texture workflow

1. Select the `ps1_tileable_texture` profile (seamless prompt/negative guidance)
2. Optionally enable **Apply AI Seam Repair** (requires 512×512 and local inpaint model)
3. Generate and import with Repeat wrap import settings — Status reports whether repair was requested and applied
4. In the Unity window: **Load Imported Texture for Tileable Tools**
5. Compare **Original** vs **Offset (50%)** previews (wrapped, no empty borders)
6. Review compact seam diagnostics (horizontal / vertical / combined scores)
7. Inspect the **3×3 Tile** preview and Unity repeat/material tiling swatch
8. Optionally **Apply Palette Reduction** (editor-side sibling asset; original preserved)
9. Export/import uses Repeat wrap — suitable for tiling materials

AI seam repair runs on the backend during generate only (circular offset + center-cross local Diffusers inpaint). Soft-blend is not a success path. Seam scores are objective diagnostics, not perceptual guarantees.

## Sprite and icon workflow

Transparency via local background removal, single-sprite import, pivots, atlas hints. Choose strategy `none` for opaque sprites when rembg is unavailable.

## Image-to-image variations

Img2img uses a **source image as the generation init/latent image** and modifies it according to
**denoising strength** (0 keeps the source, 1 allows maximum change; default `0.75`). This is **not**
reference-image conditioning (IP-Adapter / style / identity). Those workflows would use a separate
request field later and must not be mixed with `source_image`.

1. Confirm capabilities: `operations.image_to_image.supported` must be `true` (SD 1.5 / SDXL families).
   Requests against an unsupported model fail with `OPERATION_UNSUPPORTED` and are **not** converted to text-to-image.
2. Upload a PNG, JPEG, or WebP as `source_image.content_base64` (optional `media_type`).
3. Source images are validated for format, file size (`MAX_SOURCE_IMAGE_BYTES`, default 10 MiB),
   dimensions (same min/max/multiple policy as generation), and corrupt payloads.
4. Set `operation` to `image_to_image` and optionally `denoising_strength` in `0.0…1.0`.

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/generations/textures `
  -H "Content-Type: application/json" `
  -d "{\"prompt\":\"weathered rusted metal variation\",\"width\":512,\"height\":512,\"operation\":\"image_to_image\",\"denoising_strength\":0.45,\"source_image\":{\"content_base64\":\"<base64-png>\",\"media_type\":\"image/png\"},\"output_name\":\"metal_var\"}"
```

The generation response `operation` is `image_to_image`. The manifest echoes `denoising_strength` and
source-image metadata (format, media type, original dimensions, byte size, SHA-256) without storing the
uploaded pixels. The same source bytes, prompt, model, seed, denoising strength, and generation
parameters produce the same output.

In Unity: **Tools → AI Asset Generator → Image-to-Image Variation**. Select a project texture or load a
file, preview it, set denoising strength, then **Generate And Import**. Status and the metadata asset
record that the result was produced with img2img.

## Generation

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/generations/textures `
  -H "Content-Type: application/json" `
  -d "{\"prompt\":\"seamless rusted metal plate\",\"width\":512,\"height\":512,\"asset_type\":\"texture\",\"tileable\":true,\"apply_seam_correction\":false,\"palette_reduction_enabled\":false,\"output_name\":\"metal_tile\"}"
```

## Artifact retrieval

```http
GET /api/v1/generations/{generation_id}/image
GET /api/v1/generations/{generation_id}/manifest
```

When original pixels are preserved (transparency or tileable correction/palette), the manifest lists both `image` and `original_image` outputs.

## License

MIT. Model weights and generated outputs are subject to their own licenses.
