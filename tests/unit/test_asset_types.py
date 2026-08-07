"""Asset type catalog tests."""

from unity_ai_assets.domain.enums import KNOWN_ASSET_TYPES, AssetType, is_known_asset_type


def test_milestone_four_asset_types_are_known() -> None:
    assert {"texture", "sprite", "icon", "ui"} == KNOWN_ASSET_TYPES
    assert AssetType.SPRITE.value == "sprite"
    assert is_known_asset_type("icon")
    assert not is_known_asset_type("mesh")
