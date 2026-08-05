"""Optional smoke test against the real Diffusers backend.

Run explicitly (downloads model weights if not cached):

    python scripts/smoke_test.py
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure src layout works when executed as a script.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from unity_ai_assets.core.config import Settings, clear_settings_cache  # noqa: E402
from unity_ai_assets.core.logging import configure_logging, get_logger  # noqa: E402
from unity_ai_assets.inference.diffusers_backend import DiffusersBackend  # noqa: E402
from unity_ai_assets.inference.model_manager import ModelManager  # noqa: E402
from unity_ai_assets.services.generation_service import GenerationService  # noqa: E402
from unity_ai_assets.services.output_service import OutputService  # noqa: E402

logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-model smoke test for texture generation")
    parser.add_argument("--prompt", default="seamless rusted metal wall texture, PS1 low poly game")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--output-name", default="smoke_texture")
    args = parser.parse_args()

    clear_settings_cache()
    settings = Settings()
    configure_logging(settings.log_level)

    logger.info(
        "Smoke test starting with model_id=%s device=%s",
        settings.model_id,
        settings.device,
    )
    manager = ModelManager(settings)
    backend = DiffusersBackend(manager)
    output = OutputService(settings.output_directory, app_version=settings.app_version)
    service = GenerationService(backend, output, settings)

    result = service.generate_texture(
        prompt=args.prompt,
        negative_prompt="text, watermark, photo",
        width=args.width,
        height=args.height,
        steps=args.steps,
        guidance_scale=7.0,
        seed=args.seed,
        output_name=args.output_name,
    )

    print(json.dumps(asdict(result), indent=2))
    print(f"Image exists: {Path(result.image_path).is_file()}")
    print(f"Metadata exists: {Path(result.metadata_path).is_file()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
