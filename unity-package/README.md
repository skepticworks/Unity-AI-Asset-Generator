# Unity AI Asset Generator (Editor Package)

**Minimum Unity version:** **2022.3 LTS**

Editor-only package that talks to the local FastAPI backend, downloads generated PNGs by generation ID, imports them with deterministic `TextureImporter` profiles, optionally creates a material, and stores generation metadata in the project.

## Milestone 4 profiles

Generation starts with an asset type, generation profile, and subject. Unity resolves the
profile's prompt template and negative prompt, applies explicit overrides, checks the effective
settings against live backend capabilities, then submits constructed prompts with provenance.
Built-ins are read from `Editor/Profiles/Builtin`; user profiles are atomically stored under
`ProjectSettings/AIAssetGenerator/Profiles` and never under `Assets/`.

Use **Tools → AI Asset Generator → Profiles** to create, duplicate, edit, import, export,
validate, and reveal profiles. Built-ins are immutable and must be duplicated before editing.
Sprite and icon profiles support explicit transparency strategies (local background-removal
post-processing, not native diffusion alpha), alpha cleanup, PPU, and center, bottom-center,
or custom pivots. Generation is disabled unless the backend advertises the selected asset type;
background-removal requires rembg availability in capabilities (see `unavailable_reason` when not).
Switch strategy to `none` for opaque sprites when rembg is unavailable.

Tileable texture profiles (`ps1_tileable_texture`) use seamless prompt guidance and Repeat wrap
import settings. **Apply AI Seam Repair** on generate sends `apply_seam_correction` to the backend
(local Diffusers inpaint at 512×512). Status reports whether repair was requested and applied.
After import, the generator window supports offset seam inspection, diagnostics, 3×3 tile preview,
optional editor-side palette reduction, and a Unity repeat/material tiling swatch.

## Install from disk

1. Open your Unity project (2022.3 LTS or newer recommended).
2. **Window → Package Manager → + → Add package from disk…**
3. Select `unity-package/package.json` from this repository.

Or add to `Packages/manifest.json`:

```json
"com.skepticworks.unity-ai-assets": "file:../../UnityAssetGenerator/unity-package"
```

(Adjust the relative path for your machine.)

## Start the Python backend

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn unity_ai_assets.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Default URL: `http://127.0.0.1:8000`

## Configure backend URL

**Edit → Project Settings → AI Asset Generator**

- Backend Base URL (default `http://127.0.0.1:8000`)
- API timeout
- Default texture / material folders (`Assets/…` only)
- Default import profile
- Material creation defaults and shader name

Do **not** store Hugging Face tokens here.

## Open the editor window

**Tools → AI Asset Generator**

## Generate and import a texture

1. Click **Refresh Capabilities** (also happens automatically before the first generate).
2. Click **Check Backend Connection**.
3. Select an asset type/profile and enter a subject. Fields show backend-enforced min/max/multiple hints once
   capabilities are loaded.
4. Choose destination folder and import profile (**PS1 Pixel** or **Standard Environment**).
5. Optionally enable **Create Material** and set shader / material folder.
6. Click **Generate And Import** (disabled with an explanation if capabilities are missing or
   incompatible).
7. When complete, use **Select Imported Texture** or inspect the status panel.

## Image-to-image variations

Open **Image-to-Image Variation** in the generator window. Enable img2img, assign a project
`Texture2D` or **Load From Disk…** (PNG/JPEG/WebP), preview the source, and set **Denoising
Strength** (0 keeps the source almost unchanged; 1 allows maximum change). The source is the
**init/latent image**, not a style/identity reference (IP-Adapter). Generate is disabled when
the backend reports `operations.image_to_image.supported = false` or no source is selected —
img2img is never silently converted to text-to-image.

Status and the metadata asset record `operation = image_to_image`, denoising strength, and
source-image format/dimensions/SHA-256 from the manifest.

## Capability discovery and version compatibility

Before generating, the package fetches `GET /api/v1/capabilities` and caches it in memory for
the current editor session, keyed by backend base URL (`CapabilityCache`). The capability panel
shows:

