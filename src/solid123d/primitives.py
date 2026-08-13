"""OpenSCAD primitive shapes, emitted as build123d objects.

``segments`` / ``$fn`` style arguments are accepted and ignored:
build123d is a BRep kernel, so curves are exact.
"""

from collections.abc import Sequence

from build123d import Align, Box, Cone, Cylinder, FontStyle, Rectangle, Shape
from build123d import Circle as _BdCircle
from build123d import Polygon as _BdPolygon
from build123d import Sphere as _BdSphere
from build123d import Text as _BdText

from ._common import group, vec3
from .fonts import find_font_path, parse_font_spec

_CENTERED = (Align.CENTER, Align.CENTER, Align.CENTER)
_CORNER = (Align.MIN, Align.MIN, Align.MIN)


def cube(size: float | Sequence[float] = 1, center: bool = False) -> Shape:
    x, y, z = vec3(size)
    return Box(x, y, z, align=_CENTERED if center else _CORNER)


def sphere(
    r: float | None = None,
    d: float | None = None,
    segments: int | None = None,
) -> Shape:
    radius = r if r is not None else (d / 2 if d is not None else 1.0)
    return _BdSphere(radius)


def cylinder(
    r: float | None = None,
    h: float | None = None,
    r1: float | None = None,
    r2: float | None = None,
    center: bool = False,
    d: float | None = None,
    d1: float | None = None,
    d2: float | None = None,
    segments: int | None = None,
) -> Shape:
    base = r if r is not None else (d / 2 if d is not None else None)
    bottom = r1 if r1 is not None else (d1 / 2 if d1 is not None else base)
    top = r2 if r2 is not None else (d2 / 2 if d2 is not None else base)
    bottom = 1.0 if bottom is None else float(bottom)
    top = 1.0 if top is None else float(top)
    height = 1.0 if h is None else float(h)
    z_align = Align.CENTER if center else Align.MIN
    align = (Align.CENTER, Align.CENTER, z_align)
    if bottom == top:
        return Cylinder(bottom, height, align=align)
    return Cone(bottom_radius=bottom, top_radius=top, height=height, align=align)


def square(size: float | Sequence[float] = 1, center: bool = False) -> Shape:
    x, y, _ = vec3(size)
    align = (Align.CENTER, Align.CENTER) if center else (Align.MIN, Align.MIN)
    return Rectangle(x, y, align=align)


def circle(
    r: float | None = None,
    d: float | None = None,
    segments: int | None = None,
) -> Shape:
    radius = r if r is not None else (d / 2 if d is not None else 1.0)
    return _BdCircle(radius)


def polygon(
    points: Sequence[Sequence[float]],
    paths: Sequence[Sequence[int]] | None = None,
    convexity: int | None = None,
) -> Shape:
    pts = [(float(p[0]), float(p[1])) for p in points]
    if paths is None:
        return _BdPolygon(*pts, align=None)
    faces = [
        _BdPolygon(*[pts[i] for i in path], align=None) for path in paths
    ]
    outer = faces[0]
    for hole in faces[1:]:
        outer -= hole
    return outer


_FONT_STYLES = {
    "bold": FontStyle.BOLD,
    "italic": FontStyle.ITALIC,
    "bold italic": FontStyle.BOLDITALIC,
}

_HALIGN = {"left": Align.MIN, "center": Align.CENTER, "right": Align.MAX}
_VALIGN = {
    "baseline": Align.MIN,
    "bottom": Align.MIN,
    "center": Align.CENTER,
    "top": Align.MAX,
}


def text(
    text: str,
    size: float = 10,
    font: str | None = None,
    halign: str = "left",
    valign: str = "baseline",
    spacing: float = 1,
    direction: str = "ltr",
    language: str | None = None,
    script: str | None = None,
    segments: int | None = None,
) -> Shape:
    kwargs: dict[str, object] = {
        "align": (_HALIGN[halign], _VALIGN[valign]),
    }
    if font is not None:
        font_path = find_font_path(font)
        if font_path is not None:
            kwargs["font_path"] = font_path
        else:
            family, style = parse_font_spec(font)
            kwargs["font"] = family
            if style is not None:
                kwargs["font_style"] = _FONT_STYLES.get(
                    style.lower(), FontStyle.REGULAR
                )
    return _BdText(text, font_size=size, **kwargs)
