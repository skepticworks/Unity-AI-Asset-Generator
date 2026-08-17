# Changelog

## 0.12.0 — Milestone 12 packaging and hosted-worker preparation

- Optional API-key authentication for network-accessible backends. The key is stored in
  EditorPrefs, not the project settings asset. Local loopback use can leave it empty.
- Backend packaging, readiness checks, process-local quotas, durable volume layout, and a
  provider-neutral remote worker contract. See the repository README and `docs/deployment.md`.

## 0.11.0 — Milestone 11 model management

- Added a Models foldout for installed Diffusers models: validation state, license/source
  provenance, compatibility, cached disk usage, activate, revalidate, and delete.
- Delete asks for an editor confirmation dialog before calling the backend. The backend
  still refuses paths outside managed storage.
- Offline mode is toggled from the same panel. Remote installs are reported as unavailable
  offline rather than as generic failures. Local validated models remain listed and usable.
- Capabilities schema 1.7 advertises `model_management` (counts, offline, storage health)
  without walking the filesystem on every capability refresh. API minor 1.5.

## 0.10.0 — Milestone 10 batch generation UI

- Dedicated **Tools → AI Asset Generator → Batch Generation** window configures prompts, seed
  mode (fixed / random / sequential), and variation count, then expands them into ordinary
  Milestone 9 jobs.
- Backend persists batch records and `batch_id` on jobs. Unity reconstructs queue state after
  the window closes or the backend restarts. Progress is finished/completed job counts plus
  coarse pipeline stages — not invented percentages.
- Partial success, batch cancel, retry-failed, and import-all / import-selected reuse existing
  job cancel/retry semantics and Unity import profiles. Already-imported generation IDs are
  skipped on refresh.
- Capabilities schema 1.6 advertises `batches` (max jobs/prompts/variations, seed modes).
  API minor 1.4.

## 0.9.0 — Milestone 9 local job system

- Generation is submitted as a persistent local job. Unity receives a job ID, polls status/progress,
  then downloads and imports the completed result instead of holding the original HTTP request open.
- History panel lists recent jobs with mode, prompt summary, timestamps, seed, and result status.
  Completed jobs can be re-imported; failed/interrupted/cancelled jobs can be retried; queued/running
  jobs can be cancelled.
- Cancel asks the backend to drop queued work or stop a running job at the next safe pipeline point.
- Capabilities schema 1.5 advertises the job system (`jobs.supported`, persistence, states, retry
  limits) without exposing the execution backend.

## 0.8.0 — Milestone 8 masks and inpainting

- Masked inpainting is a distinct operation (`inpainting`), not a mode of img2img or
  reference-image conditioning. White mask pixels regenerate; black pixels are kept.
- Generator window: source + mask pickers, source/mask/overlay previews, brush editor,
  clear/reset mask, capability gating, and Status/metadata showing `inpainting`.
- Request DTO sends `operation`, `source_image`, `mask_image`, and `denoising_strength` when
  inpainting is enabled. Preflight fails clearly when the backend does not support it.
- Manifest 1.5 records mask convention plus source/mask metadata (format, dimensions, byte
  size, SHA-256) on `GenerationMetadataAsset`.

## 0.7.0 — Milestone 7 image-to-image variations

- Image-to-image uses a source **init/latent image** plus denoising strength. This is not
  reference-image conditioning (IP-Adapter); those fields/labels are kept separate.
- Generator window: source image ObjectField / load-from-disk, preview, denoising-strength
  slider with help text, capability gating, and Status/metadata showing `image_to_image`.
- Request DTO sends `operation`, `source_image.content_base64`, and `denoising_strength`
  only when img2img is enabled. Preflight fails clearly when the backend does not support it.
- Manifest 1.4 source-image metadata (format, dimensions, byte size, SHA-256) is stored on
  `GenerationMetadataAsset` without uploading pixels into the project as the source of truth.

## 0.6.1 — UI, seam-repair wiring, transparency clarity

- Generator window: foldout sections, word-wrapped prompts, tooltips, responsive previews,
  and explicit post-generate processing status (seam repair / background removal).
- Tileable inspect: always-available Texture2D picker, Project Selection / last-import shortcuts,
  optional compare texture (single + 3×3), auto-load after generate.
- Fixed `GenerationController` dropping tileable/seam-repair overrides so AI seam repair
  actually runs when enabled on generate; manifest fields expose applied/implementation.
- Transparent backgrounds: default `BACKGROUND_REMOVAL_ENABLED=true`, capabilities expose
  `unavailable_reason`, UI enables strategy only for sprite/icon with clear rembg guidance.
- Backend: `GET /` service identity; CDP probe paths filtered from access logs.

## 0.6.0 — Milestone 6 tileable texture workflow

- Added `ps1_tileable_texture` generation/import profiles with seamless prompt guidance and
  Repeat wrap-mode Unity import defaults.
