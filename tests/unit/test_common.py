"""Unit tests for atlas_session.common.state — file-based state helpers.

Covers:
  TestSessionDir: session_dir() returns correct path
  TestClaudeMd: claude_md() returns correct path
  TestParseMdSections: parse_md_sections() markdown parsing
  TestFindSection: find_section() partial case-insensitive lookup
  TestReadWriteJson: read_json() / write_json() round-trip and edge cases
"""

import pytest

from atlas_session.common.state import (
    find_section,
    parse_md_sections,
    read_json,
    write_json,
)


class TestSessionDir:
    """Tests for the session_dir() function — deleted trivial Path.name tests."""


class TestClaudeMd:
    """Tests for the claude_md() function — deleted trivial Path.name tests."""


class TestParseMdSections:
    """Tests for the parse_md_sections() function."""

    def test_parses_basic_sections(self):
        """Parses ## headings into a dict keyed by heading text."""
        content = (
            "# Title\n"
            "\n"
            "Preamble text.\n"
            "\n"
            "## Section One\n"
            "\n"
            "Content of section one.\n"
            "\n"
            "## Section Two\n"
            "\n"
            "Content of section two.\n"
        )
        sections = parse_md_sections(content)
        assert "## Section One" in sections
        assert "## Section Two" in sections
        assert "Content of section one." in sections["## Section One"]
        assert "Content of section two." in sections["## Section Two"]

    def test_code_blocks_not_treated_as_headings(self):
        """## inside code fences is not treated as a heading."""
        content = (
            "## Real Section\n"
            "\n"
            "Some text.\n"
            "\n"
            "```markdown\n"
            "## This Is Inside Code\n"
            "Not a real heading.\n"
            "```\n"
            "\n"
            "Still in Real Section.\n"
        )
        sections = parse_md_sections(content)
        assert len(sections) == 1
        assert "## Real Section" in sections
        assert "## This Is Inside Code" not in sections
        # The fenced content should be part of the real section body
        assert "Not a real heading." in sections["## Real Section"]

    def test_empty_input_returns_empty_dict(self):
        """Empty string returns an empty dict."""
        assert parse_md_sections("") == {}

    def test_no_sections_returns_empty_dict(self):
        """Content with no ## headings returns an empty dict."""
        content = "# Title\n\nJust a paragraph.\n"
        assert parse_md_sections(content) == {}

    def test_h3_headings_not_split(self):
        """### headings do not create new sections."""
        content = "## Parent\n\n### Child\n\nChild content.\n"
        sections = parse_md_sections(content)
        assert len(sections) == 1
        assert "### Child" not in sections
        assert "Child content." in sections["## Parent"]


class TestFindSection:
    """Tests for the find_section() function."""

    def test_finds_exact_match(self):
        """Exact heading text finds the section."""
        sections = {
            "## Structure Maintenance Rules": "content A",
            "## Ralph Loop": "content B",
        }
        heading, body = find_section(sections, "## Ralph Loop")
        assert heading == "## Ralph Loop"
        assert body == "content B"

    def test_finds_partial_case_insensitive_match(self):
        """Partial, case-insensitive key finds the section."""
        sections = {
            "## Structure Maintenance Rules": "content A",
            "## Ralph Loop": "content B",
        }
        heading, body = find_section(sections, "ralph loop")
        assert heading == "## Ralph Loop"
        assert body == "content B"

    def test_returns_none_when_not_found(self):
        """Returns (None, None) when no heading matches."""
        sections = {
            "## Structure Maintenance Rules": "content A",
        }
        heading, body = find_section(sections, "nonexistent")
        assert heading is None
        assert body is None

    def test_returns_none_on_empty_sections(self):
        """Returns (None, None) when sections dict is empty."""
        heading, body = find_section({}, "anything")
        assert heading is None
        assert body is None

    def test_first_match_wins(self):
        """Returns the first matching section when multiple match."""
        sections = {
            "## Ralph Loop Config": "first",
            "## Ralph Loop Variables": "second",
        }
        heading, body = find_section(sections, "ralph loop")
        assert heading == "## Ralph Loop Config"
        assert body == "first"