- Application name/version, model id/family, resolved device/precision, and `model_loaded`
- A capability state: `Unknown`, `Loading`, `Ready`, `Stale` (last known-good, most recent
  refresh failed), `Unavailable`, or `Incompatible`

This package supports public API major `1`, capabilities schema major `1`, and generation
manifest schema major `1` (`Editor/Versioning/ClientCompatibility.cs`). A higher **minor**
version from the backend is accepted (minor bumps are additive); a higher **major** version is
treated as incompatible and **Generate And Import** is disabled with the reason shown in the UI.

Before submitting a request, `GenerationCapabilityValidator` checks it against the fetched
capabilities (dimensions, steps, guidance scale, seed, prompt/negative-prompt/output-name
length, and img2img source/denoising constraints) and reports every violation — it never silently
clamps or rewrites your input.

## Generation manifest and integrity verification

Each generation exposes a versioned manifest at `GET /api/v1/generations/{id}/manifest`
(preferred via the `resources.manifest` link returned from the generation response; the
`/metadata` endpoint is a deprecated alias kept for older backends). The manifest records the
schema version, generation lifecycle, application/model/runtime identity, the request actually
used, and per-output SHA256 + byte size.

Downloaded PNGs are verified against the manifest's SHA256 and byte size
(`ImageIntegrityVerifier`, using `System.Security.Cryptography.SHA256`) **before** anything is
written into `Assets/`. A mismatch is rejected outright rather than imported.

## Import profiles

| Profile | Filter | Mipmaps | Compression | Notes |
|---------|--------|---------|-------------|-------|
| PS1 Pixel Texture | Point | Off | Uncompressed | NPOT scale None |
| Standard Environment Texture | Bilinear | On | Compressed | Typical environment maps |

Sprite and icon imports are explicitly `Single` sprites with native input alpha, clamp wrap,
uncompressed point filtering, and profile-controlled PPU/pivot. Atlas hints are provenance only:
this package does not create sprite sheets or atlases.

## Material creation

When enabled, the package creates a `.mat` under the material destination, assigns the imported texture to `_BaseMap` / `_MainTex` (or `mainTexture` fallback), and fails clearly if the configured shader cannot be found.

## Generated asset layout

```text
Assets/Generated/Textures/
  <name>.png
  Metadata/
    <name>.asset
Assets/Generated/Materials/   # optional
  <name>.mat
```

Conflicts append `_1`, `_2`, … instead of overwriting.

## Metadata and reproducibility

Each import creates a `GenerationMetadataAsset` ScriptableObject with generation ID, prompts, seed, model id/revision, backend elapsed time, retrieval URLs, and a reference to the texture, plus (when a manifest was retrieved) manifest schema version, operation (including `image_to_image`), asset type, status, completed-at, application name/version, API major, model family, device, precision, scheduler, output SHA256/byte size, the request ID, and img2img source-image metadata when present. Absolute backend filesystem paths are never stored — only relative resource paths/URLs.

## Cancellation limitation

**Cancel Wait** aborts the Unity-side wait / download / import pipeline only. It does **not** cancel in-flight GPU inference on the backend. The UI states this clearly.

## Single-generation limitation

The backend serializes generation with one worker. Submit one request at a time from the editor for predictable behavior.

## Security assumptions

- Backend listens on loopback by default.
- Image/metadata retrieval is by UUID generation ID only (no arbitrary path reads).
- Unity path helpers reject `..` and non-`Assets/` destinations.

## Troubleshooting

| Issue | Action |
|-------|--------|
| Connection failed | Start uvicorn; confirm Project Settings URL; check firewall |
| Validation errors | Check the field hints shown once capabilities load (dimensions/steps/etc. vary by backend config) |
| Generate disabled | Click **Refresh Capabilities**; check the reason shown (unavailable vs. incompatible) |
| Incompatible capabilities | Backend's API/schema major version is newer than this package supports — update the package |
| Integrity check failed | Downloaded image didn't match the manifest's SHA256/size; retry the generation |
| Shader not found | Set a shader present in the project (URP Lit, Standard, Unlit/Texture, …) |
| Timeout | Raise API timeout; first model load is slow |

## Edit Mode tests

Open **Window → General → Test Runner → EditMode** and run `UnityAiAssets.Editor.Tests`.
