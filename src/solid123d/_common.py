"""Shared helpers for the SolidPython -> build123d bridge."""

import math
import warnings
from collections.abc import Iterable, Sequence
from functools import reduce
from operator import add

import webcolors
from build123d import Compound, Shape

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


def color_label(rgba: Sequence[float]) -> str:
    """A human-readable name for an rgba value: the exact CSS color name
    when there is one, otherwise the hex string. Used to label shapes so
    parts show up in STEP viewers and slicers under a recognizable name
    instead of OCCT's auto-generated ``COMPOUND``/``SOLID``.
    """
    r, g, b = (round(float(v) * 255) for v in list(rgba)[:3])
    try:
        return webcolors.rgb_to_name((r, g, b))
    except ValueError:
        return f"#{r:02x}{g:02x}{b:02x}"


def _carries_color(shape: Shape) -> bool:
    """Does this shape, or any shape nested under it, have an explicit color?

    Checks the private ``_color`` rather than the ``color`` property: the
    property walks *up* through parents and caches what it finds, so it
    reports inherited color, not authored color -- and it's authored color
    (an explicit ``color()`` call) that signals "these are distinct
    parts". Descends through ``children`` because a nested disjoint colored
    group arrives here as a Compound whose own color is unset but whose
    children carry theirs.
    """
    if shape._color is not None:
        return True
    return any(_carries_color(child) for child in shape.children)


def group(children: Iterable[object]) -> Shape:
    """Combine children the way an OpenSCAD block does: implicit union.

    OpenSCAD refuses to mix 2D and 3D in one group and warns; adding a Face
    to a Solid in build123d silently degenerates instead, so filter
    explicitly and keep the 3D geometry.
    """
    shapes = flatten(children)
    if not shapes:
        raise ValueError("expected at least one shape")
    solid = [s for s in shapes if s.solids()]
    if solid and len(solid) != len(shapes):
        warnings.warn(
            "solid123d: a group mixes 2D and 3D children, which OpenSCAD "
            "does not support; the 2D children were dropped",
            stacklevel=3,
        )
        shapes = solid
    if len(shapes) == 1:
        return shapes[0]

    fused = reduce(add, shapes)

    # Everything below exists only to keep authored color() information
    # alive; a group with no colors anywhere gets the plain fuse -- and
    # skips the mass-property computations, which OCCT reruns from scratch
    # on every access (nothing is cached).
    if not any(_carries_color(s) for s in shapes):
        return fused

    # A real boolean fuse can't tell us which color survives once it's
    # merged overlapping material away -- confirmed directly, it doesn't
    # even keep the first child's color, the result comes back with none.
    # But a fuse is only *necessary* when material actually merged, and
    # volume tells us exactly that: a union's volume equals the naive sum
    # of its children's volumes if and only if the children share zero
    # volume. In that case -- disjoint parts, or parts touching along a
    # shared surface (a part sitting exactly in a cavity cut for it) --
    # return a Compound of the children instead: same total volume, and
    # grouping (unlike fusing) doesn't touch each child's own
    # color/label/material. The colors are evidence the author means these
    # as distinct parts (a multi-material print, an assembly), so touching
    # parts deliberately stay separate bodies rather than getting
    # OpenSCAD's merged-solid union semantics -- that merge is exactly what
    # would destroy the colors.
    #
    # `children=` (not a flat `Compound(shapes)`) matters: it's what makes
    # this an assembly the STEP exporter walks node by node, applying each
    # child's own .color -- a flat Compound with no parent/child tree is
    # treated as one leaf and gets a single color splashed across every
    # solid inside it instead.
    total_volume = sum(s.volume for s in shapes)
    if math.isclose(fused.volume, total_volume, rel_tol=1e-9, abs_tol=1e-9):
        return Compound(children=list(shapes))

    # Real overlap: which color the merged region should be is genuinely
    # undefined without OCCT-level boolean history tracking. No color at
    # all is a worse default than picking one, so fall back to the first
    # child that had one.
    if fused.color is None:
        for s in shapes:
            if s.color is not None:
                fused.color = s.color
                break
    if fused.color is not None and not fused.label:
        fused.label = color_label(tuple(fused.color))
    return fused