class TestReadWriteJson:
    """Tests for read_json() and write_json() round-trip."""

    def test_round_trip(self, tmp_path):
        """write_json then read_json returns the same data."""
        path = tmp_path / "data.json"
        data = {"key": "value", "nested": {"a": 1, "b": [2, 3]}}
        write_json(path, data)
        result = read_json(path)
        assert result == data

    def test_missing_file_returns_empty_dict(self, tmp_path):
        """read_json on a non-existent path returns {}."""
        path = tmp_path / "does_not_exist.json"
        assert read_json(path) == {}

    def test_invalid_json_returns_empty_dict(self, tmp_path):
        """read_json on a file with invalid JSON returns {}."""
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{")
        assert read_json(path) == {}


# =========================================================================
# Hostile Tests — try to break parse_md_sections, find_section, read/write_json
# =========================================================================


class TestParseMdSectionsHostile:
    """Hostile edge cases that try to break the markdown parser."""

    def test_unclosed_code_fence_eats_remaining_headings(self):
        """Unclosed ``` fence should swallow all subsequent ## headings.

        Once in_code_block is True and never toggled back, every subsequent
        ## line is treated as body text rather than a new section.
        """
        content = (
            "## Before Fence\n"
            "\n"
            "Normal content.\n"
            "\n"
            "```python\n"
            "# code here\n"
            "\n"
            "## Swallowed Heading\n"
            "\n"
            "More code.\n"
            "\n"
            "## Also Swallowed\n"
            "\n"
            "Even more.\n"
        )
        sections = parse_md_sections(content)
        # Only one section should exist: the one before the unclosed fence
        assert len(sections) == 1
        assert "## Before Fence" in sections
        # The "## Swallowed Heading" should be body text, not a key
        assert "## Swallowed Heading" not in sections
        assert "## Also Swallowed" not in sections
        # Both swallowed headings should appear inside the body
        body = sections["## Before Fence"]
        assert "Swallowed Heading" in body
        assert "Also Swallowed" in body

    def test_heading_with_special_chars(self):
        """Heading with parentheses, brackets, dashes should parse fine."""
        content = "## Section (deprecated) [v2] -- old\n\nBody text here.\n"
        sections = parse_md_sections(content)
        heading = "## Section (deprecated) [v2] -- old"
        assert heading in sections
        assert "Body text here." in sections[heading]

    def test_empty_section_body(self):
        """Back-to-back ## headings yield sections with only the heading line."""
        content = "## A\n## B\n"
        sections = parse_md_sections(content)
        assert "## A" in sections
        assert "## B" in sections
        # A's body is just its own heading line (no content lines were collected)
        assert sections["## A"].strip() == "## A"

    def test_find_section_ambiguous_match_returns_first(self):
        """When multiple sections match the key, the first in iteration order wins."""
        sections = {
            "## Database Config": "db config body",
            "## Database Migrations": "migrations body",
            "## Cache Config": "cache body",
        }
        # "database" matches both Database sections — first wins
        heading, body = find_section(sections, "database")
        assert heading == "## Database Config"
        assert body == "db config body"

        # "config" matches Database Config AND Cache Config — first wins
        heading, body = find_section(sections, "config")
        assert heading == "## Database Config"
        assert body == "db config body"

    def test_read_json_with_non_dict_json_returns_empty_dict(self, tmp_path):
        """File containing a JSON array (not dict) returns empty dict.

        read_json's return type is dict, so non-dict JSON (arrays, strings,
        numbers) should return {} to honor the type contract.
        """
        path = tmp_path / "array.json"
        path.write_text("[1, 2, 3]")
        result = read_json(path)
        assert result == {}
        assert isinstance(result, dict)

    def test_write_json_raises_when_parent_dir_missing(self, tmp_path):
        """write_json does NOT create parent directories; it raises."""
        path = tmp_path / "nonexistent" / "subdir" / "data.json"
        with pytest.raises(FileNotFoundError):
            write_json(path, {"key": "value"})
