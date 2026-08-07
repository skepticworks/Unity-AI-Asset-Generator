"""Generation API provenance validation tests."""

import pytest
from pydantic import ValidationError

from unity_ai_assets.api.schemas.generation import TextureGenerationRequest


def test_provenance_is_optional_and_does_not_replace_parameters() -> None:
    payload = TextureGenerationRequest(
        prompt="wall",
        width=64,
        generation_profile_id="ps1_environment_texture",
        generation_profile_revision=1,
        profile_origin="builtin",
    )
    assert payload.prompt == "wall"
    assert payload.width == 64
    assert payload.asset_type == "texture"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generation_profile_id", "../bad"),
        ("prompt_template_id", "contains space"),
        ("profile_origin", "remote"),
    ],
)
def test_invalid_provenance_is_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        TextureGenerationRequest.model_validate({"prompt": "wall", field: value})
