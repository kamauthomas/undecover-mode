from __future__ import annotations

from pathlib import Path

import pytest

from parrot_undercover.core import Preset, UndercoverError

from .conftest import MINIMAL_PRESET, write_preset


class TestPresetFromFile:
    def test_valid_preset(self, tmp_path: Path) -> None:
        path = write_preset(tmp_path, MINIMAL_PRESET)
        preset = Preset.from_file(path)
        assert preset.id == "test"
        assert preset.name == "Test Preset"
        assert preset.color_scheme_asset == "test.colors"
        assert preset.prefer_dark is False
        assert preset.launcher_desktop_ids == ["org.kde.dolphin.desktop"]

    def test_missing_field(self, tmp_path: Path) -> None:
        data = {k: v for k, v in MINIMAL_PRESET.items() if k != "id"}
        path = write_preset(tmp_path, data)
        with pytest.raises(UndercoverError, match="missing required fields.*id"):
            Preset.from_file(path)

    def test_extra_field(self, tmp_path: Path) -> None:
        data = {**MINIMAL_PRESET, "bogus": "value"}
        path = write_preset(tmp_path, data)
        with pytest.raises(UndercoverError, match="unexpected fields.*bogus"):
            Preset.from_file(path)

    def test_empty_string_field(self, tmp_path: Path) -> None:
        data = {**MINIMAL_PRESET, "id": ""}
        path = write_preset(tmp_path, data)
        with pytest.raises(UndercoverError, match="non-empty string"):
            Preset.from_file(path)

    def test_wrong_type_for_list_field(self, tmp_path: Path) -> None:
        data = {**MINIMAL_PRESET, "launcher_desktop_ids": "not-a-list"}
        path = write_preset(tmp_path, data)
        with pytest.raises(UndercoverError, match="must be a list"):
            Preset.from_file(path)

    def test_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(UndercoverError, match="not valid JSON"):
            Preset.from_file(path)

    def test_json_array_instead_of_object(self, tmp_path: Path) -> None:
        path = tmp_path / "arr.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(UndercoverError, match="JSON object"):
            Preset.from_file(path)

    def test_to_dict_roundtrip(self, tmp_path: Path) -> None:
        path = write_preset(tmp_path, MINIMAL_PRESET)
        preset = Preset.from_file(path)
        d = preset.to_dict()
        assert d == MINIMAL_PRESET
