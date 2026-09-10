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

    def test_the_conversion_is_applied(self):
        """Font-independent: whatever font OCCT resolves, our size must
        reach it scaled by the em-to-point ratio and nothing else."""
        from build123d import Text as BdText

        from solid123d.primitives import EM_PER_POINT

        ours = text("H", size=20, halign="center", valign="center")
        scaled = BdText("H", font_size=20 * EM_PER_POINT, align=ours.align)
        assert ours.area == pytest.approx(scaled.area, rel=1e-9)
        assert ours.bounding_box().size.Y == pytest.approx(
            scaled.bounding_box().size.Y, rel=1e-9
        )

    def test_size_scales_linearly(self):
        def height(size: float) -> float:
            return text("H", size=size).bounding_box().size.Y

        assert height(40) / height(10) == pytest.approx(4, rel=1e-6)

    @pytest.mark.skipif(
        find_font_path("Helvetica") is None,
        reason="needs Helvetica, which OpenSCAD was measured against",
    )
    def test_a_glyph_matches_openscads_own_render(self):
        """The numbers this was calibrated against. `text("H", size=20,
        font="Helvetica")` extrudes in OpenSCAD to 133.202 of area, in a
        box 15.81 x 19.93. Skipped where that font is absent, because both
        renderers then substitute and neither figure means anything."""
        shape = text("H", size=20, font="Helvetica", halign="center", valign="center")
        box = shape.bounding_box()
        assert box.size.Y == pytest.approx(19.93, abs=0.02)
        assert box.size.X == pytest.approx(15.81, abs=0.02)
        assert shape.area == pytest.approx(133.202, rel=0.001)


class TestFallbackFont:
    """A model naming a font nobody has must still agree with OpenSCAD.

    OpenSCAD ships the Liberation family and falls back to Liberation Sans
    silently, with no warning at all. OCCT falls back to Arial, a
    different design: the same glyph came out 5% larger in area and
    visibly different. `fontawesome` is the corpus case -- installing the
    real Font Awesome does not help, because OpenSCAD does not match that
    name either and falls back just the same.
    """

    def test_two_unknown_families_land_on_the_same_glyph(self):
        """Whatever the fallback turns out to be, it must not depend on
        which absent family was asked for."""
        one = text("H", size=20, font="No Such Font 123")
        two = text("H", size=20, font="Definitely Not Installed")
        assert one.area == pytest.approx(two.area, rel=1e-9)

    def test_the_fallback_is_liberation_where_one_exists(self):
        from solid123d.fonts import FALLBACK_FAMILY, fallback_font_path

        found = fallback_font_path()
        if found is None:
            pytest.skip("no Liberation Sans installed and no OpenSCAD bundle")
        assert "liberation" in str(found).lower()
        assert FALLBACK_FAMILY == "Liberation Sans"

    @pytest.mark.skipif(
        find_font_path("Liberation Sans") is None,
        reason="needs Liberation Sans, which OpenSCAD was measured against",
    )
    def test_it_matches_openscads_own_render(self):
        """OpenSCAD renders `text("\\u00ef", size=20, font="fontawesome")`
        to 46.925 of area in a box 7.55 x 19.03, having silently fallen
        back. Ours must land on the same glyph."""
        shape = text("ï", size=20, font="fontawesome",
                     halign="center", valign="center")
        box = shape.bounding_box()
        assert shape.area == pytest.approx(46.925, rel=0.001)
        assert box.size.X == pytest.approx(7.55, abs=0.02)
        assert box.size.Y == pytest.approx(19.03, abs=0.02)

    def test_a_font_that_is_installed_is_still_used(self):
        """The fallback must not swallow families that do resolve."""
        installed = find_font_path("Helvetica")
        if installed is None:
            pytest.skip("needs Helvetica")
        real = text("H", size=20, font="Helvetica")
        missing = text("H", size=20, font="No Such Font 123")
        assert real.area != pytest.approx(missing.area, rel=0.01)
