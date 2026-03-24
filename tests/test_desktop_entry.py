from __future__ import annotations

from parrot_undercover.core import UndercoverMode


class TestUpsertDesktopEntryKey:
    def setup_method(self) -> None:
        self.mgr = UndercoverMode.__new__(UndercoverMode)

    def test_insert_into_existing_section(self) -> None:
        content = "[Desktop Entry]\nName=Test\nExec=test\n"
        result = self.mgr._upsert_desktop_entry_key(content, "NoDisplay", "true")
        assert "NoDisplay=true" in result
        assert result.count("NoDisplay") == 1

    def test_replace_existing_key(self) -> None:
        content = "[Desktop Entry]\nName=Test\nNoDisplay=false\nExec=test\n"
        result = self.mgr._upsert_desktop_entry_key(content, "NoDisplay", "true")
        assert "NoDisplay=true" in result
        assert "NoDisplay=false" not in result

    def test_insert_before_next_section(self) -> None:
        content = "[Desktop Entry]\nName=Test\n[Desktop Action]\nExec=other\n"
        result = self.mgr._upsert_desktop_entry_key(content, "Hidden", "true")
        lines = result.splitlines()
        hidden_idx = next(i for i, line in enumerate(lines) if line == "Hidden=true")
        action_idx = next(i for i, line in enumerate(lines) if line == "[Desktop Action]")
        assert hidden_idx < action_idx

    def test_no_desktop_entry_section_creates_one(self) -> None:
        content = "[Other Section]\nKey=val\n"
        result = self.mgr._upsert_desktop_entry_key(content, "NoDisplay", "true")
        assert "[Desktop Entry]" in result
        assert "NoDisplay=true" in result

    def test_empty_content(self) -> None:
        result = self.mgr._upsert_desktop_entry_key("", "NoDisplay", "true")
        assert "[Desktop Entry]" in result
        assert "NoDisplay=true" in result

    def test_multiple_calls_compose(self) -> None:
        content = "[Desktop Entry]\nName=Test\n"
        result = self.mgr._upsert_desktop_entry_key(content, "NoDisplay", "true")
        result = self.mgr._upsert_desktop_entry_key(result, "X-Managed", "yes")
        assert "NoDisplay=true" in result
        assert "X-Managed=yes" in result

    def test_only_modifies_desktop_entry_section(self) -> None:
        content = "[Desktop Entry]\nName=Test\n[Other]\nName=Other\n"
        result = self.mgr._upsert_desktop_entry_key(content, "NoDisplay", "true")
        lines = result.splitlines()
        other_idx = next(i for i, line in enumerate(lines) if line == "[Other]")
        # NoDisplay should appear before [Other]
        no_display_idx = next(i for i, line in enumerate(lines) if line == "NoDisplay=true")
        assert no_display_idx < other_idx
