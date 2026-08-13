"""Shared helpers for the SolidPython -> build123d bridge."""

from collections.abc import Iterable, Sequence
from functools import reduce
from operator import add

from build123d import Shape

Vec3 = tuple[float, float, float]


def vec3(v: float | Sequence[float], default: float = 0.0) -> Vec3:
    """Expand an OpenSCAD-style scalar or vector into an (x, y, z) tuple."""
    if isinstance(v, (int, float)):
        return (float(v), float(v), float(v))
    vals = [float(x) for x in v]
    while len(vals) < 3:
        vals.append(default)
    return (vals[0], vals[1], vals[2])


def flatten(children: Iterable[object]) -> list[Shape]:
    """Flatten nested lists/tuples of shapes (SolidPython allows both
    ``op()(a, b)`` and ``op()([a, b])``)."""
    out: list[Shape] = []
    for child in children:
        if isinstance(child, (list, tuple)):
            out.extend(flatten(child))
        elif child is not None:
            out.append(child)
    return out


def group(children: Iterable[object]) -> Shape:
    """Combine children the way an OpenSCAD block does: implicit union."""
    shapes = flatten(children)
    if not shapes:
        raise ValueError("expected at least one shape")
    if len(shapes) == 1:
        return shapes[0]
    return reduce(add, shapes)
