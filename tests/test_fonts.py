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

        from solid123d.primitives import EM_PER_POINT

        # build123d's font_size is OCCT's typographic one; text() takes
        # OpenSCAD's em in model units, so the reference is scaled to match.
        em = 10 * EM_PER_POINT
        expected = BdText(
            "Acad",
            font_size=em,
            font_path=(
                "/System/Library/Fonts/Supplemental/Academy Engraved LET Fonts.ttf"
            ),
        ).area
        arial = BdText("Acad", font_size=em, font="Arial").area
        got = text("Acad", size=10, font="Academy Engraved LET").area
        assert got == pytest.approx(expected, rel=1e-6)
        assert got != pytest.approx(arial, rel=0.01)

    def test_unknown_font_still_renders(self) -> None:
        shape = text("hi", size=10, font="No Such Font Family 123")
        assert shape.area > 0


class TestTextSize:
    """OpenSCAD's size is the em square in model units.

    build123d's font_size goes to OCCT, which measures a font the
    typographic way: 72 points to the inch against a 100-unit em. Asking
    for 20 drew a glyph 14.35 tall where OpenSCAD draws 19.93, so every
    string came out 28% short in each direction and 48% short in area.
    """

    @staticmethod
    def measured(size: float, font: str = "Helvetica"):
        shape = text("H", size=size, font=font, halign="center", valign="center")
        return shape.bounding_box(), shape.area

    def test_a_glyph_matches_openscads_own_render(self):
        """Measured against OpenSCAD directly: `text("H", size=20,
        font="Helvetica")` extrudes to 133.202 of area, in a box
        15.81 x 19.93."""
        box, area = self.measured(20)
        assert box.size.Y == pytest.approx(19.93, abs=0.02)
        assert box.size.X == pytest.approx(15.81, abs=0.02)
        assert area == pytest.approx(133.202, rel=0.001)

    def test_arial_too(self):
        """The same, on a second font, so this is the size convention and
        not one font's metrics: 128.879 in a box 15.60 x 19.88."""
        box, area = self.measured(20, "Arial")
        assert box.size.Y == pytest.approx(19.88, abs=0.02)
        assert area == pytest.approx(128.879, rel=0.001)

    def test_size_scales_linearly(self):
        small, _ = self.measured(10)
        large, _ = self.measured(40)
        assert large.size.Y / small.size.Y == pytest.approx(4, rel=1e-6)
