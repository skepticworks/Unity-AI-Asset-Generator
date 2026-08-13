# Architecture

## Overview

Local FastAPI texture generation (Diffusers behind an inference protocol) plus an **editor-only Unity package** that discovers backend capabilities, downloads artifacts by generation ID, verifies integrity, and imports them into `Assets/`.

**ComfyUI is not used** in any form.

Application/package version: **0.7.0** (Milestone 7 — image-to-image variations).

## Backend component responsibilities

| Layer | Responsibility |
|-------|----------------|
| `api/routes` | HTTP transport: health, capabilities, generation, image/manifest retrieval |
| `api/schemas` | Versioned public Pydantic models (capabilities, generation, errors) |
| `domain/generation_policy.py` | **Authoritative** generation limits and validation |
| `domain/capabilities.py` | Capability domain models including processing support |
| `domain/generation_manifest.py` | Manifest domain model + legacy metadata compatibility |
| `domain/generation.py` | Generation request/result dataclasses |
| `services/capability_service.py` | Assemble capability document from policy + inference + processing |
| `services/generation_service.py` | Policy validation, seed, lock, orchestration, post-processing |
| `services/output_service.py` | Atomic PNG + manifest persistence, SHA-256, resolve-by-UUID |
| `processing/*` | Background removal, alpha cleanup, tileable wrap/seam/palette (isolated from diffusion backends) |
| `inference/*` | Backend protocol (`describe_capabilities` + `generate`), Diffusers, fake, model manager |
| `core/version.py` | Central API / schema / application version constants |
| `core/error_codes.py` | Stable application + field issue codes |
| `core/exception_handlers.py` | Translate AppError / Pydantic errors into the public envelope |
| `core/middleware.py` | `X-Request-ID` validation, generation, propagation |
| `core/config.py` | Settings including policy and background-removal env vars |

## Unity package components

| Area | Responsibility |
|------|----------------|
| `Editor/Api/` | Typed client, DTOs, SimpleJson, error envelope, endpoints |
| `Editor/Versioning/` | `SchemaVersion`, `ClientCompatibility` |
| `Editor/Capabilities/` | Cache, compatibility checker, preflight validator, state |
| `Editor/Integrity/` | PNG byte-size + SHA-256 verification |
| `Editor/Configuration/` | Project Settings |
| `Editor/Generation/` | Request model/factory, state, `GenerationController` orchestration |
| `Editor/Importing/` | Path utilities, import profiles, `GeneratedAssetImporter`, materials |
| `Editor/Metadata/` | Manifest-aware ScriptableObject + importer |
| `Editor/UI/` | `Tools > AI Asset Generator` window |
| `Editor/Tileable/` | Offset/wrap, seam analysis/correction, palette reduction, tileable previews |
| `Editor/Tests/` | Edit Mode tests (capabilities, errors, manifests, integrity, tileable) |
| `Editor/AssetTypes/` | Asset type contracts |
| `Editor/Prompting/` | Prompt/negative contracts and deterministic resolution |
| `Editor/Profiles/` | `ProfileCatalog`, generation registry/schema, compatibility, persistence, migration |

## Milestone 4 profile loading and persistence

```mermaid
flowchart LR
  Builtin[Package Builtin JSON] --> Catalog[ProfileCatalog]
  Builtin --> Registry[GenerationProfileRegistry]
  Catalog --> Registry
  User[ProjectSettings user JSON] --> Registry
  Registry -->|one bad file| Errors[LoadErrors]
  Manager[Profile Manager] --> Repo[UserProfileRepository]
  Repo -->|atomic temp + replace| User
  Repo -->|conflict| Quarantine[Quarantine]
```

Built-in profiles are immutable. Duplicating assigns a new UUID, revision 1, `builtin=false`,
and `Copy of …`; renaming changes only `display_name`, preserving `<id>.json`.

## Profile resolution and compatibility

```mermaid
sequenceDiagram
  participant UI as Generator Window
  participant Cat as ProfileCatalog
  participant Reg as GenerationProfileRegistry
  participant Res as Profile Resolver
  participant Caps as Backend Capabilities
  UI->>Cat: asset type defaults
  UI->>Reg: generation profile id
  UI->>Res: subject + explicit overrides
  Res->>Cat: template + negative + import refs
  Res->>Caps: check effective asset type/settings
  alt unsupported asset type or limits
    Res-->>UI: incompatible reasons (no clamp)
  else compatible
    Res-->>UI: constructed prompts + effective settings + provenance
  end
```

## Generation with profile provenance

