# Unity AI Asset Generator

Local-first backend and Unity editor package for generating Unity-ready 2D textures, sprites, icons, image-to-image variations, and masked inpainting with locally managed Diffusers models.

## Capabilities

- Managed local Diffusers model installation, validation, activation, and safe deletion
- Persistent JSON job queue, batch generation, cancellation, retry, and artifact manifests
- Local GPU or CPU inference, optional background removal, and tileable seam repair
- Offline operation with locally installed models
- Optional API-key protection, operational readiness checks, and local quota controls

## Architecture

The Unity editor package calls the FastAPI backend. The backend validates requests, persists jobs to the configured job directory, and executes them through `GenerationJobExecutor`. Local GPU execution is the default implementation. `WORKER_MODE=remote` uses a provider-neutral HTTP worker contract; no hosting vendor is coupled to core generation code.

## Requirements

- Python 3.11 (supported range: `>=3.11,<3.13`)
- Unity 2022.3 LTS or newer for the editor package
- A Diffusers-compatible model; NVIDIA CUDA is recommended but optional
- Docker is optional. GPU containers require a host NVIDIA driver and NVIDIA Container Toolkit.

## Quick start

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
Copy-Item .env.example .env
unity-ai-assets
```

The default bind address is `127.0.0.1:8000`. Install development tools separately:

```powershell
pip install -e ".[dev]"
```

For optional local sprite/icon background removal:

```powershell
pip install -e ".[background-removal]"
```

## Backend and Unity setup

Start with `unity-ai-assets` (or `uvicorn unity_ai_assets.main:app --host 127.0.0.1 --port 8000 --workers 1`). Keep one worker: the durable queue and quota limiter are process-local. Add `unity-package/` to a Unity project through Package Manager, then configure its backend URL as `http://127.0.0.1:8000`. If the backend uses `AUTHENTICATION_MODE=api_key`, set the same secret in **Edit → Project Settings → AI Asset Generator → Backend API Key** (stored in EditorPrefs, not the project asset).

Install models through **Tools → AI Asset Generator → Models**, or use `POST /api/v1/models/install`. Managed models live in `MODEL_STORAGE_DIRECTORY` (`models/` by default), are staged and hash-validated before registration, and can be used with `OFFLINE_MODE=true`.

## Configuration

Copy `.env.example`; it documents all settings. Important production settings:

| Setting | Default | Purpose |
| --- | --- | --- |
| `BIND_HOST` / `BIND_PORT` | `127.0.0.1` / `8000` | Server listener |
| `ENVIRONMENT` | `local` | `production` requires auth on a network bind |
| `AUTHENTICATION_MODE` / `API_KEY` | `disabled` | Use `api_key` plus a random secret for remote exposure |
| `MODEL_STORAGE_DIRECTORY` | `models` | Durable managed-model root |
| `OUTPUT_DIRECTORY` | `generated` | Durable generated artifact root |
| `JOB_DIRECTORY` / `BATCH_DIRECTORY` | under output root | Durable JSON records |
| `DEVICE` / `TORCH_DTYPE` | `auto` / `auto` | Explicit accelerator selection |
| `WORKER_MODE` / `REMOTE_WORKER_URL` | `local` / unset | `remote` requires a worker base URL |
| `MAX_REQUESTS_PER_MINUTE` / `MAX_QUEUED_JOBS` | `0` / `0` | Disabled local-process admission limits |
| `OFFLINE_MODE` | `false` | Blocks network model installation |

Never commit `.env`, API keys, model weights, or generated assets.

## Persistent storage

Mount or back up model and output roots. `generated/` contains artifacts plus `jobs/` and `batches/` by default. Job records use atomic replacement writes. The application image/container filesystem is not durable storage. Uploaded source and mask pixels are validated and used for a request; the manifest keeps their metadata and digest, not their image bytes.

## Docker

```powershell
docker compose up --build
```

Or:

```powershell
docker build -t unity-ai-assets .
docker run --rm -p 127.0.0.1:8000:8000 `
  -e BIND_HOST=0.0.0.0 `
  -e MODEL_STORAGE_DIRECTORY=/data/models `
  -e OUTPUT_DIRECTORY=/data/generated `
  -v "${PWD}\models:/data/models" `
  -v "${PWD}\generated:/data/generated" `
  unity-ai-assets
```

For GPU use, install a CUDA-enabled PyTorch build compatible with the selected base image and run with the NVIDIA runtime (for example `--gpus all`). See `docs/deployment.md`.

## Health and diagnostics

- `GET /health` is a lightweight liveness endpoint and never loads model weights.
- `GET /ready` checks durable paths, queue acceptance, selected device, Torch/CUDA, VRAM when observable, precision, and acceleration dependencies. It returns `503` if a fatal configuration/runtime issue exists.
- `GET /api/v1/capabilities` reports generation/model features.

Set `DEVICE=cuda` to make lack of CUDA a fatal, visible configuration error. With `DEVICE=auto`, unavailable acceleration is a warning and CPU selection is explicit in readiness output.

## Authentication and quotas

Local loopback deployments use disabled authentication by default. For a network-accessible production bind, set `ENVIRONMENT=production`, `AUTHENTICATION_MODE=api_key`, and a high-entropy `API_KEY`. Protected `/api/*` requests use `Authorization: Bearer <API_KEY>` and invalid credentials return `401`; secrets are compared in constant time and never logged.

Rate and queue limits return structured `429 QUOTA_EXCEEDED` responses. They deliberately apply only within one backend process and are not a distributed quota solution.

## API and workflows

Use `POST /api/v1/jobs` for asynchronous generation, then poll `GET /api/v1/jobs/{id}`; jobs support result retrieval, cancellation, and retry. `POST /api/v1/generations/textures` remains a synchronous compatibility wrapper. Batches use the same queue through `/api/v1/batches`. Artifacts are available under `/api/v1/generations/{id}/image` and `/manifest`.

Supported operations are text-to-image, image-to-image (an init image, not reference conditioning), and masked inpainting (white regenerates; black is preserved). Texture, sprite, and icon import settings are captured in the manifest.

## Remote workers

`RemoteWorkerClient` and `RemoteGenerationExecutor` define a provider-neutral contract: idempotent request ID and parameters, status/progress, completed output metadata, structured failures, and cancellation. Local execution remains the default. `WORKER_MODE=remote` plus `REMOTE_WORKER_URL` uses the bundled HTTP JSON adapter documented in `docs/deployment.md`. Hosting-vendor SDKs stay out of the core.

## Troubleshooting

- Readiness says CUDA unavailable: install a CUDA-enabled Torch build matching the host driver, or set `DEVICE=cpu`.
- Readiness says CPU offload is fatal: install the `accelerate` dependency.
- Model load fails offline: install and validate the model locally, set its managed ID active, and use `OFFLINE_MODE=true`.
- Queue is full: wait for work to finish or raise `MAX_QUEUED_JOBS`.

## Development

```powershell
pip install -e ".[dev]"
pytest
ruff check src tests scripts
ruff format --check src tests scripts
mypy src
```

Repository highlights: `src/unity_ai_assets/` backend, `unity-package/` editor package, `fixtures/` contract fixtures, `tests/` automated coverage, and `docs/` operational documentation.

## Security and offline operation

Treat this service as local-only until authentication, TLS termination, firewalling, storage permissions, and quota policy are configured. API keys are a minimal shared-secret mechanism; replace the authenticator for stronger identity requirements. Offline mode prevents network-dependent model operations but does not prevent local model inference.

## License

MIT. Model weights and generated outputs are subject to their respective licenses.
