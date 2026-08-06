# Getting started

1. Install this package from disk (`unity-package/package.json`).
2. Start the FastAPI backend on `127.0.0.1:8000`.
3. Open **Tools → AI Asset Generator**.
4. Click **Refresh Capabilities** to fetch backend-enforced limits and model/runtime info.
5. Click **Check Backend Connection**, then **Generate And Import**.

**Generate And Import** is disabled (with an explanation) if capabilities have not loaded yet or
are incompatible with this package version. See the package [README](../README.md) for
capability discovery, version compatibility, the generation manifest, integrity verification,
import profiles, metadata, and troubleshooting.