```mermaid
flowchart LR
  Subject[Subject and overrides] --> Resolve[Resolve profile]
  Resolve --> Validate[Capability preflight]
  Validate --> DTO[Snake-case request + provenance]
  DTO --> API[Texture generation API]
  API --> Manifest[Manifest 1.1 profile block]
  Manifest --> Metadata[Unity metadata asset]
```

## Migration and built-in versus user flow

```mermaid
flowchart TD
  File[Profile JSON] --> Version{Schema version}
  Version -->|1.x| Parse[Validate and load]
  Version -->|0.9| Migrate[profile_version to revision<br/>seed_strategy=random]
  Migrate --> Backup[Write .bak]
  Backup --> Atomic[Persist 1.0 atomically]
  Builtin[Built-in selected] --> Duplicate[Duplicate to UUID user profile]
  User[User profile selected] --> Edit[Edit and save]
  Duplicate --> Edit
```

## Dependency direction

```mermaid
flowchart TB
  UI[Editor UI]
  Ctrl[GenerationController]
  Caps[Capability Cache / Validator]
  ApiClient[Typed API Client]
  Import[GeneratedAssetImporter / Integrity / Materials]
  Meta[Metadata]
  Settings[Project Settings]
  FastAPI[FastAPI routes]
  CapSvc[Capability Service]
  GenSvc[Generation Service]
  Policy[Generation Policy]
  Out[Output / Manifest Service]
  Inference[ImageGenerationBackend]

  UI --> Ctrl
  UI --> Settings
  Ctrl --> Caps
  Ctrl --> ApiClient
  Ctrl --> Import
  Ctrl --> Meta
  Caps --> ApiClient
  ApiClient --> FastAPI
  FastAPI --> CapSvc
  FastAPI --> GenSvc
  CapSvc --> Policy
  CapSvc --> Inference
  GenSvc --> Policy
  GenSvc --> Inference
  GenSvc --> Out
```

Unity never imports Diffusers types. Public schemas never expose Python class paths or absolute backend filesystem paths as the primary contract.

## Unity capability discovery

```mermaid
sequenceDiagram
    participant Win as EditorWindow
    participant Ctrl as GenerationController
    participant Cache as CapabilityCache
    participant Client as ApiClient
    participant API as GET /capabilities

    Win->>Ctrl: RefreshCapabilities
    Ctrl->>Cache: SetLoading(baseUrl)
    Ctrl->>Client: GetCapabilitiesAsync
    Client->>API: GET /api/v1/capabilities
    Note over API: No model weight load
    API-->>Client: CapabilityDocument
    Client-->>Ctrl: typed document
    Ctrl->>Cache: SetReady / Incompatible
    Ctrl-->>Win: Progress (version, model, device, precision)
```

## Generation preflight and authoritative validation

```mermaid
sequenceDiagram
    participant UI as Editor UI
    participant Val as CapabilityValidator
    participant API as POST /textures
    participant Pol as GenerationPolicy
    participant Inf as InferenceBackend

    UI->>Val: Validate(request, capabilities)
    alt preflight fails
        Val-->>UI: issues (no coercion)
    else preflight passes
        UI->>API: submit request
        API->>Pol: authoritative validate
        alt policy rejects
            Pol-->>API: GENERATION_REQUEST_INVALID
            API-->>UI: stable error envelope
        else ok
            API->>Inf: generate
            Inf-->>API: image
            API-->>UI: resources + seed
        end
    end
```

## Error translation and request ID propagation

```mermaid
flowchart LR
  Req[Incoming request] --> MW[RequestIdMiddleware]
  MW -->|valid X-Request-ID| Keep[Preserve]
  MW -->|invalid/missing| Mint[Generate UUID]
  Keep --> Handler
  Mint --> Handler[Route / Service]
  Handler -->|AppError / ValidationError| EH[Exception handlers]
  EH --> Env[Error envelope + request_id]
  EH --> Log[Structured logs with request_id]
  Handler --> Resp[Response + X-Request-ID header]
```

## Generation manifest creation and retrieval

```mermaid
sequenceDiagram
    participant Gen as GenerationService
    participant Out as OutputService
    participant FS as Generation directory
    participant API as GET /manifest

    Gen->>Out: persist(request, image)
    Out->>FS: write PNG atomically
    Out->>Out: sha256 + byte_size
    Out->>FS: write manifest.json atomically
    Note over Out: Relative paths only
    API->>Out: load_manifest(id)
    alt versioned manifest
        Out-->>API: GenerationManifest
    else legacy flat JSON
        Out->>Out: compatibility parse
        Out-->>API: GenerationManifest
    else unknown schema major
        Out-->>API: MANIFEST_SCHEMA_UNSUPPORTED
    end
```

## Unity image download and integrity verification