- Added offset (50%) preview, seam analysis diagnostics, modular soft-edge seam correction,
  3×3 tile preview, optional palette reduction, and Unity repeat/material tiling preview.
- Seam correction preserves the original asset (sibling `.corrected` / `.palette` outputs).
- Extended generation profile schema 1.2, capabilities schema 1.2, and manifest schema 1.3
  with tileable processing settings and provenance.

## 0.5.0 — Milestone 5 sprite and icon workflow

- Added sprite/icon generation through the shared text-to-image pipeline with explicit
  transparency strategies (`none`, `background_removal`). Transparency is produced by
  local post-processing (rembg), not native diffusion alpha.
- Added deterministic alpha cleanup, pixels-per-unit, center/bottom-center/custom pivots,
  atlas-hint metadata, and single-sprite Unity import settings.
- Extended capabilities schema 1.1 and generation manifest schema 1.2 with processing
  provenance. Added PS1 weapon-icon profile alongside character sprite and item icon.

## 0.4.1 — Milestone 4.5 architecture consolidation

- Consolidated built-in asset types, prompt templates, negative prompts, and Unity import
  profiles behind `ProfileCatalog`
- Renamed orchestration and import boundaries to `GenerationController` and
  `GeneratedAssetImporter`
- Centralized resolved request DTO construction, profile file loading, profile contracts,
  capability limit checks, and API HTTP helpers without changing public wire contracts
- Retained legacy metadata retrieval only as a compatibility fallback

## 0.4.0 — Milestone 4

- Profile-driven generation with built-in asset type, prompt template, negative prompt,
  generation, and Unity import profile catalogs
- User profiles stored outside `Assets/` under
  `ProjectSettings/AIAssetGenerator/Profiles`, with atomic save, revision tracking,
  duplicate/import/export, migration, and conflict quarantine
- Subject-based deterministic prompt construction and ordered exact negative-term deduplication
- Backend capability checks per asset type; sprite, icon, and UI profiles remain disabled unless
  the backend advertises those asset types
- Generation request and manifest 1.1 profile provenance support, persisted in metadata assets
- Profile manager/editor windows and expanded Edit Mode profile tests

## 0.3.0 — Milestone 3

- Versioned capability discovery: `GET /api/v1/capabilities`, cached per backend URL for the
  editor session (`CapabilityCache`), with explicit `Unknown` / `Loading` / `Ready` / `Stale` /
  `Unavailable` / `Incompatible` states
- `CapabilityCompatibilityChecker` and `SchemaVersion` (numeric `major[.minor]` parsing/compare;
  higher minors accepted, higher majors rejected) — this package supports API major `1`,
  capabilities schema major `1`, and manifest schema major `1`
- `GenerationCapabilityValidator` preflight-checks a request against fetched capabilities
  (dimensions, steps, guidance scale, seed, prompt/negative-prompt/output-name length) and never
  silently coerces invalid values
- Versioned generation manifest support: `GET /api/v1/generations/{id}/manifest` (preferring the
  `resources.manifest` link from the generation response), with the deprecated `/metadata` alias
  kept as a fallback for older backends
- `ImageIntegrityVerifier`: downloaded PNGs are checked against the manifest's SHA256 + byte size
  before anything is written into `Assets/`; mismatches are rejected
- Minimal embedded JSON parser (`Editor/Api/SimpleJson.cs`) for capability/error/manifest payloads
  that Unity's `JsonUtility` cannot deserialize reliably (nested string arrays, dynamic field maps)
- Stable error envelope parsing (`ErrorEnvelope`, `AppErrorCode`, `FieldIssueCode`) surfaced on
  `ApiException` as `RequestId`, `AppErrorCode`, and `FieldIssues`
- `X-Request-ID` is captured from backend responses and shown in the editor window for support/debugging
- Editor window: capability status panel, **Refresh Capabilities** button, backend-enforced
  min/max/multiple hints on generation fields, and **Generate And Import** is disabled with a
  clear reason when capabilities are missing or incompatible
- `GenerationMetadataAsset` gained manifest-derived fields (schema version, operation, asset
  type, status, completed-at, application name/version, API major, model family, device,
  precision, scheduler, output SHA256/byte size, request ID) alongside the existing legacy fields
- Edit Mode tests for schema version parsing/compare, capability deserialization/compatibility/
  caching, capability preflight validation, error envelope deserialization, manifest
  deserialization, and image integrity verification

## 0.2.0 — Milestone 2

- Editor window: Tools > AI Asset Generator
- Project settings: Edit > Project Settings > AI Asset Generator
- Typed HTTP client for local FastAPI health, texture generation, and artifact download
- Texture import profiles (PS1 Pixel, Standard Environment)
- Optional material creation
- Generation metadata ScriptableObject assets
- Edit Mode tests for paths, profiles, and API serialization

## 0.1.0

- Package scaffold reserved for initial backend milestone (no Unity UI yet)
