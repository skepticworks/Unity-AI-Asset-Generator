# Unity AI Asset Generator

Local, AI-assisted generation of Unity-ready **2D game assets** using pretrained generative models (Hugging Face Diffusers) plus an **editor-only Unity package**. No ComfyUI.

## Current milestone scope (Milestone 4.5 consolidation complete; product scope through Milestone 4)

1. Versioned capability reporting (`GET /api/v1/capabilities`)
2. Authoritative generation policy (single source of truth for limits)
3. Stable machine-readable API error envelope + request IDs
4. Versioned generation manifests with SHA-256 / byte-size integrity
5. Unity capability cache, compatibility checks, and preflight validation
6. Unity download integrity verification before import
7. Existing texture generation + Unity import workflows preserved
8. Versioned built-in and user generation profiles, deterministic prompt resolution, migration,
   compatibility checks, and profile provenance in manifest schema 1.1
9. Architecture consolidation: `ProfileCatalog`, `GenerationController`, `GeneratedAssetImporter`,
   shared capability-limit checks, and unified request construction

Automated Python tests use a **fake inference backend** and do **not** download models.

## Explicit non-goals (this milestone)

- ComfyUI, ComfyUI APIs, workflows, or custom nodes
- Sprite/icon/UI **generation pipelines** (catalog profiles exist but remain capability-gated)
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

### PyTorch / CUDA note

For NVIDIA CUDA on Windows:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu124
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

## Hugging Face authentication

