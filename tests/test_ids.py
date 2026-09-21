"""Tests for viveka.core.ids."""

from __future__ import annotations

import re

import pytest

from viveka.core.ids import KNOWN_PREFIXES, new_id, short_display

_ID_PATTERN = re.compile(r"^[A-Z]+(-[A-Z0-9]+)?-[0-9A-Z]{26}$")


class TestNewId:
    @pytest.mark.parametrize("prefix", sorted(KNOWN_PREFIXES))
    def test_format_for_all_registered_prefixes(self, prefix: str) -> None:
        uid = new_id(prefix)
        assert uid.startswith(f"{prefix}-"), f"ID {uid!r} does not start with {prefix!r}"
        assert _ID_PATTERN.match(uid), f"ID {uid!r} does not match expected pattern"

    def test_two_ids_are_different(self) -> None:
        assert new_id("VCEX") != new_id("VCEX")

    def test_ids_are_lexicographically_sortable(self) -> None:
        """ULIDs generated in sequence should sort in creation order."""
        ids = [new_id("VTRIAL") for _ in range(10)]
        assert ids == sorted(ids)

    def test_custom_prefix(self) -> None:
        uid = new_id("CUSTOM")
        assert uid.startswith("CUSTOM-")


class TestShortDisplay:
    def test_format(self) -> None:
        full = new_id("VCEX")
        short = short_display(full)
        assert "VCEX" in short
        assert "…" in short
        assert len(short) < len(full)

    def test_passthrough_on_malformed(self) -> None:
        bad = "NOHYPHEN"
        assert short_display(bad) == bad
