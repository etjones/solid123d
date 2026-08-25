"""Shared helpers for the SolidPython -> build123d bridge.

Boolean operations here use build123d's native operators. Their
seam-related geometry loss (gumyr/build123d#1428) is handled in one
place -- the gated Shape.clean patch in occt_workarounds.py -- so
solid123d's union()/difference(), a user's own ``a + b``, and scad123d
all behave identically.
"""

import math
import warnings
from collections.abc import Iterable, Sequence
from functools import reduce
from operator import add

import webcolors
from build123d import Color, Compound, Shape

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

    # Real overlap: partition instead of fusing. Later children claim
    # contested volume; each earlier child keeps its color on whatever
    # part of it nothing later covers. union(color("red") sphere, cube)
    # thus yields a red sphere-minus-cube body plus the uncolored cube --
    # same total volume as the fuse, but the colors survive.
    return _partitioned_union(shapes, fused)


def _rgba(shape: Shape) -> tuple | None:
    """The color a partitioned piece should carry, as a comparable key."""
    return tuple(shape.color) if shape.color is not None else None


def _color_leaves(shapes: Iterable[Shape]) -> list[Shape]:
    """Expand colorless Compounds whose children carry authored colors,
    so partitioning sees each colored body -- a nested disjoint colored
    group arrives as such a Compound."""
    out: list[Shape] = []
    for shape in shapes:
        if shape._color is None and shape.children and _carries_color(shape):
            out.extend(_color_leaves(list(shape.children)))
        else:
            out.append(shape)
    return out


def _recolored(shape: Shape, rgba: tuple | None, label: str) -> Shape:
    """Booleans drop color and label; restore a piece's own."""
    if rgba is not None:
        shape.color = Color(*rgba)
        shape.label = label or color_label(rgba)
    elif label:
        shape.label = label
    return shape


def _partitioned_union(shapes: list[Shape], fused: Shape) -> Shape:
    """Union overlapping children as touching bodies, colors intact.

    Precedence rule: a ``color()`` region keeps its color wherever no
    later sibling claims the space -- later children clip earlier ones,
    and the last child always survives whole. Runs of adjacent
    same-colored children are fused first, so plain OpenSCAD idioms (a
    union of many uncolored or identically-colored parts) still produce
    a single merged solid per color run.

    The accumulated fuse of all children is the ground truth for
    volume. If partitioning ever loses material, that fuse is returned
    instead: correct geometry beats color fidelity.
    """
    leaves = _color_leaves(shapes)

    coalesced: list[Shape] = []
    for shape in leaves:
        if coalesced and _rgba(coalesced[-1]) == _rgba(shape):
            prev = coalesced[-1]
            coalesced[-1] = _recolored(prev + shape, _rgba(prev), prev.label)
        else:
            coalesced.append(shape)
    if len(coalesced) == 1:
        return coalesced[0]

    kept: list[Shape] = []
    later: Shape | None = None
    for shape in reversed(coalesced):
        if later is None:
            kept.append(shape)
            later = shape
        else:
            clipped = shape - later
            if clipped.volume > 1e-9:
                kept.append(_recolored(clipped, _rgba(shape), shape.label))
            later = later + shape
    kept.reverse()

    if len(kept) == 1:
        return kept[0]
    result = Compound(children=kept)
    if not math.isclose(result.volume, later.volume, rel_tol=1e-6):
        warnings.warn(
            "solid123d: color-preserving union lost volume to a boolean "
            "glitch; returning the plain fused solid without colors",
            stacklevel=3,
        )
        return fused
    return result
