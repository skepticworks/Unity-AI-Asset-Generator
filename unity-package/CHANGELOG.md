# Changelog

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