```mermaid
sequenceDiagram
    participant Ctrl as GenerationController
    participant Client as ApiClient
    participant Ver as ImageIntegrityVerifier
    participant Imp as GeneratedAssetImporter

    Ctrl->>Client: GET resources.image
    Client-->>Ctrl: PNG bytes
    Ctrl->>Client: GET resources.manifest
    Client-->>Ctrl: GenerationManifest
    Ctrl->>Ver: Verify(bytes, sha256, byte_size)
    alt mismatch
        Ver-->>Ctrl: Integrity error (no Assets write)
    else match
        Ctrl->>Imp: ImportPng
        Imp-->>Ctrl: Assets path + metadata asset
    end
```

## Schema-version responsibilities

| Schema | Owner | Writer | Reader compatibility |
|--------|-------|--------|----------------------|
| Capabilities `1.x` | Backend `CapabilityService` | Capability endpoint | Unity major-match; ignore unknown optional fields |
| Generation manifest `1.x` | Backend `OutputService` | New generations only | Unity major-match; legacy flat metadata converted on read |
| API `1.x` | Backend routes under `/api/v1` | All versioned endpoints | Unity supports API major `1` |

## Trust boundaries

- Backend binds to loopback by default
- Generation IDs are UUIDs only; no arbitrary path reads
- Capability endpoint is read-only and does not mutate model state
- Errors never include stack traces, tokens, cache paths, or absolute output paths as the primary contract
- Request IDs are sanitized against header injection

## Extending capabilities for future operations

1. Implement the operation in an inference backend
2. Report it via `describe_capabilities()` (accurate `supported` flags only)
3. Extend `OperationsCapabilities` / public schema with a new typed block
4. Keep unsupported operations as `{ "supported": false }`
5. Add policy constraints if the operation introduces new parameters
6. Bump capability schema **minor** for additive fields; **major** for breaking changes
7. Update fixtures, Unity models, validators, and docs together

## Milestone 5 sprite/icon processing flow

```mermaid
flowchart LR
  Resolve[Profile resolution] --> Caps[Capability validation]
  Caps --> Gen[Text-to-image RGB]
  Gen --> Strat{transparency_strategy}
  Strat -->|none| Persist[Persist PNG + manifest]
  Strat -->|background_removal| BR[ImageBackgroundRemover]
  BR --> Alpha[Deterministic alpha cleanup]
  Alpha --> Persist
  Persist --> Import[Unity single-sprite import]
```

Diffusion models produce RGB. Transparent backgrounds are an explicit post-processing
strategy (`background_removal` via rembg/U2-Net), not native model alpha. Background
removal is optional, lazily loaded, reused across requests, and isolated behind
`ImageBackgroundRemover` so it never enters the diffusion backend protocol.

## Milestone 7 image-to-image variations

Img2img is a first-class generation **operation** (`image_to_image`), not a form of
reference-image conditioning. The uploaded `source_image` is the diffusion **init/latent
image**. Denoising strength controls how far the result may move from that init image.

Reference conditioning (IP-Adapter and similar) is intentionally absent. A future
`reference_image` / conditioning payload can be added beside `source_image` without
reusing img2img fields, labels, or pipeline entry points.

```mermaid
flowchart LR
  Caps[Capabilities image_to_image.supported]
  Src[Source image bytes]
  Val[Format / size / dimension / decode validation]
  Init[Resize to output size LANCZOS]
  Inf[Img2img pipeline from txt2img components]
  Man[Manifest operation + source metadata]

  Caps -->|unsupported| Fail[OPERATION_UNSUPPORTED no txt2img fallback]
  Caps -->|supported| Src --> Val --> Init --> Inf --> Man
```

- API: extend `POST /api/v1/generations/textures` with `operation`, nested `source_image`
  (`content_base64`, optional `media_type`), and `denoising_strength`.
- Capabilities schema **1.3** advertises img2img ranges, supported source formats, and max
  upload size. SD 1.5 and SDXL families report `supported: true`; others report false.
- Manifest schema **1.4** records denoising strength and source-image metadata (not pixels).
- Diffusers converts the loaded txt2img pipeline with `AutoPipelineForImage2Image.from_pipe`
  so weights are shared. The fake backend blends the source with a seed color for tests.
- Unity: source picker + preview, denoising slider, preflight against capabilities, metadata
  `Operation = image_to_image`.

Milestone 5 retains the common path through `GenerationController`: resolve a generation
profile, construct a wire DTO, validate capabilities, submit, download by `generation_id`,
verify, and record metadata. Asset-specific behavior begins after verification for Unity
import (sprite PPU/pivot/alpha settings). Icons reuse the sprite pipeline via profiles.
