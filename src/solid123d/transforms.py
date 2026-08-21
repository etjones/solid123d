"""OpenSCAD transformations as callables: ``translate(v)(shape, ...)``.

Each function returns a callable that accepts one or more shapes
(children are implicitly unioned, as in an OpenSCAD block) and returns
a transformed build123d shape.
"""

from collections.abc import Callable, Sequence

from build123d import Axis, Color, Kind, Plane, Pos, Shape
from build123d import mirror as _bd_mirror
from build123d import offset as _bd_offset
from build123d import scale as _bd_scale

from ._common import color_label, group, vec3

Applier = Callable[..., Shape]


def translate(v: Sequence[float]) -> Applier:
    x, y, z = vec3(v)

    def apply(*children: Shape) -> Shape:
        return Pos(x, y, z) * group(children)

    return apply


def rotate(
    a: float | Sequence[float] | None = None,
    v: Sequence[float] | None = None,
) -> Applier:
    def apply(*children: Shape) -> Shape:
        shape = group(children)
        if a is not None and not isinstance(a, (int, float)):
            # rotate([x, y, z]): about global X, then Y, then Z (OpenSCAD order)
            ax, ay, az = vec3(a)
            for axis, angle in ((Axis.X, ax), (Axis.Y, ay), (Axis.Z, az)):
                if angle:
                    shape = shape.rotate(axis, angle)
            return shape
        angle = float(a) if a is not None else 0.0
        if v is not None:
            return shape.rotate(Axis((0, 0, 0), tuple(vec3(v))), angle)
        return shape.rotate(Axis.Z, angle)

    return apply


def scale(v: float | Sequence[float]) -> Applier:
    # OpenSCAD pads a short scale vector with 1 (identity), not 0
    factors = vec3(v, default=1.0)

    def apply(*children: Shape) -> Shape:
        return _bd_scale(group(children), by=factors)

    return apply


def mirror(v: Sequence[float]) -> Applier:
    normal = vec3(v)

    def apply(*children: Shape) -> Shape:
        return _bd_mirror(
            group(children), about=Plane(origin=(0, 0, 0), z_dir=normal)
        )

    return apply


def resize(
    newsize: Sequence[float],
    auto: bool | Sequence[bool] = False,
) -> Applier:
    target = vec3(newsize)

    def apply(*children: Shape) -> Shape:
        shape = group(children)
        bbox = shape.bounding_box()
        current = (bbox.size.X, bbox.size.Y, bbox.size.Z)
        autos = (
            (auto, auto, auto) if isinstance(auto, bool) else tuple(auto)
        )
        factors = [
            t / c if t != 0 and c != 0 else 0.0
            for t, c in zip(target, current)
        ]
        first = next((f for f in factors if f != 0), 1.0)
        resolved = tuple(
            f if f != 0 else (first if autos[i] else 1.0)
            for i, f in enumerate(factors)
        )
        return _bd_scale(shape, by=resolved)

    return apply


def color(c: str | Sequence[float], alpha: float = 1.0) -> Applier:
    if isinstance(c, str):
        col = Color(c, alpha=alpha)
        # The author wrote a name -- label with exactly that, no lookup.
        # (scad123d has to reverse-lookup names from rgba because
        # OpenSCAD's CSG export discards them; here the name never leaves.)
        label = c.lower()
    else:
        vals = [float(x) for x in c]
        if len(vals) == 3:
            vals.append(alpha)
        col = Color(*vals)
        label = color_label(vals)

    def apply(*children: Shape) -> Shape:
        shape = group(children)
        shape.color = col
        if not shape.label:
            shape.label = label
        return shape

    return apply


def offset(
    r: float | None = None,
    delta: float | None = None,
    chamfer: bool = False,
) -> Applier:
    amount = r if r is not None else delta
    if amount is None:
        raise ValueError("offset() requires r= or delta=")
    kind = Kind.ARC if r is not None else Kind.INTERSECTION

    def apply(*children: Shape) -> Shape:
        return _bd_offset(group(children), float(amount), kind=kind)

    return apply
