# Deployment guide

## Container build and persistent mounts

Build with `docker build -t unity-ai-assets .`. Mount separate durable locations for `/data/models` and `/data/generated`; configure `MODEL_STORAGE_DIRECTORY=/data/models` and `OUTPUT_DIRECTORY=/data/generated`. The output root contains generated files and JSON job/batch records, so both mounts must be included in backups. Do not rely on the writable container layer.

The image deliberately excludes models, secrets, generated assets, source history, and job history. Replacing a container preserves work only when the mounts are retained. Stop the service cleanly before an upgrade; queued and interrupted jobs are recovered on startup according to the normal retry policy.

## GPU

Install a host driver compatible with the selected CUDA-enabled Torch build. For NVIDIA containers, install NVIDIA Container Toolkit and run with `--gpus all`. The base Docker image does not select a CUDA Torch wheel because that choice must match the host/runtime. Build a derived image with your tested CUDA Torch installation.

`GET /ready` reports selected device, CUDA availability/version, VRAM when observable, precision, and required acceleration packages. `DEVICE=cuda` turns missing CUDA into a fatal readiness failure; `DEVICE=auto` explicitly reports its CPU fallback as a warning. `ENABLE_CPU_OFFLOAD=true` requires `accelerate`.

## Network, authentication, and quotas

For non-loopback production binds set:

```text
ENVIRONMENT=production
BIND_HOST=0.0.0.0
AUTHENTICATION_MODE=api_key
API_KEY=<long-random-secret>
```

Clients send `Authorization: Bearer <API_KEY>`. Terminate TLS at a reverse proxy, restrict network access, and do not put keys in command history or logs. `/health` and `/ready` stay unauthenticated for orchestration probes; restrict probe visibility at the network layer when operational details are sensitive.

`MAX_REQUESTS_PER_MINUTE` and `MAX_QUEUED_JOBS` are optional process-local controls. They return a structured `429` response. Use a shared, deployment-specific quota implementation before scaling to multiple backend replicas.

## Worker contract

The local worker implements `GenerationJobExecutor`. A hosted adapter implements `RemoteWorkerClient`: submit a stable request ID with parameters/metadata, get queued/running/completed/failed/cancelled status and progress, cancel, and return output metadata or a structured failure. Repeated submit IDs must be safe.

`WORKER_MODE=remote` with `REMOTE_WORKER_URL` uses the bundled HTTP adapter. Optional `REMOTE_WORKER_TOKEN` is sent as `Authorization: Bearer`. Example JSON:

```http
POST /jobs
{"request_id":"<uuid>","parameters":{...},"metadata":{"generation_type":"text_to_image","asset_type":"texture"}}

GET /jobs/{id}
{"job_id":"<id>","state":"completed","progress":{"stage":"completed","message":"..."},"result":{"generation_id":"...","status":"completed",...}}

POST /jobs/{id}/cancel
```

Do not add hosting-vendor SDKs to core generation code. A small HTTP worker that speaks this contract is enough to attach a future GPU host.

The image listens on `BIND_HOST=0.0.0.0` inside the container. Publish only loopback (`127.0.0.1:8000:8000`) unless authentication, TLS, and firewalling are configured. `docker-compose.yml` is a local example with persistent `./models` and `./generated` mounts.

## Operations

Use `/health` for liveness and `/ready` for readiness. Configure `LOG_LEVEL` for application logging; tokens are never logged by the built-in authenticator. Back up model metadata and generated output/job/batch roots together. For failures, inspect readiness first, then storage permissions, model validation status, and queue depth.
