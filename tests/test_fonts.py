import sys

import pytest

from solid123d import text
from solid123d.fonts import find_font_path, parse_font_spec

macos_only = pytest.mark.skipif(
    sys.platform != "darwin", reason="uses macOS system fonts"
)


class TestParseFontSpec:
    def test_plain_family(self) -> None:
        assert parse_font_spec("Liberation Sans") == ("Liberation Sans", None)

    def test_family_with_style(self) -> None:
        assert parse_font_spec("Arial:style=Bold") == ("Arial", "Bold")

    def test_whitespace(self) -> None:
        assert parse_font_spec(" Arial : style = Bold Italic ") == (
            "Arial",
            "Bold Italic",
        )


@macos_only
class TestFindFontPath:
    def test_nonstandard_subfamily_resolves(self) -> None:
        path = find_font_path("Academy Engraved LET")
        assert path is not None
        assert path.endswith(".ttf")
        assert "Academy" in path

    def test_case_insensitive(self) -> None:
        assert find_font_path("academy engraved let") == find_font_path(
            "Academy Engraved LET"
        )

    def test_style_selection(self) -> None:
        regular = find_font_path("Arial")
        bold = find_font_path("Arial:style=Bold")
        assert regular is not None and bold is not None
        assert regular != bold
        assert "Bold" in bold

    def test_unknown_family_returns_none(self) -> None:
        assert find_font_path("No Such Font Family 123") is None

    def test_unknown_style_returns_none(self) -> None:
        assert find_font_path("Arial:style=No Such Style") is None


@macos_only
class TestTextFontResolution:
    def test_family_name_uses_real_font_not_arial(self) -> None:
        from build123d import Text as BdText

        expected = BdText(
            "Acad",
            font_size=10,
            font_path=(
                "/System/Library/Fonts/Supplemental/Academy Engraved LET Fonts.ttf"
            ),
        ).area
        arial = BdText("Acad", font_size=10, font="Arial").area
        got = text("Acad", size=10, font="Academy Engraved LET").area
        assert got == pytest.approx(expected, rel=1e-6)
        assert got != pytest.approx(arial, rel=0.01)

    def test_unknown_font_still_renders(self) -> None:
        shape = text("hi", size=10, font="No Such Font Family 123")
        assert shape.area > 0
