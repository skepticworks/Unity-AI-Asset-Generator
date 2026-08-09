# Getting started

1. Install this package from disk (`unity-package/package.json`).
2. Start the FastAPI backend on `127.0.0.1:8000`.
3. Open **Tools → AI Asset Generator**.
4. Click **Refresh Capabilities** to fetch backend-enforced limits and model/runtime info.
5. Select an asset type and profile, enter a subject, inspect the constructed positive/negative
   prompt preview, then click **Generate And Import**.

Profiles are managed from **Tools → AI Asset Generator → Profiles**. Built-ins are read-only;
duplicate one to customize it. User JSON is stored at
`ProjectSettings/AIAssetGenerator/Profiles/<uuid>.json`, outside `Assets/`. Saves increment the
revision only when material profile fields change.

Texture generation remains supported. Sprite and icon generation use the same pipeline with
explicit transparency strategies. Profiles that require `background_removal` stay disabled until
capabilities report background removal as available. Single-sprite import only — sprite sheets
and automatic atlases are out of scope.
**Generate And Import** is disabled (with an explanation) if capabilities have not loaded yet or
are incompatible with this package version. See the package [README](../README.md) for
capability discovery, version compatibility, the generation manifest, integrity verification,
import profiles, metadata, and troubleshooting.
