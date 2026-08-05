# Unity AI Asset Generator

Local, AI-assisted generation of Unity-ready **2D game assets** using pretrained generative models (Hugging Face Diffusers). No ComfyUI.

## Current milestone scope

This repository currently implements a **text-to-image texture generation** vertical slice:

1. Send a prompt to a local FastAPI endpoint
2. Validate parameters
3. Generate one image with a Diffusers-compatible model
4. Save a PNG plus JSON reproducibility metadata
5. Return generation ID, paths, seed, dimensions, and elapsed time

Automated tests use a **fake inference backend** and do **not** download models.

## Explicit non-goals (this milestone)

- ComfyUI, ComfyUI APIs, workflows, or custom nodes
- Unity Editor package / import pipeline
- Sprites, icons, UI chrome, img2img, or variation workflows
- Database, Redis, Celery, Docker, auth, cloud storage
- JavaScript frontend
- Multi-GPU scheduling or distributed queues

## System requirements

- **Python 3.11** (3.12 may work; project targets `>=3.11,<3.13`)
- Windows, Linux, or macOS
- Optional **NVIDIA GPU** with a CUDA-capable PyTorch build (recommended). CPU works but is slow.
- Disk space for model weights (Stable Diffusion 1.5 is on the order of several GB)

This machine profile used during development: RTX 3050 Laptop (4 GB VRAM). Prefer 512×512 and consider `ENABLE_CPU_OFFLOAD=true` if you hit OOM.

## Environment setup

```powershell
cd C:\Users\tyler\UnityAssetGenerator
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Copy environment defaults:

```powershell
Copy-Item .env.example .env
```

Edit `.env` as needed. **Do not commit `.env`.**

## Dependency installation

Install the project (API + ML stack) and dev tools:

```powershell
pip install -e ".[dev]"
```

### PyTorch / CUDA note

`pip` may install a CPU-only torch wheel depending on your platform index. For NVIDIA CUDA acceleration on Windows, install a matching wheel from [pytorch.org](https://pytorch.org/get-started/locally/) **after** or **instead of** the default torch from this project, for example:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

Verify:

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

## Hugging Face authentication

`runwayml/stable-diffusion-v1-5` is commonly downloadable without a token, but Hugging Face may rate-limit anonymous downloads. If required:

1. Create a token at https://huggingface.co/settings/tokens
2. Set `HF_TOKEN` in your environment or `.env` (supported by `huggingface_hub`)
3. Accept any model license terms on the model card page if prompted

Never commit tokens.

## Model configuration

Configuration is read from environment variables (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `MODEL_ID` | Hugging Face Diffusers model id |
| `MODEL_REVISION` | Optional git revision / commit |
| `MODEL_VARIANT` | Optional weight variant (e.g. `fp16`) |
| `DEVICE` | `auto`, `cuda`, `mps`, or `cpu` |
| `TORCH_DTYPE` | `auto`, `float16`, `bfloat16`, or `float32` |
| `OUTPUT_DIRECTORY` | Where PNG/JSON are written |
| `MAX_WIDTH` / `MAX_HEIGHT` | Hard caps (must be divisible by 8) |
| `ENABLE_CPU_OFFLOAD` | Lower VRAM usage on CUDA |
| `LOCAL_FILES_ONLY` | Refuse network downloads |

### Default model choice

**Default:** [`runwayml/stable-diffusion-v1-5`](https://huggingface.co/runwayml/stable-diffusion-v1-5)

- Suitable for local text-to-image prototyping
- Compatible with Diffusers `StableDiffusionPipeline`
- Aligns with API defaults (guidance scale ~7, multi-step sampling)
- License: **CreativeML Open RAIL-M** — review the [license](https://huggingface.co/spaces/CompVis/stable-diffusion-license) before any commercial use

**This project does not claim that model outputs are automatically safe for commercial use.** You are responsible for license compliance, content review, and game-platform requirements.

Change `MODEL_ID` without modifying source code.

## Starting the API

```powershell
uvicorn unity_ai_assets.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Or:

```powershell
python -m unity_ai_assets.main
```

**Use a single worker.** Generation is serialized with an in-process lock; multiple workers would each load their own model copy and bypass that lock.

## Example API request

Health:

```http
GET http://127.0.0.1:8000/health
```

Generate a texture:

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/generations/textures `
  -H "Content-Type: application/json" `
  -d '{
    "prompt": "low-resolution rusted industrial wall texture, PS1 game aesthetic",
    "negative_prompt": "text, logo, watermark, photorealistic scene",
    "width": 512,
    "height": 512,
    "steps": 25,
    "guidance_scale": 7.0,
    "seed": 12345,
    "output_name": "rusted_wall"
  }'
```

Example response fields: `generation_id`, `status`, `image_path`, `metadata_path`, `seed`, `width`, `height`, `elapsed_seconds`.

Outputs land under `generated/<generation-id>/` as `<output_name>.png` and `<output_name>.json`.

## Running tests

Tests use the fake backend — **no GPU, no downloads, no Hugging Face network calls**:

```powershell
pytest
```

Lint and type-check:

```powershell
ruff check src tests scripts
ruff format --check src tests scripts
mypy src
```

## Running the real-model smoke test

Only when you intentionally want to load weights:

```powershell
python scripts/smoke_test.py
```

Optional flags: `--prompt`, `--width`, `--height`, `--steps`, `--seed`, `--output-name`.

## GPU and VRAM considerations

- On CUDA, `TORCH_DTYPE=auto` selects **float16**
- On CPU, auto uses **float32** (float16 on CPU is rejected)
- 4 GB VRAM: start at 512×512; lower steps; try `ENABLE_CPU_OFFLOAD=true`
- First request loads the model (slow); later requests reuse the pipeline
- Dimensions must be divisible by 8; invalid sizes are **rejected**, not silently resized

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| `model_load_failed` | Check `MODEL_ID`, disk space, `HF_TOKEN`, network, or set `LOCAL_FILES_ONLY=false` |
| CUDA OOM | Reduce width/height/steps; enable CPU offload; close other GPU apps |
| `DEVICE=cuda` but no GPU | Install CUDA torch build or set `DEVICE=cpu` |
| Slow first request | Expected — weights load lazily on first generation |
| Path / permission errors | Ensure `OUTPUT_DIRECTORY` is writable |
| Validation 422 | Confirm dimensions ÷ 8 and within `MAX_*` |

## Next planned milestones

1. Unity import helpers / package for generated textures
2. Sprite and icon presets (transparent backgrounds, atlas hints)
3. Reference-image / img2img variations
4. Tileable texture constraints and seamless post-process
5. Batch generation UI (still local; still no ComfyUI)

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for component boundaries, dependency direction, and the inference abstraction.
