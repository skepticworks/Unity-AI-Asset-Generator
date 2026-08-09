# Unity AI Asset Generator

Local, AI-assisted generation of Unity-ready **2D game assets** using pretrained generative models (Hugging Face Diffusers) plus an **editor-only Unity package**. No ComfyUI.

## Current milestone scope (Milestone 5)

1. Versioned capability reporting (`GET /api/v1/capabilities`) including processing support
2. Authoritative generation policy (single source of truth for limits)
3. Stable machine-readable API error envelope + request IDs
4. Versioned generation manifests with SHA-256 / byte-size integrity and processing provenance
5. Unity capability cache, compatibility checks, and preflight validation
6. Unity download integrity verification before import
7. Texture, sprite, and icon generation through one shared text-to-image pipeline
8. Explicit transparency strategies with optional local background removal + alpha cleanup
9. Single-sprite Unity import with pixels-per-unit, pivot modes, and atlas-hint metadata
10. Versioned built-in/user generation profiles with migration and profile provenance

Automated Python tests use a **fake inference backend** and a **fake background remover**.
They do **not** download diffusion or rembg weights.

## Explicit non-goals (this milestone)

- ComfyUI, ComfyUI APIs, workflows, or custom nodes
- Sprite sheets, animation frame extraction, automatic SpriteAtlas creation, Addressables
- img2img, ControlNet, IP-Adapter, inpainting, masking, batching, tile seam correction
- Database, Redis, Celery, Docker, auth, cloud storage
- Model installation UI, distributed job system
- Per-request precision or scheduler selection

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

Then set `BACKGROUND_REMOVAL_ENABLED=true` in `.env`. The rembg session loads lazily on first use and is reused across requests. Diffusion backends do not emit native alpha; transparency is post-processed.

### Background-removal model / license

- Backend: [rembg](https://github.com/danielgatis/rembg)
- Default model: `u2net` (U^2-Net family weights distributed by rembg)
- License: Apache-2.0 for rembg; review upstream model license notes before commercial shipping
- Config: `BACKGROUND_REMOVAL_BACKEND=rembg`, `BACKGROUND_REMOVAL_MODEL=u2net`

### PyTorch / CUDA note

For NVIDIA CUDA on Windows:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu124
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

## Hugging Face authentication

Default model: [`runwayml/stable-diffusion-v1-5`](https://huggingface.co/runwayml/stable-diffusion-v1-5) (CreativeML Open RAIL-M). Set `HF_TOKEN` if needed. **Outputs are not automatically safe for commercial use.**

## Model and policy configuration

See [`.env.example`](.env.example) for model, device, dtype, generation limits, and background-removal settings.

## Starting the API

```powershell
uvicorn unity_ai_assets.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Bind defaults to **loopback**. Use a **single worker**.

## Versioning policy

| Concern | Source | Notes |
|---------|--------|-------|
| Application semver | `pyproject.toml` / `core.version` | Currently `0.5.0` |
| API major/minor | `core.version` | Independent of app semver |
| Capabilities schema | `1.1` | Processing block is additive |
| Generation manifest schema | `1.2` | Processing provenance is additive |
| Generation profile schema | `1.1` | Sprite/icon defaults are additive |

## Capability discovery

```http
GET /api/v1/capabilities
```

Reports text-to-image asset types (`texture`, `sprite`, `icon`), transparency strategies,
background-removal availability (not native model alpha), alpha-cleanup ranges, and
sprite-import/pivot support.

## Sprite and icon workflow

1. Select a sprite/icon profile (`ps1_character_sprite`, `ps1_item_icon`, `ps1_weapon_icon`)
2. Generate through the existing `POST /api/v1/generations/textures` endpoint
3. When `transparency_strategy=background_removal`, the backend removes the background locally,
   then applies deterministic alpha cleanup
4. Unity imports the **final processed PNG** as `TextureType.Sprite` / `SpriteImportMode.Single`
5. Configure pixels per unit and pivot (`center`, `bottom_center`, `custom`)
6. Optional `atlas_hint` is stored as metadata only (no automatic atlas creation)

Icons reuse the sprite pipeline with icon-specific profile defaults (center pivot, compact prompts).

## Texture workflow

Unchanged. Textures use `transparency_strategy=none` and existing import profiles.

## Generation

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/generations/textures `
  -H "Content-Type: application/json" `
  -d "{\"prompt\":\"ps1 hero\",\"width\":512,\"height\":512,\"asset_type\":\"sprite\",\"transparency_strategy\":\"background_removal\",\"pixels_per_unit\":100,\"pivot_mode\":\"bottom_center\",\"atlas_hint\":\"characters\",\"output_name\":\"hero\"}"
```

## Artifact retrieval

```http
GET /api/v1/generations/{generation_id}/image
GET /api/v1/generations/{generation_id}/manifest
```

The image endpoint returns the **final** processed PNG. When original RGB is preserved, the
manifest lists both `image` and `original_image` outputs with relative paths only.

## Stable errors

Additional processing codes: `TRANSPARENCY_STRATEGY_UNSUPPORTED`,
`BACKGROUND_REMOVAL_UNAVAILABLE`, `BACKGROUND_REMOVAL_FAILED`, `ALPHA_PROCESSING_FAILED`,
`PIVOT_INVALID`, `PIXELS_PER_UNIT_INVALID`.

## Unity package

Package path: [`unity-package/`](unity-package/) (version `0.5.0`)

### Install from disk

1. Unity **2022.3 LTS+** project
2. Package Manager → **+** → **Add package from disk…** → select `unity-package/package.json`

### Generate from the editor

1. Start the Python API (enable background removal for sprite/icon profiles that require it)
2. **Tools → AI Asset Generator**
3. **Refresh Capabilities**
4. Select sprite/icon asset type and profile
5. Adjust transparency, alpha cleanup, PPU, pivot, and atlas hint as needed
6. **Generate And Import**

Generation is disabled when a profile requires background removal that capabilities report as unavailable.

## Running Python tests

```powershell
pytest
ruff check src tests scripts
ruff format --check src tests scripts
mypy src
python scripts/validate_profiles.py
python scripts/validate_contract_fixtures.py
```

## Unity Edit Mode tests

After installing the package: **Window → General → Test Runner → EditMode** → run `UnityAiAssets.Editor.Tests`.

Batchmode (when Unity is installed):

```powershell
Unity.exe -batchmode -projectPath <UnityProject> -runTests -testPlatform EditMode -logFile -
```

## Known limitations

- Single concurrent generation (in-process lock; one Uvicorn worker)
- Scheduler / precision not selectable per request
- Diffusion does **not** natively generate transparency; sprites/icons rely on post-processing
- Background removal is optional and disabled by default until configured
- Single-sprite import only (no sheets / atlas baking)
- Atlas hints are metadata only
- UI asset type remains catalogued but is not a Milestone 5 generation target

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md).