Default model: [`runwayml/stable-diffusion-v1-5`](https://huggingface.co/runwayml/stable-diffusion-v1-5) (CreativeML Open RAIL-M). Set `HF_TOKEN` if needed. **Outputs are not automatically safe for commercial use.**

## Model and policy configuration

See [`.env.example`](.env.example) for `MODEL_ID`, `MODEL_FAMILY`, `DEVICE`, `TORCH_DTYPE`, dimension/step/guidance/seed/prompt limits, and concurrency. Generation limits are validated at startup and drive both capability reporting and authoritative request validation.

## Starting the API

```powershell
uvicorn unity_ai_assets.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Bind defaults to **loopback**. Use a **single worker**.

## Versioning policy

| Concern | Source | Notes |
|---------|--------|-------|
| Application semver | `pyproject.toml` / `core.version` | Currently `0.4.1` |
| API major/minor | `core.version` (`API_MAJOR_VERSION`, `API_MINOR_VERSION`) | Independent of app semver |
| Capabilities schema | `capabilities_schema_version: "1.0"` | Independent of app semver |
| Generation manifest schema | `generation_manifest_schema_version: "1.1"` | Profile provenance is additive |

Do not infer schema compatibility from the application version. Unity accepts higher **minor** schema/API versions when the **major** matches the supported set (API major `1`, capability schema major `1`, manifest schema major `1`).

## Capability discovery

```http
GET /api/v1/capabilities
```

Returns a typed document describing:

- API / application / schema versions
- Configured vs resolved device and precision
- Model identity (`id`, `revision`, `family`, `display_name`) without loading weights
- Supported operations (`text_to_image` only today)
- Dimension, step, guidance, seed, prompt, negative-prompt, output-name limits
- Scheduler behavior (`selection_supported: false`, default public id `pndm`)
- Precision availability and `user_selectable: false`
- Concurrency limits

Canonical example: [`fixtures/contracts/capabilities.json`](fixtures/contracts/capabilities.json).

Capability requests **must not** load model weights.

## Generation

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/generations/textures `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: optional-client-id" `
  -d "{\"prompt\":\"rusted wall texture, PS1\",\"width\":512,\"height\":512,\"seed\":12345,\"output_name\":\"rusted_wall\"}"
```

Successful responses expose **resource links** (prefer these over deprecated filesystem path fields):

```json
{
  "generation_id": "...",
  "status": "completed",
  "operation": "text_to_image",
  "asset_type": "texture",
  "resources": {
    "image": "/api/v1/generations/{id}/image",
    "manifest": "/api/v1/generations/{id}/manifest"
  },
  "schema_versions": { "generation_manifest": "1.0" }
}
```

Deprecated fields `image_path`, `metadata_path`, `image_url`, and `metadata_url` may still appear for local debugging / older clients. New Unity code uses `resources` only. Planned removal after Milestone 4.

Invalid requests are **rejected** (not silently clamped/rounded/truncated) with a stable error envelope.

## Artifact retrieval

```http
GET /api/v1/generations/{generation_id}/image
GET /api/v1/generations/{generation_id}/manifest
GET /api/v1/generations/{generation_id}/metadata   # deprecated alias → manifest
```

IDs must be UUIDs. Path traversal and arbitrary filesystem reads are rejected.

### Generation manifest

New generations write `manifest.json` (schema `generation-manifest` / `1.0`) including prompt parameters, resolved runtime, relative output paths, SHA-256, and byte size. Absolute filesystem paths are never stored in the manifest.

Legacy flat metadata from Milestone 1–2 remains **readable** via the manifest endpoint (converted in memory). Files are not rewritten in place. Unknown versioned schemas return `MANIFEST_SCHEMA_UNSUPPORTED`.

Legacy fields that cannot be reconstructed (documented defaults applied):

- `model.family` → `unknown`
- `runtime.scheduler` → `unknown`
- output `sha256` / `byte_size` → empty / `0` when absent

## Stable errors and request IDs

Public `/api/v1` errors use:

```json
{
  "error": {
    "code": "GENERATION_REQUEST_INVALID",
    "message": "…",
    "request_id": "…",
    "details": { "fields": { "width": [{ "code": "VALUE_NOT_MULTIPLE", "…": "…" }] } }
  }
}
```

Send optional `X-Request-ID` (letters, digits, `._-`, max 64). Invalid incoming IDs are replaced. Every response includes `X-Request-ID`.

Application codes include: `REQUEST_BODY_INVALID`, `GENERATION_REQUEST_INVALID`, `OPERATION_UNSUPPORTED`, `ASSET_TYPE_UNSUPPORTED`, `SCHEDULER_UNSUPPORTED`, `MODEL_UNAVAILABLE`, `MODEL_LOADING_FAILED`, `INFERENCE_FAILED`, `OUTPUT_PERSISTENCE_FAILED`, `GENERATION_NOT_FOUND`, `MANIFEST_NOT_FOUND`, `CAPABILITY_SCHEMA_UNSUPPORTED`, `MANIFEST_SCHEMA_UNSUPPORTED`, `INTERNAL_SERVER_ERROR`.

## Health

`GET /health` remains lightweight (`status`, `application_version`, `model_loaded`, `resolved_device`, `request_id`). Use `/api/v1/capabilities` for feature discovery.

## Unity package

Package path: [`unity-package/`](unity-package/) (version `0.4.1`)

### Install from disk

1. Unity **2022.3 LTS+** project
2. Package Manager → **+** → **Add package from disk…** → select `unity-package/package.json`

### Configure

**Edit → Project Settings → AI Asset Generator**

Default backend URL: `http://127.0.0.1:8000`

### Generate from the editor

1. Start the Python API
2. **Tools → AI Asset Generator**
3. **Refresh Capabilities** (required before generate)
4. Select asset type/profile, enter a subject, review prompts → **Generate And Import**

User generation profiles live in `ProjectSettings/AIAssetGenerator/Profiles`, outside `Assets/`.
Built-ins are immutable. Sprite/icon/UI profiles are present but generation is capability-gated;
the current backend normally advertises only `texture`.

Unity:

- Caches capabilities per backend URL for the editor session
- Validates API / capability-schema majors
- Prefights requests against backend limits (does not silently coerce)
- Downloads the versioned manifest and verifies PNG byte size + SHA-256 before import
- Still treats the backend as authoritative

Details: [`unity-package/README.md`](unity-package/README.md) and [`unity-package/Documentation~/getting-started.md`](unity-package/Documentation~/getting-started.md).

### Cancellation note

**Cancel Wait** only stops Unity waiting/importing. Backend GPU work may continue.

## Running Python tests

```powershell
pytest
ruff check src tests scripts
ruff format --check src tests scripts
mypy src
python scripts/validate_contract_fixtures.py
```

## Contract fixtures

Canonical JSON under [`fixtures/contracts/`](fixtures/contracts/) is validated against backend Pydantic schemas and Unity field expectations:

- `capabilities.json`
- `generation_response.json`
- `api_error.json`
- `generation_manifest.json`

## Real-model smoke test

```powershell
python scripts/smoke_test.py
```

## Unity Edit Mode tests

After installing the package: **Window → General → Test Runner → EditMode** → run `UnityAiAssets.Editor.Tests`.

## GPU and VRAM

- CUDA `TORCH_DTYPE=auto` → float16
- 4 GB VRAM: start at 512×512; try `ENABLE_CPU_OFFLOAD=true`
- First request loads the model (slow)
- **Unity Editor also uses GPU VRAM.** On 4 GB cards, Unity + SD 1.5 can stall with Diffusers stuck at `0%`. Before generating: use a lightweight scene, close extra Game/Scene views, or set `ENABLE_CPU_OFFLOAD=true` / temporarily `DEVICE=cpu` in `.env`

## Known limitations

- Single concurrent generation (in-process lock; one Uvicorn worker)
- Scheduler / precision not selectable per request
- Only `text_to_image` + `texture` are supported
- Deprecated generation response path fields remain temporarily
- `/metadata` is a deprecated alias for `/manifest`

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md).
