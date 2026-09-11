import sys
from typing import ClassVar

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

    def test_a_glyph_matches_openscads_own_render(self):
        """Calibrated against OpenSCAD on the vendored face, so this holds
        on every platform. `text("H", size=20, font="Liberation Sans")`
        extrudes in OpenSCAD to 121.429 of area in a box 15.52 x 19.11.

        OpenSCAD's own reason for the number: it asks FreeType for the
        size at 100 dpi while the value is in points, which are 1/72 inch.
        Its manual calls that a miscalculation kept for compatibility, and
        notes the accident that `size` then sets capital-letter height.
        """
        shape = text("H", size=20, font="No Such Font, So The Vendored One")
        box = shape.bounding_box()
        assert box.size.Y == pytest.approx(19.11, abs=0.02)
        assert box.size.X == pytest.approx(15.52, abs=0.02)
        assert shape.area == pytest.approx(121.429, rel=0.002)


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

    def test_the_fallback_is_always_available(self):
        """Vendored, so this holds on a stock macOS and on CI, not only
        where someone happened to install Liberation."""
        from solid123d.fonts import FALLBACK_FAMILY, fallback_font_path

        found = fallback_font_path()
        assert found is not None
        assert "liberationsans" in found.name.lower().replace("-", "")
        assert FALLBACK_FAMILY == "Liberation Sans"

    def test_the_vendored_copy_is_shipped(self):
        from solid123d.fonts import _VENDORED

        assert _VENDORED.is_file(), "the vendored font is missing from the package"
        assert (_VENDORED.parent / "LICENSE").is_file(), "OFL requires the licence"

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


class TestTextPlacement:
    """Where OpenSCAD puts a string, measured against it directly.

    build123d has two alignment ideas and only one is OpenSCAD's: `align`
    moves the finished bounding box, `text_align` positions text within
    its own layout, which is where the pen and baseline live. Aligning the
    box put the ink at the origin, so "H" began at 0 where OpenSCAD begins
    at its left side bearing, and "Wg" sat wholly above the axis where
    OpenSCAD lets the g descend.

    Every figure below is OpenSCAD's own render of
    `text("Wg", size=20, font="Liberation Sans")`, the vendored face.
    """

    # (halign, valign): x_min, x_max, y_min, y_max
    OPENSCAD: ClassVar[dict] = {
        ("left", "baseline"): (0.122, 39.875, -5.764, 19.110),
        ("left", "top"): (0.122, 39.875, -24.874, -0.001),
        ("left", "center"): (0.122, 39.875, -12.433, 12.441),
        ("left", "bottom"): (0.122, 39.875, 0.009, 24.882),
        ("center", "baseline"): (-20.711, 19.042, -5.764, 19.110),
        ("center", "top"): (-20.711, 19.042, -24.874, -0.001),
        ("center", "center"): (-20.711, 19.042, -12.433, 12.441),
        ("center", "bottom"): (-20.711, 19.042, 0.009, 24.882),
        ("right", "baseline"): (-41.545, -1.791, -5.764, 19.110),
        ("right", "top"): (-41.545, -1.791, -24.874, -0.001),
        ("right", "center"): (-41.545, -1.791, -12.433, 12.441),
        ("right", "bottom"): (-41.545, -1.791, 0.009, 24.882),
    }

    @pytest.mark.parametrize(("halign", "valign"), sorted(OPENSCAD))
    def test_every_alignment_lands_where_openscad_puts_it(self, halign, valign):
        shape = text("Wg", size=20, font="Liberation Sans",
                     halign=halign, valign=valign)
        box = shape.bounding_box()
        expected = self.OPENSCAD[(halign, valign)]
        got = (box.min.X, box.max.X, box.min.Y, box.max.Y)
        assert got == pytest.approx(expected, abs=0.02)

    def test_the_baseline_is_not_the_ink_bottom(self):
        """The point of the fix: a descender hangs below y=0."""
        shape = text("Wg", size=20, font="Liberation Sans", valign="baseline")
        assert shape.bounding_box().min.Y < -5

    def test_left_leaves_the_side_bearing(self):
        """halign measures the layout box, from the pen to the advance, so
        "H" starts a bearing's width in rather than at zero."""
        shape = text("H", size=20, font="Liberation Sans", halign="left")
        assert shape.bounding_box().min.X == pytest.approx(2.279, abs=0.02)

    def test_horizontal_and_vertical_are_independent(self):
        """Changing valign must not move the string sideways."""
        widths = {
            v: text("Wg", size=20, font="Liberation Sans", valign=v).bounding_box().min.X
            for v in ("baseline", "top", "center", "bottom")
        }
        assert len({round(w, 6) for w in widths.values()}) == 1
